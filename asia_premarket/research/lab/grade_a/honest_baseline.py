#!/usr/bin/env python3
"""
honest_baseline.py -- the honest baseline of the Asia-session engine (iteration-0 integrity bundle).

Run from the project root:
    OMP_NUM_THREADS=1 python research/lab/grade_a/honest_baseline.py           # NQ and ES
    OMP_NUM_THREADS=1 python research/lab/grade_a/honest_baseline.py NQ        # one symbol (no other-symbol join)

Optional: HONEST_BASELINE_ENGINE_CACHE=<dir> loads/stores a pickled trained Engine per symbol (development only;
the default trains from scratch, ~25 s per symbol).  Nothing in the committed modules is changed; the engine's own
code paths (Engine.train, trade_plan, confidence_from_plan, wide_stop_distance, backtest.simulate, the session
grouping of sessions.path_outcomes) are reused.

Steps
  1. Engine(sym).train() gives the honest walk-forward p_raw per target; a CAUSAL isotonic calibration is fitted
     per OOS month on the OOS rows strictly before that month (min 60 rows, else p_raw)          -> fixes H0a
  2. The three regressors of model.fit_regressors are refitted per OOS month on the sample rows strictly before
     the month (same hyper-parameters); the exp_rev shrink is the causal R^2 of the walk-forward exp_rev
     predictions on the prior OOS rows (0 when fewer than 60)                                     -> fixes H0b
  3. trade_plan + confidence_from_plan per OOS night with the causal inputs; every candidate is kept.
  4. Every candidate of every night is resolved from the raw hourly bars for its OWN (target, stop) pair with stop
     priority (H0j), one P&L reference (H0c), stop-through gaps filled at the bar open (H0k), under two fills:
     the 17:00 close (engine convention) and the 18:00 open (first tradeable print, H0d; already_past /
     open_past_stop re-evaluated at the open), plus a 20:00-open variant, the Europe follow-through of a scratch,
     the mark-to-market path and MFE/MAE.
  5. Costs per LAB_DESIGN 2.8 with a sensitivity line (H0h).
  6. The published replica (backtest.simulate) is asserted against research/backtest_trades_{SYM}.csv.
  7. The integrity ladder v0 -> honest baseline (Grade A and all graded; discovery / vault / full; splice nights
     excluded from every statistic but kept in the tables, flagged).
  8. Feature join (knowability marked in the column dictionary), the two extreme detectors and the other
     symbol's honest call.

Outputs (research/lab/grade_a/): trades_honest_{SYM}.csv, candidates_{SYM}.csv, baseline_summary.json,
README_grade_a.md.
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
from datetime import timedelta

os.environ.setdefault("OMP_NUM_THREADS", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression

import backtest
from asia_extremes import SPLICE_SESSIONS
from features import load_daily, wide_stop_distance  # noqa: F401  (wide_stop_distance is what trade_plan uses)
from model import Engine, POINT_VALUE, _design, _sample_mask, confidence_from_plan
from sessions import ASIA_HOURS, EUROPE_HOURS, load_hourly

OUT = HERE
DATA = os.path.join(ROOT, "data")
EXTREMES = os.path.join(ROOT, "research", "extremes")
SPLITS = {"discovery": ("2025-04-01", "2026-05-31"), "vault": ("2026-06-01", "2026-11-06"),
          "full": ("2025-04-01", "2026-11-06")}
COST = {"NQ": {"base": 1.5, "event": 4.0, "hi": 4.0}, "ES": {"base": 0.75, "event": 2.0, "hi": 2.0}}
MIN_CAL_ROWS, MIN_REG_ROWS, MIN_R2_ROWS = 60, 150, 60
N_BOOT, SEED = 2000, 0
GRADES = ("A", "B", "C")
N_K = 9

STEPS = [
    ("step0", "v0 as published (pooled calibrator, full-sample regressors, recorded-outcome resolution, 17:00 fill, no costs)"),
    ("step1", "+ causal calibration (H0a); everything else as v0"),
    ("step2", "+ walk-forward regressors and causal exp_rev shrink (H0b)"),
    ("step3", "+ own-pair raw-bar resolution with one entry reference, stop priority, gap fills (H0c/H0j/H0k); 17:00 fill"),
    ("step4", "+ fill at the 18:00 open; already_past / open_past_stop at the open (H0d); unfillable graded nights = 0"),
    ("step5", "+ costs, base schedule (H0h) = THE HONEST BASELINE (pnl_net_open)"),
    ("step5s", "costs at the sensitivity level everywhere (pnl_net_open_hicost)"),
]


# --------------------------------------------------------------------------------------------------
# 1. causal calibration
# --------------------------------------------------------------------------------------------------
def causal_calibration(oos: pd.DataFrame) -> tuple[pd.Series, dict]:
    """Per OOS month: isotonic fitted on the OOS (p_raw, y) rows strictly before the month (>= 60 rows), else p_raw."""
    per = oos.index.to_period("M")
    out = pd.Series(np.nan, index=oos.index)
    info = {}
    for m in per.unique():
        prior, test = per < m, per == m
        if int(prior.sum()) >= MIN_CAL_ROWS:
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.03, y_max=0.97)
            iso.fit(oos.loc[prior, "p_raw"].values.astype(float), oos.loc[prior, "y"].values.astype(float))
            out[test] = iso.predict(oos.loc[test, "p_raw"].values.astype(float))
        else:
            out[test] = oos.loc[test, "p_raw"].values
        info[str(m)] = int(prior.sum())
    return out, info


# --------------------------------------------------------------------------------------------------
# 2. walk-forward regressors (same hyper-parameters as model.fit_regressors)
# --------------------------------------------------------------------------------------------------
def _hgb_reg():
    return HistGradientBoostingRegressor(max_depth=3, max_iter=120, learning_rate=0.04, l2_regularization=2.0,
                                         min_samples_leaf=20, random_state=7)


def _hgb_q(q):
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=3, max_iter=120,
                                         learning_rate=0.04, min_samples_leaf=20, random_state=7)


def walk_forward_regressors(eng: Engine, nights: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict, dict]:
    X_all = _design(eng.f, eng.cols)
    mask = _sample_mask(eng.f, eng.o, eng.o["rev_ret"], X_all)
    Xs = X_all[mask]
    rr = eng.o.loc[mask, "rev_ret"] * 1e4
    rng = eng.o.loc[mask, "asia_rng"] * 1e4
    per_s = Xs.index.to_period("M")
    per_n = nights.to_period("M")
    rows, shrink, r2s = [], {}, {}
    hist = []  # walk-forward exp_rev predictions on earlier OOS months: (y, pred, training mean)
    for m in sorted(per_n.unique()):
        train = per_s < m
        n_tr = int(train.sum())
        if n_tr < MIN_REG_ROWS:
            raise RuntimeError(f"month {m}: only {n_tr} training rows for the regressors")
        if len(hist) >= MIN_R2_ROWS:
            ph = pd.DataFrame(hist)
            sse = float(((ph.y - ph.pred) ** 2).sum())
            sst = float(((ph.y - ph.train_mean) ** 2).sum())
            r2 = 1 - sse / sst if sst > 0 else 0.0
            shrink[str(m)] = float(np.clip(r2, 0.0, 1.0))
            r2s[str(m)] = r2
        else:
            shrink[str(m)], r2s[str(m)] = 0.0, None
        reg = _hgb_reg().fit(Xs[train], rr[train])
        q50 = _hgb_q(0.5).fit(Xs[train], rng[train])
        q80 = _hgb_q(0.8).fit(Xs[train], rng[train])
        nm = nights[per_n == m]
        Xm = X_all.loc[nm]
        pe, p50, p80 = reg.predict(Xm), q50.predict(Xm), q80.predict(Xm)
        tm = float(rr[train].mean())
        for d, a, b, c in zip(nm, pe, p50, p80):
            rows.append(dict(date=d, exp_rev_bp=float(a), rng_q50_bp=float(b), rng_q80_bp=float(c),
                             train_mean_bp=tm, n_train_reg=n_tr, exp_rev_shrink=shrink[str(m)],
                             exp_rev_r2_prior=np.nan if r2s[str(m)] is None else r2s[str(m)]))
            y = eng.o.loc[d, "rev_ret"] * 1e4
            if not pd.isna(y):
                hist.append(dict(y=float(y), pred=float(a), train_mean=tm))
    return pd.DataFrame(rows).set_index("date"), shrink, r2s


def full_sample_regressors(eng: Engine, nights: pd.DatetimeIndex) -> pd.DataFrame:
    """What backtest.simulate uses: the full-sample regressors of Engine.train (H0b as published)."""
    X = eng.f.loc[nights, eng.cols].astype(float)
    return pd.DataFrame({"exp_rev_bp": eng.regs["exp_rev_bp"].predict(X), "rng_q50_bp": eng.regs["rng_q50"].predict(X),
                         "rng_q80_bp": eng.regs["rng_q80"].predict(X)}, index=nights)


# --------------------------------------------------------------------------------------------------
# 3. calls
# --------------------------------------------------------------------------------------------------
def v0_rule_pnl(o: pd.Series, call: dict, g: dict, plan: dict) -> float:
    """backtest.simulate's resolution from the recorded outcome columns (far-target 'stopped', mixed reference)."""
    if call["grade"] in ("NO EDGE", "-") or not g:
        return np.nan
    sfx = "_w" if g["variant"] == "wide" else ""
    if call["call"].startswith("MEAN"):
        if o[f"hit_{g['target_key']}_first{sfx}"] == 1:
            return g["target_dist"]
        if o[f"stopped{sfx}"] == 1:
            return -g["stop_dist"]
        return o["rev_ret"] * plan["entry"]
    if o[f"stopped{sfx}"] == 1:
        return g["target_dist"]
    if o[f"hit_vwap_first{sfx}"] == 1:
        return -g["stop_dist"]
    return -o["rev_ret"] * plan["entry"]


