"""Knowability / leakage checks for the lens_context claims C1-C13."""
import numpy as np, pandas as pd
from scipy import stats
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)

ROOT = "."
LC = "research/extremes/scripts/lens_context"

ext = pd.read_csv(f"{ROOT}/research/extremes/NQ_extremes.csv", index_col="date", parse_dates=True)
fr = pd.read_csv(f"{LC}/frame_NQ.csv", index_col=0, parse_dates=True)
frE = pd.read_csv(f"{LC}/frame_ES.csv", index_col=0, parse_dates=True)
print("extremes n", len(ext), "frame n", len(fr), "ES frame n", len(frE))
for d in ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"]:
    print(d, "in extremes:", pd.Timestamp(d) in ext.index, "in frame:", pd.Timestamp(d) in fr.index)
print("first dates:", ext.index[:6].date)
# sessions around the splices
print(ext.loc["2024-06-18":"2024-06-26", ["asia_gdate", "n_bars", "gap_open_bp", "hi_k", "lo_k", "first_bar_ret_bp"]])
print(ext.loc["2024-12-18":"2024-12-24", ["asia_gdate", "n_bars", "gap_open_bp", "hi_k", "lo_k", "first_bar_ret_bp"]])

# ---- VIX alignment: known closes
dc = pd.read_csv(f"{ROOT}/data/daily_close.csv", index_col=0, parse_dates=True)
for d in ["2024-08-05", "2025-04-04", "2025-04-08", "2024-08-02"]:
    print("VIX daily_close", d, dc.loc[d, "VIX"], "| feature vix on", d, ext.loc[d, "vix"] if pd.Timestamp(d) in ext.index else "n/a")

# ---- asia_rng_med20 ex-ante check: recompute from extremes rng_bp shifted
own = ext["rng_bp"].shift(1).rolling(20, min_periods=10).median()
# feature uses (asia_high-asia_low)/asia_open (not /ref_close); compare roughly
alt = ((ext["asia_high"] - ext["asia_low"]) / ext["asia_open"] * 1e4).shift(1).rolling(20, min_periods=10).median()
print("asia_rng_med20*1e4 vs recomputed (shifted) corr:", np.corrcoef(ext["asia_rng_med20"].dropna() * 1e4, alt.reindex(ext["asia_rng_med20"].dropna().index))[0, 1],
      " max abs diff:", (ext["asia_rng_med20"] * 1e4 - alt).abs().max())
unsh = ((ext["asia_high"] - ext["asia_low"]) / ext["asia_open"] * 1e4).rolling(20, min_periods=10).median()
print("  vs UNshifted max abs diff:", (ext["asia_rng_med20"] * 1e4 - unsh).abs().max())
print("asia_rng_prev == prior session rng? corr", np.corrcoef(ext["asia_rng_prev"].dropna()*1e4, ((ext["asia_high"]-ext["asia_low"])/ext["asia_open"]*1e4).shift(1).reindex(ext["asia_rng_prev"].dropna().index))[0,1])

# ---- C1/C2 : level distances, mechanical share
fr["sdh"] = fr["dist_rth_high0"] / (fr["asia_rng_med20"] * 1e4)
fr["sdl"] = -fr["dist_rth_low0"] / (fr["asia_rng_med20"] * 1e4)
print("\nC1: n with dist_rth_high0 <= 0 (17:00 close at/above RTH high):", (fr.dist_rth_high0 <= 0).sum(),
      " rate high_above_rth_high among them:", fr.loc[fr.dist_rth_high0 <= 0, "high_above_rth_high"].mean())
print("C1: n with dist_rth_high0 in (0,10]:", ((fr.dist_rth_high0 > 0) & (fr.dist_rth_high0 <= 10)).sum(),
      " rate:", fr.loc[(fr.dist_rth_high0 > 0) & (fr.dist_rth_high0 <= 10), "high_above_rth_high"].mean())
print("C1: <=10bp bucket n", (fr.dist_rth_high0 <= 10).sum(), "rate", fr.loc[fr.dist_rth_high0 <= 10, "high_above_rth_high"].mean())
print("C1: >50bp n", (fr.dist_rth_high0 > 50).sum(), "rate", fr.loc[fr.dist_rth_high0 > 50, "high_above_rth_high"].mean())
edges = [-np.inf, 0.10, 0.25, 0.5, 0.75, 1.0, 1.5, np.inf]
fr["sdh_b"] = pd.cut(fr.sdh, edges); fr["sdl_b"] = pd.cut(fr.sdl, edges)
print(fr.groupby("sdh_b")["high_above_rth_high"].agg(["count", "mean"]))
print("  share of <=0.10 bucket that is mechanical (dist<=0):", (fr.loc[fr.sdh <= 0.10, "dist_rth_high0"] <= 0).mean())
print(fr.groupby("sdl_b")["low_below_rth_low"].agg(["count", "mean"]))
print("C2: n with dist_rth_low0 >= 0 (close at/below RTH low):", (fr.dist_rth_low0 >= 0).sum(),
      " rate:", fr.loc[fr.dist_rth_low0 >= 0, "low_below_rth_low"].mean())
