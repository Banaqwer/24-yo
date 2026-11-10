"""T8 (ex-post sequel), T9, T11, T12, T13, T14: ex-post claims by quarter / regime / Sunday / leave-5-out."""
import sys
sys.path.insert(0, "research/extremes/scripts/refute_timing_regime")
import numpy as np, pandas as pd
from rcommon import *
from scipy import stats
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_colwidth", 200)
MK = ["claim", "n_a", "n_b", "med_a", "med_b", "diff", "p_mw", "quarters", "n_quarters_same_sign", "n_quarters_eval", "flip_quarters", "l5o_diff", "l5o_p_mw", "l5o_kills", "ex_all_regimes", "sunday_only", "weekday_only", "H1", "H2", "verdict_rule"]
MED = []

# ======================= T8 ex-post sequel: drop after a break vs no break =======================
for sym in ["NQ", "ES"]:
    x, p = load(sym); x = x.copy(); x["date"] = x.index
    print(f"\n\n################ {sym} T8 ex-post sequels (n={len(x)}) ################")
    hv = x.hi_vs_rth_high_bp
    d = median_check(x, hv > 15, hv < -15, "drop_after_hi_bp", f"{sym} T8 drop_after_hi: high>RTH high+15 vs high<RTH high-15"); MED.append(d); show(d, MK)
    d = median_check(x, hv > 15, hv < -15, "hi_k", f"{sym} T8 hi_k: break>15 vs <-15"); MED.append(d); show(d, MK)
    d = median_check(x, hv > 15, hv < -15, "close_loc", f"{sym} T8 close_loc: break>15 vs <-15"); MED.append(d); show(d, MK)
    # the drop normalised by the ex-ante range (breaks happen on big-range nights?)
    x["drop_rel"] = x.drop_after_hi_bp / (x.asia_rng_med20 * 1e4)
    d = median_check(x, hv > 15, hv < -15, "drop_rel", f"{sym} T8 drop_after_hi / med20 range: break>15 vs <-15"); MED.append(d); show(d, MK)
    # confound: a late high mechanically has less room to drop. Compare drop at matched hi_k
    print("  drop_after_hi median by hi_k, break>15 vs <-15:")
    for kk in [(0, 2), (3, 5), (6, 8)]:
        m = x.hi_k.between(*kk)
        a = x[m & (hv > 15)].drop_after_hi_bp; b = x[m & (hv < -15)].drop_after_hi_bp
        print(f"    hi_k {kk}: break {a.median():.1f} (n={len(a)}) vs no-break {b.median():.1f} (n={len(b)})")
    lv = x.lo_vs_rth_low_bp
    d = median_check(x, lv < -15, lv > 15, "rally_after_lo_bp", f"{sym} T8 rally_after_lo: low<RTH low-15 vs low>RTH low+15"); MED.append(d); show(d, MK)

# ======================= T9: level magnets, spike ratio by quarter / regime =======================
def spike_ratio(v, w=5):
    v = pd.Series(v).dropna().values
    if len(v) < 10: return np.nan, len(v), np.nan, np.nan
    inner = np.mean(np.abs(v) <= w); neigh = np.mean((np.abs(v) > w) & (np.abs(v) <= 3 * w)) / 2
    return (inner / neigh if neigh > 0 else np.nan), len(v), inner, neigh

