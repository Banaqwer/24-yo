"""Independent recompute of T9-T15."""
import numpy as np, pandas as pd
from scipy import stats
ROOT = "."
SPLIT = pd.Timestamp("2025-09-01")
BAD = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"],
       "ES": ["2025-12-15", "2025-12-16", "2025-12-17"]}
rng = np.random.default_rng(99)

def load(sym):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    bad = pd.to_datetime(BAD[sym])
    x = x[~x.index.isin(bad)]; p = p[~p.date.isin(bad)]
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    p["half"] = np.where(p.date < SPLIT, "H1", "H2")
    return x, p

def ci(v, nb=2000, fn=np.mean):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    if len(v) < 2: return (np.nan, np.nan)
    b = rng.integers(0, len(v), (nb, len(v)))
    m = np.array([fn(v[i]) for i in b])
    return (np.quantile(m, .05), np.quantile(m, .95))

def spike(d, w=5, shell=(5, 15), nb=2000):
    """density within +-w / density in shells (w..shell_hi both sides)"""
    d = np.asarray(d, float); d = d[~np.isnan(d)]
    def r(v):
        a = (np.abs(v) <= w).sum() / (2 * w)
        b = ((np.abs(v) > shell[0]) & (np.abs(v) <= shell[1])).sum() / (2 * (shell[1] - shell[0]))
        return a / b if b > 0 else np.nan
    base = r(d)
    bs = rng.integers(0, len(d), (nb, len(d)))
    arr = np.array([r(d[i]) for i in bs])
    return base, np.nanquantile(arr, .05), np.nanquantile(arr, .95), int((np.abs(d) <= w).sum()), int(((np.abs(d) > shell[0]) & (np.abs(d) <= shell[1])).sum())

