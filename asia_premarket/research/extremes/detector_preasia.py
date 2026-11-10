"""
detector_preasia.py -- the PRE-ASIA forecaster (decision point 17:xx ET, before the 18:00 reopen).

For RTH date D it forecasts, from 18:00-knowable inputs only, what the Asia session
18:00 D .. 02:59 D+1 ET will do with its high and its low:

  binary targets   high_in_first_bar, low_in_first_bar, high_in_last_bar, low_in_last_bar,
                   high_by_tokyo_open, low_by_tokyo_open, high_above_rth_high, low_below_rth_low,
                   hi_first
  quantiles        P20 / P50 / P80 of hi_bp, lo_bp and rng_bp (vs the 17:00 close)
  map of the night P(high in bar k), P(low in bar k) for k = 0..8

Inputs: the extremes table research/extremes/<SYM>_extremes.csv (one row per RTH date D, built by
asia_extremes.py) restricted to columns that are known at 18:00 ET: the features.py columns, the
calendar flags, the RTH reference levels and the 17:00 close.  Nothing from the session itself
(gap_open_bp, first_bar_*, any bar statistic) is used.

Evaluation discipline (mandatory and implemented here):
  * expanding-window walk-forward, refit at every calendar month, first MIN_TRAIN=120 sessions
    training-only, every reported number is strictly out of sample;
  * isotonic calibration is fitted ONLY on OOS predictions from months before the one being
    predicted (never pooled over the future); before MIN_CAL prior OOS rows exist the raw
    ensemble probability is used;
  * the multinomial "map" is shrunk toward the expanding histogram with a mixing weight chosen
    on prior OOS months only;
  * Brier is reported against the expanding base rate and against a DST-aware base rate
    (the "k-only" baseline: the unconditional rate for that target given tokyo_open_k);
  * contract-splice sessions and data-truncated (n_bars<9) sessions are excluded;
  * fixed random seeds; sklearn only (regularised logistic + HistGradientBoosting depth<=3,
    linear quantile regression).

Public API
  train_walk_forward(sym)      -> OOS predictions DataFrame (one row per session, all targets);
                                   oos.attrs["metrics"] holds the metric tables
  evaluate(oos, sym)           -> dict of metric tables recomputed from an OOS DataFrame
  predict_tonight(sym, date, h=None)
                               -> dict of probabilities, quantile levels (bp and price), the
                                   map of the night, and the top logistic contributions; when the
                                   date is not in the extremes table yet (night started, < 6 bars)
                                   or an hourly frame `h` is passed by the caller, the 18:00 row is
                                   built live from the hourly data (live=True); a contract-splice
                                   session raises ValueError
  __main__                     -> writes research/extremes/oos_preasia_<SYM>.csv and prints the
                                   metric tables for NQ and ES
  __main__ --now SYM [--date]  -> compact summary of predict_tonight for one night

Splice sessions come from asia_extremes.SPLICE_SESSIONS (shared with the intra-session detector).
"""
from __future__ import annotations

import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression, QuantileRegressor
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))


def _package_root() -> str:
    """The asia_premarket package root (two levels above this file), added to sys.path on import."""
    root = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


_package_root()
try:
    # sessions whose hourly bars carry a contract-splice artefact (RTH date D of the affected night):
    # the single list shared with the intra-session detector
    from asia_extremes import SPLICE_SESSIONS
except Exception:                                   # literal fallback only if the package import fails
    SPLICE_SESSIONS = {
        "NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16", "2025-09-17", "2025-12-16", "2025-12-17"],
        "ES": ["2025-09-16", "2025-09-17", "2025-12-16", "2025-12-17"],
    }

SEED = 0
MIN_TRAIN = 120          # first sessions that are training-only
MIN_CAL = 80             # prior OOS rows required before isotonic calibration is switched on
H1_END = pd.Timestamp("2025-09-01")   # OOS half split
N_BARS_FULL = 9
N_BOOT = 1000

BINARY_TARGETS = [
    "high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar",
    "high_by_tokyo_open", "low_by_tokyo_open", "high_above_rth_high", "low_below_rth_low", "hi_first",
]
LEVEL_TARGETS = ["high_above_rth_high", "low_below_rth_low"]
TIMING_TARGETS = [t for t in BINARY_TARGETS if t not in LEVEL_TARGETS]
QUANT_TARGETS = ["hi_bp", "lo_bp", "rng_bp"]
QUANTILES = (0.2, 0.5, 0.8)
MAP_TARGETS = ["hi_k", "lo_k"]

