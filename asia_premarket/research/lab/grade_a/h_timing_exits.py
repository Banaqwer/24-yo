#!/usr/bin/env python3
"""
h_timing_exits.py -- entry timing and exits on the honest Grade-A nights (group: timing_exits).

Run from the project root:
    OMP_NUM_THREADS=1 python research/lab/grade_a/h_timing_exits.py            # NQ (primary) and ES (replication arm)

Inputs (read-only): research/lab/grade_a/trades_honest_{SYM}.csv, candidates_{SYM}.csv (self-check only), data/{SYM}_1h.csv.
Outputs: research/lab/grade_a/h_timing_exits_results.json, h_timing_exits_nights.csv (per-night baseline vs hypothesis P&L
for every rule) and a printed table.  Deterministic (numpy default_rng(0) for the weekly-block bootstrap and for the
random-filter null); runtime ~1 minute.

Baseline = pnl_net_open (honest grade, 18:00-open fill, own-pair stop-priority resolution with gap fills, base costs).
Every rule re-walks the raw hourly bars of the chosen candidate with the same walker as the baseline (asserted to
reproduce the builder's resolution columns for every candidate of every night when no rule is active), so an exit at a
bar close, a moved stop or a later fill is raced against the same bars with the same conventions.

Hypotheses (parameters pre-registered in research/LAB_DESIGN.md section 8 and research/lab/forensics_v0.md section 5):
  H4      continuation checkpoint at the Tokyo cash open: CONTINUATION calls only; at the close of bar k = tokyo_open_bar
          (1 in EST, 2 in EDT) exit at that bar's close if the position is adverse by more than 0.25 x stop_dist.
          Placebo (named): the same rule on MEAN REVERSION (expected to hurt).
  TS20c   time-stop: flat at the 20:00 ET print (close of the 19:00 bar, k=1) if not resolved, CONTINUATION only
          (pre-registered as 'continuation only at 20:00', forensics H-time).  TS20m (mean reversion) is its placebo.
          TS22c/m, TS00c/m (22:00 and 00:00 prints: closes of the 21:00 and 23:00 bars) are exploratory.
  H12     two-stage execution, MEAN REVERSION only: decide at 17:xx, fill at the 20:00 open (Open of the hour-20 bar)
          only if the 18:00-20:00 move against the call is <= 0.25 x rng_q50_pts (walk-forward q50, known at 17:xx);
          nights whose target or stop was touched in the 18:00-19:59 bars are not filled (P&L 0).  Robustness test:
          effect with the nights the baseline resolved in the 18:00 bar excluded.  Placebo (LAB_DESIGN 2.6 trio, no
          named one): the sign-flipped rule (cancel when the 18-20 move is WITH the call by more than 0.25 x q50).
  SCR00   exploratory scratch handling: a position still open at the 00:00 print (close of the 23:00 bar, k=5) with
          adverse P&L is closed there instead of held to 02:59.  Plus the negative-result check that holding a scratch
          through Europe (levels active, eur_pnl_open) is worse than the 02:59 scratch.
  BE22    exploratory MFE-based partial (one rule): at the 22:00 print (close of the 21:00 bar, k=3), if the position
          is still open and its MFE so far >= 0.5 x target_dist, the stop moves to the entry for the rest of the night.
  COMBINED the rules with verdict 'supported on vault' or 'discovery only' applied jointly on the A nights.

Time convention: 'the HH:00 close' is the HH:00 ET print = the close of the hourly bar labelled HH-1 (the task's own
'20:00 open = the k=2 bar Open' is the same print); H4 uses the close of bar k = tokyo_open_bar exactly as registered.
Bars are looked up by their ET hour, not by position, so holiday-eve (6-bar) and the 2025-07-25 (20:00 start) nights
are handled; a rule whose bar is absent leaves the night unchanged.

Knowability: rule inputs are target/stop/stop_dist/target_dist/rng_q50_pts/tokyo_open_bar (17:xx), the bar closes and
highs/lows up to the decision bar, the 20:00 open and the 18:00-19:59 bars (H12).  Ex post inputs seen and NOT used as
rule inputs: outcome_open / resolved_k_open (used only to define the pre-registered H12 robustness subset and for
descriptives), 'the trade later scratches' (the BE22 wording; the rule is applied to every open position that
qualifies at 22:00 and the later-scratch subset is reported descriptively only), eur_outcome_open / eur_pnl_open (the
negative-result counterfactual, not a rule), catalogue tags, in_catalogue, kospi_next, n225_next (never touched).
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

GROUP = "timing_exits"
OUT = HERE
DATA = os.path.join(ROOT, "data")
SPLITS = {"discovery": ("2025-04-01", "2026-05-31"), "vault": ("2026-06-01", "2026-11-06"),
          "full": ("2025-04-01", "2026-11-06")}
PV = {"NQ": 20.0, "ES": 50.0}
N_BOOT, SEED, N_NULL = 2000, 0, 2000
GRADES = ("A", "B", "C")
N_K = 9
EPS = 1e-9
MR, CONT = "MEAN REVERSION", "CONTINUATION"

# pre-registered single parameters
H4_FRAC = 0.25        # x stop_dist adverse at the Tokyo-open bar close
H12_FRAC = 0.25       # x rng_q50_pts adverse 18:00-20:00 move cancels the 20:00 fill
BE_FRAC = 0.5         # x target_dist MFE by the 22:00 print arms the breakeven stop (exploratory)
TS_PRINT_TO_BAR_HOUR = {20: 19, 22: 21, 0: 23}   # the HH:00 print is the close of the bar labelled HH-1

# hypothesis registry: id -> (rule text, kind it touches, parameter text, decision time, predicted sign, pre-registered?)
REGISTRY = {
    "H4": ("continuation checkpoint at the Tokyo cash open: exit at the close of bar k=tokyo_open_bar if adverse by > 0.25 x stop_dist",
           CONT, "0.25 x stop_dist (single, pre-registered)", "close of bar k=tokyo_open_bar (20:00 ET print in EST, 21:00 ET print in EDT)", +1, True),
    "H4_placebo_MR": ("the H4 checkpoint applied to MEAN REVERSION (named placebo; expected to hurt)", MR,
                      "0.25 x stop_dist", "close of bar k=tokyo_open_bar", -1, True),
    "TS20c": ("time-stop: flat at the 20:00 ET print (close of the 19:00 bar) if unresolved, CONTINUATION only", CONT,
              "20:00 print (pre-registered, forensics H-time)", "20:00 ET print (close of bar k=1)", +1, True),
    "TS20m": ("time-stop at the 20:00 print on MEAN REVERSION (placebo of TS20c; forensics expects harm)", MR,
              "20:00 print", "20:00 ET print (close of bar k=1)", -1, True),
    "TS20c_b": ("sensitivity to the convention: flat at the close of the bar LABELLED 20:00 (the 21:00 ET print, k=2), CONTINUATION (exploratory)", CONT,
                "close of the 20:00 bar (exploratory)", "21:00 ET print (close of bar k=2)", +1, False),
    "TS20m_b": ("sensitivity to the convention: flat at the close of the bar labelled 20:00, MEAN REVERSION (exploratory)", MR,
                "close of the 20:00 bar (exploratory)", "21:00 ET print (close of bar k=2)", -1, False),
    "TS22c": ("time-stop at the 22:00 print (close of the 21:00 bar), CONTINUATION (exploratory)", CONT, "22:00 print (exploratory)", "22:00 ET print (close of bar k=3)", +1, False),
    "TS22m": ("time-stop at the 22:00 print, MEAN REVERSION (exploratory)", MR, "22:00 print (exploratory)", "22:00 ET print (close of bar k=3)", +1, False),
    "TS00c": ("time-stop at the 00:00 print (close of the 23:00 bar), CONTINUATION (exploratory)", CONT, "00:00 print (exploratory)", "00:00 ET print (close of bar k=5)", +1, False),
    "TS00m": ("time-stop at the 00:00 print, MEAN REVERSION (exploratory)", MR, "00:00 print (exploratory)", "00:00 ET print (close of bar k=5)", +1, False),
    "H12": ("two-stage MEAN REVERSION execution: fill at the 20:00 open only if the 18:00-20:00 move against the call is <= 0.25 x rng_q50_pts; "
            "pre-touched target/stop or unfillable at 20:00 = no fill", MR, "0.25 x rng_q50_pts (single, pre-registered)",
            "20:00 ET open (Open of the hour-20 bar; uses bars k<=1 and the 20:00 print)", +1, True),
    "H12_placebo_flip": ("H12 sign-flipped: cancel when the 18:00-20:00 move is WITH the call by more than 0.25 x rng_q50_pts", MR,
                         "0.25 x rng_q50_pts", "20:00 ET open", -1, True),
    "H12_uncond_e20": ("reference: every MEAN REVERSION call filled at the 20:00 open (no cancel; pre-touched = no fill)", MR,
                       "none", "20:00 ET open", 0, False),
    "SCR00": ("scratch handling (exploratory): a position open at the 00:00 print with adverse P&L is closed there", "ALL",
              "adverse at the 00:00 print (exploratory, no parameter)", "00:00 ET print (close of bar k=5)", +1, False),
    "BE22": ("MFE partial (exploratory): at the 22:00 print, if open and MFE >= 0.5 x target_dist, stop moves to the entry", "ALL",
             "0.5 x target_dist (exploratory)", "22:00 ET print (close of bar k=3)", +1, False),
}
PREREG_IDS = ["H4", "TS20c", "H12"]
EXPLORATORY_IDS = ["TS20c_b", "TS20m_b", "TS22c", "TS22m", "TS00c", "TS00m", "SCR00", "BE22"]
GRID_DISCOVERY_ONLY = {"H4": [0.0, 0.10, 0.25, 0.50], "H12": [0.10, 0.25, 0.50]}   # exploratory; the vault is scored only at 0.25
PLACEBO_OF = {"H4": "H4_placebo_MR", "TS20c": "TS20m", "H12": "H12_placebo_flip"}


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


def walk_rules(O, H, L, C, side: str, entry: float, target: float, stop: float, start: int, rules: dict | None = None) -> dict | None:
    """The builder's walk (stop priority inside a bar, gap through the stop fills at the bar Open, targets at level,
    scratch at the last close) plus close-of-bar rules:
      ckpt_k / ckpt_adverse : at the close of bar ckpt_k, exit at that close if the MTM P&L < -ckpt_adverse
      ts_k                  : at the close of bar ts_k, exit at that close (time-stop)
      scr_k                 : at the close of bar scr_k, exit at that close if the MTM P&L < 0
      be_k / be_mfe         : at the close of bar be_k, if the MFE so far >= be_mfe, the stop becomes the entry
    Rules fire in that order at the same bar close.  With rules={} this is exactly the builder's walk."""
    rules = rules or {}
    sgn = 1.0 if side == "LONG" else -1.0
    n = len(O)
    if start >= n:
        return None
    mtm = np.full(N_K, np.nan)
    mfe, mae = 0.0, 0.0
    cur_stop, be_armed = float(stop), False
    ck_k, ck_adv = rules.get("ckpt_k"), float(rules.get("ckpt_adverse", 0.0))
    ts_k, scr_k = rules.get("ts_k"), rules.get("scr_k")
    be_k, be_mfe = rules.get("be_k"), float(rules.get("be_mfe", np.inf))
    for i in range(start, n):
        fav = sgn * ((H[i] if sgn > 0 else L[i]) - entry)
        adv = sgn * ((L[i] if sgn > 0 else H[i]) - entry)
        stop_hit = (L[i] <= cur_stop) if sgn > 0 else (H[i] >= cur_stop)
        tgt_hit = (H[i] >= target) if sgn > 0 else (L[i] <= target)
        if stop_hit:
            gap = (O[i] <= cur_stop) if sgn > 0 else (O[i] >= cur_stop)
            ex = float(O[i]) if gap else float(cur_stop)
            pnl = sgn * (ex - entry)
            return dict(outcome="be_stop" if be_armed else "stop", resolved_k=i, exit=ex, pnl=pnl, mfe=mfe, mae=min(mae, pnl),
                        gapfill=int(gap), samebar=int(tgt_hit), mtm=mtm, be_armed=int(be_armed))
        if tgt_hit:
            pnl = sgn * (float(target) - entry)
            return dict(outcome="target", resolved_k=i, exit=float(target), pnl=pnl, mfe=max(mfe, pnl), mae=min(mae, adv),
                        gapfill=0, samebar=0, mtm=mtm, be_armed=int(be_armed))
        mfe, mae = max(mfe, fav), min(mae, adv)
        m = sgn * (float(C[i]) - entry)
        if i < N_K:
            mtm[i] = m
        if ck_k is not None and i == ck_k and m < -ck_adv:
            return dict(outcome="checkpoint", resolved_k=i, exit=float(C[i]), pnl=m, mfe=mfe, mae=mae, gapfill=0, samebar=0, mtm=mtm, be_armed=int(be_armed))
        if ts_k is not None and i == ts_k:
            return dict(outcome="time_stop", resolved_k=i, exit=float(C[i]), pnl=m, mfe=mfe, mae=mae, gapfill=0, samebar=0, mtm=mtm, be_armed=int(be_armed))
        if scr_k is not None and i == scr_k and m < 0:
            return dict(outcome="adverse_exit", resolved_k=i, exit=float(C[i]), pnl=m, mfe=mfe, mae=mae, gapfill=0, samebar=0, mtm=mtm, be_armed=int(be_armed))
        if be_k is not None and i == be_k and mfe >= be_mfe:
            cur_stop, be_armed = float(entry), True
    ex = float(C[n - 1])
    return dict(outcome="scratch", resolved_k=np.nan, exit=ex, pnl=sgn * (ex - entry), mfe=mfe, mae=mae, gapfill=0, samebar=0, mtm=mtm, be_armed=int(be_armed))


