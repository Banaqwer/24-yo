#!/usr/bin/env python
"""
Signal-level evaluation of the stored walk-forward predictions of the two Asia extreme detectors.

Reads only
    research/extremes/oos_intrasession_{NQ,ES}.csv   (Detector A, one row per (session, bar k))
    research/extremes/oos_preasia_{NQ,ES}.csv        (Detector B, one row per session)
    research/extremes/{NQ,ES}_hourly_panel.csv       (running extremes, hi_k / lo_k)
    research/extremes/{NQ,ES}_extremes.csv           (session table: ref close, levels, vix, calendar)
    data/{NQ,ES}_1h.csv                              (raw hourly bars, for the trade translation)
and writes the tables listed in TABLES to research/extremes/validation/.

Nothing is retrained.  Every probability evaluated here was produced out of sample by the walk-forward
documented in research/asia_extremes_report.md (sections 5 and 8.7); this script turns those stored
probabilities into flags and measures the flags against the realised labels.

Deterministic: the only randomness is the session-block bootstrap (numpy default_rng, seed 0, 1,000 draws,
re-seeded for every statistic so that results do not depend on evaluation order).

Run from the project root or from research/extremes:
    OMP_NUM_THREADS=1 python research/extremes/signal_backtest.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore", pd.errors.PerformanceWarning)   # wide frames; cosmetic

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from sessions import ASIA_HOURS, EUROPE_HOURS, load_hourly  # noqa: E402

OUT = os.path.join(HERE, "validation")
DATA = os.path.join(ROOT, "data")
SYMS = ["NQ", "ES"]

Z90 = 1.6448536269514722          # two-sided 90 %
N_BOOT = 1000
SEED = 0
LAST12_START = pd.Timestamp("2025-11-07")
LAST12_END = pd.Timestamp("2026-11-06")
H2_START = pd.Timestamp("2025-09-01")
K_ASIA_MAX = 7                    # Asia labels are definitional at k = 8
K_OVN_MAX = 8
TRADE_KMAX = 6                    # trade translation: at least two Asia bars left
TIGHT_STOP_FRAC = 0.10            # tight stop: this fraction of a range measure beyond the running extreme (two variants)
NEAR_TARGET_BP = 2.0              # trade translation: a target within this many bp of the entry close is "near"
LOW_N = 5                         # per-month cells with fewer firings are marked

TABLES = ["signals_rowlevel.csv", "signals_first_firing.csv", "first_firing_by_k.csv", "failures.csv",
          "overnight_flags.csv", "preasia_calls.csv", "envelope_coverage.csv", "joint_calls.csv",
          "stability_cuts.csv", "monthly.csv", "trade_translation.csv", "summary.json"]

# --------------------------------------------------------------------------------------------------
# flag specifications
# --------------------------------------------------------------------------------------------------
# Intra-session flags.  'invert' = the claim is about the complement of the label (extreme still ahead).
# ycol2 / kbase2 = the secondary outcome: the overnight label for the Asia flags, the Asia label for the
# overnight flags.
INTRA_FLAGS = []
for thr in (0.80, 0.90, 0.95):
    INTRA_FLAGS.append(dict(name=f"HI_IN@{thr:.2f}", family="IN", side="high", pcol="p_high_done", rawcol="p_high_raw",
                            thr=thr, op=">=", ycol="high_done", kbase="kbase_high", ycol2="overnight_high_done",
                            kbase2="kbase_ovn_high", invert=False, kmax=K_ASIA_MAX,
                            claim="the Asia high is already in"))
    INTRA_FLAGS.append(dict(name=f"LO_IN@{thr:.2f}", family="IN", side="low", pcol="p_low_done", rawcol="p_low_raw",
                            thr=thr, op=">=", ycol="low_done", kbase="kbase_low", ycol2="overnight_low_done",
                            kbase2="kbase_ovn_low", invert=False, kmax=K_ASIA_MAX,
                            claim="the Asia low is already in"))
for thr in (0.10, 0.05):
    INTRA_FLAGS.append(dict(name=f"HI_AHEAD@{thr:.2f}", family="AHEAD", side="high", pcol="p_high_done", rawcol="p_high_raw",
                            thr=thr, op="<=", ycol="high_done", kbase="kbase_high", ycol2="overnight_high_done",
                            kbase2="kbase_ovn_high", invert=True, kmax=K_ASIA_MAX,
                            claim="a new Asia high prints before 03:00"))
    INTRA_FLAGS.append(dict(name=f"LO_AHEAD@{thr:.2f}", family="AHEAD", side="low", pcol="p_low_done", rawcol="p_low_raw",
                            thr=thr, op="<=", ycol="low_done", kbase="kbase_low", ycol2="overnight_low_done",
                            kbase2="kbase_ovn_low", invert=True, kmax=K_ASIA_MAX,
                            claim="a new Asia low prints before 03:00"))
for thr in (0.80, 0.90):
    INTRA_FLAGS.append(dict(name=f"OVN_HI_IN@{thr:.2f}", family="OVN", side="high", pcol="p_ovn_high_done", rawcol="p_ovn_high_raw",
                            thr=thr, op=">=", ycol="overnight_high_done", kbase="kbase_ovn_high", ycol2="high_done",
                            kbase2="kbase_high", invert=False, kmax=K_OVN_MAX,
                            claim="the 18:00-08:59 high is already in"))
    INTRA_FLAGS.append(dict(name=f"OVN_LO_IN@{thr:.2f}", family="OVN", side="low", pcol="p_ovn_low_done", rawcol="p_ovn_low_raw",
                            thr=thr, op=">=", ycol="overnight_low_done", kbase="kbase_ovn_low", ycol2="low_done",
                            kbase2="kbase_low", invert=False, kmax=K_OVN_MAX,
                            claim="the 18:00-08:59 low is already in"))
INTRA_BY_NAME = {f["name"]: f for f in INTRA_FLAGS}

# Pre-Asia calls (one per night, decision time 17:xx ET).
PRE_CALLS = []
for thr in (0.70, 0.80, 0.90):
    PRE_CALLS.append(dict(name=f"BREAK_HI@{thr:.2f}", target="high_above_rth_high", thr=thr, op=">=", invert=False,
                          claim="Asia trades above the RTH high tonight"))
    PRE_CALLS.append(dict(name=f"BREAK_LO@{thr:.2f}", target="low_below_rth_low", thr=thr, op=">=", invert=False,
                          claim="Asia trades below the RTH low tonight"))
for thr in (0.10, 0.05):
    PRE_CALLS.append(dict(name=f"HOLD_HI@{thr:.2f}", target="high_above_rth_high", thr=thr, op="<=", invert=True,
                          claim="the RTH high holds tonight"))
    PRE_CALLS.append(dict(name=f"HOLD_LO@{thr:.2f}", target="low_below_rth_low", thr=thr, op="<=", invert=True,
                          claim="the RTH low holds tonight"))
PRE_BY_NAME = {c["name"]: c for c in PRE_CALLS}

HEADLINE_INTRA = ["HI_IN@0.90", "LO_IN@0.90", "OVN_LO_IN@0.90"]
HEADLINE_PRE = ["BREAK_HI@0.70", "BREAK_LO@0.70", "HOLD_HI@0.10", "HOLD_LO@0.10"]


# --------------------------------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------------------------------
def wilson(h: float, n: float, z: float = Z90) -> tuple[float, float]:
    """Wilson score interval for h successes in n trials."""
    if n <= 0:
        return (np.nan, np.nan)
    p = h / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = z * np.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return (centre - half, centre + half)


def session_boot_ci(y: np.ndarray, sess: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    """Percentile 90 % CI of a pooled rate under a session-block bootstrap (sessions resampled with replacement)."""
    y = np.asarray(y, dtype=float)
    if len(y) == 0:
        return (np.nan, np.nan)
    codes, inv = np.unique(np.asarray(sess), return_inverse=True)
    S = len(codes)
    sums = np.bincount(inv, weights=y, minlength=S)
    cnts = np.bincount(inv, minlength=S).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, S, size=(n_boot, S))
    rates = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return (float(np.percentile(rates, 5)), float(np.percentile(rates, 95)))


def qtiles(x, qs=(0.5, 0.75, 0.9)) -> list[float]:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return [np.nan] * len(qs)
    return [float(np.quantile(x, q)) for q in qs]


def close_time_et(k: int) -> str:
    """Wall-clock close of Asia bar k (k = 0 is the 18:00 bar, which closes at 19:00 ET)."""
    return f"{(19 + int(k)) % 24:02d}:00"


# --------------------------------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------------------------------
class SymData:
    def __init__(self, sym: str):
        self.sym = sym
        self.oos = pd.read_csv(os.path.join(HERE, f"oos_intrasession_{sym}.csv"), parse_dates=["date"])
        self.pre = pd.read_csv(os.path.join(HERE, f"oos_preasia_{sym}.csv"), parse_dates=["date"])
        self.panel = pd.read_csv(os.path.join(HERE, f"{sym}_hourly_panel.csv"), parse_dates=["date"])
        ext = pd.read_csv(os.path.join(HERE, f"{sym}_extremes.csv"), index_col=0, parse_dates=True)
        # ex-ante 20-session median Asia range (bp), the panel's med20 convention (strictly prior sessions)
        self.ext = ext.assign(asia_gdate=pd.to_datetime(ext["asia_gdate"]),
                              med20_bp=ext["rng_bp"].shift(1).rolling(20, min_periods=10).median())
        self.h = load_hourly(os.path.join(DATA, f"{sym}_1h.csv"))

        # attach panel running extremes and session context to the OOS rows
        pcols = ["date", "k", "run_hi_bp", "run_lo_bp", "cum_ret_bp", "hi_k", "lo_k"]
        self.oos = self.oos.merge(self.panel[pcols], on=["date", "k"], how="left", validate="one_to_one")
        ecols = ["ref_close", "asia_high", "asia_low", "ovn_high_bp", "ovn_low_bp", "vix", "sunday_open", "dow",
                 "is_dst", "asia_gdate", "med20_bp", "n_bars"]
        self.oos = self.oos.merge(self.ext[ecols], left_on="date", right_index=True, how="left")
        self.oos = self.oos.sort_values(["date", "k"]).reset_index(drop=True)
        self.oos = self.oos.assign(month=self.oos["date"].dt.strftime("%Y-%m"))
        self.pre = self.pre.merge(self.ext[["vix", "sunday_open", "is_dst"]].rename(columns={"is_dst": "is_dst_ext"}),
                                  left_on="date", right_index=True, how="left")
        self.pre = self.pre.assign(month=self.pre["date"].dt.strftime("%Y-%m"))

        # raw night arrays: 9 Asia bars followed by the Europe bars of the same Globex date
        self.nights = self._night_arrays()

        # population bookkeeping for the method section
        a_dates = pd.DatetimeIndex(self.oos["date"].unique())
        in_window = self.ext[(self.ext.index >= a_dates.min()) & (self.ext.index <= a_dates.max())]
        nan_ovn = self.oos.loc[self.oos["overnight_high_done"].isna(), "date"].unique()
        med_diff = (self.ext.loc[a_dates, "med20_bp"] - self.ext.loc[a_dates, "asia_rng_med20"] * 1e4).abs()
        self.meta = dict(
            detector_A=dict(n_sessions=int(len(a_dates)), first=a_dates.min().strftime("%Y-%m-%d"), last=a_dates.max().strftime("%Y-%m-%d"),
                            n_rows=int(len(self.oos)), n_rows_k_le_7=int((self.oos["k"] <= 7).sum()),
                            n_sessions_overnight_labelled=int(len(a_dates) - len(nan_ovn)),
                            sessions_without_overnight_label=[pd.Timestamp(d).strftime("%Y-%m-%d") for d in nan_ovn],
                            n_rows_without_overnight_label=int(self.oos["overnight_high_done"].isna().sum()),
                            n_sessions_calibrated=int(self.oos.groupby("date")["calibrated"].max().sum()),
                            first_calibrated=self.oos.loc[self.oos["calibrated"] == 1, "date"].min().strftime("%Y-%m-%d")),
            detector_B=dict(n_nights=int(len(self.pre)), first=self.pre["date"].min().strftime("%Y-%m-%d"),
                            last=self.pre["date"].max().strftime("%Y-%m-%d"),
                            n_nights_calibrated=int(self.pre["high_above_rth_high__full__cal_on"].sum()),
                            first_calibrated=self.pre.loc[self.pre["high_above_rth_high__full__cal_on"] == 1, "date"].min().strftime("%Y-%m-%d")),
            extremes_table=dict(n_sessions=int(len(self.ext)), first=self.ext.index.min().strftime("%Y-%m-%d"),
                                last=self.ext.index.max().strftime("%Y-%m-%d"),
                                n_short_nights_total=int((self.ext["n_bars"] != 9).sum()),
                                n_short_nights_in_A_window=int((in_window["n_bars"] != 9).sum()),
                                n_sessions_in_A_window=int(len(in_window)),
                                n_in_A_window_not_in_A=int(len(in_window) - len(a_dates)),
                                n_sunday_reopens_A=int(self.ext.loc[a_dates, "sunday_open"].sum()),
                                vix_terciles_A=[round(float(v), 2) for v in np.quantile(self.ext.loc[a_dates, "vix"].values, [1 / 3, 2 / 3])],
                                short_nights_in_A_window=self._short_night_layout(in_window)),
            # the tight stop of the trade translation uses med20_bp = rolling 20-session median of the extremes
            # table's rng_bp (Asia range vs the 17:00 ref close, strictly prior sessions).  The codebase's
            # asia_rng_med20 (features.py) is the median of (asia_high - asia_low) / asia_open over the sessions
            # table; the two series are compared here over the Detector A sessions.
            med20_convention=dict(used="rolling 20-session median of extremes rng_bp (Asia range in bp of ref_close), strictly prior sessions, min 10",
                                  codebase_series="asia_rng_med20 = rolling 20-session median of (asia_high - asia_low) / asia_open",
                                  abs_diff_bp_median=round(float(med_diff.median()), 3), abs_diff_bp_max=round(float(med_diff.max()), 3),
                                  n_dates_abs_diff_gt_1bp=int((med_diff > 1.0).sum()), n_dates=int(len(med_diff))))

    def _short_night_layout(self, in_window: pd.DataFrame) -> list:
        """Which Asia bars exist on the short nights (n_bars != 9) inside the Detector A window."""
        h = self.h
        day = h.index.tz_localize(None).normalize(); hour = h.index.hour
        out = []
        for d, r in in_window[in_window["n_bars"] != 9].iterrows():
            gd = pd.Timestamp(r["asia_gdate"])
            m = ((day == gd - pd.Timedelta(days=1)) & (hour >= 18)) | ((day == gd) & (hour <= 2))
            present = [int(x) for x in h.index[m].hour]
            missing = [x for x in ASIA_HOURS if x not in present]
            out.append(dict(date=d.strftime("%Y-%m-%d"), n_bars=int(r["n_bars"]), missing_hours_et=missing))
        return out

    def _night_arrays(self) -> dict:
        h = self.h
        day = h.index.tz_localize(None).normalize()
        hour = h.index.hour
        out = {}
        for d in self.oos["date"].unique():
            gd = self.ext.loc[d, "asia_gdate"]
            m_asia = ((day == gd - pd.Timedelta(days=1)) & (hour >= 18)) | ((day == gd) & (hour <= 2))
            m_eur = (day == gd) & (hour >= 3) & (hour <= 8)
            a = h[m_asia]
            e = h[m_eur]
            if len(a) != 9 or list(a.index.hour) != ASIA_HOURS:
                raise RuntimeError(f"{self.sym} {d.date()}: unexpected Asia bar layout {list(a.index.hour)}")
            if not all(x in EUROPE_HOURS for x in e.index.hour):
                raise RuntimeError(f"{self.sym} {d.date()}: unexpected Europe bars")
            bars = pd.concat([a, e])
            out[d] = dict(O=bars["Open"].values, H=bars["High"].values, L=bars["Low"].values,
                          C=bars["Close"].values, n_eur=len(e))
            # the panel's running extremes must equal the raw cumulative extremes
            ref = self.ext.loc[d, "ref_close"]
            sub = self.oos[self.oos["date"] == d]
            run_hi = ref * (1 + sub["run_hi_bp"].values / 1e4)
            run_lo = ref * (1 + sub["run_lo_bp"].values / 1e4)
            if not (np.allclose(run_hi, np.maximum.accumulate(out[d]["H"][:9]), rtol=1e-9)
                    and np.allclose(run_lo, np.minimum.accumulate(out[d]["L"][:9]), rtol=1e-9)):
                raise RuntimeError(f"{self.sym} {d.date()}: panel running extremes disagree with raw bars")
        return out


# --------------------------------------------------------------------------------------------------
# intra-session flags
# --------------------------------------------------------------------------------------------------
def _fire_mask(s: pd.Series, thr: float, op: str) -> pd.Series:
    return (s >= thr) if op == ">=" else (s <= thr)


def intra_population(sd: SymData, spec: dict) -> tuple[pd.DataFrame, dict]:
    """Rows eligible for the flag (k <= kmax, label present) and the exclusion counts."""
    df = sd.oos[sd.oos["k"] <= spec["kmax"]]
    lab = df[spec["ycol"]]
    excl = dict(n_rows_excluded_nan_label=int(lab.isna().sum()),
                n_sessions_excluded_nan_label=int(df.loc[lab.isna(), "date"].nunique()))
    df = df[lab.notna()]
    return df, excl


def flagged_rows(sd: SymData, spec: dict, version: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    pcol = spec["pcol"] if version == "cal" else spec["rawcol"]
    df, excl = intra_population(sd, spec)
    fired = df[_fire_mask(df[pcol], spec["thr"], spec["op"])].copy()
    inv = spec["invert"]
    fired["p"] = fired[pcol]
    fired["y"] = (1 - fired[spec["ycol"]]) if inv else fired[spec["ycol"]]
    fired["kb"] = (1 - fired[spec["kbase"]]) if inv else fired[spec["kbase"]]
    fired["y2"] = (1 - fired[spec["ycol2"]]) if inv else fired[spec["ycol2"]]
    fired["kb2"] = (1 - fired[spec["kbase2"]]) if inv else fired[spec["kbase2"]]
    return df, fired, excl


def excess_fields(sd: SymData, row: pd.Series, spec: dict) -> dict:
    """For a failed 'already in' claim: how far beyond the running extreme the eventual extreme printed, and when.
    excess_bp_vs_close is close-denominated on both sides (high: eventual / close - 1 = remaining_up_bp;
    low: 1 - eventual / close = -remaining_down_bp).  excess_bp_above_running_extreme is eventual / running - 1
    for the high (bp of the running high) and running / eventual - 1 for the low (bp of the eventual low)."""
    nb = sd.nights[row["date"]]
    k = int(row["k"])
    window = 9 if spec["family"] == "IN" else 9 + nb["n_eur"]
    if spec["side"] == "high":
        run = nb["H"][:k + 1].max()
        path = nb["H"][:window]
        new_k = int(np.argmax(path))
        eventual = path[new_k]
        exc_run = (eventual / run - 1) * 1e4
        exc_close = (eventual / nb["C"][k] - 1) * 1e4
    else:
        run = nb["L"][:k + 1].min()
        path = nb["L"][:window]
        new_k = int(np.argmin(path))
        eventual = path[new_k]
        exc_run = (run / eventual - 1) * 1e4
        exc_close = (1 - eventual / nb["C"][k]) * 1e4
    return dict(excess_bp_vs_close=float(exc_close), excess_bp_above_running_extreme=float(exc_run),
                new_extreme_k=new_k, bars_until_new_extreme=new_k - k)


def evaluate_intra(sd: SymData) -> dict:
    rows_rl, rows_ff, rows_byk, fails, events_store = [], [], [], [], {}
    for spec in INTRA_FLAGS:
        for version in ("cal", "raw"):
            df, fired, excl = flagged_rows(sd, spec, version)
            n_sessions_pop = int(df["date"].nunique())
            # (a) row level
            y = fired["y"].values.astype(float)
            ci = session_boot_ci(y, fired["date"].values)
            y2 = fired["y2"].dropna()
            kb2 = fired.loc[fired["y2"].notna(), "kb2"]
            ci2 = session_boot_ci(y2.values.astype(float), fired.loc[fired["y2"].notna(), "date"].values)
            rows_rl.append(dict(
                sym=sd.sym, flag=spec["name"], version=version, claim=spec["claim"],
                n_rows_population=int(len(df)), n_sessions_population=n_sessions_pop,
                n_rows=int(len(fired)), n_sessions=int(fired["date"].nunique()),
                share_rows=len(fired) / len(df) if len(df) else np.nan,
                hits=int(y.sum()), hit_rate=float(y.mean()) if len(y) else np.nan, ci_lo=ci[0], ci_hi=ci[1],
                kmatched_base=float(fired["kb"].mean()) if len(fired) else np.nan,
                lift=float(y.mean() - fired["kb"].mean()) if len(fired) else np.nan,
                secondary_outcome=("overnight label" if spec["family"] != "OVN" else "Asia label"),
                secondary_hit_rate=float(y2.mean()) if len(y2) else np.nan, n_secondary=int(len(y2)),
                secondary_ci_lo=ci2[0], secondary_ci_hi=ci2[1],
                secondary_kmatched_base=float(kb2.mean()) if len(kb2) else np.nan,
                mean_p=float(fired["p"].mean()) if len(fired) else np.nan, **excl))
            # (b) first firing per session
            ev = fired.sort_values(["date", "k"]).groupby("date", sort=True).head(1).copy()
            n_ev = int(len(ev))
            hits = int(ev["y"].sum()) if n_ev else 0
            wl = wilson(hits, n_ev)
            kcounts = ev["k"].value_counts().reindex(range(0, spec["kmax"] + 1), fill_value=0)
            med_k = float(ev["k"].median()) if n_ev else np.nan
            med_k_lower = int(np.quantile(ev["k"].values, 0.5, method="lower")) if n_ev else None
            med_k_upper = int(np.quantile(ev["k"].values, 0.5, method="higher")) if n_ev else None
            # the close time of the median bar; when the median falls between two observed bars (an even count
            # with different middle values) print both closes, so that "5.5 (00:00-01:00)" cannot be misread
            med_time = ("" if not n_ev else close_time_et(med_k_lower) if med_k_lower == med_k_upper
                        else f"{close_time_et(med_k_lower)}-{close_time_et(med_k_upper)}")
            ev2 = ev["y2"].dropna()
            kb2 = ev.loc[ev["y2"].notna(), "kb2"]
            # failures
            fl = ev[ev["y"] == 0]
            fl_rows = []
            for _, r in fl.iterrows():
                # secondary outcome: the overnight label for the Asia flags, the Asia label for the overnight flags
                # (at an overnight-flag failure the overnight label is 0 by construction)
                rec = dict(sym=sd.sym, date=r["date"].strftime("%Y-%m-%d"), flag=spec["name"], version=version,
                           k=int(r["k"]), close_time_et=close_time_et(r["k"]), p=float(r["p"]),
                           kmatched_base=float(r["kb"]),
                           secondary_outcome=(float(r["y2"]) if pd.notna(r["y2"]) else np.nan),
                           secondary_outcome_label=("overnight label" if spec["family"] != "OVN" else "Asia label"))
                if spec["family"] in ("IN", "OVN"):
                    rec.update(excess_fields(sd, r, spec))
                else:   # AHEAD: the failure is that no new extreme printed; the extreme bar is in the past
                    rec.update(excess_bp_vs_close=np.nan, excess_bp_above_running_extreme=np.nan,
                               new_extreme_k=int(r["hi_k"] if spec["side"] == "high" else r["lo_k"]),
                               bars_until_new_extreme=np.nan)
                fl_rows.append(rec)
            fails.extend(fl_rows)
            fdf = pd.DataFrame(fl_rows)
            exc_c = qtiles(fdf["excess_bp_vs_close"]) if len(fdf) else [np.nan] * 3
            exc_r = qtiles(fdf["excess_bp_above_running_extreme"]) if len(fdf) else [np.nan] * 3
            bu = qtiles(fdf["bars_until_new_extreme"]) if len(fdf) else [np.nan] * 3
            next_bar = float((fdf["bars_until_new_extreme"] == 1).mean()) if len(fdf) and fdf["bars_until_new_extreme"].notna().any() else np.nan
            rows_ff.append(dict(
                sym=sd.sym, flag=spec["name"], version=version, claim=spec["claim"],
                n_sessions_population=n_sessions_pop, n_fired=n_ev, share_sessions_fired=n_ev / n_sessions_pop,
                **{f"k{k}": int(kcounts.get(k, 0)) for k in range(0, 9)},
                median_first_k=med_k, median_first_close_time_et=med_time,
                hits=hits, hit_rate=(hits / n_ev if n_ev else np.nan), ci_lo=wl[0], ci_hi=wl[1],
                kmatched_base=float(ev["kb"].mean()) if n_ev else np.nan,
                lift=float(ev["y"].mean() - ev["kb"].mean()) if n_ev else np.nan,
                secondary_outcome=("overnight label (hold through Europe)" if spec["family"] != "OVN" else "Asia label"),
                secondary_hit_rate=float(ev2.mean()) if len(ev2) else np.nan, n_secondary=int(len(ev2)),
                secondary_ci_lo=wilson(ev2.sum(), len(ev2))[0], secondary_ci_hi=wilson(ev2.sum(), len(ev2))[1],
                secondary_kmatched_base=float(kb2.mean()) if len(kb2) else np.nan,
                n_fail=int(len(fdf)),
                fail_excess_close_med=exc_c[0], fail_excess_close_p75=exc_c[1], fail_excess_close_p90=exc_c[2],
                fail_excess_run_med=exc_r[0], fail_excess_run_p75=exc_r[1], fail_excess_run_p90=exc_r[2],
                fail_bars_until_med=bu[0], fail_bars_until_p75=bu[1], fail_bars_until_p90=bu[2],
                fail_share_next_bar=next_bar, mean_p=float(ev["p"].mean()) if n_ev else np.nan, **excl))
            # by k
            for k, g in ev.groupby("k"):
                hk = int(g["y"].sum()); nk = int(len(g)); w = wilson(hk, nk)
                g2 = g["y2"].dropna()
                rows_byk.append(dict(sym=sd.sym, flag=spec["name"], version=version, k=int(k), close_time_et=close_time_et(k),
                                     n_fired=nk, hits=hk, hit_rate=hk / nk, ci_lo=w[0], ci_hi=w[1],
                                     kmatched_base=float(g["kb"].mean()), lift=float(g["y"].mean() - g["kb"].mean()),
                                     secondary_hit_rate=float(g2.mean()) if len(g2) else np.nan, n_secondary=int(len(g2))))
            events_store[(spec["name"], version)] = (df, ev)
    return dict(rowlevel=rows_rl, first=rows_ff, byk=rows_byk, failures=fails, events=events_store)


# --------------------------------------------------------------------------------------------------
# pre-Asia calls
# --------------------------------------------------------------------------------------------------
def evaluate_preasia(sd: SymData) -> dict:
    pre = sd.pre
    n_nights = int(len(pre))
    rows, events = [], {}
    for spec in PRE_CALLS:
        T = spec["target"]
        for version in ("cal", "raw"):
            pcol = f"{T}__full__p_cal" if version == "cal" else f"{T}__full__p_raw"
            called = pre[_fire_mask(pre[pcol], spec["thr"], spec["op"])].copy()
            inv = spec["invert"]
            called["p"] = called[pcol]
            called["y"] = (1 - called[f"{T}__y"]) if inv else called[f"{T}__y"]
            called["kb"] = (1 - called[f"{T}__full__base"]) if inv else called[f"{T}__full__base"]
            n = int(len(called)); hits = int(called["y"].sum()); w = wilson(hits, n)
            rows.append(dict(sym=sd.sym, call=spec["name"], version=version, claim=spec["claim"], n_nights=n_nights,
                             n_called=n, share_called=n / n_nights, hits=hits, hit_rate=(hits / n if n else np.nan),
                             ci_lo=w[0], ci_hi=w[1], base_rate=float(called["kb"].mean()) if n else np.nan,
                             lift=float(called["y"].mean() - called["kb"].mean()) if n else np.nan,
                             mean_p=float(called["p"].mean()) if n else np.nan,
                             population_rate=float(((1 - pre[f"{T}__y"]) if inv else pre[f"{T}__y"]).mean())))
            events[(spec["name"], version)] = called
    # envelope coverage
    env = []
    for window, sub in (("full", pre), ("last12m", pre[(pre["date"] >= LAST12_START) & (pre["date"] <= LAST12_END)])):
        for q in ("hi_bp", "lo_bp", "rng_bp"):
            y = sub[f"{q}__y"]
            for source, pfx in (("model", ""), ("base", "base_")):
                lo, mid, hi = sub[f"{q}__{pfx}q20"], sub[f"{q}__{pfx}q50"], sub[f"{q}__{pfx}q80"]
                n = int(y.notna().sum())
                nb, ni, na = int((y < lo).sum()), int(((y >= lo) & (y <= hi)).sum()), int((y > hi).sum())
                # the shipped quantiles are fitted separately per level and are not monotone on every night;
                # coverage is computed on the quantiles as shipped (a night with q20 > q80 cannot be "inside")
                n_cross = int(((lo > mid) | (mid > hi)).sum()); n_inv = int((lo > hi).sum())
                env.append(dict(sym=sd.sym, window=window, quantity=q, source=source, n=n,
                                share_below_q20=nb / n, below_ci_lo=wilson(nb, n)[0], below_ci_hi=wilson(nb, n)[1],
                                share_inside=ni / n, inside_ci_lo=wilson(ni, n)[0], inside_ci_hi=wilson(ni, n)[1],
                                share_above_q80=na / n, above_ci_lo=wilson(na, n)[0], above_ci_hi=wilson(na, n)[1],
                                mae_q50=float((y - mid).abs().mean()),
                                median_q50=float(mid.median()), median_y=float(y.median()),
                                n_quantiles_cross=n_cross, n_q20_above_q80=n_inv))
    # joint map calls
    joint = []
    for version in ("cal", "raw"):
        sfx = "p_cal" if version == "cal" else "p_raw"
        ph = pre[f"high_above_rth_high__full__{sfx}"]; pl = pre[f"low_below_rth_low__full__{sfx}"]
        yh = pre["high_above_rth_high__y"]; yl = pre["low_below_rth_low__y"]
        for name, m, y_ext, y_hold in (("BREAK_HI@0.70 & HOLD_LO@0.10: extends up, low holds", (ph >= 0.70) & (pl <= 0.10), yh, yl),
                                       ("BREAK_LO@0.70 & HOLD_HI@0.10: extends down, high holds", (pl >= 0.70) & (ph <= 0.10), yl, yh)):
            n = int(m.sum()); ye = y_ext[m]; yo = y_hold[m]
            exact = int(((ye == 1) & (yo == 0)).sum()); both = int(((ye == 1) & (yo == 1)).sum())
            neither = int(((ye == 0) & (yo == 0)).sum()); only_other = int(((ye == 0) & (yo == 1)).sum())
            w = wilson(exact, n)
            joint.append(dict(sym=sd.sym, version=version, joint_call=name, n_nights=n_nights, n_called=n,
                              share_called=n / n_nights, n_exact=exact, share_exact=(exact / n if n else np.nan),
                              exact_ci_lo=w[0], exact_ci_hi=w[1],
                              n_extended_but_other_broke=both, n_neither_broke=neither, n_only_other_broke=only_other,
                              base_exact=float(((y_ext == 1) & (y_hold == 0)).mean())))
    return dict(calls=rows, envelope=env, joint=joint, events=events)


# --------------------------------------------------------------------------------------------------
# stability cuts
# --------------------------------------------------------------------------------------------------
def _cut_rows(flag: str, sym: str, pop: pd.DataFrame, ev: pd.DataFrame, cuts: list, with_k: bool) -> tuple[list, list]:
    """pop: one row per session in the population (date, vix, sunday_open, is_dst, month).
    ev: one row per firing session (date, k, y, kb)."""
    out, monthly = [], []
    vix_q = np.quantile(pop["vix"].dropna().values, [1 / 3, 2 / 3])
    tert = pd.cut(pop["vix"], bins=[-np.inf, vix_q[0], vix_q[1], np.inf], labels=["T1", "T2", "T3"])
    pop = pop.assign(vix_tercile=tert.astype(str))
    ev = ev.merge(pop[["date", "vix_tercile"]], on="date", how="left")
    for cname, labels, pop_mask_fn, ev_mask_fn in cuts:
        for lab in labels:
            pm = pop_mask_fn(pop, lab); em = ev_mask_fn(ev, lab)
            n_pop = int(pm.sum()); e = ev[em]; n = int(len(e)); h = int(e["y"].sum()) if n else 0; w = wilson(h, n)
            cv = lab
            if cname == "vix_tercile":
                cv = {"T1": f"T1 (vix <= {vix_q[0]:.2f})", "T2": f"T2 ({vix_q[0]:.2f} < vix <= {vix_q[1]:.2f})",
                      "T3": f"T3 (vix > {vix_q[1]:.2f})"}[lab]
            out.append(dict(flag=flag, sym=sym, cut_name=cname, cut_value=cv, n_sessions_in_cut=n_pop, n_fired=n,
                            share_fired=(n / n_pop if n_pop else np.nan), hits=h, hit_rate=(h / n if n else np.nan),
                            ci_lo=w[0], ci_hi=w[1], base_rate=(float(e["kb"].mean()) if n else np.nan),
                            lift=(float(e["y"].mean() - e["kb"].mean()) if n else np.nan)))
    if with_k:
        for k in sorted(ev["k"].unique()):
            e = ev[ev["k"] == k]; n = int(len(e)); h = int(e["y"].sum()); w = wilson(h, n)
            out.append(dict(flag=flag, sym=sym, cut_name="k", cut_value=f"k={int(k)} ({close_time_et(k)} close)",
                            n_sessions_in_cut=int(len(pop)), n_fired=n, share_fired=n / len(pop), hits=h, hit_rate=h / n,
                            ci_lo=w[0], ci_hi=w[1], base_rate=float(e["kb"].mean()), lift=float(e["y"].mean() - e["kb"].mean())))
    for m in sorted(pop["month"].unique()):
        e = ev[ev["month"] == m]; n = int(len(e)); h = int(e["y"].sum()) if n else 0; w = wilson(h, n)
        monthly.append(dict(flag=flag, sym=sym, month=m, n_sessions=int((pop["month"] == m).sum()), n_fired=n,
                            share_fired=n / max(int((pop["month"] == m).sum()), 1), hits=h,
                            hit_rate=(h / n if n else np.nan), ci_lo=w[0], ci_hi=w[1],
                            base_rate=(float(e["kb"].mean()) if n else np.nan), low_n=int(n < LOW_N)))
    return out, monthly


CUTS = [
    ("window", ["full", "last12m", "H1", "H2"],
     lambda p, l: {"full": p["date"] >= pd.Timestamp("1900-01-01"),
                   "last12m": (p["date"] >= LAST12_START) & (p["date"] <= LAST12_END),
                   "H1": p["date"] < H2_START, "H2": p["date"] >= H2_START}[l],
     lambda e, l: {"full": e["date"] >= pd.Timestamp("1900-01-01"),
                   "last12m": (e["date"] >= LAST12_START) & (e["date"] <= LAST12_END),
                   "H1": e["date"] < H2_START, "H2": e["date"] >= H2_START}[l]),
    ("session_type", ["sunday_reopen", "weeknight"],
     lambda p, l: p["sunday_open"] == (1 if l == "sunday_reopen" else 0),
     lambda e, l: e["sunday_open"] == (1 if l == "sunday_reopen" else 0)),
    ("vix_tercile", ["T1", "T2", "T3"], lambda p, l: p["vix_tercile"] == l, lambda e, l: e["vix_tercile"] == l),
    ("dst", ["EDT", "EST"], lambda p, l: p["is_dst"] == (1 if l == "EDT" else 0),
     lambda e, l: e["is_dst"] == (1 if l == "EDT" else 0)),
]


def stability(sd: SymData, intra: dict, pre: dict) -> tuple[list, list]:
    out, monthly = [], []
    for spec in INTRA_FLAGS:
        df, ev = intra["events"][(spec["name"], "cal")]
        pop = df.groupby("date", as_index=False).agg(vix=("vix", "first"), sunday_open=("sunday_open", "first"),
                                                    is_dst=("is_dst", "first"), month=("month", "first"))
        e = ev[["date", "k", "y", "kb", "sunday_open", "is_dst", "month"]].copy()
        o, m = _cut_rows(spec["name"], sd.sym, pop, e, CUTS, with_k=True)
        out += o; monthly += m
    pop = sd.pre[["date", "vix", "sunday_open", "is_dst", "month"]].copy()
    for spec in PRE_CALLS:
        called = pre["events"][(spec["name"], "cal")]
        e = called[["date", "y", "kb", "sunday_open", "is_dst", "month"]].copy(); e["k"] = -1
        o, m = _cut_rows(spec["name"], sd.sym, pop, e, CUTS, with_k=False)
        out += o; monthly += m
    return out, monthly


# --------------------------------------------------------------------------------------------------
# trade translation (evaluation device, not a strategy)
# --------------------------------------------------------------------------------------------------
def race(nb: dict, k: int, side: str, stop: float, target: float, horizon: int) -> dict:
    """Bar-by-bar race from the close of bar k to the close of bar `horizon` (inclusive).
    A bar touching both levels counts as a STOP (conservative).  Returns outcome, exit bar, MFE / MAE (bp of entry)
    over the bars held, P&L at the horizon close when neither level was touched."""
    H, L, C = nb["H"], nb["L"], nb["C"]
    entry = C[k]
    outcome, exit_k = "neither", horizon
    for j in range(k + 1, horizon + 1):
        if side == "long":
            s_hit, t_hit = L[j] <= stop, H[j] >= target
        else:
            s_hit, t_hit = H[j] >= stop, L[j] <= target
        if s_hit:
            outcome, exit_k = "stop", j; break
        if t_hit:
            outcome, exit_k = "target", j; break
    hh = H[k + 1:exit_k + 1].max(); ll = L[k + 1:exit_k + 1].min()
    if side == "long":
        mfe, mae = (hh / entry - 1) * 1e4, (ll / entry - 1) * 1e4
        pnl_h = (C[horizon] / entry - 1) * 1e4
        pnl_exit = {"stop": (stop / entry - 1) * 1e4, "target": (target / entry - 1) * 1e4, "neither": pnl_h}[outcome]
    else:
        mfe, mae = (1 - ll / entry) * 1e4, (1 - hh / entry) * 1e4
        pnl_h = (1 - C[horizon] / entry) * 1e4
        pnl_exit = {"stop": (1 - stop / entry) * 1e4, "target": (1 - target / entry) * 1e4, "neither": pnl_h}[outcome]
    sgn = 1.0 if side == "long" else -1.0
    return dict(outcome=outcome, exit_k=exit_k, mfe=float(mfe), mae=float(mae),
                pnl_horizon=float(pnl_h) if outcome == "neither" else np.nan, pnl_exit=float(pnl_exit),
                dist_stop_bp=float(sgn * (entry / stop - 1) * 1e4), dist_target_bp=float(sgn * (target / entry - 1) * 1e4))


def _weighted_median(x: np.ndarray, w: np.ndarray) -> float:
    x = np.asarray(x, dtype=float); w = np.asarray(w, dtype=float)
    m = np.isfinite(x) & np.isfinite(w)
    x, w = x[m], w[m]
    if len(x) == 0 or w.sum() <= 0:
        return np.nan
    o = np.argsort(x); cw = np.cumsum(w[o]) / w.sum()
    return float(x[o][np.searchsorted(cw, 0.5)])


def matched_rates(cell: np.ndarray, n_cells: int, f: np.ndarray, allm: np.ndarray, bins: dict,
                  d_stop: np.ndarray, d_tgt: np.ndarray, S: int) -> dict:
    """Cell-matched unconditional rates: for every binary outcome in `bins` (name -> (S, K) array of 0 / 1 / NaN)
    the unconditional rate in each cell, weighted by the share of firings in that cell.  Session bootstrap
    (N_BOOT draws, seed 0, one draw matrix shared by all outcomes) for the matched rates ('<name>_ci') and for
    the difference conditional minus matched ('diff_<name>_ci').  Arrays are (S sessions x K entry bars)."""
    onehot = (cell[..., None] == np.arange(n_cells)[None, None, :]).astype(float)       # (S, K, C)
    ff = f.astype(float); okm = allm.astype(float)
    w_cell = (ff[..., None] * onehot).sum(axis=(0, 1)); w_cell = w_cell / w_cell.sum()
    def cell_rate(a):
        m = allm & np.isfinite(a)
        a0 = np.where(m, a, 0.0); m0 = m.astype(float)
        num = (a0[..., None] * onehot).sum(axis=(0, 1)); den = (m0[..., None] * onehot).sum(axis=(0, 1))
        return np.where(den > 0, num / np.maximum(den, 1), np.nan)
    # matched entry distances: pooled weighted median, each unconditional row weighted to its cell's firing share
    row_cell_n = (okm[..., None] * onehot).sum(axis=(0, 1))
    row_w = (onehot * (w_cell / np.maximum(row_cell_n, 1))[None, None, :]).sum(axis=2) * okm
    out = dict(d_stop=_weighted_median(d_stop[allm], row_w[allm]), d_tgt=_weighted_median(d_tgt[allm], row_w[allm]))
    # bootstrap
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, S, size=(N_BOOT, S))
    cnt = np.stack([np.bincount(row, minlength=S) for row in idx]).astype(float)         # (N_BOOT, S)
    def boot_cell(a, m):
        a0 = np.where(m, a, 0.0).astype(float)
        num = np.einsum("bs,skc->bc", cnt, a0[..., None] * onehot)
        den = np.einsum("bs,skc->bc", cnt, m.astype(float)[..., None] * onehot)
        return num, den
    fw, _ = boot_cell(np.ones_like(ff), f)                                              # firings per cell per draw
    fw = fw / fw.sum(axis=1, keepdims=True)
    pct = lambda a: (float(np.nanpercentile(a, 5)), float(np.nanpercentile(a, 95)))
    for name, a in bins.items():
        m = allm & np.isfinite(a)
        out[name] = float(np.nansum(w_cell * cell_rate(a)))
        num, den = boot_cell(np.where(m, a, 0.0), m)
        rate = np.where(den > 0, num / np.maximum(den, 1), np.nan)
        mb = np.nansum(fw * rate, axis=1)
        fm = f & np.isfinite(a)
        cond = (np.einsum("bs,s->b", cnt, np.where(fm, a, 0.0).sum(1))
                / np.einsum("bs,s->b", cnt, fm.sum(1).astype(float)))
        out[f"{name}_ci"] = pct(mb); out[f"diff_{name}_ci"] = pct(cond - mb)
    return out


def trade_table(sd: SymData, intra: dict) -> list:
    rows = []
    dates = list(sd.oos["date"].unique())
    S = len(dates); d_index = {d: i for i, d in enumerate(dates)}
    K = TRADE_KMAX + 1
    ARRS = ("tgt", "stp", "tgt_next_bar", "tgt_near", "tight_med", "tight_rth", "mfe", "mae", "pnl_h", "pnl_x",
            "pnl_tight_med", "pnl_tight_rth", "d_stop", "d_tgt")
    for signal, flag, side in (("LO_IN@0.90 long", "LO_IN@0.90", "long"), ("HI_IN@0.90 short", "HI_IN@0.90", "short")):
        df, ev = intra["events"][(flag, "cal")]
        ev = ev[ev["k"] <= TRADE_KMAX]
        fired = np.zeros((S, K), dtype=bool)
        for d, k in zip(ev["date"], ev["k"]):
            fired[d_index[d], int(k)] = True
        for hname, horizon in (("A_0200", 8), ("B_0800", 14)):
            ok = np.ones(S, dtype=bool)
            A = {name: np.full((S, K), np.nan) for name in ARRS}
            for d in dates:
                nb = sd.nights[d]
                i = d_index[d]
                if horizon == 14 and nb["n_eur"] < 6:
                    ok[i] = False; continue
                ref = sd.ext.loc[d, "ref_close"]; med = sd.ext.loc[d, "med20_bp"]
                # two tight-stop distances beyond the running extreme: the specification's 0.10 x the 20-session
                # median Asia range (extremes-table rng_bp, vs ref_close), and the engine's distance, 0.10 x today's
                # RTH range (the engine itself places that stop beyond the RTH extreme, not the running Asia extreme)
                tight_med = ref * med / 1e4 * TIGHT_STOP_FRAC if pd.notna(med) else np.nan
                rth_rng = sd.ext.loc[d, "lvl_rth_high"] - sd.ext.loc[d, "lvl_rth_low"]
                tight_rth = TIGHT_STOP_FRAC * rth_rng if pd.notna(rth_rng) else np.nan
                for k in range(K):
                    run_hi = nb["H"][:k + 1].max(); run_lo = nb["L"][:k + 1].min()
                    stop, target = (run_lo, run_hi) if side == "long" else (run_hi, run_lo)
                    r = race(nb, k, side, stop, target, horizon)
                    A["tgt"][i, k] = r["outcome"] == "target"; A["stp"][i, k] = r["outcome"] == "stop"
                    A["tgt_next_bar"][i, k] = (r["outcome"] == "target") and (r["exit_k"] == k + 1)
                    A["tgt_near"][i, k] = r["dist_target_bp"] <= NEAR_TARGET_BP
                    A["mfe"][i, k] = r["mfe"]; A["mae"][i, k] = r["mae"]
                    A["pnl_h"][i, k] = r["pnl_horizon"]; A["pnl_x"][i, k] = r["pnl_exit"]
                    A["d_stop"][i, k] = r["dist_stop_bp"]; A["d_tgt"][i, k] = r["dist_target_bp"]
                    for name, dist in (("tight_med", tight_med), ("tight_rth", tight_rth)):
                        if pd.notna(dist):
                            ts = (run_lo - dist) if side == "long" else (run_hi + dist)
                            rt = race(nb, k, side, ts, target, horizon)
                            A[name][i, k] = rt["outcome"] == "stop"; A[f"pnl_{name}"][i, k] = rt["pnl_exit"]
            n_ok = int(ok.sum())
            f = fired & ok[:, None]
            allm = ok[:, None] & np.ones_like(fired)

            def prop(arr, mask, ci_kind):
                """Rate of a 0/1 array over the masked entries (NaN entries dropped) with its CI and n."""
                m = mask & np.isfinite(arr); x = arr[m]
                if len(x) == 0:
                    return np.nan, (np.nan, np.nan), 0
                ci = wilson(x.sum(), len(x)) if ci_kind == "wilson" else session_boot_ci(x, np.where(m)[0])
                return float(x.mean()), ci, int(len(x))

            def mean_ci(arr, mask):
                """Mean of a continuous array over the masked entries with a session-bootstrap CI."""
                m = mask & np.isfinite(arr); x = arr[m]
                if len(x) == 0:
                    return np.nan, (np.nan, np.nan)
                return float(x.mean()), session_boot_ci(x, np.where(m)[0])

            def summarise(mask, population, ci_kind):
                n = int(mask.sum())
                p_t, ct, _ = prop(A["tgt"], mask, ci_kind); p_s, cs, _ = prop(A["stp"], mask, ci_kind)
                p_nb, cnb, _ = prop(A["tgt_next_bar"], mask, ci_kind); p_near, cnear, _ = prop(A["tgt_near"], mask, ci_kind)
                p_tm, ctm, n_tm = prop(A["tight_med"], mask, ci_kind); p_tr, ctr, n_tr = prop(A["tight_rth"], mask, ci_kind)
                px, cpx = mean_ci(A["pnl_x"], mask); ptm, cptm = mean_ci(A["pnl_tight_med"], mask); ptr, cptr = mean_ci(A["pnl_tight_rth"], mask)
                ph = A["pnl_h"][mask]; ph = ph[np.isfinite(ph)]
                sel = lambda name: A[name][mask]
                return dict(sym=sd.sym, signal=signal, population=population, horizon=hname, n=n,
                            n_sessions=int(mask.any(axis=1).sum()),
                            p_target_first=p_t, target_ci_lo=ct[0], target_ci_hi=ct[1],
                            p_stop_first=p_s, stop_ci_lo=cs[0], stop_ci_hi=cs[1],
                            p_neither=float(1 - p_t - p_s) if n else np.nan,
                            p_target_next_bar=p_nb, target_next_bar_ci_lo=cnb[0], target_next_bar_ci_hi=cnb[1],
                            share_target_within_2bp=p_near, target_within_2bp_ci_lo=cnear[0], target_within_2bp_ci_hi=cnear[1],
                            pnl_neither_median_bp=float(np.median(ph)) if len(ph) else np.nan,
                            pnl_neither_mean_bp=float(ph.mean()) if len(ph) else np.nan, n_neither=int(len(ph)),
                            pnl_exit_mean_bp=px, pnl_exit_ci_lo=cpx[0], pnl_exit_ci_hi=cpx[1],
                            mfe_median=qtiles(sel("mfe"), (0.5,))[0], mfe_p25=qtiles(sel("mfe"), (0.25,))[0], mfe_p75=qtiles(sel("mfe"), (0.75,))[0],
                            mae_median=qtiles(sel("mae"), (0.5,))[0], mae_p25=qtiles(sel("mae"), (0.25,))[0], mae_p75=qtiles(sel("mae"), (0.75,))[0],
                            tight_stop_first_rate=p_tm, n_tight=n_tm, tight_ci_lo=ctm[0], tight_ci_hi=ctm[1],
                            pnl_exit_tight_mean_bp=ptm, pnl_exit_tight_ci_lo=cptm[0], pnl_exit_tight_ci_hi=cptm[1],
                            rth_tight_stop_first_rate=p_tr, n_rth_tight=n_tr, rth_tight_ci_lo=ctr[0], rth_tight_ci_hi=ctr[1],
                            pnl_exit_rth_tight_mean_bp=ptr, pnl_exit_rth_tight_ci_lo=cptr[0], pnl_exit_rth_tight_ci_hi=cptr[1],
                            dist_stop_bp_median=qtiles(sel("d_stop"), (0.5,))[0], dist_target_bp_median=qtiles(sel("d_tgt"), (0.5,))[0],
                            n_sessions_excluded_horizon=int(S - n_ok))

            r_flag = summarise(f, "flagged (first firing, k<=6)", "wilson")
            r_unc = summarise(allm, "unconditional (every bar close k<=6)", "boot")
            # matched unconditional baselines: per-cell unconditional rates weighted by the firing cell distribution,
            # with a session bootstrap of the difference (conditional minus matched).
            # cells = k (the k-matched baseline of the specification) and k x quintile of the stop distance in
            # units of the 20-session median range (the flag fires when price has moved away from the running
            # extreme it protects, so the stop is far and the target is near: this baseline shows how much of the
            # conditional rates that geometry explains).
            kk = np.tile(np.arange(K), (S, 1))
            med = sd.ext.loc[dates, "med20_bp"].values[:, None]
            rel = A["d_stop"] / med
            edges = np.nanquantile(rel[allm], [0.2, 0.4, 0.6, 0.8])
            qcell = np.where(np.isfinite(rel), np.digitize(np.nan_to_num(rel, nan=0.0), edges), 0)
            n_f_k = f.sum(axis=0).astype(float)
            bins = dict(target=A["tgt"], stop=A["stp"], target_next_bar=A["tgt_next_bar"], target_near=A["tgt_near"],
                        tight=A["tight_med"], rth_tight=A["tight_rth"])
            for pop_name, cell, n_cells in (("k-matched unconditional (per-k rates weighted by firing k)", kk, K),
                                            ("k x stop-distance-matched unconditional (quintiles of stop distance / med20)",
                                             kk * 5 + qcell, 5 * K)):
                mt = matched_rates(cell, n_cells, f, allm, bins, A["d_stop"], A["d_tgt"], S)
                r_km = dict(sym=sd.sym, signal=signal, population=pop_name, horizon=hname, n=int(allm.sum()), n_sessions=n_ok,
                            p_target_first=mt["target"], target_ci_lo=mt["target_ci"][0], target_ci_hi=mt["target_ci"][1],
                            p_stop_first=mt["stop"], stop_ci_lo=mt["stop_ci"][0], stop_ci_hi=mt["stop_ci"][1],
                            p_neither=1 - mt["target"] - mt["stop"],
                            p_target_next_bar=mt["target_next_bar"], target_next_bar_ci_lo=mt["target_next_bar_ci"][0],
                            target_next_bar_ci_hi=mt["target_next_bar_ci"][1],
                            share_target_within_2bp=mt["target_near"], target_within_2bp_ci_lo=mt["target_near_ci"][0],
                            target_within_2bp_ci_hi=mt["target_near_ci"][1],
                            tight_stop_first_rate=mt["tight"], n_tight=int(np.isfinite(A["tight_med"][allm]).sum()),
                            tight_ci_lo=mt["tight_ci"][0], tight_ci_hi=mt["tight_ci"][1],
                            rth_tight_stop_first_rate=mt["rth_tight"], n_rth_tight=int(np.isfinite(A["tight_rth"][allm]).sum()),
                            rth_tight_ci_lo=mt["rth_tight_ci"][0], rth_tight_ci_hi=mt["rth_tight_ci"][1],
                            dist_stop_bp_median=mt["d_stop"], dist_target_bp_median=mt["d_tgt"],
                            n_sessions_excluded_horizon=int(S - n_ok))
                if cell is kk:
                    r_flag.update(diff_target_vs_kmatched=r_flag["p_target_first"] - mt["target"],
                                  diff_target_ci_lo=mt["diff_target_ci"][0], diff_target_ci_hi=mt["diff_target_ci"][1],
                                  diff_stop_vs_kmatched=r_flag["p_stop_first"] - mt["stop"],
                                  diff_stop_ci_lo=mt["diff_stop_ci"][0], diff_stop_ci_hi=mt["diff_stop_ci"][1],
                                  firing_k_weights=";".join(f"{int(k)}:{int(n_f_k[k])}" for k in range(K)))
                else:
                    r_flag.update(diff_target_vs_distmatched=r_flag["p_target_first"] - mt["target"],
                                  diff_target_dm_ci_lo=mt["diff_target_ci"][0], diff_target_dm_ci_hi=mt["diff_target_ci"][1],
                                  diff_stop_vs_distmatched=r_flag["p_stop_first"] - mt["stop"],
                                  diff_stop_dm_ci_lo=mt["diff_stop_ci"][0], diff_stop_dm_ci_hi=mt["diff_stop_ci"][1])
                rows.append(r_km)
            rows = rows[:-2] + [r_flag, r_unc] + rows[-2:]
            # per-k unconditional rates, for reference
            for k in range(K):
                m = np.zeros_like(allm); m[:, k] = allm[:, k]
                rk = summarise(m, f"unconditional k={k}", "wilson")
                rows.append(rk)
    return rows


# --------------------------------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------------------------------
def _ff_entry(ff: pd.DataFrame, cuts: pd.DataFrame, sym: str, flag: str) -> dict:
    r = ff[(ff["sym"] == sym) & (ff["flag"] == flag) & (ff["version"] == "cal")].iloc[0]
    c = cuts[(cuts["sym"] == sym) & (cuts["flag"] == flag) & (cuts["cut_name"] == "window") & (cuts["cut_value"] == "last12m")].iloc[0]
    return dict(n_first_firings=int(r["n_fired"]), n_sessions=int(r["n_sessions_population"]),
                share_sessions_firing=round(float(r["share_sessions_fired"]), 4),
                hit_rate=round(float(r["hit_rate"]), 4), ci90=[round(float(r["ci_lo"]), 4), round(float(r["ci_hi"]), 4)],
                kmatched_base=round(float(r["kmatched_base"]), 4), lift=round(float(r["lift"]), 4),
                median_first_k=float(r["median_first_k"]), median_first_close_time_et=str(r["median_first_close_time_et"]),
                overnight_hold_rate=(round(float(r["secondary_hit_rate"]), 4) if pd.notna(r["secondary_hit_rate"]) else None),
                n_overnight=int(r["n_secondary"]),
                n_fail=int(r["n_fail"]),
                fail_excess_above_running_extreme_bp_median=(round(float(r["fail_excess_run_med"]), 2) if pd.notna(r["fail_excess_run_med"]) else None),
                fail_excess_vs_close_bp_median=(round(float(r["fail_excess_close_med"]), 2) if pd.notna(r["fail_excess_close_med"]) else None),
                fail_bars_until_new_extreme_median=(float(r["fail_bars_until_med"]) if pd.notna(r["fail_bars_until_med"]) else None),
                last12m=dict(n=int(c["n_fired"]), hit_rate=(round(float(c["hit_rate"]), 4) if pd.notna(c["hit_rate"]) else None),
                             ci90=[round(float(c["ci_lo"]), 4), round(float(c["ci_hi"]), 4)] if pd.notna(c["ci_lo"]) else None,
                             base=(round(float(c["base_rate"]), 4) if pd.notna(c["base_rate"]) else None)))


def _pre_entry(calls: pd.DataFrame, cuts: pd.DataFrame, sym: str, call: str) -> dict:
    r = calls[(calls["sym"] == sym) & (calls["call"] == call) & (calls["version"] == "cal")].iloc[0]
    c = cuts[(cuts["sym"] == sym) & (cuts["flag"] == call) & (cuts["cut_name"] == "window") & (cuts["cut_value"] == "last12m")].iloc[0]
    return dict(n_called=int(r["n_called"]), n_nights=int(r["n_nights"]), share_called=round(float(r["share_called"]), 4),
                hit_rate=round(float(r["hit_rate"]), 4), ci90=[round(float(r["ci_lo"]), 4), round(float(r["ci_hi"]), 4)],
                base=round(float(r["base_rate"]), 4), lift=round(float(r["lift"]), 4),
                last12m=dict(n=int(c["n_fired"]), hit_rate=(round(float(c["hit_rate"]), 4) if pd.notna(c["hit_rate"]) else None),
                             ci90=[round(float(c["ci_lo"]), 4), round(float(c["ci_hi"]), 4)] if pd.notna(c["ci_lo"]) else None,
                             base=(round(float(c["base_rate"]), 4) if pd.notna(c["base_rate"]) else None)))


def build_summary(ff, cuts, calls, env, trade) -> dict:
    out = {}
    for sym in SYMS:
        s = {"first_firing": {}, "preasia": {}, "envelope_rng_bp": {}, "trade_translation": {}}
        for flag in HEADLINE_INTRA:
            s["first_firing"][flag] = _ff_entry(ff, cuts, sym, flag)
        for call in HEADLINE_PRE:
            s["preasia"][call] = _pre_entry(calls, cuts, sym, call)
        for window in ("full", "last12m"):
            e = env[(env["sym"] == sym) & (env["window"] == window) & (env["quantity"] == "rng_bp")]
            s["envelope_rng_bp"][window] = {
                src: dict(n=int(r["n"]), below_q20=round(float(r["share_below_q20"]), 4), inside=round(float(r["share_inside"]), 4),
                          above_q80=round(float(r["share_above_q80"]), 4), mae_q50_bp=round(float(r["mae_q50"]), 2))
                for src, r in ((r["source"], r) for _, r in e.iterrows())}
        for signal in ("LO_IN@0.90 long", "HI_IN@0.90 short"):
            s["trade_translation"][signal] = {}
            for hz in ("A_0200", "B_0800"):
                t = trade[(trade["sym"] == sym) & (trade["signal"] == signal) & (trade["horizon"] == hz)]
                fl = t[t["population"].str.startswith("flagged")].iloc[0]
                km = t[t["population"].str.startswith("k-matched")].iloc[0]
                un = t[t["population"].str.startswith("unconditional (every")].iloc[0]
                s["trade_translation"][signal][hz] = dict(
                    n_flagged=int(fl["n"]),
                    p_target_first=round(float(fl["p_target_first"]), 4), target_ci90=[round(float(fl["target_ci_lo"]), 4), round(float(fl["target_ci_hi"]), 4)],
                    p_stop_first=round(float(fl["p_stop_first"]), 4), stop_ci90=[round(float(fl["stop_ci_lo"]), 4), round(float(fl["stop_ci_hi"]), 4)],
                    kmatched_unconditional=dict(p_target_first=round(float(km["p_target_first"]), 4), p_stop_first=round(float(km["p_stop_first"]), 4)),
                    unconditional_all_k=dict(n=int(un["n"]), p_target_first=round(float(un["p_target_first"]), 4), p_stop_first=round(float(un["p_stop_first"]), 4)),
                    diff_target_vs_kmatched=round(float(fl["diff_target_vs_kmatched"]), 4),
                    diff_target_ci90=[round(float(fl["diff_target_ci_lo"]), 4), round(float(fl["diff_target_ci_hi"]), 4)],
                    diff_stop_vs_kmatched=round(float(fl["diff_stop_vs_kmatched"]), 4),
                    diff_stop_ci90=[round(float(fl["diff_stop_ci_lo"]), 4), round(float(fl["diff_stop_ci_hi"]), 4)],
                    pnl_exit_mean_bp=round(float(fl["pnl_exit_mean_bp"]), 2),
                    pnl_exit_ci90=[round(float(fl["pnl_exit_ci_lo"]), 2), round(float(fl["pnl_exit_ci_hi"]), 2)],
                    pnl_exit_mean_bp_unconditional=round(float(un["pnl_exit_mean_bp"]), 2),
                    p_target_next_bar_flagged=round(float(fl["p_target_next_bar"]), 4),
                    p_target_next_bar_kmatched=round(float(km["p_target_next_bar"]), 4),
                    share_target_within_2bp_flagged=round(float(fl["share_target_within_2bp"]), 4),
                    tight_stop_med20_first_flagged=round(float(fl["tight_stop_first_rate"]), 4),
                    tight_stop_med20_first_kmatched=round(float(km["tight_stop_first_rate"]), 4),
                    tight_stop_rth_first_flagged=round(float(fl["rth_tight_stop_first_rate"]), 4),
                    tight_stop_rth_first_kmatched=round(float(km["rth_tight_stop_first_rate"]), 4))
        out[sym] = s
    return out


# --------------------------------------------------------------------------------------------------
def main() -> int:
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    rl, ff, byk, fails, ovn, calls, env, joint, cuts, monthly, trade = ([] for _ in range(11))
    meta = {}
    for sym in SYMS:
        sd = SymData(sym)
        meta[sym] = sd.meta
        intra = evaluate_intra(sd)
        pre = evaluate_preasia(sd)
        c, m = stability(sd, intra, pre)
        tr = trade_table(sd, intra)
        rl += intra["rowlevel"]; ff += intra["first"]; byk += intra["byk"]; fails += intra["failures"]
        calls += pre["calls"]; env += pre["envelope"]; joint += pre["joint"]; cuts += c; monthly += m; trade += tr
        print(f"{sym}: {sd.oos['date'].nunique()} Detector A sessions, {len(sd.pre)} Detector B nights, "
              f"{len(sd.nights)} nights of raw bars ({time.time() - t0:.1f} s)")
    rl = pd.DataFrame(rl); ff = pd.DataFrame(ff); byk = pd.DataFrame(byk); fails = pd.DataFrame(fails)
    calls = pd.DataFrame(calls); env = pd.DataFrame(env); joint = pd.DataFrame(joint); cuts = pd.DataFrame(cuts)
    monthly = pd.DataFrame(monthly); trade = pd.DataFrame(trade)
    # overnight bridge: Asia-label flags against the overnight label and the dedicated overnight flags
    keep = [f["name"] for f in INTRA_FLAGS if f["family"] in ("IN", "OVN")]
    ovn_rows = []
    for pop_name, tab in (("row level", rl), ("first firing", ff)):
        t = tab[(tab["flag"].isin(keep)) & (tab["version"] == "cal")]
        for _, r in t.iterrows():
            fam = INTRA_BY_NAME[r["flag"]]["family"]
            ovn_rows.append(dict(sym=r["sym"], flag=r["flag"], population=pop_name,
                                 n=int(r["n_rows"] if pop_name == "row level" else r["n_fired"]),
                                 asia_label_hit_rate=(r["hit_rate"] if fam == "IN" else r["secondary_hit_rate"]),
                                 asia_label_kmatched_base=(r["kmatched_base"] if fam == "IN" else r["secondary_kmatched_base"]),
                                 overnight_label_hit_rate=(r["secondary_hit_rate"] if fam == "IN" else r["hit_rate"]),
                                 overnight_label_kmatched_base=(r["secondary_kmatched_base"] if fam == "IN" else r["kmatched_base"]),
                                 n_overnight_labelled=int(r["n_secondary"] if fam == "IN" else (r["n_rows"] if pop_name == "row level" else r["n_fired"])),
                                 ci_lo=r["ci_lo"], ci_hi=r["ci_hi"],
                                 ci_refers_to=("Asia label" if fam == "IN" else "overnight label")))
    ovn = pd.DataFrame(ovn_rows)
    summary = build_summary(ff, cuts, calls, env, trade)
    summary["_meta"] = dict(generated_from=["oos_intrasession_{NQ,ES}.csv", "oos_preasia_{NQ,ES}.csv", "{NQ,ES}_hourly_panel.csv",
                                            "{NQ,ES}_extremes.csv", "data/{NQ,ES}_1h.csv"],
                            windows=dict(last12m=[LAST12_START.strftime("%Y-%m-%d"), LAST12_END.strftime("%Y-%m-%d")],
                                         H2_start=H2_START.strftime("%Y-%m-%d")),
                            bootstrap=dict(draws=N_BOOT, seed=SEED), ci="90 % (Wilson for session-level, session-block bootstrap for row-level)",
                            populations=meta, runtime_s=round(time.time() - t0, 1))
    for name, tab in (("signals_rowlevel.csv", rl), ("signals_first_firing.csv", ff), ("first_firing_by_k.csv", byk),
                      ("failures.csv", fails), ("overnight_flags.csv", ovn), ("preasia_calls.csv", calls),
                      ("envelope_coverage.csv", env), ("joint_calls.csv", joint), ("stability_cuts.csv", cuts),
                      ("monthly.csv", monthly), ("trade_translation.csv", trade)):
        tab.to_csv(os.path.join(OUT, name), index=False, float_format="%.6g")
    with open(os.path.join(OUT, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1)

    # compact print
    print("\nfirst firing (calibrated), hit rate [90% CI] vs k-matched base, n fired / sessions, overnight hold:")
    for _, r in ff[ff["version"] == "cal"].iterrows():
        print(f"  {r['sym']} {r['flag']:<14} {r['hit_rate']:.3f} [{r['ci_lo']:.3f},{r['ci_hi']:.3f}] base {r['kmatched_base']:.3f} "
              f"n {int(r['n_fired']):>3}/{int(r['n_sessions_population'])} med k {r['median_first_k']:.1f} "
              f"ovn {r['secondary_hit_rate']:.3f} (n {int(r['n_secondary'])})")
    print("\npre-Asia calls (calibrated):")
    for _, r in calls[calls["version"] == "cal"].iterrows():
        print(f"  {r['sym']} {r['call']:<14} {r['hit_rate']:.3f} [{r['ci_lo']:.3f},{r['ci_hi']:.3f}] base {r['base_rate']:.3f} n {int(r['n_called']):>3}/{int(r['n_nights'])}")
    print("\ntrade translation (flagged vs k-matched unconditional): P(target first) / P(stop first)")
    for _, r in trade[trade["population"].str.startswith("flagged")].iterrows():
        km = trade[(trade["sym"] == r["sym"]) & (trade["signal"] == r["signal"]) & (trade["horizon"] == r["horizon"]) & trade["population"].str.startswith("k-matched")].iloc[0]
        print(f"  {r['sym']} {r['signal']:<16} {r['horizon']} n {int(r['n']):>3}: target {r['p_target_first']:.3f} vs {km['p_target_first']:.3f}, "
              f"stop {r['p_stop_first']:.3f} vs {km['p_stop_first']:.3f}")
    print(f"\nwrote {len(TABLES)} files to {OUT} in {time.time() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
