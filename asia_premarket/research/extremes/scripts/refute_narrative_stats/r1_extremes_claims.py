"""Recompute F2..F9, F14 (18:00-knowable conditions on the extremes table) for NQ and ES."""
import sys
sys.path.insert(0, "research/extremes/scripts/refute_narrative_stats")
import numpy as np, pandas as pd
from scipy import stats
from common_r import *

pd.set_option("display.width", 250, "display.max_columns", 50)
X = {s: load_x(s) for s in ("NQ", "ES")}
x = X["NQ"]; e = X["ES"]
print("NQ n=", len(x), " ES n=", len(e), " NQ H1/H2:", x.half.value_counts().to_dict())

# ------------------------------------------------------------------ F2 Sunday
print("\n================ F2 sunday_open")
s = x.sunday_open == 1
for lab in ["low_in_first_bar", "high_in_first_bar", "lo_after_tko", "hi_after_tko", "lo_by_tko_and_close_hi", "trend_close", "asia_up", "cont"]:
    rate_vs_rest(x, s, lab, "NQ sunday")
cont_vs_rest(x, s, "rng_bp", "NQ sunday"); cont_vs_rest(x, s, "abs_gap", "NQ sunday")
print(" -- ES")
for lab in ["low_in_first_bar", "high_in_first_bar", "lo_after_tko", "lo_by_tko_and_close_hi", "asia_up"]:
    rate_vs_rest(e, e.sunday_open == 1, lab, "ES sunday")
# is the Sunday low-in-bar-0 effect just the gap? split Sunday by gap sign and by |gap|
print(" -- Sunday low_in_first_bar by gap sign / size (NQ)")
for nm, c in [("sun & gap<0", s & (x.gap_open_bp < 0)), ("sun & gap>=0", s & (x.gap_open_bp >= 0)), ("sun & |gap|>=20", s & (x.abs_gap >= 20)), ("sun & |gap|<20", s & (x.abs_gap < 20)),
              ("weekday & |gap|>=20", (~s) & (x.abs_gap >= 20)), ("weekday & gap<0", (~s) & (x.gap_open_bp < 0))]:
    sub = x[c]; print(f"    {nm:22s} n={len(sub)} low_in_first_bar={sub.low_in_first_bar.mean():.3f} high_in_first_bar={sub.high_in_first_bar.mean():.3f} asia_up={sub.asia_up.mean():.3f}")
# full-session Sundays only (5 Sundays have 6-7 bars)
print("  Sunday n_bars:", x[s].n_bars.value_counts().to_dict())
rate_vs_rest(x[x.n_bars == 9], (x[x.n_bars == 9].sunday_open == 1), "low_in_first_bar", "NQ sunday 9-bar only")
# panel: P(low_done|k) for sunday vs rest
p = load_p("NQ"); p = p.merge(x[["sunday_open", "abs_post", "megacap_earnings_tonight", "abs_kospi", "rth_ret_bp", "fomc_today", "tier1_data_tomorrow"]], left_on="date", right_index=True)
p9 = p[p.n_bars == 9]
for k in [0, 1, 2]:
    a = p9[(p9.k == k) & (p9.sunday_open == 1)].low_done; b = p9[(p9.k == k) & (p9.sunday_open == 0)].low_done
    print(f"  P(low_done|k={k}) sunday={a.mean():.3f} (n={len(a)}) rest={b.mean():.3f} p_fisher={fisher(int(a.sum()), len(a), int(b.sum()), len(b)):.4f}")
for k in [2, 3, 4]:
    a = p9[(p9.k == k) & (p9.sunday_open == 1) & (p9.bars_since_lo >= 2)].low_done; b = p9[(p9.k == k) & (p9.sunday_open == 0) & (p9.bars_since_lo >= 2)].low_done
    print(f"  P(low_done|k={k},bsl>=2) sunday={a.mean():.3f} (n={len(a)}) rest={b.mean():.3f} p={fisher(int(a.sum()), len(a), int(b.sum()), len(b)):.4f}")

# ------------------------------------------------------------------ F3 AH print
print("\n================ F3 after-hours print")
m = x.megacap_earnings_tonight == 1; pp = x.abs_post >= 25
print("  overlap megacap & |post|>=25:", int((m & pp).sum()), " megacap n=", int(m.sum()), " |post|>=25 n=", int(pp.sum()))
for nm, c in [("megacap", m), ("|post|>=25", pp)]:
    for col in ["first_bar_rng_bp", "rng_bp"]:
        cont_vs_rest(x, c, col, f"NQ {nm}")
    for lab in ["any_last_bar", "high_in_last_bar", "low_in_last_bar", "high_in_first_bar", "low_in_first_bar", "any_first_bar", "mid_close", "asia_up"]:
        rate_vs_rest(x, c, lab, f"NQ {nm}")