class Night:
    """The raw Asia bars of one night with hour -> positional index lookup."""

    def __init__(self, bars: pd.DataFrame, eur: pd.DataFrame | None):
        self.O, self.H, self.L, self.C = (bars[c].values.astype(float) for c in ("Open", "High", "Low", "Close"))
        self.hours = bars["hour"].values.astype(int)
        self.n = len(bars)
        self.eur = eur

    def k_of_hour(self, hour: int):
        w = np.where(self.hours == hour)[0]
        return int(w[0]) if len(w) else None

    def pre_touched(self, side: str, target: float, stop: float, j: int) -> tuple[bool, bool]:
        if j <= 0:
            return False, False
        t = bool(((self.H[:j] >= target) if side == "LONG" else (self.L[:j] <= target)).any())
        s = bool(((self.L[:j] <= stop) if side == "LONG" else (self.H[:j] >= stop)).any())
        return t, s


def resolve(night: Night, side: str, target: float, stop: float, fill: str, rules: dict | None = None,
            cancel: bool = False) -> dict:
    """Resolve the chosen candidate for one night.  fill='open' (Open of the first bar; unfillable when the open is already
    beyond the target or the stop) or 'e20' (Open of the hour-20 bar; unfillable when that open is beyond a level or a level
    was touched in the earlier bars).  cancel=True means the two-stage rule cancelled the fill."""
    out = {"traded": 0, "pnl": 0.0, "outcome": None, "resolved_k": np.nan, "exit": np.nan, "mfe": np.nan, "mae": np.nan,
           "reason": "", "entry": np.nan, "start": np.nan, "mtm": np.full(N_K, np.nan)}
    if fill == "open":
        j = 0
        pre_t = pre_s = False
    else:
        j = night.k_of_hour(20)
        if j is None:
            out["reason"] = "no_20:00_bar"
            return out
        pre_t, pre_s = night.pre_touched(side, target, stop, j)
    entry = float(night.O[j])
    out["entry"], out["start"] = entry, j
    if _beyond(side, entry, target, "target"):
        out["reason"] = "open_past_target"
        return out
    if _beyond(side, entry, stop, "stop"):
        out["reason"] = "open_past_stop"
        return out
    if pre_t or pre_s:
        out["reason"] = "pre_touched_target" if pre_t else "pre_touched_stop"
        return out
    if cancel:
        out["reason"] = "cancelled"
        return out
    r = walk_rules(night.O, night.H, night.L, night.C, side, entry, target, stop, j, rules)
    out.update(traded=1, pnl=float(r["pnl"]), outcome=r["outcome"], resolved_k=r["resolved_k"], exit=r["exit"], mfe=r["mfe"],
               mae=r["mae"], reason=r["outcome"] + ("+be_armed" if r["be_armed"] and r["outcome"] != "be_stop" else ""), mtm=r["mtm"])
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


