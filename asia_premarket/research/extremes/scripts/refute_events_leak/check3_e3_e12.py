import sys, numpy as np, pandas as pd
sys.path.insert(0, "research/extremes/scripts/lens_events")
from common import load_extremes, binom_p, boot_ci, mw_p
pd.set_option("display.width", 250)
for s in ("NQ", "ES"):
    x = load_extremes(s)
    sun = x[x.sunday_open == 1]
    t = sun[sun.tier1_data_today == 1]; o = sun[sun.tier1_data_today == 0]
    nfp = t[t.events_today.str.contains("NFP")]; pce = t[~t.events_today.str.contains("NFP")]
    for lab, d in (("NFP Sundays", nfp), ("PCE/CPI Sundays", pce), ("all tier1 Sundays", t)):
        k = int(d.low_below_rth_low.sum()); n = len(d); p0 = o.low_below_rth_low.mean()
        print(f"{s} {lab}: low_below_rth_low {k}/{n}={k/n:.3f} vs other Sundays {p0:.3f} p={binom_p(k,n,p0):.4f} CI {tuple(round(v,3) for v in boot_ci(d.low_below_rth_low.values))}; "
              f"H1 {d[d.half=='H1'].low_below_rth_low.mean():.2f} (n={len(d[d.half=='H1'])}) H2 {d[d.half=='H2'].low_below_rth_low.mean():.2f} (n={len(d[d.half=='H2'])}); med lo_vs_rth_low {d.lo_vs_rth_low_bp.median():.1f} vs {o.lo_vs_rth_low_bp.median():.1f}")
    # E12: tier1_today |gap| weeknights only
    w = x[x.sunday_open == 0]
    a = w[w.tier1_data_today == 1]; b = w[w.tier1_data_today == 0]
    print(f"{s} tier1_today weeknights n={len(a)}: |gap| med {a.abs_gap.median():.1f} vs {b.abs_gap.median():.1f} p={mw_p(a.abs_gap, b.abs_gap):.3f}")
    a = x[x.tier1_data_today == 1]; print(f"{s} tier1_today all (incl 38 Sundays) |gap| med {a.abs_gap.median():.1f}")
