#!/usr/bin/env python3
"""
h_detector_bridge.py -- the bridge from the Asia high/low detectors to the engine's Grade-A trades (group: detector_bridge).

Run from the project root:
    OMP_NUM_THREADS=1 python research/lab/grade_a/h_detector_bridge.py        # NQ (primary) and ES (replication arm)

Inputs (read-only): research/lab/grade_a/trades_honest_{SYM}.csv, candidates_{SYM}.csv, research/extremes/oos_intrasession_{SYM}.csv
(only for the k=7 overnight flag that the trades table does not carry), data/{SYM}_1h.csv via sessions.load_hourly.
Outputs: research/lab/grade_a/h_detector_bridge_results.json, h_detector_bridge_nights.csv (per-night baseline vs hypothesis
P&L for every rule, with the detector inputs each rule read) and a printed table.  Deterministic (numpy default_rng(0) for the
weekly-block bootstrap, the random-filter nulls and the D3 shuffle placebo); runtime about one minute.

Baseline = pnl_net_open (honest grade, 18:00-open fill, own-pair stop-priority resolution with gap fills, base costs);
sensitivity = pnl_net_open_hicost.  Every rule that changes an exit re-walks the raw hourly bars of the chosen candidate with
the builder's walker (asserted to reproduce the builder's resolution of every candidate of every night, including the Europe
hold of every scratch, when no rule is active).

ADVERSE EXTREME of a trade (the Asia extreme that hurts the position): the Asia HIGH for a SHORT, the Asia LOW for a LONG.
For a MEAN REVERSION call this is the RTH-direction extreme that the stop sits beyond (short fade after an up day: the Asia
high); for a CONTINUATION it is the opposite extreme (continuation long after an up day: the Asia low; its target sits beyond
the RTH high, which the Asia high must break).  The RTH-direction level is the RTH high after an up day (MR SHORT / CONT
LONG) and the RTH low after a down day (MR LONG / CONT SHORT); 'pB_dir' = Detector B's calibrated P(Asia breaks that level).

Hypotheses (decision-time honest; parameters pre-registered in the task text / LAB_DESIGN section 8):
  D1   Detector B veto at 17:xx.  MEAN REVERSION: NO EDGE if pB_dir >= 0.70 (BREAK call: the stop region will likely be traded
       through).  CONTINUATION: NO EDGE if pB_dir <= 0.10 (HOLD call: the level the target needs will not be taken).
       Thresholds = the validated 0.70 / 0.10 BREAK / HOLD thresholds (single, pre-registered).  Random-filter null; named
       placebo = the same rule read on the OTHER side's level (pB_other).  Exploratory, DISCOVERY ONLY: 0.80 / 0.05 and the
       raw ensemble column.
  D2   (exploratory) D1 as a demotion (A -> B when the veto holds: identical to D1 on the A series, the B series gains the
       nights) and D1 as a SWITCH (a fade whose level will break with p >= 0.70 is replaced by the night's best guard-passing
       CONTINUATION candidate, re-graded by the engine's own thresholds; no such candidate -> NO EDGE as in D1).
  D3   Detector A checkpoint at the closes of bars k=1 and k=2 (20:00 and 21:00 ET prints): for an open trade, if
       P(adverse extreme already in) <= 0.50 AND the position is adverse at that close -> exit at the close; >= 0.90 -> hold.
       The 0.90 hold threshold is the validated 'extreme already in' threshold (pre-registered); the 0.50 exit threshold
       is the tester's choice (it appears neither in LAB_DESIGN section 8 nor in the task text) and D3 is therefore
       registered as partly pre-registered; no grid was run on it.
       Comparators: (a) the price-only checkpoint (exit if adverse by > 0.25 x stop_dist at the same closes, no detector) and
       (b) a random-detector placebo (the (k1, k2) adverse probabilities shuffled across nights, default_rng(0)).
       Exploratory: D3_hold (the price-only checkpoint overridden by a >= 0.90 hold), D3_k1 / D3_k2 (one bar only).
  D4   Overnight hold conditional on the detector: for a trade still open at the 02:00 print (close of bar k=7), hold into
       Europe (levels active, exit at level else the Europe close) only when P(overnight adverse extreme already in) >= 0.90,
       else flat at 02:59 as in the baseline.  D4 reads the k=7 value (added here from oos_intrasession_{SYM}.csv: the right
       value for a decision at the 02:00 print); D4_k3 reads the last value the trades table carries (k=3, the 22:00 print),
       the bridge's stated limitation.  Reference: D4_uncond (hold every open position; the forensics negative result).
  D5   (exploratory) detector-informed stop placement: for a tight-stop fade with pB_dir in [0.30, 0.70], the same night's
       WIDE candidate with the same target (candidates table, re-walked); D5_rev: a wide fade with pB_dir < 0.30 -> tight.
  COMBINED  the group's supported-or-discovery rules jointly on the A nights, and the task's named D1 + D3 combination,
       each at the base and at the sensitivity cost schedule.

Decision times of the detector columns used: pB_high_above_cal / pB_low_below_cal (and _raw) are 17:xx ET values (Detector B,
walk-forward); pA_high_k / pA_low_k are read only at the close of bar k (D3: k=1 at the 20:00 print, k=2 at the 21:00 print);
pA_ovn_high_k / pA_ovn_low_k at the close of bar k (D4: k=7 at the 02:00 print; D4_k3: the k=3 value, stale by four bars).
Ex post inputs seen and NOT used as rule inputs: outcome_open / resolved_k_open (descriptives only: stopped rates of vetoed
nights, later-stop rates by detector bucket), eur_outcome_open / eur_pnl_open (self-check of the Europe walk only),
asia_n_bars / n_bars (never a rule input: a rule whose bar is absent leaves the night unchanged), catalogue tags, in_catalogue,
kospi_next, n225_next (never touched), the v0_* leaky probabilities (never touched).  Nights without detector values (holiday
eves with 6 bars, the 7-bar feed-gap nights, splices) are left unchanged by every detector rule and counted.
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

from sessions import ASIA_HOURS, EUROPE_HOURS, build_sessions, load_hourly

GROUP = "detector_bridge"
OUT = HERE
DATA = os.path.join(ROOT, "data")
EXTREMES = os.path.join(ROOT, "research", "extremes")
SPLITS = {"discovery": ("2025-04-01", "2026-05-31"), "vault": ("2026-06-01", "2026-11-06"),
          "full": ("2025-04-01", "2026-11-06")}
PV = {"NQ": 20.0, "ES": 50.0}
N_BOOT, SEED, N_NULL = 2000, 0, 2000
GRADES = ("A", "B", "C")
N_K = 9
EPS = 1e-9
MR, CONT = "MEAN REVERSION", "CONTINUATION"

# pre-registered single parameters
D1_BREAK, D1_HOLD = 0.70, 0.10          # Detector B BREAK / HOLD thresholds (validated)
D1_BREAK_X, D1_HOLD_X = 0.80, 0.05      # exploratory, discovery only
D3_P_EXIT, D3_P_HOLD = 0.50, 0.90       # Detector A: exit if <= 0.50 and adverse; hold if >= 0.90
D3_PRICE_FRAC = 0.25                    # price-only comparator: adverse > 0.25 x stop_dist
D3_KS = (1, 2)                          # closes of bars k=1 and k=2 (20:00 and 21:00 ET prints)
D4_P_HOLD = 0.90                        # overnight adverse-extreme flag
D4_K, D4_K_TABLE = 7, 3                 # the 02:00 print (k=7, added from the OOS file) / the table's last value (k=3)
D5_LO, D5_HI = 0.30, 0.70               # exploratory stop-placement band

REGISTRY = {
    "D1": ("Detector B veto at 17:xx: MEAN REVERSION -> NO EDGE if pB_dir >= 0.70 (BREAK); CONTINUATION -> NO EDGE if pB_dir <= 0.10 (HOLD)",
           "ALL", "0.70 (BREAK) / 0.10 (HOLD), single, pre-registered", "17:xx ET (Detector B calibrated columns)", +1, True),
    "D1_MR": ("the MEAN REVERSION half of D1 alone (BREAK veto)", MR, "0.70", "17:xx ET", +1, True),
    "D1_CONT": ("the CONTINUATION half of D1 alone (HOLD veto)", CONT, "0.10", "17:xx ET", +1, True),
    "D1_placebo": ("D1 read on the OTHER side's level (pB_other): MR veto if pB_other >= 0.70, CONT veto if pB_other <= 0.10 (named placebo)",
                   "ALL", "0.70 / 0.10", "17:xx ET", 0, True),
    "D2_demote": ("(exploratory) D1 as a demotion: A -> B when the veto condition holds (A series identical to D1; the B series gains the nights)",
                  "ALL", "0.70 / 0.10", "17:xx ET", +1, False),
    "D2_switch": ("(exploratory) D1 as a SWITCH: a fade with pB_dir >= 0.70 takes the night's max-EV guard-passing CONTINUATION candidate "
                  "(re-graded by the engine's thresholds); no such candidate -> NO EDGE; the CONT HOLD veto as in D1", "ALL", "0.70 / 0.10",
                  "17:xx ET", +1, False),
    "D2_switch_keep": ("(exploratory) the switch where a guard-passing continuation exists, otherwise the fade is KEPT (no veto); CONT half as D1",
                       "ALL", "0.70 / 0.10", "17:xx ET", +1, False),
    "D3": ("Detector A checkpoint at the closes of bars k=1 and k=2: exit at the close if adverse and P(adverse extreme in) <= 0.50; hold if >= 0.90",
           "ALL", "0.90 hold at k=1,2 (the validated 'extreme already in' threshold, pre-registered); 0.50 exit = the tester's choice, "
           "not in LAB_DESIGN section 8 or the task text (exploratory parameter, no grid run)", "close of bar k=1 (20:00 ET print) and k=2 (21:00 ET print)", +1, False),
    "D3_price": ("comparator (a): price-only checkpoint, exit at the k=1 / k=2 close if adverse by > 0.25 x stop_dist, no detector", "ALL",
                 "0.25 x stop_dist", "close of bar k=1 and k=2", +1, True),
    "D3_placebo": ("comparator (b): D3 with the (k1, k2) adverse probabilities shuffled across nights (default_rng(0))", "ALL",
                   "0.50 / 0.90 on shuffled probabilities", "close of bar k=1 and k=2", 0, True),
    "D3_hold": ("(exploratory) the price-only checkpoint (a) overridden by a hold when P(adverse extreme in) >= 0.90", "ALL",
                "0.25 x stop_dist, hold at 0.90", "close of bar k=1 and k=2", +1, False),
    "D3_k1": ("(exploratory) D3 at the k=1 close only", "ALL", "0.50 / 0.90 at k=1", "close of bar k=1 (20:00 ET print)", +1, False),
    "D3_k2": ("(exploratory) D3 at the k=2 close only", "ALL", "0.50 / 0.90 at k=2", "close of bar k=2 (21:00 ET print)", +1, False),
    "D4": ("overnight hold: a trade still open at the 02:00 print (close of bar k=7) is held into Europe (levels active, else the Europe close) "
           "only when P(overnight adverse extreme already in) at k=7 >= 0.90; else flat at 02:59", "ALL", "0.90 at k=7 (single, pre-registered)",
           "close of bar k=7 (02:00 ET print); k=7 value joined from oos_intrasession", +1, True),
    "D4_k3": ("D4 reading the last value the trades table carries (k=3, the 22:00 print) at the 02:00 decision: the bridge's stated limitation",
              "ALL", "0.90 at k=3", "close of bar k=7 using the k=3 value", +1, True),
    "D4_placebo": ("D4 read on the OTHER (favourable) overnight extreme flag >= 0.90 at k=7 (placebo by analogy with D1's; not named by LAB_DESIGN)",
                   "ALL", "0.90 at k=7", "close of bar k=7", 0, True),
    "D4_uncond": ("reference: every position still open at the 02:00 print is held into Europe (the forensics negative result)", "ALL", "none",
                  "close of bar k=7", -1, False),
    "D5": ("(exploratory) tight-stop fade with pB_dir in [0.30, 0.70] -> the same night's WIDE candidate with the same target (re-walked)", MR,
           "[0.30, 0.70]", "17:xx ET", +1, False),
    "D5_rev": ("(exploratory) wide-stop fade with pB_dir < 0.30 -> the same night's TIGHT candidate with the same target (re-walked)", MR,
               "< 0.30", "17:xx ET", +1, False),
}
PREREG_IDS = ["D1", "D4"]                 # D3's 0.90 hold threshold is validated; its 0.50 exit threshold is the tester's choice
PARTLY_PREREG_IDS = {"D3": "0.90 hold pre-registered (detector validation); 0.50 exit threshold chosen by the tester, not pre-registered"}
EXPLORATORY_IDS = ["D2_demote", "D2_switch", "D2_switch_keep", "D3_hold", "D3_k1", "D3_k2", "D4_k3", "D5", "D5_rev"]
PLACEBO_OF = {"D1": "D1_placebo", "D3": "D3_placebo", "D4": "D4_placebo"}
SKIP_RULES = ["D1", "D1_MR", "D1_CONT", "D1_placebo", "D2_demote", "D2_switch", "D2_switch_keep"]   # rules that remove nights -> random-filter null
REMOVED_PREFIXES = ("veto", "demoted", "no_cont_candidate_vetoed", "switched_cont_below_C")


# --------------------------------------------------------------------------------------------------
# bars and the rule-aware walker
# --------------------------------------------------------------------------------------------------
def bar_groups(h: pd.DataFrame) -> tuple[dict, dict]:
    """{Globex date -> Asia bars}, {Globex date -> Europe bars}: the builder's grouping (sessions.path_outcomes)."""
    g = pd.Series(h.index.date, index=h.index)
    sh = h.index.hour >= 18
    g[sh] = (h.index[sh] + pd.Timedelta(days=1)).date
    hh = h.copy()
    hh["gdate"] = g.values
    hh["hour"] = h.index.hour
    asia = {gd: grp.sort_index() for gd, grp in hh[hh["hour"].isin(ASIA_HOURS)].groupby("gdate")}
    eur = {gd: grp.sort_index() for gd, grp in hh[hh["hour"].isin(EUROPE_HOURS)].groupby("gdate")}
    return asia, eur


