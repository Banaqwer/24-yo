"""Real-time (non-circular) recomputations for M3, M4, M5, M7, M9."""
import numpy as np, pandas as pd
from scipy.stats import fisher_exact, binomtest
from sklearn.metrics import roc_auc_score

LM = "research/extremes/scripts/lens_minute"
rng = np.random.default_rng(5)


def bci(v, B=4000):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    if len(v) == 0: return (np.nan, np.nan)
    i = rng.integers(0, len(v), (B, len(v)))
    return tuple(np.round(np.percentile(v[i].mean(1), [5, 95]), 3))


def fp(v):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    return f"{int(v.sum())}/{len(v)}={v.mean():.2f} CI{bci(v)}" if len(v) else "0/0"


def fisher(a1, a0, b1, b0):
    return fisher_exact([[a1, a0], [b1, b0]])[1]


def load(sym):
    s = pd.read_csv(f"{LM}/{sym}_q15_sessions.csv", index_col=0, parse_dates=True); s = s[s.n_q == 36].sort_index()
    b = pd.read_csv(f"{LM}/{sym}_q15_bars.csv", parse_dates=["date"]); b = b[b.date.isin(s.index)].copy()
    b = b.sort_values(["date", "q"]).reset_index(drop=True)
    return s, b


for sym in ("NQ", "ES"):
    s, b = load(sym)
    half_dates = s.index[:24]
    print(f"\n#################### {sym}")

    # ---------------- M3: real-time stop-run ----------------
    print("=== M3 real-time: first 15m bar that breaks the f15 high/low; break size & close known at that bar's close")
    rows = []
    for d, g in b.groupby("date"):
        g = g.sort_values("q"); q0 = g.iloc[0]; ref = s.loc[d, "ref_close"]
        f15h, f15l = q0.high, q0.low; hiq, loq = s.loc[d, "hi_q"], s.loc[d, "lo_q"]
        r = dict(date=d, half=int(d in half_dates))
        bh = g[(g.q >= 1) & (g.high > f15h)]
        if len(bh):
            fb = bh.iloc[0]
            r.update(hi_broken=1, hi_first_q=int(fb.q), hi_first_brk_bp=(fb.high - f15h) / ref * 1e4, hi_first_close_inside=int(fb.close < f15h),
                     hi_first_is_session_high=int(fb.q == hiq), hi_eventual_brk_bp=s.loc[d, "brk_hi_bp"],
                     hi_first_bar_closeloc=(fb.close - fb.low) / max(fb.high - fb.low, 1e-9))
        else:
            r.update(hi_broken=0)
        bl = g[(g.q >= 1) & (g.low < f15l)]
        if len(bl):
            fb = bl.iloc[0]
            r.update(lo_broken=1, lo_first_q=int(fb.q), lo_first_brk_bp=(f15l - fb.low) / ref * 1e4, lo_first_close_inside=int(fb.close > f15l),
                     lo_first_is_session_low=int(fb.q == loq), lo_eventual_brk_bp=s.loc[d, "brk_lo_bp"])
        else:
            r.update(lo_broken=0)
        rows.append(r)
    R = pd.DataFrame(rows).set_index("date")
    R.to_csv(f"research/extremes/scripts/refute_minute_leak/{sym}_m3_realtime.csv")
    for side, thr_list in (("hi", (5, 10, 15, 20)), ("lo", (5, 10, 15, 20))):
        br = R[R[f"{side}_broken"] == 1]
        hold = br[f"{side}_first_is_session_{'high' if side=='hi' else 'low'}"]
        print(f"  {side}: f15 {side} broken in {len(br)}/48; P(first breaking bar IS the session extreme) = {fp(hold)}")
        print(f"      first-bar break bp median {br[f'{side}_first_brk_bp'].median():.1f} vs eventual (ex-post) break median {br[f'{side}_eventual_brk_bp'].median():.1f}; "
              f"corr first vs eventual {np.corrcoef(br[f'{side}_first_brk_bp'], br[f'{side}_eventual_brk_bp'])[0,1]:.2f}")
        for thr in thr_list:
            m = br[(br[f"{side}_first_brk_bp"] < thr)]
            mc = m[m[f"{side}_first_close_inside"] == 1]
            mo = br[~br.index.isin(mc.index)]
            h1 = mc[f"{side}_first_is_session_{'high' if side=='hi' else 'low'}"]; h0 = mo[f"{side}_first_is_session_{'high' if side=='hi' else 'low'}"]
            p = fisher(int(h1.sum()), len(h1) - int(h1.sum()), int(h0.sum()), len(h0) - int(h0.sum())) if len(h1) and len(h0) else np.nan
            # how many of these 'small first breaks that closed inside' had the EVENTUAL break also < thr (i.e. the ex-post definition)?
            ev = (mc[f"{side}_eventual_brk_bp"] < thr).mean() if len(mc) else np.nan
            print(f"      first break <{thr}bp: n={len(m)}; of which closed back inside f15: n={len(mc)} -> P(session extreme)={fp(h1)} vs other breaks {fp(h0)} Fisher p={p:.3f}; "
                  f"share whose EVENTUAL max break stayed <{thr}bp = {ev:.2f}; halves (A/B) hold: {fp(h1[mc.half==1])} / {fp(h1[mc.half==0])}")
        # the ex-post definition used by the lens: eventual break < 10 bp -> trivially 'reversed'
        ex = br[br[f"{side}_eventual_brk_bp"] < 10]
        print(f"      [ex-post def] eventual break <10bp: n={len(ex)}; of these the first breaking bar was the session extreme in {int(ex[f'{side}_first_is_session_{'high' if side=='hi' else 'low'}'].sum())}; "
              f"their first-bar break <10bp in {int((ex[f'{side}_first_brk_bp']<10).sum())}")

    # ---------------- M4: close-away rule by half; ex-ante normalisation ----------------
    print("=== M4: close-away rule split by window half; ex-ante vs in-sample vol_tod")
    b["close_loc"] = (b.close - b.low) / (b.high - b.low).replace(0, np.nan)
    b["half"] = b.date.isin(half_dates).astype(int)
    # in-sample (lens) normalisation
    b["vol_tod_is"] = b.vol / b.groupby("q").vol.transform("median")
    # ex-ante: median of the same quarter over PRIOR sessions only (expanding, needs >=5 prior)
    b["vol_tod_xa"] = np.nan
    dates = list(s.index)
    for i, d in enumerate(dates):
        if i < 5: continue
        prior = b[b.date.isin(dates[:i])].groupby("q").vol.median()
        m = b.date == d
        b.loc[m, "vol_tod_xa"] = b.loc[m, "vol"].values / prior.reindex(b.loc[m, "q"]).values
    # session-median normalisation (lens 'vol_rel') uses the whole session -> ex post; ex-ante version: running median of bars so far
    b["vol_rel_run"] = b.groupby("date").vol.transform(lambda v: v / v.expanding().median())
    for side, flag, since in (("high", "is_hi_bar", "q_since_hi"), ("low", "is_lo_bar", "q_since_lo")):
        new = b[b[since] == 0].copy()
        away = (1 - new.close_loc) if side == "high" else new.close_loc
        new["away"] = (away > 0.5).astype(int)
        for h, nm in ((1, "first24"), (0, "last24")):
            g = new[new.half == h]
            r1 = g[g.away == 1][flag]; r0 = g[g.away == 0][flag]
            print(f"  {side} {nm}: close-away P(hold)={fp(r1)} vs {fp(r0)} Fisher p={fisher(int(r1.sum()), len(r1)-int(r1.sum()), int(r0.sum()), len(r0)-int(r0.sum())):.4f}")
        inner = new[(new.q > 0) & (new.q < 35)]
        for f in ("vol_tod_is", "vol_tod_xa", "vol_rel", "vol_rel_run"):
            m = inner[f].notna()
            try:
                a = roc_auc_score(inner[flag][m], inner[f][m])
            except Exception:
                a = np.nan
            print(f"     interior AUC {f}: {a:.3f} (n={int(m.sum())})")
        # q35 bars: hold is certain by construction
        q35 = new[new.q == 35]
        print(f"     new-{side} bars at q35 (hold certain by construction): {len(q35)}, all hold: {int(q35[flag].sum())}")

    # ---------------- M5: inversion P(hold | next bar reverses) ----------------
    print("=== M5: knowable form P(session extreme | new running extreme at q, bar q+1 reverses)")
    b["next_ret"] = b.groupby("date").ret_bp.shift(-1)
    for side, flag, since, sgn in (("high", "is_hi_bar", "q_since_hi", -1), ("low", "is_lo_bar", "q_since_lo", 1)):
        new = b[(b[since] == 0) & b.next_ret.notna()]
        rev = new[sgn * new.next_ret > 0]; nrev = new[sgn * new.next_ret <= 0]
        print(f"  {side}: n new-extreme bars with a next bar {len(new)} (hold {int(new[flag].sum())}); P(hold)={new[flag].mean():.3f}; "
              f"P(hold | next reverses)={fp(rev[flag])} vs P(hold | next continues/flat)={fp(nrev[flag])}; Fisher p={fisher(int(rev[flag].sum()), len(rev)-int(rev[flag].sum()), int(nrev[flag].sum()), len(nrev)-int(nrev[flag].sum())):.4f}")
        # ex-post direction as the lens reports it, with the correct denominator
        hold = new[new[flag] == 1]
        print(f"     [lens direction] P(next reverses | session extreme) = {fp(sgn*hold.next_ret>0)} (lens quotes /48 incl. q35 sessions with no next bar)")
        for h, nm in ((1, "first24"), (0, "last24")):
            g = new[new.half == h]; r = g[sgn * g.next_ret > 0]; nr = g[sgn * g.next_ret <= 0]
            print(f"     {nm}: P(hold|rev)={fp(r[flag])} vs {fp(nr[flag])}")
        # combined with M4's close-away (is the next-bar feature incremental?)
        away = (1 - new.close_loc) if side == "high" else new.close_loc
        for aw in (1, 0):
            g = new[(away > 0.5) == bool(aw)]; r = g[sgn * g.next_ret > 0]; nr = g[sgn * g.next_ret <= 0]
            print(f"     close-away={aw}: P(hold|next rev)={fp(r[flag])} vs P(hold|next not rev)={fp(nr[flag])}")

    # ---------------- M9: halves + relation to quarters-since-running-high at 19:00 ----------------
    print("=== M9: bar-0 extreme sub-quarter -> P(bar-0 extreme holds); halves")
    b0 = b[b.q < 4]
    sub_hi = b0.groupby("date").apply(lambda d: int(d.high.values.argmax())).reindex(s.index)
    sub_lo = b0.groupby("date").apply(lambda d: int(d.low.values.argmin())).reindex(s.index)
    for nm, idx in (("first24", s.index[:24]), ("last24", s.index[24:])):
        ss = s.loc[idx]; sh = sub_hi.loc[idx]; sl = sub_lo.loc[idx]
        a1 = ss[sh == 0].hi_k15.eq(0); a0 = ss[sh > 0].hi_k15.eq(0); l1 = ss[sl == 0].lo_k15.eq(0); l0 = ss[sl > 0].lo_k15.eq(0)
        print(f"  {nm}: high set in q0 -> {fp(a1)} vs later {fp(a0)}; low set in q0 -> {fp(l1)} vs later {fp(l0)}")

if True:
    # ---------------- M7: halves Fisher ----------------
    print("\n=== M7: NQ-vs-ES same-quarter agreement, first 24 vs last 24 (Fisher)")
    nq, es = load("NQ")[0], load("ES")[0]
    j = nq.join(es, lsuffix="_nq", rsuffix="_es", how="inner").sort_index()
    for side in ("hi", "lo"):
        same = ((j[f"{side}_q_nq"] - j[f"{side}_q_es"]).abs() == 0).astype(int)
        a, bb = same.iloc[:24], same.iloc[24:]
        print(f"  {side}: A {int(a.sum())}/24 B {int(bb.sum())}/24 Fisher p={fisher(int(a.sum()), 24-int(a.sum()), int(bb.sum()), 24-int(bb.sum())):.3f}")
    # chance agreement under independence given each symbol's marginal quarter distribution
    for side in ("hi", "lo"):
        pn = j[f"{side}_q_nq"].value_counts(normalize=True).reindex(range(36), fill_value=0)
        pe = j[f"{side}_q_es"].value_counts(normalize=True).reindex(range(36), fill_value=0)
        print(f"  {side}: chance same-quarter under independence = {(pn*pe).sum():.3f}")
