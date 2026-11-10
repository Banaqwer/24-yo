"""T5, T6, T7, T8 (hold part), T15: hourly-panel claims. Quarter, leave-5-out (sessions), regime, Sunday, plus LOQO AUC for T5."""
import sys
sys.path.insert(0, "research/extremes/scripts/refute_timing_regime")
import numpy as np, pandas as pd
from rcommon import *
from scipy import stats
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_colwidth", 200)

ALL = []
KEYS = ["claim", "n", "rate", "base", "lift", "p", "quarters", "n_quarters_same_sign", "n_quarters_eval", "flip_quarters_n>=25", "l5o_rate", "l5o_p", "l5o_kills", "sessions_to_kill", "top5_share_of_lift",
        "ex_tariff_apr25", "ex_iran_war_acute", "ex_nov5_crash", "ex_all_regimes", "in_tariff_apr25", "in_iran_war_acute", "in_nov5_crash", "sunday_only", "weekday_only", "H1", "H2", "verdict_rule"]

for sym in ["NQ", "ES"]:
    x, p = load(sym)
    p = p[(p.n_bars == 9) & (p.k <= 7)].copy()
    p["date"] = pd.to_datetime(p["date"])
    print(f"\n\n############################ {sym} panel rows n={len(p)} sessions={p.date.nunique()} ############################")

    # ---------------- T5: pos_in_range ----------------
    print("\n=============== T5: pos_in_range per k ===============")
    # per-k contrast pos<0.25 vs pos>=0.75 for high_done, by quarter: sign of (rate_low_pos - rate_high_pos)
    print("per-quarter contrast P(high_done|pos<.25) - P(high_done|pos>=.75), k=2..6 pooled and per k (n = rows pos<.25 / pos>=.75):")
    for q in sorted(p.q.unique()):
        dq = p[(p.q == q) & (p.k >= 2) & (p.k <= 6)]
        a = dq[dq.pos_in_range < .25].high_done; b = dq[dq.pos_in_range >= .75].high_done
        al = dq[dq.pos_in_range >= .75].low_done; bl = dq[dq.pos_in_range < .25].low_done
        perk = []
        for k in range(2, 7):
            dk = dq[dq.k == k]; ak = dk[dk.pos_in_range < .25].high_done; bk = dk[dk.pos_in_range >= .75].high_done
            perk.append(f"{ak.mean():.2f}/{bk.mean():.2f}" if len(ak) and len(bk) else "na")
        print(f"  {q}: high {a.mean():.2f} vs {b.mean():.2f} (n={len(a)}/{len(b)}) | low {al.mean():.2f} vs {bl.mean():.2f} (n={len(al)}/{len(bl)}) | per-k high: {' '.join(perk)}")
    for k in [2, 4, 6]:
        dk = p[p.k == k].copy()
        for lab, m, oc in [(f"T5 k={k} pos<0.25 -> high_done", dk.pos_in_range < .25, "high_done"), (f"T5 k={k} pos>=0.75 -> high_done (neg)", dk.pos_in_range >= .75, "high_done"),
                           (f"T5 k={k} pos>=0.75 -> low_done", dk.pos_in_range >= .75, "low_done"), (f"T5 k={k} pos<0.25 -> low_done (neg)", dk.pos_in_range < .25, "low_done")]:
            d = rate_check(dk, m, oc, f"{sym} {lab}"); ALL.append(d); print(); show(d, KEYS)
    # LOQO logistic AUC: per-k base, +bars_since, +full; also H1->H2 and H2->H1
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score, brier_score_loss
    feats = ["k", "bars_since_hi", "bars_since_lo", "pos_in_range", "run_rng_vs_med20", "bar_close_loc", "bar_vol_rel", "run_hi_above_rth_high", "run_lo_below_rth_low",
             "cum_ret_bp", "bar_ret_bp", "after_tokyo_open", "dist_rth_high_bp", "dist_rth_low_bp", "run_hi_bp", "run_lo_bp"]
    d = p.dropna(subset=feats).copy()
    print("\nT5 logistic AUC by held-out quarter (train = all other quarters):")
    rows = []
    for lab in ["high_done", "low_done"]:
        bs = "bars_since_hi" if lab == "high_done" else "bars_since_lo"
        for q in sorted(d.q.unique()):
            te = d.q == q; tr = ~te
            bk = d[tr].groupby("k")[lab].mean(); pb = d[te].k.map(bk)
            m1 = LogisticRegression(max_iter=2000).fit(d[tr][["k", bs]], d[tr][lab]); p1 = m1.predict_proba(d[te][["k", bs]])[:, 1]
            m2 = LogisticRegression(max_iter=5000).fit(d[tr][feats], d[tr][lab]); p2 = m2.predict_proba(d[te][feats])[:, 1]
            m3 = LogisticRegression(max_iter=5000).fit(d[tr][["k", bs, "pos_in_range"]], d[tr][lab]); p3 = m3.predict_proba(d[te][["k", bs, "pos_in_range"]])[:, 1]
            rows.append(dict(sym=sym, label=lab, q=q, n_test=int(te.sum()), auc_base=roc_auc_score(d[te][lab], pb), auc_k_bsh=roc_auc_score(d[te][lab], p1), auc_k_bsh_pos=roc_auc_score(d[te][lab], p3), auc_full=roc_auc_score(d[te][lab], p2),
                             brier_base=brier_score_loss(d[te][lab], pb), brier_k_bsh=brier_score_loss(d[te][lab], p1), brier_full=brier_score_loss(d[te][lab], p2)))
        # reverse split H2 -> H1
        tr = d.half == "H2"; te = ~tr
        m1 = LogisticRegression(max_iter=2000).fit(d[tr][["k", bs]], d[tr][lab]); p1 = m1.predict_proba(d[te][["k", bs]])[:, 1]
        m2 = LogisticRegression(max_iter=5000).fit(d[tr][feats], d[tr][lab]); p2 = m2.predict_proba(d[te][feats])[:, 1]
        rows.append(dict(sym=sym, label=lab, q="H2->H1", n_test=int(te.sum()), auc_k_bsh=roc_auc_score(d[te][lab], p1), auc_full=roc_auc_score(d[te][lab], p2)))
    A = pd.DataFrame(rows); A.to_csv(f"{OUT}/t5_{sym}_loqo_auc.csv", index=False); print(A.round(3).to_string())
    print("  min/median/max auc_full by quarter:", A[A.q != "H2->H1"].groupby("label").auc_full.agg(["min", "median", "max"]).round(3).to_dict())

    # ---------------- T6: 3-condition rule ----------------
    print("\n=============== T6: bars_since>=2 & far pos & rng>=1.0 ===============")
    d26 = p[(p.k >= 2) & (p.k <= 6)].copy()
    hi_rule = (d26.bars_since_hi >= 2) & (d26.pos_in_range < .35) & (d26.run_rng_vs_med20 >= 1.0)
    lo_rule = (d26.bars_since_lo >= 2) & (d26.pos_in_range > .65) & (d26.run_rng_vs_med20 >= 1.0)
    for lab, m, oc in [("T6 high rule (bsh>=2 & pos<.35 & rng>=1) -> high_done", hi_rule, "high_done"), ("T6 low rule -> low_done", lo_rule, "low_done"),
                       ("T6 bsh==0 -> high_done (neg)", d26.bars_since_hi == 0, "high_done"), ("T6 bsh==0 & rng>=1.2 -> high_done (neg)", (d26.bars_since_hi == 0) & (d26.run_rng_vs_med20 >= 1.2), "high_done"),
                       ("T6 bsl==0 -> low_done (neg)", d26.bars_since_lo == 0, "low_done"),
                       ("T6 bsh>=2 & pos<.35 & rng<0.6 -> high_done", (d26.bars_since_hi >= 2) & (d26.pos_in_range < .35) & (d26.run_rng_vs_med20 < 0.6), "high_done")]:
        d = rate_check(d26, m, oc, f"{sym} {lab}"); ALL.append(d); print(); show(d, KEYS)
    # does the rng>=1.0 condition add over bsh>=2 & pos<.35 within each quarter?
    print("\nT6 increment of rng>=1.0 over (bsh>=2 & pos<.35), per quarter: P(high_done | rng>=1) vs P(high_done | rng<1):")
    for q in sorted(d26.q.unique()):
        dq = d26[(d26.q == q) & (d26.bars_since_hi >= 2) & (d26.pos_in_range < .35)]
        a = dq[dq.run_rng_vs_med20 >= 1.0].high_done; b = dq[dq.run_rng_vs_med20 < 1.0].high_done
        print(f"  {q}: {a.mean():.3f} (n={len(a)}) vs {b.mean():.3f} (n={len(b)})")
    # failures of the high rule: list sessions (are the 3% misses clustered?)
    f = d26[hi_rule & (d26.high_done == 0)]
    print("T6 high-rule failures: rows", len(f), "sessions", f.date.nunique(), "by quarter:", f.groupby("q").size().to_dict(), "sunday:", int(f.sunday_open.sum()), "| regime:", f.regime.value_counts().to_dict())
    print("   remaining_up_bp on failures (median, max):", round(f.remaining_up_bp.median(), 1), round(f.remaining_up_bp.max(), 1))
    f = d26[lo_rule & (d26.low_done == 0)]
    print("T6 low-rule failures: rows", len(f), "sessions", f.date.nunique(), "by quarter:", f.groupby("q").size().to_dict(), "sunday:", int(f.sunday_open.sum()), "| regime:", f.regime.value_counts().to_dict())
    print("   remaining_down_bp on failures (median, min):", round(f.remaining_down_bp.median(), 1), round(f.remaining_down_bp.min(), 1))

    # ---------------- T7: volume x direction ----------------
    print("\n=============== T7: bar_vol_rel x direction ===============")
    d17 = p[(p.k >= 1) & (p.k <= 7) & p.bar_vol_rel.notna()].copy()
    hv_dn = (d17.bar_vol_rel >= 1.5) & (d17.bar_ret_bp < 0); lv_dn = (d17.bar_vol_rel < 1.5) & (d17.bar_ret_bp < 0)
    hv_up = (d17.bar_vol_rel >= 1.5) & (d17.bar_ret_bp >= 0); lv_up = (d17.bar_vol_rel < 1.5) & (d17.bar_ret_bp >= 0)
    # the claim's key contrast is hv_dn vs lv_dn (volume adds +15 pts on down bars) -> use base_mask = down bars
    for lab, m, oc, bm in [("T7 vol>=1.5 & down -> high_done (base = all down bars)", hv_dn, "high_done", d17.bar_ret_bp < 0),
                           ("T7 vol>=1.5 & up -> low_done (base = all up bars)", hv_up, "low_done", d17.bar_ret_bp >= 0),
                           ("T7 vol>=1.5 & up -> high_done (base = all up bars)", hv_up, "high_done", d17.bar_ret_bp >= 0),
                           ("T7 vol>=1.5 & down -> low_done (base = all down bars)", hv_dn, "low_done", d17.bar_ret_bp < 0)]:
        d = rate_check(d17, m, oc, f"{sym} {lab}", base_mask=bm); ALL.append(d); print(); show(d, KEYS)
    # confound: is the volume effect just bar size / close location?  stratify by bar_rng_rel and bar_close_loc
    print("\nT7 confound check: P(high_done | down bar) by vol bucket within bar_rng_rel strata and within bar_close_loc strata (k=1..7):")
    dn = d17[d17.bar_ret_bp < 0]
    for lab, strata in [("bar_rng_rel", pd.cut(dn.bar_rng_rel, [0, 0.8, 1.2, 1.8, 99])), ("bar_close_loc", pd.cut(dn.bar_close_loc, [-0.01, 0.25, 0.5, 1.01]))]:
        t = dn.groupby([strata, dn.bar_vol_rel >= 1.5], observed=True).high_done.agg(["mean", "size"]).round(3)
        print(f"  by {lab}:"); print(t.to_string())
    # partial: logistic high_done ~ k + bars_since_hi + bar_rng_rel + bar_close_loc + vol_hi, down bars only
    dn2 = dn.dropna(subset=["bar_rng_rel", "bar_close_loc", "bar_vol_rel"]).copy()
    dn2["vol_hi"] = (dn2.bar_vol_rel >= 1.5).astype(float); dn2["bar_rng_rel_c"] = dn2.bar_rng_rel.clip(upper=5)
    for cols in [["k", "bars_since_hi", "vol_hi"], ["k", "bars_since_hi", "bar_rng_rel_c", "bar_close_loc", "vol_hi"], ["k", "bars_since_hi", "bar_rng_rel_c", "bar_close_loc", "pos_in_range", "vol_hi"]]:
        lr = LogisticRegression(penalty=None, max_iter=5000).fit(dn2[cols].astype(float), dn2.high_done)
        # bootstrap CI of the vol_hi coefficient over sessions
        sess = dn2.date.unique(); coefs = []
        for _ in range(300):
            pick = RNG.choice(sess, size=len(sess), replace=True)
            bb = pd.concat([dn2[dn2.date == s] for s in pick])
            coefs.append(LogisticRegression(penalty=None, max_iter=5000).fit(bb[cols].astype(float), bb.high_done).coef_[0][-1])
        print(f"  logit high_done on down bars, {cols}: vol_hi coef {lr.coef_[0][-1]:+.3f} (session-bootstrap 90% CI {np.quantile(coefs, .05):+.3f}..{np.quantile(coefs, .95):+.3f})")
    print("T7 per-quarter: P(high_done | hv_dn) - P(high_done | lv_dn) and the low mirror:")
    for q in sorted(d17.q.unique()):
        dq = d17.q == q
        a = d17[hv_dn & dq].high_done; b = d17[lv_dn & dq].high_done; c = d17[hv_up & dq].low_done; e = d17[lv_up & dq].low_done
        print(f"  {q}: high {a.mean():.2f}-{b.mean():.2f}={a.mean()-b.mean():+.2f} (n={len(a)}/{len(b)}) | low {c.mean():.2f}-{e.mean():.2f}={c.mean()-e.mean():+.2f} (n={len(c)}/{len(e)})")

    # ---------------- T8: RTH break and hold ----------------
    print("\n=============== T8: run_hi_above_rth_high and hold ===============")
    for lab, m, oc in [("T8 run_hi_above_rth_high=1 -> high_done (claim: slightly lower)", d26.run_hi_above_rth_high == 1, "high_done"),
                       ("T8 run_lo_below_rth_low=1 -> low_done", d26.run_lo_below_rth_low == 1, "low_done")]:
        d = rate_check(d26, m, oc, f"{sym} {lab}"); ALL.append(d); print(); show(d, KEYS)
    bsh2 = d26.bars_since_hi >= 2; bsl2 = d26.bars_since_lo >= 2
    for lab, m, oc, bm in [("T8 break=1 & bsh>=2 -> high_done (base bsh>=2)", (d26.run_hi_above_rth_high == 1) & bsh2, "high_done", bsh2),
                           ("T8 lo-break=1 & bsl>=2 -> low_done (base bsl>=2)", (d26.run_lo_below_rth_low == 1) & bsl2, "low_done", bsl2)]:
        d = rate_check(d26, m, oc, f"{sym} {lab}", base_mask=bm); ALL.append(d); print(); show(d, KEYS)
    # the break flag is confounded with pos_in_range (a running high above the RTH high tends to be a recent/near high) -> stratify
    print("T8 stratified: P(high_done | break, pos_in_range bucket, bsh>=2) k=2..6:")
    t = d26[bsh2].groupby([pd.cut(d26[bsh2].pos_in_range, [-0.01, .35, .65, 1.01]), d26[bsh2].run_hi_above_rth_high], observed=True).high_done.agg(["mean", "size"]).round(3)
    print(t.to_string())

    # ---------------- T15: remaining move ----------------
    print("\n=============== T15: remaining move when not done, by k ===============")
    rem = []
    for k in range(8):
        du = p[(p.k == k) & (p.high_done == 0)]; dd = p[(p.k == k) & (p.low_done == 0)]
        row = dict(k=k, n_up=len(du), up_med=du.remaining_up_bp.median(), up_p25=du.remaining_up_bp.quantile(.25), up_p75=du.remaining_up_bp.quantile(.75),
                   n_dn=len(dd), dn_med=dd.remaining_down_bp.median(), dn_p25=dd.remaining_down_bp.quantile(.25), dn_p75=dd.remaining_down_bp.quantile(.75))
        for q in sorted(p.q.unique()):
            row[f"up_{q}"] = du[du.q == q].remaining_up_bp.median(); row[f"dn_{q}"] = dd[dd.q == q].remaining_down_bp.median()
        row["up_sun"] = du[du.sunday_open == 1].remaining_up_bp.median(); row["up_wk"] = du[du.sunday_open == 0].remaining_up_bp.median()
        row["dn_sun"] = dd[dd.sunday_open == 1].remaining_down_bp.median(); row["dn_wk"] = dd[dd.sunday_open == 0].remaining_down_bp.median()
        row["up_exreg"] = du[du.regime == "normal"].remaining_up_bp.median(); row["dn_exreg"] = dd[dd.regime == "normal"].remaining_down_bp.median()
        # bootstrap CI of the median
        row["up_ci"] = boot_ci(du.remaining_up_bp.values, np.median); row["dn_ci"] = boot_ci(dd.remaining_down_bp.values, np.median)
        rem.append(row)
    REM = pd.DataFrame(rem); REM.to_csv(f"{OUT}/t15_{sym}_remaining_by_quarter.csv", index=False)
    print(REM[["k", "n_up", "up_med", "up_ci", "n_dn", "dn_med", "dn_ci", "up_sun", "up_wk", "dn_sun", "dn_wk", "up_exreg", "dn_exreg"]].round(1).to_string())
    qcols_up = [c for c in REM.columns if c.startswith("up_20")]; qcols_dn = [c for c in REM.columns if c.startswith("dn_20")]
    print("per-quarter medians, remaining UP | high not done (rows = k):"); print(REM[["k"] + qcols_up].round(0).to_string())
    print("per-quarter medians, remaining DOWN | low not done:"); print(REM[["k"] + qcols_dn].round(0).to_string())
    # monotone decay test per quarter: Spearman of median vs k over k=0..7
    print("Spearman(k, median remaining) per quarter (claim: negative for up, positive (towards 0) for down):")
    for cu, cd in zip(qcols_up, qcols_dn):
        su = stats.spearmanr(REM.k, REM[cu]).correlation; sd = stats.spearmanr(REM.k, REM[cd]).correlation
        print(f"  {cu[3:]}: up rho={su:+.2f}  down rho={sd:+.2f}  | up k0..7 {REM[cu].round(0).tolist()} | down {REM[cd].round(0).tolist()}")
    su = stats.spearmanr(REM.k, REM.up_med).correlation; sd = stats.spearmanr(REM.k, REM.dn_med).correlation
    print(f"  pooled: up rho={su:+.2f} down rho={sd:+.2f}; strictly decreasing up? {all(np.diff(REM.up_med) < 0)}; strictly shrinking down? {all(np.diff(REM.dn_med) > 0)}")
    # the claim says downside is larger at every k: check |dn_med| > up_med per k and per quarter
    print("  |down| > up at every k pooled:", all(-REM.dn_med > REM.up_med), "; per quarter count of k where |down|>up:", {cu[3:]: int((-REM[cd] > REM[cu]).sum()) for cu, cd in zip(qcols_up, qcols_dn)})
    # H1 vs H2 (the claim's own second half shows non-monotone downside)
    for hh in ["H1", "H2"]:
        ph = p[p.half == hh]
        ups = [ph[(ph.k == k) & (ph.high_done == 0)].remaining_up_bp.median() for k in range(8)]; dns = [ph[(ph.k == k) & (ph.low_done == 0)].remaining_down_bp.median() for k in range(8)]
        print(f"  {hh}: up {np.round(ups, 0).tolist()} down {np.round(dns, 0).tolist()}")

R = pd.DataFrame(ALL); R.to_csv(f"{OUT}/r2_panel_claims.csv", index=False)
print("\n\n=== SUMMARY r2 ===")
print(R[["claim", "n", "rate", "base", "p", "n_quarters_same_sign", "n_quarters_eval", "flip_quarters_n>=25", "l5o_rate", "l5o_kills", "sessions_to_kill", "verdict_rule"]].round(3).to_string())
