"""T1, T2, T3, T4, T10: session-level (bar-0 / 18:00) claims. Quarter, leave-5-out, regime, Sunday."""
import sys
sys.path.insert(0, "research/extremes/scripts/refute_timing_regime")
import numpy as np, pandas as pd
from rcommon import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_colwidth", 200)

ALL = []
KEYS = ["claim", "n", "rate", "base", "lift", "p", "quarters", "n_quarters_same_sign", "n_quarters_eval", "flip_quarters_n>=25", "l5o_rate", "l5o_p", "l5o_kills", "sessions_to_kill", "top5_share_of_lift",
        "ex_tariff_apr25", "ex_iran_war_acute", "ex_nov5_crash", "ex_all_regimes", "in_tariff_apr25", "in_iran_war_acute", "in_nov5_crash", "sunday_only", "weekday_only", "H1", "H2", "verdict_rule"]


def prep(sym):
    x, p = load(sym)
    x = x[x.n_bars == 9].copy()
    p0 = p[p.k == 0].set_index("date")[["bar_close_loc", "bar_vol_rel", "bar_rng_rel", "pos_in_range"]]
    p0.columns = ["b0_close_loc", "b0_vol_rel", "b0_rng_rel", "b0_pos"]
    x = x.join(p0)
    x["date"] = x.index
    x["either0"] = ((x.hi_k == 0) | (x.lo_k == 0)).astype(int)
    down = x.is_down == 1
    x["cont_k"] = np.where(down, x.lo_k, x.hi_k); x["counter_k"] = np.where(down, x.hi_k, x.lo_k)
    x["cont_first"] = (x.cont_k == 0).astype(int); x["counter_first"] = (x.counter_k == 0).astype(int)
    x["b0_in_dir"] = np.where(down, -x.first_bar_ret_bp, x.first_bar_ret_bp)
    x["b0_rng_share"] = x.first_bar_rng_bp / (x.asia_rng_med20 * 1e4)
    x["ref_to_rth_high_bp"] = (x.lvl_rth_high / x.ref_close - 1) * 1e4
    x["ref_to_rth_low_bp"] = -(x.lvl_rth_low / x.ref_close - 1) * 1e4
    return x


