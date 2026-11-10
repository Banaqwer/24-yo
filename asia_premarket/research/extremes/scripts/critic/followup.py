import sys; sys.path.insert(0, "research/extremes/scripts/critic")
from common import *

x = load_x("NQ", full=False, drop_splice=False)
x578 = x[x.index != pd.Timestamp("2025-09-16")]
print("=== F1. Table-2 up/down medians: which definition gives +32/-18/56 and +20/-31/67? (n=578 population) ===")
for lab, m in [("is_down==0", x578.is_down == 0), ("is_down==1", x578.is_down == 1)]:
    xx = x578[m]
    print(f" {lab} n={len(xx)}: median hi_bp {xx.hi_bp.median():+.1f} lo_bp {xx.lo_bp.median():+.1f} rng {xx.rng_bp.median():.1f} | "
          f"vs RTH close: hi {((xx.asia_high/xx.lvl_rth_close-1)*1e4).median():+.1f} lo {((xx.asia_low/xx.lvl_rth_close-1)*1e4).median():+.1f} | "
          f"mean hi {xx.hi_bp.mean():+.1f} lo {xx.lo_bp.mean():+.1f} | in-dir ext {np.where(xx.is_down==0, xx.hi_bp, -xx.lo_bp).mean():+.1f} / counter {np.where(xx.is_down==0, -xx.lo_bp, xx.hi_bp).mean():+.1f} (means) ; medians in-dir {np.median(np.where(xx.is_down==0, xx.hi_bp, -xx.lo_bp)):+.1f} counter {np.median(np.where(xx.is_down==0, -xx.lo_bp, xx.hi_bp)):+.1f}")
for lab, m in [("day_ret>0", x578.day_ret > 0), ("day_ret<0", x578.day_ret < 0), ("rth_ret_bp>=0 & |rth|>=50bp", (x578.rth_ret_bp >= 50)), ("rth_ret_bp<=-50bp", (x578.rth_ret_bp <= -50))]:
    xx = x578[m]
    print(f" {lab} n={len(xx)}: median hi {xx.hi_bp.median():+.1f} lo {xx.lo_bp.median():+.1f} rng {xx.rng_bp.median():.1f}")

print("\n=== F2. 'never both' ===")
for sym in ["NQ", "ES"]:
    xx = load_x(sym)
    b = xx[(xx.high_above_rth_high == 1) & (xx.low_below_rth_low == 1)]
    print(f" {sym}: both broken {len(b)}/{len(xx)}:", [(d.date().isoformat(), round(r.rng_bp), round(r.rth_range_bp)) for d, r in b.iterrows()])

print("\n=== F3. |post|>=25bp side taken, populations ===")
for lab, xx in [("all 579", x), ("578", x578), ("560 clean", load_x("NQ"))]:
    pr = xx[xx.post_ret.abs() >= 0.0025]
    side = np.where(pr.post_ret > 0, pr.high_above_rth_high, pr.low_below_rth_low)
    ahead = pr[np.where(pr.post_ret > 0, pr.ref_close < pr.lvl_rth_high, pr.ref_close > pr.lvl_rth_low)]
    side2 = np.where(ahead.post_ret > 0, ahead.high_above_rth_high, ahead.low_below_rth_low)
    print(f" {lab}: n={len(pr)} side taken {side.mean():.3f}; level still ahead n={len(ahead)} taken {side2.mean():.3f}")

print("\n=== F4. T6 rule n variants (NQ) ===")
p = load_panel("NQ"); p7 = p[p.k <= 7]
o = pd.read_csv(os.path.join(EXT, "oos_intrasession_NQ.csv"), parse_dates=["date"])
rule = (p7.bars_since_hi >= 2) & (p7.pos_in_range < 0.35) & (p7.run_rng_vs_med20 >= 1)
r = p7[rule]
print(" per-k n:", r.groupby("k").size().tolist(), "rates", r.groupby("k").high_done.mean().round(3).tolist())
r_oos = r[r.date.isin(o.date.unique())]
print(f" OOS-window only: n={len(r_oos)} rate {r_oos.high_done.mean():.3f}")
pa = load_panel("NQ", full=False, drop_splice=False); pa = pa[pa.k <= 7]
ra = pa[(pa.bars_since_hi >= 2) & (pa.pos_in_range < 0.35) & (pa.run_rng_vs_med20 >= 1)]
print(f" all rows incl. truncated: n={len(ra)} rate {ra.high_done.mean():.3f}")
r2 = p7[(p7.bars_since_hi >= 2) & (p7.pos_in_range < 0.35) & (p7.run_rng_vs_med20 >= 1) & (p7.bars_since_lo >= 1)]
print(f" + bars_since_lo>=1: n={len(r2)} rate {r2.high_done.mean():.3f}")
r3 = p7[(p7.bars_since_hi >= 2) & (p7.pos_in_range < 0.35) & (p7.run_rng_bp >= p7.run_rng_vs_med20 * 0 + 1e9)]
# bars_since_hi >= 2 by k
g = p7[p7.bars_since_hi >= 2].groupby("k").high_done.mean().round(2)
print(" P(high in | bars_since_hi>=2, k=2..7):", g.tolist())

