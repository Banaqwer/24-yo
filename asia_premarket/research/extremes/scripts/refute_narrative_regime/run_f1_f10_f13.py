"""F1 (catalogue families), F10/F11 (Tokyo-open-bar panel), F12 (15m timing), F13 (TSMC) regime / robustness checks."""
import sys
sys.path.insert(0, "research/extremes/scripts/refute_narrative_regime")
import numpy as np, pandas as pd
from scipy import stats
from robust import *

LENS = "research/extremes/scripts/lens_narrative"
pd.set_option("display.width", 300, "display.max_columns", 50, "display.max_rows", 500)
x = load_extremes("NQ")
fam = pd.read_csv(f"{LENS}/NQ_extremes_with_family.csv", index_col="date", parse_dates=True)
x["family"] = fam["family"].reindex(x.index).fillna("none"); x["is_cat"] = (x["family"] != "none").astype(int)
x["big_asia_cash"] = fam["big_asia_cash"].reindex(x.index).fillna(0)
res = []
def R(df, cond, label, name, **kw):
    r = rate_robust(df, cond, label, name, **kw); res.append(r); return r
def C(df, cond, col, name, **kw):
    r = cont_robust(df, cond, col, name, **kw); res.append(r); return r

# ====================== F1 ======================
print("=" * 100 + "\nF1 catalogue (ex post) nights vs other nights in the window 2025-11-01..")
w = x[x.index >= "2025-11-01"].copy()
print("window n:", len(w), " catalogue:", w.is_cat.sum(), " families:", w.family.value_counts().to_dict())
cat = w.is_cat == 1
for lab in ["any_first_bar", "any_at_tko", "trend_close", "high_in_first_bar", "low_in_first_bar"]:
    R(w, cat, lab, "F1 catalogue", base_df=w[~cat])
C(w, cat, "rng_bp", "F1 catalogue", base_df=w[~cat]); C(w, cat, "abs_asia_ret", "F1 catalogue", base_df=w[~cat])
# per quarter the catalogue-vs-other difference
print("\nF1 by quarter (cat vs non-cat in the same quarter):")
for q, g in w.groupby("quarter"):
    a = g[g.is_cat == 1]; b = g[g.is_cat == 0]
    print(f"  {q}: cat n={len(a)} other n={len(b)} | any_first_bar {a.any_first_bar.mean():.2f} v {b.any_first_bar.mean():.2f} | any_at_tko {a.any_at_tko.mean():.2f} v {b.any_at_tko.mean():.2f} | trend_close {a.trend_close.mean():.2f} v {b.trend_close.mean():.2f} | med rng {a.rng_bp.median():.0f} v {b.rng_bp.median():.0f}")
# selection check: catalogue nights are big nights. Compare with NON-catalogue nights matched on realised range (ex post).
print("\nF1 selection control: non-catalogue nights in the window by realised range:")
for lo_, hi_ in [(0, 50), (50, 80), (80, 120), (120, 1e9)]:
    for nm, g in [("cat", w[cat]), ("other", w[~cat])]:
        gg = g[(g.rng_bp >= lo_) & (g.rng_bp < hi_)]
        if len(gg):
            print(f"  rng [{lo_:.0f},{hi_:.0f}) {nm:5s} n={len(gg):3d} any_first_bar={gg.any_first_bar.mean():.2f} any_at_tko={gg.any_at_tko.mean():.2f} trend_close={gg.trend_close.mean():.2f} |ret|={gg.abs_asia_ret.median():.0f}")
# full-table: any_first_bar / any_at_tko by range tercile (ex post), all 578
x["rng_terc"] = pd.qcut(x.rng_bp, 3, labels=["small", "mid", "large"])
print("  full table by range tercile:", x.groupby("rng_terc", observed=True)[["any_first_bar", "any_at_tko", "trend_close"]].mean().round(2).to_dict())
big_other = w[(~cat) & (w.rng_bp >= w[cat].rng_bp.median())]
print(f"  non-catalogue nights with rng >= catalogue median ({w[cat].rng_bp.median():.0f}bp): n={len(big_other)} any_first_bar={big_other.any_first_bar.mean():.2f} any_at_tko={big_other.any_at_tko.mean():.2f} trend_close={big_other.trend_close.mean():.2f}")
# families: the sub-claims
print("\nF1 families (ex post):")
for famnm, labs in [("AH_PRINT", ["any_first_bar", "any_at_tko", "mid_close"]), ("HEADLINE", ["any_first_bar", "high_at_tokyo_open", "high_in_last_bar", "trend_close", "cont"]),
                    ("ASIA_CHIP", ["cont", "low_in_last_bar"]), ("NO_NEWS", ["any_first_bar"])]:
    cf = w.family == famnm
    for lab in labs:
        R(w, cf, lab, f"F1 fam {famnm}", base_df=w[~cat])