for sym in ["NQ", "ES"]:
    x, p = load(sym); x = x.copy()
    x["hi_vs_rth_open_bp"] = (x.asia_high / x.lvl_rth_open - 1) * 1e4; x["lo_vs_rth_open_bp"] = (x.asia_low / x.lvl_rth_open - 1) * 1e4
    print(f"\n\n################ {sym} T9 spike ratios by quarter (ratio = share within 5bp / mean share in 5-15bp shells) ################")
    rows = []
    for col, lab in [("hi_vs_rth_high_bp", "high vs RTH high"), ("lo_vs_rth_low_bp", "low vs RTH low"), ("hi_vs_rth_vwap_bp", "high vs VWAP"), ("lo_vs_rth_vwap_bp", "low vs VWAP"),
                     ("hi_vs_prior_asia_high_bp", "high vs prior Asia high"), ("lo_vs_prior_asia_low_bp", "low vs prior Asia low"), ("hi_bp", "high vs 17:00 close"), ("lo_bp", "low vs 17:00 close"), ("lo_vs_rth_open_bp", "low vs RTH open")]:
        r_all, n_all, inn, nei = spike_ratio(x[col])
        row = dict(sym=sym, level=lab, n=n_all, ratio=r_all, within5=inn)
        qs = []
        for q in sorted(x.q.unique()):
            r, n, _, _ = spike_ratio(x[x.q == q][col]); qs.append(r); row[q] = r
        qs = np.array(qs, float)
        row["n_q_gt1"] = int(np.nansum(qs > 1)); row["n_q_eval"] = int(np.sum(~np.isnan(qs)))
        row["ex_regimes"] = spike_ratio(x[x.regime == "normal"][col])[0]
        row["sunday"] = spike_ratio(x[x.sunday_open == 1][col])[0]; row["weekday"] = spike_ratio(x[x.sunday_open == 0][col])[0]
        # more powerful pooled test: is the 2-bp bin at 0 (|v|<=2) elevated vs +-2..10?  share within 2 / (share 2..10 / 4)
        v = x[col].dropna().values
        row["ratio_2bp"] = np.mean(np.abs(v) <= 2) / (np.mean((np.abs(v) > 2) & (np.abs(v) <= 10)) / 4)
        # exact binomial on count within 5 vs expected from shells (expected prob = share in 5..15 / 2 ... same as ratio)
        k_in = int(np.sum(np.abs(v) <= 5)); n_band = int(np.sum(np.abs(v) <= 15))
        # under a locally flat density, the within-5 count is Binomial(n_band, 1/3)
        row["p_flat"] = binom_p(k_in, n_band, 1 / 3) if n_band else np.nan
        row["k_in5"] = k_in; row["n_in15"] = n_band
        rows.append(row)
    S = pd.DataFrame(rows); S.to_csv(f"{OUT}/t9_{sym}_spike_by_quarter.csv", index=False)
    print(S.round(2).to_string())
    # share of highs within 5 bp of any of the 4 main levels, by quarter
    lv_hi = x[["hi_vs_rth_high_bp", "hi_vs_rth_vwap_bp", "hi_vs_prior_asia_high_bp", "hi_bp"]].abs()
    any5 = (lv_hi <= 5).any(axis=1)
    print("  share of highs within 5bp of any main level:", round(any5.mean(), 3), "by quarter:", any5.groupby(x.q).mean().round(2).to_dict())
    # 'at least one of the 4 levels within 5bp' expected if independent flat: 1-(1-p_i) product
    ps = [(x[c].abs() <= 5).mean() for c in ["hi_vs_rth_high_bp", "hi_vs_rth_vwap_bp", "hi_vs_prior_asia_high_bp", "hi_bp"]]
    print("  per-level within-5bp shares:", np.round(ps, 3), " independent-union expectation:", round(1 - np.prod([1 - q for q in ps]), 3))

