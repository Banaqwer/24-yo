import numpy as np, pandas as pd
from scipy import stats
import sys
sys.path.insert(0, "research/extremes/scripts/refute_events_stats")
exec(open("research/extremes/scripts/refute_events_stats/recompute_flags.py").read().split("for sym in (\"NQ\", \"ES\"):")[0])

for sym in ("NQ", "ES"):
    x = load(sym); p = load_panel(sym)
    print(f"\n===== {sym} =====")
    # E8: panel low_done at k=2,3 vs WEEKNIGHT base
    t8 = x[x.tier1_data_tomorrow == 1]; wk = x[x.sunday_open == 0]
    pw = p[p.date.isin(wk.index)]
    done_rates(pw, t8.index, "tier1_tmrw vs weeknights", "low_done", ks=[1, 2, 3, 4])
    o8w = wk[wk.tier1_data_tomorrow == 0]
    med(t8, o8w, "hi_vs_rth_high_bp", label="hi_vs_rth_high (wk base)")
    med(t8, o8w, "rng_bp", label="rng (wk base)")
    # E3: Friday direction as the simpler feature on Sundays and on weeknights
    sun = x[x.sunday_open == 1]
    for lab, d in (("sunday", sun), ("weeknight", wk)):
        a = d[d.is_down == 1]; b = d[d.is_down == 0]
        print(f"  {lab}: P(low<RTH low | RTH down)={a.low_below_rth_low.mean():.3f} (n={len(a)}) vs RTH up {b.low_below_rth_low.mean():.3f} (n={len(b)}) fisher p={stats.fisher_exact([[int(a.low_below_rth_low.sum()), len(a)-int(a.low_below_rth_low.sum())],[int(b.low_below_rth_low.sum()), len(b)-int(b.low_below_rth_low.sum())]])[1]:.3g}")
    s3 = sun[sun.tier1_data_today == 1]; o3 = sun[sun.tier1_data_today == 0]
    # within down-Fridays: tier1 vs not
    a = s3[s3.is_down == 1]; b = o3[o3.is_down == 1]
    print(f"  down-Friday Sundays: tier1 {a.low_below_rth_low.mean():.3f} (n={len(a)}) vs other {b.low_below_rth_low.mean():.3f} (n={len(b)}) fisher p={stats.fisher_exact([[int(a.low_below_rth_low.sum()), len(a)-int(a.low_below_rth_low.sum())],[int(b.low_below_rth_low.sum()), len(b)-int(b.low_below_rth_low.sum())]])[1]:.3g}")
    # E3: the lens's p-value vs Fisher for the headline
    print(f"  E3 headline: {int(s3.low_below_rth_low.sum())}/{len(s3)} vs {int(o3.low_below_rth_low.sum())}/{len(o3)}")
    # E13 witching
    # E12 both_first sessions
    me = x[(x.month_end == 1) & (x.both_first == 1)]
    print(f"  month_end both_first sessions: {list(me.index.strftime('%Y-%m-%d'))} sunday={me.sunday_open.tolist()}")

# Global FDR estimate from the lens's own flag screen
q1 = pd.read_csv("research/extremes/scripts/lens_events/q1_flags_table.csv")
print("\nq1 flag screen columns:", list(q1.columns)[:20], "rows:", len(q1))
pc = [c for c in q1.columns if c == "p" or c.endswith("_p") or c.startswith("p_")]
print("p columns:", pc)
for c in pc:
    v = q1[c].dropna()
    print(f"  {c}: n={len(v)}  p<0.05: {(v<0.05).sum()} (expected under null {0.05*len(v):.0f})  p<0.01: {(v<0.01).sum()} (exp {0.01*len(v):.0f})  p<2e-5: {(v<2e-5).sum()}")
    # Benjamini-Hochberg at q=0.10
    vs = np.sort(v.values); m = len(vs); thr = 0.10 * np.arange(1, m + 1) / m
    ok = np.where(vs <= thr)[0]
    print(f"    BH q=0.10 rejects {len(ok)} (largest p accepted {vs[ok.max()]:.2e})" if len(ok) else "    BH q=0.10 rejects 0")
    if len(ok):
        sig = q1[q1[c] <= vs[ok.max()]]
        cols = [k for k in ["sym", "flag", "stat", "n", "rate", "base", "med", "base_med", c] if k in sig.columns]
        print(sig[cols].sort_values(c).to_string())