def _beyond(side: str, px: float, lvl: float, kind: str) -> bool:
    if side == "LONG":
        return px >= lvl if kind == "target" else px <= lvl
    return px <= lvl if kind == "target" else px >= lvl


class Night:
    """The raw Asia (and Europe) bars of one night."""

    def __init__(self, bars: pd.DataFrame, eur: pd.DataFrame | None):
        self.O, self.H, self.L, self.C = (bars[c].values.astype(float) for c in ("Open", "High", "Low", "Close"))
        self.hours = bars["hour"].values.astype(int)
        self.n = len(bars)
        self.has_eur = eur is not None and len(eur) > 0
        if self.has_eur:
            self.EO, self.EH, self.EL, self.EC = (eur[c].values.astype(float) for c in ("Open", "High", "Low", "Close"))
        else:
            self.EO = self.EH = self.EL = self.EC = np.zeros(0)


def walk_bridge(nt: Night, side: str, entry: float, target: float, stop: float, rules: dict | None = None) -> dict:
    """The builder's walk (stop priority inside a bar, a bar opening beyond the stop fills at its Open, targets at level,
    scratch at the last Asia close) plus two close-of-bar rules:
      ckpts   : list of dicts {k, adv_thr, p, p_exit_max, p_hold_min}; at the close of bar k, if the MTM P&L < -adv_thr and
                (p_exit_max is None or p <= p_exit_max) and not (p_hold_min is not None and p >= p_hold_min) -> exit at the close.
                A checkpoint whose p is NaN never fires.
      eur_hold: dict {k, hold}; at the close of bar k, if still open and hold is True, the position is carried into the Europe
                bars (same levels, same conventions; exit at level or at the last Europe close); no Europe bars -> scratch.
    With rules={} this is exactly the builder's walk."""
    rules = rules or {}
    sgn = 1.0 if side == "LONG" else -1.0
    O, H, L, C = nt.O, nt.H, nt.L, nt.C
    n = nt.n
    mtm = np.full(N_K, np.nan)
    mfe, mae = 0.0, 0.0
    ck = {int(c["k"]): c for c in rules.get("ckpts", [])}
    eh = rules.get("eur_hold")
    extend = False
    for i in range(n):
        fav = sgn * ((H[i] if sgn > 0 else L[i]) - entry)
        adv = sgn * ((L[i] if sgn > 0 else H[i]) - entry)
        stop_hit = (L[i] <= stop) if sgn > 0 else (H[i] >= stop)
        tgt_hit = (H[i] >= target) if sgn > 0 else (L[i] <= target)
        if stop_hit:
            gap = (O[i] <= stop) if sgn > 0 else (O[i] >= stop)
            ex = float(O[i]) if gap else float(stop)
            pnl = sgn * (ex - entry)
            return dict(outcome="stop", resolved_k=i, exit=ex, pnl=pnl, mfe=mfe, mae=min(mae, pnl), gapfill=int(gap), samebar=int(tgt_hit), mtm=mtm, extended=0)
        if tgt_hit:
            pnl = sgn * (float(target) - entry)
            return dict(outcome="target", resolved_k=i, exit=float(target), pnl=pnl, mfe=max(mfe, pnl), mae=min(mae, adv), gapfill=0, samebar=0, mtm=mtm, extended=0)
        mfe, mae = max(mfe, fav), min(mae, adv)
        m = sgn * (float(C[i]) - entry)
        if i < N_K:
            mtm[i] = m
        c = ck.get(i)
        if c is not None:
            p = c.get("p")
            p_ok = True
            if c.get("p_exit_max") is not None:
                p_ok = (p is not None) and (not np.isnan(p)) and p <= c["p_exit_max"]
            if c.get("p_hold_min") is not None and p is not None and not np.isnan(p) and p >= c["p_hold_min"]:
                p_ok = False
            if m < -float(c["adv_thr"]) and p_ok:
                return dict(outcome=f"checkpoint_k{i}", resolved_k=i, exit=float(C[i]), pnl=m, mfe=mfe, mae=mae, gapfill=0, samebar=0, mtm=mtm, extended=0)
        if eh is not None and i == int(eh["k"]) and bool(eh["hold"]):
            extend = True
    if extend and nt.has_eur:
        EO, EH, EL, EC = nt.EO, nt.EH, nt.EL, nt.EC
        for i in range(len(EO)):
            fav = sgn * ((EH[i] if sgn > 0 else EL[i]) - entry)
            adv = sgn * ((EL[i] if sgn > 0 else EH[i]) - entry)
            stop_hit = (EL[i] <= stop) if sgn > 0 else (EH[i] >= stop)
            tgt_hit = (EH[i] >= target) if sgn > 0 else (EL[i] <= target)
            if stop_hit:
                gap = (EO[i] <= stop) if sgn > 0 else (EO[i] >= stop)
                ex = float(EO[i]) if gap else float(stop)
                pnl = sgn * (ex - entry)
                return dict(outcome="eur_stop", resolved_k=N_K + i, exit=ex, pnl=pnl, mfe=mfe, mae=min(mae, pnl), gapfill=int(gap), samebar=int(tgt_hit), mtm=mtm, extended=1)
            if tgt_hit:
                pnl = sgn * (float(target) - entry)
                return dict(outcome="eur_target", resolved_k=N_K + i, exit=float(target), pnl=pnl, mfe=max(mfe, pnl), mae=min(mae, adv), gapfill=0, samebar=0, mtm=mtm, extended=1)
            mfe, mae = max(mfe, fav), min(mae, adv)
        ex = float(EC[-1])
        return dict(outcome="eur_close", resolved_k=np.nan, exit=ex, pnl=sgn * (ex - entry), mfe=mfe, mae=mae, gapfill=0, samebar=0, mtm=mtm, extended=1)
    ex = float(C[n - 1])
    return dict(outcome="scratch", resolved_k=np.nan, exit=ex, pnl=sgn * (ex - entry), mfe=mfe, mae=mae, gapfill=0, samebar=0, mtm=mtm, extended=0)


def resolve_open(nt: Night, side: str, target: float, stop: float, rules: dict | None = None) -> dict:
    """The 18:00-open fill of a candidate (unfillable when the open is already beyond the target or the stop), then the walk."""
    out = {"traded": 0, "pnl": 0.0, "outcome": None, "resolved_k": np.nan, "exit": np.nan, "reason": "", "entry": float(nt.O[0]), "extended": 0}
    entry = float(nt.O[0])
    if _beyond(side, entry, target, "target"):
        out["reason"] = "open_past_target"
        return out
    if _beyond(side, entry, stop, "stop"):
        out["reason"] = "open_past_stop"
        return out
    r = walk_bridge(nt, side, entry, target, stop, rules)
    out.update(traded=1, pnl=float(r["pnl"]), outcome=r["outcome"], resolved_k=r["resolved_k"], exit=r["exit"], reason=r["outcome"], extended=r["extended"])
    return out


# --------------------------------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------------------------------
def block_boot_ci(values: pd.Series, n_boot: int = N_BOOT, seed: int = SEED, q=(0.05, 0.95)) -> list:
    """Weekly-block (ISO week) bootstrap 90% CI of the mean; numpy default_rng(seed); the builder's procedure."""
    v = values.dropna()
    if len(v) < 2:
        return [float("nan"), float("nan")]
    iso = v.index.isocalendar()
    keys = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).values
    uk = np.unique(keys)
    bs = np.array([v.values[keys == k].sum() for k in uk])
    bn = np.array([(keys == k).sum() for k in uk], dtype=float)
    rng = np.random.default_rng(seed)
    nb = len(uk)
    means = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, nb, nb)
        means[i] = bs[pick].sum() / bn[pick].sum()
    lo, hi = np.quantile(means, q)
    return [float(lo), float(hi)]


