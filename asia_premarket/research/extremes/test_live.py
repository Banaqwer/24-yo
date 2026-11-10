"""
Standalone regression test for the live Asia high / low detectors (no pytest).

    cd research/extremes && python test_live.py

Checks (each prints PASS / FAIL with the values seen; exit status 1 on any failure):
  1  live_panel_row == stored hourly panel row on every feature column, from a truncated hourly frame
  2  live_extremes_row == stored extremes row on every column make_features() reads
  3  truncated hourly file: predict_now / predict_tonight succeed, k detection, parity with the stored path
  4  partial (in-progress) trailing bar is dropped; k beyond the latest complete bar raises
  5  today's night (the as-delivered data file): predict_tonight / predict_now succeed live
  6  DST regime of a night comes from its 18:00 timestamp (switch weekends)
  7  one splice list shared by both detector modules and applied by build_dataset / load_extremes
  8  overnight labels recomputed by hand from the raw hourly CSV
  9  --now CLI of both modules
 10  the default CLI still starts the walk-forward (no args / --help), without running it
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import asia_extremes as ae                               # noqa: E402
import detector_intrasession as di                       # noqa: E402
import detector_preasia as dp                            # noqa: E402
from sessions import ET, load_hourly                     # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []
TOL = 1e-6


def check(name: str, ok: bool, detail: str = ""):
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"\n       {detail}" if detail else ""), flush=True)


def guarded(name: str, fn):
    """Run fn(); an exception is a failure with the traceback's last line."""
    try:
        fn()
    except Exception as e:                               # noqa: BLE001
        tb = traceback.format_exc().strip().splitlines()[-1]
        check(name, False, f"raised {type(e).__name__}: {e}  ({tb})")


def max_abs_diff(a: pd.Series, b: pd.Series) -> tuple[float, list[str]]:
    """Max abs difference over the common columns (NaN == NaN); returns (worst, offending columns)."""
    worst, bad = 0.0, []
    for c in a.index:
        va, vb = a[c], b[c]
        if pd.isna(va) and pd.isna(vb):
            continue
        if pd.isna(va) != pd.isna(vb):
            bad.append(f"{c}: {va!r} vs {vb!r}"); worst = np.inf; continue
        try:
            d = abs(float(va) - float(vb))
        except (TypeError, ValueError):
            if va != vb:
                bad.append(f"{c}: {va!r} vs {vb!r}"); worst = np.inf
            continue
        if d > TOL:
            bad.append(f"{c}: {va!r} vs {vb!r} (diff {d:.3g})")
        worst = max(worst, d)
    return worst, bad


def ts_et(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz=ET)


H = {sym: load_hourly(os.path.join(ae.DATA, f"{sym}_1h.csv")) for sym in ("NQ", "ES")}
X = {sym: pd.read_csv(os.path.join(HERE, f"{sym}_extremes.csv"), index_col="date", parse_dates=True) for sym in ("NQ", "ES")}
P = {sym: pd.read_csv(os.path.join(HERE, f"{sym}_hourly_panel.csv"), parse_dates=["date"]) for sym in ("NQ", "ES")}

PANEL_FEATURE_COLS = [c for c in P["NQ"].columns
                      if c not in ae.PANEL_LABEL_COLS and c not in ae.PANEL_WHOLE_NIGHT_COLS and c != "date"]
REQUIRED_PANEL_COLS = ["k", "bars_since_hi", "bars_since_lo", "pos_in_range", "run_rng_vs_med20", "bar_close_loc",
                       "bar_ret_bp", "bar_rng_rel", "run_hi_above_rth_high", "run_lo_below_rth_low",
                       "run_hi_bp", "run_lo_bp", "cum_ret_bp", "bar_vol_rel", "dist_rth_high_bp", "dist_rth_low_bp"]
MAKE_FEATURES_COLS = ["ref_close", "asia_rng_med20", "lvl_rth_high", "lvl_rth_low", "is_down", "clv", "rth_ret", "vix",
                      "asia_rng_prev", "dist_20d_high", "rth_range_bp", "post_ret", "sunday_open", "dow", "fomc_tomorrow",
                      "fomc_today", "megacap_earnings_tonight", "holiday_tomorrow", "pre_holiday", "kospi_ret",
                      "is_dst", "tokyo_open_k"]


