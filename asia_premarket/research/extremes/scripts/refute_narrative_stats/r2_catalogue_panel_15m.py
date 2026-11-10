"""Recompute F1 (catalogue), F10/F11 (panel at Tokyo-open bar), F12 (15m), F13 (TSMC), plus the F8 6-bar check."""
import sys, glob
sys.path.insert(0, "research/extremes/scripts/refute_narrative_stats")
sys.path.insert(0, "research/extremes/scripts/lens_narrative")
import numpy as np, pandas as pd
from scipy import stats
from common_r import *
from q1_families import FAM, BIG_ASIA_CASH  # the lens's hand-coded family map (data only)

pd.set_option("display.width", 250, "display.max_columns", 50)
x = load_x("NQ"); e = load_x("ES"); p = load_p("NQ"); pe = load_p("ES")

# ------------------------------------------------------------------ F8 check: which hours do 6-bar sessions hold?
print("================ F8: hours present in 6-bar sessions")
h = (x.holiday_tomorrow == 1) | (x.pre_holiday == 1)
for d in x[h & (x.n_bars == 6)].index[:10]:
    print("  ", d.date(), sorted(p[p.date == d].hour_et.tolist()))
raw = pd.read_csv(f"{ROOT}/data/NQ_1h.csv")
tcol = raw.columns[0]; raw[tcol] = pd.to_datetime(raw[tcol], utc=True).dt.tz_convert("America/New_York"); raw = raw.set_index(tcol)
for d in ["2024-07-02", "2025-11-26", "2026-07-02"]:
    t0 = pd.Timestamp(f"{d} 16:00", tz="America/New_York"); seg = raw[(raw.index >= t0) & (raw.index <= t0 + pd.Timedelta(hours=12))]
    print(f"  raw 1h bars from {d} 16:00 ET:", [t.strftime("%m-%d %H:%M") for t in seg.index])

# ------------------------------------------------------------------ F1 catalogue
print("\n================ F1 catalogue vs other nights in window")
c = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{ROOT}/research/catalogue_*.csv"))], ignore_index=True)
c["date"] = pd.to_datetime(c.date); c = c.set_index("date").sort_index()
print("  catalogue rows:", len(c), " unique dates:", c.index.nunique(), " range:", c.index.min().date(), c.index.max().date())
x["is_cat"] = x.index.isin(c.index).astype(int)
x["family"] = [FAM.get(d.strftime("%Y-%m-%d"), "none") for d in x.index]
x["big_asia_cash"] = [int(d.strftime("%Y-%m-%d") in BIG_ASIA_CASH) for d in x.index]
w = x[(x.index >= "2025-11-01")].copy()
print("  window n:", len(w), " catalogue joined:", int(w.is_cat.sum()), " other:", int((w.is_cat == 0).sum()))
print("  missing catalogue dates:", sorted(set(c.index) - set(x.index)))
cat = w.is_cat == 1
for lab in ["any_first_bar", "any_at_tko", "trend_close", "any_last_bar", "cont", "mid_close"]:
    rate_vs_rest(w, cat, lab, "window catalogue")
