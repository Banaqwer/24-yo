"""
ote_indicator.py - ICT "Optimal Trade Entry" (OTE) indicator
=============================================================

Replicates the OTE method taught in "How To Properly Use OTE (Optimal Trade
Entry)" by The Source (YouTube, Aug 2026) and in the original ICT material.

The on-screen checklist from the video (chapter "OTE trading checklist"):

    1. Confirm your HTF bias
    2. Mark out a proper OTE zone
    3. Wait patiently for market to reach the zone
    4. Wait for consolidation before entering
    5. Target expansions or scalps

Each step maps to a piece of this indicator:

    1. HTF bias        -> `bias_mode`  (higher-timeframe structure or premium/discount)
    2. Proper zone     -> an impulsive leg that breaks structure (BOS/MSS); the fib is
                          anchored wick-to-wick on that leg; 0.62-0.79 is the OTE zone,
                          0.705 is the sweet spot
    3. Wait for tap    -> zone is "armed" first, only becomes "tapped" when price trades
                          into it; stale zones expire or are superseded by a new high/low
    4. Consolidation   -> `confirm_mode`: "consolidation" (N bars with no new extreme),
                          "reclaim" (close back above/below the 0.62 level) or "touch"
    5. Targets         -> 0.0 (range extreme = scalp), -0.27 / -0.62 / -1.0 expansions

The code is pure pandas/numpy, has no look-ahead (every decision at bar t uses only
bars <= t; pivots are only used once they are confirmed `swing_len` bars later) and
exposes a per-bar DataFrame plus a list of Setup objects, so it can be dropped into the
existing scanners in this repo or plotted on its own.

Usage (CLI):
    python ote_indicator.py --symbol NQ=F --interval 15m --period 30d --htf 1h --plot
    python ote_indicator.py --csv my_bars.csv --htf 4h --confirm consolidation

Usage (library):
    from ote_indicator import OTEConfig, compute_ote
    res = compute_ote(df, OTEConfig(swing_len=5, htf="1h"))
    res.frame[["close", "ote_dir", "ote_state", "lv_705", "ote_signal"]].tail()
    res.summary()
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
@dataclass
class OTEConfig:
    # --- swing / leg detection -------------------------------------------
    swing_len: int = 5                 # pivot strength: bars on each side
    atr_len: int = 14
    min_leg_atr: float = 1.5           # leg range must be >= this many ATRs ("impulsive")
    require_structure_break: bool = True   # leg must take out the previous opposing pivot (BOS / MSS)
    require_sweep: bool = False        # leg origin must have swept the pivot before it (liquidity grab)

    # --- fib levels ---------------------------------------------------------
    zone_near: float = 0.62            # first OTE level (closest to the leg extreme)
    sweet_spot: float = 0.705
    zone_far: float = 0.79             # deepest OTE level
    sl_level: float = 1.0              # stop beyond the leg origin
    sl_buffer_atr: float = 0.10        # extra stop buffer, in ATRs
    tp_levels: Tuple[float, ...] = (0.0, -0.27, -0.62, -1.0)   # ICT fib targets

    # --- entry handling -----------------------------------------------------
    confirm_mode: str = "consolidation"   # "consolidation" | "reclaim" | "touch"
    confirm_bars: int = 2              # bars with no new extreme (consolidation mode)
    max_wait_bars: int = 80            # armed zone expires if never tapped within N bars
    max_hold_bars: int = 200           # evaluation only: force-close open trades after N bars
    eval_tp_index: int = 1             # which tp level is used to score wins (0 => range extreme)

    # --- HTF bias -----------------------------------------------------------
    htf: Optional[str] = "1h"          # pandas resample rule ("1h", "4h", "1D") or None
    bias_mode: str = "structure"       # "structure" | "range" | "none"
    htf_swing_len: int = 3
    htf_range_len: int = 20            # dealing-range length (bars) for bias_mode="range"

    # --- optional session filter (exchange local time, "HH:MM") -------------
    session: Optional[Tuple[str, str]] = None
    session_tz: str = "America/New_York"

    def level(self, origin: float, extreme: float, ratio: float) -> float:
        """Price of a fib ratio measured from the leg extreme back toward the origin.

        ratio 0.0 -> extreme, 1.0 -> origin, negative -> expansion beyond the extreme.
        """
        return extreme - (extreme - origin) * ratio


# ----------------------------------------------------------------------------
# Setup object
# ----------------------------------------------------------------------------
ACTIVE_STATES = ("armed", "tapped", "entered")
FINAL_STATES = ("win", "loss", "timeout", "expired", "superseded", "invalidated", "missed")


@dataclass
class Setup:
    direction: int                    # +1 long, -1 short
    origin_idx: int                   # bar index of the leg origin (swing low for a long)
    origin_price: float
    extreme_idx: int                  # bar index of the leg extreme (swing high for a long)
    extreme_price: float
    confirmed_idx: int                # bar at which the pivot (and therefore the leg) became known
    atr: float
    structure_break: bool
    swept_liquidity: bool
    levels: dict = field(default_factory=dict)
    sl: float = float("nan")
    tps: Tuple[float, ...] = ()
    state: str = "armed"
    tap_idx: Optional[int] = None
    entry_idx: Optional[int] = None
    entry_price: Optional[float] = None
    exit_idx: Optional[int] = None
    exit_price: Optional[float] = None
    r_multiple: Optional[float] = None
    _extreme_since_tap: Optional[float] = None
    _hold_count: int = 0

    @property
    def range(self) -> float:
        return abs(self.extreme_price - self.origin_price)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_extreme_since_tap", None)
        d.pop("_hold_count", None)
        d["levels"] = {k: round(v, 6) for k, v in self.levels.items()}
        return d


@dataclass
class OTEResult:
    frame: pd.DataFrame
    setups: List[Setup]
    config: OTEConfig

    def entries(self) -> List[Setup]:
        return [s for s in self.setups if s.entry_idx is not None]

    def active(self) -> List[Setup]:
        return [s for s in self.setups if s.state in ACTIVE_STATES]

    def summary(self) -> dict:
        ents = self.entries()
        wins = [s for s in ents if s.state == "win"]
        losses = [s for s in ents if s.state == "loss"]
        closed = [s for s in ents if s.r_multiple is not None]
        rs = [s.r_multiple for s in closed]
        out = {
            "setups_total": len(self.setups),
            "legs_rejected_or_expired": sum(s.state in ("expired", "superseded") for s in self.setups),
            "tapped": sum(s.tap_idx is not None for s in self.setups),
            "invalidated_before_entry": sum(s.state == "invalidated" for s in self.setups),
            "missed_no_confirmation": sum(s.state == "missed" for s in self.setups),
            "entries": len(ents),
            "wins": len(wins),
            "losses": len(losses),
            "timeouts": sum(s.state == "timeout" for s in ents),
            "open": sum(s.state == "entered" for s in ents),
            "win_rate": (len(wins) / (len(wins) + len(losses))) if (wins or losses) else float("nan"),
            "avg_r": float(np.mean(rs)) if rs else float("nan"),
            "total_r": float(np.sum(rs)) if rs else 0.0,
        }
        return out

    def setups_frame(self) -> pd.DataFrame:
        rows = []
        idx = self.frame.index
        for s in self.setups:
            d = s.to_dict()
            d["origin_time"] = idx[s.origin_idx]
            d["extreme_time"] = idx[s.extreme_idx]
            d["entry_time"] = idx[s.entry_idx] if s.entry_idx is not None else None
            d["exit_time"] = idx[s.exit_idx] if s.exit_idx is not None else None
            rows.append(d)
        return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def level_column(ratio: float) -> str:
    """Column name for a fib ratio: 0.0->lv_0, 0.5->lv_50, 0.62->lv_62, 0.705->lv_705, 1.0->lv_100."""
    pct = ratio * 100
    if abs(pct - round(pct)) < 1e-9:
        return f"lv_{int(round(pct))}"
    return f"lv_{int(round(ratio * 1000))}"


def _normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with lowercase open/high/low/close(/volume) columns, flattening
    yfinance's MultiIndex columns if present."""
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [c[0] for c in out.columns]
    out.columns = [str(c).lower() for c in out.columns]
    needed = {"open", "high", "low", "close"}
    missing = needed - set(out.columns)
    if missing:
        raise ValueError(f"OHLC columns missing: {sorted(missing)}")
    out = out.dropna(subset=["open", "high", "low", "close"])
    return out


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def pivots(high: np.ndarray, low: np.ndarray, n: int) -> Tuple[np.ndarray, np.ndarray]:
    """Boolean arrays marking pivot highs / lows with `n` bars on each side.

    A pivot high at i has high[i] >= every high in (i-n, i+n) and strictly greater than
    the highs to its right, so equal highs produce one pivot (the first one)."""
    N = len(high)
    ph = np.zeros(N, dtype=bool)
    pl = np.zeros(N, dtype=bool)
    for i in range(n, N - n):
        hl = high[i - n:i]
        hr = high[i + 1:i + n + 1]
        if high[i] >= hl.max() and high[i] > hr.max():
            ph[i] = True
        ll = low[i - n:i]
        lr = low[i + 1:i + n + 1]
        if low[i] <= ll.min() and low[i] < lr.min():
            pl[i] = True
    return ph, pl