# ==================================================================================================
# 1  feature parity, panel
# ==================================================================================================
def check_1():
    assert all(c in PANEL_FEATURE_COLS for c in REQUIRED_PANEL_COLS), "panel column list out of sync"
    pairs = [  # (sym, RTH date, k, what it covers)
        ("NQ", "2026-01-15", 4, "EST night, k=4"),
        ("NQ", "2026-07-15", 0, "EDT night, k=0"),
        ("NQ", "2025-07-15", 7, "EDT night, k=7"),
        ("NQ", "2025-03-07", 7, "Friday -> Sunday reopen across the spring switch (EST Friday, EDT Sunday), k=7"),
        ("NQ", "2026-03-06", 2, "Friday -> Sunday reopen across the spring switch, k=2 (Tokyo open bar in EDT)"),
        ("NQ", "2026-10-30", 0, "Friday -> Sunday reopen across the autumn switch (EDT Friday, EST Sunday), k=0"),
        ("NQ", "2026-11-05", 7, "EST night, k=7"),
        ("ES", "2026-11-05", 4, "ES EST night, k=4"),
        ("ES", "2025-09-19", 1, "ES Friday -> Sunday reopen in EDT, k=1 (the bar before the EDT Tokyo open)"),
    ]
    for sym, date, k, what in pairs:
        name = f"1 panel parity {sym} {date} k={k} ({what})"
        try:
            stored = P[sym][(P[sym]["date"] == pd.Timestamp(date)) & (P[sym]["k"] == k)]
            if stored.empty:
                check(name, False, "no stored panel row"); continue
            stored = stored.iloc[0]
            # the bar's timestamp: the k-th Asia bar of the night in the full file
            g_full, _, gd = ae.night_bars(H[sym], date, asof=pd.Timestamp.max.tz_localize("UTC"))
            bar_ts = g_full.index[k]
            h_cut = H[sym][H[sym].index <= bar_ts]
            live = ae.live_panel_row(sym, date, k, h=h_cut, asof=bar_ts + pd.Timedelta(hours=1)).iloc[0]
            worst, bad = max_abs_diff(stored[PANEL_FEATURE_COLS], live[PANEL_FEATURE_COLS])
            extra = (f"bar_ts {bar_ts}, stored hour_et {int(stored['hour_et'])} is_dst {int(stored['is_dst'])} "
                     f"tokyo_open_k {int(stored['tokyo_open_k'])}; live latest_complete_k {live['latest_complete_k']} "
                     f"partial_bar_dropped {live['partial_bar_dropped']} n_bars_so_far {live['n_bars_so_far']}; "
                     f"{len(PANEL_FEATURE_COLS)} columns compared, max abs diff {worst:.3g}")
            ok = (not bad) and live["latest_complete_k"] == k and not live["partial_bar_dropped"] and live["n_bars_so_far"] == k + 1
            check(name, ok, extra + ("" if not bad else "; MISMATCH " + "; ".join(bad[:6])))
        except Exception as e:                           # noqa: BLE001
            check(name, False, f"raised {type(e).__name__}: {e}")


# ==================================================================================================
# 2  feature parity, pre-Asia
# ==================================================================================================
def check_2():
    from features import build_feature_table
    f_nq, s_nq = build_feature_table("NQ", "ES")
    dates = ["2026-10-30", "2026-07-15", "2025-03-07", "2026-01-15"]
    for date in dates:
        for mode in ("full h", "h cut at 17:00"):
            name = f"2 extremes parity NQ {date} ({mode})"
            try:
                stored = X["NQ"].loc[[pd.Timestamp(date)]]
                h = H["NQ"] if mode == "full h" else H["NQ"][H["NQ"].index <= ts_et(f"{date} 17:00")]
                live = ae.live_extremes_row("NQ", date, h=h, f=f_nq, s=s_nq)
                missing = [c for c in MAKE_FEATURES_COLS if c not in live.columns]
                if missing:
                    check(name, False, f"live row lacks {missing}"); continue
                worst, bad = max_abs_diff(stored.iloc[0][MAKE_FEATURES_COLS], live.iloc[0][MAKE_FEATURES_COLS])
                fs, fl = dp.make_features(stored).iloc[0], dp.make_features(live).iloc[0]
                worst_f, bad_f = max_abs_diff(fs, fl)
                extra = (f"is_dst {int(live['is_dst'].iloc[0])} tokyo_open_k {int(live['tokyo_open_k'].iloc[0])} "
                         f"asia_gdate {pd.Timestamp(live['asia_gdate'].iloc[0]).date()} ref_close {float(live['ref_close'].iloc[0]):.2f}; "
                         f"{len(MAKE_FEATURES_COLS)} input columns max diff {worst:.3g}; "
                         f"make_features {len(fs)} columns max diff {worst_f:.3g}")
                check(name, not bad and not bad_f, extra + ("" if not (bad or bad_f) else "; MISMATCH " + "; ".join((bad + bad_f)[:6])))
            except Exception as e:                       # noqa: BLE001
                check(name, False, f"raised {type(e).__name__}: {e}")


