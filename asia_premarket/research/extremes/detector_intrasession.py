"""
Intra-session Asia HIGH / LOW detector: "is the Asia high / low already in?"

At the close of each hourly Asia bar k = 0..7 (0 = the 18:00 ET bar) the detector answers, using only
information known at that close:

    p_high_done   P(the session high is already in)          (label: hourly panel high_done)
    p_low_done    P(the session low is already in)           (label: low_done)
    rem_up_p50/80 quantiles of remaining_up_bp  = (session high / close_k - 1) * 1e4   (>= 0)
    rem_dn_p50/80 quantiles of remaining_down_bp = (session low / close_k - 1) * 1e4   (<= 0, reported signed)

    remaining_up_bp is the distance from the current close to the SESSION high: when the high is already
    in it is the (positive) distance back up to that high, and price will not trade above it; when the
    high is not in it is the room still to run.  Its P80 is therefore an 80% envelope for "how far above
    here can the session high be", which is what a user wants to know at the close of bar k.  Because
    that marginal envelope mixes the two states, a second set of quantiles is fitted on the rows where
    the extreme was NOT yet in (rem_up_p50_if_open, rem_up_p80_if_open, rem_dn_*_if_open): "if the high
    is still ahead, how far is it".  They are evaluated on the not-yet-in rows (an ex-post subset, so
    their coverage is a conditional statement, not a marginal one).

Inputs (20 features, all knowable at the close of bar k):
    hourly panel at bar k : k, bars_since_hi, bars_since_lo, pos_in_range, run_rng_vs_med20, bar_close_loc,
                            bar_ret_bp, bar_rng_rel, vol_dir (= bar_vol_rel * sign(bar_ret_bp)),
                            dist_run_hi_bp, dist_run_lo_bp (distance of the close to the running extremes),
                            run_hi_above_rth_high, run_lo_below_rth_low, sd_rth_high, sd_rth_low
                            (distance of the close to the RTH high / low scaled by the ex-ante 20-session
                            median Asia range)
    18:00 features (joined by date): med_rng_bp (= asia_rng_med20 * 1e4), vix, sunday_open,
                            fomc_tomorrow, ah_print (= megacap_earnings_tonight or |post_ret| >= 25 bp)

Models (sklearn, fixed seeds):
    * L2 logistic regression on a fixed non-linear design of the 20 features (k dummies, bars_since
      indicators, log scales) with median imputation + standardisation;
    * HistGradientBoostingClassifier depth <= 3 on the raw 20 features (NaN handled natively);
    * ensemble = mean of the two probabilities;
    * isotonic calibration of the ensemble fitted ONLY on prior out-of-sample predictions (never on the
      block being predicted, never pooled over the future); switched on once >= MIN_CAL_SESSIONS sessions
      of prior OOS predictions exist, raw before that;
    * quantile HistGradientBoostingRegressors (depth <= 3) for the P50 / P80 of remaining_up_bp and of
      the magnitude of remaining_down_bp.

Evaluation: expanding-window walk-forward, first TRAIN_ONLY_SESSIONS sessions training-only, refit at
every calendar-month boundary, predictions strictly out of sample.  Baselines computed with the same
walk-forward: "base" = the pooled training rate of the target, "k-only" = the training rate for that
bar index (and the per-k training quantiles for the remaining-move targets).

Population: full 9-bar sessions only (truncated 6-8 bar holiday sessions are excluded because the
missing 00:00-02:00 bars make their labels unreliable) and contract-splice sessions excluded.

Usage:
    python detector_intrasession.py [NQ] [ES]
        -> writes research/extremes/oos_intrasession_<SYM>.csv and prints the metric tables
    from detector_intrasession import train_walk_forward, predict_now
        oos = train_walk_forward('NQ')
        predict_now('NQ', '2026-11-06', 3)
"""
from __future__ import annotations

import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))

SEED = 0
TRAIN_ONLY_SESSIONS = 120      # first sessions never predicted
MIN_CAL_SESSIONS = 60          # prior OOS sessions needed before isotonic calibration is switched on
H2_START = pd.Timestamp("2025-09-01")
MAX_K = 7                      # k = 8 is the last bar, where both labels are trivially 1