def htf_bias_series(df: pd.DataFrame, cfg: OTEConfig) -> pd.Series:
    """+1 bullish / -1 bearish / 0 unknown per LTF bar, using only completed HTF bars."""
    if cfg.bias_mode == "none" or not cfg.htf:
        return pd.Series(0, index=df.index, dtype=int)
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("HTF bias needs a DatetimeIndex; set htf=None / bias_mode='none' otherwise")

    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    htf = df[["open", "high", "low", "close"]].resample(cfg.htf, label="left", closed="left").agg(agg).dropna()
    if len(htf) < 3:
        return pd.Series(0, index=df.index, dtype=int)

    bias = np.zeros(len(htf), dtype=int)
    if cfg.bias_mode == "structure":
        n = cfg.htf_swing_len
        ph, pl = pivots(htf["high"].values, htf["low"].values, n)
        last_ph = np.nan
        last_pl = np.nan
        cur = 0
        closes = htf["close"].values
        highs = htf["high"].values
        lows = htf["low"].values
        for k in range(len(htf)):
            # pivots become known n bars after they print
            j = k - n
            if j >= 0:
                if ph[j]:
                    last_ph = highs[j]
                if pl[j]:
                    last_pl = lows[j]
            if not np.isnan(last_ph) and closes[k] > last_ph:
                cur = 1
                last_ph = np.nan          # wait for a fresh pivot before re-triggering
            elif not np.isnan(last_pl) and closes[k] < last_pl:
                cur = -1
                last_pl = np.nan
            bias[k] = cur
    elif cfg.bias_mode == "range":
        hi = htf["high"].rolling(cfg.htf_range_len, min_periods=2).max()
        lo = htf["low"].rolling(cfg.htf_range_len, min_periods=2).min()
        mid = (hi + lo) / 2.0
        # discount (below equilibrium) -> look for longs; premium -> shorts
        bias = np.where(htf["close"] < mid, 1, np.where(htf["close"] > mid, -1, 0)).astype(int)
    else:
        raise ValueError(f"unknown bias_mode {cfg.bias_mode!r}")

    s = pd.Series(bias, index=htf.index)
    # a HTF bar's value is only usable once that bar has closed -> shift its timestamp forward
    s.index = s.index + pd.tseries.frequencies.to_offset(cfg.htf)
    out = s.reindex(df.index, method="ffill").fillna(0).astype(int)
    return out