def cand_id(c: dict) -> str:
    return f"{c['kind']}|{c['variant']}|{c['target_key']}"


def run_calls(eng: Engine, nights: pd.DatetimeIndex, probs: dict, regs: pd.DataFrame, shrink) -> tuple[pd.DataFrame, list]:
    """Replay the daily decision with the given probabilities / regressors.  shrink: dict 'YYYY-MM' -> float or a scalar."""
    keep = eng.regs.get("exp_rev_shrink", 0.0)
    chosen, cands = [], []
    try:
        for d in nights:
            pred = {"probs": {t: {"cal": float(probs[t].loc[d])} for t in eng.TARGETS},
                    "rng_q50_bp": float(regs.loc[d, "rng_q50_bp"]), "rng_q80_bp": float(regs.loc[d, "rng_q80_bp"]),
                    "exp_rev_bp": float(regs.loc[d, "exp_rev_bp"])}
            eng.regs["exp_rev_shrink"] = shrink[str(d.to_period("M"))] if isinstance(shrink, dict) else float(shrink)
            plan = eng.trade_plan(d, pred)
            call = confidence_from_plan(plan, pred)
            g = call.get("geometry") or {}
            kind = call["call"].split(":")[0]
            cid = f"{kind}|{g['variant']}|{g['target_key']}" if g else None
            chosen.append(dict(date=d, grade=call["grade"], call=kind, call_full=call["call"], confidence=call["confidence"],
                               ev_pts=call.get("ev_pts", np.nan), variant=g.get("variant"), best=g.get("target_key"),
                               side=g.get("side"), cand_id=cid, entry=plan["entry"], target=g.get("target"), stop=g.get("stop"),
                               target_dist=g.get("target_dist"), stop_dist=g.get("stop_dist"), p_win=g.get("p_win"),
                               p_loss=g.get("p_loss"), p_scratch=g.get("scratch"),
                               guard_failed=";".join(call.get("guard_failed", [])), rng_q50_pts=plan["rng_q50_pts"],
                               rng_q80_pts=plan["rng_q80_pts"], exp_rev_pts=plan["exp_rev_pts"],
                               exp_rev_shrink=eng.regs["exp_rev_shrink"], pnl_v0rule=v0_rule_pnl(eng.o.loc[d], call, g, plan)))
            for c in call["candidates"]:
                cands.append(dict(date=d, cand_id=cand_id(c), kind=c["kind"], variant=c["variant"], target_key=c["target_key"],
                                  side=c["side"], entry=c["entry"], target=c["target"], stop=c["stop"], target_dist=c["target_dist"],
                                  stop_dist=c["stop_dist"], p_win=c["p_win"], p_loss=c["p_loss"], scratch=c["scratch"],
                                  ev_pts=c["ev_pts"], win_rate_on_resolution=c["win_rate_on_resolution"],
                                  guard_ok=int(c["guard_ok"]), guard_reasons=";".join(c["guard_reasons"]),
                                  chosen=int(cand_id(c) == cid)))
    finally:
        eng.regs["exp_rev_shrink"] = keep
    return pd.DataFrame(chosen).set_index("date"), cands


# --------------------------------------------------------------------------------------------------
# 4. resolution from the raw bars
# --------------------------------------------------------------------------------------------------
def bar_groups(h: pd.DataFrame) -> tuple[dict, dict]:
    """{Globex date -> Asia bars}, {Globex date -> Europe bars}, grouped exactly as sessions.path_outcomes does."""
    g = pd.Series(h.index.date, index=h.index)
    sh = h.index.hour >= 18
    g[sh] = (h.index[sh] + pd.Timedelta(days=1)).date
    hh = h.copy()
    hh["gdate"] = g.values
    hh["hour"] = h.index.hour
    asia = {gd: grp.sort_index() for gd, grp in hh[hh["hour"].isin(ASIA_HOURS)].groupby("gdate")}
    eur = {gd: grp.sort_index() for gd, grp in hh[hh["hour"].isin(EUROPE_HOURS)].groupby("gdate")}
    return asia, eur


def walk(O, H, L, C, side: str, entry: float, target: float, stop: float, start: int = 0) -> dict | None:
    """Walk bars start..n-1 for a position entered at `entry`.  Stop priority inside a bar; a bar opening beyond
    the stop fills at its Open (H0k); targets fill at level; scratch = close of the last bar.  MTM is the signed
    P&L at each bar close while open (positional k), NaN from the exit bar on.  MFE/MAE: best/worst signed
    excursion over the bars held, conservative in the exit bar (its favourable excursion is not counted on a stop
    exit; its adverse excursion is counted on a target exit)."""
    sgn = 1.0 if side == "LONG" else -1.0
    n = len(O)
    if start >= n:
        return None
    mtm = np.full(N_K, np.nan)
    mfe, mae = 0.0, 0.0
    for i in range(start, n):
        fav = sgn * ((H[i] if sgn > 0 else L[i]) - entry)
        adv = sgn * ((L[i] if sgn > 0 else H[i]) - entry)
        stop_hit = (L[i] <= stop) if sgn > 0 else (H[i] >= stop)
        tgt_hit = (H[i] >= target) if sgn > 0 else (L[i] <= target)
        if stop_hit:
            gap = (O[i] <= stop) if sgn > 0 else (O[i] >= stop)
            ex = float(O[i]) if gap else float(stop)
            pnl = sgn * (ex - entry)
            return dict(outcome="stop", resolved_k=i, exit=ex, pnl=pnl, mfe=mfe, mae=min(mae, pnl),
                        gapfill=int(gap), samebar=int(tgt_hit), mtm=mtm)
        if tgt_hit:
            pnl = sgn * (float(target) - entry)
            return dict(outcome="target", resolved_k=i, exit=float(target), pnl=pnl, mfe=max(mfe, pnl), mae=min(mae, adv),
                        gapfill=0, samebar=0, mtm=mtm)
        mfe, mae = max(mfe, fav), min(mae, adv)
        if i < N_K:
            mtm[i] = sgn * (C[i] - entry)
    ex = float(C[n - 1])
    return dict(outcome="scratch", resolved_k=np.nan, exit=ex, pnl=sgn * (ex - entry), mfe=mfe, mae=mae,
                gapfill=0, samebar=0, mtm=mtm)


def _beyond(side: str, px: float, lvl: float, kind: str) -> bool:
    """Is price `px` already beyond `lvl` in the direction a `kind` ('target' / 'stop') is hit for `side`?"""
    if side == "LONG":
        return px >= lvl if kind == "target" else px <= lvl
    return px <= lvl if kind == "target" else px >= lvl


def _fill_block(res: dict | None, sfx: str, traded: bool) -> dict:
    out = {}
    keys = ("outcome", "resolved_k", "exit", "pnl", "mfe", "mae", "gapfill", "samebar")
    if res is None or not traded:
        for k in keys:
            out[f"{k}_{sfx}"] = np.nan if k != "outcome" else None
        for k in range(N_K):
            out[f"pnl_mtm_k{k}_{sfx}"] = np.nan
        return out
    for k in keys:
        out[f"{k}_{sfx}"] = res[k]
    for k in range(N_K):
        out[f"pnl_mtm_k{k}_{sfx}"] = res["mtm"][k]
    return out