# ==================================================================================================
# 3  truncation
# ==================================================================================================
def _forced_live_tables(sym: str, date: pd.Timestamp):
    """Stored tables with every row on/after `date` removed (forces the live path for `date`)."""
    x, p = X[sym].copy(), P[sym].copy()
    return x[x.index < date], p[p["date"] < date]


def check_3():
    sym, date = "NQ", pd.Timestamp("2026-11-05")
    cuts = [("18:00", 0), ("20:00", 2), ("22:00", 4), ("23:00", 5)]
    stored_res, cut_res = {}, {}
    # the stored path for the same k (reference values)
    for _, k in cuts:
        try:
            stored_res[k] = di.predict_now(sym, date, k)
        except Exception as e:                           # noqa: BLE001
            check(f"3 stored-path predict_now {sym} {date.date()} k={k}", False, f"raised {type(e).__name__}: {e}")
    # as specified: truncated h passed in, k=None, asof = cut + 1h
    for cut, k_exp in cuts:
        name = f"3 truncation predict_now {sym} {date.date()} h cut at {cut}, asof {cut}+1h"
        try:
            cut_ts = ts_et(f"{date.date()} {cut}")
            h_cut = H[sym][H[sym].index <= cut_ts]
            r = di.predict_now(sym, date, None, asof=cut_ts + pd.Timedelta(hours=1), h=h_cut)
            cut_res[k_exp] = r
            ok_k = r["k"] == k_exp
            check(f"{name}: k == {k_exp}", ok_k, f"k={r['k']} latest_complete_k={r['latest_complete_k']} "
                  f"partial_bar_dropped={r['partial_bar_dropped']} bar_ts={r['bar_ts']} n_bars_so_far={r['n_bars_so_far']}")
            check(f"{name}: live == True", r["live"] is True,
                  f"live={r['live']} (the stored {sym}_hourly_panel.csv holds {date.date()}, and _feature_row prefers a "
                  f"stored row whenever one exists; the h passed in only drives the complete-bar guard here)")
            if k_exp in stored_res:
                s = stored_res[k_exp]
                d_hi = abs(r["p_high_done"] - s["p_high_done"]); d_lo = abs(r["p_low_done"] - s["p_low_done"])
                check(f"{name}: p_high/low_done == stored path (<= 1e-9)", d_hi <= 1e-9 and d_lo <= 1e-9,
                      f"cut p_high_done={r['p_high_done']:.6f} p_low_done={r['p_low_done']:.6f}; "
                      f"stored p_high_done={s['p_high_done']:.6f} p_low_done={s['p_low_done']:.6f}; diffs {d_hi:.2e} / {d_lo:.2e}")
        except Exception as e:                           # noqa: BLE001
            check(name, False, f"raised {type(e).__name__}: {e}")
    # forced live path: the stored tables without this date, same models (bundle cached per (sym, date)),
    # so the probabilities must reproduce the stored path if the live features match
    orig = di.load_tables
    try:
        di.load_tables = lambda s_, _d=date: _forced_live_tables(s_, _d)
        for cut, k_exp in cuts:
            name = f"3 FORCED-LIVE predict_now {sym} {date.date()} h cut at {cut} (tables withheld)"
            try:
                cut_ts = ts_et(f"{date.date()} {cut}")
                h_cut = H[sym][H[sym].index <= cut_ts]
                r = di.predict_now(sym, date, None, asof=cut_ts + pd.Timedelta(hours=1), h=h_cut)
                s = stored_res.get(k_exp)
                if s is None:
                    check(name, False, "no stored reference"); continue
                d_hi = abs(r["p_high_done"] - s["p_high_done"]); d_lo = abs(r["p_low_done"] - s["p_low_done"])
                d_ov = max(abs(r["p_ovn_high_done"] - s["p_ovn_high_done"]), abs(r["p_ovn_low_done"] - s["p_ovn_low_done"]))
                fdiff = max(abs((r["features"][f] if r["features"][f] is not None else np.nan) -
                                (s["features"][f] if s["features"][f] is not None else np.nan))
                            if not (r["features"][f] is None and s["features"][f] is None) else 0.0 for f in di.FEATURES)
                ok = r["k"] == k_exp and r["live"] is True and d_hi <= 1e-9 and d_lo <= 1e-9 and d_ov <= 1e-9
                check(name, ok, f"k={r['k']} live={r['live']} latest_complete_k={r['latest_complete_k']} "
                      f"p_high_done={r['p_high_done']:.6f} (stored {s['p_high_done']:.6f}, diff {d_hi:.2e}) "
                      f"p_low_done={r['p_low_done']:.6f} (stored {s['p_low_done']:.6f}, diff {d_lo:.2e}) "
                      f"ovn diff {d_ov:.2e}; max |feature diff| over the 20 detector features {fdiff:.3g}")
            except Exception as e:                       # noqa: BLE001
                check(name, False, f"raised {type(e).__name__}: {e}")
    finally:
        di.load_tables = orig

    # predict_tonight with h cut at 17:00
    name = f"3 truncation predict_tonight {sym} {date.date()} h cut at 17:00"
    try:
        h17 = H[sym][H[sym].index <= ts_et(f"{date.date()} 17:00")]
        r_stored = dp.predict_tonight(sym, date)
        r_cut = dp.predict_tonight(sym, date, h=h17)
        check(f"{name}: succeeds, live == True", r_cut["live"] is True,
              f"live={r_cut['live']} (stored {sym}_extremes.csv holds {date.date()}; predict_tonight uses the stored row "
              f"whenever the date is in the table, so h is unused on this path)")
        same_feat = r_cut["features"] == r_stored["features"]
        check(f"{name}: features == stored-row path", same_feat,
              f"{len(r_cut['features'])} features identical={same_feat}; ref_close {r_cut['ref_close_17h']}")
        orig_le = dp.load_extremes

        def _le(s_, full_only=True, _d=date):
            x = orig_le(s_, full_only)
            return x[x.index < _d]
        try:
            dp.load_extremes = _le
            dp._OOS_CACHE.clear()
            r_live = dp.predict_tonight(sym, date, h=h17)
        finally:
            dp.load_extremes = orig_le
        fdiffs = {k: abs((v if v is not None else np.nan) - (r_stored["features"][k] if r_stored["features"][k] is not None else np.nan))
                  for k, v in r_live["features"].items() if not (v is None and r_stored["features"][k] is None)}
        worst_f = max(fdiffs.values()) if fdiffs else 0.0
        pdiff = max(abs(r_live["probabilities"][t]["p_cal"] - r_stored["probabilities"][t]["p_cal"]) for t in dp.BINARY_TARGETS)
        qdiff = max(abs(r_live["quantiles_bp"][t][q] - r_stored["quantiles_bp"][t][q]) for t in dp.QUANT_TARGETS for q in ("P20", "P50", "P80"))
        ok = (r_live["live"] is True and worst_f <= TOL and pdiff <= 1e-6 and qdiff <= 0.11
              and r_live["is_dst"] == r_stored["is_dst"] and r_live["tokyo_open_k"] == r_stored["tokyo_open_k"]
              and r_live["n_train"] == r_stored["n_train"])
        check(f"3 FORCED-LIVE predict_tonight {sym} {date.date()} h cut at 17:00 (table withheld) == stored-row path", ok,
              f"live={r_live['live']} n_train {r_live['n_train']} vs {r_stored['n_train']}; is_dst {r_live['is_dst']}/{r_stored['is_dst']} "
              f"tokyo_open_k {r_live['tokyo_open_k']}/{r_stored['tokyo_open_k']}; max |feature diff| {worst_f:.3g} "
              f"(features rounded to 4 dp by predict_tonight); max |p_cal diff| over 9 targets {pdiff:.2e}; "
              f"max |quantile diff| (bp, rounded to 0.1) {qdiff:.3g}; "
              f"p(high>RTH high) {r_live['probabilities']['high_above_rth_high']['p_cal']:.3f} vs {r_stored['probabilities']['high_above_rth_high']['p_cal']:.3f}")
    except Exception as e:                               # noqa: BLE001
        check(name, False, f"raised {type(e).__name__}: {e}")


