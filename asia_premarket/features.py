"""
Feature engine: everything knowable at 18:00 ET on RTH date D that could
explain where price is and condition what the following Asia session does.

Feature groups
  P  price structure of the day (RTH move, gap, location vs VWAP / range / settle)
  T  trend & mean-reversion state (z vs 5/20/50d means, streaks, 5d/20d returns)
  V  volatility state (realised vol, range expansion, VIX level / change / term)
  X  cross-asset (dollar, yen, yields, Nikkei, KOSPI, HSI, SOX, RUT, gold, oil, copper, BTC)
  S  session memory (what the prior Asia / Europe did; did Asia already revert yesterday)
  C  calendar (FOMC, CPI/NFP, BoJ, opex/roll, earnings, Sunday open, month end)

Targets (what the Asia session that follows did) are computed in targets().
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from sessions import load_hourly, build_sessions, with_prior_context, ET
from calendar_features import calendar_features

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def _z(x: pd.Series, win: int) -> pd.Series:
    m = x.rolling(win, min_periods=max(5, win // 2)).mean()
    s = x.rolling(win, min_periods=max(5, win // 2)).std()
    return (x - m) / s.replace(0, np.nan)


def load_daily() -> pd.DataFrame:
    c = pd.read_csv(os.path.join(DATA, "daily_close.csv"), index_col=0, parse_dates=True)
    c.index = pd.to_datetime(c.index).tz_localize(None)
    return c.astype(float)


def btc_rth_move(sessions_index: pd.DatetimeIndex) -> pd.Series:
    """BTC % move 09:00-16:00 ET on date D (BTC daily closes leak into Asia, so use hourly)."""
    p = os.path.join(DATA, "BTC_1h.csv")
    if not os.path.exists(p):
        return pd.Series(np.nan, index=sessions_index)
    b = load_hourly(p)
    out = {}
    for d in sessions_index:
        day = b[(b.index.date == d.date())]
        o = day[day.index.hour == 9]
        c = day[day.index.hour == 15]
        if len(o) and len(c):
            out[d] = float(c["Close"].iloc[0] / o["Open"].iloc[0] - 1)
    return pd.Series(out).reindex(sessions_index)


def build_feature_table(sym: str = "NQ", other: str = "ES") -> pd.DataFrame:
    h = load_hourly(os.path.join(DATA, f"{sym}_1h.csv"))
    s = with_prior_context(build_sessions(h))
    ho = load_hourly(os.path.join(DATA, f"{other}_1h.csv"))
    so = build_sessions(ho)
    daily = load_daily()

    f = pd.DataFrame(index=s.index)
    px = s["rth_close"]

    # ---- P: price structure ----
    f["rth_ret"] = s.rth_close / s.rth_open - 1
    f["day_ret"] = s.rth_close / s.prev_settle - 1
    f["gap_open"] = s.rth_open / s.prev_settle - 1
    f["post_ret"] = s.post_close / s.rth_close - 1           # 16:00-17:00 reaction (earnings etc.)
    rng = (s.rth_high - s.rth_low).replace(0, np.nan)
    f["clv"] = ((s.rth_close - s.rth_low) / rng) * 2 - 1       # -1 at low, +1 at high
    f["close_vs_vwap"] = (s.rth_close - s.rth_vwap) / s.rth_close
    f["close_vs_vwap_rng"] = (s.rth_close - s.rth_vwap) / rng
    f["close_vs_prev_close"] = s.rth_close / s.prev_rth_close - 1
    f["close_above_prev_high"] = (s.rth_close > s.prev_rth_high).astype(int)
    f["close_below_prev_low"] = (s.rth_close < s.prev_rth_low).astype(int)
    f["rth_hi_hour"] = s.rth_hi_hour
    f["rth_lo_hour"] = s.rth_lo_hour
    f["late_day_rev"] = (s.rth_close - s.rth_vwap) / rng * np.sign(f["rth_ret"])  # negative = faded into close
    f["gap_filled"] = (((s.rth_low <= s.prev_settle) & (s.rth_open > s.prev_settle)) |
                       ((s.rth_high >= s.prev_settle) & (s.rth_open < s.prev_settle))).astype(int)

    # ---- T: trend / MR state ----
    atr = (s.rth_high - s.rth_low).rolling(20, min_periods=10).mean()
    f["rth_range_atr"] = rng / atr
    for w in (5, 20, 50):
        sma = px.rolling(w, min_periods=w // 2).mean()
        f[f"z_sma{w}"] = (px - sma) / atr
    f["ret_5d"] = px / px.shift(5) - 1
    f["ret_20d"] = px / px.shift(20) - 1
    f["sma20_slope"] = px.rolling(20).mean().pct_change(5)
    sign = np.sign(f["rth_ret"])
    streak = sign.groupby((sign != sign.shift()).cumsum()).cumcount() + 1
    f["streak"] = (streak * sign).fillna(0)
    f["dist_20d_high"] = px / s.rth_high.rolling(20).max() - 1
    f["dist_20d_low"] = px / s.rth_low.rolling(20).min() - 1

    # ---- V: volatility ----
    lr = np.log(s.rth_close / s.prev_settle)
    f["rv20"] = lr.rolling(20, min_periods=10).std() * np.sqrt(252)
    f["rv5"] = lr.rolling(5, min_periods=3).std() * np.sqrt(252)
    f["rv_ratio"] = f["rv5"] / f["rv20"]
    f["rth_ret_z"] = f["rth_ret"] / lr.rolling(20, min_periods=10).std()
    vix = daily["VIX"].reindex(s.index)
    f["vix"] = vix
    f["vix_chg"] = vix.pct_change()
    f["vix_z20"] = _z(vix, 20)
    f["vix_minus_rv"] = vix / 100 - f["rv20"]
    if "VVIX" in daily:
        f["vvix"] = daily["VVIX"].reindex(s.index)
    # Asia realised range history (what is "normal" tonight)
    asia_rng = (s.asia_high - s.asia_low) / s.asia_open
    f["asia_rng_med20"] = asia_rng.shift(1).rolling(20, min_periods=10).median()
    f["asia_rng_prev"] = asia_rng.shift(1)
    f["asia_share_of_day"] = (asia_rng.shift(1) / (rng / px)).rolling(10, min_periods=5).median()

    # ---- X: cross-asset ----
    def dchg(col, w=1):
        """Most recent available session-to-session change (skips exchange holidays
        instead of printing a fake 0 on them)."""
        if col not in daily:
            return pd.Series(np.nan, index=s.index)
        x = daily[col].dropna()
        x = x[~x.index.duplicated()]
        return x.pct_change(w).reindex(s.index, method="ffill")

    def dlvl(col):
        if col not in daily:
            return pd.Series(np.nan, index=s.index)
        return daily[col].dropna().reindex(s.index, method="ffill")

    f["dxy_chg"] = dchg("DXY")
    f["usdjpy_chg"] = dchg("USDJPY")
    f["usdjpy_chg5"] = dchg("USDJPY", 5)
    f["usdjpy"] = dlvl("USDJPY")
    f["us10y"] = dlvl("US10Y")
    f["us10y_chg"] = dlvl("US10Y").diff()
    f["us10y_chg5"] = dlvl("US10Y").diff(5)
    f["curve_3m10y"] = dlvl("US10Y") - dlvl("US3M")
    f["n225_ret"] = dchg("N225")             # Tokyo session that preceded today's RTH
    f["n225_ret5"] = dchg("N225", 5)
    f["kospi_ret"] = dchg("KOSPI")
    f["hsi_ret"] = dchg("HSI")
    f["sse_ret"] = dchg("SSE")
    f["sx5e_ret"] = dchg("SX5E")
    f["sox_ret"] = dchg("SOX")
    f["sox_minus_nq"] = f["sox_ret"] - f["day_ret"]
    f["rut_ret"] = dchg("RUT")
    f["rut_minus_nq"] = f["rut_ret"] - f["day_ret"]
    f["gold_chg"] = dchg("GOLD")
    f["crude_chg"] = dchg("CRUDE")
    f["crude_chg5"] = dchg("CRUDE", 5)
    f["copper_chg"] = dchg("COPPER")
    f["btc_rth"] = btc_rth_move(s.index)
    # NQ vs ES relative strength today
    f["nq_minus_es"] = (s.rth_close / s.rth_open - 1) - (so.rth_close / so.rth_open - 1).reindex(s.index)
    # Nikkei futures proxy: where did N225 close relative to the US session? (US sells off after Tokyo close)
    f["us_after_tokyo"] = f["day_ret"] - f["n225_ret"]

    # ---- S: session memory ----
    f["prior_asia_ret"] = s.prior_asia_close / s.prior_asia_open - 1
    f["prior_eur_ret"] = s.prior_eur_close / s.prior_eur_open - 1
    f["prior_overnight_ret"] = s.rth_open / s.prev_settle - 1
    f["prior_asia_reverted"] = (np.sign(f["prior_asia_ret"]) == -np.sign(f["rth_ret"].shift(1))).astype(int)
    f["rth_vs_overnight"] = f["rth_ret"] * np.sign(f["prior_overnight_ret"])  # did RTH continue overnight direction?
    f["close_vs_prior_asia_high"] = (s.rth_close - s.prior_asia_high) / atr
    f["close_vs_prior_asia_low"] = (s.rth_close - s.prior_asia_low) / atr
    f["rth_vol_rel"] = s.rth_volume / s.rth_volume.rolling(20, min_periods=10).mean()

    # ---- C: calendar ----
    cal = calendar_features(s.index)
    f = f.join(cal)

    # ---- D: direction-framed features (relative to the RTH move; what a fade trader sees) ----
    d = np.sign(f["rth_ret"]).replace(0, 1)
    f["mag"] = f["rth_ret_z"].abs()
    f["ext_in_dir"] = f["clv"] * d                    # +1 closed at extreme in direction of move
    f["vwap_in_dir"] = f["close_vs_vwap_rng"] * d     # how far beyond VWAP in direction of move
    f["stretch20_in_dir"] = f["z_sma20"] * d          # move extends stretch from 20d mean (>0) or corrects it (<0)
    f["stretch50_in_dir"] = f["z_sma50"] * d
    f["ret5_in_dir"] = f["ret_5d"] * d
    f["gap_in_dir"] = f["gap_open"] * d
    f["post_in_dir"] = f["post_ret"] * d
    f["prior_asia_in_dir"] = f["prior_asia_ret"] * d  # last night already moved this way?
    f["overnight_in_dir"] = f["prior_overnight_ret"] * d
    f["n225_in_dir"] = f["n225_ret"] * d
    f["sox_in_dir"] = f["sox_minus_nq"] * d
    f["rut_in_dir"] = f["rut_minus_nq"] * d
    f["nqes_in_dir"] = f["nq_minus_es"] * d
    f["btc_in_dir"] = f["btc_rth"] * d
    f["yen_in_dir"] = f["usdjpy_chg"] * d             # >0: yen weakening on an up day (consistent risk-on)
    f["yield_in_dir"] = f["us10y_chg"] * d
    f["vix_consistent"] = f["vix_chg"] * -d           # >0: VIX moved with the equity move (confirmation)
    f["abs_streak"] = f["streak"].abs()
    f["is_down"] = (d < 0).astype(int)

    # reference levels for the report
    for k in ["rth_open", "rth_high", "rth_low", "rth_close", "rth_vwap", "post_close",
              "prev_settle", "prev_rth_high", "prev_rth_low", "prior_asia_high", "prior_asia_low"]:
        f[f"lvl_{k}"] = s[k]
    f["lvl_atr20"] = atr
    f["lvl_sma20"] = px.rolling(20).mean()
    f["lvl_sma50"] = px.rolling(50).mean()
    f = f.copy()  # defragment
    return f, s


def targets(s: pd.DataFrame) -> pd.DataFrame:
    """What the Asia session (18:00 D -> 03:00 D+1) did, keyed on RTH date D."""
    t = pd.DataFrame(index=s.index)
    rth_ret = s.rth_close / s.rth_open - 1
    rth_move = s.rth_close - s.rth_open
    t["asia_ret"] = s.asia_close / s.asia_open - 1
    t["asia_ret_vs_settle"] = s.asia_close / s.post_close - 1
    t["tokyo_ret"] = s.tokyo_close / s.tokyo_open - 1
    t["asia_first_hr"] = s.asia_first_close / s.asia_open - 1
    t["asia_rng"] = (s.asia_high - s.asia_low) / s.asia_open
    t["asia_up_ext"] = s.asia_high / s.asia_open - 1
    t["asia_dn_ext"] = s.asia_low / s.asia_open - 1
    t["eur_ret"] = s.eur_close / s.eur_open - 1
    t["overnight_ret"] = s.eur_close / s.asia_open - 1
    # reversion of the RTH move: sign of Asia opposite to sign of RTH
    t["rth_sign"] = np.sign(rth_ret)
    t["reverted"] = (np.sign(t["asia_ret"]) == -t["rth_sign"]).astype(float)
    t.loc[t["rth_sign"] == 0, "reverted"] = np.nan
    # fraction of the RTH move retraced at the Asia extreme in the reversion direction
    ext = np.where(rth_move > 0, s.asia_open - s.asia_low, s.asia_high - s.asia_open)
    t["retrace_frac"] = ext / rth_move.abs().replace(0, np.nan)
    # touched reference levels during Asia?
    t["hit_vwap"] = ((s.asia_low <= s.rth_vwap) & (s.asia_high >= s.rth_vwap)).astype(int)
    t["hit_settle"] = ((s.asia_low <= s.post_close) & (s.asia_high >= s.post_close)).astype(int)
    t["hit_rth_mid"] = ((s.asia_low <= (s.rth_high + s.rth_low) / 2) & (s.asia_high >= (s.rth_high + s.rth_low) / 2)).astype(int)
    t["broke_rth_high"] = (s.asia_high > s.rth_high).astype(int)
    t["broke_rth_low"] = (s.asia_low < s.rth_low).astype(int)
    # continuation: Asia closes beyond RTH extreme in the RTH direction
    t["continued"] = (((rth_move > 0) & (s.asia_close > s.rth_high)) | ((rth_move < 0) & (s.asia_close < s.rth_low))).astype(int)
    return t


WIDE_STOP_MULT = 0.6   # wide stop = 0.6 x recent (20d) median Asia range, from the 17:00 close


def wide_stop_distance(s: pd.DataFrame) -> pd.Series:
    """Known at 18:00: max(0.6 x 20d median Asia range, 0.3 x today's RTH range), in points.
    The second term scales the stop with today's own volatility (vol clusters)."""
    asia_rng = (s.asia_high - s.asia_low)
    med = asia_rng.shift(1).rolling(20, min_periods=10).median()
    today = 0.3 * (s.rth_high - s.rth_low)
    return pd.concat([WIDE_STOP_MULT * med, today], axis=1).max(axis=1)


def path_targets(sym: str, s: pd.DataFrame) -> pd.DataFrame:
    from sessions import path_outcomes
    h = load_hourly(os.path.join(DATA, f"{sym}_1h.csv"))
    tight = path_outcomes(h, s)
    wide = path_outcomes(h, s, stop_dist=wide_stop_distance(s), suffix="_w")
    return tight.join(wide)


FEATURE_COLS_COMPACT = [
    "mag", "is_down", "ext_in_dir", "vwap_in_dir", "stretch20_in_dir", "stretch50_in_dir", "ret5_in_dir",
    "gap_in_dir", "post_in_dir", "prior_asia_in_dir", "overnight_in_dir", "n225_in_dir", "sox_in_dir",
    "nqes_in_dir", "yen_in_dir", "yield_in_dir", "vix_consistent", "vix_z20", "vix", "rv_ratio",
    "rth_range_atr", "abs_streak", "rth_vol_rel", "asia_rng_med20",
    "fomc_today", "tier1_data_today", "tier1_data_tomorrow", "fomc_tomorrow", "megacap_earnings_tonight",
    "boj_tonight", "opex_today", "witching_today", "sunday_open", "pre_holiday", "month_end",
]

FEATURE_COLS_MODEL = [
    # P
    "rth_ret", "day_ret", "gap_open", "post_ret", "clv", "close_vs_vwap_rng", "late_day_rev",
    "close_above_prev_high", "close_below_prev_low", "gap_filled",
    # T
    "rth_range_atr", "z_sma5", "z_sma20", "z_sma50", "ret_5d", "ret_20d", "sma20_slope", "streak",
    "dist_20d_high", "dist_20d_low",
    # V
    "rv20", "rv_ratio", "rth_ret_z", "vix", "vix_chg", "vix_z20", "vix_minus_rv", "asia_rng_med20",
    # X
    "dxy_chg", "usdjpy_chg", "usdjpy_chg5", "us10y_chg", "us10y_chg5", "n225_ret", "kospi_ret", "hsi_ret",
    "sox_minus_nq", "rut_minus_nq", "gold_chg", "crude_chg", "btc_rth", "nq_minus_es", "us_after_tokyo",
    # S
    "prior_asia_ret", "prior_eur_ret", "prior_overnight_ret", "prior_asia_reverted", "rth_vs_overnight",
    "rth_vol_rel",
    # C
    "fomc_today", "tier1_data_today", "tier2_data_today", "opex_today", "witching_today", "roll_today",
    "megacap_earnings_tonight", "boj_tonight", "cn_data_tonight", "fomc_tomorrow", "tier1_data_tomorrow",
    "sunday_open", "month_end", "pre_holiday", "dow", "days_to_fomc",
]


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "NQ"
    other = "ES" if sym == "NQ" else "NQ"
    f, s = build_feature_table(sym, other)
    t = targets(s)
    f.to_csv(os.path.join(DATA, f"{sym}_features.csv"))
    t.to_csv(os.path.join(DATA, f"{sym}_targets.csv"))
    print(f.shape, t.shape)
    print(f.iloc[-1].to_string())