def resolve_candidate(bars: pd.DataFrame, eur: pd.DataFrame | None, side: str, entry_post: float, target: float,
                      stop: float) -> dict:
    O, H, L, C = (bars[c].values.astype(float) for c in ("Open", "High", "Low", "Close"))
    hours = bars["hour"].values
    n = len(bars)
    out = {"n_bars": n, "k0_hour": int(hours[0]),
           "bars_contiguous": int(all(((hours[i + 1] - hours[i]) % 24) == 1 for i in range(n - 1)) and hours[0] == 18)}
    # --- fill 1: the 17:00 close (engine convention); a candidate whose target or stop is already beyond that
    #     reference is degenerate (the engine checks already_past only for fade targets) -> not traded, P&L 0 ---
    out["entry_post"] = float(entry_post)
    out["already_past_post"] = int(_beyond(side, float(entry_post), target, "target"))
    out["stop_past_post"] = int(_beyond(side, float(entry_post), stop, "stop"))
    fill_post = not (out["already_past_post"] or out["stop_past_post"])
    r_post = walk(O, H, L, C, side, float(entry_post), target, stop, 0) if fill_post else None
    out.update(_fill_block(r_post, "post", fill_post))
    out["traded_post"] = int(fill_post)
    if not fill_post:
        out["pnl_post"] = 0.0
    # --- fill 2: the 18:00 open, already_past / open_past_stop re-evaluated at the open ---
    op = float(O[0])
    out["entry_open"] = op
    out["already_past_open"] = int(_beyond(side, op, target, "target"))
    out["open_past_stop"] = int(_beyond(side, op, stop, "stop"))
    fill_open = not (out["already_past_open"] or out["open_past_stop"])
    r_open = walk(O, H, L, C, side, op, target, stop, 0) if fill_open else None
    out.update(_fill_block(r_open, "open", fill_open))
    out["traded_open"] = int(fill_open)
    if not fill_open:
        out["pnl_open"] = 0.0
    # --- Europe follow-through of a position still open at 03:00 (levels kept active; stop priority) ---
    for sfx, r, ent in (("post", r_post, float(entry_post)), ("open", r_open, op)):
        eo, ep, ec = None, np.nan, np.nan
        if r is not None and r["outcome"] == "scratch" and eur is not None and len(eur):
            EO, EH, EL, EC = (eur[c].values.astype(float) for c in ("Open", "High", "Low", "Close"))
            re_ = walk(EO, EH, EL, EC, side, ent, target, stop, 0)
            eo = "neither" if re_["outcome"] == "scratch" else re_["outcome"]
            ep = re_["pnl"]
            ec = (1.0 if side == "LONG" else -1.0) * (EC[-1] - ent)
        out[f"eur_outcome_{sfx}"], out[f"eur_pnl_{sfx}"], out[f"pnl_at_eur_close_{sfx}"] = eo, ep, ec
    # --- the same candidate entered at the 20:00 open (two-stage execution hypothesis) ---
    j = int(np.where(hours == 20)[0][0]) if (hours == 20).any() else None
    if j is None:
        out.update({"e20_k": np.nan, "entry_e20": np.nan, "pre_touched_target_e20": np.nan, "pre_touched_stop_e20": np.nan,
                    "already_past_e20": np.nan, "open_past_stop_e20": np.nan, "traded_e20": 0})
        out.update(_fill_block(None, "e20", False))
    else:
        e20 = float(O[j])
        pre_t = bool(((H[:j] >= target) if side == "LONG" else (L[:j] <= target)).any()) if j > 0 else False
        pre_s = bool(((L[:j] <= stop) if side == "LONG" else (H[:j] >= stop)).any()) if j > 0 else False
        ap, ops = _beyond(side, e20, target, "target"), _beyond(side, e20, stop, "stop")
        fill = not (ap or ops)
        out.update({"e20_k": j, "entry_e20": e20, "pre_touched_target_e20": int(pre_t), "pre_touched_stop_e20": int(pre_s),
                    "already_past_e20": int(ap), "open_past_stop_e20": int(ops), "traded_e20": int(fill)})
        r_e20 = walk(O, H, L, C, side, e20, target, stop, j) if fill else None
        out.update(_fill_block(r_e20, "e20", fill))
        if not fill:
            out["pnl_e20"] = 0.0
    return out


# --------------------------------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------------------------------
def block_boot_ci(values: pd.Series, n_boot: int = N_BOOT, seed: int = SEED, q=(0.05, 0.95)) -> tuple[float, float]:
    """Weekly-block (ISO week) bootstrap CI of the mean; numpy default_rng(seed)."""
    v = values.dropna()
    if len(v) < 2:
        return (np.nan, np.nan)
    iso = v.index.isocalendar()
    keys = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).values
    uk = np.unique(keys)
    blocks = [v.values[keys == k] for k in uk]
    rng = np.random.default_rng(seed)
    nb = len(blocks)
    means = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, nb, nb)
        means[i] = np.concatenate([blocks[j] for j in pick]).mean()
    lo, hi = np.quantile(means, q)
    return (float(lo), float(hi))


def months_in(split: str) -> float:
    a, b = (pd.Timestamp(x) for x in SPLITS[split])
    return (b - a).days / 365.25 * 12


def grade_stats(df: pd.DataFrame, grade_col: str, pnl_col: str, pv: float, split: str, untraded_col: str | None = None) -> dict:
    sub = df[df[grade_col] == "A"]
    p = sub[pnl_col].astype(float)
    graded = df[df[grade_col].isin(GRADES)][pnl_col].astype(float)
    out = {"A_n": int(len(sub)), "A_win": float((p > 0).mean()) if len(sub) else np.nan,
           "A_avg": float(p.mean()) if len(sub) else np.nan, "A_total": float(p.sum()), "A_worst": float(p.min()) if len(sub) else np.nan,
           "A_sd": float(p.std(ddof=1)) if len(sub) > 1 else np.nan,
           "A_usd_per_contract_per_year": float(p.sum() * pv * 12 / months_in(split)),
           "A_avg_ci90": list(block_boot_ci(p)),
           "graded_n": int(len(graded)), "all_graded_avg": float(graded.mean()) if len(graded) else np.nan,
           "all_graded_total": float(graded.sum()), "graded_win": float((graded > 0).mean()) if len(graded) else np.nan}
    for g in ("B", "C"):
        s = df[df[grade_col] == g][pnl_col].astype(float)
        out[f"{g}_n"], out[f"{g}_avg"] = int(len(s)), (float(s.mean()) if len(s) else np.nan)
    if untraded_col is not None:
        out["A_untraded"] = int((sub[untraded_col] == 0).sum())
        out["graded_untraded"] = int((df[df[grade_col].isin(GRADES)][untraded_col] == 0).sum())
    out["A_pts_per_sigma"] = float(out["A_avg"] / out["A_sd"]) if out.get("A_sd") and out["A_sd"] > 0 else np.nan
    return out


def membership(df: pd.DataFrame, grade_col: str) -> dict:
    a0 = set(df.index[df["v0_grade"] == "A"])
    a1 = set(df.index[df[grade_col] == "A"])
    both = a0 & a1
    return {"v0_A": len(a0), "step_A": len(a1), "both": len(both), "only_v0": len(a0 - a1), "only_step": len(a1 - a0),
            "jaccard": (len(both) / len(a0 | a1)) if (a0 | a1) else np.nan,
            "v0_A_retained_frac": (len(both) / len(a0)) if a0 else np.nan,
            "dates_dropped": sorted(str(d.date()) for d in (a0 - a1)), "dates_added": sorted(str(d.date()) for d in (a1 - a0))}


# --------------------------------------------------------------------------------------------------
# column dictionaries
# --------------------------------------------------------------------------------------------------
def _col_entry(desc: str, units: str, knowable: str) -> dict:
    return {"desc": desc, "units": units, "knowable_at": knowable}