cont_vs_rest(w, cat, "rng_bp", "window catalogue"); cont_vs_rest(w, cat, "abs_ret", "window catalogue"); cont_vs_rest(w, cat, "abs_gap", "window catalogue")
# adversarial: is 'catalogue' just 'big range'? control: non-catalogue nights in the window with rng >= 80 bp, and full-table by range tercile
big_non = (w.is_cat == 0) & (w.rng_bp >= 80)
print(f"  non-catalogue window nights with rng>=80 (n={int(big_non.sum())}): any_first_bar={w[big_non].any_first_bar.mean():.3f} any_at_tko={w[big_non].any_at_tko.mean():.3f} trend_close={w[big_non].trend_close.mean():.3f}")
cat_big = cat & (w.rng_bp >= 80)
print(f"  catalogue nights with rng>=80 (n={int(cat_big.sum())}): any_first_bar={w[cat_big].any_first_bar.mean():.3f} any_at_tko={w[cat_big].any_at_tko.mean():.3f} trend_close={w[cat_big].trend_close.mean():.3f}")
print("  full table any_first_bar / any_at_tko / trend_close by realised-range tercile (ex post):")
x["rng_terc"] = pd.qcut(x.rng_bp, 3, labels=["small", "mid", "large"])
print(x.groupby("rng_terc", observed=True)[["any_first_bar", "any_at_tko", "trend_close", "any_last_bar"]].mean().round(3).to_string())
x["gap_terc"] = pd.qcut(x.abs_gap, 3, labels=["small", "mid", "large"])
print("  full table by |gap| tercile (k0-open knowable):"); print(x.groupby("gap_terc", observed=True)[["any_first_bar", "any_at_tko", "trend_close"]].mean().round(3).to_string())
# within window: catalogue vs non-catalogue, stratified by |gap|>=20
for nm, msk in [("|gap|>=20", w.abs_gap >= 20), ("|gap|<20", w.abs_gap < 20)]:
    a = w[cat & msk]; b = w[(~cat) & msk]
    print(f"  window {nm}: catalogue n={len(a)} any_first_bar={a.any_first_bar.mean():.3f} any_at_tko={a.any_at_tko.mean():.3f} | other n={len(b)} any_first_bar={b.any_first_bar.mean():.3f} any_at_tko={b.any_at_tko.mean():.3f}")
# families
print("  families:")
other = w[w.is_cat == 0]
rows = []
for fam, g in w[cat].groupby("family"):
    rows.append(dict(family=fam, n=len(g), any_first_bar=g.any_first_bar.mean(), any_at_tko=g.any_at_tko.mean(), high_at_tko=g.high_at_tokyo_open.mean(),
                     high_in_last_bar=g.high_in_last_bar.mean(), low_in_last_bar=g.low_in_last_bar.mean(), trend_close=g.trend_close.mean(), mid_close=g.mid_close.mean(),
                     cont=g.cont.mean(), med_rng=g.rng_bp.median(), med_abs_ret=g.abs_ret.median(),
                     lo_k_hist=np.bincount(g.lo_k.astype(int), minlength=9).tolist()))
rows.append(dict(family="OTHER(window)", n=len(other), any_first_bar=other.any_first_bar.mean(), any_at_tko=other.any_at_tko.mean(), high_at_tko=other.high_at_tokyo_open.mean(),
                 high_in_last_bar=other.high_in_last_bar.mean(), low_in_last_bar=other.low_in_last_bar.mean(), trend_close=other.trend_close.mean(), mid_close=other.mid_close.mean(),
                 cont=other.cont.mean(), med_rng=other.rng_bp.median(), med_abs_ret=other.abs_ret.median(), lo_k_hist=np.bincount(other.lo_k.astype(int), minlength=9).tolist()))
print(pd.DataFrame(rows).round(3).to_string())
# family tests vs other-window nights (Fisher)
for fam, lab in [("AH_PRINT", "any_first_bar"), ("AH_PRINT", "any_at_tko"), ("AH_PRINT", "mid_close"), ("HEADLINE", "trend_close"), ("HEADLINE", "high_at_tokyo_open"),
                 ("HEADLINE", "high_in_last_bar"), ("HEADLINE", "cont"), ("ASIA_CHIP", "cont"), ("ASIA_CHIP", "low_in_last_bar")]:
    g = w[w.family == fam]; o = w[w.is_cat == 0]
    print(f"    {fam:10s} {lab:18s} n={len(g)} rate={g[lab].mean():.3f} vs other-window {o[lab].mean():.3f} (n={len(o)}) p_fisher={fisher(int(g[lab].sum()), len(g), int(o[lab].sum()), len(o)):.3f} "
          f"| vs full-table {x[lab].mean():.3f} p_binom={stats.binomtest(int(g[lab].sum()), len(g), x[lab].mean()).pvalue:.3f}")
# big_asia_cash within catalogue
g1 = w[cat & (w.big_asia_cash == 1)]; g0 = w[cat & (w.big_asia_cash == 0)]
print(f"  big_asia_cash=1 n={len(g1)} any_at_tko={g1.any_at_tko.mean():.3f} | =0 n={len(g0)} any_at_tko={g0.any_at_tko.mean():.3f} p_fisher={fisher(int(g1.any_at_tko.sum()), len(g1), int(g0.any_at_tko.sum()), len(g0)):.3f}; "
      f"other-window any_at_tko={other.any_at_tko.mean():.3f}")
