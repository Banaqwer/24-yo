"""Q5: ES robustness for the main NQ findings + sharper statistics."""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_narrative")
import numpy as np, pandas as pd
from scipy import stats
from common import *

def enrich(x):
    x = x.copy()
    x["abs_post"] = x["post_ret"].abs() * 1e4; x["abs_kospi"] = x["kospi_ret"].abs() * 100; x["abs_sox"] = x["sox_ret"].abs() * 100
    x["abs_rth"] = x["rth_ret_bp"].abs(); x["abs_gap"] = x["gap_open_bp"].abs(); x["abs_yen"] = x["usdjpy_chg"].abs() * 100
    x["asia_up"] = (x["asia_ret_bp"] > 0).astype(int)
    x["lo_by_tko_and_close_hi"] = ((x["lo_k"] <= x["tokyo_open_k"]) & (x["close_loc"] >= 0.6)).astype(int)
    x["close_hi70"] = (x["close_loc"] >= 0.7).astype(int); x["close_lo30"] = (x["close_loc"] <= 0.3).astype(int)
    x["quiet"] = ((x["megacap_earnings_tonight"] == 0) & (x["sunday_open"] == 0) & (x["fomc_today"] == 0) & (x["boj_tonight"] == 0)
                  & (x["abs_rth"] < 50) & (x["abs_post"] < 8) & (x["abs_kospi"] < 1.5) & (x["tier1_data_today"] == 0)).astype(int)
    return x

TESTS = [
 ("sunday_open==1", lambda x: x["sunday_open"] == 1, ["low_in_first_bar", "high_in_first_bar", "lo_after_tko", "lo_by_tko_and_close_hi", "trend_close", "asia_up", "any_first_bar"]),
 ("|post_ret|>=25bp", lambda x: x["abs_post"] >= 25, ["any_last_bar", "high_in_last_bar", "high_in_first_bar", "any_first_bar"]),
 ("megacap_earnings_tonight==1", lambda x: x["megacap_earnings_tonight"] == 1, ["any_last_bar", "any_first_bar", "mid_close", "cont"]),
 ("|kospi_ret|>=3%", lambda x: x["abs_kospi"] >= 3, ["any_at_tko", "low_at_tokyo_open", "high_at_tokyo_open", "low_in_last_bar", "cont"]),
 ("|sox_ret|>=3%", lambda x: x["abs_sox"] >= 3, ["any_at_tko"]),
 ("rth<=-150bp", lambda x: x["rth_ret_bp"] <= -150, ["low_below_rth_low", "asia_up", "low_by_tokyo_open", "close_hi70"]),
 ("-130<=rth<=-30bp", lambda x: (x["rth_ret_bp"] <= -30) & (x["rth_ret_bp"] >= -130), ["low_below_rth_low", "high_above_rth_high", "close_hi70", "cont", "asia_up"]),
 ("30<=rth<=130bp", lambda x: (x["rth_ret_bp"] >= 30) & (x["rth_ret_bp"] <= 130), ["high_above_rth_high", "low_below_rth_low", "close_lo30", "cont", "asia_up"]),
 ("rth<0", lambda x: x["rth_ret_bp"] < 0, ["close_hi70", "asia_up"]),
 ("rth>0", lambda x: x["rth_ret_bp"] > 0, ["close_lo30", "asia_up"]),
 ("tier1_data_tomorrow==1", lambda x: x["tier1_data_tomorrow"] == 1, ["lo_post_tko", "lo_after_tko", "cont", "asia_up"]),
 ("fomc_today==1", lambda x: x["fomc_today"] == 1, ["any_first_bar", "any_last_bar", "low_in_first_bar", "cont"]),
 ("quiet", lambda x: x["quiet"] == 1, ["lo_after_tko", "lo_post_tko", "any_at_tko", "asia_up", "close_hi70", "close_lo30", "any_last_bar"]),
 ("vix<15", lambda x: x["vix"] < 15, ["any_last_bar"]),
 ("vix>=25", lambda x: x["vix"] >= 25, ["low_below_rth_low", "any_first_bar"]),
 ("gap_open>=+20bp [k0]", lambda x: x["gap_open_bp"] >= 20, ["low_in_first_bar", "high_in_first_bar", "asia_up"]),
 ("gap_open<=-20bp [k0]", lambda x: x["gap_open_bp"] <= -20, ["low_in_first_bar", "high_in_first_bar", "asia_up"]),
 ("boj_tonight==1", lambda x: x["boj_tonight"] == 1, ["any_first_bar", "asia_up"]),
 ("cn_data_tonight==1", lambda x: x["cn_data_tonight"] == 1, ["low_at_tokyo_open", "lo_post_tko", "low_in_last_bar"]),
 ("sox<=-3%&rth<0", lambda x: (x["sox_ret"] <= -0.03) & (x["rth_ret_bp"] < 0), ["low_below_rth_low", "asia_up", "low_at_tokyo_open"]),
]
CONT = [
 ("megacap_earnings_tonight==1", lambda x: x["megacap_earnings_tonight"] == 1, ["rng_bp", "first_bar_rng_bp", "abs_asia_ret"]),
 ("|post_ret|>=25bp", lambda x: x["abs_post"] >= 25, ["rng_bp", "first_bar_rng_bp"]),
 ("sunday_open==1", lambda x: x["sunday_open"] == 1, ["rng_bp", "abs_gap", "first_bar_rng_bp"]),
 ("|kospi_ret|>=3%", lambda x: x["abs_kospi"] >= 3, ["rng_bp"]),
 ("rth<=-150bp", lambda x: x["rth_ret_bp"] <= -150, ["rng_bp", "rally_after_lo_bp"]),
 ("fomc_today==1", lambda x: x["fomc_today"] == 1, ["rng_bp"]),
 ("tier1_data_tomorrow==1", lambda x: x["tier1_data_tomorrow"] == 1, ["rng_bp"]),
 ("holiday_tomorrow|pre_holiday", lambda x: (x["holiday_tomorrow"] == 1) | (x["pre_holiday"] == 1), ["rng_bp"]),
 ("vix>=25", lambda x: x["vix"] >= 25, ["rng_bp", "first_bar_rng_bp"]),
 ("vix<15", lambda x: x["vix"] < 15, ["rng_bp"]),
 ("boj_tonight==1", lambda x: x["boj_tonight"] == 1, ["rng_bp"]),
 ("quiet", lambda x: x["quiet"] == 1, ["rng_bp", "abs_asia_ret"]),
]
allrows = []
for sym in ["NQ", "ES"]:
    x = enrich(load_extremes(sym))
    x["abs_asia_ret"] = x["asia_ret_bp"].abs()
    for nm, fn, labs in TESTS:
        c = fn(x).fillna(False)
        for lab in labs:
            r = cond_table(x, c, lab, nm); r["sym"] = sym; r["kind"] = "rate"; allrows.append(r)
    for nm, fn, cols in CONT:
        c = fn(x).fillna(False)
        for col in cols:
            r = cont_table(x, c, col, nm); r["sym"] = sym; r["kind"] = "cont"; allrows.append(r)
