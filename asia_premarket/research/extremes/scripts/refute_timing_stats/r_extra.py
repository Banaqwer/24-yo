import numpy as np, pandas as pd
ROOT = "."
BAD = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"], "ES": ["2025-12-15", "2025-12-16", "2025-12-17"]}
for sym in ["NQ", "ES"]:
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    x = x[~x.index.isin(pd.to_datetime(BAD[sym]))]
    dh = (x.lvl_rth_high / x.ref_close - 1) * 1e4
    hb = x.hi_bp.values
    # mechanical prediction: unconditional survival P(hi_bp > d) averaged over sessions in bucket
    def surv(d): return (hb > d).mean()
    print(f"{sym}: T10 mechanical check (observed break rate vs mean unconditional P(hi_bp>dist))")
    for lab, m in [("<10", dh < 10), ("10-25", (dh >= 10) & (dh < 25)), ("25-50", (dh >= 25) & (dh < 50)), ("50-100", (dh >= 50) & (dh < 100)), (">=100", dh >= 100)]:
        obs = x.loc[m, "high_above_rth_high"].mean(); mech = np.mean([surv(d) for d in dh[m]])
        print(f"   {lab:7s} n={m.sum()} observed {obs:.3f} mechanical {mech:.3f}  median hi_bp in bucket {x.loc[m,'hi_bp'].median():.1f} (all {x.hi_bp.median():.1f})")
    # T9: four main levels variants
    w = 5
    a = (x.hi_vs_rth_high_bp.abs() <= w); b = (x.hi_vs_rth_vwap_bp.abs() <= w); c = (x.hi_vs_prior_asia_high_bp.abs() <= w); d = (x.hi_bp.abs() <= w)
    e = ((x.asia_high / x.lvl_rth_low - 1).abs() * 1e4 <= w)
    print(f"   T9 highs within 5bp of any of {{RTH high, VWAP, prior Asia high, 17:00 close}}: {(a|b|c|d).mean():.3f}; of {{RTH high, RTH low, VWAP, prior asia high}}: {(a|b|c|e).mean():.3f}; of all five {(a|b|c|d|e).mean():.3f}")
    print(f"   same_bar_extremes sessions: {int(x.same_bar_extremes.sum())} of {len(x)}")