XS = {}; PS = {}
for sym in ["NQ", "ES"]:
    x, p = load(sym); XS[sym] = x; PS[sym] = p
    print(f"\n===== {sym}: sessions n={len(x)} =====")
    print("--- T9: magnets ---")
    lv = {"high vs RTH high": x.hi_vs_rth_high_bp, "low vs RTH low": x.lo_vs_rth_low_bp,
          "high vs VWAP": x.hi_vs_rth_vwap_bp, "low vs VWAP": x.lo_vs_rth_vwap_bp,
          "high vs prior Asia high": x.hi_vs_prior_asia_high_bp, "low vs prior Asia low": x.lo_vs_prior_asia_low_bp,
          "high vs 17:00 close": x.hi_bp, "low vs 17:00 close": x.lo_bp,
          "high vs RTH open": (x.asia_high / x.lvl_rth_open - 1) * 1e4, "low vs RTH open": (x.asia_low / x.lvl_rth_open - 1) * 1e4,
          "high vs prev settle": (x.asia_high / x.lvl_prev_settle - 1) * 1e4, "low vs prev settle": (x.asia_low / x.lvl_prev_settle - 1) * 1e4,
          "high vs prev RTH high": (x.asia_high / x.lvl_prev_rth_high - 1) * 1e4, "low vs prev RTH low": (x.asia_low / x.lvl_prev_rth_low - 1) * 1e4,
          "CTRL high vs RTH low": (x.asia_high / x.lvl_rth_low - 1) * 1e4, "CTRL low vs RTH high": (x.asia_low / x.lvl_rth_high - 1) * 1e4}
    for lab, d in lv.items():
        r, lo, hi, nin, nsh = spike(d)
        d1 = d[x.half == "H1"]; d2 = d[x.half == "H2"]
        r1 = spike(d1)[0]; r2 = spike(d2)[0]
        print(f"  {lab:26s} ratio={r:.2f} CI[{lo:.2f},{hi:.2f}] n_in5={nin} n_shell={nsh} H1={r1:.2f} H2={r2:.2f}")
    # alt: narrower window +-2bp vs 2-10 shell for RTH high/low
    for lab in ["high vs RTH high", "low vs RTH low"]:
        r, lo, hi, nin, nsh = spike(lv[lab], w=2, shell=(2, 10))
        print(f"  narrow +-2bp {lab:26s} ratio={r:.2f} CI[{lo:.2f},{hi:.2f}] n_in={nin}")
    # Exact-touch test: how often is asia_high within 2 bp of RTH high vs expected from a smooth density?
    d = x.hi_vs_rth_high_bp.dropna()
    hist, edges = np.histogram(d, bins=np.arange(-20, 21, 2))
    print("  2-bp histogram hi_vs_rth_high_bp -20..20:", hist.tolist())
    d = x.lo_vs_rth_low_bp.dropna()
    hist, edges = np.histogram(d, bins=np.arange(-20, 21, 2))
    print("  2-bp histogram lo_vs_rth_low_bp -20..20:", hist.tolist())
    # share within 5 bp of any of the four main levels (RTH high, RTH low, VWAP, prior asia high) for highs
    any4 = (x.hi_vs_rth_high_bp.abs() <= 5) | (x.hi_vs_rth_vwap_bp.abs() <= 5) | (x.hi_vs_prior_asia_high_bp.abs() <= 5) | ((x.asia_high / x.lvl_rth_low - 1).abs() * 1e4 <= 5)
    print(f"  share of highs within 5bp of any of RTH high/low/VWAP/prior Asia high: {any4.mean():.3f}")
    # round numbers
    mods = {"NQ": [(100, 2), (50, 2), (25, 1)], "ES": [(25, 1), (10, .5), (5, .25)]}[sym]
    for mod, w in mods:
        for lab, s in [("high", x.asia_high), ("low", x.asia_low)]:
            dist = np.minimum(s % mod, mod - (s % mod))
            obs = (dist <= w).mean(); exp = 2 * w / mod
            k = int((dist <= w).sum()); pv = stats.binomtest(k, len(s), exp).pvalue
            print(f"  round {lab} mod{mod} +-{w}: obs {obs:.3f} exp {exp:.3f} ratio {obs/exp:.2f} p={pv:.2f}")

    print("--- T10: distance ladder ---")
    dh = (x.lvl_rth_high / x.ref_close - 1) * 1e4; dl = (1 - x.lvl_rth_low / x.ref_close) * 1e4
    print(f"  base P(high>RTH high) {x.high_above_rth_high.mean():.3f}; P(low<RTH low) {x.low_below_rth_low.mean():.3f}")
    print("  check high_above_rth_high == hi_vs_rth_high_bp>0:", ((x.hi_vs_rth_high_bp > 0) == (x.high_above_rth_high == 1)).mean())
    full = x[x.n_bars == 9]
    dhf = dh[full.index]
    for lab, m in [("<10", dh < 10), ("10-25", (dh >= 10) & (dh < 25)), ("25-50", (dh >= 25) & (dh < 50)), ("50-100", (dh >= 50) & (dh < 100)), (">=100", dh >= 100)]:
        s = x.loc[m, "high_above_rth_high"]; lo, hi = ci(s)
        h1 = x.loc[m & (x.half == "H1"), "high_above_rth_high"].mean(); h2 = x.loc[m & (x.half == "H2"), "high_above_rth_high"].mean()
        mf = m.reindex(full.index).fillna(False)
        hi0 = (full.loc[mf, "hi_k"] == 0).mean(); hi8 = (full.loc[mf, "hi_k"] == 8).mean(); med = full.loc[mf, "hi_k"].median()
        p0 = stats.binomtest(int((full.loc[mf, "hi_k"] == 0).sum()), int(mf.sum()), (full.hi_k == 0).mean()).pvalue
        p8 = stats.binomtest(int((full.loc[mf, "hi_k"] == 8).sum()), int(mf.sum()), (full.hi_k == 8).mean()).pvalue
        print(f"  high dist {lab:7s} n={len(s)} P(break)={s.mean():.3f} CI[{lo:.3f},{hi:.3f}] H1={h1:.3f} H2={h2:.3f} | timing: hi0={hi0:.2f}(p={p0:.2f}) hi8={hi8:.2f}(p={p8:.2f}) med hi_k={med}")
    for lab, m in [("<10", dl < 10), ("10-25", (dl >= 10) & (dl < 25)), ("25-50", (dl >= 25) & (dl < 50)), ("50-100", (dl >= 50) & (dl < 100)), (">=100", dl >= 100)]:
        s = x.loc[m, "low_below_rth_low"]; lo, hi = ci(s)
        mf = m.reindex(full.index).fillna(False)
        lo0 = (full.loc[mf, "lo_k"] == 0).mean(); lo8 = (full.loc[mf, "lo_k"] == 8).mean()
        print(f"  low dist {lab:7s} n={len(s)} P(break)={s.mean():.3f} CI[{lo:.3f},{hi:.3f}] | timing lo0={lo0:.2f} lo8={lo8:.2f}")
    # is the ladder just hi_bp distribution? median hi_bp
    print(f"  median hi_bp {x.hi_bp.median():.1f}; P(hi_bp>=10) {(x.hi_bp>=10).mean():.2f}, P(hi_bp>=25) {(x.hi_bp>=25).mean():.2f}, P(hi_bp>=50) {(x.hi_bp>=50).mean():.2f}, P(hi_bp>=100) {(x.hi_bp>=100).mean():.2f}")

    print("--- T11: extreme-bar signature ---")
    P = p[(p.n_bars == 9)].copy()
    P = P.merge(x[["same_bar_extremes"]], left_on="date", right_index=True)
    P = P[P.k <= 7]  # match lens? they said 4496 rows -> k<=7
    ishi = (P.k == P.hi_k) & (P.same_bar_extremes == 0); islo = (P.k == P.lo_k) & (P.same_bar_extremes == 0)
    neither = (P.k != P.hi_k) & (P.k != P.lo_k)
    print(f"  n high bars {ishi.sum()}, low bars {islo.sum()}, neither {neither.sum()}")
    for col in ["bar_rng_rel", "bar_vol_rel", "bar_close_loc", "bar_rng_bp"]:
        o = P.loc[neither, col].median(); h = P.loc[ishi, col].median(); l = P.loc[islo, col].median()
        dl_ = ci(P.loc[islo, col].values, fn=np.median); dh_ = ci(P.loc[ishi, col].values, fn=np.median); do = ci(P.loc[neither, col].values, fn=np.median)
        h1l = P.loc[islo & (P.half == "H1"), col].median(); h2l = P.loc[islo & (P.half == "H2"), col].median()
        h1h = P.loc[ishi & (P.half == "H1"), col].median(); h2h = P.loc[ishi & (P.half == "H2"), col].median()
        print(f"  {col:14s} ordinary {o:.2f} CI[{do[0]:.2f},{do[1]:.2f}] | low bar {l:.2f} CI[{dl_[0]:.2f},{dl_[1]:.2f}] H1 {h1l:.2f} H2 {h2l:.2f} | high bar {h:.2f} CI[{dh_[0]:.2f},{dh_[1]:.2f}] H1 {h1h:.2f} H2 {h2h:.2f}")
    print(f"  close in upper quarter: ordinary {(P.loc[neither,'bar_close_loc']>=.75).mean():.2f} low bar {(P.loc[islo,'bar_close_loc']>=.75).mean():.2f}; lower quarter ord {(P.loc[neither,'bar_close_loc']<=.25).mean():.2f} high bar {(P.loc[ishi,'bar_close_loc']<=.25).mean():.2f}")
    print(f"  rng_rel>=1.5: ord {(P.loc[neither,'bar_rng_rel']>=1.5).mean():.2f} low {(P.loc[islo,'bar_rng_rel']>=1.5).mean():.2f} high {(P.loc[ishi,'bar_rng_rel']>=1.5).mean():.2f}; vol>=1.5 ord {(P.loc[neither,'bar_vol_rel']>=1.5).mean():.2f} low {(P.loc[islo,'bar_vol_rel']>=1.5).mean():.2f} high {(P.loc[ishi,'bar_vol_rel']>=1.5).mean():.2f}")
    # k-matched: for each k in 1..7 compare medians (bar 0 excluded since bar 0 has no neighbours)
    print("  k-matched medians (low bar / high bar / ordinary) for bar_vol_rel, bar_rng_rel:")
    for k in range(1, 8):
        a = P[(P.k == k)]
        print(f"    k={k}: vol low {a.loc[islo[a.index],'bar_vol_rel'].median():.2f} high {a.loc[ishi[a.index],'bar_vol_rel'].median():.2f} ord {a.loc[neither[a.index],'bar_vol_rel'].median():.2f} | rng low {a.loc[islo[a.index],'bar_rng_rel'].median():.2f} high {a.loc[ishi[a.index],'bar_rng_rel'].median():.2f} ord {a.loc[neither[a.index],'bar_rng_rel'].median():.2f} | n low {islo[a.index].sum()} high {ishi[a.index].sum()}")
    # Is the asymmetry just because lows are more often in bar 0 (which is wide)? exclude k=0
    P1 = P[P.k >= 1]; ishi1 = ishi[P1.index]; islo1 = islo[P1.index]; nei1 = neither[P1.index]
    print(f"  excluding k=0: low bar rng_rel {P1.loc[islo1,'bar_rng_rel'].median():.2f} vol {P1.loc[islo1,'bar_vol_rel'].median():.2f} close_loc {P1.loc[islo1,'bar_close_loc'].median():.2f} | high bar {P1.loc[ishi1,'bar_rng_rel'].median():.2f} {P1.loc[ishi1,'bar_vol_rel'].median():.2f} {P1.loc[ishi1,'bar_close_loc'].median():.2f} | ord {P1.loc[nei1,'bar_rng_rel'].median():.2f} {P1.loc[nei1,'bar_vol_rel'].median():.2f} {P1.loc[nei1,'bar_close_loc'].median():.2f}")
    # Mann-Whitney low-bar vs high-bar vol_rel
    print("  MWU low-bar vs high-bar vol_rel p:", stats.mannwhitneyu(P.loc[islo, 'bar_vol_rel'].dropna(), P.loc[ishi, 'bar_vol_rel'].dropna()).pvalue,
          " rng_rel p:", stats.mannwhitneyu(P.loc[islo, 'bar_rng_rel'].dropna(), P.loc[ishi, 'bar_rng_rel'].dropna()).pvalue)
    # also the lens included bar 8 in extreme bars? bar 8 (k=8) is not in k<=7 rows -> extremes at k=8 excluded; check with all k
    Pa = p[(p.n_bars == 9)].merge(x[["same_bar_extremes"]], left_on="date", right_index=True)
    print("  panel max k:", Pa.k.max())
    print(f"  wick medians: hi_bar_wick {x.hi_bar_wick.median():.2f} lo_bar_wick {x.lo_bar_wick.median():.2f}; vol share hi {x.hi_bar_vol_share.median():.3f} lo {x.lo_bar_vol_share.median():.3f}")

    print("--- T12: Tokyo/China open bars by DST ---")
    full = x[x.n_bars == 9]
    for dst, lab in [(0, "winter"), (1, "summer")]:
        f = full[full.is_dst == dst]
        hs = f.hi_k.value_counts(normalize=True).reindex(range(9)).fillna(0); ls = f.lo_k.value_counts(normalize=True).reindex(range(9)).fillna(0)
        print(f"  {lab} n={len(f)} tokyo_k={f.tokyo_open_k.mode()[0]} china_k={f.china_open_k.mode()[0]} high by k: {hs.round(3).tolist()} low: {ls.round(3).tolist()}")
    s = full[full.is_dst == 1]
    for ext in ["hi_k", "lo_k"]:
        k2 = (s[ext] == 2); nb = ((s[ext] == 1) | (s[ext] == 3)).sum() / 2 / len(s)
        pv = stats.binomtest(int(k2.sum()), len(s), nb).pvalue if nb > 0 else np.nan
        lo, hi = ci(k2.astype(float))
        h1 = k2[s.half == "H1"].mean(); h2 = k2[s.half == "H2"].mean()
        # also vs mean of k=1..7 excluding 2 (U-shape-free interior)
        inter = s[ext].isin([1, 3, 4, 5, 6, 7]).mean() / 6
        pv2 = stats.binomtest(int(k2.sum()), len(s), inter).pvalue
        print(f"  summer k=2 {ext}: share {k2.mean():.3f} CI[{lo:.3f},{hi:.3f}] neighbours(1,3) mean {nb:.3f} p={pv:.3f}; interior mean(1,3-7) {inter:.3f} p={pv2:.3f}; H1 {h1:.3f}(n{(s.half=='H1').sum()}) H2 {h2:.3f}(n{(s.half=='H2').sum()})")
    w = full[full.is_dst == 0]
    for ext in ["hi_k", "lo_k"]:
        k1 = (w[ext] == 1); nb = ((w[ext] == 2) | (w[ext] == 3)).sum() / 2 / len(w)
        pv = stats.binomtest(int(k1.sum()), len(w), nb).pvalue if nb > 0 else np.nan
        print(f"  winter k=1 {ext}: share {k1.mean():.3f} vs k2/k3 mean {nb:.3f} p={pv:.3f}; winter k=2 share {(w[ext]==2).mean():.3f} vs summer k=2 {(s[ext]==2).mean():.3f}")
    # China bars
    for dst, ck in [(0, 2), (1, 3)]:
        f = full[full.is_dst == dst]
        for ext in ["hi_k", "lo_k"]:
            kc = (f[ext] == ck); nb = ((f[ext] == ck - 1) | (f[ext] == ck + 1)).sum() / 2 / len(f)
            pv = stats.binomtest(int(kc.sum()), len(f), nb).pvalue if nb > 0 else np.nan
            print(f"  china bar dst={dst} k={ck} {ext}: share {kc.mean():.3f} vs neighbours {nb:.3f} p={pv:.3f}")
    # Fisher test H1 vs H2 for summer k=2 high share
    a = s[(s.half == "H1")]; b = s[(s.half == "H2")]
    print("  summer k=2 high H1 vs H2 fisher p:", stats.fisher_exact([[(a.hi_k == 2).sum(), (a.hi_k != 2).sum()], [(b.hi_k == 2).sum(), (b.hi_k != 2).sum()]])[1])

    print("--- T15: remaining move ---")
    P = p[(p.n_bars == 9) & (p.k <= 7)]
    for k in range(8):
        d = P[(P.k == k) & (P.high_done == 0)].remaining_up_bp; e = P[(P.k == k) & (P.low_done == 0)].remaining_down_bp
        cu = ci(d.values, fn=np.median); cd = ci(e.values, fn=np.median)
        d1 = P[(P.k == k) & (P.high_done == 0) & (P.half == "H1")].remaining_up_bp.median(); d2 = P[(P.k == k) & (P.high_done == 0) & (P.half == "H2")].remaining_up_bp.median()
        e1 = P[(P.k == k) & (P.low_done == 0) & (P.half == "H1")].remaining_down_bp.median(); e2 = P[(P.k == k) & (P.low_done == 0) & (P.half == "H2")].remaining_down_bp.median()
        print(f"  k={k} up|not done n={len(d)} p25/med/p75 {d.quantile(.25):.0f}/{d.median():.0f}/{d.quantile(.75):.0f} CI[{cu[0]:.0f},{cu[1]:.0f}] H1 {d1:.0f} H2 {d2:.0f} | down|not done n={len(e)} {e.quantile(.25):.0f}/{e.median():.0f}/{e.quantile(.75):.0f} CI[{cd[0]:.0f},{cd[1]:.0f}] H1 {e1:.0f} H2 {e2:.0f}")
    # check sign convention / definition: remaining_up_bp when high_done=0 should be >0
    print("  min remaining_up when not done:", P[P.high_done == 0].remaining_up_bp.min(), " max remaining_down when not done:", P[P.low_done == 0].remaining_down_bp.max())
    # is 'larger downside' a real asymmetry? compare |down| vs up at each k with MWU
    for k in [0, 2, 4, 6]:
        d = P[(P.k == k) & (P.high_done == 0)].remaining_up_bp; e = -P[(P.k == k) & (P.low_done == 0)].remaining_down_bp
        print(f"    k={k} MWU up vs |down| p={stats.mannwhitneyu(d, e).pvalue:.3f}  H1-only medians up {P[(P.k==k)&(P.high_done==0)&(P.half=='H1')].remaining_up_bp.median():.0f} |down| {-P[(P.k==k)&(P.low_done==0)&(P.half=='H1')].remaining_down_bp.median():.0f}")

