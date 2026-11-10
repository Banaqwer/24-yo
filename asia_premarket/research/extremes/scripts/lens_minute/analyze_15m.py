"""Minute-level anatomy of the Asia high / low from 15-minute bars (NQ, ES; 48 sessions 2026-08-31 .. 2026-11-06).
Reads {sym}_q15_sessions.csv / {sym}_q15_bars.csv from build_15m.py, writes the cited tables as CSV.
"""
import numpy as np, pandas as pd
from scipy.stats import binomtest, mannwhitneyu

OUT = "research/extremes/scripts/lens_minute"
rng = np.random.default_rng(7)
SPLICE_FLAG = pd.Timestamp("2026-09-11")   # Sunday 09-13 reopen, -131bp NQ gap, roll week, no documented news


def boot_ci(v, stat=np.mean, B=5000):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    if len(v) == 0: return (np.nan, np.nan)
    idx = rng.integers(0, len(v), (B, len(v)))
    s = np.array([stat(v[i]) for i in idx])
    return tuple(np.round(np.percentile(s, [5, 95]), 3))


def prop(v):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    n = len(v); k = int(v.sum())
    return n, k, k / n if n else np.nan, boot_ci(v)


def binom_p(k, n, p0):
    return binomtest(int(k), int(n), p0).pvalue if n else np.nan