# up-night high_in_last_bar
up = x[x.asia_ret_bp > 0]
for nm, c in [("megacap", up.megacap_earnings_tonight == 1), ("|post|>=25", up.abs_post >= 25)]:
    rate_vs_rest(up, c, "high_in_last_bar", f"NQ up-nights {nm}")
dn = x[x.asia_ret_bp < 0]
for nm, c in [("megacap", dn.megacap_earnings_tonight == 1), ("|post|>=25", dn.abs_post >= 25)]:
    rate_vs_rest(dn, c, "low_in_last_bar", f"NQ down-nights {nm}")
# sign of post_ret
for nm, c in [("post>=+15", x.post_ret >= 0.0015), ("post<=-15", x.post_ret <= -0.0015)]:
    for lab in ["asia_up", "low_in_first_bar", "high_in_first_bar", "cont"]:
        rate_vs_rest(x, c, lab, f"NQ {nm}")
# panel bars_since_hi>=2
for nm, c in [("megacap", p9.megacap_earnings_tonight == 1), ("|post|>=25", p9.abs_post >= 25)]:
    r = []
    for k in range(2, 8):
        a = p9[(p9.k == k) & c & (p9.bars_since_hi >= 2)].high_done; b = p9[(p9.k == k) & (~c) & (p9.bars_since_hi >= 2)].high_done
        r.append(f"k{k}: {a.mean():.2f}(n={len(a)}) vs {b.mean():.2f} p={fisher(int(a.sum()), len(a), int(b.sum()), len(b)):.3f}")
    print(f"  P(high_done|k,bsh>=2) {nm}: ", " | ".join(r))
print(" -- ES")
for nm, c in [("megacap", e.megacap_earnings_tonight == 1), ("|post|>=25", e.abs_post >= 25)]:
    cont_vs_rest(e, c, "first_bar_rng_bp", f"ES {nm}"); cont_vs_rest(e, c, "rng_bp", f"ES {nm}")
    for lab in ["any_last_bar", "high_in_last_bar", "high_in_first_bar"]:
        rate_vs_rest(e, c, lab, f"ES {nm}")
eup = e[e.asia_ret_bp > 0]
rate_vs_rest(eup, eup.megacap_earnings_tonight == 1, "high_in_last_bar", "ES up-nights megacap")
rate_vs_rest(eup, eup.abs_post >= 25, "high_in_last_bar", "ES up-nights |post|>=25")

# ------------------------------------------------------------------ F4 kospi
print("\n================ F4 |kospi|>=3%")
kb = x.abs_kospi >= 3
print("  kospi n by half:", x[kb].half.value_counts().to_dict())
for lab in ["any_at_tko", "low_at_tokyo_open", "high_at_tokyo_open", "low_in_last_bar", "high_in_last_bar", "cont", "any_first_bar", "any_last_bar"]:
    rate_vs_rest(x, kb, lab, "NQ kospi>=3")
cont_vs_rest(x, kb, "rng_bp", "NQ kospi>=3")
# regime control: within H2 only, and vs an H2 base; also vs date>=2026-01-01 base
h2 = x[x.half == "H2"]
rate_vs_rest(h2, h2.abs_kospi >= 3, "any_at_tko", "NQ H2-only kospi>=3")
w26 = x[x.index >= "2026-01-01"]
print("  2026-only:")
rate_vs_rest(w26, w26.abs_kospi >= 3, "any_at_tko", "NQ 2026-only kospi>=3")
rate_vs_rest(w26, w26.abs_kospi >= 3, "low_in_last_bar", "NQ 2026-only kospi>=3")
# any_at_tko by year / by dst
print("  any_at_tko by half-year:", x.groupby(x.index.to_period("Q"))["any_at_tko"].agg(["mean", "size"]).round(2).T.to_dict())
print("  any_at_tko by is_dst:", x.groupby("is_dst")["any_at_tko"].agg(["mean", "size"]).round(3).to_dict())
print("  kospi>=3 by is_dst:", x[kb].is_dst.value_counts().to_dict(), " all:", x.is_dst.value_counts().to_dict())
# dst-matched: any_at_tko among kospi nights vs rest within each dst
for d in (0, 1):
    xd = x[x.is_dst == d]; rate_vs_rest(xd, xd.abs_kospi >= 3, "any_at_tko", f"NQ dst={d} kospi>=3")
