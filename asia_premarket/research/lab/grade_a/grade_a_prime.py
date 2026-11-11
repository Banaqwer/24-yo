"""Grade A prime: the rules of the four hypothesis groups applied jointly, paired against the honest baseline
(pnl_net_open), plus the honest-A anatomy, the attribution between specs, the trial ledger, Holm on the vault tests,
the deflated Sharpe ratio and the kill-switch reachability arithmetic.  Writer-stage script; reads only the per-night
files the groups wrote.

Run from the project root:  OMP_NUM_THREADS=1 python research/lab/grade_a/grade_a_prime.py

Rule layers (decision time 17:xx ET, every input listed in baseline_summary.json as 17:xx):
  geometry re-call H2 + H3 (h_geometry_nights.csv column H2H3_*): target cap 1.0 x med20_pts, CONTINUATION|wide removed,
     MEAN REVERSION|wide needs the raw ratio win_rate_on_resolution >= 0.80 (h_geometry H3_floor_convention);
  H3 alone (column H3_*);
  vetoes -> NO EDGE on the (re-)called night: H5 (|post_ret| > 0.3% or megacap_earnings_tonight == 1), H9 (pre_holiday == 1,
     i.e. the next CALENDAR day is a US holiday; calendar_features), D1 (MEAN REVERSION with Detector B pB_dir >= 0.70;
     CONTINUATION with pB_dir <= 0.10), where pB_dir = pB_high_above_cal on up-RTH nights and pB_low_below_cal on down nights.
Specs:
  S0 = honest baseline;  S1 = geometry re-call only (H2 + H3);  S2 = S1 + H5 + H9 (the four-rule spec of the first draft of the
  report, superseded: H2 is dead under LAB_DESIGN 2.6 and H3 is discovery-only under 12.3; kept for the attribution table);
  S3 = S2 + D1 (redundancy check; identical to S2 on NQ);  S4 = H5 + H9 + D1 on the baseline call;  S5 = H3 + H5 + H9 + D1;
  S6 = GRADE A PRIME (the paper-trading spec) = honest baseline + the two free vetoes H5 and H9, no geometry change;
  S7 = the SHADOW spec = H3 + H5 + H9 (no D1), logged nightly, not paper-traded.
Outputs: grade_a_prime_results.json, grade_a_prime_nights.csv (next to this script).
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(ROOT, "grade_a_prime_results.json")
OUT_CSV = os.path.join(ROOT, "grade_a_prime_nights.csv")

SPLITS = {"discovery": ("2025-04-01", "2026-05-31"), "vault": ("2026-06-01", "2026-11-06"),
          "full": ("2025-04-01", "2026-11-06")}
MONTHS = {"discovery": 14.0, "vault": 5.2, "full": 19.2}
POINT = {"NQ": 20.0, "ES": 50.0}
DRAWS = 2000
GRADES = ("A", "B", "C")
D1_BREAK, D1_HOLD = 0.70, 0.10
H5_POST = 0.003
KILL_TRAILING12 = -470.0          # LAB_DESIGN 12.3 item 5: trailing 12 Grade-A nights with net sum < -1.5 x 90 x sqrt(12)
DSR_N_EXTRA = 250                 # sensitivity line for the deflated Sharpe

SPECS = ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7")
SPEC_SRC = {"S0": "base", "S1": "H2H3", "S2": "H2H3", "S3": "H2H3", "S4": "base", "S5": "H3", "S6": "base", "S7": "H3"}
SRC_COLS = {
    "base": dict(grade="grade", pnl="base_pnl", pnl_hi="base_pnl_hi", traded="traded_open", kind="call", variant="variant", outcome="outcome_open"),
    "H2H3": dict(grade="H2H3_grade", pnl="H2H3_pnl_net_open", pnl_hi="H2H3_pnl_net_open_hicost", traded="H2H3_traded", kind="H2H3_kind",
                 variant="H2H3_variant", outcome="H2H3_outcome"),
    "H3": dict(grade="H3_grade", pnl="H3_pnl_net_open", pnl_hi="H3_pnl_net_open_hicost", traded="H3_traded", kind="H3_kind",
               variant="H3_variant", outcome="H3_outcome"),
}
SPEC_VETOES = {"S0": [], "S1": [], "S2": ["flag_H5", "flag_H9"], "S3": ["flag_H5", "flag_H9", "flag_D1_H2H3"],
               "S4": ["flag_H5", "flag_H9", "flag_D1_base"], "S5": ["flag_H5", "flag_H9", "flag_D1_H3"],
               "S6": ["flag_H5", "flag_H9"], "S7": ["flag_H5", "flag_H9"]}
SPEC_DESC = {
    "S0": "honest baseline (pnl_net_open)",
    "S1": "geometry re-call only: H2 target cap 1.0 x med20 + H3 (no CONTINUATION|wide; MEAN REVERSION|wide needs ratio >= 0.80)",
    "S2": "the four-rule spec of the first draft (S1 + free vetoes H5 and H9); SUPERSEDED: H2 is dead under LAB_DESIGN 2.6 (placebo) and H3 is discovery-only under 12.3; kept for attribution",
    "S3": "redundancy check: S2 + D1 Detector B veto (MR with pB_dir >= 0.70 -> NO EDGE; CONT with pB_dir <= 0.10 -> NO EDGE); identical to S2 on NQ",
    "S4": "free vetoes plus D1 on the baseline call (H5 + H9 + D1), no geometry change",
    "S5": "H3 alone (H2 cap not applied) + H5 + H9 + D1",
    "S6": "GRADE A PRIME = the paper-trading spec: honest baseline + the two free vetoes H5 (|post_ret| > 0.3% or megacap print) and H9 (pre_holiday); no geometry change, no D1",
    "S7": "SHADOW spec: H3 (no CONTINUATION|wide; MEAN REVERSION|wide needs ratio >= 0.80) + H5 + H9; no H2, no D1; logged nightly, not paper-traded",
}
# the attribution pairs (a minus b), paired per night on the A book and on the graded book
ATTRIBUTION_PAIRS = [("S6", "S0", "free vetoes H5 + H9 over the honest baseline (= GRADE A PRIME minus baseline)"),
                     ("S7", "S0", "shadow spec (H3 + H5 + H9) over the honest baseline"),
                     ("S7", "S6", "H3's increment inside the shadow spec, over the free vetoes"),
                     ("S2", "S0", "the superseded four-rule spec over the honest baseline"),
                     ("S2", "S6", "geometry layer (H2 + H3) increment over the free vetoes"),
                     ("S2", "S7", "H2's increment inside the superseded spec (S2 minus the H3-only shadow)"),
                     ("S2", "S5", "H2's increment with D1 in both legs (S2 minus S5; S5 = S7 on NQ)"),
                     ("S5", "S0", "S5 over the honest baseline")]


def rng():
    return np.random.default_rng(0)


def iso_week(dates):
    d = pd.to_datetime(dates)
    iso = d.dt.isocalendar()
    return (iso.year.astype(int) * 100 + iso.week.astype(int)).to_numpy()


def block_boot(diff, dates, draws=DRAWS):
    """ISO-week block bootstrap of the mean of a per-night series. Returns (mean, lo90, hi90, draws array)."""
    diff = np.asarray(diff, dtype=float)
    if len(diff) == 0:
        return 0.0, 0.0, 0.0, np.zeros(draws)
    wk = iso_week(dates)
    uniq = np.unique(wk)
    groups = [diff[wk == w] for w in uniq]
    g = rng()
    out = np.empty(draws)
    nb = len(groups)
    for i in range(draws):
        idx = g.integers(0, nb, nb)
        out[i] = np.concatenate([groups[j] for j in idx]).mean()
    return float(diff.mean()), float(np.percentile(out, 5)), float(np.percentile(out, 95)), out


def ci80(draws):
    return [float(np.percentile(draws, 10)), float(np.percentile(draws, 90))]


def one_sided_p(draws, sign):
    """Bootstrap p-value against zero in the predicted direction (sign = +1 or -1)."""
    draws = np.asarray(draws)
    if sign >= 0:
        return float((draws <= 0).mean())
    return float((draws >= 0).mean())


def series_stats(pnl, hicost=None, traded=None):
    pnl = np.asarray(pnl, dtype=float)
    n = len(pnl)
    if n == 0:
        return {"n": 0}
    sd = float(pnl.std(ddof=1)) if n > 1 else 0.0
    out = {"n": n, "win": float((pnl > 0).mean()), "avg": float(pnl.mean()), "total": float(pnl.sum()),
           "worst": float(pnl.min()), "best": float(pnl.max()), "sd": sd,
           "pts_per_sigma": float(pnl.mean() / sd) if sd > 0 else 0.0}
    if hicost is not None:
        h = np.asarray(hicost, dtype=float)
        out["avg_hicost"] = float(h.mean())
        out["total_hicost"] = float(h.sum())
    if traded is not None:
        out["untraded"] = int((np.asarray(traded) == 0).sum())
    return out


def usd_per_year(total, sym, split):
    return float(total * POINT[sym] * 12.0 / MONTHS[split])


def random_filter(base_pnl, kept_mask, draws=DRAWS):
    """Null for a rule that removes nights: remove the same count at random from the same population."""
    base_pnl = np.asarray(base_pnl, dtype=float)
    kept_mask = np.asarray(kept_mask, dtype=bool)
    n = len(base_pnl)
    n_removed = int((~kept_mask).sum())
    if n == 0 or n_removed == 0 or n_removed >= n:
        return {"n_population": n, "n_removed": n_removed, "percentile": None}
    actual = float(base_pnl[kept_mask].mean())
    g = rng()
    null = np.empty(draws)
    for i in range(draws):
        rm = g.choice(n, n_removed, replace=False)
        m = np.ones(n, dtype=bool)
        m[rm] = False
        null[i] = base_pnl[m].mean()
    return {"n_population": n, "n_removed": n_removed, "actual_kept_avg": actual,
            "null_mean": float(null.mean()), "null_p95": float(np.percentile(null, 95)),
            "percentile": float((null <= actual).mean() * 100)}


def dsr(pnl, n_trials, var_sr):
    """Deflated Sharpe ratio (Bailey and Lopez de Prado) of a per-night series; kurtosis is the raw (non-excess) moment."""
    pnl = np.asarray(pnl, dtype=float)
    T = len(pnl)
    if T < 3 or pnl.std(ddof=1) == 0:
        return {"T": T, "dsr": None}
    sr = float(pnl.mean() / pnl.std(ddof=1))
    g3 = float(skew(pnl))
    g4 = float(kurtosis(pnl, fisher=False))
    emc = 0.5772156649
    if n_trials > 1 and var_sr > 0:
        sr0 = math.sqrt(var_sr) * ((1 - emc) * norm.ppf(1 - 1.0 / n_trials) + emc * norm.ppf(1 - 1.0 / (n_trials * math.e)))
    else:
        sr0 = 0.0
    denom = 1 - g3 * sr + (g4 - 1) / 4.0 * sr * sr
    if denom <= 0:
        return {"T": T, "sr_per_night": sr, "sr0": sr0, "dsr": None}
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(denom)
    return {"T": T, "sr_per_night": sr, "skew": g3, "kurtosis_raw": g4, "n_trials": n_trials, "var_sr_trials": var_sr,
            "expected_max_sr_null": sr0, "z": z, "dsr": float(norm.cdf(z)),
            "psr_vs_zero": float(norm.cdf(sr * math.sqrt(T - 1) / math.sqrt(denom)))}


def holm(pvals, alpha=0.10):
    """Holm step-down; returns the list of rejected ids."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    rejected = []
    for i, (k, p) in enumerate(items):
        if p <= alpha / (m - i):
            rejected.append(k)
        else:
            break
    return rejected


