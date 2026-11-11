#!/usr/bin/env python3
"""
h_vetoes_gates.py -- vetoes, gates and cross-asset confirmation (group 'vetoes_gates') of the Grade-A lab.

Run from the project root:
    OMP_NUM_THREADS=1 python research/lab/grade_a/h_vetoes_gates.py

Inputs (read-only, written by honest_baseline.py): trades_honest_{SYM}.csv, candidates_{SYM}.csv; data/daily_close.csv
(HSI closes for the H6 placebo, same dchg convention as features.py); data/{SYM}_1h.csv via sessions.load_hourly (raw bars,
raced only for the H8 stand-down counterfactual and for a self-check).
Outputs: h_vetoes_gates_results.json, h_vetoes_gates_nights.csv (long format: one row per night per rule with the baseline
and the hypothesis P&L of the A book and of the graded book, so a refuter can recompute every number).

THE BASELINE is the honest baseline of the builder: grade in A/B/C, fill at the 18:00 open, own-pair stop-priority
resolution, base costs (column pnl_net_open; sensitivity pnl_net_open_hicost).  The object of this group is the A BOOK
(P&L of the nights graded A, untraded = 0); the graded book (A/B/C) is reported alongside.

Decision time of every rule: 17:xx ET.  Rule inputs (all 17:xx-knowable per baseline_summary.json): post_ret,
megacap_earnings_tonight, pre_holiday, holiday_tomorrow (expected_asia_bars_proxy), kospi_dd20, kospi_ret, hsi_dd20,
hsi_ret (placebo), sunday_open, vix, vix_z20, rv_ratio, fomc_tomorrow, tier1_data_tomorrow, dow, and the other symbol's
honest call for the same RTH date (other_grade / other_call / other_side, produced at the same 17:xx).  The H8 stand-down
uses open_past_stop (the 18:00 print, known at execution, not at grading).

Hypotheses (LAB_DESIGN section 8, pre-registered single parameters; no grid on the vault):
  H5   after-hours print veto: |post_ret| > 0.3% or megacap_earnings_tonight == 1 -> NO EDGE (free rule, no-harm criterion:
       the flagged nights' net P&L <= 0 on discovery AND on the vault; random-filter null).
  H9   thin sessions: pre_holiday == 1 -> skip (free rule).  Also reported: the knowable proxy pre_holiday | holiday_tomorrow
       (expected_asia_bars_proxy < 9) and the EX POST 'fewer than 9 Asia bars' version, labelled ex post (never a rule).
  H6   Kospi-stress gate: kospi_dd20 < -8% or |kospi_ret| > 2.5% -> MEAN REVERSION demoted one grade (A->B, B->C,
       C->NO EDGE); CONTINUATION unchanged.  Placebo: the same gate on hsi_dd20 / hsi_ret.
  H8   Sunday reopens: (a) the honest A record with and without Sunday nights (no verdict); (b) the stand-down when the
       Sunday 18:00 open is already past the stop (open_past_stop) -- the honest baseline already books those nights at 0,
       so the stand-down is scored against a 'chase' counterfactual (fill at the 18:00 open, registered target, stop
       re-anchored at the open by the registered stop distance, raced on the raw bars), with a random-filter null among
       Sunday graded nights; (c) the Sunday A record under the open fill and the 4-pt cost.
  REG  regime negative controls (no rule): lift of A nights flagged by VIX > 25, vix_z20 > 1.5, rv_ratio > 1.5,
       fomc_tomorrow, tier1_data_tomorrow versus the rest.
  H14  other-symbol agreement filter on A nights: keep an A night only if the other symbol's honest engine GRADED (A/B/C)
       the same call kind and side (the definition that reproduces the pre-registered v0 numbers +43 / -8.5); filtered-out
       A nights are treated as B (they leave the A book; the graded book is unchanged).  Reported: agreeing / disagreeing /
       no-call (other NO EDGE, NO TRADE or no row) averages; placebo = the same split on NO-EDGE nights (chosen candidate's
       P&L; must not help); CPCV-style: the agree-minus-disagree gap in four contiguous blocks of equal A count.
       Exploratory variant (labelled): agreement at the call level regardless of the other symbol's grade.
  DOW  day-of-week: unregistered observation only (5 cells of ~15 nights cannot carry a rule).
  COMBINED: the free rules that meet their no-harm criterion plus the gates / filters whose verdict is 'supported on vault'
       or 'discovery only', applied jointly; COMBINED_ALL = H5 + H9 + H6 + H14 jointly regardless of verdict (reference);
       COMBINED_FREE = H5 + H9 (reference); on ES also COMBINED_NQSET = the member set selected on NQ.

Verdicts (the task's rules) are taken on the A-avg effect; the n for 'not testable at this n' counts the vault nights the rule
TOUCHES (grade or P&L changed, every grade the rule acts on); the A-level count is reported alongside.  The LAB_DESIGN 2.7
degeneracy guard (>= 2.5 A nights per month on discovery) is reported per rule.

Protocol: discovery = 2025-04-01..2026-05-31, vault = 2026-06-01..2026-11-06, full = both; NQ primary, ES same-sign
replication (the other symbol of ES is NQ); splice nights excluded from every statistic (rows kept, flagged); paired per-night
differences (hypothesis minus baseline) with an ISO-week block bootstrap (2000 draws, numpy default_rng(0)) 90% CI; random-
filter null (2000 random removals of the same count from the same population, default_rng(0)) for every rule that removes
nights; exploratory parameter looks are run on discovery only and labelled; the vault is scored once at the pre-registered
value.  Dollars: NQ 20 / ES 50 per point per contract; per-year = total x 12 / months in the split (14.0 / 5.2 / 19.2).

Ex post inputs seen and NOT used as rule inputs: outcome_open / resolved_k_open / mfe / mae (descriptives only), n_bars /
asia_n_bars (the labelled ex post H9 variant only), v0_* columns (leaky by construction; used only to reproduce the
pre-registered H14 numbers in a self-check), catalogue tags, in_catalogue, kospi_next, n225_next, move_18_20_in_dir,
eur_* columns (never touched).
"""
from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np
import pandas as pd

from sessions import ASIA_HOURS, build_sessions, load_hourly

GROUP = "vetoes_gates"
DATA = os.path.join(ROOT, "data")
SPLITS = {"discovery": ("2025-04-01", "2026-05-31"), "vault": ("2026-06-01", "2026-11-06"),
          "full": ("2025-04-01", "2026-11-06")}
MONTHS = {"discovery": 14.0, "vault": 5.2, "full": 19.2}       # the builder's convention
PV = {"NQ": 20.0, "ES": 50.0}
N_BOOT, SEED = 2000, 0
GRADES = ("A", "B", "C")
MR, CONT = "MEAN REVERSION", "CONTINUATION"
DEMOTE = {"A": "B", "B": "C", "C": "NO EDGE"}
EPS = 1e-9

# pre-registered single parameters (LAB_DESIGN section 8)
H5_POST_RET = 0.003          # |post_ret| > 0.3% (or megacap_earnings_tonight == 1)
H6_DD, H6_RET = -0.08, 0.025  # kospi_dd20 < -8% or |kospi_ret| > 2.5%
H14_MIN_BLOCKS = 4
# exploratory looks (discovery only, point estimates, labelled)
H5_GRID = [0.002, 0.003, 0.005]
H6_DD_GRID = [-0.05, -0.08, -0.12]

REGISTRY = {
    "H5": {"rule": "after-hours print veto: |post_ret| > 0.3% or megacap_earnings_tonight == 1 -> NO EDGE (all grades)",
           "parameters": "|post_ret| > 0.003 (single, pre-registered); megacap flag from the calendar", "decision_time": "17:xx ET",
           "type": "free rule", "predicted_sign": +1,
           "predicted": "flagged nights avg -40..-50; A nights lost <= 3; +1.5..+2 pts/night over all nights; no-harm criterion: flagged net P&L <= 0 on discovery and on the vault"},
    "H9": {"rule": "thin sessions: pre_holiday == 1 -> skip (NO EDGE, all grades)", "parameters": "pre_holiday flag (calendar; no parameter)",
           "decision_time": "17:xx ET", "type": "free rule", "predicted_sign": +1,
           "predicted": "~0 cost (< 1 A night/month); affected A nights win <= 40%"},
    "H9_proxy": {"rule": "thin sessions, knowable proxy: pre_holiday == 1 or holiday_tomorrow == 1 (expected_asia_bars_proxy < 9) -> skip",
                 "parameters": "calendar flags (no parameter)", "decision_time": "17:xx ET", "type": "free rule (variant)", "predicted_sign": +1,
                 "predicted": "as H9"},
    "H9_expost": {"rule": "EX POST (not a rule): nights with fewer than 9 Asia bars -> skip; reported for the record only",
                  "parameters": "n_bars < 9 (ex post)", "decision_time": "EX POST (after the night) -- forbidden as a rule input",
                  "type": "ex post reference", "predicted_sign": +1, "predicted": "as H9 (the backlog's '5 graded, 0 wins' slice)"},
    "H6": {"rule": "Kospi-stress gate: kospi_dd20 < -8% or |kospi_ret| > 2.5% -> MEAN REVERSION demoted one grade (A->B, B->C, C->NO EDGE); CONTINUATION unchanged",
           "parameters": "dd20 < -0.08, |ret| > 0.025 (pre-registered pair, counted as one rule)", "decision_time": "17:xx ET (KOSPI session of calendar day D closes ~02:30 ET)",
           "type": "gate", "predicted_sign": +1,
           "predicted": "fade stopped rate on gate-active nights 45% vs 30%; A avg +2..+3; B avg -19 -> -12; all-night +4..+6"},
    "H6_placebo_HSI": {"rule": "PLACEBO of H6: the same gate on hsi_dd20 < -8% or |hsi_ret| > 2.5%", "parameters": "as H6",
                       "decision_time": "17:xx ET", "type": "placebo", "predicted_sign": +1, "predicted": "no effect (a placebo reproducing >= 50% of H6 kills H6)"},
    "H14": {"rule": "other-symbol agreement filter on A nights: keep only if the other symbol's honest engine graded (A/B/C) the same call kind and side; filtered-out A nights -> B",
            "parameters": "none (agreement = same kind and same side, other grade in A/B/C)", "decision_time": "17:xx ET (both engines run at the same time)",
            "type": "filter", "predicted_sign": +1,
            "predicted": "filtered A avg >= +30; disagreeing nights <= +5; n(A) 78 -> ~45; 50% prior of noise; admissible only if the gap holds in CPCV"},
    "H14_calllevel": {"rule": "EXPLORATORY variant of H14: agreement at the call level (same kind and side) regardless of the other symbol's grade",
                      "parameters": "none", "decision_time": "17:xx ET", "type": "filter (exploratory variant)", "predicted_sign": +1, "predicted": "as H14"},
    "H8b": {"rule": "Sunday stand-down: skip a Sunday-reopen night whose 18:00 open is already past the stop (open_past_stop); scored against the chase counterfactual (fill at the open, registered target, stop re-anchored by the registered stop distance)",
            "parameters": "none", "decision_time": "18:00 ET Sunday (the first print; execution, not grading)", "type": "free rule", "predicted_sign": +1,
            "predicted": "forward Sunday A win 65-75%, avg +15..+30 net; stand-down evaluated with a random-filter null among Sunday nights"},
}
REG_FLAGS = {"vix_gt25": ("vix", lambda s: s > 25), "vix_z20_gt1.5": ("vix_z20", lambda s: s > 1.5),
             "rv_ratio_gt1.5": ("rv_ratio", lambda s: s > 1.5), "fomc_tomorrow": ("fomc_tomorrow", lambda s: s == 1),
             "tier1_data_tomorrow": ("tier1_data_tomorrow", lambda s: s == 1)}


