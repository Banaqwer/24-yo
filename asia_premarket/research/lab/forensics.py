#!/usr/bin/env python3
"""
forensics.py -- loss-cause clustering and Grade-A anatomy for the Asia-session engine (NQ).

Run from the project directory so the engine's own session/feature helpers import:
    cd /home/user/24-yo/asia_premarket && python3 <path to this file>

Inputs (ground truth, never modified):
    research/backtest_trades_NQ.csv   one row per OOS night (call, grade, confidence, variant, best, pnl_pts ...)
    data/NQ_features.csv              features knowable at 18:00 ET
    data/NQ_targets.csv               what Asia did
    data/NQ_sessions.csv              session OHLC incl. eur_high/eur_low and next-day rth_open
    data/NQ_1h.csv                    hourly bars (for the bar-by-bar walk of every trade)
    data/daily_close.csv              KOSPI / N225 daily closes (ex-post Asia-shock proxy)
    research/catalogue_*.csv          agent-researched drivers of every big Asia night

Outputs:
    research/lab/forensics_v0.md               full tables
    research/lab/forensics_graded_NQ.csv       every graded night with reconstructed geometry + flags
    research/lab/forensics_losses_NQ.csv       the losing nights with their cause flags and primary cluster
"""
from __future__ import annotations

import glob
import os
import re
import sys

import numpy as np
import pandas as pd

PROJ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # asia_premarket/
sys.path.insert(0, PROJ)
from sessions import ASIA_HOURS, EUROPE_HOURS, load_hourly  # noqa: E402
from features import wide_stop_distance  # noqa: E402

SYM = "NQ"
LAB = os.path.join(PROJ, "research", "lab")
os.makedirs(LAB, exist_ok=True)
OUT_MD = os.path.join(LAB, "forensics_v0.md")
RNG = np.random.default_rng(7)

# --------------------------------------------------------------------------- load
trades = pd.read_csv(f"{PROJ}/research/backtest_trades_{SYM}.csv", parse_dates=["date"]).set_index("date")
feats = pd.read_csv(f"{PROJ}/data/{SYM}_features.csv", index_col=0, parse_dates=True)
# the CSV snapshot predates the direction-framed columns; derive them exactly as features.py does
_d = np.sign(feats["rth_ret"]).replace(0, 1)
feats["mag"] = feats["rth_ret_z"].abs()
feats["ext_in_dir"] = feats["clv"] * _d
feats["vwap_in_dir"] = feats["close_vs_vwap_rng"] * _d
feats["stretch20_in_dir"] = feats["z_sma20"] * _d
feats["post_in_dir"] = feats["post_ret"] * _d
feats["prior_asia_in_dir"] = feats["prior_asia_ret"] * _d
feats["n225_in_dir"] = feats["n225_ret"] * _d
feats["sox_in_dir"] = feats["sox_minus_nq"] * _d
feats["vix_consistent"] = feats["vix_chg"] * -_d
feats["abs_streak"] = feats["streak"].abs()
tgts = pd.read_csv(f"{PROJ}/data/{SYM}_targets.csv", index_col=0, parse_dates=True)
sess = pd.read_csv(f"{PROJ}/data/{SYM}_sessions.csv", index_col=0, parse_dates=True)
sess["asia_gdate"] = pd.to_datetime(sess["asia_gdate"], errors="coerce")
daily = pd.read_csv(f"{PROJ}/data/daily_close.csv", index_col=0, parse_dates=True)
hourly = load_hourly(f"{PROJ}/data/{SYM}_1h.csv")
cat = pd.concat([pd.read_csv(p) for p in sorted(glob.glob(f"{PROJ}/research/catalogue_*.csv"))], ignore_index=True)
cat["date"] = pd.to_datetime(cat["date"], errors="coerce")
cat = cat.dropna(subset=["date"])
cat = cat.groupby("date").agg(rth_driver=("rth_driver", " | ".join), asia_driver=("asia_driver", " | ".join),
                              tags=("tags", ";".join))
WSD = wide_stop_distance(sess)

# hourly bars grouped by Globex date
h = hourly.copy()
gd = pd.Series(h.index.date, index=h.index)
shift = h.index.hour >= 18
gd[shift] = (h.index[shift] + pd.Timedelta(days=1)).date
h["gdate"] = gd.values
h["hour"] = h.index.hour
ASIA = h[h["hour"].isin(ASIA_HOURS)].groupby("gdate")
EUR = h[h["hour"].isin(EUROPE_HOURS)].groupby("gdate")
# everything after 03:00 on the Asia session's calendar date: Europe 03:00-08:59 then RTH 09:00-15:59
h["cdate"] = h.index.date
AFTER = h[h["hour"].between(3, 15)].groupby("cdate")

graded = trades[trades.grade.isin(["A", "B", "C"])].copy()
assert len(graded) == 196, len(graded)