def describe_columns(cols: list[str], table: str) -> dict:
    d = {}
    K17, K18, K20, EXPOST = "17:xx ET (decision time)", "18:00 ET (first Asia print)", "20:00 ET (close of bar k=1)", "ex post (after the night)"
    fixed = {
        "date": _col_entry("RTH date D; the night is 18:00 D .. 02:59 D+1 ET (Sunday reopen after a Friday)", "date", K17),
        "splice": _col_entry("1 on asia_extremes.SPLICE_SESSIONS nights (contract splice; excluded from every statistic)", "0/1", K17),
        "split": _col_entry("discovery (2025-04-01..2026-05-31) or vault (2026-06-01..)", "label", K17),
        "cand_id": _col_entry("kind|variant|target_key", "label", K17),
        "kind": _col_entry("MEAN REVERSION or CONTINUATION", "label", K17),
        "variant": _col_entry("stop variant: tight (RTH extreme + 10% range) or wide (max(0.6 x med20 Asia range, 0.3 x RTH range))", "label", K17),
        "target_key": _col_entry("vwap / r382 / r500 for fades; stop_level for continuation", "label", K17),
        "best": _col_entry("target_key of the chosen candidate", "label", K17),
        "side": _col_entry("LONG / SHORT of the chosen candidate", "label", K17),
        "grade": _col_entry("honest grade (causal calibration + walk-forward regressors): A >= 72, B >= 63, C >= 56, NO EDGE, '-' = NO TRADE", "label", K17),
        "call": _col_entry("honest call kind (MEAN REVERSION / CONTINUATION / NO TRADE)", "label", K17),
        "call_full": _col_entry("the engine's full call string", "label", K17),
        "confidence": _col_entry("honest confidence = 100 x p_win/(p_win+p_loss) of the chosen candidate", "0-100", K17),
        "ev_pts": _col_entry("engine EV of the candidate (p_win x min(target_dist, q80) - p_loss x stop_dist + scratch x exp_rev)", "index points", K17),
        "entry": _col_entry("engine entry reference = 17:00 post_close (levels and distances are measured from it)", "index points", K17),
        "target": _col_entry("target level", "index points", K17), "stop": _col_entry("stop level", "index points", K17),
        "target_dist": _col_entry("|target - entry|", "index points", K17), "stop_dist": _col_entry("|stop - entry|", "index points", K17),
        "p_win": _col_entry("causal calibrated P(target first) of the candidate (normalised with p_loss when their sum > 1)", "probability", K17),
        "p_loss": _col_entry("causal calibrated P(stop first)", "probability", K17),
        "p_scratch": _col_entry("1 - p_win - p_loss (floored at 0)", "probability", K17),
        "scratch": _col_entry("1 - p_win - p_loss (floored at 0)", "probability", K17),
        "win_rate_on_resolution": _col_entry("p_win/(p_win+p_loss)", "probability", K17),
        "guard_ok": _col_entry("passed the geometry guard (target >= 25% q50, stop <= q80, EV >= 3% q50, win rate >= 0.5)", "0/1", K17),
        "guard_reasons": _col_entry("guard failure reasons, ';'-joined", "text", K17),
        "guard_failed": _col_entry("guard reasons of the chosen candidate when no candidate passed (grade NO EDGE)", "text", K17),
        "chosen": _col_entry("1 for the candidate the honest call selected", "0/1", K17),
        "v0_chosen": _col_entry("1 for the candidate v0 selected", "0/1", K17),
        "s1_chosen": _col_entry("1 for the candidate step 1 (causal calibration, full-sample regressors) selected", "0/1", K17),
        "rng_q50_pts": _col_entry("walk-forward median expected Asia range", "index points", K17),
        "rng_q80_pts": _col_entry("walk-forward P80 expected Asia range", "index points", K17),
        "rng_q50_bp": _col_entry("walk-forward median expected Asia range", "bp of entry", K17),
        "rng_q80_bp": _col_entry("walk-forward P80 expected Asia range", "bp of entry", K17),
        "exp_rev_bp": _col_entry("walk-forward expected signed reversion return", "bp", K17),
        "exp_rev_pts": _col_entry("exp_rev_bp x entry x shrink (the scratch valuation used in the EV)", "index points", K17),
        "exp_rev_shrink": _col_entry("causal shrink = clip(R^2 of walk-forward exp_rev on the prior OOS rows, 0, 1); 0 under 60 rows", "fraction", K17),
        "exp_rev_r2_prior": _col_entry("the unclipped prior-OOS R^2 behind exp_rev_shrink", "fraction", K17),
        "n_train_reg": _col_entry("rows the month's regressors were fitted on", "count", K17),
        "cal_rows_prior": _col_entry("OOS rows the month's causal calibrator was fitted on (0 = p_raw used)", "count", K17),
        "pnl_v0rule": _col_entry("P&L of the honest chosen candidate under v0's resolution rule (recorded outcome columns, 17:00 fill, mixed scratch reference)", "index points", EXPOST),
        "n_bars": _col_entry("Asia bars in the night (9 normal; 6 on holiday eves; 7 on two data-gap nights)", "count", EXPOST),
        "n_eur_bars": _col_entry("Europe bars (03:00-08:59 of the Globex date) in the file (6 normal; 0 on holiday mornings)", "count", EXPOST),
        "k0_hour": _col_entry("ET hour of the first Asia bar (18 normally; 20 on 2025-07-25 NQ/ES, a data gap)", "hour", K18),
        "bars_contiguous": _col_entry("1 when the Asia bars start at 18:00 and are consecutive hours", "0/1", EXPOST),
        "cost_base": _col_entry("round-trip cost, base schedule: NQ 1.5 (ES 0.75) weeknight; 4.0 (2.0) on Sunday reopens, |post_ret| > 0.3% or mega-cap earnings", "index points", K17),
        "cost_hi": _col_entry("round-trip cost, sensitivity: NQ 4.0 / ES 2.0 every night", "index points", K17),
        "event_night": _col_entry("1 when the event cost applies (sunday_open, |post_ret| > 0.3%, megacap_earnings_tonight)", "0/1", K17),
        "traded_post": _col_entry("1 when the candidate is tradeable at the 17:00 reference (not already_past_post, not stop_past_post)", "0/1", K17),
        "already_past_post": _col_entry("target already at/beyond the 17:00 entry (degenerate: the engine checks this only for fade targets, not for the continuation target); not traded, P&L 0", "0/1", K17),
        "stop_past_post": _col_entry("stop already at/beyond the 17:00 entry (post-close moved through the stop level); not traded, P&L 0", "0/1", K17),
        "traded_open": _col_entry("1 when the candidate is fillable at the 18:00 open (not already_past_open, not open_past_stop)", "0/1", K18),
        "traded_e20": _col_entry("1 when the candidate is fillable at the 20:00 open (same two checks at that open)", "0/1", K20),
        "entry_post": _col_entry("fill price under fill_ref=post_close (= entry, the 17:00 close)", "index points", K17),
        "entry_open": _col_entry("fill price under fill_ref=asia_open (Open of the first Asia bar)", "index points", K18),
        "entry_e20": _col_entry("fill price of the 20:00-open variant (Open of the hour-20 bar)", "index points", K20),
        "already_past_open": _col_entry("target already beyond the 18:00 open (not tradeable; P&L 0)", "0/1", K18),
        "open_past_stop": _col_entry("stop already beyond the 18:00 open (not traded; P&L 0)", "0/1", K18),
        "e20_k": _col_entry("positional index of the hour-20 bar (2 normally)", "k", K18),
        "pre_touched_target_e20": _col_entry("target touched in the bars before the 20:00 open", "0/1", K20),
        "pre_touched_stop_e20": _col_entry("stop touched in the bars before the 20:00 open", "0/1", K20),
        "already_past_e20": _col_entry("target already beyond the 20:00 open", "0/1", K20),
        "open_past_stop_e20": _col_entry("stop already beyond the 20:00 open", "0/1", K20),
        "pnl_gross_post": _col_entry("baseline reference: pnl_post when graded (NaN when not graded)", "index points", EXPOST),
        "pnl_net_post": _col_entry("pnl_gross_post - cost_base", "index points", EXPOST),
        "pnl_net_post_hicost": _col_entry("pnl_gross_post - cost_hi", "index points", EXPOST),
        "pnl_gross_open": _col_entry("HONEST gross: pnl_open when graded; 0 when graded but unfillable at the open; NaN when not graded", "index points", EXPOST),
        "pnl_net_open": _col_entry("THE HONEST BASELINE: pnl_gross_open - cost_base (cost only when traded)", "index points", EXPOST),
        "pnl_net_open_hicost": _col_entry("pnl_gross_open - cost_hi (sensitivity)", "index points", EXPOST),
        "pnl_gross_e20": _col_entry("20:00-open variant gross when graded (0 when unfillable at 20:00; NaN when not graded)", "index points", EXPOST),
        "pnl_net_e20": _col_entry("pnl_gross_e20 - cost_base when traded", "index points", EXPOST),
        "pnl_net_e20_hicost": _col_entry("pnl_gross_e20 - cost_hi when traded", "index points", EXPOST),
        "v0_grade": _col_entry("published grade (backtest.simulate replica)", "label", K17),
        "v0_call": _col_entry("published call kind", "label", K17), "v0_confidence": _col_entry("published confidence", "0-100", K17),
        "v0_ev_pts": _col_entry("published EV", "index points", K17), "v0_variant": _col_entry("published stop variant", "label", K17),
        "v0_best": _col_entry("published target_key", "label", K17), "v0_cand_id": _col_entry("published chosen candidate id", "label", K17),
        "v0_pnl_pts": _col_entry("published P&L (recorded-outcome rule, 17:00 fill, no costs)", "index points", EXPOST),
        "v0_p_win": _col_entry("pooled-calibrator (leaky) P(target first) of the candidate", "probability", "LEAKY (pooled OOS)"),
        "v0_p_loss": _col_entry("pooled-calibrator (leaky) P(stop first)", "probability", "LEAKY (pooled OOS)"),
        "v0_scratch": _col_entry("pooled-calibrator scratch probability", "probability", "LEAKY (pooled OOS)"),
        "v0_ev_pts_cand": _col_entry("v0 EV of the candidate (full-sample regressors)", "index points", "LEAKY (full-sample regressors)"),
        "v0_guard_ok": _col_entry("v0 guard decision for the candidate", "0/1", "LEAKY (full-sample regressors)"),
        "s1_grade": _col_entry("grade with causal calibration only (full-sample regressors kept)", "label", "ladder step 1 (regressors still leaky)"),
        "s1_call": _col_entry("step-1 call kind", "label", "ladder step 1"), "s1_confidence": _col_entry("step-1 confidence", "0-100", "ladder step 1"),
        "s1_variant": _col_entry("step-1 stop variant", "label", "ladder step 1"), "s1_best": _col_entry("step-1 target_key", "label", "ladder step 1"),
        "s1_cand_id": _col_entry("step-1 chosen candidate id", "label", "ladder step 1"),
        "s1_pnl_v0rule": _col_entry("step-1 chosen candidate under v0's resolution rule", "index points", EXPOST),
        "mag": _col_entry("|rth_ret_z| = |RTH return| / 20d daily-return sd", "sigma", K17),
        "is_down": _col_entry("1 when the RTH move was down", "0/1", K17), "rth_ret": _col_entry("RTH close / RTH open - 1", "fraction", K17),
        "stretch20_in_dir": _col_entry("(close - SMA20)/ATR20 signed with the RTH move (>0 extends a stretch)", "ATR units", K17),
        "abs_streak": _col_entry("consecutive RTH sessions in the same direction (incl. today)", "count", K17),
        "post_ret": _col_entry("post_close / rth_close - 1 (16:00-17:00 reaction)", "fraction", K17),
        "post_in_dir": _col_entry("post_ret signed with the RTH move", "fraction", K17),
        "megacap_earnings_tonight": _col_entry("mega-cap earnings after the close (calendar)", "0/1", K17),
        "sunday_open": _col_entry("D is a Friday: the night is the Sunday 18:00 reopen", "0/1", K17),
        "pre_holiday": _col_entry("next CALENDAR day is a US holiday (calendar_features; a Friday before a Monday holiday is not flagged)", "0/1", K17),
        "holiday_tomorrow": _col_entry("holiday flag from research/event_calendar.csv for D+1", "0/1", K17),
        "expected_asia_bars_proxy": _col_entry("knowable proxy for the session length: 6 if pre_holiday or holiday_tomorrow else 9", "count", K17),
        "asia_n_bars": _col_entry("actual Asia bars of the night (sessions table)", "count", EXPOST),
        "dow": _col_entry("day of week of D (0 = Monday)", "0-6", K17), "vix": _col_entry("VIX close on D", "index", K17),
        "vix_z20": _col_entry("VIX z-score vs its 20d mean/sd", "sigma", K17), "rv_ratio": _col_entry("5d / 20d realised vol", "ratio", K17),
        "rth_vol_rel": _col_entry("RTH volume / 20d mean", "ratio", K17),
        "asia_rng_med20": _col_entry("20-night rolling median of (asia_high - asia_low) / asia_open, prior nights only", "fraction of asia_open", K17),
        "med20_pts": _col_entry("asia_rng_med20 x entry (post_close)", "index points", K17),
        "kospi_ret": _col_entry("KOSPI session-to-session change, prior session (features.py dchg: the row dated <= D, forward-filled)", "fraction", K17),
        "n225_ret": _col_entry("Nikkei session-to-session change, prior session (features.py dchg)", "fraction", K17),
        "kospi_dd20": _col_entry("KOSPI close (row dated <= D, the session that closed before 18:00 ET of D) / its 20-session rolling max - 1", "fraction", K17),
        "hsi_dd20": _col_entry("HSI likewise (placebo for kospi_dd20)", "fraction", K17),
        "fomc_tomorrow": _col_entry("FOMC decision on the next trading day", "0/1", K17),
        "tier1_data_tomorrow": _col_entry("CPI/NFP/PCE on the next trading day", "0/1", K17),
        "is_dst": _col_entry("the night's 18:00 bar is in EDT (UTC-4)", "0/1", K17),
        "tokyo_open_bar": _col_entry("positional k of the bar containing the Tokyo cash open 09:00 JST (19:00 ET EST -> 1, 20:00 ET EDT -> 2)", "k", K17),
        "move_18_20_in_dir": _col_entry("(Close of bar k=1 - Open of bar k=0) x (+1 LONG / -1 SHORT of the chosen side)", "index points", K20),
        "other_grade": _col_entry("the other symbol's honest grade for the same RTH date", "label", K17),
        "other_call": _col_entry("the other symbol's honest call kind", "label", K17),
        "other_side": _col_entry("the other symbol's honest side", "label", K17),
        "pB_high_above_cal": _col_entry("Detector B: P(Asia high > RTH high), calibrated, walk-forward (oos_preasia high_above_rth_high__full__p_cal)", "probability", K17),
        "pB_low_below_cal": _col_entry("Detector B: P(Asia low < RTH low), calibrated (low_below_rth_low__full__p_cal)", "probability", K17),
        "pB_high_above_raw": _col_entry("Detector B raw p (high_above_rth_high__full__p_raw)", "probability", K17),
        "pB_low_below_raw": _col_entry("Detector B raw p (low_below_rth_low__full__p_raw)", "probability", K17),
        "pB_rng_q50_bp": _col_entry("Detector B expected Asia range median (rng_bp__q50)", "bp of the 17:00 close", K17),
        "v0_pnl_post_resolved": _col_entry("own-pair raw-bar P&L (17:00 fill, no costs) of v0's chosen candidate (self-check column)", "index points", EXPOST),
        "v0_resolution_disagreement": _col_entry("why v0_pnl_pts differs from v0_pnl_post_resolved ('' = agrees)", "text", EXPOST),
    }
    for sfx, lab, kn in (("post", "17:00-close fill", K17), ("open", "18:00-open fill", K18), ("e20", "20:00-open variant", K20)):
        fixed[f"outcome_{sfx}"] = _col_entry(f"{lab}: target / stop / scratch (None when not traded)", "label", EXPOST)
        fixed[f"resolved_k_{sfx}"] = _col_entry(f"{lab}: positional Asia bar index of the exit (0 = first bar, normally 18:00); NaN for scratch", "k", EXPOST)
        fixed[f"exit_{sfx}"] = _col_entry(f"{lab}: exit price (stop level, bar Open on a gap through the stop, target level, or the last Asia close)", "index points", EXPOST)
        fixed[f"pnl_{sfx}"] = _col_entry(f"{lab}: signed gross P&L of the candidate from its fill (0 when not traded)", "index points", EXPOST)
        fixed[f"mfe_{sfx}"] = _col_entry(f"{lab}: max favourable excursion over the bars held (conservative in the exit bar)", "index points", EXPOST)
        fixed[f"mae_{sfx}"] = _col_entry(f"{lab}: max adverse excursion over the bars held (<= 0)", "index points", EXPOST)
        fixed[f"gapfill_{sfx}"] = _col_entry(f"{lab}: 1 when the stop was filled at a bar Open beyond the stop level (H0k)", "0/1", EXPOST)
        fixed[f"samebar_{sfx}"] = _col_entry(f"{lab}: 1 when the exit bar touched both the stop and the target (booked as stop)", "0/1", EXPOST)
        for k in range(N_K):
            fixed[f"pnl_mtm_k{k}_{sfx}"] = _col_entry(f"{lab}: mark-to-market P&L at the close of positional bar k while open; NaN from the exit bar on or when the bar is missing", "index points", f"close of bar k={k}")
        if sfx != "e20":
            fixed[f"eur_outcome_{sfx}"] = _col_entry(f"{lab}: a scratch held into Europe (03:00-08:59) with the levels active: target / stop / neither", "label", EXPOST)
            fixed[f"eur_pnl_{sfx}"] = _col_entry(f"{lab}: P&L of that Europe hold (exit at the level, else the Europe close)", "index points", EXPOST)
            fixed[f"pnl_at_eur_close_{sfx}"] = _col_entry(f"{lab}: mark-to-market P&L of the scratch at the last Europe bar close", "index points", EXPOST)
    for k in range(4):
        fixed[f"pA_high_k{k}"] = _col_entry(f"Detector A at the close of bar k={k}: P(the Asia high is already in)", "probability", f"close of bar k={k}")
        fixed[f"pA_low_k{k}"] = _col_entry(f"Detector A at the close of bar k={k}: P(the Asia low is already in)", "probability", f"close of bar k={k}")
        fixed[f"pA_ovn_high_k{k}"] = _col_entry(f"Detector A at the close of bar k={k}: P(the 18:00-08:59 overnight high is already in)", "probability", f"close of bar k={k}")
        fixed[f"pA_ovn_low_k{k}"] = _col_entry(f"Detector A at the close of bar k={k}: P(the overnight low is already in)", "probability", f"close of bar k={k}")
    if table == "candidates":   # candidate-level columns: not grade-gated
        fixed["side"] = _col_entry("LONG / SHORT of the candidate", "label", K17)
        for sfx, lab in (("post", "17:00-close fill"), ("open", "18:00-open fill"), ("e20", "20:00-open variant")):
            fixed[f"pnl_net_{sfx}"] = _col_entry(f"{lab}: pnl_{sfx} - cost_base when the candidate is fillable, 0 otherwise (candidate level, NOT grade-gated; the night's grade is in `grade`)", "index points", EXPOST)
            fixed[f"pnl_net_{sfx}_hicost"] = _col_entry(f"{lab}: pnl_{sfx} - cost_hi when fillable, 0 otherwise (candidate level, NOT grade-gated)", "index points", EXPOST)
    for c in cols:
        d[c] = fixed.get(c, _col_entry("(undocumented)", "", ""))
    return d


