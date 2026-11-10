"""Q3: test the narrative 'repeating patterns' that speak about session highs/lows, opening prints, Tokyo-open
reversals, late trends into Europe. Each test uses the FULL NQ table with an 18:00-knowable proxy where the
narrative's condition is ex post."""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_narrative")
import numpy as np, pandas as pd
from scipy import stats
from common import *

x = pd.read_csv(f"{OUT}/NQ_extremes_enriched.csv", index_col="date", parse_dates=True)
x["fam"] = pd.read_csv(f"{OUT}/NQ_extremes_with_family.csv", index_col="date", parse_dates=True)["family"]
x["is_cat"] = (x["fam"] != "none").astype(int)
x["rest_after_first_bar"] = x["asia_ret_bp"] - x["first_bar_ret_bp"]
x["fb_sign_agree"] = (np.sign(x["first_bar_ret_bp"]) == np.sign(x["rest_after_first_bar"])).astype(int)
x["fb_sign_agree_total"] = (np.sign(x["first_bar_ret_bp"]) == np.sign(x["asia_ret_bp"])).astype(int)
x["gap_sign_agree_total"] = (np.sign(x["gap_open_bp"]) == np.sign(x["asia_ret_bp"])).astype(int)
x["abs_fb"] = x["first_bar_ret_bp"].abs()
res = []

def rep(pid, pattern, test, cond, label=None, col=None, stat="median", note=""):
    cond = pd.Series(np.asarray(cond), index=x.index).fillna(False).astype(bool)
    if label is not None:
        r = cond_table(x, cond, label, test)
        r.update(pid=pid, pattern=pattern, kind="rate", note=note)
    else:
        r = cont_table(x, cond, col, test, stat=stat)
        r.update(pid=pid, pattern=pattern, kind="cont", note=note)
    res.append(r)
    return r

# P1 Q4#2 / Q1#9 / Q3: after-hours megacap prints override RTH; sign independent of rth; |asia_ret| > 0.7%
m = x["megacap_earnings_tonight"] == 1
rep("P1a", "AH megacap print overrides RTH direction", "megacap_tonight -> cont (sign asia == sign rth)", m, label="cont")
rep("P1b", "AH megacap print -> |asia_ret| large", "megacap_tonight -> |asia_ret| (bp)", m, col="abs_asia_ret")
rep("P1c", "AH megacap print -> extreme at the 18:00 open", "megacap_tonight -> any_first_bar", m, label="any_first_bar")
rep("P1d", "AH megacap print -> extreme at the 18:00 open", "megacap_tonight -> first_bar_rng_bp", m, col="first_bar_rng_bp")
rep("P1e", "AH megacap print -> no late trend", "megacap_tonight -> any_last_bar", m, label="any_last_bar")
rep("P1f", "AH megacap print -> no late trend", "|post_ret|>=25bp -> any_last_bar", x["abs_post"] >= 25, label="any_last_bar")
rep("P1g", "AH print -> high in first bar", "|post_ret|>=25bp -> high_in_first_bar", x["abs_post"] >= 25, label="high_in_first_bar")
rep("P1h", "AH print -> low in first bar", "|post_ret|>=25bp -> low_in_first_bar", x["abs_post"] >= 25, label="low_in_first_bar")
# direction: does the sign of post_ret say which extreme is in bar 0?
up = (x["post_ret"] >= 0.0015); dn = (x["post_ret"] <= -0.0015)
rep("P1i", "post_ret up -> the open is the LOW (momentum) or the HIGH (fade)?", "post_ret>=+15bp -> low_in_first_bar", up, label="low_in_first_bar")
rep("P1j", "post_ret up -> ...", "post_ret>=+15bp -> high_in_first_bar", up, label="high_in_first_bar")
rep("P1k", "post_ret down -> the open is the HIGH (momentum) or the LOW (fade)?", "post_ret<=-15bp -> high_in_first_bar", dn, label="high_in_first_bar")
rep("P1l", "post_ret down -> ...", "post_ret<=-15bp -> low_in_first_bar", dn, label="low_in_first_bar")
rep("P1m", "post_ret up -> cont of post direction (asia_ret>0)", "post_ret>=+15bp -> asia_up", up, label="asia_up")
rep("P1n", "post_ret down -> asia_ret<0", "post_ret<=-15bp -> asia_up", dn, label="asia_up")