def paired(base: pd.Series, hyp: pd.Series, split: str, pv: float, base_traded: pd.Series | None = None,
           hyp_traded: pd.Series | None = None, base_hi: pd.Series | None = None, hyp_hi: pd.Series | None = None) -> dict:
    """Paired per-night stats of hyp vs base on one population (already restricted to the split)."""
    d = (hyp - base).astype(float)
    out = {"n": int(len(d)), "n_affected": int((d.abs() > EPS).sum()), "effect": float(d.mean()) if len(d) else float("nan"),
           "effect_ci90": block_boot_ci(d), "effect_total": float(d.sum()),
           "usd_per_contract_per_year": float(d.sum() * pv * 12 / months_in(split)),
           "base": series_stats(base, base_traded), "hyp": series_stats(hyp, hyp_traded)}
    if base_hi is not None and hyp_hi is not None:
        dh = (hyp_hi - base_hi).astype(float)
        out["effect_hicost"] = float(dh.mean()) if len(dh) else float("nan")
        out["hyp_avg_hicost"] = float(hyp_hi.mean()) if len(hyp_hi) else float("nan")
    return out


def verdict_of(res: dict, pred_sign: int, rf_pct: float | None) -> str:
    """The task's verdict rules.  harmful > not testable (< 8 affected vault nights) > supported on vault > discovery only
    > no effect.  The random-filter condition applies only to rules that remove or skip nights (rf_pct is None otherwise)."""
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
    rf_ok = True if rf_pct is None else (rf_pct >= 90)
    if sign_ok and (excl(lo_v, hi_v) or (excl(lo_f, hi_f) and lo_f <= v["effect"] <= hi_f and rf_ok)):
        return "supported on vault"
    d_ok = ((pred_sign >= 0 and dsc["effect"] > 0) or (pred_sign < 0 and dsc["effect"] < 0)) and excl(lo_d, hi_d)
    if d_ok:
        return "discovery only"
    return "no effect"


# --------------------------------------------------------------------------------------------------
# the symbol run
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
    return T, cands, nights