def in_split(dates, split):
    lo, hi = SPLITS[split]
    d = pd.to_datetime(dates)
    return (d >= lo) & (d <= hi)


# ----------------------------------------------------------------------------------------------
def load(sym):
    t = pd.read_csv(os.path.join(ROOT, f"trades_honest_{sym}.csv"))
    g = pd.read_csv(os.path.join(ROOT, "h_geometry_nights.csv"))
    g = g[g.sym == sym].copy()
    c = pd.read_csv(os.path.join(ROOT, f"candidates_{sym}.csv"))
    det = pd.read_csv(os.path.join(ROOT, "h_detector_bridge_nights.csv"))
    det = det[det.sym == sym].copy()
    v = pd.read_csv(os.path.join(ROOT, "h_vetoes_gates_nights.csv"))
    v = v[v.sym == sym].copy()
    tm = pd.read_csv(os.path.join(ROOT, "h_timing_exits_nights.csv"))
    tm = tm[tm.sym == sym].copy()
    return t, g, c, det, v, tm


def build_nights(sym):
    t, g, c, det, v, tm = load(sym)
    g_full = g.copy()
    n = t[["date", "grade", "call", "variant", "best", "side", "cand_id", "confidence", "is_down", "sunday_open",
           "pre_holiday", "holiday_tomorrow", "post_ret", "megacap_earnings_tonight", "pB_high_above_cal", "pB_low_below_cal", "splice",
           "split", "pnl_net_open", "pnl_net_open_hicost", "outcome_open", "resolved_k_open", "traded_open",
           "target_dist", "stop_dist", "med20_pts", "dow", "event_night"]].copy()
    n["date"] = n["date"].astype(str)
    # baseline A book
    n["base_A"] = (n.grade == "A").astype(int)
    n["base_G"] = n.grade.isin(GRADES).astype(int)
    n["base_pnl"] = np.where(n.base_G == 1, n.pnl_net_open.fillna(0.0), 0.0)
    n["base_pnl_hi"] = np.where(n.base_G == 1, n.pnl_net_open_hicost.fillna(0.0), 0.0)
    n["base_pnl_A"] = np.where(n.base_A == 1, n.base_pnl, 0.0)
    n["base_pnl_A_hi"] = np.where(n.base_A == 1, n.base_pnl_hi, 0.0)
    # geometry re-call (H2 + H3, H3 alone, H2 alone) from the geometry group's per-night file
    g = g[["date", "base_grade", "base_pnl_net_open", "H2H3_grade", "H2H3_cand_id", "H2H3_conf", "H2H3_pnl_net_open",
           "H2H3_pnl_net_open_hicost", "H3_grade", "H3_cand_id", "H3_conf", "H3_pnl_net_open", "H3_pnl_net_open_hicost",
           "H2_grade", "H2_cand_id", "H2_pnl_net_open", "H2_pnl_net_open_hicost"]].copy()
    g["date"] = g["date"].astype(str)
    n = n.merge(g, on="date", how="left", validate="1:1")
    # self-check: the geometry file's baseline equals the trades table
    chk = n[(n.splice == 0)]
    assert (chk.base_grade.fillna("-") == chk.grade.fillna("-")).all(), "geometry baseline grade mismatch"
    assert np.allclose(chk.base_pnl_net_open.fillna(0.0), chk.base_pnl, atol=1e-6), "geometry baseline pnl mismatch"
    # traded flag, kind, variant, target and outcome of the re-called candidate (18:00 fill constraint), from the candidates table
    cc = c[["date", "cand_id", "traded_open", "kind", "side", "variant", "target_key", "outcome_open"]].copy()
    cc["date"] = cc["date"].astype(str)
    for pref in ("H2H3", "H3"):
        m = cc.rename(columns={"cand_id": f"{pref}_cand_id", "traded_open": f"{pref}_traded", "kind": f"{pref}_kind",
                               "side": f"{pref}_side", "variant": f"{pref}_variant", "target_key": f"{pref}_target",
                               "outcome_open": f"{pref}_outcome"})
        n = n.merge(m, on=["date", f"{pref}_cand_id"], how="left")
    # Detector B direction-relative probability (17:xx): the detector group's convention
    d = det[["date", "pB_dir_cal", "det_B_avail", "rth_dir_up"]].copy()
    d["date"] = d["date"].astype(str)
    n = n.merge(d, on="date", how="left", validate="1:1")
    own = np.where(n.is_down == 0, n.pB_high_above_cal, n.pB_low_below_cal)
    both = n.det_B_avail == 1
    assert np.allclose(own[both.values].astype(float), n.pB_dir_cal[both].astype(float), atol=1e-9), "pB_dir convention mismatch"
    n["pB_dir"] = n.pB_dir_cal
    # veto flags (17:xx)
    n["flag_H5"] = ((n.post_ret.abs() > H5_POST) | (n.megacap_earnings_tonight == 1)).astype(int)
    n["flag_H9"] = (n.pre_holiday == 1).astype(int)                    # H9 as scored: pre_holiday only (NOT holiday_tomorrow)
    n["flag_H9_proxy"] = ((n.pre_holiday == 1) | (n.holiday_tomorrow == 1)).astype(int)   # the vetoes group's H9_proxy, reported only

    def d1(kind_col):
        k = n[kind_col]
        p = n.pB_dir
        mr = (k == "MEAN REVERSION") & (p >= D1_BREAK)
        co = (k == "CONTINUATION") & (p <= D1_HOLD)
        return ((mr | co) & p.notna()).astype(int)

    n["flag_D1_base"] = d1("call")
    n["flag_D1_H2H3"] = d1("H2H3_kind")
    n["flag_D1_H3"] = d1("H3_kind")
    # cross-check the veto flags against the vetoes group's file (graded nights touched, full window)
    vv = v[v.rule == "H5"]
    vv_dates = set(vv[vv.affected == 1].date.astype(str))
    mine = set(n[(n.flag_H5 == 1) & (n.base_G == 1) & (n.splice == 0)].date)
    assert vv_dates == mine, f"H5 flag mismatch: {sorted(vv_dates ^ mine)}"
    vv = v[v.rule == "H9"]
    vv_dates = set(vv[vv.affected == 1].date.astype(str))
    mine = set(n[(n.flag_H9 == 1) & (n.base_G == 1) & (n.splice == 0)].date)
    assert vv_dates == mine, f"H9 flag mismatch: {sorted(vv_dates ^ mine)}"
    dd = det[(det.affected_D1 == 1)]
    mine = set(n[(n.flag_D1_base == 1) & (n.base_G == 1)].date)
    assert set(dd.date.astype(str)) == mine, f"D1 flag mismatch: {sorted(set(dd.date.astype(str)) ^ mine)}"

    # ---- specs ----
    def spec(grade_col, pnl_col, pnl_hi_col, traded_col, vetoes, name):
        vet = np.zeros(len(n), dtype=bool)
        for f in vetoes:
            vet |= n[f].fillna(0).astype(int).values == 1
        grade = n[grade_col].fillna("-").astype(str).values.copy()
        grade = np.where(vet & np.isin(grade, GRADES), "NO EDGE", grade)
        pnl = np.where(np.isin(grade, GRADES), n[pnl_col].fillna(0.0).values, 0.0)
        pnl_hi = np.where(np.isin(grade, GRADES), n[pnl_hi_col].fillna(0.0).values, 0.0)
        n[f"{name}_grade"] = grade
        n[f"{name}_pnl"] = pnl
        n[f"{name}_pnl_hi"] = pnl_hi
        n[f"{name}_A"] = (grade == "A").astype(int)
        n[f"{name}_pnl_A"] = np.where(grade == "A", pnl, 0.0)
        n[f"{name}_pnl_A_hi"] = np.where(grade == "A", pnl_hi, 0.0)
        n[f"{name}_traded"] = np.where(grade == "A", n[traded_col].fillna(0).values, np.nan)
        n[f"{name}_vetoed"] = (vet & np.isin(n[grade_col].fillna("-").astype(str).values, GRADES)).astype(int)
        reason = np.full(len(n), "", dtype=object)
        for f in vetoes:
            reason = np.where((n[f].fillna(0).astype(int).values == 1) & np.isin(n[grade_col].fillna("-").astype(str).values, GRADES),
                              np.char.add(reason.astype(str), f.replace("flag_", "") + ";"), reason)
        n[f"{name}_veto_reason"] = reason

    n["base_traded_col"] = n.traded_open
    for name in SPECS:
        sc = SRC_COLS[SPEC_SRC[name]]
        spec(sc["grade"], sc["pnl"], sc["pnl_hi"], sc["traded"], SPEC_VETOES[name], name)
    assert np.allclose(n.S0_pnl_A, n.base_pnl_A), "S0 must equal the baseline"
    return n, t, det, v, tm, g_full


