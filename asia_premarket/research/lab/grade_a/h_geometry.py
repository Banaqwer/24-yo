#!/usr/bin/env python3
"""
h_geometry.py -- geometry and candidate-selection hypotheses of the Grade-A lab (group 'geometry').

Run from the project root:
    OMP_NUM_THREADS=1 python research/lab/grade_a/h_geometry.py

Inputs (read-only, written by honest_baseline.py): trades_honest_{SYM}.csv, candidates_{SYM}.csv.
Outputs: h_geometry_results.json, h_geometry_nights.csv (per-night baseline vs hypothesis P&L for every rule).

Decision time of every rule: 17:xx ET.  Rule inputs are the candidates table (geometry, causal probabilities,
guard flags) and 17:xx-knowable night features (med20_pts).  No rule changes the entry or the exit, so a night is
re-called from the candidates table (best EV among guard passers, else NO EDGE) and takes the chosen candidate's
own raw-bar resolution under the honest baseline fill (18:00 open, base costs, column pnl_net_open; sensitivity
pnl_net_open_hicost).  Outcome columns are used only (a) as P&L and (b) for H1, strictly before each month.

Hypotheses (LAB_DESIGN section 8, pre-registered single parameters):
  H2  target cap: a candidate with target_dist > 1.0 x med20_pts fails the guard ('target beyond expected range').
      Placebo: the same cap with a random other night's med20_pts (default_rng(0)).
  H3  dead-weight candidates: wide CONTINUATION removed from the candidate set; a wide fade with
      win_rate_on_resolution < 0.80 fails the guard.
  H11 scratch cap: a candidate with p_scratch > 0.30 fails the guard ('scratch too likely').
      Placebo: the cap applied to the p_scratch of a random other candidate of the same night (default_rng(0)).
  H1  winner's-curse calibration: confidence = walk-forward isotonic second stage of 'won on resolution' (target
      before stop under the open fill) against the raw ratio p_win/(p_win+p_loss) of the chosen candidate, fitted on
      the graded nights strictly before each month (min 40 resolved graded nights, raw ratio before that); re-graded
      with the 72/63/56 cutoffs.  Primary metric: calibration (ECE / mid-band gap); secondary: paired P&L.
  Confidence-band observation (no verdict): honest A P&L by confidence band and A >= 80 vs A >= 72.
  COMBO = H2 + H3 + H11 jointly; COMBO_H1 = the same with H1 fitted inside the combined pipeline.

Protocol: discovery = 2025-04-01..2026-05-31, vault = 2026-06-01..2026-11-06; parameters are the pre-registered ones
(an exploratory grid is run on discovery only and labelled as such); NQ primary, ES same-sign replication; splice
nights excluded from every statistic (rows kept, flagged); weekly-block bootstrap (ISO weeks, 2000 draws,
default_rng(0)) 90% CIs; random-filter null (2000 draws, default_rng(0)) for the A nights a rule removes.
"""
from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
os.chdir(ROOT)

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

GROUP = "geometry"
SPLITS = {"discovery": ("2025-04-01", "2026-05-31"), "vault": ("2026-06-01", "2026-11-06"),
          "full": ("2025-04-01", "2026-11-06")}
PV = {"NQ": 20.0, "ES": 50.0}
N_BOOT, SEED = 2000, 0
GRADES = ("A", "B", "C")
CUTS = ((72, "A"), (63, "B"), (56, "C"))
BANDS = [56, 63, 72, 80, 90, 101]           # calibration buckets [56,63) [63,72) [72,80) [80,90) [90,100]
A_BANDS = [72, 75, 80, 90, 101]             # confidence-band observation
# pre-registered parameters (LAB_DESIGN section 8)
H2_CAP = 1.0            # target_dist <= 1.0 x med20_pts
H3_WIDE_FADE_CONF = 0.80
H11_SCRATCH_CAP = 0.30
H1_MIN_ROWS = 40
PREDICTED = {"H2": "A avg +4..+6, A count -8%, ~8% of graded nights removed that win <= 40%",
             "H3": "A count -15%, A avg +21 -> >= +26 (i.e. +5 or more), worst A loss improves",
             "H11": "A scratch share 29% -> <= 20%, A avg +4..+8, n(A) -20%",
             "H1": "mid band [63,72) realised-vs-stated gap -> within 10 points; ~40% of B and ~50% of C -> NO EDGE; A membership change <= 20%; paired P&L not worse",
             "COMBO": "the three geometry rules jointly: A avg up, A count down",
             "COMBO_H1": "COMBO with the second-stage calibration: calibration gap closed, A avg not worse",
             "H2H3": "post-hoc joint rule of the two surviving geometry rules (H2 + H3): A avg up; not pre-registered as a pair"}


def months_in(split: str) -> float:
    a, b = (pd.Timestamp(x) for x in SPLITS[split])
    return (b - a).days / 365.25 * 12


