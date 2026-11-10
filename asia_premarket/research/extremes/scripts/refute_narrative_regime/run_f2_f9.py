"""F2..F9 and F14: 18:00-knowable flags on the extremes table, recomputed by quarter / regime / weekday / leave-5-out."""
import sys
sys.path.insert(0, "research/extremes/scripts/refute_narrative_regime")
import numpy as np, pandas as pd
from robust import *

pd.set_option("display.width", 300, "display.max_columns", 50, "display.max_rows", 500)
x = load_extremes("NQ")
xa = load_extremes("NQ", drop_artefacts=False)
print("NQ sessions (artefacts excluded):", len(x), " included:", len(xa))
print("quarter sizes:", x.groupby("quarter").size().to_dict())
for rg, (a, b) in REGIMES.items():
    print(f"regime {rg}: {a}..{b} -> {int(in_regime(x.index, rg).sum())} sessions")
res = []

def R(x, cond, label, name, **kw):
    r = rate_robust(x, cond, label, name, **kw); res.append(r); return r

def C(x, cond, col, name, **kw):
    r = cont_robust(x, cond, col, name, **kw); res.append(r); return r

# ---------------- F2 Sunday ----------------
print("\n" + "=" * 100 + "\nF2 sunday_open")
s = x.sunday_open == 1
for lab in ["low_in_first_bar", "lo_after_tko", "lo_by_tko_and_close_hi", "high_in_first_bar", "trend_close", "asia_up"]:
    R(x, s, lab, "F2 sunday_open")
C(x, s, "rng_bp", "F2 sunday_open")
# Iran-war Sundays specifically
war_sun = s & in_regime(x.index, "iran26_war")
print("Iran-war Sundays:", x[war_sun].index.strftime("%Y-%m-%d").tolist(), "low_in_first_bar:", x[war_sun].low_in_first_bar.tolist())
# with artefacts included (2024-06-21 and 2024-12-20 are Fridays -> Sunday sessions with splice at 18:00!)
print("artefact rows are Sunday sessions?", xa.loc[xa.index.isin(pd.to_datetime(ARTEFACT_NQ)), ["sunday_open", "low_in_first_bar", "high_in_first_bar", "hi_k", "lo_k", "gap_open_bp"]])
sa = xa.sunday_open == 1
for lab in ["low_in_first_bar", "lo_after_tko"]:
    sub = xa[sa]; k = int(sub[lab].sum()); n = len(sub); b = xa[lab].mean()
    print(f"  artefacts INCLUDED: {lab} n={n} {k/n:.3f} v {b:.3f} p={binom_p(k, n, b):.3g}")

# ---------------- F3 after-hours print ----------------
print("\n" + "=" * 100 + "\nF3 megacap / |post|>=25")
m = x.megacap_earnings_tonight == 1; pp = x.abs_post >= 25
print("megacap n=", m.sum(), " |post|>=25 n=", pp.sum(), " overlap=", (m & pp).sum())
for cond, nm in [(m, "F3 megacap"), (pp, "F3 |post|>=25")]:
    C(x, cond, "first_bar_rng_bp", nm); C(x, cond, "rng_bp", nm)
    R(x, cond, "any_last_bar", nm); R(x, cond, "high_in_last_bar", nm); R(x, cond, "high_in_first_bar", nm); R(x, cond, "mid_close", nm)
# up-night high_in_last_bar
up = x[x.asia_ret_bp > 0]
for cond_fn, nm in [(lambda d: d.megacap_earnings_tonight == 1, "F3 up-nights megacap"), (lambda d: d.abs_post >= 25, "F3 up-nights |post|>=25")]:
    R(up, cond_fn(up), "high_in_last_bar", nm, base_df=up)
# sign of post_ret tests (null claims) by quarter
for cond, nm in [(x.post_ret >= 0.0015, "F3 post>=+15"), (x.post_ret <= -0.0015, "F3 post<=-15")]:
    R(x, cond, "asia_up", nm); R(x, cond, "low_in_first_bar", nm); R(x, cond, "high_in_first_bar", nm)