def self_check(sym: str, T: pd.DataFrame, cands: pd.DataFrame, nights: dict) -> dict:
    """The walker with no rule reproduces the builder's resolution of EVERY candidate (18:00-open and 20:00-open fills),
    and the night tables agree with the bars (first open, bar count, tokyo_open_bar, move_18_20_in_dir)."""
    n_open = n_e20 = 0
    for _, c in cands.iterrows():
        nt = nights[c["date"]]
        for fill, sfx in (("open", "open"), ("e20", "e20")):
            r = resolve(nt, c["side"], float(c["target"]), float(c["stop"]), fill)
            tr = int(c[f"traded_{sfx}"])
            if fill == "e20" and tr == 1 and r["reason"].startswith("pre_touched"):
                # the builder's traded_e20 ignores pre-touches (H12 adds them); compare the walk itself
                j = nt.k_of_hour(20)
                w = walk_rules(nt.O, nt.H, nt.L, nt.C, c["side"], float(nt.O[j]), float(c["target"]), float(c["stop"]), j)
                assert abs(w["pnl"] - float(c["pnl_e20"])) < 1e-9 and w["outcome"] == c["outcome_e20"], (sym, c["date"], c["cand_id"])
                pt, ps = nt.pre_touched(c["side"], float(c["target"]), float(c["stop"]), j)
                assert int(pt) == int(c["pre_touched_target_e20"]) and int(ps) == int(c["pre_touched_stop_e20"])
                n_e20 += 1
                continue
            assert r["traded"] == tr, (sym, c["date"], c["cand_id"], fill, r["reason"], tr)
            if tr == 1:
                assert abs(r["pnl"] - float(c[f"pnl_{sfx}"])) < 1e-9, (sym, c["date"], c["cand_id"], fill, r["pnl"], c[f"pnl_{sfx}"])
                assert r["outcome"] == c[f"outcome_{sfx}"], (sym, c["date"], c["cand_id"], fill)
                rk = c[f"resolved_k_{sfx}"]
                assert (pd.isna(rk) and pd.isna(r["resolved_k"])) or int(rk) == int(r["resolved_k"])
                assert abs(r["mfe"] - float(c[f"mfe_{sfx}"])) < 1e-9 and abs(r["mae"] - float(c[f"mae_{sfx}"])) < 1e-9
                for k in range(N_K):
                    a, b = r["mtm"][k], float(c[f"pnl_mtm_k{k}_{sfx}"])
                    assert (np.isnan(a) and np.isnan(b)) or abs(a - b) < 1e-9, (sym, c["date"], c["cand_id"], fill, k, a, b)
                if fill == "open":
                    n_open += 1
                else:
                    n_e20 += 1
    n_tok = 0
    for d, r in T.iterrows():
        nt = nights[d]
        assert nt.n == int(r["n_bars"]) and nt.hours[0] == int(r["k0_hour"])
        want = 20 if int(r["is_dst"]) else 19
        k = nt.k_of_hour(want)
        assert (k is None and pd.isna(r["tokyo_open_bar"])) or k == int(r["tokyo_open_bar"]), (sym, d)
        if pd.notna(r["move_18_20_in_dir"]):
            sgn = 1.0 if r["side"] == "LONG" else -1.0
            assert abs(sgn * (nt.C[1] - nt.O[0]) - float(r["move_18_20_in_dir"])) < 1e-9
            n_tok += 1
        if pd.notna(r["entry_open"]):
            assert abs(nt.O[0] - float(r["entry_open"])) < 1e-9
    return {"candidates_open_fill_reproduced": n_open, "candidates_e20_fill_reproduced": n_e20, "nights_checked": int(len(T)),
            "move_18_20_reproduced": n_tok}


def apply_rule(T: pd.DataFrame, nights: dict, rid: str, cfg: dict) -> pd.DataFrame:
    """Per-night hypothesis P&L for one rule on the graded nights.  cfg: kind ('ALL' or a call kind), fill ('open'/'e20'),
    and the close-of-bar rule parameters (by bar hour or 'tokyo'); 'cancel' = ('adverse'|'favourable', frac) for H12.
    Returns a frame indexed like T with pnl_net, pnl_net_hi, traded, reason, affected (vs the baseline)."""
    rows = {}
    for d, r in T.iterrows():
        g = r["grade"]
        if g not in GRADES:
            rows[d] = dict(pnl_net=np.nan, pnl_net_hi=np.nan, traded=0, reason="not graded", applies=0)
            continue
        base_net, base_hi = float(r["pnl_net_open"]), float(r["pnl_net_open_hicost"])
        applies = cfg["kind"] == "ALL" or r["call"] == cfg["kind"]
        if not applies:
            rows[d] = dict(pnl_net=base_net, pnl_net_hi=base_hi, traded=int(r["traded_open"]), reason="untouched kind", applies=0)
            continue
        nt = nights[d]
        rules = {}
        if "ckpt" in cfg:                       # ('tokyo', frac)
            k = int(r["tokyo_open_bar"]) if pd.notna(r["tokyo_open_bar"]) else None
            if k is not None:
                rules["ckpt_k"], rules["ckpt_adverse"] = k, cfg["ckpt"] * float(r["stop_dist"])
        if "ts_print" in cfg:
            k = nt.k_of_hour(TS_PRINT_TO_BAR_HOUR[cfg["ts_print"]])
            if k is not None:
                rules["ts_k"] = k
        if "ts_bar" in cfg:                      # the close of the bar labelled ts_bar (convention sensitivity)
            k = nt.k_of_hour(cfg["ts_bar"])
            if k is not None:
                rules["ts_k"] = k
        if "scr_print" in cfg:
            k = nt.k_of_hour(TS_PRINT_TO_BAR_HOUR[cfg["scr_print"]])
            if k is not None:
                rules["scr_k"] = k
        if "be" in cfg:                          # (print hour, frac)
            k = nt.k_of_hour(TS_PRINT_TO_BAR_HOUR[cfg["be"][0]])
            if k is not None:
                rules["be_k"], rules["be_mfe"] = k, cfg["be"][1] * float(r["target_dist"])
        cancel = False
        if cfg.get("cancel") is not None:
            mode, frac = cfg["cancel"]
            mv = float(r["move_18_20_in_dir"]) if pd.notna(r["move_18_20_in_dir"]) else np.nan
            thr = frac * float(r["rng_q50_pts"])
            if np.isnan(mv) or int(r["k0_hour"]) != 18 or int(r["bars_contiguous"]) != 1:
                cancel = True                     # the 18:00-19:59 bars are not both present: no two-stage decision
            elif mode == "adverse":
                cancel = mv < -thr
            else:
                cancel = mv > thr
        res = resolve(nt, r["side"], float(r["target"]), float(r["stop"]), cfg["fill"], rules, cancel)
        cost_b, cost_h = float(r["cost_base"]), float(r["cost_hi"])
        pnl_net = res["pnl"] - cost_b if res["traded"] else 0.0
        pnl_hi = res["pnl"] - cost_h if res["traded"] else 0.0
        rows[d] = dict(pnl_net=pnl_net, pnl_net_hi=pnl_hi, traded=res["traded"], reason=res["reason"], applies=1,
                       outcome=res["outcome"], resolved_k=res["resolved_k"], hyp_entry=res["entry"])
    R = pd.DataFrame.from_dict(rows, orient="index")
    R.index.name = "date"
    R["affected"] = ((R["pnl_net"] - T["pnl_net_open"]).abs() > EPS).astype(int)
    return R