print("  number of family x label cells in the lens family table: 6 families x ~22 columns =", 6 * 22)

# ------------------------------------------------------------------ F10 pos_in_range at Tokyo-open bar
print("\n================ F10 pos_in_range at k=tokyo_open_k")
def tko_table(p, x, sym):
    p9 = p[p.n_bars == 9]
    t = p9[p9.k == p9.tokyo_open_k].merge(x[["sunday_open", "half"]], left_on="date", right_index=True, suffixes=("", "_x"))
    print(f"  {sym}: n sessions at k=tko: {len(t)}; base P(high_done)={t.high_done.mean():.3f} P(low_done)={t.low_done.mean():.3f}; "
          f"check vs hi_k<=tko: {(t.hi_k <= t.tokyo_open_k).mean():.3f}")
    for nm, c in [("pos<0.2", t.pos_in_range < 0.2), ("pos<0.2 & rr>=0.7", (t.pos_in_range < 0.2) & (t.run_rng_vs_med20 >= 0.7)), ("pos<0.2 & rr<0.4", (t.pos_in_range < 0.2) & (t.run_rng_vs_med20 < 0.4)),
                  ("sunday & pos<0.2", (t.pos_in_range < 0.2) & (t.sunday_open == 1)), ("weekday & pos<0.2", (t.pos_in_range < 0.2) & (t.sunday_open == 0))]:
        rate_vs_rest(t, c, "high_done", f"{sym} {nm}")
    for nm, c in [("pos>=0.8", t.pos_in_range >= 0.8), ("pos>=0.8 & rr>=0.7", (t.pos_in_range >= 0.8) & (t.run_rng_vs_med20 >= 0.7)), ("pos>=0.8 & rr<0.4", (t.pos_in_range >= 0.8) & (t.run_rng_vs_med20 < 0.4)),
                  ("sunday & pos>=0.8", (t.pos_in_range >= 0.8) & (t.sunday_open == 1)), ("weekday & pos>=0.8", (t.pos_in_range >= 0.8) & (t.sunday_open == 0))]:
        rate_vs_rest(t, c, "low_done", f"{sym} {nm}")
    # is k=tko special? same conditional at every k (pooled over DST) and at k=tko-1, tko+1
    print(f"  {sym}: P(high_done | pos<0.2) and P(low_done | pos>=0.8) by k (all 9-bar sessions):")
    for k in range(0, 8):
        s = p9[p9.k == k]; a = s[s.pos_in_range < 0.2]; b = s[s.pos_in_range >= 0.8]
        print(f"    k={k}: base hi={s.high_done.mean():.2f} | pos<0.2 n={len(a)} hi_done={a.high_done.mean():.2f} (lift {a.high_done.mean() - s.high_done.mean():+.2f}) || base lo={s.low_done.mean():.2f} | pos>=0.8 n={len(b)} lo_done={b.low_done.mean():.2f} (lift {b.low_done.mean() - s.low_done.mean():+.2f})")
    for off, nm in [(-1, "tko-1"), (1, "tko+1")]:
        s = p9[p9.k == p9.tokyo_open_k + off]; a = s[s.pos_in_range < 0.2]; b = s[s.pos_in_range >= 0.8]
        print(f"    k={nm}: base hi={s.high_done.mean():.2f} pos<0.2 n={len(a)} hi_done={a.high_done.mean():.2f} || base lo={s.low_done.mean():.2f} pos>=0.8 n={len(b)} lo_done={b.low_done.mean():.2f}")
    # does pos_in_range add beyond bars_since_hi? at k=tko
    for bs in [0, 1, 2]:
        s = t[t.bars_since_hi == bs] if bs < 2 else t[t.bars_since_hi >= 2]
        a = s[s.pos_in_range < 0.2]
        print(f"    k=tko bars_since_hi{'>=' if bs == 2 else '=='}{bs}: n={len(s)} hi_done={s.high_done.mean():.2f} | & pos<0.2 n={len(a)} hi_done={a.high_done.mean():.2f}")
    return t