def paired_block(diff, dates, sym, split):
    mean, lo, hi, dr = block_boot(diff, dates)
    tot = float(np.asarray(diff).sum())
    return {"n": int(len(diff)), "mean": mean, "ci90": [lo, hi], "ci80": ci80(dr), "total": tot,
            "p_onesided_pos": one_sided_p(dr, +1), "win_share": float((np.asarray(diff) > 0).mean()) if len(diff) else 0.0,
            "n_pnl_changed": int((np.asarray(diff) != 0).sum()),
            "usd_per_contract_per_year": usd_per_year(tot, sym, split),
            "usd_per_contract_per_year_ci90": [usd_per_year(lo * len(diff), sym, split), usd_per_year(hi * len(diff), sym, split)]}


def evaluate(n, sym, name):
    sc = SRC_COLS[SPEC_SRC[name]]
    kcol, vcol, ocol, tcol = sc["kind"], sc["variant"], sc["outcome"], sc["traded"]
    recalled_pnl_col = sc["pnl"]
    res = {"desc": SPEC_DESC[name], "source_columns": SPEC_SRC[name], "vetoes": [f.replace("flag_", "") for f in SPEC_VETOES[name]]}
    for split in SPLITS:
        m = in_split(n.date, split) & (n.splice == 0)
        s = n[m]
        A = s[s[f"{name}_A"] == 1]
        G = s[s[f"{name}_grade"].isin(GRADES)]
        bA = s[s.base_A == 1]
        bG = s[s.base_G == 1]
        r = {}
        r["A"] = series_stats(A[f"{name}_pnl_A"], A[f"{name}_pnl_A_hi"], A[f"{name}_traded"])
        r["A"]["usd_per_contract_per_year"] = usd_per_year(r["A"].get("total", 0.0), sym, split)
        r["A"]["usd_per_contract_per_year_hicost"] = usd_per_year(r["A"].get("total_hicost", 0.0), sym, split)
        kinds = A[kcol].fillna(A.call)
        r["A"]["by_kind"] = {k: series_stats(A[kinds == k][f"{name}_pnl_A"]) for k in ("MEAN REVERSION", "CONTINUATION")}
        r["A"]["sunday"] = series_stats(A[A.sunday_open == 1][f"{name}_pnl_A"])
        r["A"]["weeknight"] = series_stats(A[A.sunday_open == 0][f"{name}_pnl_A"])
        tot = float(A[f"{name}_pnl_A"].sum())
        r["A"]["sunday_share_of_total"] = float(A[A.sunday_open == 1][f"{name}_pnl_A"].sum() / tot) if tot else None
        top = A.sort_values(f"{name}_pnl_A", ascending=False).head(5)
        r["A"]["top5"] = {"dates": top.date.tolist(), "pnl": [round(x, 1) for x in top[f"{name}_pnl_A"].tolist()],
                          "share_of_total": float(top[f"{name}_pnl_A"].sum() / tot) if tot else None,
                          "avg_without_top5": float(A[~A.date.isin(top.date)][f"{name}_pnl_A"].mean()) if len(A) > 5 else None}
        bands = [("[72,75)", 72, 75), ("[75,80)", 75, 80), ("[80,90)", 80, 90), ("[90,100]", 90, 101)]
        conf = A["H2H3_conf"] if SPEC_SRC[name] == "H2H3" else (A["H3_conf"] if SPEC_SRC[name] == "H3" else A["confidence"])
        r["A"]["confidence_bands"] = {lab: series_stats(A[(conf >= lo) & (conf < hi)][f"{name}_pnl_A"]) for lab, lo, hi in bands}
        q = pd.to_datetime(A.date).dt.to_period("Q").astype(str)
        r["A"]["by_quarter"] = {str(k): series_stats(A[f"{name}_pnl_A"][q == k]) for k in sorted(q.unique())}
        r["graded"] = series_stats(G[f"{name}_pnl"], G[f"{name}_pnl_hi"])
        r["graded"]["usd_per_contract_per_year"] = usd_per_year(r["graded"].get("total", 0.0), sym, split)
        r["base_A"] = series_stats(bA.base_pnl_A, bA.base_pnl_A_hi, bA.traded_open)
        r["base_graded"] = series_stats(bG.base_pnl, bG.base_pnl_hi)
        r["grade_counts"] = {k: int((s[f"{name}_grade"] == k).sum()) for k in ("A", "B", "C", "NO EDGE")}
        r["grade_counts_base"] = {k: int((s.grade == k).sum()) for k in ("A", "B", "C", "NO EDGE")}
        r["A_n_before_after"] = [int(s.base_A.sum()), int(s[f"{name}_A"].sum())]
        r["effect_A_avg"] = r["A"].get("avg", 0.0) - r["base_A"].get("avg", 0.0)
        # bootstrap of the difference in A averages (the groups' headline statistic): paired on A-either nights
        either = s[(s.base_A == 1) | (s[f"{name}_A"] == 1)]
        dA = either[f"{name}_pnl_A"].values
        bAv = either.base_pnl_A.values
        wk = iso_week(either.date)
        uniq = np.unique(wk)
        gi = rng()
        boots = np.empty(DRAWS)
        hypA = either[f"{name}_A"].values.astype(bool)
        baseA = either.base_A.values.astype(bool)
        idxs = [np.where(wk == w)[0] for w in uniq]
        for i in range(DRAWS):
            pick = gi.integers(0, len(uniq), len(uniq))
            ii = np.concatenate([idxs[j] for j in pick])
            h_ = dA[ii][hypA[ii]]
            b_ = bAv[ii][baseA[ii]]
            boots[i] = (h_.mean() if len(h_) else 0.0) - (b_.mean() if len(b_) else 0.0)
        r["effect_A_avg_ci90"] = [float(np.percentile(boots, 5)), float(np.percentile(boots, 95))]
        r["effect_A_avg_ci80"] = ci80(boots)
        r["effect_A_avg_p_onesided_pos"] = one_sided_p(boots, +1)
        # paired per-night differences
        for pop, mask in (("all_nights", np.ones(len(s), dtype=bool)),
                          ("changed_nights", (s[f"{name}_pnl_A"].values != s.base_pnl_A.values) | (s[f"{name}_A"].values != s.base_A.values)),
                          ("A_either", ((s.base_A == 1) | (s[f"{name}_A"] == 1)).values),
                          ("graded_book_all_nights", np.ones(len(s), dtype=bool))):
            ss = s[mask]
            if pop == "graded_book_all_nights":
                diff = ss[f"{name}_pnl"].values - ss.base_pnl.values
            else:
                diff = ss[f"{name}_pnl_A"].values - ss.base_pnl_A.values
            r[f"paired_{pop}"] = paired_block(diff, ss.date, sym, split)
        diff_hi = s[f"{name}_pnl_A_hi"].values - s.base_pnl_A_hi.values
        r["paired_all_nights_hicost"] = paired_block(diff_hi, s.date, sym, split)
        # membership
        kept = (bA[f"{name}_A"] == 1).values
        r["A_membership"] = {"retained": int(kept.sum()), "dropped": int((~kept).sum()),
                             "added": int(((s.base_A == 0) & (s[f"{name}_A"] == 1)).sum()),
                             "dropped_base_avg": float(bA.base_pnl_A[~kept].mean()) if (~kept).any() else None,
                             "dropped_base_win": float((bA.base_pnl_A[~kept] > 0).mean()) if (~kept).any() else None,
                             "retained_base_avg": float(bA.base_pnl_A[kept].mean()) if kept.any() else None,
                             "retained_hyp_avg": float(bA[f"{name}_pnl_A"][kept].mean()) if kept.any() else None,
                             "added_hyp_avg": float(s[(s.base_A == 0) & (s[f"{name}_A"] == 1)][f"{name}_pnl_A"].mean()) if ((s.base_A == 0) & (s[f"{name}_A"] == 1)).any() else None,
                             "dropped_dates": bA[~kept].date.tolist(), "added_dates": s[(s.base_A == 0) & (s[f"{name}_A"] == 1)].date.tolist()}
        # survivorship of the honest top-5 A nights of the split
        htop = bA.sort_values("base_pnl_A", ascending=False).head(5)
        r["honest_top5_survivorship"] = {"dates": htop.date.tolist(), "base_pnl": [round(x, 1) for x in htop.base_pnl_A.tolist()],
                                         "survive_as_A": htop[htop[f"{name}_A"] == 1].date.tolist(),
                                         "n_survive": int((htop[f"{name}_A"] == 1).sum())}
        r["random_filter_null_A"] = random_filter(bA.base_pnl_A.values, kept)
        keptG = (bG[f"{name}_grade"].isin(GRADES)).values
        r["random_filter_null_graded"] = random_filter(bG.base_pnl.values, keptG)
        r["vetoed_graded_nights"] = {"n": int(s[f"{name}_vetoed"].sum()),
                                     "reasons": s[s[f"{name}_vetoed"] == 1][f"{name}_veto_reason"].value_counts().to_dict(),
                                     "their_recalled_pnl_total": float(s[s[f"{name}_vetoed"] == 1][[recalled_pnl_col]].fillna(0).values.sum())}
        # A nights per month (degeneracy guard) and A pnl retained fraction, discovery only
        if split == "discovery":
            r["degeneracy_guard"] = {"A_per_month": r["A"]["n"] / MONTHS["discovery"],
                                     "A_pnl_retained_frac": (r["A"]["total"] / r["base_A"]["total"]) if r["base_A"]["total"] else None,
                                     "passes": (r["A"]["n"] / MONTHS["discovery"] >= 2.5) and (r["base_A"]["total"] > 0 and r["A"]["total"] >= 0.6 * r["base_A"]["total"])}
            # sign consistency of the paired effect by discovery quarter (LAB_DESIGN 2.6: same sign in >= 3 of 4 quarters and the stub)
            dates = pd.to_datetime(s.date)
            for lab_key, hyp_col, base_col in (("quarter_sign_consistency", f"{name}_pnl_A", "base_pnl_A"),
                                               ("quarter_sign_consistency_graded", f"{name}_pnl", "base_pnl")):
                q = {}
                for lab, lo, hi in (("2025Q2", "2025-04-01", "2025-06-30"), ("2025Q3", "2025-07-01", "2025-09-30"),
                                    ("2025Q4", "2025-10-01", "2025-12-31"), ("2026Q1", "2026-01-01", "2026-03-31"),
                                    ("2026AprMay", "2026-04-01", "2026-05-31")):
                    mm = (dates >= lo) & (dates <= hi)
                    dq = (s[hyp_col].values - s[base_col].values)[mm.values]
                    q[lab] = {"n": int(mm.sum()), "mean": float(dq.mean()) if len(dq) else 0.0, "total": float(dq.sum())}
                pos_q = sum(1 for k in ("2025Q2", "2025Q3", "2025Q4", "2026Q1") if q[k]["mean"] > 0)
                q["positive_quarters_of_4"] = pos_q
                q["stub_positive"] = bool(q["2026AprMay"]["mean"] > 0)
                q["passes_2_6"] = bool(pos_q >= 3 and q["2026AprMay"]["mean"] > 0)
                r[lab_key] = q
        # resolution mix of the spec's A nights (ex post descriptive), from the (re-)called candidate's own outcome
        oc = A[ocol].fillna("untraded")
        oc = np.where(A[tcol].fillna(0) == 0, "untraded", oc)
        r["A_outcome_mix"] = pd.Series(oc).value_counts().to_dict()
        r["A_scratch_share"] = float((oc == "scratch").mean()) if len(oc) else None
        r["A_stop_share"] = float((oc == "stop").mean()) if len(oc) else None
        r["A_by_variant"] = {}
        for k in ("MEAN REVERSION", "CONTINUATION"):
            for vv_ in ("tight", "wide"):
                r["A_by_variant"][f"{k}|{vv_}"] = series_stats(A[(kinds == k) & (A[vcol] == vv_)][f"{name}_pnl_A"])
        res[split] = r
    return res


