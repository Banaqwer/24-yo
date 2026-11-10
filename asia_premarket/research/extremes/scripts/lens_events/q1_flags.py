"""Q1: every calendar flag vs the unconditional base rates (complement = flag==0).
One row per (symbol, flag, statistic) with n, rate/median, base, 90% bootstrap CI, p, and the two halves."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research/extremes/scripts/lens_events")
from common import *

PROPS = ["high_in_first_bar", "low_in_first_bar", "hi_last", "lo_last", "either_first", "both_first", "either_last",
         "high_by_tokyo_open", "low_by_tokyo_open", "high_above_rth_high", "low_below_rth_low", "hi_first",
         "same_bar_extremes", "close_loc_ext"]
MEDS = ["hi_k", "lo_k", "hi_bp", "lo_bp", "rng_bp", "close_loc", "first_bar_rng_bp", "abs_gap", "drop_after_hi_bp",
        "rally_after_lo_bp", "abs_asia_ret", "hi_vs_rth_high_bp", "lo_vs_rth_low_bp"]

rows = []
n_comp = 0
for sym in ("NQ", "ES"):
    x = load_extremes(sym)
    for f in FLAGS:
        sub = x[x[f] == 1]; base = x[x[f] == 0]
        if len(sub) == 0:
            continue
        for col in PROPS:
            r = prop_row(col, sub, base, col); n_comp += 1
            for h in ("H1", "H2"):
                s_h = sub[sub.half == h]; b_h = base[base.half == h]
                r[f"{h}_n"] = len(s_h); r[f"{h}_rate"] = s_h[col].mean() if len(s_h) else np.nan
                r[f"{h}_base"] = b_h[col].mean() if len(b_h) else np.nan
            r.update(sym=sym, flag=f, kind="prop"); rows.append(r)
        for col in MEDS:
            r = med_row(col, sub, base, col); n_comp += 1
            for h in ("H1", "H2"):
                s_h = sub[sub.half == h]; b_h = base[base.half == h]
                r[f"{h}_n"] = len(s_h); r[f"{h}_med"] = s_h[col].median() if len(s_h) else np.nan
                r[f"{h}_base"] = b_h[col].median() if len(b_h) else np.nan
            r.update(sym=sym, flag=f, kind="med"); rows.append(r)
        # hi_k / lo_k histograms
        for col in ("hi_k", "lo_k"):
            d = sub[col].value_counts(normalize=True).sort_index()
            b = base[col].value_counts(normalize=True).sort_index()
            rows.append(dict(sym=sym, flag=f, kind="hist", stat=col, n=len(sub),
                             hist=";".join(f"{int(k)}:{v:.3f}" for k, v in d.items()),
                             base_hist=";".join(f"{int(k)}:{v:.3f}" for k, v in b.items())))

out = pd.DataFrame(rows)
out.to_csv(f"{OUT}/q1_flags_table.csv", index=False)
print("comparisons:", n_comp)
# screen: proportion rows with p<0.05 and n>=15
scr = out[(out.kind == "prop") & (out.p < 0.05)].sort_values("p")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
print(scr[["sym", "flag", "stat", "n", "k", "rate", "base", "ci_lo", "ci_hi", "p", "H1_n", "H1_rate", "H1_base", "H2_n", "H2_rate", "H2_base"]].round(3).to_string())
scr = out[(out.kind == "med") & (out.p < 0.05)].sort_values("p")
print(scr[["sym", "flag", "stat", "n", "med", "base_med", "ci_lo", "ci_hi", "diff_ci_lo", "diff_ci_hi", "p", "H1_n", "H1_med", "H1_base", "H2_n", "H2_med", "H2_base"]].round(2).to_string())