# ==================================================================================================
# 4  partial bar
# ==================================================================================================
def check_4():
    sym, date = "NQ", "2026-11-09"
    tail = H[sym].index[-3:]
    print(f"       (as-delivered {sym} file ends with bars {[str(t) for t in tail]})")
    name = f"4 partial bar: predict_now {sym} {date} asof 19:35"
    try:
        r = di.predict_now(sym, date, asof=f"{date} 19:35")
        ok = r["latest_complete_k"] == 0 and r["partial_bar_dropped"] is True and r["k"] == 0
        check(name, ok, f"k={r['k']} latest_complete_k={r['latest_complete_k']} partial_bar_dropped={r['partial_bar_dropped']} "
              f"bar_ts={r['bar_ts']} live={r['live']} p_high_done={r['p_high_done']:.3f} p_low_done={r['p_low_done']:.3f} "
              f"p_ovn_high_done={r['p_ovn_high_done']:.3f} p_ovn_low_done={r['p_ovn_low_done']:.3f}")
    except Exception as e:                               # noqa: BLE001
        check(name, False, f"raised {type(e).__name__}: {e}")
    name = f"4 partial bar: predict_now {sym} {date} asof 20:05 -> k=1"
    try:
        r = di.predict_now(sym, date, asof=f"{date} 20:05")
        ok = r["k"] == 1 and r["latest_complete_k"] == 1 and r["partial_bar_dropped"] is False
        check(name, ok, f"k={r['k']} latest_complete_k={r['latest_complete_k']} partial_bar_dropped={r['partial_bar_dropped']} "
              f"bar_ts={r['bar_ts']} p_high_done={r['p_high_done']:.3f} p_low_done={r['p_low_done']:.3f}")
    except Exception as e:                               # noqa: BLE001
        check(name, False, f"raised {type(e).__name__}: {e}")
    name = f"4 partial bar: predict_now {sym} {date} k=1 asof 19:35 raises ValueError naming latest_complete_k"
    try:
        r = di.predict_now(sym, date, 1, asof=f"{date} 19:35")
        check(name, False, f"did not raise; returned k={r['k']} latest_complete_k={r['latest_complete_k']}")
    except ValueError as e:
        check(name, "latest_complete_k" in str(e), f"ValueError: {e}")
    except Exception as e:                               # noqa: BLE001
        check(name, False, f"raised {type(e).__name__} instead of ValueError: {e}")
    # the same guard on the stored path: a stored row must not be served when the bar is not complete
    name = "4 complete-bar guard on the stored path: predict_now NQ 2026-11-05 k=4 asof 2026-11-05 22:30 raises"
    try:
        r = di.predict_now("NQ", "2026-11-05", 4, asof="2026-11-05 22:30")
        check(name, False, f"did not raise (k={r['k']}, live={r['live']})")
    except ValueError as e:
        check(name, "latest_complete_k=3" in str(e), f"ValueError: {e}")
    except Exception as e:                               # noqa: BLE001
        check(name, False, f"raised {type(e).__name__}: {e}")