tN = tko_table(p, x, "NQ"); tE = tko_table(pe, e, "ES")

# ------------------------------------------------------------------ F11 momentum after Tokyo-open bar
print("\n================ F11 momentum")
def mom(p, x, sym):
    p9 = p[p.n_bars == 9]
    t = p9[p9.k == p9.tokyo_open_k][["date", "cum_ret_bp"]].set_index("date")
    xx = x.join(t, how="inner"); xx["rest"] = xx.close_bp - xx.cum_ret_bp
    xx["rest_cont"] = (np.sign(xx.rest) == np.sign(xx.cum_ret_bp)).astype(int)
    for nm, c in [("all", xx.cum_ret_bp.abs() >= 0), ("|move|>=20", xx.cum_ret_bp.abs() >= 20), ("|move|>=40", xx.cum_ret_bp.abs() >= 40), ("sunday", xx.sunday_open == 1),
                  ("megacap|post>=15", (xx.megacap_earnings_tonight == 1) | (xx.abs_post >= 15)), ("|kospi|>=3", xx.abs_kospi >= 3)]:
        s = xx[c]; k = int(s.rest_cont.sum()); n = len(s)
        print(f"  {sym} rest continues [{nm}] n={n} rate={k / n:.3f} CI90={bci(s.rest_cont.values)} p_vs_0.5={stats.binomtest(k, n, 0.5).pvalue:.3f} "
              f"H1={s[s.half == 'H1'].rest_cont.mean():.3f} (n={(s.half == 'H1').sum()}) H2={s[s.half == 'H2'].rest_cont.mean():.3f}")
    # first-bar impulse
    x2 = x.copy(); x2["rest"] = x2.asia_ret_bp - x2.first_bar_ret_bp; x2["agree"] = (np.sign(x2.first_bar_ret_bp) == np.sign(x2.rest)).astype(int)
    big = x2.first_bar_ret_bp.abs() >= 20
    hd = (x2.megacap_earnings_tonight == 1) | (x2.sunday_open == 1) | (x2.fomc_today == 1) | (x2.abs_post >= 15)
    for nm, c in [("|fb|>=20", big), ("headline proxy & |fb|>=20", hd & big), ("no proxy & |fb|>=20", (~hd) & big),
                  ("catalogue & |fb|>=20 (ex post)", (x2.index.isin(c_idx)) & big), ("window non-cat & |fb|>=20 (ex post)", (~x2.index.isin(c_idx)) & (x2.index >= "2025-11-01") & big)]:
        s = x2[c]; k = int(s.agree.sum()); n = len(s)
        print(f"  {sym} bar0 impulse continues [{nm}] n={n} rate={k / n:.3f} CI90={bci(s.agree.values)} p_vs_0.5={stats.binomtest(k, n, 0.5).pvalue:.3f} "
              f"H1={s[s.half == 'H1'].agree.mean() if (s.half == 'H1').sum() else float('nan'):.3f} H2={s[s.half == 'H2'].agree.mean():.3f}")
c_idx = c.index
mom(p, x, "NQ"); mom(pe, e, "ES")

# ------------------------------------------------------------------ F12 15m timing
print("\n================ F12 15m timing")
m15 = pd.read_csv(f"{ROOT}/data/NQ_15m.csv"); tc = m15.columns[0]
m15[tc] = pd.to_datetime(m15[tc], utc=True).dt.tz_convert("America/New_York"); m15 = m15.set_index(tc).sort_index()
print("  15m range:", m15.index.min(), m15.index.max(), " rows:", len(m15))
m15["gdate"] = m15.index.date; sh = m15.index.hour >= 18
m15.loc[sh, "gdate"] = (m15.index[sh] + pd.Timedelta(days=1)).date
asia = m15[m15.index.hour.isin([18, 19, 20, 21, 22, 23, 0, 1, 2])]
recs = []
for gd, g in asia.groupby("gdate"):
    if len(g) < 24:
        continue
    ih = g.High.values.argmax(); il = g.Low.values.argmin(); th = g.index[ih]; tl = g.index[il]
    d = x.index[x.asia_gdate == str(gd)]
    if len(d) == 0:
        continue
    r = x.loc[d[0]]
    # tie check: how many 15m bars share the max High / min Low
    recs.append(dict(date=d[0], nbars15=len(g), hi_t=th.strftime("%H:%M"), lo_t=tl.strftime("%H:%M"), hi_h=th.hour, hi_m=th.minute, lo_h=tl.hour, lo_m=tl.minute,
                     hi_k=r.hi_k, lo_k=r.lo_k, dst=r.is_dst, hi_ties=int((g.High.values == g.High.max()).sum()), lo_ties=int((g.Low.values == g.Low.min()).sum()),
                     hi1h=g.High.max(), lo1h=g.Low.min(), x_hi=r.asia_high, x_lo=r.asia_low))
