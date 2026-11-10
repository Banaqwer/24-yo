"""C5 (Sunday), C6 (Monday), C7 (FOMC eve), C8 (close location after down days), C9 (hi_first), C10 (timing skill), C11 (bar-0 asymmetry)."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "research/extremes/scripts/refute_context_regime")
from common import *


def block(f, preds, mask_a, mask_b, t, label, model=None):
    print(f"\n### {label}: {t}")
    r = rate_diff(f, mask_a, mask_b, t)
    print("overall:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, "CI diff", np.round(boot_diff_ci(f.loc[mask_a, t], f.loc[mask_b, t]), 3))
    print(fmt(rate_diff_by_quarter(f, mask_a, mask_b, t)))
    print(fmt(rate_diff_by_regime(f, mask_a, mask_b, t)))
    print("leave-5:", leave5_rate_diff(f, mask_a, mask_b, t))
    if model is not None and f"{t}|{model}" in preds.columns:
        y = f[t].values.astype(float); pb = preds[f"{t}|base"].values; p = preds[f"{t}|{model}"].values
        s, n = skill_from_preds(y, p, pb)
        print(f"OOS skill {model}: {s:.3f} (n={n}) by quarter:", {q: round(v, 3) for q, v in skill_by_quarter(f, y, p, pb)["skill"].items() if not np.isnan(v)})
        print("   top5:", skill_top5(f, y, p, pb))


for sym in ("NQ", "ES"):
    f = load(sym)
    preds = pd.read_csv(f"{LENS}/wf_logit_preds_{sym}.csv", index_col=0, parse_dates=True).reindex(f.index)
    raw = pd.read_csv(f"./research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    f = f.join(raw[["open_bp", "close_bp", "first_bar_ret_bp"]])
    print(f"\n==================== {sym}  n={len(f)} ====================")
    sun = f.sunday == 1; mon = f.monday == 1; rest_s = ~sun; rest_m = ~mon
    up = f.is_down == 0; dn = f.is_down == 1

    # ---------------- C5 Sunday -----------------
    print("\n=========== C5 SUNDAY ===========")
    for t in ("low_by_tokyo_open", "low_in_first_bar", "high_by_tokyo_open", "high_in_first_bar"):
        block(f, preds, sun, rest_s, t, "Sunday vs rest", model="uni:sunday_open")
    print("\nSunday drift by quarter: median close_bp, P(close_bp>0), n")
    print(fmt(f[sun].groupby("quarter")["close_bp"].agg(["median", lambda x: (x > 0).mean(), "count"]).reindex(QUARTERS).T))
    print("rest drift by quarter: median close_bp")
    print(fmt(f[rest_s].groupby("quarter")["close_bp"].agg(["median", lambda x: (x > 0).mean()]).reindex(QUARTERS).T))
    # is the Sunday low-early effect explained by drift?  condition on close_bp sign
    for lab, m in (("close up", f.close_bp > 0), ("close down", f.close_bp <= 0)):
        r = rate_diff(f, sun & m, rest_s & m, "low_by_tokyo_open")
        print(f"  low_by_tokyo | {lab}: sunday {r['p_a']:.3f} (n={r['n_a']}) rest {r['p_b']:.3f} (n={r['n_b']}) p={r['p']:.3g}")
    # DST split by quarter-ish
    print("  Sunday by DST:", f[sun].groupby("is_dst")["low_by_tokyo_open"].agg(["mean", "count"]).round(3).to_dict())
    print("  Rest by DST:", f[rest_s].groupby("is_dst")["low_by_tokyo_open"].agg(["mean", "count"]).round(3).to_dict())

    # ---------------- C6 Monday -----------------
    print("\n=========== C6 MONDAY ===========")
    for t in ("low_in_first_bar", "low_by_tokyo_open", "hi_first", "high_in_first_bar", "low_in_last_bar"):
        block(f, preds, mon, rest_m, t, "Monday vs rest", model="uni:dow")
    print("\nMonday drift by quarter: median close_bp, P(close_bp>0), n")
    print(fmt(f[mon].groupby("quarter")["close_bp"].agg(["median", lambda x: (x > 0).mean(), "count"]).reindex(QUARTERS).T))
    print("  Monday by DST low_by_tokyo:", f[mon].groupby("is_dst")["low_by_tokyo_open"].agg(["mean", "count"]).round(3).to_dict(),
          " hi_first:", f[mon].groupby("is_dst")["hi_first"].agg(["mean", "count"]).round(3).to_dict())
    print("  Rest by DST low_by_tokyo:", f[rest_m].groupby("is_dst")["low_by_tokyo_open"].agg(["mean", "count"]).round(3).to_dict())
    # Monday vs Tue-Thu only (excluding Sunday from the comparison group, since Sunday pushes the 'rest' rate up)
    tt = f.dow.isin([1, 2, 3])
    for t in ("low_in_first_bar", "low_by_tokyo_open", "hi_first"):
        r = rate_diff(f, mon, tt, t)
        print(f"  Monday vs Tue-Thu {t}: {r['p_a']:.3f} vs {r['p_b']:.3f} (n {r['n_a']}/{r['n_b']}) p={r['p']:.3g}")
        print("     by quarter:", fmt(rate_diff_by_quarter(f, mon, tt, t)[["n_a", "p_a", "p_b", "diff", "p"]].T))

    # ---------------- C7 FOMC eve -----------------
    print("\n=========== C7 FOMC-EVE ===========")
    fe = f.fomc_tomorrow == 1
    print("FOMC-eve dates:", [str(d.date()) for d in f.index[fe]])
    print("quarter counts:", f[fe].quarter.value_counts().reindex(QUARTERS).fillna(0).astype(int).to_dict())
    for t in ("hi_first", "close_top20", "close_bot20", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar"):
        block(f, preds, fe, ~fe, t, "FOMC-eve vs rest", model="uni:fomc_tomorrow" if f"{t}|uni:fomc_tomorrow" in preds.columns else None)
    print("per-night table:")
    print(fmt(f.loc[fe, ["quarter", "dow", "is_down", "hi_first", "close_top20", "close_loc", "close_bp", "hi_k", "lo_k", "hi_bp", "lo_bp", "regime"]]))
    # other 'eve' flags as placebo: tier1_data_tomorrow, boj_tonight
    for flag in ("tier1_data_tomorrow", "boj_tonight", "fomc_today"):
        m = f[flag] == 1
        print(f"  placebo {flag} (n={m.sum()}): hi_first {f.loc[m,'hi_first'].mean():.3f} close_top20 {f.loc[m,'close_top20'].mean():.3f} P(close_bp>0) {(f.loc[m,'close_bp']>0).mean():.3f}")

    # ---------------- C8 close location after down day -----------------
    print("\n=========== C8 CLOSE LOCATION ===========")
    for t in ("close_top20", "close_with_dir", "close_bot20"):
        block(f, preds, dn, up, t, "down vs up", model="uni:is_down")
    print("\nmean close_loc_in_dir by quarter x is_down:")
    print(fmt(f.groupby(["is_down", "quarter"])["close_loc_in_dir"].mean().unstack("quarter").reindex(columns=QUARTERS)))
    print("Spearman(is_down, close_loc_in_dir) by quarter:"); print(fmt(spearman_by_quarter(f, "is_down", "close_loc_in_dir").T))
    print(fmt(spearman_by_regime(f, "is_down", "close_loc_in_dir").T))
    print("leave-5 Spearman:", leave5_spearman(f, "is_down", "close_loc_in_dir"))
    print("Spearman(rth_ret_z, close_loc_in_dir) by quarter:"); print(fmt(spearman_by_quarter(f, "rth_ret_z", "close_loc_in_dir").T))
    # is it a drift artefact?  close_with_dir on up days = P(close_loc>=0.5); on down days = P(close_loc<=0.5). A positive drift mechanically lowers close_with_dir on down days.
    print("  median close_bp by is_down x quarter:")
    print(fmt(f.groupby(["is_down", "quarter"])["close_bp"].median().unstack("quarter").reindex(columns=QUARTERS)))
    print("  P(close_bp>0) up / down:", (f.loc[up, 'close_bp'] > 0).mean().round(3), (f.loc[dn, 'close_bp'] > 0).mean().round(3))

    # ---------------- C9 hi_first -----------------
    print("\n=========== C9 HI_FIRST ===========")
    block(f, preds, up, dn, "hi_first", "up vs down", model="uni:is_down")
    print("hi_first by dow x quarter:")
    print(fmt(f.groupby(["dow", "quarter"])["hi_first"].mean().unstack("quarter").reindex(columns=QUARTERS)))
    print("hi_first by dow overall:", f.groupby("dow")["hi_first"].agg(["mean", "count"]).round(3).to_dict())
    for mdl in ("uni:dow", "uni:is_down", "compact", "levels"):
        y = f["hi_first"].values.astype(float); pb = preds["hi_first|base"].values; p = preds[f"hi_first|{mdl}"].values
        s, n = skill_from_preds(y, p, pb)
        print(f"  OOS skill {mdl}: {s:.3f} by quarter:", {q: round(v, 3) for q, v in skill_by_quarter(f, y, p, pb)["skill"].items() if not np.isnan(v)})

    # ---------------- C10 timing not predictable -----------------
    print("\n=========== C10 TIMING SKILL ===========")
    tt_targets = ["high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar", "high_by_tokyo_open", "low_by_tokyo_open"]
    unis = [c.split("|", 1)[1] for c in preds.columns if c.startswith("high_in_first_bar|uni:")]
    rows = []
    for t in tt_targets:
        y = f[t].values.astype(float); pb = preds[f"{t}|base"].values
        best = []
        for u in unis + ["compact", "levels"]:
            p = preds[f"{t}|{u}"].values
            s, n = skill_from_preds(y, p, pb)
            bq = skill_by_quarter(f, y, p, pb)["skill"].dropna()
            rows.append(dict(target=t, model=u, skill=s, n_q_pos=(bq > 0.02).sum(), n_q_neg=(bq < -0.02).sum(), max_q=bq.max(), min_q=bq.min()))
    R = pd.DataFrame(rows)
    print("single-feature models with OOS skill > 0.02 on any timing target:")
    print(fmt(R[(R.skill > 0.02) & (R.model != "compact")].sort_values("skill", ascending=False)))
    print("compact / levels by target:")
    print(fmt(R[R.model.isin(["compact", "levels"])]))
    print("count of (target, model) with skill>0.02:", int((R.skill > 0.02).sum()), "of", len(R))
    # per-quarter: does any single feature show consistent skill (>0.02 in >=5 of 8 OOS quarters)?
    print("features with skill>0.02 in >=5 OOS quarters:")
    print(fmt(R[R.n_q_pos >= 5]))

    # ---------------- C11 bar-0 asymmetry -----------------
    print("\n=========== C11 BAR-0 / BAR-8 ASYMMETRY ===========")
    f["_d0"] = f["low_in_first_bar"] - f["high_in_first_bar"]; f["_d8"] = f["high_in_last_bar"] - f["low_in_last_bar"]
    tab = f.groupby("quarter").agg(n=("_d0", "count"), low0=("low_in_first_bar", "mean"), high0=("high_in_first_bar", "mean"), d0=("_d0", "mean"),
                                   high8=("high_in_last_bar", "mean"), low8=("low_in_last_bar", "mean"), d8=("_d8", "mean"), med_close=("close_bp", "median")).reindex(QUARTERS)
    # paired sign test p for d0, d8 per quarter
    def sgn_p(x):
        x = x.dropna(); pos = int((x > 0).sum()); neg = int((x < 0).sum())
        return stats.binomtest(pos, pos + neg, 0.5).pvalue if pos + neg > 0 else np.nan
    tab["p_d0"] = [sgn_p(f.loc[f.quarter == q, "_d0"]) for q in QUARTERS]; tab["p_d8"] = [sgn_p(f.loc[f.quarter == q, "_d8"]) for q in QUARTERS]
    print(fmt(tab))
    print("overall d0 (low0-high0):", f["_d0"].mean().round(3), "sign p", sgn_p(f["_d0"]), " d8 (high8-low8):", f["_d8"].mean().round(3), "sign p", sgn_p(f["_d8"]))
    for k in REGIMES:
        m = f.regime == k
        print(f"  {k}: in d0 {f.loc[m,'_d0'].mean():.3f} d8 {f.loc[m,'_d8'].mean():.3f} (n={m.sum()}) | ex d0 {f.loc[~m,'_d0'].mean():.3f} d8 {f.loc[~m,'_d8'].mean():.3f}")
    print(f"  sunday: d0 {f.loc[sun,'_d0'].mean():.3f} d8 {f.loc[sun,'_d8'].mean():.3f} | ex-sunday d0 {f.loc[~sun,'_d0'].mean():.3f} (p {sgn_p(f.loc[~sun,'_d0']):.3g}) d8 {f.loc[~sun,'_d8'].mean():.3f} (p {sgn_p(f.loc[~sun,'_d8']):.3g})")
    print(f"  ex-sunday ex-monday: d0 {f.loc[~sun & ~mon,'_d0'].mean():.3f} (p {sgn_p(f.loc[~sun & ~mon,'_d0']):.3g}) d8 {f.loc[~sun & ~mon,'_d8'].mean():.3f} (p {sgn_p(f.loc[~sun & ~mon,'_d8']):.3g}) n={(~sun & ~mon).sum()}")
    print("  leave-5 d0: remove 5 nights with low0=1,high0=0 ->", (f["_d0"].sum() - 5) / (len(f) - 5))
    # direction independence by quarter
    for t in ("high_in_first_bar", "low_in_first_bar"):
        print(f"  {t} up vs down by quarter:"); print(fmt(rate_diff_by_quarter(f, up, dn, t)[["n_a", "p_a", "p_b", "diff", "p"]].T))
        print("   overall:", rate_diff(f, up, dn, t))
    # relation between d0 and drift
    print("  Spearman(quarter median close_bp, quarter d0):", stats.spearmanr(tab["med_close"], tab["d0"]))