# P2 Q4#4 / Q1#1 / Q3#5: Sunday opens gap on weekend headlines; the 18:00 gap sign = session sign; Friday RTH uninformative
s = x["sunday_open"] == 1
rep("P2a", "Sunday: Friday RTH sign uninformative", "sunday_open -> cont", s, label="cont")
rep("P2b", "Sunday: gap sign = session sign", "sunday_open -> sign(gap_open)==sign(asia_ret)", s, label="gap_sign_agree_total")
rep("P2c", "Weekday: gap sign = session sign", "weekday -> sign(gap_open)==sign(asia_ret)", ~s, label="gap_sign_agree_total")
rep("P2d", "Sunday: first-bar extreme", "sunday_open -> any_first_bar", s, label="any_first_bar")
rep("P2e", "Sunday: low in first bar", "sunday_open -> low_in_first_bar", s, label="low_in_first_bar")
rep("P2f", "Sunday: high in first bar", "sunday_open -> high_in_first_bar", s, label="high_in_first_bar")
rep("P2g", "Sunday: low by Tokyo open and close in upper 40%", "sunday_open -> lo_by_tko_and_close_hi", s, label="lo_by_tko_and_close_hi")
rep("P2h", "Sunday: trend close", "sunday_open -> trend_close", s, label="trend_close")
rep("P2i", "Sunday: range", "sunday_open -> rng_bp", s, col="rng_bp")
rep("P2j", "Sunday: asia up rate", "sunday_open -> asia_up", s, label="asia_up")
# Sunday gap size vs weekday
rep("P2k", "Sunday |gap| bigger", "sunday_open -> |gap_open_bp|", s, col="abs_gap")
# does the corr(rth_ret, asia_ret) differ?
for nm, msk in [("sunday", s), ("weekday", ~s)]:
    sub = x[msk]; r_, p_ = stats.spearmanr(sub["rth_ret_bp"], sub["asia_ret_bp"])
    res.append(dict(pid="P2l", pattern="Friday RTH uninformative for Sunday asia_ret", test=f"{nm}: spearman(rth_ret, asia_ret)", kind="corr",
                    n=len(sub), value=r_, p_mw=p_, note=""))

# P3 Q1#11: fading the first 18:00-19:00 impulse was wrong on headline nights, right on no-news nights
big_fb = x["abs_fb"] >= 20
rep("P3a", "first-bar impulse continues (sign of rest == sign of bar0)", "|first_bar_ret|>=20bp -> fb_sign_agree(rest)", big_fb, label="fb_sign_agree")
rep("P3b", "first-bar impulse continues", "|first_bar_ret|<10bp -> fb_sign_agree(rest)", x["abs_fb"] < 10, label="fb_sign_agree")
hd = (x["megacap_earnings_tonight"] == 1) | (x["sunday_open"] == 1) | (x["fomc_today"] == 1) | (x["abs_post"] >= 15)
rep("P3c", "headline-proxy nights: impulse continues", "headline proxy(megacap|sunday|fomc|post>=15) & |fb|>=20 -> fb_sign_agree", hd & big_fb, label="fb_sign_agree")
rep("P3d", "no-headline nights: impulse fades", "no headline proxy & |fb|>=20 -> fb_sign_agree", (~hd) & big_fb, label="fb_sign_agree")
rep("P3e", "all: bar0 sign == session sign", "all -> sign(first_bar_ret)==sign(asia_ret)", x["abs_fb"] >= 0, label="fb_sign_agree_total")
rep("P3f", "catalogue (ex post headline) nights: impulse continues", "is_cat & |fb|>=20 -> fb_sign_agree", (x["is_cat"] == 1) & big_fb, label="fb_sign_agree", note="ex post")
rep("P3g", "non-catalogue nights in window: impulse", "window non-cat & |fb|>=20 -> fb_sign_agree", (x["is_cat"] == 0) & (x.index >= "2025-11-01") & big_fb, label="fb_sign_agree", note="ex post")