def composition_effect(base_pnl: np.ndarray, hyp_pnl: np.ndarray, baseA: np.ndarray, hypA: np.ndarray, index: pd.DatetimeIndex,
                       n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Difference of Grade-A averages (hyp over its A nights minus base over its A nights) with a weekly-block bootstrap
    CI over the population's nights (the statistic the geometry and vetoes groups report as 'effect on A avg')."""
    if len(index) == 0 or baseA.sum() == 0:
        return {"effect_A_avg_composition": float("nan"), "effect_A_avg_composition_ci90": [float("nan"), float("nan")]}
    mean_h = float(hyp_pnl[hypA].mean()) if hypA.sum() else 0.0
    mean_b = float(base_pnl[baseA].mean())
    iso = index.isocalendar()
    keys = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).values
    uk = np.unique(keys)
    blocks = [np.flatnonzero(keys == k) for k in uk]
    rng = np.random.default_rng(seed)
    nb = len(blocks)
    draws = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, nb, nb)
        ii = np.concatenate([blocks[j] for j in pick])
        h_, b_ = hyp_pnl[ii][hypA[ii]], base_pnl[ii][baseA[ii]]
        draws[i] = (h_.mean() if len(h_) else 0.0) - (b_.mean() if len(b_) else 0.0)
    return {"effect_A_avg_composition": mean_h - mean_b, "A_avg_hyp_composition": mean_h, "A_avg_base_composition": mean_b,
            "effect_A_avg_composition_ci90": [float(np.quantile(draws, 0.05)), float(np.quantile(draws, 0.95))]}


def months_in(split: str) -> float:
    a, b = (pd.Timestamp(x) for x in SPLITS[split])
    return (b - a).days / 365.25 * 12


def split_mask(idx: pd.DatetimeIndex, split: str) -> np.ndarray:
    a, b = (pd.Timestamp(x) for x in SPLITS[split])
    return (idx >= a) & (idx <= b)


def series_stats(p: pd.Series, traded: pd.Series | None = None) -> dict:
    p = p.astype(float)
    n = len(p)
    sd = float(p.std(ddof=1)) if n > 1 else float("nan")
    out = {"n": int(n), "avg": float(p.mean()) if n else float("nan"), "total": float(p.sum()),
           "win": float((p > 0).mean()) if n else float("nan"), "worst": float(p.min()) if n else float("nan"),
           "sd": sd, "pts_per_sigma": float(p.mean() / sd) if n > 1 and sd > 0 else float("nan")}
    if traded is not None:
        out["traded_n"] = int(traded.sum())
        tr = p[traded == 1]
        out["avg_per_traded"] = float(tr.mean()) if len(tr) else float("nan")
        out["win_per_traded"] = float((tr > 0).mean()) if len(tr) else float("nan")
    return out


def paired(base: pd.Series, hyp: pd.Series, split: str, pv: float, base_traded=None, hyp_traded=None, base_hi=None, hyp_hi=None) -> dict:
    d = (hyp - base).astype(float)
    out = {"n": int(len(d)), "n_affected": int((d.abs() > EPS).sum()), "effect": float(d.mean()) if len(d) else float("nan"),
           "effect_ci90": block_boot_ci(d), "effect_total": float(d.sum()),
           "usd_per_contract_per_year": float(d.sum() * pv * 12 / months_in(split)),
           "base": series_stats(base, base_traded), "hyp": series_stats(hyp, hyp_traded)}
    if base_hi is not None and hyp_hi is not None:
        dh = (hyp_hi - base_hi).astype(float)
        out["effect_hicost"] = float(dh.mean()) if len(dh) else float("nan")
        out["effect_hicost_ci90"] = block_boot_ci(dh)
        out["hyp_avg_hicost"] = float(hyp_hi.mean()) if len(hyp_hi) else float("nan")
        out["base_avg_hicost"] = float(base_hi.mean()) if len(base_hi) else float("nan")
    return out


def verdict_of(res: dict, pred_sign: int, rf_pct: float | None) -> str:
    """The task's verdict rules.  harmful > not testable (< 8 affected vault nights) > supported on vault > discovery only > no effect.
    The random-filter condition applies only to rules that remove or skip nights (rf_pct is None otherwise)."""
    f, v, dsc = res["full"], res["vault"], res["discovery"]
    lo_f, hi_f = f["effect_ci90"]
    lo_v, hi_v = v["effect_ci90"]
    lo_d, hi_d = dsc["effect_ci90"]
    excl = lambda lo, hi: (lo > 0) or (hi < 0)
    if f["effect"] < 0 and excl(lo_f, hi_f):
        return "harmful"
    if v["n_affected"] < 8:
        return "not testable at this n"
    sign_ok = (pred_sign == 0 and v["effect"] != 0) or (pred_sign > 0 and v["effect"] > 0) or (pred_sign < 0 and v["effect"] < 0)
    rf_ok = True if rf_pct is None or np.isnan(rf_pct) else (rf_pct >= 90)
    if sign_ok and (excl(lo_v, hi_v) or (excl(lo_f, hi_f) and lo_f <= v["effect"] <= hi_f and rf_ok)):
        return "supported on vault"
    d_ok = ((pred_sign >= 0 and dsc["effect"] > 0) or (pred_sign < 0 and dsc["effect"] < 0)) and excl(lo_d, hi_d)
    if d_ok:
        return "discovery only"
    return "no effect"


# --------------------------------------------------------------------------------------------------
# loading, derived detector columns, self-checks
# --------------------------------------------------------------------------------------------------
def load_symbol(sym: str):
    T = pd.read_csv(os.path.join(OUT, f"trades_honest_{sym}.csv"), parse_dates=["date"]).set_index("date")
    cands = pd.read_csv(os.path.join(OUT, f"candidates_{sym}.csv"), parse_dates=["date"])
    h = load_hourly(os.path.join(DATA, f"{sym}_1h.csv"))
    s = build_sessions(h)
    asia_g, eur_g = bar_groups(h)
    nights = {}
    for d in T.index:
        gd = pd.Timestamp(s.loc[d, "asia_gdate"]).date()
        nights[d] = Night(asia_g[gd], eur_g.get(gd))
    # the k=7 (02:00 print) and k=8 overnight flags from the detector's OOS file (keyed by RTH date, positional k; the
    # trades table carries k=0..3 only)
    ia = pd.read_csv(os.path.join(EXTREMES, f"oos_intrasession_{sym}.csv"), parse_dates=["date"])
    add = {}
    for k in (D4_K, 8):
        sub = ia[ia["k"] == k].set_index("date")
        for dst, src in (("pA_ovn_high", "p_ovn_high_done"), ("pA_ovn_low", "p_ovn_low_done"), ("pA_high", "p_high_done"), ("pA_low", "p_low_done")):
            add[f"{dst}_k{k}"] = sub[src].reindex(T.index).values
    T = pd.concat([T, pd.DataFrame(add, index=T.index)], axis=1)
    # consistency of the join with the builder's k<=3 columns
    for k in range(4):
        sub = ia[ia["k"] == k].set_index("date")
        for dst, src in (("pA_ovn_low", "p_ovn_low_done"), ("pA_high", "p_high_done")):
            a, b = T[f"{dst}_k{k}"], sub[src].reindex(T.index)
            assert ((a - b).abs().fillna(0) < 1e-12).all() and (a.isna() == b.isna()).all(), (sym, dst, k)
    return T, cands, nights


def derive(T: pd.DataFrame) -> pd.DataFrame:
    """Side-specific detector columns.  up-day night: MR SHORT / CONT LONG (asserted against is_down)."""
    T = T.copy()
    graded = T["grade"].isin(GRADES)
    up = ((T["call"] == MR) & (T["side"] == "SHORT")) | ((T["call"] == CONT) & (T["side"] == "LONG"))
    assert ((up == (T["is_down"] == 0)) | ~graded).all(), "side/direction mapping"
    T["rth_dir_up"] = up.astype(int)
    for sfx in ("cal", "raw"):
        hi, lo = T[f"pB_high_above_{sfx}"], T[f"pB_low_below_{sfx}"]
        T[f"pB_dir_{sfx}"] = np.where(up, hi, lo)
        T[f"pB_other_{sfx}"] = np.where(up, lo, hi)
    is_short = T["side"] == "SHORT"
    for k in range(4):
        T[f"pA_adv_k{k}"] = np.where(is_short, T[f"pA_high_k{k}"], T[f"pA_low_k{k}"])
        T[f"pA_fav_k{k}"] = np.where(is_short, T[f"pA_low_k{k}"], T[f"pA_high_k{k}"])
        T[f"pA_ovn_adv_k{k}"] = np.where(is_short, T[f"pA_ovn_high_k{k}"], T[f"pA_ovn_low_k{k}"])
        T[f"pA_ovn_fav_k{k}"] = np.where(is_short, T[f"pA_ovn_low_k{k}"], T[f"pA_ovn_high_k{k}"])
    for k in (D4_K, 8):
        T[f"pA_ovn_adv_k{k}"] = np.where(is_short, T[f"pA_ovn_high_k{k}"], T[f"pA_ovn_low_k{k}"])
        T[f"pA_ovn_fav_k{k}"] = np.where(is_short, T[f"pA_ovn_low_k{k}"], T[f"pA_ovn_high_k{k}"])
        T[f"pA_adv_k{k}"] = np.where(is_short, T[f"pA_high_k{k}"], T[f"pA_low_k{k}"])
    T.loc[~graded, [c for c in T.columns if c.startswith(("pB_dir", "pB_other", "pA_adv", "pA_fav", "pA_ovn_adv", "pA_ovn_fav"))]] = np.nan
    T["det_B_avail"] = (graded & T["pB_dir_cal"].notna()).astype(int)
    T["det_A_avail"] = (graded & T["pA_adv_k1"].notna() & T["pA_adv_k2"].notna()).astype(int)
    T["det_ovn7_avail"] = (graded & T[f"pA_ovn_adv_k{D4_K}"].notna()).astype(int)
    return T