# ==================================================================================================
# 5  today
# ==================================================================================================
def check_5():
    for sym in ("NQ", "ES"):
        name = f"5 today: predict_tonight {sym} 2026-11-09 live"
        try:
            r = dp.predict_tonight(sym, "2026-11-09")
            pr = r["probabilities"]
            check(name, r["live"] is True and 0 <= pr["high_above_rth_high"]["p_cal"] <= 1,
                  f"live={r['live']} ref_close {r['ref_close_17h']} is_dst {r['is_dst']} tokyo_open_k {r['tokyo_open_k']} n_train {r['n_train']} "
                  f"p(high>RTH high)={pr['high_above_rth_high']['p_cal']:.3f} p(low<RTH low)={pr['low_below_rth_low']['p_cal']:.3f} "
                  f"rng P50={r['quantiles_bp']['rng_bp']['P50']} warning={r['short_session_warning']}")
        except Exception as e:                           # noqa: BLE001
            check(name, False, f"raised {type(e).__name__}: {e}")
        name = f"5 today: predict_now {sym} 2026-11-09 (default asof)"
        try:
            r = di.predict_now(sym, "2026-11-09")
            ok = r["live"] is True and all(0 <= r[c] <= 1 for c in ("p_high_done", "p_low_done", "p_ovn_high_done", "p_ovn_low_done"))
            check(name, ok, f"asof={r['asof'][:16]} k={r['k']} live={r['live']} latest_complete_k={r['latest_complete_k']} "
                  f"partial_bar_dropped={r['partial_bar_dropped']} bar_ts={r['bar_ts']} "
                  f"p_high_done={r['p_high_done']:.3f} p_low_done={r['p_low_done']:.3f} "
                  f"p_ovn_high_done={r['p_ovn_high_done']:.3f} p_ovn_low_done={r['p_ovn_low_done']:.3f} "
                  f"calibrated={r['calibrated']} ({r['calibration_sessions']} sessions) n_train={r['n_train_sessions']}")
        except Exception as e:                           # noqa: BLE001
            check(name, False, f"raised {type(e).__name__}: {e}")