# also: the 18:00 OPEN vs RTH high -> gap_open is bar-0 info, not 18:00; check that lens did not use it
# C1 scaled bucket by half
for hl in ["H1", "H2"]:
    s = fr[fr.half == hl]
    print(hl, "<=10bp", s.loc[s.dist_rth_high0 <= 10, "high_above_rth_high"].agg(["count", "mean"]).round(3).to_dict(),
          ">50", s.loc[s.dist_rth_high0 > 50, "high_above_rth_high"].agg(["count", "mean"]).round(3).to_dict())

# ---- walk-forward results quoted
wl = pd.read_csv(f"{LC}/wf_logit_NQ.csv"); we = pd.read_csv(f"{LC}/wf_extra_NQ.csv"); wq = pd.read_csv(f"{LC}/wf_quant_NQ.csv")
print("\nC1 wf:", wl[(wl.target == "high_above_rth_high") & (wl.model.isin(["uni:dist_rth_high0", "levels", "uni:is_down", "uni:clv"]))][["model", "n_oos", "brier", "brier_base", "skill", "skill_ci_lo", "skill_ci_hi", "skill_h1", "skill_h2"]].to_string())
print(we[(we.target == "high_above_rth_high") & (we.model.isin(["uni:scaled_dist_high", "scaled_levels"]))][["model", "skill", "skill_ci_lo", "skill_ci_hi", "skill_h1", "skill_h2"]].to_string())
print("C2 wf:", wl[(wl.target == "low_below_rth_low") & (wl.model.isin(["uni:dist_rth_low0", "levels", "uni:is_down"]))][["model", "n_oos", "brier", "brier_base", "skill", "skill_ci_lo", "skill_ci_hi", "skill_h1", "skill_h2"]].to_string())
print(we[(we.target == "low_below_rth_low") & (we.model.isin(["uni:scaled_dist_low", "scaled_levels"]))][["model", "skill", "skill_ci_lo", "skill_ci_hi", "skill_h1", "skill_h2"]].to_string())

# ---- C3
for dn in [0, 1]:
    s = fr[fr.is_down == dn]
    print("C3 is_down", dn, "n", len(s), "high_above", round(s.high_above_rth_high.mean(), 3), "low_below", round(s.low_below_rth_low.mean(), 3))

# ---- C4
print("\nC4 wf_quant levels set:")
print(wq[(wq.model == "levels") & (wq.target.isin(["rng_bp", "hi_bp", "lo_bp"]))][["target", "tau", "skill", "skill_ci_lo", "skill_ci_hi", "skill_h1", "skill_h2", "oos_coverage"]].to_string())
print(wq[(wq.model == "scale") & (wq.target == "rng_bp")][["target", "tau", "skill"]].to_string())

# ---- C5/C6: dow and session gap
ext["gap_days"] = (pd.to_datetime(ext["asia_gdate"]) - ext.index.to_series()).dt.days
print("\nC5 gap_days by dow:\n", pd.crosstab(ext.index.dayofweek, ext["gap_days"]))
f5 = fr.copy(); f5["gap_days"] = ext["gap_days"].reindex(f5.index)
sun = f5[f5.dow == 4]; rest = f5[f5.dow != 4]
print("C5 sunday n", len(sun), "low_by_tokyo", round(sun.low_by_tokyo_open.mean(), 3), "rest", round(rest.low_by_tokyo_open.mean(), 3),
      "low_in_first", round(sun.low_in_first_bar.mean(), 3), "rest", round(rest.low_in_first_bar.mean(), 3))
print("   by tokyo_open_k:", sun.groupby("tokyo_open_k")["low_by_tokyo_open"].agg(["count", "mean"]).round(3).to_dict())
print("   fisher p low_by_tokyo:", stats.fisher_exact(pd.crosstab(f5.dow == 4, f5.low_by_tokyo_open).values)[1])
mon = f5[f5.dow == 0]; restm = f5[f5.dow != 0]
print("C6 monday n", len(mon), "low_in_first", round(mon.low_in_first_bar.mean(), 3), "rest", round(restm.low_in_first_bar.mean(), 3),
      "low_by_tokyo", round(mon.low_by_tokyo_open.mean(), 3), "rest", round(restm.low_by_tokyo_open.mean(), 3),
      "hi_first", round(mon.hi_first.mean(), 3), "rest", round(restm.hi_first.mean(), 3))