# --------------------------------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------------------------------
def hsi_ret_series(index: pd.DatetimeIndex) -> pd.Series:
    """HSI session-to-session change with features.py's dchg convention (row dated <= D, forward-filled)."""
    d = pd.read_csv(os.path.join(DATA, "daily_close.csv"), parse_dates=["Date"]).set_index("Date")
    x = d["HSI"].dropna()
    x = x[~x.index.duplicated()]
    return x.pct_change().reindex(index, method="ffill")


def load(sym: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    T = pd.read_csv(os.path.join(HERE, f"trades_honest_{sym}.csv"), parse_dates=["date"]).set_index("date").sort_index()
    C = pd.read_csv(os.path.join(HERE, f"candidates_{sym}.csv"), parse_dates=["date"])
    ch = C[C["chosen"] == 1].set_index("date")
    assert not ch.index.duplicated().any()
    # the chosen candidate's own P&L for EVERY night that has candidates (NO EDGE nights included: the H14 placebo population)
    new = pd.DataFrame({"cand_pnl": ch["pnl_net_open"].reindex(T.index).fillna(0.0),
                        "cand_pnl_hi": ch["pnl_net_open_hicost"].reindex(T.index).fillna(0.0),
                        "cand_outcome": ch["outcome_open"].reindex(T.index),
                        "cand_traded": ch["traded_open"].reindex(T.index).fillna(0).astype(int),
                        "hsi_ret": hsi_ret_series(T.index)}, index=T.index)
    T = pd.concat([T, new], axis=1)
    g = T["grade"].isin(GRADES)
    assert np.allclose(T.loc[g, "cand_pnl"], T.loc[g, "pnl_net_open"]), "chosen-candidate P&L != trades P&L on graded nights"
    assert (ch["cand_id"].reindex(T.index).fillna("-") == T["cand_id"].fillna("-")).all()
    # replication check of the builder's KOSPI columns from the same daily file (asserts the dchg convention used for hsi_ret)
    d = pd.read_csv(os.path.join(DATA, "daily_close.csv"), parse_dates=["Date"]).set_index("Date")
    k = d["KOSPI"].dropna()
    k = k[~k.index.duplicated()]
    assert np.allclose(k.pct_change().reindex(T.index, method="ffill"), T["kospi_ret"], equal_nan=True)
    assert np.allclose((k / k.rolling(20).max() - 1).reindex(T.index, method="ffill"), T["kospi_dd20"], equal_nan=True)
    h = d["HSI"].dropna()
    h = h[~h.index.duplicated()]
    assert np.allclose((h / h.rolling(20).max() - 1).reindex(T.index, method="ffill"), T["hsi_dd20"], equal_nan=True)
    return T, C


def load_nights(sym: str, T: pd.DataFrame) -> dict:
    """{RTH date -> (O, H, L, C) arrays of the Asia bars}, grouped exactly as the builder (sessions.path_outcomes)."""
    h = load_hourly(os.path.join(DATA, f"{sym}_1h.csv"))
    s = build_sessions(h)
    g = pd.Series(h.index.date, index=h.index)
    sh = h.index.hour >= 18
    g[sh] = (h.index[sh] + pd.Timedelta(days=1)).date
    hh = h.copy()
    hh["gdate"] = g.values
    hh["hour"] = h.index.hour
    asia = {gd: grp.sort_index() for gd, grp in hh[hh["hour"].isin(ASIA_HOURS)].groupby("gdate")}
    nights = {}
    for d in T.index:
        gd = pd.Timestamp(s.loc[d, "asia_gdate"]).date()
        b = asia[gd]
        nights[d] = tuple(b[c].values.astype(float) for c in ("Open", "High", "Low", "Close"))
    return nights


def walk(O, H, L, C, side: str, entry: float, target: float, stop: float) -> dict:
    """The builder's walk: stop priority inside a bar, a bar opening beyond the stop fills at its Open, targets at level,
    scratch = last close minus the entry."""
    sgn = 1.0 if side == "LONG" else -1.0
    for i in range(len(O)):
        stop_hit = (L[i] <= stop) if sgn > 0 else (H[i] >= stop)
        tgt_hit = (H[i] >= target) if sgn > 0 else (L[i] <= target)
        if stop_hit:
            gap = (O[i] <= stop) if sgn > 0 else (O[i] >= stop)
            ex = float(O[i]) if gap else float(stop)
            return {"outcome": "stop", "pnl": sgn * (ex - entry), "exit": ex, "k": i, "gapfill": int(gap)}
        if tgt_hit:
            return {"outcome": "target", "pnl": sgn * (float(target) - entry), "exit": float(target), "k": i, "gapfill": 0}
    ex = float(C[-1])
    return {"outcome": "scratch", "pnl": sgn * (ex - entry), "exit": ex, "k": np.nan, "gapfill": 0}


def beyond(side: str, px: float, lvl: float, kind: str) -> bool:
    if side == "LONG":
        return px >= lvl if kind == "target" else px <= lvl
    return px <= lvl if kind == "target" else px >= lvl


def self_check_bars(sym: str, T: pd.DataFrame, C: pd.DataFrame, nights: dict) -> dict:
    """The walker reproduces the builder's 18:00-open resolution of every fillable candidate; bar counts match."""
    n_ok = 0
    for _, c in C.iterrows():
        O, H, L, Cl = nights[c["date"]]
        entry = float(O[0])
        fillable = not beyond(c["side"], entry, float(c["target"]), "target") and not beyond(c["side"], entry, float(c["stop"]), "stop")
        assert int(fillable) == int(c["traded_open"]), (sym, c["date"], c["cand_id"])
        if fillable:
            r = walk(O, H, L, Cl, c["side"], entry, float(c["target"]), float(c["stop"]))
            assert abs(r["pnl"] - float(c["pnl_open"])) < EPS and r["outcome"] == c["outcome_open"], (sym, c["date"], c["cand_id"])
            n_ok += 1
    for d, r in T.iterrows():
        assert len(nights[d][0]) == int(r["n_bars"]), (sym, d)
        if pd.notna(r["entry_open"]):
            assert abs(nights[d][0][0] - float(r["entry_open"])) < EPS
    return {"candidates_open_fill_reproduced": n_ok, "nights_checked": int(len(T))}


# --------------------------------------------------------------------------------------------------
# books and rules
# --------------------------------------------------------------------------------------------------
def make_books(F: pd.DataFrame) -> pd.DataFrame:
    isA = (F["grade"] == "A").values
    gr = F["grade"].isin(GRADES).values
    F["pnl_A"] = np.where(isA, F["cand_pnl"].values, 0.0)
    F["pnl_G"] = np.where(gr, F["cand_pnl"].values, 0.0)
    F["pnl_A_hi"] = np.where(isA, F["cand_pnl_hi"].values, 0.0)
    F["pnl_G_hi"] = np.where(gr, F["cand_pnl_hi"].values, 0.0)
    return F


def base_frame(T: pd.DataFrame) -> pd.DataFrame:
    B = pd.DataFrame(index=T.index)
    for c in ("grade", "call", "side", "cand_pnl", "cand_pnl_hi", "cand_outcome", "cand_traded", "sunday_open", "split", "splice"):
        B[c] = T[c]
    B["rule_input"] = ""
    return make_books(B)


def veto(base: pd.DataFrame, mask: np.ndarray, inputs: pd.Series) -> pd.DataFrame:
    H = base.copy()
    sel = mask & H["grade"].isin(GRADES).values
    H.loc[sel, "grade"] = "NO EDGE"
    H["rule_input"] = inputs.astype(str).values
    return make_books(H)


def demote(base: pd.DataFrame, mask: np.ndarray, inputs: pd.Series) -> pd.DataFrame:
    H = base.copy()
    sel = mask & H["grade"].isin(GRADES).values & (H["call"] == MR).values
    H.loc[sel, "grade"] = H.loc[sel, "grade"].map(DEMOTE)
    H["rule_input"] = inputs.astype(str).values
    return make_books(H)


def filter_a(base: pd.DataFrame, keep: np.ndarray, inputs: pd.Series) -> pd.DataFrame:
    H = base.copy()
    sel = (H["grade"] == "A").values & ~keep
    H.loc[sel, "grade"] = "B"
    H["rule_input"] = inputs.astype(str).values
    return make_books(H)


def chase_counterfactual(base: pd.DataFrame, T: pd.DataFrame, nights: dict) -> tuple[pd.DataFrame, list]:
    """The 'no stand-down' counterfactual of H8b: on Sunday graded nights whose 18:00 open is past the stop, fill at the open
    with the registered target and the stop re-anchored at open -/+ stop_dist; race the raw bars; base costs."""
    CF = base.copy()
    rows = []
    sel = (T["sunday_open"] == 1) & (T["open_past_stop"] == 1) & T["grade"].isin(GRADES)
    for d in T.index[sel.values]:
        r = T.loc[d]
        O, H, L, C = nights[d]
        entry = float(O[0])
        side = r["side"]
        sgn = 1.0 if side == "LONG" else -1.0
        stop2 = entry - sgn * float(r["stop_dist"])
        if beyond(side, entry, float(r["target"]), "target"):
            res = {"outcome": "open_past_target", "pnl": 0.0, "exit": np.nan, "k": np.nan, "gapfill": 0}
            traded = 0
        else:
            res = walk(O, H, L, C, side, entry, float(r["target"]), stop2)
            traded = 1
        net = res["pnl"] - float(r["cost_base"]) if traded else 0.0
        net_hi = res["pnl"] - float(r["cost_hi"]) if traded else 0.0
        CF.loc[d, "cand_pnl"] = net
        CF.loc[d, "cand_pnl_hi"] = net_hi
        CF.loc[d, "cand_outcome"] = res["outcome"]
        CF.loc[d, "cand_traded"] = traded
        rows.append({"date": str(d.date()), "grade": r["grade"], "call": r["call"], "side": side, "entry_post": float(r["entry"]),
                     "open": entry, "registered_stop": float(r["stop"]), "reanchored_stop": stop2, "target": float(r["target"]),
                     "chase_outcome": res["outcome"], "chase_pnl_net": net, "honest_pnl_net": float(r["pnl_net_open"]),
                     "v0_pnl_pts": float(r["v0_pnl_pts"]) if pd.notna(r["v0_pnl_pts"]) else None, "v0_grade": r["v0_grade"]})
    return make_books(CF), rows


# --------------------------------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------------------------------
def iso_block_ids(index: pd.DatetimeIndex) -> np.ndarray:
    iso = index.isocalendar()
    keys = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).values
    _, ids = np.unique(keys, return_inverse=True)
    return ids