# bars_since_hi>=2 panel variant: P(high_done | k, bars_since_hi>=2) for |post|>=25
p = load_panel("NQ"); p = p[p.n_bars == 9].merge(x[["abs_post", "megacap_earnings_tonight", "quarter", "sunday_open", "half"]], left_on="date", right_index=True)
pp2 = p[(p.abs_post >= 25) & (p.bars_since_hi >= 2) & (p.k.between(2, 7))]
bb2 = p[(p.bars_since_hi >= 2) & (p.k.between(2, 7))]
print("\nF3 panel P(high_done | k in 2..7, bars_since_hi>=2): |post|>=25:", pp2.groupby("k").high_done.mean().round(2).to_dict(), " base:", bb2.groupby("k").high_done.mean().round(2).to_dict())
print("   by quarter (pooled k=2..7), |post|>=25 vs base:")
print(pd.DataFrame({"n_rows": pp2.groupby("quarter").size(), "n_sessions": pp2.groupby("quarter").date.nunique(), "cond": pp2.groupby("quarter").high_done.mean().round(2), "base": bb2.groupby("quarter").high_done.mean().round(2)}).to_string())

# ---------------- F4 Kospi ----------------
print("\n" + "=" * 100 + "\nF4 |kospi|>=3%")
kb = x.abs_kospi >= 3
print("kospi>=3% nights by quarter:", x[kb].groupby("quarter").size().to_dict())
for lab in ["any_at_tko", "low_at_tokyo_open", "high_at_tokyo_open", "low_in_last_bar", "cont", "mid_close"]:
    R(x, kb, lab, "F4 |kospi|>=3%")
C(x, kb, "rng_bp", "F4 |kospi|>=3%")
# the DST check: any_at_tko by is_dst within kospi nights vs base
for d in (0, 1):
    sub = x[kb & (x.is_dst == d)]; b = x[x.is_dst == d].any_at_tko.mean()
    print(f"  is_dst={d}: kospi n={len(sub)} any_at_tko={sub.any_at_tko.mean():.3f} v base {b:.3f} p={binom_p(sub.any_at_tko.sum(), len(sub), b):.3g}")
# control: is it the Kospi or just 'big |rth| / big vix' nights? conditional on |rth|<100
sub = x[kb & (x.abs_rth < 100)]; b = x[x.abs_rth < 100].any_at_tko.mean()
print(f"  kospi>=3% & |rth|<100: n={len(sub)} any_at_tko={sub.any_at_tko.mean():.3f} v {b:.3f} p={binom_p(sub.any_at_tko.sum(), len(sub), b):.3g}")
sub = x[kb & (x.vix < 20)]; b = x[x.vix < 20].any_at_tko.mean()
print(f"  kospi>=3% & vix<20: n={len(sub)} any_at_tko={sub.any_at_tko.mean():.3f} v {b:.3f} p={binom_p(sub.any_at_tko.sum(), len(sub), b):.3g}")
# 2026 only base: the claim's regime caveat -> compare kospi nights to the other 2026 nights
w = x[x.index >= "2026-01-01"]
sub = w[w.abs_kospi >= 3]; b = w.any_at_tko.mean()
print(f"  2026-only base: kospi n={len(sub)} any_at_tko={sub.any_at_tko.mean():.3f} v 2026 base {b:.3f} p={binom_p(sub.any_at_tko.sum(), len(sub), b):.3g}; low_in_last_bar {sub.low_in_last_bar.mean():.3f} v {w.low_in_last_bar.mean():.3f}")
# Kospi nights by month in 2026
print("  kospi nights by month:", x[kb].groupby(x[kb].index.to_period("M")).size().to_dict())

