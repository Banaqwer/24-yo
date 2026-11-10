"""Build the 15-minute Asia-session table for NQ and ES (2026-08-31 .. 2026-11-06 RTH dates).

Outputs (all in this folder):
  {sym}_q15_sessions.csv : one row per session (RTH date) with quarter-hour index of the high/low, etc.
  {sym}_q15_bars.csv     : one row per (date, q) 15-minute bar inside the Asia session with running stats.
"""
import os, sys
import numpy as np, pandas as pd
from datetime import timedelta

ROOT = "."
OUT = "research/extremes/scripts/lens_minute"
ET = "America/New_York"
ASIA_HOURS = list(range(18, 24)) + [0, 1, 2]


def load15(sym):
    d = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv", index_col=0)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(ET)
    d = d[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d


def is_dst(ts):
    return ts.dst() != timedelta(0)


def build(sym):
    d = load15(sym)
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True)
    x["asia_gdate"] = pd.to_datetime(x["asia_gdate"])
    gd_to_date = {pd.Timestamp(g).date(): dt for dt, g in x["asia_gdate"].items()}

    h = d.copy()
    h["hour"] = h.index.hour
    g = pd.Series(h.index.date, index=h.index)
    sh = h.index.hour >= 18
    g[sh] = (h.index[sh] + pd.Timedelta(days=1)).date
    h["gdate"] = g.values
    a = h[h["hour"].isin(ASIA_HOURS)]
    srows, brows = [], []
    for gd, grp in a.groupby("gdate"):
        if gd not in gd_to_date:
            continue
        grp = grp.sort_index()
        date = gd_to_date[gd]
        xr = x.loc[date]
        ts0 = grp.index[0]
        dst = is_dst(ts0)
        # quarter index q = minutes since 18:00 / 15
        qidx = ((grp.index.hour - 18) % 24) * 4 + grp.index.minute // 15
        grp = grp.assign(q=qidx.values)
        nq = len(grp)
        if nq < 30:
            print(sym, date, "short session", nq);
        ref = float(xr["ref_close"])
        hi_q = int(grp["High"].values.argmax()); lo_q = int(grp["Low"].values.argmin())
        hi = float(grp["High"].iloc[hi_q]); lo = float(grp["Low"].iloc[lo_q])
        hiq = int(grp["q"].iloc[hi_q]); loq = int(grp["q"].iloc[lo_q])
        q0 = grp.iloc[0]
        tko_q = 8 if dst else 4          # 09:00 JST
        cno_q = 14 if dst else 10        # 09:30 CST / HKT
        # first-15-minute hold / break
        f15_hi, f15_lo = float(q0["High"]), float(q0["Low"])
        brk_hi_bp = (hi - f15_hi) / ref * 1e4
        brk_lo_bp = (f15_lo - lo) / ref * 1e4
        after_hi = grp.iloc[hi_q + 1:]; after_lo = grp.iloc[lo_q + 1:]
        drop_after_hi = (hi - after_hi["Low"].min()) / ref * 1e4 if len(after_hi) else np.nan
        rally_after_lo = (after_lo["High"].max() - lo) / ref * 1e4 if len(after_lo) else np.nan
        # stop-run of the first-15m high: broken by <10bp and price later trades back below the f15 high
        hi_stoprun = int((0 < brk_hi_bp < 10) and len(after_hi) > 0 and after_hi["Low"].min() < f15_hi)
        lo_stoprun = int((0 < brk_lo_bp < 10) and len(after_lo) > 0 and after_lo["High"].max() > f15_lo)
        close = float(grp["Close"].iloc[-1])
        # extreme-bar signatures
        hb = grp.iloc[hi_q]; lb = grp.iloc[lo_q]
        med_vol = grp["Volume"].median(); med_rng = (grp["High"] - grp["Low"]).median()
        def wick_hi(b): return (b["High"] - max(b["Open"], b["Close"])) / max(b["High"] - b["Low"], 1e-9)
        def wick_lo(b): return (min(b["Open"], b["Close"]) - b["Low"]) / max(b["High"] - b["Low"], 1e-9)
        nxt_hi = grp.iloc[hi_q + 1] if hi_q + 1 < nq else None
        nxt_lo = grp.iloc[lo_q + 1] if lo_q + 1 < nq else None
        rec = dict(
            date=date, asia_gdate=pd.Timestamp(gd), is_dst=int(dst), n_q=nq, ref_close=ref,
            hi=hi, lo=lo, hi_q=hiq, lo_q=loq, hi_k15=hiq // 4, lo_k15=loq // 4, hi_sub=hiq % 4, lo_sub=loq % 4,
            hi_k_hourly=int(xr["hi_k"]), lo_k_hourly=int(xr["lo_k"]),
            hi_match=int(abs(hi - xr["asia_high"]) < 1e-6), lo_match=int(abs(lo - xr["asia_low"]) < 1e-6),
            tko_q=tko_q, cno_q=cno_q,
            hi_min_since_tko=(hiq - tko_q) * 15, lo_min_since_tko=(loq - tko_q) * 15,
            hi_first=int(hiq < loq), same_q=int(hiq == loq), q_between=loq - hiq,
            hi_bp=(hi / ref - 1) * 1e4, lo_bp=(lo / ref - 1) * 1e4, rng_bp=(hi - lo) / ref * 1e4,
            open_18=float(q0["Open"]), f15_hi=f15_hi, f15_lo=f15_lo,
            f15_rng_bp=(f15_hi - f15_lo) / ref * 1e4, f15_ret_bp=(q0["Close"] / q0["Open"] - 1) * 1e4,
            open_is_high=int(abs(hi - q0["Open"]) < 1e-6), open_is_low=int(abs(lo - q0["Open"]) < 1e-6),
            f15_high_holds=int(hiq == 0), f15_low_holds=int(loq == 0),
            brk_hi_bp=brk_hi_bp, brk_lo_bp=brk_lo_bp, hi_stoprun=hi_stoprun, lo_stoprun=lo_stoprun,
            close_below_f15hi=int(close < f15_hi), close_above_f15lo=int(close > f15_lo),
            drop_after_hi_bp=drop_after_hi, rally_after_lo_bp=rally_after_lo,
            hi_bar_vol_rel=hb["Volume"] / max(med_vol, 1), lo_bar_vol_rel=lb["Volume"] / max(med_vol, 1),
            hi_bar_rng_rel=(hb["High"] - hb["Low"]) / max(med_rng, 1e-9), lo_bar_rng_rel=(lb["High"] - lb["Low"]) / max(med_rng, 1e-9),
            hi_bar_rng_bp=(hb["High"] - hb["Low"]) / ref * 1e4, lo_bar_rng_bp=(lb["High"] - lb["Low"]) / ref * 1e4,
            hi_bar_wick=wick_hi(hb), lo_bar_wick=wick_lo(lb),
            hi_bar_ret_bp=(hb["Close"] / hb["Open"] - 1) * 1e4, lo_bar_ret_bp=(lb["Close"] / lb["Open"] - 1) * 1e4,
            hi_bar_close_loc=(hb["Close"] - hb["Low"]) / max(hb["High"] - hb["Low"], 1e-9),
            lo_bar_close_loc=(lb["Close"] - lb["Low"]) / max(lb["High"] - lb["Low"], 1e-9),
            hi_next_ret_bp=(nxt_hi["Close"] / nxt_hi["Open"] - 1) * 1e4 if nxt_hi is not None else np.nan,
            lo_next_ret_bp=(nxt_lo["Close"] / nxt_lo["Open"] - 1) * 1e4 if nxt_lo is not None else np.nan,
            hi_next_rng_rel=(nxt_hi["High"] - nxt_hi["Low"]) / max(med_rng, 1e-9) if nxt_hi is not None else np.nan,
            lo_next_rng_rel=(nxt_lo["High"] - nxt_lo["Low"]) / max(med_rng, 1e-9) if nxt_lo is not None else np.nan,
            hi_next_vol_rel=nxt_hi["Volume"] / max(med_vol, 1) if nxt_hi is not None else np.nan,
            lo_next_vol_rel=nxt_lo["Volume"] / max(med_vol, 1) if nxt_lo is not None else np.nan,
            hi_next_closes_below_bar_low=int(nxt_hi["Close"] < hb["Low"]) if nxt_hi is not None else np.nan,
            lo_next_closes_above_bar_high=int(nxt_lo["Close"] > lb["High"]) if nxt_lo is not None else np.nan,
            close_bp=(close / ref - 1) * 1e4, gap_open_bp=(q0["Open"] / ref - 1) * 1e4,
            sunday_open=int(xr["sunday_open"]) if "sunday_open" in xr else 0,
            rth_ret_bp=float(xr["rth_ret_bp"]),
        )
        srows.append(rec)
        # bar panel
        run_hi, run_lo = -np.inf, np.inf; qh = ql = 0
        for i in range(nq):
            b = grp.iloc[i]
            if b["High"] > run_hi: run_hi, qh = b["High"], int(b["q"])
            if b["Low"] < run_lo: run_lo, ql = b["Low"], int(b["q"])
            brows.append(dict(
                date=date, q=int(b["q"]), hour_et=int(grp.index[i].hour), minute=int(grp.index[i].minute), is_dst=int(dst),
                q_since_tko=int(b["q"]) - tko_q,
                open=b["Open"], high=b["High"], low=b["Low"], close=b["Close"], vol=b["Volume"],
                vol_rel=b["Volume"] / max(med_vol, 1), rng_rel=(b["High"] - b["Low"]) / max(med_rng, 1e-9),
                rng_bp=(b["High"] - b["Low"]) / ref * 1e4, ret_bp=(b["Close"] / b["Open"] - 1) * 1e4,
                wick_hi=wick_hi(b), wick_lo=wick_lo(b),
                run_hi_bp=(run_hi / ref - 1) * 1e4, run_lo_bp=(run_lo / ref - 1) * 1e4,
                q_since_hi=int(b["q"]) - qh, q_since_lo=int(b["q"]) - ql,
                is_hi_bar=int(int(b["q"]) == hiq), is_lo_bar=int(int(b["q"]) == loq),
                high_done=int(run_hi >= hi - 1e-9), low_done=int(run_lo <= lo + 1e-9),
            ))
    s = pd.DataFrame(srows).set_index("date").sort_index()
    b = pd.DataFrame(brows)
    s.to_csv(f"{OUT}/{sym}_q15_sessions.csv"); b.to_csv(f"{OUT}/{sym}_q15_bars.csv", index=False)
    return s, b


if __name__ == "__main__":
    for sym in ("NQ", "ES"):
        s, b = build(sym)
        print(sym, "sessions", len(s), "bars", len(b), "n_q counts", s["n_q"].value_counts().to_dict())
        print("  hi/lo level match vs hourly table:", s["hi_match"].mean(), s["lo_match"].mean())
        print("  hi_k match:", (s["hi_k15"] == s["hi_k_hourly"]).mean(), " lo_k match:", (s["lo_k15"] == s["lo_k_hourly"]).mean())
        mm = s[(s["hi_k15"] != s["hi_k_hourly"]) | (s["lo_k15"] != s["lo_k_hourly"]) | (s["hi_match"] == 0) | (s["lo_match"] == 0)]
        if len(mm):
            print(mm[["hi", "lo", "hi_q", "lo_q", "hi_k15", "hi_k_hourly", "lo_k15", "lo_k_hourly", "hi_match", "lo_match"]])
        print("  gap_open_bp extremes:", s["gap_open_bp"].abs().sort_values(ascending=False).head(4).round(1).to_dict())
