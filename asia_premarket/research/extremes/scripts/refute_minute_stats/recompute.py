"""Independent recomputation of the 'minute' lens claims M1..M10 from raw 15m bars + the 579-session hourly tables."""
import numpy as np, pandas as pd
from datetime import timedelta
from scipy.stats import binomtest, fisher_exact, mannwhitneyu, chisquare
from sklearn.metrics import roc_auc_score

ROOT = "."
OUT = "research/extremes/scripts/refute_minute_stats"
ET = "America/New_York"
rng = np.random.default_rng(123)
lines = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); lines.append(s)

def bci(v, stat=np.mean, B=5000):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    if len(v) == 0: return (np.nan, np.nan)
    idx = rng.integers(0, len(v), (B, len(v)))
    return tuple(np.round(np.percentile([stat(v[i]) for i in idx], [5, 95]), 3))

def fp(v):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    return f"{int(v.sum())}/{len(v)}={v.mean():.3f} CI90{bci(v)}"

def bp(k, n, p0, alt="two-sided"):
    return binomtest(int(k), int(n), p0, alternative=alt).pvalue

def cluster_auc(df, y, x, cl, B=2000):
    """AUC with a cluster (session) bootstrap."""
    a = roc_auc_score(df[y], df[x])
    groups = df[cl].unique(); g2i = {g: np.where(df[cl].values == g)[0] for g in groups}
    out = []
    yv = df[y].values; xv = df[x].values
    for _ in range(B):
        pick = rng.choice(groups, len(groups), replace=True)
        idx = np.concatenate([g2i[g] for g in pick])
        if yv[idx].min() == yv[idx].max(): continue
        out.append(roc_auc_score(yv[idx], xv[idx]))
    return round(a, 3), tuple(np.round(np.percentile(out, [5, 95]), 3))

def cluster_rate_ci(df, y, mask, cl, B=3000):
    groups = df[cl].unique(); g2i = {g: np.where(df[cl].values == g)[0] for g in groups}
    yv = df[y].values; mv = mask.values
    out = []
    for _ in range(B):
        pick = rng.choice(groups, len(groups), replace=True)
        idx = np.concatenate([g2i[g] for g in pick])
        m = mv[idx]
        if m.sum() == 0: continue
        out.append(yv[idx][m].mean())
    return tuple(np.round(np.percentile(out, [5, 95]), 3))

# ---------------------------------------------------------------- build 15m sessions
def load15(sym):
    d = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv", index_col=0)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(ET)
    d = d[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    return d[~d.index.duplicated(keep="last")].sort_index()

def build(sym):
    d = load15(sym)
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True)
    x["asia_gdate"] = pd.to_datetime(x["asia_gdate"])
    gd_to_date = {pd.Timestamp(g).date(): dt for dt, g in x["asia_gdate"].items()}
    h = d.copy()
    g = pd.Series(h.index.date, index=h.index)
    sh = h.index.hour >= 18
    g[sh] = (h.index[sh] + pd.Timedelta(days=1)).date
    h["gdate"] = g.values
    a = h[h.index.hour.isin(list(range(18, 24)) + [0, 1, 2])]
    S, B = [], []
    for gd, grp in a.groupby("gdate"):
        if gd not in gd_to_date: continue
        grp = grp.sort_index(); date = gd_to_date[gd]; xr = x.loc[date]
        q = ((grp.index.hour - 18) % 24) * 4 + grp.index.minute // 15
        grp = grp.assign(q=q.values)
        if len(grp) != 36: continue
        ref = float(xr["ref_close"]); dst = grp.index[0].dst() != timedelta(0)
        H = grp.High.values; L = grp.Low.values; O = grp.Open.values; C = grp.Close.values; V = grp.Volume.values
        hq = int(H.argmax()); lq = int(L.argmin()); hi = H[hq]; lo = L[lq]
        # ties?
        hties = int((H == hi).sum()); lties = int((L == lo).sum())
        tko = 8 if dst else 4; cno = 14 if dst else 10
        f15h, f15l = H[0], L[0]
        # knowable stop-run: the first bar that breaks the f15 high; break size at that bar's close (running high - f15h)
        brk_idx_h = next((i for i in range(1, 36) if H[i] > f15h), None)
        brk_idx_l = next((i for i in range(1, 36) if L[i] < f15l), None)
        first_brk_h_bp = (H[brk_idx_h] - f15h) / ref * 1e4 if brk_idx_h is not None else np.nan
        first_brk_l_bp = (f15l - L[brk_idx_l]) / ref * 1e4 if brk_idx_l is not None else np.nan
        final_brk_h_bp = (hi - f15h) / ref * 1e4; final_brk_l_bp = (f15l - lo) / ref * 1e4
        rec = dict(date=date, is_dst=int(dst), ref=ref, hi=hi, lo=lo, hi_q=hq, lo_q=lq, hi_k=hq // 4, lo_k=lq // 4,
                   hi_sub=hq % 4, lo_sub=lq % 4, hi_k_hourly=int(xr.hi_k), lo_k_hourly=int(xr.lo_k),
                   hi_match=int(abs(hi - xr.asia_high) < 1e-6), lo_match=int(abs(lo - xr.asia_low) < 1e-6),
                   hties=hties, lties=lties, tko=tko, cno=cno, open18=O[0], close=C[-1],
                   open_is_high=int(abs(hi - O[0]) < 1e-9), open_is_low=int(abs(lo - O[0]) < 1e-9),
                   f15_rng_bp=(f15h - f15l) / ref * 1e4, f15_ret_bp=(C[0] / O[0] - 1) * 1e4,
                   f15_high_holds=int(hq == 0), f15_low_holds=int(lq == 0),
                   final_brk_h_bp=final_brk_h_bp, final_brk_l_bp=final_brk_l_bp,
                   first_brk_h_bp=first_brk_h_bp, first_brk_l_bp=first_brk_l_bp, brk_idx_h=brk_idx_h, brk_idx_l=brk_idx_l,
                   close_below_f15h=int(C[-1] < f15h), close_above_f15l=int(C[-1] > f15l),
                   rng_bp=(hi - lo) / ref * 1e4, hi_bp=(hi / ref - 1) * 1e4, lo_bp=(lo / ref - 1) * 1e4,
                   hi_next_ret=(C[hq + 1] / O[hq + 1] - 1) * 1e4 if hq < 35 else np.nan,
                   lo_next_ret=(C[lq + 1] / O[lq + 1] - 1) * 1e4 if lq < 35 else np.nan,
                   hi_next_below_barlow=int(C[hq + 1] < L[hq]) if hq < 35 else np.nan,
                   lo_next_above_barhigh=int(C[lq + 1] > H[lq]) if lq < 35 else np.nan,
                   bar0_hi_sub=int(H[:4].argmax()), bar0_lo_sub=int(L[:4].argmin()),
                   bar0_close_loc=(C[3] - L[:4].min()) / (H[:4].max() - L[:4].min()),
                   vol_tko=V[tko], vol_q0=V[0], vol_q35=V[35], vol_med=np.median(V))
        S.append(rec)
        rh, rl = -np.inf, np.inf; qh = ql = 0
        medV = np.median(V)
        for i in range(36):
            newh = H[i] > rh; newl = L[i] < rl
            if newh: rh, qh = H[i], i
            if newl: rl, ql = L[i], i
            r = max(H[i] - L[i], 1e-9)
            B.append(dict(date=date, q=i, is_dst=int(dst), new_hi=int(newh), new_lo=int(newl), is_hi_bar=int(i == hq), is_lo_bar=int(i == lq),
                          close_loc=(C[i] - L[i]) / r, wick_hi=(H[i] - max(O[i], C[i])) / r, wick_lo=(min(O[i], C[i]) - L[i]) / r,
                          ret_bp=(C[i] / O[i] - 1) * 1e4, rng_bp=(H[i] - L[i]) / ref * 1e4, vol=V[i], vol_rel=V[i] / max(medV, 1),
                          next_ret=(C[i + 1] / O[i + 1] - 1) * 1e4 if i < 35 else np.nan,
                          high_done=int(rh >= hi - 1e-9), low_done=int(rl <= lo + 1e-9)))
    s = pd.DataFrame(S).set_index("date").sort_index(); b = pd.DataFrame(B)
    b["vol_tod"] = b.vol / b.groupby("q").vol.transform("median"); b["rng_tod"] = b.rng_bp / b.groupby("q").rng_bp.transform("median")
    return s, b

