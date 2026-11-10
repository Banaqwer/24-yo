"""The right null for 'where is the argmax of a path' is the arcsine law, not a uniform 1/36 per quarter.
(i) analytic arcsine bin probabilities for 36 quarters and 9 hours; (ii) binomial p of the window's q0/q35/edge counts vs it;
(iii) log-likelihood of the window histogram under the lens's 'two spikes + flat interior' model vs the arcsine null;
(iv) hourly population 9-bin shape vs arcsine (chi-square, per-bin ratio), by half; (v) P(open print is the extreme) for a
540-step walk; (vi) Tokyo-open-bar share by quarter in DST sessions vs the arcsine expectation."""
import numpy as np, pandas as pd
from scipy.stats import binomtest, chi2
from common import *

L = Log(f"{OUT}/arcsine_check_log.txt")


def arcsine_bins(m):
    e = np.arange(m + 1) / m
    F = 2 / np.pi * np.arcsin(np.sqrt(e))
    return np.diff(F)


p36 = arcsine_bins(36); p9 = arcsine_bins(9)
L(f"arcsine 36-bin probabilities (pct): q0 {p36[0]*100:.1f} q1 {p36[1]*100:.1f} q2 {p36[2]*100:.1f} q3 {p36[3]*100:.1f} ... q17 {p36[17]*100:.1f} ... q35 {p36[35]*100:.1f} ; edge pair {(p36[0]+p36[35])*100:.1f}")
L("arcsine 9-bin probabilities (pct): " + " ".join(f"{v*100:.1f}" for v in p9))
L("  (uniform null used by the lens: 2.8% per quarter, 5.6% for the edge pair; 11.1% per hour)")

