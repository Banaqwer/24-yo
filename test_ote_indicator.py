"""
Tests for ote_indicator.py

Run:  python test_ote_indicator.py
(or:  python -m pytest test_ote_indicator.py -q)

Covers
  * fib level arithmetic for longs and shorts
  * a textbook bullish OTE (sweep -> displacement/BOS -> pullback to 0.705 -> expansion)
    is detected, tapped, entered and closed at the -0.27 target
  * the mirrored bearish setup
  * a "trap" (pullback runs straight through the leg origin) is invalidated, not traded
  * no look-ahead: results on a truncated series equal the prefix of the full-series results
  * HTF bias filter removes counter-trend legs
"""

import numpy as np
import pandas as pd

from ote_indicator import OTEConfig, Setup, compute_ote, level_column, pivots


def make_bars(path, noise=0.0, seed=0, freq="15min", start="2026-01-05 09:30"):
    """Build OHLC bars that follow a piece-wise linear price path (one bar per point)."""
    rng = np.random.default_rng(seed)
    path = np.asarray(path, dtype=float)
    n = len(path)
    close = path
    open_ = np.r_[path[0], path[:-1]]
    hi = np.maximum(open_, close) + np.abs(rng.normal(0, noise, n)) + 0.05
    lo = np.minimum(open_, close) - np.abs(rng.normal(0, noise, n)) - 0.05
    idx = pd.date_range(start, periods=n, freq=freq, tz="America/New_York")
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close}, index=idx)


def segment(a, b, n):
    return np.linspace(a, b, n, endpoint=False)


def bullish_path():
    # choppy base -> lower low (sweep) -> impulsive rally that breaks the base high (BOS)
    # -> pullback into 0.62-0.79 -> consolidation -> expansion past -0.27
    p = []
    p += list(segment(100, 103, 8)) + list(segment(103, 100.5, 8)) + list(segment(100.5, 102.5, 8))
    p += list(segment(102.5, 98.0, 10))            # sweep of the base lows, origin ~98
    p += list(segment(98.0, 110.0, 12))            # impulsive leg 98 -> 110 (breaks 103 high)
    p += list(segment(110.0, 108.5, 6))            # small pause so the pivot high confirms
    p += list(segment(108.5, 101.6, 10))           # pullback to ~0.70 of the leg (110 - 12*0.7 = 101.6)
    p += [101.7, 101.9, 101.8, 102.0, 102.1]       # consolidation in the zone
    p += list(segment(102.1, 114.5, 14))           # expansion beyond -0.27 (113.24)
    p += list(segment(114.5, 113.0, 8))
    return np.array(p)


def test_level_math():
    cfg = OTEConfig()
    assert abs(cfg.level(100.0, 110.0, 0.62) - 103.8) < 1e-9
    assert abs(cfg.level(100.0, 110.0, 0.705) - 102.95) < 1e-9
    assert abs(cfg.level(100.0, 110.0, 0.79) - 102.1) < 1e-9
    assert abs(cfg.level(100.0, 110.0, 1.0) - 100.0) < 1e-9
    assert abs(cfg.level(100.0, 110.0, -0.27) - 112.7) < 1e-9
    # short leg: origin above, extreme below
    assert abs(cfg.level(110.0, 100.0, 0.705) - 107.05) < 1e-9
    assert abs(cfg.level(110.0, 100.0, -1.0) - 90.0) < 1e-9
    assert level_column(0.0) == "lv_0" and level_column(0.5) == "lv_50"
    assert level_column(0.62) == "lv_62" and level_column(0.705) == "lv_705" and level_column(1.0) == "lv_100"


def test_pivots_basic():
    h = np.array([1, 2, 3, 2, 1, 2, 5, 2, 1, 1, 1], dtype=float)
    l = h - 1
    ph, pl = pivots(h, l, 2)
    assert ph[2] and ph[6] and ph.sum() == 2
    assert pl[4] and pl.sum() >= 1


def _cfg(**kw):
    base = dict(swing_len=3, min_leg_atr=1.0, htf=None, bias_mode="none",
                confirm_mode="consolidation", confirm_bars=2, eval_tp_index=1, max_wait_bars=100)
    base.update(kw)
    return OTEConfig(**base)