# ASIA_CHIP lo_k bimodal and continuation by quarter
ac = w[w.family == "ASIA_CHIP"]
print("  ASIA_CHIP lo_k:", np.bincount(ac.lo_k.astype(int), minlength=9).tolist(), " cont by quarter:", ac.groupby("quarter").cont.agg(["mean", "size"]).round(2).to_dict())
hl = w[w.family == "HEADLINE"]
print("  HEADLINE nights by quarter:", hl.groupby("quarter").size().to_dict(), " in Iran war window:", int(in_regime(hl.index, "iran26_war").sum()))
print("  HEADLINE ex Iran war: n=", (~in_regime(hl.index, "iran26_war")).sum(), " trend_close=", round(hl[~in_regime(hl.index, "iran26_war")].trend_close.mean(), 2), " high_at_tko=", round(hl[~in_regime(hl.index, "iran26_war")].high_at_tokyo_open.mean(), 2),
      " | Iran-war HEADLINE: trend_close=", round(hl[in_regime(hl.index, "iran26_war")].trend_close.mean(), 2), " high_at_tko=", round(hl[in_regime(hl.index, "iran26_war")].high_at_tokyo_open.mean(), 2))
bac = w[(w.is_cat == 1)]
print("  big_asia_cash any_at_tko:", bac.groupby("big_asia_cash").any_at_tko.agg(["mean", "size"]).round(2).to_dict())

# ====================== F10 / F11 (panel at k = tokyo_open_k) ======================
print("\n" + "=" * 100 + "\nF10 Tokyo-open-bar position")
p = load_panel("NQ"); p = p[p.n_bars == 9]
at = p[p.k == p.tokyo_open_k][["date", "cum_ret_bp", "pos_in_range", "bars_since_hi", "bars_since_lo", "run_rng_bp", "run_rng_vs_med20", "run_hi_bp", "run_lo_bp"]].set_index("date")
xx = x.join(at, how="inner")
xx["high_in"] = (xx.hi_k <= xx.tokyo_open_k).astype(int); xx["low_in"] = (xx.lo_k <= xx.tokyo_open_k).astype(int)
xx["pos_lo"] = (xx.pos_in_range < 0.2); xx["pos_hi"] = (xx.pos_in_range >= 0.8)
print("n full sessions:", len(xx), " base P(high_in)=", round(xx.high_in.mean(), 3), " P(low_in)=", round(xx.low_in.mean(), 3))
R(xx, xx.pos_lo, "high_in", "F10 pos<0.2")
R(xx, xx.pos_hi, "low_in", "F10 pos>=0.8")
R(xx, xx.pos_lo & (xx.run_rng_vs_med20 >= 0.7), "high_in", "F10 pos<0.2 & rng>=0.7med")
R(xx, xx.pos_hi & (xx.run_rng_vs_med20 >= 0.7), "low_in", "F10 pos>=0.8 & rng>=0.7med")
R(xx, xx.pos_lo & (xx.run_rng_vs_med20 < 0.4), "high_in", "F10 pos<0.2 & rng<0.4med")
R(xx, xx.pos_hi & (xx.run_rng_vs_med20 < 0.4), "low_in", "F10 pos>=0.8 & rng<0.4med")
R(xx, xx.pos_hi & (xx.sunday_open == 1), "low_in", "F10 sunday & pos>=0.8")
R(xx, xx.pos_lo & (xx.sunday_open == 1), "high_in", "F10 sunday & pos<0.2")
# DST split: tko_k = 1 (winter) vs 2 (summer): different number of bars elapsed -> different base
for d in (0, 1):
    g = xx[xx.is_dst == d]
    print(f"  is_dst={d} (tko_k={g.tokyo_open_k.iloc[0]}): n={len(g)} base high_in={g.high_in.mean():.2f} low_in={g.low_in.mean():.2f} | pos<0.2 n={g.pos_lo.sum()} high_in={g[g.pos_lo].high_in.mean():.2f} | pos>=0.8 n={g.pos_hi.sum()} low_in={g[g.pos_hi].low_in.mean():.2f}")
