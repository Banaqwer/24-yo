"""Extra regime checks: E9 event-bar families, E1/E10 panel rules, E12 gap->first-bar test, night lists for E3/E4/E5."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research/extremes/scripts/refute_events_regime")
from rob import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)

X = {s: load(s) for s in ("NQ", "ES")}
P = {}
for s in ("NQ", "ES"):
    p = load_panel(s)
    p["hy"] = [f"{d.year}H{1 if d.month <= 6 else 2}" for d in p["date"]]
    p = p.merge(X[s][["sunday_open", "cn_data_tonight", "fomc_tomorrow", "fomc_today", "any_regime"]], left_on="date", right_index=True, how="inner")
    P[s] = p

print("=" * 30, "E1 half-year detail (ES) + panel rule by half-year")
for s in ("NQ", "ES"):
    x = X[s]
    for hy in sorted(x.hy.unique()):
        d = x[x.hy == hy]; su = d[d.sunday_open == 1]; wk = d[d.sunday_open == 0]
        print(f"  {s} {hy}: low_by_tokyo Sun {su.low_by_tokyo_open.mean():.2f} (n={len(su)}) vs wk {wk.low_by_tokyo_open.mean():.2f} | low_in_first_bar {su.low_in_first_bar.mean():.2f} vs {wk.low_in_first_bar.mean():.2f} | high_by_tokyo {su.high_by_tokyo_open.mean():.2f} vs {wk.high_by_tokyo_open.mean():.2f}")
    p = P[s]
    # rule: close of bar 1 on Sunday with running low still the 18:00-bar low (bars_since_lo == 1)
    d = p[(p.k == 1) & (p.bars_since_lo == 1)]
    for lab, m in (("all", slice(None)),):
        su = d[d.sunday_open == 1]; wk = d[d.sunday_open == 0]
        print(f"  {s} panel rule k=1 & bars_since_lo==1: Sunday P(low_done)={su.low_done.mean():.3f} (n={len(su)}) vs weeknight {wk.low_done.mean():.3f} (n={len(wk)}) p={binom_p(su.low_done.sum(), len(su), wk.low_done.mean()):.3g}")
        for hy in sorted(d.hy.unique()):
            a = su[su.hy == hy]; b = wk[wk.hy == hy]
            print(f"      {hy}: {a.low_done.mean():.2f} (n={len(a)}) vs {b.low_done.mean():.2f} (n={len(b)})")
        a = su[su.any_regime == 0]; b = wk[wk.any_regime == 0]
        print(f"      ex-regime: {a.low_done.mean():.2f} (n={len(a)}) vs {b.low_done.mean():.2f} (n={len(b)})")
    # P(low_done | k) Sunday vs weeknight by half
    for k in range(0, 8):
        d = p[p.k == k]; su = d[d.sunday_open == 1]; wk = d[d.sunday_open == 0]
        h1s = su[su.half == "H1"]; h2s = su[su.half == "H2"]; h1w = wk[wk.half == "H1"]; h2w = wk[wk.half == "H2"]
        print(f"  {s} P(low_done|k={k}) Sun {su.low_done.mean():.2f} vs wk {wk.low_done.mean():.2f} | H1 {h1s.low_done.mean():.2f}/{h1w.low_done.mean():.2f} H2 {h2s.low_done.mean():.2f}/{h2w.low_done.mean():.2f} | 2026H2 Sun {su[su.hy=='2026H2'].low_done.mean():.2f} (n={len(su[su.hy=='2026H2'])}) wk {wk[wk.hy=='2026H2'].low_done.mean():.2f}")

print("=" * 30, "E3 NFP Sunday nights (NQ): low_below_rth_low")
x = X["NQ"]
d = x[(x.sunday_open == 1) & (x.tier1_data_today == 1)][["low_below_rth_low", "lo_vs_rth_low_bp", "gap_open_bp", "rth_ret_bp", "any_regime"]]
d["ES_low_below"] = X["ES"].loc[d.index, "low_below_rth_low"]
print(d.to_string())
print("other Sundays by half-year (NQ):")
o = x[(x.sunday_open == 1) & (x.tier1_data_today == 0)]
print(o.groupby("hy").low_below_rth_low.agg(["mean", "size"]).round(2).T.to_string())
print("NFP Sundays by half-year (NQ):")
print(x[(x.sunday_open == 1) & (x.tier1_data_today == 1)].groupby("hy").low_below_rth_low.agg(["mean", "size"]).round(2).T.to_string())
print("NFP Sundays by half-year (ES):")
xe = X["ES"]
print(xe[(xe.sunday_open == 1) & (xe.tier1_data_today == 1)].groupby("hy").low_below_rth_low.agg(["mean", "size"]).round(2).T.to_string())
print(xe[(xe.sunday_open == 1) & (xe.tier1_data_today == 0)].groupby("hy").low_below_rth_low.agg(["mean", "size"]).round(2).T.to_string())
# alternative base: all weeknights (is the NFP-Sunday rate unusual vs ALL sessions?)
for s in ("NQ", "ES"):
    xx = X[s]; sub = xx[(xx.sunday_open == 1) & (xx.tier1_data_today == 1)]; base = xx[~((xx.sunday_open == 1) & (xx.tier1_data_today == 1))]
    r = compare(sub, base, "low_below_rth_low", "prop"); print(f"  {s} NFP Sunday vs ALL other sessions: {r['val']:.3f} vs {r['base']:.3f} p={r['p']:.3g}")

print("=" * 30, "E4 FOMC-eve nights (NQ / ES)")
cols = ["hi_first", "hi_k", "lo_k", "hi_last", "low_in_first_bar", "close_loc", "asia_ret_bp", "n_bars", "any_regime"]
d = X["NQ"][X["NQ"].fomc_tomorrow == 1][cols].copy()
e = X["ES"][X["ES"].fomc_tomorrow == 1][["hi_first", "hi_k", "lo_k", "close_loc", "asia_ret_bp"]].add_prefix("ES_")
print(d.join(e, how="outer").round(2).to_string())
print("by year NQ:", X["NQ"][X["NQ"].fomc_tomorrow == 1].groupby(X["NQ"][X["NQ"].fomc_tomorrow == 1].index.year)[["hi_first", "hi_last", "asia_up", "close_above_ref"]].mean().round(2).to_dict())
print("by year ES:", X["ES"][X["ES"].fomc_tomorrow == 1].groupby(X["ES"][X["ES"].fomc_tomorrow == 1].index.year)[["hi_first", "hi_last", "asia_up", "close_above_ref"]].mean().round(2).to_dict())

print("=" * 30, "E5 FOMC-night nights (NQ / ES)")
cols = ["low_in_first_bar", "either_last", "hi_k", "lo_k", "hi_bp", "rng_bp", "rally_after_lo_bp", "asia_ret_bp", "gap_open_bp"]
d = X["NQ"][X["NQ"].fomc_today == 1][cols].copy()
e = X["ES"][X["ES"].fomc_today == 1][["low_in_first_bar", "either_last", "hi_bp", "rng_bp"]].add_prefix("ES_")
print(d.join(e, how="outer").round(1).to_string())
print("by year NQ:", X["NQ"][X["NQ"].fomc_today == 1].groupby(X["NQ"][X["NQ"].fomc_today == 1].index.year)[["low_in_first_bar", "either_last"]].mean().round(2).to_dict())
print("by year ES:", X["ES"][X["ES"].fomc_today == 1].groupby(X["ES"][X["ES"].fomc_today == 1].index.year)[["low_in_first_bar", "either_last"]].mean().round(2).to_dict())

print("=" * 30, "E12: does |gap| predict first-bar extremes? (either_first by |gap| quartile, within Sunday / weeknight, by half)")
for s in ("NQ", "ES"):
    x = X[s]
    for lab, m in (("weeknight", x.sunday_open == 0), ("Sunday", x.sunday_open == 1)):
        d = x[m].copy()
        d["gq"] = pd.qcut(d.abs_gap.rank(method="first"), 4, labels=["q1", "q2", "q3", "q4"])
        t = d.groupby("gq", observed=True).agg(n=("either_first", "size"), either_first=("either_first", "mean"), low_first=("low_in_first_bar", "mean"), high_first=("high_in_first_bar", "mean"), gap_med=("abs_gap", "median"))
        print(f"  {s} {lab}:\n{t.round(3).to_string()}")
        for h in ("H1", "H2"):
            dh = d[d.half == h]
            print(f"     {h}: either_first top-quartile {dh[dh.gq=='q4'].either_first.mean():.2f} (n={len(dh[dh.gq=='q4'])}) vs bottom {dh[dh.gq=='q1'].either_first.mean():.2f} (n={len(dh[dh.gq=='q1'])})")
        from scipy import stats
        print(f"     spearman(|gap|, either_first) rho={stats.spearmanr(d.abs_gap, d.either_first)[0]:.3f} p={stats.spearmanr(d.abs_gap, d.either_first)[1]:.3g}; vs first_bar_rng rho={stats.spearmanr(d.first_bar_rng_bp, d.either_first)[0]:.3f}")
    # megacap/fomc nights: does gap predict first-bar extreme?
    d = x[(x.megacap_earnings_tonight == 1) | (x.fomc_today == 1)]
    print(f"  {s} megacap+FOMC nights (n={len(d)}): either_first {d.either_first.mean():.2f}; |gap|>=10bp {d[d.abs_gap>=10].either_first.mean():.2f} (n={len(d[d.abs_gap>=10])}) vs <10 {d[d.abs_gap<10].either_first.mean():.2f} (n={len(d[d.abs_gap<10])})")

print("=" * 30, "E10 panel P(high_done|k=7) & P(low_done|k=7) cn_data weeknights by half-year")
for s in ("NQ", "ES"):
    p = P[s]; d = p[(p.k == 7) & (p.sunday_open == 0) & (p.n_bars == 9)]
    a = d[d.cn_data_tonight == 1]; b = d[d.cn_data_tonight == 0]
    print(f"  {s} k=7 high_done cn {a.high_done.mean():.3f} (n={len(a)}) vs {b.high_done.mean():.3f} p={binom_p(a.high_done.sum(), len(a), b.high_done.mean()):.3g}; low_done {a.low_done.mean():.3f} vs {b.low_done.mean():.3f} p={binom_p(a.low_done.sum(), len(a), b.low_done.mean()):.3g}")
    for hy in sorted(d.hy.unique()):
        ah = a[a.hy == hy]; bh = b[b.hy == hy]
        print(f"     {hy}: high_done {ah.high_done.mean():.2f}/{bh.high_done.mean():.2f} low_done {ah.low_done.mean():.2f}/{bh.low_done.mean():.2f} (n={len(ah)})")
    x = X[s]; wk = x[x.sunday_open == 0]
    print("   either_last by half-year:", wk.groupby("hy").apply(lambda g: f"{g[g.cn_data_tonight==1].either_last.mean():.2f}/{g[g.cn_data_tonight==0].either_last.mean():.2f}(n={int((g.cn_data_tonight==1).sum())})").to_dict())

print("=" * 30, "E9 event-bar clustering by half-year + CN_0930 next-bar range robustness")
ev = load_calendar()
asia = ev[ev["time_et"].notna()].copy()
asia["hour"] = asia["time_et"].str[:2].astype(int)
asia = asia[(asia["hour"] >= 18) | (asia["hour"] < 3)].copy()
asia["ke"] = np.where(asia["hour"] >= 18, asia["hour"] - 18, asia["hour"] + 6)
FAM = {"CN_0930CST": ["CN_CPI", "CN_PMI_NBS"], "CN_0945CST": ["CN_PMI_CAIXIN", "CN_PMI_CAIXIN_SVC"], "CN_1000CST": ["CN_ACTIVITY"],
       "CN_TRADE": ["CN_TRADE"], "JP_0830JST": ["JP_CPI"], "JP_TANKAN": ["TANKAN"], "RBA": ["RBA"]}
rows = []
for s in ("NQ", "ES"):
    x = X[s]; p = P[s]
    by_g = x.reset_index().set_index("asia_gdate")
    pooled = []  # per event-session: hit_hi, exp_hi, hit_lo, exp_lo, hy, date
    for fam, names in FAM.items():
        e = asia[asia["event"].isin(names)].copy(); e = e[e["gdate"].isin(by_g.index)] if "gdate" in e else e
        e["gdate"] = e["date"]; e = e[e["gdate"].isin(by_g.index)]
        e = e.sort_values("ke").drop_duplicates("gdate")
        sess = by_g.loc[e["gdate"].values].copy(); sess["ke"] = e["ke"].values; sess = sess[sess["ke"] <= sess["last_k"]]
        ctrl_all = x[~x.index.isin(sess["date"])]
        for _, r in sess.iterrows():
            ke = int(r["ke"]); ks = {ke, ke + 1}; ks = {k for k in ks if 0 <= k <= r["last_k"]}
            ctrl = ctrl_all[(ctrl_all["is_dst"] == r["is_dst"]) & (ctrl_all["n_bars"] == r["n_bars"])]
            pooled.append(dict(fam=fam, date=r["date"], hy=r["hy"], q=r["q"], any_regime=r["any_regime"],
                               hit_hi=int(r["hi_k"] in ks), exp_hi=ctrl["hi_k"].isin(ks).mean(),
                               hit_lo=int(r["lo_k"] in ks), exp_lo=ctrl["lo_k"].isin(ks).mean(),
                               hit_hi0=int(r["hi_k"] == ke), exp_hi0=(ctrl["hi_k"] == ke).mean(),
                               hit_lo0=int(r["lo_k"] == ke), exp_lo0=(ctrl["lo_k"] == ke).mean()))
        # CN_0930 next-bar range
        if fam == "CN_0930CST":
            pp = p.merge(sess[["date", "ke"]], on="date"); nb = pp[pp["k"] == pp["ke"] + 1]
            ctrl_p = p[~p["date"].isin(sess["date"])]; cm = ctrl_p.merge(nb[["k", "is_dst"]].drop_duplicates(), on=["k", "is_dst"])
            print(f"  {s} CN_0930 next-bar bar_rng_rel: {nb.bar_rng_rel.median():.3f} (n={len(nb)}) vs ctrl {cm.bar_rng_rel.median():.3f} p={mw_p(nb.bar_rng_rel, cm.bar_rng_rel):.3g}")
            for hy in sorted(nb.hy.unique()):
                a = nb[nb.hy == hy]; b = cm[cm.hy == hy]
                print(f"      {hy}: {a.bar_rng_rel.median():.2f} (n={len(a)}) vs {b.bar_rng_rel.median():.2f}")
            top = nb.sort_values("bar_rng_rel", ascending=False).iloc[5:]
            print(f"      top-5 removed: {top.bar_rng_rel.median():.3f} (n={len(top)}) vs {cm.bar_rng_rel.median():.3f} p={mw_p(top.bar_rng_rel, cm.bar_rng_rel):.3g}")
            a = nb[nb.any_regime == 0]; print(f"      ex-regime: {a.bar_rng_rel.median():.3f} (n={len(a)}) vs {cm[cm.any_regime==0].bar_rng_rel.median():.3f} p={mw_p(a.bar_rng_rel, cm[cm.any_regime==0].bar_rng_rel):.3g}")
    pl = pd.DataFrame(pooled)
    print(f"  {s} pooled event-or-next: hi {pl.hit_hi.mean():.3f} vs exp {pl.exp_hi.mean():.3f} (n={len(pl)}) p={binom_p(pl.hit_hi.sum(), len(pl), pl.exp_hi.mean()):.3g}; lo {pl.hit_lo.mean():.3f} vs {pl.exp_lo.mean():.3f} p={binom_p(pl.hit_lo.sum(), len(pl), pl.exp_lo.mean()):.3g}")
    print(f"  {s} pooled event bar: hi {pl.hit_hi0.mean():.3f} vs exp {pl.exp_hi0.mean():.3f}; lo {pl.hit_lo0.mean():.3f} vs {pl.exp_lo0.mean():.3f}")
    for hy in sorted(pl.hy.unique()):
        a = pl[pl.hy == hy]
        print(f"      {hy}: event-or-next hi {a.hit_hi.mean():.2f}/{a.exp_hi.mean():.2f} lo {a.hit_lo.mean():.2f}/{a.exp_lo.mean():.2f} (n={len(a)}) | event bar hi {a.hit_hi0.mean():.2f}/{a.exp_hi0.mean():.2f} lo {a.hit_lo0.mean():.2f}/{a.exp_lo0.mean():.2f}")
    a = pl[pl.any_regime == 1]
    print(f"      inside regimes: event-or-next hi {a.hit_hi.mean():.2f}/{a.exp_hi.mean():.2f} lo {a.hit_lo.mean():.2f}/{a.exp_lo.mean():.2f} (n={len(a)})")
    for fam in FAM:
        a = pl[pl.fam == fam]
        print(f"      {fam}: event-or-next hi {a.hit_hi.mean():.2f}/{a.exp_hi.mean():.2f} lo {a.hit_lo.mean():.2f}/{a.exp_lo.mean():.2f} (n={len(a)}) H1 hi {a[a.hy<'2025H2'].hit_hi.mean():.2f} lo {a[a.hy<'2025H2'].hit_lo.mean():.2f} H2 hi {a[a.hy>='2025H2'].hit_hi.mean():.2f} lo {a[a.hy>='2025H2'].hit_lo.mean():.2f}")
