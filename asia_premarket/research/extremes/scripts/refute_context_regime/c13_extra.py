import sys
import numpy as np, pandas as pd
sys.path.insert(0, "research/extremes/scripts/refute_context_regime")
from common import *
for sym in ("NQ", "ES"):
    f = load(sym)
    f["rng_rel"] = f["rng_bp"] / (f["asia_rng_med20"] * 1e4)
    f["hi_rel"] = f["hi_bp"] / (f["asia_rng_med20"] * 1e4); f["lo_rel"] = -f["lo_bp"] / (f["asia_rng_med20"] * 1e4)
    print(f"== {sym} Spearman(mag, rng_rel) by quarter:"); print(fmt(spearman_by_quarter(f, "mag", "rng_rel").T))
    print(fmt(spearman_by_regime(f, "mag", "rng_rel").T))
    print("leave-5:", leave5_spearman(f, "mag", "rng_rel"))
    d = f[["mag", "rng_rel", "vix", "rth_range_bp", "abs_post", "rng_bp", "asia_rng_med20"]].dropna()
    def partial(x, y, ctrl):
        X = np.column_stack([np.ones(len(d))] + [d[c].rank().values for c in ctrl])
        def resid(v):
            b, *_ = np.linalg.lstsq(X, v, rcond=None); return v - X @ b
        return stats.pearsonr(resid(d[x].rank().values), resid(d[y].rank().values))
    print("partial(mag, rng_rel | vix):", partial("mag", "rng_rel", ["vix"]))
    print("partial(mag, rng_rel | vix, rth_range_bp):", partial("mag", "rng_rel", ["vix", "rth_range_bp"]))
    print("partial(mag, rng_bp | vix, rth_range_bp, asia_rng_med20):", partial("mag", "rng_bp", ["vix", "rth_range_bp", "asia_rng_med20"]))
    print("Spearman(mag, rth_range_bp):", spearman(f.mag.values.astype(float), f.rth_range_bp.values.astype(float)))
    print("Spearman(rth_range_bp, rng_rel):", spearman(f.rth_range_bp.values.astype(float), f.rng_rel.values.astype(float)))
    print("Spearman(mag, hi_rel):", spearman(f.mag.values.astype(float), f.hi_rel.values.astype(float)), " (mag, lo_rel):", spearman(f.mag.values.astype(float), f.lo_rel.values.astype(float)))
    print("mag terciles -> median rng_rel:", f.groupby(pd.qcut(f.mag, 3, labels=["T1","T2","T3"]), observed=True)["rng_rel"].median().round(3).to_dict())
    # in-sample quantile regression of rng_bp: levels set with and without mag (pinball at q50), 5-fold CV by time blocks
    from sklearn.linear_model import QuantileRegressor
    cols = ["dist_rth_high0", "dist_rth_low0", "dist_rth_vwap0", "rth_range_bp", "asia_rng_med20", "vix"]
    dd = f[cols + ["mag", "rng_bp"]].dropna()
    n = len(dd); blocks = np.array_split(np.arange(n), 5)
    for tau in (0.5, 0.9):
        res = {}
        for lab, cc in (("levels", cols), ("levels+mag", cols + ["mag"])):
            loss = []
            for b in blocks:
                tr = np.setdiff1d(np.arange(n), b)
                m = QuantileRegressor(quantile=tau, alpha=0.01, solver="highs").fit(dd.iloc[tr][cc], dd.iloc[tr]["rng_bp"])
                q = m.predict(dd.iloc[b][cc]); y = dd.iloc[b]["rng_bp"].values
                loss.append(np.maximum(tau * (y - q), (tau - 1) * (y - q)))
            res[lab] = np.concatenate(loss).mean()
        print(f"  5-block CV pinball tau={tau}: levels {res['levels']:.3f} levels+mag {res['levels+mag']:.3f} (gain {1 - res['levels+mag']/res['levels']:+.3f})")