# the proper base for the conditional: P(high_in | pos band) across bands
print("  pos band table:")
for lo_, hi_ in [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]:
    g = xx[(xx.pos_in_range >= lo_) & (xx.pos_in_range < hi_)]
    print(f"    [{lo_:.1f},{hi_:.1f}) n={len(g)} high_in={g.high_in.mean():.2f} low_in={g.low_in.mean():.2f} | by quarter high_in: " + " ".join(f"{q}:{gg.high_in.mean():.2f}({len(gg)})" for q, gg in g.groupby("quarter")))
# ES replication by quarter
pe = load_panel("ES"); pe = pe[pe.n_bars == 9]; xe = load_extremes("ES")
ate = pe[pe.k == pe.tokyo_open_k][["date", "pos_in_range", "run_rng_vs_med20", "cum_ret_bp"]].set_index("date")
xxe = xe.join(ate, how="inner"); xxe["high_in"] = (xxe.hi_k <= xxe.tokyo_open_k).astype(int); xxe["low_in"] = (xxe.lo_k <= xxe.tokyo_open_k).astype(int)
R(xxe, xxe.pos_in_range < 0.2, "high_in", "F10 ES pos<0.2"); R(xxe, xxe.pos_in_range >= 0.8, "low_in", "F10 ES pos>=0.8")

print("\n" + "=" * 100 + "\nF11 momentum after the Tokyo-open bar")
xx["rest"] = xx.close_bp - xx.cum_ret_bp
xx["rest_cont"] = (np.sign(xx.rest) == np.sign(xx.cum_ret_bp)).astype(int)
xx["abs_move"] = xx.cum_ret_bp.abs()
# the base here is 0.5 (coin); use rate vs 0.5 by quarter
def coin_table(df, cond, name):
    cond = pd.Series(np.asarray(cond), index=df.index).fillna(False).astype(bool)
    s = df[cond]; k = int(s.rest_cont.sum()); n = len(s)
    print(f"\n[{name}] rest_cont n={n} {k/n:.3f} p_vs_0.5={binom_p(k, n, 0.5):.3g} CI={boot_ci(s.rest_cont.values)}")
    rows = []
    for q, g in s.groupby("quarter"):
        kq = int(g.rest_cont.sum()); rows.append((q, len(g), kq / len(g), binom_p(kq, len(g), 0.5)))
    print("   quarters: " + " | ".join(f"{q} n={n_} {r_:.2f} p={p_:.2f}" for q, n_, r_, p_ in rows))
    sig = [(q, n_, r_) for q, n_, r_, p_ in rows if p_ < 0.05 and n_ >= 25]
    print("   quarters with n>=25 and p<0.05 vs coin:", sig)
    for h in ("H1", "H2"):
        g = s[s.half == h]; print(f"   {h}: n={len(g)} {g.rest_cont.mean():.3f} p={binom_p(g.rest_cont.sum(), len(g), 0.5):.3g}", end="")
    print()
    for rg in list(REGIMES) + ["all"]:
        m = np.ones(len(s), bool)
        for r_ in (REGIMES if rg == "all" else [rg]): m &= ~in_regime(s.index, r_)
        g = s[m]; print(f"   ex {rg:12s}: n={len(g)} {g.rest_cont.mean():.3f} p={binom_p(g.rest_cont.sum(), len(g), 0.5):.3g}")
    for nm, v in (("weekday", 0), ("sunday", 1)):
        g = s[s.sunday_open == v]
        if len(g): print(f"   {nm}: n={len(g)} {g.rest_cont.mean():.3f} p={binom_p(g.rest_cont.sum(), len(g), 0.5):.3g}")
    # leave-5-out (remove 5 continuation nights)
    k5 = k - 5; n5 = n - 5; print(f"   leave-5-out: {k5/n5:.3f} p={binom_p(k5, n5, 0.5):.3g}")
    # magnitude: does the rest move WITH or AGAINST? mean rest signed by move-so-far
    signed = (xx.loc[s.index, "rest"] * np.sign(xx.loc[s.index, "cum_ret_bp"]))
    print(f"   signed rest (bp, + = continuation): mean {signed.mean():+.1f} median {signed.median():+.1f}; by quarter: " + " ".join(f"{q}:{g.mean():+.0f}" for q, g in signed.groupby(xx.loc[s.index, 'quarter'])))