# ==================================================================================================
# 6  DST switch
# ==================================================================================================
def check_6():
    cases = [("2026-10-30", 0, 1, "Friday before the autumn switch: Sunday 2026-11-01 reopen is EST"),
             ("2026-03-06", 1, 2, "Friday before the spring switch: Sunday 2026-03-08 reopen is EDT"),
             ("2025-10-31", 0, 1, "Friday before the autumn switch: Sunday 2025-11-02 reopen is EST")]
    from features import build_feature_table
    f_nq, s_nq = build_feature_table("NQ", "ES")
    for date, dst, tko, what in cases:
        name = f"6 DST predict_tonight NQ {date} ({what})"
        try:
            r = dp.predict_tonight("NQ", date)
            check(name, r["is_dst"] == dst and r["tokyo_open_k"] == tko,
                  f"is_dst={r['is_dst']} (expected {dst}) tokyo_open_k={r['tokyo_open_k']} (expected {tko}) live={r['live']}")
        except Exception as e:                           # noqa: BLE001
            check(name, False, f"raised {type(e).__name__}: {e}")
        # the live derivation with no night bars in the file (calendar rule) and with the night's bars
        name = f"6 DST live_extremes_row NQ {date} with h cut at 17:00 (no night bars: calendar rule)"
        try:
            h17 = H["NQ"][H["NQ"].index <= ts_et(f"{date} 17:00")]
            lr = ae.live_extremes_row("NQ", date, h=h17, f=f_nq, s=s_nq).iloc[0]
            ts0 = ae.night_start_ts(h17, date)
            check(name, int(lr["is_dst"]) == dst and int(lr["tokyo_open_k"]) == tko,
                  f"is_dst={int(lr['is_dst'])} tokyo_open_k={int(lr['tokyo_open_k'])} china_open_k={int(lr['china_open_k'])} "
                  f"night_start_ts={ts0} asia_gdate={pd.Timestamp(lr['asia_gdate']).date()}")
        except Exception as e:                           # noqa: BLE001
            check(name, False, f"raised {type(e).__name__}: {e}")
        # the stored Friday row itself vs the preceding Thursday (old regime) for contrast
        thu = pd.Timestamp(date) - pd.Timedelta(days=1)
        xs = X["NQ"]
        if thu in xs.index:
            print(f"       (stored: Thursday {thu.date()} is_dst={int(xs.loc[thu,'is_dst'])} tokyo_open_k={int(xs.loc[thu,'tokyo_open_k'])}; "
                  f"Friday {date} is_dst={int(xs.loc[date,'is_dst'])} tokyo_open_k={int(xs.loc[date,'tokyo_open_k'])})")


# ==================================================================================================
# 7  splice lists
# ==================================================================================================
def check_7():
    same_obj = di.SPLICE_SESSIONS is ae.SPLICE_SESSIONS and dp.SPLICE_SESSIONS is ae.SPLICE_SESSIONS
    equal = di.SPLICE_SESSIONS == ae.SPLICE_SESSIONS == dp.SPLICE_SESSIONS and di.SPLICE_DATES is di.SPLICE_SESSIONS
    check("7 splice: one list shared (same object) by asia_extremes / detector_intrasession / detector_preasia",
          same_obj and equal, f"same object={same_obj} equal={equal}; NQ={ae.SPLICE_SESSIONS['NQ']} ES={ae.SPLICE_SESSIONS['ES']}")
    for sym in ("NQ", "ES"):
        sp = pd.to_datetime(ae.SPLICE_SESSIONS[sym])
        in_x = [str(d.date()) for d in sp if d in X[sym].index]
        in_p = [str(d.date()) for d in sp if (P[sym]["date"] == d).any()]
        d = di.build_dataset(sym)
        d_all = di.build_dataset(sym, full_sessions_only=False)
        xl = dp.load_extremes(sym, full_only=False)
        xf = dp.load_extremes(sym)
        left_d = sorted({str(t.date()) for t in d["date"] if t in set(sp)} | {str(t.date()) for t in d_all["date"] if t in set(sp)})
        left_x = sorted({str(t.date()) for t in xl.index if t in set(sp)} | {str(t.date()) for t in xf.index if t in set(sp)})
        check(f"7 splice: {sym} build_dataset / load_extremes drop the splice dates", not left_d and not left_x and len(in_x) > 0,
              f"splice dates present in the stored extremes table: {in_x}; in the panel: {in_p}; left after build_dataset: {left_d}; "
              f"left after load_extremes: {left_x}; build_dataset {d['date'].nunique()} full sessions / {len(d)} rows "
              f"(k<= {di.OVN_MAX_K}); load_extremes full-only {len(xf)} rows")


# ==================================================================================================
# 8  overnight labels by hand
# ==================================================================================================
def _raw_et(sym: str) -> pd.DataFrame:
    """The raw hourly CSV read independently of sessions.load_hourly (same tz handling)."""
    d = pd.read_csv(os.path.join(ae.DATA, f"{sym}_1h.csv"), index_col=0)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(ET)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d[d.index.minute == 0]


def _hand_overnight(raw: pd.DataFrame, gd: pd.Timestamp):
    """Asia bars (18:00 gd-1 .. 02:59 gd), Europe bars (03:00 .. 08:59 gd), overnight extremes."""
    start = pd.Timestamp(f"{(gd - pd.Timedelta(days=1)).date()} 18:00", tz=ET)
    end_asia = pd.Timestamp(f"{gd.date()} 02:59", tz=ET)
    end_eur = pd.Timestamp(f"{gd.date()} 08:59", tz=ET)
    asia = raw[(raw.index >= start) & (raw.index <= end_asia)]
    eur = raw[(raw.index > end_asia) & (raw.index <= end_eur)]
    win = raw[(raw.index >= start) & (raw.index <= end_eur)]
    return asia, eur, float(win["High"].max()), float(win["Low"].min())


