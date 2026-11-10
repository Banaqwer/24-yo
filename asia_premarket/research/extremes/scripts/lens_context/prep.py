"""Build the clean analysis frame for the 18:00-context lens.

Output: <scratch>/frame_NQ.csv, frame_ES.csv  (one row per RTH date, artefact sessions removed)
Adds 18:00-knowable level distances and direction-framed targets.
"""
import os, sys
import numpy as np
import pandas as pd

ROOT = "."
OUT = "research/extremes/scripts/lens_context"
os.makedirs(OUT, exist_ok=True)

ARTEFACTS = {
    "NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"],
    "ES": ["2025-12-16", "2025-12-17"],
}

# 18:00-knowable features examined by this lens
FEATS = [
    # RTH move / location
    "mag", "is_down", "rth_ret", "rth_ret_z", "ext_in_dir", "clv", "vwap_in_dir", "close_vs_vwap_rng",
    "late_day_rev", "stretch20_in_dir", "stretch50_in_dir", "z_sma20", "z_sma50", "ret5_in_dir", "ret_5d",
    "abs_streak", "streak", "gap_in_dir", "gap_open", "post_in_dir", "post_ret", "abs_post",
    "dist_20d_high", "dist_20d_low",
    # vol state
    "vix", "vix_z20", "vix_chg", "vix_consistent", "rv_ratio", "rv20", "rth_range_atr", "rth_vol_rel",
    "asia_rng_med20", "asia_rng_prev", "vvix",
    # cross asset
    "yen_in_dir", "usdjpy_chg", "yield_in_dir", "us10y_chg", "n225_in_dir", "n225_ret", "sox_in_dir",
    "sox_minus_nq", "nqes_in_dir", "nq_minus_es", "kospi_ret", "hsi_ret", "sx5e_ret", "dxy_chg",
    "gold_chg", "crude_chg", "btc_rth",
    # session memory
    "prior_asia_in_dir", "prior_asia_ret", "prior_eur_ret", "overnight_in_dir", "prior_overnight_ret",
    "prior_asia_reverted",
    # derived level distances (18:00-knowable)
    "dist_rth_high0", "dist_rth_low0", "dist_rth_vwap0", "dist_prior_asia_high0", "dist_prior_asia_low0",
    "dist_with0", "dist_against0", "rth_range_bp", "open_vs_rth_range0",
    # calendar
    "sunday_open", "pre_holiday", "month_end", "fomc_today", "tier1_data_today", "tier2_data_today",
    "opex_today", "witching_today", "roll_today", "megacap_earnings_tonight", "boj_tonight",
    "jp_data_tonight", "cn_data_tonight", "rba_tonight", "fomc_tomorrow", "tier1_data_tomorrow",
    "holiday_tomorrow", "dow", "is_dst",
]

BIN_TARGETS = [
    "hi_first", "high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar",
    "high_above_rth_high", "low_below_rth_low", "high_by_tokyo_open", "low_by_tokyo_open",
    # direction-framed
    "with_first", "with_in_first_bar", "against_in_first_bar", "with_in_last_bar", "against_in_last_bar",
    "with_beyond_rth", "against_beyond_rth", "close_top20", "close_bot20", "close_with_dir",
]
CONT_TARGETS = ["hi_bp", "lo_bp", "rng_bp", "close_loc", "close_loc_in_dir", "with_ext_bp", "against_ext_bp",
                "hi_k", "lo_k"]


def build(sym):
    df = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    n0 = len(df)
    drop = [pd.Timestamp(d) for d in ARTEFACTS[sym] if pd.Timestamp(d) in df.index]
    df = df.drop(index=drop)
    print(sym, "sessions", n0, "-> after artefact drop", len(df), "dropped", [d.date() for d in drop])

    ref = df["ref_close"]
    d = np.where(df["is_down"] == 1, -1.0, 1.0)
    df["dir"] = d
    # level distances from the 17:00 close (bp, positive = level above close for highs, negative for lows)
    df["dist_rth_high0"] = (df["lvl_rth_high"] / ref - 1) * 1e4
    df["dist_rth_low0"] = (df["lvl_rth_low"] / ref - 1) * 1e4
    df["dist_rth_vwap0"] = (df["lvl_rth_vwap"] / ref - 1) * 1e4
    df["dist_prior_asia_high0"] = (df["lvl_prior_asia_high"] / ref - 1) * 1e4
    df["dist_prior_asia_low0"] = (df["lvl_prior_asia_low"] / ref - 1) * 1e4
    # distance to the RTH extreme in the direction of the move (small = closed near the extreme)
    df["dist_with0"] = np.where(d > 0, df["dist_rth_high0"], -df["dist_rth_low0"])
    df["dist_against0"] = np.where(d > 0, -df["dist_rth_low0"], df["dist_rth_high0"])
    df["open_vs_rth_range0"] = df["dist_with0"] / df["rth_range_bp"].replace(0, np.nan)
    df["abs_post"] = df["post_ret"].abs()

    # direction-framed targets
    df["with_first"] = np.where(d > 0, df["hi_first"], 1 - df["hi_first"])
    df.loc[df["same_bar_extremes"] == 1, "with_first"] = np.nan  # order unknown inside one bar
    df["with_in_first_bar"] = np.where(d > 0, df["high_in_first_bar"], df["low_in_first_bar"])
    df["against_in_first_bar"] = np.where(d > 0, df["low_in_first_bar"], df["high_in_first_bar"])
    df["with_in_last_bar"] = np.where(d > 0, df["high_in_last_bar"], df["low_in_last_bar"])
    df["against_in_last_bar"] = np.where(d > 0, df["low_in_last_bar"], df["high_in_last_bar"])
    df["with_beyond_rth"] = np.where(d > 0, df["high_above_rth_high"], df["low_below_rth_low"])
    df["against_beyond_rth"] = np.where(d > 0, df["low_below_rth_low"], df["high_above_rth_high"])
    df["with_ext_bp"] = np.where(d > 0, df["hi_bp"], -df["lo_bp"])        # extension in the RTH direction (bp, >=0 mostly)
    df["against_ext_bp"] = np.where(d > 0, -df["lo_bp"], df["hi_bp"])     # extension against the RTH direction
    df["close_loc_in_dir"] = np.where(d > 0, df["close_loc"], 1 - df["close_loc"])
    df["close_top20"] = (df["close_loc"] >= 0.8).astype(int)
    df["close_bot20"] = (df["close_loc"] <= 0.2).astype(int)
    df["close_with_dir"] = (df["close_loc_in_dir"] >= 0.5).astype(int)
    df["half"] = np.where(df.index < pd.Timestamp("2025-09-01"), "H1", "H2")
    df["full"] = df["n_bars"] == 9
    keep = ["half", "full", "n_bars", "tokyo_open_k", "china_open_k", "dir", "same_bar_extremes", "hi_k", "lo_k"] + \
           [c for c in FEATS if c in df.columns] + [t for t in BIN_TARGETS if t in df.columns] + \
           [t for t in CONT_TARGETS if t in df.columns and t not in ("hi_k", "lo_k")]
    keep = list(dict.fromkeys(keep))
    out = df[keep].copy()
    out.to_csv(f"{OUT}/frame_{sym}.csv")
    missing = [c for c in FEATS if c not in df.columns]
    print("missing feats:", missing)
    return out


if __name__ == "__main__":
    for sym in ("NQ", "ES"):
        o = build(sym)
        print(o.shape, "H1/H2:", o["half"].value_counts().to_dict())
