"""Recompute report numbers from the tables (traceability check)."""
import sys; sys.path.insert(0, "research/extremes/scripts/critic")
from common import *
from sklearn.metrics import roc_auc_score

print("=== R1. Section 2 table rows (NQ, base row n=578 in the report) ===")
x_all = load_x("NQ", full=False, drop_splice=False)
print("rows in NQ_extremes.csv:", len(x_all), "| full 9-bar:", (x_all.n_bars == 9).sum(), "| after splice drop (6 dates):", len(load_x('NQ', full=False)))
for name, x in [("all rows", x_all), ("ex splice", load_x("NQ", full=False)), ("full+ex splice", load_x("NQ"))]:
    sun = x[x.sunday_open == 1]; mon = x[x.dow == 0]
    print(f" [{name} n={len(x)}] low_in_bar0 {x.low_in_first_bar.mean():.3f} low_by_tokyo {x.low_by_tokyo_open.mean():.3f} "
          f"high_in_bar0 {x.high_in_first_bar.mean():.3f} high_in_last {x.high_in_last_bar.mean():.3f} "
          f"hi>rth {x.high_above_rth_high.mean():.3f} lo<rth {x.low_below_rth_low.mean():.3f} med hi/lo/rng {x.hi_bp.median():.0f}/{x.lo_bp.median():.0f}/{x.rng_bp.median():.0f}")
    print(f"   Sunday n={len(sun)}: low_in_bar0 {fmt(ci_prop(sun.low_in_first_bar))} low_by_tokyo {fmt(ci_prop(sun.low_by_tokyo_open))} vs weekday {x[x.sunday_open==0].low_by_tokyo_open.mean():.3f}; med rng {sun.rng_bp.median():.0f}")
    print(f"   Monday n={len(mon)}: low_in_bar0 {fmt(ci_prop(mon.low_in_first_bar))} vs non-Mon {x[x.dow!=0].low_in_first_bar.mean():.3f}; low_by_tokyo {fmt(ci_prop(mon.low_by_tokyo_open))}")
x = load_x("NQ", full=False)
h1, h2 = halves(x)
for nm, xx in [("H1", h1), ("H2", h2)]:
    mon = xx[xx.dow == 0]; sun = xx[xx.sunday_open == 1]
    print(f"   {nm}: Monday low_in_bar0 {mon.low_in_first_bar.mean():.3f} (n={len(mon)}) vs other {xx[xx.dow!=0].low_in_first_bar.mean():.3f}; "
          f"Sunday low_by_tokyo {sun.low_by_tokyo_open.mean():.3f} (n={len(sun)}) vs {xx[xx.sunday_open==0].low_by_tokyo_open.mean():.3f}")
print("   Monday p (binom vs non-Monday rate):", f"{binom_p(mon.low_in_first_bar.sum(), len(mon), x[x.dow!=0].low_in_first_bar.mean()):.4f}" if False else
      f"{binom_p(x[x.dow==0].low_in_first_bar.sum(), (x.dow==0).sum(), x[x.dow!=0].low_in_first_bar.mean()):.4f}")

print("\n=== R2. RTH up / down rows ===")
for nm, m in [("up", x.is_down == 0), ("down", x.is_down == 1)]:
    xx = x[m]
    print(f" {nm} n={len(xx)}: hi>rth {fmt(ci_prop(xx.high_above_rth_high))} lo<rth {fmt(ci_prop(xx.low_below_rth_low))} med {xx.hi_bp.median():.0f}/{xx.lo_bp.median():.0f}/{xx.rng_bp.median():.0f}; hi_first {xx.hi_first.mean():.3f}")

print("\n=== R3. Scaled-distance ladder to the RTH high ===")
d = (x.lvl_rth_high / x.ref_close - 1) / x.asia_rng_med20
edges = [-np.inf, .10, .25, .5, .75, 1.0, 1.5, np.inf]
b = pd.cut(d, edges)
g = x.groupby(b, observed=True).high_above_rth_high.agg(["size", "mean"])
print(g.T.round(3).to_string())
d2 = (1 - x.lvl_rth_low / x.ref_close) / x.asia_rng_med20
g2 = x.groupby(pd.cut(d2, edges), observed=True).low_below_rth_low.agg(["size", "mean"])
print(g2.T.round(3).to_string())
w10 = x[(x.lvl_rth_high / x.ref_close - 1) * 1e4 <= 10]
print(f" 17:00 close within 10 bp of RTH high (incl. above): n={len(w10)} hi>rth {fmt(ci_prop(w10.high_above_rth_high))}")
w100 = x[(x.lvl_rth_high / x.ref_close - 1) * 1e4 >= 100]
print(f" >=100 bp below RTH high: n={len(w100)} hi>rth {fmt(ci_prop(w100.high_above_rth_high))}")

