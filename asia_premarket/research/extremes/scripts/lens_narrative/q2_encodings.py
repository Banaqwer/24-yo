"""Q2: 18:00-knowable encodings for each driver family, hit rate for extreme-at/after-Tokyo-open etc. on the FULL table."""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_narrative")
import numpy as np, pandas as pd
from common import *

x = load_extremes("NQ")
x["abs_post"] = x["post_ret"].abs() * 1e4
x["abs_kospi"] = x["kospi_ret"].abs() * 100
x["abs_n225"] = x["n225_ret"].abs() * 100
x["abs_sox"] = x["sox_ret"].abs() * 100
x["abs_yen"] = x["usdjpy_chg"].abs() * 100
x["abs_crude"] = x["crude_chg"].abs() * 100
x["abs_rth"] = x["rth_ret_bp"].abs()
x["abs_gap"] = x["gap_open_bp"].abs()
x["abs_prior_asia"] = x["prior_asia_ret"].abs() * 1e4
x["hi_at_k45"] = x["hi_k"].isin([4, 5]).astype(int)   # 22:00 / 23:00 ET bars (BoJ decision window)
x["lo_at_k45"] = x["lo_k"].isin([4, 5]).astype(int)
x["any_at_k45"] = ((x["hi_at_k45"] == 1) | (x["lo_at_k45"] == 1)).astype(int)
x["hi_at_k01"] = x["hi_k"].isin([0, 1]).astype(int)
x["lo_at_k01"] = x["lo_k"].isin([0, 1]).astype(int)
x["any_at_k34"] = (x["hi_k"].isin([3, 4]) | x["lo_k"].isin([3, 4])).astype(int)   # 21:00/22:00 ET (China data)
x["any_at_k6"] = ((x["hi_k"] == 6) | (x["lo_k"] == 6)).astype(int)                 # 00:00 ET bar (RBA 00:30)
x["revers_close"] = (((x["rth_ret_bp"] > 0) & (x["close_loc"] <= 0.3)) | ((x["rth_ret_bp"] < 0) & (x["close_loc"] >= 0.7))).astype(int)
x["asia_up"] = (x["asia_ret_bp"] > 0).astype(int)
x["lo_by_tko_and_close_hi"] = ((x["lo_k"] <= x["tokyo_open_k"]) & (x["close_loc"] >= 0.6)).astype(int)
x["hi_by_tko_and_close_lo"] = ((x["hi_k"] <= x["tokyo_open_k"]) & (x["close_loc"] <= 0.4)).astype(int)

