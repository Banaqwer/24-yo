"""Window-level robustness of the 15m lens claims (M1..M7, M9, M10):
sub-period (2026Q3 = Aug31..Sep30 vs 2026Q4 = Oct1..Nov6), Sunday reopens vs weekdays,
drop the 5 widest-range nights, drop the Nov 2-6 crash week, drop the 09-11 splice-flag session."""
import numpy as np, pandas as pd
from common import *

L = Log(f"{OUT}/window_robust_log.txt")


def subsets(s):
    top5 = s.rng_bp.sort_values(ascending=False).index[:5]
    return {
        "all": s,
        "2026Q3": s[s.period == "2026Q3"],
        "2026Q4": s[s.period == "2026Q4"],
        "sunday": s[s.sunday_open == 1],
        "weekday": s[s.sunday_open == 0],
        "drop_top5_rng": s.drop(top5),
        "drop_crash_wk": s[s.crash_week == 0],
        "drop_0911_flag": s.drop(pd.Timestamp("2026-09-11"), errors="ignore"),
    }


def rate_table(s, name, cols, p0=None):
    """cols: dict label -> boolean series over s.index ; p0: null rate for binomial p"""
    rows = []
    for sub, ss in subsets(s).items():
        r = dict(subset=sub, n=len(ss))
        for lab, v in cols.items():
            vv = v.loc[ss.index]
            n, k, p = prop(vv)
            r[lab] = f"{k}/{n}={p:.2f}" + (f" p={binom_p(k, n, p0[lab]):.3f}" if p0 and lab in p0 and n else "")
        rows.append(r)
    t = pd.DataFrame(rows)
    L(f"\n--- {name}"); L(t.to_string(index=False))
    return t