def check_8():
    sym = "NQ"
    raw = _raw_et(sym)
    xs, ps = X[sym], P[sym]
    nights = [("2026-10-27", "bar-8 high (hi_k=8)"), ("2026-11-05", "bar-0 low (lo_k=0)"), ("2026-10-30", "Sunday reopen (Friday RTH date)")]
    for date, what in nights:
        name = f"8 overnight labels by hand {sym} {date} ({what})"
        try:
            xr = xs.loc[pd.Timestamp(date)]
            gd = pd.Timestamp(xr["asia_gdate"])
            asia, eur, ovn_hi, ovn_lo = _hand_overnight(raw, gd)
            ref = float(xr["ref_close"])
            got = []
            ok = len(eur) == 6 and len(asia) == 9
            ok &= abs((ovn_hi / ref - 1) * 1e4 - xr["ovn_high_bp"]) <= 1e-6 and abs((ovn_lo / ref - 1) * 1e4 - xr["ovn_low_bp"]) <= 1e-6
            e_above = int(float(eur["High"].max()) > float(asia["High"].max())); e_below = int(float(eur["Low"].min()) < float(asia["Low"].min()))
            ok &= e_above == int(xr["europe_above_asia_high"]) and e_below == int(xr["europe_below_asia_low"])
            for k in (0, 4, 8):
                run_hi = float(asia["High"].iloc[:k + 1].max()); run_lo = float(asia["Low"].iloc[:k + 1].min())
                hand_hi = int(run_hi >= ovn_hi); hand_lo = int(run_lo <= ovn_lo)
                pr = ps[(ps["date"] == pd.Timestamp(date)) & (ps["k"] == k)].iloc[0]
                got.append(f"k={k}: hand ovn_high_done={hand_hi}/panel={int(pr['overnight_high_done'])} "
                           f"hand ovn_low_done={hand_lo}/panel={int(pr['overnight_low_done'])} "
                           f"(session high_done={int(pr['high_done'])} low_done={int(pr['low_done'])})")
                ok &= hand_hi == int(pr["overnight_high_done"]) and hand_lo == int(pr["overnight_low_done"])
            check(name, ok, f"gdate {gd.date()} hi_k={int(xr['hi_k'])} lo_k={int(xr['lo_k'])} asia bars {len(asia)} europe bars {len(eur)} "
                  f"first bar {asia.index[0]}; ovn_hi {ovn_hi} (asia hi {float(asia['High'].max())}) ovn_lo {ovn_lo} (asia lo {float(asia['Low'].min())}); "
                  f"europe_above_asia_high hand {e_above}/stored {int(xr['europe_above_asia_high'])}, "
                  f"europe_below_asia_low hand {e_below}/stored {int(xr['europe_below_asia_low'])}; " + "; ".join(got))
        except Exception as e:                           # noqa: BLE001
            check(name, False, f"raised {type(e).__name__}: {e}")
    # the last night in the panel: NaN iff its 6 Europe bars are missing from the file
    name = f"8 overnight labels: last night in the {sym} panel is NaN iff its Europe bars are missing"
    try:
        last = ps["date"].max()
        gd = pd.Timestamp(xs.loc[last, "asia_gdate"])
        asia, eur, _, _ = _hand_overnight(raw, gd)
        rows = ps[ps["date"] == last]
        is_nan = rows["overnight_high_done"].isna().all() and rows["overnight_low_done"].isna().all()
        expected_nan = len(eur) < 6
        check(name, is_nan == expected_nan,
              f"last panel night = RTH date {last.date()} (gdate {gd.date()}): {len(eur)} Europe bars in the file "
              f"(file ends {raw.index[-1]}), overnight labels NaN={is_nan}, expected NaN={expected_nan}")
        # force the no-Europe-bars case: rebuild the panel from the file cut at 02:00 of that night
        h_cut = H[sym][H[sym].index <= pd.Timestamp(f"{gd.date()} 02:00", tz=ET)]
        p_cut = ae.hourly_panel(sym, h=h_cut)
        rows_cut = p_cut[p_cut["date"] == last]
        nan_cut = rows_cut["overnight_high_done"].isna().all() and rows_cut["overnight_low_done"].isna().all()
        other = p_cut[p_cut["date"] < last]
        m = other.merge(ps, on=["date", "k"], suffixes=("_cut", "_full"))
        same = ((m["overnight_high_done_cut"] == m["overnight_high_done_full"]) | (m["overnight_high_done_cut"].isna() & m["overnight_high_done_full"].isna())).all()
        check(f"8 overnight labels: panel rebuilt from the file cut at {gd.date()} 02:00 -> last night NaN, earlier nights unchanged",
              nan_cut and len(rows_cut) == 9 and same,
              f"last night rows {len(rows_cut)}, overnight labels all NaN={nan_cut}, session labels high_done={rows_cut['high_done'].tolist()}; "
              f"{len(m)} earlier rows overnight_high_done identical={same}")
    except Exception as e:                               # noqa: BLE001
        check(name, False, f"raised {type(e).__name__}: {e}")
    # every NaN night in the stored table has < 6 Europe bars, every non-NaN night has 6
    name = f"8 overnight labels: NaN pattern of the stored {sym} extremes table matches the Europe-bar count"
    try:
        bad = []
        for d, r in xs.iterrows():
            _, eur, _, _ = _hand_overnight(raw, pd.Timestamp(r["asia_gdate"]))
            if (len(eur) >= 6) == pd.isna(r["ovn_high_bp"]):
                bad.append(f"{d.date()} (europe bars {len(eur)}, ovn_high_bp {r['ovn_high_bp']})")
        n_nan = int(xs["ovn_high_bp"].isna().sum())
        check(name, not bad, f"{len(xs)} nights, {n_nan} NaN; mismatches: {bad[:5]}")
    except Exception as e:                               # noqa: BLE001
        check(name, False, f"raised {type(e).__name__}: {e}")