def attribution(n, sym):
    """Paired per-night differences between specs (a minus b) on the A book and on the graded book."""
    out = {}
    for a, b, desc in ATTRIBUTION_PAIRS:
        key = f"{a}_minus_{b}"
        out[key] = {"desc": desc}
        for split in SPLITS:
            m = in_split(n.date, split) & (n.splice == 0)
            s = n[m]
            dA = s[f"{a}_pnl_A"].values - s[f"{b}_pnl_A"].values
            dG = s[f"{a}_pnl"].values - s[f"{b}_pnl"].values
            r = {"A_book_all_nights": paired_block(dA, s.date, sym, split), "graded_book_all_nights": paired_block(dG, s.date, sym, split)}
            ch = s[dA != 0]
            r["A_book_changed_nights"] = {"n": int(len(ch)), "dates": ch.date.tolist(), "diffs": [round(x, 2) for x in (ch[f"{a}_pnl_A"] - ch[f"{b}_pnl_A"]).tolist()]}
            r["A_n"] = {a: int(s[f"{a}_A"].sum()), b: int(s[f"{b}_A"].sum())}
            out[key][split] = r
    return out


def kill_switch(n, name):
    """Reachability of the forward conditions and the LAB_DESIGN 12.3 item-5 kill switch under the spec's full-window A rate."""
    m = in_split(n.date, "full") & (n.splice == 0)
    s = n[m].sort_values("date")
    A = s[s[f"{name}_A"] == 1]
    nA = len(A)
    a_per_month = nA / MONTHS["full"]
    nights_per_month = len(s) / MONTHS["full"]
    pnl = A[f"{name}_pnl_A"].values
    w = 12
    sums = np.array([pnl[i:i + w].sum() for i in range(0, max(0, nA - w + 1))])
    out = {"A_nights_full": nA, "A_per_month": a_per_month, "nights_per_month": nights_per_month,
           "months_to_12_A": 12 / a_per_month if a_per_month else None, "months_to_25_A": 25 / a_per_month if a_per_month else None,
           "months_to_40_A": 40 / a_per_month if a_per_month else None, "months_to_80_nights": 80 / nights_per_month,
           "trailing12_windows": int(len(sums)), "trailing12_worst_sum": float(sums.min()) if len(sums) else None,
           "trailing12_below_kill_count": int((sums < KILL_TRAILING12).sum()) if len(sums) else 0, "kill_threshold": KILL_TRAILING12}
    if len(sums):
        i = int(sums.argmin())
        out["trailing12_worst_window"] = [A.date.iloc[i], A.date.iloc[min(i + w - 1, nA - 1)]]
    return out