def evaluate(T: pd.DataFrame, R: pd.DataFrame, pop: pd.Series, pv: float) -> dict:
    """Paired evaluation of a rule on a population mask (boolean Series over T.index), per split."""
    out = {}
    for split in SPLITS:
        m = pop & split_mask(T.index, split) & (T["splice"] == 0)
        base, hyp = T.loc[m, "pnl_net_open"], R.loc[m, "pnl_net"]
        out[split] = paired(base, hyp, split, pv, T.loc[m, "traded_open"], R.loc[m, "traded"],
                            T.loc[m, "pnl_net_open_hicost"], R.loc[m, "pnl_net_hi"])
        out[split]["A_n"] = int((T.loc[m, "grade"] == "A").sum())
        # hypothesis-side outcome mix on the touched, traded nights
        mix = R.loc[m & (R["applies"] == 1) & (R["traded"] == 1), "reason"].value_counts()
        out[split]["hyp_exit_mix"] = {str(k): int(v) for k, v in mix.items()}
        bmix = T.loc[m & (T["traded_open"] == 1), "outcome_open"].value_counts()
        out[split]["base_outcome_mix"] = {str(k): int(v) for k, v in bmix.items()}
    return out


def random_filter_null(T: pd.DataFrame, R: pd.DataFrame, pop: pd.Series, e20_net: pd.Series, eligible: pd.Series) -> dict:
    """For the H12 cancel rule: the same number of cancellations drawn at random among the nights eligible for the 20:00
    fill (fillable at 20:00, no pre-touch); the retained nights take the 20:00-fill P&L; the effect is measured against
    the baseline on the whole population.  Reports the percentile of the actual effect among 2000 draws (default_rng(0))."""
    out = {}
    for split in SPLITS:
        m = pop & split_mask(T.index, split) & (T["splice"] == 0)
        base = T.loc[m, "pnl_net_open"].values
        hyp = R.loc[m, "pnl_net"].values
        el = eligible[m].values.astype(bool)
        e20 = e20_net[m].values
        n_cancel = int(((R.loc[m, "reason"] == "cancelled")).sum())
        n_el = int(el.sum())
        actual = float((hyp - base).mean())
        if n_el == 0 or n_cancel == 0 or n_cancel > n_el:
            out[split] = {"n_cancelled": n_cancel, "n_eligible": n_el, "actual_effect": actual, "percentile": float("nan"), "draws": 0}
            continue
        rng = np.random.default_rng(SEED)
        el_idx = np.where(el)[0]
        eff = np.empty(N_NULL)
        for i in range(N_NULL):
            h = np.zeros(len(base))
            h[el_idx] = e20[el_idx]
            drop = rng.choice(el_idx, n_cancel, replace=False)
            h[drop] = 0.0
            eff[i] = (h - base).mean()
        out[split] = {"n_cancelled": n_cancel, "n_eligible": n_el, "actual_effect": actual,
                      "percentile": float((eff < actual).mean() * 100), "null_mean": float(eff.mean()),
                      "null_p95": float(np.quantile(eff, 0.95)), "draws": N_NULL}
    return out


