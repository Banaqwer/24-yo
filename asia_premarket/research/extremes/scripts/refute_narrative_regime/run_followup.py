"""Follow-ups: F4 2026-only base; F1 catalogue selection rule; F8 6-bar sessions; F12 15m open semantics."""
import sys
sys.path.insert(0, "research/extremes/scripts/refute_narrative_regime")
import numpy as np, pandas as pd
from scipy import stats
from robust import *
LENS = "research/extremes/scripts/lens_narrative"
pd.set_option("display.width", 300, "display.max_columns", 50, "display.max_rows", 500)
x = load_extremes("NQ"); xe = load_extremes("ES")

# ---------------- F4 with regime-matched bases ----------------
print("=" * 90 + "\nF4 |kospi|>=3% vs regime-matched bases")
kb = x.abs_kospi >= 3
for nm, w in [("full", x), ("2026 only", x[x.index >= "2026-01-01"]), ("2026 ex Iran war", x[(x.index >= "2026-01-01") & ~in_regime(x.index, "iran26_war")]),
              ("2025-11-01 onward", x[x.index >= "2025-11-01"]), ("H2", x[x.half == "H2"])]:
    c = w.abs_kospi >= 3
    for lab in ["any_at_tko", "low_at_tokyo_open", "high_at_tokyo_open", "low_in_last_bar"]:
        s = w[c]; b = w[~c][lab].mean(); k = int(s[lab].sum()); n = len(s)
        print(f"  {nm:18s} {lab:19s} n={n:3d} {k/n:.3f} v non-kospi base {b:.3f} p={binom_p(k, n, b):.3g}")
    s = w[c].rng_bp; r = w[~c].rng_bp
    print(f"  {nm:18s} rng_bp median {s.median():.0f} v {r.median():.0f} p_MW={stats.mannwhitneyu(s, r).pvalue:.3g}; rng/med20 {(w[c].rng_bp/w[c].asia_rng_med20).median():.2f} v {(w[~c].rng_bp/w[~c].asia_rng_med20).median():.2f}")
# monthly within 2026: kospi vs non-kospi any_at_tko
w = x[x.index >= "2025-11-01"]
print("  by quarter (kospi vs NON-kospi in the same quarter):")
for q, g in w.groupby("quarter"):
    a = g[g.abs_kospi >= 3]; b = g[g.abs_kospi < 3]
    print(f"    {q}: kospi n={len(a)} any_at_tko={a.any_at_tko.mean():.2f} rng={a.rng_bp.median():.0f} | other n={len(b)} any_at_tko={b.any_at_tko.mean():.2f} rng={b.rng_bp.median():.0f}")
# ES with 2026-only base
we = xe[xe.index >= "2026-01-01"]; ce = we.abs_kospi >= 3
print(f"  ES 2026-only: kospi n={ce.sum()} any_at_tko={we[ce].any_at_tko.mean():.3f} v {we[~ce].any_at_tko.mean():.3f} p={binom_p(we[ce].any_at_tko.sum(), ce.sum(), we[~ce].any_at_tko.mean()):.3g}; low_in_last_bar {we[ce].low_in_last_bar.mean():.3f} v {we[~ce].low_in_last_bar.mean():.3f}")
# is any_at_tko trending up over time regardless of kospi? by quarter
print("  any_at_tko by quarter (all):", x.groupby("quarter").any_at_tko.mean().round(2).to_dict())

# ---------------- F1 catalogue selection ----------------
print("\n" + "=" * 90 + "\nF1 catalogue selection rule")
fam = pd.read_csv(f"{LENS}/NQ_extremes_with_family.csv", index_col="date", parse_dates=True)
w = x[x.index >= "2025-11-01"].copy(); w["is_cat"] = (fam["family"].reindex(w.index).fillna("none") != "none").astype(int)
print("  |asia_ret| quantiles: cat", w[w.is_cat == 1].abs_asia_ret.quantile([0, .1, .25, .5]).round(0).to_dict(), " other", w[w.is_cat == 0].abs_asia_ret.quantile([.5, .75, .9, 1]).round(0).to_dict())
for thr in (40, 50, 60, 70):
    big = w.abs_asia_ret >= thr
    print(f"  |asia_ret|>={thr}: n={big.sum()} in catalogue {w[big].is_cat.mean():.2f}; |asia_ret|<{thr}: n={(~big).sum()} in catalogue {w[~big].is_cat.mean():.2f}")
# the F1 contrast among nights MATCHED on |asia_ret| (>=50bp): catalogue vs non-catalogue
for thr in (40, 60):
    big = w.abs_asia_ret >= thr
    a = w[big & (w.is_cat == 1)]; b = w[big & (w.is_cat == 0)]
    print(f"  |ret|>={thr}: cat n={len(a)} any_first_bar={a.any_first_bar.mean():.2f} any_at_tko={a.any_at_tko.mean():.2f} trend={a.trend_close.mean():.2f} | non-cat n={len(b)} any_first_bar={b.any_first_bar.mean():.2f} any_at_tko={b.any_at_tko.mean():.2f} trend={b.trend_close.mean():.2f}")
