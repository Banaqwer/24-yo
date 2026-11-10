"""Check predict_tonight on the last session and on a Sunday / FOMC-eve session; verify no leakage
in the OOS CSV (every prediction date later than the first MIN_TRAIN sessions) and that
evaluate() reproduces the tables from the saved CSV."""
import sys, json, time
sys.path.insert(0, "./research/extremes")
import numpy as np, pandas as pd
import detector_preasia as dp

for sym in ("NQ", "ES"):
    oos = pd.read_csv(f"./research/extremes/oos_preasia_{sym}.csv", index_col="date", parse_dates=True)
    x = dp.load_extremes(sym)
    print(sym, "OOS rows", len(oos), "first OOS", oos.index.min().date(), "position of first OOS session in the table:",
          int(np.where(x.index == oos.index.min())[0][0]), "(>= 120 required)")
    print("  cal_on share (primary sets):", {t: round(oos[f"{t}__{dp.PRIMARY_SET[t]}__cal_on"].mean(), 2) for t in dp.BINARY_TARGETS[:3]})
    m = dp.evaluate(oos, sym)
    print("  evaluate() from CSV ok; binary rows", len(m["binary"]), "quant rows", len(m["quantile"]))

t0 = time.time()
r = dp.predict_tonight("NQ", "2026-11-06")
print("predict_tonight NQ 2026-11-06 took", round(time.time() - t0, 1), "s")
print(json.dumps({k: r[k] for k in ("date", "ref_close_17h", "rth_high", "rth_low", "n_train", "tokyo_open_k")}, indent=None))
print("probabilities:", json.dumps(r["probabilities"], indent=None))
print("quantiles_bp:", json.dumps(r["quantiles_bp"], indent=None))
print("quantiles_price:", json.dumps(r["quantiles_price"], indent=None))
print("map:", json.dumps(r["map"], indent=None))
print("contributions:", json.dumps(r["contributions"], indent=None))
# a Sunday reopen and an FOMC eve for sanity
for d in ("2026-10-30", "2026-10-27"):
    r = dp.predict_tonight("NQ", d)
    print(d, "sunday", r["features"]["sunday_open"], "fomc_tomorrow", r["features"]["fomc_tomorrow"],
          {t: r["probabilities"][t]["p_cal"] for t in ("low_in_first_bar", "low_by_tokyo_open", "hi_first", "high_in_last_bar", "high_above_rth_high")},
          "map low:", r["map"]["lo_k"]["p_by_bar"])