# vs other 'big move' proxies: |sox|>=3, |rth|>=100: does kospi add beyond general vol?
for nm, c in [("|sox|>=3", x.abs_sox >= 3), ("|sox|>=3&|kospi|<1.5", (x.abs_sox >= 3) & (x.abs_kospi < 1.5)), ("|kospi|>=3&|sox|<3", kb & (x.abs_sox < 3)), ("|rth|>=100", x.abs_rth >= 100)]:
    rate_vs_rest(x, c, "any_at_tko", f"NQ {nm}")
# logistic-ish check: is any_at_tko related to kospi beyond H2 dummy? simple stratified (CMH-like) via H2 strata
print(" -- ES")
ek = e.abs_kospi >= 3
for lab in ["any_at_tko", "low_in_last_bar", "low_at_tokyo_open", "high_at_tokyo_open"]:
    rate_vs_rest(e, ek, lab, "ES kospi>=3")
cont_vs_rest(e, ek, "rng_bp", "ES kospi>=3")
eh2 = e[e.half == "H2"]; rate_vs_rest(eh2, eh2.abs_kospi >= 3, "any_at_tko", "ES H2-only kospi>=3")

# ------------------------------------------------------------------ F5 rth<=-150
print("\n================ F5 rth<=-150")
d15 = x.rth_ret_bp <= -150
for lab in ["low_below_rth_low", "high_above_rth_high", "asia_up", "low_by_tokyo_open", "close_hi70", "cont"]:
    rate_vs_rest(x, d15, lab, "NQ rth<=-150")
for col in ["rally_after_lo_bp", "rng_bp", "close_loc", "drop_after_hi_bp"]:
    cont_vs_rest(x, d15, col, "NQ rth<=-150")
# mechanical check: distance from 17:00 close to RTH low / high on these nights
x["dist_to_rth_low_bp"] = (x.lvl_rth_low / x.ref_close - 1) * 1e4; x["dist_to_rth_high_bp"] = (x.lvl_rth_high / x.ref_close - 1) * 1e4
print("  median dist ref_close->RTH low (bp): rth<=-150:", x[d15].dist_to_rth_low_bp.median().round(1), " all:", x.dist_to_rth_low_bp.median().round(1))
print("  median dist ref_close->RTH high (bp): rth<=-150:", x[d15].dist_to_rth_high_bp.median().round(1), " all:", x.dist_to_rth_high_bp.median().round(1))
print("  min dist to RTH high on rth<=-150 nights:", x[d15].dist_to_rth_high_bp.min().round(1), " max hi_bp on those nights:", x[d15].hi_bp.max().round(1))
# is low_below_rth_low just 'close is near the RTH low'? compare with nights where dist_to_rth_low is similarly small but rth not <= -150
near = (x.dist_to_rth_low_bp > -40) & (x.rth_ret_bp > -150)
print(f"  control: dist_to_rth_low > -40bp & rth>-150: n={near.sum()} low_below_rth_low={x[near].low_below_rth_low.mean():.3f}; rth<=-150 nights' median dist={x[d15].dist_to_rth_low_bp.median():.1f}")
rate_vs_rest(x, x.rth_ret_bp <= -200, "asia_up", "NQ rth<=-200")
sx = (x.sox_ret <= -0.03) & (x.rth_ret_bp < 0)
for lab in ["low_below_rth_low", "asia_up", "low_at_tokyo_open"]:
    rate_vs_rest(x, sx, lab, "NQ sox<=-3&rth<0")
cont_vs_rest(x, sx, "rally_after_lo_bp", "NQ sox<=-3&rth<0")
print(" -- ES")
ed = e.rth_ret_bp <= -150
for lab in ["low_below_rth_low", "high_above_rth_high", "asia_up"]:
    rate_vs_rest(e, ed, lab, "ES rth<=-150")
cont_vs_rest(e, ed, "rally_after_lo_bp", "ES rth<=-150")

# ------------------------------------------------------------------ F6 moderate
print("\n================ F6 moderate RTH move")
md = (x.rth_ret_bp <= -30) & (x.rth_ret_bp >= -130); mu = (x.rth_ret_bp >= 30) & (x.rth_ret_bp <= 130)
for nm, c in [("mod down", md), ("mod up", mu)]:
    for lab in ["low_below_rth_low", "high_above_rth_high", "close_hi70", "close_lo30", "cont", "asia_up"]:
        rate_vs_rest(x, c, lab, f"NQ {nm}")
