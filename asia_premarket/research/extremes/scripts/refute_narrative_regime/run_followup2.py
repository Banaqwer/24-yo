"""Follow-ups: F4 2026-only base; F1 catalogue selection rule; F8 6-bar sessions; F12 15m open semantics."""
import sys
sys.path.insert(0, "research/extremes/scripts/refute_narrative_regime")
import numpy as np, pandas as pd
from scipy import stats
from robust import *
LENS = "research/extremes/scripts/lens_narrative"
pd.set_option("display.width", 300, "display.max_columns", 50, "display.max_rows", 500)
x = load_extremes("NQ"); xe = load_extremes("ES")

# ---------------- F8 6-bar sessions ----------------
print("\n" + "=" * 90 + "\nF8 which hours exist in the 6-bar holiday sessions")
h1 = pd.read_csv(f"{ROOT}/data/NQ_1h.csv")
tcol = [c for c in h1.columns if "ate" in c or "time" in c.lower()][0]
h1[tcol] = pd.to_datetime(h1[tcol], utc=True).dt.tz_convert("America/New_York"); h1 = h1.set_index(tcol).sort_index()
hol = x[((x.holiday_tomorrow == 1) | (x.pre_holiday == 1))]
for d, r in hol.iterrows():
    gd = pd.Timestamp(r.asia_gdate).tz_localize("America/New_York")
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