def halves(s):
    s = s.sort_index(); n = len(s); return s.iloc[: n // 2], s.iloc[n // 2:]

SS = {}
for sym in ("NQ", "ES"):
    s, b = build(sym); SS[sym] = (s, b)
    P(f"\n#### {sym}: {len(s)} sessions {s.index.min().date()}..{s.index.max().date()}, EDT={int(s.is_dst.sum())}; hi/lo level match hourly {s.hi_match.mean():.2f}/{s.lo_match.mean():.2f}; hi_k match {(s.hi_k==s.hi_k_hourly).mean():.2f} lo_k {(s.lo_k==s.lo_k_hourly).mean():.2f}; tied highs {int((s.hties>1).sum())} tied lows {int((s.lties>1).sum())}")
    s.to_csv(f"{OUT}/{sym}_sessions.csv"); b.to_csv(f"{OUT}/{sym}_bars.csv", index=False)

# ================================================================= M1
P("\n================= M1: quarter concentration")
for sym, (s, b) in SS.items():
    n = len(s)
    ch = s.hi_q.value_counts().reindex(range(36), fill_value=0); cl = s.lo_q.value_counts().reindex(range(36), fill_value=0)
    P(f"{sym} high counts by q: {ch.tolist()}")
    P(f"{sym} low  counts by q: {cl.tolist()}")
    for side, c in (("high", ch), ("low", cl)):
        edge = c[0] + c[35]
        P(f"  {side}: q0={c[0]} q35={c[35]} edge={edge}/{n}={edge/n:.3f} p_vs_uniform(2/36)={bp(edge, n, 2/36):.2e}")
        # last hour excluding q35, first hour excluding q0
        near = c[1] + c[2] + c[3] + c[32] + c[33] + c[34]
        lasthr_ex = c[32] + c[33] + c[34]; firsthr_ex = c[1] + c[2] + c[3]
        P(f"  {side}: near-edge q1-3 + q32-34 = {near}/{n} (uniform exp {n*6/36:.1f}) p={bp(near, n, 6/36):.3f}; q32-34 = {lasthr_ex} (exp {n*3/36:.1f}) p={bp(lasthr_ex, n, 3/36):.3f}; q1-3 = {firsthr_ex} p={bp(firsthr_ex, n, 3/36):.3f}")
        # interior test: chi-square over 34 interior quarters among interior extremes
        inter = c[1:35]; m = inter.sum()
        chi = chisquare(inter.values, f_exp=np.full(34, m / 34))
        P(f"  {side}: interior n={m}, expected per cell {m/34:.2f}; chi2 p={chi.pvalue:.3f} (expected count per cell ~1: test has ~no power)")
        # alternative: interior grouped into 4 hour-blocks of near-edge vs middle: q1-3,q32-34 vs q4-31
        k_near = near; k_mid = m - near
        p_near = bp(k_near, m, 6/34)
        P(f"  {side}: within interior, near-edge 6 quarters hold {k_near}/{m} (uniform exp {m*6/34:.1f}) p={p_near:.3f}")
        # whole-session hourly-level: share in hourly bars k=0 and k=8 vs q0+q35 alone
        kk = s.hi_k if side == "high" else s.lo_k
        P(f"  {side}: hourly k=0 share {int((kk==0).sum())}/{n}, k=8 share {int((kk==8).sum())}/{n}; of those, q0 share {c[0]}, q35 share {c[35]} -> {int((kk==0).sum())-c[0]} first-hour extremes are NOT in q0, {int((kk==8).sum())-c[35]} last-hour extremes NOT in q35")
    a, bb = halves(s)
    P(f"  halves: hi_q0 {int((a.hi_q==0).sum())}/{len(a)} vs {int((bb.hi_q==0).sum())}/{len(bb)} Fisher p={fisher_exact([[int((a.hi_q==0).sum()), len(a)-int((a.hi_q==0).sum())],[int((bb.hi_q==0).sum()), len(bb)-int((bb.hi_q==0).sum())]])[1]:.3f}; lo_q0 {int((a.lo_q==0).sum())} vs {int((bb.lo_q==0).sum())}; hi_q35 {int((a.hi_q==35).sum())} vs {int((bb.hi_q==35).sum())}; lo_q35 {int((a.lo_q==35).sum())} vs {int((bb.lo_q==35).sum())}")
    P(f"  halves edge share: high {int(((a.hi_q==0)|(a.hi_q==35)).sum())}/{len(a)} vs {int(((bb.hi_q==0)|(bb.hi_q==35)).sum())}/{len(bb)}; low {int(((a.lo_q==0)|(a.lo_q==35)).sum())} vs {int(((bb.lo_q==0)|(bb.lo_q==35)).sum())}")
# power of the interior chi-square: simulate a 2x excess in 6 near-edge quarters
m = 37; sims = []
for _ in range(2000):
    p = np.full(34, 1.0); p[[0, 1, 2, 31, 32, 33]] = 2.0; p /= p.sum()
    cnt = rng.multinomial(m, p); sims.append(chisquare(cnt, f_exp=np.full(34, m / 34)).pvalue < 0.05)
P(f"  power of 34-cell chi-square (n=37) to detect a 2x excess in 6 near-edge quarters at alpha=.05: {np.mean(sims):.2f}")

# ================================================================= M2
P("\n================= M2: sub-quarter of first/last-bar extremes; open print")
for sym, (s, b) in SS.items():
    fh = s[s.hi_k == 0]; fl = s[s.lo_k == 0]; lh = s[s.hi_k == 8]; ll = s[s.lo_k == 8]
    P(f"{sym} k=0 highs n={len(fh)}: sub counts {fh.hi_sub.value_counts().reindex(range(4), fill_value=0).tolist()}; q0 share {fp(fh.hi_sub==0)} binom p vs .25 = {bp((fh.hi_sub==0).sum(), len(fh), .25, 'greater'):.3f}")
    P(f"{sym} k=0 lows  n={len(fl)}: sub counts {fl.lo_sub.value_counts().reindex(range(4), fill_value=0).tolist()}; q0 share {fp(fl.lo_sub==0)} p={bp((fl.lo_sub==0).sum(), len(fl), .25, 'greater'):.3f}")
    P(f"{sym} k=8 highs n={len(lh)}: sub counts {lh.hi_sub.value_counts().reindex(range(4), fill_value=0).tolist()}; last-q share {fp(lh.hi_sub==3)} p={bp((lh.hi_sub==3).sum(), len(lh), .25, 'greater'):.3f}")
    P(f"{sym} k=8 lows  n={len(ll)}: sub counts {ll.lo_sub.value_counts().reindex(range(4), fill_value=0).tolist()}; last-q share {fp(ll.lo_sub==3)} p={bp((ll.lo_sub==3).sum(), len(ll), .25, 'greater'):.3f}")
    P(f"{sym} open print == session high {int(s.open_is_high.sum())}/{len(s)}, == session low {int(s.open_is_low.sum())}/{len(s)}; rule-of-three 95% upper bound for 0/48 = {3/48:.3f}")
    P(f"{sym} open18 vs q0 bar: open==bar0 high {int((b[b.q==0].set_index('date').wick_hi.index.size>0))}")
    h0 = s[s.hi_q == 0]; l0 = s[s.lo_q == 0]
    P(f"   q0-high sessions: high-open bp {((h0.hi-h0.open18)/h0.ref*1e4).round(1).tolist()}; q0-low sessions: open-low bp {((l0.open18-l0.lo)/l0.ref*1e4).round(1).tolist()}")
    # pooled sub-quarter distribution of ALL highs/lows (interior)
    P(f"   all-session sub-quarter counts high {s.hi_sub.value_counts().reindex(range(4), fill_value=0).tolist()} low {s.lo_sub.value_counts().reindex(range(4), fill_value=0).tolist()} (exp 12)")
    a, bb = halves(s)
    for nm, part in (("A", a), ("B", bb)):
        fh = part[part.hi_k == 0]; fl = part[part.lo_k == 0]; ll = part[part.lo_k == 8]
        P(f"   half {nm}: k=0 high in q0 {int((fh.hi_sub==0).sum())}/{len(fh)}; k=0 low in q0 {int((fl.lo_sub==0).sum())}/{len(fl)}; k=8 low in last q {int((ll.lo_sub==3).sum())}/{len(ll)}")

# ================================================================= M3
P("\n================= M3: f15 hold, overshoot, stop-run (ex post vs knowable)")
for sym, (s, b) in SS.items():
    n = len(s)
    P(f"{sym} f15 high holds {fp(s.f15_high_holds)}; low holds {fp(s.f15_low_holds)}; either {fp((s.f15_high_holds==1)|(s.f15_low_holds==1))}; both {int(((s.f15_high_holds==1)&(s.f15_low_holds==1)).sum())}")
    bh = s[s.final_brk_h_bp > 0]; bl = s[s.final_brk_l_bp > 0]
    P(f"   broken high n={len(bh)}: median final break {bh.final_brk_h_bp.median():.1f} bp IQR [{bh.final_brk_h_bp.quantile(.25):.1f},{bh.final_brk_h_bp.quantile(.75):.1f}]; f15 range median {s.f15_rng_bp.median():.1f}; median ratio break/f15rng {(bh.final_brk_h_bp/bh.f15_rng_bp).median():.2f} CI{bci(bh.final_brk_h_bp/bh.f15_rng_bp, np.median)}")
    P(f"   broken low n={len(bl)}: median final break {bl.final_brk_l_bp.median():.1f}; ratio {(bl.final_brk_l_bp/bl.f15_rng_bp).median():.2f} CI{bci(bl.final_brk_l_bp/bl.f15_rng_bp, np.median)}")
    for thr in (5, 10):
        sm_h = bh[bh.final_brk_h_bp < thr]; sm_l = bl[bl.final_brk_l_bp < thr]
        P(f"   EX POST final break < {thr} bp: high {len(sm_h)}/{n}, close back below f15 high {int(sm_h.close_below_f15h.sum())}/{len(sm_h)}; low {len(sm_l)}/{n}, close back above f15 low {int(sm_l.close_above_f15l.sum())}/{len(sm_l)}; base rate close-back among all broken: high {bh.close_below_f15h.mean():.2f} low {bl.close_above_f15l.mean():.2f}")
        # mechanical check: for the close to stay above f15h when the session high < f15h+thr, the close must be within thr bp of the session high
        P(f"      mechanical: among ALL broken-high sessions, P(close within {thr} bp of the session high) = {((bh.hi-bh.close)/bh.ref*1e4 < thr).mean():.2f} -> 'close back inside' is near-automatic for a <{thr} bp final break")
        # KNOWABLE version: at the first breaking bar, break < thr bp. Then: does the session high end within thr bp of f15h (i.e. the small break was the whole break)?
        kb_h = bh[bh.first_brk_h_bp < thr]; kb_l = bl[bl.first_brk_l_bp < thr]
        P(f"   KNOWABLE first break < {thr} bp: high n={len(kb_h)}/{len(bh)}: session high stays < f15h+{thr} in {int((kb_h.final_brk_h_bp<thr).sum())}/{len(kb_h)}; that first breaking bar is the session high in {int((kb_h.brk_idx_h==kb_h.hi_q).sum())}/{len(kb_h)}; median final break {kb_h.final_brk_h_bp.median():.1f} bp")
        P(f"                               low  n={len(kb_l)}/{len(bl)}: session low stays within {thr} in {int((kb_l.final_brk_l_bp<thr).sum())}/{len(kb_l)}; first breaking bar is the session low in {int((kb_l.brk_idx_l==kb_l.lo_q).sum())}/{len(kb_l)}; median final break {kb_l.final_brk_l_bp.median():.1f}")
    # base rate: P(a new-running-high bar is the session high) ~ 15%; compare with the first-break bar being the session high
    a, bb = halves(s)
    P(f"   halves: high holds {int(a.f15_high_holds.sum())}/{len(a)} vs {int(bb.f15_high_holds.sum())}/{len(bb)}; low holds {int(a.f15_low_holds.sum())} vs {int(bb.f15_low_holds.sum())}; ex-post <10bp high {int(((a.final_brk_h_bp>0)&(a.final_brk_h_bp<10)).sum())} vs {int(((bb.final_brk_h_bp>0)&(bb.final_brk_h_bp<10)).sum())}")

# ================================================================= M4
P("\n================= M4: new-running-extreme bar features (cluster bootstrap by session)")
for sym, (s, b) in SS.items():
    for side, flag, newf, feats in (("high", "is_hi_bar", "new_hi", {"close_loc": -1, "wick_hi": 1, "ret_bp": -1, "vol_tod": 1, "rng_tod": 1, "vol_rel": 1, "q": 1}),
                                     ("low", "is_lo_bar", "new_lo", {"close_loc": 1, "wick_lo": 1, "ret_bp": 1, "vol_tod": 1, "rng_tod": 1, "vol_rel": 1, "q": 1})):
        new = b[b[newf] == 1].copy()
        P(f"{sym} new {side} bars n={len(new)}, hold={int(new[flag].sum())} ({new[flag].mean():.3f})")
        for f, sg in feats.items():
            new["_x"] = sg * new[f]
            a, ci = cluster_auc(new, flag, "_x", "date")
            P(f"   AUC {f:9s} {a:.3f} cluster-CI90 {ci}")
        cl = (1 - new.close_loc) if side == "high" else new.close_loc
        away = cl > 0.5
        r1 = new[away][flag]; r0 = new[~away][flag]
        fisher = fisher_exact([[r1.sum(), len(r1) - r1.sum()], [r0.sum(), len(r0) - r0.sum()]])[1]
        P(f"   close-away rule: P(hold)={r1.mean():.3f} (n={len(r1)}) cluster-CI {cluster_rate_ci(new, flag, away, 'date')} vs {r0.mean():.3f} (n={len(r0)}) CI {cluster_rate_ci(new, flag, ~away, 'date')}; Fisher p={fisher:.4f}; lift {r1.mean()/r0.mean():.2f}x")
        # halves by session
        dates = sorted(new.date.unique()); hA = set(dates[: len(dates) // 2])
        for nm, part in (("A", new[new.date.isin(hA)]), ("B", new[~new.date.isin(hA)])):
            cl2 = (1 - part.close_loc) if side == "high" else part.close_loc; aw = cl2 > 0.5
            P(f"      half {nm}: close-away P(hold) {int(part[aw][flag].sum())}/{int(aw.sum())}={part[aw][flag].mean():.3f} vs {int(part[~aw][flag].sum())}/{int((~aw).sum())}={part[~aw][flag].mean():.3f}; AUC close_loc {roc_auc_score(part[flag], (-(part.close_loc) if side=='high' else part.close_loc)):.3f}; AUC q {roc_auc_score(part[flag], part.q):.3f}")
        # interior only
        inner = new[(new.q > 0) & (new.q < 35)].copy(); inner["_x"] = (-(inner.close_loc) if side == "high" else inner.close_loc)
        P(f"   interior-only AUC close_loc {cluster_auc(inner, flag, '_x', 'date')}; interior AUC q {cluster_auc(inner.assign(_q=inner.q), flag, '_q', 'date')}")

# population hourly analogue: at the close of a bar that set a new running high, does bar_close_loc predict high_done?
P("\n--- M4 population analogue (hourly panel, 579 sessions): new-running-extreme hourly bars, bar_close_loc -> P(extreme already in)")
for sym in ("NQ", "ES"):
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    p = p[p.n_bars == 9]
    for side, since, done, sg in (("high", "bars_since_hi", "high_done", -1), ("low", "bars_since_lo", "low_done", 1)):
        new = p[(p[since] == 0) & (p.k < 8)].copy()   # exclude k=8 where done is trivially 1
        new["_x"] = sg * new.bar_close_loc
        cl = (1 - new.bar_close_loc) if side == "high" else new.bar_close_loc; away = cl > 0.5
        r1 = new[away][done]; r0 = new[~away][done]
        a, ci = cluster_auc(new, done, "_x", "date")
        P(f"{sym} {side}: n new bars (k<8) {len(new)}, hold rate {new[done].mean():.3f}; close-away P(hold) {r1.mean():.3f} (n={len(r1)}) vs {r0.mean():.3f} (n={len(r0)}) Fisher p={fisher_exact([[r1.sum(), len(r1)-r1.sum()],[r0.sum(), len(r0)-r0.sum()]])[1]:.1e}; AUC close_loc {a} CI{ci}; AUC k {cluster_auc(new.assign(_k=new.k), done, '_k', 'date')}; AUC bar_vol_rel {cluster_auc(new.dropna(subset=['bar_vol_rel']).assign(_v=lambda d: d.bar_vol_rel), done, '_v', 'date')}")
        for nm, part in (("pre-2025-09-01", new[new.date < "2025-09-01"]), ("post", new[new.date >= "2025-09-01"])):
            cl2 = (1 - part.bar_close_loc) if side == "high" else part.bar_close_loc; aw = cl2 > 0.5
            P(f"      {nm}: close-away {part[aw][done].mean():.3f} (n={int(aw.sum())}) vs {part[~aw][done].mean():.3f} (n={int((~aw).sum())}); AUC {roc_auc_score(part[done], sg*part.bar_close_loc):.3f}")
        # per k
        P("      by k: " + "; ".join(f"k{k}: away {new[(new.k==k)&away][done].mean():.2f}(n={int(((new.k==k)&away).sum())}) vs {new[(new.k==k)&~away][done].mean():.2f}(n={int(((new.k==k)&~away).sum())})" for k in range(8)))

# ================================================================= M5
P("\n================= M5: bar after the extreme")
for sym, (s, b) in SS.items():
    P(f"{sym} bar after HIGH down: {fp(s.hi_next_ret<0)} median {s.hi_next_ret.median():.1f} CI{bci(s.hi_next_ret, np.median)}; after LOW up: {fp(s.lo_next_ret>0)} median {s.lo_next_ret.median():.1f}")
    for side, flag, newf, sg in (("high", "is_hi_bar", "new_hi", -1), ("low", "is_lo_bar", "new_lo", 1)):
        new = b[(b[newf] == 1) & b.next_ret.notna()].copy()
        rev = sg * new.next_ret > 0
        hold = new[flag] == 1
        P(f"   {side}: P(next bar reverses | hold) {rev[hold].mean():.3f} (n={hold.sum()}) vs | fail {rev[~hold].mean():.3f} (n={(~hold).sum()}) Fisher p={fisher_exact([[rev[hold].sum(), hold.sum()-rev[hold].sum()],[rev[~hold].sum(), (~hold).sum()-rev[~hold].sum()]])[1]:.4f}")
        P(f"   {side}: KNOWABLE inversion: P(hold | next bar reverses) {new[rev][flag].mean():.3f} (n={rev.sum()}) cluster-CI {cluster_rate_ci(new, flag, rev, 'date')} vs P(hold | next bar continues) {new[~rev][flag].mean():.3f} (n={(~rev).sum()}) CI {cluster_rate_ci(new, flag, ~rev, 'date')}; base {new[flag].mean():.3f}")
        # but: 'next bar continues' often means the next bar made a NEW running high -> trivially not hold. Condition on next bar NOT being a new extreme:
        nxt_new = b.groupby("date")[newf].shift(-1).reindex(new.index)
        nn = new[nxt_new == 0]; rev2 = sg * nn.next_ret > 0
        P(f"   {side}: among new-{side} bars whose NEXT bar did not set a further extreme (n={len(nn)}): P(hold | next reverses) {nn[rev2][flag].mean():.3f} (n={rev2.sum()}) vs P(hold | next continues but no new extreme) {nn[~rev2][flag].mean():.3f} (n={(~rev2).sum()})")
    a, bb = halves(s)
    P(f"   halves after-high down: {int((a.hi_next_ret<0).sum())}/{a.hi_next_ret.notna().sum()} vs {int((bb.hi_next_ret<0).sum())}/{bb.hi_next_ret.notna().sum()}; after-low up: {int((a.lo_next_ret>0).sum())}/{a.lo_next_ret.notna().sum()} vs {int((bb.lo_next_ret>0).sum())}/{bb.lo_next_ret.notna().sum()}")
P("\n--- M5 population analogue (hourly): bars with bars_since_hi==1 (running high set last bar): P(high_done | this bar down) vs up")
for sym in ("NQ", "ES"):
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"]); p = p[p.n_bars == 9]
    for side, since, done, sg in (("high", "bars_since_hi", "high_done", -1), ("low", "bars_since_lo", "low_done", 1)):
        x = p[(p[since] == 1) & (p.k < 8)]
        rev = sg * x.bar_ret_bp > 0
        P(f"{sym} {side}: n={len(x)}; P(done | bar reverses) {x[rev][done].mean():.3f} (n={rev.sum()}) vs P(done | bar continues) {x[~rev][done].mean():.3f} (n={(~rev).sum()}); Fisher p={fisher_exact([[x[rev][done].sum(), rev.sum()-x[rev][done].sum()],[x[~rev][done].sum(), (~rev).sum()-x[~rev][done].sum()]])[1]:.1e}; base {x[done].mean():.3f}")
        for nm, part in (("pre", x[x.date < "2025-09-01"]), ("post", x[x.date >= "2025-09-01"])):
            r = sg * part.bar_ret_bp > 0
            P(f"      {nm}: {part[r][done].mean():.3f} (n={r.sum()}) vs {part[~r][done].mean():.3f} (n={(~r).sum()})")

# ================================================================= M6
P("\n================= M6: time between high and low")
for sym, (s, b) in SS.items():
    dq = (s.hi_q - s.lo_q).abs() * 15
    P(f"{sym} |dt| median {dq.median():.0f} CI{bci(dq, np.median)}; deciles {np.percentile(dq,[10,25,50,75,90]).round(0).tolist()}; P(<=60) {fp(dq<=60)}; P(<=120) {fp(dq<=120)}; P(>=360) {fp(dq>=360)}; same q {int((s.hi_q==s.lo_q).sum())}")
    edge = s[(s.hi_q == 0) | (s.lo_q == 0) | (s.hi_q == 35) | (s.lo_q == 35)]; inner = s.drop(edge.index)
    P(f"   edge sessions {len(edge)} |dt| med {((edge.hi_q-edge.lo_q).abs()*15).median():.0f}; interior {len(inner)} med {((inner.hi_q-inner.lo_q).abs()*15).median():.0f}; MWU p={mannwhitneyu((edge.hi_q-edge.lo_q).abs(), (inner.hi_q-inner.lo_q).abs()).pvalue:.3f}")
    # mechanical expectation: if one extreme is at q0 or q35, the other is uniformly anywhere -> E|dt| larger. Simulate independent uniform placement.
    sim_e, sim_i = [], []
    for _ in range(20000):
        h, l = rng.integers(0, 36, 2)
        if h == l: continue
        (sim_e if (h in (0, 35) or l in (0, 35)) else sim_i).append(abs(h - l) * 15)
    P(f"   under independent uniform placement: median |dt| edge {np.median(sim_e):.0f} vs interior {np.median(sim_i):.0f}; overall P(|dt|<=60) = {np.mean(np.array(sim_e+sim_i)<=60):.3f}")
P("--- M6 population (hourly, 579 NQ / ES sessions): |hi_k - lo_k|")
for sym in ("NQ", "ES"):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True); x = x[x.n_bars == 9]
    d = (x.hi_k - x.lo_k).abs()
    P(f"{sym} n={len(x)}: same hourly bar {fp(d==0)}; |dk|<=1 {fp(d<=1)}; median |dk| {d.median():.0f} h; mean {d.mean():.2f}; P(|dk|>=6) {fp(d>=6)}; expected 0/48 given pop same-bar rate: P(0 of 48)={(1-(d==0).mean())**48:.2f}")
    for nm, part in (("pre", x[x.index < "2025-09-01"]), ("post", x[x.index >= "2025-09-01"])):
        dd = (part.hi_k - part.lo_k).abs(); P(f"   {nm}: same bar {int((dd==0).sum())}/{len(dd)}={(dd==0).mean():.3f}; |dk|<=1 {(dd<=1).mean():.3f}")
    w = x.loc[x.index >= "2026-08-31"]; dw = (w.hi_k - w.lo_k).abs()
    P(f"   window (hourly): same bar {int((dw==0).sum())}/{len(dw)}; |dk|<=1 {int((dw<=1).sum())}/{len(dw)}")

# ================================================================= M7
P("\n================= M7: NQ vs ES agreement")
nq, es = SS["NQ"][0], SS["ES"][0]
j = nq.join(es, lsuffix="_nq", rsuffix="_es", how="inner")
P(f"n={len(j)}")
for side in ("hi", "lo"):
    dq = (j[f"{side}_q_nq"] - j[f"{side}_q_es"]).abs()
    P(f"  {side}: same q {fp(dq==0)}; within 1q {fp(dq<=1)}; within 4q {fp(dq<=4)}; same hourly k {fp(j[f'{side}_k_nq']==j[f'{side}_k_es'])}")
    # chance under independence (product of marginals)
    pn = j[f"{side}_q_nq"].value_counts(normalize=True); pe = j[f"{side}_q_es"].value_counts(normalize=True)
    P(f"     chance same-q under independence {sum(pn.get(q,0)*pe.get(q,0) for q in range(36)):.3f}")
    a, bb = halves(j)
    ka = int(((a[f"{side}_q_nq"] - a[f"{side}_q_es"]).abs() == 0).sum()); kb = int(((bb[f"{side}_q_nq"] - bb[f"{side}_q_es"]).abs() == 0).sum())
    P(f"     halves same-q {ka}/{len(a)} vs {kb}/{len(bb)} Fisher p={fisher_exact([[ka, len(a)-ka],[kb, len(bb)-kb]])[1]:.3f}")
P(f"  hi_first agree {fp(j.hi_first_nq==j.hi_first_es)}" if "hi_first_nq" in j else f"  hi_first agree {fp((j.hi_q_nq<j.lo_q_nq)==(j.hi_q_es<j.lo_q_es))}")

# ================================================================= M8
P("\n================= M8: window vs the REST of the population (complement, not the pooled population)")
x = pd.read_csv(f"{ROOT}/research/extremes/NQ_extremes.csv", index_col=0, parse_dates=True)
w = x.loc[x.index >= "2026-08-31"]; rest = x.loc[x.index < "2026-08-31"]
P(f"window n={len(w)} rest n={len(rest)}")
tests = []
for nm, col in (("high k=0", w.hi_k == 0), ("high k=8", w.hi_k == 8), ("low k=0", w.lo_k == 0), ("low k=8", w.lo_k == 8), ("high by tko", w.high_by_tokyo_open == 1), ("low by tko", w.low_by_tokyo_open == 1), ("hi_first", w.hi_first == 1), ("high>rth high", w.high_above_rth_high == 1), ("low<rth low", w.low_below_rth_low == 1)):
    rc = {"high k=0": rest.hi_k == 0, "high k=8": rest.hi_k == 8, "low k=0": rest.lo_k == 0, "low k=8": rest.lo_k == 8, "high by tko": rest.high_by_tokyo_open == 1, "low by tko": rest.low_by_tokyo_open == 1, "hi_first": rest.hi_first == 1, "high>rth high": rest.high_above_rth_high == 1, "low<rth low": rest.low_below_rth_low == 1}[nm]
    k = int(col.sum()); p0 = rc.mean(); pv = bp(k, len(w), p0)
    fe = fisher_exact([[k, len(w) - k], [int(rc.sum()), len(rest) - int(rc.sum())]])[1]
    tests.append(pv)
    P(f"  {nm:14s}: window {k}/{len(w)}={k/len(w):.3f} rest {p0:.3f}; binom p={pv:.3f}; Fisher p={fe:.3f}")
P(f"  range: window median {w.rng_bp.median():.1f} CI{bci(w.rng_bp, np.median)} vs rest {rest.rng_bp.median():.1f}; MWU p={mannwhitneyu(w.rng_bp, rest.rng_bp).pvalue:.2e}; vs rest-2026 {rest.loc[rest.index>='2026-01-01'].rng_bp.median():.1f} MWU p={mannwhitneyu(w.rng_bp, rest.loc[rest.index>='2026-01-01'].rng_bp).pvalue:.3f}")
P(f"  Bonferroni over 11 tests: min p*11 = {min(tests)*11:.3f}")
# second half of population as the comparison (regime-adjacent)
post = rest.loc[rest.index >= "2025-09-01"]
P(f"  vs post-2025-09-01 rest (n={len(post)}): low k=8 {(post.lo_k==8).mean():.3f}; low by tko {post.low_by_tokyo_open.mean():.3f}; high k=8 {(post.hi_k==8).mean():.3f}; hi_first {post.hi_first.mean():.3f}; range med {post.rng_bp.median():.1f}")

# ================================================================= M9
P("\n================= M9: bar-0 sub-quarter (19:00) -> P(session extreme in bar 0)")
for sym, (s, b) in SS.items():
    fq = s[s.bar0_hi_sub == 0]; lt = s[s.bar0_hi_sub > 0]
    P(f"{sym} high: set in q0 -> {fp(fq.hi_k==0)} vs later {fp(lt.hi_k==0)}; Fisher p={fisher_exact([[int((fq.hi_k==0).sum()), len(fq)-int((fq.hi_k==0).sum())],[int((lt.hi_k==0).sum()), len(lt)-int((lt.hi_k==0).sum())]])[1]:.3f}; base {(s.hi_k==0).mean():.3f}")
    fq = s[s.bar0_lo_sub == 0]; lt = s[s.bar0_lo_sub > 0]
    P(f"{sym} low : set in q0 -> {fp(fq.lo_k==0)} vs later {fp(lt.lo_k==0)}; Fisher p={fisher_exact([[int((fq.lo_k==0).sum()), len(fq)-int((fq.lo_k==0).sum())],[int((lt.lo_k==0).sum()), len(lt)-int((lt.lo_k==0).sum())]])[1]:.3f}; base {(s.lo_k==0).mean():.3f}")
    # close location of bar 0 alone (available in the hourly panel for all 579 sessions)
    lo_half = s[s.bar0_close_loc < 0.5]; up_half = s[s.bar0_close_loc >= 0.5]
    P(f"{sym} bar-0 close in lower half -> P(high in bar0) {fp(lo_half.hi_k==0)} vs upper half {fp(up_half.hi_k==0)}; bar-0 close upper half -> P(low in bar0) {fp(up_half.lo_k==0)} vs lower {fp(lo_half.lo_k==0)}")
    a, bb = halves(s)
    for nm, part in (("A", a), ("B", bb)):
        fq = part[part.bar0_hi_sub == 0]; lt = part[part.bar0_hi_sub > 0]; fql = part[part.bar0_lo_sub == 0]; ltl = part[part.bar0_lo_sub > 0]
        P(f"   half {nm}: high q0 {int((fq.hi_k==0).sum())}/{len(fq)} vs later {int((lt.hi_k==0).sum())}/{len(lt)}; low q0 {int((fql.lo_k==0).sum())}/{len(fql)} vs later {int((ltl.lo_k==0).sum())}/{len(ltl)}")
P("--- M9 population analogue (hourly panel k=0, 579 sessions): bar-0 close location -> P(high_done at k=0)")
for sym in ("NQ", "ES"):
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"]); p = p[(p.n_bars == 9) & (p.k == 0)]
    lo_half = p[p.bar_close_loc < 0.5]; up_half = p[p.bar_close_loc >= 0.5]
    P(f"{sym}: n={len(p)}; P(high_done|k=0) base {p.high_done.mean():.3f}; close lower half {lo_half.high_done.mean():.3f} (n={len(lo_half)}) vs upper {up_half.high_done.mean():.3f} (n={len(up_half)}) Fisher p={fisher_exact([[lo_half.high_done.sum(), len(lo_half)-lo_half.high_done.sum()],[up_half.high_done.sum(), len(up_half)-up_half.high_done.sum()]])[1]:.1e}")
    P(f"{sym}: P(low_done|k=0) base {p.low_done.mean():.3f}; close upper half {up_half.low_done.mean():.3f} vs lower {lo_half.low_done.mean():.3f} Fisher p={fisher_exact([[up_half.low_done.sum(), len(up_half)-up_half.low_done.sum()],[lo_half.low_done.sum(), len(lo_half)-lo_half.low_done.sum()]])[1]:.1e}")
    for q in ((0, .25), (.25, .5), (.5, .75), (.75, 1.01)):
        m = p[(p.bar_close_loc >= q[0]) & (p.bar_close_loc < q[1])]
        P(f"     close_loc in [{q[0]},{q[1]}): n={len(m)} P(high_done) {m.high_done.mean():.3f} P(low_done) {m.low_done.mean():.3f}")
    for nm, part in (("pre", p[p.date < "2025-09-01"]), ("post", p[p.date >= "2025-09-01"])):
        lh = part[part.bar_close_loc < 0.5]; uh = part[part.bar_close_loc >= 0.5]
        P(f"     {nm}: high_done lower {lh.high_done.mean():.3f} (n={len(lh)}) vs upper {uh.high_done.mean():.3f}; low_done upper {uh.low_done.mean():.3f} vs lower {lh.low_done.mean():.3f}")

# ================================================================= M10
P("\n================= M10: event quarters")
for sym, (s, b) in SS.items():
    n = len(s)
    for nm, qf in (("tokyo open q", lambda r: r.tko), ("china open q", lambda r: r.cno)):
        kh = int(sum(r.hi_q == qf(r) for r in s.itertuples())); kl = int(sum(r.lo_q == qf(r) for r in s.itertuples()))
        P(f"{sym} {nm}: high {kh}/{n} (exp {n/36:.2f}) p={bp(kh, n, 1/36):.2f}; low {kl}/{n} p={bp(kl, n, 1/36):.2f}; 90% CI high {bci([1.0 if r.hi_q==qf(r) else 0.0 for r in s.itertuples()])}")
    # power: how large an excess could be detected at n=48 for a single quarter?
    for mult in (2, 3, 4):
        pw = np.mean([bp(k, n, 1/36, "greater") < 0.05 for k in rng.binomial(n, mult / 36, 3000)])
        P(f"   power to detect a {mult}x single-quarter excess at n={n}: {pw:.2f}")
    # volume profile
    P(f"{sym} median volume ratio: Tokyo-open quarter / session median {np.median(s.vol_tko/s.vol_med):.2f}; q0 {np.median(s.vol_q0/s.vol_med):.2f}; q35 {np.median(s.vol_q35/s.vol_med):.2f}")
P("--- M10 population (hourly, DST-aware): share of session highs/lows in the Tokyo-open bar and China-open bar vs 1/9 and vs neighbouring bars")
for sym in ("NQ", "ES"):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True); x = x[x.n_bars == 9]
    for nm, col in (("high_at_tokyo_open", "high_at_tokyo_open"), ("low_at_tokyo_open", "low_at_tokyo_open"), ("high_at_china_open", "high_at_china_open"), ("low_at_china_open", "low_at_china_open")):
        k = int(x[col].sum()); P(f"{sym} {nm}: {k}/{len(x)}={k/len(x):.3f} CI{bci(x[col])} p vs 1/9 = {bp(k, len(x), 1/9):.3f}; pre {x.loc[x.index<'2025-09-01', col].mean():.3f} post {x.loc[x.index>='2025-09-01', col].mean():.3f}")
    # relative to the bar before / after the Tokyo open
    rel = x.hi_k - x.tokyo_open_k; rell = x.lo_k - x.tokyo_open_k
    P(f"{sym} hi_k - tokyo_open_k distribution (-2..+3): {[(int((rel==d).sum())) for d in range(-2,4)]}; lo: {[(int((rell==d).sum())) for d in range(-2,4)]}")
    # interior (k=1..7) share: Tokyo-open bar vs other interior bars
    inter = x[(x.hi_k > 0) & (x.hi_k < 8)]; P(f"{sym} among interior highs (n={len(inter)}): at Tokyo-open bar {int(inter.high_at_tokyo_open.sum())} = {inter.high_at_tokyo_open.mean():.3f} (uniform over 7 interior bars = .143)")
    inter = x[(x.lo_k > 0) & (x.lo_k < 8)]; P(f"{sym} among interior lows  (n={len(inter)}): at Tokyo-open bar {int(inter.low_at_tokyo_open.sum())} = {inter.low_at_tokyo_open.mean():.3f}")
    # CN data nights: hourly bar containing 21:00/22:00 ET (k=3 EDT->21:00 is k=3; 22:00 k=4; EST 21:00 k=3 too since bars are ET-indexed)
    cal = pd.read_csv(f"{ROOT}/research/event_calendar.csv"); cal["date"] = pd.to_datetime(cal["date"])
    cn = cal[cal.category == "cn_data"]
    x["asia_gdate"] = pd.to_datetime(x["asia_gdate"])
    cnn = x[x.asia_gdate.isin(cn.date)]; non = x[~x.asia_gdate.isin(cn.date)]
    P(f"{sym} CN-data nights n={len(cnn)}: high in k=3or4 (21:00-23:00 ET) {((cnn.hi_k==3)|(cnn.hi_k==4)).mean():.3f} vs non-CN {((non.hi_k==3)|(non.hi_k==4)).mean():.3f}; low {((cnn.lo_k==3)|(cnn.lo_k==4)).mean():.3f} vs {((non.lo_k==3)|(non.lo_k==4)).mean():.3f}")

with open(f"{OUT}/recompute_log.txt", "w") as f:
    f.write("\n".join(lines))
