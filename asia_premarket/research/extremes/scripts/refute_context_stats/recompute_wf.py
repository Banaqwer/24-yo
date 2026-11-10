"""Independent walk-forward recompute for the model-based claims (C1, C2, C3, C4, C5, C6, C9, C10).
Differences from the lens: own code, refit at every month start (same) AND an every-session refit variant for key models,
plus a non-parametric expanding 7-bucket lookup for the scaled distance."""
import sys, warnings
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, QuantileRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

warnings.filterwarnings("ignore")
sys.path.insert(0, "research/extremes/scripts/refute_context_stats")
from recompute_desc import load

rng = np.random.default_rng(7)
MIN_TRAIN = 150
COMPACT = ["mag", "is_down", "ext_in_dir", "vwap_in_dir", "stretch20_in_dir", "stretch50_in_dir", "ret5_in_dir",
           "gap_in_dir", "post_in_dir", "prior_asia_in_dir", "overnight_in_dir", "n225_in_dir", "sox_in_dir",
           "nqes_in_dir", "yen_in_dir", "yield_in_dir", "vix_consistent", "vix_z20", "vix", "rv_ratio",
           "rth_range_atr", "abs_streak", "rth_vol_rel", "asia_rng_med20", "fomc_today", "tier1_data_today",
           "tier1_data_tomorrow", "fomc_tomorrow", "megacap_earnings_tonight", "boj_tonight", "opex_today",
           "witching_today", "sunday_open", "pre_holiday", "month_end"]
UNI = ["mag", "is_down", "rth_ret", "ext_in_dir", "vwap_in_dir", "stretch20_in_dir", "stretch50_in_dir", "ret5_in_dir",
       "abs_streak", "gap_in_dir", "post_in_dir", "abs_post", "vix", "vix_z20", "rv_ratio", "rth_range_atr", "rth_vol_rel",
       "asia_rng_med20", "yen_in_dir", "yield_in_dir", "n225_in_dir", "sox_in_dir", "nqes_in_dir", "prior_asia_in_dir",
       "prior_eur_ret", "overnight_in_dir", "dist_rth_high0", "dist_rth_low0", "dist_rth_vwap0", "rth_range_bp",
       "sunday_open", "is_monday", "clv", "z_sma20", "ret_5d", "vix_chg", "dist_prior_asia_high0", "dist_prior_asia_low0",
       "megacap_earnings_tonight", "pre_holiday", "dow", "fomc_tomorrow", "sd_high", "sd_low"]


def prep(sym):
    df = load(sym)
    ref = df["ref_close"]
    df["dist_rth_vwap0"] = (df["lvl_rth_vwap"] / ref - 1) * 1e4
    df["dist_prior_asia_high0"] = (df["lvl_prior_asia_high"] / ref - 1) * 1e4
    df["dist_prior_asia_low0"] = (df["lvl_prior_asia_low"] / ref - 1) * 1e4
    df["is_monday"] = (df["dow"] == 0).astype(int)
    df["log_sd_high"] = np.log1p(df["sd_high"].clip(lower=0))
    df["log_sd_low"] = np.log1p(df["sd_low"].clip(lower=0))
    return df


def refit_points(idx, every_session=False):
    if every_session:
        return list(range(MIN_TRAIN, len(idx)))
    months = idx.to_period("M")
    return [i for i in range(len(idx)) if i >= MIN_TRAIN and (i == MIN_TRAIN or months[i] != months[i - 1])]


def wf_logit(df, feats, t, C=1.0, every_session=False):
    y = df[t].values.astype(float); X = df[feats].values.astype(float)
    pred = np.full(len(df), np.nan)
    starts = refit_points(df.index, every_session); bounds = starts + [len(df)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        ytr = y[:a]; Xtr = X[:a]; ok = ~np.isnan(ytr)
        if ok.sum() < 50 or len(np.unique(ytr[ok])) < 2:
            continue
        m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=C, max_iter=3000))
        m.fit(Xtr[ok], ytr[ok]); pred[a:b] = m.predict_proba(X[a:b])[:, 1]
    return pred


def wf_bucket(df, scol, t, edges):
    """Expanding-window bucket lookup (non-parametric), refit every session."""
    x = df[scol].values; y = df[t].values.astype(float)
    b = np.digitize(x, edges)  # bucket id
    pred = np.full(len(df), np.nan)
    for i in range(MIN_TRAIN, len(df)):
        if np.isnan(x[i]):
            continue
        past = (b[:i] == b[i]) & ~np.isnan(x[:i]) & ~np.isnan(y[:i])
        if past.sum() >= 5:
            # Laplace-smoothed toward the expanding base rate
            base = np.nanmean(y[:i]); k = 2.0
            pred[i] = (y[:i][past].sum() + k * base) / (past.sum() + k)
        else:
            pred[i] = np.nanmean(y[:i])
    return pred