def _in_session(ts: pd.Timestamp, cfg: OTEConfig) -> bool:
    if cfg.session is None:
        return True
    t = ts
    if t.tzinfo is not None:
        t = t.tz_convert(cfg.session_tz)
    start, end = cfg.session
    hhmm = t.strftime("%H:%M")
    return start <= hhmm <= end


# ----------------------------------------------------------------------------
# Core engine
# ----------------------------------------------------------------------------
def compute_ote(data: pd.DataFrame, cfg: Optional[OTEConfig] = None) -> OTEResult:
    cfg = cfg or OTEConfig()
    df = _normalize_ohlc(data)
    N = len(df)
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    atr_v = atr(df, cfg.atr_len).values
    ph, pl = pivots(h, l, cfg.swing_len)
    bias = htf_bias_series(df, cfg).values
    index = df.index
    n = cfg.swing_len

    setups: List[Setup] = []
    active_long: Optional[Setup] = None
    active_short: Optional[Setup] = None
    conf_ph: List[int] = []   # confirmed pivot highs (bar indices), in order
    conf_pl: List[int] = []

    # per-bar output arrays
    col_dir = np.zeros(N, dtype=int)
    col_state = np.array([""] * N, dtype=object)
    col_signal = np.zeros(N, dtype=int)
    lv_cols = {r: np.full(N, np.nan) for r in (0.0, 0.5, cfg.zone_near, cfg.sweet_spot, cfg.zone_far, 1.0)}
    col_sl = np.full(N, np.nan)
    col_tp = [np.full(N, np.nan) for _ in cfg.tp_levels]

    def build_setup(direction: int, origin_idx: int, extreme_idx: int, t: int,
                    broke: bool, swept: bool) -> Setup:
        origin = l[origin_idx] if direction > 0 else h[origin_idx]
        extreme = h[extreme_idx] if direction > 0 else l[extreme_idx]
        a = atr_v[extreme_idx] if not np.isnan(atr_v[extreme_idx]) else abs(extreme - origin) / 3.0
        levels = {}
        for r in (0.0, 0.5, cfg.zone_near, cfg.sweet_spot, cfg.zone_far, 1.0) + tuple(cfg.tp_levels):
            levels[f"{r:g}"] = cfg.level(origin, extreme, r)
        sl = cfg.level(origin, extreme, cfg.sl_level) - direction * cfg.sl_buffer_atr * a
        tps = tuple(cfg.level(origin, extreme, r) for r in cfg.tp_levels)
        return Setup(direction, origin_idx, origin, extreme_idx, extreme, t, a, broke, swept,
                     levels, sl, tps)

    def try_new_leg(direction: int, pivot_idx: int, t: int) -> Optional[Setup]:
        """A pivot high (long leg) or pivot low (short leg) was just confirmed at bar t."""
        prev_same = conf_ph if direction > 0 else conf_pl        # previous pivots of the same kind
        prev_same = [p for p in prev_same if p < pivot_idx]
        if not prev_same:
            return None
        prev_idx = prev_same[-1]
        # leg origin = the opposite extreme between the previous same-kind pivot and this one
        seg = slice(prev_idx, pivot_idx + 1)
        if direction > 0:
            origin_idx = prev_idx + int(np.argmin(l[seg]))
            extreme = h[pivot_idx]
            origin = l[origin_idx]
            broke = bool(np.max(c[origin_idx:pivot_idx + 1]) > h[prev_idx])
        else:
            origin_idx = prev_idx + int(np.argmax(h[seg]))
            extreme = l[pivot_idx]
            origin = h[origin_idx]
            broke = bool(np.min(c[origin_idx:pivot_idx + 1]) < l[prev_idx])
        if origin_idx == pivot_idx:
            return None
        rng = abs(extreme - origin)
        a = atr_v[pivot_idx]
        if np.isnan(a) or rng < cfg.min_leg_atr * a:
            return None
        if cfg.require_structure_break and not broke:
            return None
        # liquidity sweep: did the origin take out the pivot of the opposite kind before it?
        opp = conf_pl if direction > 0 else conf_ph
        opp_prev = [p for p in opp if p < origin_idx]
        if direction > 0:
            swept = bool(opp_prev and l[origin_idx] < l[opp_prev[-1]])
        else:
            swept = bool(opp_prev and h[origin_idx] > h[opp_prev[-1]])
        if cfg.require_sweep and not swept:
            return None
        if cfg.bias_mode != "none" and bias[t] != direction:
            return None
        s = build_setup(direction, origin_idx, pivot_idx, t, broke, swept)
        # Replay the bars between the pivot and its confirmation: their OHLC is already
        # known at bar t, so the zone may already be tapped (or invalidated / superseded).
        # Entries are not allowed before bar t (that would be a back-dated signal).
        for tt in range(pivot_idx + 1, t):
            s = step(s, tt, allow_entry=False)
            if s.state not in ACTIVE_STATES:
                return None
        return s

    def tp_price(s: Setup) -> float:
        k = min(cfg.eval_tp_index, len(s.tps) - 1)
        return s.tps[k]

    def step(s: Setup, t: int, allow_entry: bool = True) -> Setup:
        """Advance one active setup by bar t. Returns the (possibly finished) setup."""
        d = s.direction
        near = s.levels[f"{cfg.zone_near:g}"]
        sweet = s.levels[f"{cfg.sweet_spot:g}"]
        beyond_extreme = (h[t] > s.extreme_price) if d > 0 else (l[t] < s.extreme_price)
        hit_sl = (l[t] <= s.sl) if d > 0 else (h[t] >= s.sl)
        touched_zone = (l[t] <= near) if d > 0 else (h[t] >= near)
        touched_sweet = (l[t] <= sweet) if d > 0 else (h[t] >= sweet)

        if s.state == "armed":
            if beyond_extreme:
                s.state = "superseded"       # leg is extending; a new pivot will redraw the zone
                s.exit_idx = t
                return s
            if t - s.confirmed_idx > cfg.max_wait_bars:
                s.state = "expired"
                s.exit_idx = t
                return s
            if touched_zone:
                s.state = "tapped"
                s.tap_idx = t
                s._extreme_since_tap = l[t] if d > 0 else h[t]
                s._hold_count = 0
                if hit_sl:
                    s.state = "invalidated"  # straight through the zone and the origin: a trap
                    s.exit_idx = t
                    return s
                if cfg.confirm_mode == "touch" and allow_entry:
                    return enter(s, t, price=sweet if touched_sweet else near)
            return s

        if s.state == "tapped":
            if hit_sl:
                s.state = "invalidated"
                s.exit_idx = t
                return s
            if beyond_extreme:
                s.state = "missed"            # left the zone without giving a confirmation
                s.exit_idx = t
                return s
            if cfg.confirm_mode == "touch":
                if touched_sweet and allow_entry:
                    return enter(s, t, price=sweet)
                return s
            if cfg.confirm_mode == "reclaim":
                bullish = c[t] > o[t]
                ok = (d > 0 and c[t] > near and bullish) or (d < 0 and c[t] < near and not bullish)
                if ok and allow_entry:
                    return enter(s, t, price=c[t])
                return s
            if cfg.confirm_mode == "consolidation":
                ext = l[t] if d > 0 else h[t]
                made_new_extreme = (ext < s._extreme_since_tap) if d > 0 else (ext > s._extreme_since_tap)
                if made_new_extreme:
                    s._extreme_since_tap = ext
                    s._hold_count = 0
                else:
                    s._hold_count += 1
                if s._hold_count >= cfg.confirm_bars and allow_entry:
                    return enter(s, t, price=c[t])
                return s
            raise ValueError(f"unknown confirm_mode {cfg.confirm_mode!r}")

        if s.state == "entered":
            tp = tp_price(s)
            hit_tp = h[t] >= tp if d > 0 else l[t] <= tp
            risk = abs(s.entry_price - s.sl)
            if hit_sl and hit_tp:
                # ambiguous bar: assume the stop was hit first (conservative)
                hit_tp = False
            if hit_sl:
                s.state, s.exit_idx, s.exit_price = "loss", t, s.sl
                s.r_multiple = -1.0
            elif hit_tp:
                s.state, s.exit_idx, s.exit_price = "win", t, tp
                s.r_multiple = (tp - s.entry_price) * d / risk if risk > 0 else float("nan")
            elif t - s.entry_idx >= cfg.max_hold_bars:
                s.state, s.exit_idx, s.exit_price = "timeout", t, c[t]
                s.r_multiple = (c[t] - s.entry_price) * d / risk if risk > 0 else float("nan")
            return s
        return s

    def enter(s: Setup, t: int, price: float) -> Setup:
        if not _in_session(index[t], cfg):
            return s                      # outside session: stay tapped, keep waiting
        s.state = "entered"
        s.entry_idx = t
        s.entry_price = float(price)
        col_signal[t] = s.direction
        return s

    # ------------------------------------------------------------------ loop
    for t in range(N):
        # 1) pivots that become confirmed at this bar
        j = t - n
        new_long = new_short = None
        if j >= 0:
            if ph[j]:
                new_long = try_new_leg(+1, j, t)
                conf_ph.append(j)
            if pl[j]:
                new_short = try_new_leg(-1, j, t)
                conf_pl.append(j)

        # 2) advance existing setups (uses the bar's full OHLC)
        if active_long is not None:
            active_long = step(active_long, t)
            if active_long.state not in ACTIVE_STATES:
                active_long = None
        if active_short is not None:
            active_short = step(active_short, t)
            if active_short.state not in ACTIVE_STATES:
                active_short = None

        # 3) install freshly confirmed legs (an armed zone is replaced; a tapped/entered one is kept)
        if new_long is not None:
            if active_long is None or active_long.state == "armed":
                if active_long is not None:
                    active_long.state, active_long.exit_idx = "superseded", t
                active_long = new_long
                setups.append(new_long)
        if new_short is not None:
            if active_short is None or active_short.state == "armed":
                if active_short is not None:
                    active_short.state, active_short.exit_idx = "superseded", t
                active_short = new_short
                setups.append(new_short)

        # 4) per-bar columns: show the most relevant active setup (entered > tapped > armed)
        cands = [s for s in (active_long, active_short) if s is not None]
        if cands:
            rank = {"entered": 2, "tapped": 1, "armed": 0}
            best = max(cands, key=lambda s: (rank[s.state], s.confirmed_idx))
            col_dir[t] = best.direction
            col_state[t] = best.state
            for r in lv_cols:
                lv_cols[r][t] = best.levels[f"{r:g}"]
            col_sl[t] = best.sl
            for k, tp in enumerate(best.tps):
                col_tp[k][t] = tp

    out = df.copy()
    out["atr"] = atr_v
    out["pivot_high"] = np.where(ph, h, np.nan)
    out["pivot_low"] = np.where(pl, l, np.nan)
    out["htf_bias"] = bias
    out["ote_dir"] = col_dir
    out["ote_state"] = col_state
    out["ote_signal"] = col_signal
    for r, arr in lv_cols.items():
        out[level_column(r)] = arr
    out["ote_sl"] = col_sl
    for k, arr in enumerate(col_tp):
        out[f"ote_tp{k + 1}"] = arr
    return OTEResult(out, setups, cfg)