# ---------------------------------------------------------------------------------------------
# feature sets (all knowable at 18:00 ET; <= 20 each)
# ---------------------------------------------------------------------------------------------
FEATURES_FULL = [
    "lsd_high", "lsd_low",                      # log scaled distance 17:00 close -> RTH high / low (C1, C2, T10)
    "is_down", "clv", "rth_ret_bp",             # RTH direction / close location (C3, F5, F6)
    "vix", "asia_rng_med20_bp", "asia_rng_prev_bp", "dist_20d_high_pct", "rth_range_bp", "abs_post_bp",  # vol state (C4)
    "post_ret_bp",                              # signed 16:00-17:00 bar (E7)
    "sunday_open", "is_monday", "fomc_tomorrow", "fomc_today", "megacap_earnings_tonight", "holiday_eve",  # calendar (C5-C7, E1, E4, E6, F3)
    "abs_kospi_pct",                            # F4
    "is_dst",                                   # the Tokyo-open bar index moves with DST (rule 6)
]
FEATURES_TIMING = [
    "sunday_open", "is_monday", "fomc_tomorrow", "fomc_today", "megacap_earnings_tonight", "holiday_eve",
    "is_dst", "abs_post_bp", "abs_kospi_pct", "rth_ret_bp", "is_down", "vix",
]
FEATURES_QUANT = [
    "vix", "asia_rng_med20_bp", "asia_rng_prev_bp", "dist_20d_high_pct", "rth_range_bp", "abs_post_bp",
    "lsd_high", "lsd_low", "is_down", "clv",
    "sunday_open", "megacap_earnings_tonight", "holiday_eve", "fomc_today", "fomc_tomorrow", "is_dst",
]
FEATURE_SETS = {"full": FEATURES_FULL, "timing": FEATURES_TIMING, "quant": FEATURES_QUANT}
# pre-declared primary set per binary target (level targets: full; timing targets: timing)
PRIMARY_SET = {t: ("full" if t in LEVEL_TARGETS else "timing") for t in BINARY_TARGETS}
# a third, non-ML variant evaluated under the same walk-forward: the expanding conditional rate
# given the weekday (dow 0..4; Friday = Sunday reopen).  This is the "prior shift" encoding the
# characterisation phase proposed for the timing targets (C5, C6, E1, F2, C9, C10); cells with
# fewer than PRIOR_MIN_CELL training sessions fall back to the unconditional rate.
BINARY_SETS = ("full", "timing", "dow_prior")
PRIOR_MIN_CELL = 20
assert all(len(v) <= 20 for v in FEATURE_SETS.values())


# ---------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------
def load_extremes(sym: str, full_only: bool = True) -> pd.DataFrame:
    x = pd.read_csv(os.path.join(HERE, f"{sym}_extremes.csv"), index_col="date", parse_dates=True).sort_index()
    x = x[~x.index.isin(pd.to_datetime(SPLICE_SESSIONS.get(sym, [])))]
    if full_only:
        x = x[x["n_bars"] == N_BARS_FULL]
    return x


def make_features(x: pd.DataFrame) -> pd.DataFrame:
    """Engineer the 18:00-knowable feature frame from an extremes table (or a single-row frame)."""
    f = pd.DataFrame(index=x.index)
    ref = x["ref_close"].astype(float)
    med = x["asia_rng_med20"].astype(float)                      # fraction, ex-ante 20-session median Asia range
    dist_hi = x["lvl_rth_high"] / ref - 1.0                      # fraction above the 17:00 close
    dist_lo = 1.0 - x["lvl_rth_low"] / ref
    # log of the scaled distance; floor at ~0 so a 17:00 close beyond the RTH extreme reads as "zero distance"
    f["lsd_high"] = np.log(np.clip(dist_hi / med, -0.04, None) + 0.05)
    f["lsd_low"] = np.log(np.clip(dist_lo / med, -0.04, None) + 0.05)
    f["is_down"] = x["is_down"].astype(float)
    f["clv"] = x["clv"].astype(float)
    f["rth_ret_bp"] = x["rth_ret"].astype(float) * 1e4
    f["vix"] = x["vix"].astype(float)
    f["asia_rng_med20_bp"] = med * 1e4
    f["asia_rng_prev_bp"] = x["asia_rng_prev"].astype(float) * 1e4
    f["dist_20d_high_pct"] = x["dist_20d_high"].astype(float) * 100
    f["rth_range_bp"] = x["rth_range_bp"].astype(float)
    f["post_ret_bp"] = x["post_ret"].astype(float) * 1e4
    f["abs_post_bp"] = f["post_ret_bp"].abs()
    f["sunday_open"] = x["sunday_open"].astype(float)
    f["is_monday"] = (x["dow"] == 0).astype(float)
    f["fomc_tomorrow"] = x["fomc_tomorrow"].astype(float)
    f["fomc_today"] = x["fomc_today"].astype(float)
    f["megacap_earnings_tonight"] = x["megacap_earnings_tonight"].astype(float)
    f["holiday_eve"] = ((x["holiday_tomorrow"] == 1) | (x["pre_holiday"] == 1)).astype(float)
    f["abs_kospi_pct"] = x["kospi_ret"].astype(float).abs() * 100
    f["is_dst"] = x["is_dst"].astype(float)
    return f.replace([np.inf, -np.inf], np.nan)


# ---------------------------------------------------------------------------------------------
# model factories
# ---------------------------------------------------------------------------------------------
def _logit(C: float = 0.1) -> object:
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(C=C, penalty="l2", max_iter=5000))


