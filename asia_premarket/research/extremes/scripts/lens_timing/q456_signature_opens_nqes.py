"""Q4 extreme-bar signature (ex post), Q5 Tokyo/China open bars, Q6 NQ vs ES and 15-minute timing inside the hourly bars."""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_timing")
import numpy as np, pandas as pd
from common import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
ncomp = 0

# ======================= Q4: extreme-bar signature =======================
for sym in ["NQ", "ES"]:
    x, p = load(sym)
    p = p[p.n_bars == 9].copy()
    p["is_hi_bar"] = (p.k == p.hi_k).astype(int); p["is_lo_bar"] = (p.k == p.lo_k).astype(int)
    p["bar_ret_abs"] = p.bar_ret_bp.abs()
    rows = []
    for lab, flag, oth in [("high bar", "is_hi_bar", "is_lo_bar"), ("low bar", "is_lo_bar", "is_hi_bar")]:
        A = p[(p[flag] == 1) & (p[oth] == 0)]           # extreme bar, excluding same-bar extremes
        B = p[(p[flag] == 0) & (p[oth] == 0)]           # ordinary bars (neither extreme)
        for col in ["bar_close_loc", "bar_ret_bp", "bar_ret_abs", "bar_vol_rel", "bar_rng_rel", "bar_rng_bp"]:
            a = A[col].dropna(); b = B[col].dropna()
            lo, hi = boot_ci_diff(a.values, b.values, np.median)
            rows.append(dict(sym=sym, bar=lab, stat=col, n_ext=len(a), n_other=len(b), med_ext=a.median(), med_other=b.median(), diff_med=a.median() - b.median(), ci90_lo=lo, ci90_hi=hi,
                             med_ext_H1=A[A.half == "H1"][col].median(), med_ext_H2=A[A.half == "H2"][col].median(), med_oth_H1=B[B.half == "H1"][col].median(), med_oth_H2=B[B.half == "H2"][col].median()))
            ncomp += 1
        # binary signatures
        for lab2, fn in [("close in lower half", lambda d: d.bar_close_loc < 0.5), ("close in lower quarter", lambda d: d.bar_close_loc < 0.25), ("close in upper half", lambda d: d.bar_close_loc >= 0.5), ("close in upper quarter", lambda d: d.bar_close_loc >= 0.75),
                         ("bar down", lambda d: d.bar_ret_bp < 0), ("vol_rel>=1.5", lambda d: d.bar_vol_rel >= 1.5), ("rng_rel>=1.5", lambda d: d.bar_rng_rel >= 1.5)]:
            a = fn(A).mean(); b = fn(B).mean(); ka = int(fn(A).sum())
            rows.append(dict(sym=sym, bar=lab, stat=lab2, n_ext=len(A), n_other=len(B), med_ext=a, med_other=b, diff_med=a - b, ci90_lo=boot_ci(fn(A).values.astype(float))[0], ci90_hi=boot_ci(fn(A).values.astype(float))[1],
                             p_binom=binom_p(ka, len(A), b), med_ext_H1=fn(A[A.half == "H1"]).mean(), med_ext_H2=fn(A[A.half == "H2"]).mean(), med_oth_H1=fn(B[B.half == "H1"]).mean(), med_oth_H2=fn(B[B.half == "H2"]).mean()))
            ncomp += 1
    SIG = pd.DataFrame(rows); SIG.to_csv(f"{OUT}/q4_{sym}_extreme_bar_signature.csv", index=False)
    print(f"\n=== Q4 {sym}: extreme bar vs ordinary bars (medians / shares) ===")
    print(SIG[["bar", "stat", "n_ext", "n_other", "med_ext", "med_other", "diff_med", "ci90_lo", "ci90_hi", "med_ext_H1", "med_ext_H2", "med_oth_H1", "med_oth_H2"]].round(3).to_string())
    # same-k control: the high bar vs other bars at the same k, for close_loc and vol_rel (k-matched)
    rows = []
    for k in range(9):
        d = p[p.k == k]
        for lab, flag in [("hi", "is_hi_bar"), ("lo", "is_lo_bar")]:
            a = d[d[flag] == 1]; b = d[d[flag] == 0]
            rows.append(dict(k=k, bar=lab, n_ext=len(a), close_loc_ext=a.bar_close_loc.median(), close_loc_oth=b.bar_close_loc.median(), vol_rel_ext=a.bar_vol_rel.median(), vol_rel_oth=b.bar_vol_rel.median(),
                             rng_rel_ext=a.bar_rng_rel.median(), rng_rel_oth=b.bar_rng_rel.median(), share_lower_half_ext=(a.bar_close_loc < .5).mean(), share_lower_half_oth=(b.bar_close_loc < .5).mean()))
    KM = pd.DataFrame(rows); KM.to_csv(f"{OUT}/q4_{sym}_signature_by_k.csv", index=False); print(KM.round(2).to_string())
    # wick from extremes table
    print(f"{sym} hi_bar_wick median {x.hi_bar_wick.median():.2f} (H1 {x[x.half=='H1'].hi_bar_wick.median():.2f}, H2 {x[x.half=='H2'].hi_bar_wick.median():.2f}); lo_bar_wick median {x.lo_bar_wick.median():.2f}; hi_bar_vol_share median {x.hi_bar_vol_share.median():.3f} lo {x.lo_bar_vol_share.median():.3f} (1/9={1/9:.3f})")
    # is the volume signal in Q2 explained by down bars? P(high_done | k, bar down & vol>=1.5) vs (bar up & vol>=1.5)
    d = p[(p.k >= 1) & (p.k <= 7)]
    for lab, m in [("vol>=1.5 & bar down", (d.bar_vol_rel >= 1.5) & (d.bar_ret_bp < 0)), ("vol>=1.5 & bar up", (d.bar_vol_rel >= 1.5) & (d.bar_ret_bp >= 0)), ("vol<1.5 & bar down", (d.bar_vol_rel < 1.5) & (d.bar_ret_bp < 0)), ("vol<1.5 & bar up", (d.bar_vol_rel < 1.5) & (d.bar_ret_bp >= 0))]:
        print(f"  {sym} k=1..7 {lab:22s} n={int(m.sum()):4d} P(high_done)={d[m].high_done.mean():.2f} P(low_done)={d[m].low_done.mean():.2f}")
        ncomp += 2