# RTH dates whose Asia session (or 17:00 reference / RTH levels) is corrupted by a contract splice in the
# hourly files.  2024-06-21, 2024-12-20 and 2025-03-21 are not in the extremes tables (dropped by the
# session builder) but are listed for safety.  Both NQ and ES toggle between two contracts every bar
# from 2025-12-16 03:00 to 2025-12-17 13:00 ET.
SPLICE_DATES = {
    "NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16", "2025-12-16", "2025-12-17"],
    "ES": ["2025-12-16", "2025-12-17"],
}

FEATURES = [
    "k", "bars_since_hi", "bars_since_lo", "pos_in_range", "run_rng_vs_med20", "med_rng_bp",
    "bar_close_loc", "bar_ret_bp", "bar_rng_rel", "vol_dir", "dist_run_hi_bp", "dist_run_lo_bp",
    "run_hi_above_rth_high", "run_lo_below_rth_low", "sd_rth_high", "sd_rth_low",
    "sunday_open", "fomc_tomorrow", "ah_print", "vix",
]
FEATURES_1800 = ["sunday_open", "fomc_tomorrow", "megacap_earnings_tonight", "post_ret", "vix", "asia_rng_med20"]
TARGETS = ["high_done", "low_done"]
QUANTILES = [0.5, 0.8]


# --------------------------------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------------------------------
def load_tables(sym: str):
    x = pd.read_csv(os.path.join(HERE, f"{sym}_extremes.csv"), index_col="date", parse_dates=True)
    p = pd.read_csv(os.path.join(HERE, f"{sym}_hourly_panel.csv"), parse_dates=["date"])
    return x, p


def build_dataset(sym: str, x: pd.DataFrame | None = None, p: pd.DataFrame | None = None,
                  full_sessions_only: bool = True) -> pd.DataFrame:
    """Panel rows k<=7 with the 20 detector features, the labels and the 18:00 flags joined by date."""
    if x is None or p is None:
        x, p = load_tables(sym)
    d = p.merge(x[FEATURES_1800], left_on="date", right_index=True, how="left")
    d = d[d["k"] <= MAX_K].copy()
    d = d[~d["date"].isin(pd.to_datetime(SPLICE_DATES.get(sym, [])))]
    if full_sessions_only:
        d = d[d["n_bars"] == 9]
    d["med_rng_bp"] = d["asia_rng_med20"] * 1e4
    d["vol_dir"] = d["bar_vol_rel"].fillna(1.0) * np.sign(d["bar_ret_bp"])
    d["dist_run_hi_bp"] = d["run_hi_bp"] - d["cum_ret_bp"]
    d["dist_run_lo_bp"] = d["cum_ret_bp"] - d["run_lo_bp"]
    d["sd_rth_high"] = d["dist_rth_high_bp"] / d["med_rng_bp"]      # + : RTH high above the close
    d["sd_rth_low"] = -d["dist_rth_low_bp"] / d["med_rng_bp"]       # + : RTH low below the close
    d["ah_print"] = ((d["megacap_earnings_tonight"] == 1) | (d["post_ret"].abs() >= 0.0025)).astype(int)
    d["rem_dn_mag"] = -d["remaining_down_bp"]
    d = d.sort_values(["date", "k"]).reset_index(drop=True)
    return d