print("\n--- T13: NQ vs ES ---")
xn, xe = XS["NQ"], XS["ES"]
j = xn[["hi_k", "lo_k", "n_bars", "hi_first", "high_above_rth_high", "low_below_rth_low", "half"]].join(
    xe[["hi_k", "lo_k", "n_bars", "hi_first", "high_above_rth_high", "low_below_rth_low"]], lsuffix="_nq", rsuffix="_es", how="inner")
j = j[(j.n_bars_nq == 9) & (j.n_bars_es == 9)]
print(f"  joint full sessions n={len(j)}")
same_h = (j.hi_k_nq == j.hi_k_es); same_l = (j.lo_k_nq == j.lo_k_es)
ph = j.hi_k_nq.value_counts(normalize=True).reindex(range(9)).fillna(0); pe = j.hi_k_es.value_counts(normalize=True).reindex(range(9)).fillna(0)
pl = j.lo_k_nq.value_counts(normalize=True).reindex(range(9)).fillna(0); ple = j.lo_k_es.value_counts(normalize=True).reindex(range(9)).fillna(0)
indep_h = (ph * pe).sum(); indep_l = (pl * ple).sum()
print(f"  same high bar {same_h.mean():.3f} CI{ci(same_h.astype(float))} (indep {indep_h:.3f}); within +-1 {(abs(j.hi_k_nq-j.hi_k_es)<=1).mean():.3f}; H1 {same_h[j.half=='H1'].mean():.3f} H2 {same_h[j.half=='H2'].mean():.3f}")
print(f"  same low bar {same_l.mean():.3f} CI{ci(same_l.astype(float))} (indep {indep_l:.3f}); within +-1 {(abs(j.lo_k_nq-j.lo_k_es)<=1).mean():.3f}; H1 {same_l[j.half=='H1'].mean():.3f} H2 {same_l[j.half=='H2'].mean():.3f}")
print(f"  both same {(same_h & same_l).mean():.3f}; agree hi_first {(j.hi_first_nq==j.hi_first_es).mean():.3f}; agree high_above {(j.high_above_rth_high_nq==j.high_above_rth_high_es).mean():.3f}; agree low_below {(j.low_below_rth_low_nq==j.low_below_rth_low_es).mean():.3f}")
dh = j[~same_h]; dl = j[~same_l]
kh = int((dh.hi_k_nq < dh.hi_k_es).sum()); kl = int((dl.lo_k_nq < dl.lo_k_es).sum())
print(f"  NQ earlier | different: highs {kh}/{len(dh)}={kh/len(dh):.3f} p={stats.binomtest(kh,len(dh),.5).pvalue:.2f}; lows {kl}/{len(dl)}={kl/len(dl):.3f} p={stats.binomtest(kl,len(dl),.5).pvalue:.2f}")
print(f"    H1: highs {(dh[dh.half=='H1'].hi_k_nq<dh[dh.half=='H1'].hi_k_es).mean():.2f} lows {(dl[dl.half=='H1'].lo_k_nq<dl[dl.half=='H1'].lo_k_es).mean():.2f}; H2: highs {(dh[dh.half=='H2'].hi_k_nq<dh[dh.half=='H2'].hi_k_es).mean():.2f} lows {(dl[dl.half=='H2'].lo_k_nq<dl[dl.half=='H2'].lo_k_es).mean():.2f}")
# panel agreement
pn = PS["NQ"]; pe_ = PS["ES"]
pj = pn[pn.n_bars == 9][["date", "k", "high_done", "low_done"]].merge(pe_[pe_.n_bars == 9][["date", "k", "high_done", "low_done"]], on=["date", "k"], suffixes=("_nq", "_es"))
pj = pj[pj.k <= 7]
for k in range(8):
    d = pj[pj.k == k]
    print(f"  k={k} P(ES hd|NQ hd)={d[d.high_done_nq==1].high_done_es.mean():.2f} P(ES hd|NQ not)={d[d.high_done_nq==0].high_done_es.mean():.2f} agree high {(d.high_done_nq==d.high_done_es).mean():.2f} low {(d.low_done_nq==d.low_done_es).mean():.2f}")

