"""
Asia-session HIGH / LOW characterisation and detector dataset.

Two tables per symbol:

  build_extremes(sym)  -> one row per RTH date D describing the following Asia session
                          (18:00 D .. 02:59 D+1 ET): when the high and the low were made (ET bar
                          index, ET hour, Tokyo-clock hour), where they sit relative to the 17:00
                          close, the RTH range, the prior Asia range, and how the session resolved
                          after each extreme.  Joined with the 18:00-knowable features and the
                          calendar flags.

  hourly_panel(sym)    -> one row per (RTH date D, Asia bar k) with everything known at the CLOSE
                          of bar k (running high/low, bars since each, position in range, bar
                          return/range/volume relative to history) and the labels
                          high_done / low_done (the session extreme is already in) and the
                          remaining upside / downside in bp.  This is the training table for the
                          "is the Asia high / low in yet?" detector.

Bar index k: 0 = the 18:00 ET bar, ..., 8 = the 02:00 ET bar (fewer on short sessions).
Tokyo cash opens 09:00 JST = 19:00 ET in winter (EST, k=1) and 20:00 ET in summer (EDT, k=2);
Shanghai/HK open 09:30 local = 20:30 ET winter (inside k=2) / 21:30 ET summer (inside k=3).
"""
from __future__ import annotations

import os
import warnings
from datetime import timedelta

import numpy as np
import pandas as pd

from sessions import ASIA_HOURS, ET, build_sessions, load_hourly, with_prior_context

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "research", "extremes")


def _asia_groups(h: pd.DataFrame):
    h = h.copy()
    h["hour"] = h.index.hour
    g = pd.Series(h.index.date, index=h.index)
    shift = h.index.hour >= 18
    g[shift] = (h.index[shift] + pd.Timedelta(days=1)).date
    h["gdate"] = g.values
    a = h[h["hour"].isin(ASIA_HOURS)]
    return {pd.Timestamp(gd): grp.sort_index() for gd, grp in a.groupby("gdate") if len(grp) >= 6}


def _is_dst(ts: pd.Timestamp) -> bool:
    return ts.dst() != timedelta(0)


def tokyo_open_bar(ts: pd.Timestamp) -> int:
    """Bar index of the Tokyo cash open (09:00 JST) inside the Asia session that starts at ts."""
    return 2 if _is_dst(ts) else 1


def china_open_bar(ts: pd.Timestamp) -> int:
    """Bar index containing the Shanghai/HK open (09:30 local)."""
    return 3 if _is_dst(ts) else 2


def _jst_hour(ts: pd.Timestamp) -> int:
    return (ts.hour + (13 if _is_dst(ts) else 14)) % 24