coin_table(xx, xx.abs_move >= 0, "F11 all")
coin_table(xx, xx.abs_move >= 20, "F11 |move|>=20")
coin_table(xx, xx.abs_move >= 40, "F11 |move|>=40")
coin_table(xx, xx.sunday_open == 1, "F11 sunday")
coin_table(xx, (xx.is_cat == 1), "F11 catalogue (ex post)")
# first-bar impulse: headline proxy vs no proxy
x["hd"] = (x.megacap_earnings_tonight == 1) | (x.sunday_open == 1) | (x.fomc_today == 1) | (x.abs_post >= 15)
big_fb = x.abs_fb >= 20
for nm, c in [("all |fb|>=20", big_fb), ("headline-proxy & |fb|>=20", x.hd & big_fb), ("no-proxy & |fb|>=20", (~x.hd) & big_fb),
              ("catalogue & |fb|>=20 (ex post)", (x.is_cat == 1) & big_fb), ("window non-cat & |fb|>=20 (ex post)", (x.is_cat == 0) & (x.index >= "2025-11-01") & big_fb)]:
    s = x[c]; k = int(s.fb_sign_agree.sum()); n = len(s)
    print(f"\n[F11 first-bar {nm}] fb_sign_agree n={n} {k/n:.3f} p_vs_0.5={binom_p(k, n, 0.5):.3g}; quarters: " +
          " | ".join(f"{q} n={len(g)} {g.fb_sign_agree.mean():.2f}" for q, g in s.groupby("quarter")) +
          f"; ex Iran war: n={(~in_regime(s.index,'iran26_war')).sum()} {s[~in_regime(s.index,'iran26_war')].fb_sign_agree.mean():.2f}; ex all regimes: {s[~(in_regime(s.index,'iran26_war')|in_regime(s.index,'apr25_tariff')|in_regime(s.index,'aug24_carry')|in_regime(s.index,'nov26_crash'))].fb_sign_agree.mean():.2f}")

# ====================== F12 15m ======================
print("\n" + "=" * 100 + "\nF12 15m timing (independent recomputation)")
m15 = pd.read_csv(f"{ROOT}/data/NQ_15m.csv")
tcol = [c for c in m15.columns if "ate" in c or "time" in c.lower()][0]
print("15m columns:", list(m15.columns), "rows:", len(m15), "tcol:", tcol, "first:", m15[tcol].iloc[0], "last:", m15[tcol].iloc[-1])
m15[tcol] = pd.to_datetime(m15[tcol], utc=True).dt.tz_convert("America/New_York")
m15 = m15.set_index(tcol).sort_index()
m15["gdate"] = m15.index.date
sh = m15.index.hour >= 18
m15.loc[sh, "gdate"] = (m15.index[sh] + pd.Timedelta(days=1)).date
asia = m15[m15.index.hour.isin([18, 19, 20, 21, 22, 23, 0, 1, 2])]
recs = []
for gd, g in asia.groupby("gdate"):
    if len(g) < 24:
        continue
    g = g.sort_index(); ih = g["High"].values.argmax(); il = g["Low"].values.argmin()
    th = g.index[ih]; tl = g.index[il]
    d = x.index[x["asia_gdate"] == str(gd)]
    if len(d) == 0:
        continue
    r = x.loc[d[0]]
    first = g.iloc[0]
    # does the 18:00-18:15 bar's extreme equal its OPEN (the 18:00 print)?
    recs.append(dict(date=d[0], gdate=gd, hi_time=th.strftime("%H:%M"), lo_time=tl.strftime("%H:%M"), hi_hour=th.hour, hi_min=th.minute, lo_hour=tl.hour, lo_min=tl.minute,
                     hi_k=r.hi_k, lo_k=r.lo_k, tko=r.tokyo_open_k, is_dst=r.is_dst, sunday=r.sunday_open, quarter=r.quarter, n15=len(g),
                     fb_open_is_high=int(first["Open"] >= first["High"] - 1e-9), fb_open_is_low=int(first["Open"] <= first["Low"] + 1e-9),
                     hi_in_bar0=int(th.hour == 18), lo_in_bar0=int(tl.hour == 18), hi_first15=int(th.hour == 18 and th.minute == 0), lo_first15=int(tl.hour == 18 and tl.minute == 0),
                     hourly_hi_k0=int(r.hi_k == 0), hourly_lo_k0=int(r.lo_k == 0)))