t15 = pd.DataFrame(recs)
print("  sessions:", len(t15), " nbars15 counts:", t15.nbars15.value_counts().to_dict(), " ties hi>1:", int((t15.hi_ties > 1).sum()), " lo>1:", int((t15.lo_ties > 1).sum()))
print("  15m-vs-1h high mismatch (|diff|>0.5):", int((t15.hi1h - t15.x_hi).abs().gt(0.5).sum()), " low mismatch:", int((t15.lo1h - t15.x_lo).abs().gt(0.5).sum()))
b0h = t15[t15.hi_h == 18]; b0l = t15[t15.lo_h == 18]
print(f"  bar-0 highs n={len(b0h)} in 18:00 sub-bar={int((b0h.hi_m == 0).sum())}; bar-0 lows n={len(b0l)} in 18:00 sub-bar={int((b0l.lo_m == 0).sum())}; "
      f"combined {int((b0h.hi_m == 0).sum() + (b0l.lo_m == 0).sum())}/{len(b0h) + len(b0l)}")
kk = int((b0h.hi_m == 0).sum() + (b0l.lo_m == 0).sum()); nn = len(b0h) + len(b0l)
print(f"    vs uniform 0.25: exact binomial p={stats.binomtest(kk, nn, 0.25).pvalue:.2e} CI90={bci(np.r_[(b0h.hi_m == 0).values, (b0l.lo_m == 0).values].astype(float))}")
# is the 18:00 sub-bar extreme the OPEN print? compare the 18:00 15m bar's Open with its High/Low
op = []
for gd, g in asia.groupby("gdate"):
    if len(g) < 24: continue
    f0 = g.iloc[0]
    op.append(dict(gdate=gd, open_is_high=f0.Open == f0.High, open_is_low=f0.Open == f0.Low, sess_hi_is_open=(f0.Open == g.High.max()), sess_lo_is_open=(f0.Open == g.Low.min())))
op = pd.DataFrame(op)
print(f"  18:00 print itself is the session high: {int(op.sess_hi_is_open.sum())}/{len(op)}; session low: {int(op.sess_lo_is_open.sum())}/{len(op)}")
l2 = t15[t15.lo_h == 2]; h2_ = t15[t15.hi_h == 2]
print(f"  02:00-bar lows n={len(l2)} by sub-bar: {l2.lo_m.value_counts().sort_index().to_dict()}; 02:00-bar highs n={len(h2_)}: {h2_.hi_m.value_counts().sort_index().to_dict()}")
print(f"    02:45 share {int((l2.lo_m == 45).sum())}/{len(l2)} vs 0.25: p={stats.binomtest(int((l2.lo_m == 45).sum()), len(l2), 0.25).pvalue:.3f}")
tk_h = np.where(t15.dst == 1, 20, 19)
th_ = t15[t15.hi_h == tk_h]; tl_ = t15[t15.lo_h == tk_h]
print(f"  Tokyo-open-bar highs n={len(th_)}: {th_.hi_m.value_counts().sort_index().to_dict()}; lows n={len(tl_)}: {tl_.lo_m.value_counts().sort_index().to_dict()}")
print("  minute-of-hour all highs:", t15.hi_m.value_counts().sort_index().to_dict(), " lows:", t15.lo_m.value_counts().sort_index().to_dict())
# same for ES 15m as a replication
e15 = pd.read_csv(f"{ROOT}/data/ES_15m.csv"); tc = e15.columns[0]
e15[tc] = pd.to_datetime(e15[tc], utc=True).dt.tz_convert("America/New_York"); e15 = e15.set_index(tc).sort_index()
e15["gdate"] = e15.index.date; sh = e15.index.hour >= 18; e15.loc[sh, "gdate"] = (e15.index[sh] + pd.Timedelta(days=1)).date
ea = e15[e15.index.hour.isin([18, 19, 20, 21, 22, 23, 0, 1, 2])]
er = []
for gd, g in ea.groupby("gdate"):
    if len(g) < 24: continue
    th = g.index[g.High.values.argmax()]; tl = g.index[g.Low.values.argmin()]
    er.append(dict(hi_h=th.hour, hi_m=th.minute, lo_h=tl.hour, lo_m=tl.minute))