for sym in ("NQ", "ES"):
    s, b = load_q15(sym)
    n = len(s)
    L(f"\n===== {sym} window n={n}")
    for side, col in (("high", "hi_q"), ("low", "lo_q")):
        q = s[col].values
        k0 = int((q == 0).sum()); k35 = int((q == 35).sum()); ke = k0 + k35
        L(f"  {side}: q0 {k0}/{n} p_vs_arcsine={binomtest(k0, n, p36[0]).pvalue:.3f} (p_vs_uniform={binomtest(k0, n, 1/36).pvalue:.4f}); q35 {k35}/{n} p={binomtest(k35, n, p36[35]).pvalue:.3f}; edge {ke}/{n} p={binomtest(ke, n, p36[0]+p36[35]).pvalue:.3f}; q1-q3+q32-q34 (next to the edges) {int(((q>=1)&(q<=3)).sum()+((q>=32)&(q<=34)).sum())} expected arcsine {n*(p36[1:4].sum()+p36[32:35].sum()):.1f} uniform {n*6/36:.1f}; mid q12-q23 {int(((q>=12)&(q<=23)).sum())} expected arcsine {n*p36[12:24].sum():.1f} uniform {n*12/36:.1f}")
        cnt = np.bincount(q, minlength=36)
        # lens model: edge probabilities fitted from the data, flat interior
        pe = np.full(36, (n - ke) / n / 34); pe[0] = k0 / n; pe[35] = k35 / n
        ll_lens = (cnt * np.log(np.where(pe > 0, pe, 1e-12))).sum(); ll_arc = (cnt * np.log(p36)).sum()
        L(f"     log-lik: lens 'two spikes + flat interior' (2 fitted params) {ll_lens:.1f} vs arcsine (0 params) {ll_arc:.1f} -> AIC difference (lens - arcsine) {2*2 - 2*(ll_lens-ll_arc):+.1f} (positive favours arcsine)")
        # chi-square of the full 36-bin histogram vs arcsine (coarsened to 9 hourly bins to keep expected counts >= 4)
        cnt9 = cnt.reshape(9, 4).sum(axis=1); e9 = n * p9
        st = ((cnt9 - e9) ** 2 / e9).sum()
        L(f"     hourly-coarsened counts {cnt9.tolist()} vs arcsine expected {np.round(e9,1).tolist()}: chi2={st:.1f} p={1-chi2.cdf(st, 8):.3f}")
    # M2 under the null: P(the 18:00 open print is the extreme) for a 540-step symmetric walk (discrete arcsine: P(argmax = 0) = C(2n,n)/4^n ~ 1/sqrt(pi n))
    L(f"  M2 null: P(open print is the session high) for a 540-step symmetric random walk ~ 1/sqrt(pi*540) = {1/np.sqrt(np.pi*540):.3f}; observed open==high {int(s.open_is_high.sum())}/{n}, open==low {int(s.open_is_low.sum())}/{n}")
    L(f"  M2 null: share of k=0 extremes that sit in q0 under arcsine = {p36[0]/p36[:4].sum():.2f}; of k=8 extremes in q35 = {p36[35]/p36[32:].sum():.2f}; observed k0-high-in-q0 {int(((s.hi_k15==0)&(s.hi_sub==0)).sum())}/{int((s.hi_k15==0).sum())}, k0-low-in-q0 {int(((s.lo_k15==0)&(s.lo_sub==0)).sum())}/{int((s.lo_k15==0).sum())}, k8-low-in-q35 {int(((s.lo_k15==8)&(s.lo_sub==3)).sum())}/{int((s.lo_k15==8).sum())}, k8-high-in-q35 {int(((s.hi_k15==8)&(s.hi_sub==3)).sum())}/{int((s.hi_k15==8).sum())}")

    # ---- hourly population vs the 9-bin arcsine ----
    x, p = load_pop(sym)
    L(f"\n===== {sym} hourly population n={len(x)} vs 9-bin arcsine")
    for side, col in (("high", "hi_k"), ("low", "lo_k")):
        for lab, d in (("ALL", x), ("H1", x[x.half == "H1"]), ("H2", x[x.half == "H2"]), ("EDT", x[x.is_dst == 1]), ("EST", x[x.is_dst == 0])):
            c = np.bincount(d[col], minlength=9); e = len(d) * p9
            st = ((c - e) ** 2 / e).sum()
            L(f"  {side} {lab:3s} n={len(d)} obs% {np.round(c/len(d)*100,1).tolist()} ratio obs/arcsine {np.round(c/e,2).tolist()} chi2={st:.1f} p={1-chi2.cdf(st,8):.4f}")
    # Sunday vs weekday for the k=0 low excess
    for lab, d in (("sunday", x[x.sunday_open == 1]), ("weekday", x[x.sunday_open == 0])):
        c = np.bincount(d.lo_k, minlength=9)
        L(f"  low {lab:7s} n={len(d)} k0 {c[0]/len(d):.3f} (arcsine .216) p={binomtest(int(c[0]), len(d), p9[0]).pvalue:.4f}; high k0 {(d.hi_k==0).mean():.3f} p={binomtest(int((d.hi_k==0).sum()), len(d), p9[0]).pvalue:.3f}")

    # ---- M10: Tokyo-open bar share by quarter, DST sessions only (tokyo_open_k=2), vs arcsine k=2 = 7.9% and uniform 11.1% ----
    L(f"\n===== {sym} Tokyo-open bar (k=2, EDT sessions) share of session highs/lows by quarter; arcsine expectation for k=2 = {p9[2]*100:.1f}%, uniform 11.1%")
    d = x[x.is_dst == 1]
    rows = []
    for q in sorted(d.quarter.unique()):
        dq = d[d.quarter == q]
        if len(dq) < 20: continue
        kh = int((dq.hi_k == 2).sum()); kl = int((dq.lo_k == 2).sum())
        rows.append(dict(quarter=q, n=len(dq), hi_k2=f"{kh}/{len(dq)}={kh/len(dq):.3f}", p_hi=round(binomtest(kh, len(dq), p9[2]).pvalue, 3), lo_k2=f"{kl}/{len(dq)}={kl/len(dq):.3f}", p_lo=round(binomtest(kl, len(dq), p9[2]).pvalue, 3),
                         hi_k3_china=f"{(dq.hi_k==3).mean():.3f}", lo_k3_china=f"{(dq.lo_k==3).mean():.3f}", hi_k1=f"{(dq.hi_k==1).mean():.3f}"))
    for lab, dq in (("H1", d[d.half == "H1"]), ("H2", d[d.half == "H2"]), ("ALL", d)):
        kh = int((dq.hi_k == 2).sum()); kl = int((dq.lo_k == 2).sum())
        rows.append(dict(quarter=lab, n=len(dq), hi_k2=f"{kh}/{len(dq)}={kh/len(dq):.3f}", p_hi=round(binomtest(kh, len(dq), p9[2]).pvalue, 4), lo_k2=f"{kl}/{len(dq)}={kl/len(dq):.3f}", p_lo=round(binomtest(kl, len(dq), p9[2]).pvalue, 4),
                         hi_k3_china=f"{(dq.hi_k==3).mean():.3f}", lo_k3_china=f"{(dq.lo_k==3).mean():.3f}", hi_k1=f"{(dq.hi_k==1).mean():.3f}"))
    t = pd.DataFrame(rows); L(t.to_string(index=False)); t.to_csv(f"{OUT}/{sym}_tokyo_bar_by_quarter.csv", index=False)
    w = x.loc["2026-08-31":"2026-11-06"]; w = w[w.is_dst == 1]
    L(f"  window EDT sessions n={len(w)}: hi_k2 {int((w.hi_k==2).sum())}/{len(w)}={(w.hi_k==2).mean():.3f}, lo_k2 {int((w.lo_k==2).sum())}/{len(w)}={(w.lo_k==2).mean():.3f}")
L.close()