def run_symbol(sym: str) -> tuple[dict, pd.DataFrame]:
    t0 = time.time()
    pv = PV[sym]
    T, cands, nights = load_symbol(sym)
    checks = self_check(sym, T, cands, nights)
    isA = T["grade"] == "A"
    graded = T["grade"].isin(GRADES)
    kind_mask = {CONT: T["call"] == CONT, MR: T["call"] == MR, "ALL": pd.Series(True, index=T.index)}

    configs = {
        "H4": dict(kind=CONT, fill="open", ckpt=H4_FRAC),
        "H4_placebo_MR": dict(kind=MR, fill="open", ckpt=H4_FRAC),
        "TS20c": dict(kind=CONT, fill="open", ts_print=20), "TS20m": dict(kind=MR, fill="open", ts_print=20),
        "TS20c_b": dict(kind=CONT, fill="open", ts_bar=20), "TS20m_b": dict(kind=MR, fill="open", ts_bar=20),
        "TS22c": dict(kind=CONT, fill="open", ts_print=22), "TS22m": dict(kind=MR, fill="open", ts_print=22),
        "TS00c": dict(kind=CONT, fill="open", ts_print=0), "TS00m": dict(kind=MR, fill="open", ts_print=0),
        "H12": dict(kind=MR, fill="e20", cancel=("adverse", H12_FRAC)),
        "H12_placebo_flip": dict(kind=MR, fill="e20", cancel=("favourable", H12_FRAC)),
        "H12_uncond_e20": dict(kind=MR, fill="e20", cancel=None),
        "SCR00": dict(kind="ALL", fill="open", scr_print=0),
        "BE22": dict(kind="ALL", fill="open", be=(22, BE_FRAC)),
    }
    results, R_all = {}, {}
    nights_out = T[["split", "splice", "grade", "call", "variant", "side", "confidence", "tokyo_open_bar", "stop_dist", "target_dist",
                    "rng_q50_pts", "move_18_20_in_dir", "traded_open", "outcome_open", "resolved_k_open", "pnl_net_open", "pnl_net_open_hicost",
                    "eur_outcome_open", "eur_pnl_open", "pnl_at_eur_close_open"]].copy()
    nights_out.insert(0, "sym", sym)
    nights_out.rename(columns={"pnl_net_open": "base_pnl_net", "pnl_net_open_hicost": "base_pnl_net_hicost"}, inplace=True)
    for rid, cfg in configs.items():
        R = apply_rule(T, nights, rid, cfg)
        R_all[rid] = R
        pop_touched = isA & kind_mask[cfg["kind"]]
        res = {"rule": REGISTRY[rid][0], "kind": REGISTRY[rid][1], "parameters": REGISTRY[rid][2], "decision_time": REGISTRY[rid][3],
               "predicted_sign": REGISTRY[rid][4], "pre_registered": REGISTRY[rid][5],
               "A_touched": evaluate(T, R, pop_touched, pv),           # the registered population
               "A_all": evaluate(T, R, isA, pv),                       # effect on the whole Grade-A average (dilution included)
               "graded_touched_context": evaluate(T, R, graded & kind_mask[cfg["kind"]], pv)}
        results[rid] = res
        nights_out[f"pnl_{rid}"] = R["pnl_net"]
        nights_out[f"reason_{rid}"] = R["reason"]
        nights_out[f"affected_{rid}"] = R["affected"]

    # ---- H12 specifics: fills dropped, per-fill avg, random-filter null, robustness without the 18:00-bar resolutions ----
    R12 = R_all["H12"]
    popMR = isA & kind_mask[MR]
    e20_net = pd.Series(np.where(T["traded_e20"] == 1, T["pnl_e20"] - T["cost_base"], 0.0), index=T.index)
    eligible = (T["traded_e20"] == 1) & (T["pre_touched_target_e20"] == 0) & (T["pre_touched_stop_e20"] == 0) & (T["k0_hour"] == 18) & (T["bars_contiguous"] == 1)
    h12 = {"random_filter_null": random_filter_null(T, R12, popMR, e20_net, eligible), "fills": {}, "excluding_bar0_resolutions": {},
           "placebo_random_filter_null": random_filter_null(T, R_all["H12_placebo_flip"], popMR, e20_net, eligible)}
    for split in SPLITS:
        m = popMR & split_mask(T.index, split) & (T["splice"] == 0)
        rs = R12.loc[m, "reason"].value_counts()
        n = int(m.sum())
        filled = R12.loc[m, "traded"] == 1
        h12["fills"][split] = {"n_A_MR": n, "base_traded": int(T.loc[m, "traded_open"].sum()), "h12_filled": int(filled.sum()),
                               "fills_dropped_share": float(1 - filled.sum() / n) if n else float("nan"),
                               "not_filled_reasons": {str(k): int(v) for k, v in rs.items() if k in ("cancelled", "pre_touched_target", "pre_touched_stop", "open_past_target", "open_past_stop", "no_20:00_bar")},
                               "per_fill_avg": float(R12.loc[m & filled, "pnl_net"].mean()) if filled.sum() else float("nan"),
                               "per_fill_win": float((R12.loc[m & filled, "pnl_net"] > 0).mean()) if filled.sum() else float("nan"),
                               "base_per_traded_avg": float(T.loc[m & (T["traded_open"] == 1), "pnl_net_open"].mean()),
                               "base_per_traded_win": float((T.loc[m & (T["traded_open"] == 1), "pnl_net_open"] > 0).mean()),
                               "all_night_avg_base": float(T.loc[m, "pnl_net_open"].mean()) if n else float("nan"),
                               "all_night_avg_h12": float(R12.loc[m, "pnl_net"].mean()) if n else float("nan")}
        m2 = m & ~(T["resolved_k_open"] == 0)
        h12["excluding_bar0_resolutions"][split] = paired(T.loc[m2, "pnl_net_open"], R12.loc[m2, "pnl_net"], split, pv)
        h12["excluding_bar0_resolutions"][split]["n_excluded"] = int((m & (T["resolved_k_open"] == 0)).sum())
    results["H12"]["details"] = h12

    # ---- scratch handling details: the negative-result check (hold a scratch through Europe) ----
    scr = {}
    for split in SPLITS:
        for label, pop in (("A", isA), ("graded", graded)):
            m = pop & split_mask(T.index, split) & (T["splice"] == 0) & (T["outcome_open"] == "scratch") & (T["traded_open"] == 1)
            sc = T.loc[m]
            d_eur = (sc["eur_pnl_open"] - sc["pnl_open"]).dropna()
            d_cl = (sc["pnl_at_eur_close_open"] - sc["pnl_open"]).dropna()
            scr[f"{label}_{split}"] = {"n_scratch": int(m.sum()), "scratch_avg_0259": float(sc["pnl_open"].mean()) if len(sc) else float("nan"),
                                       "hold_eur_levels_active_avg": float(sc["eur_pnl_open"].mean()) if len(sc) else float("nan"),
                                       "hold_eur_delta": float(d_eur.mean()) if len(d_eur) else float("nan"), "hold_eur_delta_ci90": block_boot_ci(d_eur),
                                       "hold_to_eur_close_delta": float(d_cl.mean()) if len(d_cl) else float("nan"), "hold_to_eur_close_delta_ci90": block_boot_ci(d_cl),
                                       "eur_outcome_mix": {str(k): int(v) for k, v in sc["eur_outcome_open"].value_counts(dropna=False).items()},
                                       "adverse_at_0000_print_n": int((R_all["SCR00"].loc[m, "reason"] == "adverse_exit").sum())}
    results["SCR00"]["details"] = {"hold_through_europe_negative_check": scr}

    # ---- BE22 descriptive: the ex post 'later scratches' subset (reported, never a rule input) ----
    be = {}
    Rbe = R_all["BE22"]
    for split in SPLITS:
        m = isA & split_mask(T.index, split) & (T["splice"] == 0) & (T["traded_open"] == 1)
        armed = Rbe.loc[m, "reason"].str.contains("be_", na=False)
        later_scratch = m & (T["outcome_open"] == "scratch")
        ls = later_scratch & armed.reindex(T.index).fillna(False)
        be[split] = {"A_traded": int(m.sum()), "armed_n": int(armed.sum()),
                     "armed_exit_mix": {str(k): int(v) for k, v in Rbe.loc[m & armed.reindex(T.index).fillna(False), "reason"].value_counts().items()},
                     "later_scratch_armed_n": int(ls.sum()),
                     "later_scratch_armed_base_avg": float(T.loc[ls, "pnl_net_open"].mean()) if ls.sum() else float("nan"),
                     "later_scratch_armed_hyp_avg": float(Rbe.loc[ls, "pnl_net"].mean()) if ls.sum() else float("nan"),
                     "armed_then_target_base_vs_hyp": [float(T.loc[m & armed.reindex(T.index).fillna(False) & (T["outcome_open"] == "target"), "pnl_net_open"].sum()),
                                                       float(Rbe.loc[m & armed.reindex(T.index).fillna(False) & (T["outcome_open"] == "target"), "pnl_net"].sum())]}
    results["BE22"]["details"] = {"ex_post_descriptives": be}

    # ---- exploratory parameter grids, DISCOVERY ONLY (the vault is scored only at the pre-registered 0.25) ----
    for rid, grid in GRID_DISCOVERY_ONLY.items():
        rows = []
        for frac in grid:
            cfg = dict(kind=CONT, fill="open", ckpt=frac) if rid == "H4" else dict(kind=MR, fill="e20", cancel=("adverse", frac))
            Rg = apply_rule(T, nights, f"{rid}_grid", cfg)
            m = isA & kind_mask[cfg["kind"]] & split_mask(T.index, "discovery") & (T["splice"] == 0)
            p = paired(T.loc[m, "pnl_net_open"], Rg.loc[m, "pnl_net"], "discovery", pv)
            rows.append({"frac": frac, "n": p["n"], "n_affected": p["n_affected"], "effect": p["effect"], "effect_ci90": p["effect_ci90"],
                         "hyp_avg": p["hyp"]["avg"], "hyp_win": p["hyp"]["win"], "pre_registered": frac == (H4_FRAC if rid == "H4" else H12_FRAC)})
        results[rid]["exploratory_grid_discovery_only"] = rows

    # ---- verdicts (on the registered population) ----
    for rid in configs:
        rf = None
        if rid in ("H12", "H12_placebo_flip"):
            rf = results[rid]["details"]["random_filter_null"]["vault"]["percentile"] if rid == "H12" else h12["placebo_random_filter_null"]["vault"]["percentile"]
            results[rid]["random_filter_percentile_vault"] = rf
            results[rid]["random_filter_percentile_full"] = (h12["random_filter_null"] if rid == "H12" else h12["placebo_random_filter_null"])["full"]["percentile"]
            results[rid]["random_filter_percentile_discovery"] = (h12["random_filter_null"] if rid == "H12" else h12["placebo_random_filter_null"])["discovery"]["percentile"]
        results[rid]["verdict"] = verdict_of(results[rid]["A_touched"], REGISTRY[rid][4], rf)
        results[rid]["verdict_on_all_A_series"] = verdict_of(results[rid]["A_all"], REGISTRY[rid][4], rf)

    # ---- COMBINED: the supported-or-discovery rules jointly on the A nights ----
    chosen = [rid for rid in PREREG_IDS + EXPLORATORY_IDS if results[rid]["verdict"] in ("supported on vault", "discovery only")]
    comb_cfg = {CONT: dict(kind=CONT, fill="open"), MR: dict(kind=MR, fill="open")}
    for rid in chosen:
        cfg = configs[rid]
        kinds = [CONT, MR] if cfg["kind"] == "ALL" else [cfg["kind"]]
        for kd in kinds:
            for key in ("ckpt", "ts_print", "scr_print", "be"):
                if key in cfg:
                    if key == "ts_print" and "ts_print" in comb_cfg[kd]:
                        comb_cfg[kd][key] = min(cfg[key], comb_cfg[kd][key], key=lambda p: (p - 18) % 24)   # the earliest time-stop wins
                    else:
                        comb_cfg[kd][key] = cfg[key]
            if cfg["fill"] == "e20":
                comb_cfg[kd]["fill"] = "e20"
                comb_cfg[kd]["cancel"] = cfg["cancel"]
    Rc = pd.concat([apply_rule(T, nights, "COMBINED", comb_cfg[CONT]).loc[kind_mask[CONT]],
                    apply_rule(T, nights, "COMBINED", comb_cfg[MR]).loc[kind_mask[MR]]]).reindex(T.index)
    nt_mask = ~(kind_mask[CONT] | kind_mask[MR])
    Rc.loc[nt_mask, ["pnl_net", "pnl_net_hi"]] = np.nan
    Rc.loc[nt_mask, "traded"] = 0
    Rc.loc[nt_mask, "applies"] = 0
    Rc["affected"] = ((Rc["pnl_net"] - T["pnl_net_open"]).abs() > EPS).astype(int)
    combined = {"rules_applied": chosen, "config": {k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in comb_cfg.items()},
                "A_all": evaluate(T, Rc, isA, pv), "graded_context": evaluate(T, Rc, graded, pv)}
    if "H12" in chosen:
        combined["random_filter_null_cancel_component"] = random_filter_null(T, Rc, popMR, e20_net, eligible)
    nights_out["pnl_COMBINED"], nights_out["reason_COMBINED"], nights_out["affected_COMBINED"] = Rc["pnl_net"], Rc["reason"], Rc["affected"]

    # all-night effect (every OOS night, ungraded/untraded = 0, splice excluded), full window, for each rule on A nights only
    all_idx = T.index[(T["splice"] == 0) & split_mask(T.index, "full")]
    for rid in list(configs) + ["COMBINED"]:
        R = R_all[rid] if rid != "COMBINED" else Rc
        dA = (R["pnl_net"] - T["pnl_net_open"]).where(isA, 0.0).fillna(0.0).reindex(all_idx)
        tgt = results[rid] if rid != "COMBINED" else combined
        tgt["all_night_effect_full_pts"] = float(dA.mean())
        tgt["all_night_effect_full_ci90"] = block_boot_ci(dA)
        tgt["all_night_n"] = int(len(dA))

    summary = {"self_checks": checks, "hypotheses": results, "combined": combined, "runtime_s": time.time() - t0,
               "A_counts": {s: int((isA & split_mask(T.index, s) & (T["splice"] == 0)).sum()) for s in SPLITS},
               "A_by_kind": {s: {k: int((isA & kind_mask[k] & split_mask(T.index, s) & (T["splice"] == 0)).sum()) for k in (CONT, MR)} for s in SPLITS}}
    return summary, nights_out


