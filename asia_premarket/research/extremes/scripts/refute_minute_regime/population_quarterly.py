"""Hourly-population (579 sessions, splice removed, full 9-bar sessions) checks by calendar quarter of the
claims that have an hourly analogue: M1 (interior non-uniformity), M4 (close-away rule, volume), M5 (next bar after the
extreme), M6 (bars between extremes), M7 (NQ/ES agreement), M8 (window vs population rates), M9 (bar-0 close location),
M10 (Tokyo/China open bar)."""
import numpy as np, pandas as pd
from common import *
from sklearn.metrics import roc_auc_score

L = Log(f"{OUT}/population_quarterly_log.txt")
QS = ["2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2", "2026Q3", "2026Q4"]


def by_q(df, fn, name):
    rows = []
    for q in QS:
        d = df[df.quarter == q]
        if len(d) == 0: continue
        r = fn(d); r = dict(quarter=q, **r); rows.append(r)
    for h in ("H1", "H2"):
        rows.append(dict(quarter=h, **fn(df[df.half == h])))
    rows.append(dict(quarter="ALL", **fn(df)))
    t = pd.DataFrame(rows); L(f"\n--- {name}"); L(t.to_string(index=False)); return t


POP = {}
for sym in ("NQ", "ES"):
    x, p = load_pop(sym); POP[sym] = (x, p)
    L(f"\n################ {sym} population: {len(x)} full sessions (splice removed), panel rows {len(p)}")

    # ---------- M1: are the interior hours (k=1..7) uniform in the population? ----------
    def f_interior(d):
        ch = np.bincount(d[(d.hi_k >= 1) & (d.hi_k <= 7)].hi_k, minlength=9)[1:8]
        cl = np.bincount(d[(d.lo_k >= 1) & (d.lo_k <= 7)].lo_k, minlength=9)[1:8]
        sh, ph = chisq_uniform(ch); sl, pl = chisq_uniform(cl)
        return dict(n=len(d), hi_k1_7=ch.tolist(), chi2_p_high=round(ph, 4), lo_k1_7=cl.tolist(), chi2_p_low=round(pl, 4),
                    hi_tko_bar=f"{int((d.hi_k==d.tokyo_open_k).sum())}/{len(d)}={(d.hi_k==d.tokyo_open_k).mean():.3f}",
                    lo_tko_bar=f"{int((d.lo_k==d.tokyo_open_k).sum())}/{len(d)}={(d.lo_k==d.tokyo_open_k).mean():.3f}",
                    hi_k0=f"{(d.hi_k==0).mean():.3f}", hi_k8=f"{(d.hi_k==8).mean():.3f}", lo_k0=f"{(d.lo_k==0).mean():.3f}", lo_k8=f"{(d.lo_k==8).mean():.3f}")
    by_q(x, f_interior, "M1/M10: interior hourly counts k=1..7, chi-square vs uniform, Tokyo-open-bar share (uniform interior = 1/7 of interior = .143; of all sessions ~.074)")
    # Tokyo-open bar vs the other interior bars, conditioned on tokyo_open_k (DST)
    for dst in (0, 1):
        d = x[x.is_dst == dst]; tk = d.tokyo_open_k.iloc[0]
        inter_h = d[(d.hi_k >= 1) & (d.hi_k <= 7)]; inter_l = d[(d.lo_k >= 1) & (d.lo_k <= 7)]
        L(f"  DST={dst} tokyo_open_k={tk}: among interior highs (n={len(inter_h)}) share at the Tokyo-open bar {fp(inter_h.hi_k==tk)} (uniform .143) p={binom_p((inter_h.hi_k==tk).sum(), len(inter_h), 1/7):.4f}; interior lows (n={len(inter_l)}) {fp(inter_l.lo_k==tk)} p={binom_p((inter_l.lo_k==tk).sum(), len(inter_l), 1/7):.4f}")
        L(f"           per-bar counts k=1..7 high {np.bincount(inter_h.hi_k, minlength=9)[1:8].tolist()} low {np.bincount(inter_l.lo_k, minlength=9)[1:8].tolist()}; china_open_k={d.china_open_k.iloc[0]}")

    # ---------- M4: close-away rule on hourly new-running-extreme bars (interior k=1..7) ----------
    p["away_hi"] = (p.bar_close_loc < 0.5).astype(int); p["away_lo"] = (p.bar_close_loc > 0.5).astype(int)
    for side, qs, flag, away in [("high", "bars_since_hi", "high_done", "away_hi"), ("low", "bars_since_lo", "low_done", "away_lo")]:
        new = p[(p[qs] == 0) & (p.k >= 1) & (p.k <= 7)]
        def f_rule(d, flag=flag, away=away):
            a1 = d[d[away] == 1][flag]; a0 = d[d[away] == 0][flag]
            vv = d.dropna(subset=["bar_vol_rel"])
            auc_v = roc_auc_score(vv[flag], vv.bar_vol_rel) if vv[flag].nunique() == 2 and len(vv) > 20 else np.nan
            vr = d.dropna(subset=["bar_rng_rel"])
            auc_r = roc_auc_score(vr[flag], vr.bar_rng_rel) if vr[flag].nunique() == 2 and len(vr) > 20 else np.nan
            auc_c = roc_auc_score(d[flag], (1 - d.bar_close_loc) if side == "high" else d.bar_close_loc) if d[flag].nunique() == 2 else np.nan
            return dict(n_bars=len(d), sessions=d.date.nunique(), away=f"{int(a1.sum())}/{len(a1)}={a1.mean():.3f}", toward=f"{int(a0.sum())}/{len(a0)}={a0.mean():.3f}",
                        diff=round(a1.mean() - a0.mean(), 3), fisher_p=round(fisher(int(a1.sum()), len(a1), int(a0.sum()), len(a0)), 4),
                        auc_close=round(auc_c, 3), auc_vol_rel=round(auc_v, 3), auc_rng_rel=round(auc_r, 3))
        t = by_q(new, f_rule, f"M4 hourly: new running {side} at k=1..7 -> P({flag}) by close-away (close in the half away from the extreme) + AUC of close_loc / bar_vol_rel / bar_rng_rel (vol/rng rel = vs prior-20-session median of that ET hour)")
        t.to_csv(f"{OUT}/{sym}_M4_hourly_{side}.csv", index=False)
        # volume: hold rate by vol_rel tercile, all + halves
        vv = new.dropna(subset=["bar_vol_rel"]).copy(); vv["vt"] = pd.qcut(vv.bar_vol_rel, 3, labels=["low", "mid", "high"])
        L("   hold by bar_vol_rel tercile: " + "; ".join(f"{t_}: {fp(vv[vv.vt==t_][flag])}" for t_ in ["low", "mid", "high"]) +
          " | H1: " + "; ".join(f"{t_}: {fp_short(vv[(vv.vt==t_)&(vv.half=='H1')][flag])}" for t_ in ["low", "mid", "high"]) +
          " | H2: " + "; ".join(f"{t_}: {fp_short(vv[(vv.vt==t_)&(vv.half=='H2')][flag])}" for t_ in ["low", "mid", "high"]))

    # ---------- M5: bar after the session extreme ----------
    p2 = p.merge(x[["hi_k", "lo_k"]].rename(columns={"hi_k": "HK", "lo_k": "LK"}), left_on="date", right_index=True)
    aft_h = p2[p2.k == p2.HK + 1]; aft_l = p2[p2.k == p2.LK + 1]
    # bars after a failed new running high (new running high at k, but high not done)
    fail_h = p2[(p2.bars_since_hi == 0) & (p2.high_done == 0)]; fail_l = p2[(p2.bars_since_lo == 0) & (p2.low_done == 0)]
    nxt = p2.set_index(["date", "k"]).bar_ret_bp
    def nxt_ret(df):
        idx = list(zip(df.date, df.k + 1)); return nxt.reindex(idx).values
    fh_next = nxt_ret(fail_h); fl_next = nxt_ret(fail_l)
    def f_m5(d):
        ah = aft_h[aft_h.date.isin(d.index)]; al = aft_l[aft_l.date.isin(d.index)]
        fh = fail_h[fail_h.date.isin(d.index)]; fl = fail_l[fail_l.date.isin(d.index)]
        fhn = nxt_ret(fh); fln = nxt_ret(fl)
        return dict(n=len(d), after_high_down=f"{int((ah.bar_ret_bp<0).sum())}/{len(ah)}={(ah.bar_ret_bp<0).mean():.3f}", med_ret_after_high=round(ah.bar_ret_bp.median(), 1),
                    after_low_up=f"{int((al.bar_ret_bp>0).sum())}/{len(al)}={(al.bar_ret_bp>0).mean():.3f}", med_ret_after_low=round(al.bar_ret_bp.median(), 1),
                    after_FAILED_newhigh_down=f"{int((fhn<0).sum())}/{len(fhn)}={(fhn<0).mean():.3f}", after_FAILED_newlow_up=f"{int((fln>0).sum())}/{len(fln)}={(fln>0).mean():.3f}")
    by_q(x, f_m5, "M5 hourly: the bar after the session high closes down / after the low closes up; vs the bar after a FAILED new running extreme")

    # ---------- M6: bars between the extremes ----------
    def f_m6(d):
        bb = d.bars_between
        return dict(n=len(d), same_bar=f"{int((bb==0).sum())}/{len(d)}={(bb==0).mean():.3f}", within_1bar=f"{int((bb<=1).sum())}/{len(d)}={(bb<=1).mean():.3f}",
                    within_2bars=f"{(bb<=2).mean():.3f}", ge_6bars=f"{(bb>=6).mean():.3f}", median_bars=bb.median(), mean_bars=round(bb.mean(), 2), hi_first=f"{d.hi_first.mean():.3f}")
    by_q(x, f_m6, "M6 hourly: |hi_k - lo_k| (bars between the extremes); 'within 1 bar' is the hourly analogue of |dt|<=60-120 min")
    # the window in hourly terms
    w = x.loc["2026-08-31":"2026-11-06"]
    L(f"  window (hourly): same_bar {fp_short(w.bars_between==0)}, within_1bar {fp_short(w.bars_between<=1)}, median bars {w.bars_between.median()}; population same_bar {fp(x.bars_between==0)} within_1bar {fp(x.bars_between<=1)}")

    # ---------- M9: bar-0 close location -> high_done at k=0 ----------
    k0 = p[p.k == 0]
    def f_m9(d):
        lo_half = d[d.bar_close_loc < 0.5]; up_half = d[d.bar_close_loc >= 0.5]
        return dict(n=len(d), P_high_done_k0=f"{d.high_done.mean():.3f}", close_lower_half=f"{int(lo_half.high_done.sum())}/{len(lo_half)}={lo_half.high_done.mean():.3f}", close_upper_half=f"{int(up_half.high_done.sum())}/{len(up_half)}={up_half.high_done.mean():.3f}",
                    P_low_done_k0=f"{d.low_done.mean():.3f}", low_close_upper=f"{int(up_half.low_done.sum())}/{len(up_half)}={up_half.low_done.mean():.3f}", low_close_lower=f"{int(lo_half.low_done.sum())}/{len(lo_half)}={lo_half.low_done.mean():.3f}",
                    fisher_high=round(fisher(int(lo_half.high_done.sum()), len(lo_half), int(up_half.high_done.sum()), len(up_half)), 4))
    by_q(k0, f_m9, "M9 hourly: at the close of bar 0, bar_close_loc < .5 -> P(high_done); > .5 -> P(low_done)")
    # strong version: bar-0 closes in the bottom quartile
    for thr in (0.25, 0.5):
        a = k0[k0.bar_close_loc < thr]; b_ = k0[k0.bar_close_loc >= thr]
        L(f"   close_loc<{thr}: P(high_done|k=0) {fp(a.high_done)} vs {fp(b_.high_done)}; H1 {fp_short(a[a.half=='H1'].high_done)} vs {fp_short(b_[b_.half=='H1'].high_done)}; H2 {fp_short(a[a.half=='H2'].high_done)} vs {fp_short(b_[b_.half=='H2'].high_done)}")

    # ---------- M8: window-vs-population rates, by quarter ----------
    def f_m8(d):
        return dict(n=len(d), hi_k0=f"{(d.hi_k==0).mean():.3f}", hi_k8=f"{(d.hi_k==8).mean():.3f}", lo_k0=f"{(d.lo_k==0).mean():.3f}", lo_k8=f"{(d.lo_k==8).mean():.3f}",
                    hi_by_tko=f"{d.high_by_tokyo_open.mean():.3f}", lo_by_tko=f"{d.low_by_tokyo_open.mean():.3f}", hi_first=f"{d.hi_first.mean():.3f}",
                    hi_gt_rth=f"{d.high_above_rth_high.mean():.3f}", lo_lt_rth=f"{d.low_below_rth_low.mean():.3f}", med_rng=round(d.rng_bp.median(), 1), med_drop=round(d.drop_after_hi_bp.median(), 1), med_rally=round(d.rally_after_lo_bp.median(), 1))
    t = by_q(x, f_m8, "M8: hourly base rates by calendar quarter (the window 2026-08-31..11-06 straddles 2026Q3/2026Q4)")
    t.to_csv(f"{OUT}/{sym}_M8_quarterly_rates.csv", index=False)
    # how unusual is the window? compare each window stat with the distribution over 48-session rolling blocks
    L("  rolling 48-session blocks: distribution of the block rate (5th/50th/95th pct) vs the window's value")
    for col, wv in [("low_in_last_bar", w.low_in_last_bar.mean()), ("low_by_tokyo_open", w.low_by_tokyo_open.mean()), ("high_in_last_bar", w.high_in_last_bar.mean()),
                    ("low_in_first_bar", w.low_in_first_bar.mean()), ("hi_first", w.hi_first.mean()), ("high_above_rth_high", w.high_above_rth_high.mean())]:
        r = x[col].rolling(48).mean().dropna()
        L(f"    {col:22s} window {wv:.3f}; blocks 5/50/95%: {r.quantile(.05):.3f}/{r.median():.3f}/{r.quantile(.95):.3f}; share of blocks as extreme as the window: {((r-r.median()).abs()>=abs(wv-r.median())).mean():.2f}")
    r = x.rng_bp.rolling(48).median().dropna()
    L(f"    median rng_bp            window {w.rng_bp.median():.1f}; blocks 5/50/95%: {r.quantile(.05):.1f}/{r.median():.1f}/{r.quantile(.95):.1f}")
    # the window without the crash week / Sundays
    w2 = w[~w.index.isin(CRASH_WEEK)]; w3 = w[w.sunday_open == 0]
    L(f"  window ex crash week (n={len(w2)}): lo_k8 {fp_short(w2.lo_k==8)} lo_by_tko {fp_short(w2.low_by_tokyo_open)} hi_first {fp_short(w2.hi_first)} med rng {w2.rng_bp.median():.1f} | ex Sundays (n={len(w3)}): lo_k8 {fp_short(w3.lo_k==8)} lo_by_tko {fp_short(w3.low_by_tokyo_open)} hi_k0 {fp_short(w3.hi_k==0)} lo_k0 {fp_short(w3.lo_k==0)}")
    L(f"  Sunday reopens, population: hi_k0 {fp(x[x.sunday_open==1].hi_k==0)} vs weekday {fp(x[x.sunday_open==0].hi_k==0)}; lo_k0 {fp(x[x.sunday_open==1].lo_k==0)} vs {fp(x[x.sunday_open==0].lo_k==0)}")