# ---- the encodings (all knowable at 18:00 ET unless noted) ----
ENC = {
 # after-hours print family
 "megacap_earnings_tonight==1": x["megacap_earnings_tonight"] == 1,
 "|post_ret|>=15bp (16-17h bar)": x["abs_post"] >= 15,
 "|post_ret|>=25bp": x["abs_post"] >= 25,
 "megacap|post>=15": (x["megacap_earnings_tonight"] == 1) | (x["abs_post"] >= 15),
 # headline / weekend family
 "sunday_open==1": x["sunday_open"] == 1,
 "politics_today==1": x["politics_today"] == 1,
 "|crude_chg|>=3%": x["abs_crude"] >= 3,
 "|crude_chg|>=5%": x["abs_crude"] >= 5,
 # Asia-origin chip family (prior Asia session / US chips)
 "|kospi_ret|>=3%": x["abs_kospi"] >= 3,
 "|kospi_ret|>=5%": x["abs_kospi"] >= 5,
 "|n225_ret|>=2%": x["abs_n225"] >= 2,
 "|sox_ret|>=3%": x["abs_sox"] >= 3,
 "|sox_ret|>=5%": x["abs_sox"] >= 5,
 "sox<=-3%&rth<0": (x["sox_ret"] <= -0.03) & (x["rth_ret_bp"] < 0),
 "|prior_asia_ret|>=80bp": x["abs_prior_asia"] >= 80,
 # BoJ / yen family
 "boj_tonight==1": x["boj_tonight"] == 1,
 "|usdjpy_chg|>=0.5%": x["abs_yen"] >= 0.5,
 "|usdjpy_chg|>=0.8%": x["abs_yen"] >= 0.8,
 "jp_data_tonight==1": x["jp_data_tonight"] == 1,
 # US macro family
 "fomc_today==1": x["fomc_today"] == 1,
 "tier1_data_today==1": x["tier1_data_today"] == 1,
 "tier1_data_tomorrow==1": x["tier1_data_tomorrow"] == 1,
 "rth<=-150bp": x["rth_ret_bp"] <= -150,
 "rth<=-200bp": x["rth_ret_bp"] <= -200,
 "rth>=+150bp": x["rth_ret_bp"] >= 150,
 "-130<=rth<=-30bp": (x["rth_ret_bp"] <= -30) & (x["rth_ret_bp"] >= -130),
 "|rth|>=100bp": x["abs_rth"] >= 100,
 "vix>=25": x["vix"] >= 25,
 "vix<15": x["vix"] < 15,
 "cn_data_tonight==1": x["cn_data_tonight"] == 1,
 "rba_tonight==1": x["rba_tonight"] == 1,
 "holiday_tomorrow|pre_holiday": (x["holiday_tomorrow"] == 1) | (x["pre_holiday"] == 1),
 "quarter_end==1": x["quarter_end"] == 1,
 "month_end==1": x["month_end"] == 1,
 "roll|witching|opex_today": (x["roll_today"] == 1) | (x["witching_today"] == 1) | (x["opex_today"] == 1),
 # no-news drift proxy
 "quiet: no flags & |rth|<50 & |post|<8 & |kospi|<1.5": (x["megacap_earnings_tonight"] == 0) & (x["sunday_open"] == 0) & (x["fomc_today"] == 0)
     & (x["boj_tonight"] == 0) & (x["abs_rth"] < 50) & (x["abs_post"] < 8) & (x["abs_kospi"] < 1.5) & (x["tier1_data_today"] == 0),
 # the 18:00 open print (knowable at the 18:00 print, i.e. k=0 open, NOT before 18:00)
 "[k0 open] |gap_open|>=20bp": x["abs_gap"] >= 20,
 "[k0 open] |gap_open|>=40bp": x["abs_gap"] >= 40,
 "[k0 open] |gap_open|<5bp": x["abs_gap"] < 5,
}
LABELS = ["hi_after_tko", "lo_after_tko", "hi_post_tko", "lo_post_tko", "high_in_first_bar", "low_in_first_bar", "any_first_bar",
          "high_at_tokyo_open", "low_at_tokyo_open", "any_at_tko", "high_at_china_open", "low_at_china_open",
          "high_in_last_bar", "low_in_last_bar", "any_last_bar", "trend_close", "mid_close", "cont", "revers_close",
          "any_at_k45", "any_at_k34", "any_at_k6", "high_above_rth_high", "low_below_rth_low", "hi_first",
          "lo_by_tko_and_close_hi", "hi_by_tko_and_close_lo", "asia_up"]
rows = []
for name, cond in ENC.items():
    cond = cond.fillna(False)
    for lab in LABELS:
        rows.append(cond_table(x, cond, lab, name))
tab = pd.DataFrame(rows)
tab.to_csv(f"{OUT}/q2_encoding_screen.csv", index=False)
print("comparisons:", len(tab))

# continuous outcomes
crows = []
for name, cond in ENC.items():
    cond = cond.fillna(False)
    for col in ["rng_bp", "abs_asia_ret", "close_loc", "drop_after_hi_bp", "rally_after_lo_bp", "first_bar_rng_bp"]:
        crows.append(cont_table(x, cond, col, name))
ctab = pd.DataFrame(crows)
ctab.to_csv(f"{OUT}/q2_encoding_continuous.csv", index=False)

pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 500)
# headline view: the labels the task asks for
view = tab[tab["label"].isin(["hi_after_tko", "lo_after_tko", "any_first_bar", "any_at_tko", "any_last_bar", "trend_close", "cont"])]
piv = view.pivot(index="cond", columns="label", values="rate").round(2)
piv["n"] = view.groupby("cond")["n"].first()
base = {lab: round(x[lab].mean(), 2) for lab in piv.columns if lab != "n"}
print("BASE:", base)
print(piv.loc[list(ENC.keys())].to_string())
print("\nsignificant (p<0.05, n>=30):")
sig = tab[(tab.p_binom < 0.05) & (tab.n >= 30)].sort_values("p_binom")
print(sig[["cond", "label", "n", "rate", "base_rate", "ci_lo", "ci_hi", "p_binom", "H1_n", "H1_rate", "H1_base", "H2_n", "H2_rate", "H2_base"]].round(3).to_string())
print("\ncontinuous (p<0.05, n>=30):")
csig = ctab[(ctab.p_mw < 0.05) & (ctab.n >= 30)].sort_values("p_mw")
print(csig[["cond", "col", "n", "value", "base_value", "ci_lo", "ci_hi", "p_mw", "H1_n", "H1_value", "H1_base", "H2_n", "H2_value", "H2_base"]].round(2).to_string())
x.to_csv(f"{OUT}/NQ_extremes_enriched.csv")