# --------------------------------------------------------------------------------------------------
# loading and re-calling
# --------------------------------------------------------------------------------------------------
def load(sym: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = pd.read_csv(os.path.join(HERE, f"trades_honest_{sym}.csv"), parse_dates=["date"]).set_index("date").sort_index()
    c = pd.read_csv(os.path.join(HERE, f"candidates_{sym}.csv"), parse_dates=["date"])
    keep = ["date", "cand_id", "kind", "variant", "target_key", "side", "entry", "target", "stop", "target_dist", "stop_dist",
            "p_win", "p_loss", "scratch", "ev_pts", "win_rate_on_resolution", "guard_ok", "guard_reasons", "chosen",
            "outcome_open", "traded_open", "pnl_open", "pnl_net_open", "pnl_net_open_hicost", "grade", "splice"]
    c = c[keep].copy()
    c["row"] = np.arange(len(c))                                    # the engine's candidate order (tie-break)
    c["med20_pts"] = c["date"].map(t["med20_pts"])
    c["tfrac"] = c["target_dist"] / c["med20_pts"]
    return t, c.copy()


def grade_of(conf: float, guard_pass: bool) -> str:
    if not guard_pass or pd.isna(conf):
        return "NO EDGE"
    for cut, g in CUTS:
        if conf >= cut:
            return g
    return "NO EDGE"


def recall(t: pd.DataFrame, c: pd.DataFrame, ok_extra: pd.Series | None = None, drop: pd.Series | None = None) -> pd.DataFrame:
    """Re-call every night from the candidate rows that survive `drop`, with the guard tightened by `ok_extra`.
    Pool = guard passers (else every remaining candidate, graded NO EDGE); best = max EV, first in engine order on ties.
    Returns one row per night of the trades table (nights without candidates = NO TRADE '-', P&L 0)."""
    cc = c if drop is None else c[~drop.values]
    ok = cc["guard_ok"].astype(bool)
    if ok_extra is not None:
        ok = ok & ok_extra.loc[cc.index].astype(bool)
    cc = cc.assign(ok2=ok.values).copy()
    cc = cc.sort_values(["date", "ok2", "ev_pts", "row"], ascending=[True, False, False, True], kind="mergesort")
    best = cc.groupby("date", sort=True).head(1).set_index("date")
    out = pd.DataFrame(index=t.index)
    out["cand_id"] = best["cand_id"].reindex(t.index)
    out["guard_pass"] = best["ok2"].reindex(t.index).fillna(False).astype(bool)
    out["conf_raw"] = (best["win_rate_on_resolution"] * 100).reindex(t.index)
    out["grade"] = [grade_of(cf, gp) if isinstance(cid, str) else "-" for cid, cf, gp in zip(out["cand_id"], out["conf_raw"], out["guard_pass"])]
    graded = out["grade"].isin(GRADES)
    for col, src in (("pnl", "pnl_net_open"), ("pnl_hi", "pnl_net_open_hicost"), ("pnl_gross", "pnl_open")):
        out[f"cand_{col}"] = best[src].reindex(t.index).fillna(0.0).astype(float)   # the chosen candidate's own P&L (0 when unfillable)
        out[col] = np.where(graded, out[f"cand_{col}"], 0.0)
    for col in ("outcome_open", "traded_open", "kind", "variant", "target_key", "scratch", "target_dist", "stop_dist", "tfrac", "ev_pts"):
        out[col] = best[col].reindex(t.index)
    out["conf"] = out["conf_raw"]
    out["n_cands"] = cc.groupby("date").size().reindex(t.index).fillna(0).astype(int)
    out["n_pass"] = cc.groupby("date")["ok2"].sum().reindex(t.index).fillna(0).astype(int)
    return out


# --------------------------------------------------------------------------------------------------
# H1: walk-forward isotonic second stage on the chosen candidate's raw ratio
# --------------------------------------------------------------------------------------------------
def h1_stage(night: pd.DataFrame, splice: pd.Series, min_rows: int = H1_MIN_ROWS) -> tuple[pd.DataFrame, dict]:
    """night: a re-called frame (grade = first-stage grade).  For each OOS month, fit isotonic(y = won on resolution |
    x = raw ratio) on the first-stage graded nights strictly before the month whose chosen candidate was fillable at
    the open and resolved (target / stop); months with fewer than min_rows such nights keep the raw ratio.
    Scratch and unfillable nights are not labels (confidence = P(target | resolves)).  Splice nights never enter a fit."""
    out = night.copy()
    graded1 = out["grade"].isin(GRADES)
    resolved = out["outcome_open"].isin(["target", "stop"]) & (out["traded_open"] == 1)
    won = (out["outcome_open"] == "target").astype(float)
    conf2 = out["conf_raw"].copy()
    months = sorted(set(out.index.to_period("M")))
    diag = {}
    for m in months:
        start = m.to_timestamp()
        fit_mask = graded1 & resolved & (out.index < start) & (~splice.astype(bool))
        n_fit = int(fit_mask.sum())
        in_month = (out.index.to_period("M") == m) & out["guard_pass"]
        if n_fit >= min_rows:
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip")
            iso.fit(out.loc[fit_mask, "conf_raw"].values / 100.0, won[fit_mask].values)
            conf2[in_month] = iso.predict(out.loc[in_month, "conf_raw"].values / 100.0) * 100.0
            diag[str(m)] = {"fit_rows": n_fit, "mode": "isotonic", "nights_in_month": int(in_month.sum())}
        else:
            diag[str(m)] = {"fit_rows": n_fit, "mode": "raw", "nights_in_month": int(in_month.sum())}
    out["conf"] = conf2
    out["grade"] = [grade_of(cf, gp) if isinstance(cid, str) else "-" for cid, cf, gp in zip(out["cand_id"], out["conf"], out["guard_pass"])]
    graded = out["grade"].isin(GRADES)
    for col in ("pnl", "pnl_hi", "pnl_gross"):
        out[col] = np.where(graded, out[f"cand_{col}"], 0.0)   # the same chosen candidate; graded set re-cut by the new confidence
    diag["_promoted_from_no_edge"] = int((graded & ~graded1).sum())
    diag["_demoted_to_no_edge"] = int((graded1 & ~graded).sum())
    return out, diag


# --------------------------------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------------------------------
def iso_blocks(index: pd.DatetimeIndex) -> list[np.ndarray]:
    iso = index.isocalendar()
    keys = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).values
    return [np.flatnonzero(keys == k) for k in np.unique(keys)]


def block_boot(index: pd.DatetimeIndex, arrays: dict, stat_fn, n_boot: int = N_BOOT, seed: int = SEED) -> np.ndarray:
    """Weekly-block bootstrap: resample ISO-week blocks with replacement, evaluate stat_fn(dict of resampled arrays)
    (a vector), return the (n_boot x k) matrix of statistics.  numpy default_rng(seed) for every call."""
    blocks = iso_blocks(index)
    nb = len(blocks)
    rng = np.random.default_rng(seed)
    first = None
    res = None
    for i in range(n_boot):
        pick = rng.integers(0, nb, nb)
        idx = np.concatenate([blocks[j] for j in pick])
        v = np.atleast_1d(np.asarray(stat_fn({k: a[idx] for k, a in arrays.items()}), dtype=float))
        if res is None:
            res = np.empty((n_boot, len(v)))
        res[i] = v
    return res


def ci90(mat: np.ndarray, col: int) -> list[float]:
    v = mat[:, col]
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return [float("nan"), float("nan")]
    return [float(np.quantile(v, 0.05)), float(np.quantile(v, 0.95))]


def _mean(x):
    return float(np.mean(x)) if len(x) else float("nan")


