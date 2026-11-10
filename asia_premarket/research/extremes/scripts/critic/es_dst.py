"""ES base rates (missing from the report) and DST-split hour-of-extreme tables for both symbols."""
import sys; sys.path.insert(0, "research/extremes/scripts/critic")
from common import *

for sym in ["NQ", "ES"]:
    x = load_x(sym)
    print(f"\n===== {sym}: n={len(x)} full sessions ex splice; H1 {len(halves(x)[0])} H2 {len(halves(x)[1])} =====")
    hk = (x.hi_k.value_counts(normalize=True).sort_index() * 100).round(1)
    lk = (x.lo_k.value_counts(normalize=True).sort_index() * 100).round(1)
    print(" hour of HIGH by k %:", hk.tolist()); print(" hour of LOW  by k %:", lk.tolist())
    for nm, xx in zip(["H1", "H2"], halves(x)):
        print(f"  {nm} high: {(xx.hi_k.value_counts(normalize=True).sort_index()*100).round(1).tolist()}")
        print(f"  {nm} low : {(xx.lo_k.value_counts(normalize=True).sort_index()*100).round(1).tolist()}")
    print(f" high by Tokyo {x.high_by_tokyo_open.mean():.3f} low by Tokyo {x.low_by_tokyo_open.mean():.3f} hi>RTH {x.high_above_rth_high.mean():.3f} lo<RTH {x.low_below_rth_low.mean():.3f} both {((x.high_above_rth_high==1)&(x.low_below_rth_low==1)).sum()} hi_first {x.hi_first.mean():.3f} (down {x[x.is_down==1].hi_first.mean():.3f} up {x[x.is_down==0].hi_first.mean():.3f})")
    print(f" median hi_bp {x.hi_bp.median():+.1f} lo_bp {x.lo_bp.median():+.1f} rng {x.rng_bp.median():.1f}; drop after high {x.drop_after_hi_bp.median():.1f} rally after low {x.rally_after_lo_bp.median():.1f}")
    print(f" bar0 low-vs-high paired diff {fmt(ci_diff(x.low_in_first_bar, x.high_in_first_bar))}; bar8 high-vs-low {fmt(ci_diff(x.high_in_last_bar, x.low_in_last_bar))}")
    # DST split
    for dst, lab in [(0, "EST (tokyo k=1, china k=2)"), (1, "EDT (tokyo k=2, china k=3)")]:
        xx = x[x.is_dst == dst]
        print(f"  {lab} n={len(xx)}: high % {(xx.hi_k.value_counts(normalize=True).reindex(range(9)).fillna(0)*100).round(1).tolist()}")
        print(f"  {' '*len(lab)}      low  % {(xx.lo_k.value_counts(normalize=True).reindex(range(9)).fillna(0)*100).round(1).tolist()}")
        print(f"      high by Tokyo {xx.high_by_tokyo_open.mean():.3f} low by Tokyo {xx.low_by_tokyo_open.mean():.3f}; extreme AT Tokyo bar: high {xx.high_at_tokyo_open.mean():.3f} low {xx.low_at_tokyo_open.mean():.3f}; AT China bar: high {xx.high_at_china_open.mean():.3f} low {xx.low_at_china_open.mean():.3f}")
    # Section-2 style rows for ES
    sun = x[x.sunday_open == 1]; wk = x[x.sunday_open == 0]; mon = x[x.dow == 0]; nmon = x[(x.dow != 0)]
    print(f" Sunday n={len(sun)}: low_in_bar0 {fmt(ci_prop(sun.low_in_first_bar))} vs {wk.low_in_first_bar.mean():.3f}; low_by_tokyo {fmt(ci_prop(sun.low_by_tokyo_open))} vs {wk.low_by_tokyo_open.mean():.3f} p={binom_p(sun.low_by_tokyo_open.sum(), len(sun), wk.low_by_tokyo_open.mean()):.4f}; "
          f"H1 {sun[sun.index<H2].low_by_tokyo_open.mean():.3f} H2 {sun[sun.index>=H2].low_by_tokyo_open.mean():.3f}; high_in_bar0 {sun.high_in_first_bar.mean():.3f} med rng {sun.rng_bp.median():.0f} vs {wk.rng_bp.median():.0f}")
    print(f" Monday n={len(mon)}: low_in_bar0 {fmt(ci_prop(mon.low_in_first_bar))} vs {nmon.low_in_first_bar.mean():.3f} p={binom_p(mon.low_in_first_bar.sum(), len(mon), nmon.low_in_first_bar.mean()):.4f}; H1 {mon[mon.index<H2].low_in_first_bar.mean():.3f} (n={len(mon[mon.index<H2])}) H2 {mon[mon.index>=H2].low_in_first_bar.mean():.3f} (n={len(mon[mon.index>=H2])}); low_by_tokyo {mon.low_by_tokyo_open.mean():.3f} vs {nmon.low_by_tokyo_open.mean():.3f}")
    fe = x[x.fomc_tomorrow == 1]
    print(f" FOMC eve n={len(fe)}: hi_first {fe.hi_first.sum()}/{len(fe)}; close>ref {(fe.close_bp>0).sum()}/{len(fe)}; low_in_bar0 {fe.low_in_first_bar.mean():.2f}; high_in_last {fe.high_in_last_bar.mean():.2f}")
    for nm, m in [("up", x.is_down == 0), ("down", x.is_down == 1)]:
        xx = x[m]
        print(f" RTH {nm} n={len(xx)}: hi>RTH {fmt(ci_prop(xx.high_above_rth_high))} lo<RTH {fmt(ci_prop(xx.low_below_rth_low))} med {xx.hi_bp.median():+.0f}/{xx.lo_bp.median():+.0f}/{xx.rng_bp.median():.0f}")
    d = (x.lvl_rth_high / x.ref_close - 1) / x.asia_rng_med20
    edges = [-np.inf, .10, .25, .5, .75, 1.0, 1.5, np.inf]
    g = x.groupby(pd.cut(d, edges), observed=True).high_above_rth_high.agg(["size", "mean"])
    print(" scaled dist to RTH high ladder: n", g["size"].tolist(), "P(hi>RTH)", g["mean"].round(3).tolist())
    d2 = (1 - x.lvl_rth_low / x.ref_close) / x.asia_rng_med20
    g2 = x.groupby(pd.cut(d2, edges), observed=True).low_below_rth_low.agg(["size", "mean"])
    print(" scaled dist to RTH low  ladder: n", g2["size"].tolist(), "P(lo<RTH)", g2["mean"].round(3).tolist())
    t = pd.qcut(x.vix, 3)
    print(" VIX terciles median range:", x.groupby(t, observed=True).rng_bp.median().round(1).tolist(), "edges", [round(iv.right, 2) for iv in t.cat.categories])
    mc = x[x.megacap_earnings_tonight == 1]
    print(f" megacap n={len(mc)}: med rng {mc.rng_bp.median():.0f} vs {x[x.megacap_earnings_tonight==0].rng_bp.median():.0f}; hi>RTH {mc.high_above_rth_high.mean():.3f} vs {x[x.megacap_earnings_tonight==0].high_above_rth_high.mean():.3f}")
    # Monday x Sunday-less weekday comparison for timing columns, and the Tokyo bump
    edt = x[x.is_dst == 1]
    print(f" EDT Tokyo-bar (k=2) share of highs: all {(edt.hi_k==2).mean():.3f} (n={len(edt)}) H1 {(edt[edt.index<H2].hi_k==2).mean():.3f} (n={len(edt[edt.index<H2])}) H2 {(edt[edt.index>=H2].hi_k==2).mean():.3f} (n={len(edt[edt.index>=H2])})")

# NQ vs ES same-bar agreement
xn = load_x("NQ"); xe = load_x("ES")
j = xn[["hi_k", "lo_k"]].join(xe[["hi_k", "lo_k"]], lsuffix="_nq", rsuffix="_es", how="inner")
print(f"\nNQ/ES same bar: high {(j.hi_k_nq==j.hi_k_es).mean():.3f} low {(j.lo_k_nq==j.lo_k_es).mean():.3f} n={len(j)}")