# ---------------- F5 rth<=-150 ----------------
print("\n" + "=" * 100 + "\nF5 rth<=-150")
d15 = x.rth_ret_bp <= -150
print("rth<=-150 nights by quarter:", x[d15].groupby("quarter").size().to_dict())
print("dates:", x[d15].index.strftime("%Y-%m-%d").tolist())
for lab in ["low_below_rth_low", "high_above_rth_high", "asia_up", "low_by_tokyo_open", "cont"]:
    R(x, d15, lab, "F5 rth<=-150")
C(x, d15, "rally_after_lo_bp", "F5 rth<=-150"); C(x, d15, "rng_bp", "F5 rth<=-150")
# mechanical check: distance from the 17:00 close to the RTH low / high on those nights
sub = x[d15]
dl = (sub.lvl_rth_low / sub.ref_close - 1) * 1e4; dh = (sub.lvl_rth_high / sub.ref_close - 1) * 1e4
print(f"  dist 17:00 close -> RTH low: median {dl.median():+.0f} bp (IQR {dl.quantile(.25):+.0f}..{dl.quantile(.75):+.0f});  -> RTH high: median {dh.median():+.0f} bp (min {dh.min():+.0f})")
print(f"  median lo_bp on those nights {sub.lo_bp.median():+.0f}, median hi_bp {sub.hi_bp.median():+.0f}; max hi_bp {sub.hi_bp.max():+.0f}")
# all nights: P(high_above_rth_high) when dist to RTH high >= 100bp
allh = (x.lvl_rth_high / x.ref_close - 1) * 1e4
for thr in (60, 100, 150):
    sub2 = x[allh >= thr]
    print(f"  all nights with RTH high >= {thr} bp above the 17:00 close: n={len(sub2)} high_above_rth_high={sub2.high_above_rth_high.mean():.3f}, low_below_rth_low={sub2.low_below_rth_low.mean():.3f}")
# low_below_rth_low vs distance control: nights with RTH low within 30 bp of the close
alll = (x.lvl_rth_low / x.ref_close - 1) * 1e4
sub2 = x[(alll >= -30) & (x.rth_ret_bp > -150)]
print(f"  control: RTH low within 30bp of close & rth>-150: n={len(sub2)} low_below_rth_low={sub2.low_below_rth_low.mean():.3f}; rth<=-150 nights dist within 30bp: n={(dl>=-30).sum()}, low_below={sub[dl>=-30].low_below_rth_low.mean():.3f}")

# ---------------- F6 moderate ----------------
print("\n" + "=" * 100 + "\nF6 moderate")
md = (x.rth_ret_bp <= -30) & (x.rth_ret_bp >= -130); mu = (x.rth_ret_bp >= 30) & (x.rth_ret_bp <= 130)
for lab in ["low_below_rth_low", "high_above_rth_high", "close_hi70", "cont"]:
    R(x, md, lab, "F6 mod-down")
for lab in ["high_above_rth_high", "low_below_rth_low", "close_lo30", "cont"]:
    R(x, mu, lab, "F6 mod-up")
# mechanical: distance control. Among mod-down nights, the RTH low distance vs RTH high distance
sub = x[md]; dl = (sub.lvl_rth_low / sub.ref_close - 1) * 1e4; dh = (sub.lvl_rth_high / sub.ref_close - 1) * 1e4
print(f"  mod-down: median dist to RTH low {dl.median():+.0f} bp, to RTH high {dh.median():+.0f} bp")
# the same label among nights with similar distance but opposite RTH sign (does the sign matter beyond distance?)
x["d_lo"] = (x.lvl_rth_low / x.ref_close - 1) * 1e4; x["d_hi"] = (x.lvl_rth_high / x.ref_close - 1) * 1e4
for lo_, hi_ in [(-40, -20), (-60, -40), (-90, -60)]:
    a = x[(x.d_lo > lo_) & (x.d_lo <= hi_) & (x.rth_ret_bp < 0)]; b = x[(x.d_lo > lo_) & (x.d_lo <= hi_) & (x.rth_ret_bp > 0)]
    print(f"  dist to RTH low in ({lo_},{hi_}]: rth<0 n={len(a)} low_below={a.low_below_rth_low.mean():.2f} | rth>0 n={len(b)} low_below={b.low_below_rth_low.mean():.2f}")

