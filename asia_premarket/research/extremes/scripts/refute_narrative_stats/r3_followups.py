"""Follow-ups: F4 quarter-stratified (CMH), F10 per-DST by-k curves, F12 opening print check, F3/F4 extra cells."""
import sys
sys.path.insert(0, "research/extremes/scripts/refute_narrative_stats")
import numpy as np, pandas as pd
from scipy import stats
from common_r import *


class StratifiedTable:
    """Mantel-Haenszel pooled OR and CMH chi-square test (hand-rolled; tables are [[a,b],[c,d]] with rows = exposed/unexposed)."""
    def __init__(self, tabs):
        self.tabs = [np.asarray(t, dtype=float) for t in tabs]
        num = sum(t[0, 0] * t[1, 1] / t.sum() for t in self.tabs); den = sum(t[0, 1] * t[1, 0] / t.sum() for t in self.tabs)
        self.oddsratio_pooled = num / den if den > 0 else np.inf

    def test_null_odds(self):
        num = 0.0; var = 0.0
        for t in self.tabs:
            n = t.sum(); r1 = t[0].sum(); c1 = t[:, 0].sum(); r2 = t[1].sum(); c2 = t[:, 1].sum()
            if n < 2: continue
            num += t[0, 0] - r1 * c1 / n; var += r1 * r2 * c1 * c2 / (n * n * (n - 1))
        chi2 = num ** 2 / var if var > 0 else 0.0

        class R: pass
        r = R(); r.statistic = chi2; r.pvalue = float(stats.chi2.sf(chi2, 1)); return r

x = load_x("NQ"); e = load_x("ES"); p = load_p("NQ"); pe = load_p("ES")

print("================ F4 regime stratification")
for sym, d in [("NQ", x), ("ES", e)]:
    d = d.copy(); d["q"] = d.index.to_period("Q").astype(str); kb = d.abs_kospi >= 3
    print(f"  {sym} kospi>=3 nights by quarter:", d[kb].q.value_counts().sort_index().to_dict())
    print(f"  {sym} any_at_tko by quarter, kospi nights vs other:")
    tabs = []
    for q, g in d.groupby("q"):
        a = g[g.abs_kospi >= 3]; b = g[g.abs_kospi < 3]
        if len(a) >= 3:
            print(f"    {q}: kospi n={len(a)} rate={a.any_at_tko.mean():.2f} | other n={len(b)} rate={b.any_at_tko.mean():.2f}")
        if len(a) >= 1 and len(b) >= 1:
            tabs.append(np.array([[a.any_at_tko.sum(), len(a) - a.any_at_tko.sum()], [b.any_at_tko.sum(), len(b) - b.any_at_tko.sum()]]))
    st = StratifiedTable(tabs)
    print(f"  {sym} CMH stratified by quarter: pooled OR={st.oddsratio_pooled:.2f} p={st.test_null_odds().pvalue:.4f}; crude OR={stats.fisher_exact([[d[kb].any_at_tko.sum(), (~d[kb].any_at_tko.astype(bool)).sum()], [d[~kb].any_at_tko.sum(), (~d[~kb].any_at_tko.astype(bool)).sum()]])[0]:.2f}")
    # same for low_in_last_bar and rng
    tabs = []
    for q, g in d.groupby("q"):
        a = g[g.abs_kospi >= 3]; b = g[g.abs_kospi < 3]
        if len(a) >= 1 and len(b) >= 1:
            tabs.append(np.array([[a.low_in_last_bar.sum(), len(a) - a.low_in_last_bar.sum()], [b.low_in_last_bar.sum(), len(b) - b.low_in_last_bar.sum()]]))
    st = StratifiedTable(tabs); print(f"  {sym} CMH low_in_last_bar: pooled OR={st.oddsratio_pooled:.2f} p={st.test_null_odds().pvalue:.4f}")
    # half-year strata (coarser)
    d["hy"] = d.index.year.astype(str) + "H" + ((d.index.month > 6) + 1).astype(str)
    tabs = []
    for q, g in d.groupby("hy"):
        a = g[g.abs_kospi >= 3]; b = g[g.abs_kospi < 3]
        if len(a) >= 1 and len(b) >= 1:
            tabs.append(np.array([[a.any_at_tko.sum(), len(a) - a.any_at_tko.sum()], [b.any_at_tko.sum(), len(b) - b.any_at_tko.sum()]]))
    st = StratifiedTable(tabs); print(f"  {sym} CMH any_at_tko stratified by half-year: pooled OR={st.oddsratio_pooled:.2f} p={st.test_null_odds().pvalue:.4f}")
# kospi x sox cells
for nm, c in [("kospi>=3 & sox>=3", (x.abs_kospi >= 3) & (x.abs_sox >= 3)), ("kospi>=3 & sox<3", (x.abs_kospi >= 3) & (x.abs_sox < 3)), ("kospi<3 & sox>=3", (x.abs_kospi < 3) & (x.abs_sox >= 3)),
              ("kospi<3 & sox<3", (x.abs_kospi < 3) & (x.abs_sox < 3))]:
    s = x[c]; print(f"  NQ {nm}: n={len(s)} any_at_tko={s.any_at_tko.mean():.3f} H2-only n={(s.half == 'H2').sum()} rate={s[s.half == 'H2'].any_at_tko.mean():.3f}")