print("\n=== R4. VIX terciles -> median range ===")
t = pd.qcut(x.vix, 3)
print(x.groupby(t, observed=True).rng_bp.agg(["size", "median"]).round(1).to_string())
for lab, grp in x.groupby(t, observed=True):
    print("  ", lab, fmt(ci_med(grp.rng_bp.values), pct=False))

print("\n=== R5. Mega-cap earnings and |post_ret|>=25bp ===")
mc = x[x.megacap_earnings_tonight == 1]; nmc = x[x.megacap_earnings_tonight == 0]
print(f" megacap n={len(mc)}: med rng {mc.rng_bp.median():.1f} vs {nmc.rng_bp.median():.1f}; first-bar rng med {mc.first_bar_rng_bp.median():.1f} vs {nmc.first_bar_rng_bp.median():.1f}; "
      f"|gap| {mc.gap_open_bp.abs().median():.1f} vs {nmc.gap_open_bp.abs().median():.1f}; hi>rth {mc.high_above_rth_high.mean():.3f}; high_in_bar0 {mc.high_in_first_bar.mean():.3f} low_in_bar0 {mc.low_in_first_bar.mean():.3f}")
pr = x[x.post_ret.abs() >= 0.0025]
print(f" |post|>=25bp n={len(pr)}: med rng {pr.rng_bp.median():.1f}; high_in_bar0 {pr.high_in_first_bar.mean():.3f}")
side = np.where(pr.post_ret > 0, pr.high_above_rth_high, pr.low_below_rth_low)
print(f"   post_ret side taken {side.mean():.3f} (n={len(pr)})")

print("\n=== R6. T6 rule: bars_since_hi>=2 & pos<0.35 & run_rng_vs_med20>=1 ===")
for sym in ["NQ", "ES"]:
    p = load_panel(sym); p = p[p.k <= 7]
    r = p[(p.bars_since_hi >= 2) & (p.pos_in_range < 0.35) & (p.run_rng_vs_med20 >= 1)]
    rh1 = r[r.date < H2]; rh2 = r[r.date >= H2]
    print(f" {sym}: P(high_done)={fmt(ci_prop(r.high_done))} n={len(r)} ({r.date.nunique()} sessions); H1 {rh1.high_done.mean():.3f} (n={len(rh1)}) H2 {rh2.high_done.mean():.3f} (n={len(rh2)})")
    rl = p[(p.bars_since_lo >= 2) & (p.pos_in_range > 0.65) & (p.run_rng_vs_med20 >= 1)]
    print(f"   low rule: {fmt(ci_prop(rl.low_done))} n={len(rl)}")
    bs0 = p[p.bars_since_hi == 0]
    print(f"   bars_since_hi==0: P(high_done)={bs0.high_done.mean():.3f} n={len(bs0)}  (rows k<=7, full sessions)")
    # hold rates table, unconditional and pos<0.25
    unc = p.groupby("k").high_done.mean().round(2).tolist()
    lowq = p[p.pos_in_range < 0.25].groupby("k").high_done.agg(["mean", "size"])
    print(f"   P(high_done|k) {unc}; pos<0.25: {lowq['mean'].round(2).tolist()} n={lowq['size'].tolist()}")
    # Tokyo-open bar
    tk = p[(p.k == p.tokyo_open_k)]
    a = tk[tk.pos_in_range < 0.2]; b_ = tk[tk.pos_in_range >= 0.8]
    print(f"   Tokyo-open bar pos<0.2 P(high_done)={fmt(ci_prop(a.high_done))} n={len(a)} | EST {a[a.is_dst==0].high_done.mean():.3f} EDT {a[a.is_dst==1].high_done.mean():.3f}; pos>=0.8 P(low_done)={fmt(ci_prop(b_.low_done))} n={len(b_)}")

print("\n=== R7. Bar-0 close location (T1) ===")
for sym in ["NQ", "ES"]:
    p = load_panel(sym); p0 = p[p.k == 0]
    b = pd.cut(p0.bar_close_loc, [-0.01, 0.2, 0.5, 0.8, 1.01])
    g = p0.groupby(b, observed=True).agg(n=("low_done", "size"), low_in_bar0=("low_done", "mean"), high_in_bar0=("high_done", "mean"))
    print(sym); print(g.round(3).to_string())
    hi_ = p0[p0.bar_close_loc >= 0.8]
    print("   >=0.8 low_in_bar0", fmt(ci_prop(hi_.low_done)))