# ---------- M7: NQ vs ES agreement on the hourly population ----------
xn, xe = POP["NQ"][0], POP["ES"][0]
j = xn[["hi_k", "lo_k", "hi_first", "quarter", "half", "sunday_open", "rng_bp"]].join(xe[["hi_k", "lo_k", "hi_first"]], lsuffix="_nq", rsuffix="_es", how="inner")
def f_m7(d):
    return dict(n=len(d), same_hi_k=f"{int((d.hi_k_nq==d.hi_k_es).sum())}/{len(d)}={(d.hi_k_nq==d.hi_k_es).mean():.3f}", same_lo_k=f"{int((d.lo_k_nq==d.lo_k_es).sum())}/{len(d)}={(d.lo_k_nq==d.lo_k_es).mean():.3f}",
                within1_hi=f"{((d.hi_k_nq-d.hi_k_es).abs()<=1).mean():.3f}", within1_lo=f"{((d.lo_k_nq-d.lo_k_es).abs()<=1).mean():.3f}", hi_first_agree=f"{(d.hi_first_nq==d.hi_first_es).mean():.3f}")
t = by_q(j, f_m7, "M7: NQ vs ES same hourly bar for the high / low, by quarter (population)")
t.to_csv(f"{OUT}/M7_quarterly_agreement.csv", index=False)
# chance agreement under independence given the marginal hi_k distributions
ph = np.bincount(j.hi_k_nq, minlength=9) / len(j); pe = np.bincount(j.hi_k_es, minlength=9) / len(j)
pl = np.bincount(j.lo_k_nq, minlength=9) / len(j); ple = np.bincount(j.lo_k_es, minlength=9) / len(j)
L(f"  chance same-bar agreement under independence: high {(ph*pe).sum():.3f}, low {(pl*ple).sum():.3f}")
r = (j.hi_k_nq == j.hi_k_es).astype(float).rolling(48).mean().dropna(); r2 = (j.lo_k_nq == j.lo_k_es).astype(float).rolling(48).mean().dropna()
L(f"  rolling-48 same-bar agreement 5/50/95%: high {r.quantile(.05):.2f}/{r.median():.2f}/{r.quantile(.95):.2f}; low {r2.quantile(.05):.2f}/{r2.median():.2f}/{r2.quantile(.95):.2f}; window(hourly) high {(j.loc['2026-08-31':'2026-11-06'].hi_k_nq==j.loc['2026-08-31':'2026-11-06'].hi_k_es).mean():.2f} low {(j.loc['2026-08-31':'2026-11-06'].lo_k_nq==j.loc['2026-08-31':'2026-11-06'].lo_k_es).mean():.2f}")
L.close()