# ======================= T11: extreme bar signature by quarter =======================
for sym in ["NQ", "ES"]:
    x, p = load(sym); p = p[p.n_bars == 9].copy(); p["date"] = pd.to_datetime(p.date)
    p["is_hi"] = (p.k == p.hi_k).astype(int); p["is_lo"] = (p.k == p.lo_k).astype(int)
    print(f"\n\n################ {sym} T11 extreme-bar signature ################")
    lo_bar = (p.is_lo == 1) & (p.is_hi == 0); hi_bar = (p.is_hi == 1) & (p.is_lo == 0); oth = (p.is_lo == 0) & (p.is_hi == 0)
    for col in ["bar_rng_rel", "bar_vol_rel", "bar_close_loc"]:
        d = median_check(p, lo_bar, oth, col, f"{sym} T11 LOW bar vs ordinary: {col}"); MED.append(d); show(d, MK)
        d = median_check(p, hi_bar, oth, col, f"{sym} T11 HIGH bar vs ordinary: {col}"); MED.append(d); show(d, MK)
    # asymmetry: low bar sharper than high bar, by quarter
    print("  asymmetry per quarter (low-bar median - high-bar median) for rng_rel / vol_rel / close_loc:")
    for q in sorted(p.q.unique()):
        dq = p.q == q
        s = []
        for col in ["bar_rng_rel", "bar_vol_rel", "bar_close_loc"]:
            s.append(p[lo_bar & dq][col].median() - p[hi_bar & dq][col].median())
        print(f"    {q}: {np.round(s, 2)} (n low={int((lo_bar & dq).sum())}, high={int((hi_bar & dq).sum())})")
    # k-matched: is the low-bar excess present when excluding k=0 and k=8 (where the extreme is mechanically the bar's open/close)?
    mid = (p.k >= 1) & (p.k <= 7)
    for col in ["bar_rng_rel", "bar_vol_rel", "bar_close_loc"]:
        a = p[lo_bar & mid][col]; b = p[oth & mid][col]; c = p[hi_bar & mid][col]
        print(f"  k=1..7 only: {col}: low bar {a.median():.2f} (n={len(a)}) | high bar {c.median():.2f} (n={len(c)}) | ordinary {b.median():.2f}")
    # by sunday
    for col in ["bar_rng_rel", "bar_vol_rel"]:
        for lab, m in [("sunday", p.sunday_open == 1), ("weekday", p.sunday_open == 0)]:
            print(f"  {lab}: {col}: low bar {p[lo_bar & m][col].median():.2f} | high bar {p[hi_bar & m][col].median():.2f} | ordinary {p[oth & m][col].median():.2f}")

# ======================= T12: Tokyo / China bars by DST season-year =======================
for sym in ["NQ", "ES"]:
    x, p = load(sym); x = x[x.n_bars == 9].copy()
    # season-year labels
    def season(d):
        if d < pd.Timestamp("2024-11-03"): return "summer24"
        if d < pd.Timestamp("2025-03-09"): return "winter24/25"
        if d < pd.Timestamp("2025-11-02"): return "summer25"
        if d < pd.Timestamp("2026-03-08"): return "winter25/26"
        if d < pd.Timestamp("2026-11-01"): return "summer26"
        return "winter26/27"
    x["season"] = [season(d) for d in x.index]
    print(f"\n\n################ {sym} T12 Tokyo/China bars by season ################")
    print(pd.crosstab(x.season, x.is_dst))
    rows = []
    for s in ["summer24", "summer25", "summer26", "winter24/25", "winter25/26", "winter26/27"]:
        d = x[x.season == s]
        if len(d) < 10: continue
        tko = int(d.tokyo_open_k.iloc[0]); cno = int(d.china_open_k.iloc[0])
        for ext, kcol in [("high", "hi_k"), ("low", "lo_k")]:
            at = (d[kcol] == tko).mean(); nb = d[kcol].isin([tko - 1, tko + 1]).mean() / 2
            atc = (d[kcol] == cno).mean(); nbc = d[kcol].isin([cno - 1, cno + 1]).mean() / 2
            rows.append(dict(sym=sym, season=s, n=len(d), ext=ext, tokyo_k=tko, share_tokyo=at, share_tokyo_nb=nb, lift_tokyo=at - nb, p_tokyo=binom_p(int((d[kcol] == tko).sum()), len(d), nb) if nb > 0 else np.nan,
                             china_k=cno, share_china=atc, share_china_nb=nbc, lift_china=atc - nbc, dist=" ".join(f"{(d[kcol] == k).mean():.2f}" for k in range(9))))
    T = pd.DataFrame(rows); T.to_csv(f"{OUT}/t12_{sym}_tokyo_by_season.csv", index=False); print(T.round(3).to_string())
    # summer k=2 by quarter (summer quarters only)
    s = x[x.is_dst == 1]
    print("  summer k=2 share of highs by quarter:", s.groupby("q").apply(lambda d: f"{(d.hi_k == 2).mean():.2f}({len(d)})").to_dict())
    print("  summer k=2 share of lows  by quarter:", s.groupby("q").apply(lambda d: f"{(d.lo_k == 2).mean():.2f}({len(d)})").to_dict())
    print("  summer k=2 high share: sunday", round((s[s.sunday_open == 1].hi_k == 2).mean(), 3), "weekday", round((s[s.sunday_open == 0].hi_k == 2).mean(), 3), "| ex regimes", round((s[s.regime == 'normal'].hi_k == 2).mean(), 3))
    # JST-clock pooled: share at 09:00 JST bar vs 10:00 JST bar vs 08:00 JST
    print("  pooled JST hour share of highs:", x.hi_hour_jst.value_counts(normalize=True).sort_index().round(3).to_dict())