class Boot:
    """Weekly-block bootstrap (ISO weeks, with replacement, default_rng(seed)); every statistic is a signed sum of masked
    means, evaluated on the resampled nights as ratio of block sums (identical to re-evaluating on the concatenated draw)."""

    def __init__(self, index: pd.DatetimeIndex, n_boot: int = N_BOOT, seed: int = SEED):
        self.ids = iso_block_ids(index)
        self.nb = int(self.ids.max()) + 1 if len(index) else 0
        rng = np.random.default_rng(seed)
        self.pick = rng.integers(0, self.nb, (n_boot, self.nb)) if self.nb else np.zeros((n_boot, 0), int)

    def draws(self, stats: list) -> np.ndarray:
        terms = [(si, coef, np.asarray(v, float), np.asarray(m, bool)) for si, st in enumerate(stats) for (coef, v, m) in st]
        nt = len(terms)
        num = np.zeros((self.nb, nt))
        den = np.zeros((self.nb, nt))
        for t, (si, coef, v, m) in enumerate(terms):
            num[:, t] = np.bincount(self.ids, weights=np.where(m, v, 0.0), minlength=self.nb)
            den[:, t] = np.bincount(self.ids, weights=m.astype(float), minlength=self.nb)
        ns = num[self.pick].sum(axis=1)
        ds = den[self.pick].sum(axis=1)
        ratio = np.where(ds > 0, ns / np.where(ds > 0, ds, 1.0), np.nan)
        out = np.zeros((self.pick.shape[0], len(stats)))
        for t, (si, coef, v, m) in enumerate(terms):
            out[:, si] += coef * ratio[:, t]
        return out


def ci(mat: np.ndarray, col: int, q=(0.05, 0.95)) -> list[float]:
    v = mat[:, col]
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return [float("nan"), float("nan")]
    return [float(np.quantile(v, q[0])), float(np.quantile(v, q[1]))]


def _mean(x) -> float:
    return float(np.mean(x)) if len(x) else float("nan")


def block(p: np.ndarray, untraded: np.ndarray | None = None) -> dict:
    n = len(p)
    out = {"n": int(n), "win": float((p > 0).mean()) if n else float("nan"), "avg": _mean(p), "total": float(p.sum()),
           "worst": float(p.min()) if n else float("nan"), "best": float(p.max()) if n else float("nan"),
           "sd": float(p.std(ddof=1)) if n > 1 else float("nan")}
    out["pts_per_sigma"] = out["avg"] / out["sd"] if n > 1 and out["sd"] > 0 else float("nan")
    if untraded is not None:
        out["untraded"] = int(untraded.sum())
    return out


