"""
═══════════════════════════════════════════════════════════════════════════════
OTE VALIDATION PIPELINE
Backtest + Monte Carlo + Walk-Forward for the ICT Optimal Trade Entry indicator
═══════════════════════════════════════════════════════════════════════════════

Engine : ote_indicator.py (compute_ote)
Mirror : hurst_validation_pipeline.py (same four pillars, same pass thresholds)

Pillars
  1. Backtest with costs   : every confirmed OTE entry, 1% of equity risked per trade,
                             stop just beyond the leg origin, target = chosen fib expansion
  2. Benchmark             : buy-and-hold return and max drawdown over the same bars
  3. Monte Carlo           : 1000 bootstrap resamples of the realised trade R-multiples
                             (profitable %, median return, worst 5% drawdown, p-value of
                             mean R <= 0)
  4. Walk-forward          : (a) default rules on 4 sequential out-of-sample periods
                             (b) real walk-forward optimisation: pick the best parameter set
                                 on a train window, apply it unchanged to the next test
                                 window, roll forward

Data : yfinance. Hourly bars (2 years, 4h bias) for futures / FX / crypto,
       daily bars (15 years, weekly bias) for ETFs, stocks and BTC.

Usage:
    python ote_validation_pipeline.py                 # full run
    python ote_validation_pipeline.py --quick         # 3 markets, small grid
    python ote_validation_pipeline.py --markets NQ=F,EURUSD=X --no-wfo
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from ote_indicator import OTEConfig, compute_ote, load_yfinance  # noqa: E402

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
CONFIG = {
    "initial_capital": 100_000,
    "risk_per_trade": 0.01,            # 1% of equity risked per trade (R-based sizing)

    "hourly": {"interval": "1h", "period": "730d", "htf": "4h"},
    "daily":  {"interval": "1d", "period": "15y",  "htf": "7D"},

    "hourly_markets": {
        "NQ=F": "INDEX_FUT", "ES=F": "INDEX_FUT", "GC=F": "METALS", "CL=F": "ENERGY",
        "EURUSD=X": "FX", "GBPUSD=X": "FX", "USDJPY=X": "FX",
        "BTC-USD": "CRYPTO", "ETH-USD": "CRYPTO",
    },
    "daily_markets": {
        "SPY": "ETF", "QQQ": "ETF", "GLD": "ETF", "TLT": "ETF",
        "NVDA": "STOCK", "AAPL": "STOCK", "BTC-USD": "CRYPTO",
    },

    # round-trip cost as a fraction of price per side
    "costs_per_side": {
        "INDEX_FUT": 0.00005, "METALS": 0.0001, "ENERGY": 0.0002,
        "FX": 0.00005, "CRYPTO": 0.001, "ETF": 0.0005, "STOCK": 0.0005,
    },

    "mc_simulations": 1000,
    "mc_seed": 42,

    "wf_periods": 4,                   # sequential OOS periods with the default rules

    "wfo": {                           # walk-forward optimisation
        "train_frac": 0.50, "test_frac": 0.25, "step_frac": 0.25,
        "min_train_trades": 15,
        "grid": {
            "swing_len": [4, 5, 7, 10],
            "confirm_mode": ["consolidation", "reclaim", "touch"],
            "eval_tp_index": [0, 1, 2],
            "min_leg_atr": [1.5, 2.5],
            "require_sweep": [False, True],
        },
    },

    # same thresholds as hurst_validation_pipeline.py
    "thresholds": {
        "sharpe": 0.6, "sortino": 0.8, "win_rate": 42.0, "profit_factor": 1.4,
        "max_drawdown": -35.0, "expectancy": 0.0, "min_trades": 12, "avg_r_multiple": 0.3,
        "mc_profitable_pct": 70.0, "wf_positive_periods": 2, "dd_reduction": 5.0,
    },
    "out_dir": "ote_validation_results",
}

DEFAULT_CFG = dict(swing_len=5, min_leg_atr=1.5, confirm_mode="consolidation", confirm_bars=2,
                   eval_tp_index=1, require_structure_break=True, require_sweep=False,
                   bias_mode="structure", max_wait_bars=80, max_hold_bars=200)

CACHE_DIR = Path(os.environ.get("OTE_DATA_CACHE", "/tmp/ote_data_cache"))


# ── DATA ──────────────────────────────────────────────────────────────────────
def get_data(ticker: str, interval: str, period: str) -> pd.DataFrame | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = CACHE_DIR / f"{ticker}_{interval}_{period}.pkl"
    if f.exists():
        return pd.read_pickle(f)
    try:
        df = load_yfinance(ticker, interval, period)
    except Exception as e:  # noqa: BLE001
        print(f"   data error {ticker}: {e}")
        return None
    if df is None or len(df) < 500:
        return None
    df.to_pickle(f)
    return df


def years_spanned(index: pd.DatetimeIndex) -> float:
    return max((index[-1] - index[0]).total_seconds() / (365.25 * 86400), 1e-6)


# ── BACKTEST ─────────────────────────────────────────────────────────────────
def trades_from_result(res, cost_side: float) -> pd.DataFrame:
    """One row per closed trade with gross and net (after costs) R multiples."""
    rows = []
    idx = res.frame.index
    for s in res.setups:
        if s.r_multiple is None or s.entry_idx is None or s.exit_idx is None:
            continue
        risk = abs(s.entry_price - s.sl)
        cost_r = (2 * cost_side * s.entry_price) / risk if risk > 0 else 0.0
        rows.append({
            "entry_time": idx[s.entry_idx], "exit_time": idx[s.exit_idx],
            "direction": s.direction, "entry": s.entry_price, "sl": s.sl, "exit": s.exit_price,
            "state": s.state, "r_gross": s.r_multiple, "cost_r": cost_r,
            "r_net": s.r_multiple - cost_r, "bars_held": s.exit_idx - s.entry_idx,
            "swept": s.swept_liquidity,
        })
    return pd.DataFrame(rows)


def equity_from_trades(r_net: np.ndarray, risk: float, initial: float) -> np.ndarray:
    eq = initial * np.cumprod(1.0 + risk * r_net)
    return np.insert(eq, 0, initial)


def metrics(trades: pd.DataFrame, years: float, risk: float, initial: float) -> dict | None:
    if trades is None or len(trades) == 0:
        return None
    r = trades["r_net"].values
    eq = equity_from_trades(r, risk, initial)
    rets = np.diff(eq) / eq[:-1]
    tpy = len(r) / years
    sharpe = rets.mean() / rets.std() * np.sqrt(tpy) if rets.std() > 0 else 0.0
    neg = rets[rets < 0]
    sortino = rets.mean() / neg.std() * np.sqrt(tpy) if len(neg) > 1 and neg.std() > 0 else 0.0
    roll = np.maximum.accumulate(eq)
    dd = (eq - roll) / roll * 100
    wins = r[r > 0]
    losses = r[r <= 0]
    pf = wins.sum() / abs(losses.sum()) if len(losses) and losses.sum() != 0 else 99.0
    max_cl = cur = 0
    for v in r:
        cur = cur + 1 if v <= 0 else 0
        max_cl = max(max_cl, cur)
    total_ret = (eq[-1] - initial) / initial * 100
    return {
        "total_return": round(total_ret, 2),
        "final_capital": round(eq[-1], 2),
        "n_trades": int(len(r)),
        "trades_per_year": round(tpy, 1),
        "win_rate": round(len(wins) / len(r) * 100, 2),
        "profit_factor": round(float(pf), 3),
        "expectancy": round(float(r.mean() * risk * initial), 2),   # $ per trade at initial equity
        "avg_r_multiple": round(float(r.mean()), 3),
        "avg_r_gross": round(float(trades["r_gross"].mean()), 3),
        "avg_cost_r": round(float(trades["cost_r"].mean()), 3),
        "total_r": round(float(r.sum()), 2),
        "sharpe": round(float(sharpe), 3),
        "sortino": round(float(sortino), 3),
        "max_drawdown": round(float(dd.min()), 2),
        "max_consec_loss": int(max_cl),
        "avg_bars_held": round(float(trades["bars_held"].mean()), 1),
        "long_share": round(float((trades["direction"] > 0).mean() * 100), 1),
    }


def benchmark(close: np.ndarray) -> dict:
    eq = close / close[0]
    roll = np.maximum.accumulate(eq)
    return {"bh_return": round((eq[-1] - 1) * 100, 2),
            "bh_max_dd": round(float(((eq - roll) / roll * 100).min()), 2)}


def run_backtest(df: pd.DataFrame, htf: str, cost_side: float, **cfg_over):
    cfg = OTEConfig(htf=htf, **{**DEFAULT_CFG, **cfg_over})
    res = compute_ote(df, cfg)
    return res, trades_from_result(res, cost_side)


# ── MONTE CARLO ───────────────────────────────────────────────────────────────
def monte_carlo(trades: pd.DataFrame, risk: float, initial: float) -> dict | None:
    if trades is None or len(trades) < 8:
        return None
    r = trades["r_net"].values
    n = len(r)
    rng = np.random.default_rng(CONFIG["mc_seed"])
    rets, dds, means = [], [], []
    for _ in range(CONFIG["mc_simulations"]):
        path = rng.choice(r, size=n, replace=True)
        eq = equity_from_trades(path, risk, initial)
        roll = np.maximum.accumulate(eq)
        rets.append((eq[-1] - initial) / initial * 100)
        dds.append(((eq - roll) / roll * 100).min())
        means.append(path.mean())
    rets, dds, means = map(np.array, (rets, dds, means))
    return {
        "profitable_pct": round(float((rets > 0).mean() * 100), 1),
        "median_return": round(float(np.median(rets)), 2),
        "worst_5pct": round(float(np.quantile(rets, 0.05)), 2),
        "best_5pct": round(float(np.quantile(rets, 0.95)), 2),
        "median_max_dd": round(float(np.median(dds)), 2),
        "worst_dd_5pct": round(float(np.quantile(dds, 0.05)), 2),
        "p_value_mean_r_le_0": round(float((means <= 0).mean()), 3),
        "n_simulations": CONFIG["mc_simulations"],
    }


# ── WALK-FORWARD (default rules, sequential OOS periods) ─────────────────────
def walk_forward_periods(df: pd.DataFrame, htf: str, cost_side: float) -> dict | None:
    k = CONFIG["wf_periods"]
    edges = np.linspace(0, len(df), k + 1).astype(int)
    out = []
    for i in range(k):
        part = df.iloc[edges[i]:edges[i + 1]]
        if len(part) < 300:
            continue
        _, tr = run_backtest(part, htf, cost_side)
        m = metrics(tr, years_spanned(part.index), CONFIG["risk_per_trade"], CONFIG["initial_capital"])
        bh = benchmark(part["close"].values)
        out.append({
            "period": f"{str(part.index[0])[:10]} → {str(part.index[-1])[:10]}",
            "n_trades": m["n_trades"] if m else 0,
            "return": m["total_return"] if m else 0.0,
            "total_r": m["total_r"] if m else 0.0,
            "win_rate": m["win_rate"] if m else 0.0,
            "positive": bool(m and m["total_r"] > 0),
            "bh_return": bh["bh_return"],
        })
    if not out:
        return None
    pos = sum(o["positive"] for o in out)
    return {"splits": out, "positive_periods": pos, "total_periods": len(out),
            "avg_oos_r": round(float(np.mean([o["total_r"] for o in out])), 2),
            "consistency": round(pos / len(out), 3)}


# ── WALK-FORWARD OPTIMISATION ─────────────────────────────────────────────────
def grid_combos(grid: dict) -> list[dict]:
    keys = list(grid)
    return [dict(zip(keys, vals)) for vals in itertools.product(*[grid[k] for k in keys])]


def _eval_combo(args):
    df, htf, cost_side, combo = args
    _, tr = run_backtest(df, htf, cost_side, **combo)
    return combo, (float(tr["r_net"].sum()) if len(tr) else 0.0), int(len(tr))


def walk_forward_optimisation(df: pd.DataFrame, htf: str, cost_side: float, grid: dict,
                              workers: int) -> dict | None:
    w = CONFIG["wfo"]
    N = len(df)
    train, test, step = int(N * w["train_frac"]), int(N * w["test_frac"]), int(N * w["step_frac"])
    combos = grid_combos(grid)
    windows = []
    start = 0
    while start + train + test <= N:
        windows.append((start, start + train, start + train + test))
        start += step
    if not windows:
        return None

    results = []
    for (a, b, c) in windows:
        tr_df, te_df = df.iloc[a:b], df.iloc[b:c]
        tasks = [(tr_df, htf, cost_side, combo) for combo in combos]
        if workers > 1:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                scored = list(ex.map(_eval_combo, tasks, chunksize=4))
        else:
            scored = [_eval_combo(t) for t in tasks]
        eligible = [s for s in scored if s[2] >= w["min_train_trades"]] or scored
        best_combo, best_train_r, best_train_n = max(eligible, key=lambda s: s[1])
        # apply the chosen parameters unchanged to the unseen test window
        _, te_tr = run_backtest(te_df, htf, cost_side, **best_combo)
        _, te_def = run_backtest(te_df, htf, cost_side)
        oos_r = float(te_tr["r_net"].sum()) if len(te_tr) else 0.0
        def_r = float(te_def["r_net"].sum()) if len(te_def) else 0.0
        results.append({
            "train": f"{str(tr_df.index[0])[:10]} → {str(tr_df.index[-1])[:10]}",
            "test": f"{str(te_df.index[0])[:10]} → {str(te_df.index[-1])[:10]}",
            "best_params": best_combo,
            "train_r": round(best_train_r, 2), "train_trades": best_train_n,
            "oos_r": round(oos_r, 2), "oos_trades": int(len(te_tr)),
            "oos_win_rate": round(float((te_tr["r_net"] > 0).mean() * 100), 1) if len(te_tr) else 0.0,
            "default_oos_r": round(def_r, 2),
            "positive": oos_r > 0,
            "grid_positive_train_pct": round(float(np.mean([s[1] > 0 for s in scored]) * 100), 1),
        })
    pos = sum(r["positive"] for r in results)
    return {"windows": results, "positive_windows": pos, "total_windows": len(results),
            "sum_oos_r": round(sum(r["oos_r"] for r in results), 2),
            "sum_default_oos_r": round(sum(r["default_oos_r"] for r in results), 2),
            "n_combos": len(combos)}


# ── PASS / FAIL ───────────────────────────────────────────────────────────────
def pass_fail(m, bh, mc, wf, wfo):
    t = CONFIG["thresholds"]
    failed, score, total = [], 0, 11
    checks = [
        (m["sharpe"] >= t["sharpe"], f"Sharpe {m['sharpe']:.2f} < {t['sharpe']}"),
        (m["sortino"] >= t["sortino"], f"Sortino {m['sortino']:.2f} < {t['sortino']}"),
        (m["win_rate"] >= t["win_rate"], f"WinRate {m['win_rate']:.1f}% < {t['win_rate']}%"),
        (m["profit_factor"] >= t["profit_factor"], f"PF {m['profit_factor']:.2f} < {t['profit_factor']}"),
        (m["max_drawdown"] >= t["max_drawdown"], f"MaxDD {m['max_drawdown']:.1f}% worse than {t['max_drawdown']}%"),
        (m["avg_r_multiple"] > t["expectancy"], f"Expectancy {m['avg_r_multiple']:.2f}R <= 0"),
        (m["n_trades"] >= t["min_trades"], f"Only {m['n_trades']} trades (min {t['min_trades']})"),
        (bh["bh_max_dd"] - m["max_drawdown"] >= t["dd_reduction"],
         f"DD not reduced: {m['max_drawdown']:.1f}% vs B&H {bh['bh_max_dd']:.1f}%"),
    ]
    for ok, msg in checks:
        if ok:
            score += 1
        else:
            failed.append(msg)
    if mc:
        if mc["profitable_pct"] >= t["mc_profitable_pct"]:
            score += 1
        else:
            failed.append(f"MC profitable {mc['profitable_pct']:.1f}% < {t['mc_profitable_pct']}%")
    else:
        failed.append("MC: insufficient trades")
    if wf:
        if wf["positive_periods"] >= t["wf_positive_periods"]:
            score += 1
        else:
            failed.append(f"WF: {wf['positive_periods']}/{wf['total_periods']} OOS periods positive")
    else:
        failed.append("WF: insufficient data")
    if wfo:
        if wfo["positive_windows"] >= max(1, wfo["total_windows"] - 1):
            score += 1
        else:
            failed.append(f"WFO: {wfo['positive_windows']}/{wfo['total_windows']} optimised OOS windows positive")
    else:
        failed.append("WFO: not run")
    grade = "A" if score >= 10 else "B" if score >= 8 else "C" if score >= 6 else "D" if score >= 4 else "F"
    return len(failed) == 0, failed, score, total, grade


# ── SINGLE MARKET ─────────────────────────────────────────────────────────────
def validate_market(ticker: str, sector: str, tf: str, grid: dict | None, workers: int) -> dict:
    spec = CONFIG[tf]
    t0 = time.time()
    df = get_data(ticker, spec["interval"], spec["period"])
    if df is None:
        return {"ticker": ticker, "sector": sector, "timeframe": tf, "status": "NO_DATA",
                "passed": False, "grade": "F", "score": "0/11"}
    cost = CONFIG["costs_per_side"][sector]
    res, trades = run_backtest(df, spec["htf"], cost)
    years = years_spanned(df.index)
    m = metrics(trades, years, CONFIG["risk_per_trade"], CONFIG["initial_capital"])
    if m is None or m["n_trades"] < 5:
        return {"ticker": ticker, "sector": sector, "timeframe": tf, "status": "INSUFFICIENT_TRADES",
                "passed": False, "grade": "F", "score": "0/11", "bars": len(df)}
    summ = res.summary()
    m["legs_marked"] = summ["setups_total"]
    m["legs_tapped"] = summ["tapped"]
    m["traps_invalidated"] = summ["invalidated_before_entry"]
    bh = benchmark(df["close"].values)
    mc = monte_carlo(trades, CONFIG["risk_per_trade"], CONFIG["initial_capital"])
    wf = walk_forward_periods(df, spec["htf"], cost)
    wfo = walk_forward_optimisation(df, spec["htf"], cost, grid, workers) if grid else None
    passed, failures, score, total, grade = pass_fail(m, bh, mc, wf, wfo)
    return {
        "ticker": ticker, "sector": sector, "timeframe": tf, "bars": len(df), "years": round(years, 2),
        "range": f"{str(df.index[0])[:10]} → {str(df.index[-1])[:10]}",
        "passed": passed, "grade": grade, "score": f"{score}/{total}",
        "status": "PASS" if passed else "FAIL",
        "metrics": m, "benchmark": bh, "monte_carlo": mc, "walk_forward": wf,
        "walk_forward_opt": wfo, "failures": failures, "seconds": round(time.time() - t0, 1),
    }


# ── REPORT ────────────────────────────────────────────────────────────────────
def write_report(results: list[dict], out_dir: Path, started: datetime) -> Path:
    L = []
    L.append("# OTE Indicator Validation Report\n")
    L.append(f"Generated {started:%Y-%m-%d %H:%M} UTC by `ote_validation_pipeline.py`. "
             f"Rules under test: `ote_indicator.py` defaults (swing 5, leg ≥ 1.5 ATR, structure break required, "
             f"consolidation 2 bars, stop beyond origin, target −0.27 expansion, HTF structure bias). "
             f"1% of equity risked per trade, costs per side as configured, no slippage beyond costs.\n")
    L.append("Pass thresholds are the same as `hurst_validation_pipeline.py` "
             "(Sharpe ≥ 0.6, Sortino ≥ 0.8, win rate ≥ 42%, PF ≥ 1.4, max DD ≥ −35%, positive expectancy, "
             "≥ 12 trades, DD at least 5 pts better than buy-and-hold, MC ≥ 70% profitable, "
             "≥ 2 of 4 OOS periods positive, optimised walk-forward OOS positive in all but one window).\n")

    ok = [r for r in results if r.get("metrics")]
    L.append("## Summary\n")
    L.append("| Market | TF | Bars | Trades | Win % | Avg R | Total R | PF | Sharpe | Max DD | B&H | MC prof % | MC p(R≤0) | WF +/n | WFO +/n (ΣR opt / default) | Score | Grade |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        if not r.get("metrics"):
            L.append(f"| {r['ticker']} | {r['timeframe']} | {r.get('bars','')} | {r['status']} |||||||||||| {r['score']} | {r['grade']} |")
            continue
        m, bh, mc, wf, wfo = r["metrics"], r["benchmark"], r["monte_carlo"], r["walk_forward"], r["walk_forward_opt"]
        L.append(f"| {r['ticker']} | {r['timeframe']} | {r['bars']} | {m['n_trades']} | {m['win_rate']:.1f} | "
                 f"{m['avg_r_multiple']:+.2f} | {m['total_r']:+.1f} | {m['profit_factor']:.2f} | {m['sharpe']:.2f} | "
                 f"{m['max_drawdown']:.1f}% | {bh['bh_return']:+.0f}% | "
                 f"{mc['profitable_pct'] if mc else 'n/a'} | {mc['p_value_mean_r_le_0'] if mc else 'n/a'} | "
                 f"{wf['positive_periods']}/{wf['total_periods'] if wf else 0} | "
                 f"{(str(wfo['positive_windows']) + '/' + str(wfo['total_windows']) + ' (' + format(wfo['sum_oos_r'], '+.1f') + ' / ' + format(wfo['sum_default_oos_r'], '+.1f') + ')') if wfo else 'n/a'} | "
                 f"{r['score']} | {r['grade']} |")
    n_pass = sum(r["passed"] for r in results)
    L.append(f"\n**{n_pass} of {len(results)} markets pass all criteria.** "
             f"Total net R across all markets with default rules: "
             f"{sum(r['metrics']['total_r'] for r in ok):+.1f} R over {sum(r['metrics']['n_trades'] for r in ok)} trades.\n")

    # pooled stats
    if ok:
        pooled_r = np.concatenate([np.array([0.0])] + [np.array([r["metrics"]["avg_r_multiple"]] * r["metrics"]["n_trades"]) for r in ok])
        L.append("## Pooled view\n")
        L.append(f"- Average net R per trade across all markets (trade-weighted): {pooled_r[1:].mean():+.3f} R")
        L.append(f"- Markets with positive expectancy: {sum(r['metrics']['avg_r_multiple'] > 0 for r in ok)} of {len(ok)}")
        L.append(f"- Markets where the optimised walk-forward beat the defaults out of sample: "
                 f"{sum(1 for r in ok if r['walk_forward_opt'] and r['walk_forward_opt']['sum_oos_r'] > r['walk_forward_opt']['sum_default_oos_r'])} "
                 f"of {sum(1 for r in ok if r['walk_forward_opt'])}")
        L.append(f"- Share of marked legs that were tapped: "
                 f"{sum(r['metrics']['legs_tapped'] for r in ok) / max(1, sum(r['metrics']['legs_marked'] for r in ok)) * 100:.0f}%; "
                 f"share of tapped legs that were traps (ran through the origin before confirming): "
                 f"{sum(r['metrics']['traps_invalidated'] for r in ok) / max(1, sum(r['metrics']['legs_tapped'] for r in ok)) * 100:.0f}%\n")

    L.append("## Per-market detail\n")
    for r in results:
        L.append(f"### {r['ticker']} ({r['sector']}, {r['timeframe']})  —  {r['status']} {r['score']} grade {r['grade']}\n")
        if not r.get("metrics"):
            continue
        m, bh, mc, wf, wfo = r["metrics"], r["benchmark"], r["monte_carlo"], r["walk_forward"], r["walk_forward_opt"]
        L.append(f"Range {r['range']}, {r['bars']} bars, {r['years']} years. Legs marked {m['legs_marked']}, tapped {m['legs_tapped']}, "
                 f"traps {m['traps_invalidated']}, trades {m['n_trades']} ({m['trades_per_year']}/yr, {m['long_share']}% long).\n")
        L.append(f"- Backtest: return {m['total_return']:+.1f}% (B&H {bh['bh_return']:+.1f}%), win rate {m['win_rate']:.1f}%, "
                 f"PF {m['profit_factor']:.2f}, avg R {m['avg_r_multiple']:+.3f} (gross {m['avg_r_gross']:+.3f}, cost {m['avg_cost_r']:.3f}), "
                 f"Sharpe {m['sharpe']:.2f}, Sortino {m['sortino']:.2f}, max DD {m['max_drawdown']:.1f}% (B&H {bh['bh_max_dd']:.1f}%), "
                 f"max consecutive losses {m['max_consec_loss']}, avg hold {m['avg_bars_held']} bars")
        if mc:
            L.append(f"- Monte Carlo ({mc['n_simulations']} bootstraps): profitable {mc['profitable_pct']}%, median return {mc['median_return']:+.1f}%, "
                     f"worst 5% {mc['worst_5pct']:+.1f}%, median max DD {mc['median_max_dd']:.1f}%, worst-5% DD {mc['worst_dd_5pct']:.1f}%, "
                     f"p(mean R ≤ 0) = {mc['p_value_mean_r_le_0']}")
        if wf:
            L.append(f"- Walk-forward, default rules: {wf['positive_periods']}/{wf['total_periods']} periods positive, avg {wf['avg_oos_r']:+.1f} R per period")
            for s in wf["splits"]:
                L.append(f"    - {s['period']}: {s['n_trades']} trades, {s['total_r']:+.1f} R, win {s['win_rate']:.0f}%, B&H {s['bh_return']:+.0f}%")
        if wfo:
            L.append(f"- Walk-forward optimisation ({wfo['n_combos']} parameter sets): {wfo['positive_windows']}/{wfo['total_windows']} OOS windows positive, "
                     f"Σ OOS {wfo['sum_oos_r']:+.1f} R vs defaults {wfo['sum_default_oos_r']:+.1f} R")
            for w in wfo["windows"]:
                bp = w["best_params"]
                L.append(f"    - train {w['train']} ({w['train_trades']} trades, {w['train_r']:+.1f} R, {w['grid_positive_train_pct']}% of grid positive) "
                         f"→ test {w['test']}: {w['oos_trades']} trades, {w['oos_r']:+.1f} R (defaults {w['default_oos_r']:+.1f} R); "
                         f"chosen swing={bp['swing_len']} confirm={bp['confirm_mode']} tp={bp['eval_tp_index']} leg≥{bp['min_leg_atr']}ATR sweep={bp['require_sweep']}")
        if r["failures"]:
            L.append("- Failed criteria: " + "; ".join(r["failures"]))
        L.append("")
    path = out_dir / "OTE_VALIDATION_REPORT.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return path


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true")
    p.add_argument("--markets", help="comma-separated tickers (hourly set unless --daily)")
    p.add_argument("--daily", action="store_true", help="with --markets: use the daily spec")
    p.add_argument("--no-wfo", action="store_true", help="skip walk-forward optimisation")
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = p.parse_args(argv)

    started = datetime.utcnow()
    out_dir = Path(CONFIG["out_dir"])
    out_dir.mkdir(exist_ok=True)

    jobs = []
    if a.markets:
        tf = "daily" if a.daily else "hourly"
        pool = CONFIG[f"{tf}_markets"]
        for t in a.markets.split(","):
            jobs.append((t, pool.get(t, "STOCK"), tf))
    else:
        jobs += [(t, s, "hourly") for t, s in CONFIG["hourly_markets"].items()]
        jobs += [(t, s, "daily") for t, s in CONFIG["daily_markets"].items()]
        if a.quick:
            jobs = [j for j in jobs if j[0] in ("NQ=F", "EURUSD=X", "SPY")]

    grid = None if a.no_wfo else CONFIG["wfo"]["grid"]
    if a.quick and grid:
        grid = {"swing_len": [5, 7], "confirm_mode": ["consolidation", "reclaim"],
                "eval_tp_index": [0, 1], "min_leg_atr": [1.5], "require_sweep": [False]}

    print("=" * 78)
    print(f"OTE VALIDATION PIPELINE  {len(jobs)} markets  workers={a.workers}  wfo={'off' if grid is None else len(grid_combos(grid))}")
    print("=" * 78)
    results = []
    for ticker, sector, tf in jobs:
        print(f"\n▶ {ticker} ({sector}, {tf}) ...", flush=True)
        r = validate_market(ticker, sector, tf, grid, a.workers)
        results.append(r)
        if r.get("metrics"):
            m = r["metrics"]
            print(f"   {r['status']} {r['score']} grade {r['grade']} | trades {m['n_trades']} win {m['win_rate']:.1f}% "
                  f"avgR {m['avg_r_multiple']:+.3f} totalR {m['total_r']:+.1f} PF {m['profit_factor']:.2f} "
                  f"Sharpe {m['sharpe']:.2f} DD {m['max_drawdown']:.1f}% | MC {r['monte_carlo']['profitable_pct'] if r['monte_carlo'] else 'n/a'}% "
                  f"| WF {r['walk_forward']['positive_periods'] if r['walk_forward'] else 0}/{r['walk_forward']['total_periods'] if r['walk_forward'] else 0}"
                  f"{(' | WFO ' + str(r['walk_forward_opt']['positive_windows']) + '/' + str(r['walk_forward_opt']['total_windows']) + ' ΣR ' + format(r['walk_forward_opt']['sum_oos_r'], '+.1f')) if r['walk_forward_opt'] else ''}"
                  f" | {r['seconds']}s", flush=True)
        else:
            print(f"   {r['status']}")

    (out_dir / "ote_validation_results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    path = write_report(results, out_dir, started)
    print("\n" + "=" * 78)
    print(f"PASS {sum(r['passed'] for r in results)} / {len(results)}   report: {path}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