# P4 Q1 typical path: gap at 18:00, extension/reversal at the Tokyo/Seoul open, drift into 03:00
g20 = x["abs_gap"] >= 20
rep("P4a", "big 18:00 gap -> extreme at Tokyo open bar", "[k0 open] |gap|>=20 -> any_at_tko", g20, label="any_at_tko")
rep("P4b", "big 18:00 gap -> extreme at 18:00", "[k0 open] |gap|>=20 -> any_first_bar", g20, label="any_first_bar")
rep("P4c", "big 18:00 gap -> drift into Europe (last bar extreme)", "[k0 open] |gap|>=20 -> any_last_bar", g20, label="any_last_bar")
rep("P4d", "big 18:00 gap -> low early", "[k0 open] |gap|>=20 -> lo_after_tko", g20, label="lo_after_tko")
rep("P4e", "big 18:00 gap -> high early", "[k0 open] |gap|>=20 -> hi_after_tko", g20, label="hi_after_tko")
gu = x["gap_open_bp"] >= 20; gd = x["gap_open_bp"] <= -20
rep("P4f", "gap UP -> low in first bar (gap holds)", "gap>=+20 -> low_in_first_bar", gu, label="low_in_first_bar")
rep("P4g", "gap UP -> high in first bar (gap fades)", "gap>=+20 -> high_in_first_bar", gu, label="high_in_first_bar")
rep("P4h", "gap DOWN -> high in first bar (gap holds)", "gap<=-20 -> high_in_first_bar", gd, label="high_in_first_bar")
rep("P4i", "gap DOWN -> low in first bar (gap fades)", "gap<=-20 -> low_in_first_bar", gd, label="low_in_first_bar")
rep("P4j", "gap UP -> asia_up", "gap>=+20 -> asia_up", gu, label="asia_up")
rep("P4k", "gap DOWN -> asia_up", "gap<=-20 -> asia_up", gd, label="asia_up")

# P5 Q2#7 / Q3#7: Kospi/Seoul open is the inflection -> 18:00 proxy |kospi_ret|>=3% (yesterday's Kospi), |sox_ret|>=3%
kb = x["abs_kospi"] >= 3
rep("P5a", "big prior Kospi day -> extreme at Tokyo/Seoul open bar", "|kospi_ret|>=3% -> any_at_tko", kb, label="any_at_tko")
rep("P5b", "big prior Kospi day -> high at Tokyo open", "|kospi_ret|>=3% -> high_at_tokyo_open", kb, label="high_at_tokyo_open")
rep("P5c", "big prior Kospi day -> low at Tokyo open", "|kospi_ret|>=3% -> low_at_tokyo_open", kb, label="low_at_tokyo_open")
rep("P5d", "big prior Kospi day -> no late low", "|kospi_ret|>=3% -> low_in_last_bar", kb, label="low_in_last_bar")
rep("P5e", "big prior Kospi day -> range", "|kospi_ret|>=3% -> rng_bp", kb, col="rng_bp")
rep("P5f", "big prior Kospi day -> cont", "|kospi_ret|>=3% -> cont", kb, label="cont")
rep("P5g", "big US chip day -> extreme at Tokyo/Seoul open", "|sox_ret|>=3% -> any_at_tko", x["abs_sox"] >= 3, label="any_at_tko")
rep("P5h", "big US chip day & small prior Kospi -> extreme at Tokyo open", "|sox|>=3% & |kospi|<1.5% -> any_at_tko", (x["abs_sox"] >= 3) & (x["abs_kospi"] < 1.5), label="any_at_tko")
rep("P5i", "big prior Asia (NQ) session -> extreme at Tokyo open", "|prior_asia_ret|>=80bp -> any_at_tko", x["abs_prior_asia"] >= 80, label="any_at_tko")
rep("P5j", "Tokyo-open extremes, 2026-10-12 onward (narrative: Seoul open is the pivot post-Oct 12)", "date>=2026-10-12 -> any_at_tko", x.index >= "2026-10-12", label="any_at_tko", note="n small, regime claim")