def lr_design(X: pd.DataFrame) -> pd.DataFrame:
    """Fixed non-linear design for the logistic component (no fitting involved)."""
    D = pd.DataFrame(index=X.index)
    for kk in range(MAX_K + 1):
        D[f"k={kk}"] = (X["k"] == kk).astype(float)
    D["bars_since_hi==0"] = (X["bars_since_hi"] == 0).astype(float)
    D["bars_since_lo==0"] = (X["bars_since_lo"] == 0).astype(float)
    D["log1p_bars_since_hi"] = np.log1p(X["bars_since_hi"])
    D["log1p_bars_since_lo"] = np.log1p(X["bars_since_lo"])
    D["pos_in_range"] = X["pos_in_range"]
    D["pos_in_range*k"] = X["pos_in_range"] * X["k"] / MAX_K
    D["log_run_rng_vs_med20"] = np.log(X["run_rng_vs_med20"].clip(0.05, 5))
    D["log_med_rng_bp"] = np.log(X["med_rng_bp"].clip(5, 500))
    D["bar_close_loc"] = X["bar_close_loc"]
    D["bar_ret/med_rng"] = (X["bar_ret_bp"] / X["med_rng_bp"]).clip(-3, 3)
    D["log_bar_rng_rel"] = np.log(X["bar_rng_rel"].clip(0.1, 10))
    D["vol_dir"] = X["vol_dir"].clip(-4, 4)
    D["dist_run_hi/med_rng"] = (X["dist_run_hi_bp"] / X["med_rng_bp"]).clip(0, 4)
    D["dist_run_lo/med_rng"] = (X["dist_run_lo_bp"] / X["med_rng_bp"]).clip(0, 4)
    D["run_hi_above_rth_high"] = X["run_hi_above_rth_high"].astype(float)
    D["run_lo_below_rth_low"] = X["run_lo_below_rth_low"].astype(float)
    D["sd_rth_high"] = X["sd_rth_high"].clip(-3, 3)
    D["sd_rth_low"] = X["sd_rth_low"].clip(-3, 3)
    D["sunday_open"] = X["sunday_open"].astype(float)
    D["fomc_tomorrow"] = X["fomc_tomorrow"].astype(float)
    D["ah_print"] = X["ah_print"].astype(float)
    D["log_vix"] = np.log(X["vix"].clip(8, 90))
    return D


# --------------------------------------------------------------------------------------------------
# models
# --------------------------------------------------------------------------------------------------
def _lr():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(C=0.3, max_iter=5000, random_state=SEED))


def _gb():
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                          l2_regularization=1.0, early_stopping=False, random_state=SEED)


def _qgb(q: float):
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=3, learning_rate=0.05,
                                         max_iter=150, min_samples_leaf=40, l2_regularization=1.0,
                                         early_stopping=False, random_state=SEED)


def fit_models(tr: pd.DataFrame) -> dict:
    """Fit every component on the training rows `tr` (all rows strictly before the prediction block)."""
    X = tr[FEATURES]
    D = lr_design(tr)
    m = {"n_train_sessions": tr["date"].nunique(), "n_train_rows": len(tr), "design_cols": list(D.columns)}
    for t in TARGETS:
        y = tr[t].values
        m[f"lr_{t}"] = _lr().fit(D, y)
        m[f"gb_{t}"] = _gb().fit(X, y)
        m[f"base_{t}"] = float(y.mean())
        m[f"kbase_{t}"] = tr.groupby("k")[t].mean()
    up_open = tr[tr["high_done"] == 0]          # conditional models: the extreme was still ahead
    dn_open = tr[tr["low_done"] == 0]
    for q in QUANTILES:
        m[f"q_up_{q}"] = _qgb(q).fit(X, tr["remaining_up_bp"].values)
        m[f"q_dn_{q}"] = _qgb(q).fit(X, tr["rem_dn_mag"].values)
        m[f"kq_up_{q}"] = tr.groupby("k")["remaining_up_bp"].quantile(q)
        m[f"kq_dn_{q}"] = tr.groupby("k")["rem_dn_mag"].quantile(q)
        m[f"qo_up_{q}"] = _qgb(q).fit(up_open[FEATURES], up_open["remaining_up_bp"].values)
        m[f"qo_dn_{q}"] = _qgb(q).fit(dn_open[FEATURES], dn_open["rem_dn_mag"].values)
        m[f"kqo_up_{q}"] = up_open.groupby("k")["remaining_up_bp"].quantile(q)
        m[f"kqo_dn_{q}"] = dn_open.groupby("k")["rem_dn_mag"].quantile(q)
    return m