# full table: any_first_bar / any_at_tko by |asia_ret| band (the mechanical link)
x["ret_band"] = pd.cut(x.abs_asia_ret, [0, 20, 40, 60, 90, 1e9], right=False)
print("  full table by |asia_ret| band:")
print(x.groupby("ret_band", observed=True)[["any_first_bar", "any_at_tko", "trend_close", "any_last_bar"]].agg(["mean", "size"]).round(2).to_string())

# ---------------- F8 6-bar sessions ----------------
print("\n" + "=" * 90 + "\nF8 which hours exist in the 6-bar holiday sessions")
h1 = pd.read_csv(f"{ROOT}/data/NQ_1h.csv")
tcol = [c for c in h1.columns if "ate" in c or "time" in c.lower()][0]
h1[tcol] = pd.to_datetime(h1[tcol], utc=True).dt.tz_convert("America/New_York"); h1 = h1.set_index(tcol).sort_index()
hol = x[((x.holiday_tomorrow == 1) | (x.pre_holiday == 1))]
for d, r in hol.iterrows():
    gd = pd.Timestamp(r.asia_gdate)
    seg = h1[(h1.index >= (gd - pd.Timedelta(days=1)).replace(hour=18)) & (h1.index <= gd.replace(hour=3))]
    print(f"  {d.date()} n_bars={r.n_bars} hours present: {sorted(set(seg.index.hour))} rng={r.rng_bp:.0f}")
# all 6-bar sessions in the table: are they all holiday-related?
six = x[x.n_bars < 9]
print("  all <9-bar sessions:", [(str(d.date()), int(r.n_bars), int((r.holiday_tomorrow == 1) | (r.pre_holiday == 1))) for d, r in six.iterrows()])
print("  median rng of ALL 6-bar sessions:", six.rng_bp.median().round(0), " of 9-bar:", x[x.n_bars == 9].rng_bp.median().round(0))
# partial-session comparison: range over the first 6 bars of ordinary 9-bar sessions (from the panel run_rng_bp at k=5)
p = load_panel("NQ"); p9 = p[(p.n_bars == 9) & (p.k == 5)]
print(f"  ordinary 9-bar sessions: running range at the close of bar 5 (6 bars): median {p9.run_rng_bp.median():.0f} bp (n={len(p9)}) vs 6-bar holiday sessions median {hol[hol.n_bars==6].rng_bp.median():.0f} (n={(hol.n_bars==6).sum()}) p_MW={stats.mannwhitneyu(hol[hol.n_bars==6].rng_bp, p9.run_rng_bp).pvalue:.3g}")

# ---------------- F12 15m open semantics ----------------
print("\n" + "=" * 90 + "\nF12 15m 18:00 bar: Open vs 17:00 close vs hourly open")
m15 = pd.read_csv(f"{ROOT}/data/NQ_15m.csv"); m15["Datetime"] = pd.to_datetime(m15["Datetime"], utc=True).dt.tz_convert("America/New_York"); m15 = m15.set_index("Datetime").sort_index()
fb = m15[(m15.index.hour == 18) & (m15.index.minute == 0)]
rows = []
for ts, r in fb.iterrows():
    gd = (ts + pd.Timedelta(days=1)).date()
    d = x.index[x["asia_gdate"] == str(gd)]
    if len(d) == 0: continue
    xr = x.loc[d[0]]
    rows.append(dict(date=d[0].date(), open15=r.Open, ref_close=xr.ref_close, asia_open_1h=xr.asia_open, hi15=r.High, lo15=r.Low, open_eq_ref=abs(r.Open - xr.ref_close) < 0.3, open_eq_1h=abs(r.Open - xr.asia_open) < 0.3,
                     open_is_hi=abs(r.Open - r.High) < 0.3, open_is_lo=abs(r.Open - r.Low) < 0.3, gap_bp=(r.Open / xr.ref_close - 1) * 1e4, rng15_bp=(r.High - r.Low) / xr.ref_close * 1e4))
t = pd.DataFrame(rows)
print(f"  n={len(t)}: 15m Open == 17:00 close: {t.open_eq_ref.sum()}; 15m Open == hourly asia_open: {t.open_eq_1h.sum()}; Open is the 15m high: {t.open_is_hi.sum()}, is the 15m low: {t.open_is_lo.sum()}")
print("  median |gap| at 18:00 (bp):", t.gap_bp.abs().median().round(1), " median 18:00-18:15 range (bp):", t.rng15_bp.median().round(1))
print(t.head(6).round(2).to_string())