def qlabel(q):
    h = (18 + q // 4) % 24; m = (q % 4) * 15
    return f"{h:02d}:{m:02d}"


def load(sym):
    s = pd.read_csv(f"{OUT}/{sym}_q15_sessions.csv", index_col=0, parse_dates=True)
    b = pd.read_csv(f"{OUT}/{sym}_q15_bars.csv", parse_dates=["date"])
    s = s[s["n_q"] == 36]; b = b[b["date"].isin(s.index)]
    return s, b


def zone_of(q, dst):
    tko = 8 if dst else 4; cno = 14 if dst else 10
    if q == 0: return "A_reopen_1800"
    if q >= 32: return "L_last_hour_0200"
    if q < tko: return "B_pre_tokyo"
    if q == tko: return "C_tokyo_open_q"
    if q < cno: return "D_tokyo_0915_0930"
    if q == cno: return "E_china_open_q"
    if q <= cno + 2: return "F_china_data_0945_1015"
    if q <= tko + 9: return "G_tokyo_late_am"
    if q <= tko + 13: return "H_tokyo_lunch"
    if q < 24: return "I_tokyo_pm_to_0000"
    if q < 28: return "J_0000_0100"
    return "K_0100_0200"


ZONE_Q = {  # number of quarters in each zone for EDT / EST
    "A_reopen_1800": (1, 1), "B_pre_tokyo": (7, 3), "C_tokyo_open_q": (1, 1), "D_tokyo_0915_0930": (5, 5),
    "E_china_open_q": (1, 1), "F_china_data_0945_1015": (2, 2), "G_tokyo_late_am": (1, 1), "H_tokyo_lunch": (4, 4),
    "I_tokyo_pm_to_0000": (2, 6), "J_0000_0100": (4, 4), "K_0100_0200": (4, 4), "L_last_hour_0200": (4, 4),
}


def halves(s):
    s = s.sort_index(); n = len(s)
    return s.iloc[: n // 2], s.iloc[n // 2:]


def fmt_prop(v):
    n, k, p, ci = prop(v)
    return f"{k}/{n}={p:.2f} CI[{ci[0]:.2f},{ci[1]:.2f}]"


def main():
    S = {sym: load(sym) for sym in ("NQ", "ES")}
    lines = []
    P = lambda *a: (print(*a), lines.append(" ".join(str(x) for x in a)))

    # ---------- Q1: quarter-hour histogram ----------
    for sym, (s, b) in S.items():
        P(f"\n===== {sym}: n={len(s)} sessions {s.index.min().date()}..{s.index.max().date()}; EDT={int(s.is_dst.sum())} EST={int((1-s.is_dst).sum())}")
        hist = pd.DataFrame({"q": range(36)})
        hist["label_et"] = hist["q"].map(qlabel)
        hist["n_high"] = hist["q"].map(s["hi_q"].value_counts()).fillna(0).astype(int)
        hist["n_low"] = hist["q"].map(s["lo_q"].value_counts()).fillna(0).astype(int)
        hist["pct_high"] = hist["n_high"] / len(s) * 100; hist["pct_low"] = hist["n_low"] / len(s) * 100
        hist["p_binom_high_vs_uniform"] = [binom_p(k, len(s), 1 / 36) for k in hist["n_high"]]
        hist["p_binom_low_vs_uniform"] = [binom_p(k, len(s), 1 / 36) for k in hist["n_low"]]
        hist.to_csv(f"{OUT}/{sym}_quarter_hist.csv", index=False)
        P(hist[(hist.n_high > 1) | (hist.n_low > 1)].to_string(index=False))
        # hour-of-session (k) x sub-quarter matrix
        mat_h = pd.crosstab(s["hi_k15"], s["hi_sub"]).reindex(index=range(9), columns=range(4), fill_value=0)
        mat_l = pd.crosstab(s["lo_k15"], s["lo_sub"]).reindex(index=range(9), columns=range(4), fill_value=0)
        mat_h.to_csv(f"{OUT}/{sym}_hour_x_quarter_high.csv"); mat_l.to_csv(f"{OUT}/{sym}_hour_x_quarter_low.csv")
        P("HIGH: hour k (rows) x quarter within hour (cols)\n" + mat_h.to_string())
        P("LOW : hour k (rows) x quarter within hour (cols)\n" + mat_l.to_string())
        # zones (Tokyo-clock aligned)
        s["hi_zone"] = [zone_of(q, d) for q, d in zip(s["hi_q"], s["is_dst"])]
        s["lo_zone"] = [zone_of(q, d) for q, d in zip(s["lo_q"], s["is_dst"])]
        zrows = []
        for z, (nq_edt, nq_est) in ZONE_Q.items():
            exp = (nq_edt * s.is_dst.sum() + nq_est * (1 - s.is_dst).sum()) / 36  # expected count under uniform
            kh = int((s.hi_zone == z).sum()); kl = int((s.lo_zone == z).sum())
            p0 = exp / len(s)
            zrows.append(dict(zone=z, quarters_edt=nq_edt, quarters_est=nq_est, expected_uniform=round(exp, 2),
                              n_high=kh, pct_high=round(kh / len(s) * 100, 1), p_high=round(binom_p(kh, len(s), p0), 4),
                              ci_high=boot_ci((s.hi_zone == z).astype(float)),
                              n_low=kl, pct_low=round(kl / len(s) * 100, 1), p_low=round(binom_p(kl, len(s), p0), 4),
                              ci_low=boot_ci((s.lo_zone == z).astype(float))))
        zt = pd.DataFrame(zrows); zt.to_csv(f"{OUT}/{sym}_zone_table.csv", index=False)
        P(zt.to_string(index=False))
        # halves for zones
        a, bb = halves(s)
        for z in ["A_reopen_1800", "L_last_hour_0200", "C_tokyo_open_q", "E_china_open_q", "F_china_data_0945_1015", "H_tokyo_lunch"]:
            P(f"  zone {z}: high A={int((a.hi_zone==z).sum())}/{len(a)} B={int((bb.hi_zone==z).sum())}/{len(bb)} | low A={int((a.lo_zone==z).sum())}/{len(a)} B={int((bb.lo_zone==z).sum())}/{len(bb)}")
        S[sym] = (s, b)

    # ---------- Q7: hourly base rates on the window vs the 579-session population ----------
    pop = {"NQ": dict(hi_k0=.235, hi_k8=.244, lo_k0=.311, lo_k8=.202, high_by_tko=.41, low_by_tko=.48, hi_first=.46)}
    for sym, (s, b) in S.items():
        x = pd.read_csv(f"./research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True)
        xw = x.loc[s.index]
        rows = []
        pr = pop.get(sym, {})
        def add(name, v, p0=None):
            n, k, p, ci = prop(v)
            rows.append(dict(stat=name, n=n, k=k, rate=round(p, 3), ci90=ci, pop_rate=p0, p_vs_pop=round(binom_p(k, n, p0), 4) if p0 else None))
        add("high_in_first_bar(k=0)", xw.high_in_first_bar, pr.get("hi_k0"))
        add("high_in_last_bar(k=8)", xw.high_in_last_bar, pr.get("hi_k8"))
        add("low_in_first_bar(k=0)", xw.low_in_first_bar, pr.get("lo_k0"))
        add("low_in_last_bar(k=8)", xw.low_in_last_bar, pr.get("lo_k8"))
        add("high_by_tokyo_open", xw.high_by_tokyo_open, pr.get("high_by_tko"))
        add("low_by_tokyo_open", xw.low_by_tokyo_open, pr.get("low_by_tko"))
        add("hi_first", xw.hi_first, pr.get("hi_first"))
        add("high_above_rth_high", xw.high_above_rth_high, .32 if sym == "NQ" else None)
        add("low_below_rth_low", xw.low_below_rth_low, .25 if sym == "NQ" else None)
        add("first_or_last_bar_high", ((xw.hi_k == 0) | (xw.hi_k == 8)).astype(float), (.235 + .244) if sym == "NQ" else None)
        add("first_or_last_bar_low", ((xw.lo_k == 0) | (xw.lo_k == 8)).astype(float), (.311 + .202) if sym == "NQ" else None)
        t = pd.DataFrame(rows); t.to_csv(f"{OUT}/{sym}_window_vs_population.csv", index=False)
        P(f"\n===== {sym}: window hourly base rates vs population"); P(t.to_string(index=False))
        P(f"  medians: hi_bp {xw.hi_bp.median():.1f} (pop +27) lo_bp {xw.lo_bp.median():.1f} (pop -23) rng_bp {xw.rng_bp.median():.1f} (pop 62); rng CI {boot_ci(xw.rng_bp, np.median)}")
        P("  hi_k dist %:", (xw.hi_k.value_counts(normalize=True).reindex(range(9), fill_value=0) * 100).round(1).tolist())
        P("  lo_k dist %:", (xw.lo_k.value_counts(normalize=True).reindex(range(9), fill_value=0) * 100).round(1).tolist())
        P("  population hi_k %: 23.5, 8.1, 11.1, 8.6, 5.2, 5.5, 5.5, 8.1, 24.4 ; lo_k %: 31.1, 8.6, 10.7, 7.4, 6.4, 3.5, 3.5, 8.6, 20.2")

    # ---------- Q2: hourly first-bar / last-bar extremes decomposed into quarters ----------
    for sym, (s, b) in S.items():
        P(f"\n===== {sym}: first/last hourly bar decomposition")
        fh = s[s.hi_k15 == 0]; fl = s[s.lo_k15 == 0]
        P(f"  high in k=0: n={len(fh)}; quarter 18:00 = {fmt_prop(fh.hi_sub==0)}; 18:15={int((fh.hi_sub==1).sum())} 18:30={int((fh.hi_sub==2).sum())} 18:45={int((fh.hi_sub==3).sum())}")
        P(f"     of which the 18:00 OPEN print itself is the session high: {fmt_prop(fh.open_is_high)}")
        P(f"  low  in k=0: n={len(fl)}; quarter 18:00 = {fmt_prop(fl.lo_sub==0)}; 18:15={int((fl.lo_sub==1).sum())} 18:30={int((fl.lo_sub==2).sum())} 18:45={int((fl.lo_sub==3).sum())}")
        P(f"     of which the 18:00 OPEN print itself is the session low: {fmt_prop(fl.open_is_low)}")
        P(f"  all sessions: open print is the high {fmt_prop(s.open_is_high)}, open print is the low {fmt_prop(s.open_is_low)}")
        lh = s[s.hi_k15 == 8]; ll = s[s.lo_k15 == 8]
        P(f"  high in k=8: n={len(lh)}; sub-quarter counts 02:00/02:15/02:30/02:45 = {[int((lh.hi_sub==i).sum()) for i in range(4)]}; last quarter {fmt_prop(lh.hi_sub==3)}")
        P(f"  low  in k=8: n={len(ll)}; sub-quarter counts = {[int((ll.lo_sub==i).sum()) for i in range(4)]}; last quarter {fmt_prop(ll.lo_sub==3)}")
        # overall first-15m and last-15m shares
        P(f"  session high in 18:00-18:15 bar: {fmt_prop(s.hi_q==0)} ; low: {fmt_prop(s.lo_q==0)}")
        P(f"  session high in 02:45-03:00 bar: {fmt_prop(s.hi_q==35)} ; low: {fmt_prop(s.lo_q==35)}")
        P(f"  high in first OR last 15m: {fmt_prop((s.hi_q==0)|(s.hi_q==35))} ; low: {fmt_prop((s.lo_q==0)|(s.lo_q==35))}")
        a, bb = halves(s)
        P(f"  halves: hi_q==0 A={int((a.hi_q==0).sum())}/{len(a)} B={int((bb.hi_q==0).sum())}/{len(bb)}; lo_q==0 A={int((a.lo_q==0).sum())}/{len(a)} B={int((bb.lo_q==0).sum())}/{len(bb)}; hi_q==35 A={int((a.hi_q==35).sum())} B={int((bb.hi_q==35).sum())}; lo_q==35 A={int((a.lo_q==35).sum())} B={int((bb.lo_q==35).sum())}")
        P(f"  ex-splice-flag: hi_q==0 {fmt_prop(s.drop(SPLICE_FLAG, errors='ignore').hi_q==0)} lo_q==0 {fmt_prop(s.drop(SPLICE_FLAG, errors='ignore').lo_q==0)}")

    # ---------- Q3: first-15-minute high/low hold; stop-runs ----------
    for sym, (s, b) in S.items():
        P(f"\n===== {sym}: first-15m range as the session extreme")
        rows = []
        for side, hold, brk, sr, closeback in [("high", "f15_high_holds", "brk_hi_bp", "hi_stoprun", "close_below_f15hi"),
                                                ("low", "f15_low_holds", "brk_lo_bp", "lo_stoprun", "close_above_f15lo")]:
            broken = s[s[brk] > 0]
            small = broken[broken[brk] < 10]
            rows.append(dict(side=side, n=len(s), holds=int(s[hold].sum()), holds_rate=round(s[hold].mean(), 3), holds_ci=boot_ci(s[hold]),
                             broken=len(broken), broken_lt10bp=len(small), broken_lt10bp_rate_of_all=round(len(small) / len(s), 3),
                             stoprun_lt10_and_reversed=int(s[sr].sum()), stoprun_rate_of_all=round(s[sr].mean(), 3), stoprun_ci=boot_ci(s[sr]),
                             broken_lt20bp=int((broken[brk] < 20).sum()),
                             median_break_bp=round(broken[brk].median(), 1), q25_break=round(broken[brk].quantile(.25), 1), q75_break=round(broken[brk].quantile(.75), 1),
                             close_back_inside_f15_when_broken=round(broken[closeback].mean(), 3) if len(broken) else np.nan))
        t = pd.DataFrame(rows); t.to_csv(f"{OUT}/{sym}_f15_hold.csv", index=False); P(t.to_string(index=False))
        P(f"  f15 range bp median {s.f15_rng_bp.median():.1f}; session range median {s.rng_bp.median():.1f}; f15/session range median {(s.f15_rng_bp/s.rng_bp).median():.2f}")
        # knowable-at-18:15 conditioning: f15 bar direction
        up = s[s.f15_ret_bp > 0]; dn = s[s.f15_ret_bp < 0]
        P(f"  P(f15 high holds | f15 bar down) = {fmt_prop(dn.f15_high_holds)} ; | f15 bar up = {fmt_prop(up.f15_high_holds)}")
        P(f"  P(f15 low  holds | f15 bar up)   = {fmt_prop(up.f15_low_holds)} ; | f15 bar down = {fmt_prop(dn.f15_low_holds)}")
        # either side holds
        P(f"  P(f15 high OR low holds) = {fmt_prop((s.f15_high_holds==1)|(s.f15_low_holds==1))}; both = {fmt_prop((s.f15_high_holds==1)&(s.f15_low_holds==1))}")
        a, bb = halves(s)
        P(f"  halves: high holds A={int(a.f15_high_holds.sum())}/{len(a)} B={int(bb.f15_high_holds.sum())}/{len(bb)}; low holds A={int(a.f15_low_holds.sum())}/{len(a)} B={int(bb.f15_low_holds.sum())}/{len(bb)}; hi stoprun A={int(a.hi_stoprun.sum())} B={int(bb.hi_stoprun.sum())}; lo stoprun A={int(a.lo_stoprun.sum())} B={int(bb.lo_stoprun.sum())}")
        # first-hour (4 quarters) range hold, for comparison with the hourly first-bar rate
        P(f"  (check) hourly first-bar high rate = {fmt_prop(s.hi_k15==0)}, low = {fmt_prop(s.lo_k15==0)}")

    # ---------- Q4: extreme-bar signature at 15m ----------
    for sym, (s, b) in S.items():
        P(f"\n===== {sym}: 15m extreme-bar signature")
        # time-of-day adjusted volume / range: relative to the median of the same quarter over the window
        b = b.copy()
        b["vol_tod"] = b["vol"] / b.groupby("q")["vol"].transform("median")
        b["rng_tod"] = b["rng_bp"] / b.groupby("q")["rng_bp"].transform("median")
        newhi = b[b.q_since_hi == 0]; newlo = b[b.q_since_lo == 0]
        rows = []
        def cmp(name, grp, flag, cols):
            g1 = grp[grp[flag] == 1]; g0 = grp[grp[flag] == 0]
            for c in cols:
                u = mannwhitneyu(g1[c].dropna(), g0[c].dropna(), alternative="two-sided").pvalue
                rows.append(dict(set=name, feature=c, n_extreme=len(g1), n_other=len(g0), med_extreme=round(g1[c].median(), 3), med_other=round(g0[c].median(), 3),
                                 ci_extreme=boot_ci(g1[c], np.median), p_mwu=round(u, 4),
                                 frac_extreme_gt1p5=round((g1[c] > 1.5).mean(), 3) if "vol" in c or "rng" in c else None,
                                 frac_other_gt1p5=round((g0[c] > 1.5).mean(), 3) if "vol" in c or "rng" in c else None))
        cmp("new_running_high_bars", newhi, "is_hi_bar", ["vol_rel", "vol_tod", "rng_rel", "rng_tod", "wick_hi", "ret_bp"])
        cmp("new_running_low_bars", newlo, "is_lo_bar", ["vol_rel", "vol_tod", "rng_rel", "rng_tod", "wick_lo", "ret_bp"])
        cmp("all_bars", b, "is_hi_bar", ["vol_rel", "vol_tod", "rng_rel", "rng_tod", "wick_hi"])
        cmp("all_bars", b, "is_lo_bar", ["vol_rel", "vol_tod", "rng_rel", "rng_tod", "wick_lo"])
        t = pd.DataFrame(rows); t.to_csv(f"{OUT}/{sym}_extreme_bar_signature.csv", index=False); P(t.to_string(index=False))
        # the bar after the extreme
        P(f"  bar after HIGH: median ret {s.hi_next_ret_bp.median():.1f} bp CI {boot_ci(s.hi_next_ret_bp, np.median)}; P(ret<0)={fmt_prop(s.hi_next_ret_bp<0)}; P(closes below high-bar low)={fmt_prop(s.hi_next_closes_below_bar_low)}; vol_rel med {s.hi_next_vol_rel.median():.2f}; rng_rel med {s.hi_next_rng_rel.median():.2f}")
        P(f"  bar after LOW : median ret {s.lo_next_ret_bp.median():.1f} bp CI {boot_ci(s.lo_next_ret_bp, np.median)}; P(ret>0)={fmt_prop(s.lo_next_ret_bp>0)}; P(closes above low-bar high)={fmt_prop(s.lo_next_closes_above_bar_high)}; vol_rel med {s.lo_next_vol_rel.median():.2f}; rng_rel med {s.lo_next_rng_rel.median():.2f}")
        # baseline for 'bar after a new running high that did not hold'
        nh_hold = newhi[newhi.is_hi_bar == 1]; nh_fail = newhi[newhi.is_hi_bar == 0]
        P(f"  new-running-high bars: n hold={len(nh_hold)} fail={len(nh_fail)}; P(hold)={len(nh_hold)/len(newhi):.3f}")
        # next-bar return after a new running high that held vs failed
        b["next_ret"] = b.groupby("date")["ret_bp"].shift(-1)
        b["next_close"] = b.groupby("date")["close"].shift(-1)
        newhi = b[b.q_since_hi == 0]; newlo = b[b.q_since_lo == 0]
        for nm, grp, flag, sgn in [("after new high", newhi, "is_hi_bar", -1), ("after new low", newlo, "is_lo_bar", 1)]:
            g1 = grp[grp[flag] == 1]; g0 = grp[grp[flag] == 0]
            P(f"  next-bar ret {nm}: hold med {g1.next_ret.median():.1f} (P(sign reverses)={(sgn*g1.next_ret>0).mean():.2f}, n={g1.next_ret.notna().sum()}) vs fail med {g0.next_ret.median():.1f} (P={(sgn*g0.next_ret>0).mean():.2f}, n={g0.next_ret.notna().sum()})")
        # wick on extreme bar by quartile
        P(f"  high-bar wick median {s.hi_bar_wick.median():.2f} CI {boot_ci(s.hi_bar_wick, np.median)}; P(wick>0.5)={fmt_prop(s.hi_bar_wick>0.5)}; low-bar wick median {s.lo_bar_wick.median():.2f}; P(wick>0.5)={fmt_prop(s.lo_bar_wick>0.5)}")
        P(f"  high-bar vol_rel median {s.hi_bar_vol_rel.median():.2f} CI {boot_ci(s.hi_bar_vol_rel, np.median)} P(>1.5)={fmt_prop(s.hi_bar_vol_rel>1.5)}; low-bar vol_rel median {s.lo_bar_vol_rel.median():.2f} P(>1.5)={fmt_prop(s.lo_bar_vol_rel>1.5)}")
        P(f"  high-bar rng_rel median {s.hi_bar_rng_rel.median():.2f} P(>1.5)={fmt_prop(s.hi_bar_rng_rel>1.5)}; low-bar rng_rel median {s.lo_bar_rng_rel.median():.2f} P(>1.5)={fmt_prop(s.lo_bar_rng_rel>1.5)}")
        # excluding the q=0 and q=35 extremes (which are structurally high-volume)
        mid_h = s[(s.hi_q > 0) & (s.hi_q < 35)]; mid_l = s[(s.lo_q > 0) & (s.lo_q < 35)]
        P(f"  interior highs (n={len(mid_h)}): vol_rel med {mid_h.hi_bar_vol_rel.median():.2f} P(>1.5)={fmt_prop(mid_h.hi_bar_vol_rel>1.5)}, wick med {mid_h.hi_bar_wick.median():.2f}, next ret med {mid_h.hi_next_ret_bp.median():.1f}")
        P(f"  interior lows  (n={len(mid_l)}): vol_rel med {mid_l.lo_bar_vol_rel.median():.2f} P(>1.5)={fmt_prop(mid_l.lo_bar_vol_rel>1.5)}, wick med {mid_l.lo_bar_wick.median():.2f}, next ret med {mid_l.lo_next_ret_bp.median():.1f}")
        a, bb = halves(s)
        P(f"  halves hi_bar_vol_rel>1.5: A={fmt_prop(a.hi_bar_vol_rel>1.5)} B={fmt_prop(bb.hi_bar_vol_rel>1.5)}; lo: A={fmt_prop(a.lo_bar_vol_rel>1.5)} B={fmt_prop(bb.lo_bar_vol_rel>1.5)}")
        P(f"  halves next-bar after high ret<0: A={fmt_prop(a.hi_next_ret_bp<0)} B={fmt_prop(bb.hi_next_ret_bp<0)}; after low ret>0: A={fmt_prop(a.lo_next_ret_bp>0)} B={fmt_prop(bb.lo_next_ret_bp>0)}")
        S[sym] = (s, b)

    # ---------- Q5: time from high to low ----------
    for sym, (s, b) in S.items():
        P(f"\n===== {sym}: time between high and low (quarters; + = high first)")
        d = s.q_between; ad = d.abs() * 15
        P(f"  signed median {d.median()} q; |dt| median {ad.median():.0f} min CI {boot_ci(ad, np.median)}; mean {ad.mean():.0f} min")
        P(f"  P(|dt|<=60min)={fmt_prop(ad<=60)}; P(|dt|<=120)={fmt_prop(ad<=120)}; P(|dt|>=6h)={fmt_prop(ad>=360)}; P(|dt|>=8h)={fmt_prop(ad>=480)}")
        P(f"  hi_first={fmt_prop(s.hi_first)}; same quarter={int(s.same_q.sum())}")
        P(f"  |dt| deciles (min): {np.percentile(ad,[10,25,50,75,90]).round(0).tolist()}")
        # by whether an extreme sits at q0 / q35
        edge = s[(s.hi_q==0)|(s.lo_q==0)|(s.hi_q==35)|(s.lo_q==35)]; inner = s.drop(edge.index)
        P(f"  sessions with an extreme at the first or last 15m: {len(edge)}/{len(s)} |dt| med {(edge.q_between.abs()*15).median():.0f}; interior-only sessions {len(inner)} |dt| med {(inner.q_between.abs()*15).median():.0f}")
        hist = pd.DataFrame({"abs_dt_min": ad, "signed_q": d}); hist.to_csv(f"{OUT}/{sym}_hi_lo_time.csv")
        a, bb = halves(s)
        P(f"  halves |dt| median: A={(a.q_between.abs()*15).median():.0f} B={(bb.q_between.abs()*15).median():.0f}; P(<=60) A={fmt_prop(a.q_between.abs()*15<=60)} B={fmt_prop(bb.q_between.abs()*15<=60)}")
        # given high first, time to low; after-high drop
        P(f"  drop after high median {s.drop_after_hi_bp.median():.1f} bp; rally after low median {s.rally_after_lo_bp.median():.1f} bp (hourly pop: 38 / 47)")

    # ---------- Q6: NQ vs ES ----------
    nq, es = S["NQ"][0], S["ES"][0]
    j = nq.join(es, lsuffix="_nq", rsuffix="_es", how="inner")
    P(f"\n===== NQ vs ES agreement (n={len(j)})")
    rows = []
    for side in ("hi", "lo"):
        dq = (j[f"{side}_q_nq"] - j[f"{side}_q_es"]).abs()
        rows.append(dict(side=side, same_quarter=fmt_prop(dq == 0), within_1q=fmt_prop(dq <= 1), within_1h=fmt_prop(dq <= 4),
                         same_hour_bar=fmt_prop(j[f"{side}_k15_nq"] == j[f"{side}_k15_es"]), same_zone=fmt_prop(j[f"{side}_zone_nq"] == j[f"{side}_zone_es"]),
                         median_abs_dq_min=dq.median() * 15, p90_abs_dq_min=np.percentile(dq, 90) * 15))
    t = pd.DataFrame(rows); t.to_csv(f"{OUT}/NQ_vs_ES_agreement.csv", index=False); P(t.to_string(index=False))
    P(f"  hi_first agrees: {fmt_prop(j.hi_first_nq == j.hi_first_es)}; f15 high holds both: NQ {fmt_prop(j.f15_high_holds_nq)} ES {fmt_prop(j.f15_high_holds_es)} agree {fmt_prop(j.f15_high_holds_nq==j.f15_high_holds_es)}")
    P(f"  f15 low holds agree {fmt_prop(j.f15_low_holds_nq==j.f15_low_holds_es)}; hi_q==0 agree {fmt_prop((j.hi_q_nq==0)==(j.hi_q_es==0))}")
    # where they disagree by > 1h, which one is earlier?
    dq = j.hi_q_nq - j.hi_q_es; P(f"  high: NQ earlier than ES by >4q in {int((dq < -4).sum())}, ES earlier in {int((dq > 4).sum())}")
    dq = j.lo_q_nq - j.lo_q_es; P(f"  low : NQ earlier than ES by >4q in {int((dq < -4).sum())}, ES earlier in {int((dq > 4).sum())}")
    a, bb = halves(j)
    for side in ("hi", "lo"):
        P(f"  halves same_quarter {side}: A={fmt_prop((a[f'{side}_q_nq']-a[f'{side}_q_es']).abs()==0)} B={fmt_prop((bb[f'{side}_q_nq']-bb[f'{side}_q_es']).abs()==0)}; within_1q A={fmt_prop((a[f'{side}_q_nq']-a[f'{side}_q_es']).abs()<=1)} B={fmt_prop((bb[f'{side}_q_nq']-bb[f'{side}_q_es']).abs()<=1)}")
    j[["hi_q_nq", "hi_q_es", "lo_q_nq", "lo_q_es", "hi_zone_nq", "hi_zone_es", "lo_zone_nq", "lo_zone_es", "f15_high_holds_nq", "f15_high_holds_es", "f15_low_holds_nq", "f15_low_holds_es"]].to_csv(f"{OUT}/NQ_vs_ES_sessions.csv")

    # ---------- event quarters (anecdotal, n tiny) ----------
    cal = pd.read_csv("./research/event_calendar.csv")
    cal["date"] = pd.to_datetime(cal["date"])
    s = S["NQ"][0]
    P("\n===== NQ: sessions with a scheduled Asia-hours event (event-date = the morning date; anecdotal)")
    ev = cal[(cal.date >= "2026-08-31") & (cal.date <= "2026-11-10") & cal.category.isin(["cn_data", "jp_data", "boj", "rba", "cn_policy"])]
    erows = []
    for _, e in ev.iterrows():
        gd = e.date
        m = s[pd.to_datetime(s.asia_gdate) == gd]
        if len(m) == 0: continue
        r = m.iloc[0]
        erows.append(dict(rth_date=m.index[0].date(), event=e.event, time_et=e.time_et, hi_q=qlabel(r.hi_q), lo_q=qlabel(r.lo_q), hi_zone=r.hi_zone, lo_zone=r.lo_zone, rng_bp=round(r.rng_bp, 0)))
    et = pd.DataFrame(erows); et.to_csv(f"{OUT}/NQ_event_sessions.csv", index=False); P(et.to_string(index=False))
    # China-data quarters: for sessions with cn_data at 21:30/21:45/22:00 EDT, fraction with an extreme in q14..16 (or q10..12 EST)
    cn = et[et.event.str.startswith("CN_") & et.time_et.notna()]
    P(f"  sessions with CN data in the 09:30-10:15 CST window: {len(cn)}; high in E/F zone: {int(cn.hi_zone.isin(['E_china_open_q','F_china_data_0945_1015']).sum())}, low in E/F zone: {int(cn.lo_zone.isin(['E_china_open_q','F_china_data_0945_1015']).sum())}")
    noncn = s[~pd.to_datetime(s.asia_gdate).isin(cal[cal.category=='cn_data'].date)]
    P(f"  non-CN-data sessions: {len(noncn)}; high in E/F: {int(noncn.hi_zone.isin(['E_china_open_q','F_china_data_0945_1015']).sum())}, low in E/F: {int(noncn.lo_zone.isin(['E_china_open_q','F_china_data_0945_1015']).sum())}")

    with open(f"{OUT}/analysis_log.txt", "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