t = pd.DataFrame(allrows); t.to_csv(f"{OUT}/q5_es_robustness.csv", index=False)
pd.set_option("display.width", 320, "display.max_columns", 40, "display.max_rows", 500)
rt = t[t.kind == "rate"].pivot_table(index=["cond", "label"], columns="sym", values=["n", "rate", "base_rate", "p_binom", "H1_rate", "H2_rate"])
rt = rt.reorder_levels([1, 0], axis=1).sort_index(axis=1)
print(rt.round(3).to_string())
ct = t[t.kind == "cont"].pivot_table(index=["cond", "col"], columns="sym", values=["n", "value", "base_value", "p_mw", "H1_value", "H2_value"])
ct = ct.reorder_levels([1, 0], axis=1).sort_index(axis=1)
print(ct.round(2).to_string())

# ---- post-Tokyo-open continuation (bar_k knowable at the close of the Tokyo-open bar) ----
for sym in ["NQ", "ES"]:
    x = enrich(load_extremes(sym)); p = load_panel(sym); p = p[p.n_bars == 9]
    at = p[p.k == p.tokyo_open_k][["date", "cum_ret_bp", "pos_in_range", "bars_since_hi", "bars_since_lo", "run_rng_bp"]].set_index("date")
    xx = x.join(at, how="inner")
    xx["rest"] = xx["close_bp"] - xx["cum_ret_bp"]
    xx["rest_cont"] = (np.sign(xx["rest"]) == np.sign(xx["cum_ret_bp"])).astype(int)
    print(f"\n{sym}: at the close of the Tokyo-open bar: does the rest of the session continue the sign of the move so far?")
    for nm, c in [("all", xx["cum_ret_bp"].abs() >= 0), ("|move so far|>=20bp", xx["cum_ret_bp"].abs() >= 20), ("|move so far|>=40bp", xx["cum_ret_bp"].abs() >= 40),
                  ("|move|<10bp", xx["cum_ret_bp"].abs() < 10), ("sunday", xx["sunday_open"] == 1), ("megacap|post>=15", (xx["megacap_earnings_tonight"] == 1) | (xx["abs_post"] >= 15)),
                  ("|kospi|>=3%", xx["abs_kospi"] >= 3), ("quiet", xx["quiet"] == 1), ("tier1_tomorrow", xx["tier1_data_tomorrow"] == 1)]:
        s = xx[c]; r, k, n = rate(s["rest_cont"]); lo, hi = boot_ci(s["rest_cont"].values)
        h1 = s[s.half == "H1"]["rest_cont"].mean(); h2 = s[s.half == "H2"]["rest_cont"].mean()
        print(f"  {nm:22s} n={n:3d} rest_cont={r:.3f} ci=({lo:.2f},{hi:.2f}) p_vs_0.5={binom_p(k, n, 0.5):.3f} H1={h1:.2f} H2={h2:.2f}  med|rest|={s['rest'].abs().median():.0f}bp")
    # position in range at the Tokyo-open close -> which extreme is still to come
    print(f"  {sym}: pos_in_range at Tokyo-open bar close vs high_done/low_done later")
    for lo_, hi_ in [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]:
        s = xx[(xx.pos_in_range >= lo_) & (xx.pos_in_range < hi_)]
        hd = (s["hi_k"] <= s["tokyo_open_k"]).mean(); ld = (s["lo_k"] <= s["tokyo_open_k"]).mean()
        print(f"    pos [{lo_:.1f},{hi_:.1f}) n={len(s):3d} P(high already in)={hd:.2f} P(low already in)={ld:.2f}")

