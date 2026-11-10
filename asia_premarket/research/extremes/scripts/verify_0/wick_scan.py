"""Scan every Asia-session hourly bar (18:00..02:00 ET) for splice-like wicks: a High or Low that sits > 40 bp
beyond both the bar's open/close AND beyond the neighbouring bars' closes, i.e. a print that no close confirms."""
import pandas as pd, numpy as np
D = "./data"
R = "./research/extremes"
for sym in ["NQ", "ES"]:
    h = pd.read_csv(f"{D}/{sym}_1h.csv"); t = h.columns[0]
    h[t] = pd.to_datetime(h[t], utc=True).dt.tz_convert("America/New_York"); h = h.set_index(t).sort_index()
    c = h["Close"]; prev_c = c.shift(1); next_c = c.shift(-1)
    body_hi = np.maximum(h["Open"], h["Close"]); body_lo = np.minimum(h["Open"], h["Close"])
    ref_hi = np.maximum.reduce([body_hi.values, prev_c.fillna(body_hi).values, next_c.fillna(body_hi).values])
    ref_lo = np.minimum.reduce([body_lo.values, prev_c.fillna(body_lo).values, next_c.fillna(body_lo).values])
    up_wick = (h["High"].values / ref_hi - 1) * 1e4; dn_wick = (1 - h["Low"].values / ref_lo) * 1e4
    h["up_wick_bp"] = up_wick; h["dn_wick_bp"] = dn_wick
    asia = h[h.index.hour.isin([18, 19, 20, 21, 22, 23, 0, 1, 2])]
    bad = asia[(asia["up_wick_bp"] > 40) | (asia["dn_wick_bp"] > 40)]
    # map to RTH date: bars >= 18:00 belong to that date; bars < 03:00 to the previous trading date
    x = pd.read_csv(f"{R}/{sym}_extremes.csv", parse_dates=["date", "asia_gdate"])
    gmap = dict(zip(x["asia_gdate"].dt.date, x["date"].dt.date))
    rows = []
    for ts, r in bad.iterrows():
        gd = (ts + pd.Timedelta(days=1)).date() if ts.hour >= 18 else ts.date()
        rows.append((str(ts), gmap.get(gd, "n/a"), round(r["up_wick_bp"]), round(r["dn_wick_bp"]), int(r["Volume"])))
    print(f"\n{sym}: {len(bad)} suspicious Asia bars (unconfirmed wick > 40 bp); (bar, RTH date, up_wick, dn_wick, volume)")
    for r in rows: print("  ", r)