# ==================================================================================================
# 9  CLI
# ==================================================================================================
def _run(args: list[str], timeout: int = 900) -> tuple[int, str, str, float]:
    t0 = time.time()
    r = subprocess.run([sys.executable] + args, cwd=HERE, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr, time.time() - t0


def check_9():
    rc, out, err, dt = _run(["detector_intrasession.py", "--now", "NQ"])
    has_p = ("session  high in: p=" in out) and ("overnight high in" in out) and ("session  low  in: p=" in out)
    first = out.strip().splitlines()[:2] if out.strip() else [err.strip().splitlines()[-1] if err.strip() else ""]
    check("9 CLI: python detector_intrasession.py --now NQ exits 0 and prints probabilities", rc == 0 and has_p,
          f"rc={rc} ({dt:.0f}s) probabilities printed={has_p}; " + " | ".join(first))
    rc, out, err, dt = _run(["detector_preasia.py", "--now", "NQ"])
    has_p = ("high_above_rth_high" in out) and ("probabilities" in out) and ("quantiles" in out)
    first = out.strip().splitlines()[:2] if out.strip() else [err.strip().splitlines()[-1] if err.strip() else ""]
    check("9 CLI: python detector_preasia.py --now NQ exits 0 and prints probabilities", rc == 0 and has_p,
          f"rc={rc} ({dt:.0f}s) probabilities printed={has_p}; " + " | ".join(first))


# ==================================================================================================
# 10  default CLI still starts the walk-forward (without running it)
# ==================================================================================================
def check_10():
    for mod, fname in ((di, "detector_intrasession.py"), (dp, "detector_preasia.py")):
        rc, out, err, _ = _run([fname, "--help"], timeout=120)
        ok_help = rc == 0 and "walk-forward" in out and "--now" in out
        check(f"10 CLI: {fname} --help describes the default walk-forward re-run and --now", ok_help,
              f"rc={rc}; " + " ".join(out.split())[:220])
        called = []
        orig = mod.train_walk_forward

        def _stub(sym="NQ", verbose=True, *a, **kw):
            called.append(sym)
            raise RuntimeError("stub: walk-forward would start here")
        try:
            mod.train_walk_forward = _stub
            try:
                mod._cli([])
            except RuntimeError as e:
                if "stub" not in str(e):
                    raise
        finally:
            mod.train_walk_forward = orig
        check(f"10 CLI: {fname} with no args calls train_walk_forward (first symbol NQ)", called == ["NQ"],
              f"train_walk_forward called with {called}")


# ==================================================================================================
if __name__ == "__main__":
    t_all = time.time()
    for fn in (check_1, check_2, check_3, check_4, check_5, check_6, check_7, check_8, check_9, check_10):
        t0 = time.time()
        print(f"\n=== {fn.__name__} ===", flush=True)
        guarded(fn.__name__, fn)
        print(f"    ({time.time() - t0:.0f}s)", flush=True)
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n{'=' * 100}\n{len(RESULTS) - n_fail} passed, {n_fail} failed  ({time.time() - t_all:.0f}s)")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED: {name}\n          {detail}")
    sys.exit(1 if n_fail else 0)