er = pd.DataFrame(er)
eb0h = er[er.hi_h == 18]; eb0l = er[er.lo_h == 18]; el2 = er[er.lo_h == 2]
print(f"  ES: sessions={len(er)} bar-0 highs {int((eb0h.hi_m == 0).sum())}/{len(eb0h)} in 18:00 sub-bar; bar-0 lows {int((eb0l.lo_m == 0).sum())}/{len(eb0l)}; 02:00-bar lows by sub-bar {el2.lo_m.value_counts().sort_index().to_dict()}")

# ------------------------------------------------------------------ F13 TSMC
print("\n================ F13 TSMC")
tsmc = ["2024-07-17", "2024-10-16", "2025-01-15", "2025-04-16", "2025-07-16", "2025-10-15", "2026-01-14", "2026-04-15", "2026-07-15", "2026-10-14"]
tt = x.loc[x.index.isin(pd.to_datetime(tsmc))]
print(tt[["is_dst", "n_bars", "hi_k", "lo_k", "asia_ret_bp", "rng_bp", "close_loc", "megacap_earnings_tonight", "events_tonight_tomorrow"]].to_string())
k7 = int((tt.hi_k >= 7).sum()); n = len(tt)
base = (x.hi_k >= x.n_bars - 2).mean(); base9 = (x[x.n_bars == 9].hi_k >= 7).mean()
print(f"  hi_k>=7: {k7}/{n}; base P(hi_k in last 2 bars)={base:.3f}; p_binom={stats.binomtest(k7, n, base).pvalue:.2e}")
up_base = (x[x.asia_ret_bp > 0].hi_k >= x[x.asia_ret_bp > 0].n_bars - 2).mean()
print(f"  TSMC nights asia_up: {int((tt.asia_ret_bp > 0).sum())}/{n}; among up-nights base P(hi in last 2 bars)={up_base:.3f}; p_binom vs up-night base={stats.binomtest(k7, n, up_base).pvalue:.3f}")
# control: other Wednesday sessions in Jan/Apr/Jul/Oct weeks 2-3 (earnings-season mid-month Wednesdays) not TSMC
wed = x[(x.index.dayofweek == 2) & (x.index.month.isin([1, 4, 7, 10])) & (x.index.day >= 8) & (x.index.day <= 23) & (~x.index.isin(pd.to_datetime(tsmc)))]
print(f"  control mid-month Wednesdays in Jan/Apr/Jul/Oct (non-TSMC) n={len(wed)}: P(hi_k>=7)={(wed.hi_k >= wed.n_bars - 2).mean():.3f}")
wedall = x[(x.index.dayofweek == 2) & (~x.index.isin(pd.to_datetime(tsmc)))]
print(f"  all other Wednesdays n={len(wedall)}: P(hi_k in last2)={(wedall.hi_k >= wedall.n_bars - 2).mean():.3f}; high_in_last_bar={wedall.high_in_last_bar.mean():.3f}")
print(f"  TSMC nights with megacap_earnings_tonight=1: {int(tt.megacap_earnings_tonight.sum())}")
# ES replication
te = e.loc[e.index.isin(pd.to_datetime(tsmc))]
print(f"  ES TSMC nights hi_k: {te.hi_k.tolist()} -> hi_k>=7: {int((te.hi_k >= 7).sum())}/{len(te)}; ES base {(e.hi_k >= e.n_bars - 2).mean():.3f}")
