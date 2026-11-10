"""Data-integrity checks for the intra-session detector population and labels (no model involved)."""
import sys
import numpy as np
import pandas as pd

R = "./research/extremes"
D = "./data"
sys.path.insert(0, "research/extremes/scripts/verify_0/run")
import detector_intrasession as det

for sym in ["NQ", "ES"]:
    print(f"\n===== {sym} =====")
    x = pd.read_csv(f"{R}/{sym}_extremes.csv", index_col="date", parse_dates=True)
    p = pd.read_csv(f"{R}/{sym}_hourly_panel.csv", parse_dates=["date"])
    print("extremes sessions:", len(x), x.index.min().date(), "..", x.index.max().date())
    print("n_bars distribution:", x["n_bars"].value_counts().sort_index().to_dict())
    # splice dates present?
    for dstr in ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16", "2025-12-16", "2025-12-17"]:
        print(f"  {dstr} in extremes index: {pd.Timestamp(dstr) in x.index}")
    # DST consistency
    print("tokyo_open_k vs is_dst:", pd.crosstab(x["is_dst"], x["tokyo_open_k"]).to_dict())
    print("china_open_k vs is_dst:", pd.crosstab(x["is_dst"], x["china_open_k"]).to_dict())
    # label sanity on panel
    full = p[p["n_bars"] == 9]
    g = full.groupby("date")
    mono_hi = g["high_done"].apply(lambda s: bool(np.all(np.diff(s.values) >= 0))).all()
    mono_lo = g["low_done"].apply(lambda s: bool(np.all(np.diff(s.values) >= 0))).all()
    last_hi = full[full["k"] == 8]["high_done"].eq(1).all()
    last_lo = full[full["k"] == 8]["low_done"].eq(1).all()
    print("high_done/low_done monotone in k:", mono_hi, mono_lo, "| k=8 done:", last_hi, last_lo)
    # mechanical identity: remaining_up_bp == run_hi_bp - cum_ret_bp when high_done (approx; both vs ref/close)
    dd = full.copy()
    dd["dist_run_hi"] = dd["run_hi_bp"] - dd["cum_ret_bp"]
    dd["dist_run_lo"] = dd["cum_ret_bp"] - dd["run_lo_bp"]
    done = dd[dd["high_done"] == 1]
    # exact identity: remaining_up_bp = (hi/c - 1)*1e4; dist_run_hi = (run_hi - c)/ref*1e4 -> differ by factor c/ref
    err = (done["remaining_up_bp"] - done["dist_run_hi"]).abs()
    print(f"|remaining_up - dist_run_hi| on high_done rows: median {err.median():.3f} bp, p95 {err.quantile(.95):.3f}, max {err.max():.2f}")
    # the detector population
    d = det.build_dataset(sym)
    print("detector population: sessions", d["date"].nunique(), "rows", len(d), d["date"].min().date(), "..", d["date"].max().date())
    dates = np.array(sorted(d["date"].unique()))
    print("train-only cutoff (120th session):", pd.Timestamp(dates[119]).date(), "; first OOS:", pd.Timestamp(dates[120]).date())
    blocks = det._month_blocks(dates[120:])
    print("month blocks:", len(blocks), [b[0] for b in blocks])
    h1 = int((pd.DatetimeIndex(dates[120:]) < pd.Timestamp("2025-09-01")).sum())
    print("OOS sessions:", len(dates) - 120, "H1:", h1, "H2:", len(dates) - 120 - h1)
    # feature NaN share
    print("NaN share per feature:", {f: round(float(d[f].isna().mean()), 3) for f in det.FEATURES if d[f].isna().any()})
    # excluded truncated sessions
    exc = x[x["n_bars"] < 9]
    print("truncated sessions:", len(exc), list(exc.index.strftime("%Y-%m-%d")))

# hourly splice check for 2025-12-16/17 in both symbols: look at bar-to-bar close jumps
for sym in ["NQ", "ES"]:
    h = pd.read_csv(f"{D}/{sym}_1h.csv")
    tcol = h.columns[0]
    h[tcol] = pd.to_datetime(h[tcol], utc=True).dt.tz_convert("America/New_York")
    h = h.set_index(tcol).sort_index()
    w = h.loc["2025-12-15 18:00":"2025-12-17 18:00"]
    jumps = (w["Close"].pct_change().abs() * 1e4)
    print(f"\n{sym} 2025-12-15 18:00 .. 2025-12-17 18:00: n bars {len(w)}, bars with |close chg| > 50 bp: {(jumps > 50).sum()}, max {jumps.max():.0f} bp")
    print(jumps[jumps > 50].round(0).to_string())
    for dstr in ["2025-09-16"]:
        w = h.loc[f"{dstr} 14:00":f"{dstr} 20:00"]
        j = w["Close"].pct_change().abs() * 1e4
        print(f"{sym} {dstr} 14:00-20:00 max bar-to-bar close change: {j.max():.0f} bp")
