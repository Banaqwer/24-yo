"""Data-alignment and sample checks for the pre-Asia verifier."""
import os, sys
import numpy as np, pandas as pd

ROOT = "."
EX = os.path.join(ROOT, "research", "extremes")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)

# --- 1. daily_close.csv alignment (KOSPI / N225 dates must be LOCAL trading dates) ---
dc = pd.read_csv(os.path.join(ROOT, "data", "daily_close.csv"), index_col=0, parse_dates=True)
print("daily_close columns:", list(dc.columns))
print("daily_close index sample:", dc.index[:3].tolist(), "...", dc.index[-3:].tolist())
for col in ["KOSPI", "N225", "VIX"]:
    if col in dc:
        s = dc[col].dropna()
        r = s.pct_change()
        print(f"\n{col} biggest daily moves (local-date stamping check; KOSPI/N225 crash was 2024-08-05, rebound 2024-08-06):")
        print(r.loc["2024-08-01":"2024-08-08"].round(4).to_string())

# --- 2. extremes table: n_bars distribution, splice dates presence, counts ---
for sym in ["NQ", "ES"]:
    x = pd.read_csv(os.path.join(EX, f"{sym}_extremes.csv"), index_col="date", parse_dates=True).sort_index()
    print(f"\n=== {sym}: {len(x)} sessions {x.index.min().date()}..{x.index.max().date()}")
    print("n_bars value counts:", x["n_bars"].value_counts().sort_index().to_dict())
    print("n_bars != 9 dates:", [str(d.date()) + f"(n={n})" for d, n in x["n_bars"][x["n_bars"] != 9].items()])
    splice = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"], "ES": ["2025-12-16", "2025-12-17"]}[sym]
    print("splice dates present in table:", [d for d in splice if pd.Timestamp(d) in x.index])
    full = x[(x["n_bars"] == 9) & ~x.index.isin(pd.to_datetime(splice))]
    print("after exclusions:", len(full), "| before 2025-09-01:", int((full.index < "2025-09-01").sum()))
    # geometric check: how often is the 17:00 close already beyond the RTH extreme?
    dh = full["lvl_rth_high"] / full["ref_close"] - 1
    dl = 1 - full["lvl_rth_low"] / full["ref_close"]
    print(f"17:00 close >= RTH high: {(dh <= 0).mean():.3f} (n={(dh <= 0).sum()}); P(high_above | that)={full.loc[dh <= 0, 'high_above_rth_high'].mean():.3f}")
    print(f"17:00 close <= RTH low : {(dl <= 0).mean():.3f} (n={(dl <= 0).sum()}); P(low_below | that)={full.loc[dl <= 0, 'low_below_rth_low'].mean():.3f}")
    for thr in [10, 25, 50]:
        m = dh * 1e4 > thr
        print(f"  dist to RTH high > {thr}bp: share {m.mean():.3f}, P(high_above)={full.loc[m, 'high_above_rth_high'].mean():.3f}")
    for thr in [10, 25, 50]:
        m = dl * 1e4 > thr
        print(f"  dist to RTH low  > {thr}bp: share {m.mean():.3f}, P(low_below)={full.loc[m, 'low_below_rth_low'].mean():.3f}")
    # the weekday distribution and DST
    print("dow counts:", full["dow"].value_counts().sort_index().to_dict(), "| is_dst share:", round(full["is_dst"].mean(), 3))
    # asia_rng_prev sanity: must equal previous row's realised range (shift) -> check against rng_bp of previous session in the FULL table
    xr = x.copy()
    prev_rng = ((xr["asia_high"] - xr["asia_low"]) / xr["asia_open"]).shift(1)
    diff = (xr["asia_rng_prev"] - prev_rng).abs()
    print("asia_rng_prev == prev session realised range (max abs diff over rows where both defined):", float(diff.max()), "| n mismatches>1e-9:", int((diff > 1e-9).sum()))
    # check that asia_rng_prev is NOT the same night's range
    same = (xr["asia_rng_prev"] - (xr["asia_high"] - xr["asia_low"]) / xr["asia_open"]).abs()
    print("asia_rng_prev == SAME night range count:", int((same < 1e-12).sum()))
    # asia_rng_med20 is a shifted rolling median
    med = prev_rng.rolling(20, min_periods=10).median()
    print("asia_rng_med20 matches shifted rolling median: max abs diff", float((xr["asia_rng_med20"] - med).abs().max()))
