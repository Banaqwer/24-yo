"""Recompute the headline statistic(s) of E1..E8, E10..E13 by quarter / half-year / ex-regime / top-5 / Sunday split."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research/extremes/scripts/refute_events_regime")
from rob import *

pd.set_option("display.width", 250)
rows = []
for sym in ("NQ", "ES"):
    x = load(sym)
    sun = x.sunday_open == 1; wk = x.sunday_open == 0
    print(f"\n==================== {sym}  n={len(x)}  regimes: " + ", ".join(f"{nm}={int(x[nm].sum())}" for nm in list(REGIMES)))

    # ---------------- E1 Sunday low early
    for col, d in (("low_by_tokyo_open", +1), ("low_in_first_bar", +1), ("high_by_tokyo_open", +1), ("high_in_first_bar", +1), ("either_first", +1)):
        run(sym, x, "E1", "Sunday vs weeknight", sun, wk, col, "prop", d, rows)
    for col, d in (("abs_gap", +1), ("first_bar_rng_bp", +1), ("first_bar_ret_bp", +1), ("rally_after_lo_bp", +1), ("lo_k", -1)):
        run(sym, x, "E1", "Sunday vs weeknight", sun, wk, col, "med", d, rows)

    # ---------------- E2 Sunday level placement / range / hi_bp
    for col, d in (("high_above_rth_high", -1), ("low_below_rth_low", +1), ("both_inside", -1), ("asia_up", +1), ("close_loc_ext", +1)):
        run(sym, x, "E2", "Sunday vs weeknight", sun, wk, col, "prop", d, rows)
    for col, d in (("rng_bp", +1), ("hi_bp", +1), ("lo_bp", +1), ("hi_vs_rth_high_bp", -1), ("lo_vs_rth_low_bp", +1)):
        run(sym, x, "E2", "Sunday vs weeknight", sun, wk, col, "med", d, rows)

    # ---------------- E3 Sunday after NFP
    nfp_sun = sun & (x.tier1_data_today == 1); oth_sun = sun & (x.tier1_data_today == 0)
    run(sym, x, "E3", "NFP Sunday vs other Sunday", nfp_sun, oth_sun, "low_below_rth_low", "prop", +1, rows)
    run(sym, x, "E3", "NFP Sunday vs other Sunday", nfp_sun, oth_sun, "lo_vs_rth_low_bp", "med", -1, rows)
    run(sym, x, "E3", "NFP Sunday vs other Sunday", nfp_sun, oth_sun, "high_above_rth_high", "prop", -1, rows)
    run(sym, x, "E3", "NFP Sunday vs other Sunday", nfp_sun, oth_sun, "rth_range_bp", "med", +1, rows)
    t1wk = wk & (x.tier1_data_today == 1); t0wk = wk & (x.tier1_data_today == 0)
    run(sym, x, "E3", "tier1 weeknight vs other weeknight", t1wk, t0wk, "low_below_rth_low", "prop", +1, rows)

    # ---------------- E4 FOMC eve
    fe = x.fomc_tomorrow == 1; nfe = x.fomc_tomorrow == 0
    for col, d in (("hi_first", -1), ("hi_last", +1), ("lo_last", -1), ("low_in_first_bar", +1), ("close_above_ref", +1), ("asia_up", +1)):
        run(sym, x, "E4", "FOMC eve vs rest", fe, nfe, col, "prop", d, rows)
    for col, d in (("hi_k", +1), ("close_loc", +1), ("asia_ret_bp", +1), ("drop_after_hi_bp", -1), ("rng_bp", +1), ("abs_gap", -1)):
        run(sym, x, "E4", "FOMC eve vs rest", fe, nfe, col, "med", d, rows)

    # ---------------- E5 FOMC night
    ft = x.fomc_today == 1; nft = x.fomc_today == 0
    for col, d in (("low_in_first_bar", +1), ("either_last", -1), ("hi_first", -1), ("high_by_tokyo_open", -1), ("close_above_ref", +1)):
        run(sym, x, "E5", "FOMC night vs rest", ft, nft, col, "prop", d, rows)
    for col, d in (("hi_bp", +1), ("rng_bp", +1), ("rally_after_lo_bp", +1), ("asia_ret_bp", +1), ("first_bar_rng_bp", +1), ("abs_gap", +1)):
        run(sym, x, "E5", "FOMC night vs rest", ft, nft, col, "med", d, rows)

    # ---------------- E6 megacap size
    me = x.megacap_earnings_tonight == 1; nme = x.megacap_earnings_tonight == 0
    for col, d in (("high_in_first_bar", +1), ("low_in_first_bar", +1), ("either_last", -1), ("hi_last", -1)):
        run(sym, x, "E6", "megacap vs rest", me, nme, col, "prop", d, rows)
    for col, d in (("rng_bp", +1), ("first_bar_rng_bp", +1), ("abs_gap", +1), ("drop_after_hi_bp", +1), ("rally_after_lo_bp", +1)):
        run(sym, x, "E6", "megacap vs rest", me, nme, col, "med", d, rows)

    # ---------------- E7 megacap x post_ret side
    run(sym, x, "E7", "megacap vs rest", me, nme, "post_side_break", "prop", +1, rows)
    run(sym, x, "E7", "megacap vs rest", me, nme, "opp_side_break", "prop", -1, rows)
    run(sym, x, "E7", "megacap post>0 vs rest post>0", me & (x.post_ret > 0), nme & (x.post_ret > 0), "high_above_rth_high", "prop", +1, rows)
    run(sym, x, "E7", "megacap post<0 vs rest post<0", me & (x.post_ret < 0), nme & (x.post_ret < 0), "low_below_rth_low", "prop", +1, rows)
    big = nme & (x.post_ret.abs() >= 0.0015)
    run(sym, x, "E7", "non-megacap |post|>=15bp vs rest non-megacap", big, nme & (x.post_ret.abs() < 0.0015), "post_side_break", "prop", +1, rows)

    # ---------------- E8 tier1 tomorrow
    t1 = x.tier1_data_tomorrow == 1; nt1 = x.tier1_data_tomorrow == 0
    for col, d in (("low_by_tokyo_open", -1), ("close_loc_ext", -1), ("either_last", -1), ("high_by_tokyo_open", -1)):
        run(sym, x, "E8", "tier1 tomorrow vs rest", t1, nt1, col, "prop", d, rows)
    for col, d in (("rng_bp", -1), ("hi_vs_rth_high_bp", -1), ("abs_asia_ret", -1)):
        run(sym, x, "E8", "tier1 tomorrow vs rest", t1, nt1, col, "med", d, rows)

    # ---------------- E10 China data weeknights
    cn = wk & (x.cn_data_tonight == 1); ncn = wk & (x.cn_data_tonight == 0)
    for col, d in (("either_last", -1), ("hi_last", -1), ("lo_last", -1)):
        run(sym, x, "E10", "cn_data weeknight vs other weeknight", cn, ncn, col, "prop", d, rows)

    # ---------------- E11 short sessions / holiday eve
    sh = x.n_bars < 9; fu = x.n_bars == 9
    run(sym, x, "E11", "short vs full", sh, fu, "rng_bp", "med", -1, rows)
    run(sym, x, "E11", "short vs full", sh, fu, "low_in_first_bar", "prop", +1, rows)
    run(sym, x, "E11", "short vs full", sh, fu, "high_in_first_bar", "prop", +1, rows)
    ht = x.holiday_tomorrow == 1
    run(sym, x, "E11", "holiday_tomorrow vs full", ht, fu & ~ht, "rng_bp", "med", -1, rows)
    run(sym, x, "E11", "holiday_tomorrow vs full", ht, fu & ~ht, "rally_after_lo_bp", "med", -1, rows)
    run(sym, x, "E11", "holiday_tomorrow vs full", ht, fu & ~ht, "drop_after_hi_bp", "med", -1, rows)
    ph = x.pre_holiday == 1
    run(sym, x, "E11", "pre_holiday vs rest", ph, ~ph, "rng_bp", "med", -1, rows)
    run(sym, x, "E11", "pre_holiday vs rest", ph, ~ph, "hi_bp", "med", -1, rows)

    # ---------------- E12 gap / month-end
    mth = x.month_end == 1
    run(sym, x, "E12", "month_end (all) vs weeknight", mth, wk & ~mth, "abs_gap", "med", +1, rows)
    run(sym, x, "E12", "month_end weeknight vs other weeknight", mth & wk, wk & ~mth, "abs_gap", "med", +1, rows)
    run(sym, x, "E12", "month_end Sunday vs other Sunday", mth & sun, sun & ~mth, "abs_gap", "med", +1, rows)
    run(sym, x, "E12", "month_end (all) vs weeknight", mth, wk & ~mth, "low_by_tokyo_open", "prop", +1, rows)
    run(sym, x, "E12", "month_end weeknight vs other weeknight", mth & wk, wk & ~mth, "low_by_tokyo_open", "prop", +1, rows)
    run(sym, x, "E12", "month_end (all) vs weeknight", mth, wk & ~mth, "low_in_first_bar", "prop", +1, rows)
    run(sym, x, "E12", "month_end weeknight vs other weeknight", mth & wk, wk & ~mth, "low_in_first_bar", "prop", +1, rows)
    run(sym, x, "E12", "month_end (all) vs weeknight", mth, wk & ~mth, "both_first", "prop", +1, rows)
    run(sym, x, "E12", "month_end weeknight vs other weeknight", mth & wk, wk & ~mth, "both_first", "prop", +1, rows)
    for f in ("megacap_earnings_tonight", "fomc_today", "tier1_data_today", "fomc_tomorrow"):
        run(sym, x, "E12", f"{f} weeknight vs other weeknight", wk & (x[f] == 1), wk & (x[f] == 0), "abs_gap", "med", +1 if f != "fomc_tomorrow" else -1, rows)

    # ---------------- E13 opex Sundays
    op = x.opex_today == 1
    run(sym, x, "E13", "opex Sunday vs other Sunday", op & sun, sun & ~op, "lo_last", "prop", +1, rows)
    run(sym, x, "E13", "opex Sunday vs other Sunday", op & sun, sun & ~op, "first_bar_ret_bp", "med", +1, rows)
    run(sym, x, "E13", "opex Sunday vs other Sunday", op & sun, sun & ~op, "abs_gap", "med", +1, rows)
    run(sym, x, "E13", "opex Sunday vs other Sunday", op & sun, sun & ~op, "either_last", "prop", +1, rows)

df = pd.DataFrame(rows)
df.to_csv(f"{OUT}/claims_robustness.csv", index=False)
print("\nrows:", len(df))
