"""Detector encodings: P(high_done | close of bar k, flag) and P(low_done | k, flag) vs the flag==0 base,
for the flags that showed timing effects.  Also P(low_done | k, flag, bars_since_lo>=1)."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research/extremes/scripts/lens_events")
from common import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)

FL = ["sunday_open", "fomc_tomorrow", "fomc_today", "megacap_earnings_tonight", "tier1_data_tomorrow", "tier1_data_today", "cn_data_tonight"]
rows = []
for sym in ("NQ", "ES"):
    x = load_extremes(sym); p = load_panel(sym)
    p = p.merge(x[FL + ["half"]].rename(columns={"half": "h"}), left_on="date", right_index=True)
    full = p[p.n_bars == 9]
    for f in FL:
        for k in range(9):
            d = full[full.k == k]
            a = d[d[f] == 1]; b = d[d[f] == 0]
            if f == "cn_data_tonight":  # stratify away Sunday
                a = a[a.sunday_open == 0]; b = b[b.sunday_open == 0]
            for lab in ("high_done", "low_done"):
                r = dict(sym=sym, flag=f, k=k, label=lab, n=len(a), rate=a[lab].mean(), base=b[lab].mean(),
                         p=binom_p(a[lab].sum(), len(a), b[lab].mean()),
                         H1_rate=a[a.h == "H1"][lab].mean(), H1_base=b[b.h == "H1"][lab].mean(),
                         H2_rate=a[a.h == "H2"][lab].mean(), H2_base=b[b.h == "H2"][lab].mean(),
                         med_remaining=a["remaining_up_bp" if lab == "high_done" else "remaining_down_bp"].median(),
                         base_remaining=b["remaining_up_bp" if lab == "high_done" else "remaining_down_bp"].median())
                rows.append(r)
out = pd.DataFrame(rows); out.to_csv(f"{OUT}/q4_panel_done_rates.csv", index=False)
for f in FL:
    for lab in ("high_done", "low_done"):
        s = out[(out.flag == f) & (out.label == lab)]
        print(f"\n--- {f} / {lab}")
        print(s[["sym", "k", "n", "rate", "base", "p", "H1_rate", "H1_base", "H2_rate", "H2_base", "med_remaining", "base_remaining"]].round(3).to_string(index=False))

# Sunday: P(low_done | k, bars_since_lo >= 1) i.e. the running low has held one bar
print("\n--- Sunday: P(low_done | k, bars_since_lo>=1) vs weekday")
for sym in ("NQ", "ES"):
    x = load_extremes(sym); p = load_panel(sym)
    p = p.merge(x[["sunday_open"]], left_on="date", right_index=True)
    full = p[(p.n_bars == 9)]
    for k in (1, 2, 3):
        d = full[(full.k == k) & (full.bars_since_lo >= 1)]
        a = d[d.sunday_open == 1]; b = d[d.sunday_open == 0]
        print(sym, "k", k, "sunday n", len(a), round(a.low_done.mean(), 3), "weekday n", len(b), round(b.low_done.mean(), 3), "p", round(binom_p(a.low_done.sum(), len(a), b.low_done.mean()), 4))
        d = full[(full.k == k) & (full.bars_since_lo == k)]  # low still the 18:00-bar low
        a = d[d.sunday_open == 1]; b = d[d.sunday_open == 0]
        print(sym, "k", k, "low still in bar0: sunday n", len(a), round(a.low_done.mean(), 3), "weekday n", len(b), round(b.low_done.mean(), 3), "p", round(binom_p(a.low_done.sum(), len(a), b.low_done.mean()), 4))
