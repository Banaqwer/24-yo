"""
Intra-session Asia HIGH / LOW detector: "is the Asia high / low already in?"

At the close of each hourly Asia bar k (0 = the 18:00 ET bar) the detector answers, using only
information known at that close:

    p_high_done      P(the SESSION high 18:00-02:59 is already in)    (label: hourly panel high_done)
    p_low_done       P(the session low is already in)                 (label: low_done)
    p_ovn_high_done  P(the OVERNIGHT high 18:00-08:59 is already in)  (label: overnight_high_done)
    p_ovn_low_done   P(the overnight low is already in)               (label: overnight_low_done)
    rem_up_p50/80    quantiles of remaining_up_bp  = (session high / close_k - 1) * 1e4   (>= 0)
    rem_dn_p50/80    quantiles of remaining_down_bp = (session low / close_k - 1) * 1e4   (<= 0, reported signed)

    The overnight labels are the question a trader actually asks: a bar-8 Asia extreme is exceeded in
    the following Europe session 80-85% of the time, so "the Asia high is in" is not "the high is in".
    The overnight window is the Asia bars plus the Europe bars 03:00-08:59 of the same Globex date;
    the label is NaN when those Europe bars are missing from the file and such rows are left out of
    the overnight training sets (and only those).

    remaining_up_bp is the distance from the current close to the SESSION high: when the high is already
    in it is the (positive) distance back up to that high, and price will not trade above it; when the
    high is not in it is the room still to run.  Its P80 is therefore an 80% envelope for "how far above
    here can the session high be".  Because that marginal envelope mixes the two states, a second set of
    quantiles is fitted on the rows where the extreme was NOT yet in (rem_up_p50_if_open, ...): "if the
    high is still ahead, how far is it".  They are evaluated on the not-yet-in rows (an ex-post subset,
    so their coverage is a conditional statement, not a marginal one).

Bar index k and the last bar: the session targets are modelled for k = 0..MAX_K (7); at k = 8 (the
02:00 bar, the last bar of a full night) the session extremes are in by definition, so predict_now
reports p_high_done = p_low_done = 1 and the exact remaining distances there without a model.  The
overnight targets are modelled for k = 0..OVN_MAX_K (8) with their own k = 8 dummy in the logistic
design, because at the close of bar 8 "will Europe take out the Asia extreme?" is the live question.

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
missing 00:00-02:00 bars make their labels unreliable) and contract-splice sessions excluded
(asia_extremes.SPLICE_SESSIONS, the single splice list shared with the pre-Asia module).

Live use: predict_now() uses the stored panel row when the caller reads the hourly FILE (h=None) and
the tables hold (date, k) (a night with >= 6 bars); otherwise - the night is not in the tables yet,
or the caller passed an hourly frame `h` - the row is built from the bars with
asia_extremes.live_panel_row, which drops the trailing bar when it is not complete as of `asof`
(default now, US/Eastern).  A frame passed as `h` is the data the caller wants used, so it always
takes the live path (live=True); the live row equals the stored row on every feature, so the numbers
do not depend on the path.  A night that is not in the extremes table yet gets its 18:00 features
from asia_extremes.live_extremes_row.  Contract-splice nights (asia_extremes.SPLICE_SESSIONS) and a
night whose first bar in the data is not the 18:00 bar (bar index k would be shifted) raise ValueError.

Usage:
    python detector_intrasession.py [NQ] [ES]
        -> writes research/extremes/oos_intrasession_<SYM>.csv and prints the metric tables
    python detector_intrasession.py --now NQ [--date YYYY-MM-DD] [--k K] [--asof 'YYYY-MM-DD HH:MM']
        -> compact live summary at the close of bar k (default: the latest complete bar of the
           latest RTH date's night)
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


def _package_root() -> str:
    """The asia_premarket package root (two levels above this file), added to sys.path on import."""
    root = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


_package_root()
try:
    from asia_extremes import SPLICE_SESSIONS
except Exception:                                   # literal fallback only if the package import fails
    SPLICE_SESSIONS = {
        "NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16", "2025-09-17", "2025-12-16", "2025-12-17"],
        "ES": ["2025-09-16", "2025-09-17", "2025-12-16", "2025-12-17"],
    }
SPLICE_DATES = SPLICE_SESSIONS                      # backward-compatible alias

SEED = 0
TRAIN_ONLY_SESSIONS = 120      # first sessions never predicted
MIN_CAL_SESSIONS = 60          # prior OOS sessions needed before isotonic calibration is switched on
H2_START = pd.Timestamp("2025-09-01")
MAX_K = 7                      # session targets: k = 8 is the last bar, where both labels are trivially 1
OVN_MAX_K = 8                  # overnight targets are defined at every bar, including the 02:00 bar
N_BOOT = 1000

FEATURES = [
    "k", "bars_since_hi", "bars_since_lo", "pos_in_range", "run_rng_vs_med20", "med_rng_bp",
    "bar_close_loc", "bar_ret_bp", "bar_rng_rel", "vol_dir", "dist_run_hi_bp", "dist_run_lo_bp",
    "run_hi_above_rth_high", "run_lo_below_rth_low", "sd_rth_high", "sd_rth_low",
    "sunday_open", "fomc_tomorrow", "ah_print", "vix",
]
FEATURES_1800 = ["sunday_open", "fomc_tomorrow", "megacap_earnings_tonight", "post_ret", "vix", "asia_rng_med20"]
TARGETS = ["high_done", "low_done"]
OVN_TARGETS = ["overnight_high_done", "overnight_low_done"]
ALL_TARGETS = TARGETS + OVN_TARGETS
# short name used in the output columns (p_<side>_lr / _gb / _raw / _done, base_<side>, kbase_<side>)
SIDE = {"high_done": "high", "low_done": "low", "overnight_high_done": "ovn_high", "overnight_low_done": "ovn_low"}
LABEL = {v: k for k, v in SIDE.items()}
SIDE_MAX_K = {"high": MAX_K, "low": MAX_K, "ovn_high": OVN_MAX_K, "ovn_low": OVN_MAX_K}
SIDES = list(SIDE.values())
QUANTILES = [0.5, 0.8]


# --------------------------------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------------------------------
def load_tables(sym: str):
    x = pd.read_csv(os.path.join(HERE, f"{sym}_extremes.csv"), index_col="date", parse_dates=True)
    p = pd.read_csv(os.path.join(HERE, f"{sym}_hourly_panel.csv"), parse_dates=["date"])
    return x, p


def engineer(d: pd.DataFrame) -> pd.DataFrame:
    """The derived detector features from a panel frame already joined with the 18:00 columns."""
    d = d.copy()
    for t in OVN_TARGETS:
        if t not in d.columns:
            d[t] = np.nan
    d["med_rng_bp"] = d["asia_rng_med20"] * 1e4
    d["vol_dir"] = d["bar_vol_rel"].fillna(1.0) * np.sign(d["bar_ret_bp"])
    d["dist_run_hi_bp"] = d["run_hi_bp"] - d["cum_ret_bp"]
    d["dist_run_lo_bp"] = d["cum_ret_bp"] - d["run_lo_bp"]
    d["sd_rth_high"] = d["dist_rth_high_bp"] / d["med_rng_bp"]      # + : RTH high above the close
    d["sd_rth_low"] = -d["dist_rth_low_bp"] / d["med_rng_bp"]       # + : RTH low below the close
    d["ah_print"] = ((d["megacap_earnings_tonight"] == 1) | (d["post_ret"].abs() >= 0.0025)).astype(int)
    d["rem_dn_mag"] = -d["remaining_down_bp"]
    return d


def build_dataset(sym: str, x: pd.DataFrame | None = None, p: pd.DataFrame | None = None,
                  full_sessions_only: bool = True) -> pd.DataFrame:
    """Panel rows k<=8 with the 20 detector features, the labels and the 18:00 flags joined by date.
    (The session targets are fitted on k<=MAX_K only; the k=8 rows serve the overnight targets.)"""
    if x is None or p is None:
        x, p = load_tables(sym)
    d = p.merge(x[FEATURES_1800], left_on="date", right_index=True, how="left")
    d = d[d["k"] <= OVN_MAX_K].copy()
    d = d[~d["date"].isin(pd.to_datetime(SPLICE_SESSIONS.get(sym, [])))]
    if full_sessions_only:
        d = d[d["n_bars"] == 9]
    d = engineer(d)
    d = d.sort_values(["date", "k"]).reset_index(drop=True)
    return d


def lr_design(X: pd.DataFrame, max_k: int = MAX_K) -> pd.DataFrame:
    """Fixed non-linear design for the logistic component (no fitting involved); k dummies 0..max_k."""
    D = pd.DataFrame(index=X.index)
    for kk in range(max_k + 1):
        D[f"k={kk}"] = (X["k"] == kk).astype(float)
    D["bars_since_hi==0"] = (X["bars_since_hi"] == 0).astype(float)
    D["bars_since_lo==0"] = (X["bars_since_lo"] == 0).astype(float)
    D["log1p_bars_since_hi"] = np.log1p(X["bars_since_hi"])
    D["log1p_bars_since_lo"] = np.log1p(X["bars_since_lo"])
    D["pos_in_range"] = X["pos_in_range"]
    D["pos_in_range*k"] = X["pos_in_range"] * X["k"] / max_k
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
    """Fit every component on the training rows `tr` (all rows strictly before the prediction block).

    Session targets and the remaining-move quantiles use the rows k <= MAX_K; the overnight targets use
    the rows k <= OVN_MAX_K whose overnight label is not NaN (only those rows are dropped, only there).
    """
    trs = tr[tr["k"] <= MAX_K]
    X = trs[FEATURES]
    D = lr_design(trs, MAX_K)
    m = {"n_train_sessions": tr["date"].nunique(), "n_train_rows": len(trs), "design_cols": list(D.columns)}
    for t in TARGETS:
        y = trs[t].values
        m[f"lr_{t}"] = _lr().fit(D, y)
        m[f"gb_{t}"] = _gb().fit(X, y)
        m[f"base_{t}"] = float(y.mean())
        m[f"kbase_{t}"] = trs.groupby("k")[t].mean()
    for t in OVN_TARGETS:
        tro = tr[tr[t].notna()]
        Do = lr_design(tro, OVN_MAX_K)
        y = tro[t].astype(int).values
        m[f"lr_{t}"] = _lr().fit(Do, y)
        m[f"gb_{t}"] = _gb().fit(tro[FEATURES], y)
        m[f"base_{t}"] = float(y.mean())
        m[f"kbase_{t}"] = tro.groupby("k")[t].mean()
        m[f"n_train_rows_{t}"] = len(tro)
        m["design_cols_ovn"] = list(Do.columns)
    up_open = trs[trs["high_done"] == 0]          # conditional models: the extreme was still ahead
    dn_open = trs[trs["low_done"] == 0]
    for q in QUANTILES:
        m[f"q_up_{q}"] = _qgb(q).fit(X, trs["remaining_up_bp"].values)
        m[f"q_dn_{q}"] = _qgb(q).fit(X, trs["rem_dn_mag"].values)
        m[f"kq_up_{q}"] = trs.groupby("k")["remaining_up_bp"].quantile(q)
        m[f"kq_dn_{q}"] = trs.groupby("k")["rem_dn_mag"].quantile(q)
        m[f"qo_up_{q}"] = _qgb(q).fit(up_open[FEATURES], up_open["remaining_up_bp"].values)
        m[f"qo_dn_{q}"] = _qgb(q).fit(dn_open[FEATURES], dn_open["rem_dn_mag"].values)
        m[f"kqo_up_{q}"] = up_open.groupby("k")["remaining_up_bp"].quantile(q)
        m[f"kqo_dn_{q}"] = dn_open.groupby("k")["rem_dn_mag"].quantile(q)
    return m


def predict_models(m: dict, te: pd.DataFrame) -> pd.DataFrame:
    """Raw (uncalibrated) predictions and walk-forward baselines for the rows `te`.
    Session-target and remaining-move columns are NaN on rows with k > MAX_K."""
    out = te[["date", "k"] + ALL_TARGETS + ["remaining_up_bp", "remaining_down_bp"]].copy()
    sess = (te["k"] <= MAX_K).values
    X = te.loc[sess, FEATURES]
    D = lr_design(te.loc[sess], MAX_K)
    for t in TARGETS:
        s = SIDE[t]
        for c in (f"p_{s}_lr", f"p_{s}_gb", f"p_{s}_raw", f"base_{s}", f"kbase_{s}"):
            out[c] = np.nan
        if sess.any():
            out.loc[sess, f"p_{s}_lr"] = m[f"lr_{t}"].predict_proba(D)[:, 1]
            out.loc[sess, f"p_{s}_gb"] = m[f"gb_{t}"].predict_proba(X)[:, 1]
            out.loc[sess, f"p_{s}_raw"] = 0.5 * (out.loc[sess, f"p_{s}_lr"] + out.loc[sess, f"p_{s}_gb"])
            out.loc[sess, f"base_{s}"] = m[f"base_{t}"]
            out.loc[sess, f"kbase_{s}"] = te.loc[sess, "k"].map(m[f"kbase_{t}"]).values
    Xo = te[FEATURES]
    Do = lr_design(te, OVN_MAX_K)
    for t in OVN_TARGETS:
        s = SIDE[t]
        out[f"p_{s}_lr"] = m[f"lr_{t}"].predict_proba(Do)[:, 1]
        out[f"p_{s}_gb"] = m[f"gb_{t}"].predict_proba(Xo)[:, 1]
        out[f"p_{s}_raw"] = 0.5 * (out[f"p_{s}_lr"] + out[f"p_{s}_gb"])
        out[f"base_{s}"] = m[f"base_{t}"]
        out[f"kbase_{s}"] = te["k"].map(m[f"kbase_{t}"]).values
    for q in QUANTILES:
        tag = f"p{int(q * 100)}"
        cols = [f"rem_up_{tag}", f"rem_dn_{tag}", f"kq_up_{tag}", f"kq_dn_{tag}",
                f"rem_up_{tag}_if_open", f"rem_dn_{tag}_if_open", f"kqo_up_{tag}", f"kqo_dn_{tag}"]
        for c in cols:
            out[c] = np.nan
        if sess.any():
            kk = te.loc[sess, "k"]
            out.loc[sess, f"rem_up_{tag}"] = np.clip(m[f"q_up_{q}"].predict(X), 0, None)
            out.loc[sess, f"rem_dn_{tag}"] = -np.clip(m[f"q_dn_{q}"].predict(X), 0, None)
            out.loc[sess, f"kq_up_{tag}"] = kk.map(m[f"kq_up_{q}"]).values
            out.loc[sess, f"kq_dn_{tag}"] = -kk.map(m[f"kq_dn_{q}"]).values
            out.loc[sess, f"rem_up_{tag}_if_open"] = np.clip(m[f"qo_up_{q}"].predict(X), 0, None)
            out.loc[sess, f"rem_dn_{tag}_if_open"] = -np.clip(m[f"qo_dn_{q}"].predict(X), 0, None)
            out.loc[sess, f"kqo_up_{tag}"] = kk.map(m[f"kqo_up_{q}"]).values
            out.loc[sess, f"kqo_dn_{tag}"] = -kk.map(m[f"kqo_dn_{q}"]).values
    return out


def fit_calibrators(hist: pd.DataFrame) -> dict:
    """Isotonic calibrators fitted on PRIOR out-of-sample predictions only (one per target; rows whose
    label or raw probability is NaN are left out of that target's fit only)."""
    cal = {}
    if hist is None or hist["date"].nunique() < MIN_CAL_SESSIONS:
        return cal
    for t in ALL_TARGETS:
        s = SIDE[t]
        hs = hist[hist[t].notna() & hist[f"p_{s}_raw"].notna()]
        if hs["date"].nunique() < MIN_CAL_SESSIONS:
            continue
        cal[s] = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(hs[f"p_{s}_raw"], hs[t].astype(int))
    return cal


def apply_calibrators(out: pd.DataFrame, cal: dict) -> pd.DataFrame:
    out = out.copy()
    out["calibrated"] = int(bool(cal))
    for t in ALL_TARGETS:
        s = SIDE[t]
        raw = out[f"p_{s}_raw"]
        ok = raw.notna().values
        p = raw.values.astype(float).copy()
        if s in cal and ok.any():
            p[ok] = cal[s].predict(raw.values[ok])
        out[f"p_{s}_done"] = p
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
            print(f"  {sym} block {ym}: train {m['n_train_sessions']} sessions / {m['n_train_rows']} rows "
                  f"(overnight {m['n_train_rows_overnight_high_done']}), "
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


def _side_rows(oos: pd.DataFrame, side: str) -> pd.DataFrame:
    """Rows on which the target `side` is defined: k <= its max k, label and final p not NaN."""
    t = LABEL[side]
    return oos[(oos["k"] <= SIDE_MAX_K[side]) & oos[t].notna() & oos[f"p_{side}_done"].notna()]


def classification_table(oos: pd.DataFrame, side: str) -> pd.DataFrame:
    """Per-k and pooled metrics for one side: 'high', 'low' (session) or 'ovn_high', 'ovn_low' (overnight)."""
    t = LABEL[side]
    base = _side_rows(oos, side)
    rows = []
    groups = [(f"k={kk}", base[base["k"] == kk]) for kk in range(SIDE_MAX_K[side] + 1)] + [("pooled", base)]
    for name, g in groups:
        y = g[t].values.astype(float)
        if len(g) == 0:
            rows.append(dict(k=name, n=0)); continue
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
    t = LABEL[side]
    oos = _side_rows(oos, side)
    b = pd.cut(oos[col].clip(0, 1), [0, 0.2, 0.4, 0.6, 0.8, 1.0], include_lowest=True)
    g = oos.groupby(b, observed=False)
    return pd.DataFrame({"n": g.size(), "mean_pred": g[col].mean(), "obs_rate": g[t].mean()})


def quantile_table(oos: pd.DataFrame, conditional: bool = False) -> pd.DataFrame:
    """Pinball loss and coverage of the remaining-move quantiles vs the per-k training quantiles.

    conditional=True evaluates the `_if_open` quantiles on the rows where the extreme was NOT yet in
    (an ex-post subset) against the per-k training quantiles of the same not-yet-in rows.
    """
    oos = oos[oos["k"] <= MAX_K]
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


def headline(oos: pd.DataFrame, side: str, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Headline numbers for one side from the calibrated p_<side>_done column: Brier vs the base and
    k-only baselines, AUC, skill vs k-only with a 90% bootstrap CI over sessions, skill by half
    (H2 = date >= H2_START), precision at p >= 0.90 / 0.95 and the done rate at p <= 0.10."""
    t = LABEL[side]
    g = _side_rows(oos, side)
    y = g[t].values.astype(float); p = g[f"p_{side}_done"].values.astype(float)
    kb = g[f"kbase_{side}"].values.astype(float); bb = g[f"base_{side}"].values.astype(float)
    ef = (p - y) ** 2; ek = (kb - y) ** 2
    skill = 1 - ef.mean() / ek.mean()
    # bootstrap over sessions: per-date sums of squared errors, ratio of sums
    dsum = pd.DataFrame({"f": ef, "k": ek}, index=g["date"].values).groupby(level=0).sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(dsum), (n_boot, len(dsum)))
    sf = dsum["f"].values[idx].sum(axis=1); sk = dsum["k"].values[idx].sum(axis=1)
    boots = 1 - sf / sk
    h1 = (g["date"] < H2_START).values; h2 = ~h1

    def _skill(mask):
        return float(1 - ef[mask].mean() / ek[mask].mean()) if mask.sum() > 10 else np.nan

    def _prec(mask):
        return (float(y[mask].mean()) if mask.sum() else np.nan, int(mask.sum()))

    p90, n90 = _prec(p >= 0.90); p95, n95 = _prec(p >= 0.95); p10, n10 = _prec(p <= 0.10)
    return dict(brier_base=_brier(y, bb), brier_konly=float(ek.mean()), brier_final=float(ef.mean()),
                auc=_auc(y, p), skill_vs_konly=float(skill),
                skill_ci_lo=float(np.nanpercentile(boots, 5)), skill_ci_hi=float(np.nanpercentile(boots, 95)),
                skill_h1=_skill(h1), skill_h2=_skill(h2),
                prec_p90=p90, n_p90=n90, prec_p95=p95, n_p95=n95, done_rate_p10=p10, n_p10=n10,
                n_rows=int(len(g)), n_sessions=int(g["date"].nunique()),
                oos_start=str(pd.Timestamp(g["date"].min()).date()), oos_end=str(pd.Timestamp(g["date"].max()).date()))


def report(oos: pd.DataFrame, sym: str) -> str:
    lines = []
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    h1 = oos[oos["date"] < H2_START]; h2 = oos[oos["date"] >= H2_START]
    ns = oos[oos["k"] <= MAX_K]
    lines.append(f"=== {sym} intra-session detector: OOS {oos['date'].min().date()} .. {oos['date'].max().date()}, "
                 f"{oos['date'].nunique()} sessions, {len(ns)} rows (k=0..{MAX_K}) + {len(oos) - len(ns)} k={OVN_MAX_K} rows "
                 f"(overnight targets only), calibrated rows {oos['calibrated'].mean():.0%}; "
                 f"H1 {h1['date'].nunique()} sessions, H2 {h2['date'].nunique()} ===")
    for side in SIDES:
        t = LABEL[side]
        lines.append(f"\n--- {t}: per-k and pooled (Brier; skill = 1 - Brier_final/Brier_konly) ---")
        lines.append(classification_table(oos, side).to_string())
        sub = []
        for name, g in (("H1 (<2025-09-01)", h1), ("H2 (>=2025-09-01)", h2)):
            ct = classification_table(g, side)[["n", "rate", "brier_konly", "brier_final", "auc_final", "skill_vs_konly"]]
            ct.columns = pd.MultiIndex.from_product([[name], ct.columns])
            sub.append(ct)
        lines.append(f"\n--- {t} by half ---")
        lines.append(pd.concat(sub, axis=1).to_string())
        lines.append(f"\n--- {t} calibration (final p, 5 buckets, pooled over k) ---")
        lines.append(calibration_table(oos, side).to_string())
        lines.append(f"    H1: " + calibration_table(h1, side)["obs_rate"].round(3).tolist().__repr__() +
                     "  H2: " + calibration_table(h2, side)["obs_rate"].round(3).tolist().__repr__())
        hl = headline(oos, side)
        lines.append(f"    headline: skill vs k-only {hl['skill_vs_konly']:+.3f} [90% CI {hl['skill_ci_lo']:+.3f}, {hl['skill_ci_hi']:+.3f}] "
                     f"H1 {hl['skill_h1']:+.3f} H2 {hl['skill_h2']:+.3f} AUC {hl['auc']:.3f}; "
                     f"precision p>=0.90: {hl['prec_p90']:.3f} (n={hl['n_p90']}), p>=0.95: {hl['prec_p95']:.3f} (n={hl['n_p95']}); "
                     f"done rate p<=0.10: {hl['done_rate_p10']:.3f} (n={hl['n_p10']})")
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
        for t in ALL_TARGETS:                       # an OOS file written before the overnight targets existed
            if t not in oos.columns:
                oos[t] = np.nan; oos[f"p_{SIDE[t]}_raw"] = np.nan
        hist = oos[oos["date"] < date]
        cal = fit_calibrators(hist)
        cal_sessions = int(hist["date"].nunique()) if cal else 0
    b = {"models": m, "cal": cal, "cal_sessions": cal_sessions}
    _CACHE[key] = b
    return b


def _feature_row(sym: str, date: pd.Timestamp, k, asof, h, x: pd.DataFrame, p: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The detector feature row for (date, k): the stored panel row when the hourly FILE is read
    (h=None), the tables hold (date, k) and bar k is complete as of `asof`; else a row built live from
    the bars of `h`.  An explicitly passed `h` always takes the live path: it is the data the caller
    wants used (a truncated frame, a replay), and the stored tables were built from the full file.
    Returns (row, info)."""
    import asia_extremes as ae
    explicit_h = h is not None
    if date in pd.to_datetime(SPLICE_SESSIONS.get(sym, [])):
        raise ValueError(f"{sym} {date.date()}: contract-splice session (asia_extremes.SPLICE_SESSIONS); "
                         f"its bars toggle between two contracts, so no detector row is served")
    h = ae.load_h(sym, h)
    cut = ae._asof(asof)
    g, dropped, _ = ae.night_bars(h, date, cut)
    latest = len(g) - 1
    if latest < 0:
        raise ValueError(f"{sym} {date.date()}: no complete Asia bar as of {cut:%Y-%m-%d %H:%M %Z}")
    if g.index[0].hour != 18:
        raise ValueError(f"{sym} {date.date()}: the first Asia bar in the data is stamped {g.index[0]:%H:%M %Z}, "
                         f"not 18:00 - bar index k would be shifted (missing 18:00 bar?); no detector row is served")
    if k is None:
        k = latest
    k = int(k)
    if k > latest:
        raise ValueError(f"{sym} {date.date()}: bar k={k} is not complete as of {cut:%Y-%m-%d %H:%M %Z} "
                         f"(latest_complete_k={latest})")
    if k > OVN_MAX_K:
        raise ValueError(f"k={k} beyond the last Asia bar (k <= {OVN_MAX_K})")
    info = dict(k=k, bar_ts=str(g.index[k]), latest_complete_k=int(latest), partial_bar_dropped=bool(dropped),
                n_bars_so_far=int(len(g)))
    stored = p[(p["date"] == date) & (p["k"] == k)]
    if not explicit_h and not stored.empty and date in x.index:
        d = build_dataset(sym, x, p, full_sessions_only=False)
        row = d[(d["date"] == date) & (d["k"] == k)]
        if not row.empty:                       # (empty only for a date build_dataset drops)
            info["live"] = False
            info["n_bars"] = int(row["n_bars"].iloc[0])
            return row, info
    lp = ae.live_panel_row(sym, date, k, h=h, asof=cut)
    x18 = x.loc[[date], FEATURES_1800] if date in x.index else ae.live_extremes_row(sym, date, h=h)[FEATURES_1800]
    row = engineer(lp.merge(x18, left_on="date", right_index=True, how="left"))
    info["live"] = True
    info["n_bars"] = None
    return row, info


def predict_now(sym: str, date, k: int | None = None, top_n: int = 5, asof=None, h: pd.DataFrame | None = None) -> dict:
    """Detector output at the close of bar k of the Asia session that follows RTH date `date`.

    k=None -> the latest bar that is complete as of `asof` (default now, US/Eastern; a bar stamped ts is
    complete iff ts + 1 hour <= asof).  With h=None the hourly file is read and the stored panel row is
    used when it exists (live=False); when `h` is an hourly frame passed by the caller, or the night is
    not in the tables yet, the row is built live from the bars (live=True; the same numbers, the live
    row equals the stored row on every feature).  At k = 8 the session extremes are in by definition:
    p_high_done = p_low_done = 1 and the remaining distances are the exact distances back to the
    running extremes, (session high / close_k - 1) * 1e4 and (session low / close_k - 1) * 1e4 like
    the labels; the overnight probabilities are modelled there.  Raises ValueError for a contract-
    splice session, a night whose first bar in the data is not the 18:00 bar, an incomplete bar k, or
    no complete bar yet.

    The models are fitted on every full session strictly before `date`; the isotonic calibrators on the
    prior out-of-sample predictions in oos_intrasession_<SYM>.csv (raw ensemble if that file is absent or
    holds fewer than MIN_CAL_SESSIONS prior sessions).  Contributions are the logistic component's
    coefficient * standardised feature value (log-odds units), top `top_n` by magnitude.
    """
    import asia_extremes as ae
    date = pd.Timestamp(date).normalize()
    x, p = load_tables(sym)
    row, info = _feature_row(sym, date, k, asof, h, x, p)
    k = info["k"]
    b = _bundle(sym, date)
    m = b["models"]
    out = apply_calibrators(predict_models(m, row), b["cal"]).iloc[0]
    r0 = row.iloc[0]
    res = {
        "sym": sym, "date": str(date.date()), "k": int(k), "hour_et": int(r0["hour_et"]),
        "n_bars": info["n_bars"], "live": info["live"], "bar_ts": info["bar_ts"],
        "latest_complete_k": info["latest_complete_k"], "partial_bar_dropped": info["partial_bar_dropped"],
        "n_bars_so_far": info["n_bars_so_far"], "asof": str(ae._asof(asof)),
        "short_session_warning": ae.short_session_warning(sym, date),
    }
    last_bar = k > MAX_K
    if last_bar:
        # the session extremes are in by definition at the close of the last bar; the exact remaining
        # distances use the label's definition (session extreme / close_k - 1) * 1e4, i.e. close-
        # denominated, not the ref-close-denominated difference dist_run_hi_bp = run_hi_bp - cum_ret_bp
        cum = float(r0["cum_ret_bp"])
        up = ((1 + float(r0["run_hi_bp"]) / 1e4) / (1 + cum / 1e4) - 1) * 1e4
        dn = ((1 + float(r0["run_lo_bp"]) / 1e4) / (1 + cum / 1e4) - 1) * 1e4
        res.update({
            "p_high_done": 1.0, "p_low_done": 1.0, "p_high_raw": 1.0, "p_low_raw": 1.0,
            "p_high_lr": 1.0, "p_high_gb": 1.0, "p_low_lr": 1.0, "p_low_gb": 1.0,
            "k_only_high": 1.0, "k_only_low": 1.0,
            "rem_up_p50": up, "rem_up_p80": up, "rem_dn_p50": dn, "rem_dn_p80": dn,
            "k_only_rem_up_p50": up, "k_only_rem_up_p80": up, "k_only_rem_dn_p50": dn, "k_only_rem_dn_p80": dn,
            "rem_up_p50_if_open": None, "rem_up_p80_if_open": None, "rem_dn_p50_if_open": None, "rem_dn_p80_if_open": None,
            "session_note": f"k={k} is the last Asia bar: the session high / low are in by definition; "
                            f"the remaining distances are the exact distances back to the running extremes. "
                            f"See p_ovn_high_done / p_ovn_low_done for the overnight question.",
        })
    else:
        res.update({
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
        })
    res.update({
        "p_ovn_high_done": float(out["p_ovn_high_done"]), "p_ovn_low_done": float(out["p_ovn_low_done"]),
        "p_ovn_high_raw": float(out["p_ovn_high_raw"]), "p_ovn_low_raw": float(out["p_ovn_low_raw"]),
        "p_ovn_high_lr": float(out["p_ovn_high_lr"]), "p_ovn_high_gb": float(out["p_ovn_high_gb"]),
        "p_ovn_low_lr": float(out["p_ovn_low_lr"]), "p_ovn_low_gb": float(out["p_ovn_low_gb"]),
        "k_only_ovn_high": float(out["kbase_ovn_high"]), "k_only_ovn_low": float(out["kbase_ovn_low"]),
        "calibrated": bool(b["cal"]), "calibrated_sides": sorted(b["cal"].keys()),
        "calibration_sessions": b["cal_sessions"],
        "n_train_sessions": int(m["n_train_sessions"]),
        "features": {f: (None if pd.isna(r0[f]) else float(r0[f])) for f in FEATURES},
    })
    for t in ALL_TARGETS:
        s = SIDE[t]
        if t in TARGETS and last_bar:
            res[f"top_contributions_{s}"] = []
            res[f"lr_intercept_{s}"] = None
            continue
        D = lr_design(row, MAX_K if t in TARGETS else OVN_MAX_K)
        pipe = m[f"lr_{t}"]
        z = pipe[:-1].transform(D)[0]
        coef = pipe[-1].coef_[0]
        contrib = pd.Series(coef * z, index=m["design_cols" if t in TARGETS else "design_cols_ovn"])
        top = contrib.reindex(contrib.abs().sort_values(ascending=False).index).head(top_n)
        res[f"top_contributions_{s}"] = [(name, round(float(v), 3)) for name, v in top.items()]
        res[f"lr_intercept_{s}"] = float(pipe[-1].intercept_[0])
    return res


def format_now(r: dict) -> str:
    """Compact human-readable summary of a predict_now() result."""
    L = []
    flags = [f"live={'yes' if r['live'] else 'no (stored panel row)'}",
             f"latest_complete_k={r['latest_complete_k']}",
             f"partial_bar_dropped={'YES' if r['partial_bar_dropped'] else 'no'}",
             f"calibrated={'yes' if r['calibrated'] else 'no'} ({r['calibration_sessions']} prior OOS sessions)"]
    bar_open = pd.Timestamp(r["bar_ts"]).tz_convert("America/New_York")
    L.append(f"=== {r['sym']} {r['date']}  bar k={r['k']} ({r['hour_et']:02d}:00-{r['hour_et']:02d}:59 ET bar, "
             f"stamped {bar_open:%Y-%m-%d %H:%M %Z}, closed {bar_open + pd.Timedelta(hours=1):%H:%M %Z})  as of {r['asof'][:16]} ===")
    L.append("    " + " | ".join(flags) + f" | train sessions {r['n_train_sessions']}")
    if r.get("short_session_warning"):
        L.append(f"    SHORT-SESSION WARNING: {r['short_session_warning']}")
    if r.get("session_note"):
        L.append(f"    note: {r['session_note']}")
    L.append(f"  session  high in: p={r['p_high_done']:.3f} (k-only {r['k_only_high']:.3f}; raw {r['p_high_raw']:.3f} = lr {r['p_high_lr']:.3f} / gb {r['p_high_gb']:.3f})")
    L.append(f"  session  low  in: p={r['p_low_done']:.3f} (k-only {r['k_only_low']:.3f}; raw {r['p_low_raw']:.3f} = lr {r['p_low_lr']:.3f} / gb {r['p_low_gb']:.3f})")
    L.append(f"  overnight high in (18:00-08:59): p={r['p_ovn_high_done']:.3f} (k-only {r['k_only_ovn_high']:.3f}; raw {r['p_ovn_high_raw']:.3f} = lr {r['p_ovn_high_lr']:.3f} / gb {r['p_ovn_high_gb']:.3f})")
    L.append(f"  overnight low  in (18:00-08:59): p={r['p_ovn_low_done']:.3f} (k-only {r['k_only_ovn_low']:.3f}; raw {r['p_ovn_low_raw']:.3f} = lr {r['p_ovn_low_lr']:.3f} / gb {r['p_ovn_low_gb']:.3f})")
    L.append(f"  remaining up   to the session high (bp): P50 {r['rem_up_p50']:.1f} / P80 {r['rem_up_p80']:.1f}  (k-only {r['k_only_rem_up_p50']:.1f} / {r['k_only_rem_up_p80']:.1f})"
             + (f"; if still open: {r['rem_up_p50_if_open']:.1f} / {r['rem_up_p80_if_open']:.1f}" if r.get("rem_up_p50_if_open") is not None else ""))
    L.append(f"  remaining down to the session low  (bp): P50 {r['rem_dn_p50']:.1f} / P80 {r['rem_dn_p80']:.1f}  (k-only {r['k_only_rem_dn_p50']:.1f} / {r['k_only_rem_dn_p80']:.1f})"
             + (f"; if still open: {r['rem_dn_p50_if_open']:.1f} / {r['rem_dn_p80_if_open']:.1f}" if r.get("rem_dn_p50_if_open") is not None else ""))
    f = r["features"]
    L.append(f"  state: run_hi {f['dist_run_hi_bp']:.1f} bp above close, run_lo {f['dist_run_lo_bp']:.1f} bp below, pos_in_range {f['pos_in_range']:.2f}, "
             f"range/med20 {f['run_rng_vs_med20']:.2f}, bars since hi/lo {int(f['bars_since_hi'])}/{int(f['bars_since_lo'])}, "
             f"above RTH high {int(f['run_hi_above_rth_high'])}, below RTH low {int(f['run_lo_below_rth_low'])}, vix {f['vix']:.1f}")
    for s in SIDES:
        tc = r.get(f"top_contributions_{s}") or []
        if tc:
            L.append(f"  top contributions {s} (log-odds): " + ", ".join(f"{n} {v:+.2f}" for n, v in tc))
    return "\n".join(L)


def _cli(argv: list[str]):
    import argparse
    ap = argparse.ArgumentParser(description="Intra-session Asia high/low detector")
    ap.add_argument("syms", nargs="*", help="symbols for the full walk-forward re-run (default NQ ES)")
    ap.add_argument("--now", metavar="SYM", help="live summary for SYM instead of the walk-forward")
    ap.add_argument("--date", help="RTH date YYYY-MM-DD (default: the latest RTH date in the hourly data)")
    ap.add_argument("--k", type=int, default=None, help="bar index 0..8 (default: the latest complete bar)")
    ap.add_argument("--asof", default=None, help="'YYYY-MM-DD HH:MM' US/Eastern (default: now)")
    ap.add_argument("--top", type=int, default=5)
    a = ap.parse_args(argv)
    if a.now:
        import asia_extremes as ae
        sym = a.now.upper()
        date = pd.Timestamp(a.date) if a.date else ae.latest_rth_date(sym)
        print(format_now(predict_now(sym, date, a.k, top_n=a.top, asof=a.asof)))
        return
    for sym in [s.upper() for s in a.syms] or ["NQ", "ES"]:
        print(f"\n##### {sym} #####")
        oos = train_walk_forward(sym, verbose=True)
        f = os.path.join(HERE, f"oos_intrasession_{sym}.csv")
        oos.to_csv(f, index=False)
        print(f"wrote {f}  ({len(oos)} rows)")
        print(report(oos, sym))


# --------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    _cli(sys.argv[1:])