def test_bullish_setup_detected_and_won():
    df = make_bars(bullish_path(), noise=0.05, seed=1)
    res = compute_ote(df, _cfg())
    longs = [s for s in res.setups if s.direction > 0]
    assert longs, "no bullish leg detected"
    s = longs[0]                               # the leg off the swept low
    assert 97 < s.origin_price < 99 and 109 < s.extreme_price < 111
    assert s.structure_break is True
    assert s.swept_liquidity is True
    assert s.tap_idx is not None, "zone was never tapped"
    assert s.entry_idx is not None, "no entry after consolidation"
    assert s.entry_idx > s.tap_idx
    assert s.levels["0.79"] - 0.3 <= s.entry_price <= s.levels["0.62"] + 0.8
    assert s.state == "win", s.state
    assert s.r_multiple > 1.0
    # per-bar columns are populated while the zone is active and the signal fires once
    f = res.frame
    assert (f["ote_signal"] == 1).sum() == 1
    assert f["ote_signal"].values[s.entry_idx] == 1
    assert f["lv_705"].notna().sum() > 5
    assert f["ote_state"].values[s.entry_idx] == "entered"


def test_bearish_mirror():
    path = 220.0 - bullish_path()          # mirror the whole path around 110
    df = make_bars(path, noise=0.05, seed=2)
    res = compute_ote(df, _cfg())
    shorts = [s for s in res.setups if s.direction < 0]
    assert shorts, "no bearish leg detected"
    s = shorts[0]
    assert s.origin_price > s.extreme_price
    assert 121 < s.origin_price < 123 and 109 < s.extreme_price < 111
    assert s.entry_idx is not None and s.state == "win"
    assert (res.frame["ote_signal"] == -1).sum() == 1


def test_trap_is_invalidated_not_traded():
    p = []
    p += list(segment(100, 103, 8)) + list(segment(103, 100.5, 8)) + list(segment(100.5, 102.5, 8))
    p += list(segment(102.5, 98.0, 10))
    p += list(segment(98.0, 110.0, 12))
    p += list(segment(110.0, 108.5, 6))
    p += list(segment(108.5, 96.0, 14))            # retrace straight through the origin
    p += list(segment(96.0, 97.0, 8))
    df = make_bars(np.array(p), noise=0.05, seed=3)
    res = compute_ote(df, _cfg())
    longs = [s for s in res.setups if s.direction > 0 and s.extreme_price > 109]
    assert longs
    s = longs[0]
    assert s.entry_idx is None
    assert s.state == "invalidated"
    assert (res.frame["ote_signal"] != 0).sum() == 0


def test_no_lookahead():
    df = make_bars(bullish_path(), noise=0.05, seed=1)
    full = compute_ote(df, _cfg()).frame
    for k in (40, 55, 62, 70, 85):
        part = compute_ote(df.iloc[:k], _cfg()).frame
        cols = ["ote_dir", "ote_state", "ote_signal", "lv_705", "ote_sl"]
        a = part[cols].reset_index(drop=True)
        b = full[cols].iloc[:k].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_htf_bias_filter():
    df = make_bars(bullish_path(), noise=0.05, seed=1)
    # force a bearish bias everywhere -> no longs allowed
    from ote_indicator import htf_bias_series
    import ote_indicator as oi

    orig = oi.htf_bias_series
    try:
        oi.htf_bias_series = lambda d, c: pd.Series(-1, index=d.index)
        res = compute_ote(df, _cfg(bias_mode="structure", htf="1h"))
        assert not [s for s in res.setups if s.direction > 0]
        oi.htf_bias_series = lambda d, c: pd.Series(1, index=d.index)
        res = compute_ote(df, _cfg(bias_mode="structure", htf="1h"))
        assert [s for s in res.setups if s.direction > 0]
    finally:
        oi.htf_bias_series = orig
    # the real HTF function also runs on tz-aware intraday data and only returns -1/0/1
    b = htf_bias_series(df, OTEConfig(htf="1h", bias_mode="structure", htf_swing_len=2))
    assert set(np.unique(b.values)) <= {-1, 0, 1}


def test_setups_frame_and_summary():
    df = make_bars(bullish_path(), noise=0.05, seed=1)
    res = compute_ote(df, _cfg())
    sf = res.setups_frame()
    assert {"direction", "state", "entry_time", "r_multiple"} <= set(sf.columns)
    summ = res.summary()
    assert summ["entries"] >= 1 and summ["wins"] >= 1


if __name__ == "__main__":
    import inspect
    import sys

    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and inspect.isfunction(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print("ALL PASSED" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