# ---------------- F7 FOMC ----------------
print("\n" + "=" * 100 + "\nF7 fomc_today")
f = x.fomc_today == 1
print("FOMC dates:", x[f].index.strftime("%Y-%m-%d").tolist())
print(x[f][["quarter", "rng_bp", "any_first_bar", "any_last_bar", "low_in_first_bar", "high_in_first_bar", "hi_k", "lo_k", "cont", "asia_up", "rth_ret_bp"]].round(0).to_string())
C(x, f, "rng_bp", "F7 fomc")
for lab in ["any_first_bar", "any_last_bar", "low_in_first_bar", "cont", "asia_up"]:
    R(x, f, lab, "F7 fomc")
# ES FOMC
xe = load_extremes("ES"); fe = xe.fomc_today == 1
C(xe, fe, "rng_bp", "F7 fomc ES"); R(xe, fe, "any_first_bar", "F7 fomc ES"); R(xe, fe, "any_last_bar", "F7 fomc ES")

# ---------------- F8 holiday ----------------
print("\n" + "=" * 100 + "\nF8 holiday")
h = (x.holiday_tomorrow == 1) | (x.pre_holiday == 1)
print(x[h][["quarter", "holiday_tomorrow", "pre_holiday", "sunday_open", "n_bars", "rng_bp", "abs_asia_ret", "any_first_bar", "any_last_bar", "events_tonight_tomorrow"]].round(0).to_string())
C(x, h, "rng_bp", "F8 holiday"); C(x, h, "abs_asia_ret", "F8 holiday")
C(x, h, "rng_bp", "F8 holiday (mean)", stat="mean")
he = (xe.holiday_tomorrow == 1) | (xe.pre_holiday == 1)
C(xe, he, "rng_bp", "F8 holiday ES")
# range relative to the ex-ante 20-session median (controls for regime vol)
x["rng_rel"] = x.rng_bp / x.asia_rng_med20; xe["rng_rel"] = xe.rng_bp / xe.asia_rng_med20
C(x, h, "rng_rel", "F8 holiday rng/med20"); C(xe, he, "rng_rel", "F8 holiday ES rng/med20")
# n_bars: are holiday sessions short sessions (6-7 bars)?  range mechanically smaller with fewer bars
print("  n_bars of holiday sessions:", x[h].n_bars.value_counts().to_dict(), " full table:", x.n_bars.value_counts().to_dict())
h9 = h & (x.n_bars == 9)
C(x[x.n_bars == 9], h9[x.n_bars == 9], "rng_bp", "F8 holiday, 9-bar sessions only")
C(x[x.n_bars == 9], h9[x.n_bars == 9], "rng_rel", "F8 holiday 9-bar rng/med20")

# ---------------- F9 tier1 tomorrow ----------------
print("\n" + "=" * 100 + "\nF9 tier1_data_tomorrow")
t1 = x.tier1_data_tomorrow == 1
C(x, t1, "rng_bp", "F9 tier1_tmrw"); C(x, t1, "abs_asia_ret", "F9 tier1_tmrw"); C(x, t1, "rng_rel", "F9 tier1_tmrw rng/med20")
for lab in ["lo_post_tko", "cont", "revers_close", "lo_after_tko"]:
    R(x, t1, lab, "F9 tier1_tmrw")