t = pd.DataFrame(recs)
print("15m sessions:", len(t), " date range:", t.date.min().date(), "..", t.date.max().date(), " n15 per session:", t.n15.value_counts().to_dict())
print("agreement hourly hi_k==0 vs 15m hi in 18:00 hour:", (t.hourly_hi_k0 == t.hi_in_bar0).mean().round(3), " lo:", (t.hourly_lo_k0 == t.lo_in_bar0).mean().round(3))
b0 = t[(t.hi_in_bar0 == 1)]; b0l = t[(t.lo_in_bar0 == 1)]
print(f"bar-0 highs: {len(b0)} of which 18:00-18:15 sub-bar: {b0.hi_first15.sum()}; bar-0 lows: {len(b0l)} first15: {b0l.lo_first15.sum()}; combined {b0.hi_first15.sum()+b0l.lo_first15.sum()}/{len(b0)+len(b0l)}")
# is the 18:00-18:15 extreme the opening print? (open == high / open == low of the first 15m bar)
print("  of the 18:00-18:15 highs, the 18:00 OPEN equals the sub-bar high:", int(b0[b0.hi_first15 == 1].fb_open_is_high.sum()), "/", int(b0.hi_first15.sum()),
      "; of the 18:00-18:15 lows, OPEN equals the sub-bar low:", int(b0l[b0l.lo_first15 == 1].fb_open_is_low.sum()), "/", int(b0l.lo_first15.sum()))
print("  all sessions: 18:00 open is the first-15m high:", int(t.fb_open_is_high.sum()), " is the first-15m low:", int(t.fb_open_is_low.sum()), " of", len(t))
# regime: Nov 3-6 crash, Sundays
for nm, msk in [("ex nov crash", ~in_regime(pd.DatetimeIndex(t.date), "nov26_crash")), ("weekday", t.sunday == 0), ("sunday", t.sunday == 1)]:
    tt = t[msk.values if hasattr(msk, "values") else msk]
    bb = tt[tt.hi_in_bar0 == 1]; bbl = tt[tt.lo_in_bar0 == 1]
    print(f"  {nm}: sessions={len(tt)} bar-0 extremes={len(bb)+len(bbl)} first15={bb.hi_first15.sum()+bbl.lo_first15.sum()}")
# by month
print("  by month: " + " | ".join(f"{mo}: sessions={len(g)} bar0ext={(g.hi_in_bar0.sum()+g.lo_in_bar0.sum())} first15={(g.hi_first15.sum()+g.lo_first15.sum())}" for mo, g in t.groupby(pd.DatetimeIndex(t.date).to_period('M'))))
# 02:00-bar lows
l2 = t[t.lo_hour == 2]; h2 = t[t.hi_hour == 2]
print(f"02:00-bar lows: {len(l2)} sub-bar minutes {l2.lo_min.value_counts().sort_index().to_dict()}; 02:00-bar highs: {len(h2)} {h2.hi_min.value_counts().sort_index().to_dict()}")
print("  02:00-bar lows ex nov crash:", l2[~in_regime(pd.DatetimeIndex(l2.date), 'nov26_crash')].lo_min.value_counts().sort_index().to_dict(), " dates of 02:45 lows:", l2[l2.lo_min == 45].date.dt.strftime("%m-%d").tolist())
# leave-5-out on 14/22 and 8/16
print(f"  14/22 vs 0.25: p={binom_p(14,22,0.25):.2g}; leave-5-out 9/17: p={binom_p(9,17,0.25):.2g}; 8/16 vs .25 p={binom_p(8,16,0.25):.2g}; leave-5-out 3/11 p={binom_p(3,11,0.25):.2g}")
# within-hour minute distribution of ALL highs/lows (is :00 generally over-represented, i.e. is this just 'hourly-bar open = extreme' generic?)
print("  minute-of-hour of all highs:", t.hi_min.value_counts().sort_index().to_dict(), " lows:", t.lo_min.value_counts().sort_index().to_dict())
tk = np.where(t.is_dst == 1, 20, 19)
print("  Tokyo-open-bar highs sub-bar:", t[t.hi_hour == tk].hi_min.value_counts().sort_index().to_dict(), " lows:", t[t.lo_hour == tk].lo_min.value_counts().sort_index().to_dict())
# generic: for hourly bars that host an extreme (any hour), share in the first 15 minutes
t["hi_slot_first"] = (t.hi_min == 0).astype(int); t["lo_slot_first"] = (t.lo_min == 0).astype(int)
nb0 = t[(t.hi_in_bar0 == 0)]; nb0l = t[(t.lo_in_bar0 == 0)]
print(f"  non-bar-0 extremes in the first 15 min of their hour: highs {nb0.hi_slot_first.sum()}/{len(nb0)}, lows {nb0l.lo_slot_first.sum()}/{len(nb0l)}")
t.to_csv(f"{OUT}/f12_15m_timing_recomputed.csv", index=False)

