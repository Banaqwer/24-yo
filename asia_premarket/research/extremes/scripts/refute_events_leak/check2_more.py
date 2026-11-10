"""Second batch: duplicates, E11 truncation, E1 open-print, E3 event names, E9 BoJ DST, E10 attribution, E12 gap, E7 done rates."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research/extremes/scripts/lens_events")
sys.path.insert(0, ".")
from common import load_extremes, load_panel, load_calendar, binom_p, boot_ci, mw_p, boot_diff_ci
from sessions import load_hourly
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 60)

ev = load_calendar()
X = {s: load_extremes(s) for s in ("NQ", "ES")}
P = {s: load_panel(s) for s in ("NQ", "ES")}
H = {s: load_hourly(f"./data/{s}_1h.csv") for s in ("NQ", "ES")}

print("=== A. duplicate asia_gdate (two RTH dates mapped to the same Asia session) ===")
for s, x in X.items():
    dup = x[x.asia_gdate.duplicated(keep=False)]
    print(s, "n dup rows:", len(dup)); print(dup[["asia_gdate", "n_bars", "rng_bp", "sunday_open", "pre_holiday", "holiday_tomorrow"]].to_string())

print("\n=== B. E11: 6-bar holiday sessions vs the FIRST 6 bars (run_rng at k=5) of full sessions ===")
for s in ("NQ", "ES"):
    x = X[s]; p = P[s]
    sh = x[x.n_bars == 6]
    full = x[x.n_bars == 9]
    r5 = p[(p.k == 5) & (p.date.isin(full.index))].set_index("date")["run_rng_bp"]
    print(f"{s}: 6-bar sessions n={len(sh)} rng med {sh.rng_bp.median():.1f}; full sessions 9-bar rng med {full.rng_bp.median():.1f}; "
          f"full sessions range over bars 0-5 med {r5.median():.1f}; MW p (6-bar rng vs full run_rng@k5) = {mw_p(sh.rng_bp, r5):.4f}; diff CI {boot_diff_ci(sh.rng_bp.values, r5.values)}")
    # by DST (the matched clock)
    for dst in (0, 1):
        a = sh[sh.is_dst == dst].rng_bp; b = r5[full[full.is_dst == dst].index.intersection(r5.index)]
        print(f"   is_dst={dst}: 6-bar n={len(a)} med {a.median():.1f} vs full-session 6-bar running range med {b.median():.1f} (n={len(b)}) MW p={mw_p(a, b):.3f}")
    # share of full sessions whose final extreme is made in bars 6-8 (what the truncation hides)
    print(f"   full sessions: P(hi_k>=6)={(full.hi_k >= 6).mean():.3f} P(lo_k>=6)={(full.lo_k >= 6).mean():.3f} P(either>=6)={((full.hi_k >= 6) | (full.lo_k >= 6)).mean():.3f}")
    # holiday_tomorrow / pre_holiday with 9 bars only
    for f in ("holiday_tomorrow", "pre_holiday"):
        a = x[(x[f] == 1) & (x.n_bars == 9)]; b = x[(x[f] == 0) & (x.n_bars == 9)]
        print(f"   {f} restricted to 9-bar sessions: n={len(a)} rng med {a.rng_bp.median() if len(a) else np.nan:.1f} vs {b.rng_bp.median():.1f} p={mw_p(a.rng_bp, b.rng_bp) if len(a) > 1 else np.nan}")

print("\n=== C. E1: is the Sunday first-bar low the 18:00 open print itself? (bar-0 Open == Low) ===")
for s in ("NQ", "ES"):
    x = X[s]; h = H[s]
    rows = []
    for d, r in x.iterrows():
        gd = pd.Timestamp(r.asia_gdate)
        t0 = pd.Timestamp((gd - pd.Timedelta(days=1)).replace(hour=18), tz="America/New_York")
        if t0 in h.index:
            b = h.loc[t0]
            rows.append(dict(date=d, open_is_low=int(b.Open <= b.Low + 1e-9), open_is_high=int(b.High <= b.Open + 1e-9), bar0_rng=(b.High - b.Low) / r.ref_close * 1e4))
    z = pd.DataFrame(rows).set_index("date").join(x[["sunday_open", "low_in_first_bar", "high_in_first_bar", "gap_open_bp"]])
    for lab, m in (("sunday", z.sunday_open == 1), ("weeknight", z.sunday_open == 0)):
        d = z[m]; dl = d[d.low_in_first_bar == 1]; dh = d[d.high_in_first_bar == 1]
        print(f"{s} {lab}: low_in_first_bar n={len(dl)}, of which the 18:00 open print IS the bar low: {dl.open_is_low.mean():.3f}; high_in_first_bar n={len(dh)}, open is the high: {dh.open_is_high.mean():.3f}")
        print(f"   P(open is bar-0 low) all nights: {d.open_is_low.mean():.3f}; P(low_in_first_bar & open is low)={((d.low_in_first_bar==1)&(d.open_is_low==1)).mean():.3f}; P(low_in_first_bar & open NOT low)={((d.low_in_first_bar==1)&(d.open_is_low==0)).mean():.3f}")

print("\n=== D. E3: tier-1 events on the 38 'NFP Friday' Sundays ===")
x = X["NQ"]
t = x[(x.sunday_open == 1) & (x.tier1_data_today == 1)]
print(t.events_today.value_counts().to_string())

print("\n=== E. E9: BoJ decision window DST-aware ({3,4} EST, {4,5} EDT) ===")
boj = ev[ev.category == "boj"]
for s in ("NQ", "ES"):
    x = X[s]; by_g = x.reset_index().set_index("asia_gdate")
    sess = by_g.loc[by_g.index.intersection(boj.date)]
    ctrl = x[~x.index.isin(sess.date)]
    for which in ("hi_k", "lo_k"):
        hits = 0; exp = 0.0; n = 0
        for _, r in sess.iterrows():
            ks = {4, 5} if r.is_dst == 1 else {3, 4}
            hit = int(r[which] in ks); c = ctrl[(ctrl.is_dst == r.is_dst) & (ctrl.n_bars == r.n_bars)]
            hits += hit; exp += c[which].isin(ks).mean(); n += 1
        print(f"{s} BoJ DST-aware decision window {which}: {hits}/{n}={hits/n:.3f} vs base {exp/n:.3f} p={binom_p(hits, n, exp/n):.3f}")
    print(f"   BoJ sessions is_dst counts: {sess.is_dst.value_counts().to_dict()}")

print("\n=== F. E10: weeknight cn_data_tonight sessions -- is there a cn_data event dated asia_gdate (i.e. actually inside the session)? ===")
cn_dates = set(ev[ev.category == "cn_data"].date.dt.normalize())
for s in ("NQ",):
    x = X[s]
    w = x[(x.cn_data_tonight == 1) & (x.sunday_open == 0)]
    inside = w.asia_gdate.dt.normalize().isin(cn_dates)
    print(f"{s}: weeknight cn_data_tonight n={len(w)}; event actually dated asia_gdate: {inside.sum()}; mis-attributed: {(~inside).sum()}")
    print(w[~inside][["asia_gdate", "events_tonight_tomorrow"]].to_string())
    # and sessions with a cn_data event in-session but flag==0 (missed)
    miss = x[(x.cn_data_tonight == 0) & (x.asia_gdate.dt.normalize().isin(cn_dates))]
    print(f"   sessions with cn_data dated asia_gdate but flag=0: {len(miss)}")
    # weeknight either_last restricted to correctly attributed
    a = w[inside]; b = x[(x.cn_data_tonight == 0) & (x.sunday_open == 0)]
    for sym in ("NQ", "ES"):
        xx = X[sym]; ww = xx[(xx.cn_data_tonight == 1) & (xx.sunday_open == 0)]; ins = ww.asia_gdate.dt.normalize().isin(cn_dates)
        aa = ww[ins]; bb = xx[(xx.cn_data_tonight == 0) & (xx.sunday_open == 0)]
        print(f"   {sym} either_last correctly-attributed weeknight cn_data: {aa.either_last.sum()}/{len(aa)}={aa.either_last.mean():.3f} vs {bb.either_last.mean():.3f} p={binom_p(aa.either_last.sum(), len(aa), bb.either_last.mean()):.3f}")

print("\n=== G. E12: |gap| and first-bar extremes (bar-0 feature) ===")
for s in ("NQ", "ES"):
    x = X[s].copy()
    x["gq"] = pd.qcut(x.abs_gap, 5, labels=False, duplicates="drop")
    g = x.groupby("gq").agg(n=("abs_gap", "size"), gap_med=("abs_gap", "median"), either_first=("either_first", "mean"), low_first=("low_in_first_bar", "mean"), high_first=("high_in_first_bar", "mean"), both_first=("both_first", "mean"))
    print(s); print(g.round(3).to_string())
    big = x[x.abs_gap >= x.abs_gap.quantile(0.8)]; small = x[x.abs_gap < x.abs_gap.quantile(0.8)]
    print(f"   top-quintile |gap| (>= {x.abs_gap.quantile(0.8):.1f} bp) n={len(big)}: either_first {big.either_first.mean():.3f} vs {small.either_first.mean():.3f} p={binom_p(big.either_first.sum(), len(big), small.either_first.mean()):.2e}; "
          f"H1 {big[big.half=='H1'].either_first.mean():.2f}/{small[small.half=='H1'].either_first.mean():.2f} H2 {big[big.half=='H2'].either_first.mean():.2f}/{small[small.half=='H2'].either_first.mean():.2f}")
    # within weeknights only (Sunday carries the gap)
    wb = big[big.sunday_open == 0]; ws = small[small.sunday_open == 0]
    print(f"   weeknights only: top-quintile n={len(wb)} either_first {wb.either_first.mean():.3f} vs {ws.either_first.mean():.3f} p={binom_p(wb.either_first.sum(), len(wb), ws.either_first.mean()):.3f}")
    # month_end restricted to weeknights
    me = x[(x.month_end == 1) & (x.sunday_open == 0)]; nme = x[(x.month_end == 0) & (x.sunday_open == 0)]
    print(f"   month_end weeknights n={len(me)}: |gap| {me.abs_gap.median():.1f} vs {nme.abs_gap.median():.1f} p={mw_p(me.abs_gap, nme.abs_gap):.3f}; low_by_tokyo {me.low_by_tokyo_open.mean():.3f} vs {nme.low_by_tokyo_open.mean():.3f} p={binom_p(me.low_by_tokyo_open.sum(), len(me), nme.low_by_tokyo_open.mean()):.3f}; low_in_first_bar {me.low_in_first_bar.mean():.3f} vs {nme.low_in_first_bar.mean():.3f}")

print("\n=== H. E7 encoding: P(high_done|k) on megacap post_ret>0 nights, P(low_done|k) on post_ret<0, vs base; and vs ref-already-beyond ===")
for s in ("NQ", "ES"):
    x = X[s]; p = P[s]
    pp = p.merge(x[["megacap_earnings_tonight", "post_ret", "lvl_post_close", "lvl_rth_high", "lvl_rth_low"]], left_on="date", right_index=True)
    pp = pp[pp.n_bars == 9]
    up = pp[pp.post_ret > 0]; dn = pp[pp.post_ret < 0]
    print(s, "post_ret>0: P(high_done|k) megacap vs base")
    for k in range(0, 6):
        a = up[(up.k == k) & (up.megacap_earnings_tonight == 1)]; b = up[(up.k == k) & (up.megacap_earnings_tonight == 0)]
        print(f"   k={k}: megacap {a.high_done.mean():.3f} (n={len(a)}) vs base {b.high_done.mean():.3f} p={binom_p(a.high_done.sum(), len(a), b.high_done.mean()):.3f}; med remaining_up {a.remaining_up_bp.median():.1f} vs {b.remaining_up_bp.median():.1f}")
    print(s, "post_ret<0: P(low_done|k) megacap vs base")
    for k in range(0, 6):
        a = dn[(dn.k == k) & (dn.megacap_earnings_tonight == 1)]; b = dn[(dn.k == k) & (dn.megacap_earnings_tonight == 0)]
        print(f"   k={k}: megacap {a.low_done.mean():.3f} (n={len(a)}) vs base {b.low_done.mean():.3f} p={binom_p(a.low_done.sum(), len(a), b.low_done.mean()):.3f}; med remaining_down {a.remaining_down_bp.median():.1f} vs {b.remaining_down_bp.median():.1f}")

print("\n=== I. tier1_data_tomorrow / fomc_tomorrow / fomc_today / megacap: Sunday overlap and n_bars ===")
for f in ("tier1_data_tomorrow", "fomc_tomorrow", "fomc_today", "megacap_earnings_tonight", "tier1_data_today", "opex_today", "month_end"):
    x = X["NQ"]; a = x[x[f] == 1]
    print(f"{f}: n={len(a)} sunday={int(a.sunday_open.sum())} n_bars<9={int((a.n_bars < 9).sum())} dup_gdate={int(a.asia_gdate.duplicated(keep=False).sum())}")