# ======================= Q5: Tokyo / China open bars =======================
for sym in ["NQ", "ES"]:
    x, p = load(sym)
    x = x[x.n_bars == 9]
    rows = []
    for dst in [0, 1]:
        d = x[x.is_dst == dst]
        tko = d.tokyo_open_k.iloc[0]; cno = d.china_open_k.iloc[0]
        for ext, kcol in [("high", "hi_k"), ("low", "lo_k")]:
            dist = d[kcol].value_counts(normalize=True).reindex(range(9)).fillna(0)
            for k in range(9):
                rows.append(dict(sym=sym, is_dst=dst, ext=ext, k=k, hour_et=(18 + k) % 24, share=dist[k], n=len(d), is_tokyo=int(k == tko), is_china=int(k == cno),
                                 share_H1=(d[d.half == "H1"][kcol] == k).mean(), share_H2=(d[d.half == "H2"][kcol] == k).mean()))
    DS = pd.DataFrame(rows); DS.to_csv(f"{OUT}/q5_{sym}_hour_dist_by_dst.csv", index=False)
    print(f"\n=== Q5 {sym}: share of extremes by bar k, by DST (T = Tokyo open bar, C = China open bar) ===")
    for ext in ["high", "low"]:
        pv = DS[DS.ext == ext].pivot(index="is_dst", columns="k", values="share").round(3)
        print(ext); print(pv.to_string())
    # tests: P(ext at tokyo bar) vs the average of the two neighbouring bars (k-1, k+1), per DST; and winter k=1 vs summer k=1 (same ET hour, Tokyo open vs pre-open)
    rows = []
    for dst in [0, 1]:
        d = x[x.is_dst == dst]; tko = int(d.tokyo_open_k.iloc[0]); cno = int(d.china_open_k.iloc[0])
        for ext, kcol in [("high", "hi_k"), ("low", "lo_k")]:
            for name, kk in [("tokyo", tko), ("china", cno)]:
                at = (d[kcol] == kk); nb = d[kcol].isin([kk - 1, kk + 1]).mean() / 2
                r = rate_row(np.ones(len(d), bool), at.astype(int), nb, f"{ext} at {name} bar k={kk} vs mean of neighbours", d.half); r.update(sym=sym, is_dst=dst, ext=ext, open=name, k=kk); rows.append(r); ncomp += 1
    # same ET hour, different Tokyo status: bar k=1 (19:00 ET) is the Tokyo open in winter but pre-open in summer; k=2 (20:00) is Tokyo open in summer but Tokyo 10:00 in winter
    for ext, kcol in [("high", "hi_k"), ("low", "lo_k")]:
        for k in [1, 2, 3]:
            w = x[x.is_dst == 0]; s = x[x.is_dst == 1]
            rw = (w[kcol] == k).mean(); rs = (s[kcol] == k).mean()
            lo, hi = boot_ci_diff((w[kcol] == k).values.astype(float), (s[kcol] == k).values.astype(float))
            rows.append(dict(sym=sym, ext=ext, k=k, cond=f"{ext} share at k={k}: winter(EST) - summer(EDT)", n=len(w), n_summer=len(s), rate=rw, rate_summer=rs, lift=rw - rs, ci90_lo=lo, ci90_hi=hi,
                             rate_H1=(w[w.half == "H1"][kcol] == k).mean() - (s[s.half == "H1"][kcol] == k).mean(), rate_H2=(w[w.half == "H2"][kcol] == k).mean() - (s[s.half == "H2"][kcol] == k).mean())); ncomp += 1
    TK = pd.DataFrame(rows); TK.to_csv(f"{OUT}/q5_{sym}_tokyo_china_tests.csv", index=False)
    print(TK[["cond", "n", "base", "rate", "lift", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2"]].round(3).to_string())
    # JST-clock view: share of extremes by JST hour, pooled over DST (the Tokyo open is always 09:00 JST)
    rows = []
    for ext, col in [("high", "hi_hour_jst"), ("low", "lo_hour_jst")]:
        vc = x[col].value_counts(normalize=True).sort_index()
        for h, s_ in vc.items():
            rows.append(dict(sym=sym, ext=ext, hour_jst=h, share=s_, n=len(x), share_dst0=(x[x.is_dst == 0][col] == h).mean(), share_dst1=(x[x.is_dst == 1][col] == h).mean()))
    JS = pd.DataFrame(rows); JS.to_csv(f"{OUT}/q5_{sym}_jst_hour_dist.csv", index=False)
    print("JST-hour share (pooled; winter session covers JST 08..16, summer 07..15):"); print(JS.pivot(index="ext", columns="hour_jst", values="share").round(3).to_string())

# ======================= Q6: NQ vs ES =======================
xn, pn = load("NQ"); xe, pe = load("ES")
j = xn[["hi_k", "lo_k", "n_bars", "hi_bp", "lo_bp", "rng_bp", "is_dst", "half", "high_above_rth_high", "low_below_rth_low", "hi_first"]].join(xe[["hi_k", "lo_k", "n_bars", "hi_bp", "lo_bp", "rng_bp", "high_above_rth_high", "low_below_rth_low", "hi_first"]], rsuffix="_es", how="inner")
j = j[(j.n_bars == 9) & (j.n_bars_es == 9)]
print(f"\n=== Q6: NQ vs ES, joint sessions n={len(j)} ===")
rows = []
for ext in ["hi", "lo"]:
    same = (j[f"{ext}_k"] == j[f"{ext}_k_es"])
    d = (j[f"{ext}_k"] - j[f"{ext}_k_es"])
    # null for 'same bar' if independent: sum_k p_nq(k) p_es(k)
    pn_ = j[f"{ext}_k"].value_counts(normalize=True).reindex(range(9)).fillna(0); pe_ = j[f"{ext}_k_es"].value_counts(normalize=True).reindex(range(9)).fillna(0)
    null = float((pn_ * pe_).sum())
    r = rate_row(np.ones(len(j), bool), same.astype(int), null, f"{ext}: same bar NQ==ES (null if independent={null:.2f})", j.half); r.update(ext=ext, within1=(d.abs() <= 1).mean(), nq_earlier=(d < 0).mean(), es_earlier=(d > 0).mean(), mean_diff=d.mean()); rows.append(r); ncomp += 1
    # when different: who is earlier?  exact binomial vs 0.5
    dd = d[d != 0]
    rows.append(dict(cond=f"{ext}: NQ earlier | different bars", n=len(dd), rate=(dd < 0).mean(), base=0.5, p_binom=binom_p(int((dd < 0).sum()), len(dd), 0.5), ci90_lo=boot_ci((dd < 0).values.astype(float))[0], ci90_hi=boot_ci((dd < 0).values.astype(float))[1],
                     rate_H1=(dd[j.loc[dd.index, "half"] == "H1"] < 0).mean(), rate_H2=(dd[j.loc[dd.index, "half"] == "H2"] < 0).mean(), n_H1=int((j.loc[dd.index, "half"] == "H1").sum()), n_H2=int((j.loc[dd.index, "half"] == "H2").sum()), ext=ext)); ncomp += 1
    # agreement on the break flags
    f = "high_above_rth_high" if ext == "hi" else "low_below_rth_low"
    agree = (j[f] == j[f + "_es"]).mean()
    rows.append(dict(cond=f"{ext}: agreement on {f}", n=len(j), rate=agree, base=np.nan, ext=ext, nq_only=((j[f] == 1) & (j[f + "_es"] == 0)).mean(), es_only=((j[f] == 0) & (j[f + "_es"] == 1)).mean())); ncomp += 1
rows.append(dict(cond="hi_first agreement", n=len(j), rate=(j.hi_first == j.hi_first_es).mean(), base=np.nan))
# both same bar for both extremes
rows.append(dict(cond="both extremes same bars", n=len(j), rate=((j.hi_k == j.hi_k_es) & (j.lo_k == j.lo_k_es)).mean(), base=np.nan))
Q6 = pd.DataFrame(rows); Q6.to_csv(f"{OUT}/q6_nq_vs_es.csv", index=False)
print(Q6[["cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2", "within1", "nq_earlier", "es_earlier", "nq_only", "es_only"]].round(3).to_string())
# conditional on the NQ high being in at bar k, is the ES high in?  (panel join)
pj = pn[pn.n_bars == 9][["date", "k", "high_done", "low_done", "bars_since_hi", "bars_since_lo", "pos_in_range", "half"]].merge(pe[pe.n_bars == 9][["date", "k", "high_done", "low_done", "bars_since_hi", "bars_since_lo", "pos_in_range"]], on=["date", "k"], suffixes=("_nq", "_es"))
pj = pj[pj.k <= 7]
rows = []
for k in range(8):
    d = pj[pj.k == k]
    rows.append(dict(k=k, n=len(d), P_es_hi_done=d.high_done_es.mean(), P_es_hi_done_given_nq_done=d[d.high_done_nq == 1].high_done_es.mean(), P_es_hi_done_given_nq_not=d[d.high_done_nq == 0].high_done_es.mean(),
                     P_es_lo_done=d.low_done_es.mean(), P_es_lo_done_given_nq_done=d[d.low_done_nq == 1].low_done_es.mean(), P_es_lo_done_given_nq_not=d[d.low_done_nq == 0].low_done_es.mean(),
                     agree_hi=(d.high_done_nq == d.high_done_es).mean(), agree_lo=(d.low_done_nq == d.low_done_es).mean()))
PJ = pd.DataFrame(rows); PJ.to_csv(f"{OUT}/q6_panel_agreement.csv", index=False); print(PJ.round(3).to_string())

# ======================= 15-minute timing inside the hourly bars (2026-08-31 .. 2026-11-09) =======================
print("\n=== 15m timing: which 15-min slot inside the hourly extreme bar made the extreme (Aug 31 - Nov 9 2026) ===")
for sym in ["NQ", "ES"]:
    m = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv")
    m["ts"] = pd.to_datetime(m["Datetime"], utc=True).dt.tz_convert("America/New_York")
    m = m.set_index("ts").sort_index()
    m["hour"] = m.index.hour; m["minute"] = m.index.minute
    g = pd.Series(m.index.date, index=m.index); sh = m.index.hour >= 18
    g[sh] = (m.index[sh] + pd.Timedelta(days=1)).date
    m["gdate"] = g.values
    a = m[m.hour.isin(list(range(18, 24)) + [0, 1, 2])]
    x, _ = load(sym)
    rows = []
    for gd, grp in a.groupby("gdate"):
        if len(grp) < 30: continue
        hi_i = int(np.argmax(grp.High.values)); lo_i = int(np.argmin(grp.Low.values))
        th = grp.index[hi_i]; tl = grp.index[lo_i]
        kh = (th.hour - 18) % 24; kl = (tl.hour - 18) % 24
        rows.append(dict(sym=sym, gdate=gd, n15=len(grp), hi_k=kh, hi_min=th.minute, lo_k=kl, lo_min=tl.minute, hi_slot=hi_i, lo_slot=lo_i,
                         hi_is_first_print=int(hi_i == 0 and grp.High.iloc[0] == grp.Open.iloc[0]), lo_is_first_print=int(lo_i == 0 and grp.Low.iloc[0] == grp.Open.iloc[0]),
                         hi_is_last_slot=int(hi_i == len(grp) - 1), lo_is_last_slot=int(lo_i == len(grp) - 1)))
    M = pd.DataFrame(rows); M.to_csv(f"{OUT}/q6_{sym}_15m_timing.csv", index=False)
    print(f"{sym}: sessions with 15m data: {len(M)}")
    print("  high: bar-0 highs =", int((M.hi_k == 0).sum()), "; of those, minute slot of the high:", M[M.hi_k == 0].hi_min.value_counts().sort_index().to_dict(), "; high == 18:00 open print:", int(M[M.hi_k == 0].hi_is_first_print.sum()))
    print("  low : bar-0 lows  =", int((M.lo_k == 0).sum()), "; of those, minute slot of the low :", M[M.lo_k == 0].lo_min.value_counts().sort_index().to_dict(), "; low == 18:00 open print:", int(M[M.lo_k == 0].lo_is_first_print.sum()))
    print("  high: bar-8 highs =", int((M.hi_k == 8).sum()), "; minute slot:", M[M.hi_k == 8].hi_min.value_counts().sort_index().to_dict(), "; last 15m slot:", int(M[M.hi_k == 8].hi_is_last_slot.sum()))
    print("  low : bar-8 lows  =", int((M.lo_k == 8).sum()), "; minute slot:", M[M.lo_k == 8].lo_min.value_counts().sort_index().to_dict(), "; last 15m slot:", int(M[M.lo_k == 8].lo_is_last_slot.sum()))
    mid = M[(M.hi_k > 0) & (M.hi_k < 8)]; midl = M[(M.lo_k > 0) & (M.lo_k < 8)]
    print("  middle-bar highs: minute slot dist:", mid.hi_min.value_counts().sort_index().to_dict(), "; middle-bar lows:", midl.lo_min.value_counts().sort_index().to_dict())
    # all extremes: minute slot distribution (00/15/30/45) -> does the extreme sit at the hourly bar boundary?
    print("  all highs minute slot:", M.hi_min.value_counts().sort_index().to_dict(), " all lows:", M.lo_min.value_counts().sort_index().to_dict())
    ncomp += 4
print("\ncomparisons run in q4/q5/q6:", ncomp)