def self_check(sym: str, T: pd.DataFrame, cands: pd.DataFrame, nights: dict) -> dict:
    """The walker with no rule reproduces the builder's 18:00-open resolution of EVERY candidate (P&L, outcome, exit bar, MTM
    path), and the unconditional Europe hold reproduces eur_pnl_open on every scratch with Europe bars."""
    n_open = n_eur = 0
    for _, c in cands.iterrows():
        nt = nights[c["date"]]
        r = resolve_open(nt, c["side"], float(c["target"]), float(c["stop"]))
        assert r["traded"] == int(c["traded_open"]), (sym, c["date"], c["cand_id"], r["reason"])
        if r["traded"]:
            assert abs(r["pnl"] - float(c["pnl_open"])) < 1e-9 and r["outcome"] == c["outcome_open"], (sym, c["date"], c["cand_id"])
            rk = c["resolved_k_open"]
            assert (pd.isna(rk) and pd.isna(r["resolved_k"])) or int(rk) == int(r["resolved_k"])
            n_open += 1
            if c["outcome_open"] == "scratch" and nt.has_eur:
                w = walk_bridge(nt, c["side"], float(nt.O[0]), float(c["target"]), float(c["stop"]), {"eur_hold": {"k": 0, "hold": True}})
                assert w["extended"] == 1 and abs(w["pnl"] - float(c["eur_pnl_open"])) < 1e-9, (sym, c["date"], c["cand_id"], w["pnl"], c["eur_pnl_open"])
                eo = {"eur_stop": "stop", "eur_target": "target", "eur_close": "neither"}[w["outcome"]]
                assert eo == c["eur_outcome_open"], (sym, c["date"], c["cand_id"], eo, c["eur_outcome_open"])
                n_eur += 1
    for d, r in T.iterrows():
        nt = nights[d]
        assert nt.n == int(r["n_bars"]) and nt.hours[0] == int(r["k0_hour"])
        if pd.notna(r["entry_open"]):
            assert abs(nt.O[0] - float(r["entry_open"])) < 1e-9
        if r["grade"] in GRADES:
            for k in range(N_K):
                a, b = (np.nan, float(r[f"pnl_mtm_k{k}_open"]))
                # MTM path: recompute from the bars for the chosen candidate when traded
                if int(r["traded_open"]) == 1:
                    w = walk_bridge(nt, r["side"], float(nt.O[0]), float(r["target"]), float(r["stop"]))
                    a = w["mtm"][k]
                assert (np.isnan(a) and np.isnan(b)) or abs(a - b) < 1e-9, (sym, d, k, a, b)
    return {"candidates_open_fill_reproduced": n_open, "europe_hold_reproduced_on_scratches": n_eur, "nights_checked": int(len(T))}


# --------------------------------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------------------------------
def best_cont_candidate(cands_night: pd.DataFrame):
    """The night's max-EV guard-passing CONTINUATION candidate, or None."""
    c = cands_night[(cands_night["kind"] == CONT) & (cands_night["guard_ok"] == 1)]
    if c.empty:
        return None
    return c.loc[c["ev_pts"].idxmax()]


def grade_of(conf_frac: float) -> str:
    conf = conf_frac * 100
    return "A" if conf >= 72 else "B" if conf >= 63 else "C" if conf >= 56 else "NO EDGE"