print("\n=== R8. Detector A OOS metrics from oos_intrasession_NQ.csv ===")
for sym in ["NQ", "ES"]:
    o = pd.read_csv(os.path.join(EXT, f"oos_intrasession_{sym}.csv"), parse_dates=["date"])
    for side in ["high", "low"]:
        y = o[f"{side}_done"].values
        bb = np.mean((o[f"base_{side}"] - y) ** 2); bk = np.mean((o[f"kbase_{side}"] - y) ** 2)
        bf = np.mean((o[f"p_{side}_done"] - y) ** 2); br = np.mean((o[f"p_{side}_raw"] - y) ** 2)
        auc = roc_auc_score(y, o[f"p_{side}_done"])
        h1 = o[o.date < H2]; h2 = o[o.date >= H2]
        sk = lambda g: 1 - np.mean((g[f"p_{side}_done"] - g[f"{side}_done"]) ** 2) / np.mean((g[f"kbase_{side}"] - g[f"{side}_done"]) ** 2)
        flag = o[o[f"p_{side}_done"] >= 0.9]
        flag95 = o[o[f"p_{side}_done"] >= 0.95]
        lowf = o[o[f"p_{side}_done"] <= 0.10]
        print(f" {sym} {side}: brier base {bb:.3f} k-only {bk:.3f} final {bf:.3f} raw {br:.3f} AUC {auc:.3f} skill vs k-only {1-bf/bk:+.3f} H1 {sk(h1):+.3f} H2 {sk(h2):+.3f} | "
              f"p>=.9: share {len(flag)/len(o):.3f} prec {flag[f'{side}_done'].mean():.3f} n={len(flag)} recall {flag[f'{side}_done'].sum()/y.sum():.3f}; p>=.95 prec {flag95[f'{side}_done'].mean():.3f} n={len(flag95)}; p<=.1 done-rate {lowf[f'{side}_done'].mean():.3f} n={len(lowf)}")
    print("  sessions", o.date.nunique(), "rows", len(o), "H1 sessions", o[o.date < H2].date.nunique(), "H2", o[o.date >= H2].date.nunique(), "blocks", o.refit_block.nunique())

print("\n=== R9. Detector B level targets from oos_preasia ===")
for sym in ["NQ", "ES"]:
    o = pd.read_csv(os.path.join(EXT, f"oos_preasia_{sym}.csv"), index_col="date", parse_dates=True)
    for t in ["high_above_rth_high", "low_below_rth_low"]:
        y = o[f"{t}__y"].values; p = o[f"{t}__full__p_cal"].values; b = o[f"{t}__full__base"].values
        sk = 1 - np.mean((p - y) ** 2) / np.mean((b - y) ** 2)
        rng = np.random.default_rng(0); bs = []
        for _ in range(1000):
            i = rng.integers(0, len(y), len(y)); bs.append(1 - np.mean((p[i] - y[i]) ** 2) / np.mean((b[i] - y[i]) ** 2))
        m1 = (o.half == "H1").values
        print(f" {sym} {t}: n={len(y)} skill {sk:+.3f} [{np.percentile(bs,5):+.3f}, {np.percentile(bs,95):+.3f}] AUC {roc_auc_score(y,p):.3f} H1 {1-np.mean((p[m1]-y[m1])**2)/np.mean((b[m1]-y[m1])**2):+.3f} H2 {1-np.mean((p[~m1]-y[~m1])**2)/np.mean((b[~m1]-y[~m1])**2):+.3f}")

print("\n=== R10. Hour-of-extreme by k and the Tokyo-open EDT bump (section 1) ===")
x = load_x("NQ")
print(" NQ hour of high %:", (x.hi_k.value_counts(normalize=True).sort_index() * 100).round(1).tolist())
print(" NQ hour of low  %:", (x.lo_k.value_counts(normalize=True).sort_index() * 100).round(1).tolist())
edt = x[x.is_dst == 1]
for nm, xx in [("EDT all", edt), ("EDT H1", edt[edt.index < H2]), ("EDT H2", edt[edt.index >= H2])]:
    k2 = (xx.hi_k == 2).mean(); n = len(xx)
    print(f"  {nm}: n={n} share of highs in k=2 {k2:.3f}; low in k=2 {(xx.lo_k==2).mean():.3f}; any extreme at k=2 {((xx.hi_k==2)|(xx.lo_k==2)).mean():.3f}")
est = x[x.is_dst == 0]
for nm, xx in [("EST all", est), ("EST H1", est[est.index < H2]), ("EST H2", est[est.index >= H2])]:
    print(f"  {nm}: n={len(xx)} share of highs in k=1 {(xx.hi_k==1).mean():.3f}; low in k=1 {(xx.lo_k==1).mean():.3f}")
print(" hi_first all:", x.hi_first.mean().round(3), " same_bar:", x.same_bar_extremes.mean().round(3), " adjacent (bars_between==1):", (x.bars_between == 1).mean().round(3))
print(" paired diff low-high in bar0:", fmt(ci_diff(x.low_in_first_bar, x.high_in_first_bar)))
