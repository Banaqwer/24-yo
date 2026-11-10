"""
Mean-reversion confidence engine for the Asia session (18:00-03:00 ET).

Three views feed one report:

  1. RULES    - named, interpretable setups.  For every rule TRUE tonight we show
                the historical Asia outcome when it was true ("where in the past
                this happened").  Descriptive evidence, computed point-in-time.
  2. MODELS   - regularised logistic regression + shallow gradient boosting,
                trained walk-forward (never sees the future), one classifier per
                outcome:
                    reverted        Asia close is against the RTH move
                    hit_vwap_first  Asia touches RTH VWAP before the stop
                    hit_r382_first  Asia retraces 38.2% of the RTH move before the stop
                    hit_r500_first  Asia retraces 50% before the stop
                    stopped         stop (RTH extreme + 10% of range) hit first
                Probabilities are isotonic-calibrated on out-of-sample folds.
                Quantile regressors give the expected Asia range (stop sizing).
  3. ANALOGS  - nearest-neighbour days in standardised setup space with their
                realised Asia outcomes and the research narrative for that night.

The headline confidence is the calibrated probability that the fade trade
WINS when it resolves: P(target first) / (P(target first) + P(stop first)),
with expected value in points = P(tgt) * dist_tgt - P(stop) * dist_stop.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import FEATURE_COLS_COMPACT, build_feature_table, path_targets, targets

warnings.filterwarnings("ignore")

MIN_RTH_MOVE = 0.0015   # ignore days where RTH moved < 0.15% (nothing to revert)

TARGET_DESC = {
    "reverted": "Asia closes (03:00) on the opposite side of the 18:00 open vs the RTH move",
    "hit_vwap_first": "Asia touches RTH VWAP before the tight stop",
    "hit_r382_first": "Asia retraces 38.2% of the RTH move before the tight stop",
    "hit_r500_first": "Asia retraces 50% of the RTH move before the tight stop",
    "stopped": "Tight stop (RTH extreme + 10% of RTH range) is hit before any target",
    "hit_vwap_first_w": "Asia touches RTH VWAP before the wide stop",
    "hit_r382_first_w": "Asia retraces 38.2% of the RTH move before the wide stop",
    "hit_r500_first_w": "Asia retraces 50% of the RTH move before the wide stop",
    "stopped_w": "Wide stop (max(0.6x median Asia range, 0.3x today's RTH range) from 17:00 close) is hit first",
}
STOP_VARIANTS = {"tight": "", "wide": "_w"}

POINT_VALUE = {"NQ": 20.0, "ES": 50.0, "MNQ": 2.0, "MES": 5.0}

# ----------------------------------------------------------------------------
# 1. RULES
# ----------------------------------------------------------------------------
RULES = {
    # price structure
    "rth_down_big":        ("RTH down more than 1%",                      lambda f: f.rth_ret < -0.01),
    "rth_up_big":          ("RTH up more than 1%",                        lambda f: f.rth_ret > 0.01),
    "rth_down_huge":       ("RTH down more than 2%",                      lambda f: f.rth_ret < -0.02),
    "rth_up_huge":         ("RTH up more than 2%",                        lambda f: f.rth_ret > 0.02),
    "rth_move_2sig":       ("RTH move > 2 sigma of 20d daily vol",        lambda f: f.rth_ret_z.abs() > 2),
    "close_at_extreme":    ("Closed in outer 20% of range in the move's direction", lambda f: f.ext_in_dir > 0.6),
    "close_mid_range":     ("Closed in middle 40% of range (indecision)", lambda f: f.clv.abs() < 0.2),
    "late_day_fade":       ("Faded back toward VWAP into the close",      lambda f: f.late_day_rev < -0.15),
    "close_far_from_vwap": ("Closed > 0.5 range-widths beyond RTH VWAP",  lambda f: f.vwap_in_dir > 0.5),
    "close_near_vwap":     ("Closed within 0.1 range-widths of RTH VWAP", lambda f: f.close_vs_vwap_rng.abs() < 0.1),
    "gap_and_go":          ("Gapped and extended in gap direction",       lambda f: (f.gap_open * f.rth_ret > 0) & (f.gap_open.abs() > 0.005)),
    "gap_reversed":        ("Gapped then reversed the gap in RTH",        lambda f: (f.gap_open * f.rth_ret < 0) & (f.gap_open.abs() > 0.005)),
    "range_expansion":     ("RTH range > 1.5x 20d ATR",                   lambda f: f.rth_range_atr > 1.5),
    "range_contraction":   ("RTH range < 0.6x 20d ATR",                   lambda f: f.rth_range_atr < 0.6),
    "post_close_shock":    ("Post-close (16-17h) move > 0.3% (earnings/news)", lambda f: f.post_ret.abs() > 0.003),
    "post_close_extends":  ("Post-close move extended the RTH direction",  lambda f: f.post_in_dir > 0.0015),
    "broke_prev_high":     ("Closed above prior RTH high",                lambda f: f.close_above_prev_high == 1),
    "broke_prev_low":      ("Closed below prior RTH low",                 lambda f: f.close_below_prev_low == 1),
    # trend / stretch
    "stretched_below_20":  ("More than 2 ATR below 20d SMA",              lambda f: f.z_sma20 < -2),
    "stretched_above_20":  ("More than 2 ATR above 20d SMA",              lambda f: f.z_sma20 > 2),
    "stretched_below_50":  ("More than 3 ATR below 50d SMA",              lambda f: f.z_sma50 < -3),
    "move_extends_stretch": ("Today's move extended an existing >1.5 ATR stretch from 20d SMA", lambda f: f.stretch20_in_dir > 1.5),
    "move_corrects_stretch": ("Today's move corrected a >1.5 ATR stretch from 20d SMA", lambda f: f.stretch20_in_dir < -1.5),
    "down_streak_3":       ("3+ consecutive down RTH sessions",           lambda f: f.streak <= -3),
    "up_streak_3":         ("3+ consecutive up RTH sessions",             lambda f: f.streak >= 3),
    "drawdown_5pct":       ("More than 5% below 20d high",                lambda f: f.dist_20d_high < -0.05),
    "at_20d_high":         ("Within 0.5% of 20d high",                    lambda f: f.dist_20d_high > -0.005),
    # volatility
    "vix_spike":           ("VIX up more than 10% today",                 lambda f: f.vix_chg > 0.10),
    "vix_crush":           ("VIX down more than 10% today",               lambda f: f.vix_chg < -0.10),
    "vix_diverged":        ("VIX moved AGAINST the equity move (>5%)",    lambda f: f.vix_consistent < -0.05),
    "vix_high":            ("VIX above 25",                               lambda f: f.vix > 25),
    "vix_low":             ("VIX below 14",                               lambda f: f.vix < 14),
    "vol_regime_shift":    ("5d realised vol > 1.6x 20d (vol expanding)", lambda f: f.rv_ratio > 1.6),
    "vix_z_high":          ("VIX > 2 sigma above its 20d mean",           lambda f: f.vix_z20 > 2),
    # cross-asset
    "yen_surge":           ("USDJPY down > 1% today (yen bid / carry unwind)", lambda f: f.usdjpy_chg < -0.01),
    "yen_surge_5d":        ("USDJPY down > 2% over 5d",                   lambda f: f.usdjpy_chg5 < -0.02),
    "yields_spike":        ("US10Y up > 8bp today",                       lambda f: f.us10y_chg > 0.08),
    "yields_plunge":       ("US10Y down > 8bp today",                     lambda f: f.us10y_chg < -0.08),
    "dollar_up":           ("DXY up > 0.5% today",                        lambda f: f.dxy_chg > 0.005),
    "semis_led_down":      ("SOX underperformed NQ by > 1.5%",            lambda f: f.sox_minus_nq < -0.015),
    "semis_led_up":        ("SOX outperformed NQ by > 1.5%",              lambda f: f.sox_minus_nq > 0.015),
    "semis_confirm":       ("Semis led in the direction of the move (>1%)", lambda f: f.sox_in_dir > 0.01),
    "nikkei_down_big":     ("Nikkei fell > 1.5% in the prior Tokyo session", lambda f: f.n225_ret < -0.015),
    "nikkei_up_big":       ("Nikkei rose > 1.5% in the prior Tokyo session", lambda f: f.n225_ret > 0.015),
    "us_diverged_from_asia": ("US moved > 1.5% opposite to Tokyo's session", lambda f: (f.us_after_tokyo.abs() > 0.015) & (np.sign(f.day_ret) != np.sign(f.n225_ret))),
    "crude_spike":         ("Crude up > 3% today",                        lambda f: f.crude_chg > 0.03),
    "btc_down_rth":        ("BTC fell > 2% during US hours",              lambda f: f.btc_rth < -0.02),
    "btc_confirms":        ("BTC moved > 1.5% with the equity move in US hours", lambda f: f.btc_in_dir > 0.015),
    "nq_underperf_es":     ("NQ underperformed ES by > 0.5%",             lambda f: f.nq_minus_es < -0.005),
    "nq_outperf_es":       ("NQ outperformed ES by > 0.5%",               lambda f: f.nq_minus_es > 0.005),
    # session memory
    "prior_asia_reverted": ("Last night's Asia already reverted the prior RTH", lambda f: f.prior_asia_reverted == 1),
    "prior_asia_big":      ("Last night's Asia moved > 0.7%",             lambda f: f.prior_asia_ret.abs() > 0.007),
    "prior_asia_same_dir": ("Last night's Asia moved > 0.4% in today's RTH direction", lambda f: f.prior_asia_in_dir > 0.004),
    "rth_fought_overnight": ("RTH reversed the prior overnight move",     lambda f: (f.rth_vs_overnight < 0) & (f.prior_overnight_ret.abs() > 0.004)),
    "heavy_volume":        ("RTH volume > 1.4x 20d average",              lambda f: f.rth_vol_rel > 1.4),
    "light_volume":        ("RTH volume < 0.7x 20d average",              lambda f: f.rth_vol_rel < 0.7),
    # calendar
    "fomc_today":          ("FOMC decision was today",                    lambda f: f.fomc_today == 1),
    "fomc_tomorrow":       ("FOMC decision tomorrow",                     lambda f: f.fomc_tomorrow == 1),
    "tier1_today":         ("CPI/NFP/PCE released today",                 lambda f: f.tier1_data_today == 1),
    "tier1_tomorrow":      ("CPI/NFP/PCE tomorrow (pre-event night)",     lambda f: f.tier1_data_tomorrow == 1),
    "earnings_tonight":    ("Mega-cap earnings after the close tonight",  lambda f: f.megacap_earnings_tonight == 1),
    "boj_tonight":         ("BoJ decision during tonight's Asia session", lambda f: f.boj_tonight == 1),
    "cn_data_tonight":     ("China data during tonight's Asia session",   lambda f: f.cn_data_tonight == 1),
    "opex_today":          ("Monthly opex today",                         lambda f: f.opex_today == 1),
    "witching_today":      ("Quarterly witching today",                   lambda f: f.witching_today == 1),
    "roll_week":           ("Quarterly roll day today",                   lambda f: f.roll_today == 1),
    "sunday_open":         ("Friday close -> Sunday 18:00 reopen (weekend gap risk)", lambda f: f.sunday_open == 1),
    "month_end":           ("Month-end rebalancing session",              lambda f: f.month_end == 1),
    "pre_holiday":         ("US holiday tomorrow (thin Asia)",            lambda f: f.pre_holiday == 1),
    "monday":              ("Monday",                                     lambda f: f.dow == 0),
    "thursday":            ("Thursday",                                   lambda f: f.dow == 3),
    "fomc_within_2d":      ("FOMC within next 2 trading days",            lambda f: (f.days_to_fomc >= 1) & (f.days_to_fomc <= 2)),
}


def signed_outcomes(t: pd.DataFrame, f: pd.DataFrame, p: pd.DataFrame | None = None) -> pd.DataFrame:
    """Outcomes in the *reversion* frame (positive = Asia went against RTH)."""
    o = pd.DataFrame(index=t.index)
    rs = np.sign(f["rth_ret"])
    o["rev_ret"] = t["asia_ret"] * -rs
    o["rev_ret_tokyo"] = t["tokyo_ret"] * -rs
    o["rev_first_hr"] = t["asia_first_hr"] * -rs
    o["reverted"] = t["reverted"]
    o["retrace_frac"] = t["retrace_frac"]
    o["hit_vwap"] = t["hit_vwap"]
    o["hit_settle"] = t["hit_settle"]
    o["continued"] = t["continued"]
    o["asia_rng"] = t["asia_rng"]
    o["rev_mae"] = np.where(rs > 0, t["asia_up_ext"], -t["asia_dn_ext"])
    o["rev_mfe"] = np.where(rs > 0, -t["asia_dn_ext"], t["asia_up_ext"])
    o["valid"] = (f["rth_ret"].abs() >= MIN_RTH_MOVE).astype(int)
    if p is not None:
        for c in p.columns:
            o[c] = p[c]
    return o


def rule_table(f: pd.DataFrame, o: pd.DataFrame, lookback_days: int | None = None,
               asof: pd.Timestamp | None = None) -> pd.DataFrame:
    """Historical outcome for every rule using data strictly before `asof`."""
    hist = (f.index < asof) if asof is not None else np.ones(len(f), bool)
    if lookback_days:
        start = (asof if asof is not None else f.index[-1]) - pd.Timedelta(days=lookback_days)
        hist &= f.index >= start
    valid = (o["valid"] == 1).values & hist & o["reverted"].notna().values
    base = o.loc[valid]
    rows = []
    for key, (desc, fn) in RULES.items():
        try:
            m = fn(f).fillna(False).values & valid
        except Exception:
            continue
        sub = o.loc[m]
        n = len(sub)
        if n == 0:
            rows.append(dict(rule=key, desc=desc, n=0))
            continue
        sd = sub["rev_ret"].std(ddof=1)
        rows.append(dict(
            rule=key, desc=desc, n=n,
            rev_rate=sub["reverted"].mean(),
            rev_rate_lift=sub["reverted"].mean() - base["reverted"].mean(),
            avg_rev_ret_bp=sub["rev_ret"].mean() * 1e4,
            med_rev_ret_bp=sub["rev_ret"].median() * 1e4,
            vwap_first=sub["hit_vwap_first"].mean() if "hit_vwap_first" in sub else np.nan,
            r382_first=sub["hit_r382_first"].mean() if "hit_r382_first" in sub else np.nan,
            stopped=sub["stopped"].mean() if "stopped" in sub else np.nan,
            continued=sub["continued"].mean(),
            med_retrace=sub["retrace_frac"].median(),
            med_rng_bp=sub["asia_rng"].median() * 1e4,
            avg_mae_bp=sub["rev_mae"].mean() * 1e4,
            t_stat=(sub["rev_ret"].mean() / (sd / np.sqrt(n))) if n > 2 and sd > 0 else np.nan,
        ))
    return pd.DataFrame(rows).set_index("rule")


def active_rules(f_row: pd.Series) -> list[str]:
    fr = f_row.to_frame().T
    out = []
    for key, (desc, fn) in RULES.items():
        try:
            if bool(fn(fr).fillna(False).iloc[0]):
                out.append(key)
        except Exception:
            pass
    return out


# ----------------------------------------------------------------------------
# 2. MODELS (walk-forward)
# ----------------------------------------------------------------------------
@dataclass
class FitResult:
    target: str
    oos: pd.DataFrame
    coef: pd.Series
    calibrator: IsotonicRegression | None
    models: dict = field(default_factory=dict)
    cols: list = field(default_factory=list)
    eval: dict = field(default_factory=dict)


def _design(f: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return f[cols].astype(float).replace([np.inf, -np.inf], np.nan)


def _make_models(n: int):
    lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                       LogisticRegression(C=0.08, penalty="l2", max_iter=3000, class_weight="balanced"))
    gb = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.04,
                                        l2_regularization=2.0, min_samples_leaf=max(15, n // 25),
                                        max_features=0.6, random_state=7)
    return {"logit": lr, "gbm": gb}


def _sample_mask(f: pd.DataFrame, o: pd.DataFrame, y: pd.Series, X: pd.DataFrame) -> pd.Series:
    return ((o["valid"] == 1) & y.notna() & o["rev_ret"].notna() & o["asia_rng"].notna()
            & X.notna().mean(axis=1).gt(0.6))


def walk_forward_target(f: pd.DataFrame, o: pd.DataFrame, target: str, cols: list[str],
                        min_train: int = 150, step: str = "M") -> FitResult:
    X = _design(f, cols)
    y = o[target]
    mask = _sample_mask(f, o, y, X)
    X, y = X[mask], y[mask].astype(int)
    periods = X.index.to_period(step)
    preds, coefs = [], []
    for p in periods.unique():
        train, test = periods < p, periods == p
        if train.sum() < min_train:
            continue
        models = _make_models(int(train.sum()))
        row = pd.DataFrame(index=X.index[test])
        for name, m in models.items():
            m.fit(X[train], y[train])
            row[f"p_{name}"] = m.predict_proba(X[test])[:, 1]
        preds.append(row)
        coefs.append(pd.Series(models["logit"][-1].coef_[0], index=cols))
    oos = pd.concat(preds).sort_index()
    oos["p_raw"] = oos[["p_logit", "p_gbm"]].mean(axis=1)
    oos["y"] = y.reindex(oos.index)
    oos["rev_ret"] = o.loc[oos.index, "rev_ret"]
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.03, y_max=0.97)
    iso.fit(oos["p_raw"], oos["y"])
    oos["p_cal"] = iso.predict(oos["p_raw"])
    final = _make_models(len(X))
    for m in final.values():
        m.fit(X, y)
    fr = FitResult(target=target, oos=oos, coef=pd.concat(coefs, axis=1).mean(axis=1),
                   calibrator=iso, models=final, cols=cols)
    fr.eval = evaluate_probs(oos)
    return fr


def fit_regressors(f: pd.DataFrame, o: pd.DataFrame, cols: list[str]) -> dict:
    X = _design(f, cols)
    mask = _sample_mask(f, o, o["rev_ret"], X)
    X = X[mask]
    out = {}
    reg = HistGradientBoostingRegressor(max_depth=3, max_iter=120, learning_rate=0.04, l2_regularization=2.0,
                                        min_samples_leaf=20, random_state=7)
    reg.fit(X, o.loc[mask, "rev_ret"] * 1e4)
    out["exp_rev_bp"] = reg
    # honest OOS check of the magnitude regressor (70/30 time split): R^2 vs predicting the training mean
    n = len(X)
    cut = int(n * 0.7)
    rr = o.loc[mask, "rev_ret"] * 1e4
    reg2 = HistGradientBoostingRegressor(max_depth=3, max_iter=120, learning_rate=0.04, l2_regularization=2.0,
                                         min_samples_leaf=20, random_state=7)
    reg2.fit(X.iloc[:cut], rr.iloc[:cut])
    pred = reg2.predict(X.iloc[cut:])
    sse = float(np.sum((rr.iloc[cut:].values - pred) ** 2))
    sst = float(np.sum((rr.iloc[cut:].values - rr.iloc[:cut].mean()) ** 2))
    out["exp_rev_oos_r2"] = 1 - sse / sst if sst > 0 else 0.0
    out["exp_rev_shrink"] = float(np.clip(out["exp_rev_oos_r2"], 0.0, 1.0))
    rng = o.loc[mask, "asia_rng"] * 1e4
    for q in (0.5, 0.8):
        qm = HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=3, max_iter=120,
                                           learning_rate=0.04, min_samples_leaf=20, random_state=7)
        qm.fit(X, rng)
        out[f"rng_q{int(q*100)}"] = qm
    # out-of-sample check of the range median via a simple split for the honesty box
    n = len(X)
    cut = int(n * 0.7)
    qm = HistGradientBoostingRegressor(loss="quantile", quantile=0.5, max_depth=3, max_iter=120,
                                       learning_rate=0.04, min_samples_leaf=20, random_state=7)
    qm.fit(X.iloc[:cut], rng.iloc[:cut])
    pred = qm.predict(X.iloc[cut:])
    out["rng_q50_oos_mae_bp"] = float(np.mean(np.abs(pred - rng.iloc[cut:].values)))
    out["rng_q50_naive_mae_bp"] = float(np.mean(np.abs(rng.iloc[:cut].median() - rng.iloc[cut:].values)))
    out["rng_q50_oos_coverage"] = float(np.mean(rng.iloc[cut:].values <= pred))
    return out


def evaluate_probs(oos: pd.DataFrame) -> dict:
    y = oos["y"].values
    out = {"n": int(len(y)), "base_rate": float(y.mean())}
    out["base_brier"] = float(np.mean((y.mean() - y) ** 2))
    for col in ("p_logit", "p_gbm", "p_raw", "p_cal"):
        p = oos[col].clip(1e-4, 1 - 1e-4).values
        out[f"{col}_brier"] = float(np.mean((p - y) ** 2))
        out[f"{col}_logloss"] = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        out[f"{col}_acc"] = float(np.mean((p > 0.5) == (y == 1)))
    b = pd.cut(oos["p_cal"], [0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0], include_lowest=True)
    out["buckets"] = oos.groupby(b, observed=True).agg(n=("y", "size"), realised=("y", "mean"), predicted=("p_cal", "mean"))
    return out


def logit_contributions(fit: FitResult, X: pd.DataFrame) -> pd.Series:
    pipe = fit.models["logit"]
    Xs = pipe[1].transform(pipe[0].transform(X))
    return pd.Series(Xs[0] * pipe[2].coef_[0], index=fit.cols).sort_values(key=np.abs, ascending=False)


# ----------------------------------------------------------------------------
# 3. ANALOGS
# ----------------------------------------------------------------------------
ANALOG_COLS = ["rth_ret_z", "ext_in_dir", "vwap_in_dir", "gap_in_dir", "stretch20_in_dir", "stretch50_in_dir",
               "ret5_in_dir", "vix_z20", "vix_consistent", "rv_ratio", "yen_in_dir", "yield_in_dir",
               "sox_in_dir", "n225_in_dir", "prior_asia_in_dir", "abs_streak", "rth_range_atr", "dxy_chg"]
ANALOG_WEIGHTS = {"rth_ret_z": 2.5, "ext_in_dir": 1.5, "vwap_in_dir": 1.5, "stretch20_in_dir": 1.5,
                  "vix_consistent": 1.5, "vix_z20": 1.2, "rv_ratio": 1.0}


def find_analogs(f: pd.DataFrame, o: pd.DataFrame, asof: pd.Timestamp, k: int = 12,
                 same_direction: bool = True) -> pd.DataFrame:
    cols = [c for c in ANALOG_COLS if c in f.columns]
    hist = f.loc[f.index < asof, cols].astype(float)
    hist = hist[(o.loc[hist.index, "valid"] == 1) & o.loc[hist.index, "rev_ret"].notna()]
    row = f.loc[asof, cols].astype(float)
    if same_direction:
        hist = hist[np.sign(f.loc[hist.index, "rth_ret"]) == np.sign(f.loc[asof, "rth_ret"])]
    mu, sd = hist.mean(), hist.std().replace(0, 1)
    Z, z0 = (hist - mu) / sd, (row - mu) / sd
    w = pd.Series({c: ANALOG_WEIGHTS.get(c, 1.0) for c in cols})
    d = (((Z - z0) ** 2) * w).fillna(0).sum(axis=1) ** 0.5
    top = d.nsmallest(k)
    res = pd.DataFrame({"distance": top})
    res = res.join(f.loc[top.index, ["rth_ret", "clv", "vix_chg", "z_sma20", "events_today"]])
    keep = [c for c in ["rev_ret", "reverted", "retrace_frac", "hit_vwap_first", "hit_r382_first", "stopped", "asia_rng", "continued"] if c in o]
    return res.join(o.loc[top.index, keep])


# ----------------------------------------------------------------------------
# 4. ENGINE
# ----------------------------------------------------------------------------
class Engine:
    TARGETS = ["reverted", "hit_vwap_first", "hit_r382_first", "hit_r500_first", "stopped",
               "hit_vwap_first_w", "hit_r382_first_w", "hit_r500_first_w", "stopped_w"]

    def __init__(self, sym: str = "NQ", other: str | None = None, cols: list[str] | None = None):
        self.sym = sym
        self.other = other or ("ES" if sym == "NQ" else "NQ")
        self.cols = cols or FEATURE_COLS_COMPACT
        self.f, self.s = build_feature_table(self.sym, self.other)
        self.t = targets(self.s)
        self.p = path_targets(self.sym, self.s)
        self.o = signed_outcomes(self.t, self.f, self.p)
        self.fits: dict[str, FitResult] = {}
        self.regs: dict = {}

    def train(self, min_train: int = 150):
        for tgt in self.TARGETS:
            self.fits[tgt] = walk_forward_target(self.f, self.o, tgt, self.cols, min_train=min_train)
        self.regs = fit_regressors(self.f, self.o, self.cols)
        return self

    def predict(self, asof: pd.Timestamp | None = None) -> dict:
        asof = pd.Timestamp(asof) if asof is not None else self.f.index[-1]
        row = self.f.loc[asof]
        X = _design(row.to_frame().T, self.cols)
        out = {"asof": asof, "probs": {}, "contrib": {}}
        for tgt, fit in self.fits.items():
            pl = float(fit.models["logit"].predict_proba(X)[0, 1])
            pg = float(fit.models["gbm"].predict_proba(X)[0, 1])
            praw = (pl + pg) / 2
            pcal = float(fit.calibrator.predict([praw])[0])
            out["probs"][tgt] = {"logit": pl, "gbm": pg, "raw": praw, "cal": pcal}
            out["contrib"][tgt] = logit_contributions(fit, X)
        out["exp_rev_bp"] = float(self.regs["exp_rev_bp"].predict(X)[0])
        out["rng_q50_bp"] = float(self.regs["rng_q50"].predict(X)[0])
        out["rng_q80_bp"] = float(self.regs["rng_q80"].predict(X)[0])
        out["active_rules"] = active_rules(row)
        out["trade"] = self.trade_plan(asof, out)
        return out

    def trade_plan(self, asof: pd.Timestamp, pred: dict) -> dict:
        """EV of fading the RTH move from the 18:00 open toward each target, for both stop variants.
        EV includes the scratch outcome (neither target nor stop by 03:00), valued at the model's
        expected signed reversion return."""
        from features import wide_stop_distance
        r = self.s.loc[asof]
        up = (r["rth_close"] - r["rth_open"]) > 0
        move = r["rth_close"] - r["rth_open"]
        rng = r["rth_high"] - r["rth_low"]
        entry = r["post_close"] if not pd.isna(r.get("post_close")) else r["rth_close"]
        wsd = wide_stop_distance(self.s).get(asof, np.nan)
        stops = {"tight": r["rth_high"] + 0.10 * rng if up else r["rth_low"] - 0.10 * rng}
        if not pd.isna(wsd):
            stops["wide"] = entry + wsd if up else entry - wsd
        tg = {"vwap": r["rth_vwap"], "r382": r["rth_close"] - 0.382 * move, "r500": r["rth_close"] - 0.5 * move}
        exp_rev_pts = pred.get("exp_rev_bp", 0.0)
        # the scratch outcome is valued at the magnitude model's expectation, shrunk by its OOS R^2
        # (if the regressor has no out-of-sample skill the scratch is valued at zero)
        shrink = self.regs.get("exp_rev_shrink", 0.0)
        exp_rev_pts = 0.0 if pd.isna(exp_rev_pts) else exp_rev_pts / 1e4 * entry * shrink
        q80_pts = pred["rng_q80_bp"] / 1e4 * entry if not pd.isna(pred.get("rng_q80_bp", np.nan)) else np.inf
        variants = {}
        for vname, stop in stops.items():
            sfx = STOP_VARIANTS[vname]
            d_stop = abs(stop - entry)
            p_stop = pred["probs"][f"stopped{sfx}"]["cal"]
            plans = {}
            for k, lvl in tg.items():
                p_t = pred["probs"][f"hit_{k}_first{sfx}"]["cal"]
                s = p_t + p_stop
                p_t_n, p_s_n = (p_t / s, p_stop / s) if s > 1 else (p_t, p_stop)
                scratch = max(0.0, 1 - p_t_n - p_s_n)
                d_t = abs(lvl - entry)
                past = (lvl >= entry) if up else (lvl <= entry)
                # a target beyond the P80 expected range is a lottery ticket: cap its payoff for EV purposes
                ev_pts = p_t_n * min(d_t, q80_pts) - p_s_n * d_stop + scratch * exp_rev_pts
                plans[k] = {
                    "level": float(lvl), "dist_pts": float(d_t), "p_target": float(p_t_n), "p_stop": float(p_s_n),
                    "p_scratch": float(scratch),
                    "win_rate_on_resolution": float(p_t_n / (p_t_n + p_s_n)) if (p_t_n + p_s_n) > 0 else np.nan,
                    "ev_pts": float(ev_pts), "ev_usd": float(ev_pts * POINT_VALUE.get(self.sym, 1.0)),
                    "already_past": bool(past),
                }
            best = max((k for k in plans if not plans[k]["already_past"]), key=lambda k: plans[k]["ev_pts"], default=None)
            variants[vname] = {"stop": float(stop), "stop_dist_pts": float(d_stop), "p_stop": float(p_stop), "targets": plans, "best": best}
        direction = "SHORT (fade the up move)" if up else "LONG (fade the down move)"
        # keep the legacy top-level keys pointing at the tight variant
        t = variants["tight"]
        return {"entry": float(entry), "stop": t["stop"], "stop_dist_pts": t["stop_dist_pts"], "fade_direction": direction,
                "rth_direction": "UP" if up else "DOWN", "targets": t["targets"], "best": t["best"], "variants": variants,
                "exp_rev_pts": float(exp_rev_pts),
                "rng_q50_pts": pred["rng_q50_bp"] / 1e4 * entry, "rng_q80_pts": pred["rng_q80_bp"] / 1e4 * entry}

    def rule_table(self, asof=None, lookback_days=None):
        asof = pd.Timestamp(asof) if asof is not None else self.f.index[-1]
        return rule_table(self.f, self.o, lookback_days=lookback_days, asof=asof)

    def analogs(self, asof=None, k=12):
        asof = pd.Timestamp(asof) if asof is not None else self.f.index[-1]
        return find_analogs(self.f, self.o, asof, k=k)


MIN_TARGET_FRAC_OF_RANGE = 0.25   # target must be at least 25% of the expected median Asia range away
MAX_STOP_FRAC_OF_P80 = 1.0        # stop must sit inside the P80 expected range
MIN_EV_FRAC_OF_RANGE = 0.03       # EV must be at least 3% of the median range (covers costs/slippage)


def _candidates(plan: dict) -> list[dict]:
    """Every tradeable (variant, side) with its geometry and EV."""
    up = plan["rth_direction"] == "UP"
    exp_rev = plan.get("exp_rev_pts", 0.0)
    out = []
    for vname, v in plan["variants"].items():
        p_stop = v["p_stop"]
        for k, t in v["targets"].items():
            if t["already_past"]:
                continue
            # fade: target k, stop = variant stop
            out.append({"kind": "MEAN REVERSION", "variant": vname, "target_key": k, "side": "SHORT" if up else "LONG",
                        "entry": plan["entry"], "target": t["level"], "target_dist": t["dist_pts"],
                        "stop": v["stop"], "stop_dist": v["stop_dist_pts"], "p_win": t["p_target"], "p_loss": t["p_stop"],
                        "scratch": t["p_scratch"], "ev_pts": t["ev_pts"]})
        # continuation: with the move; target = variant stop level, stop = VWAP (nearest fade target)
        vw = v["targets"]["vwap"]
        if not vw["already_past"]:
            scratch = max(0.0, 1 - vw["p_stop"] - vw["p_target"])
            ev = vw["p_stop"] * v["stop_dist_pts"] - vw["p_target"] * vw["dist_pts"] - scratch * exp_rev
            out.append({"kind": "CONTINUATION", "variant": vname, "target_key": "stop_level", "side": "LONG" if up else "SHORT",
                        "entry": plan["entry"], "target": v["stop"], "target_dist": v["stop_dist_pts"],
                        "stop": vw["level"], "stop_dist": vw["dist_pts"], "p_win": vw["p_stop"], "p_loss": vw["p_target"],
                        "scratch": scratch, "ev_pts": ev})
    return out


def confidence_from_plan(plan: dict, pred: dict) -> dict:
    """
    Headline call.  Among all (stop variant x target x side) candidates, choose the highest-EV
    trade that passes the geometry guard:
        target distance >= 25% of the expected median Asia range  (a meaningful target)
        stop distance   <= P80 expected Asia range                 (a plausible stop)
        EV              >= 3% of the median range                   (clears costs)
    Confidence = probability the chosen trade wins when it resolves (0-100).
    """
    cands = _candidates(plan)
    q50, q80 = plan.get("rng_q50_pts", np.nan), plan.get("rng_q80_pts", np.nan)
    guard_ok = []
    for c in cands:
        c["win_rate_on_resolution"] = c["p_win"] / (c["p_win"] + c["p_loss"]) if (c["p_win"] + c["p_loss"]) > 0 else 0.5
        ok = True
        reasons = []
        if not pd.isna(q50) and c["target_dist"] < MIN_TARGET_FRAC_OF_RANGE * q50:
            ok, reasons = False, reasons + ["target too close vs expected range"]
        if not pd.isna(q80) and c["stop_dist"] > MAX_STOP_FRAC_OF_P80 * q80:
            ok, reasons = False, reasons + ["stop outside P80 range"]
        if not pd.isna(q50) and c["ev_pts"] < MIN_EV_FRAC_OF_RANGE * q50:
            ok, reasons = False, reasons + ["EV too small"]
        if c["win_rate_on_resolution"] < 0.5:
            ok, reasons = False, reasons + ["stop more likely than target"]
        c["guard_ok"], c["guard_reasons"] = ok, reasons
        if ok:
            guard_ok.append(c)
    if not cands:
        return {"call": "NO TRADE", "confidence": 50, "grade": "-", "reason": "price already through all targets post-close",
                "ev_pts": 0.0, "best_target": None, "geometry": {}, "candidates": cands}
    pool = guard_ok if guard_ok else cands
    best = max(pool, key=lambda c: c["ev_pts"])
    conf = best["win_rate_on_resolution"] * 100
    ev = best["ev_pts"]
    side_txt = ("fade the up move" if best["side"] == "SHORT" else "fade the down move") if best["kind"] == "MEAN REVERSION" \
        else ("with the up move" if best["side"] == "LONG" else "with the down move")
    call = f"{best['kind']}: {best['side']} ({side_txt}, {best['variant']} stop, target {best['target_key']})"
    if not guard_ok:
        grade = "NO EDGE"
    elif conf >= 72:
        grade = "A"
    elif conf >= 63:
        grade = "B"
    elif conf >= 56:
        grade = "C"
    else:
        grade = "NO EDGE"
    geometry = {k: best[k] for k in ["side", "entry", "target", "target_dist", "stop", "stop_dist", "p_win", "p_loss", "scratch", "variant", "target_key"]}
    return {"call": call, "confidence": round(conf), "grade": grade, "ev_pts": round(ev, 1), "best_target": best["target_key"],
            "geometry": geometry, "candidates": cands, "guard_failed": [] if guard_ok else best["guard_reasons"]}