# mechanical control: distance to the RTH extreme in the direction of the move
print("  mod down: median dist to RTH low", x[md].dist_to_rth_low_bp.median().round(1), " to RTH high", x[md].dist_to_rth_high_bp.median().round(1))
print("  mod up:   median dist to RTH low", x[mu].dist_to_rth_low_bp.median().round(1), " to RTH high", x[mu].dist_to_rth_high_bp.median().round(1))
# does rth sign add anything beyond distance? bin by dist_to_rth_low in (-30,0] and compare down vs up days
for lo_, hi_ in [(-20, 0), (-40, -20), (-80, -40)]:
    c = (x.dist_to_rth_low_bp > lo_) & (x.dist_to_rth_low_bp <= hi_)
    a = x[c & (x.rth_ret_bp < 0)]; b = x[c & (x.rth_ret_bp > 0)]
    print(f"    dist_to_rth_low in ({lo_},{hi_}]: down-days n={len(a)} low_below={a.low_below_rth_low.mean():.2f} | up-days n={len(b)} low_below={b.low_below_rth_low.mean():.2f}")
print(" -- ES")
emd = (e.rth_ret_bp <= -30) & (e.rth_ret_bp >= -130); emu = (e.rth_ret_bp >= 30) & (e.rth_ret_bp <= 130)
for nm, c in [("mod down", emd), ("mod up", emu)]:
    for lab in ["low_below_rth_low", "high_above_rth_high", "close_hi70", "cont"]:
        rate_vs_rest(e, c, lab, f"ES {nm}")

# ------------------------------------------------------------------ F7 FOMC
print("\n================ F7 fomc_today")
f = x.fomc_today == 1
print("  fomc dates:", [d.strftime("%Y-%m-%d") for d in x[f].index], " n_bars:", x[f].n_bars.value_counts().to_dict())
cont_vs_rest(x, f, "rng_bp", "NQ fomc"); cont_vs_rest(x, f, "first_bar_rng_bp", "NQ fomc")
for lab in ["any_first_bar", "any_last_bar", "low_in_first_bar", "high_in_first_bar", "cont", "asia_up"]:
    rate_vs_rest(x, f, lab, "NQ fomc")
# range relative to ex-ante median (controls for vol regime)
x["rng_rel"] = x.rng_bp / (x.asia_rng_med20 * 1e4)
cont_vs_rest(x, f, "rng_rel", "NQ fomc")
# vs |post|>=25 control: fomc nights' post_ret
print("  fomc nights |post_ret| bp:", x[f].abs_post.round(0).tolist())
print("  fomc nights with |post|<15:", int((f & (x.abs_post < 15)).sum()), "-> any_first_bar", x[f & (x.abs_post < 15)].any_first_bar.mean().round(2))
print(" -- ES")
ef = e.fomc_today == 1
cont_vs_rest(e, ef, "rng_bp", "ES fomc")
for lab in ["any_first_bar", "any_last_bar", "low_in_first_bar", "cont"]:
    rate_vs_rest(e, ef, lab, "ES fomc")

# ------------------------------------------------------------------ F8 holiday
print("\n================ F8 holiday")
h = (x.holiday_tomorrow == 1) | (x.pre_holiday == 1)
print(x[h][["n_bars", "rng_bp", "abs_ret", "holiday_tomorrow", "pre_holiday", "half"]].to_string())
cont_vs_rest(x, h, "rng_bp", "NQ holiday (all n_bars)")
cont_vs_rest(x, h, "abs_ret", "NQ holiday (all n_bars)")
# n_bars-matched: holiday 9-bar sessions vs other 9-bar sessions; holiday 6-bar sessions vs run_rng at close of k=5 on 9-bar sessions
x9 = x[x.n_bars == 9]; cont_vs_rest(x9, (x9.holiday_tomorrow == 1) | (x9.pre_holiday == 1), "rng_bp", "NQ holiday 9-bar only")
cont_vs_rest(x9, (x9.holiday_tomorrow == 1) | (x9.pre_holiday == 1), "rng_rel", "NQ holiday 9-bar only")
r5 = p9[p9.k == 5].set_index("date")["run_rng_bp"]
h6 = x[h & (x.n_bars == 6)]
print(f"  6-bar holiday sessions (n={len(h6)}): median rng={h6.rng_bp.median():.1f}; 9-bar sessions' running range at close of k=5 (6 bars): median={r5.median():.1f}; "
      f"MW p={stats.mannwhitneyu(h6.rng_bp, r5, alternative='two-sided').pvalue:.3f}")