for sym in ["NQ", "ES"]:
    x = prep(sym)
    print(f"\n\n############################ {sym}  full sessions n={len(x)} ############################")
    print("sessions per quarter:", x.q.value_counts().sort_index().to_dict())
    print("regime counts:", x.regime.value_counts().to_dict(), "| sunday:", int(x.sunday_open.sum()))

    # ---------------- T1 ----------------
    print("\n=============== T1: bar-0 close location ===============")
    cl = x.b0_close_loc
    for lab, m, oc in [("T1 close_loc>=0.8 -> low in bar0", cl >= 0.8, "low_in_first_bar"), ("T1 close_loc>=0.8 -> high in bar0 (neg)", cl >= 0.8, "high_in_first_bar"),
                       ("T1 close_loc<0.2 -> high in bar0", cl < 0.2, "high_in_first_bar"), ("T1 close_loc<0.2 -> low in bar0 (neg)", cl < 0.2, "low_in_first_bar"),
                       ("T1 0.2-0.5 -> high in bar0", (cl >= 0.2) & (cl < 0.5), "high_in_first_bar"), ("T1 0.5-0.8 -> high in bar0 (neg)", (cl >= 0.5) & (cl < 0.8), "high_in_first_bar")]:
        d = rate_check(x, m, oc, f"{sym} {lab}"); ALL.append(d); print(); show(d, KEYS)
    # monotone ordering of the 4 buckets per quarter (high in bar0 should fall with close_loc; low should rise)
    print("\nT1 per-quarter bucket rates (high_in_first_bar | <0.2, 0.2-0.5, 0.5-0.8, >=0.8) and (low_in_first_bar | same):")
    for q in sorted(x.q.unique()):
        dq = x[x.q == q]
        hs = [dq[(dq.b0_close_loc >= a) & (dq.b0_close_loc < b)].high_in_first_bar.mean() for a, b in [(-1, .2), (.2, .5), (.5, .8), (.8, 2)]]
        ls = [dq[(dq.b0_close_loc >= a) & (dq.b0_close_loc < b)].low_in_first_bar.mean() for a, b in [(-1, .2), (.2, .5), (.5, .8), (.8, 2)]]
        ns = [int(((dq.b0_close_loc >= a) & (dq.b0_close_loc < b)).sum()) for a, b in [(-1, .2), (.2, .5), (.5, .8), (.8, 2)]]
        print(f"  {q}: high {np.round(hs, 2)}  low {np.round(ls, 2)}  n {ns}  mono_high={all(np.diff(hs) <= 0)} mono_low={all(np.diff(ls) >= 0)}")

    # ---------------- T2 ----------------
    print("\n=============== T2: bar-0 signed return ===============")
    fb = x.first_bar_ret_bp
    for lab, m, oc in [("T2 ret>+20 -> low in bar0", fb > 20, "low_in_first_bar"), ("T2 ret<-20 -> high in bar0", fb < -20, "high_in_first_bar"),
                       ("T2 b0 against RTH >10 -> counter extreme in bar0", x.b0_in_dir < -10, "counter_first"), ("T2 b0 with RTH >10 -> cont extreme in bar0", x.b0_in_dir > 10, "cont_first"),
                       ("T2 ret>+20 -> high in bar0 (neg)", fb > 20, "high_in_first_bar"), ("T2 ret<-20 -> low in bar0 (neg)", fb < -20, "low_in_first_bar")]:
        d = rate_check(x, m, oc, f"{sym} {lab}"); ALL.append(d); print(); show(d, KEYS)
    # does T2 add to T1?  within close_loc>=0.8, does ret>20 raise P(low in bar0)?
    print("\nT2 incremental over T1: P(low in bar0 | close_loc>=0.8) by first_bar_ret bucket")
    d = x[x.b0_close_loc >= 0.8]
    for lab, m in [("ret<=5", d.first_bar_ret_bp <= 5), ("5-20", (d.first_bar_ret_bp > 5) & (d.first_bar_ret_bp <= 20)), (">20", d.first_bar_ret_bp > 20)]:
        print(f"  {lab}: {d[m].low_in_first_bar.mean():.3f} (n={int(m.sum())})  H1 {d[m & (d.half=='H1')].low_in_first_bar.mean():.2f} H2 {d[m & (d.half=='H2')].low_in_first_bar.mean():.2f}")
    print("T2 within ret>20: P(low in bar0) by close_loc")
    d = x[x.first_bar_ret_bp > 20]
    for lab, m in [("close_loc<0.8", d.b0_close_loc < 0.8), ("close_loc>=0.8", d.b0_close_loc >= 0.8)]:
        print(f"  {lab}: {d[m].low_in_first_bar.mean():.3f} (n={int(m.sum())})")

    # ---------------- T3 ----------------
    print("\n=============== T3: bar-0 range share ===============")
    sh = x.b0_rng_share
    xs = x[sh.notna()].copy()
    sh = xs.b0_rng_share
    for lab, m, oc in [("T3 share>=0.5 -> either extreme in bar0", sh >= 0.5, "either0"), ("T3 share 0.15-0.3 -> either in bar0 (neg)", (sh >= 0.15) & (sh < 0.3), "either0"),
                       ("T3 share>=0.5 -> high in bar0", sh >= 0.5, "high_in_first_bar"), ("T3 share>=0.5 -> low in bar0", sh >= 0.5, "low_in_first_bar"),
                       ("T3 share>=0.5 -> high in bar8 (neg?)", sh >= 0.5, "high_in_last_bar"), ("T3 share>=0.5 -> low in bar8 (neg?)", sh >= 0.5, "low_in_last_bar")]:
        d = rate_check(xs, m, oc, f"{sym} {lab}"); ALL.append(d); print(); show(d, KEYS)
    print("\nT3: share>=0.5 vs 0.15-0.3 contrast per quarter (either0):")
    for q in sorted(xs.q.unique()):
        dq = xs[xs.q == q]
        a = dq[dq.b0_rng_share >= 0.5].either0; b = dq[(dq.b0_rng_share >= 0.15) & (dq.b0_rng_share < 0.3)].either0
        print(f"  {q}: >=0.5 {a.mean():.2f} (n={len(a)}) | 0.15-0.3 {b.mean():.2f} (n={len(b)}) | diff {a.mean()-b.mean():+.2f}")
    print("T3 first-bar range share distribution: Sunday vs weekday median:", xs[xs.sunday_open == 1].b0_rng_share.median().round(2), xs[xs.sunday_open == 0].b0_rng_share.median().round(2))
    # is T3 mechanical? bar-0 range share vs session range share: P(either0) vs share of bar0 range in the final session range
    xs["b0_share_of_session"] = xs.first_bar_rng_bp / xs.rng_bp
    print("T3 ex-post: median bar0 range / session range when either0=1:", xs[xs.either0 == 1].b0_share_of_session.median().round(2), " when 0:", xs[xs.either0 == 0].b0_share_of_session.median().round(2))

    # ---------------- T4 ----------------
    print("\n=============== T4: 18:00 features vs first/last-bar timing (negative claim) + sunday_open ===============")
    for lab, m, oc in [("T4 sunday_open -> low in bar0", x.sunday_open == 1, "low_in_first_bar"), ("T4 sunday_open -> high in bar0", x.sunday_open == 1, "high_in_first_bar"),
                       ("T4 sunday_open -> low in bar8", x.sunday_open == 1, "low_in_last_bar"), ("T4 sunday_open -> high in bar8", x.sunday_open == 1, "high_in_last_bar"),
                       ("T4 rth_lo_hour late tercile -> low in bar0", x.rth_lo_hour > x.rth_lo_hour.quantile(2/3), "low_in_first_bar")]:
        d = rate_check(x, m, oc, f"{sym} {lab}"); ALL.append(d); print(); show(d, KEYS)
    # per-quarter consistency scan of the lens' 18:00 scan: how many 18:00 conditionals have the same sign of lift in >=8 of 9 quarters?
    feat18 = ["is_down", "mag", "rth_ret", "ext_in_dir", "vwap_in_dir", "clv", "post_ret", "post_in_dir", "late_day_rev", "rth_range_atr", "vix", "vix_z20", "rv_ratio", "abs_streak", "rth_vol_rel", "asia_rng_med20", "is_dst",
              "sunday_open", "gap_open", "gap_in_dir", "stretch20_in_dir", "ret5_in_dir", "prior_asia_in_dir", "overnight_in_dir", "n225_in_dir", "sox_in_dir", "yen_in_dir", "yield_in_dir", "vix_consistent", "close_vs_vwap", "rth_hi_hour", "rth_lo_hour",
              "close_vs_prior_asia_high", "close_vs_prior_asia_low", "dist_20d_high", "dist_20d_low", "z_sma20", "day_ret", "usdjpy_chg", "n225_ret"]
    flags18 = ["fomc_today", "fed_minutes_today", "tier1_data_today", "tier2_data_today", "opex_today", "witching_today", "roll_today", "megacap_earnings_tonight", "election_today", "politics_today", "boj_tonight", "jp_data_tonight", "cn_data_tonight",
               "cn_policy_tonight", "rba_tonight", "fomc_tomorrow", "tier1_data_tomorrow", "tier2_data_tomorrow", "ecb_tomorrow", "boe_tomorrow", "opex_tomorrow", "holiday_tomorrow", "sunday_open", "pre_holiday", "month_end"]
    rows = []
    qs = sorted(x.q.unique())
    for oc in ["high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar"]:
        for f in feat18:
            v = x[f]
            if v.nunique() <= 2:
                conds = [(f"{f}==1", v == 1)]
            else:
                qq = v.quantile([1/3, 2/3]).values
                conds = [(f"{f} T1", v <= qq[0]), (f"{f} T3", v > qq[1])]
            for lab, m in conds:
                r_all, n_all, k_all = rate(m, x[oc]); base = x[oc].mean()
                sg = np.sign(r_all - base)
                same = 0; ev = 0
                for q in qs:
                    dq = x.q == q
                    rq, nq, _ = rate(m & dq, x[oc]); bq = x[dq][oc].mean()
                    if nq >= 5 and not np.isnan(rq): ev += 1; same += int(np.sign(rq - bq) == sg)
                rows.append(dict(outcome=oc, cond=lab, n=n_all, rate=r_all, base=base, lift=r_all - base, p=binom_p(k_all, n_all, base), q_same=same, q_eval=ev))
        for f in flags18:
            m = x[f] == 1
            r_all, n_all, k_all = rate(m, x[oc]); base = x[oc].mean(); sg = np.sign(r_all - base)
            same = 0; ev = 0
            for q in qs:
                dq = x.q == q
                rq, nq, _ = rate(m & dq, x[oc]); bq = x[dq][oc].mean()
                if nq >= 5 and not np.isnan(rq): ev += 1; same += int(np.sign(rq - bq) == sg)
            rows.append(dict(outcome=oc, cond=f"{f}==1", n=n_all, rate=r_all, base=base, lift=r_all - base, p=binom_p(k_all, n_all, base), q_same=same, q_eval=ev))
    S = pd.DataFrame(rows); S.to_csv(f"{OUT}/t4_{sym}_quarter_consistency.csv", index=False)
    S["frac_same"] = S.q_same / S.q_eval
    print(f"T4 scan: {len(S)} conditionals; with p<.05 & n>=30: {int(((S.p < .05) & (S.n >= 30)).sum())}; with >=8/9 quarters same sign & n>=30: {int(((S.q_same >= 8) & (S.q_eval >= 9) & (S.n >= 30)).sum())} (chance ~ {len(S) * 20 / 512:.1f})")
    print(S[(S.n >= 30) & (S.q_eval >= 8)].sort_values(["q_same", "p"], ascending=[False, True]).head(12).round(3).to_string())
    # OOS predictability check: logistic / GBM on 18:00 features, leave-one-quarter-out, AUC per outcome
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline
        F = [f for f in feat18 + flags18 if f in x.columns]
        F = list(dict.fromkeys(F))
        X = x[F].astype(float).fillna(x[F].astype(float).median())
        for oc in ["high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar"]:
            y = x[oc].values
            pl = np.zeros(len(x)); pg = np.zeros(len(x))
            for q in qs:
                te = (x.q == q).values; tr = ~te
                ml = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000)).fit(X[tr], y[tr]); pl[te] = ml.predict_proba(X[te])[:, 1]
                mg = HistGradientBoostingClassifier(max_depth=3, max_iter=100, learning_rate=0.05).fit(X[tr], y[tr]); pg[te] = mg.predict_proba(X[te])[:, 1]
            # H1->H2
            tr = (x.half == "H1").values; te = ~tr
            ml = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000)).fit(X[tr], y[tr]); a12 = roc_auc_score(y[te], ml.predict_proba(X[te])[:, 1])
            print(f"  T4 OOS AUC {oc:18s}: logit LOQO {roc_auc_score(y, pl):.3f} | GBM LOQO {roc_auc_score(y, pg):.3f} | logit H1->H2 {a12:.3f}")
    except Exception as e:
        print("sklearn failed", e)

    # ---------------- T10 ----------------
    print("\n=============== T10: 18:00 distance ladder -> P(break) and timing ===============")
    dh = x.ref_to_rth_high_bp; dl = x.ref_to_rth_low_bp
    for lab, m, oc in [("T10 ref->RTHhigh <10 -> high>RTH high", dh < 10, "high_above_rth_high"), ("T10 ref->RTHhigh >=100 -> high>RTH high (neg)", dh >= 100, "high_above_rth_high"),
                       ("T10 ref->RTHlow <10 -> low<RTH low", dl < 10, "low_below_rth_low"), ("T10 ref->RTHlow >=100 -> low<RTH low (neg)", dl >= 100, "low_below_rth_low"),
                       ("T10 timing: ref->RTHhigh <10 -> high in bar0", dh < 10, "high_in_first_bar"), ("T10 timing: ref->RTHhigh <10 -> high in bar8", dh < 10, "high_in_last_bar"),
                       ("T10 timing: ref->RTHhigh >=100 -> high in bar0", dh >= 100, "high_in_first_bar"), ("T10 timing: ref->RTHhigh >=100 -> high in bar8", dh >= 100, "high_in_last_bar"),
                       ("T10 timing: ref->RTHlow <10 -> low in bar0", dl < 10, "low_in_first_bar"), ("T10 timing: ref->RTHlow >=100 -> low in bar8", dl >= 100, "low_in_last_bar")]:
        d = rate_check(x, m, oc, f"{sym} {lab}"); ALL.append(d); print(); show(d, KEYS)
    print("\nT10 per-quarter ladder P(high>RTH high) for <10 / 10-25 / 25-50 / 50-100 / >=100 and Spearman(k vs rate):")
    for q in sorted(x.q.unique()):
        dq = x[x.q == q]
        rs = []; ns = []
        for a, b in [(-1e9, 10), (10, 25), (25, 50), (50, 100), (100, 1e9)]:
            m = (dq.ref_to_rth_high_bp >= a) & (dq.ref_to_rth_high_bp < b); rs.append(dq[m].high_above_rth_high.mean()); ns.append(int(m.sum()))
        print(f"  {q}: {np.round(rs, 2)} n={ns} mono={all(np.diff([r for r in rs if not np.isnan(r)]) <= 0)}")
    # timing: median hi_k by distance bucket per quarter? (too thin) -> pooled Kruskal
    from scipy.stats import kruskal
    b = pd.cut(x.ref_to_rth_high_bp, [-1e9, 10, 25, 50, 100, 1e9], labels=["<10", "10-25", "25-50", "50-100", ">=100"])
    print("T10 timing pooled: Kruskal hi_k by distance bucket p =", round(kruskal(*[x.hi_k[b == c].values for c in b.cat.categories]).pvalue, 3), "; mean hi_k by bucket:", x.groupby(b, observed=True).hi_k.mean().round(2).to_dict())
    b2 = pd.cut(x.ref_to_rth_low_bp, [-1e9, 10, 25, 50, 100, 1e9], labels=["<10", "10-25", "25-50", "50-100", ">=100"])
    print("T10 timing pooled: Kruskal lo_k by distance bucket p =", round(kruskal(*[x.lo_k[b2 == c].values for c in b2.cat.categories]).pvalue, 3), "; mean lo_k by bucket:", x.groupby(b2, observed=True).lo_k.mean().round(2).to_dict())
    # P(high by tokyo open) by bucket (another timing measure)
    print("T10 timing: P(high_by_tokyo_open) by bucket:", x.groupby(b, observed=True).high_by_tokyo_open.mean().round(2).to_dict(), " base", round(x.high_by_tokyo_open.mean(), 2))
    print("T10 timing: P(low_by_tokyo_open) by bucket:", x.groupby(b2, observed=True).low_by_tokyo_open.mean().round(2).to_dict(), " base", round(x.low_by_tokyo_open.mean(), 2))

R = pd.DataFrame(ALL); R.to_csv(f"{OUT}/r1_session_claims.csv", index=False)
print("\n\n=== SUMMARY r1 ===")
print(R[["claim", "n", "rate", "base", "p", "n_quarters_same_sign", "n_quarters_eval", "flip_quarters_n>=25", "l5o_kills", "sessions_to_kill", "verdict_rule"]].round(3).to_string())