# --------------------------------------------------------------------------------------------------
# per-symbol build
# --------------------------------------------------------------------------------------------------
def load_engine(sym: str) -> Engine:
    cache = os.environ.get("HONEST_BASELINE_ENGINE_CACHE")
    if cache:
        p = os.path.join(cache, f"eng_{sym}.pkl")
        if os.path.exists(p):
            with open(p, "rb") as fh:
                return pickle.load(fh)
    eng = Engine(sym).train()
    if cache:
        os.makedirs(cache, exist_ok=True)
        with open(os.path.join(cache, f"eng_{sym}.pkl"), "wb") as fh:
            pickle.dump(eng, fh)
    return eng


def build_symbol(sym: str) -> dict:
    t0 = time.time()
    pv = POINT_VALUE[sym]
    eng = load_engine(sym)
    nights = eng.fits["stopped"].oos.index
    for t in eng.TARGETS:
        nights = nights.intersection(eng.fits[t].oos.index)
    nights = pd.DatetimeIndex(sorted(nights))

    # ---- 6. the published replica ----
    sim = backtest.simulate(eng)
    pub = pd.read_csv(os.path.join(ROOT, "research", f"backtest_trades_{sym}.csv"), index_col=0, parse_dates=True)
    assert sim.index.equals(pub.index), "replica index differs from the committed CSV"
    assert sim.index.equals(nights), "OOS nights differ from the replica"
    grade_agree = float((sim["grade"].values == pub["grade"].values).mean())
    pnl_diff = float(np.nanmax(np.abs(sim["pnl_pts"].fillna(0).values - pub["pnl_pts"].fillna(0).values)))
    assert grade_agree == 1.0 and pnl_diff < 1e-6, f"replica mismatch: grade agreement {grade_agree}, |pnl diff| {pnl_diff}"
    assert sim["pnl_pts"].isna().equals(pub["pnl_pts"].isna()), "replica NaN pattern differs"

    # ---- 1. causal calibration ----
    probs_causal, probs_v0, cal_info = {}, {}, {}
    for t in eng.TARGETS:
        oos = eng.fits[t].oos
        pc, info = causal_calibration(oos)
        probs_causal[t] = pc.reindex(nights)
        probs_v0[t] = oos["p_cal"].reindex(nights)
        cal_info[t] = info
    cal_rows_prior = pd.Series({d: cal_info["stopped"][str(d.to_period("M"))] for d in nights})

    # ---- 2. regressors ----
    regs_full = full_sample_regressors(eng, nights)
    regs_wf, shrink_wf, r2_wf = walk_forward_regressors(eng, nights)

    # ---- 3. calls under the three configurations ----
    v0_calls, v0_cands = run_calls(eng, nights, probs_v0, regs_full, float(eng.regs["exp_rev_shrink"]))
    s1_calls, s1_cands = run_calls(eng, nights, probs_causal, regs_full, float(eng.regs["exp_rev_shrink"]))
    hon, hon_cands = run_calls(eng, nights, probs_causal, regs_wf, shrink_wf)
    # the in-script v0 replay must equal backtest.simulate exactly (same inputs, same code path)
    assert (v0_calls["grade"].values == sim["grade"].values).all(), "in-script v0 replay differs from backtest.simulate (grade)"
    assert np.nanmax(np.abs(v0_calls["pnl_v0rule"].fillna(0).values - sim["pnl_pts"].fillna(0).values)) < 1e-9, "v0 replay P&L differs"

    cands = pd.DataFrame(hon_cands)
    v0c = pd.DataFrame(v0_cands).set_index(["date", "cand_id"])
    s1c = pd.DataFrame(s1_cands).set_index(["date", "cand_id"])
    cands = cands.set_index(["date", "cand_id"])
    assert cands.index.equals(v0c.index) and cands.index.equals(s1c.index), "candidate universes differ across configurations"
    for c_src, c_dst in (("p_win", "v0_p_win"), ("p_loss", "v0_p_loss"), ("scratch", "v0_scratch"), ("ev_pts", "v0_ev_pts_cand"),
                         ("guard_ok", "v0_guard_ok"), ("chosen", "v0_chosen")):
        cands[c_dst] = v0c[c_src]
    cands["s1_chosen"] = s1c["chosen"]
    cands = cands.reset_index()

    # ---- 4. resolution of every candidate from the raw bars ----
    h = load_hourly(os.path.join(DATA, f"{sym}_1h.csv"))
    asia_g, eur_g = bar_groups(h)
    res_rows, night_info = [], {}
    for d in nights:
        gd = pd.Timestamp(eng.s.loc[d, "asia_gdate"]).date()
        bars = asia_g[gd]
        assert len(bars) == int(eng.s.loc[d, "asia_n_bars"]), f"{d.date()}: bar count {len(bars)} != sessions table"
        hrs = bars["hour"].values
        night_info[d] = {"n_bars": len(bars), "k0_hour": int(hrs[0]),
                         "bars_contiguous": int(all(((hrs[i + 1] - hrs[i]) % 24) == 1 for i in range(len(hrs) - 1)) and hrs[0] == 18),
                         "n_eur_bars": int(len(eur_g.get(gd, [])))}
    night_info = pd.DataFrame.from_dict(night_info, orient="index")
    for (d, grp) in cands.groupby("date", sort=False):
        gd = pd.Timestamp(eng.s.loc[d, "asia_gdate"]).date()
        bars = asia_g[gd]
        eur = eur_g.get(gd)
        for _, c in grp.iterrows():
            r = resolve_candidate(bars, eur, c["side"], float(c["entry"]), float(c["target"]), float(c["stop"]))
            r["date"], r["cand_id"] = d, c["cand_id"]
            res_rows.append(r)
    res = pd.DataFrame(res_rows)
    cands = cands.merge(res, on=["date", "cand_id"], how="left")

    # ---- 5. costs (candidate level: applied when the candidate is fillable) ----
    f = eng.f
    event = ((f["sunday_open"] == 1) | (f["post_ret"].abs() > 0.003) | (f["megacap_earnings_tonight"] == 1)).reindex(nights).fillna(False)
    cost_base = pd.Series(np.where(event, COST[sym]["event"], COST[sym]["base"]), index=nights)
    cost_hi = pd.Series(COST[sym]["hi"], index=nights)
    cands["event_night"] = cands["date"].map(event.astype(int))
    cands["cost_base"] = cands["date"].map(cost_base)
    cands["cost_hi"] = cands["date"].map(cost_hi)
    for sfx in ("post", "open", "e20"):
        tr = cands[f"traded_{sfx}"] == 1
        cands[f"pnl_net_{sfx}"] = np.where(tr, cands[f"pnl_{sfx}"] - cands["cost_base"], 0.0)
        cands[f"pnl_net_{sfx}_hicost"] = np.where(tr, cands[f"pnl_{sfx}"] - cands["cost_hi"], 0.0)
    cands["grade"] = cands["date"].map(hon["grade"])
    cands["v0_grade"] = cands["date"].map(v0_calls["grade"])
    splice_dates = {pd.Timestamp(x) for x in SPLICE_SESSIONS.get(sym, [])}
    cands["splice"] = cands["date"].isin(splice_dates).astype(int)

    # ---- the night table ----
    T = hon.copy()
    T["cal_rows_prior"] = cal_rows_prior
    for c in ("rng_q50_bp", "rng_q80_bp", "exp_rev_bp", "exp_rev_r2_prior", "n_train_reg"):
        T[c] = regs_wf[c]
    for c, src in (("v0_grade", "grade"), ("v0_call", "call"), ("v0_confidence", "confidence"), ("v0_ev_pts", "ev_pts"),
                   ("v0_variant", "variant"), ("v0_best", "best"), ("v0_cand_id", "cand_id")):
        T[c] = v0_calls[src]
    T["v0_pnl_pts"] = sim["pnl_pts"]
    for c, src in (("s1_grade", "grade"), ("s1_call", "call"), ("s1_confidence", "confidence"), ("s1_variant", "variant"),
                   ("s1_best", "best"), ("s1_cand_id", "cand_id"), ("s1_pnl_v0rule", "pnl_v0rule")):
        T[c] = s1_calls[src]
    T["splice"] = T.index.isin(splice_dates).astype(int)
    T["split"] = np.where(T.index <= pd.Timestamp(SPLITS["discovery"][1]), "discovery", "vault")
    # resolution of the chosen candidate
    res_cols = [c for c in res.columns if c not in ("date", "cand_id", "n_bars", "k0_hour", "bars_contiguous")]
    chosen_res = cands[cands["chosen"] == 1].set_index("date")[res_cols]
    T = T.join(night_info).join(chosen_res)
    T["cost_base"], T["cost_hi"], T["event_night"] = cost_base, cost_hi, event.astype(int)
    for sfx in ("post", "open", "e20"):   # NO TRADE nights have no candidate: nothing was traded
        T[f"traded_{sfx}"] = T[f"traded_{sfx}"].fillna(0).astype(int)
    graded = T["grade"].isin(GRADES)
    for sfx in ("post", "open", "e20"):
        tr = graded & (T[f"traded_{sfx}"] == 1)
        T[f"pnl_gross_{sfx}"] = np.where(graded, np.where(tr, T[f"pnl_{sfx}"], 0.0), np.nan)
        T[f"pnl_net_{sfx}"] = np.where(graded, np.where(tr, T[f"pnl_{sfx}"] - T["cost_base"], 0.0), np.nan)
        T[f"pnl_net_{sfx}_hicost"] = np.where(graded, np.where(tr, T[f"pnl_{sfx}"] - T["cost_hi"], 0.0), np.nan)

    # ---- 10. self-check: own-pair post_close resolution of v0's chosen candidate vs v0 pnl_pts ----
    v0_res = cands[cands["v0_chosen"] == 1].set_index("date")
    T["v0_pnl_post_resolved"] = v0_res["pnl_post"]
    reasons = []
    for d in T.index:
        v = T.loc[d, "v0_pnl_pts"]
        if pd.isna(v):
            reasons.append("")
            continue
        r = v0_res.loc[d]
        why = []
        if abs(r["pnl_post"] - v) > 1e-6:
            if r["already_past_post"] == 1:
                why.append("target_already_past_at_17:00_entry(degenerate candidate: the post-close moved through the tight stop level; v0 books it)")
            elif r["stop_past_post"] == 1:
                why.append("stop_already_past_at_17:00_entry(degenerate candidate; v0 books an immediate stop)")
            elif r["outcome_post"] == "scratch":
                why.append("scratch_reference(asia_open->post_close)")
            if r["outcome_post"] == "stop" and r["gapfill_post"] == 1:
                why.append("stop_gap_fill_at_open(H0k)")
            if r["kind"] == "CONTINUATION" and r["samebar_post"] == 1:
                why.append("same_bar_both_touched(v0 books a continuation win)")
            elif r["kind"] == "CONTINUATION" and r["outcome_post"] == "stop" and v > 0:
                why.append("continuation_far_target_rule(VWAP touched before the stop level; v0 books a win)")
            if not why:
                why.append("UNEXPLAINED")
        reasons.append(";".join(why))
    T["v0_resolution_disagreement"] = reasons
    n_graded_v0 = int(T["v0_pnl_pts"].notna().sum())
    dis = T[T["v0_resolution_disagreement"] != ""]
    unex = T[T["v0_resolution_disagreement"].str.contains("UNEXPLAINED")]
    if len(unex):
        cols = ["v0_grade", "v0_call", "v0_variant", "v0_best", "v0_pnl_pts", "v0_pnl_post_resolved"]
        print(unex[cols].to_string())
        print(v0_res.loc[unex.index, ["side", "entry", "target", "stop", "outcome_post", "resolved_k_post", "exit_post", "gapfill_post", "samebar_post"]].to_string())
        raise AssertionError(f"{sym}: unexplained resolution disagreement on {len(unex)} night(s)")
    unamb = T[T["v0_pnl_pts"].notna() & (T["v0_resolution_disagreement"] == "")]
    assert np.nanmax(np.abs(unamb["v0_pnl_pts"] - unamb["v0_pnl_post_resolved"])) < 1e-6 if len(unamb) else True
    # shares sum to one; bar counts
    for sfx in ("post", "open"):
        tr = T[T[f"traded_{sfx}"] == 1]
        sh = tr[f"outcome_{sfx}"].value_counts(normalize=True)
        assert abs(sh.reindex(["target", "stop", "scratch"]).fillna(0).sum() - 1) < 1e-9
    assert T["n_bars"].between(6, 9).all() and (T["n_bars"] == 9).mean() > 0.9
    assert (cands.groupby("date")["chosen"].sum() <= 1).all()

    # ---- 8. feature join ----
    for c in ("mag", "is_down", "rth_ret", "stretch20_in_dir", "abs_streak", "post_ret", "post_in_dir", "megacap_earnings_tonight",
              "sunday_open", "pre_holiday", "holiday_tomorrow", "dow", "vix", "vix_z20", "rv_ratio", "rth_vol_rel", "asia_rng_med20",
              "kospi_ret", "n225_ret", "fomc_tomorrow", "tier1_data_tomorrow"):
        T[c] = f.loc[nights, c]
    T["med20_pts"] = T["asia_rng_med20"] * T["entry"]
    daily = load_daily()
    for col, name in (("KOSPI", "kospi_dd20"), ("HSI", "hsi_dd20")):
        x = daily[col].dropna()
        x = x[~x.index.duplicated()]
        dd = x / x.rolling(20, min_periods=10).max() - 1
        T[name] = dd.reindex(nights, method="ffill")
    T["asia_n_bars"] = eng.s.loc[nights, "asia_n_bars"]
    T["expected_asia_bars_proxy"] = np.where((T["pre_holiday"] == 1) | (T["holiday_tomorrow"] == 1), 6, 9)
    is_dst, tko, m1820 = [], [], []
    for d in nights:
        bars = asia_g[pd.Timestamp(eng.s.loc[d, "asia_gdate"]).date()]
        dst = bars.index[0].dst() != timedelta(0)
        is_dst.append(int(dst))
        hrs = bars["hour"].values
        want = 20 if dst else 19
        tko.append(int(np.where(hrs == want)[0][0]) if (hrs == want).any() else np.nan)
        side = T.loc[d, "side"]
        if side is None or pd.isna(side) or len(bars) < 2:
            m1820.append(np.nan)
        else:
            m1820.append((1.0 if side == "LONG" else -1.0) * (float(bars["Close"].iloc[1]) - float(bars["Open"].iloc[0])))
    T["is_dst"], T["tokyo_open_bar"], T["move_18_20_in_dir"] = is_dst, tko, m1820
    # detectors
    b = pd.read_csv(os.path.join(EXTREMES, f"oos_preasia_{sym}.csv"), index_col=0, parse_dates=True)
    for dst_c, src_c in (("pB_high_above_cal", "high_above_rth_high__full__p_cal"), ("pB_low_below_cal", "low_below_rth_low__full__p_cal"),
                         ("pB_high_above_raw", "high_above_rth_high__full__p_raw"), ("pB_low_below_raw", "low_below_rth_low__full__p_raw"),
                         ("pB_rng_q50_bp", "rng_bp__q50")):
        T[dst_c] = b[src_c].reindex(nights) if src_c in b.columns else np.nan
    a = pd.read_csv(os.path.join(EXTREMES, f"oos_intrasession_{sym}.csv"), parse_dates=["date"])
    a = a[a["k"] <= 3]
    for dst_c, src_c in (("pA_high", "p_high_done"), ("pA_low", "p_low_done"), ("pA_ovn_high", "p_ovn_high_done"), ("pA_ovn_low", "p_ovn_low_done")):
        w = a.pivot(index="date", columns="k", values=src_c)
        for k in range(4):
            T[f"{dst_c}_k{k}"] = w[k].reindex(nights) if k in w.columns else np.nan

    # ---- 7. the ladder ----
    L = T[T["splice"] == 0].copy()
    L["step0_grade"], L["step0_pnl"] = L["v0_grade"], L["v0_pnl_pts"]
    L["step1_grade"], L["step1_pnl"] = L["s1_grade"], L["s1_pnl_v0rule"]
    for st in ("step2", "step3", "step4", "step5", "step5s"):
        L[f"{st}_grade"] = L["grade"]
    L["step2_pnl"] = L["pnl_v0rule"]
    L["step3_pnl"] = L["pnl_gross_post"]
    L["step4_pnl"] = L["pnl_gross_open"]
    L["step5_pnl"] = L["pnl_net_open"]
    L["step5s_pnl"] = L["pnl_net_open_hicost"]
    ladder, member, paired = {}, {}, {}
    for split in SPLITS:
        a_, b_ = (pd.Timestamp(x) for x in SPLITS[split])
        S = L[(L.index >= a_) & (L.index <= b_)]
        ladder[split] = []
        for st, desc in STEPS:
            unt = "traded_open" if st in ("step4", "step5", "step5s") else ("traded_post" if st == "step3" else None)
            row = {"step": st, "desc": desc}
            row.update(grade_stats(S, f"{st}_grade", f"{st}_pnl", pv, split, unt))
            ladder[split].append(row)
    for st, _ in STEPS:
        member[st] = membership(L, f"{st}_grade")
    # paired per-night differences (untraded / ungraded = 0), weekly-block bootstrap 90% CI
    prev = None
    for st, _ in STEPS:
        cur = L[f"{st}_pnl"].fillna(0.0)
        if prev is not None:
            for split in SPLITS:
                a_, b_ = (pd.Timestamp(x) for x in SPLITS[split])
                m = (L.index >= a_) & (L.index <= b_)
                diff = (cur - prev)[m]
                aset = L[f"{st}_grade"].eq("A") | L[prev_name + "_grade"].eq("A")
                da = diff[aset[m]]
                paired.setdefault(split, {})[f"{prev_name}->{st}"] = {
                    "all_nights_mean": float(diff.mean()), "all_nights_ci90": list(block_boot_ci(diff)), "n_affected": int((diff.abs() > 1e-9).sum()),
                    "A_either_mean": float(da.mean()) if len(da) else np.nan, "A_either_ci90": list(block_boot_ci(da)), "A_either_n": int(len(da)),
                    "usd_per_contract_per_year_all_nights": float(diff.sum() * pv * 12 / months_in(split))}
        prev, prev_name = cur, st
    for split in SPLITS:
        a_, b_ = (pd.Timestamp(x) for x in SPLITS[split])
        m = (L.index >= a_) & (L.index <= b_)
        diff = (L["step5_pnl"].fillna(0.0) - L["step0_pnl"].fillna(0.0))[m]
        aset = (L["step5_grade"].eq("A") | L["step0_grade"].eq("A"))[m]
        paired[split]["step0->step5"] = {"all_nights_mean": float(diff.mean()), "all_nights_ci90": list(block_boot_ci(diff)),
                                         "n_affected": int((diff.abs() > 1e-9).sum()), "A_either_mean": float(diff[aset].mean()),
                                         "A_either_ci90": list(block_boot_ci(diff[aset])), "A_either_n": int(aset.sum()),
                                         "usd_per_contract_per_year_all_nights": float(diff.sum() * pv * 12 / months_in(split))}

    # ---- 9. write ----
    T.index.name = "date"
    out = {"sym": sym, "T": T, "cands": cands, "ladder": ladder, "membership": member, "paired": paired,
           "self_checks": {"replica_grade_agreement": grade_agree, "replica_max_abs_pnl_diff": pnl_diff,
                           "v0_graded_nights": n_graded_v0, "v0_resolution_agree": int(n_graded_v0 - len(dis)),
                           "v0_resolution_disagree": int(len(dis)),
                           "v0_resolution_disagreements": {str(d.date()): {"reason": r["v0_resolution_disagreement"], "v0_pnl": float(r["v0_pnl_pts"]),
                                                                            "own_pair_pnl": float(r["v0_pnl_post_resolved"]), "grade": r["v0_grade"],
                                                                            "call": r["v0_call"], "variant": r["v0_variant"]}
                                                           for d, r in dis.iterrows()},
                           "night_bar_counts": {int(k): int(v) for k, v in T["n_bars"].value_counts().sort_index().items()},
                           "outcome_shares_post": {k: float(v) for k, v in T[T["traded_post"] == 1]["outcome_post"].value_counts(normalize=True).items()},
                           "outcome_shares_open": {k: float(v) for k, v in T[T["traded_open"] == 1]["outcome_open"].value_counts(normalize=True).items()},
                           "n_oos_nights": int(len(T)), "n_splice_nights": int(T["splice"].sum()),
                           "splice_dates": sorted(str(d.date()) for d in T.index[T["splice"] == 1])},
           "calibration_rows_prior_by_month": cal_info["stopped"], "exp_rev_shrink_by_month": shrink_wf, "exp_rev_r2_prior_by_month": r2_wf,
           "cost_schedule": COST[sym], "runtime_s": time.time() - t0}
    return out