for sym in ("NQ", "ES"):
    s, b = load_q15(sym)
    L(f"\n################ {sym}: n={len(s)}; 2026Q3={int((s.period=='2026Q3').sum())} 2026Q4={int((s.period=='2026Q4').sum())}; sunday={int(s.sunday_open.sum())}; crash week={int(s.crash_week.sum())}")
    top5 = s.rng_bp.sort_values(ascending=False).index[:5]
    L("top-5 range nights:", [f"{d.date()} {r:.0f}bp" for d, r in s.rng_bp.loc[top5].items()])

    # ---------------- M1: edge quarters ----------------
    cols = {"hi_q0": s.hi_q == 0, "lo_q0": s.lo_q == 0, "hi_q35": s.hi_q == 35, "lo_q35": s.lo_q == 35,
            "hi_edge": (s.hi_q == 0) | (s.hi_q == 35), "lo_edge": (s.lo_q == 0) | (s.lo_q == 35)}
    p0 = {"hi_q0": 1/36, "lo_q0": 1/36, "hi_q35": 1/36, "lo_q35": 1/36, "hi_edge": 2/36, "lo_edge": 2/36}
    rate_table(s, "M1 edge quarters (binomial p vs uniform 1/36 or 2/36)", cols, p0)
    # which nights carry the q35 mass / q0 mass
    L("  q0 highs:", [str(d.date()) + ("*S" if s.loc[d, "sunday_open"] else "") for d in s.index[s.hi_q == 0]])
    L("  q0 lows :", [str(d.date()) + ("*S" if s.loc[d, "sunday_open"] else "") for d in s.index[s.lo_q == 0]])
    L("  q35 highs:", [str(d.date()) for d in s.index[s.hi_q == 35]])
    L("  q35 lows :", [str(d.date()) for d in s.index[s.lo_q == 35]])
    # the lens's 'interior indistinguishable from uniform' claim: power of the 34-cell chi-square at n=48
    inner_h = s[(s.hi_q > 0) & (s.hi_q < 35)].hi_q; inner_l = s[(s.lo_q > 0) & (s.lo_q < 35)].lo_q
    ch = np.bincount(inner_h, minlength=36)[1:35]; cl = np.bincount(inner_l, minlength=36)[1:35]
    L(f"  interior chi-square: high stat={chisq_uniform(ch)[0]:.1f} p={chisq_uniform(ch)[1]:.2f} (n={ch.sum()}, expected {ch.sum()/34:.2f}/cell); low stat={chisq_uniform(cl)[0]:.1f} p={chisq_uniform(cl)[1]:.2f}")
    # power: simulate the population HOURLY interior shape (k=1..7 rates) spread uniformly within each hour, n=37 interior extremes
    pop_hi = np.array([8.1, 11.1, 8.6, 5.2, 5.5, 5.5, 8.1]); pop_lo = np.array([8.6, 10.7, 7.4, 6.4, 3.5, 3.5, 8.6])
    # the 34 interior quarters: q1..q3 (k=0 tail, use k=0's 3 quarters share? unknown) -> approximate: give q1..3 and q32..34 the hourly k=0/k=8 interior share
    def power(pop_k, n_int, B=3000):
        # quarter probabilities: k=1..7 hourly rates split over 4 quarters each; q1-3 and q32-34 use the population k=0/k=8 rates minus the edge quarter (assume half of the hourly mass sits in the edge quarter)
        pk = np.zeros(36)
        for k in range(1, 8): pk[4*k:4*k+4] = pop_k[k-1] / 4
        pk[1:4] = 23.5 / 2 / 3 if pop_k is pop_hi else 31.1 / 2 / 3
        pk[32:35] = 24.4 / 2 / 3 if pop_k is pop_hi else 20.2 / 2 / 3
        p_int = pk[1:35] / pk[1:35].sum()
        rej = 0
        for _ in range(B):
            c = rng.multinomial(n_int, p_int)
            if chisq_uniform(c)[1] < 0.05: rej += 1
        return rej / B
    L(f"  power of the 34-cell chi-square (alpha .05) to reject uniform when the truth is the population hourly interior shape (k=1..7 rates 8.1/11.1/8.6/5.2/5.5/5.5/8.1): high {power(pop_hi, int(ch.sum())):.2f}, low {power(pop_lo, int(cl.sum())):.2f}")
    # pooled interior at hour resolution (k=1..7) in the window vs the population shape
    hk = np.bincount(s[(s.hi_k15 >= 1) & (s.hi_k15 <= 7)].hi_k15, minlength=9)[1:8]
    lk = np.bincount(s[(s.lo_k15 >= 1) & (s.lo_k15 <= 7)].lo_k15, minlength=9)[1:8]
    L(f"  window interior hourly counts k=1..7: high {hk.tolist()} low {lk.tolist()}; population shares (of all) high {pop_hi.tolist()} low {pop_lo.tolist()}")

    # ---------------- M2: within k=0 / k=8 ----------------
    L("\n--- M2 within-hour placement of k=0 and k=8 extremes")
    for sub, ss in subsets(s).items():
        fh = ss[ss.hi_k15 == 0]; fl = ss[ss.lo_k15 == 0]; lh = ss[ss.hi_k15 == 8]; ll = ss[ss.lo_k15 == 8]
        L(f"  {sub:14s} n={len(ss):2d} | k0 high in q0: {fp_short(fh.hi_sub==0)}  k0 low in q0: {fp_short(fl.lo_sub==0)} | k8 high in q35: {fp_short(lh.hi_sub==3)}  k8 low in q35: {fp_short(ll.lo_sub==3)} | open==high {int(ss.open_is_high.sum())} open==low {int(ss.open_is_low.sum())}")
    # how close is the 18:00 open to the q0 extreme when q0 holds (in bp) - and how many are within 1 tick / 2 bp
    h0 = s[s.hi_q == 0]; l0 = s[s.lo_q == 0]
    dh = (h0.hi - h0.open_18) / h0.ref_close * 1e4; dl = (l0.open_18 - l0.lo) / l0.ref_close * 1e4
    L(f"  q0-held highs: high-open bp {dh.round(1).tolist()} -> within 2bp of the open: {int((dh<=2).sum())}/{len(dh)}; q0-held lows: open-low bp {dl.round(1).tolist()} -> within 2bp: {int((dl<=2).sum())}/{len(dl)}")
    L(f"  q0-held highs on Sunday reopens: {int(h0.sunday_open.sum())}/{len(h0)}; q0-held lows on Sunday: {int(l0.sunday_open.sum())}/{len(l0)}")

    # ---------------- M3: f15 hold / stop-run ----------------
    cols = {"f15_hi_hold": s.f15_high_holds == 1, "f15_lo_hold": s.f15_low_holds == 1,
            "hi_stoprun<10": s.hi_stoprun == 1, "lo_stoprun<10": s.lo_stoprun == 1,
            "hi_brk<10": (s.brk_hi_bp > 0) & (s.brk_hi_bp < 10), "lo_brk<10": (s.brk_lo_bp > 0) & (s.brk_lo_bp < 10)}
    rate_table(s, "M3 first-15m hold and stop-run (session-level, ex post)", cols)
    L("  median break (bp) / f15 range (bp) / ratio-of-medians / median-of-ratios by subset:")
    for sub, ss in subsets(s).items():
        bh = ss[ss.brk_hi_bp > 0]; bl = ss[ss.brk_lo_bp > 0]
        L(f"  {sub:14s} high: {bh.brk_hi_bp.median():5.1f}/{ss.f15_rng_bp.median():4.1f}={bh.brk_hi_bp.median()/ss.f15_rng_bp.median():.2f} med-ratio {(bh.brk_hi_bp/bh.f15_rng_bp).median():.2f} IQR[{(bh.brk_hi_bp/bh.f15_rng_bp).quantile(.25):.1f},{(bh.brk_hi_bp/bh.f15_rng_bp).quantile(.75):.1f}] | low: {bl.brk_lo_bp.median():5.1f} med-ratio {(bl.brk_lo_bp/bl.f15_rng_bp).median():.2f} IQR[{(bl.brk_lo_bp/bl.f15_rng_bp).quantile(.25):.1f},{(bl.brk_lo_bp/bl.f15_rng_bp).quantile(.75):.1f}]")
    # 'reversed' rate by break-size band: is <10bp special, or is any break reversed because the close is rarely at the high?
    L("  P(session close back inside f15 range | break size band):")
    for lo_, hi_ in [(0, 5), (5, 10), (10, 20), (20, 40), (40, 1e9)]:
        bh = s[(s.brk_hi_bp > lo_) & (s.brk_hi_bp <= hi_)]; bl = s[(s.brk_lo_bp > lo_) & (s.brk_lo_bp <= hi_)]
        L(f"    ({lo_:.0f},{hi_ if hi_ < 1e8 else 'inf'}] high: {fp_short(bh.close_below_f15hi)}  low: {fp_short(bl.close_above_f15lo)}")
    # the knowable-at-the-time version: at the close of the FIRST 15m bar that breaks the f15 high, break size < 10bp -> P(session high already in)?
    L("  knowable version: at the close of the first bar that breaks the f15 high/low, break size so far < thr -> P(session extreme already in)")
    rows = []
    for d, ss in b.groupby("date"):
        ss = ss.sort_values("q"); f15h = ss.high.iloc[0]; f15l = ss.low.iloc[0]; ref = s.loc[d, "ref_close"]
        bh = ss[(ss.q > 0) & (ss.high > f15h)]; bl = ss[(ss.q > 0) & (ss.low < f15l)]
        if len(bh):
            r = bh.iloc[0]; rows.append(dict(date=d, side="high", brk_at_first_break=(r.high - f15h) / ref * 1e4, q=r.q, done=r.high_done, closed_back=int(r.close < f15h)))
        if len(bl):
            r = bl.iloc[0]; rows.append(dict(date=d, side="low", brk_at_first_break=(f15l - r.low) / ref * 1e4, q=r.q, done=r.low_done, closed_back=int(r.close > f15l)))
    fb = pd.DataFrame(rows)
    for side in ("high", "low"):
        f = fb[fb.side == side]
        for thr in (5, 10, 20):
            sm = f[f.brk_at_first_break < thr]; lg = f[f.brk_at_first_break >= thr]
            L(f"    {side}: first break < {thr}bp: P(extreme already in at that close) {fp_short(sm.done)} ; >= {thr}bp: {fp_short(lg.done)} ; first break < {thr}bp AND bar closed back inside: {fp_short(sm[sm.closed_back==1].done)} (n={int(sm.closed_back.sum())})")
    fb.to_csv(f"{OUT}/{sym}_first_break_knowable.csv", index=False)

    # ---------------- M4: close-away rule on new-running-extreme bars ----------------
    L("\n--- M4 close-away rule on 15m new-running-extreme bars (interior quarters 1..34 only, which the lens also reports)")
    b["close_loc"] = (b.close - b.low) / (b.high - b.low).replace(0, np.nan)
    b["vol_tod"] = b.vol / b.groupby("q").vol.transform("median")
    b = b.merge(s[["period", "sunday_open", "crash_week", "rng_bp"]].rename(columns={"rng_bp": "sess_rng"}), left_on="date", right_index=True)
    for side, flag, qs in [("high", "is_hi_bar", "q_since_hi"), ("low", "is_lo_bar", "q_since_lo")]:
        new = b[(b[qs] == 0) & (b.q > 0) & (b.q < 35)].copy()
        away = (1 - new.close_loc) if side == "high" else new.close_loc
        new["away"] = (away > 0.5).astype(int)
        for sub, mask in [("all", np.ones(len(new), bool)), ("2026Q3", new.period == "2026Q3"), ("2026Q4", new.period == "2026Q4"),
                          ("sunday", new.sunday_open == 1), ("weekday", new.sunday_open == 0),
                          ("drop_top5_rng", ~new.date.isin(top5)), ("drop_crash_wk", new.crash_week == 0)]:
            m = new[mask]; a1 = m[m.away == 1][flag]; a0 = m[m.away == 0][flag]
            L(f"  {side} {sub:14s}: away {fp_short(a1)} vs toward {fp_short(a0)}  Fisher p={fisher(int(a1.sum()), len(a1), int(a0.sum()), len(a0)):.4f}  (sessions {m.date.nunique()})")
        # session-level sanity: the rule applied as 'P(hold) among away-bars' is dominated by how many new-extreme bars a session has; cluster bootstrap by session
        diffs = []
        dates = new.date.unique()
        for _ in range(2000):
            dd = rng.choice(dates, len(dates)); m = pd.concat([new[new.date == d] for d in dd])
            a1 = m[m.away == 1][flag]; a0 = m[m.away == 0][flag]
            diffs.append(a1.mean() - a0.mean())
        L(f"    cluster(session)-bootstrap 90% CI of the away-minus-toward hold-rate difference: [{np.percentile(diffs,5):.3f},{np.percentile(diffs,95):.3f}]")
        # time-of-day adjusted volume: hold rate by vol_tod tercile
        new["vt"] = pd.qcut(new.vol_tod, 3, labels=["low", "mid", "high"])
        L("    hold rate by vol_tod tercile: " + "; ".join(f"{t}: {fp_short(new[new.vt==t][flag])}" for t in ["low", "mid", "high"]))

    # ---------------- M5: next bar after the extreme ----------------
    cols = {"after_hi_down": s.hi_next_ret_bp < 0, "after_lo_up": s.lo_next_ret_bp > 0}
    rate_table(s, "M5 bar after the session extreme (15m)", cols)
    # the comparison the lens makes: bars after a FAILED new running extreme
    b["next_ret"] = b.groupby("date").ret_bp.shift(-1)
    for side, flag, qs, sgn in [("high", "is_hi_bar", "q_since_hi", -1), ("low", "is_lo_bar", "q_since_lo", 1)]:
        new = b[(b[qs] == 0) & b.next_ret.notna()]
        g1 = new[new[flag] == 1]; g0 = new[new[flag] == 0]
        L(f"  {side}: P(next bar reverses) hold {fp_short(sgn*g1.next_ret>0)} vs fail {fp_short(sgn*g0.next_ret>0)}; by period: " +
          "; ".join(f"{p}: hold {fp_short(sgn*g1[g1.period==p].next_ret>0)} fail {fp_short(sgn*g0[g0.period==p].next_ret>0)}" for p in ["2026Q3", "2026Q4"]))

    # ---------------- M6: time between extremes ----------------
    L("\n--- M6 |high-low| time (15m)")
    for sub, ss in subsets(s).items():
        ad = ss.q_between.abs() * 15
        L(f"  {sub:14s} n={len(ss):2d} median {ad.median():5.0f} min; P(<=60) {fp_short(ad<=60)}; P(<=120) {fp_short(ad<=120)}; P(>=6h) {fp_short(ad>=360)}; hi_first {fp_short(ss.hi_first)}")

    # ---------------- M9: bar-0 sub-quarter -> hold ----------------
    L("\n--- M9 bar-0 extreme set in 18:00-18:15 -> P(session extreme in bar 0)")
    for sub, ss in subsets(s).items():
        fh = ss[ss.bar0_hi_sub == 0]; lh = ss[ss.bar0_hi_sub > 0]; fl = ss[ss.bar0_lo_sub == 0]; ll = ss[ss.bar0_lo_sub > 0]
        L(f"  {sub:14s} high: q0 {fp_short(fh.hi_k15==0)} vs later {fp_short(lh.hi_k15==0)} | low: q0 {fp_short(fl.lo_k15==0)} vs later {fp_short(ll.lo_k15==0)} | bar0 close_loc<.5 -> high in bar0 {fp_short(ss[ss.bar0_close_loc<0.5].hi_k15==0)} vs {fp_short(ss[ss.bar0_close_loc>=0.5].hi_k15==0)}")

    # ---------------- M10: event quarters ----------------
    L("\n--- M10 Tokyo-open / China-open quarter and hour (DST-aware)")
    s["tko_hi"] = (s.hi_q == s.tko_q).astype(int); s["tko_lo"] = (s.lo_q == s.tko_q).astype(int)
    s["tko_hr_hi"] = ((s.hi_q >= s.tko_q) & (s.hi_q < s.tko_q + 4)).astype(int); s["tko_hr_lo"] = ((s.lo_q >= s.tko_q) & (s.lo_q < s.tko_q + 4)).astype(int)
    s["pre_tko_hi"] = ((s.hi_q >= s.tko_q - 4) & (s.hi_q < s.tko_q)).astype(int); s["pre_tko_lo"] = ((s.lo_q >= s.tko_q - 4) & (s.lo_q < s.tko_q)).astype(int)
    cols = {"tko_q_hi": s.tko_hi == 1, "tko_q_lo": s.tko_lo == 1, "tko_hour_hi": s.tko_hr_hi == 1, "tko_hour_lo": s.tko_hr_lo == 1, "hour_before_tko_hi": s.pre_tko_hi == 1, "hour_before_tko_lo": s.pre_tko_lo == 1}
    rate_table(s, "M10 Tokyo open quarter / hour (uniform: 1/36 per quarter, 4/36=.111 per hour)", cols, {"tko_hour_hi": 4/36, "tko_hour_lo": 4/36, "tko_q_hi": 1/36, "tko_q_lo": 1/36})
    # power of a single-quarter binomial test at n=48 to detect a 2x or 3x bump
    for mult in (2, 3):
        p1 = mult / 36
        # two-sided exact test at alpha .05: rejection region k >= kcrit
        kcrit = next(k for k in range(0, 49) if binom_p(k, 48, 1/36) < 0.05 and k > 48/36)
        from scipy.stats import binom
        pw = 1 - binom.cdf(kcrit - 1, 48, p1)
        L(f"  power at n=48 to detect a {mult}x bump in one quarter (reject when k>={kcrit}): {pw:.2f}")

    s.to_csv(f"{OUT}/{sym}_sessions_flagged.csv")

L.close()