def anatomy(n, sym):
    out = {}
    for split in SPLITS:
        m = in_split(n.date, split) & (n.splice == 0)
        s = n[m]
        A = s[s.base_A == 1].copy()
        r = {"n": int(len(A))}
        oc = A.outcome_open.fillna("untraded")
        oc = np.where(A.traded_open == 0, "untraded", oc)
        r["resolution_shares"] = pd.Series(oc).value_counts(normalize=True).round(3).to_dict()
        r["resolution_counts"] = pd.Series(oc).value_counts().to_dict()
        r["by_outcome"] = {k: series_stats(A.base_pnl_A[oc == k]) for k in pd.unique(oc)}
        r["by_call_variant"] = {f"{k}|{v}": series_stats(A[(A.call == k) & (A.variant == v)].base_pnl_A)
                                for k in ("MEAN REVERSION", "CONTINUATION") for v in ("tight", "wide")}
        r["by_target"] = {k: series_stats(A[A.best == k].base_pnl_A) for k in sorted(A.best.dropna().unique())}
        r["by_call"] = {k: series_stats(A[A.call == k].base_pnl_A) for k in ("MEAN REVERSION", "CONTINUATION")}
        r["sunday"] = series_stats(A[A.sunday_open == 1].base_pnl_A)
        r["weeknight"] = series_stats(A[A.sunday_open == 0].base_pnl_A)
        tot = float(A.base_pnl_A.sum())
        r["sunday_share_of_total"] = float(A[A.sunday_open == 1].base_pnl_A.sum() / tot) if tot else None
        top = A.sort_values("base_pnl_A", ascending=False).head(5)
        r["top5"] = {"dates": top.date.tolist(), "pnl": [round(x, 1) for x in top.base_pnl_A.tolist()],
                     "share_of_total": float(top.base_pnl_A.sum() / tot) if tot else None,
                     "avg_without_top5": float(A[~A.date.isin(top.date)].base_pnl_A.mean()) if len(A) > 5 else None,
                     "total_without_top5": float(A[~A.date.isin(top.date)].base_pnl_A.sum()) if len(A) > 5 else None}
        bot = A.sort_values("base_pnl_A").head(5)
        r["bottom5"] = {"dates": bot.date.tolist(), "pnl": [round(x, 1) for x in bot.base_pnl_A.tolist()]}
        q = pd.to_datetime(A.date).dt.to_period("Q").astype(str)
        r["by_quarter"] = {str(k): series_stats(A.base_pnl_A[q == k]) for k in sorted(q.unique())}
        # confidence bands on the engine's ROUNDED confidence (the trades table's `confidence` column); the geometry file
        # buckets the raw ratio x 100, which moves nights whose ratio sits just below a band edge (e.g. 74.68 -> 75)
        bands = [("[72,75)", 72, 75), ("[75,80)", 75, 80), ("[80,90)", 80, 90), ("[90,100]", 90, 101)]
        r["confidence_bands"] = {lab: series_stats(A[(A.confidence >= lo) & (A.confidence < hi)].base_pnl_A) for lab, lo, hi in bands}
        r["confidence_bands_convention"] = "rounded integer confidence (trades table); h_geometry_results.json buckets the raw ratio x 100"
        rk = A.resolved_k_open
        r["resolved_by_k2_share"] = float(((rk <= 2) & rk.notna()).mean())
        r["scratch_share"] = float((oc == "scratch").mean())
        # the honest record with and without the raw-probability months 2025-04..07 (no causal calibrator yet)
        raw = pd.to_datetime(A.date) < "2025-08-01"
        r["A_excluding_raw_probability_months_2025_04_07"] = series_stats(A.base_pnl_A[~raw.values])
        r["A_raw_probability_months_2025_04_07"] = series_stats(A.base_pnl_A[raw.values])
        out[split] = r
    return out