# ====================== F13 TSMC ======================
print("\n" + "=" * 100 + "\nF13 TSMC nights")
tsmc = pd.to_datetime(["2024-07-17", "2024-10-16", "2025-01-15", "2025-04-16", "2025-07-16", "2025-10-15", "2026-01-14", "2026-04-15", "2026-07-15", "2026-10-14"])
tt = x.loc[x.index.isin(tsmc)]
print(tt[["quarter", "is_dst", "n_bars", "hi_k", "lo_k", "rng_bp", "asia_ret_bp", "rth_ret_bp", "megacap_earnings_tonight", "events_tonight_tomorrow"]].to_string())
x["hi_last2"] = (x.hi_k >= x.n_bars - 2).astype(int)
print("P(hi_k>=7) base:", round((x.hi_k >= 7).mean(), 3), " TSMC:", (tt.hi_k >= 7).mean(), f"({int((tt.hi_k>=7).sum())}/{len(tt)}) p={binom_p((tt.hi_k>=7).sum(), len(tt), (x.hi_k>=7).mean()):.2g}")
# control 1: same weekday (Wednesday) sessions one and two weeks before/after each TSMC date
ctrl_dates = []
for d in tsmc:
    for off in (-14, -7, 7, 14):
        ctrl_dates.append(d + pd.Timedelta(days=off))
ctrl = x.loc[x.index.isin(ctrl_dates)]
print(f"control: Wednesdays +-1/+-2 weeks: n={len(ctrl)} P(hi_k>=7)={(ctrl.hi_k>=7).mean():.3f} any_last_bar={ctrl.any_last_bar.mean():.3f}; by TSMC quarter: " + " ".join(f"{q}:{(g.hi_k>=7).mean():.2f}" for q, g in ctrl.groupby('quarter')))
# control 2: all Wednesday sessions in the 3rd week of Jan/Apr/Jul/Oct (earnings season) excluding the TSMC dates
x["dow"] = x.index.dayofweek; x["mo"] = x.index.month; x["dom"] = x.index.day
es = x[(x.dow == 2) & x.mo.isin([1, 4, 7, 10]) & (x.dom.between(8, 24)) & ~x.index.isin(tsmc)]
print(f"control: other Wednesdays 8th-24th of Jan/Apr/Jul/Oct: n={len(es)} P(hi_k>=7)={(es.hi_k>=7).mean():.3f}")
# control 3: all Wednesdays
wd = x[x.dow == 2]
print(f"all Wednesdays: n={len(wd)} P(hi_k>=7)={(wd.hi_k>=7).mean():.3f}; all Wednesdays with megacap_earnings_tonight: n={(wd.megacap_earnings_tonight==1).sum()} P={(wd[wd.megacap_earnings_tonight==1].hi_k>=7).mean():.3f}")
# per-quarter base P(hi_k>=7) in the TSMC quarters
print("P(hi_k>=7) by quarter:", x.groupby("quarter").apply(lambda g: round((g.hi_k >= 7).mean(), 2)).to_dict())
# P(hi_k>=7) by DST: in EST the TSMC release at 01:00 ET is bar 7; EDT 02:00 = bar 8
print("P(hi_k>=7) by is_dst:", x.groupby("is_dst").apply(lambda g: round((g.hi_k >= 7).mean(), 2)).to_dict(), " P(hi_k==8):", x.groupby("is_dst").apply(lambda g: round((g.hi_k == 8).mean(), 2)).to_dict())
# the ES replication (not run by the lens)
tte = xe.loc[xe.index.isin(tsmc)]
print("ES TSMC nights hi_k:", tte.hi_k.tolist(), " P(hi_k>=7)=", (tte.hi_k >= 7).mean(), " ES base:", round((xe.hi_k >= 7).mean(), 3))
# leave-5-out
print(f"leave-5-out: 4/5 vs .325 p={binom_p(4,5,0.325):.2g}")
# also: the LOW on TSMC nights (if the 'event' at 02:00 moves price, lows should also be late if negative)
print("TSMC lo_k>=7:", int((tt.lo_k >= 7).sum()), "/", len(tt), " base:", round((x.lo_k >= 7).mean(), 3))

pd.DataFrame(res).to_csv(f"{OUT}/f1_f10_f13_robust.csv", index=False)
print("\nrows:", len(res))