# ----------------------------------------------------------------------------
# Data loading / plotting / CLI
# ----------------------------------------------------------------------------
def load_yfinance(symbol: str, interval: str, period: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=False)
    if df is None or len(df) == 0:
        raise RuntimeError(f"no data returned for {symbol} {interval} {period}")
    df = _normalize_ohlc(df)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def plot_ote(res: OTEResult, last: int = 300, path: Optional[str] = None, title: str = "") -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    df = res.frame.iloc[-last:]
    start = len(res.frame) - len(df)
    x = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(16, 8), dpi=110)
    up = df["close"].values >= df["open"].values
    colors = np.where(up, "#2e7d32", "#c62828")
    ax.vlines(x, df["low"].values, df["high"].values, color=colors, linewidth=0.8)
    ax.bar(x, (df["close"] - df["open"]).values, bottom=df["open"].values, width=0.6, color=colors, edgecolor=colors)

    cfg = res.config
    for s in res.setups:
        end_idx = s.exit_idx if s.exit_idx is not None else len(res.frame) - 1
        if end_idx < start or s.confirmed_idx > start + len(df):
            continue
        x0 = max(s.confirmed_idx, start) - start
        x1 = end_idx - start
        near, far = s.levels[f"{cfg.zone_near:g}"], s.levels[f"{cfg.zone_far:g}"]
        zc = "#1565c0" if s.direction > 0 else "#ad1457"
        alpha = 0.35 if s.entry_idx is not None else 0.15
        ax.add_patch(Rectangle((x0, min(near, far)), max(x1 - x0, 1), abs(far - near), color=zc, alpha=alpha, lw=0))
        ax.hlines(s.levels[f"{cfg.sweet_spot:g}"], x0, x1, color=zc, linestyles="dashed", linewidth=0.8)
        # leg itself
        ax.plot([s.origin_idx - start, s.extreme_idx - start], [s.origin_price, s.extreme_price],
                color=zc, linewidth=0.8, alpha=0.6)
        if s.entry_idx is not None:
            ex = s.entry_idx - start
            ax.scatter([ex], [s.entry_price], marker="^" if s.direction > 0 else "v", s=90,
                       color="#00c853" if s.direction > 0 else "#ff1744", zorder=5, edgecolor="black")
            ax.hlines(s.sl, ex, x1, color="#d50000", linewidth=1.0)
            tp = s.tps[min(cfg.eval_tp_index, len(s.tps) - 1)]
            ax.hlines(tp, ex, x1, color="#00897b", linewidth=1.0)
            ax.annotate(s.state, (x1, s.entry_price), fontsize=8, color=zc)

    ax.set_xlim(-1, len(df))
    lo, hi = df["low"].min(), df["high"].max()
    pad = (hi - lo) * 0.05
    ax.set_ylim(lo - pad, hi + pad)
    ticks = np.linspace(0, len(df) - 1, min(10, len(df))).astype(int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(df.index[i])[:16] for i in ticks], rotation=30, ha="right", fontsize=8)
    ax.set_title(title or f"OTE indicator  |  zone {cfg.zone_near}-{cfg.zone_far}, sweet spot {cfg.sweet_spot}  |  "
                 f"confirm={cfg.confirm_mode}, htf={cfg.htf}/{cfg.bias_mode}")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    path = path or "ote_chart.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def _fmt(price: float) -> str:
    """Price string with sensible precision (FX pairs need 5 decimals, indices 2)."""
    if price is None or not np.isfinite(price):
        return "nan"
    mag = math.floor(math.log10(abs(price))) if price != 0 else 0
    dec = int(min(6, max(2, 5 - mag)))
    return f"{price:.{dec}f}"