print("\n--- T14: 15-minute timing ---")
for sym in ["NQ", "ES"]:
    m = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv")
    m.columns = [c.lower() for c in m.columns]
    tcol = [c for c in m.columns if "date" in c or "time" in c][0]
    m["ts"] = pd.to_datetime(m[tcol], utc=True).dt.tz_convert("America/New_York")
    m = m.sort_values("ts")
    # Asia session: 18:00 .. 02:59 ET; session id = date of the 18:00 bar (RTH date D)
    m["h"] = m.ts.dt.hour; m["mi"] = m.ts.dt.minute
    asia = m[(m.h >= 18) | (m.h <= 2)].copy()
    asia["sess"] = np.where(asia.h >= 18, asia.ts.dt.normalize(), (asia.ts - pd.Timedelta(days=1)).dt.normalize())
    asia["k"] = np.where(asia.h >= 18, asia.h - 18, asia.h + 6); asia["slot"] = asia.mi // 15
    g = asia.groupby("sess")
    rows = []
    for s, d in g:
        if len(d) < 36: continue  # full session = 36 x 15m bars
        hi_i = d.high.idxmax(); lo_i = d.low.idxmin()
        open0 = d.iloc[0].open
        rows.append(dict(sess=s, hi_k=d.loc[hi_i, "k"], hi_slot=d.loc[hi_i, "slot"], lo_k=d.loc[lo_i, "k"], lo_slot=d.loc[lo_i, "slot"],
                         hi_eq_open=d.loc[hi_i, "high"] == open0, lo_eq_open=d.loc[lo_i, "low"] == open0, nbar=len(d),
                         hi_at_open_slot_eq=(d.loc[hi_i, "k"] == 0) and (d.loc[hi_i, "slot"] == 0) and (d.loc[hi_i, "high"] == d.loc[hi_i, "open"])))
    r = pd.DataFrame(rows)
    print(f"  {sym}: full 15m sessions n={len(r)} (range {r.sess.min().date()}..{r.sess.max().date()}), nbar counts {r.nbar.value_counts().to_dict()}")
    b0h = r[r.hi_k == 0]; b0l = r[r.lo_k == 0]; b8h = r[r.hi_k == 8]; b8l = r[r.lo_k == 8]
    print(f"    bar-0 highs n={len(b0h)} slots {b0h.hi_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}; bar-0 lows n={len(b0l)} slots {b0l.lo_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}")
    print(f"    extreme == 18:00 open print: highs {int(b0h.hi_eq_open.sum())}/{len(b0h)}, lows {int(b0l.lo_eq_open.sum())}/{len(b0l)}; high==open of its own 15m bar in slot0: {int(b0h.hi_at_open_slot_eq.sum())}")
    print(f"    bar-8 highs n={len(b8h)} slots {b8h.hi_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}; bar-8 lows n={len(b8l)} slots {b8l.lo_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}")
    mid_h = r[(r.hi_k >= 1) & (r.hi_k <= 7)]; mid_l = r[(r.lo_k >= 1) & (r.lo_k <= 7)]
    print(f"    middle highs n={len(mid_h)} slots {mid_h.hi_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}; middle lows n={len(mid_l)} slots {mid_l.lo_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}")
    n0 = len(b0h) + len(b0l); k0 = int((b0h.hi_slot == 0).sum() + (b0l.lo_slot == 0).sum())
    print(f"    first-slot share bar-0 extremes {k0}/{n0} p={stats.binomtest(k0, n0, .25).pvalue:.1e}; bar-8 lows last slot {int((b8l.lo_slot==3).sum())}/{len(b8l)} p={stats.binomtest(int((b8l.lo_slot==3).sum()), len(b8l), .25).pvalue:.3f}; bar-8 highs last slot {int((b8h.hi_slot==3).sum())}/{len(b8h)}")
    # cross-check hi_k from 15m vs hourly table
    xx = XS[sym]
    cmp_ = r.set_index("sess").join(xx[["hi_k", "lo_k"]], rsuffix="_1h", how="inner")
    print(f"    agreement of 15m-derived hi_k with hourly table: {(cmp_.hi_k==cmp_.hi_k_1h).mean():.2f}, lo_k {(cmp_.lo_k==cmp_.lo_k_1h).mean():.2f} (n={len(cmp_)})")