def apply_rule(T: pd.DataFrame, nights: dict, cands_by_date: dict, rid: str, cfg: dict, shuffled: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-night hypothesis P&L for one rule on the graded nights.  cfg keys:
       veto=(mode, break_thr, hold_thr, column) with mode in {'dir','other'} and column 'cal'/'raw'   -> night-level NO EDGE
       switch=('veto'|'keep')          -> the D2 switch (fade -> best continuation when pB_dir >= break_thr)
       demote=True                     -> D2 demotion (grade A -> B when the veto holds; P&L unchanged)
       ckpt=dict(ks, adv_frac, p_col, p_exit_max, p_hold_min)   -> close-of-bar checkpoints (p_col None = price only)
       eur=dict(k, p_col, thr) / eur_uncond=True                  -> overnight hold
       swap=('tight->wide', lo, hi) / ('wide->tight', hi)         -> D5 candidate swap
       kind: 'ALL' or a call kind the rule touches
    Returns a frame indexed like T: pnl_net, pnl_net_hi, traded, reason, applies, hyp_grade, hyp_kind, affected."""
    rows = {}
    for d, r in T.iterrows():
        g = r["grade"]
        if g not in GRADES:
            rows[d] = dict(pnl_net=np.nan, pnl_net_hi=np.nan, traded=0, reason="not graded", applies=0, hyp_grade=g, hyp_kind=r["call"], det_in=np.nan)
            continue
        base_net, base_hi = float(r["pnl_net_open"]), float(r["pnl_net_open_hicost"])
        applies = cfg.get("kind", "ALL") == "ALL" or r["call"] == cfg.get("kind", "ALL")
        if not applies:
            rows[d] = dict(pnl_net=base_net, pnl_net_hi=base_hi, traded=int(r["traded_open"]), reason="untouched kind", applies=0, hyp_grade=g, hyp_kind=r["call"], det_in=np.nan)
            continue
        side, target, stop, kind, hyp_grade = r["side"], float(r["target"]), float(r["stop"]), r["call"], g
        cost_b, cost_h = float(r["cost_base"]), float(r["cost_hi"])
        reason_pre, det_in = "", np.nan
        # ---- 17:xx rules: veto / demotion / switch / swap ----
        if "veto" in cfg or "switch" in cfg or cfg.get("demote"):
            mode, bthr, hthr, col = cfg.get("veto", ("dir", D1_BREAK, D1_HOLD, "cal"))
            p = float(r[f"pB_{mode}_{col}"]) if pd.notna(r[f"pB_{mode}_{col}"]) else np.nan
            det_in = p
            vetoed = False
            if not np.isnan(p):
                if kind == MR and p >= bthr:
                    vetoed = True
                    reason_pre = "veto_MR_break"
                elif kind == CONT and p <= hthr:
                    vetoed = True
                    reason_pre = "veto_CONT_hold"
            else:
                reason_pre = "no_detector_B"
            if vetoed and cfg.get("demote"):
                hyp_grade = "B" if g == "A" else g
                rows[d] = dict(pnl_net=base_net, pnl_net_hi=base_hi, traded=int(r["traded_open"]), reason="demoted_A_to_B" if g == "A" else reason_pre,
                               applies=1, hyp_grade=hyp_grade, hyp_kind=kind, det_in=det_in)
                continue
            if vetoed and kind == MR and "switch" in cfg:
                bc = best_cont_candidate(cands_by_date.get(d))
                if bc is not None:
                    side, target, stop, kind = bc["side"], float(bc["target"]), float(bc["stop"]), CONT
                    hyp_grade = grade_of(float(bc["win_rate_on_resolution"]))
                    reason_pre = f"switched_to_{bc['variant']}_cont"
                    vetoed = hyp_grade == "NO EDGE"
                    if vetoed:
                        reason_pre = "switched_cont_below_C"
                elif cfg["switch"] == "keep":
                    vetoed = False
                    reason_pre = "no_cont_candidate_kept_fade"
                else:
                    reason_pre = "no_cont_candidate_vetoed"
            if vetoed:
                rows[d] = dict(pnl_net=0.0, pnl_net_hi=0.0, traded=0, reason=reason_pre, applies=1, hyp_grade="NO EDGE" if "switch" in cfg or "veto" in cfg else hyp_grade,
                               hyp_kind=kind, det_in=det_in)
                continue
        if "swap" in cfg and kind == MR:
            p = float(r["pB_dir_cal"]) if pd.notna(r["pB_dir_cal"]) else np.nan
            det_in = p
            want = None
            if cfg["swap"][0] == "tight->wide" and r["variant"] == "tight" and not np.isnan(p) and cfg["swap"][1] <= p <= cfg["swap"][2]:
                want = "wide"
            if cfg["swap"][0] == "wide->tight" and r["variant"] == "wide" and not np.isnan(p) and p < cfg["swap"][1]:
                want = "tight"
            if want is not None:
                cn = cands_by_date.get(d)
                alt = cn[(cn["kind"] == MR) & (cn["variant"] == want) & (cn["target_key"] == r["best"]) & (cn["side"] == side)]
                if len(alt) == 1:
                    target, stop = float(alt["target"].iloc[0]), float(alt["stop"].iloc[0])
                    reason_pre = f"swapped_to_{want}"
                else:
                    reason_pre = f"no_{want}_candidate"
        # ---- walker rules ----
        rules = {}
        if "ckpt" in cfg:
            ck = cfg["ckpt"]
            lst = []
            for k in ck["ks"]:
                if ck.get("p_col") is None:
                    p = np.nan
                    if int(r["det_A_avail"]) != 1:      # comparability: the price-only comparator fires only where the detector could
                        continue
                    lst.append({"k": k, "adv_thr": ck["adv_frac"] * float(r["stop_dist"]), "p": None, "p_exit_max": None, "p_hold_min": ck.get("p_hold_min")})
                else:
                    src = shuffled.loc[d] if ck.get("shuffled") else r
                    p = float(src[f"{ck['p_col']}_k{k}"]) if pd.notna(src[f"{ck['p_col']}_k{k}"]) else np.nan
                    lst.append({"k": k, "adv_thr": ck["adv_frac"] * float(r["stop_dist"]), "p": p, "p_exit_max": ck.get("p_exit_max"), "p_hold_min": ck.get("p_hold_min")})
            if "hold_col" in ck:                        # D3_hold: price-only exit unless the detector says the adverse extreme is in
                for item in lst:
                    pv_ = float(r[f"{ck['hold_col']}_k{item['k']}"]) if pd.notna(r[f"{ck['hold_col']}_k{item['k']}"]) else np.nan
                    item["p"], item["p_hold_min"], item["p_exit_max"] = pv_, ck["p_hold_min"], None
            rules["ckpts"] = lst
            det_in = lst[0]["p"] if lst and lst[0]["p"] is not None else det_in
        if "eur" in cfg:
            e = cfg["eur"]
            p = float(r[f"{e['p_col']}_k{e['k']}"]) if pd.notna(r[f"{e['p_col']}_k{e['k']}"]) else np.nan
            det_in = p
            rules["eur_hold"] = {"k": D4_K, "hold": (not np.isnan(p)) and p >= e["thr"]}
        if cfg.get("eur_uncond"):
            rules["eur_hold"] = {"k": D4_K, "hold": True}
        res = resolve_open(nights[d], side, target, stop, rules)
        pnl_net = res["pnl"] - cost_b if res["traded"] else 0.0
        pnl_hi = res["pnl"] - cost_h if res["traded"] else 0.0
        reason = (reason_pre + "|" if reason_pre else "") + (res["reason"] or "")
        rows[d] = dict(pnl_net=pnl_net, pnl_net_hi=pnl_hi, traded=res["traded"], reason=reason, applies=1, hyp_grade=hyp_grade, hyp_kind=kind,
                       det_in=det_in, outcome=res["outcome"], resolved_k=res["resolved_k"], extended=res["extended"])
    R = pd.DataFrame.from_dict(rows, orient="index")
    R.index.name = "date"
    R["affected"] = (((R["pnl_net"] - T["pnl_net_open"]).abs() > EPS) | (R["hyp_grade"] != T["grade"])).astype(int)
    return R


def a_series(T: pd.DataFrame, R: pd.DataFrame | None, col_base: str = "pnl_net_open", col_hyp: str = "pnl_net", hi: bool = False):
    """The Grade-A P&L series: a night's P&L counts when it is graded A (baseline grade for the base series, hypothesis grade
    for the hypothesis series), else 0; indexed over all nights."""
    if R is None:
        c = "pnl_net_open_hicost" if hi else col_base
        return T[c].where(T["grade"] == "A", 0.0).fillna(0.0)
    c = "pnl_net_hi" if hi else col_hyp
    return R[c].where(R["hyp_grade"] == "A", 0.0).fillna(0.0)


def evaluate(T: pd.DataFrame, R: pd.DataFrame, pop: pd.Series, pv: float, grade_aware: bool = False) -> dict:
    """Paired evaluation of a rule on a population mask per split.  grade_aware=True pairs the A series (A-either population,
    a night that leaves or enters Grade A counts 0 on the side where it is not A)."""
    out = {}
    for split in SPLITS:
        m = pop & split_mask(T.index, split) & (T["splice"] == 0)
        if grade_aware:
            base, hyp = a_series(T, None)[m], a_series(T, R)[m]
            base_hi, hyp_hi = a_series(T, None, hi=True)[m], a_series(T, R, hi=True)[m]
            bt, ht = T.loc[m, "traded_open"].where(T.loc[m, "grade"] == "A", 0), R.loc[m, "traded"].where(R.loc[m, "hyp_grade"] == "A", 0)
        else:
            base, hyp = T.loc[m, "pnl_net_open"], R.loc[m, "pnl_net"]
            base_hi, hyp_hi = T.loc[m, "pnl_net_open_hicost"], R.loc[m, "pnl_net_hi"]
            bt, ht = T.loc[m, "traded_open"], R.loc[m, "traded"]
        out[split] = paired(base, hyp, split, pv, bt, ht, base_hi, hyp_hi)
        out[split]["A_n_before"] = int((T.loc[m, "grade"] == "A").sum())
        out[split]["A_n_after"] = int(((R.loc[m, "hyp_grade"] == "A") & ((R.loc[m, "traded"] == 1) | (R.loc[m, "reason"].str.startswith("open_past", na=False)))).sum())
        # composition statistic (difference of A averages), the other groups' headline, with its own weekly-block CI
        baseA = (T.loc[m, "grade"] == "A").values
        hypA = ((R.loc[m, "hyp_grade"] == "A") & ((R.loc[m, "traded"] == 1) | (R.loc[m, "reason"].str.startswith("open_past", na=False)))).values
        out[split].update(composition_effect(T.loc[m, "pnl_net_open"].values.astype(float), np.nan_to_num(hyp.values.astype(float)), baseA, hypA, T.index[m]))
        mix = R.loc[m & (R["applies"] == 1), "reason"].value_counts()
        out[split]["hyp_reason_mix"] = {str(k): int(v) for k, v in mix.items()}
        bmix = T.loc[m & (T["traded_open"] == 1), "outcome_open"].value_counts()
        out[split]["base_outcome_mix"] = {str(k): int(v) for k, v in bmix.items()}
    return out


def random_filter_null(T: pd.DataFrame, R: pd.DataFrame, pop: pd.Series, eligible: pd.Series, removed: pd.Series) -> dict:
    """Random-filter null for a rule that sets nights to 0: the same number of removals drawn at random from the eligible
    population (nights the rule could have removed: graded, in the population, detector available); the effect is measured on
    the whole population against the baseline.  Unstratified (the task's wording) and kind-stratified percentiles, 2000 draws."""
    out = {}
    for split in SPLITS:
        m = pop & split_mask(T.index, split) & (T["splice"] == 0)
        base = T.loc[m, "pnl_net_open"].values
        hyp = R.loc[m, "pnl_net"].values
        el = eligible[m].values.astype(bool)
        rem = removed[m].values.astype(bool)
        kinds = T.loc[m, "call"].values
        n_rem, n_el = int(rem.sum()), int(el.sum())
        actual = float((hyp - base).mean())
        if n_el == 0 or n_rem == 0 or n_rem > n_el:
            out[split] = {"n_removed": n_rem, "n_eligible": n_el, "actual_effect": actual, "percentile": float("nan"), "percentile_kind_stratified": float("nan"), "draws": 0}
            continue
        npop = len(base)
        rng = np.random.default_rng(SEED)
        el_idx = np.where(el)[0]
        eff = np.empty(N_NULL)
        for i in range(N_NULL):
            drop = rng.choice(el_idx, n_rem, replace=False)
            eff[i] = -base[drop].sum() / npop
        # kind-stratified: the same number of MR and CONT removals as the rule made
        rng2 = np.random.default_rng(SEED)
        strata = [(np.where(el & (kinds == kd))[0], int((rem & (kinds == kd)).sum())) for kd in (MR, CONT)]
        ok = all(len(ix) >= nr for ix, nr in strata)
        eff2 = np.empty(N_NULL)
        if ok:
            for i in range(N_NULL):
                s = 0.0
                for ix, nr in strata:
                    if nr:
                        s += base[rng2.choice(ix, nr, replace=False)].sum()
                eff2[i] = -s / npop
        out[split] = {"n_removed": n_rem, "n_eligible": n_el, "actual_effect": actual, "percentile": float((eff < actual).mean() * 100),
                      "null_mean": float(eff.mean()), "null_p95": float(np.quantile(eff, 0.95)),
                      "percentile_kind_stratified": float((eff2 < actual).mean() * 100) if ok else float("nan"), "draws": N_NULL}
    return out


def vetoed_vs_rest(T: pd.DataFrame, R: pd.DataFrame, pop: pd.Series) -> dict:
    """Descriptives of the vetoed nights against the rest (ex post outcomes, reported, never a rule input)."""
    out = {}
    for split in SPLITS:
        m = pop & split_mask(T.index, split) & (T["splice"] == 0)
        vet = m & R["reason"].str.startswith("veto", na=False)
        rest = m & ~vet
        out[split] = {}
        for lab, mm in (("vetoed", vet), ("rest", rest)):
            s = T.loc[mm]
            tr = s[s["traded_open"] == 1]
            out[split][lab] = {"n": int(mm.sum()), "avg_net": float(s["pnl_net_open"].mean()) if len(s) else float("nan"),
                               "win": float((s["pnl_net_open"] > 0).mean()) if len(s) else float("nan"),
                               "stopped_rate": float((tr["outcome_open"] == "stop").mean()) if len(tr) else float("nan"),
                               "target_rate": float((tr["outcome_open"] == "target").mean()) if len(tr) else float("nan"),
                               "scratch_rate": float((tr["outcome_open"] == "scratch").mean()) if len(tr) else float("nan"),
                               "untraded": int((s["traded_open"] == 0).sum()),
                               "by_kind": {kd: {"n": int((s["call"] == kd).sum()), "avg_net": float(s.loc[s["call"] == kd, "pnl_net_open"].mean()) if (s["call"] == kd).any() else float("nan"),
                                                "stopped_rate": float((tr.loc[tr["call"] == kd, "outcome_open"] == "stop").mean()) if (tr["call"] == kd).any() else float("nan")}
                                           for kd in (MR, CONT)}}
    return out


def later_stop_by_bucket(T: pd.DataFrame, pop: pd.Series) -> dict:
    """Descriptive bridge check (ex post outcomes): among nights still open at the close of bar k (baseline chosen trade,
    18:00 fill), the share later stopped / later at target by the detector's adverse-probability bucket at that close."""
    out = {}
    for k in D3_KS:
        m = pop & (T["splice"] == 0) & (T["traded_open"] == 1) & T[f"pA_adv_k{k}"].notna() & (T["resolved_k_open"].isna() | (T["resolved_k_open"] > k))
        s = T.loc[m]
        p = s[f"pA_adv_k{k}"]
        out[f"k{k}"] = {}
        for lab, mm in (("p>=0.90", p >= 0.90), ("0.50<p<0.90", (p > 0.50) & (p < 0.90)), ("p<=0.50", p <= 0.50)):
            ss = s[mm]
            out[f"k{k}"][lab] = {"n": int(len(ss)), "later_stop": float((ss["outcome_open"] == "stop").mean()) if len(ss) else float("nan"),
                                 "later_target": float((ss["outcome_open"] == "target").mean()) if len(ss) else float("nan"),
                                 "avg_net": float(ss["pnl_net_open"].mean()) if len(ss) else float("nan"),
                                 "adverse_at_close_n": int((ss[f"pnl_mtm_k{k}_open"] < 0).sum())}
    return out


# --------------------------------------------------------------------------------------------------
def run_symbol(sym: str) -> tuple[dict, pd.DataFrame]:
    t0 = time.time()
    pv = PV[sym]
    T, cands, nights = load_symbol(sym)
    checks = self_check(sym, T, cands, nights)
    T = derive(T)
    cands_by_date = {d: g for d, g in cands.groupby("date")}
    isA = T["grade"] == "A"
    graded = T["grade"].isin(GRADES)
    kind_mask = {CONT: T["call"] == CONT, MR: T["call"] == MR, "ALL": pd.Series(True, index=T.index)}

    # D3 placebo: shuffle the (k1, k2) adverse probabilities across the graded nights that have them (default_rng(0))
    det_nights = T.index[T["det_A_avail"] == 1]
    perm = np.random.default_rng(SEED).permutation(len(det_nights))
    shuffled = T[[f"pA_adv_k{k}" for k in D3_KS]].copy()
    shuffled.loc[det_nights, :] = T.loc[det_nights[perm], [f"pA_adv_k{k}" for k in D3_KS]].values

    configs = {
        "D1": dict(kind="ALL", veto=("dir", D1_BREAK, D1_HOLD, "cal")),
        "D1_MR": dict(kind=MR, veto=("dir", D1_BREAK, D1_HOLD, "cal")),
        "D1_CONT": dict(kind=CONT, veto=("dir", D1_BREAK, D1_HOLD, "cal")),
        "D1_placebo": dict(kind="ALL", veto=("other", D1_BREAK, D1_HOLD, "cal")),
        "D2_demote": dict(kind="ALL", veto=("dir", D1_BREAK, D1_HOLD, "cal"), demote=True),
        "D2_switch": dict(kind="ALL", veto=("dir", D1_BREAK, D1_HOLD, "cal"), switch="veto"),
        "D2_switch_keep": dict(kind="ALL", veto=("dir", D1_BREAK, D1_HOLD, "cal"), switch="keep"),
        "D3": dict(kind="ALL", ckpt=dict(ks=D3_KS, adv_frac=0.0, p_col="pA_adv", p_exit_max=D3_P_EXIT, p_hold_min=D3_P_HOLD)),
        "D3_price": dict(kind="ALL", ckpt=dict(ks=D3_KS, adv_frac=D3_PRICE_FRAC, p_col=None)),
        "D3_placebo": dict(kind="ALL", ckpt=dict(ks=D3_KS, adv_frac=0.0, p_col="pA_adv", p_exit_max=D3_P_EXIT, p_hold_min=D3_P_HOLD, shuffled=True)),
        "D3_hold": dict(kind="ALL", ckpt=dict(ks=D3_KS, adv_frac=D3_PRICE_FRAC, p_col=None, hold_col="pA_adv", p_hold_min=D3_P_HOLD)),
        "D3_k1": dict(kind="ALL", ckpt=dict(ks=(1,), adv_frac=0.0, p_col="pA_adv", p_exit_max=D3_P_EXIT, p_hold_min=D3_P_HOLD)),
        "D3_k2": dict(kind="ALL", ckpt=dict(ks=(2,), adv_frac=0.0, p_col="pA_adv", p_exit_max=D3_P_EXIT, p_hold_min=D3_P_HOLD)),
        "D4": dict(kind="ALL", eur=dict(k=D4_K, p_col="pA_ovn_adv", thr=D4_P_HOLD)),
        "D4_k3": dict(kind="ALL", eur=dict(k=D4_K_TABLE, p_col="pA_ovn_adv", thr=D4_P_HOLD)),
        "D4_placebo": dict(kind="ALL", eur=dict(k=D4_K, p_col="pA_ovn_fav", thr=D4_P_HOLD)),
        "D4_uncond": dict(kind="ALL", eur_uncond=True),
        "D5": dict(kind=MR, swap=("tight->wide", D5_LO, D5_HI)),
        "D5_rev": dict(kind=MR, swap=("wide->tight", D5_LO)),
    }
    GRADE_AWARE = {"D2_demote", "D2_switch", "D2_switch_keep"}
    results, R_all = {}, {}
    nights_out = T[["split", "splice", "grade", "call", "variant", "best", "side", "confidence", "stop_dist", "target_dist", "sunday_open",
                    "traded_open", "outcome_open", "resolved_k_open", "pnl_net_open", "pnl_net_open_hicost", "eur_outcome_open", "eur_pnl_open",
                    "rth_dir_up", "pB_dir_cal", "pB_other_cal", "pB_dir_raw", "pA_adv_k1", "pA_adv_k2", "pA_fav_k1", "pA_fav_k2",
                    "pA_ovn_adv_k3", f"pA_ovn_adv_k{D4_K}", f"pA_ovn_fav_k{D4_K}", "det_B_avail", "det_A_avail", "det_ovn7_avail"]].copy()
    nights_out.insert(0, "sym", sym)
    nights_out.rename(columns={"pnl_net_open": "base_pnl_net", "pnl_net_open_hicost": "base_pnl_net_hicost"}, inplace=True)
    nights_out["D3_placebo_shuffled_k1"], nights_out["D3_placebo_shuffled_k2"] = shuffled["pA_adv_k1"], shuffled["pA_adv_k2"]
    for rid, cfg in configs.items():
        R = apply_rule(T, nights, cands_by_date, rid, cfg, shuffled)
        R_all[rid] = R
        ga = rid in GRADE_AWARE
        popA = (isA | (R["hyp_grade"] == "A")) if ga else isA
        res = {"rule": REGISTRY[rid][0], "kind": REGISTRY[rid][1], "parameters": REGISTRY[rid][2], "decision_time": REGISTRY[rid][3],
               "predicted_sign": REGISTRY[rid][4], "pre_registered": REGISTRY[rid][5],
               "A": evaluate(T, R, popA & kind_mask[cfg["kind"]], pv, grade_aware=ga),
               "A_MR": evaluate(T, R, popA & kind_mask[MR], pv, grade_aware=ga),
               "A_CONT": evaluate(T, R, popA & kind_mask[CONT], pv, grade_aware=ga),
               "graded": evaluate(T, R, graded & kind_mask[cfg["kind"]], pv, grade_aware=False)}
        results[rid] = res
        nights_out[f"pnl_{rid}"] = R["pnl_net"]
        nights_out[f"pnl_hicost_{rid}"] = R["pnl_net_hi"]
        nights_out[f"reason_{rid}"] = R["reason"]
        nights_out[f"grade_{rid}"] = R["hyp_grade"]
        nights_out[f"affected_{rid}"] = R["affected"]

    # ---- random-filter nulls for the skip rules (A population and all graded) ----
    for rid in SKIP_RULES:
        R = R_all[rid]
        kd = configs[rid]["kind"]
        removed = R["reason"].str.startswith(REMOVED_PREFIXES, na=False)
        elig = T["det_B_avail"] == 1
        results[rid]["random_filter_null"] = {"A": random_filter_null(T, R if rid != "D2_demote" else R_all["D1"], isA & kind_mask[kd], elig, removed),
                                              "graded": random_filter_null(T, R, graded & kind_mask[kd], elig, removed)}
        for split in SPLITS:
            results[rid][f"random_filter_percentile_{split}"] = results[rid]["random_filter_null"]["A"][split]["percentile"]
        results[rid]["vetoed_vs_rest"] = {"A": vetoed_vs_rest(T, R, isA & kind_mask[kd]), "graded": vetoed_vs_rest(T, R, graded & kind_mask[kd])}
    # D2_demote on the A series equals D1 by construction; its B series before/after
    bser = {}
    for split in SPLITS:
        m = split_mask(T.index, split) & (T["splice"] == 0)
        b0 = T.loc[m & (T["grade"] == "B"), "pnl_net_open"]
        b1 = T.loc[m & (R_all["D2_demote"]["hyp_grade"] == "B"), "pnl_net_open"]
        bser[split] = {"B_n_before": int(len(b0)), "B_avg_before": float(b0.mean()) if len(b0) else float("nan"), "B_n_after": int(len(b1)),
                       "B_avg_after": float(b1.mean()) if len(b1) else float("nan"), "demoted_n": int((R_all["D2_demote"].loc[m, "reason"] == "demoted_A_to_B").sum())}
    results["D2_demote"]["B_series"] = bser
    results["D2_demote"]["A_series_identical_to_D1"] = True
    # D1 on the A series uses the demotion-free veto: A-series effect of D2_demote == D1 (assert)
    for split in SPLITS:
        assert abs(results["D2_demote"]["A"][split]["effect"] - results["D1"]["A"][split]["effect"]) < 1e-9

    # ---- D1 exploratory thresholds and the raw column: DISCOVERY ONLY ----
    expl = {}
    for lab, cfg in (("0.80/0.05 cal", dict(kind="ALL", veto=("dir", D1_BREAK_X, D1_HOLD_X, "cal"))),
                     ("0.70/0.10 raw", dict(kind="ALL", veto=("dir", D1_BREAK, D1_HOLD, "raw"))),
                     ("0.80/0.05 raw", dict(kind="ALL", veto=("dir", D1_BREAK_X, D1_HOLD_X, "raw")))):
        Rx = apply_rule(T, nights, cands_by_date, "D1_x", cfg)
        m = isA & split_mask(T.index, "discovery") & (T["splice"] == 0)
        p = paired(T.loc[m, "pnl_net_open"], Rx.loc[m, "pnl_net"], "discovery", pv)
        mg = graded & split_mask(T.index, "discovery") & (T["splice"] == 0)
        pg = paired(T.loc[mg, "pnl_net_open"], Rx.loc[mg, "pnl_net"], "discovery", pv)
        expl[lab] = {"A_discovery": {"n": p["n"], "n_affected": p["n_affected"], "effect": p["effect"], "effect_ci90": p["effect_ci90"], "hyp_avg": p["hyp"]["avg"], "hyp_win": p["hyp"]["win"]},
                     "graded_discovery": {"n": pg["n"], "n_affected": pg["n_affected"], "effect": pg["effect"], "effect_ci90": pg["effect_ci90"]},
                     "pre_registered": False, "note": "exploratory; the vault is scored only at 0.70 / 0.10 on the calibrated column"}
    results["D1"]["exploratory_discovery_only"] = expl

    # ---- D2 switch descriptives ----
    for rid in ("D2_switch", "D2_switch_keep"):
        R = R_all[rid]
        sw = {}
        for split in SPLITS:
            m = split_mask(T.index, split) & (T["splice"] == 0) & graded
            rs = R.loc[m, "reason"].str.split("|").str[0].value_counts()
            swm = m & R["reason"].str.startswith("switched_to", na=False)
            sw[split] = {"reasons": {str(k): int(v) for k, v in rs.items() if not k.startswith(("target", "stop", "scratch", "open_past"))},
                         "switched_n": int(swm.sum()), "switched_hyp_grades": {str(k): int(v) for k, v in R.loc[swm, "hyp_grade"].value_counts().items()},
                         "switched_from_A_n": int((swm & isA).sum()),
                         "switched_base_avg": float(T.loc[swm, "pnl_net_open"].mean()) if swm.sum() else float("nan"),
                         "switched_hyp_avg": float(R.loc[swm, "pnl_net"].mean()) if swm.sum() else float("nan"),
                         "switched_hyp_win": float((R.loc[swm, "pnl_net"] > 0).mean()) if swm.sum() else float("nan")}
        results[rid]["switch_details"] = sw

    # ---- D3 descriptives: the bridge's later-stop rates by bucket (ex post, reported only) and the exits each variant made ----
    results["D3"]["later_stop_by_detector_bucket"] = {"A": later_stop_by_bucket(T, isA), "graded": later_stop_by_bucket(T, graded)}
    for rid in ("D3", "D3_price", "D3_placebo", "D3_hold", "D3_k1", "D3_k2"):
        R = R_all[rid]
        ex = {}
        for split in SPLITS:
            m = isA & split_mask(T.index, split) & (T["splice"] == 0)
            exits = m & R["reason"].str.startswith("checkpoint", na=False)
            ex[split] = {"exits_n": int(exits.sum()), "exits_by_k": {str(k): int(v) for k, v in R.loc[exits, "reason"].value_counts().items()},
                         "exited_base_avg": float(T.loc[exits, "pnl_net_open"].mean()) if exits.sum() else float("nan"),
                         "exited_hyp_avg": float(R.loc[exits, "pnl_net"].mean()) if exits.sum() else float("nan"),
                         "exited_base_outcomes": {str(k): int(v) for k, v in T.loc[exits, "outcome_open"].value_counts().items()},
                         "detector_available_A_n": int((m & (T["det_A_avail"] == 1)).sum())}
        results[rid]["exit_details"] = ex
    # placebo share of the effect
    for rid, pid in PLACEBO_OF.items():
        for split in SPLITS:
            e, ep = results[rid]["A"][split]["effect"], results[pid]["A"][split]["effect"]
            results[rid][f"placebo_share_of_effect_{split}"] = float(ep / e) if abs(e) > EPS else float("nan")

    # ---- D4 descriptives ----
    for rid in ("D4", "D4_k3", "D4_placebo", "D4_uncond"):
        R = R_all[rid]
        hd = {}
        for split in SPLITS:
            m = isA & split_mask(T.index, split) & (T["splice"] == 0)
            held = m & (R["extended"] == 1)
            open_at_k7 = m & (T["traded_open"] == 1) & (T["resolved_k_open"].isna() | (T["resolved_k_open"] > D4_K)) & (T["n_bars"] > D4_K)
            hd[split] = {"open_at_0200_print_n": int(open_at_k7.sum()), "held_into_europe_n": int(held.sum()),
                         "held_outcomes": {str(k): int(v) for k, v in R.loc[held, "reason"].value_counts().items()},
                         "held_base_avg": float(T.loc[held, "pnl_net_open"].mean()) if held.sum() else float("nan"),
                         "held_hyp_avg": float(R.loc[held, "pnl_net"].mean()) if held.sum() else float("nan"),
                         "flag_available_among_open_n": int((open_at_k7 & (T["det_ovn7_avail"] == 1)).sum())}
        results[rid]["hold_details"] = hd
    # the k=7 (and k=8, context only) overnight-adverse flag among the A positions still open at the 02:00 print, and an
    # exploratory threshold ladder, DISCOVERY ONLY (the vault is scored only at the pre-registered 0.90)
    open_k7 = isA & (T["splice"] == 0) & (T["traded_open"] == 1) & (T["resolved_k_open"].isna() | (T["resolved_k_open"] > D4_K)) & (T["n_bars"] > D4_K)
    fd = {}
    for k in (D4_K, 8, D4_K_TABLE):
        p = T.loc[open_k7, f"pA_ovn_adv_k{k}"].dropna()
        fd[f"k{k}"] = {"n": int(len(p)), "max": float(p.max()) if len(p) else float("nan"), "median": float(p.median()) if len(p) else float("nan"),
                       "n_ge_0.90": int((p >= 0.90).sum()), "n_ge_0.80": int((p >= 0.80).sum()), "n_ge_0.70": int((p >= 0.70).sum()), "n_ge_0.50": int((p >= 0.50).sum())}
    results["D4"]["flag_distribution_open_at_0200_A_full"] = fd
    lad = []
    for thr in (0.80, 0.70, 0.50):
        Rx = apply_rule(T, nights, cands_by_date, "D4_x", dict(kind="ALL", eur=dict(k=D4_K, p_col="pA_ovn_adv", thr=thr)))
        m = isA & split_mask(T.index, "discovery") & (T["splice"] == 0)
        p = paired(T.loc[m, "pnl_net_open"], Rx.loc[m, "pnl_net"], "discovery", pv)
        lad.append({"thr": thr, "n": p["n"], "n_affected": p["n_affected"], "effect": p["effect"], "effect_ci90": p["effect_ci90"], "hyp_avg": p["hyp"]["avg"],
                    "held_n": int((m & (Rx["extended"] == 1)).sum()), "pre_registered": False})
    results["D4"]["exploratory_threshold_ladder_discovery_only"] = lad

    # ---- D5 descriptives: wide vs tight by pB_dir bucket on A fades (candidate table, ex post P&L; exploratory) ----
    d5 = {}
    for split in SPLITS:
        m = isA & kind_mask[MR] & split_mask(T.index, split) & (T["splice"] == 0) & T["pB_dir_cal"].notna()
        rows = []
        for d in T.index[m]:
            r = T.loc[d]
            cn = cands_by_date[d]
            pair = {}
            for v in ("tight", "wide"):
                alt = cn[(cn["kind"] == MR) & (cn["variant"] == v) & (cn["target_key"] == r["best"]) & (cn["side"] == r["side"])]
                pair[v] = float(alt["pnl_net_open"].iloc[0]) if len(alt) == 1 else np.nan
            rows.append({"p": float(r["pB_dir_cal"]), "chosen": r["variant"], **pair})
        df = pd.DataFrame(rows)
        d5[split] = {}
        if len(df):
            for lab, mm in (("p<0.30", df["p"] < D5_LO), ("0.30<=p<=0.70", (df["p"] >= D5_LO) & (df["p"] <= D5_HI)), ("p>0.70", df["p"] > D5_HI)):
                s = df[mm]
                d5[split][lab] = {"n": int(len(s)), "chosen_tight": int((s["chosen"] == "tight").sum()), "tight_avg": float(s["tight"].mean()) if len(s) else float("nan"),
                                  "wide_avg": float(s["wide"].mean()) if len(s) else float("nan"), "wide_minus_tight": float((s["wide"] - s["tight"]).mean()) if len(s) else float("nan")}
    results["D5"]["wide_vs_tight_by_bucket_A_fades"] = d5

    # ---- verdicts (A population of the touched kind) ----
    for rid in configs:
        rf = results[rid].get("random_filter_percentile_vault")
        rf_g = results[rid]["random_filter_null"]["graded"]["vault"]["percentile"] if rid in SKIP_RULES else None
        results[rid]["verdict"] = verdict_of(results[rid]["A"], REGISTRY[rid][4], rf)
        results[rid]["verdict_MR"] = verdict_of(results[rid]["A_MR"], REGISTRY[rid][4], rf)
        results[rid]["verdict_CONT"] = verdict_of(results[rid]["A_CONT"], REGISTRY[rid][4], rf)
        results[rid]["verdict_graded"] = verdict_of(results[rid]["graded"], REGISTRY[rid][4], rf_g)
        results[rid]["random_filter_percentile_graded_vault"] = rf_g

    # ---- COMBINED ----
    def combined_cfg(ids: list) -> dict:
        cfg = dict(kind="ALL")
        for rid in ids:
            c = configs[rid]
            for key in ("veto", "switch", "ckpt", "eur", "eur_uncond", "swap"):
                if key in c:
                    cfg[key] = c[key]
        return cfg

    def run_combined(ids: list, label: str) -> dict:
        if not ids:
            return {"rules_applied": [], "note": "no rule qualified"}
        cfg = combined_cfg(ids)
        Rc = apply_rule(T, nights, cands_by_date, label, cfg, shuffled)
        ga = any(i in GRADE_AWARE for i in ids)
        popA = (isA | (Rc["hyp_grade"] == "A")) if ga else isA
        out = {"rules_applied": ids, "config": {k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg.items()},
               "A": evaluate(T, Rc, popA, pv, grade_aware=ga), "A_MR": evaluate(T, Rc, popA & kind_mask[MR], pv, grade_aware=ga),
               "A_CONT": evaluate(T, Rc, popA & kind_mask[CONT], pv, grade_aware=ga), "graded": evaluate(T, Rc, graded, pv)}
        if "veto" in cfg:
            removed = Rc["reason"].str.startswith(REMOVED_PREFIXES, na=False)
            out["random_filter_null_veto_component"] = random_filter_null(T, Rc, isA, T["det_B_avail"] == 1, removed)
        nights_out[f"pnl_{label}"], nights_out[f"pnl_hicost_{label}"] = Rc["pnl_net"], Rc["pnl_net_hi"]
        nights_out[f"reason_{label}"], nights_out[f"affected_{label}"] = Rc["reason"], Rc["affected"]
        R_all[label] = Rc
        return out

    chosen = [rid for rid in PREREG_IDS + EXPLORATORY_IDS if results[rid]["verdict"] in ("supported on vault", "discovery only")]
    # a rule family keeps one member: D2 variants supersede D1 only if D1 is not itself chosen; D3 variants likewise
    combined = {"supported_or_discovery": run_combined(chosen, "COMBINED"),
                "D1_plus_D3_named": run_combined(["D1", "D3"], "COMBINED_D1_D3")}

    # ---- all-night effect (every OOS night, ungraded/untraded = 0, splice excluded), full window ----
    all_idx = T.index[(T["splice"] == 0) & split_mask(T.index, "full")]
    for rid in list(configs) + ["COMBINED", "COMBINED_D1_D3"]:
        if rid not in R_all:
            continue
        R = R_all[rid]
        if rid in GRADE_AWARE or (rid == "COMBINED" and any(i in GRADE_AWARE for i in chosen)):
            dA = (a_series(T, R) - a_series(T, None)).reindex(all_idx).fillna(0.0)
        else:
            dA = (R["pnl_net"] - T["pnl_net_open"]).where(isA, 0.0).fillna(0.0).reindex(all_idx)
        tgt = results[rid] if rid in results else combined["supported_or_discovery" if rid == "COMBINED" else "D1_plus_D3_named"]
        tgt["all_night_effect_full_pts"] = float(dA.mean())
        tgt["all_night_effect_full_ci90"] = block_boot_ci(dA)
        tgt["all_night_n"] = int(len(dA))

    summary = {"self_checks": checks, "hypotheses": results, "combined": combined, "runtime_s": time.time() - t0,
               "A_counts": {s: int((isA & split_mask(T.index, s) & (T["splice"] == 0)).sum()) for s in SPLITS},
               "A_by_kind": {s: {k: int((isA & kind_mask[k] & split_mask(T.index, s) & (T["splice"] == 0)).sum()) for k in (CONT, MR)} for s in SPLITS},
               "detector_coverage": {"A_without_detector_B": [str(d.date()) for d in T.index[isA & (T["det_B_avail"] == 0) & (T["splice"] == 0)]],
                                     "A_without_detector_A_k1k2": [str(d.date()) for d in T.index[isA & (T["det_A_avail"] == 0) & (T["splice"] == 0)]],
                                     "A_without_ovn_k7": [str(d.date()) for d in T.index[isA & (T["det_ovn7_avail"] == 0) & (T["splice"] == 0)]],
                                     "graded_without_detector_B": int((graded & (T["det_B_avail"] == 0) & (T["splice"] == 0)).sum())},
               "pB_dir_distribution_A": {kd: {"n": int((isA & kind_mask[kd] & (T["splice"] == 0) & T["pB_dir_cal"].notna()).sum()),
                                              ">=0.70": int((isA & kind_mask[kd] & (T["splice"] == 0) & (T["pB_dir_cal"] >= D1_BREAK)).sum()),
                                              "<=0.10": int((isA & kind_mask[kd] & (T["splice"] == 0) & (T["pB_dir_cal"] <= D1_HOLD)).sum()),
                                              "median": float(T.loc[isA & kind_mask[kd] & (T["splice"] == 0), "pB_dir_cal"].median())} for kd in (MR, CONT)}}
    return summary, nights_out


# --------------------------------------------------------------------------------------------------
def fmt_ci(ci):
    return f"[{ci[0]:+.1f},{ci[1]:+.1f}]"


def print_table(sym: str, S: dict):
    print(f"\n{'=' * 140}\n{sym}: detector bridge on the honest Grade-A nights (baseline pnl_net_open; splice nights excluded)")
    print(f"A nights: {S['A_counts']}  by kind: {S['A_by_kind']}  detector coverage: {S['detector_coverage']}")
    print(f"pB_dir on A nights: {S['pB_dir_distribution_A']}")
    hdr = f"{'id':15s} {'pop':6s} {'split':9s} {'n':>3s} {'aff':>3s} {'A b/a':>7s} {'base_avg':>8s} {'hyp_avg':>8s} {'effect':>7s} {'ci90':>15s} {'win b/h':>11s} {'worst b/h':>15s} {'pts/sig b/h':>11s} {'usd/yr':>7s} {'eff_hi':>7s}"
    print(hdr)
    for rid, res in S["hypotheses"].items():
        for popk in ("A",):
            for split in ("discovery", "vault", "full"):
                r = res[popk][split]
                print(f"{rid:15s} {popk:6s} {split:9s} {r['n']:3d} {r['n_affected']:3d} {r['A_n_before']:3d}/{r['A_n_after']:3d} {r['base']['avg']:8.1f} {r['hyp']['avg']:8.1f} {r['effect']:+7.1f} "
                      f"{fmt_ci(r['effect_ci90']):>15s} {r['base']['win']:5.2f}/{r['hyp']['win']:5.2f} {r['base']['worst']:7.1f}/{r['hyp']['worst']:7.1f} "
                      f"{r['base']['pts_per_sigma']:5.2f}/{r['hyp']['pts_per_sigma']:5.2f} {r['usd_per_contract_per_year']:7.0f} {r['effect_hicost']:+7.1f}")
        rf = res.get("random_filter_percentile_vault")
        extra = f"  random-filter pct (disc/vault/full): {res.get('random_filter_percentile_discovery', float('nan')):.0f}/{rf:.0f}/{res.get('random_filter_percentile_full', float('nan')):.0f}" if rf is not None else ""
        pl = f"  placebo share of effect (full): {res['placebo_share_of_effect_full']:.2f}" if "placebo_share_of_effect_full" in res else ""
        print(f"{'':15s} verdict: {res['verdict']} (MR: {res['verdict_MR']}; CONT: {res['verdict_CONT']}; graded: {res['verdict_graded']}){extra}{pl}")
    print("\nby kind (A nights) and all graded, full window:")
    for rid, res in S["hypotheses"].items():
        parts = []
        for popk in ("A_MR", "A_CONT", "graded"):
            r = res[popk]["full"]
            parts.append(f"{popk:6s} n={r['n']:3d} aff={r['n_affected']:3d} {r['base']['avg']:+6.1f}->{r['hyp']['avg']:+6.1f} eff {r['effect']:+6.1f} {fmt_ci(r['effect_ci90'])}")
        print(f"  {rid:15s} " + " | ".join(parts))
    d1 = S["hypotheses"]["D1"]
    print("\nD1 vetoed vs rest (A, full):", json.dumps({k: {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != 'by_kind'} for k, v in d1["vetoed_vs_rest"]["A"]["full"].items()}))
    print("D1 vetoed vs rest (graded, full):", json.dumps({k: {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != 'by_kind'} for k, v in d1["vetoed_vs_rest"]["graded"]["full"].items()}))
    print("D1 exploratory (discovery only):", json.dumps({k: {"A": {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v["A_discovery"].items()}} for k, v in d1["exploratory_discovery_only"].items()}))
    print("D1 random-filter null, graded population:", {s: (round(d1["random_filter_null"]["graded"][s]["percentile"], 0), round(d1["random_filter_null"]["graded"][s]["percentile_kind_stratified"], 0),
                                                        d1["random_filter_null"]["graded"][s]["n_removed"]) for s in SPLITS},
          " A population kind-stratified:", {s: round(d1["random_filter_null"]["A"][s]["percentile_kind_stratified"], 0) for s in SPLITS})
    print("D1 graded splits:", {s: (d1["graded"][s]["n"], d1["graded"][s]["n_affected"], round(d1["graded"][s]["effect"], 2), [round(x, 1) for x in d1["graded"][s]["effect_ci90"]]) for s in SPLITS})
    print("D2_switch graded splits:", {s: (S["hypotheses"]["D2_switch"]["graded"][s]["n"], S["hypotheses"]["D2_switch"]["graded"][s]["n_affected"], round(S["hypotheses"]["D2_switch"]["graded"][s]["effect"], 2),
                                           [round(x, 1) for x in S["hypotheses"]["D2_switch"]["graded"][s]["effect_ci90"]]) for s in SPLITS})
    print("D4 flag distribution (open at 02:00, A, full):", json.dumps(S["hypotheses"]["D4"]["flag_distribution_open_at_0200_A_full"]))
    print("D4 exploratory ladder (discovery only):", json.dumps([{k: (round(v, 2) if isinstance(v, float) else v) for k, v in g.items()} for g in S["hypotheses"]["D4"]["exploratory_threshold_ladder_discovery_only"]]))
    print("D2 switch details (full):", json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in S["hypotheses"]["D2_switch"]["switch_details"]["full"].items()}))
    print("D3 later-stop by bucket (A):", json.dumps(S["hypotheses"]["D3"]["later_stop_by_detector_bucket"]["A"]))
    for rid in ("D3", "D3_price", "D3_placebo", "D3_hold"):
        print(f"{rid} exits (full):", json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in S["hypotheses"][rid]["exit_details"]["full"].items()}))
    for rid in ("D4", "D4_k3", "D4_placebo", "D4_uncond"):
        print(f"{rid} holds (full):", json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in S["hypotheses"][rid]["hold_details"]["full"].items()}))
    print("D5 wide vs tight by bucket (A fades, full):", json.dumps(S["hypotheses"]["D5"]["wide_vs_tight_by_bucket_A_fades"]["full"]))
    for lab, c in S["combined"].items():
        print(f"\nCOMBINED [{lab}] rules {c.get('rules_applied')}:")
        if "A" not in c:
            continue
        for split in ("discovery", "vault", "full"):
            r = c["A"][split]
            print(f"{'COMBINED':15s} {'A':6s} {split:9s} {r['n']:3d} {r['n_affected']:3d} {r['A_n_before']:3d}/{r['A_n_after']:3d} {r['base']['avg']:8.1f} {r['hyp']['avg']:8.1f} {r['effect']:+7.1f} "
                  f"{fmt_ci(r['effect_ci90']):>15s} {r['base']['win']:5.2f}/{r['hyp']['win']:5.2f} {r['base']['worst']:7.1f}/{r['hyp']['worst']:7.1f} "
                  f"{r['base']['pts_per_sigma']:5.2f}/{r['hyp']['pts_per_sigma']:5.2f} {r['usd_per_contract_per_year']:7.0f} {r['effect_hicost']:+7.1f}")
        g = c["graded"]["full"]
        print(f"{'':15s} graded full: n={g['n']} aff={g['n_affected']} {g['base']['avg']:+.1f}->{g['hyp']['avg']:+.1f} eff {g['effect']:+.1f} {fmt_ci(g['effect_ci90'])}; all-night full effect {c['all_night_effect_full_pts']:+.2f} {fmt_ci(c['all_night_effect_full_ci90'])}")


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
    t0 = time.time()
    out, nights_frames = {"group": GROUP, "generated_from": "research/lab/grade_a/h_detector_bridge.py",
                          "baseline": "pnl_net_open (honest grade, 18:00-open fill, own-pair resolution, base costs); sensitivity pnl_net_open_hicost",
                          "splits": SPLITS, "bootstrap": {"blocks": "ISO week", "draws": N_BOOT, "rng": "numpy default_rng(0)", "ci": "90%"},
                          "random_filter_null": {"draws": N_NULL, "rng": "numpy default_rng(0)", "applies_to": SKIP_RULES,
                                                 "eligible": "graded nights of the population with a Detector B value; unstratified (primary) and kind-stratified"},
                          "parameters": {"D1_BREAK": D1_BREAK, "D1_HOLD": D1_HOLD, "D1_exploratory": [D1_BREAK_X, D1_HOLD_X], "D3_P_EXIT": D3_P_EXIT, "D3_P_HOLD": D3_P_HOLD,
                                         "D3_PRICE_FRAC": D3_PRICE_FRAC, "D3_KS": list(D3_KS), "D4_P_HOLD": D4_P_HOLD, "D4_K": D4_K, "D4_K_TABLE": D4_K_TABLE, "D5_band": [D5_LO, D5_HI]},
                          "detector_columns": {
                              "pB_dir": "17:xx ET: pB_high_above_cal on up-day nights (MR SHORT / CONT LONG), pB_low_below_cal on down-day nights (MR LONG / CONT SHORT) = P(Asia breaks the RTH-direction level)",
                              "pB_other": "17:xx ET: the other side's level (placebo)",
                              "pA_adv_k": "close of bar k: pA_high_k for a SHORT, pA_low_k for a LONG = P(the trade's adverse Asia extreme is already in); D3 reads k=1 (20:00 ET print) and k=2 (21:00 ET print)",
                              "pA_ovn_adv_k7": "close of bar k=7 (02:00 ET print): p_ovn_high_done / p_ovn_low_done at k=7 from oos_intrasession (not in the trades table); D4",
                              "pA_ovn_adv_k3": "the trades table's last value (22:00 print), used stale at the 02:00 decision in D4_k3",
                              "pA_ovn_fav_k7": "the favourable overnight extreme flag (D4 placebo)"},
                          "conventions": {"k": "positional Asia bar index (0 = first bar, normally 18:00); 'close of bar k' = the (k+19):00 ET print on a normal night",
                                          "adverse extreme": "Asia HIGH for a SHORT, Asia LOW for a LONG (fade: the RTH-direction extreme the stop sits beyond; continuation: the opposite one)",
                                          "verdict": "computed on the A nights of the touched kind (A-either for the grade-changing D2 variants); MR / CONT / graded verdicts alongside",
                                          "all_night_effect": "rule on A nights only, spread over every OOS night of the window (ungraded = 0)",
                                          "nights without detector values": "left unchanged by every detector rule (holiday eves, feed-gap nights, splices); listed per symbol",
                                          "D3 comparability": "every D3 variant, including the price-only comparator, fires only on nights with a k=1 and k=2 detector value"},
                          "registry": {k: {"rule": v[0], "kind": v[1], "parameters": v[2], "decision_time": v[3], "predicted_sign": v[4], "pre_registered": v[5]} for k, v in REGISTRY.items()},
                          "pre_registered": PREREG_IDS, "partly_pre_registered": PARTLY_PREREG_IDS, "exploratory": EXPLORATORY_IDS, "placebo_of": PLACEBO_OF,
                          "effect_statistics": {"effect": "paired per-night mean of (hypothesis - baseline) over the fixed population (vetoed nights booked 0): the group's headline",
                                                "effect_A_avg_composition": "difference of Grade-A averages (hypothesis A nights vs baseline A nights), the statistic the "
                                                                            "geometry and vetoes groups call 'effect on A avg'; added so that cross-group tables use one statistic"}}, []
    for sym in ("NQ", "ES"):
        S, N = run_symbol(sym)
        out[sym] = S
        nights_frames.append(N)
        print_table(sym, S)
    rep = {}
    for rid in out["NQ"]["hypotheses"]:
        a, b = out["NQ"]["hypotheses"][rid]["A"], out["ES"]["hypotheses"][rid]["A"]
        rep[rid] = {s: {"NQ": a[s]["effect"], "ES": b[s]["effect"], "same_sign": bool(np.sign(a[s]["effect"]) == np.sign(b[s]["effect"]) and a[s]["effect"] != 0),
                        "ES_n_affected": b[s]["n_affected"], "ES_ci90": b[s]["effect_ci90"]} for s in SPLITS}
    out["es_replication_same_sign"] = rep
    out["runtime_s"] = time.time() - t0
    with open(os.path.join(OUT, f"h_{GROUP}_results.json"), "w") as f:
        json.dump(_jsonable(out), f, indent=1)
    N = pd.concat(nights_frames).reset_index()
    N.to_csv(os.path.join(OUT, f"h_{GROUP}_nights.csv"), index=False, float_format="%.6f")
    print("\nES same-sign replication (A population; full / vault):")
    for rid, r in rep.items():
        print(f"  {rid:15s} full NQ {r['full']['NQ']:+6.1f} ES {r['full']['ES']:+6.1f} same={r['full']['same_sign']}   vault NQ {r['vault']['NQ']:+6.1f} ES {r['vault']['ES']:+6.1f} same={r['vault']['same_sign']} (ES aff {r['vault']['ES_n_affected']})")
    print(f"\nwrote h_{GROUP}_results.json and h_{GROUP}_nights.csv in {OUT} ({out['runtime_s']:.0f} s)")


if __name__ == "__main__":
    main()