# ======================= T13: NQ vs ES by quarter =======================
xn, pn = load("NQ"); xe, pe = load("ES")
j = xn[["hi_k", "lo_k", "n_bars", "q", "half", "sunday_open", "regime", "high_above_rth_high", "low_below_rth_low", "hi_first"]].join(xe[["hi_k", "lo_k", "n_bars", "high_above_rth_high", "low_below_rth_low", "hi_first"]], rsuffix="_es", how="inner")
j = j[(j.n_bars == 9) & (j.n_bars_es == 9)].copy(); j["date"] = j.index
print(f"\n\n################ T13 NQ vs ES joint sessions n={len(j)} ################")
j["same_hi"] = (j.hi_k == j.hi_k_es).astype(int); j["same_lo"] = (j.lo_k == j.lo_k_es).astype(int)
j["nq_earlier_hi"] = np.where(j.hi_k != j.hi_k_es, (j.hi_k < j.hi_k_es).astype(float), np.nan); j["nq_earlier_lo"] = np.where(j.lo_k != j.lo_k_es, (j.lo_k < j.lo_k_es).astype(float), np.nan)
for q in sorted(j.q.unique()):
    d = j[j.q == q]
    pn_ = d.hi_k.value_counts(normalize=True).reindex(range(9)).fillna(0); pe_ = d.hi_k_es.value_counts(normalize=True).reindex(range(9)).fillna(0); null_hi = float((pn_ * pe_).sum())
    pn_ = d.lo_k.value_counts(normalize=True).reindex(range(9)).fillna(0); pe_ = d.lo_k_es.value_counts(normalize=True).reindex(range(9)).fillna(0); null_lo = float((pn_ * pe_).sum())
    dh = d.nq_earlier_hi.dropna(); dl = d.nq_earlier_lo.dropna()
    print(f"  {q}: n={len(d)} same hi {d.same_hi.mean():.2f} (null {null_hi:.2f}) same lo {d.same_lo.mean():.2f} (null {null_lo:.2f}) | NQ earlier hi {dh.mean():.2f} (n={len(dh)}) lo {dl.mean():.2f} (n={len(dl)})")
for lab, m in [("sunday", j.sunday_open == 1), ("weekday", j.sunday_open == 0), ("ex regimes", j.regime == "normal"), ("iran war", j.regime == "iran_war_acute"), ("tariff", j.regime == "tariff_apr25")]:
    d = j[m]; dh = d.nq_earlier_hi.dropna(); dl = d.nq_earlier_lo.dropna()
    print(f"  {lab}: n={len(d)} same hi {d.same_hi.mean():.2f} same lo {d.same_lo.mean():.2f} | NQ earlier hi {dh.mean():.2f} (n={len(dh)}) lo {dl.mean():.2f} (n={len(dl)})")