def _print_report(res: OTEResult, symbol: str) -> None:
    cfg = res.config
    print("=" * 78)
    print(f"OTE INDICATOR  {symbol}  bars={len(res.frame)}  {res.frame.index[0]} -> {res.frame.index[-1]}")
    print(f"config: swing={cfg.swing_len} minLeg={cfg.min_leg_atr}ATR BOS={cfg.require_structure_break} "
          f"sweep={cfg.require_sweep} confirm={cfg.confirm_mode}/{cfg.confirm_bars} "
          f"htf={cfg.htf} bias={cfg.bias_mode} tp=idx{cfg.eval_tp_index}({cfg.tp_levels[min(cfg.eval_tp_index, len(cfg.tp_levels)-1)]})")
    print("-" * 78)
    for k, v in res.summary().items():
        print(f"  {k:28s} {v:.3f}" if isinstance(v, float) else f"  {k:28s} {v}")
    print("-" * 78)
    act = res.active()
    if act:
        print("ACTIVE ZONES:")
        for s in act:
            side = "LONG" if s.direction > 0 else "SHORT"
            print(f"  {side} {s.state:8s} leg {_fmt(s.origin_price)} -> {_fmt(s.extreme_price)} "
                  f"| OTE {_fmt(s.levels[f'{cfg.zone_near:g}'])} / {_fmt(s.levels[f'{cfg.sweet_spot:g}'])} / "
                  f"{_fmt(s.levels[f'{cfg.zone_far:g}'])} | SL {_fmt(s.sl)} | TPs "
                  + ", ".join(_fmt(tp) for tp in s.tps))
    else:
        print("ACTIVE ZONES: none")
    ents = res.entries()[-8:]
    if ents:
        print("LAST ENTRIES:")
        idx = res.frame.index
        for s in ents:
            side = "LONG" if s.direction > 0 else "SHORT"
            r = f"{s.r_multiple:+.2f}R" if s.r_multiple is not None else "open"
            print(f"  {str(idx[s.entry_idx])[:16]} {side:5s} @ {_fmt(s.entry_price)} SL {_fmt(s.sl)} "
                  f"TP {_fmt(s.tps[min(cfg.eval_tp_index, len(s.tps)-1)])} -> {s.state:8s} {r}")
    print("=" * 78)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="ICT Optimal Trade Entry indicator")
    p.add_argument("--symbol", default="NQ=F")
    p.add_argument("--interval", default="15m")
    p.add_argument("--period", default="30d")
    p.add_argument("--csv", help="load OHLC from a CSV (datetime index in first column) instead of yfinance")
    p.add_argument("--htf", default="1h", help="higher timeframe for bias (pandas rule, e.g. 1h, 4h, 1D) or 'none'")
    p.add_argument("--bias", default="structure", choices=["structure", "range", "none"])
    p.add_argument("--swing", type=int, default=5)
    p.add_argument("--min-leg-atr", type=float, default=1.5)
    p.add_argument("--confirm", default="consolidation", choices=["consolidation", "reclaim", "touch"])
    p.add_argument("--confirm-bars", type=int, default=2)
    p.add_argument("--tp", type=int, default=1, help="index into tp levels (0=range extreme, 1=-0.27, 2=-0.62, 3=-1.0)")
    p.add_argument("--no-bos", action="store_true", help="do not require a structure break")
    p.add_argument("--sweep", action="store_true", help="require a liquidity sweep at the leg origin")
    p.add_argument("--session", help="entry session, e.g. 09:30-11:00 (exchange time)")
    p.add_argument("--plot", action="store_true")
    p.add_argument("--last", type=int, default=300, help="bars to plot")
    p.add_argument("--out", default="ote_results")
    a = p.parse_args(argv)

    cfg = OTEConfig(
        swing_len=a.swing, min_leg_atr=a.min_leg_atr, require_structure_break=not a.no_bos,
        require_sweep=a.sweep, confirm_mode=a.confirm, confirm_bars=a.confirm_bars,
        eval_tp_index=a.tp, htf=None if a.htf.lower() == "none" else a.htf,
        bias_mode="none" if a.htf.lower() == "none" else a.bias,
        session=tuple(a.session.split("-")) if a.session else None,
    )
    if a.csv:
        df = pd.read_csv(a.csv, index_col=0, parse_dates=True)
        symbol = os.path.basename(a.csv)
    else:
        df = load_yfinance(a.symbol, a.interval, a.period)
        symbol = f"{a.symbol} {a.interval}"
    res = compute_ote(df, cfg)
    _print_report(res, symbol)
    os.makedirs(a.out, exist_ok=True)
    tag = symbol.replace("=", "").replace(" ", "_").replace("/", "_")
    res.setups_frame().to_csv(os.path.join(a.out, f"ote_setups_{tag}.csv"), index=False)
    res.frame.to_csv(os.path.join(a.out, f"ote_frame_{tag}.csv"))
    if a.plot:
        path = plot_ote(res, last=a.last, path=os.path.join(a.out, f"ote_chart_{tag}.png"), title=f"OTE - {symbol}")
        print(f"chart saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