def _gbm(n: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_depth=3, max_iter=100, learning_rate=0.04, l2_regularization=2.0,
                                          min_samples_leaf=max(15, n // 25), max_features=0.7, random_state=SEED)


def _gbm_multi(n: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_depth=2, max_iter=80, learning_rate=0.04, l2_regularization=4.0,
                                          min_samples_leaf=max(20, n // 20), max_features=0.7, random_state=SEED)


def _qreg(q: float) -> object:
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         QuantileRegressor(quantile=q, alpha=0.01, solver="highs"))


def _month_blocks(index: pd.DatetimeIndex, min_train: int = MIN_TRAIN):
    """Expanding-window monthly blocks: yields (train_mask, test_mask) with train = every session
    before the first session of the test month; the first test month is the first whose sessions
    all lie beyond the first `min_train` sessions."""
    periods = index.to_period("M")
    for p in periods.unique():
        train = periods < p
        test = periods == p
        if train.sum() < min_train:
            continue
        yield np.asarray(train), np.asarray(test)


# ---------------------------------------------------------------------------------------------
# walk-forward: binary targets
# ---------------------------------------------------------------------------------------------
def walk_forward_binary(X: pd.DataFrame, y: pd.Series, dst: pd.Series, min_train: int = MIN_TRAIN,
                        min_cal: int = MIN_CAL) -> tuple[pd.DataFrame, pd.Series]:
    """OOS probabilities for one binary target. Returns (oos frame, mean logistic coefficients)."""
    y = y.astype(int)
    preds, coefs = [], []
    for train, test in _month_blocks(X.index, min_train):
        Xtr, ytr = X[train], y[train]
        lr = _logit().fit(Xtr, ytr)
        gb = _gbm(int(train.sum())).fit(Xtr, ytr)
        row = pd.DataFrame(index=X.index[test])
        row["p_logit"] = lr.predict_proba(X[test])[:, 1]
        row["p_gbm"] = gb.predict_proba(X[test])[:, 1]
        row["p_raw"] = row[["p_logit", "p_gbm"]].mean(axis=1)
        row["base"] = float(ytr.mean())                                   # expanding base rate
        bd = ytr.groupby(dst[train]).mean()                                # DST-aware ("k-only") base rate
        row["base_dst"] = dst[test].map(bd).fillna(float(ytr.mean())).values
        # isotonic calibration on PRIOR OOS months only
        prior = pd.concat(preds) if preds else None
        if prior is not None and len(prior) >= min_cal:
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.02, y_max=0.98)
            iso.fit(prior["p_raw"].values, prior["y"].values)
            row["p_cal"] = iso.predict(row["p_raw"].values)
            row["cal_on"] = 1
        else:
            row["p_cal"] = row["p_raw"]
            row["cal_on"] = 0
        row["y"] = y[test].values
        preds.append(row)
        coefs.append(pd.Series(lr[-1].coef_[0], index=X.columns))
    oos = pd.concat(preds).sort_index()
    return oos, pd.concat(coefs, axis=1).mean(axis=1)


def walk_forward_prior(y: pd.Series, cond: pd.Series, dst: pd.Series, min_train: int = MIN_TRAIN,
                       min_cell: int = PRIOR_MIN_CELL) -> pd.DataFrame:
    """No-ML forecaster: the expanding rate of y conditional on `cond` (e.g. weekday). Same column
    layout as walk_forward_binary so it is evaluated identically (p_cal = p_raw = the rate)."""
    y = y.astype(int)
    preds = []
    for train, test in _month_blocks(y.index, min_train):
        ytr = y[train]; base = float(ytr.mean())
        g = ytr.groupby(cond[train]).agg(["mean", "size"])
        rate = cond[test].map(lambda v: float(g.loc[v, "mean"]) if (v in g.index and g.loc[v, "size"] >= min_cell) else base)
        row = pd.DataFrame(index=y.index[test])
        row["p_logit"] = row["p_gbm"] = row["p_raw"] = row["p_cal"] = rate.values
        row["base"] = base
        bd = ytr.groupby(dst[train]).mean()
        row["base_dst"] = dst[test].map(bd).fillna(base).values
        row["cal_on"] = 0
        row["y"] = y[test].values
        preds.append(row)
    return pd.concat(preds).sort_index()


# ---------------------------------------------------------------------------------------------
# walk-forward: quantiles
# ---------------------------------------------------------------------------------------------
def walk_forward_quantile(X: pd.DataFrame, y: pd.Series, qs=QUANTILES, min_train: int = MIN_TRAIN) -> pd.DataFrame:
    y = y.astype(float)
    preds = []
    for train, test in _month_blocks(X.index, min_train):
        row = pd.DataFrame(index=X.index[test])
        for q in qs:
            m = _qreg(q).fit(X[train], y[train])
            row[f"q{int(q*100)}"] = m.predict(X[test])
            row[f"base_q{int(q*100)}"] = float(y[train].quantile(q))     # expanding unconditional quantile
        row["y"] = y[test].values
        preds.append(row)
    return pd.concat(preds).sort_index()


# ---------------------------------------------------------------------------------------------
# walk-forward: map of the night (multinomial over the bar index of the extreme)
# ---------------------------------------------------------------------------------------------
def _hist(yk: pd.Series, n_cls: int = N_BARS_FULL) -> np.ndarray:
    c = np.bincount(yk.astype(int).values, minlength=n_cls).astype(float) + 1.0   # Laplace
    return c / c.sum()


def _ll(P: np.ndarray, yk: np.ndarray) -> float:
    P = np.clip(P, 1e-6, 1)
    return float(-np.mean(np.log(P[np.arange(len(yk)), yk])))


def _best_mix(prior: pd.DataFrame, pcols: list[str], hcols: list[str]) -> float:
    """Mixing weight w in [0,1] on the histogram, chosen on prior OOS rows (log-loss)."""
    yk = prior["y"].astype(int).values
    P, H = prior[pcols].values, prior[hcols].values
    grid = np.linspace(0, 1, 21)
    ll = [_ll((1 - w) * P + w * H, yk) for w in grid]
    return float(grid[int(np.argmin(ll))])


def walk_forward_map(X: pd.DataFrame, yk: pd.Series, dst: pd.Series, min_train: int = MIN_TRAIN,
                     min_cal: int = MIN_CAL, n_cls: int = N_BARS_FULL) -> pd.DataFrame:
    yk = yk.astype(int)
    pc = [f"p{i}" for i in range(n_cls)]; hc = [f"h{i}" for i in range(n_cls)]
    hd = [f"hd{i}" for i in range(n_cls)]; mc = [f"m{i}" for i in range(n_cls)]
    preds = []
    for train, test in _month_blocks(X.index, min_train):
        Xtr, ytr = X[train], yk[train]
        lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                           LogisticRegression(C=0.05, max_iter=5000)).fit(Xtr, ytr)
        gb = _gbm_multi(int(train.sum())).fit(Xtr, ytr)
        def full(P, classes):
            out = np.zeros((P.shape[0], n_cls)); out[:, classes] = P; return out
        P = 0.5 * full(lr.predict_proba(X[test]), lr[-1].classes_) + 0.5 * full(gb.predict_proba(X[test]), gb.classes_)
        row = pd.DataFrame(P, index=X.index[test], columns=pc)
        h = _hist(ytr, n_cls)
        row[hc] = np.tile(h, (test.sum(), 1))
        # DST-aware histogram (the k-only baseline that respects tokyo_open_k)
        H = np.vstack([_hist(ytr[dst[train].values == d], n_cls) if (dst[train].values == d).sum() >= 30 else h
                       for d in dst[test].values]) if test.sum() else np.zeros((0, n_cls))
        row[hd] = H
        prior = pd.concat(preds) if preds else None
        w = _best_mix(prior, pc, hc) if (prior is not None and len(prior) >= min_cal) else 1.0
        row[mc] = (1 - w) * row[pc].values + w * row[hc].values
        row["mix_w"] = w
        row["y"] = yk[test].values
        preds.append(row)
    return pd.concat(preds).sort_index()


# ---------------------------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------------------------
def train_walk_forward(sym: str = "NQ", verbose: bool = True) -> pd.DataFrame:
    """Run the full walk-forward for one symbol. Returns one wide OOS DataFrame (index = RTH date)
    with columns  <target>__<set>__p_{logit,gbm,raw,cal} / base / base_dst / cal_on, <target>__y,
    <qtarget>__q20/q50/q80 (+ base_), <hi_k|lo_k>__p0..p8 (model), h0..h8 (hist), hd0..hd8
    (DST hist), m0..m8 (mixed), and 'half'. oos.attrs['metrics'] holds the tables."""
    x = load_extremes(sym)
    F = make_features(x)
    dst = x["is_dst"].astype(int)
    parts, coefs = {}, {}
    dow = x["dow"].astype(int)
    for t in BINARY_TARGETS:
        for sname in BINARY_SETS:
            if sname == "dow_prior":
                o = walk_forward_prior(x[t], dow, dst)
            else:
                o, c = walk_forward_binary(F[FEATURE_SETS[sname]], x[t], dst)
                coefs[(t, sname)] = c
            parts[(t, sname)] = o
            if verbose:
                print(f"  {sym} {t:22s} [{sname:9s}] n_oos={len(o)} brier_cal={np.mean((o.p_cal-o.y)**2):.4f} base={np.mean((o.base-o.y)**2):.4f}", file=sys.stderr)
    qparts = {t: walk_forward_quantile(F[FEATURES_QUANT], x[t]) for t in QUANT_TARGETS}
    mparts = {t: walk_forward_map(F[FEATURES_TIMING], x[t], dst) for t in MAP_TARGETS}
    # assemble the wide frame
    idx = parts[(BINARY_TARGETS[0], "full")].index
    out = pd.DataFrame(index=idx)
    for (t, sname), o in parts.items():
        for c in ("p_logit", "p_gbm", "p_raw", "p_cal", "base", "base_dst", "cal_on"):
            out[f"{t}__{sname}__{c}"] = o[c]
        out[f"{t}__y"] = o["y"]
    for t, o in qparts.items():
        for c in o.columns:
            out[f"{t}__{c}"] = o[c]
    for t, o in mparts.items():
        for c in o.columns:
            out[f"{t}__{c}"] = o[c]
    out["half"] = np.where(out.index < H1_END, "H1", "H2")
    out["ref_close"] = x.loc[idx, "ref_close"]
    out["is_dst"] = dst.loc[idx]
    out.index.name = "date"
    out.attrs["metrics"] = evaluate(out, sym)
    out.attrs["coefs"] = coefs
    return out


# ---------------------------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------------------------
def _brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def _skill_ci(p, y, base, n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float, float]:
    p, y, base = map(np.asarray, (p, y, base))
    rng = np.random.default_rng(seed)
    n = len(y)
    sk = 1 - _brier(p, y) / _brier(base, y)
    boots = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        bb = _brier(base[i], y[i])
        boots.append(1 - _brier(p[i], y[i]) / bb if bb > 0 else np.nan)
    return sk, float(np.nanpercentile(boots, 5)), float(np.nanpercentile(boots, 95))


def _pinball(pred, y, q):
    d = np.asarray(y) - np.asarray(pred)
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def _pinball_skill_ci(pred, y, base, q, n_boot: int = N_BOOT, seed: int = SEED):
    pred, y, base = map(np.asarray, (pred, y, base))
    rng = np.random.default_rng(seed)
    n = len(y)
    sk = 1 - _pinball(pred, y, q) / _pinball(base, y, q)
    boots = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        boots.append(1 - _pinball(pred[i], y[i], q) / _pinball(base[i], y[i], q))
    return sk, float(np.percentile(boots, 5)), float(np.percentile(boots, 95))


def calibration_table(oos: pd.DataFrame, target: str, sname: str | None = None, n_bins: int = 5) -> pd.DataFrame:
    sname = sname or PRIMARY_SET[target]
    p = oos[f"{target}__{sname}__p_cal"]; y = oos[f"{target}__y"]
    try:
        b = pd.qcut(p, n_bins, duplicates="drop")
    except ValueError:
        b = pd.cut(p, n_bins)
    g = pd.DataFrame({"p": p, "y": y}).groupby(b, observed=True)
    return g.agg(n=("y", "size"), predicted=("p", "mean"), observed=("y", "mean")).round(3)


def evaluate(oos: pd.DataFrame, sym: str = "") -> dict:
    """Recompute every metric table from an OOS frame (works on a frame reloaded from CSV)."""
    rows = []
    for t in BINARY_TARGETS:
        y = oos[f"{t}__y"].values
        for sname in BINARY_SETS:
            pre = f"{t}__{sname}__"
            if pre + "p_cal" not in oos:
                continue
            pc, pr, base, bdst = (oos[pre + c].values for c in ("p_cal", "p_raw", "base", "base_dst"))
            sk, lo, hi = _skill_ci(pc, y, base)
            r = dict(target=t, set=sname, primary=int(PRIMARY_SET[t] == sname), n=len(y), base_rate=y.mean(),
                     brier_base=_brier(base, y), brier_konly=_brier(bdst, y), brier_raw=_brier(pr, y),
                     brier_cal=_brier(pc, y), skill_cal=sk, ci90_lo=lo, ci90_hi=hi,
                     skill_vs_konly=1 - _brier(pc, y) / _brier(bdst, y),
                     auc=roc_auc_score(y, pc) if 0 < y.mean() < 1 else np.nan)
            for h in ("H1", "H2"):
                m = (oos["half"] == h).values
                r[f"n_{h}"] = int(m.sum())
                r[f"skill_{h}"] = (1 - _brier(pc[m], y[m]) / _brier(base[m], y[m])) if m.sum() > 10 else np.nan
            rows.append(r)
    binary = pd.DataFrame(rows)
    binary["verdict"] = np.where((binary.ci90_lo > 0) & (binary.skill_H1 > 0) & (binary.skill_H2 > 0), "SKILL",
                                 np.where(binary.ci90_lo > 0, "skill (one half <= 0)", "none"))

    qrows = []
    for t in QUANT_TARGETS:
        y = oos[f"{t}__y"].values
        for q in QUANTILES:
            c = f"q{int(q*100)}"
            pred, base = oos[f"{t}__{c}"].values, oos[f"{t}__base_{c}"].values
            sk, lo, hi = _pinball_skill_ci(pred, y, base, q)
            r = dict(target=t, q=q, n=len(y), pinball_model=_pinball(pred, y, q), pinball_base=_pinball(base, y, q),
                     skill=sk, ci90_lo=lo, ci90_hi=hi, coverage_model=float(np.mean(y <= pred)),
                     coverage_base=float(np.mean(y <= base)))
            for h in ("H1", "H2"):
                m = (oos["half"] == h).values
                r[f"skill_{h}"] = 1 - _pinball(pred[m], y[m], q) / _pinball(base[m], y[m], q)
            qrows.append(r)
    quant = pd.DataFrame(qrows)
    quant["verdict"] = np.where((quant.ci90_lo > 0) & (quant.skill_H1 > 0) & (quant.skill_H2 > 0), "SKILL",
                                np.where(quant.ci90_lo > 0, "skill (one half <= 0)", "none"))

    mrows, perbar = [], []
    for t in MAP_TARGETS:
        yk = oos[f"{t}__y"].astype(int).values
        P = {k: oos[[f"{t}__{k}{i}" for i in range(N_BARS_FULL)]].values for k in ("p", "h", "hd", "m")}
        r = dict(target=t, n=len(yk), logloss_model=_ll(P["p"], yk), logloss_mixed=_ll(P["m"], yk),
                 logloss_hist=_ll(P["h"], yk), logloss_hist_dst=_ll(P["hd"], yk),
                 mix_w_median=float(oos[f"{t}__mix_w"].median()))
        r["skill_mixed_vs_hist"] = 1 - r["logloss_mixed"] / r["logloss_hist"]
        r["skill_model_vs_hist"] = 1 - r["logloss_model"] / r["logloss_hist"]
        # bootstrap CI on the mixed-vs-hist skill
        rng = np.random.default_rng(SEED); boots = []
        for _ in range(N_BOOT):
            i = rng.integers(0, len(yk), len(yk))
            boots.append(1 - _ll(P["m"][i], yk[i]) / _ll(P["h"][i], yk[i]))
        r["ci90_lo"], r["ci90_hi"] = float(np.percentile(boots, 5)), float(np.percentile(boots, 95))
        for h in ("H1", "H2"):
            m = (oos["half"] == h).values
            r[f"skill_{h}"] = 1 - _ll(P["m"][m], yk[m]) / _ll(P["h"][m], yk[m])
        mrows.append(r)
        for i in range(N_BARS_FULL):
            yi = (yk == i).astype(float)
            perbar.append(dict(target=t, bar=i, obs_rate=yi.mean(), mean_p_mixed=P["m"][:, i].mean(),
                               brier_mixed=_brier(P["m"][:, i], yi), brier_hist=_brier(P["h"][:, i], yi),
                               skill=1 - _brier(P["m"][:, i], yi) / _brier(P["h"][:, i], yi)))
    mapt = pd.DataFrame(mrows)
    mapt["verdict"] = np.where((mapt.ci90_lo > 0) & (mapt.skill_H1 > 0) & (mapt.skill_H2 > 0), "SKILL",
                               np.where(mapt.ci90_lo > 0, "skill (one half <= 0)", "none"))
    calib = {t: calibration_table(oos, t) for t in BINARY_TARGETS}
    return {"binary": binary, "quantile": quant, "map": mapt, "map_per_bar": pd.DataFrame(perbar), "calibration": calib,
            "oos_start": str(oos.index.min().date()), "oos_end": str(oos.index.max().date()), "sym": sym}


def format_metrics(m: dict) -> str:
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    s = [f"=== {m['sym']} PRE-ASIA forecaster, OOS {m['oos_start']} .. {m['oos_end']} (H1 < {H1_END.date()} <= H2) ==="]
    b = m["binary"].copy()
    cols = ["target", "set", "primary", "n", "base_rate", "brier_base", "brier_konly", "brier_raw", "brier_cal",
            "skill_cal", "ci90_lo", "ci90_hi", "skill_vs_konly", "auc", "n_H1", "skill_H1", "n_H2", "skill_H2", "verdict"]
    s.append("\n-- binary targets (Brier; skill = 1 - Brier_cal / Brier_base; CI = 90% bootstrap over OOS sessions) --")
    s.append(b[cols].round(4).to_string(index=False))
    s.append("\n-- quantiles (pinball loss vs the expanding unconditional quantile; coverage = share of y <= forecast) --")
    s.append(m["quantile"].round(4).to_string(index=False))
    s.append("\n-- map of the night (multinomial over the bar of the extreme; log-loss vs expanding histogram) --")
    s.append(m["map"].round(4).to_string(index=False))
    s.append("\n-- map per bar (one-vs-rest Brier of the mixed model vs the histogram) --")
    pb = m["map_per_bar"].round(4)
    s.append(pb.pivot(index="bar", columns="target", values=["obs_rate", "mean_p_mixed", "skill"]).round(3).to_string())
    s.append("\n-- calibration, primary set, 5 quantile buckets of p_cal --")
    for t, tab in m["calibration"].items():
        s.append(f"[{t} / {PRIMARY_SET[t]}]\n" + tab.to_string())
    return "\n".join(s)


# ---------------------------------------------------------------------------------------------
# tonight
# ---------------------------------------------------------------------------------------------
_OOS_CACHE: dict = {}


def _oos_for(sym: str) -> pd.DataFrame:
    if sym in _OOS_CACHE:
        return _OOS_CACHE[sym]
    p = os.path.join(HERE, f"oos_preasia_{sym}.csv")
    if os.path.exists(p):
        o = pd.read_csv(p, index_col="date", parse_dates=True)
    else:
        o = train_walk_forward(sym, verbose=False)
    _OOS_CACHE[sym] = o
    return o


def _oos_skill_binary(oos: pd.DataFrame, t: str, sname: str):
    pre = f"{t}__{sname}__"
    if pre + "p_cal" not in oos or len(oos) < MIN_CAL:
        return None
    y = oos[f"{t}__y"].values
    return round(1 - _brier(oos[pre + "p_cal"].values, y) / _brier(oos[pre + "base"].values, y), 3)


def _oos_skill_quantile(oos: pd.DataFrame, t: str, q: float):
    c = f"q{int(q*100)}"
    if f"{t}__{c}" not in oos or len(oos) < MIN_CAL:
        return None
    y = oos[f"{t}__y"].values
    return round(1 - _pinball(oos[f"{t}__{c}"].values, y, q) / _pinball(oos[f"{t}__base_{c}"].values, y, q), 3)


def _contrib(pipe, Xrow: pd.DataFrame, cols: list[str], top: int = 5) -> list[tuple[str, float]]:
    z = pipe[1].transform(pipe[0].transform(Xrow[cols]))[0]
    c = pd.Series(z * pipe[-1].coef_[0], index=cols)
    c = c.reindex(c.abs().sort_values(ascending=False).index)[:top]
    return [(k, round(float(v), 3)) for k, v in c.items()]


def predict_tonight(sym: str, date, h: pd.DataFrame | None = None) -> dict:
    """Forecast for the Asia session that follows RTH date `date`, trained on every session strictly
    before it; calibration and shrinkage come from OOS predictions strictly before it.

    When `date` is not in <SYM>_extremes.csv yet (the night has fewer than 6 bars, or has not started),
    or when the caller passes an hourly frame `h` (the data it wants used - a truncated frame, a
    replay), the 18:00 row is built from the hourly data with asia_extremes.live_extremes_row; the
    result then carries live=True.  With h=None and the date in the table the stored row is used
    (live=False); both rows agree on every column make_features() reads.  A contract-splice session
    (asia_extremes.SPLICE_SESSIONS) raises ValueError.
    """
    import asia_extremes as ae
    date = pd.Timestamp(date).normalize()
    if date in pd.to_datetime(SPLICE_SESSIONS.get(sym, [])):
        raise ValueError(f"{sym} {date.date()}: contract-splice session (asia_extremes.SPLICE_SESSIONS); "
                         f"its bars toggle between two contracts, so no forecast is served")
    x_all = load_extremes(sym, full_only=False)
    live = h is not None or date not in x_all.index
    row = ae.live_extremes_row(sym, date, h=h) if live else x_all.loc[[date]]
    xtr = load_extremes(sym)
    xtr = xtr[xtr.index < date]
    if len(xtr) < MIN_TRAIN:
        raise ValueError(f"only {len(xtr)} training sessions before {date.date()} (need {MIN_TRAIN})")
    Ftr, Fx = make_features(xtr), make_features(row)
    oos = _oos_for(sym)
    oos = oos[oos.index < date]
    ref = float(row["ref_close"].iloc[0])
    out = {"sym": sym, "date": str(date.date()), "ref_close_17h": ref, "n_train": int(len(xtr)),
           "live": bool(live), "short_session_warning": ae.short_session_warning(sym, date),
           "rth_high": float(row["lvl_rth_high"].iloc[0]), "rth_low": float(row["lvl_rth_low"].iloc[0]),
           "is_dst": int(row["is_dst"].iloc[0]), "tokyo_open_k": int(row["tokyo_open_k"].iloc[0]),
           "features": {k: (None if pd.isna(v) else round(float(v), 4)) for k, v in Fx.iloc[0].items()},
           "probabilities": {}, "contributions": {}, "quantiles_bp": {}, "quantiles_price": {}, "map": {}}
    for t in BINARY_TARGETS:
        sname = PRIMARY_SET[t]; cols = FEATURE_SETS[sname]
        lr = _logit().fit(Ftr[cols], xtr[t].astype(int))
        gb = _gbm(len(xtr)).fit(Ftr[cols], xtr[t].astype(int))
        p_raw = 0.5 * lr.predict_proba(Fx[cols])[0, 1] + 0.5 * gb.predict_proba(Fx[cols])[0, 1]
        pre = f"{t}__{sname}__"
        if len(oos) >= MIN_CAL and pre + "p_raw" in oos:
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.02, y_max=0.98)
            iso.fit(oos[pre + "p_raw"].values, oos[f"{t}__y"].values)
            p_cal = float(iso.predict([p_raw])[0])
        else:
            p_cal = float(p_raw)
        # the no-ML weekday prior (expanding conditional rate given dow), evaluated alongside
        dow = int(row["dow"].iloc[0])
        g = xtr[t].groupby(xtr["dow"]).agg(["mean", "size"])
        p_prior = float(g.loc[dow, "mean"]) if (dow in g.index and g.loc[dow, "size"] >= PRIOR_MIN_CELL) else float(xtr[t].mean())
        out["probabilities"][t] = {"p_cal": round(p_cal, 3), "p_raw": round(float(p_raw), 3),
                                   "p_dow_prior": round(p_prior, 3),
                                   "base_rate": round(float(xtr[t].mean()), 3), "feature_set": sname,
                                   "oos_skill_model": _oos_skill_binary(oos, t, sname),
                                   "oos_skill_dow_prior": _oos_skill_binary(oos, t, "dow_prior")}
        out["contributions"][t] = _contrib(lr, Fx, cols)
    for t in QUANT_TARGETS:
        qb, qp = {}, {}
        for q in QUANTILES:
            m = _qreg(q).fit(Ftr[FEATURES_QUANT], xtr[t].astype(float))
            v = float(m.predict(Fx[FEATURES_QUANT])[0])
            qb[f"P{int(q*100)}"] = round(v, 1)
            if t != "rng_bp":
                qp[f"P{int(q*100)}"] = round(ref * (1 + v / 1e4), 2)
        qb["uncond"] = {f"P{int(q*100)}": round(float(xtr[t].quantile(q)), 1) for q in QUANTILES}
        qb["oos_skill"] = {f"P{int(q*100)}": _oos_skill_quantile(oos, t, q) for q in QUANTILES}
        out["quantiles_bp"][t] = qb
        if qp:
            out["quantiles_price"][t.replace("_bp", "")] = qp
    out["quantiles_price"]["range_points_P50"] = round(ref * out["quantiles_bp"]["rng_bp"]["P50"] / 1e4, 2)
    for t in MAP_TARGETS:
        yk = xtr[t].astype(int)
        lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                           LogisticRegression(C=0.05, max_iter=5000)).fit(Ftr[FEATURES_TIMING], yk)
        gb = _gbm_multi(len(xtr)).fit(Ftr[FEATURES_TIMING], yk)
        P = np.zeros(N_BARS_FULL)
        P[lr[-1].classes_] += 0.5 * lr.predict_proba(Fx[FEATURES_TIMING])[0]
        P[gb.classes_] += 0.5 * gb.predict_proba(Fx[FEATURES_TIMING])[0]
        h = _hist(yk)
        pc = [f"{t}__p{i}" for i in range(N_BARS_FULL)]; hc = [f"{t}__h{i}" for i in range(N_BARS_FULL)]
        if len(oos) >= MIN_CAL and all(c in oos for c in pc):
            prior = oos[pc + hc + [f"{t}__y"]].rename(columns={f"{t}__y": "y"})
            prior.columns = [c.replace(f"{t}__", "") for c in prior.columns]
            w = _best_mix(prior, [f"p{i}" for i in range(N_BARS_FULL)], [f"h{i}" for i in range(N_BARS_FULL)])
        else:
            w = 1.0
        skill = None
        if len(oos) >= MIN_CAL and all(c in oos for c in pc):
            yk_o = oos[f"{t}__y"].astype(int).values
            mc = [f"{t}__m{i}" for i in range(N_BARS_FULL)]
            skill = round(1 - _ll(oos[mc].values, yk_o) / _ll(oos[hc].values, yk_o), 4)
        out["map"][t] = {"p_by_bar": [round(float(v), 3) for v in (1 - w) * P + w * h],
                         "hist_by_bar": [round(float(v), 3) for v in h], "mix_w_on_hist": w,
                         "model_by_bar": [round(float(v), 3) for v in P], "oos_logloss_skill_vs_hist": skill}
    out["reading_guide"] = (
        "OOS skill fields are Brier/pinball/log-loss skill vs the expanding base rate on every OOS session "
        "before this date. In the walk-forward only high_above_rth_high, low_below_rth_low, the rng_bp quantiles, "
        "the hi_bp P80 and (weakly) the lo_bp P20/P50 carried skill; the nine timing probabilities and the "
        "map of the night did not beat their base rates, so read them as priors, not forecasts.")
    return out