# P6 Q2#2 / Q3#1: RTH <= -1.5% -> Asia positive; capitulation: low at/by Tokyo open then V
d15 = x["rth_ret_bp"] <= -150; d20 = x["rth_ret_bp"] <= -200
rep("P6a", "RTH<=-1.5% -> Asia positive", "rth<=-150 -> asia_up", d15, label="asia_up")
rep("P6b", "RTH<=-2% -> Asia positive", "rth<=-200 -> asia_up", d20, label="asia_up")
rep("P6c", "RTH<=-1.5% -> low by Tokyo open", "rth<=-150 -> low_by_tokyo_open", d15, label="low_by_tokyo_open")
rep("P6d", "RTH<=-1.5% -> low by Tokyo open & close upper", "rth<=-150 -> lo_by_tko_and_close_hi", d15, label="lo_by_tko_and_close_hi")
rep("P6e", "RTH<=-1.5% -> close_loc", "rth<=-150 -> close_loc", d15, col="close_loc")
rep("P6f", "RTH<=-1.5% -> low below RTH low", "rth<=-150 -> low_below_rth_low", d15, label="low_below_rth_low")
rep("P6g", "RTH<=-1.5% -> high above RTH high", "rth<=-150 -> high_above_rth_high", d15, label="high_above_rth_high")
rep("P6h", "RTH<=-1.5% -> rally after low (bp)", "rth<=-150 -> rally_after_lo_bp", d15, col="rally_after_lo_bp")
rep("P6i", "RTH<=-1.5% -> high before low", "rth<=-150 -> hi_first", d15, label="hi_first")
rep("P6j", "RTH>=+1.5% -> Asia positive", "rth>=+150 -> asia_up", x["rth_ret_bp"] >= 150, label="asia_up")
rep("P6k", "RTH>=+1.5% -> high by Tokyo open & close lower", "rth>=+150 -> hi_by_tko_and_close_lo", x["rth_ret_bp"] >= 150, label="hi_by_tko_and_close_lo")

# P7 Q3#2: moderate down day (-0.3..-1.3) -> continuation lower
md = (x["rth_ret_bp"] <= -30) & (x["rth_ret_bp"] >= -130)
rep("P7a", "moderate down day -> continuation", "-130<=rth<=-30 -> cont", md, label="cont")
rep("P7b", "moderate down day -> asia_up", "-130<=rth<=-30 -> asia_up", md, label="asia_up")
rep("P7c", "moderate down day -> low in last bar", "-130<=rth<=-30 -> low_in_last_bar", md, label="low_in_last_bar")
rep("P7d", "moderate down day -> low below RTH low", "-130<=rth<=-30 -> low_below_rth_low", md, label="low_below_rth_low")
rep("P7e", "moderate down day -> high above RTH high", "-130<=rth<=-30 -> high_above_rth_high", md, label="high_above_rth_high")
rep("P7f", "moderate down day -> reversal close (close_loc>=0.7)", "-130<=rth<=-30 -> revers_close", md, label="revers_close")

# P8 Q3#4 / Q4#9 / Q2#4 / Q1#7: FOMC nights: overnight sign != RTH sign; range not big
f = x["fomc_today"] == 1
rep("P8a", "FOMC night: sign != RTH", "fomc_today -> cont", f, label="cont")
rep("P8b", "FOMC night: range", "fomc_today -> rng_bp", f, col="rng_bp")
rep("P8c", "FOMC night: extreme at 18:00", "fomc_today -> any_first_bar", f, label="any_first_bar")
rep("P8d", "FOMC night: late extreme", "fomc_today -> any_last_bar", f, label="any_last_bar")
rep("P8e", "FOMC night: high by Tokyo open", "fomc_today -> high_by_tokyo_open", f, label="high_by_tokyo_open")

# P9 Q4#8 / Q1#7: pre-CPI/NFP nights not compressed; scheduled US macro flat
t1 = x["tier1_data_tomorrow"] == 1
rep("P9a", "pre-tier1 night range", "tier1_data_tomorrow -> rng_bp", t1, col="rng_bp")
rep("P9b", "pre-tier1 night |asia_ret|", "tier1_data_tomorrow -> |asia_ret|", t1, col="abs_asia_ret")
rep("P9c", "pre-tier1 night: low after Tokyo open", "tier1_data_tomorrow -> lo_post_tko", t1, label="lo_post_tko")
rep("P9d", "pre-tier1 night: high after Tokyo open", "tier1_data_tomorrow -> hi_post_tko", t1, label="hi_post_tko")
rep("P9e", "pre-tier1 night: cont", "tier1_data_tomorrow -> cont", t1, label="cont")
rep("P9f", "post-tier1 (data today) night range", "tier1_data_today -> rng_bp", x["tier1_data_today"] == 1, col="rng_bp")

