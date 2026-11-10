"""Extra walk-forward logistic specs: features the first pass omitted and small calendar/structure sets.
Also a scaled-distance single-feature model for the beyond-RTH targets."""
import sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
OUT = "research/extremes/scripts/lens_context"
sys.path.insert(0, OUT)
from wf_logit import walk_forward, base_rate, brier, skill_ci

EXTRA_UNI = ["asia_rng_prev", "dist_20d_high", "vvix", "gold_chg", "usdjpy_chg", "streak", "crude_chg", "rth_ret_z",
             "is_monday", "is_sunday", "fomc_tomorrow", "scaled_dist_high", "scaled_dist_low", "n225_in_dir", "sx5e_ret", "abs_post"]
SETS = {
    "cal": ["is_sunday", "is_monday", "fomc_tomorrow", "fomc_today", "megacap_earnings_tonight", "pre_holiday", "month_end", "tier1_data_tomorrow"],
    "dir+cal": ["is_sunday", "is_monday", "fomc_tomorrow", "is_down", "rth_ret_z", "clv", "close_vs_vwap_rng", "streak"],
    "timing6": ["is_sunday", "is_monday", "fomc_tomorrow", "rth_ret_z", "asia_rng_prev", "rth_range_atr"],
    "scaled_levels": ["scaled_dist_high", "scaled_dist_low", "is_down", "clv"],
}
TARGETS = ["hi_first", "high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar",
           "high_by_tokyo_open", "low_by_tokyo_open", "high_above_rth_high", "low_below_rth_low",
           "close_top20", "close_bot20", "close_with_dir", "with_in_first_bar", "against_in_first_bar"]


def run(sym):
    df = pd.read_csv(f"{OUT}/frame_{sym}.csv", index_col=0, parse_dates=True).sort_index()
    df["is_monday"] = (df.dow == 0).astype(int); df["is_sunday"] = (df.dow == 4).astype(int)
    df["scaled_dist_high"] = df["dist_rth_high0"] / (df["asia_rng_med20"] * 1e4)
    df["scaled_dist_low"] = -df["dist_rth_low0"] / (df["asia_rng_med20"] * 1e4)
    rows = []
    h1 = (df.half == "H1").values; h2 = ~h1
    for t in TARGETS:
        y = df[t].values.astype(float); pb = base_rate(df, t); b0, _ = brier(y, pb)
        specs = {f"uni:{f}": ([f], 1.0) for f in EXTRA_UNI}
        specs.update({k: (v, 1.0) for k, v in SETS.items()})
        for name, (feats, C) in specs.items():
            p = walk_forward(df, feats, t, C)
            b, n = brier(y, p); b1, _ = brier(y[h1], p[h1]); b2, _ = brier(y[h2], p[h2])
            bb1, _ = brier(y[h1], pb[h1]); bb2, _ = brier(y[h2], pb[h2])
            lo, hi = skill_ci(y, p, pb)
            rows.append(dict(sym=sym, target=t, model=name, n_oos=n, base_rate=np.nanmean(y), brier_base=b0, brier=b,
                             skill=1 - b / b0, skill_ci_lo=lo, skill_ci_hi=hi, skill_h1=1 - b1 / bb1, skill_h2=1 - b2 / bb2))
    res = pd.DataFrame(rows); res.to_csv(f"{OUT}/wf_extra_{sym}.csv", index=False)
    pd.set_option("display.width", 250)
    print(res.sort_values("skill", ascending=False).groupby("target").head(5).round(4).to_string(index=False))


if __name__ == "__main__":
    for sym in sys.argv[1:] or ["NQ"]:
        run(sym)