print("   monday by tokyo_open_k:", mon.groupby("tokyo_open_k")[["low_by_tokyo_open", "hi_first"]].agg(["count", "mean"]).round(3))
# dow x half
print("   C6 by half:", mon.groupby("half")[["low_in_first_bar", "low_by_tokyo_open", "hi_first"]].agg(["count", "mean"]).round(3))
print("   C5 by half:", sun.groupby("half")[["low_in_first_bar", "low_by_tokyo_open"]].agg(["count", "mean"]).round(3))
print("   wf skills dow / is_sunday / is_monday:")
print(wl[(wl.model == "uni:dow") & (wl.target.isin(["low_by_tokyo_open", "low_in_first_bar", "hi_first"]))][["target", "skill", "skill_ci_lo", "skill_ci_hi", "skill_h1", "skill_h2"]].to_string())
print(we[(we.model.isin(["uni:is_sunday", "uni:is_monday", "uni:fomc_tomorrow", "timing6"])) & (we.target.isin(["low_by_tokyo_open", "low_in_first_bar", "hi_first"]))][["target", "model", "skill", "skill_ci_lo", "skill_ci_hi", "skill_h1", "skill_h2"]].to_string())

# ---- C7: fomc_tomorrow sessions
f7 = fr[fr.fomc_tomorrow == 1]
print("\nC7 n", len(f7), "dates:", [d.strftime("%Y-%m-%d (%a)") for d in f7.index])
print("   hi_first", f7.hi_first.sum(), "close_top20", f7.close_top20.sum(), "close_bot20", f7.close_bot20.sum(), "low_in_first", f7.low_in_first_bar.sum(),
      "high_in_last", f7.high_in_last_bar.sum(), "same_bar", f7.same_bar_extremes.sum(), "closed up", (f7.close_loc.notna() & (ext.loc[f7.index, "close_bp"] > 0)).sum())
print("   mean hi_k", f7.hi_k.mean(), "lo_k", f7.lo_k.mean(), "n_bars", f7.n_bars.value_counts().to_dict())
print("   by half:", f7.groupby("half")[["hi_first", "close_top20", "high_in_last_bar"]].agg(["count", "sum"]))
# any fomc_tomorrow session missing (FOMC eve not in frame)?
fomc = pd.to_datetime(["2024-07-31","2024-09-18","2024-11-07","2024-12-18","2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10","2026-01-28","2026-03-18","2026-04-29","2026-06-17","2026-07-29","2026-09-16","2026-10-28"])
eves = [ext.index[ext.index < d][-1] for d in fomc if (ext.index < d).any()]
print("   eves from FOMC list:", [e.strftime("%Y-%m-%d") for e in eves], "\n   in frame:", [e in fr.index for e in eves])
print("   fomc_today==1 on D=eve? (should be 0):", ext.loc[eves, "fomc_today"].sum(), " fomc_tomorrow on eves:", ext.loc[eves, "fomc_tomorrow"].sum())
# exact binomial for hi_first 1/18 vs 0.462
print("   binom p hi_first<=1/18:", stats.binom.cdf(1, 18, fr.hi_first.mean()))

# ---- C8
for dn in [0, 1]:
    s = fr[fr.is_down == dn]
    print("C8 is_down", dn, "close_top20", round(s.close_top20.mean(), 3), "close_with_dir", round(s.close_with_dir.mean(), 3), "mean close_loc", round(s.close_loc.mean(), 3))

# ---- C11
print("\nC11 low_in_first", fr.low_in_first_bar.mean().round(3), "high_in_first", fr.high_in_first_bar.mean().round(3),
      "high_in_last", fr.high_in_last_bar.mean().round(3), "low_in_last", fr.low_in_last_bar.mean().round(3))
print("   by half:", fr.groupby("half")[["low_in_first_bar", "high_in_first_bar", "high_in_last_bar", "low_in_last_bar"]].mean().round(3))
# bar-0 extreme == the 18:00 open print? compare asia_open with asia_high/low when hi_k==0
e0 = ext.reindex(fr.index)
m = e0.hi_k == 0
print("   when hi_k==0: share where asia_high == asia_open (the open print):", (np.isclose(e0.loc[m, "asia_high"], e0.loc[m, "asia_open"])).mean(), "n", m.sum())
m = e0.lo_k == 0
print("   when lo_k==0: share where asia_low == asia_open:", (np.isclose(e0.loc[m, "asia_low"], e0.loc[m, "asia_open"])).mean(), "n", m.sum())

# ---- C12
print("\nC12 P(with>against)", (fr.with_ext_bp > fr.against_ext_bp).mean().round(3), " with/against are built from hi_bp/lo_bp (ex post):",
      np.allclose(np.where(fr.dir > 0, fr.hi_bp, -fr.lo_bp), fr.with_ext_bp))

# ---- C13
s = fr.dropna(subset=["mag"])
print("\nC13 n", len(s), "rho(mag,rng)", stats.spearmanr(s.mag, s.rng_bp), "rho(abs_post,rng)", stats.spearmanr(s.abs_post, s.rng_bp))
