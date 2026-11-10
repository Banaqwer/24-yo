"""Walk-forward logistic fits for the binary targets.

Expanding window, refit at the start of each calendar month, first 150 sessions train-only.
Models per target:
  base         : expanding-window base rate
  uni:<f>      : one-feature logistic (standardised, L2 C=1)
  compact      : the project's FEATURE_COLS_COMPACT set (+ level distances), L2 C=0.3
  levels       : the level-distance set only (dist_rth_high0, dist_rth_low0, dist_with0, dist_against0, rth_range_bp, asia_rng_med20)
  small        : hand-picked 6-feature set
OOS Brier vs base, skill = 1 - Brier/Brier_base, by half, paired bootstrap CI on the skill.
"""
import sys, warnings
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer

warnings.filterwarnings("ignore")
OUT = "research/extremes/scripts/lens_context"
rng = np.random.default_rng(1)

COMPACT = ["mag", "is_down", "ext_in_dir", "vwap_in_dir", "stretch20_in_dir", "stretch50_in_dir", "ret5_in_dir",
           "gap_in_dir", "post_in_dir", "prior_asia_in_dir", "overnight_in_dir", "n225_in_dir", "sox_in_dir",
           "nqes_in_dir", "yen_in_dir", "yield_in_dir", "vix_consistent", "vix_z20", "vix", "rv_ratio",
           "rth_range_atr", "abs_streak", "rth_vol_rel", "asia_rng_med20", "fomc_today", "tier1_data_today",
           "tier1_data_tomorrow", "fomc_tomorrow", "megacap_earnings_tonight", "boj_tonight", "opex_today",
           "witching_today", "sunday_open", "pre_holiday", "month_end"]
LEVELS = ["dist_rth_high0", "dist_rth_low0", "dist_rth_vwap0", "rth_range_bp", "asia_rng_med20", "vix"]
UNI = ["mag", "is_down", "rth_ret", "ext_in_dir", "vwap_in_dir", "stretch20_in_dir", "stretch50_in_dir", "ret5_in_dir",
       "abs_streak", "gap_in_dir", "post_in_dir", "abs_post", "vix", "vix_z20", "rv_ratio", "rth_range_atr", "rth_vol_rel",
       "asia_rng_med20", "yen_in_dir", "yield_in_dir", "n225_in_dir", "sox_in_dir", "nqes_in_dir", "prior_asia_in_dir",
       "prior_eur_ret", "overnight_in_dir", "dist_rth_high0", "dist_rth_low0", "dist_rth_vwap0", "dist_with0",
       "dist_against0", "rth_range_bp", "sunday_open", "clv", "close_vs_vwap_rng", "z_sma20", "ret_5d", "vix_chg",
       "dist_prior_asia_high0", "dist_prior_asia_low0", "megacap_earnings_tonight", "pre_holiday", "dow"]
TARGETS = ["hi_first", "high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar",
           "high_above_rth_high", "low_below_rth_low", "high_by_tokyo_open", "low_by_tokyo_open",
           "with_first", "with_in_first_bar", "against_in_first_bar", "with_beyond_rth", "against_beyond_rth",
           "close_top20", "close_bot20", "close_with_dir"]
MIN_TRAIN = 150


def refit_points(idx):
    """Indices where a new month starts (after MIN_TRAIN)."""
    months = idx.to_period("M")
    starts = [i for i in range(len(idx)) if i >= MIN_TRAIN and (i == MIN_TRAIN or months[i] != months[i - 1])]
    return starts


def walk_forward(df, feats, t, C=1.0):
    y = df[t].values.astype(float)
    X = df[feats].values.astype(float)
    pred = np.full(len(df), np.nan)
    starts = refit_points(df.index)
    bounds = starts + [len(df)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        tr = slice(0, a)
        ytr = y[tr]; Xtr = X[tr]
        ok = ~np.isnan(ytr)
        if ok.sum() < 50 or len(np.unique(ytr[ok])) < 2:
            continue
        model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                              LogisticRegression(C=C, max_iter=2000))
        model.fit(Xtr[ok], ytr[ok])
        pred[a:b] = model.predict_proba(X[a:b])[:, 1]
    return pred


def base_rate(df, t):
    y = df[t]
    exp = y.expanding().mean().shift(1)
    pred = np.full(len(df), np.nan)
    pred[MIN_TRAIN:] = exp.values[MIN_TRAIN:]
    return pred


def brier(y, p):
    m = ~np.isnan(p) & ~np.isnan(y)
    return np.mean((p[m] - y[m]) ** 2), int(m.sum())


def skill_ci(y, p, pb, B=2000):
    m = ~np.isnan(p) & ~np.isnan(y) & ~np.isnan(pb)
    e1 = (p[m] - y[m]) ** 2; e0 = (pb[m] - y[m]) ** 2
    n = m.sum()
    idx = rng.integers(0, n, (B, n))
    s = 1 - e1[idx].mean(1) / e0[idx].mean(1)
    return tuple(np.quantile(s, [0.05, 0.95]))


def run(sym):
    df = pd.read_csv(f"{OUT}/frame_{sym}.csv", index_col=0, parse_dates=True).sort_index()
    rows = []
    preds = {}
    for t in TARGETS:
        y = df[t].values.astype(float)
        pb = base_rate(df, t)
        b0, n0 = brier(y, pb)
        h1 = (df["half"] == "H1").values; h2 = ~h1
        specs = {"base": (None, None)}
        for f in UNI:
            specs[f"uni:{f}"] = ([f], 1.0)
        specs["compact"] = (COMPACT, 0.3)
        specs["levels"] = (LEVELS, 1.0)
        specs["levels+compact"] = (list(dict.fromkeys(LEVELS + COMPACT)), 0.3)
        for name, (feats, C) in specs.items():
            if feats is None:
                p = pb
            else:
                p = walk_forward(df, feats, t, C)
            preds[(t, name)] = p
            b, n = brier(y, p)
            b1, n1 = brier(y[h1], p[h1]); b2, n2 = brier(y[h2], p[h2])
            bb1, _ = brier(y[h1], pb[h1]); bb2, _ = brier(y[h2], pb[h2])
            lo, hi = skill_ci(y, p, pb) if feats is not None else (np.nan, np.nan)
            rows.append(dict(sym=sym, target=t, model=name, n_oos=n, brier=b, brier_base=b0,
                             skill=1 - b / b0, skill_ci_lo=lo, skill_ci_hi=hi,
                             n_h1=n1, skill_h1=1 - b1 / bb1, n_h2=n2, skill_h2=1 - b2 / bb2,
                             base_rate=np.nanmean(y)))
        print(sym, t, "done")
    res = pd.DataFrame(rows)
    res.to_csv(f"{OUT}/wf_logit_{sym}.csv", index=False)
    pd.DataFrame({f"{t}|{m}": p for (t, m), p in preds.items()}, index=df.index).to_csv(f"{OUT}/wf_logit_preds_{sym}.csv")
    best = res[res.model != "base"].sort_values("skill", ascending=False).groupby("target").head(4)
    print(best[["target", "model", "n_oos", "base_rate", "brier_base", "brier", "skill", "skill_ci_lo", "skill_ci_hi", "skill_h1", "skill_h2"]].to_string())


if __name__ == "__main__":
    for sym in sys.argv[1:] or ["NQ", "ES"]:
        run(sym)