def base_rate(df, t):
    exp = df[t].expanding().mean().shift(1).values
    p = np.full(len(df), np.nan); p[MIN_TRAIN:] = exp[MIN_TRAIN:]; return p


def brier_skill(y, p, pb, half, B=2000):
    m = ~np.isnan(p) & ~np.isnan(y) & ~np.isnan(pb)
    e1 = (p[m] - y[m]) ** 2; e0 = (pb[m] - y[m]) ** 2
    idx = rng.integers(0, m.sum(), (B, m.sum()))
    s = 1 - e1[idx].mean(1) / e0[idx].mean(1)
    h1 = half[m] == "H1"
    return dict(n=int(m.sum()), skill=1 - e1.mean() / e0.mean(), lo=np.quantile(s, 0.05), hi=np.quantile(s, 0.95),
                h1=1 - e1[h1].mean() / e0[h1].mean(), h2=1 - e1[~h1].mean() / e0[~h1].mean(), brier=e1.mean(), brier_base=e0.mean())


def fmt(name, r):
    return f"  {name:45s} n={r['n']} brier={r['brier']:.4f} base={r['brier_base']:.4f} skill={r['skill']:+.3f} CI90=[{r['lo']:+.3f},{r['hi']:+.3f}] H1={r['h1']:+.3f} H2={r['h2']:+.3f}"


def run_logit(sym):
    df = prep(sym); half = df["half"].values
    print(f"\n######## {sym} walk-forward logistic (n={len(df)}, OOS from session {MIN_TRAIN})")
    LEVELS = ["dist_rth_high0", "dist_rth_low0", "dist_rth_vwap0", "rth_range_bp", "asia_rng_med20", "vix"]
    specs = {
        "high_above_rth_high": [("uni:dist_rth_high0", ["dist_rth_high0"], 1.0, False), ("uni:sd_high", ["sd_high"], 1.0, False),
                                ("uni:log_sd_high", ["log_sd_high"], 1.0, False), ("uni:log_sd_high every-session", ["log_sd_high"], 1.0, True),
                                ("uni:is_down", ["is_down"], 1.0, False), ("uni:clv", ["clv"], 1.0, False),
                                ("log_sd_high + is_down", ["log_sd_high", "is_down"], 1.0, False), ("levels", LEVELS, 1.0, False),
                                ("bucket7:sd_high", None, None, None)],
        "low_below_rth_low": [("uni:dist_rth_low0", ["dist_rth_low0"], 1.0, False), ("uni:sd_low", ["sd_low"], 1.0, False),
                              ("uni:log_sd_low", ["log_sd_low"], 1.0, False), ("uni:log_sd_low every-session", ["log_sd_low"], 1.0, True),
                              ("uni:is_down", ["is_down"], 1.0, False), ("log_sd_low + is_down", ["log_sd_low", "is_down"], 1.0, False),
                              ("levels", LEVELS, 1.0, False), ("bucket7:sd_low", None, None, None)],
        "low_by_tokyo_open": [("uni:sunday_open", ["sunday_open"], 1.0, False), ("uni:sunday_open every-session", ["sunday_open"], 1.0, True),
                              ("uni:is_monday", ["is_monday"], 1.0, False), ("sun+mon", ["sunday_open", "is_monday"], 1.0, False), ("compact", COMPACT, 0.3, False)],
        "low_in_first_bar": [("uni:sunday_open", ["sunday_open"], 1.0, False), ("uni:is_monday", ["is_monday"], 1.0, False),
                             ("sun+mon", ["sunday_open", "is_monday"], 1.0, False), ("compact", COMPACT, 0.3, False)],
        "hi_first": [("uni:is_down", ["is_down"], 1.0, False), ("uni:is_monday", ["is_monday"], 1.0, False), ("uni:sunday_open", ["sunday_open"], 1.0, False),
                     ("uni:fomc_tomorrow", ["fomc_tomorrow"], 1.0, False), ("sun+mon+fomc", ["sunday_open", "is_monday", "fomc_tomorrow"], 1.0, False),
                     ("sun+mon+fomc+is_down", ["sunday_open", "is_monday", "fomc_tomorrow", "is_down"], 1.0, False),
                     ("timing6", ["sunday_open", "is_monday", "fomc_tomorrow", "rth_ret_z", "asia_rng_prev", "rth_range_atr"], 1.0, False),
                     ("compact", COMPACT, 0.3, False)],
        "close_with_dir": [("uni:is_down", ["is_down"], 1.0, False), ("uni:is_down every-session", ["is_down"], 1.0, True)],
        "close_top20": [("uni:is_down", ["is_down"], 1.0, False)],
        "high_in_first_bar": [("compact", COMPACT, 0.3, False), ("compact C=0.03", COMPACT, 0.03, False)],
        "high_in_last_bar": [("compact", COMPACT, 0.3, False), ("compact C=0.03", COMPACT, 0.03, False)],
        "low_in_last_bar": [("compact", COMPACT, 0.3, False), ("compact C=0.03", COMPACT, 0.03, False)],
        "high_by_tokyo_open": [("compact", COMPACT, 0.3, False), ("compact C=0.03", COMPACT, 0.03, False)],
    }
    for t, models in specs.items():
        y = df[t].values.astype(float); pb = base_rate(df, t)
        print(f" target {t}: base rate {np.nanmean(y):.3f}")
        for name, feats, C, es in models:
            if feats is None:
                scol = name.split(":")[1]
                p = wf_bucket(df, scol, t, [0.10, 0.25, 0.50, 0.75, 1.0, 1.5])
            else:
                p = wf_logit(df, feats, t, C, es)
            print(fmt(name, brier_skill(y, p, pb, half)))
    # C10: best single-feature skill over all UNI features for the timing targets (monthly refit, like the lens)
    print(" C10: single-feature sweep over", len(UNI), "features x 6 timing targets")
    for t in ["high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar", "high_by_tokyo_open", "low_by_tokyo_open"]:
        y = df[t].values.astype(float); pb = base_rate(df, t)
        res = []
        for f in UNI:
            if f not in df.columns:
                continue
            r = brier_skill(y, wf_logit(df, [f], t), pb, half); res.append((f, r["skill"], r["lo"], r["hi"], r["h1"], r["h2"]))
        res = sorted(res, key=lambda z: -z[1])
        print(f"  {t}: best 3: " + "; ".join(f"{f} {s:+.3f} [{lo:+.3f},{hi:+.3f}] H1 {h1:+.3f} H2 {h2:+.3f}" for f, s, lo, hi, h1, h2 in res[:3]) +
              f" | n features with CI lo > 0: {sum(1 for z in res if z[2] > 0)}; n with |skill|<=0.01: {sum(1 for z in res if abs(z[1]) <= 0.01)}/{len(res)}")


