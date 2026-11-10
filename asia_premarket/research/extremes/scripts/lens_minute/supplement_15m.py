"""Supplementary checks for the 15m lens."""
import numpy as np, pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu
from sklearn.metrics import roc_auc_score

OUT = "research/extremes/scripts/lens_minute"
rng = np.random.default_rng(11)


def boot_ci(v, stat=np.mean, B=4000):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    idx = rng.integers(0, len(v), (B, len(v)))
    return tuple(np.round(np.percentile([stat(v[i]) for i in idx], [5, 95]), 3))


def auc_ci(y, x, B=2000):
    y = np.asarray(y); x = np.asarray(x, float); m = ~np.isnan(x); y, x = y[m], x[m]
    a = roc_auc_score(y, x); out = []
    for _ in range(B):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max(): continue
        out.append(roc_auc_score(y[i], x[i]))
    return round(a, 3), tuple(np.round(np.percentile(out, [5, 95]), 3))


def fp(v):
    v = np.asarray(v, float); return f"{int(v.sum())}/{len(v)}={v.mean():.2f} CI{boot_ci(v)}"


lines = []
P = lambda *a: (print(*a), lines.append(" ".join(str(x) for x in a)))

for sym in ("NQ", "ES"):
    s = pd.read_csv(f"{OUT}/{sym}_q15_sessions.csv", index_col=0, parse_dates=True); s = s[s.n_q == 36]
    b = pd.read_csv(f"{OUT}/{sym}_q15_bars.csv", parse_dates=["date"]); b = b[b.date.isin(s.index)].copy()
    P(f"\n===== {sym}")
    # (a) the 18:00 open print vs the first bar's high/low
    q0 = b[b.q == 0]
    oloc = (q0.open - q0.low) / (q0.high - q0.low)
    P(f"(a) bar-0 open location in its own range: median {oloc.median():.2f}; open==high {int((q0.open==q0.high).sum())}/{len(q0)}; open==low {int((q0.open==q0.low).sum())}/{len(q0)}; open within 1 tick of high {int(((q0.high-q0.open)<=0.25).sum())}; of low {int(((q0.open-q0.low)<=0.25).sum())}")
    # distance of the 18:00 open from the bar-0 extreme that became the session extreme, in bp
    h0 = s[s.hi_q == 0]; l0 = s[s.lo_q == 0]
    P(f"    sessions with the high in q0 (n={len(h0)}): high - open = {((h0.hi - h0.open_18)/h0.ref_close*1e4).round(1).tolist()} bp")
    P(f"    sessions with the low  in q0 (n={len(l0)}): open - low  = {((l0.open_18 - l0.lo)/l0.ref_close*1e4).round(1).tolist()} bp")
    # (b) scale-normalised stop-run thresholds
    for thr in (5, 10, 15, 20):
        hs = ((s.brk_hi_bp > 0) & (s.brk_hi_bp < thr) & (s.close_below_f15hi == 1))
        ls = ((s.brk_lo_bp > 0) & (s.brk_lo_bp < thr) & (s.close_above_f15lo == 1))
        hs2 = (s.brk_hi_bp > 0) & (s.brk_hi_bp < thr); ls2 = (s.brk_lo_bp > 0) & (s.brk_lo_bp < thr)
        P(f"(b) thr {thr}bp: f15-high broken by <thr: {int(hs2.sum())}/48, of which session CLOSE back below f15 high: {int(hs.sum())}; f15-low broken by <thr: {int(ls2.sum())}/48, close back above f15 low: {int(ls.sum())}")
    # break size relative to the first-15m range
    P(f"    median break of f15 high in units of f15 range: {(s.brk_hi_bp[s.brk_hi_bp>0]/s.f15_rng_bp[s.brk_hi_bp>0]).median():.2f}; low: {(s.brk_lo_bp[s.brk_lo_bp>0]/s.f15_rng_bp[s.brk_lo_bp>0]).median():.2f}")
    # (c) AUC of features for 'new running extreme bar holds as the session extreme'
    b["vol_tod"] = b.vol / b.groupby("q").vol.transform("median"); b["rng_tod"] = b.rng_bp / b.groupby("q").rng_bp.transform("median")
    b["close_loc"] = (b.close - b.low) / (b.high - b.low).replace(0, np.nan)
    b["next_ret"] = b.groupby("date").ret_bp.shift(-1)
    b["dq_from_edge"] = np.minimum(b.q, 35 - b.q)
    for side, flag, feats in [("high", "is_hi_bar", {"wick_hi": 1, "close_loc": -1, "ret_bp": -1, "vol_tod": 1, "rng_tod": 1, "vol_rel": 1, "rng_rel": 1, "q": 1, "dq_from_edge": -1, "run_hi_bp": 1}),
                              ("low", "is_lo_bar", {"wick_lo": 1, "close_loc": 1, "ret_bp": 1, "vol_tod": 1, "rng_tod": 1, "vol_rel": 1, "rng_rel": 1, "q": 1, "dq_from_edge": -1, "run_lo_bp": -1})]:
        new = b[b[f"q_since_{'hi' if side=='high' else 'lo'}"] == 0]
        inner = new[(new.q > 0) & (new.q < 35)]
        rows = []
        for f, sgn in feats.items():
            a_all = auc_ci(new[flag], sgn * new[f]); a_in = auc_ci(inner[flag], sgn * inner[f])
            rows.append(dict(side=side, feature=f, sign=sgn, n_new=len(new), n_hold=int(new[flag].sum()), auc_all=a_all[0], ci_all=a_all[1],
                             n_new_interior=len(inner), n_hold_interior=int(inner[flag].sum()), auc_interior=a_in[0], ci_interior=a_in[1]))
        t = pd.DataFrame(rows); t.to_csv(f"{OUT}/{sym}_newextreme_hold_auc_{side}.csv", index=False)
        P(f"(c) AUC for 'new running {side} bar is the session {side}' (hold rate all {new[flag].mean():.3f}, interior {inner[flag].mean():.3f}):\n" + t[["feature", "sign", "auc_all", "ci_all", "auc_interior", "ci_interior"]].to_string(index=False))
        # a simple rule: wick > 0.5 on a new-extreme bar
        w = "wick_hi" if side == "high" else "wick_lo"
        for thr in (0.4, 0.5, 0.6):
            r1 = new[new[w] > thr][flag]; r0 = new[new[w] <= thr][flag]
            P(f"    rule {w}>{thr}: P(hold)={r1.mean():.3f} (n={len(r1)}) vs {r0.mean():.3f} (n={len(r0)}); interior: {inner[inner[w]>thr][flag].mean():.3f} (n={int((inner[w]>thr).sum())}) vs {inner[inner[w]<=thr][flag].mean():.3f}")
        # close location rule
        cl = new.close_loc if side == "low" else 1 - new.close_loc
        r1 = new[cl > 0.5][flag]; r0 = new[cl <= 0.5][flag]
        P(f"    rule 'bar closes in the half away from the extreme': P(hold)={r1.mean():.3f} (n={len(r1)}) vs {r0.mean():.3f} (n={len(r0)}); Fisher p={fisher_exact([[r1.sum(), len(r1)-r1.sum()],[r0.sum(), len(r0)-r0.sum()]])[1]:.4f}")
    # (d) knowable at 19:00: sub-quarter of the bar-0 high/low -> P(session high in bar 0)
    b0 = b[b.q < 4]
    g = b0.groupby("date")
    sub_hi = g.apply(lambda d: int(d.high.values.argmax())); sub_lo = g.apply(lambda d: int(d.low.values.argmin()))
    s["bar0_hi_sub"] = sub_hi.reindex(s.index); s["bar0_lo_sub"] = sub_lo.reindex(s.index)
    s["bar0_ret_bp"] = g.apply(lambda d: (d.close.iloc[-1] / d.open.iloc[0] - 1) * 1e4).reindex(s.index)
    s["bar0_close_loc"] = g.apply(lambda d: (d.close.iloc[-1] - d.low.min()) / (d.high.max() - d.low.min())).reindex(s.index)
    rows = []
    for sub in range(4):
        m = s[s.bar0_hi_sub == sub]; ml = s[s.bar0_lo_sub == sub]
        rows.append(dict(sub=sub, n_hi=len(m), P_high_in_bar0=round(m.hi_k15.eq(0).mean(), 3) if len(m) else np.nan, n_lo=len(ml), P_low_in_bar0=round(ml.lo_k15.eq(0).mean(), 3) if len(ml) else np.nan))
    t = pd.DataFrame(rows); t.to_csv(f"{OUT}/{sym}_bar0_subquarter_vs_hold.csv", index=False)
    P("(d) at 19:00: sub-quarter in which the bar-0 high/low was set -> P(session extreme is in bar 0):\n" + t.to_string(index=False))
    first_q = s[s.bar0_hi_sub == 0]; later = s[s.bar0_hi_sub > 0]
    P(f"    high: bar-0 high set in 18:00-18:15 -> P(high in bar0)={fp(first_q.hi_k15.eq(0))} vs set later in the hour -> {fp(later.hi_k15.eq(0))}; Fisher p={fisher_exact([[first_q.hi_k15.eq(0).sum(), len(first_q)-first_q.hi_k15.eq(0).sum()],[later.hi_k15.eq(0).sum(), len(later)-later.hi_k15.eq(0).sum()]])[1]:.3f}")
    first_q = s[s.bar0_lo_sub == 0]; later = s[s.bar0_lo_sub > 0]
    P(f"    low : bar-0 low set in 18:00-18:15 -> P(low in bar0)={fp(first_q.lo_k15.eq(0))} vs later -> {fp(later.lo_k15.eq(0))}; Fisher p={fisher_exact([[first_q.lo_k15.eq(0).sum(), len(first_q)-first_q.lo_k15.eq(0).sum()],[later.lo_k15.eq(0).sum(), len(later)-later.lo_k15.eq(0).sum()]])[1]:.3f}")
    # combine: bar-0 extreme in q0 AND bar closes away from it
    m = s[(s.bar0_hi_sub == 0) & (s.bar0_close_loc < 0.5)]; P(f"    high set in q0 AND bar-0 closes in lower half: P(high in bar0)={fp(m.hi_k15.eq(0))}")
    m = s[(s.bar0_lo_sub == 0) & (s.bar0_close_loc > 0.5)]; P(f"    low set in q0 AND bar-0 closes in upper half: P(low in bar0)={fp(m.lo_k15.eq(0))}")
    # (e) Fisher for f15 direction conditioning
    up = s[s.f15_ret_bp > 0]; dn = s[s.f15_ret_bp < 0]
    P(f"(e) f15 bar down -> f15 high holds {fp(dn.f15_high_holds)} vs up {fp(up.f15_high_holds)}; Fisher p={fisher_exact([[dn.f15_high_holds.sum(), len(dn)-dn.f15_high_holds.sum()],[up.f15_high_holds.sum(), len(up)-up.f15_high_holds.sum()]])[1]:.3f}")
    P(f"    f15 bar up -> f15 low holds {fp(up.f15_low_holds)} vs down {fp(dn.f15_low_holds)}; Fisher p={fisher_exact([[up.f15_low_holds.sum(), len(up)-up.f15_low_holds.sum()],[dn.f15_low_holds.sum(), len(dn)-dn.f15_low_holds.sum()]])[1]:.3f}")
    P(f"    f15 bar down -> HOURLY bar-0 high holds {fp(dn.hi_k15.eq(0))} vs up {fp(up.hi_k15.eq(0))}; f15 up -> hourly bar-0 low holds {fp(up.lo_k15.eq(0))} vs down {fp(dn.lo_k15.eq(0))}")
    # (f) regime of the window
    P(f"(f) window regime: median close_bp {s.close_bp.median():.1f}; P(close<ref) {fp(s.close_bp<0)}; median rng {s.rng_bp.median():.1f}; median |rth_ret| {s.rth_ret_bp.abs().median():.1f}")
    vp = b.groupby("q").agg(vol_med=("vol", "median"), rng_med=("rng_bp", "median"), n=("vol", "size")).reset_index()
    vp["vol_share_pct"] = vp.vol_med / vp.vol_med.sum() * 100
    vp.to_csv(f"{OUT}/{sym}_quarter_volume_profile.csv", index=False)
    top = vp.sort_values("vol_med", ascending=False).head(6)
    P("    quarter volume profile top-6 (q, med vol, med rng bp): " + "; ".join(f"q{int(r.q)}({(18+int(r.q)//4)%24:02d}:{(int(r.q)%4)*15:02d}) {r.vol_med:.0f}/{r.rng_med:.1f}" for r in top.itertuples()))
    P(f"    q0 vol vs session-median: {(b[b.q==0].vol_rel).median():.2f}; q35: {(b[b.q==35].vol_rel).median():.2f}; q8 (20:00): {(b[b.q==8].vol_rel).median():.2f}; q14 (21:30): {(b[b.q==14].vol_rel).median():.2f}")
    # (g) sessions where the 15m extreme and the hourly k agree but the within-hour quarter is the hour's first quarter (xx:00) vs others
    P(f"(g) sub-quarter of the session high (all): {s.hi_sub.value_counts().sort_index().tolist()} ; low: {s.lo_sub.value_counts().sort_index().tolist()} (uniform expectation 12 each)")
    s.to_csv(f"{OUT}/{sym}_q15_sessions_aug.csv")

with open(f"{OUT}/supplement_log.txt", "w") as f:
    f.write("\n".join(lines))