# P10 Q4#10 / Q2#11: thin-holiday sessions
h = (x["holiday_tomorrow"] == 1) | (x["pre_holiday"] == 1)
rep("P10a", "thin holiday range", "holiday_tomorrow|pre_holiday -> rng_bp", h, col="rng_bp", note="n small")
rep("P10b", "thin holiday |asia_ret|", "holiday_tomorrow|pre_holiday -> |asia_ret|", h, col="abs_asia_ret", note="n small")

# P11 Q3#6 / Q2#10: range expansion calendar-bound (quarter-end, megacap earnings)
rep("P11a", "quarter-end range", "quarter_end -> rng_bp", x["quarter_end"] == 1, col="rng_bp", note="n small")
rep("P11b", "quarter-end late extreme", "quarter_end -> any_last_bar", x["quarter_end"] == 1, label="any_last_bar", note="n small")
rep("P11c", "month-end range", "month_end -> rng_bp", x["month_end"] == 1, col="rng_bp", note="n small")
rep("P11d", "megacap range", "megacap_tonight -> rng_bp", m, col="rng_bp")
rep("P11e", "roll/witching/opex range", "roll|witching|opex_today -> rng_bp", (x["roll_today"] == 1) | (x["witching_today"] == 1) | (x["opex_today"] == 1), col="rng_bp")

# P12 Q4#6 / Q3#9 / Q1#7: BoJ nights (decision ~22:00-23:30 ET = bars k=4/5)
b = x["boj_tonight"] == 1
rep("P12a", "BoJ night: extreme in the 22:00/23:00 ET bars", "boj_tonight -> any_at_k45", b, label="any_at_k45", note="n=19")
rep("P12b", "BoJ night: range", "boj_tonight -> rng_bp", b, col="rng_bp", note="n=19")
rep("P12c", "BoJ night: asia_up", "boj_tonight -> asia_up", b, label="asia_up", note="n=19")
rep("P12d", "BoJ night: first-bar extreme", "boj_tonight -> any_first_bar", b, label="any_first_bar", note="n=19")
rep("P12e", "yen move >=0.8% -> range", "|usdjpy_chg|>=0.8% -> rng_bp", x["abs_yen"] >= 0.8, col="rng_bp")
rep("P12f", "yen move >=0.8% -> late extreme", "|usdjpy_chg|>=0.8% -> any_last_bar", x["abs_yen"] >= 0.8, label="any_last_bar")
rep("P12g", "jp_data_tonight (18:30/19:30 ET) -> extreme in bars 0/1", "jp_data_tonight -> hi_at_k01|lo_at_k01", x["jp_data_tonight"] == 1, label="any_first_bar", note="n=38")
rep("P12h", "jp_data_tonight -> late extreme", "jp_data_tonight -> any_last_bar", x["jp_data_tonight"] == 1, label="any_last_bar", note="n=38")

# P13 Q2#1: mean reversion after US-origin shock; continuation after Asia-origin shock
us_shock = (x["abs_rth"] >= 100) & (x["abs_kospi"] < 1.5)
as_shock = (x["abs_kospi"] >= 3)
rep("P13a", "US-origin shock (|rth|>=1%, |kospi|<1.5%) -> cont", "US-origin -> cont", us_shock, label="cont")
rep("P13b", "Asia-origin (|kospi|>=3%) -> cont", "Asia-origin -> cont", as_shock, label="cont")
rep("P13c", "Asia-origin & same-sign rth (|kospi|>=3% & sign kospi == sign rth) -> cont", "Asia-origin aligned -> cont", as_shock & (np.sign(x["kospi_ret"]) == np.sign(x["rth_ret_bp"])), label="cont")
rep("P13d", "Asia-origin -> trend close", "Asia-origin -> trend_close", as_shock, label="trend_close")