# --------------------------------------------------------------------------------------------------
def fmt_ci(ci):
    return f"[{ci[0]:+.1f},{ci[1]:+.1f}]"


def print_table(sym: str, S: dict):
    print(f"\n{'=' * 130}\n{sym}: entry timing and exits on the honest Grade-A nights (baseline pnl_net_open; splice nights excluded)")
    print(f"A nights: {S['A_counts']}  by kind: {S['A_by_kind']}")
    hdr = f"{'id':18s} {'pop':5s} {'split':9s} {'n':>3s} {'aff':>3s} {'base_avg':>8s} {'hyp_avg':>8s} {'effect':>7s} {'ci90':>15s} {'win b/h':>11s} {'worst b/h':>15s} {'pts/sig b/h':>11s} {'usd/yr':>8s}"
    print(hdr)
    for rid, res in S["hypotheses"].items():
        for popk in ("A_touched",):
            for split in ("discovery", "vault", "full"):
                r = res[popk][split]
                print(f"{rid:18s} {popk[:5]:5s} {split:9s} {r['n']:3d} {r['n_affected']:3d} {r['base']['avg']:8.1f} {r['hyp']['avg']:8.1f} {r['effect']:+7.1f} "
                      f"{fmt_ci(r['effect_ci90']):>15s} {r['base']['win']:5.2f}/{r['hyp']['win']:5.2f} {r['base']['worst']:7.1f}/{r['hyp']['worst']:7.1f} "
                      f"{r['base']['pts_per_sigma']:5.2f}/{r['hyp']['pts_per_sigma']:5.2f} {r['usd_per_contract_per_year']:8.0f}")
        rf = res.get("random_filter_percentile_vault")
        extra = f"  random-filter pct (disc/vault/full): {res.get('random_filter_percentile_discovery', float('nan')):.0f}/{rf:.0f}/{res.get('random_filter_percentile_full', float('nan')):.0f}" if rf is not None else ""
        print(f"{'':18s} verdict: {res['verdict']} (on all-A series: {res['verdict_on_all_A_series']}); all-A full effect {res['A_all']['full']['effect']:+.1f} {fmt_ci(res['A_all']['full']['effect_ci90'])}{extra}")
    print("\ncontext: the same rules on ALL graded nights of the touched kind (A/B/C):")
    for rid, res in S["hypotheses"].items():
        parts = []
        for split in ("discovery", "vault", "full"):
            r = res["graded_touched_context"][split]
            parts.append(f"{split[:4]} n={r['n']:3d} aff={r['n_affected']:3d} base {r['base']['avg']:+6.1f} -> {r['hyp']['avg']:+6.1f} eff {r['effect']:+6.1f} {fmt_ci(r['effect_ci90'])}")
        print(f"  {rid:18s} " + " | ".join(parts))
    for rid in GRID_DISCOVERY_ONLY:
        print(f"\nexploratory grid, DISCOVERY ONLY, {rid} (A nights of the touched kind; the vault is scored only at the pre-registered value):")
        for g in S["hypotheses"][rid]["exploratory_grid_discovery_only"]:
            print(f"  frac {g['frac']:.2f}{' *' if g['pre_registered'] else '  '} n={g['n']} affected={g['n_affected']:3d} effect {g['effect']:+6.1f} {fmt_ci(g['effect_ci90'])} hyp avg {g['hyp_avg']:+6.1f} win {g['hyp_win']:.2f}")
    c = S["combined"]
    print(f"\nCOMBINED rules {c['rules_applied']}:")
    for split in ("discovery", "vault", "full"):
        r = c["A_all"][split]
        print(f"{'COMBINED':18s} {'A_all':5s} {split:9s} {r['n']:3d} {r['n_affected']:3d} {r['base']['avg']:8.1f} {r['hyp']['avg']:8.1f} {r['effect']:+7.1f} "
              f"{fmt_ci(r['effect_ci90']):>15s} {r['base']['win']:5.2f}/{r['hyp']['win']:5.2f} {r['base']['worst']:7.1f}/{r['hyp']['worst']:7.1f} "
              f"{r['base']['pts_per_sigma']:5.2f}/{r['hyp']['pts_per_sigma']:5.2f} {r['usd_per_contract_per_year']:8.0f}")
    h = S["hypotheses"]["H12"]["details"]
    print("\nH12 fills:", json.dumps({s: {k: (round(v, 2) if isinstance(v, float) else v) for k, v in h["fills"][s].items()} for s in SPLITS}))
    print("H12 excluding bar-0 resolutions:", {s: (h["excluding_bar0_resolutions"][s]["n"], round(h["excluding_bar0_resolutions"][s]["effect"], 1),
                                                   [round(x, 1) for x in h["excluding_bar0_resolutions"][s]["effect_ci90"]]) for s in SPLITS})
    sc = S["hypotheses"]["SCR00"]["details"]["hold_through_europe_negative_check"]
    print("Hold scratches through Europe (A, full):", {k: (round(v, 1) if isinstance(v, float) else v) for k, v in sc["A_full"].items()})
    print("BE22 descriptives:", json.dumps(S["hypotheses"]["BE22"]["details"]["ex_post_descriptives"]["full"]))


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
    out, nights_frames = {"group": GROUP, "generated_from": "research/lab/grade_a/h_timing_exits.py",
                          "baseline": "pnl_net_open (honest grade, 18:00-open fill, own-pair resolution, base costs); sensitivity pnl_net_open_hicost",
                          "splits": SPLITS, "bootstrap": {"blocks": "ISO week", "draws": N_BOOT, "rng": "numpy default_rng(0)", "ci": "90%"},
                          "random_filter_null": {"draws": N_NULL, "rng": "numpy default_rng(0)", "applies_to": "H12 (the only rule that skips nights)"},
                          "parameters": {"H4_FRAC": H4_FRAC, "H12_FRAC": H12_FRAC, "BE_FRAC": BE_FRAC, "time_stop_prints": TS_PRINT_TO_BAR_HOUR},
                          "conventions": {"HH:00 close": "the HH:00 ET print = close of the hourly bar labelled HH-1 (20:00 -> k=1, 22:00 -> k=3, 00:00 -> k=5 on a normal night)",
                                          "H4 checkpoint": "close of bar k = tokyo_open_bar (1 in EST, 2 in EDT) as registered",
                                          "20:00 open": "Open of the hour-20 bar (k=2 on a normal night)",
                                          "verdict": "computed on the registered population (A nights of the touched kind); the all-A series verdict is reported alongside",
                                          "all_night_effect": "rule on A nights only, spread over every OOS night of the window (ungraded = 0)"},
                          "registry": {k: {"rule": v[0], "kind": v[1], "parameters": v[2], "decision_time": v[3], "predicted_sign": v[4], "pre_registered": v[5]} for k, v in REGISTRY.items()},
                          "pre_registered": PREREG_IDS, "exploratory": EXPLORATORY_IDS, "placebo_of": PLACEBO_OF}, []
    for sym in ("NQ", "ES"):
        S, N = run_symbol(sym)
        out[sym] = S
        nights_frames.append(N)
        print_table(sym, S)
    # ES same-sign replication of the NQ touched-population effects
    rep = {}
    for rid in out["NQ"]["hypotheses"]:
        a, b = out["NQ"]["hypotheses"][rid]["A_touched"], out["ES"]["hypotheses"][rid]["A_touched"]
        rep[rid] = {s: {"NQ": a[s]["effect"], "ES": b[s]["effect"], "same_sign": bool(np.sign(a[s]["effect"]) == np.sign(b[s]["effect"]) and a[s]["effect"] != 0),
                        "ES_n_affected": b[s]["n_affected"]} for s in SPLITS}
    out["es_replication_same_sign"] = rep
    out["runtime_s"] = time.time() - t0
    with open(os.path.join(OUT, f"h_{GROUP}_results.json"), "w") as f:
        json.dump(_jsonable(out), f, indent=1)
    N = pd.concat(nights_frames).reset_index()
    N.to_csv(os.path.join(OUT, f"h_{GROUP}_nights.csv"), index=False, float_format="%.6f")
    print(f"\nES same-sign replication (full / vault):")
    for rid, r in rep.items():
        print(f"  {rid:18s} full NQ {r['full']['NQ']:+6.1f} ES {r['full']['ES']:+6.1f} same={r['full']['same_sign']}   vault NQ {r['vault']['NQ']:+6.1f} ES {r['vault']['ES']:+6.1f} same={r['vault']['same_sign']}")
    print(f"\nwrote h_{GROUP}_results.json and h_{GROUP}_nights.csv in {OUT} ({out['runtime_s']:.0f} s)")


if __name__ == "__main__":
    main()
