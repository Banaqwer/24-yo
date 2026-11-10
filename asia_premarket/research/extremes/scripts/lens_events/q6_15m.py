"""15-minute look (2026-08-31 .. 2026-11-09 only): inside the 18:00 hourly bar, where is the extreme made —
is it the 18:00-18:15 print?  For mega-cap earnings nights, Sunday reopens, and all sessions."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research/extremes/scripts/lens_events")
from common import *
pd.set_option("display.width", 250)

rows = []
for sym in ("NQ", "ES"):
    m = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv")
    m["ts"] = pd.to_datetime(m["Datetime"], utc=True).dt.tz_convert("America/New_York")
    m = m.set_index("ts").sort_index()
    x = load_extremes(sym)
    x = x[x.asia_gdate >= pd.Timestamp("2026-09-01")]
    for d, r in x.iterrows():
        gd = r.asia_gdate
        start = (gd - pd.Timedelta(days=1)).replace(hour=18, minute=0)
        start = pd.Timestamp(start).tz_localize("America/New_York")
        end = pd.Timestamp(gd.replace(hour=2, minute=59)).tz_localize("America/New_York")
        s = m[(m.index >= start) & (m.index <= end)]
        if len(s) < 20:
            continue
        hi_i = int(np.argmax(s.High.values)); lo_i = int(np.argmin(s.Low.values))
        rows.append(dict(sym=sym, date=d, gdate=gd, n15=len(s), hi_15=hi_i, lo_15=lo_i,
                         hi_min=(s.index[hi_i] - start).total_seconds() / 60, lo_min=(s.index[lo_i] - start).total_seconds() / 60,
                         hi_in_first15=int(hi_i == 0), lo_in_first15=int(lo_i == 0),
                         hi_in_first_hour=int(hi_i <= 3), lo_in_first_hour=int(lo_i <= 3),
                         hi_k=r.hi_k, lo_k=r.lo_k, megacap=r.megacap_earnings_tonight, sunday=r.sunday_open,
                         tier1_tmrw=r.tier1_data_tomorrow, cn=r.cn_data_tonight, fomc_tmrw=r.fomc_tomorrow, fomc=r.fomc_today,
                         is_dst=r.is_dst, rng_bp=r.rng_bp, asia_ret=r.asia_ret_bp))
t = pd.DataFrame(rows); t.to_csv(f"{OUT}/q6_15m_first_bar.csv", index=False)
for sym in ("NQ", "ES"):
    d = t[t.sym == sym]
    print(f"\n{sym}: n sessions with 15m = {len(d)}")
    print(f"  all: P(high in first 15m)={d.hi_in_first15.mean():.3f}  P(low in first 15m)={d.lo_in_first15.mean():.3f}  "
          f"P(high in first hour)={d.hi_in_first_hour.mean():.3f}  P(low in first hour)={d.lo_in_first_hour.mean():.3f}")
    fh = d[d.hi_k == 0]; fl = d[d.lo_k == 0]
    print(f"  given high in the 18:00 hourly bar (n={len(fh)}): P(it is the 18:00-18:15 print)={fh.hi_in_first15.mean():.3f}; 15m slot hist {fh.hi_15.value_counts().sort_index().to_dict()}")
    print(f"  given low  in the 18:00 hourly bar (n={len(fl)}): P(it is the 18:00-18:15 print)={fl.lo_in_first15.mean():.3f}; 15m slot hist {fl.lo_15.value_counts().sort_index().to_dict()}")
    for f in ("megacap", "sunday", "fomc_tmrw", "fomc"):
        e = d[d[f] == 1]
        if len(e) == 0:
            continue
        print(f"  {f} (n={len(e)}): P(high first15)={e.hi_in_first15.mean():.2f} P(low first15)={e.lo_in_first15.mean():.2f} "
              f"P(high first hour)={e.hi_in_first_hour.mean():.2f} P(low first hour)={e.lo_in_first_hour.mean():.2f}; "
              f"hi_min med {e.hi_min.median():.0f} lo_min med {e.lo_min.median():.0f}")
        print(e[["date", "hi_min", "lo_min", "hi_k", "lo_k", "rng_bp", "asia_ret"]].round(1).to_string(index=False))
    # minute-of-session histogram of extremes (30-min buckets) for all sessions
    b = (d.hi_min // 60).value_counts(normalize=True).sort_index().round(3).to_dict()
    print("  high by hour-from-18:00:", b)
    b = (d.lo_min // 60).value_counts(normalize=True).sort_index().round(3).to_dict()
    print("  low  by hour-from-18:00:", b)
    # China data at 21:30 EDT = minute 210; JP CPI at 19:30 EDT = minute 90 : 15m-slot hist within those hours
    for lab, lo_m, hi_m in (("21:00-22:00 (China 09:30/09:45 CST, EDT)", 180, 240), ("19:00-20:00 (JP 08:30 JST, EDT)", 60, 120)):
        e = d[(d.is_dst == 1)]
        hh = e[(e.hi_min >= lo_m) & (e.hi_min < hi_m)].hi_min.value_counts().sort_index().to_dict()
        ll = e[(e.lo_min >= lo_m) & (e.lo_min < hi_m)].lo_min.value_counts().sort_index().to_dict()
        print(f"  {lab}: high minute slots {hh} | low minute slots {ll}")