# --------------------------------------------------------------------------- helpers
def md(df: pd.DataFrame, fmt="{:.2f}", index=True) -> str:
    cols = list(df.columns)
    head = ([df.index.name or ""] if index else []) + [str(c) for c in cols]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for i, r in df.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                vals.append("" if pd.isna(v) else fmt.format(v))
            elif isinstance(v, (bool, np.bool_)):
                vals.append("yes" if v else "")
            else:
                vals.append("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
        lines.append("| " + " | ".join(([str(i)[:10] if isinstance(i, pd.Timestamp) else str(i)] if index else []) + vals) + " |")
    return "\n".join(lines)


def first_touch(bars: pd.DataFrame, side: str, target: float, stop: float):
    """Index (0-based bar number) and hour of the first bar touching target / stop. None if never."""
    stop_i = tgt_i = None
    stop_h = tgt_h = None
    for i, (ts, b) in enumerate(bars.iterrows()):
        if side == "LONG":
            s_hit, t_hit = b["Low"] <= stop, b["High"] >= target
        else:
            s_hit, t_hit = b["High"] >= stop, b["Low"] <= target
        if s_hit and stop_i is None:
            stop_i, stop_h = i, ts.hour
        if t_hit and tgt_i is None:
            tgt_i, tgt_h = i, ts.hour
        if stop_i is not None and tgt_i is not None:
            break
    return stop_i, tgt_i, stop_h, tgt_h


def resolve(kind: str, stop_i, tgt_i) -> str:
    """Engine resolution semantics. Fade: a bar touching both counts as stopped. Continuation: the mirror image
    (the fade's 'stopped' flag is the continuation's win), so a both-in-one-bar bar counts as a WIN."""
    if kind == "MEAN REVERSION":
        if tgt_i is not None and (stop_i is None or tgt_i < stop_i):
            return "target"
        if stop_i is not None:
            return "stop"
        return "scratch"
    else:
        if tgt_i is not None and (stop_i is None or tgt_i <= stop_i):
            return "target"
        if stop_i is not None:
            return "stop"
        return "scratch"


def pnl_from(res: str, side: str, entry: float, target: float, stop: float, scratch_pts: float) -> float:
    """Engine convention: target/stop pay their distance from `entry`; a scratch pays `scratch_pts`
    (the engine values it as the Asia open-to-close return in the trade direction times the 17:00 close)."""
    if res == "target":
        return abs(target - entry)
    if res == "stop":
        return -abs(stop - entry)
    return scratch_pts


def next_move(series: pd.Series, d: pd.Timestamp, max_days=4):
    s = series.dropna()
    s = s[~s.index.duplicated()]
    r = s.pct_change()
    nxt = r[(r.index > d) & (r.index <= d + pd.Timedelta(days=max_days))]
    return float(nxt.iloc[0]) if len(nxt) else np.nan


# --------------------------------------------------------------------------- 1. reconstruct every graded trade
rows = []
for d, tr in graded.iterrows():
    r = sess.loc[d]
    up = (r["rth_close"] - r["rth_open"]) > 0
    move = r["rth_close"] - r["rth_open"]
    rng = r["rth_high"] - r["rth_low"]
    entry = r["post_close"] if not pd.isna(r.get("post_close")) else r["rth_close"]
    wsd = WSD.get(d, np.nan)
    stops = {"tight": r["rth_high"] + 0.10 * rng if up else r["rth_low"] - 0.10 * rng}
    if not pd.isna(wsd):
        stops["wide"] = entry + wsd if up else entry - wsd
    tg = {"vwap": r["rth_vwap"], "r382": r["rth_close"] - 0.382 * move, "r500": r["rth_close"] - 0.5 * move}
    kind = tr["call"]
    if kind == "MEAN REVERSION":
        target, stop = tg[tr["best"]], stops[tr["variant"]]
        side = "SHORT" if up else "LONG"
    else:
        target, stop = stops[tr["variant"]], tg["vwap"]
        side = "LONG" if up else "SHORT"
    sgn = 1.0 if side == "LONG" else -1.0
    gdate = r["asia_gdate"]
    bars = ASIA.get_group(gdate.date()) if (not pd.isna(gdate) and gdate.date() in ASIA.groups) else None
    rec = dict(date=d, grade=tr.grade, confidence=tr.confidence, call=kind, side=side, variant=tr.variant, best=tr.best,
               pnl_pts=tr.pnl_pts, entry=entry, target=target, stop=stop,
               target_dist=abs(target - entry), stop_dist=abs(stop - entry), rth_ret=tr.rth_ret,
               rth_range_pts=rng, asia_open=r["asia_open"], asia_close=r["asia_close"],
               asia_rng_pts=r["asia_high"] - r["asia_low"], asia_n_bars=r["asia_n_bars"])
    if bars is not None:
        stop_i, tgt_i, stop_h, tgt_h = first_touch(bars, side, target, stop)
        res = resolve(kind, stop_i, tgt_i)
        scratch_engine = sgn * (r["asia_close"] / r["asia_open"] - 1) * entry
        rec.update(res=res, stop_i=stop_i, tgt_i=tgt_i, stop_hour=stop_h, tgt_hour=tgt_h,
                   same_bar=(stop_i is not None and tgt_i is not None and stop_i == tgt_i),
                   whipsaw=(res == "stop" and tgt_i is not None and tgt_i > stop_i),
                   decided_bar=min([x for x in (stop_i, tgt_i) if x is not None], default=np.nan),
                   pnl_recon=pnl_from(res, side, entry, target, stop, scratch_engine),
                   mfe=(bars["High"].max() - entry) if side == "LONG" else (entry - bars["Low"].min()),
                   mae=(entry - bars["Low"].min()) if side == "LONG" else (bars["High"].max() - entry),
                   gap_18_in_dir=sgn * (r["asia_open"] - entry),
                   move_18_20_in_dir=sgn * (bars["Close"].iloc[1] - bars["Open"].iloc[0]) if len(bars) > 1 else np.nan)
        # P&L if the fill were the 18:00 open rather than the 17:00 close (same levels)
        ao = r["asia_open"]
        past_t = (ao >= target) if side == "LONG" else (ao <= target)
        past_s = (ao <= stop) if side == "LONG" else (ao >= stop)
        rec["open_past_target"], rec["open_past_stop"] = bool(past_t), bool(past_s)
        # scratch nights: mark-to-market at the close of bar k (engine convention) to test an earlier time stop
        if res == "scratch":
            for k_, lbl in [(1, "20"), (3, "22"), (5, "00")]:
                if len(bars) > k_:
                    rec[f"scratch_at_{lbl}"] = sgn * (bars["Close"].iloc[k_] / r["asia_open"] - 1) * entry
        # FULL time-stop counterfactual: keep the engine's resolution if it happened in bars 0-1 (18:00, 19:00),
        # otherwise mark the open position at the 20:00 close (bar-1 close), engine convention
        for k_, lbl in [(1, "20"), (3, "22")]:
            if len(bars) > k_:
                dec = min([x for x in (stop_i, tgt_i) if x is not None], default=None)
                if dec is not None and dec <= k_:
                    rec[f"pnl_timestop_{lbl}"] = rec["pnl_recon"]
                else:
                    rec[f"pnl_timestop_{lbl}"] = sgn * (bars["Close"].iloc[k_] / r["asia_open"] - 1) * entry
        rec["pnl_open_fill"] = 0.0 if (past_t or past_s) else pnl_from(res, side, ao, target, stop, sgn * (r["asia_close"] - ao))
        # 20:00 entry (after the Seoul/Tokyo open): same levels, walk from bar 2
        if len(bars) > 2:
            b2 = bars.iloc[2:]
            e2 = b2["Open"].iloc[0]
            p_t = (e2 >= target) if side == "LONG" else (e2 <= target)
            p_s = (e2 <= stop) if side == "LONG" else (e2 >= stop)
            if p_t or p_s or (stop_i is not None and stop_i < 2) or (tgt_i is not None and tgt_i < 2):
                rec["pnl_entry20"] = np.nan   # already resolved / level already crossed before 20:00
            else:
                si, ti, _, _ = first_touch(b2, side, target, stop)
                rec["pnl_entry20"] = pnl_from(resolve(kind, si, ti), side, e2, target, stop, sgn * (r["asia_close"] - e2))
        # counterfactual: the same target with the wide stop (for tight-stop fades)
        if kind == "MEAN REVERSION" and "wide" in stops:
            si, ti, _, _ = first_touch(bars, side, target, stops["wide"])
            rec["pnl_wide_cf"] = pnl_from(resolve(kind, si, ti), side, entry, target, stops["wide"], scratch_engine)
        # Europe follow-through (03:00-09:00) and the next RTH
        eb = EUR.get_group(gdate.date()) if gdate.date() in EUR.groups else None
        if eb is not None and len(eb):
            esi, eti, _, _ = first_touch(eb, side, target, stop)
            rec["eur_target_first"] = (eti is not None and (esi is None or eti < esi))
            rec["eur_target_touched"] = eti is not None
            rec["eur_close"] = eb["Close"].iloc[-1]
            # hold-through-Europe counterfactual for scratches: resolve in Europe, else close at 09:00
            if res == "scratch":
                rec["pnl_hold_eur"] = pnl_from(resolve(kind, esi, eti), side, entry, target, stop,
                                               sgn * (eb["Close"].iloc[-1] / r["asia_open"] - 1) * entry)
        # hold-through-next-RTH-close: first touch of target vs stop over Europe + next RTH (same calendar date)
        ab = AFTER.get_group(gdate.date()) if gdate.date() in AFTER.groups else None
        if ab is not None and len(ab) >= 6:
            hsi, hti, _, hth = first_touch(ab, side, target, stop)
            hres = "target" if (hti is not None and (hsi is None or hti < hsi)) else ("stop" if hsi is not None else "none")
            rec["hold_res"] = hres
            rec["hold_target_hour"] = hth if hres == "target" else np.nan
            if res == "scratch":
                rec["pnl_hold_next"] = pnl_from(hres if hres != "none" else "scratch", side, entry, target, stop,
                                                sgn * (ab["Close"].iloc[-1] / r["asia_open"] - 1) * entry)
    pos = sess.index.get_loc(d)
    if pos + 1 < len(sess):
        nr = sess.iloc[pos + 1]
        rec["next_rth_date"] = sess.index[pos + 1]
        rec["next_open_past_target"] = (nr["rth_open"] >= target) if side == "LONG" else (nr["rth_open"] <= target)
        rec["next_rth_touched_target"] = (nr["rth_high"] >= target) if side == "LONG" else (nr["rth_low"] <= target)
    rows.append(rec)

G = pd.DataFrame(rows).set_index("date")
G["win"] = G.pnl_pts > 0
G["quarter"] = G.index.to_period("Q").astype(str)
# verify the reconstruction reproduces the engine's P&L
G["recon_err"] = (G.pnl_recon - G.pnl_pts).abs()
assert G.recon_err.max() < 1e-6, G[G.recon_err > 1e-6][["call", "variant", "best", "pnl_pts", "pnl_recon"]]

# join features / targets / catalogue
FCOLS = ["mag", "ext_in_dir", "vwap_in_dir", "vix_consistent", "vix", "vix_z20", "vix_chg", "rv_ratio", "rth_range_atr",
         "post_ret", "post_in_dir", "megacap_earnings_tonight", "sunday_open", "pre_holiday", "dow", "stretch20_in_dir",
         "asia_rng_med20", "abs_streak", "tier1_data_tomorrow", "fomc_today", "boj_tonight", "cn_data_tonight",
         "events_today", "events_tonight_tomorrow", "prior_asia_in_dir", "n225_in_dir", "sox_in_dir", "rth_vol_rel"]
G = G.join(feats[FCOLS]).join(tgts[["asia_ret", "asia_rng", "retrace_frac", "continued", "reverted"]])
G = G.join(cat, how="left")
G["in_catalogue"] = G.tags.notna()
G["kospi_next"] = [next_move(daily["KOSPI"], d) for d in G.index]
G["n225_next"] = [next_move(daily["N225"], d) for d in G.index]
G["stop_vs_realised"] = G.stop_dist / G.asia_rng_pts
G["target_vs_realised"] = G.target_dist / G.asia_rng_pts
G["stop_vs_expected"] = G.stop_dist / (G.asia_rng_med20 * G.entry)
G["rr"] = G.target_dist / G.stop_dist
# trailing engine form known at 18:00 (previous 20 graded trades)
G = G.sort_index()
G["trail20_wr"] = G.win.astype(float).shift(1).rolling(20, min_periods=10).mean()

# --------------------------------------------------------------------------- 2. catalyst classification
ASIA_KW = re.compile(r"kospi|kosdaq|nikkei|topix|sidecar|circuit|halt|\bboj\b|jgb|\bmof\b|intervention|taiex|tsmc|samsung|hynix|softbank|pboc|csi ?300|hang seng|\bhsi\b|\brba\b|seoul|tokyo|korea|japan|china|takaichi|katayama", re.I)
AH_KW = re.compile(r"\bah\b|after[- ]hours|after the close|post-earnings|earnings|guid(e|ance)|reported|\bbeat\b|\bmiss(ed)?\b", re.I)
HEAD_KW = re.compile(r"trump|iran|hormuz|tariff|truth social|strike|ceasefire|brent|\bwti\b|\boil\b|houthi|\bwar\b|\bwsj\b|\bnyt\b|headline|probe|election|midterm|sanders|moratorium|bessent", re.I)
USMACRO_KW = re.compile(r"fomc|\bfed\b|warsh|\bcpi\b|\bnfp\b|payroll|\bpce\b|yield|treasury|10y|30y|auction|powell", re.I)


def classify_driver(txt):
    if not isinstance(txt, str):
        return ""
    kinds = []
    if AH_KW.search(txt):
        kinds.append("after-hours print")
    if ASIA_KW.search(txt):
        kinds.append("Asia-origin")
    if HEAD_KW.search(txt):
        kinds.append("headline")
    if USMACRO_KW.search(txt):
        kinds.append("US macro/rates")
    return "+".join(kinds)


G["driver_kind"] = G.asia_driver.map(classify_driver)
G["ah_shock_proxy"] = (G.post_ret.abs() > 0.003) | (G.megacap_earnings_tonight == 1)
G["asia_shock_expost"] = (G.kospi_next.abs() > 0.02) | (G.n225_next.abs() > 0.02)

# --------------------------------------------------------------------------- 3. cause flags for every losing night
L = G[G.pnl_pts <= 0].copy()
assert len(L) == 87, len(L)
L["f_artefact_samebar"] = L.same_bar.fillna(False).astype(bool)
L["f_artefact_thin"] = (L.asia_n_bars < 9)
L["f_calendar_sunday"] = (L.sunday_open == 1)
L["f_calendar_holiday"] = (L.pre_holiday == 1) | L.tags.fillna("").str.contains("holiday_thin")
L["f_catalyst_catalogue"] = L.in_catalogue
L["f_catalyst_ah"] = L.ah_shock_proxy.fillna(False).astype(bool)
L["f_catalyst_asia_expost"] = L.asia_shock_expost.fillna(False).astype(bool)
L["f_geom_whipsaw"] = L.whipsaw.fillna(False).astype(bool)
L["f_geom_stop_lt_third_range"] = (L.res == "stop") & (L.stop_vs_realised < 0.34)
L["f_geom_target_beyond_range"] = (L.res == "scratch") & (L.target_vs_realised > 1.0)
L["f_geom_stopped_before_move"] = (L.res == "stop") & (L.whipsaw.fillna(False).astype(bool) | L.eur_target_first.fillna(False).astype(bool))
L["f_timing_scratch_then_target"] = (L.res == "scratch") & (L.hold_res == "target")
L["f_timing_eur_touch_any"] = L.eur_target_touched.fillna(False).astype(bool) & (L.res != "target")
L["f_timing_nextrth_touch_any"] = (L.next_open_past_target.fillna(False) | L.next_rth_touched_target.fillna(False)).astype(bool) & (L.res != "target")
L["f_regime_vol"] = (L.vix > 25) | (L.vix_z20 > 1.5) | (L.rv_ratio > 1.5)
L["f_regime_form"] = (L.trail20_wr < 0.45)
L["f_calib_midband"] = (L.confidence >= 56) & (L.confidence < 72)


def primary(r):
    if r.f_artefact_samebar:
        return "f) data artefact: target+stop in one hourly bar (ambiguous first-hit)"
    if r.f_catalyst_catalogue or r.f_catalyst_ah:
        return "c) catalyst (catalogue driver / after-hours print)"
    if r.f_geom_stopped_before_move:
        return "a) geometry: stopped, then the target was reached (Asia whipsaw or Europe target-first)"
    if r.f_timing_scratch_then_target:
        return "e) timing: scratch at 03:00, target hit before stop in Europe / next RTH"
    if r.f_geom_stop_lt_third_range or r.f_geom_target_beyond_range:
        return "a) geometry: stop < 1/3 of realised range or target beyond realised range"
    # NOTE: the ex-post KOSPI/N225 > 2% flag is deliberately NOT a primary cause: it is as common on winning nights
    # (see table 1a, lift ~0.9), so it explains nothing. It is reported as a flag only.
    if r.f_calendar_sunday or r.f_calendar_holiday or r.f_artefact_thin:
        return "f) calendar: Sunday reopen / holiday / thin session"
    if r.f_regime_vol or r.f_regime_form:
        return "b) regime: VIX>25 / vix_z>1.5 / rv_ratio>1.5 / trailing form <45%"
    if r.f_calib_midband:
        return "d) calibration: mid-band confidence only"
    return "g) unexplained"


L["primary"] = L.apply(primary, axis=1)
FLAGS = [c for c in L.columns if c.startswith("f_")]

# --------------------------------------------------------------------------- 4. tables
Lsum = L.groupby("primary").agg(n=("pnl_pts", "size"), pts=("pnl_pts", "sum"), avg=("pnl_pts", "mean"),
                                 A=("grade", lambda x: (x == "A").sum()), B=("grade", lambda x: (x == "B").sum()),
                                 C=("grade", lambda x: (x == "C").sum()))
Lsum["share_n"] = Lsum.n / len(L)
Lsum["share_pts"] = Lsum.pts / L.pnl_pts.sum()
Lsum = Lsum.sort_values("n", ascending=False)

flag_counts = pd.DataFrame({"n_losses": L[FLAGS].sum(), "share": L[FLAGS].mean(),
                            "pts": [L.loc[L[c], "pnl_pts"].sum() for c in FLAGS],
                            "A_losses": [int((L.loc[L[c], "grade"] == "A").sum()) for c in FLAGS]})
# base rates of the same conditions among WINNING graded nights (does the flag discriminate, or is it just common?)
W = G[G.pnl_pts > 0]
base = {
    "f_calendar_sunday": (W.sunday_open == 1).mean(),
    "f_calendar_holiday": (W.pre_holiday == 1).mean(),
    "f_catalyst_catalogue": W.in_catalogue.mean(),
    "f_catalyst_ah": W.ah_shock_proxy.fillna(False).mean(),
    "f_catalyst_asia_expost": W.asia_shock_expost.fillna(False).mean(),
    "f_regime_vol": ((W.vix > 25) | (W.vix_z20 > 1.5) | (W.rv_ratio > 1.5)).mean(),
    "f_regime_form": (W.trail20_wr < 0.45).mean(),
    "f_calib_midband": ((W.confidence >= 56) & (W.confidence < 72)).mean(),
    "f_artefact_thin": (W.asia_n_bars < 9).mean(),
}
flag_counts["share_among_wins"] = pd.Series(base).reindex(flag_counts.index)
flag_counts["lift_vs_wins"] = flag_counts.share / flag_counts.share_among_wins
# catalyst sub-classification: was the driver knowable at 18:00 ET?
Lc = L[L.f_catalyst_catalogue | L.f_catalyst_ah].copy()
def knowable(r):
    k = []
    if r.f_catalyst_ah or "after-hours print" in str(r.driver_kind):
        k.append("after-hours print (known 16:05-17:00)")
    if r.sunday_open == 1 and ("headline" in str(r.driver_kind)):
        k.append("weekend headline (known by Sunday 17:00)")
    if any(int(r.get(c, 0) or 0) == 1 for c in ["boj_tonight", "cn_data_tonight", "fomc_today", "tier1_data_tomorrow"]):
        k.append("scheduled event flag already in the model")
    if "Asia-origin" in str(r.driver_kind) and not k:
        k.append("Asia-origin, only visible at the 19:00-20:00 Seoul/Tokyo open")
    if not k:
        k.append("intra-session headline (Trump/Iran/oil) or unflagged")
    return "; ".join(k)
Lc["knowable_at_18"] = Lc.apply(knowable, axis=1)
know_tab = Lc.groupby("knowable_at_18").agg(n=("pnl_pts", "size"), pts=("pnl_pts", "sum"), A=("grade", lambda x: (x == "A").sum()))
driver_tab = Lc.driver_kind.replace("", "not in catalogue (after-hours proxy only)").str.split("+").explode().value_counts().rename("n").to_frame()
tag_tab = Lc.tags.dropna().str.split(";").explode().value_counts().rename("n").to_frame()

by_res = G.groupby(["grade", "res"]).agg(n=("pnl_pts", "size"), avg=("pnl_pts", "mean"), pts=("pnl_pts", "sum"))
loss_by_res = L.groupby(["grade", "call", "variant", "res"]).agg(n=("pnl_pts", "size"), pts=("pnl_pts", "sum"), avg=("pnl_pts", "mean"))

# quarter concentration of losses and of the whole graded set
q = G.groupby(["quarter"]).agg(n=("pnl_pts", "size"), win=("win", "mean"), pts=("pnl_pts", "sum"))
qa = G[G.grade == "A"].groupby("quarter").agg(A_n=("pnl_pts", "size"), A_win=("win", "mean"), A_pts=("pnl_pts", "sum"))
ql = L.groupby("quarter").agg(losses=("pnl_pts", "size"), loss_pts=("pnl_pts", "sum"))
qtab = q.join(qa).join(ql)

# ------------------------------------------------------------------ 5. hypothesis counterfactuals (in-sample, exploratory)
H = {}
# H1 geometry: tight-stop fade losses -> wide stop, same target
m = (G.call == "MEAN REVERSION") & (G.variant == "tight") & G.pnl_wide_cf.notna()
sub = G[m]
H["wide_stop_all_tight_fades"] = dict(n=int(m.sum()), engine_pts=float(sub.pnl_pts.sum()), cf_pts=float(sub.pnl_wide_cf.sum()),
                                     engine_win=float(sub.win.mean()), cf_win=float((sub.pnl_wide_cf > 0).mean()))
ml = m & (G.pnl_pts <= 0)
H["wide_stop_tight_fade_losses"] = dict(n=int(ml.sum()), converted=int((G.loc[ml, "pnl_wide_cf"] > 0).sum()),
                                       engine_pts=float(G.loc[ml, "pnl_pts"].sum()), cf_pts=float(G.loc[ml, "pnl_wide_cf"].sum()))
# H2 timing: scratch nights held through Europe (close 09:00) or through the next RTH close, first-touch semantics
ms = (G.res == "scratch") & G.pnl_hold_eur.notna()
H["hold_eur_all_scratches"] = dict(n=int(ms.sum()), engine_pts=float(G.loc[ms, "pnl_pts"].sum()), cf_pts=float(G.loc[ms, "pnl_hold_eur"].sum()),
                                   engine_win=float((G.loc[ms, "pnl_pts"] > 0).mean()), cf_win=float((G.loc[ms, "pnl_hold_eur"] > 0).mean()))
mn = (G.res == "scratch") & G.pnl_hold_next.notna()
H["hold_nextRTH_all_scratches"] = dict(n=int(mn.sum()), engine_pts=float(G.loc[mn, "pnl_pts"].sum()), cf_pts=float(G.loc[mn, "pnl_hold_next"].sum()),
                                       engine_win=float((G.loc[mn, "pnl_pts"] > 0).mean()), cf_win=float((G.loc[mn, "pnl_hold_next"] > 0).mean()))
for g in ["A", "B", "C"]:
    mg = mn & (G.grade == g)
    H[f"hold_nextRTH scratches grade {g}"] = dict(n=int(mg.sum()), engine_pts=float(G.loc[mg, "pnl_pts"].sum()), cf_pts=float(G.loc[mg, "pnl_hold_next"].sum()),
                                                 engine_win=float((G.loc[mg, "pnl_pts"] > 0).mean()) if mg.sum() else np.nan,
                                                 cf_win=float((G.loc[mg, "pnl_hold_next"] > 0).mean()) if mg.sum() else np.nan)
hold_res_tab = G[G.res == "scratch"].groupby(["grade", "hold_res"]).agg(n=("pnl_pts", "size"), engine_pts=("pnl_pts", "sum"), hold_pts=("pnl_hold_next", "sum"))
# H2b: the opposite of holding longer: a time stop for scratches (mark at 20:00 / 22:00 / 00:00 instead of 03:00)
for lbl in ["20", "22", "00"]:
    c_ = f"scratch_at_{lbl}"
    mm = (G.res == "scratch") & G[c_].notna()
    H[f"time-stop scratches at {lbl}:00 (all)"] = dict(n=int(mm.sum()), engine_pts=float(G.loc[mm, "pnl_pts"].sum()), cf_pts=float(G.loc[mm, c_].sum()),
                                                     engine_win=float((G.loc[mm, "pnl_pts"] > 0).mean()), cf_win=float((G.loc[mm, c_] > 0).mean()))
    ma = mm & (G.grade == "A")
    H[f"time-stop scratches at {lbl}:00 (A)"] = dict(n=int(ma.sum()), engine_pts=float(G.loc[ma, "pnl_pts"].sum()), cf_pts=float(G.loc[ma, c_].sum()),
                                                   engine_win=float((G.loc[ma, "pnl_pts"] > 0).mean()), cf_win=float((G.loc[ma, c_] > 0).mean()))
# H2c: FULL time-stop (every graded trade; resolved in bars 0-1 as engine, else marked at the 20:00 / 22:00 close)
half = G.index[len(G) // 2]
ts_rows = {}
for lbl in ["20", "22"]:
    c_ = f"pnl_timestop_{lbl}"
    for g_, mg in [("all graded", pd.Series(True, index=G.index)), ("A", G.grade == "A"), ("B", G.grade == "B"), ("C", G.grade == "C"),
                   ("A first half", (G.grade == "A") & (G.index < half)), ("A second half", (G.grade == "A") & (G.index >= half)),
                   ("A mean reversion", (G.grade == "A") & (G.call == "MEAN REVERSION")), ("A continuation", (G.grade == "A") & (G.call == "CONTINUATION"))]:
        mm = mg & G[c_].notna()
        ts_rows[f"time-stop {lbl}:00 | {g_}"] = dict(n=int(mm.sum()), engine_pts=float(G.loc[mm, "pnl_pts"].sum()), cf_pts=float(G.loc[mm, c_].sum()),
                                                    engine_win=float(G.loc[mm, "win"].mean()), cf_win=float((G.loc[mm, c_] > 0).mean()),
                                                    engine_avg=float(G.loc[mm, "pnl_pts"].mean()), cf_avg=float(G.loc[mm, c_].mean()),
                                                    cf_worst=float(G.loc[mm, c_].min()))
timestop_tab = pd.DataFrame(ts_rows).T
# geometry: win rate by target distance relative to the EX-ANTE expected range (20d median Asia range, known at 18:00)
G["target_vs_expected"] = G.target_dist / (G.asia_rng_med20 * G.entry)
tb = pd.cut(G.target_vs_expected, [0, 0.3, 0.5, 0.7, 1.0, 10])
geom_tab = G.groupby([tb, "grade"], observed=True).agg(n=("win", "size"), win=("win", "mean"), avg=("pnl_pts", "mean"), pts=("pnl_pts", "sum"))
sb = pd.cut(G.stop_vs_expected, [0, 0.5, 0.75, 1.0, 1.5, 10])
geom_stop_tab = G.groupby([sb, "grade"], observed=True).agg(n=("win", "size"), win=("win", "mean"), avg=("pnl_pts", "mean"), pts=("pnl_pts", "sum"))
# the tail: worst 10 graded losses and what the 18:00-20:00 sub-session had done
worst = G.nsmallest(10, "pnl_pts")[["grade", "confidence", "call", "variant", "best", "pnl_pts", "res", "decided_bar", "move_18_20_in_dir", "gap_18_in_dir", "in_catalogue", "driver_kind"]]
# all-graded P&L with and without the ex-ante exclusion flags
excl = {}
for lbl, cond in [("after-hours shock (|post_ret|>0.3% or megacap earnings tonight)", G.ah_shock_proxy.fillna(False).astype(bool)),
                  ("pre-holiday / thin session (<9 Asia bars)", (G.pre_holiday == 1) | (G.asia_n_bars < 9)),
                  ("Sunday reopen", G.sunday_open == 1),
                  ("wide-stop variant", G.variant == "wide"),
                  ("grade B or C", G.grade.isin(["B", "C"]))]:
    for g_, m_ in [("all graded", pd.Series(True, index=G.index)), ("A only", G.grade == "A")]:
        s_in, s_out = G[cond & m_], G[~cond & m_]
        excl[(lbl, g_)] = dict(n_flagged=len(s_in), win_flagged=s_in.win.mean() if len(s_in) else np.nan, pts_flagged=s_in.pnl_pts.sum(),
                               n_rest=len(s_out), win_rest=s_out.win.mean() if len(s_out) else np.nan, pts_rest=s_out.pnl_pts.sum())
excl_tab = pd.DataFrame(excl).T
excl_tab.index = [f"{a} | {b}" for a, b in excl_tab.index]
# H3 sub-session: enter at 20:00 (after Seoul/Tokyo open) instead of 18:00, unconditional and conditioned on the 18-20 move
m20 = G.pnl_entry20.notna()
H["entry20_unconditional"] = dict(n=int(m20.sum()), engine_pts_same_nights=float(G.loc[m20, "pnl_pts"].sum()),
                                  cf_pts=float(G.loc[m20, "pnl_entry20"].sum()),
                                  resolved_before_20=int((~m20).sum()))
for lbl, cond in [("18-20 move WITH trade", G.move_18_20_in_dir > 0), ("18-20 move AGAINST trade", G.move_18_20_in_dir <= 0)]:
    mm = m20 & cond
    H[f"entry20 | {lbl}"] = dict(n=int(mm.sum()), cf_pts=float(G.loc[mm, "pnl_entry20"].sum()), cf_win=float((G.loc[mm, "pnl_entry20"] > 0).mean()),
                                engine_pts=float(G.loc[mm, "pnl_pts"].sum()))
# first-bar decision and 18:00 fill sensitivity
for g in ["A", "B", "C"]:
    gg = G[G.grade == g]
    H[f"grade {g}: decided in 18:00 bar"] = dict(n=len(gg), share_decided_bar0=float((gg.decided_bar == 0).mean()),
                                               wins_decided_bar0=int(((gg.decided_bar == 0) & gg.win).sum()),
                                               losses_decided_bar0=int(((gg.decided_bar == 0) & ~gg.win).sum()))
    H[f"grade {g}: fill at 18:00 open instead of 17:00 close"] = dict(
        n=len(gg), engine_pts=float(gg.pnl_pts.sum()), open_fill_pts=float(gg.pnl_open_fill.sum()),
        n_open_past_target=int(gg.open_past_target.sum()), n_open_past_stop=int(gg.open_past_stop.sum()),
        avg_gap_in_dir=float(gg.gap_18_in_dir.mean()))
# regime gates on A
A = G[G.grade == "A"]
for lbl, cond in [("trail20_wr<0.45", A.trail20_wr < 0.45), ("trail20_wr>=0.45", A.trail20_wr >= 0.45), ("trail20 unknown", A.trail20_wr.isna()),
                  ("vix>25", A.vix > 25), ("vix<=25", A.vix <= 25), ("vix_z20>1.5", A.vix_z20 > 1.5), ("rv_ratio>1.5", A.rv_ratio > 1.5)]:
    s_ = A[cond]
    H[f"A | {lbl}"] = dict(n=len(s_), win=float(s_.win.mean()) if len(s_) else np.nan, pts=float(s_.pnl_pts.sum()), avg=float(s_.pnl_pts.mean()) if len(s_) else np.nan)
for lbl, cond in [("ah_shock_proxy", A.ah_shock_proxy), ("no ah shock", ~A.ah_shock_proxy), ("sunday_open", A.sunday_open == 1), ("weeknight", A.sunday_open == 0),
                  ("in catalogue (big night)", A.in_catalogue), ("not in catalogue", ~A.in_catalogue)]:
    s_ = A[cond.fillna(False)]
    H[f"A | {lbl}"] = dict(n=len(s_), win=float(s_.win.mean()) if len(s_) else np.nan, pts=float(s_.pnl_pts.sum()), avg=float(s_.pnl_pts.mean()) if len(s_) else np.nan)
# same-bar dependence of continuation wins
cw = G[(G.call == "CONTINUATION") & G.win]
H["continuation wins that were same-bar touches"] = dict(n_cont_wins=len(cw), same_bar=int(cw.same_bar.sum()),
                                                         A_same_bar=int(cw[cw.grade == "A"].same_bar.sum()),
                                                         A_same_bar_pts=float(cw[(cw.grade == "A") & cw.same_bar].pnl_pts.sum()))
# calibration by confidence bucket
cb = pd.cut(G.confidence, [55, 63, 72, 80, 90, 101], right=False)
calib = G.groupby(cb, observed=True).agg(n=("win", "size"), realised=("win", "mean"), stated=("confidence", lambda x: x.mean() / 100), avg_pts=("pnl_pts", "mean"))

# ------------------------------------------------------------------ 6. Grade-A anatomy
AW, AL = A[A.win], A[~A.win]
ATTR = ["confidence", "mag", "ext_in_dir", "vwap_in_dir", "vix_consistent", "vix", "vix_z20", "rv_ratio", "rth_range_atr", "stretch20_in_dir",
        "post_in_dir", "prior_asia_in_dir", "n225_in_dir", "sox_in_dir", "rth_vol_rel", "abs_streak", "stop_dist", "target_dist", "rr",
        "stop_vs_expected", "asia_rng_pts", "gap_18_in_dir", "move_18_20_in_dir", "trail20_wr"]


def cmp_table(w: pd.DataFrame, l: pd.DataFrame, cols) -> pd.DataFrame:
    out = []
    for c in cols:
        a, b = w[c].dropna().astype(float), l[c].dropna().astype(float)
        if len(a) < 3 or len(b) < 3:
            continue
        se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        out.append(dict(feature=c, win_mean=a.mean(), win_med=a.median(), loss_mean=b.mean(), loss_med=b.median(),
                        t=(a.mean() - b.mean()) / se if se > 0 else np.nan))
    return pd.DataFrame(out).set_index("feature").sort_values("t", key=np.abs, ascending=False)


A_cmp = cmp_table(AW, AL, ATTR)
A_cmp_by_call = {k: cmp_table(AW[AW.call == k], AL[AL.call == k], ATTR) for k in ["MEAN REVERSION", "CONTINUATION"]}
A_sunday = A[A.sunday_open == 1][["call", "variant", "best", "confidence", "pnl_pts", "pnl_open_fill", "gap_18_in_dir", "res", "decided_bar"]]
A_cat = {}
for c in ["call", "variant", "best", "dow", "sunday_open", "quarter", "res"]:
    A_cat[c] = A.groupby(c).agg(n=("win", "size"), win=("win", "mean"), pts=("pnl_pts", "sum"), avg=("pnl_pts", "mean"))
A_calltype = A.groupby(["call", "variant", "best"]).agg(n=("win", "size"), win=("win", "mean"), pts=("pnl_pts", "sum"), avg=("pnl_pts", "mean"),
                                                        avg_win=("pnl_pts", lambda x: x[x > 0].mean()), avg_loss=("pnl_pts", lambda x: x[x <= 0].mean() if (x <= 0).any() else np.nan),
                                                        rr=("rr", "median"))
# fragility
boot = np.array([RNG.choice(A.pnl_pts.values, len(A), replace=True).mean() for _ in range(5000)])
top5 = A.pnl_pts.nlargest(5)
frag = {
    "A nights / wins / losses": f"{len(A)} / {int(A.win.sum())} / {int((~A.win).sum())}",
    "avg pts (bootstrap 90% CI)": f"{A.pnl_pts.mean():+.1f} ({np.percentile(boot, 5):+.1f} .. {np.percentile(boot, 95):+.1f})",
    "P(mean <= 0) bootstrap": f"{(boot <= 0).mean():.3f}",
    "avg win / avg loss / reward:risk (realised)": f"{AW.pnl_pts.mean():+.1f} / {AL.pnl_pts.mean():+.1f} / {AW.pnl_pts.mean() / abs(AL.pnl_pts.mean()):.2f}",
    "median planned target:stop": f"{A.rr.median():.2f}",
    "top-5 wins share of total": f"{top5.sum() / A.pnl_pts.sum():.0%} ({', '.join(d.strftime('%Y-%m-%d') for d in top5.index)})",
    "total without top-5 wins": f"{A.pnl_pts.sum() - top5.sum():+.0f}",
    "worst-5 losses share of loss pts": f"{A.pnl_pts.nsmallest(5).sum() / AL.pnl_pts.sum():.0%}",
    "share of A decided in the 18:00 bar": f"{(A.decided_bar == 0).mean():.0%}",
    "A P&L if filled at the 18:00 open": f"{A.pnl_open_fill.sum():+.0f} vs {A.pnl_pts.sum():+.0f} engine ({int(A.open_past_target.sum())} nights open already past target, {int(A.open_past_stop.sum())} past stop)",
    "continuation A wins that were same-bar touches": f"{int(A[(A.call == 'CONTINUATION') & A.win].same_bar.sum())} of {int(((A.call == 'CONTINUATION') & A.win).sum())} (pts {A[(A.call == 'CONTINUATION') & A.win & A.same_bar].pnl_pts.sum():+.0f})",
    "best quarter share of total": f"{qa.A_pts.max() / A.pnl_pts.sum():.0%} ({qa.A_pts.idxmax()})",
    "quarters with A win rate < 50%": ", ".join(f"{i} ({r.A_win:.0%}, n={int(r.A_n)})" for i, r in qa.iterrows() if r.A_win < 0.5),
    "continuation share of A pts": f"{A[A.call == 'CONTINUATION'].pnl_pts.sum() / A.pnl_pts.sum():.0%}",
    "A nights in the catalogue (big-move nights)": f"{int(A.in_catalogue.sum())} ({A[A.in_catalogue].win.mean():.0%} win, {A[A.in_catalogue].pnl_pts.sum():+.0f} pts) vs {int((~A.in_catalogue).sum())} not ({A[~A.in_catalogue].win.mean():.0%} win, {A[~A.in_catalogue].pnl_pts.sum():+.0f} pts)",
    "A Sunday reopens (Friday rows)": f"{len(A_sunday)} nights, {A_sunday.pnl_pts.gt(0).mean():.0%} win, {A_sunday.pnl_pts.sum():+.0f} pts engine, {A_sunday.pnl_open_fill.sum():+.0f} pts if filled at the Sunday 18:00 open; {A_sunday.pnl_pts.sum() / A.pnl_pts.sum():.0%} of all A pts",
    "A losses by resolution": f"scratch {int(((A.res == 'scratch') & ~A.win).sum())} ({A[(A.res == 'scratch') & ~A.win].pnl_pts.sum():+.0f} pts), stop {int(((A.res == 'stop') & ~A.win).sum())} ({A[(A.res == 'stop') & ~A.win].pnl_pts.sum():+.0f} pts)",
    "A wins by resolution": f"target {int(((A.res == 'target') & A.win).sum())}, scratch-but-positive {int(((A.res == 'scratch') & A.win).sum())}",
    "median hour of A target hits (ET)": f"{A[A.res == 'target'].tgt_hour.median():.0f} (share hit by the 20:00 bar: {(A[A.res == 'target'].tgt_i <= 2).mean():.0%})",
}

# ------------------------------------------------------------------ 7. write
G.to_csv(os.path.join(LAB, f"forensics_graded_{SYM}.csv"))
L.to_csv(os.path.join(LAB, f"forensics_losses_{SYM}.csv"))

PER_NIGHT = ["grade", "confidence", "call", "variant", "best", "pnl_pts", "res", "decided_bar", "stop_dist", "target_dist", "asia_rng_pts",
             "stop_vs_realised", "whipsaw", "hold_res", "kospi_next", "n225_next", "vix", "rv_ratio", "trail20_wr", "sunday_open",
             "driver_kind", "primary"]


def fmt_night(df):
    d = df[PER_NIGHT].copy()
    d["primary"] = d.primary.str.slice(0, 2)
    d["driver_kind"] = d.driver_kind.fillna("")
    return d


Lines = []
P = Lines.append
P(f"# Forensics v0 — why the {SYM} engine loses, and what the Grade-A wins are made of")
P("")
P(f"Source: `research/backtest_trades_{SYM}.csv` (331 OOS nights, 196 graded, 87 losing graded nights) joined with `data/{SYM}_features.csv`, "
  f"`data/{SYM}_targets.csv`, `data/{SYM}_sessions.csv`, hourly bars and the four `research/catalogue_*.csv`. "
  "Every graded trade's geometry (entry = 17:00 close, stop, target) was rebuilt from the session table and walked bar by bar; "
  f"the rebuilt P&L matches the engine's `pnl_pts` on all {len(G)} graded nights (max abs error {G.recon_err.max():.2e}). "
  "Script: `/tmp/claude-0/-home-user-24-yo/0f4c1f58-9634-52a1-b9e3-d380ed906070/scratchpad/forensics.py`.")
P("")
P("Reading guide: `res` = how the trade resolved (target / stop / scratch at 03:00); `decided_bar` = index of the hourly bar in which it resolved "
  "(0 = the 18:00 bar); `stop_vs_realised` = stop distance / realised Asia range; `whipsaw` = stopped and the target was reached later in the same Asia session; "
  "`same_bar` = target and stop first touched in the same hourly bar (the engine counts that as stopped for a fade and as a win for a continuation).")
P("")
P("## 0. Headline numbers")
P("")
P(md(G.groupby("grade").agg(n=("win", "size"), win=("win", "mean"), avg=("pnl_pts", "mean"), pts=("pnl_pts", "sum"),
                            avg_win=("pnl_pts", lambda x: x[x > 0].mean()), avg_loss=("pnl_pts", lambda x: x[x <= 0].mean()),
                            decided_bar0=("decided_bar", lambda x: (x == 0).mean()))))
P("")
P("Resolution of every graded trade (how the loss happened matters more than the grade):")
P("")
P(md(by_res))
P("")
P("Losses by grade / call / stop variant / resolution:")
P("")
P(md(loss_by_res))
P("")
P("## 1. Loss clusters (87 losing graded nights)")
P("")
P("Each losing night gets every flag it satisfies (table 1a, overlapping) and one PRIMARY cluster by a fixed priority "
  "(table 1b, mutually exclusive): same-bar artefact > identified catalyst (catalogue driver or after-hours print) > geometry whipsaw > "
  "geometry (stop < 1/3 of realised range, target beyond realised range) > timing (target reached in Europe / next RTH) > ex-post Asia shock "
  "(KOSPI or N225 moved > 2% that night, not in catalogue) > calendar > regime > mid-band calibration > unexplained.")
P("")
P("### 1a. Flag counts (overlapping) with the base rate of the same condition among the 109 winning graded nights")
P("")
P(md(flag_counts, "{:.2f}"))
P("")
P("### 1b. Primary cluster")
P("")
P(md(Lsum))
P("")
P("### 1b-i. Inside the catalyst cluster: what kind of driver, and was it knowable at 18:00 ET?")
P("")
P(md(know_tab))
P("")
P("Driver kinds (keyword classification of the catalogue's `asia_driver`, overlapping):")
P("")
P(md(driver_tab, "{:.0f}"))
P("")
P("Catalogue tags on the catalyst-cluster nights:")
P("")
P(md(tag_tab, "{:.0f}"))
P("")
P("### 1b-ii. Scratch nights: what happened after 03:00 (first touch of target vs stop over Europe + next RTH)")
P("")
P(md(hold_res_tab))
P("")
for name, sub in L.groupby("primary"):
    P(f"### {name} — n={len(sub)}, {sub.pnl_pts.sum():+.0f} pts")
    P("")
    P(md(fmt_night(sub.sort_values('pnl_pts')), "{:.2f}"))
    P("")
    if name.startswith("c)"):
        P("Catalogue drivers for these nights (truncated):")
        P("")
        for d, r in sub.sort_values("pnl_pts").iterrows():
            if isinstance(r.asia_driver, str):
                P(f"- **{d:%Y-%m-%d}** ({r.grade}, {r.call.lower()}, {r.pnl_pts:+.0f} pts, tags `{r.tags}`): {r.asia_driver[:260]}")
            else:
                P(f"- **{d:%Y-%m-%d}** ({r.grade}, {r.call.lower()}, {r.pnl_pts:+.0f} pts): not in catalogue; after-hours proxy post_ret={r.post_ret * 1e4:+.0f} bp, megacap_earnings_tonight={int(r.megacap_earnings_tonight)}, events `{r.events_today}` / `{r.events_tonight_tomorrow}`")
        P("")
P("### 1c. Quarter concentration")
P("")
P(md(qtab))
P("")
pq = pd.crosstab(L.primary.str.slice(0, 2), L.quarter)
pq.index.name = "primary"
P("Primary cluster by quarter (n):")
P("")
P(md(pq, "{:.0f}"))
P("")
pqp = pd.crosstab(L.primary.str.slice(0, 2), L.quarter, values=L.pnl_pts, aggfunc="sum").round(0)
pqp.index.name = "primary"
P("Primary cluster by quarter (pts):")
P("")
P(md(pqp, "{:.0f}"))
P("")
P("Note: the catalogue starts 2025-11-03, so the 28 losses of 2025Q2-Q3 cannot fall into cluster c); their geometry / calibration / unexplained labels are upper bounds.")
P("")
P("### 1e. Geometry vs the EX-ANTE expected range (target or stop distance / 20d median Asia range known at 18:00), all graded nights")
P("")
geom_tab.index = [f"{a} | {b}" for a, b in geom_tab.index]
geom_tab.index.name = "target/expected range | grade"
P(md(geom_tab))
P("")
geom_stop_tab.index = [f"{a} | {b}" for a, b in geom_stop_tab.index]
geom_stop_tab.index.name = "stop/expected range | grade"
P(md(geom_stop_tab))
P("")
P("### 1f. The tail: ten worst graded losses")
P("")
P(md(worst, "{:.2f}"))
P("")
P("### 1g. Ex-ante exclusion flags: P&L of the flagged nights vs the rest")
P("")
P(md(excl_tab, "{:.2f}"))
P("")
P("### 1d. Calibration by stated confidence (all graded nights)")
P("")
calib.index = [str(i) for i in calib.index]
calib.index.name = "confidence bucket"
P(md(calib))
P("")
P("## 2. Hypothesis counterfactuals (IN-SAMPLE, exploratory; effect sizes are what a pre-registered test should expect, not results)")
P("")
Htab = pd.DataFrame(H).T
P(md(Htab, "{:.2f}"))
P("")
P("### 2a. Full time-stop counterfactual (every graded trade: engine resolution if it happened by the 19:00 bar, otherwise flat at the 20:00 / 22:00 close)")
P("")
P(md(timestop_tab, "{:.2f}"))
P("")
P("## 5. Hypotheses for the loop (candidates for pre-registration; every effect size above is in-sample and must be re-estimated on nights no agent has seen)")
P("")
P("- **H-cat (catalyst)**: a night with an identifiable driver at 18:00 (|post_ret| > 0.3%, mega-cap/semis print after the close, or a narrative-agent 'Asia-origin / headline' flag) has no A-grade edge. "
  "Predicted: win rate on flagged A nights <= 50% vs ~72% on the rest; skipping them costs 0 and removes roughly a third of A loss points. Test: the daily narrative agent writes the flag to `catalogue_live.csv` BEFORE 18:00; score prospectively.")
P("- **H-time (sub-session)**: what the engine wins, it wins early (66% of A target hits by the 20:00 bar) and A scratches lose -1145 pts between 20:00 and 03:00. "
  "But the FULL counterfactual (table 2a) is sober: a 20:00 time-stop lifts A continuation (+17 -> +32 pts/night, worst night -340 -> -114) and HURTS A mean reversion (+26 -> +13) and grade B; it is unstable across sample halves. "
  "Predicted (if real): +10-15 pts/night on A continuation only, ~0 on A overall. Low prior; pre-register for continuation trades only and evaluate on the next 60 graded nights.")
P("- **H-geom (target cap)**: targets beyond 1.0 x the 20-day median Asia range (known at 18:00) resolve to target 30% of the time at every grade. "
  "Predicted: a max-target guard removes ~8% of graded nights and ~+1600 pts of in-sample losses; the wide-stop variant is NOT a fix (0 of 10 tight-fade losses convert, and they lose more).")
P("- **H-calib (joint calibration)**: the mid band [63,72) realises 45% (n=83) against a stated 67%. Predicted: a single classifier for 'target before stop' of the chosen candidate, isotonic-calibrated, moves most B/C nights to NO EDGE and the realised-vs-stated gap in the mid band to < 5 points. Test: Brier/ECE on held-out months.")
P("- **H-regime (narrative regime, not vol)**: VIX/rv/trailing-form flags have no lift (~1.0-1.1); the regime failure is a calendar cluster (2025Q4-2026Q1: A win rate 42-45%) that coincides with the catalogue's AI-capex/semis + Iran-oil driver regime. "
  "Predicted: a weekly narrative regime label ('Asia-origin continuation regime') gates A nights with ~0 cost in P&L and halves the quarterly drawdown. Test: label written weekly in advance by the pattern agent; compare gated vs ungated on the following weeks only.")
P("- **H-cal (thin sessions)**: pre-holiday / 6-bar sessions: 0 wins in 5 graded nights (3 A). Predicted: skipping them is free (n is tiny; treat as a rule to pre-register, not a result).")
P("- **H-hold (negative result)**: holding scratches through Europe or the next RTH makes them worse (-941 to -2592 pts); 'the target came later' explains only 4 losses. Do not spend loop budget here.")
P("")
P("## 3. Grade-A anatomy")
P("")
P("### 3a. Winners vs losers inside Grade A (t = Welch t-stat of the mean difference)")
P("")
P(md(A_cmp, "{:.2f}"))
P("")
for k, t in A_cmp_by_call.items():
    P(f"Same comparison inside Grade-A **{k}** trades only ({int(((A.call == k) & A.win).sum())} wins vs {int(((A.call == k) & ~A.win).sum())} losses):")
    P("")
    P(md(t.head(12), "{:.2f}"))
    P("")
P("### 3a-ii. Grade-A Sunday reopens (Friday rows): engine P&L vs a fill at the Sunday 18:00 open")
P("")
P(md(A_sunday, "{:.2f}"))
P("")
for c, t in A_cat.items():
    P(f"### 3b. Grade A by `{c}`")
    P("")
    P(md(t))
    P("")
P("### 3c. Grade A by call / variant / target")
P("")
P(md(A_calltype))
P("")
P("### 3d. Fragility")
P("")
for k, v in frag.items():
    P(f"- **{k}**: {v}")
P("")
P("### 3e. Every Grade-A night")
P("")
P(md(fmt_night(A.assign(primary=A.index.map(lambda d: L.primary.get(d, 'win'))).sort_values('pnl_pts', ascending=False)), "{:.2f}"))
P("")
P("## 4. Caveats")
P("")
P("- All counterfactuals in section 2 are evaluated on the same 331 nights that produced the grades: they size hypotheses, they do not confirm them.")
P("- The catalogue covers Nov 2025 → Nov 2026 and only the big Asia nights, so `in_catalogue` is itself a proxy for 'big move happened' (selection on the outcome).")
P("- `asia_shock_expost` uses the next KOSPI/N225 daily close: ex post by construction.")
P("- Hourly bars: a bar that touches both levels is ambiguous; 'whipsaw' and 'same_bar' depend on that granularity.")
P("- P&L is booked from the 17:00 close; the first tradable price is the 18:00 open. See the `fill at 18:00 open` rows.")

with open(OUT_MD, "w", encoding="utf-8") as fh:
    fh.write("\n".join(Lines))
print("wrote", OUT_MD)

# console summary for the structured report
pd.set_option("display.width", 250, "display.max_columns", 50, "display.max_rows", 500)
print("\n=== primary clusters ===\n", Lsum)
print("\n=== flags ===\n", flag_counts)
print("\n=== by resolution ===\n", by_res)
print("\n=== quarters ===\n", qtab)
print("\n=== calibration ===\n", calib)
print("\n=== hypotheses ===\n", Htab)
print("\n=== A winners vs losers ===\n", A_cmp)
for c, t in A_cat.items():
    print(f"\n=== A by {c} ===\n", t)
print("\n=== A by call type ===\n", A_calltype)
print("\n=== fragility ===")
for k, v in frag.items():
    print(f"- {k}: {v}")