print("\n=== F5. Monday high in bar 0; Sunday by DST ===")
xx = x578
mon = xx[xx.dow == 0]
print(f" Monday high_in_bar0 {mon.high_in_first_bar.mean():.3f} (n={len(mon)}) vs other {xx[xx.dow!=0].high_in_first_bar.mean():.3f}; p={binom_p(mon.high_in_first_bar.sum(), len(mon), xx[xx.dow!=0].high_in_first_bar.mean()):.3f}")
sun = xx[xx.sunday_open == 1]
for d in [0, 1]:
    s = sun[sun.is_dst == d]
    print(f" Sunday is_dst={d} (tokyo k={s.tokyo_open_k.iloc[0]}): low_by_tokyo {s.low_by_tokyo_open.mean():.3f} n={len(s)}")

print("\n=== F6. zero-volume 18:00 bars ===")
for sym in ["NQ", "ES"]:
    h = load_1h(sym)
    b0 = h[h.index.hour == 18]
    print(f" {sym}: 18:00 bars {len(b0)}, zero volume {(b0.Volume==0).mean():.3f}; 19:00 bars zero volume {(h[h.index.hour==19].Volume==0).mean():.3f}")

print("\n=== F7. Europe-adjusted label: P(the running Asia high at the close of bar k is the 18:00-08:59 overnight high) ===")
for sym in ["NQ", "ES"]:
    e = pd.read_csv(f"research/extremes/scripts/critic/europe_{sym}.csv", index_col="date", parse_dates=True)
    p = load_panel(sym); p = p[p.k <= 8]
    m = p.merge(e[["eur_high", "eur_low", "asia_high", "asia_low", "ref"]], left_on="date", right_index=True, how="inner")
    m["run_hi_px"] = m.ref * (1 + m.run_hi_bp / 1e4); m["run_lo_px"] = m.ref * (1 + m.run_lo_bp / 1e4)
    m["on_high_done"] = ((m.run_hi_px >= m.asia_high - 1e-6) & (m.asia_high >= m.eur_high)).astype(int)
    m["on_low_done"] = ((m.run_lo_px <= m.asia_low + 1e-6) & (m.asia_low <= m.eur_low)).astype(int)
    g = m.groupby("k").agg(asia_high_done=("high_done", "mean"), overnight_high_done=("on_high_done", "mean"),
                           asia_low_done=("low_done", "mean"), overnight_low_done=("on_low_done", "mean"))
    print(f" {sym} (n sessions {m.date.nunique()}):"); print(g.round(2).T.to_string())
    # the T6-style rule under the overnight label
    r = m[(m.bars_since_hi >= 2) & (m.pos_in_range < 0.35) & (m.run_rng_vs_med20 >= 1) & (m.k <= 7)]
    print(f"   T6 rule rows: Asia-high-done {r.high_done.mean():.3f} -> overnight-high-done {fmt(ci_prop(r.on_high_done))} (n={len(r)}); H1/H2 {r[r.date<H2].on_high_done.mean():.3f}/{r[r.date>=H2].on_high_done.mean():.3f}")
    rl = m[(m.bars_since_lo >= 2) & (m.pos_in_range > 0.65) & (m.run_rng_vs_med20 >= 1) & (m.k <= 7)]
    print(f"   low rule rows: Asia-low-done {rl.low_done.mean():.3f} -> overnight-low-done {fmt(ci_prop(rl.on_low_done))} (n={len(rl)})")
    # detector p>=0.9 flags under the overnight label
    o = pd.read_csv(os.path.join(EXT, f"oos_intrasession_{sym}.csv"), parse_dates=["date"])
    mo = o.merge(m[["date", "k", "on_high_done", "on_low_done"]], on=["date", "k"])
    fh = mo[mo.p_high_done >= 0.9]; fl = mo[mo.p_low_done >= 0.9]
    print(f"   detector p_high_done>=0.9 (n={len(fh)}): Asia label precision {fh.high_done.mean():.3f}, overnight-label precision {fmt(ci_prop(fh.on_high_done))}; H1/H2 {fh[fh.date<H2].on_high_done.mean():.3f}/{fh[fh.date>=H2].on_high_done.mean():.3f}")
    print(f"   detector p_low_done>=0.9  (n={len(fl)}): Asia label precision {fl.low_done.mean():.3f}, overnight-label precision {fmt(ci_prop(fl.on_low_done))}; H1/H2 {fl[fl.date<H2].on_low_done.mean():.3f}/{fl[fl.date>=H2].on_low_done.mean():.3f}")
    print("   by k, p_high>=0.9 overnight precision:", fh.groupby("k").on_high_done.mean().round(2).tolist(), "n", fh.groupby("k").size().tolist())
    # Sunday vs weekday Europe break
    es = e.copy()
    print(f"   Europe breaks Asia high: Sunday {es[es.sunday==1].eur_breaks_high.mean():.3f} (n={int((es.sunday==1).sum())}) weekday {es[es.sunday==0].eur_breaks_high.mean():.3f}; low: {es[es.sunday==1].eur_breaks_low.mean():.3f} / {es[es.sunday==0].eur_breaks_low.mean():.3f}")