def vault_family_tests(sym, n, det, v, tm, g):
    """One-sided weekly-block bootstrap p-values of the vault paired effect (hypothesis minus baseline) on the
    A-either population of every vault-scored rule with a predicted sign; Holm at FWER 0.10."""
    tests = {}
    vault = lambda df: df[in_split(df.date.astype(str), "vault") & (df.splice == 0)]
    # geometry
    gg = vault(g.copy())
    for rid in ("H2", "H3", "H11", "H1", "COMBO", "COMBO_H1", "H2H3"):
        hypA = gg[f"{rid}_grade"] == "A"
        baseA = gg.base_grade == "A"
        either = gg[hypA | baseA]
        d = np.where(either[f"{rid}_grade"] == "A", either[f"{rid}_pnl_net_open"], 0.0) - np.where(either.base_grade == "A", either.base_pnl_net_open, 0.0)
        mean, lo, hi, dr = block_boot(d, either.date)
        tests[f"geometry:{rid}"] = {"n": int(len(either)), "mean": mean, "ci90": [lo, hi], "p": one_sided_p(dr, +1), "sign": +1}
    # timing (A nights, grades unchanged)
    tt = vault(tm.copy())
    tA = tt[tt.grade == "A"]
    for rid, sg in (("H4", 1), ("TS20c", 1), ("TS20c_b", 1), ("TS22c", 1), ("TS22m", 1), ("TS00c", 1), ("TS00m", 1),
                    ("H12", 1), ("SCR00", 1), ("BE22", 1)):
        d = tA[f"pnl_{rid}"].values - tA.base_pnl_net.values
        mean, lo, hi, dr = block_boot(d, tA.date)
        tests[f"timing:{rid}"] = {"n": int(len(tA)), "mean": mean, "ci90": [lo, hi], "p": one_sided_p(dr, sg), "sign": sg}
    # detector
    dd = vault(det.copy())
    for rid in ("D1", "D1_MR", "D1_CONT", "D2_demote", "D2_switch", "D2_switch_keep", "D3", "D3_price", "D3_hold",
                "D3_k1", "D3_k2", "D4", "D4_k3", "D5", "D5_rev"):
        gc = f"grade_{rid}"
        hypA = dd[gc] == "A" if gc in dd.columns else (dd.grade == "A")
        baseA = dd.grade == "A"
        either = dd[hypA | baseA]
        hyp_pnl = np.where(either[gc] == "A", either[f"pnl_{rid}"], 0.0) if gc in dd.columns else either[f"pnl_{rid}"].values
        d = hyp_pnl - np.where(either.grade == "A", either.base_pnl_net, 0.0)
        mean, lo, hi, dr = block_boot(d, either.date)
        tests[f"detector:{rid}"] = {"n": int(len(either)), "mean": mean, "ci90": [lo, hi], "p": one_sided_p(dr, +1) if len(either) and np.any(d != 0) else 1.0, "sign": +1}
    # vetoes (long format)
    vv = vault(v.copy())
    for rid in ("H5", "H9", "H9_proxy", "H6", "H14", "H14_calllevel", "COMBINED", "COMBINED_ALL", "COMBINED_FREE"):
        x = vv[vv.rule == rid]
        either = x[(x.base_grade == "A") | (x.hyp_grade == "A")]
        d = either.hyp_pnl_A.values - either.base_pnl_A.values
        mean, lo, hi, dr = block_boot(d, either.date)
        tests[f"vetoes:{rid}"] = {"n": int(len(either)), "mean": mean, "ci90": [lo, hi], "p": one_sided_p(dr, +1) if np.any(d != 0) else 1.0, "sign": +1}
    pv = {k: t["p"] for k, t in tests.items()}
    rej = holm(pv, 0.10)
    slot = [k for k, p in pv.items() if p <= 0.10 / 12]
    nominal = [k for k, p in pv.items() if p <= 0.05]
    # the same statistic for this script's specs, reported beside the family (NOT members of it: the family is the groups' 41 tests)
    specs_same_stat = {}
    nn = vault(n.copy())
    for s_ in SPECS[1:]:
        either = nn[(nn.base_A == 1) | (nn[f"{s_}_A"] == 1)]
        d = either[f"{s_}_pnl_A"].values - either.base_pnl_A.values
        mean, lo, hi, dr = block_boot(d, either.date)
        specs_same_stat[s_] = {"n": int(len(either)), "mean": mean, "ci90": [lo, hi], "p": one_sided_p(dr, +1) if np.any(d != 0) else 1.0}
    return {"family_size": len(tests), "tests": tests, "holm_rejected_fwer_0_10": rej,
            "bonferroni_slot_alpha_0_10_over_12_rejected": slot, "nominal_p_le_0_05": nominal, "slot_alpha": 0.10 / 12,
            "vault_h_status": f"{len(tests)} historical tests scored on Vault-H against a 12-slot lifetime wallet (LAB_DESIGN 1.3, 2.6): Vault-H is spent; every later test is Vault-F",
            "specs_same_statistic_not_in_family": specs_same_stat}