C(x, x.tier1_data_today == 1, "rng_bp", "F9 tier1_today"); C(x, x.tier1_data_today == 1, "rng_rel", "F9 tier1_today rng/med20")
te = xe.tier1_data_tomorrow == 1
R(xe, te, "lo_post_tko", "F9 tier1_tmrw ES"); C(xe, te, "rng_bp", "F9 tier1_tmrw ES")
# panel low_done at k=2,3,4
p = load_panel("NQ"); p = p[p.n_bars == 9].merge(x[["tier1_data_tomorrow", "quarter", "half"]], left_on="date", right_index=True)
for k in (2, 3, 4):
    sk = p[(p.k == k) & (p.tier1_data_tomorrow == 1)]; bk = p[p.k == k]
    print(f"  P(low_done|k={k}): tier1_tmrw {sk.low_done.mean():.3f} (n={len(sk)}) v {bk.low_done.mean():.3f} p={binom_p(sk.low_done.sum(), len(sk), bk.low_done.mean()):.3g}; by half: " +
          " ".join(f"{hh}:{sk[sk.half==hh].low_done.mean():.2f}v{bk[bk.half==hh].low_done.mean():.2f}" for hh in ("H1", "H2")))

# ---------------- F14 direction ----------------
print("\n" + "=" * 100 + "\nF14 direction (cont) under proxies, by quarter")
conds = {
 "all": x.rth_ret_bp != 0, "megacap": m, "sunday": s, "fomc": f, "mod-down": md, "|kospi|>=3": kb,
 "US-origin(|rth|>=100,|kospi|<1.5)": (x.abs_rth >= 100) & (x.abs_kospi < 1.5), "chip-led-down": (x.sox_ret <= -0.03) & (x.rth_ret_bp < 0),
 "up days": x.rth_ret_bp > 0, "down days": x.rth_ret_bp < 0, "boj": x.boj_tonight == 1, "rth<=-150 (asia_up)": d15,
}
for nm, c in conds.items():
    lab = "asia_up" if "asia_up" in nm else "cont"
    R(x, c, lab, f"F14 {nm}")
# quarterly cont for all sessions and up/down days: any quarter with |cont-0.5| big and n>=25?
qq = x.groupby("quarter").agg(n=("cont", "size"), cont=("cont", "mean"), asia_up=("asia_up", "mean"), up_days_cont=("cont", lambda s: s[x.loc[s.index, "rth_ret_bp"] > 0].mean()),
                              n_up=("rth_ret_bp", lambda s: (s > 0).sum()), down_days_cont=("cont", lambda s: s[x.loc[s.index, "rth_ret_bp"] < 0].mean()), n_down=("rth_ret_bp", lambda s: (s < 0).sum()))
print(qq.round(3).to_string())
for q, g in x.groupby("quarter"):
    k = int(g.cont.sum()); n = len(g)
    print(f"   {q}: cont {k}/{n}={k/n:.2f} p_vs_0.5={binom_p(k, n, 0.5):.3f}; up-days cont {g[g.rth_ret_bp>0].cont.mean():.2f} (n={(g.rth_ret_bp>0).sum()}) p={binom_p(g[g.rth_ret_bp>0].cont.sum(), (g.rth_ret_bp>0).sum(), 0.5):.3f}; down-days cont {g[g.rth_ret_bp<0].cont.mean():.2f} (n={(g.rth_ret_bp<0).sum()}) p={binom_p(g[g.rth_ret_bp<0].cont.sum(), (g.rth_ret_bp<0).sum(), 0.5):.3f}")
# the Sunday Spearman(rth, asia) = -0.20 by half / quarter
for nm, sub in [("sunday", x[s]), ("weekday", x[~s])]:
    r_, p_ = stats.spearmanr(sub.rth_ret_bp, sub.asia_ret_bp)
    print(f"  spearman(rth,asia) {nm}: r={r_:+.3f} p={p_:.3f} n={len(sub)}; by half:", {hh: round(stats.spearmanr(g.rth_ret_bp, g.asia_ret_bp)[0], 3) for hh, g in sub.groupby("half")},
          "; ex Iran war:", round(stats.spearmanr(sub[~in_regime(sub.index, 'iran26_war')].rth_ret_bp, sub[~in_regime(sub.index, 'iran26_war')].asia_ret_bp)[0], 3))

pd.DataFrame(res).to_csv(f"{OUT}/f2_f9_f14_robust.csv", index=False)
print("\nrows:", len(res))
