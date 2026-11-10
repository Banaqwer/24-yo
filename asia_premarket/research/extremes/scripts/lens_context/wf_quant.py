"""Walk-forward quantile regression for hi_bp, lo_bp, rng_bp (and the direction-framed extensions).

Expanding window, monthly refit, first 150 sessions train only. Quantiles 0.1, 0.25, 0.5, 0.75, 0.9.
Benchmark: expanding-window unconditional quantile. Metric: OOS pinball loss; skill = 1 - pin/pin_base.
Feature sets: scale (asia_rng_med20), scale+vol (asia_rng_med20, vix, rth_range_atr, mag, rv_ratio),
              levels (scale+vol + dist_rth_high0, dist_rth_low0, dist_rth_vwap0, is_down, ext_in_dir),
              compact (project compact set + scale/levels).
"""
import sys, warnings
import numpy as np
import pandas as pd
from sklearn.linear_model import QuantileRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore")
OUT = "research/extremes/scripts/lens_context"
sys.path.insert(0, OUT)
from wf_logit import refit_points, MIN_TRAIN, COMPACT

rng = np.random.default_rng(2)
QS = [0.1, 0.25, 0.5, 0.75, 0.9]
SETS = {
    "scale": ["asia_rng_med20"],
    "scale+vol": ["asia_rng_med20", "vix", "rth_range_atr", "mag", "rv_ratio"],
    "levels": ["asia_rng_med20", "vix", "rth_range_atr", "mag", "rv_ratio", "dist_rth_high0", "dist_rth_low0",
               "dist_rth_vwap0", "is_down", "ext_in_dir", "post_in_dir", "sunday_open"],
    "compact": list(dict.fromkeys(COMPACT + ["dist_rth_high0", "dist_rth_low0", "dist_rth_vwap0"])),
}
TARGETS = ["hi_bp", "lo_bp", "rng_bp", "with_ext_bp", "against_ext_bp", "close_loc"]


def pinball(y, q, tau):
    d = y - q
    return np.mean(np.maximum(tau * d, (tau - 1) * d))


def wf_quant(df, feats, t, tau, alpha=0.01):
    y = df[t].values.astype(float); X = df[feats].values.astype(float)
    pred = np.full(len(df), np.nan)
    starts = refit_points(df.index); bounds = starts + [len(df)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        ytr = y[:a]; Xtr = X[:a]; ok = ~np.isnan(ytr)
        m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                          QuantileRegressor(quantile=tau, alpha=alpha, solver="highs"))
        m.fit(Xtr[ok], ytr[ok])
        pred[a:b] = m.predict(X[a:b])
    return pred


def base_quant(df, t, tau):
    y = df[t]
    exp = y.expanding().quantile(tau).shift(1)
    pred = np.full(len(df), np.nan); pred[MIN_TRAIN:] = exp.values[MIN_TRAIN:]
    return pred


def run(sym):
    df = pd.read_csv(f"{OUT}/frame_{sym}.csv", index_col=0, parse_dates=True).sort_index()
    rows = []; preds = {}
    h1 = (df["half"] == "H1").values; h2 = ~h1
    for t in TARGETS:
        y = df[t].values.astype(float)
        for tau in QS:
            pb = base_quant(df, t, tau); preds[(t, tau, "base")] = pb
            m0 = ~np.isnan(pb) & ~np.isnan(y)
            l0 = pinball(y[m0], pb[m0], tau)
            for name, feats in SETS.items():
                p = wf_quant(df, feats, t, tau); preds[(t, tau, name)] = p
                m = ~np.isnan(p) & ~np.isnan(y)
                l = pinball(y[m], p[m], tau)
                l1 = pinball(y[m & h1], p[m & h1], tau); b1 = pinball(y[m & h1], pb[m & h1], tau)
                l2 = pinball(y[m & h2], p[m & h2], tau); b2 = pinball(y[m & h2], pb[m & h2], tau)
                # paired bootstrap of the skill
                e1 = np.maximum(tau * (y[m] - p[m]), (tau - 1) * (y[m] - p[m]))
                e0 = np.maximum(tau * (y[m] - pb[m]), (tau - 1) * (y[m] - pb[m]))
                idx = rng.integers(0, m.sum(), (1000, m.sum()))
                s = 1 - e1[idx].mean(1) / e0[idx].mean(1)
                cov = np.mean(y[m] <= p[m])
                rows.append(dict(sym=sym, target=t, tau=tau, model=name, n_oos=int(m.sum()), pin_base=l0, pin=l,
                                 skill=1 - l / l0, skill_ci_lo=np.quantile(s, 0.05), skill_ci_hi=np.quantile(s, 0.95),
                                 skill_h1=1 - l1 / b1, skill_h2=1 - l2 / b2, oos_coverage=cov))
        print(sym, t, "done")
    res = pd.DataFrame(rows)
    res.to_csv(f"{OUT}/wf_quant_{sym}.csv", index=False)
    pd.DataFrame({f"{t}|{tau}|{m}": p for (t, tau, m), p in preds.items()}, index=df.index).to_csv(f"{OUT}/wf_quant_preds_{sym}.csv")
    print(res.pivot_table(index=["target", "tau"], columns="model", values="skill").round(3).to_string())


if __name__ == "__main__":
    for sym in sys.argv[1:] or ["NQ", "ES"]:
        run(sym)