def trial_sharpes(n, det, v, tm, g):
    """Per-night Sharpe of every rule's A series on discovery (for Var(SR) across trials)."""
    disc = lambda df: df[in_split(df.date.astype(str), "discovery") & (df.splice == 0)]
    srs = {}

    def sr(x):
        x = np.asarray(x, dtype=float)
        return float(x.mean() / x.std(ddof=1)) if len(x) > 2 and x.std(ddof=1) > 0 else 0.0

    gg = disc(g.copy())
    for rid in ("H2", "H2_placebo", "H3", "H11", "H11_placebo", "H1", "COMBO", "COMBO_H1", "H2H3"):
        srs[f"geometry:{rid}"] = sr(gg[gg[f"{rid}_grade"] == "A"][f"{rid}_pnl_net_open"])
    srs["geometry:baseline"] = sr(gg[gg.base_grade == "A"].base_pnl_net_open)
    tt = disc(tm.copy())
    tA = tt[tt.grade == "A"]
    for c in [c for c in tt.columns if c.startswith("pnl_")]:
        srs[f"timing:{c[4:]}"] = sr(tA[c])
    dd = disc(det.copy())
    for c in [c for c in dd.columns if c.startswith("pnl_") and not c.startswith("pnl_hicost")]:
        rid = c[4:]
        gc = f"grade_{rid}"
        if gc in dd.columns:
            srs[f"detector:{rid}"] = sr(dd[dd[gc] == "A"][c])
        else:
            srs[f"detector:{rid}"] = sr(dd[dd.grade == "A"][c])
    vv = disc(v.copy())
    for rid in vv.rule.unique():
        x = vv[vv.rule == rid]
        srs[f"vetoes:{rid}"] = sr(x[x.hyp_grade == "A"].hyp_pnl_A)
    nn = disc(n.copy())
    for s_ in SPECS[1:]:
        srs[f"prime:{s_}"] = sr(nn[nn[f"{s_}_A"] == 1][f"{s_}_pnl_A"])
    return srs


def trial_ledger():
    """Count of every hypothesis, placebo, combo and exploratory variant actually computed by the four groups."""
    geo = json.load(open(os.path.join(ROOT, "h_geometry_results.json")))
    tim = json.load(open(os.path.join(ROOT, "h_timing_exits_results.json")))
    vet = json.load(open(os.path.join(ROOT, "h_vetoes_gates_results.json")))
    dtb = json.load(open(os.path.join(ROOT, "h_detector_bridge_results.json")))
    led = {}
    led["geometry_rules"] = sorted(geo["symbols"]["NQ"]["rules"].keys())
    led["geometry_exploratory"] = [f'{e["hypothesis"]}@{e["value"]}' for e in geo["symbols"]["NQ"]["exploratory_discovery_only"]]
    led["geometry_observations"] = ["confidence_band_A_at_80"]
    led["timing_registry"] = sorted(tim["registry"].keys())
    grids = []
    for rid, h in tim["NQ"]["hypotheses"].items():
        eg = h.get("exploratory_grid_discovery_only")
        if isinstance(eg, list):
            for e in eg:
                if isinstance(e, dict) and not e.get("pre_registered", False):
                    grids.append(f"{rid}@{e.get('frac')}")
    led["timing_exploratory_grid"] = grids
    led["timing_negative_result_checks"] = ["hold_through_europe_levels_active", "hold_to_europe_close"]
    led["vetoes_rules"] = [r["id"] for r in vet["summary"]["NQ"]]
    led["vetoes_exploratory"] = ["H5@0.002", "H5@0.005", "H5_post_ret_only", "H5_megacap_only", "H6_dd@-0.05", "H6_dd@-0.12",
                                 "H6_skip_MR", "H6_skip_both", "H14_es_no_call_veto", "H14_es_no_call_veto_no_missing",
                                 "REG_vix25", "REG_vixz20", "REG_rv_ratio", "REG_fomc", "REG_tier1", "DOW", "H8a_sunday_split", "H8c_sunday_band"]
    led["detector_registry"] = sorted(dtb["registry"].keys())
    led["detector_exploratory"] = list(dtb["NQ"]["hypotheses"]["D1"]["exploratory_discovery_only"].keys())
    total = sum(len(v_) for v_ in led.values())
    led["n_trials_four_groups"] = total
    led["lab_design_precharge"] = 25
    led["n_trials_with_precharge"] = total + 25
    led["this_script_specs"] = list(SPECS[1:])
    led["n_trials_with_precharge_and_this_script"] = total + 25 + len(SPECS) - 1
    led["note"] = ("lower bound on trials: the seven honest-baseline ladder steps, the placebo re-draws (300 per placebo, which are nulls, not candidate rules) "
                   "and the forensic looks that sized the backlog are not counted")
    return led