def predict_models(m: dict, te: pd.DataFrame) -> pd.DataFrame:
    """Raw (uncalibrated) predictions and walk-forward baselines for the rows `te`."""
    X = te[FEATURES]
    D = lr_design(te)
    out = te[["date", "k"] + TARGETS + ["remaining_up_bp", "remaining_down_bp"]].copy()
    for t in TARGETS:
        s = t.split("_")[0]
        out[f"p_{s}_lr"] = m[f"lr_{t}"].predict_proba(D)[:, 1]
        out[f"p_{s}_gb"] = m[f"gb_{t}"].predict_proba(X)[:, 1]
        out[f"p_{s}_raw"] = 0.5 * (out[f"p_{s}_lr"] + out[f"p_{s}_gb"])
        out[f"base_{s}"] = m[f"base_{t}"]
        out[f"kbase_{s}"] = te["k"].map(m[f"kbase_{t}"]).values
    for q in QUANTILES:
        tag = f"p{int(q * 100)}"
        out[f"rem_up_{tag}"] = np.clip(m[f"q_up_{q}"].predict(X), 0, None)
        out[f"rem_dn_{tag}"] = -np.clip(m[f"q_dn_{q}"].predict(X), 0, None)
        out[f"kq_up_{tag}"] = te["k"].map(m[f"kq_up_{q}"]).values
        out[f"kq_dn_{tag}"] = -te["k"].map(m[f"kq_dn_{q}"]).values
        out[f"rem_up_{tag}_if_open"] = np.clip(m[f"qo_up_{q}"].predict(X), 0, None)
        out[f"rem_dn_{tag}_if_open"] = -np.clip(m[f"qo_dn_{q}"].predict(X), 0, None)
        out[f"kqo_up_{tag}"] = te["k"].map(m[f"kqo_up_{q}"]).values
        out[f"kqo_dn_{tag}"] = -te["k"].map(m[f"kqo_dn_{q}"]).values
    return out


def fit_calibrators(hist: pd.DataFrame) -> dict:
    """Isotonic calibrators fitted on PRIOR out-of-sample predictions only."""
    cal = {}
    if hist is None or hist["date"].nunique() < MIN_CAL_SESSIONS:
        return cal
    for t in TARGETS:
        s = t.split("_")[0]
        cal[s] = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(hist[f"p_{s}_raw"], hist[t])
    return cal


def apply_calibrators(out: pd.DataFrame, cal: dict) -> pd.DataFrame:
    out = out.copy()
    out["calibrated"] = int(bool(cal))
    for t in TARGETS:
        s = t.split("_")[0]
        out[f"p_{s}_done"] = cal[s].predict(out[f"p_{s}_raw"]) if s in cal else out[f"p_{s}_raw"].values
    return out


# --------------------------------------------------------------------------------------------------
# walk-forward
# --------------------------------------------------------------------------------------------------
def _month_blocks(dates: np.ndarray):
    """Group an ordered array of dates into calendar-month blocks."""
    s = pd.Series(pd.to_datetime(dates))
    key = s.dt.year * 100 + s.dt.month
    return [(int(kk), grp.values) for kk, grp in s.groupby(key)]


def train_walk_forward(sym: str = "NQ", verbose: bool = True) -> pd.DataFrame:
    """Expanding-window walk-forward with monthly refits; returns the out-of-sample prediction frame."""
    d = build_dataset(sym)
    dates = np.array(sorted(d["date"].unique()))
    if len(dates) <= TRAIN_ONLY_SESSIONS + 1:
        raise ValueError("not enough sessions")
    preds, hist = [], None
    for ym, bdates in _month_blocks(dates[TRAIN_ONLY_SESSIONS:]):
        t0 = pd.Timestamp(bdates[0])
        tr = d[d["date"] < t0]
        te = d[d["date"].isin(bdates)]
        m = fit_models(tr)
        out = apply_calibrators(predict_models(m, te), fit_calibrators(hist))
        out["refit_block"] = ym
        out["n_train_sessions"] = m["n_train_sessions"]
        preds.append(out)
        hist = pd.concat(preds, ignore_index=True)
        if verbose:
            print(f"  {sym} block {ym}: train {m['n_train_sessions']} sessions / {m['n_train_rows']} rows, "
                  f"predict {te['date'].nunique()} sessions, calibrated={int(bool(out['calibrated'].iloc[0]))}")
    oos = pd.concat(preds, ignore_index=True)
    oos.insert(0, "sym", sym)
    return oos


# --------------------------------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------------------------------
def _brier(y, p):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def _auc(y, p):
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return np.nan
    return float(roc_auc_score(y, p))


def _pinball(y, qhat, q):
    y = np.asarray(y, float); qhat = np.asarray(qhat, float)
    e = y - qhat
    return float(np.mean(np.maximum(q * e, (q - 1) * e)))