# 2026Q2-Q3 window only: kospi vs other
w = x[(x.index >= "2026-04-01") & (x.index < "2026-10-01")]
rate_vs_rest(w, w.abs_kospi >= 3, "any_at_tko", "NQ 2026Q2-Q3 only kospi>=3")
rate_vs_rest(w, w.abs_kospi >= 3, "low_in_last_bar", "NQ 2026Q2-Q3 only kospi>=3")
cont_vs_rest(w, w.abs_kospi >= 3, "rng_bp", "NQ 2026Q2-Q3 only kospi>=3")

print("\n================ F10 per-DST by-k curves (is the Tokyo-open bar a discontinuity?)")
for sym, pp in [("NQ", p), ("ES", pe)]:
    p9 = pp[pp.n_bars == 9]
    for d in (1, 0):
        s = p9[p9.is_dst == d]; tko = int(s.tokyo_open_k.iloc[0])
        line = []
        for k in range(0, 6):
            sk = s[s.k == k]; a = sk[sk.pos_in_range < 0.2]; b = sk[sk.pos_in_range >= 0.8]
            line.append(f"k{k}{'*' if k == tko else ''}: hi {a.high_done.mean():.2f}(n={len(a)}) lo {b.low_done.mean():.2f}(n={len(b)})")
        print(f"  {sym} dst={d} (tko=k{tko}): " + " | ".join(line))
    # a simple logistic-free check: at k=tko, does P(high_done | pos<0.2) differ from P(high_done | pos<0.2) at k=tko+1 or tko-1 after controlling k? (just print)

print("\n================ F12 opening-print check")
m15 = pd.read_csv(f"{ROOT}/data/NQ_15m.csv"); tc = m15.columns[0]
m15[tc] = pd.to_datetime(m15[tc], utc=True).dt.tz_convert("America/New_York"); m15 = m15.set_index(tc).sort_index()
m15["gdate"] = m15.index.date; sh = m15.index.hour >= 18; m15.loc[sh, "gdate"] = (m15.index[sh] + pd.Timedelta(days=1)).date
asia = m15[m15.index.hour.isin([18, 19, 20, 21, 22, 23, 0, 1, 2])]
rows = []
for gd, g in asia.groupby("gdate"):
    if len(g) < 24: continue
    f0 = g.iloc[0]; sh_ = g.High.max(); sl_ = g.Low.min()
    rows.append(dict(gdate=gd, open=f0.Open, b0_high=f0.High, b0_low=f0.Low, sess_hi=sh_, sess_lo=sl_,
                     hi_in_first15=(f0.High == sh_), lo_in_first15=(f0.Low == sl_), open_eq_b0_high=abs(f0.Open - f0.High) < 0.3, open_eq_b0_low=abs(f0.Open - f0.Low) < 0.3,
                     open_to_b0_high_bp=(f0.High / f0.Open - 1) * 1e4, open_to_b0_low_bp=(f0.Low / f0.Open - 1) * 1e4))
r = pd.DataFrame(rows)
print(f"  sessions={len(r)}; session high in the first 15m bar: {int(r.hi_in_first15.sum())}; of those the open print IS the bar high (within 1 tick): {int((r.hi_in_first15 & r.open_eq_b0_high).sum())}")
print(f"  session low in the first 15m bar: {int(r.lo_in_first15.sum())}; of those the open print IS the bar low: {int((r.lo_in_first15 & r.open_eq_b0_low).sum())}")
print("  first-15m sessions where the extreme is in the first bar: open->extreme distance (bp):")
print("   highs:", r[r.hi_in_first15].open_to_b0_high_bp.round(1).tolist())
print("   lows :", r[r.lo_in_first15].open_to_b0_low_bp.round(1).tolist())
print(f"  all sessions: open==first-bar high within 1 tick: {int(r.open_eq_b0_high.sum())}/{len(r)}; open==first-bar low: {int(r.open_eq_b0_low.sum())}/{len(r)}")
# 1h data: how often is the 18:00 hourly Open equal to the hourly High/Low (full sample, proxy for 'the 18:00 print is the bar-0 extreme')
raw = pd.read_csv(f"{ROOT}/data/NQ_1h.csv"); tc = raw.columns[0]
raw[tc] = pd.to_datetime(raw[tc], utc=True).dt.tz_convert("America/New_York"); raw = raw.set_index(tc)
b0 = raw[raw.index.hour == 18]
print(f"  1h bars at 18:00 (n={len(b0)}): Open==High {int((b0.Open == b0.High).sum())}, Open==Low {int((b0.Open == b0.Low).sum())}; "
      f"median |open->high| {((b0.High / b0.Open - 1) * 1e4).median():.1f} bp, |open->low| {((1 - b0.Low / b0.Open) * 1e4).median():.1f} bp")

print("\n================ F1: catalogue nights' big_asia_cash vs the k0 |gap| etc. (nothing new); F3 extra: megacap & |post|>=25 union")
u = (x.megacap_earnings_tonight == 1) | (x.abs_post >= 25)
for lab in ["any_last_bar", "high_in_first_bar", "any_first_bar"]:
    rate_vs_rest(x, u, lab, "NQ ah_print union")
eu = (e.megacap_earnings_tonight == 1) | (e.abs_post >= 25)
for lab in ["any_last_bar", "high_in_first_bar"]:
    rate_vs_rest(e, eu, lab, "ES ah_print union")