def a_block(p: np.ndarray, untraded: np.ndarray | None = None) -> dict:
    n = len(p)
    out = {"n": int(n), "win": float((p > 0).mean()) if n else float("nan"), "avg": _mean(p), "total": float(p.sum()),
           "worst": float(p.min()) if n else float("nan"), "best": float(p.max()) if n else float("nan"),
           "sd": float(p.std(ddof=1)) if n > 1 else float("nan")}
    out["pts_per_sigma"] = out["avg"] / out["sd"] if n > 1 and out["sd"] > 0 else float("nan")
    if untraded is not None:
        out["untraded"] = int(untraded.sum())
    return out


def paired_stats(d: np.ndarray) -> dict:
    return {"n": int(len(d)), "mean": _mean(d), "total": float(d.sum()), "win_share": float((d > 0).mean()) if len(d) else float("nan")}


def random_filter_null(base_pnl: np.ndarray, keep_mask: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """base_pnl: baseline P&L of the population (e.g. baseline A nights); keep_mask: nights the rule keeps.
    Null: remove the same number of random nights; statistic = mean baseline P&L of the kept nights.
    Percentile = share of null draws at or below the actual (high = the removed nights were worse than random)."""
    n = len(base_pnl)
    n_d = int((~keep_mask).sum())
    if n == 0 or n_d == 0 or n_d >= n:
        return {"n_population": int(n), "n_removed": n_d, "actual_kept_avg": _mean(base_pnl[keep_mask]) if n else float("nan"),
                "null_mean": float("nan"), "null_p95": float("nan"), "percentile": float("nan")}
    rng = np.random.default_rng(seed)
    tot = base_pnl.sum()
    draws = np.empty(n_boot)
    for i in range(n_boot):
        rem = rng.choice(n, n_d, replace=False)
        draws[i] = (tot - base_pnl[rem].sum()) / (n - n_d)
    actual = float(base_pnl[keep_mask].mean())
    return {"n_population": int(n), "n_removed": n_d, "actual_kept_avg": actual, "null_mean": float(draws.mean()),
            "null_p95": float(np.quantile(draws, 0.95)), "percentile": float(100.0 * (draws <= actual).mean())}


def ece_table(conf: np.ndarray, won: np.ndarray, resolved: np.ndarray, graded: np.ndarray) -> dict:
    """Calibration on resolved graded nights (confidence = P(target | resolves)).  Buckets by stated confidence."""
    m = resolved & graded
    c, w = conf[m], won[m]
    rows = []
    n_tot = int(m.sum())
    acc = 0.0
    mid_gap = float("nan")
    # the [0,56) bucket is empty by construction on a graded population; it is populated only when the new confidence of a
    # fixed (baseline-graded) population is scored, and it then counts in the pooled ECE like every other bucket
    for lo, hi in zip([0] + BANDS[:-1], BANDS):
        b = (c >= lo) & (c < hi)
        n = int(b.sum())
        stated = _mean(c[b])
        realised = 100.0 * _mean(w[b]) if n else float("nan")
        gap = realised - stated if n else float("nan")
        rows.append({"bucket": f"[{lo},{hi if hi < 101 else 100})", "n": n, "stated": stated, "realised": realised, "gap": gap})
        if n:
            acc += n * abs(gap)
        if lo == 63:
            mid_gap = gap
    return {"n_resolved_graded": n_tot, "buckets": rows, "ece_pooled": acc / n_tot if n_tot else float("nan"), "mid_band_gap": mid_gap,
            "mid_band_abs_gap": abs(mid_gap) if not np.isnan(mid_gap) else float("nan")}


def _ece_scalar(conf, won, resolved, graded):
    return ece_table(conf, won, resolved, graded)["ece_pooled"]


def _mid_abs_gap(conf, won, resolved, graded):
    return ece_table(conf, won, resolved, graded)["mid_band_abs_gap"]


# --------------------------------------------------------------------------------------------------
# evaluation of one rule against the baseline on one split
# --------------------------------------------------------------------------------------------------
def split_mask(index: pd.DatetimeIndex, split: str, splice: pd.Series) -> np.ndarray:
    a, b = (pd.Timestamp(x) for x in SPLITS[split])
    return ((index >= a) & (index <= b) & (~splice.astype(bool).values)).astype(bool)


def evaluate(base: pd.DataFrame, hyp: pd.DataFrame, split: str, sym: str, splice: pd.Series, with_null: bool = True) -> dict:
    m = split_mask(base.index, split, splice)
    b, h = base[m], hyp[m]
    idx = b.index
    pv, months = PV[sym], months_in(split)
    isA_b, isA_h = (b["grade"] == "A").values, (h["grade"] == "A").values
    gr_b, gr_h = b["grade"].isin(GRADES).values, h["grade"].isin(GRADES).values
    pb, ph = b["pnl"].values.astype(float), h["pnl"].values.astype(float)
    pbh, phh = b["pnl_hi"].values.astype(float), h["pnl_hi"].values.astype(float)
    changed = ((b["cand_id"].fillna("") != h["cand_id"].fillna("")) | (b["grade"] != h["grade"])).values
    a_either = isA_b | isA_h
    d = ph - pb

    def stat(ar):
        ab, ah = ar["isA_b"].astype(bool), ar["isA_h"].astype(bool)
        gb, gh = ar["gr_b"].astype(bool), ar["gr_h"].astype(bool)
        ch, ae = ar["changed"].astype(bool), ar["a_either"].astype(bool)
        dd = ar["ph"] - ar["pb"]
        return [_mean(ar["ph"][ah]) - _mean(ar["pb"][ab]),          # 0 A avg diff
                _mean(ar["ph"][gh]) - _mean(ar["pb"][gb]),          # 1 graded avg diff
                _mean(dd),                                          # 2 all-night paired
                _mean(dd[ch]),                                      # 3 changed nights paired
                _mean(dd[ae]),                                      # 4 A-either paired
                _mean(ar["phh"][ah]) - _mean(ar["pbh"][ab]),        # 5 A avg diff, high costs
                _mean(ar["ph"][ah]),                                # 6 A avg hyp
                _mean(ar["pb"][ab])]                                # 7 A avg base
    arrays = {"isA_b": isA_b, "isA_h": isA_h, "gr_b": gr_b, "gr_h": gr_h, "changed": changed, "a_either": a_either,
              "pb": pb, "ph": ph, "pbh": pbh, "phh": phh}
    mat = block_boot(idx, arrays, stat)
    out = {
        "split": split, "n_nights": int(m.sum()),
        "A_before": a_block(pb[isA_b], (b["traded_open"].values[isA_b] == 0)), "A_after": a_block(ph[isA_h], (h["traded_open"].values[isA_h] == 0)),
        "A_before_hicost": a_block(pbh[isA_b]), "A_after_hicost": a_block(phh[isA_h]),
        "graded_before": a_block(pb[gr_b]), "graded_after": a_block(ph[gr_h]),
        "B_before": a_block(pb[(b["grade"] == "B").values]), "B_after": a_block(ph[(h["grade"] == "B").values]),
        "C_before": a_block(pb[(b["grade"] == "C").values]), "C_after": a_block(ph[(h["grade"] == "C").values]),
        "effect_A_avg": _mean(ph[isA_h]) - _mean(pb[isA_b]), "effect_A_avg_ci90": ci90(mat, 0),
        "effect_A_avg_hicost": _mean(phh[isA_h]) - _mean(pbh[isA_b]), "effect_A_avg_hicost_ci90": ci90(mat, 5),
        "effect_graded_avg": _mean(ph[gr_h]) - _mean(pb[gr_b]), "effect_graded_avg_ci90": ci90(mat, 1),
        "paired_all_nights": {**paired_stats(d), "ci90": ci90(mat, 2)},
        "paired_changed_nights": {**paired_stats(d[changed]), "ci90": ci90(mat, 3)},
        "paired_A_either_nights": {**paired_stats(d[a_either]), "ci90": ci90(mat, 4)},
        "n_affected": int(changed.sum()),
        "A_membership": {"retained": int((isA_b & isA_h).sum()), "dropped": int((isA_b & ~isA_h).sum()), "added": int((~isA_b & isA_h).sum()),
                         "jaccard": float((isA_b & isA_h).sum() / max(1, (isA_b | isA_h).sum())),
                         "retained_base_avg": _mean(pb[isA_b & isA_h]), "retained_hyp_avg": _mean(ph[isA_b & isA_h]),
                         "dropped_base_avg": _mean(pb[isA_b & ~isA_h]), "dropped_base_win": float((pb[isA_b & ~isA_h] > 0).mean()) if (isA_b & ~isA_h).sum() else float("nan"),
                         "added_hyp_avg": _mean(ph[~isA_b & isA_h]), "added_hyp_win": float((ph[~isA_b & isA_h] > 0).mean()) if (~isA_b & isA_h).sum() else float("nan"),
                         "dropped_dates": [str(x.date()) for x in idx[isA_b & ~isA_h]], "added_dates": [str(x.date()) for x in idx[~isA_b & isA_h]]},
        "graded_membership": {"retained": int((gr_b & gr_h).sum()), "dropped": int((gr_b & ~gr_h).sum()), "added": int((~gr_b & gr_h).sum()),
                              "dropped_base_avg": _mean(pb[gr_b & ~gr_h]), "dropped_base_win": float((pb[gr_b & ~gr_h] > 0).mean()) if (gr_b & ~gr_h).sum() else float("nan")},
        "usd_per_contract_per_year_A": float((ph[isA_h].sum() - pb[isA_b].sum()) * pv * 12 / months),
        "usd_per_contract_per_year_all_nights": float(d.sum() * pv * 12 / months),
        "A_scratch_share_before": float((b["outcome_open"].values[isA_b] == "scratch").mean()) if isA_b.sum() else float("nan"),
        "A_scratch_share_after": float((h["outcome_open"].values[isA_h] == "scratch").mean()) if isA_h.sum() else float("nan"),
    }
    if with_null:
        out["random_filter_null_A"] = random_filter_null(pb[isA_b], isA_h[isA_b])
        out["random_filter_null_graded"] = random_filter_null(pb[gr_b], gr_h[gr_b])
    return out


def calibration_eval(base: pd.DataFrame, hyp: pd.DataFrame, split: str, splice: pd.Series) -> dict:
    m = split_mask(base.index, split, splice)
    b, h = base[m], hyp[m]
    resolved = (b["outcome_open"].isin(["target", "stop"]) & (b["traded_open"] == 1)).values   # same candidate under H1
    won = (b["outcome_open"] == "target").values.astype(float)
    cb, ch = b["conf"].values.astype(float), h["conf"].values.astype(float)
    gb, gh = b["grade"].isin(GRADES).values, h["grade"].isin(GRADES).values
    before, after = ece_table(cb, won, resolved, gb), ece_table(ch, won, resolved, gh)
    after_fixed_pop = ece_table(ch, won, resolved, gb)        # the new confidence scored on the BASELINE graded population
    arrays = {"cb": cb, "ch": ch, "won": won, "res": resolved, "gb": gb, "gh": gh}

    def stat(ar):
        r, g1, g2 = ar["res"].astype(bool), ar["gb"].astype(bool), ar["gh"].astype(bool)
        return [_ece_scalar(ar["ch"], ar["won"], r, g2) - _ece_scalar(ar["cb"], ar["won"], r, g1),
                _mid_abs_gap(ar["ch"], ar["won"], r, g2) - _mid_abs_gap(ar["cb"], ar["won"], r, g1),
                _mid_abs_gap(ar["ch"], ar["won"], r, g2)]
    mat = block_boot(b.index, arrays, stat)
    counts_b, counts_h = b["grade"].value_counts().to_dict(), h["grade"].value_counts().to_dict()
    trans = pd.crosstab(b["grade"], h["grade"])
    return {"split": split, "before": before, "after": after, "after_on_baseline_graded_population": after_fixed_pop,
            "ece_diff": after["ece_pooled"] - before["ece_pooled"], "ece_diff_ci90": ci90(mat, 0),
            "mid_abs_gap_diff": after["mid_band_abs_gap"] - before["mid_band_abs_gap"], "mid_abs_gap_diff_ci90": ci90(mat, 1),
            "mid_abs_gap_after_ci90": ci90(mat, 2),
            "grade_counts_before": {g: int(counts_b.get(g, 0)) for g in ("A", "B", "C", "NO EDGE", "-")},
            "grade_counts_after": {g: int(counts_h.get(g, 0)) for g in ("A", "B", "C", "NO EDGE", "-")},
            "B_to_no_edge_share": float((h["grade"][b["grade"] == "B"] == "NO EDGE").mean()) if (b["grade"] == "B").any() else float("nan"),
            "C_to_no_edge_share": float((h["grade"][b["grade"] == "C"] == "NO EDGE").mean()) if (b["grade"] == "C").any() else float("nan"),
            "transition": {str(i): {str(c): int(trans.loc[i, c]) for c in trans.columns} for i in trans.index},
            "confidence_before_mean_A": _mean(cb[(b["grade"] == "A").values]), "confidence_after_mean_A": _mean(ch[(h["grade"] == "A").values])}


def confidence_bands(base: pd.DataFrame, split: str, splice: pd.Series) -> dict:
    m = split_mask(base.index, split, splice)
    b = base[m]
    a = b[b["grade"] == "A"]
    rows = []
    for lo, hi in zip(A_BANDS[:-1], A_BANDS[1:]):
        s = a[(a["conf"] >= lo) & (a["conf"] < hi)]
        rows.append({"band": f"[{lo},{hi if hi < 101 else 100})", **a_block(s["pnl"].values.astype(float)),
                     "scratch_share": float((s["outcome_open"] == "scratch").mean()) if len(s) else float("nan")})
    hi80 = a[a["conf"] >= 80]
    lo80 = a[a["conf"] < 80]
    return {"split": split, "bands": rows, "A_at_72": a_block(a["pnl"].values.astype(float)), "A_at_80": a_block(hi80["pnl"].values.astype(float)),
            "A_72_to_80_only": a_block(lo80["pnl"].values.astype(float)),
            "A80_beats_A72_per_night": bool(_mean(hi80["pnl"].values) > _mean(a["pnl"].values)) if len(hi80) and len(a) else None,
            "A80_beats_A72_total": bool(hi80["pnl"].sum() > a["pnl"].sum()) if len(hi80) and len(a) else None}


# --------------------------------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------------------------------
def rule_masks(t: pd.DataFrame, c: pd.DataFrame) -> dict:
    """Each rule = (ok_extra over candidate rows, drop over candidate rows).  Built only from 17:xx-knowable columns."""
    rules = {}
    rules["H2"] = (~(c["tfrac"] > H2_CAP), None)
    # H2 placebo: the cap with a random OTHER night's med20_pts (derangement over the nights of the trades table)
    rng = np.random.default_rng(SEED)
    nights = t.index.values
    n_n = len(nights)
    perm = rng.permutation(n_n)
    while True:                                   # derangement: every night gets ANOTHER night's med20
        fixed = np.flatnonzero(perm == np.arange(n_n))
        if len(fixed) == 0:
            break
        for i in fixed:
            j = int(rng.integers(0, n_n))
            perm[i], perm[j] = perm[j], perm[i]
    assert not (perm == np.arange(n_n)).any(), "placebo permutation has a fixed point"
    med_placebo = pd.Series(t["med20_pts"].values[perm], index=t.index)
    tfrac_pl = c["target_dist"] / c["date"].map(med_placebo)
    rules["H2_placebo"] = (~(tfrac_pl > H2_CAP), None)
    # H3: drop wide continuation; wide fade needs win_rate_on_resolution >= 0.80
    drop3 = (c["kind"] == "CONTINUATION") & (c["variant"] == "wide")
    ok3 = ~((c["kind"] == "MEAN REVERSION") & (c["variant"] == "wide") & (c["win_rate_on_resolution"] < H3_WIDE_FADE_CONF))
    rules["H3"] = (ok3, drop3)
    # H11: scratch cap
    rules["H11"] = (~(c["scratch"] > H11_SCRATCH_CAP), None)
    # H11 placebo: the cap on the p_scratch of a random other candidate of the same night
    rng = np.random.default_rng(SEED)
    other_scratch = np.empty(len(c))
    for _, g in c.groupby("date", sort=True):
        pos = g.index.values
        sc = g["scratch"].values
        for i, p in enumerate(pos):
            if len(pos) == 1:
                other_scratch[p] = sc[i]
            else:
                j = rng.integers(0, len(pos) - 1)
                j = j if j < i else j + 1
                other_scratch[p] = sc[j]
    rules["H11_placebo"] = (~(pd.Series(other_scratch, index=c.index) > H11_SCRATCH_CAP), None)
    # COMBO = H2 + H3 + H11 (the pre-registered joint rule of the group); H2H3 = the two rules that are not 'no effect' / 'harmful'
    rules["COMBO"] = (rules["H2"][0] & ok3 & rules["H11"][0], drop3)
    rules["H2H3"] = (rules["H2"][0] & ok3, drop3)
    return rules


def exploratory_grid(t: pd.DataFrame, c: pd.DataFrame, base: pd.DataFrame, splice: pd.Series, sym: str) -> list[dict]:
    """Other parameter values, DISCOVERY ONLY (never scored on the vault); labelled exploratory."""
    out = []
    grid = [("H2", "cap", v, (~(c["tfrac"] > v), None)) for v in (0.75, 1.25)]
    grid += [("H11", "cap", v, (~(c["scratch"] > v), None)) for v in (0.25, 0.40)]
    grid += [("H3", "wide_fade_conf", v, (~((c["kind"] == "MEAN REVERSION") & (c["variant"] == "wide") & (c["win_rate_on_resolution"] < v)),
                                        (c["kind"] == "CONTINUATION") & (c["variant"] == "wide"))) for v in (0.75, 0.85)]
    for hid, pname, v, (ok, drop) in grid:
        hyp = recall(t, c, ok, drop)
        m = split_mask(base.index, "discovery", splice)
        b, h = base[m], hyp[m]
        out.append({"hypothesis": hid, "parameter": pname, "value": v, "split": "discovery", "label": "EXPLORATORY (not pre-registered; not scored on the vault)",
                    "A_n_before": int((b["grade"] == "A").sum()), "A_n_after": int((h["grade"] == "A").sum()),
                    "A_avg_before": _mean(b["pnl"][b["grade"] == "A"].values), "A_avg_after": _mean(h["pnl"][h["grade"] == "A"].values),
                    "paired_all_nights_mean": _mean((h["pnl"] - b["pnl"]).values)})
    return out


# --------------------------------------------------------------------------------------------------
# verdicts
# --------------------------------------------------------------------------------------------------
def verdict_pnl(res: dict, predicted_sign: int = +1) -> tuple[str, str]:
    """res: {split: evaluate(...)} ; effect = A avg change (predicted_sign * effect > 0 = predicted direction)."""
    v, f, dsc = res["vault"], res["full"], res["discovery"]
    s = predicted_sign
    n_aff_v = v["n_affected"]
    e_v, ci_v = s * v["effect_A_avg"], [s * x for x in v["effect_A_avg_ci90"]]
    e_f, ci_f = s * f["effect_A_avg"], [s * x for x in f["effect_A_avg_ci90"]]
    e_d, ci_d = s * dsc["effect_A_avg"], [s * x for x in dsc["effect_A_avg_ci90"]]
    rf_v = v.get("random_filter_null_A", {}).get("percentile", float("nan"))
    rf_f = f.get("random_filter_null_A", {}).get("percentile", float("nan"))
    ci_v_s, ci_f_s, ci_d_s = sorted(ci_v), sorted(ci_f), sorted(ci_d)
    why = []
    if n_aff_v < 8:
        return "not testable at this n", f"only {n_aff_v} affected vault nights (< 8)"
    if e_f < 0 and ci_f_s[1] < 0:
        return "harmful", f"full-window A-avg effect {e_f * s:+.1f} with 90% CI {[round(x * s, 1) for x in ci_f_s]} excluding zero against the prediction"
    vault_ci_ok = ci_v_s[0] > 0
    full_ci_ok = ci_f_s[0] > 0 and (ci_f_s[0] <= e_v <= ci_f_s[1]) and (not np.isnan(rf_f) and rf_f >= 90)
    if e_v > 0 and (vault_ci_ok or full_ci_ok):
        why.append("vault sign as predicted; " + ("vault CI excludes zero" if vault_ci_ok else f"full CI excludes zero, vault point inside it, random-filter pct {rf_f:.0f}"))
        return "supported on vault", "; ".join(why)
    disc_ok = e_d > 0 and ci_d_s[0] > 0
    if disc_ok:
        return "discovery only", f"discovery A-avg effect {e_d * s:+.1f} CI {[round(x * s, 1) for x in ci_d_s]} excludes zero; vault effect {e_v * s:+.1f} CI {[round(x * s, 1) for x in ci_v_s]} does not (random-filter pct vault {rf_v:.0f}, full {rf_f:.0f})"
    return "no effect", f"vault A-avg effect {e_v * s:+.1f} CI {[round(x * s, 1) for x in ci_v_s]}, full {e_f * s:+.1f} CI {[round(x * s, 1) for x in ci_f_s]}, discovery {e_d * s:+.1f} CI {[round(x * s, 1) for x in ci_d_s]}"


def verdict_calibration(cal: dict, pnl: dict) -> tuple[str, str]:
    """H1: primary = pooled ECE change (predicted negative); the paired all-night P&L must not be worse (CI upper >= 0)."""
    v, f, dsc = cal["vault"], cal["full"], cal["discovery"]
    n_aff_v = pnl["vault"]["n_affected"]
    if n_aff_v < 8:
        return "not testable at this n", f"only {n_aff_v} affected vault nights (< 8)"
    pnl_worse = pnl["full"]["paired_all_nights"]["ci90"][1] < 0
    if (f["ece_diff"] > 0 and f["ece_diff_ci90"][0] > 0) or pnl_worse:
        return "harmful", f"full-window ECE change {f['ece_diff']:+.1f} CI {[round(x, 1) for x in f['ece_diff_ci90']]}; paired all-night P&L CI {[round(x, 1) for x in pnl['full']['paired_all_nights']['ci90']]}"
    vault_ok = v["ece_diff"] < 0 and v["ece_diff_ci90"][1] < 0
    full_ok = f["ece_diff_ci90"][1] < 0 and (f["ece_diff_ci90"][0] <= v["ece_diff"] <= f["ece_diff_ci90"][1]) and v["ece_diff"] < 0
    if vault_ok or full_ok:
        return "supported on vault", f"vault ECE change {v['ece_diff']:+.1f} CI {[round(x, 1) for x in v['ece_diff_ci90']]}; full {f['ece_diff']:+.1f} CI {[round(x, 1) for x in f['ece_diff_ci90']]}"
    if dsc["ece_diff"] < 0 and dsc["ece_diff_ci90"][1] < 0:
        return "discovery only", f"discovery ECE change {dsc['ece_diff']:+.1f} CI {[round(x, 1) for x in dsc['ece_diff_ci90']]}; vault {v['ece_diff']:+.1f} CI {[round(x, 1) for x in v['ece_diff_ci90']]}"
    return "no effect", f"ECE change vault {v['ece_diff']:+.1f} CI {[round(x, 1) for x in v['ece_diff_ci90']]}, full {f['ece_diff']:+.1f} CI {[round(x, 1) for x in f['ece_diff_ci90']]}, discovery {dsc['ece_diff']:+.1f} CI {[round(x, 1) for x in dsc['ece_diff_ci90']]}"


# --------------------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------------------
def fmt(x, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "nan"
    return f"{x:.{nd}f}"


def print_rule_table(sym: str, name: str, res: dict):
    print(f"\n[{sym}] {name}")
    print(f"  {'split':10s} {'A n b->a':>10s} {'A avg b->a':>16s} {'dA_avg':>8s} {'CI90':>16s} {'win b->a':>12s} {'worst b->a':>14s} "
          f"{'pts/sig b->a':>13s} {'all-night':>9s} {'CI90':>16s} {'n_aff':>5s} {'rf%':>5s} {'USD/yr(A)':>10s}")
    for sp in ("discovery", "vault", "full"):
        r = res[sp]
        ab, aa = r["A_before"], r["A_after"]
        rf = r.get("random_filter_null_A", {}).get("percentile", float("nan"))
        print(f"  {sp:10s} {ab['n']:>4d}->{aa['n']:<4d} {fmt(ab['avg']):>7s}->{fmt(aa['avg']):<7s} {fmt(r['effect_A_avg']):>8s} "
              f"[{fmt(r['effect_A_avg_ci90'][0])},{fmt(r['effect_A_avg_ci90'][1])}]".ljust(17) +
              f" {fmt(ab['win'], 2):>5s}->{fmt(aa['win'], 2):<5s} {fmt(ab['worst'], 0):>6s}->{fmt(aa['worst'], 0):<6s} "
              f"{fmt(ab['pts_per_sigma'], 2):>5s}->{fmt(aa['pts_per_sigma'], 2):<6s} {fmt(r['paired_all_nights']['mean'], 2):>9s} "
              f"[{fmt(r['paired_all_nights']['ci90'][0])},{fmt(r['paired_all_nights']['ci90'][1])}]".ljust(17) +
              f" {r['n_affected']:>5d} {fmt(rf, 0):>5s} {fmt(r['usd_per_contract_per_year_A'], 0):>10s}")


def run_symbol(sym: str) -> tuple[dict, pd.DataFrame]:
    t0 = time.time()
    t, c = load(sym)
    splice = t["splice"].fillna(0).astype(int)
    base = recall(t, c)
    # self-check: the re-call reproduces the honest baseline exactly
    hb = t["grade"].values
    assert (base["grade"].values == hb).all(), "re-call does not reproduce the honest grades"
    hp = t["pnl_net_open"].fillna(0.0).values
    assert np.allclose(base["pnl"].values, hp, atol=1e-9), "re-call does not reproduce pnl_net_open"
    same_cid = (base["cand_id"].fillna("").values == t["cand_id"].fillna("").values)
    assert same_cid.all(), "re-call does not reproduce the chosen candidate"
    rules = rule_masks(t, c)
    hyps: dict[str, pd.DataFrame] = {}
    for name, (ok, drop) in rules.items():
        hyps[name] = recall(t, c, ok, drop)
    h1_base, h1_diag = h1_stage(base, splice)
    hyps["H1"] = h1_base
    combo_h1, combo_h1_diag = h1_stage(hyps["COMBO"], splice)
    hyps["COMBO_H1"] = combo_h1
    results = {"symbol": sym, "n_nights": int(len(t)), "n_splice_excluded": int(splice.sum()), "rules": {}, "h1_fit_diag": h1_diag,
               "combo_h1_fit_diag": combo_h1_diag}
    for name in ("H2", "H2_placebo", "H3", "H11", "H11_placebo", "H1", "COMBO", "COMBO_H1", "H2H3"):
        results["rules"][name] = {sp: evaluate(base, hyps[name], sp, sym, splice) for sp in SPLITS}
        print_rule_table(sym, name, results["rules"][name])
    # calibration (H1 on the baseline, and inside the combined rule)
    results["calibration"] = {"H1": {sp: calibration_eval(base, h1_base, sp, splice) for sp in SPLITS},
                              "COMBO_H1": {sp: calibration_eval(hyps["COMBO"], combo_h1, sp, splice) for sp in SPLITS}}
    for sp in SPLITS:
        cb, ca = results["calibration"]["H1"][sp]["before"], results["calibration"]["H1"][sp]["after"]
        print(f"\n[{sym}] H1 calibration {sp}: ECE {fmt(cb['ece_pooled'])} -> {fmt(ca['ece_pooled'])} (diff CI {[round(x, 1) for x in results['calibration']['H1'][sp]['ece_diff_ci90']]}); "
              f"mid band gap {fmt(cb['mid_band_gap'])} -> {fmt(ca['mid_band_gap'])}; grades {results['calibration']['H1'][sp]['grade_counts_before']} -> {results['calibration']['H1'][sp]['grade_counts_after']}")
        for rb, ra in zip(cb["buckets"], ca["buckets"]):
            print(f"    {rb['bucket']:9s} before n={rb['n']:3d} stated {fmt(rb['stated'])} realised {fmt(rb['realised'])} | after n={ra['n']:3d} stated {fmt(ra['stated'])} realised {fmt(ra['realised'])}")
    # confidence bands (observation)
    results["confidence_bands"] = {sp: confidence_bands(base, sp, splice) for sp in SPLITS}
    for sp in SPLITS:
        cbnd = results["confidence_bands"][sp]
        print(f"\n[{sym}] honest A by confidence band, {sp}: " + "; ".join(f"{r['band']} n={r['n']} avg {fmt(r['avg'])} total {fmt(r['total'], 0)} win {fmt(r['win'], 2)}" for r in cbnd["bands"]) +
              f" | A>=80: n={cbnd['A_at_80']['n']} avg {fmt(cbnd['A_at_80']['avg'])} total {fmt(cbnd['A_at_80']['total'], 0)} vs A>=72: n={cbnd['A_at_72']['n']} avg {fmt(cbnd['A_at_72']['avg'])} total {fmt(cbnd['A_at_72']['total'], 0)}")
    # combined: vault honest-A survivors
    for name in ("COMBO", "COMBO_H1", "H2H3"):
        m = split_mask(base.index, "vault", splice)
        b, h = base[m], hyps[name][m]
        surv = (b["grade"] == "A") & (h["grade"] == "A")
        results["rules"][name]["vault_honest_A_survivors"] = {"n_honest_A": int((b["grade"] == "A").sum()), "n_survive": int(surv.sum()),
                                                              "survivors_base_avg": _mean(b["pnl"][surv].values), "survivors_hyp_avg": _mean(h["pnl"][surv].values),
                                                              "non_survivors_base_avg": _mean(b["pnl"][(b["grade"] == "A") & ~surv].values)}
    # exploratory grid on discovery only
    results["exploratory_discovery_only"] = exploratory_grid(t, c, base, splice, sym)
    # verdicts
    results["verdicts"] = {}
    for name in ("H2", "H3", "H11", "COMBO", "H2H3"):
        v, why = verdict_pnl(results["rules"][name])
        results["verdicts"][name] = {"verdict": v, "why": why, "predicted": PREDICTED[name]}
    # degeneracy guard (LAB_DESIGN 2.7): >= 2.5 A nights/month on discovery and >= 60% of discovery A P&L retained
    results["degeneracy_guard_discovery"] = {}
    for name in ("H2", "H3", "H11", "H1", "COMBO", "COMBO_H1", "H2H3"):
        r = results["rules"][name]["discovery"]
        per_month = r["A_after"]["n"] / months_in("discovery")
        base_total = r["A_before"]["total"]
        retained = r["A_after"]["total"] / base_total if base_total else float("nan")
        results["degeneracy_guard_discovery"][name] = {"A_per_month": per_month, "A_pnl_retained_frac": retained,
                                                       "passes": bool(per_month >= 2.5 and (np.isnan(retained) or retained >= 0.6))}
    v, why = verdict_calibration(results["calibration"]["H1"], results["rules"]["H1"])
    results["verdicts"]["H1"] = {"verdict": v, "why": why, "predicted": PREDICTED["H1"]}
    v, why = verdict_pnl(results["rules"]["COMBO_H1"])
    results["verdicts"]["COMBO_H1"] = {"verdict": v, "why": why, "predicted": PREDICTED["COMBO_H1"]}
    # placebo share of the claimed effect (A avg, full window)
    for name, pl in (("H2", "H2_placebo"), ("H11", "H11_placebo")):
        for sp in SPLITS:
            e, ep = results["rules"][name][sp]["effect_A_avg"], results["rules"][pl][sp]["effect_A_avg"]
            results["rules"][name][sp]["placebo_effect_A_avg"] = ep
            results["rules"][name][sp]["placebo_share_of_effect"] = float(ep / e) if e not in (0.0,) and not np.isnan(e) else float("nan")
    # per-night table
    night = pd.DataFrame({"sym": sym, "date": t.index.strftime("%Y-%m-%d"), "split": t["split"].values, "splice": splice.values,
                          "sunday_open": t["sunday_open"].values, "med20_pts": t["med20_pts"].values,
                          "v0_grade": t["v0_grade"].values, "v0_pnl_pts": t["v0_pnl_pts"].values,
                          "base_grade": base["grade"].values, "base_cand_id": base["cand_id"].values, "base_conf": base["conf"].values,
                          "base_tfrac": base["tfrac"].values, "base_scratch": base["scratch"].values, "base_outcome_open": base["outcome_open"].values,
                          "base_pnl_net_open": base["pnl"].values, "base_pnl_net_open_hicost": base["pnl_hi"].values})
    for name, h in hyps.items():
        night[f"{name}_grade"] = h["grade"].values
        night[f"{name}_cand_id"] = h["cand_id"].values
        night[f"{name}_conf"] = np.round(h["conf"].values.astype(float), 2)
        night[f"{name}_pnl_net_open"] = h["pnl"].values
        night[f"{name}_pnl_net_open_hicost"] = h["pnl_hi"].values
        night[f"{name}_changed"] = ((base["cand_id"].fillna("") != h["cand_id"].fillna("")) | (base["grade"] != h["grade"])).astype(int).values
    print(f"\n[{sym}] degeneracy guard (discovery): " + "; ".join(f"{k}: {v['A_per_month']:.2f} A/month, {v['A_pnl_retained_frac']:.2f} of A P&L, {'pass' if v['passes'] else 'FAIL'}"
                                                             for k, v in results["degeneracy_guard_discovery"].items()))
    print(f"[{sym}] runtime {time.time() - t0:.1f} s")
    return results, night


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def main():
    syms = sys.argv[1:] or ["NQ", "ES"]
    all_res = {"group": GROUP, "generated_from": "research/lab/grade_a/h_geometry.py", "baseline_pnl_column": "pnl_net_open (18:00-open fill, own-pair resolution, base costs); sensitivity pnl_net_open_hicost",
               "splits": SPLITS, "months": {sp: months_in(sp) for sp in SPLITS}, "bootstrap": {"blocks": "ISO week", "draws": N_BOOT, "rng": "numpy default_rng(0)", "ci": "90%"},
               "random_filter_null": "2000 random removals of the same count from the baseline A (and graded) population of the split; statistic = baseline mean P&L of the kept nights; percentile of the actual kept set",
               "parameters": {"H2_cap_x_med20": H2_CAP, "H3_wide_fade_min_win_rate": H3_WIDE_FADE_CONF, "H3_drop": "CONTINUATION|wide", "H11_scratch_cap": H11_SCRATCH_CAP, "H1_min_fit_rows": H1_MIN_ROWS,
                              "grade_cutoffs": {"A": 72, "B": 63, "C": 56}},
               "decision_time": "17:xx ET for every rule (H1's calibrator is refitted monthly on nights strictly before the month)",
               "ex_post_inputs_not_used": ["outcome_open / resolved_k / scratch outcomes except as P&L and, for H1, as labels strictly before each month",
                                           "asia_n_bars, n_bars, move_18_20_in_dir, pA_* bar-close detector outputs (checkpoint inputs, not 17:xx)",
                                           "v0_p_*, v0_guard_ok, v0_ev_pts_cand (pooled-calibrator / full-sample-regressor columns, leaky)",
                                           "realised Asia range (the cap uses the prior-20-night median med20_pts, knowable at 17:xx)",
                                           "catalogue tags, in_catalogue, kospi_next, n225_next, the other symbol's outcome"],
               "symbols": {}}
    nights = []
    for sym in syms:
        res, night = run_symbol(sym)
        all_res["symbols"][sym] = res
        nights.append(night)
    if len(syms) == 2:
        rep = {}
        for name in ("H2", "H3", "H11", "COMBO", "COMBO_H1", "H2H3"):
            rep[name] = {sp: {"NQ_effect_A_avg": all_res["symbols"]["NQ"]["rules"][name][sp]["effect_A_avg"],
                              "ES_effect_A_avg": all_res["symbols"]["ES"]["rules"][name][sp]["effect_A_avg"],
                              "same_sign": bool(np.sign(all_res["symbols"]["NQ"]["rules"][name][sp]["effect_A_avg"]) == np.sign(all_res["symbols"]["ES"]["rules"][name][sp]["effect_A_avg"])),
                              "NQ_all_night": all_res["symbols"]["NQ"]["rules"][name][sp]["paired_all_nights"]["mean"],
                              "ES_all_night": all_res["symbols"]["ES"]["rules"][name][sp]["paired_all_nights"]["mean"],
                              "ES_all_night_ci90": all_res["symbols"]["ES"]["rules"][name][sp]["paired_all_nights"]["ci90"]} for sp in SPLITS}
        rep["H1"] = {sp: {"NQ_ece_diff": all_res["symbols"]["NQ"]["calibration"]["H1"][sp]["ece_diff"], "ES_ece_diff": all_res["symbols"]["ES"]["calibration"]["H1"][sp]["ece_diff"],
                          "same_sign": bool(np.sign(all_res["symbols"]["NQ"]["calibration"]["H1"][sp]["ece_diff"]) == np.sign(all_res["symbols"]["ES"]["calibration"]["H1"][sp]["ece_diff"]))} for sp in SPLITS}
        all_res["es_replication_same_sign"] = rep
    out_json = os.path.join(HERE, f"h_{GROUP}_results.json")
    with open(out_json, "w") as f:
        json.dump(_jsonable(all_res), f, indent=1)
    out_csv = os.path.join(HERE, f"h_{GROUP}_nights.csv")
    pd.concat(nights, ignore_index=True).to_csv(out_csv, index=False)
    print(f"\nwrote {out_json}\nwrote {out_csv}")
    for sym in syms:
        print(f"\n[{sym}] verdicts:")
        for k, v in all_res["symbols"][sym]["verdicts"].items():
            print(f"  {k:9s} {v['verdict']:24s} {v['why']}")


if __name__ == "__main__":
    main()