def random_filter_null(pop_pnl: np.ndarray, keep: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Null: remove the same number of random nights from the same population; statistic = mean P&L of the kept nights;
    percentile = share of null draws at or below the actual (high = the removed nights were worse than random)."""
    n = len(pop_pnl)
    n_d = int((~keep).sum())
    base = {"n_population": int(n), "n_removed": n_d, "actual_kept_avg": _mean(pop_pnl[keep]) if n else float("nan"),
            "removed_avg": _mean(pop_pnl[~keep]) if n_d else float("nan")}
    if n == 0 or n_d == 0 or n_d >= n:
        return {**base, "null_mean": float("nan"), "null_p95": float("nan"), "percentile": float("nan")}
    rng = np.random.default_rng(seed)
    tot = pop_pnl.sum()
    draws = np.empty(n_boot)
    for i in range(n_boot):
        draws[i] = (tot - pop_pnl[rng.choice(n, n_d, replace=False)].sum()) / (n - n_d)
    actual = float(pop_pnl[keep].mean())
    return {**base, "null_mean": float(draws.mean()), "null_p95": float(np.quantile(draws, 0.95)),
            "percentile": float(100.0 * (draws <= actual).mean())}


def split_mask(index: pd.DatetimeIndex, split: str, splice: np.ndarray) -> np.ndarray:
    a, b = (pd.Timestamp(x) for x in SPLITS[split])
    return ((index >= a) & (index <= b) & ~splice).astype(bool)


def evaluate(base: pd.DataFrame, hyp: pd.DataFrame, split: str, sym: str, with_null: bool = True) -> dict:
    """Baseline vs hypothesis on one split: A-book and graded-book effects, paired per-night differences with the
    weekly-block bootstrap, membership, random-filter nulls on the removed nights, dollars."""
    splice = base["splice"].values.astype(bool)
    m = split_mask(base.index, split, splice)
    b, h = base[m], hyp[m]
    idx = b.index
    pv, months = PV[sym], MONTHS[split]
    isA_b, isA_h = (b["grade"] == "A").values, (h["grade"] == "A").values
    gr_b, gr_h = b["grade"].isin(GRADES).values, h["grade"].isin(GRADES).values
    pA_b, pA_h = b["pnl_A"].values, h["pnl_A"].values
    pG_b, pG_h = b["pnl_G"].values, h["pnl_G"].values
    pAh_b, pAh_h = b["pnl_A_hi"].values, h["pnl_A_hi"].values
    pGh_b, pGh_h = b["pnl_G_hi"].values, h["pnl_G_hi"].values
    chg_grade = (b["grade"].values != h["grade"].values)
    touched = chg_grade | (np.abs(h["cand_pnl"].values - b["cand_pnl"].values) > EPS)   # nights the rule acts on
    chg_A = (np.abs(pA_h - pA_b) > EPS) | (isA_b != isA_h)
    chg_G = (np.abs(pG_h - pG_b) > EPS) | (gr_b != gr_h)
    a_either = isA_b | isA_h
    allm = np.ones(len(b), bool)
    removed_A = isA_b & ~isA_h
    removed_G = gr_b & ~gr_h
    stats = [
        [(1, pA_h, isA_h), (-1, pA_b, isA_b)],          # 0 A avg diff
        [(1, pG_h, gr_h), (-1, pG_b, gr_b)],            # 1 graded avg diff
        [(1, pG_h - pG_b, allm)],                       # 2 paired graded book, all nights
        [(1, pA_h - pA_b, allm)],                       # 3 paired A book, all nights
        [(1, pA_h - pA_b, a_either)],                   # 4 paired A book, A-either nights
        [(1, pAh_h, isA_h), (-1, pAh_b, isA_b)],        # 5 A avg diff, high costs
        [(1, pA_h, isA_h)],                             # 6 A avg hyp
        [(1, pA_b, isA_b)],                             # 7 A avg base
        [(1, pG_b, gr_b & chg_G)],                      # 8 affected graded nights' base avg
        [(1, pA_b, removed_A)],                         # 9 removed A nights' base avg
        [(1, pGh_h - pGh_b, allm)],                     # 10 paired graded book, high costs
    ]
    mat = Boot(idx).draws(stats)
    out = {
        "split": split, "n_nights": int(m.sum()),
        "A_before": block(pA_b[isA_b], (b["cand_traded"].values[isA_b] == 0)), "A_after": block(pA_h[isA_h], (h["cand_traded"].values[isA_h] == 0)),
        "A_before_hicost": block(pAh_b[isA_b]), "A_after_hicost": block(pAh_h[isA_h]),
        "graded_before": block(pG_b[gr_b]), "graded_after": block(pG_h[gr_h]),
        "B_before": block(pG_b[(b["grade"] == "B").values]), "B_after": block(pG_h[(h["grade"] == "B").values]),
        "C_before": block(pG_b[(b["grade"] == "C").values]), "C_after": block(pG_h[(h["grade"] == "C").values]),
        "effect_A_avg": _mean(pA_h[isA_h]) - _mean(pA_b[isA_b]), "effect_A_avg_ci90": ci(mat, 0), "effect_A_avg_ci80": ci(mat, 0, (0.10, 0.90)),
        "effect_A_avg_hicost": _mean(pAh_h[isA_h]) - _mean(pAh_b[isA_b]), "effect_A_avg_hicost_ci90": ci(mat, 5),
        "effect_graded_avg": _mean(pG_h[gr_h]) - _mean(pG_b[gr_b]), "effect_graded_avg_ci90": ci(mat, 1),
        "paired_A_book_all_nights": {"n": int(len(b)), "mean": _mean(pA_h - pA_b), "total": float((pA_h - pA_b).sum()), "ci90": ci(mat, 3), "ci80": ci(mat, 3, (0.10, 0.90))},
        "paired_A_book_A_either": {"n": int(a_either.sum()), "mean": _mean((pA_h - pA_b)[a_either]), "ci90": ci(mat, 4)},
        "paired_graded_book_all_nights": {"n": int(len(b)), "mean": _mean(pG_h - pG_b), "total": float((pG_h - pG_b).sum()), "ci90": ci(mat, 2)},
        "paired_graded_book_all_nights_hicost": {"mean": _mean(pGh_h - pGh_b), "ci90": ci(mat, 10)},
        "n_affected_A": int(chg_A.sum()), "n_affected_graded": int(chg_G.sum()), "n_grade_changed": int(chg_grade.sum()),
        "n_touched": int(touched.sum()), "touched_dates": [str(x.date()) for x in idx[touched]],
        "A_after_per_month": float(isA_h.sum() / months), "A_before_per_month": float(isA_b.sum() / months),
        "affected_graded_base": {"n": int((gr_b & chg_G).sum()), "avg": _mean(pG_b[gr_b & chg_G]), "total": float(pG_b[gr_b & chg_G].sum()),
                                 "win": float((pG_b[gr_b & chg_G] > 0).mean()) if (gr_b & chg_G).sum() else float("nan"), "ci90": ci(mat, 8)},
        "removed_A_base": {"n": int(removed_A.sum()), "avg": _mean(pA_b[removed_A]), "total": float(pA_b[removed_A].sum()),
                           "win": float((pA_b[removed_A] > 0).mean()) if removed_A.sum() else float("nan"), "ci90": ci(mat, 9),
                           "dates": [str(x.date()) for x in idx[removed_A]]},
        "A_membership": {"retained": int((isA_b & isA_h).sum()), "dropped": int(removed_A.sum()), "added": int((~isA_b & isA_h).sum()),
                         "jaccard": float((isA_b & isA_h).sum() / max(1, a_either.sum()))},
        "usd_per_contract_per_year_A": float((pA_h[isA_h].sum() - pA_b[isA_b].sum()) * pv * 12 / months),
        "usd_per_contract_per_year_graded": float((pG_h - pG_b).sum() * pv * 12 / months),
        "A_scratch_share_before": float((b["cand_outcome"].values[isA_b] == "scratch").mean()) if isA_b.sum() else float("nan"),
        "A_scratch_share_after": float((h["cand_outcome"].values[isA_h] == "scratch").mean()) if isA_h.sum() else float("nan"),
    }
    if with_null:
        out["random_filter_null_A"] = random_filter_null(pA_b[isA_b], isA_h[isA_b])
        out["random_filter_null_graded"] = random_filter_null(pG_b[gr_b], gr_h[gr_b])
    return out


def verdict_of(res: dict, predicted_sign: int = +1) -> tuple[str, str]:
    """The task's verdict rules on the A-avg effect (predicted_sign x effect > 0 = predicted direction); n = the vault nights the
    rule touches (grade changed or P&L changed: the vetoed / demoted / filtered / stood-down nights of every grade the rule
    acts on); the A-level count is reported alongside."""
    v, f, d = res["vault"], res["full"], res["discovery"]
    s = predicted_sign
    n_aff_v = v["n_touched"]
    e_v, ci_v = s * v["effect_A_avg"], sorted(s * x for x in v["effect_A_avg_ci90"])
    e_f, ci_f = s * f["effect_A_avg"], sorted(s * x for x in f["effect_A_avg_ci90"])
    e_d, ci_d = s * d["effect_A_avg"], sorted(s * x for x in d["effect_A_avg_ci90"])
    rf_f = f.get("random_filter_null_A", {}).get("percentile", float("nan"))
    rf_v = v.get("random_filter_null_A", {}).get("percentile", float("nan"))
    r1 = lambda x: [round(y * s, 1) for y in x]
    if n_aff_v < 8:
        return "not testable at this n", f"only {n_aff_v} touched vault nights ({v['n_affected_A']} A) (< 8); vault A-avg effect {e_v * s:+.1f}, full {e_f * s:+.1f} CI {r1(ci_f)}, discovery {e_d * s:+.1f} CI {r1(ci_d)}"
    if e_f < 0 and ci_f[1] < 0:
        return "harmful", f"full-window A-avg effect {e_f * s:+.1f} CI {r1(ci_f)} excludes zero against the prediction"
    vault_ok = ci_v[0] > 0
    full_ok = ci_f[0] > 0 and (ci_f[0] <= e_v <= ci_f[1]) and (not np.isnan(rf_f) and rf_f >= 90)
    if e_v > 0 and (vault_ok or full_ok):
        return "supported on vault", ("vault sign as predicted; " + ("vault CI excludes zero" if vault_ok else f"full CI excludes zero, vault point inside it, random-filter pct {rf_f:.0f}")
                                      + f"; vault {e_v * s:+.1f} CI {r1(ci_v)}, full {e_f * s:+.1f} CI {r1(ci_f)}")
    if e_d > 0 and ci_d[0] > 0:
        return "discovery only", f"discovery A-avg effect {e_d * s:+.1f} CI {r1(ci_d)} excludes zero; vault {e_v * s:+.1f} CI {r1(ci_v)} does not (random-filter pct vault {rf_v:.0f}, full {rf_f:.0f})"
    return "no effect", f"vault A-avg effect {e_v * s:+.1f} CI {r1(ci_v)}, full {e_f * s:+.1f} CI {r1(ci_f)}, discovery {e_d * s:+.1f} CI {r1(ci_d)} (random-filter pct vault {rf_v:.0f}, full {rf_f:.0f})"


def free_rule_criterion(res: dict) -> dict:
    """No-harm criterion of a free rule: the flagged (affected) graded nights' net P&L <= 0 on discovery AND on the vault;
    also at the A level."""
    out = {}
    for lvl, key in (("graded", "affected_graded_base"), ("A", "removed_A_base")):
        d, v = res["discovery"][key], res["vault"][key]
        out[lvl] = {"discovery_total": d["total"], "discovery_n": d["n"], "vault_total": v["total"], "vault_n": v["n"],
                    "met": bool(d["total"] <= 0 and v["total"] <= 0 and (d["n"] + v["n"]) > 0)}
    return out


def lift(base: pd.DataFrame, flag: np.ndarray, split: str) -> dict:
    """Negative control: A nights flagged vs the rest (no rule)."""
    splice = base["splice"].values.astype(bool)
    m = split_mask(base.index, split, splice)
    b = base[m]
    isA = (b["grade"] == "A").values
    f = flag[m] & isA
    r = ~flag[m] & isA
    p = b["pnl_A"].values
    mat = Boot(b.index).draws([[(1, p, f), (-1, p, r)]])
    return {"n_flagged_A": int(f.sum()), "flagged": block(p[f]), "rest": block(p[r]), "lift": _mean(p[f]) - _mean(p[r]), "lift_ci90": ci(mat, 0),
            "n_flagged_all_nights": int(flag[m].sum())}


# --------------------------------------------------------------------------------------------------
# H14 details
# --------------------------------------------------------------------------------------------------
def agreement_groups(T: pd.DataFrame) -> dict:
    og = T["other_grade"]
    oc, os_ = T["other_call"], T["other_side"]
    same = (oc == T["call"]) & (os_ == T["side"]) & T["call"].isin([MR, CONT])
    other_graded = og.isin(GRADES)
    other_has_call = oc.isin([MR, CONT])
    return {"agree": (same & other_graded).values, "disagree": (other_graded & ~same).values,
            "nocall_noedge": og.isin(["NO EDGE", "-"]).values, "nocall_missing": og.isna().values,
            "agree_call": (same & other_has_call).values, "disagree_call": (other_has_call & ~same).values,
            "missing_call": (~other_has_call).values}


def h14_tables(T: pd.DataFrame, base: pd.DataFrame, groups: dict, pop: np.ndarray, pnl: np.ndarray, label: str) -> dict:
    """Group averages (agree / disagree / no-call) of `pnl` on the population `pop`, per split, with the gap and its CI."""
    out = {}
    splice = base["splice"].values.astype(bool)
    for split in SPLITS:
        m = split_mask(base.index, split, splice) & pop
        rows = {}
        for g in ("agree", "disagree", "nocall_noedge", "nocall_missing", "agree_call", "disagree_call", "missing_call"):
            rows[g] = block(pnl[m & groups[g]])
        bt = Boot(base.index[m])
        mat = bt.draws([[(1, pnl[m], groups["agree"][m]), (-1, pnl[m], groups["disagree"][m])],
                        [(1, pnl[m], groups["agree"][m]), (-1, pnl[m], ~groups["agree"][m])],
                        [(1, pnl[m], groups["agree_call"][m]), (-1, pnl[m], groups["disagree_call"][m])]])
        rows["gap_agree_minus_disagree"] = {"gap": rows["agree"]["avg"] - rows["disagree"]["avg"], "ci90": ci(mat, 0)}
        rows["gap_kept_minus_dropped"] = {"gap": rows["agree"]["avg"] - _mean(pnl[m & ~groups["agree"]]), "ci90": ci(mat, 1)}
        rows["gap_calllevel_agree_minus_disagree"] = {"gap": rows["agree_call"]["avg"] - rows["disagree_call"]["avg"], "ci90": ci(mat, 2)}
        out[split] = rows
    out["population"] = label
    return out


def h14_cpcv_blocks(base: pd.DataFrame, groups: dict, n_blocks: int = H14_MIN_BLOCKS) -> dict:
    """Four contiguous time blocks of equal A count on the full window (splice excluded): the agree-minus-disagree gap
    and the kept-minus-dropped gap in each."""
    splice = base["splice"].values.astype(bool)
    m = split_mask(base.index, "full", splice)
    isA = (base["grade"] == "A").values & m
    pos = np.flatnonzero(isA)
    edges = np.array_split(pos, n_blocks)
    rows = []
    for i, e in enumerate(edges):
        sel = np.zeros(len(base), bool)
        sel[e] = True
        p = base["pnl_A"].values
        ag, dg, kept, dropped = sel & groups["agree"], sel & groups["disagree"], sel & groups["agree"], sel & ~groups["agree"]
        rows.append({"block": i + 1, "from": str(base.index[e[0]].date()), "to": str(base.index[e[-1]].date()), "n_A": int(len(e)),
                     "n_agree": int(ag.sum()), "n_disagree": int(dg.sum()), "n_nocall": int((sel & ~groups["agree"] & ~groups["disagree"]).sum()),
                     "avg_agree": _mean(p[ag]), "avg_disagree": _mean(p[dg]), "avg_nocall": _mean(p[sel & ~groups["agree"] & ~groups["disagree"]]),
                     "gap_agree_minus_disagree": _mean(p[ag]) - _mean(p[dg]), "gap_kept_minus_dropped": _mean(p[kept]) - _mean(p[dropped])})
    g1 = [r["gap_agree_minus_disagree"] for r in rows]
    g2 = [r["gap_kept_minus_dropped"] for r in rows]
    return {"blocks": rows, "n_blocks_gap_agree_minus_disagree_positive": int(sum(1 for g in g1 if g > 0)),
            "n_blocks_gap_kept_minus_dropped_positive": int(sum(1 for g in g2 if g > 0)), "n_blocks": n_blocks}


def h14_v0_reproduction(T: pd.DataFrame, other_T: pd.DataFrame) -> dict:
    """Self-check: the pre-registered H14 numbers (v0 A nights, other v0 graded same call/side: +43 n=28 vs -8.5 n=21 [FULL])
    are reproduced from the v0 columns (v0 side = f(v0 call, is_down), the engine's convention, asserted on the honest columns)."""
    def v0side(call, is_down):
        if call == MR:
            return "LONG" if is_down == 1 else "SHORT"
        if call == CONT:
            return "SHORT" if is_down == 1 else "LONG"
        return None
    chk = T[T["call"].isin([MR, CONT])]
    assert all(s == v0side(c, d) for s, c, d in zip(chk["side"], chk["call"], chk["is_down"]))
    o = other_T.reindex(T.index)
    o_side = pd.Series([v0side(c, d) for c, d in zip(o["v0_call"], o["is_down"])], index=T.index)
    t_side = pd.Series([v0side(c, d) for c, d in zip(T["v0_call"], T["is_down"])], index=T.index)
    A = (T["v0_grade"] == "A") & (T["splice"] == 0)
    og = o["v0_grade"].isin(GRADES)
    same = (o["v0_call"] == T["v0_call"]) & (o_side == t_side)
    agree, dis = A & og & same, A & og & ~same
    p = T["v0_pnl_pts"]
    return {"v0_A_n": int(A.sum()), "agree_n": int(agree.sum()), "agree_avg": _mean(p[agree]), "disagree_n": int(dis.sum()),
            "disagree_avg": _mean(p[dis]), "nocall_n": int((A & ~og).sum()), "nocall_avg": _mean(p[A & ~og]),
            "pre_registered": "+43 (n=28) vs -8.5 (n=21) [FULL]; the graded-agreement definition reproduces them within one night"}


# --------------------------------------------------------------------------------------------------
# H8 and the observations
# --------------------------------------------------------------------------------------------------
def h8_tables(T: pd.DataFrame, base: pd.DataFrame) -> dict:
    out = {}
    splice = base["splice"].values.astype(bool)
    for split in SPLITS:
        m = split_mask(base.index, split, splice)
        b = T[m]
        isA = (b["grade"] == "A").values
        sun = (b["sunday_open"] == 1).values
        p = base["pnl_A"].values[m]
        ph = base["pnl_A_hi"].values[m]
        unf = (b["cand_traded"].values == 0)
        sunA = isA & sun
        rec = {"A_all": block(p[isA], unf[isA]), "A_weeknights": block(p[isA & ~sun], unf[isA & ~sun]), "A_sunday": block(p[sunA], unf[sunA]),
               "A_sunday_hicost": block(ph[sunA]), "A_sunday_fillable_only": block(p[sunA & ~unf]),
               "sunday_share_of_A_points": float(p[sunA].sum() / p[isA].sum()) if isA.sum() and abs(p[isA].sum()) > 0 else float("nan"),
               "sunday_share_of_A_nights": float(sunA.sum() / isA.sum()) if isA.sum() else float("nan"),
               "sunday_A_unfillable": {"already_past_target": int((sunA & (b["already_past_open"].values == 1)).sum()),
                                       "open_past_stop": int((sunA & (b["open_past_stop"].values == 1)).sum())},
               "sunday_A_by_call": {k: block(p[sunA & (b["call"].values == k)]) for k in (MR, CONT)},
               "v0_A_sunday": block(b["v0_pnl_pts"].fillna(0).values[(b["v0_grade"] == "A").values & sun]),
               "sunday_graded": block(base["pnl_G"].values[m][b["grade"].isin(GRADES).values & sun]),
               "sunday_nights": int(sun.sum()), "sunday_open_past_stop_all": int((sun & (b["open_past_stop"].values == 1)).sum()),
               "sunday_already_past_all": int((sun & (b["already_past_open"].values == 1)).sum())}
        # weekly-block CI of the Sunday A avg and of Sunday-minus-weeknight A avg
        mat = Boot(base.index[m]).draws([[(1, p, sunA)], [(1, p, sunA), (-1, p, isA & ~sun)]])
        rec["A_sunday_avg_ci90"] = ci(mat, 0)
        rec["A_sunday_minus_weeknight_ci90"] = ci(mat, 1)
        out[split] = rec
    return out


def dow_tables(T: pd.DataFrame, base: pd.DataFrame) -> dict:
    out = {}
    splice = base["splice"].values.astype(bool)
    for split in SPLITS:
        m = split_mask(base.index, split, splice)
        b = T[m]
        isA = (b["grade"] == "A").values
        p = base["pnl_A"].values[m]
        out[split] = {int(d): block(p[isA & (b["dow"].values == d)]) for d in range(5)}
    out["note"] = ("unregistered observation; dow 4 = Friday decision = the Sunday reopen night; 5 cells of ~15 nights cannot carry a rule "
                   "(v0 showed Tuesday weak)")
    return out


# --------------------------------------------------------------------------------------------------
# main per symbol
# --------------------------------------------------------------------------------------------------
def fmt(x, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "nan"
    return f"{x:.{nd}f}"


def print_rule(sym: str, rid: str, res: dict, verdict: str, text: str | None = None):
    print(f"\n[{sym}] {rid}: {text or REGISTRY.get(rid, {}).get('rule', rid)}")
    print(f"  {'split':10s} {'A n b->a':>10s} {'A avg b->a':>16s} {'dA_avg':>8s} {'CI90':>18s} {'win b->a':>12s} {'worst b->a':>16s} {'touch':>5s} {'affA':>5s} {'rfA%':>5s} {'A-book/night':>13s} {'usd/yr A':>9s}")
    for split in ("discovery", "vault", "full"):
        r = res[split]
        ab, aa = r["A_before"], r["A_after"]
        rf = r.get("random_filter_null_A", {}).get("percentile", float("nan"))
        print(f"  {split:10s} {ab['n']:>4d}->{aa['n']:<4d} {fmt(ab['avg']):>7s}->{fmt(aa['avg']):<7s} {fmt(r['effect_A_avg']):>8s} "
              f"[{fmt(r['effect_A_avg_ci90'][0])},{fmt(r['effect_A_avg_ci90'][1])}]".ljust(19) +
              f"{fmt(ab['win'], 2):>5s}->{fmt(aa['win'], 2):<5s} {fmt(ab['worst']):>7s}->{fmt(aa['worst']):<7s} {r['n_touched']:>5d} {r['n_affected_A']:>5d} {fmt(rf, 0):>5s} "
              f"{fmt(r['paired_A_book_all_nights']['mean'], 2):>13s} {fmt(r['usd_per_contract_per_year_A'], 0):>9s}")
    print(f"  verdict: {verdict}")


def run_symbol(sym: str, other_sym: str, forced_members: list | None = None) -> tuple[dict, list]:
    """forced_members: for the replication arm, the member set selected on the primary symbol (reported as COMBINED_NQSET)."""
    t0 = time.time()
    T, C = load(sym)
    other_T, _ = load(other_sym)
    nights = load_nights(sym, T)
    checks = {"bars": self_check_bars(sym, T, C, nights)}
    base = base_frame(T)
    splice = T["splice"].values.astype(bool)
    R = {"baseline": {s: evaluate(base, base, s, sym, with_null=False)["A_before"] for s in SPLITS}, "rules": {}, "self_checks": checks}
    hyps = {}
    rows = []

    # ---- H5 ----
    f5 = ((T["post_ret"].abs() > H5_POST_RET) | (T["megacap_earnings_tonight"] == 1)).values
    hyps["H5"] = veto(base, f5, "post_ret=" + T["post_ret"].round(5).astype(str) + ";mega=" + T["megacap_earnings_tonight"].astype(str))
    # ---- H9 ----
    hyps["H9"] = veto(base, (T["pre_holiday"] == 1).values, "pre_holiday=" + T["pre_holiday"].astype(str))
    hyps["H9_proxy"] = veto(base, (T["expected_asia_bars_proxy"] < 9).values, "expected_asia_bars_proxy=" + T["expected_asia_bars_proxy"].astype(str))
    hyps["H9_expost"] = veto(base, (T["n_bars"] < 9).values, "n_bars=" + T["n_bars"].astype(str) + " (EX POST)")
    # ---- H6 ----
    g6 = ((T["kospi_dd20"] < H6_DD) | (T["kospi_ret"].abs() > H6_RET)).values
    hyps["H6"] = demote(base, g6, "kospi_dd20=" + T["kospi_dd20"].round(4).astype(str) + ";kospi_ret=" + T["kospi_ret"].round(4).astype(str))
    gP = ((T["hsi_dd20"] < H6_DD) | (T["hsi_ret"].abs() > H6_RET)).values
    hyps["H6_placebo_HSI"] = demote(base, gP, "hsi_dd20=" + T["hsi_dd20"].round(4).astype(str) + ";hsi_ret=" + T["hsi_ret"].round(4).astype(str))
    # ---- H14 ----
    groups = agreement_groups(T)
    oinp = "other=" + T["other_grade"].fillna("missing").astype(str) + "/" + T["other_call"].fillna("-").astype(str) + "/" + T["other_side"].fillna("-").astype(str)
    hyps["H14"] = filter_a(base, groups["agree"], oinp)
    hyps["H14_calllevel"] = filter_a(base, groups["agree_call"], oinp)
    # ---- H8b: base = chase counterfactual, hyp = the honest baseline (stand-down) ----
    cf, chase_rows = chase_counterfactual(base, T, nights)
    cf["rule_input"] = ("sunday=" + T["sunday_open"].astype(str) + ";open_past_stop=" + T["open_past_stop"].fillna(-1).astype(int).astype(str)).values
    hyps["H8b"] = base.copy()
    hyps["H8b"]["rule_input"] = cf["rule_input"].values

    for rid, H in hyps.items():
        B = cf if rid == "H8b" else base
        res = {s: evaluate(B, H, s, sym) for s in SPLITS}
        v, why = verdict_of(res, REGISTRY[rid]["predicted_sign"])
        rec = {**REGISTRY[rid], "by_split": res, "verdict": v, "verdict_why": why}
        if REGISTRY[rid]["type"].startswith("free rule"):
            rec["free_rule_criterion"] = free_rule_criterion(res)
        R["rules"][rid] = rec
        print_rule(sym, rid, res, v)
        for d, b_, h_ in zip(B.index, B.itertuples(), H.itertuples()):
            rows.append({"sym": sym, "date": str(d.date()), "split": b_.split, "splice": int(b_.splice), "rule": rid, "call": b_.call, "side": b_.side,
                         "base_grade": b_.grade, "hyp_grade": h_.grade, "affected": int((b_.grade != h_.grade) or abs(b_.pnl_A - h_.pnl_A) > EPS or abs(b_.pnl_G - h_.pnl_G) > EPS),
                         "rule_input": h_.rule_input, "base_cand_pnl": b_.cand_pnl, "hyp_cand_pnl": h_.cand_pnl,
                         "base_pnl_A": b_.pnl_A, "hyp_pnl_A": h_.pnl_A, "base_pnl_G": b_.pnl_G, "hyp_pnl_G": h_.pnl_G,
                         "base_pnl_A_hi": b_.pnl_A_hi, "hyp_pnl_A_hi": h_.pnl_A_hi, "base_outcome": b_.cand_outcome, "hyp_outcome": h_.cand_outcome})

    # ---- H5 extras ----
    gr = T["grade"].isin(GRADES).values
    R["rules"]["H5"]["flagged_graded_nights"] = [
        {"date": str(d.date()), "split": r["split"], "grade": r["grade"], "call": r["call"], "pnl_net_open": float(r["pnl_net_open"]), "post_ret": float(r["post_ret"]),
         "megacap": int(r["megacap_earnings_tonight"]), "outcome": r["cand_outcome"], "v0_grade": r["v0_grade"]}
        for d, r in T[f5 & gr & ~splice].iterrows()]
    R["rules"]["H5"]["A_nights_lost"] = {s: R["rules"]["H5"]["by_split"][s]["removed_A_base"]["n"] for s in SPLITS}
    R["rules"]["H5"]["note"] = ("the flagged nights already carry the 4-pt event cost in the baseline; 2025-09-16 (splice, fake post_ret) is excluded; "
                                "the backlog expected <= 3 A nights lost and ~8-10 flagged discovery nights")
    expl = []
    for thr in H5_GRID:
        fm = ((T["post_ret"].abs() > thr) | (T["megacap_earnings_tonight"] == 1)).values
        e = evaluate(base, veto(base, fm, T["post_ret"].astype(str)), "discovery", sym, with_null=False)
        expl.append({"threshold": thr, "n_affected_A": e["n_affected_A"], "effect_A_avg": e["effect_A_avg"], "removed_A_avg": e["removed_A_base"]["avg"],
                     "affected_graded_avg": e["affected_graded_base"]["avg"], "paired_A_book": e["paired_A_book_all_nights"]["mean"]})
    for part, fm in (("post_ret_only", (T["post_ret"].abs() > H5_POST_RET).values), ("megacap_only", (T["megacap_earnings_tonight"] == 1).values)):
        e = evaluate(base, veto(base, fm, T["post_ret"].astype(str)), "discovery", sym, with_null=False)
        expl.append({"component": part, "n_affected_A": e["n_affected_A"], "effect_A_avg": e["effect_A_avg"], "removed_A_avg": e["removed_A_base"]["avg"],
                     "affected_graded_avg": e["affected_graded_base"]["avg"]})
    R["rules"]["H5"]["exploratory_discovery_only"] = expl

    # ---- H9 extras ----
    for rid, mk in (("H9", (T["pre_holiday"] == 1).values), ("H9_proxy", (T["expected_asia_bars_proxy"] < 9).values), ("H9_expost", (T["n_bars"] < 9).values)):
        R["rules"][rid]["affected_graded_nights"] = [
            {"date": str(d.date()), "split": r["split"], "grade": r["grade"], "call": r["call"], "pnl_net_open": float(r["pnl_net_open"]), "n_bars": int(r["n_bars"]),
             "pre_holiday": int(r["pre_holiday"]), "holiday_tomorrow": int(r["holiday_tomorrow"]), "outcome": r["cand_outcome"]}
            for d, r in T[mk & gr & ~splice].iterrows()]
        a_aff = T[mk & (T["grade"] == "A").values & ~splice]
        R["rules"][rid]["affected_A_win"] = float((a_aff["pnl_net_open"] > 0).mean()) if len(a_aff) else float("nan")
    R["rules"]["H9_expost"]["warning"] = "EX POST: n_bars is known only after the night; reported for the record, never a rule"

    # ---- H6 extras ----
    def gate_diag(gmask, name):
        d = {}
        for split in SPLITS:
            m = split_mask(base.index, split, splice)
            mr = (T["call"] == MR).values & gr & (T["cand_traded"].values == 1) & m
            on, off = mr & gmask, mr & ~gmask
            oc = T["cand_outcome"].values
            d[split] = {"gate_active_nights": int((gmask & m).sum()), "gate_active_graded": int((gmask & gr & m).sum()),
                        "MR_graded_traded_on": int(on.sum()), "MR_graded_traded_off": int(off.sum()),
                        "fade_stopped_rate_on": float((oc[on] == "stop").mean()) if on.sum() else float("nan"),
                        "fade_stopped_rate_off": float((oc[off] == "stop").mean()) if off.sum() else float("nan"),
                        "fade_target_rate_on": float((oc[on] == "target").mean()) if on.sum() else float("nan"),
                        "fade_target_rate_off": float((oc[off] == "target").mean()) if off.sum() else float("nan"),
                        "fade_avg_on": _mean(T["pnl_net_open"].values[on]), "fade_avg_off": _mean(T["pnl_net_open"].values[off]),
                        "cont_graded_on_avg": _mean(T["pnl_net_open"].values[(T["call"] == CONT).values & gr & m & gmask]),
                        "cont_graded_on_n": int(((T["call"] == CONT).values & gr & m & gmask).sum()),
                        "A_MR_on_n": int((on & (T["grade"] == "A").values).sum()), "A_MR_on_avg": _mean(T["pnl_net_open"].values[on & (T["grade"] == "A").values]),
                        "A_MR_off_avg": _mean(T["pnl_net_open"].values[off & (T["grade"] == "A").values])}
        d["name"] = name
        return d
    R["rules"]["H6"]["mechanism"] = gate_diag(g6, "kospi gate")
    R["rules"]["H6_placebo_HSI"]["mechanism"] = gate_diag(gP, "hsi gate (placebo)")
    e6, eP = R["rules"]["H6"]["by_split"], R["rules"]["H6_placebo_HSI"]["by_split"]
    R["rules"]["H6"]["placebo_summary"] = {s: {"H6_effect_A_avg": e6[s]["effect_A_avg"], "placebo_effect_A_avg": eP[s]["effect_A_avg"],
                                               "placebo_share": (eP[s]["effect_A_avg"] / e6[s]["effect_A_avg"]) if abs(e6[s]["effect_A_avg"]) > EPS else float("nan"),
                                               "H6_paired_A_book": e6[s]["paired_A_book_all_nights"]["mean"], "placebo_paired_A_book": eP[s]["paired_A_book_all_nights"]["mean"],
                                               "H6_n_affected_A": e6[s]["n_affected_A"], "placebo_n_affected_A": eP[s]["n_affected_A"]} for s in SPLITS}
    expl = []
    for dd in H6_DD_GRID:
        gm = ((T["kospi_dd20"] < dd) | (T["kospi_ret"].abs() > H6_RET)).values
        e = evaluate(base, demote(base, gm, T["kospi_dd20"].astype(str)), "discovery", sym, with_null=False)
        expl.append({"dd_threshold": dd, "ret_threshold": H6_RET, "mode": "demote MR", "n_affected_A": e["n_affected_A"], "effect_A_avg": e["effect_A_avg"],
                     "removed_A_avg": e["removed_A_base"]["avg"], "paired_graded_book": e["paired_graded_book_all_nights"]["mean"]})
    e = evaluate(base, veto(base, g6 & (T["call"] == MR).values, T["kospi_dd20"].astype(str)), "discovery", sym, with_null=False)
    expl.append({"dd_threshold": H6_DD, "ret_threshold": H6_RET, "mode": "skip MR (veto instead of demote)", "n_affected_A": e["n_affected_A"],
                 "effect_A_avg": e["effect_A_avg"], "removed_A_avg": e["removed_A_base"]["avg"], "paired_graded_book": e["paired_graded_book_all_nights"]["mean"]})
    e = evaluate(base, veto(base, g6, T["kospi_dd20"].astype(str)), "discovery", sym, with_null=False)
    expl.append({"dd_threshold": H6_DD, "ret_threshold": H6_RET, "mode": "skip both kinds", "n_affected_A": e["n_affected_A"],
                 "effect_A_avg": e["effect_A_avg"], "removed_A_avg": e["removed_A_base"]["avg"], "paired_graded_book": e["paired_graded_book_all_nights"]["mean"]})
    R["rules"]["H6"]["exploratory_discovery_only"] = expl

    # ---- H14 extras ----
    isA = (T["grade"] == "A").values
    R["rules"]["H14"]["groups_A"] = h14_tables(T, base, groups, isA, base["pnl_A"].values, "honest A nights")
    noedge = (T["grade"] == "NO EDGE").values
    R["rules"]["H14"]["placebo_NO_EDGE"] = h14_tables(T, base, groups, noedge, T["cand_pnl"].values, "NO-EDGE nights, chosen candidate's P&L (must not help)")
    R["rules"]["H14"]["placebo_summary"] = {s: {"A_gap_kept_minus_dropped": R["rules"]["H14"]["groups_A"][s]["gap_kept_minus_dropped"]["gap"],
                                                "placebo_gap_kept_minus_dropped": R["rules"]["H14"]["placebo_NO_EDGE"][s]["gap_kept_minus_dropped"]["gap"],
                                                "A_gap_agree_minus_disagree": R["rules"]["H14"]["groups_A"][s]["gap_agree_minus_disagree"]["gap"],
                                                "placebo_gap_agree_minus_disagree": R["rules"]["H14"]["placebo_NO_EDGE"][s]["gap_agree_minus_disagree"]["gap"]} for s in SPLITS}
    R["rules"]["H14"]["cpcv_blocks"] = h14_cpcv_blocks(base, groups)
    # exploratory, discovery only, post hoc (NOT pre-registered; never scored on the vault): the H14 effect comes from the
    # no-call group, so the natural follow-up is a veto of A nights on which the other symbol issued NO EDGE / NO TRADE / no row
    nocall = groups["nocall_noedge"] | groups["nocall_missing"]
    e = evaluate(base, filter_a(base, ~nocall, oinp), "discovery", sym)
    R["rules"]["H14"]["exploratory_discovery_only"] = [
        {"variant": "no-call veto (keep A unless the other symbol is NO EDGE / NO TRADE / missing); post hoc, discovery only, not scored on the vault",
         "A_before": e["A_before"]["n"], "A_after": e["A_after"]["n"], "A_avg_before": e["A_before"]["avg"], "A_avg_after": e["A_after"]["avg"],
         "effect_A_avg": e["effect_A_avg"], "effect_A_avg_ci90": e["effect_A_avg_ci90"], "removed_A_avg": e["removed_A_base"]["avg"],
         "random_filter_pct_A": e["random_filter_null_A"]["percentile"], "A_after_per_month": e["A_after_per_month"]},
        {"variant": "no-call veto excluding the missing-row nights (other NO EDGE / NO TRADE only); post hoc, discovery only",
         **{k: v for k, v in (lambda ee: {"A_before": ee["A_before"]["n"], "A_after": ee["A_after"]["n"], "A_avg_after": ee["A_after"]["avg"], "effect_A_avg": ee["effect_A_avg"],
                                           "effect_A_avg_ci90": ee["effect_A_avg_ci90"], "random_filter_pct_A": ee["random_filter_null_A"]["percentile"],
                                           "A_after_per_month": ee["A_after_per_month"]})(evaluate(base, filter_a(base, ~groups["nocall_noedge"], oinp), "discovery", sym)).items()}}]
    R["rules"]["H14"]["v0_reproduction"] = h14_v0_reproduction(T, other_T)
    R["rules"]["H14"]["other_symbol"] = other_sym
    R["rules"]["H14"]["note"] = ("agreement requires the other symbol's call to be GRADED (A/B/C); 'no-call' = other NO EDGE / NO TRADE / no OOS row "
                                 f"({int(groups['nocall_missing'].sum())} of {len(T)} nights have no {other_sym} row); the exploratory call-level variant counts an ungraded call")
    # ---- H8 ----
    R["rules"]["H8b"]["chase_rows"] = chase_rows
    R["rules"]["H8b"]["note"] = ("the honest baseline already books open_past_stop nights at 0 (stand-down built in); the effect is scored against the chase "
                                 "counterfactual; already_past_target Sunday nights (the open gapped beyond the target) are also 0 in the baseline and are not chased")
    for split in SPLITS:
        m = split_mask(base.index, split, splice)
        sunG = m & (T["sunday_open"] == 1).values & gr
        R["rules"]["H8b"]["by_split"][split]["random_filter_null_sunday_graded"] = random_filter_null(cf["pnl_G"].values[sunG], ~(T["open_past_stop"].values[sunG] == 1))
        sunA = sunG & isA
        R["rules"]["H8b"]["by_split"][split]["random_filter_null_sunday_A"] = random_filter_null(cf["pnl_A"].values[sunA], ~(T["open_past_stop"].values[sunA] == 1))
    R["H8"] = h8_tables(T, base)
    # ---- regime negative controls ----
    R["regime_controls"] = {}
    for name, (col, fn) in REG_FLAGS.items():
        flag = fn(T[col]).fillna(False).values.astype(bool)
        R["regime_controls"][name] = {s: lift(base, flag, s) for s in SPLITS}
    R["regime_controls"]["note"] = "negative controls, no rule: lift = flagged A avg - rest A avg; forensics expected ~none (1.0-1.1 lift)"
    # ---- day of week ----
    R["dow"] = dow_tables(T, base)

    # ---- COMBINED ----
    def selected_rules():
        sel = []
        for rid in ("H5", "H9"):
            if R["rules"][rid]["free_rule_criterion"]["graded"]["met"]:
                sel.append(rid)
        for rid in ("H6", "H14"):
            if R["rules"][rid]["verdict"] in ("supported on vault", "discovery only"):
                sel.append(rid)
        return sel

    def combined(rids: list) -> pd.DataFrame:
        H = base.copy()
        grd = H["grade"].isin(GRADES).values
        if "H5" in rids:
            H.loc[f5 & grd, "grade"] = "NO EDGE"
        if "H9" in rids:
            H.loc[(T["pre_holiday"] == 1).values & grd, "grade"] = "NO EDGE"
        if "H6" in rids:
            s6 = g6 & H["grade"].isin(GRADES).values & (H["call"] == MR).values
            H.loc[s6, "grade"] = H.loc[s6, "grade"].map(DEMOTE)
        if "H14" in rids:
            s14 = (H["grade"] == "A").values & ~groups["agree"]
            H.loc[s14, "grade"] = "B"
        H["rule_input"] = "+".join(rids) if rids else "none"
        return make_books(H)

    sel = selected_rules()
    combos = [("COMBINED", sel), ("COMBINED_ALL", ["H5", "H9", "H6", "H14"]), ("COMBINED_FREE", ["H5", "H9"])]
    if forced_members is not None:
        combos.append(("COMBINED_NQSET", list(forced_members)))
    for cid, rids in combos:
        H = combined(rids)
        res = {s: evaluate(base, H, s, sym) for s in SPLITS}
        v, why = verdict_of(res, +1) if rids else ("no effect", "no rule selected")
        note = {"COMBINED": "members = free rules meeting the no-harm criterion + gates/filters with verdict supported/discovery only (selected on this symbol); the selection is itself post hoc",
                "COMBINED_ALL": "all four rules regardless of verdict (reference)",
                "COMBINED_FREE": "the two free rules (H5 + H9) jointly (reference)",
                "COMBINED_NQSET": "the member set selected on the primary symbol, applied to this symbol (replication)"}[cid]
        R["rules"][cid] = {"rule": f"joint application of {rids if rids else 'nothing'}", "parameters": "the members' pre-registered parameters", "decision_time": "17:xx ET",
                           "type": "combined", "members": rids, "by_split": res, "verdict": v, "verdict_why": why, "note": note}
        print_rule(sym, cid, res, v, R["rules"][cid]["rule"])
        for d, b_, h_ in zip(base.index, base.itertuples(), H.itertuples()):
            rows.append({"sym": sym, "date": str(d.date()), "split": b_.split, "splice": int(b_.splice), "rule": cid, "call": b_.call, "side": b_.side,
                         "base_grade": b_.grade, "hyp_grade": h_.grade, "affected": int((b_.grade != h_.grade) or abs(b_.pnl_A - h_.pnl_A) > EPS or abs(b_.pnl_G - h_.pnl_G) > EPS),
                         "rule_input": h_.rule_input, "base_cand_pnl": b_.cand_pnl, "hyp_cand_pnl": h_.cand_pnl,
                         "base_pnl_A": b_.pnl_A, "hyp_pnl_A": h_.pnl_A, "base_pnl_G": b_.pnl_G, "hyp_pnl_G": h_.pnl_G,
                         "base_pnl_A_hi": b_.pnl_A_hi, "hyp_pnl_A_hi": h_.pnl_A_hi, "base_outcome": b_.cand_outcome, "hyp_outcome": h_.cand_outcome})
    R["selected_members"] = sel
    R["runtime_s"] = time.time() - t0
    return R, rows


def print_observations(sym: str, R: dict):
    print(f"\n[{sym}] H8 Sunday reopens (honest A, open fill, 4-pt cost)")
    for split in SPLITS:
        r = R["H8"][split]
        a, w, s_ = r["A_all"], r["A_weeknights"], r["A_sunday"]
        print(f"  {split:10s} A all n={a['n']} avg={fmt(a['avg'])} | weeknights n={w['n']} avg={fmt(w['avg'])} win={fmt(w['win'], 2)} | Sunday n={s_['n']} avg={fmt(s_['avg'])} "
              f"win={fmt(s_['win'], 2)} worst={fmt(s_['worst'])} unfillable={s_.get('untraded')} CI90={[round(x, 1) for x in r['A_sunday_avg_ci90']]} share_of_A_pts={fmt(r['sunday_share_of_A_points'], 2)} "
              f"| v0 Sunday A n={r['v0_A_sunday']['n']} win={fmt(r['v0_A_sunday']['win'], 2)} avg={fmt(r['v0_A_sunday']['avg'])}")
    print(f"\n[{sym}] regime negative controls on A nights (lift = flagged - rest)")
    for name, rr in R["regime_controls"].items():
        if name == "note":
            continue
        print("  " + name.ljust(22) + " ".join(f"{s}: n={rr[s]['n_flagged_A']} lift={fmt(rr[s]['lift'])} CI={[round(x, 1) for x in rr[s]['lift_ci90']]}" for s in SPLITS))
    print(f"\n[{sym}] day of week (A nights; dow 4 = Sunday reopen)")
    for split in SPLITS:
        print(f"  {split:10s} " + " | ".join(f"d{d}: n={R['dow'][split][d]['n']} avg={fmt(R['dow'][split][d]['avg'])} win={fmt(R['dow'][split][d]['win'], 2)}" for d in range(5)))
    print(f"\n[{sym}] H14 groups on A nights (full): " + ", ".join(f"{g}: n={R['rules']['H14']['groups_A']['full'][g]['n']} avg={fmt(R['rules']['H14']['groups_A']['full'][g]['avg'])}"
                                                               for g in ("agree", "disagree", "nocall_noedge", "nocall_missing")))
    print(f"  CPCV blocks (agree-minus-disagree): " + ", ".join(f"b{b['block']} {fmt(b['gap_agree_minus_disagree'])} (n {b['n_agree']}/{b['n_disagree']})" for b in R["rules"]["H14"]["cpcv_blocks"]["blocks"]))
    print(f"  placebo on NO-EDGE nights (full): kept-minus-dropped gap {fmt(R['rules']['H14']['placebo_NO_EDGE']['full']['gap_kept_minus_dropped']['gap'])}, "
          f"agree-minus-disagree {fmt(R['rules']['H14']['placebo_NO_EDGE']['full']['gap_agree_minus_disagree']['gap'])}")
    print(f"\n[{sym}] H6 mechanism (full): " + ", ".join(f"{k}={fmt(v, 2) if isinstance(v, float) else v}" for k, v in R["rules"]["H6"]["mechanism"]["full"].items()))
    print(f"  placebo share of the H6 A-avg effect: " + ", ".join(f"{s}: {fmt(R['rules']['H6']['placebo_summary'][s]['placebo_share'], 2)}" for s in SPLITS))


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
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    return o


def summary_rows(R: dict, sym: str) -> list:
    out = []
    for rid, r in R["rules"].items():
        b = r["by_split"]
        out.append({"id": rid, "sym": sym, "verdict": r["verdict"], "n_affected_A": {s: b[s]["n_affected_A"] for s in SPLITS},
                    "n_touched": {s: b[s]["n_touched"] for s in SPLITS},
                    "A_per_month_discovery_after": round(b["discovery"]["A_after_per_month"], 2),
                    "degeneracy_guard_2_5_A_per_month": bool(b["discovery"]["A_after_per_month"] >= 2.5),
                    "effect_A_avg": {s: round(b[s]["effect_A_avg"], 2) for s in SPLITS},
                    "ci90": {s: [round(x, 1) for x in b[s]["effect_A_avg_ci90"]] for s in SPLITS},
                    "A_n": {s: [b[s]["A_before"]["n"], b[s]["A_after"]["n"]] for s in SPLITS},
                    "A_avg": {s: [round(b[s]["A_before"]["avg"], 1), round(b[s]["A_after"]["avg"], 1)] for s in SPLITS},
                    "paired_A_book_full": round(b["full"]["paired_A_book_all_nights"]["mean"], 2),
                    "paired_graded_book_full": round(b["full"]["paired_graded_book_all_nights"]["mean"], 2),
                    "usd_yr_A_full": round(b["full"]["usd_per_contract_per_year_A"]), "rf_pct_A": {s: b[s].get("random_filter_null_A", {}).get("percentile") for s in SPLITS},
                    "worst_A_full": [round(b["full"]["A_before"]["worst"], 1), round(b["full"]["A_after"]["worst"], 1)],
                    "pts_per_sigma_full": [round(b["full"]["A_before"]["pts_per_sigma"], 3), round(b["full"]["A_after"]["pts_per_sigma"], 3)],
                    "hicost_effect_full": round(b["full"]["effect_A_avg_hicost"], 2), "free_rule_criterion": r.get("free_rule_criterion")})
    return out


def main():
    t0 = time.time()
    out = {"group": GROUP, "generated_from": f"research/lab/grade_a/h_{GROUP}.py", "baseline_pnl_column": "pnl_net_open (sensitivity pnl_net_open_hicost)",
           "splits": SPLITS, "months": MONTHS, "bootstrap": {"blocks": "ISO week", "draws": N_BOOT, "rng": f"numpy default_rng({SEED})", "ci": "90% (80% also stored for the replication arm)"},
           "random_filter_null": {"draws": N_BOOT, "rng": f"numpy default_rng({SEED})"},
           "parameters": {"H5_post_ret": H5_POST_RET, "H6_dd20": H6_DD, "H6_ret": H6_RET, "H14_blocks": H14_MIN_BLOCKS, "exploratory_discovery_only": {"H5_grid": H5_GRID, "H6_dd_grid": H6_DD_GRID}},
           "knowability": {"rule_inputs_17xx": ["post_ret", "megacap_earnings_tonight", "pre_holiday", "holiday_tomorrow", "expected_asia_bars_proxy", "kospi_dd20", "kospi_ret",
                                                "hsi_dd20", "hsi_ret (computed from data/daily_close.csv with features.dchg's convention)", "sunday_open", "vix", "vix_z20", "rv_ratio",
                                                "fomc_tomorrow", "tier1_data_tomorrow", "dow", "other_grade/other_call/other_side (the other symbol's honest call, same 17:xx)"],
                           "rule_inputs_1800": ["open_past_stop (H8b stand-down; execution-time, not grading)"],
                           "ex_post_seen_not_used": ["outcome_open/resolved_k_open/mfe/mae (descriptives)", "n_bars/asia_n_bars (only the labelled ex post H9 variant)",
                                                     "v0_* (only the H14 self-check that reproduces the pre-registered numbers)", "catalogue tags", "in_catalogue", "kospi_next", "n225_next",
                                                     "move_18_20_in_dir", "eur_* columns"]},
           "verdict_rules": "supported on vault: vault effect with the predicted sign AND (vault CI90 excludes zero OR (full CI90 excludes zero AND vault point inside it AND random-filter pct >= 90)); "
                            "discovery only: discovery effect with the predicted sign and CI90 excluding zero while the vault does not; not testable at this n: < 8 affected vault A nights; "
                            "harmful: full effect negative with CI90 excluding zero; else no effect.  'Affected' for the n rule = the vault nights the rule touches (grade or P&L changed, "
                            "every grade the rule acts on; n_affected_A is reported alongside).  Free rules additionally carry the no-harm criterion (flagged nights' net P&L <= 0 on discovery AND vault).  "
                            "The LAB_DESIGN 2.7 degeneracy guard (>= 2.5 A nights per month on discovery) is reported per rule.",
           "symbols": {}}
    rows_all = []
    nq_sel = None
    for sym, other in (("NQ", "ES"), ("ES", "NQ")):
        R, rows = run_symbol(sym, other, forced_members=nq_sel if sym == "ES" else None)
        print_observations(sym, R)
        out["symbols"][sym] = R
        rows_all.extend(rows)
        if sym == "NQ":
            nq_sel = R["selected_members"]
    # replication: same-sign check of the ES full / vault A-avg effects against NQ
    rep = {}
    for rid in out["symbols"]["NQ"]["rules"]:
        if rid not in out["symbols"]["ES"]["rules"]:
            continue
        rep[rid] = {}
        for s in SPLITS:
            n, e = out["symbols"]["NQ"]["rules"][rid]["by_split"][s], out["symbols"]["ES"]["rules"][rid]["by_split"][s]
            ci80 = e["effect_A_avg_ci80"]
            arm = "supports" if (ci80[0] > 0 and n["effect_A_avg"] > 0) or (ci80[1] < 0 and n["effect_A_avg"] < 0) else \
                  ("contradicts" if (ci80[1] < 0 and n["effect_A_avg"] > 0) or (ci80[0] > 0 and n["effect_A_avg"] < 0) else "uninformative")
            rep[rid][s] = {"NQ_effect_A_avg": n["effect_A_avg"], "ES_effect_A_avg": e["effect_A_avg"], "ES_ci80": ci80, "ES_ci90": e["effect_A_avg_ci90"],
                           "same_sign": bool(np.sign(n["effect_A_avg"]) == np.sign(e["effect_A_avg"])) if abs(n["effect_A_avg"]) > EPS and abs(e["effect_A_avg"]) > EPS else None,
                           "ES_n_affected_A": e["n_affected_A"], "arm_reading_LAB_12_4": arm}
    out["replication_ES"] = rep
    out["summary"] = {sym: summary_rows(out["symbols"][sym], sym) for sym in ("NQ", "ES")}
    out["runtime_s"] = time.time() - t0
    with open(os.path.join(HERE, f"h_{GROUP}_results.json"), "w") as f:
        json.dump(_jsonable(out), f, indent=1)
    pd.DataFrame(rows_all).to_csv(os.path.join(HERE, f"h_{GROUP}_nights.csv"), index=False)
    print("\nSUMMARY (A-avg effect, A-book):")
    for sym in ("NQ", "ES"):
        for r in out["summary"][sym]:
            print(f"  {sym} {r['id']:16s} {r['verdict']:24s} dA disc/vault/full = {r['effect_A_avg']['discovery']:+.1f} / {r['effect_A_avg']['vault']:+.1f} / {r['effect_A_avg']['full']:+.1f} "
                  f"CI_full {r['ci90']['full']} touched {r['n_touched']['discovery']}/{r['n_touched']['vault']} affA {r['n_affected_A']['discovery']}/{r['n_affected_A']['vault']} "
                  f"rf% full {fmt(r['rf_pct_A']['full'], 0)} usd/yr {r['usd_yr_A_full']} A/month disc {r['A_per_month_discovery_after']}")
    print(f"\nwrote h_{GROUP}_results.json and h_{GROUP}_nights.csv ({len(rows_all)} rows) in {out['runtime_s']:.1f} s")


if __name__ == "__main__":
    main()