def build_extremes(sym: str = "NQ", s: pd.DataFrame | None = None) -> pd.DataFrame:
    h = load_hourly(os.path.join(DATA, f"{sym}_1h.csv"))
    if s is None:
        s = with_prior_context(build_sessions(h))
    groups = _asia_groups(h)
    rows = []
    for d, r in s.iterrows():
        if pd.isna(r.get("asia_gdate")):
            continue
        gd = pd.Timestamp(r["asia_gdate"])
        if gd not in groups:
            continue
        g = groups[gd]
        ts0 = g.index[0]
        ref = float(r["post_close"])
        hi_k = int(np.argmax(g["High"].values))
        lo_k = int(np.argmin(g["Low"].values))
        hi = float(g["High"].iloc[hi_k]); lo = float(g["Low"].iloc[lo_k])
        n = len(g)
        close = float(g["Close"].iloc[-1]); opn = float(g["Open"].iloc[0])
        rng = hi - lo
        # what happened after each extreme
        after_hi = g.iloc[hi_k + 1:]
        after_lo = g.iloc[lo_k + 1:]
        drop_after_hi = (hi - after_hi["Low"].min()) / ref * 1e4 if len(after_hi) else (hi - float(g["Low"].iloc[hi_k])) / ref * 1e4
        rally_after_lo = (after_lo["High"].max() - lo) / ref * 1e4 if len(after_lo) else (float(g["High"].iloc[lo_k]) - lo) / ref * 1e4
        # bar-level: did the extreme bar close near its extreme (rejection wick)?
        hb = g.iloc[hi_k]; lb = g.iloc[lo_k]
        hi_bar_wick = (hb["High"] - max(hb["Open"], hb["Close"])) / max(hb["High"] - hb["Low"], 1e-9)
        lo_bar_wick = (min(lb["Open"], lb["Close"]) - lb["Low"]) / max(lb["High"] - lb["Low"], 1e-9)
        # running-extreme hold: the bar index after which the running high never changed = hi_k
        tko = tokyo_open_bar(ts0); cno = china_open_bar(ts0)
        rec = dict(
            date=d, asia_gdate=gd, is_dst=int(_is_dst(ts0)), n_bars=n, ref_close=ref,
            asia_open=opn, asia_high=hi, asia_low=lo, asia_close=close,
            hi_k=hi_k, lo_k=lo_k, hi_hour_et=int(g.index[hi_k].hour), lo_hour_et=int(g.index[lo_k].hour),
            hi_hour_jst=_jst_hour(g.index[hi_k]), lo_hour_jst=_jst_hour(g.index[lo_k]),
            tokyo_open_k=tko, china_open_k=cno,
            hi_first=int(hi_k < lo_k), same_bar_extremes=int(hi_k == lo_k), bars_between=abs(hi_k - lo_k),
            hi_bp=(hi / ref - 1) * 1e4, lo_bp=(lo / ref - 1) * 1e4, rng_bp=rng / ref * 1e4,
            open_bp=(opn / ref - 1) * 1e4, close_bp=(close / ref - 1) * 1e4,
            close_loc=(close - lo) / rng if rng > 0 else np.nan,
            open_loc=(opn - lo) / rng if rng > 0 else np.nan,
            hi_vs_rth_high_bp=(hi / r["rth_high"] - 1) * 1e4, lo_vs_rth_low_bp=(lo / r["rth_low"] - 1) * 1e4,
            high_above_rth_high=int(hi > r["rth_high"]), low_below_rth_low=int(lo < r["rth_low"]),
            hi_vs_rth_vwap_bp=(hi / r["rth_vwap"] - 1) * 1e4, lo_vs_rth_vwap_bp=(lo / r["rth_vwap"] - 1) * 1e4,
            hi_vs_prior_asia_high_bp=(hi / r["prior_asia_high"] - 1) * 1e4 if pd.notna(r.get("prior_asia_high")) else np.nan,
            lo_vs_prior_asia_low_bp=(lo / r["prior_asia_low"] - 1) * 1e4 if pd.notna(r.get("prior_asia_low")) else np.nan,
            high_in_first_bar=int(hi_k == 0), low_in_first_bar=int(lo_k == 0),
            high_in_last_bar=int(hi_k == n - 1), low_in_last_bar=int(lo_k == n - 1),
            high_at_tokyo_open=int(hi_k == tko), low_at_tokyo_open=int(lo_k == tko),
            high_by_tokyo_open=int(hi_k <= tko), low_by_tokyo_open=int(lo_k <= tko),
            high_at_china_open=int(hi_k == cno), low_at_china_open=int(lo_k == cno),
            drop_after_hi_bp=drop_after_hi, rally_after_lo_bp=rally_after_lo,
            hi_bar_wick=hi_bar_wick, lo_bar_wick=lo_bar_wick,
            hi_bar_ret_bp=(hb["Close"] / hb["Open"] - 1) * 1e4, lo_bar_ret_bp=(lb["Close"] / lb["Open"] - 1) * 1e4,
            hi_bar_vol_share=float(hb["Volume"] / max(g["Volume"].sum(), 1)),
            lo_bar_vol_share=float(lb["Volume"] / max(g["Volume"].sum(), 1)),
            first_bar_ret_bp=(float(g["Close"].iloc[0]) / opn - 1) * 1e4,
            first_bar_rng_bp=(float(g["High"].iloc[0]) - float(g["Low"].iloc[0])) / ref * 1e4,
            gap_open_bp=(opn / ref - 1) * 1e4,
            asia_ret_bp=(close / opn - 1) * 1e4,
            rth_ret_bp=(r["rth_close"] / r["rth_open"] - 1) * 1e4,
            rth_range_bp=(r["rth_high"] - r["rth_low"]) / ref * 1e4,
        )
        # the "opposite extreme after the first extreme" = the realised move available after the first extreme
        rec["move_after_first_extreme_bp"] = rec["drop_after_hi_bp"] if rec["hi_first"] else rec["rally_after_lo_bp"]
        rows.append(rec)
    x = pd.DataFrame(rows).set_index("date").sort_index()
    return x