def pinball(y, q, tau):
    d = y - q; return np.maximum(tau * d, (tau - 1) * d)


def wf_quant(df, feats, t, tau, alpha=0.01):
    y = df[t].values.astype(float); X = df[feats].values.astype(float)
    pred = np.full(len(df), np.nan)
    starts = refit_points(df.index); bounds = starts + [len(df)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        ok = ~np.isnan(y[:a])
        m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), QuantileRegressor(quantile=tau, alpha=alpha, solver="highs"))
        m.fit(X[:a][ok], y[:a][ok]); pred[a:b] = m.predict(X[a:b])
    return pred


def run_quant(sym):
    df = prep(sym); half = df["half"].values
    print(f"\n######## {sym} walk-forward quantile regression")
    SETS = {"scale": ["asia_rng_med20"],
            "scale+vol": ["asia_rng_med20", "vix", "rth_range_atr", "mag", "rv_ratio"],
            "levels": ["asia_rng_med20", "vix", "rth_range_atr", "mag", "rv_ratio", "dist_rth_high0", "dist_rth_low0", "dist_rth_vwap0", "is_down", "ext_in_dir", "post_in_dir", "sunday_open"],
            "vol5(log)": ["log_vix", "log_med20", "log_rth_range", "abs_post", "dist_20d_high"]}
    df["log_vix"] = np.log(df["vix"]); df["log_med20"] = np.log(df["asia_rng_med20"]); df["log_rth_range"] = np.log(df["rth_range_bp"].clip(lower=1))
    for t in ["rng_bp", "hi_bp", "lo_bp"]:
        y = df[t].values.astype(float)
        for tau in [0.1, 0.25, 0.5, 0.75, 0.9]:
            pb = df[t].expanding().quantile(tau).shift(1).values.copy(); pb[:MIN_TRAIN] = np.nan
            line = f"  {t} tau={tau}:"
            for name, feats in SETS.items():
                p = wf_quant(df, feats, t, tau)
                m = ~np.isnan(p) & ~np.isnan(y) & ~np.isnan(pb)
                e1 = pinball(y[m], p[m], tau); e0 = pinball(y[m], pb[m], tau)
                idx = rng.integers(0, m.sum(), (1000, m.sum())); s = 1 - e1[idx].mean(1) / e0[idx].mean(1)
                h1 = half[m] == "H1"
                line += f" {name} {1-e1.mean()/e0.mean():+.3f}[{np.quantile(s,0.05):+.3f},{np.quantile(s,0.95):+.3f}] H1 {1-e1[h1].mean()/e0[h1].mean():+.3f} H2 {1-e1[~h1].mean()/e0[~h1].mean():+.3f} cov {np.mean(y[m] <= p[m]):.2f} |"
            print(line)


if __name__ == "__main__":
    what = sys.argv[1]; syms = sys.argv[2:] or ["NQ"]
    for s in syms:
        if what in ("logit", "all"):
            run_logit(s)
        if what in ("quant", "all"):
            run_quant(s)