def classification_table(oos: pd.DataFrame, side: str) -> pd.DataFrame:
    """Per-k and pooled metrics for high_done (side='high') or low_done (side='low')."""
    t = f"{side}_done"
    rows = []
    groups = [(f"k={kk}", oos[oos["k"] == kk]) for kk in range(MAX_K + 1)] + [("pooled", oos)]
    for name, g in groups:
        y = g[t].values
        r = dict(k=name, n=len(g), rate=y.mean(),
                 brier_base=_brier(y, g[f"base_{side}"]),
                 brier_konly=_brier(y, g[f"kbase_{side}"]),
                 brier_lr=_brier(y, g[f"p_{side}_lr"]),
                 brier_gb=_brier(y, g[f"p_{side}_gb"]),
                 brier_ens_raw=_brier(y, g[f"p_{side}_raw"]),
                 brier_final=_brier(y, g[f"p_{side}_done"]),
                 auc_final=_auc(y, g[f"p_{side}_done"]))
        r["skill_vs_konly"] = 1 - r["brier_final"] / r["brier_konly"] if r["brier_konly"] > 0 else np.nan
        r["skill_vs_base"] = 1 - r["brier_final"] / r["brier_base"] if r["brier_base"] > 0 else np.nan
        rows.append(r)
    return pd.DataFrame(rows).set_index("k")


def calibration_table(oos: pd.DataFrame, side: str, col: str | None = None) -> pd.DataFrame:
    """Reliability in 5 fixed-width probability buckets."""
    col = col or f"p_{side}_done"
    t = f"{side}_done"
    b = pd.cut(oos[col].clip(0, 1), [0, 0.2, 0.4, 0.6, 0.8, 1.0], include_lowest=True)
    g = oos.groupby(b, observed=False)
    return pd.DataFrame({"n": g.size(), "mean_pred": g[col].mean(), "obs_rate": g[t].mean()})


def quantile_table(oos: pd.DataFrame, conditional: bool = False) -> pd.DataFrame:
    """Pinball loss and coverage of the remaining-move quantiles vs the per-k training quantiles.

    conditional=True evaluates the `_if_open` quantiles on the rows where the extreme was NOT yet in
    (an ex-post subset) against the per-k training quantiles of the same not-yet-in rows.
    """
    rows = []
    for side, ycol, sign, done in [("up", "remaining_up_bp", 1.0, "high_done"), ("dn", "remaining_down_bp", -1.0, "low_done")]:
        base = oos[oos[done] == 0] if conditional else oos
        mcol, kcol = (f"rem_{side}_%s_if_open", f"kqo_{side}_%s") if conditional else (f"rem_{side}_%s", f"kq_{side}_%s")
        for q in QUANTILES:
            tag = f"p{int(q * 100)}"
            for name, g in [(f"k={kk}", base[base["k"] == kk]) for kk in range(MAX_K + 1)] + [("pooled", base)]:
                y = sign * g[ycol].values                       # magnitudes, >= 0
                qm = sign * g[mcol % tag].values
                qk = sign * g[kcol % tag].values
                pm, pk = _pinball(y, qm, q), _pinball(y, qk, q)
                rows.append(dict(target=f"rem_{side}", q=q, k=name, n=len(g), median_actual=float(np.median(y)),
                                 pinball_model=pm, pinball_konly=pk, skill=1 - pm / pk if pk > 0 else np.nan,
                                 coverage_model=float(np.mean(y <= qm)), coverage_konly=float(np.mean(y <= qk)),
                                 mean_pred=float(np.mean(qm))))
    return pd.DataFrame(rows)