def main():
    results = {"generated_from": "research/lab/grade_a/grade_a_prime.py", "baseline": "pnl_net_open (honest grade, 18:00-open fill, own-pair resolution, base costs); hicost = pnl_net_open_hicost",
               "splits": SPLITS, "months": MONTHS, "point_value_usd": POINT, "bootstrap": {"blocks": "ISO week", "draws": DRAWS, "rng": "numpy default_rng(0)", "ci": "90% (ci90) and 80% (ci80) of the same draws"},
               "random_filter_null": {"draws": DRAWS, "rng": "numpy default_rng(0)"}, "spec": SPEC_DESC, "spec_sources": SPEC_SRC, "spec_vetoes": {k: [f.replace("flag_", "") for f in v_] for k, v_ in SPEC_VETOES.items()},
               "paper_trading_spec": "S6", "shadow_spec": "S7", "superseded_spec": "S2",
               "parameters": {"H2_cap_x_med20": 1.0, "H3_wide_fade_min_ratio": 0.80, "H3_floor_convention": "raw ratio win_rate_on_resolution (not the rounded confidence); see h_geometry_results.json H3_floor_convention",
                              "H3_drop": "CONTINUATION|wide", "H5_post_ret": H5_POST,
                              "H9_flag": "pre_holiday == 1 only (calendar_features: the next CALENDAR day is a US holiday; a Friday before a Monday holiday is not flagged); holiday_tomorrow is NOT part of the scored rule (the vetoes group's H9_proxy union is reported, not scored here)",
                              "D1_BREAK": D1_BREAK, "D1_HOLD": D1_HOLD, "kill_switch_trailing12": KILL_TRAILING12},
               "usd_note": "per-rule and per-spec USD figures are each measured against the honest baseline alone and are NOT additive across rules; the joint effect of a spec is its own paired figure",
               "attribution_pairs": [{"a": a, "b": b, "desc": d} for a, b, d in ATTRIBUTION_PAIRS]}
    ledger = trial_ledger()
    results["trial_ledger"] = ledger
    nights_out = []
    for sym in ("NQ", "ES"):
        n, t, det, v, tm, g = build_nights(sym)
        R = {"n_nights": int(len(n)), "n_splice_excluded": int(n.splice.sum())}
        R["anatomy_honest_A"] = anatomy(n, sym)
        for s_ in SPECS:
            R[s_] = evaluate(n, sym, s_)
        R["attribution"] = attribution(n, sym)
        R["kill_switch"] = {s_: kill_switch(n, s_) for s_ in ("S0", "S2", "S6", "S7")}
        srs = trial_sharpes(n, det, v, tm, g)
        R["trial_sharpes_discovery_A_series"] = srs
        var_sr = float(np.var(list(srs.values()), ddof=1))
        R["var_sr_trials"] = var_sr
        R["n_trial_sharpes"] = len(srs)
        R["dsr"] = {}
        dsr_ns = (ledger["n_trials_four_groups"], ledger["n_trials_with_precharge_and_this_script"], DSR_N_EXTRA)
        R["dsr_n_trials"] = list(dsr_ns)
        for s_ in SPECS:
            R["dsr"][s_] = {}
            for split in SPLITS:
                m = in_split(n.date, split) & (n.splice == 0)
                A = n[m & (n[f"{s_}_A"] == 1)]
                R["dsr"][s_][split] = {f"N{N}": dsr(A[f"{s_}_pnl_A"].values, N, var_sr) for N in dsr_ns}
        R["vault_family"] = vault_family_tests(sym, n, det, v, tm, g)
        results[sym] = R
        keep = ["date", "split", "splice", "grade", "call", "variant", "best", "side", "confidence", "sunday_open", "traded_open", "outcome_open",
                "pre_holiday", "holiday_tomorrow", "base_pnl_A", "base_pnl_A_hi", "base_pnl",
                "H2_grade", "H2_cand_id", "H2_pnl_net_open",
                "H3_grade", "H3_cand_id", "H3_conf", "H3_kind", "H3_variant", "H3_traded", "H3_outcome", "H3_pnl_net_open",
                "H2H3_grade", "H2H3_cand_id", "H2H3_conf", "H2H3_kind", "H2H3_variant", "H2H3_traded", "H2H3_outcome", "H2H3_pnl_net_open",
                "pB_dir", "flag_H5", "flag_H9", "flag_H9_proxy", "flag_D1_base", "flag_D1_H2H3", "flag_D1_H3"] + \
               [c for c in n.columns if c[:2] in SPECS[1:] and c[2] == "_"]
        o = n[keep].copy()
        o.insert(0, "sym", sym)
        nights_out.append(o)
    pd.concat(nights_out).to_csv(OUT_CSV, index=False, float_format="%.6f")
    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=1, default=lambda x: None if (isinstance(x, float) and math.isnan(x)) else (x.item() if hasattr(x, "item") else str(x)))
    # console summary
    for sym in ("NQ", "ES"):
        print(f"\n===== {sym} =====")
        for s_ in SPECS:
            print(f"-- {s_}: {SPEC_DESC[s_]}")
            for split in ("vault", "discovery", "full"):
                r = results[sym][s_][split]
                a = r["A"]
                pa = r["paired_all_nights"]
                pc = r["paired_changed_nights"]
                print(f"   {split:9s} A n={a['n']:3d} win={a.get('win', 0):.2f} avg={a.get('avg', 0):7.2f} tot={a.get('total', 0):8.1f} worst={a.get('worst', 0):7.1f} sd={a.get('sd', 0):6.1f} p/s={a.get('pts_per_sigma', 0):5.2f} untr={a.get('untraded', 0)} "
                      f"usd/yr={a['usd_per_contract_per_year']:8.0f} hi={a['usd_per_contract_per_year_hicost']:8.0f} | dA_avg={r['effect_A_avg']:6.2f} ci={np.round(r['effect_A_avg_ci90'], 1)} | all-night {pa['mean']:5.2f} ci={np.round(pa['ci90'], 1)} usd={pa['usd_per_contract_per_year']:7.0f} "
                      f"usd_ci={np.round(pa['usd_per_contract_per_year_ci90'], 0)} | changed n={pc['n']} (pnl {pc['n_pnl_changed']}) {pc['mean']:6.2f} ci={np.round(pc['ci90'], 1)} | rfA={r['random_filter_null_A'].get('percentile')} rfG={r['random_filter_null_graded'].get('percentile')} | A {r['A_n_before_after']}")
            q = results[sym][s_]["discovery"]["quarter_sign_consistency"]
            print("   degeneracy:", results[sym][s_]["discovery"].get("degeneracy_guard"), "quarters A book:", {k: round(x["mean"], 2) for k, x in q.items() if isinstance(x, dict)}, "passes 2.6:", q["passes_2_6"])
        print("attribution (A book all nights, mean [ci90]):")
        for key, blk in results[sym]["attribution"].items():
            print(f"   {key:14s} " + " | ".join(f"{sp} {blk[sp]['A_book_all_nights']['mean']:+.2f} {np.round(blk[sp]['A_book_all_nights']['ci90'], 2)} (n_chg {blk[sp]['A_book_changed_nights']['n']})" for sp in ("discovery", "vault", "full")))
        for s_ in ("S0", "S2", "S6", "S7"):
            print(f"DSR {s_} full:", {k: (round(v_['dsr'], 3) if v_.get('dsr') is not None else None) for k, v_ in results[sym]["dsr"][s_]["full"].items()}, "| kill switch:", {k: (round(v_, 2) if isinstance(v_, float) else v_) for k, v_ in results[sym]["kill_switch"][s_].items() if k in ("A_per_month", "months_to_25_A", "trailing12_worst_sum", "trailing12_below_kill_count")})
        vf = results[sym]["vault_family"]
        print("vault family:", vf["family_size"], "holm:", vf["holm_rejected_fwer_0_10"], "slot:", vf["bonferroni_slot_alpha_0_10_over_12_rejected"], "nominal:", vf["nominal_p_le_0_05"])
        for k, tst in sorted(vf["tests"].items(), key=lambda kv: kv[1]["p"])[:12]:
            print(f"   {k:28s} n={tst['n']:3d} mean={tst['mean']:7.2f} ci={np.round(tst['ci90'], 1)} p={tst['p']:.3f}")
        print("   specs (same statistic, not in the family):", {k: round(v_["p"], 3) for k, v_ in vf["specs_same_statistic_not_in_family"].items()})
    print("\ntrial ledger:", {k: (len(v_) if isinstance(v_, list) else v_) for k, v_ in ledger.items()})
    print("written:", OUT_JSON, OUT_CSV)


if __name__ == "__main__":
    main()
