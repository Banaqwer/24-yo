import numpy as np, pandas as pd
from scipy import stats
import io, contextlib, sys
sys.path.insert(0, "research/extremes/scripts/refute_narrative_leak")
with contextlib.redirect_stdout(io.StringIO()):
    from recompute import load, lp, bp, bci, ROOT

x = load("NQ"); e = load("ES"); p = lp("NQ"); pe = lp("ES")

# ---- F8: are the 6-bar sessions real early closes or data gaps? list the ET hours present ----
h = pd.read_csv(f"{ROOT}/data/NQ_1h.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("America/New_York")
short = x[x.n_bars < 9]
for d, r in short.iterrows():
    gd = pd.Timestamp(r.asia_gdate)
    hn = h.index.tz_localize(None)
    bars = h[(hn >= (gd - pd.Timedelta(days=1)).replace(hour=18)) & (hn < gd.replace(hour=3))]
    hrs = sorted(set(bars.index.hour)); print(f"F8 short session RTH date {d.date()} asia_gdate {gd.date()} n_bars={r.n_bars} hours present: {hrs} holiday_flag={int(r.holiday_tomorrow or r.pre_holiday)}")
# also: what does the next bar after the 6-bar session look like (is 00:00-02:00 missing entirely in yfinance)?
d = pd.Timestamp("2025-11-26"); print(h[(h.index >= "2025-11-26 17:00-05:00") & (h.index <= "2025-11-27 10:00-05:00")][["Open", "High", "Low", "Close", "Volume"]])
# ES holiday
he = e[(e.holiday_tomorrow == 1) | (e.pre_holiday == 1)]
print(f"F8 ES: holiday n={len(he)} n_bars dist {he.n_bars.value_counts().to_dict()} median rng={he.rng_bp.median():.0f} vs all {e.rng_bp.median():.0f}; 9-bar only n={(he.n_bars==9).sum()} median {he[he.n_bars==9].rng_bp.median():.0f} vs all 9-bar {e[e.n_bars==9].rng_bp.median():.0f}")
x9 = x[x.n_bars == 9]; h9 = x9[(x9.holiday_tomorrow == 1) | (x9.pre_holiday == 1)]
print(f"F8 NQ 9-bar holiday: {h9.rng_bp.tolist()} median {h9.rng_bp.median():.0f}; MW p vs other 9-bar = {stats.mannwhitneyu(h9.rng_bp, x9.drop(h9.index).rng_bp).pvalue:.3f}")
sh = x[x.n_bars < 9]; print(f"F8 short-session range median {sh.rng_bp.median():.0f} (n={len(sh)}) vs 9-bar {x9.rng_bp.median():.0f}; short sessions NOT holiday-flagged: {sh[(sh.holiday_tomorrow==0)&(sh.pre_holiday==0)].index.date.tolist()}")

# ---- F7: FOMC nights without a megacap print ----
f = x[x.fomc_today == 1]; fm = f[f.megacap_earnings_tonight == 0]; fe = f[f.megacap_earnings_tonight == 1]
for nm, g in [("FOMC all", f), ("FOMC no megacap", fm), ("FOMC & megacap", fe)]:
    print(f"F7 {nm}: n={len(g)} rng med={g.rng_bp.median():.0f} any_first_bar={g.any_first_bar.mean():.2f} any_last_bar={g.any_last_bar.mean():.2f} low_first={g.low_in_first_bar.mean():.2f} |post| med={g.abs_post.median():.0f} bp")
mg = x[(x.megacap_earnings_tonight == 1) & (x.fomc_today == 0)]
print(f"F7 megacap non-FOMC: n={len(mg)} rng={mg.rng_bp.median():.0f} any_first_bar={mg.any_first_bar.mean():.2f} any_last_bar={mg.any_last_bar.mean():.2f}")
ef = e[e.fomc_today == 1]; efm = ef[ef.megacap_earnings_tonight == 0]
print(f"F7 ES FOMC all n={len(ef)} rng={ef.rng_bp.median():.0f} vs {e.rng_bp.median():.0f}; ES FOMC no-megacap n={len(efm)} rng={efm.rng_bp.median():.0f} any_first={efm.any_first_bar.mean():.2f} any_last={efm.any_last_bar.mean():.2f}")

# ---- F10: is the pos_in_range signal specific to the Tokyo-open bar? compare k=1 EST (tko) vs k=1 EDT (pre-Tokyo), k=2 EDT (tko) vs k=2 EST (post) ----
for pp, nm in [(p, "NQ"), (pe, "ES")]:
    pp = pp[pp.n_bars == 9]
    for k in [1, 2]:
        for dst in [0, 1]:
            s = pp[(pp.k == k) & (pp.is_dst == dst)]
            a = s[s.pos_in_range < .2]; b = s[s.pos_in_range >= .8]
            tag = "TKO" if ((k == 1 and dst == 0) or (k == 2 and dst == 1)) else ("pre" if k == 1 else "post")
            print(f"F10 {nm} k={k} is_dst={dst} [{tag}-Tokyo]: pos<0.2 -> P(high_done)={a.high_done.mean():.2f} (n={len(a)}); pos>=0.8 -> P(low_done)={b.low_done.mean():.2f} (n={len(b)}); base hd={s.high_done.mean():.2f} ld={s.low_done.mean():.2f}")

# ---- F13: Thursday-night control n, and all nights with hi_k>=7 by month-week ----
thu = x[(x.index.dayofweek == 3) & (x.index.month.isin([1, 4, 7, 10])) & (x.index.day >= 12) & (x.index.day <= 21)]
print(f"F13 Thursday control n={len(thu)} P(hi_k>=7)={thu.hi_ge7.mean():.3f}; all mid-month (12-21) nights in Jan/Apr/Jul/Oct n={len(x[(x.index.month.isin([1,4,7,10]))&(x.index.day>=12)&(x.index.day<=21)])} P={x[(x.index.month.isin([1,4,7,10]))&(x.index.day>=12)&(x.index.day<=21)].hi_ge7.mean():.3f}")
ts = pd.to_datetime(["2024-07-17", "2024-10-16", "2025-01-15", "2025-04-16", "2025-07-16", "2025-10-15", "2026-01-14", "2026-04-15", "2026-07-15", "2026-10-14"])
mm = x[(x.index.month.isin([1, 4, 7, 10])) & (x.index.day >= 12) & (x.index.day <= 21)].drop(ts, errors="ignore")
print(f"F13 same-window non-TSMC nights n={len(mm)} P(hi_k>=7)={mm.hi_ge7.mean():.3f} vs TSMC 9/10; p(9/10 vs {mm.hi_ge7.mean():.2f})={bp(9,10,mm.hi_ge7.mean()):.4f}")
# the EST nights: release at 01:00 ET (bar 7). hi_k for 2025-01-15 is 8 (bar after), 2026-01-14 is 7.
print("F13 is the high in the release bar or after? EDT nights (release in bar 8):", x.loc[ts[x.loc[ts].is_dst == 1], "hi_k"].tolist(), " EST nights (release in bar 7):", x.loc[ts[x.loc[ts].is_dst == 0], "hi_k"].tolist())

# ---- F4 fair comparison: P(low_done | k, bars_since_lo = k - tko) kospi vs all ----
p9 = p[p.n_bars == 9].merge(x[["abs_kospi"]], left_on="date", right_index=True)
for k in [3, 4, 5]:
    for nm, c in [("all", p9.k >= 0), ("|kospi|>=3", p9.abs_kospi >= 3)]:
        s = p9[c & (p9.k == k) & ((p9.k - p9.bars_since_lo) == p9.tokyo_open_k)]
        t = p9[c & (p9.k == k) & ((p9.k - p9.bars_since_lo) == p9.tokyo_open_k - 1)]
        u = p9[c & (p9.k == k) & ((p9.k - p9.bars_since_lo) == 0)]
        print(f"F4 k={k} {nm}: P(low_done | low set in tko bar)={s.low_done.mean():.2f} (n={len(s)}); low set in bar tko-1: {t.low_done.mean():.2f} (n={len(t)}); low set in bar 0: {u.low_done.mean():.2f} (n={len(u)})")

# ---- F5: 'running high at the RTH high near-certain to hold': how close does price get to the RTH high on -150 nights? ----
d15 = x[x.rth_ret_bp <= -150]
print(f"F5 -150 nights: hi_vs_rth_high_bp median {d15.hi_vs_rth_high_bp.median():.0f}, max {d15.hi_vs_rth_high_bp.max():.0f}; share within 30bp of RTH high: {(d15.hi_vs_rth_high_bp>=-30).mean():.2f}")
# F5 encoding alt: at the first break of the RTH low, how much further does price fall? remaining_down_bp
pm = p9.merge(x[["rth_ret_bp"]], left_on="date", right_index=True).sort_values(["date", "k"])
pm["prev"] = pm.groupby("date").run_lo_below_rth_low.shift(1).fillna(0)
fb = pm[(pm.run_lo_below_rth_low == 1) & (pm.prev == 0)]
for nm, c in [("all", fb.k >= 0), ("rth<=-150", fb.rth_ret_bp <= -150)]:
    g = fb[c]; print(f"F5 first RTH-low-break bar {nm}: n={len(g)} P(low_done)={g.low_done.mean():.2f} median remaining_down={g.remaining_down_bp.median():.0f} bp; P(low_done | bars_left<=2)={g[g.bars_left<=2].low_done.mean():.2f} (n={(g.bars_left<=2).sum()})")