def hourly_panel(sym: str = "NQ", x: pd.DataFrame | None = None, s: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per (RTH date, Asia bar k) with information known at the close of bar k."""
    h = load_hourly(os.path.join(DATA, f"{sym}_1h.csv"))
    if s is None:
        s = with_prior_context(build_sessions(h))
    if x is None:
        x = build_extremes(sym, s)
    groups = _asia_groups(h)
    # rolling medians of per-hour volume and bar range over the prior 20 sessions (by ET hour)
    allbars = pd.concat(groups.values())
    allbars = allbars.assign(gdate=np.repeat(list(groups.keys()), [len(g) for g in groups.values()]))
    allbars["rng"] = allbars["High"] - allbars["Low"]
    hist = {}
    for hr, grp in allbars.groupby(allbars.index.hour):
        grp = grp.sort_index()
        hist[hr] = pd.DataFrame({
            "vol_med20": grp["Volume"].shift(1).rolling(20, min_periods=10).median(),
            "rng_med20": grp["rng"].shift(1).rolling(20, min_periods=10).median(),
        }, index=grp.index)
    hist = pd.concat(hist.values()).sort_index()
    # ex-ante session range reference: rolling 20-session median of the realised Asia range (shifted)
    med_rng = x["rng_bp"].shift(1).rolling(20, min_periods=10).median()

    rows = []
    for d, r in x.iterrows():
        g = groups[pd.Timestamp(r["asia_gdate"])]
        ref = r["ref_close"]; srow = s.loc[d]
        hi, lo = r["asia_high"], r["asia_low"]
        run_hi = -np.inf; run_lo = np.inf; k_hi = 0; k_lo = 0
        for k in range(len(g)):
            b = g.iloc[k]; ts = g.index[k]
            if b["High"] > run_hi:
                run_hi = b["High"]; k_hi = k
            if b["Low"] < run_lo:
                run_lo = b["Low"]; k_lo = k
            c = b["Close"]
            rr = run_hi - run_lo
            hh = hist.loc[ts] if ts in hist.index else pd.Series({"vol_med20": np.nan, "rng_med20": np.nan})
            rows.append(dict(
                date=d, k=k, hour_et=int(ts.hour), hour_jst=_jst_hour(ts), is_dst=int(_is_dst(ts)),
                n_bars=len(g), bars_left=len(g) - 1 - k,
                tokyo_open_k=r["tokyo_open_k"], china_open_k=r["china_open_k"],
                after_tokyo_open=int(k >= r["tokyo_open_k"]), after_china_open=int(k >= r["china_open_k"]),
                run_hi_bp=(run_hi / ref - 1) * 1e4, run_lo_bp=(run_lo / ref - 1) * 1e4, run_rng_bp=rr / ref * 1e4,
                run_rng_vs_med20=(rr / ref * 1e4) / med_rng.loc[d] if pd.notna(med_rng.loc[d]) and med_rng.loc[d] > 0 else np.nan,
                bars_since_hi=k - k_hi, bars_since_lo=k - k_lo,
                pos_in_range=(c - run_lo) / rr if rr > 0 else 0.5,
                cum_ret_bp=(c / ref - 1) * 1e4, bar_ret_bp=(c / b["Open"] - 1) * 1e4,
                bar_rng_bp=(b["High"] - b["Low"]) / ref * 1e4,
                bar_rng_rel=(b["High"] - b["Low"]) / hh["rng_med20"] if pd.notna(hh["rng_med20"]) and hh["rng_med20"] > 0 else np.nan,
                bar_vol_rel=b["Volume"] / hh["vol_med20"] if pd.notna(hh["vol_med20"]) and hh["vol_med20"] > 0 else np.nan,
                bar_close_loc=(c - b["Low"]) / (b["High"] - b["Low"]) if b["High"] > b["Low"] else 0.5,
                run_hi_above_rth_high=int(run_hi > srow["rth_high"]), run_lo_below_rth_low=int(run_lo < srow["rth_low"]),
                dist_rth_high_bp=(srow["rth_high"] / c - 1) * 1e4, dist_rth_low_bp=(srow["rth_low"] / c - 1) * 1e4,
                dist_rth_vwap_bp=(srow["rth_vwap"] / c - 1) * 1e4,
                dist_prior_asia_high_bp=(srow["prior_asia_high"] / c - 1) * 1e4 if pd.notna(srow.get("prior_asia_high")) else np.nan,
                dist_prior_asia_low_bp=(srow["prior_asia_low"] / c - 1) * 1e4 if pd.notna(srow.get("prior_asia_low")) else np.nan,
                # labels
                high_done=int(run_hi >= hi - 1e-9), low_done=int(run_lo <= lo + 1e-9),
                remaining_up_bp=(hi / c - 1) * 1e4, remaining_down_bp=(lo / c - 1) * 1e4,
                high_in_next_bar=int(r["hi_k"] == k + 1), low_in_next_bar=int(r["lo_k"] == k + 1),
                hi_k=r["hi_k"], lo_k=r["lo_k"],
            ))
    return pd.DataFrame(rows)


def build_all(sym: str = "NQ", write: bool = True):
    from features import build_feature_table
    f, s = build_feature_table(sym, "ES" if sym == "NQ" else "NQ")
    x = build_extremes(sym, s)
    keep = [c for c in f.columns if c not in x.columns]
    xf = x.join(f[keep], how="left")
    p = hourly_panel(sym, x, s)
    if write:
        os.makedirs(OUT, exist_ok=True)
        xf.to_csv(os.path.join(OUT, f"{sym}_extremes.csv"))
        p.to_csv(os.path.join(OUT, f"{sym}_hourly_panel.csv"), index=False)
    return xf, p


if __name__ == "__main__":
    import sys
    for sym in (sys.argv[1:] or ["NQ", "ES"]):
        xf, p = build_all(sym)
        print(sym, "extremes", xf.shape, "panel", p.shape, "->", OUT)