def print_ladder(sym: str, ladder: dict):
    for split in ("discovery", "vault", "full"):
        print(f"\n{sym} ladder [{split}] (splices excluded)")
        print(f"{'step':8s} {'A_n':>4s} {'A_win':>6s} {'A_avg':>7s} {'A_tot':>8s} {'A_worst':>8s} {'A_sd':>6s} {'untr':>4s} {'grd_n':>5s} {'grd_avg':>7s} {'B_avg':>7s} {'C_avg':>7s}")
        for r in ladder[split]:
            print(f"{r['step']:8s} {r['A_n']:4d} {r['A_win']:6.2f} {r['A_avg']:7.1f} {r['A_total']:8.0f} {r['A_worst']:8.0f} {r['A_sd']:6.0f} "
                  f"{r.get('A_untraded', 0):4d} {r['graded_n']:5d} {r['all_graded_avg']:7.1f} {r['B_avg']:7.1f} {r['C_avg']:7.1f}")


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (isinstance(o, float) or isinstance(o, np.floating)) and np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    return o


def main(syms):
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    results = {s: build_symbol(s) for s in syms}
    # other symbol's honest call
    for s, r in results.items():
        o = "ES" if s == "NQ" else "NQ"
        T = r["T"]
        if o in results:
            To = results[o]["T"]
            T["other_grade"] = To["grade"].reindex(T.index)
            T["other_call"] = To["call"].reindex(T.index)
            T["other_side"] = To["side"].reindex(T.index)
        else:
            T["other_grade"], T["other_call"], T["other_side"] = None, None, None
    summary = {"generated_from": "research/lab/grade_a/honest_baseline.py", "steps": dict(STEPS), "splits": SPLITS,
               "oos_months_full": 19.2, "bootstrap": {"blocks": "ISO week", "draws": N_BOOT, "rng": f"numpy default_rng({SEED})", "ci": "90%"},
               "symbols": {}}
    for s, r in results.items():
        T, C = r["T"], r["cands"]
        T.to_csv(os.path.join(OUT, f"trades_honest_{s}.csv"))
        C.to_csv(os.path.join(OUT, f"candidates_{s}.csv"), index=False)
        print_ladder(s, r["ladder"])
        summary["symbols"][s] = {k: r[k] for k in ("ladder", "membership", "paired", "self_checks", "calibration_rows_prior_by_month",
                                                   "exp_rev_shrink_by_month", "exp_rev_r2_prior_by_month", "cost_schedule", "runtime_s")}
        summary["symbols"][s]["point_value_usd"] = POINT_VALUE[s]
        summary["symbols"][s]["grade_counts_honest"] = {str(k): int(v) for k, v in T["grade"].value_counts().items()}
        summary["symbols"][s]["grade_counts_v0"] = {str(k): int(v) for k, v in T["v0_grade"].value_counts().items()}
        summary["symbols"][s]["grade_transition_v0_to_honest"] = {f"{a}->{b}": int(n) for (a, b), n in T.groupby(["v0_grade", "grade"]).size().items()}
    anyT = next(iter(results.values()))
    summary["columns"] = {"trades_honest": describe_columns(["date"] + list(anyT["T"].columns), "trades"),
                          "candidates": describe_columns(list(anyT["cands"].columns), "candidates")}
    summary["runtime_s"] = time.time() - t0
    with open(os.path.join(OUT, "baseline_summary.json"), "w") as fh:
        json.dump(_jsonable(summary), fh, indent=1)
    readme = [
        "# research/lab/grade_a -- honest baseline of the Asia-session engine (iteration-0 integrity bundle H0a-H0d, H0h-H0k)",
        "honest_baseline.py: builds everything below from the committed engine (no committed module is modified); run from the project root with OMP_NUM_THREADS=1 python research/lab/grade_a/honest_baseline.py",
        "trades_honest_{SYM}.csv: one row per OOS night (2025-04-01..2026-11-06): honest call (causal calibration + walk-forward regressors), the chosen candidate's raw-bar resolution under the 17:00 and 18:00 fills and the 20:00 variant, costs, the v0 replica (v0_*), step-1 columns (s1_*), features (knowability in baseline_summary.json), both extreme detectors, the other symbol's call; splice=1 rows are kept but excluded from every statistic.",
        "THE HONEST BASELINE P&L for every hypothesis tester = pnl_net_open (grade in A/B/C; 18:00-open fill; 0 when unfillable at the open; base costs); sensitivity = pnl_net_open_hicost; pnl_gross_open and pnl_net_post for reference.",
        "candidates_{SYM}.csv: one row per night per candidate (kind x stop variant x target) with geometry, causal probabilities, guard flags, the v0 probabilities, and the full resolution block (outcome/exit/P&L/MTM path/MFE/MAE/Europe follow-through/20:00 variant/costs) so a night can be re-called without touching the bars.",
        "baseline_summary.json: the integrity ladder (step0 = v0 ... step5 = honest baseline, step5s = high costs) for Grade A and all graded per split (discovery / vault / full), A-membership overlap with v0, paired per-night step effects with weekly-block bootstrap 90% CIs, self-checks (replica match, resolution disagreements with reasons), calibration/regressor diagnostics, and the column dictionaries with units and knowability.",
        "Resolution rules: own (target, stop) pair walked bar by bar; stop priority inside a bar; a bar opening beyond the stop fills at its Open; targets fill at level; scratch = last Asia close minus the fill (one reference); k is the positional Asia bar index (0 = first bar, normally 18:00; 2025-07-25 starts at 20:00).",
        "Knowability: columns marked 17:xx / 18:00 are usable as rule inputs at the decision; 'close of bar k' columns only for a checkpoint at bar k; 'ex post' columns (outcomes, asia_n_bars) are never rule inputs; move_18_20_in_dir is a 20:00 input (close of bar k=1), usable only by a checkpoint at or after 20:00; v0_p_* and v0_guard_ok are leaky by construction.",
        "Costs: NQ 1.5 pts round trip (4.0 on Sunday reopens, |post_ret| > 0.3% or mega-cap earnings nights), ES 0.75 / 2.0; sensitivity 4.0 / 2.0 everywhere; dollars = NQ 20 / ES 50 per point; per-year = total x 12 / 19.2 on the full window.",
        "Protocol: size any rule on discovery (2025-04-01..2026-05-31) with its pre-registered parameter, score the vault (2026-06-01..2026-11-06) once; NQ is primary, ES is a same-sign replication arm.",
    ]
    with open(os.path.join(OUT, "README_grade_a.md"), "w") as fh:
        fh.write("\n".join(readme) + "\n")
    print(f"\nwrote trades_honest_*.csv, candidates_*.csv, baseline_summary.json, README_grade_a.md to {OUT} in {summary['runtime_s']:.0f} s")
    return summary


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or ("NQ", "ES"))