# ---- megacap 'peak not held': among up-nights, high in last bar ----
for sym in ["NQ", "ES"]:
    x = enrich(load_extremes(sym)); up = x[x["asia_ret_bp"] > 0]
    m = up[up["megacap_earnings_tonight"] == 1]; r, k, n = rate(m["high_in_last_bar"]); b = up["high_in_last_bar"].mean()
    print(f"\n{sym} up-nights: megacap -> high_in_last_bar {r:.2f} (k={k} n={n}) vs up-night base {b:.2f} p={binom_p(k, n, b):.3f} "
          f"H1={m[m.half=='H1']['high_in_last_bar'].mean():.2f}(n={(m.half=='H1').sum()}) H2={m[m.half=='H2']['high_in_last_bar'].mean():.2f}(n={(m.half=='H2').sum()})")
    pm = up[up["abs_post"] >= 25]; r, k, n = rate(pm["high_in_last_bar"])
    print(f"{sym} up-nights: |post|>=25 -> high_in_last_bar {r:.2f} (k={k} n={n}) vs {b:.2f} p={binom_p(k, n, b):.3f} "
          f"H1={pm[pm.half=='H1']['high_in_last_bar'].mean():.2f} H2={pm[pm.half=='H2']['high_in_last_bar'].mean():.2f}")
    dn = x[x["asia_ret_bp"] < 0]; md = dn[dn["abs_post"] >= 25]; r, k, n = rate(md["low_in_last_bar"]); b2 = dn["low_in_last_bar"].mean()
    print(f"{sym} down-nights: |post|>=25 -> low_in_last_bar {r:.2f} (k={k} n={n}) vs down-night base {b2:.2f} p={binom_p(k, n, b2):.3f}")

# ---- the Q1 'ordinary nights have Tokyo-open extremes' question on the full table: any_at_tko by rng tercile (ex post) and by quiet flag
x = enrich(load_extremes("NQ"))
x["rng_terc"] = pd.qcut(x["rng_bp"], 3, labels=["small", "mid", "large"])
print("\nNQ any_at_tko by realised range tercile (ex post):", x.groupby("rng_terc", observed=True)["any_at_tko"].agg(["mean", "size"]).round(2).to_dict())
print("NQ any_at_tko by asia_rng_med20 tercile (18:00):", x.groupby(pd.qcut(x["asia_rng_med20"], 3, labels=["low", "mid", "high"]), observed=True)["any_at_tko"].agg(["mean", "size"]).round(2).to_dict())
print("NQ any_at_tko by is_dst:", x.groupby("is_dst")["any_at_tko"].agg(["mean", "size"]).round(2).to_dict())
print("NQ high_at_tko by is_dst:", x.groupby("is_dst")["high_at_tokyo_open"].agg(["mean", "size"]).round(2).to_dict(), " low_at_tko:", x.groupby("is_dst")["low_at_tokyo_open"].agg(["mean", "size"]).round(2).to_dict())
print("NQ hi_k hist by dst:", {d: np.bincount(g["hi_k"].astype(int), minlength=9).tolist() for d, g in x[x.n_bars == 9].groupby("is_dst")})
print("NQ lo_k hist by dst:", {d: np.bincount(g["lo_k"].astype(int), minlength=9).tolist() for d, g in x[x.n_bars == 9].groupby("is_dst")})