def report(oos: pd.DataFrame, sym: str) -> str:
    lines = []
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    h1 = oos[oos["date"] < H2_START]; h2 = oos[oos["date"] >= H2_START]
    lines.append(f"=== {sym} intra-session detector: OOS {oos['date'].min().date()} .. {oos['date'].max().date()}, "
                 f"{oos['date'].nunique()} sessions, {len(oos)} rows (k=0..7), "
                 f"calibrated rows {oos['calibrated'].mean():.0%}; H1 {h1['date'].nunique()} sessions, H2 {h2['date'].nunique()} ===")
    for side in ("high", "low"):
        lines.append(f"\n--- {side}_done: per-k and pooled (Brier; skill = 1 - Brier_final/Brier_konly) ---")
        lines.append(classification_table(oos, side).to_string())
        sub = []
        for name, g in (("H1 (<2025-09-01)", h1), ("H2 (>=2025-09-01)", h2)):
            ct = classification_table(g, side)[["n", "rate", "brier_konly", "brier_final", "auc_final", "skill_vs_konly"]]
            ct.columns = pd.MultiIndex.from_product([[name], ct.columns])
            sub.append(ct)
        lines.append(f"\n--- {side}_done by half ---")
        lines.append(pd.concat(sub, axis=1).to_string())
        lines.append(f"\n--- {side}_done calibration (final p, 5 buckets, pooled over k) ---")
        lines.append(calibration_table(oos, side).to_string())
        lines.append(f"    H1: " + calibration_table(h1, side)["obs_rate"].round(3).tolist().__repr__() +
                     "  H2: " + calibration_table(h2, side)["obs_rate"].round(3).tolist().__repr__())
    qt = quantile_table(oos)
    lines.append("\n--- remaining move quantiles (pinball loss vs per-k training quantiles; coverage should be ~q) ---")
    lines.append(qt[qt["k"] == "pooled"].set_index(["target", "q"]).to_string())
    lines.append("\n    per-k skill (rem_up P50 / P80, rem_dn P50 / P80):")
    for kk in range(MAX_K + 1):
        g = qt[qt["k"] == f"k={kk}"].set_index(["target", "q"])["skill"]
        lines.append(f"    k={kk}: {g[('rem_up', 0.5)]:+.3f} / {g[('rem_up', 0.8)]:+.3f}   {g[('rem_dn', 0.5)]:+.3f} / {g[('rem_dn', 0.8)]:+.3f}")
    for name, g in (("H1", h1), ("H2", h2)):
        q = quantile_table(g); q = q[q["k"] == "pooled"].set_index(["target", "q"])
        lines.append(f"    {name} pooled skill: " + ", ".join(f"{a}@{b}: {v:+.3f} (cov {c:.2f})" for (a, b), v, c in
                                                            zip(q.index, q["skill"], q["coverage_model"])))
    qc = quantile_table(oos, conditional=True)
    lines.append("\n--- CONDITIONAL quantiles '_if_open', evaluated only on rows where the extreme was NOT yet in "
                 "(ex-post subset; baseline = per-k training quantile of the same not-yet-in rows) ---")
    lines.append(qc[qc["k"] == "pooled"].set_index(["target", "q"]).to_string())
    lines.append("\n    per-k coverage of the P80_if_open on not-yet-in rows (target 0.80), model / k-only:")
    for kk in range(MAX_K + 1):
        g = qc[(qc["k"] == f"k={kk}") & (qc["q"] == 0.8)].set_index("target")
        lines.append(f"    k={kk}: up {g.loc['rem_up', 'coverage_model']:.2f}/{g.loc['rem_up', 'coverage_konly']:.2f} "
                     f"(n={int(g.loc['rem_up', 'n'])}, skill {g.loc['rem_up', 'skill']:+.3f})   "
                     f"dn {g.loc['rem_dn', 'coverage_model']:.2f}/{g.loc['rem_dn', 'coverage_konly']:.2f} "
                     f"(n={int(g.loc['rem_dn', 'n'])}, skill {g.loc['rem_dn', 'skill']:+.3f})")
    for name, g in (("H1", h1), ("H2", h2)):
        q = quantile_table(g, conditional=True); q = q[q["k"] == "pooled"].set_index(["target", "q"])
        lines.append(f"    {name} pooled (if_open) skill: " + ", ".join(f"{a}@{b}: {v:+.3f} (cov {c:.2f})" for (a, b), v, c in
                                                                      zip(q.index, q["skill"], q["coverage_model"])))
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------------
# live use
# --------------------------------------------------------------------------------------------------
_CACHE: dict = {}


def _bundle(sym: str, date: pd.Timestamp) -> dict:
    """Models fitted on every full session strictly before `date`, calibrators from prior OOS predictions."""
    key = (sym, date)
    if key in _CACHE:
        return _CACHE[key]
    d = build_dataset(sym)
    tr = d[d["date"] < date]
    if tr["date"].nunique() < TRAIN_ONLY_SESSIONS:
        raise ValueError(f"only {tr['date'].nunique()} training sessions before {date.date()}")
    m = fit_models(tr)
    cal, cal_sessions = {}, 0
    f = os.path.join(HERE, f"oos_intrasession_{sym}.csv")
    if os.path.exists(f):
        oos = pd.read_csv(f, parse_dates=["date"])
        hist = oos[oos["date"] < date]
        cal = fit_calibrators(hist)
        cal_sessions = int(hist["date"].nunique()) if cal else 0
    b = {"models": m, "cal": cal, "cal_sessions": cal_sessions}
    _CACHE[key] = b
    return b