# P14 Q3#3: regime flip: from late Sep 2026 Asia faded every up day
rep("P14a", "late-2026 up days faded", "date>=2026-09-25 & rth>0 -> cont", (x.index >= "2026-09-25") & (x["rth_ret_bp"] > 0), label="cont", note="regime, n small")
rep("P14b", "up days overall", "rth>0 -> cont", x["rth_ret_bp"] > 0, label="cont")

# P15 Q4#3: post-print overnight peak not held -> megacap night with asia up: high in last bar?
rep("P15a", "megacap night & asia up -> high in last bar (peak held into 03:00)", "megacap & asia_up -> high_in_last_bar", m & (x["asia_ret_bp"] > 0), label="high_in_last_bar")
rep("P15b", "all nights & asia up -> high in last bar", "asia_up -> high_in_last_bar", x["asia_ret_bp"] > 0, label="high_in_last_bar")
rep("P15c", "megacap night -> drop after high (bp)", "megacap -> drop_after_hi_bp", m, col="drop_after_hi_bp")

# P17 late trend into Europe: who predicts last-bar extremes?
for nm, cnd in [("vix>=25", x["vix"] >= 25), ("vix<15", x["vix"] < 15), ("|kospi|>=3%", kb), ("rba_tonight", x["rba_tonight"] == 1),
                ("quiet", (x["megacap_earnings_tonight"] == 0) & (x["sunday_open"] == 0) & (x["fomc_today"] == 0) & (x["boj_tonight"] == 0) & (x["abs_rth"] < 50) & (x["abs_post"] < 8) & (x["abs_kospi"] < 1.5) & (x["tier1_data_today"] == 0)),
                ("|post|<8 & no megacap", (x["abs_post"] < 8) & (m == 0)), ("|post|>=15 | megacap", hd & (x["sunday_open"] == 0) & (x["fomc_today"] == 0))]:
    rep("P17", "late trend into Europe (extreme in last bar)", f"{nm} -> any_last_bar", cnd, label="any_last_bar")
    rep("P17", "late trend into Europe (extreme in last 2 bars)", f"{nm} -> hi_last2|lo_last2", cnd, label="any_last_bar")

# P19 Q4#1: AI-capex RTH selloffs -> Asia continuation with Tokyo/Seoul over-reacting -> proxy sox<=-3% & rth<0
sx = (x["sox_ret"] <= -0.03) & (x["rth_ret_bp"] < 0)
rep("P19a", "chip-led down day -> cont", "sox<=-3% & rth<0 -> cont", sx, label="cont")
rep("P19b", "chip-led down day -> low below RTH low", "sox<=-3% & rth<0 -> low_below_rth_low", sx, label="low_below_rth_low")
rep("P19c", "chip-led down day -> low in last bar", "sox<=-3% & rth<0 -> low_in_last_bar", sx, label="low_in_last_bar")
rep("P19d", "chip-led down day -> low at Tokyo open", "sox<=-3% & rth<0 -> low_at_tokyo_open", sx, label="low_at_tokyo_open")
rep("P19e", "chip-led down day -> rally after low", "sox<=-3% & rth<0 -> rally_after_lo_bp", sx, col="rally_after_lo_bp")
rep("P19f", "chip-led down day -> high before low", "sox<=-3% & rth<0 -> hi_first", sx, label="hi_first")

tab = pd.DataFrame(res)
tab.to_csv(f"{OUT}/q3_pattern_tests.csv", index=False)
pd.set_option("display.width", 300, "display.max_columns", 40, "display.max_rows", 500)
cols = ["pid", "test", "n", "rate", "base_rate", "ci_lo", "ci_hi", "p_binom", "H1_n", "H1_rate", "H1_base", "H2_n", "H2_rate", "H2_base", "note"]
print(tab[tab.kind == "rate"][cols].round(3).to_string())
cols2 = ["pid", "test", "n", "value", "base_value", "ci_lo", "ci_hi", "p_mw", "H1_n", "H1_value", "H1_base", "H2_n", "H2_value", "H2_base", "note"]
print(tab[tab.kind == "cont"][cols2].round(2).to_string())
print(tab[tab.kind == "corr"][["pid", "test", "n", "value", "p_mw"]].round(3).to_string())
print("n pattern tests:", len(tab))