# sunday 6-bar sessions as another control
s6 = x[(x.sunday_open == 1) & (x.n_bars < 9)]; print(f"  other short sessions (Sunday 6/7-bar, n={len(s6)}): median rng={s6.rng_bp.median():.1f}")
# rng_rel on all holiday sessions, vs the matched 6-bar running range relative
x["rng_rel6"] = np.nan
x.loc[h & (x.n_bars == 6), "rng_rel6"] = x.loc[h & (x.n_bars == 6)].rng_rel
r5rel = (r5 / (x9.asia_rng_med20 * 1e4)).dropna()
print(f"  rng_rel: holiday 9-bar {x9[(x9.holiday_tomorrow == 1) | (x9.pre_holiday == 1)].rng_rel.median():.2f} (n={int(((x9.holiday_tomorrow == 1) | (x9.pre_holiday == 1)).sum())}) vs all 9-bar {x9.rng_rel.median():.2f}; "
      f"holiday 6-bar {x.loc[h & (x.n_bars == 6)].rng_rel.median():.2f} (n={int((h & (x.n_bars == 6)).sum())}) vs 9-bar run_rng@k5 rel {r5rel.median():.2f}")
print(" -- ES")
eh = (e.holiday_tomorrow == 1) | (e.pre_holiday == 1)
print("  ES holiday n_bars:", e[eh].n_bars.value_counts().to_dict())
cont_vs_rest(e, eh, "rng_bp", "ES holiday (all)")
e9 = e[e.n_bars == 9]; cont_vs_rest(e9, (e9.holiday_tomorrow == 1) | (e9.pre_holiday == 1), "rng_bp", "ES holiday 9-bar only")

# ------------------------------------------------------------------ F9 tier1 tomorrow
print("\n================ F9 tier1_data_tomorrow")
t1 = x.tier1_data_tomorrow == 1
cont_vs_rest(x, t1, "rng_bp", "NQ t1 tomorrow"); cont_vs_rest(x, t1, "abs_ret", "NQ t1 tomorrow"); cont_vs_rest(x, t1, "rng_rel", "NQ t1 tomorrow")
for lab in ["lo_post_tko", "lo_after_tko", "hi_post_tko", "cont", "revers_close", "low_in_last_bar"]:
    rate_vs_rest(x, t1, lab, "NQ t1 tomorrow")
cont_vs_rest(x, x.tier1_data_today == 1, "rng_bp", "NQ t1 today"); cont_vs_rest(x, x.tier1_data_today == 1, "rng_rel", "NQ t1 today")
for k in [2, 3, 4]:
    a = p9[(p9.k == k) & (p9.tier1_data_tomorrow == 1)].low_done; b = p9[(p9.k == k) & (p9.tier1_data_tomorrow == 0)].low_done
    print(f"  P(low_done|k={k}) t1tom={a.mean():.3f} (n={len(a)}) rest={b.mean():.3f} p={fisher(int(a.sum()), len(a), int(b.sum()), len(b)):.4f}")
print(" -- ES")
et = e.tier1_data_tomorrow == 1
cont_vs_rest(e, et, "rng_bp", "ES t1 tomorrow")
for lab in ["lo_post_tko", "lo_after_tko"]:
    rate_vs_rest(e, et, lab, "ES t1 tomorrow")

# ------------------------------------------------------------------ F14 direction nulls
print("\n================ F14 direction")
conds = {"megacap": m, "sunday": s, "fomc": f, "mod down": md, "kospi>=3": kb, "US shock": (x.abs_rth >= 100) & (x.abs_kospi < 1.5),
         "chip-led down": sx, "rth>0": x.rth_ret_bp > 0, "boj": x.boj_tonight == 1, "late26 up": (x.index >= "2026-09-25") & (x.rth_ret_bp > 0),
         "rth<=-150": d15, "rth<=-200": x.rth_ret_bp <= -200}
for nm, c in conds.items():
    rate_vs_rest(x, c, "cont", f"NQ {nm}")
for nm, c in [("rth<=-150", d15), ("rth<=-200", x.rth_ret_bp <= -200)]:
    rate_vs_rest(x, c, "asia_up", f"NQ {nm}")
for nm, msk in [("sunday", s), ("weekday", ~s)]:
    r_, p_ = stats.spearmanr(x[msk].rth_ret_bp, x[msk].asia_ret_bp); print(f"  spearman(rth, asia) {nm}: r={r_:.3f} p={p_:.3f} n={msk.sum()}")
# smallest p among n>=30 across the direction conditions (how many comparisons)
print("  comparisons here:", len(conds) + 2)