# lead/lag pooled binomial and by half
for col in ["nq_earlier_hi", "nq_earlier_lo"]:
    v = j[col].dropna(); print(f"  {col}: {v.mean():.3f} n={len(v)} p={binom_p(int(v.sum()), len(v), .5):.2f} | H1 {j[j.half=='H1'][col].dropna().mean():.2f} H2 {j[j.half=='H2'][col].dropna().mean():.2f}")
# panel agreement by quarter
pj = pn[pn.n_bars == 9][["date", "k", "high_done", "low_done", "q"]].merge(pe[pe.n_bars == 9][["date", "k", "high_done", "low_done"]], on=["date", "k"], suffixes=("_nq", "_es"))
pj = pj[pj.k <= 7]
print("  panel agreement on high_done by quarter:", pj.groupby("q").apply(lambda d: round((d.high_done_nq == d.high_done_es).mean(), 2)).to_dict())
print("  panel agreement on low_done  by quarter:", pj.groupby("q").apply(lambda d: round((d.low_done_nq == d.low_done_es).mean(), 2)).to_dict())

# ======================= T14: 15-minute timing =======================
print("\n\n################ T14 15-minute timing ################")
for sym in ["NQ", "ES"]:
    m = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv")
    m["ts"] = pd.to_datetime(m["Datetime"], utc=True).dt.tz_convert("America/New_York")
    m = m.set_index("ts").sort_index()
    m["hour"] = m.index.hour; m["minute"] = m.index.minute
    g = pd.Series(m.index.date, index=m.index); sh = m.index.hour >= 18
    g[sh] = (m.index[sh] + pd.Timedelta(days=1)).date
    m["gdate"] = g.values
    a = m[m.hour.isin(list(range(18, 24)) + [0, 1, 2])]
    rows = []
    for gd, grp in a.groupby("gdate"):
        if len(grp) < 30: continue
        hi_i = int(np.argmax(grp.High.values)); lo_i = int(np.argmin(grp.Low.values))
        th = grp.index[hi_i]; tl = grp.index[lo_i]
        rows.append(dict(sym=sym, gdate=pd.Timestamp(gd), n15=len(grp), hi_k=(th.hour - 18) % 24, hi_min=th.minute, lo_k=(tl.hour - 18) % 24, lo_min=tl.minute,
                         hi_is_open_print=int(hi_i == 0 and grp.High.iloc[0] == grp.Open.iloc[0]), lo_is_open_print=int(lo_i == 0 and grp.Low.iloc[0] == grp.Open.iloc[0]),
                         sunday=int(pd.Timestamp(gd).dayofweek == 0), month=pd.Timestamp(gd).strftime("%Y-%m"),
                         n_ties_hi=int((grp.High.values == grp.High.max()).sum()), n_ties_lo=int((grp.Low.values == grp.Low.min()).sum())))
    M = pd.DataFrame(rows)
    print(f"\n{sym}: sessions {len(M)}, date range {M.gdate.min().date()}..{M.gdate.max().date()}, n15 distribution {M.n15.value_counts().to_dict()}")
    print("  ties at the extreme price (hi/lo appear in >1 15m bar):", int((M.n_ties_hi > 1).sum()), int((M.n_ties_lo > 1).sum()))
    b0h = M[M.hi_k == 0]; b0l = M[M.lo_k == 0]
    print(f"  bar-0 highs n={len(b0h)}: minute slots {b0h.hi_min.value_counts().sort_index().to_dict()} | open print {int(b0h.hi_is_open_print.sum())} | sunday {int(b0h.sunday.sum())} | first-slot share by month {b0h.groupby('month').apply(lambda d: f'{(d.hi_min==0).mean():.2f}({len(d)})').to_dict()}")
    print(f"  bar-0 lows  n={len(b0l)}: minute slots {b0l.lo_min.value_counts().sort_index().to_dict()} | open print {int(b0l.lo_is_open_print.sum())} | sunday {int(b0l.sunday.sum())} | first-slot share by month {b0l.groupby('month').apply(lambda d: f'{(d.lo_min==0).mean():.2f}({len(d)})').to_dict()}")
    first0 = pd.concat([b0h.hi_min == 0, b0l.lo_min == 0])
    print(f"  bar-0 first-slot share pooled {first0.mean():.2f} (n={len(first0)}) p vs .25 = {binom_p(int(first0.sum()), len(first0), .25):.2g}; sunday-only {pd.concat([b0h[b0h.sunday==1].hi_min==0, b0l[b0l.sunday==1].lo_min==0]).mean():.2f} (n={int(b0h.sunday.sum()+b0l.sunday.sum())}); weekday-only {pd.concat([b0h[b0h.sunday==0].hi_min==0, b0l[b0l.sunday==0].lo_min==0]).mean():.2f}")
    # leave-5-out: remove 5 first-slot cases
    k5 = int(first0.sum()) - 5; n5 = len(first0) - 5
    print(f"  bar-0 leave-5-out: {k5}/{n5} = {k5/n5:.2f}, p vs .25 = {binom_p(k5, n5, .25):.2g}")
    b8h = M[M.hi_k == 8]; b8l = M[M.lo_k == 8]
    print(f"  bar-8 highs n={len(b8h)}: slots {b8h.hi_min.value_counts().sort_index().to_dict()} | bar-8 lows n={len(b8l)}: slots {b8l.lo_min.value_counts().sort_index().to_dict()} by month {b8l.groupby('month').apply(lambda d: f'{(d.lo_min==45).mean():.2f}({len(d)})').to_dict()}")
    k8 = int((b8l.lo_min == 45).sum()); print(f"  bar-8 lows last-slot share {k8}/{len(b8l)} p={binom_p(k8, len(b8l), .25):.2g}; leave-5-out {max(k8-5,0)}/{max(len(b8l)-5,0)} p={binom_p(max(k8-5,0), max(len(b8l)-5,1), .25):.2g}")
    k8h = int((b8h.hi_min == 45).sum()); print(f"  bar-8 highs last-slot share {k8h}/{len(b8h)} p={binom_p(k8h, len(b8h), .25):.2g}")
    mid = M[(M.hi_k > 0) & (M.hi_k < 8)]; midl = M[(M.lo_k > 0) & (M.lo_k < 8)]
    print(f"  middle-bar highs slots {mid.hi_min.value_counts().sort_index().to_dict()} chi2 p={stats.chisquare(mid.hi_min.value_counts().reindex([0,15,30,45]).fillna(0)).pvalue:.2f}; lows {midl.lo_min.value_counts().sort_index().to_dict()} p={stats.chisquare(midl.lo_min.value_counts().reindex([0,15,30,45]).fillna(0)).pvalue:.2f}")
    # cross-check hourly-derived hi_k against 15m-derived hi_k
    x, _ = load(sym)
    xx = x[["hi_k", "lo_k", "asia_gdate"]].copy(); xx["asia_gdate"] = pd.to_datetime(xx.asia_gdate)
    mm = M.merge(xx, left_on="gdate", right_on="asia_gdate", suffixes=("", "_1h"))
    print(f"  cross-check vs hourly table: n={len(mm)}, hi_k agree {int((mm.hi_k == mm.hi_k_1h).sum())}, lo_k agree {int((mm.lo_k == mm.lo_k_1h).sum())}")
    M.to_csv(f"{OUT}/t14_{sym}_15m.csv", index=False)

R = pd.DataFrame(MED); R.to_csv(f"{OUT}/r3_median_claims.csv", index=False)
print("\n\n=== SUMMARY r3 (median claims) ===")
print(R[["claim", "n_a", "n_b", "med_a", "med_b", "diff", "p_mw", "n_quarters_same_sign", "n_quarters_eval", "flip_quarters", "l5o_kills", "verdict_rule"]].round(3).to_string())
