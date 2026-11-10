"""
OTE sensitivity / ablation study
================================

Companion to ote_validation_pipeline.py. Answers "is the negative result an artefact of
one modelling choice?" by re-running the OTE engine with the choices flipped:

  1. Fill assumption      : bar touching both stop and target -> stop first (default) vs target first
  2. Full-sample grid     : all 144 parameter sets on the whole history (in-sample best case):
                            what share is profitable, and the best set per market
  3. Rule ablation        : each checklist rule switched off one at a time
                            (no HTF bias, no structure-break requirement, no consolidation wait)
  4. Session filter       : index futures restricted to the New York morning (08:00-11:00 ET),
                            which is when the video's examples trade

Usage: python ote_sensitivity.py            -> ote_validation_results/OTE_SENSITIVITY.md
"""

from __future__ import annotations

import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from ote_validation_pipeline import CONFIG, DEFAULT_CFG, get_data, run_backtest, grid_combos, years_spanned, metrics

OUT = Path(CONFIG["out_dir"])


def total_r(tr: pd.DataFrame) -> float:
    return float(tr["r_net"].sum()) if len(tr) else 0.0


def _combo(args):
    df, htf, cost, combo = args
    _, tr = run_backtest(df, htf, cost, **combo)
    return combo, total_r(tr), int(len(tr)), (float((tr["r_net"] > 0).mean() * 100) if len(tr) else 0.0)


def main() -> int:
    workers = max(1, (os.cpu_count() or 2) - 1)
    markets = [(t, s, "hourly") for t, s in CONFIG["hourly_markets"].items()] + \
              [(t, s, "daily") for t, s in CONFIG["daily_markets"].items()]
    combos = grid_combos(CONFIG["wfo"]["grid"])
    rows_fill, rows_grid, rows_abl, rows_sess = [], [], [], []

    for ticker, sector, tf in markets:
        spec = CONFIG[tf]
        df = get_data(ticker, spec["interval"], spec["period"])
        if df is None:
            continue
        cost = CONFIG["costs_per_side"][sector]
        key = f"{ticker} {tf}"
        print(f"▶ {key}", flush=True)

        # 1. fill assumption
        _, a = run_backtest(df, spec["htf"], cost)
        _, b = run_backtest(df, spec["htf"], cost, ambiguous_bar="tp_first")
        both = int(((a["state"] == "loss") & (b["state"] == "win")).sum()) if len(a) == len(b) else -1
        rows_fill.append({"market": key, "trades": len(a), "sl_first_R": round(total_r(a), 1),
                          "tp_first_R": round(total_r(b), 1), "ambiguous_bars": both})

        # 2. full-sample grid (in-sample)
        tasks = [(df, spec["htf"], cost, c) for c in combos]
        with ProcessPoolExecutor(max_workers=workers) as ex:
            scored = list(ex.map(_combo, tasks, chunksize=6))
        scored = [s for s in scored if s[2] >= 10]
        pos = sum(s[1] > 0 for s in scored)
        best = max(scored, key=lambda s: s[1])
        worst = min(scored, key=lambda s: s[1])
        med = float(np.median([s[1] for s in scored]))
        rows_grid.append({"market": key, "sets": len(scored), "positive_pct": round(pos / len(scored) * 100, 0),
                          "median_R": round(med, 1), "best_R": round(best[1], 1), "best_trades": best[2],
                          "best_win": round(best[3], 0), "best_params": best[0], "worst_R": round(worst[1], 1)})

        # 3. rule ablation
        variants = {
            "default": {},
            "no HTF bias": {"bias_mode": "none"},
            "no structure break": {"require_structure_break": False},
            "no consolidation (touch 0.705)": {"confirm_mode": "touch"},
            "reclaim close instead": {"confirm_mode": "reclaim"},
            "require sweep": {"require_sweep": True},
            "scalp to range extreme (tp0)": {"eval_tp_index": 0},
            "target -0.62 (tp2)": {"eval_tp_index": 2},
            "symmetrical -1.0 (tp3)": {"eval_tp_index": 3},
            "range bias (discount/premium)": {"bias_mode": "range"},
        }
        row = {"market": key}
        for name, over in variants.items():
            _, tr = run_backtest(df, spec["htf"], cost, **over)
            row[name] = f"{total_r(tr):+.1f} ({len(tr)})"
        rows_abl.append(row)

        # 4. session filter for index futures
        if sector == "INDEX_FUT":
            for sess in (("08:00", "11:00"), ("09:00", "12:00"), ("13:00", "16:00")):
                _, tr = run_backtest(df, spec["htf"], cost, session=sess)
                rows_sess.append({"market": key, "session_ET": f"{sess[0]}-{sess[1]}", "trades": len(tr),
                                  "total_R": round(total_r(tr), 1),
                                  "win_pct": round(float((tr["r_net"] > 0).mean() * 100), 1) if len(tr) else 0.0})

    fill, grid, abl, sess = map(pd.DataFrame, (rows_fill, rows_grid, rows_abl, rows_sess))
    L = ["# OTE Sensitivity / Ablation Study\n",
         "All numbers are total net R (sum of R-multiples after costs) over the full history, "
         "default rules unless stated. Positive = profitable. Trade counts in brackets.\n",
         "## 1. Fill assumption on bars that touch both stop and target\n",
         fill.to_markdown(index=False), "",
         f"Across all markets: stop-first {fill['sl_first_R'].sum():+.1f} R, target-first {fill['tp_first_R'].sum():+.1f} R "
         f"({fill['ambiguous_bars'].sum()} ambiguous bars out of {fill['trades'].sum()} trades).\n",
         "## 2. Full-sample parameter grid (144 sets, in-sample, best case)\n",
         grid.drop(columns=["best_params"]).to_markdown(index=False), "",
         "Best parameter set per market (in-sample, so optimistic):", ""]
    for r in rows_grid:
        L.append(f"- {r['market']}: {r['best_params']} -> {r['best_R']:+.1f} R, {r['best_trades']} trades, win {r['best_win']:.0f}%")
    L += ["", "## 3. One rule switched at a time\n", abl.to_markdown(index=False), ""]
    tot = {}
    for name in variants:
        tot[name] = sum(float(v.split(" ")[0]) for v in abl[name])
    L.append("Sum over all markets:")
    for name, v in tot.items():
        L.append(f"- {name}: {v:+.1f} R")
    L += ["", "## 4. Session filter, index futures (hourly bars, exchange time)\n",
          sess.to_markdown(index=False) if len(sess) else "n/a", ""]
    path = OUT / "OTE_SENSITIVITY.md"
    path.write_text("\n".join(L), encoding="utf-8")
    (OUT / "ote_sensitivity.json").write_text(json.dumps({"fill": rows_fill, "grid": rows_grid, "ablation": rows_abl,
                                                           "session": rows_sess}, indent=2, default=str))
    print(f"\nreport: {path}")
    print("\n".join(L[-20:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