def predict_now(sym: str, date, k: int, top_n: int = 5) -> dict:
    """Detector output at the close of bar k of the Asia session that follows RTH date `date`.

    The models are fitted on every full session strictly before `date`; the isotonic calibrators on the
    prior out-of-sample predictions in oos_intrasession_<SYM>.csv (raw ensemble if that file is absent or
    holds fewer than MIN_CAL_SESSIONS prior sessions).  Contributions are the logistic component's
    coefficient * standardised feature value (log-odds units), top `top_n` by magnitude.
    """
    date = pd.Timestamp(date)
    x, p = load_tables(sym)
    d = build_dataset(sym, x, p, full_sessions_only=False)
    row = d[(d["date"] == date) & (d["k"] == int(k))]
    if row.empty:
        raise ValueError(f"no panel row for {sym} {date.date()} k={k}")
    b = _bundle(sym, date)
    m = b["models"]
    out = apply_calibrators(predict_models(m, row), b["cal"]).iloc[0]
    res = {
        "sym": sym, "date": str(date.date()), "k": int(k), "hour_et": int(row["hour_et"].iloc[0]),
        "n_bars": int(row["n_bars"].iloc[0]),
        "p_high_done": float(out["p_high_done"]), "p_low_done": float(out["p_low_done"]),
        "p_high_raw": float(out["p_high_raw"]), "p_low_raw": float(out["p_low_raw"]),
        "p_high_lr": float(out["p_high_lr"]), "p_high_gb": float(out["p_high_gb"]),
        "p_low_lr": float(out["p_low_lr"]), "p_low_gb": float(out["p_low_gb"]),
        "k_only_high": float(out["kbase_high"]), "k_only_low": float(out["kbase_low"]),
        "rem_up_p50": float(out["rem_up_p50"]), "rem_up_p80": float(out["rem_up_p80"]),
        "rem_dn_p50": float(out["rem_dn_p50"]), "rem_dn_p80": float(out["rem_dn_p80"]),
        "k_only_rem_up_p50": float(out["kq_up_p50"]), "k_only_rem_up_p80": float(out["kq_up_p80"]),
        "k_only_rem_dn_p50": float(out["kq_dn_p50"]), "k_only_rem_dn_p80": float(out["kq_dn_p80"]),
        "rem_up_p50_if_open": float(out["rem_up_p50_if_open"]), "rem_up_p80_if_open": float(out["rem_up_p80_if_open"]),
        "rem_dn_p50_if_open": float(out["rem_dn_p50_if_open"]), "rem_dn_p80_if_open": float(out["rem_dn_p80_if_open"]),
        "calibrated": bool(b["cal"]), "calibration_sessions": b["cal_sessions"],
        "n_train_sessions": int(m["n_train_sessions"]),
        "features": {f: (None if pd.isna(row[f].iloc[0]) else float(row[f].iloc[0])) for f in FEATURES},
    }
    D = lr_design(row)
    for t in TARGETS:
        s = t.split("_")[0]
        pipe = m[f"lr_{t}"]
        z = pipe[:-1].transform(D)[0]
        coef = pipe[-1].coef_[0]
        contrib = pd.Series(coef * z, index=m["design_cols"])
        top = contrib.reindex(contrib.abs().sort_values(ascending=False).index).head(top_n)
        res[f"top_contributions_{s}"] = [(name, round(float(v), 3)) for name, v in top.items()]
        res[f"lr_intercept_{s}"] = float(pipe[-1].intercept_[0])
    return res


# --------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    syms = [a.upper() for a in sys.argv[1:]] or ["NQ", "ES"]
    for sym in syms:
        print(f"\n##### {sym} #####")
        oos = train_walk_forward(sym, verbose=True)
        f = os.path.join(HERE, f"oos_intrasession_{sym}.csv")
        oos.to_csv(f, index=False)
        print(f"wrote {f}  ({len(oos)} rows)")
        print(report(oos, sym))
