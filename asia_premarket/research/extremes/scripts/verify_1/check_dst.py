"""DST check on the raw hourly bars: how many Asia bars exist on the spring-forward and fall-back nights,
and what the extremes table says for those sessions (tokyo_open_k, is_dst, n_bars)."""
import os, sys
sys.path.insert(0, ".")
import pandas as pd, numpy as np
from sessions import load_hourly

ROOT = "."
for sym in ["NQ"]:
    h = load_hourly(os.path.join(ROOT, "data", f"{sym}_1h.csv"))
    x = pd.read_csv(os.path.join(ROOT, "research", "extremes", f"{sym}_extremes.csv"), index_col="date", parse_dates=True)
    for night, rth_date in [("2025-03-09", "2025-03-07"), ("2025-11-02", "2025-10-31"), ("2026-03-08", "2026-03-06"), ("2026-11-01", "2026-10-30"), ("2024-11-03", "2024-11-01")]:
        t0 = pd.Timestamp(night + " 17:00", tz="America/New_York"); t1 = t0 + pd.Timedelta(hours=11)
        bars = h[(h.index >= t0) & (h.index <= t1)]
        print(f"\n{sym} night of {night}: bars from 17:00 (ET label, UTC):")
        print("  " + " | ".join(f"{ts.strftime('%H:%M%Z')}/{ts.tz_convert('UTC').strftime('%H:%MZ')}" for ts in bars.index))
        if pd.Timestamp(rth_date) in x.index:
            r = x.loc[pd.Timestamp(rth_date)]
            print(f"  extremes row {rth_date}: n_bars={r.n_bars} is_dst={r.is_dst} tokyo_open_k={r.tokyo_open_k} hi_k={r.hi_k} hi_hour_et={r.hi_hour_et} lo_k={r.lo_k} lo_hour_et={r.lo_hour_et}")
    # generic: distribution of (is_dst, tokyo_open_k) and of first-bar hour
    print("\n(is_dst, tokyo_open_k) counts:", x.groupby(["is_dst", "tokyo_open_k"]).size().to_dict())
    # sessions keyed to a Friday RTH date in the week of a DST change: is_dst must be that of the SUNDAY session
    for d in ["2025-03-07", "2025-10-31", "2026-03-06", "2026-10-30", "2024-11-01"]:
        if pd.Timestamp(d) in x.index:
            print(f"  {d} (Fri): is_dst={x.loc[d, 'is_dst']} asia_gdate={x.loc[d, 'asia_gdate']}")