def format_tonight(r: dict) -> str:
    """Compact human-readable summary of a predict_tonight() result."""
    L = [f"=== {r['sym']} pre-Asia forecast for the night after {r['date']}  (17:00 ref {r['ref_close_17h']:.2f}, "
         f"RTH high {r['rth_high']:.2f} / low {r['rth_low']:.2f}, {'EDT' if r['is_dst'] else 'EST'}, Tokyo open bar k={r['tokyo_open_k']}) ===",
         f"    live={'yes (row built from the hourly data)' if r['live'] else 'no (stored extremes row)'} | train sessions {r['n_train']}"]
    if r.get("short_session_warning"):
        L.append(f"    SHORT-SESSION WARNING: {r['short_session_warning']}")
    L.append("  probabilities (p_cal; base rate; weekday prior; OOS Brier skill of the model / of the weekday prior):")
    for t, pr in r["probabilities"].items():
        sk = pr["oos_skill_model"]; skp = pr["oos_skill_dow_prior"]
        L.append(f"    {t:22s} {pr['p_cal']:.3f}  base {pr['base_rate']:.3f}  dow {pr['p_dow_prior']:.3f}   "
                 f"skill {sk if sk is None else f'{sk:+.3f}'} / {skp if skp is None else f'{skp:+.3f}'}"
                 + ("   <- carried OOS skill" if t in LEVEL_TARGETS else ""))
    L.append("  quantiles (bp vs the 17:00 close; unconditional in brackets):")
    for t, q in r["quantiles_bp"].items():
        u = q["uncond"]; sk = q["oos_skill"]
        L.append(f"    {t:7s} P20 {q['P20']:7.1f} [{u['P20']:7.1f}]  P50 {q['P50']:7.1f} [{u['P50']:7.1f}]  P80 {q['P80']:7.1f} [{u['P80']:7.1f}]"
                 f"   skill " + "/".join("n/a" if sk[k] is None else f"{sk[k]:+.3f}" for k in ("P20", "P50", "P80")))
    qp = r["quantiles_price"]
    L.append(f"  levels: high P20/P50/P80 {qp['hi']['P20']:.2f} / {qp['hi']['P50']:.2f} / {qp['hi']['P80']:.2f}; "
             f"low P20/P50/P80 {qp['lo']['P20']:.2f} / {qp['lo']['P50']:.2f} / {qp['lo']['P80']:.2f}; "
             f"range P50 {qp['range_points_P50']:.2f} points")
    for t, mp in r["map"].items():
        L.append(f"  map {t}: " + " ".join(f"k{i}:{v:.2f}" for i, v in enumerate(mp["p_by_bar"])) +
                 f"   (hist mix {mp['mix_w_on_hist']:.2f}, OOS log-loss skill {mp['oos_logloss_skill_vs_hist']})")
    for t in LEVEL_TARGETS:
        L.append(f"  top contributions {t}: " + ", ".join(f"{n} {v:+.2f}" for n, v in r["contributions"][t]))
    L.append("  " + r["reading_guide"])
    return "\n".join(L)


def _cli(argv: list[str]):
    import argparse
    ap = argparse.ArgumentParser(description="Pre-Asia high/low forecaster")
    ap.add_argument("syms", nargs="*", help="symbols for the full walk-forward re-run (default NQ ES)")
    ap.add_argument("--now", metavar="SYM", help="tonight's forecast for SYM instead of the walk-forward")
    ap.add_argument("--date", help="RTH date YYYY-MM-DD (default: the latest RTH date in the hourly data)")
    a = ap.parse_args(argv)
    if a.now:
        import asia_extremes as ae
        sym = a.now.upper()
        date = pd.Timestamp(a.date) if a.date else ae.latest_rth_date(sym)
        print(format_tonight(predict_tonight(sym, date)))
        return
    for sym in [s.upper() for s in a.syms] or ["NQ", "ES"]:
        oos = train_walk_forward(sym)
        path = os.path.join(HERE, f"oos_preasia_{sym}.csv")
        oos.to_csv(path)
        print(f"\nwrote {path}  ({oos.shape[0]} OOS sessions x {oos.shape[1]} columns)")
        print(format_metrics(oos.attrs["metrics"]))


# ---------------------------------------------------------------------------------------------
if __name__ == "__main__":
    _cli(sys.argv[1:])
