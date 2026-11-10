"""What breaks when the detectors are run live at 17:20 ET or at the close of bar k."""
import sys, os, traceback
sys.path.insert(0, ".")
sys.path.insert(0, "./research/extremes")
os.chdir(".")
import numpy as np, pandas as pd
from sessions import load_hourly, build_sessions
import asia_extremes as ax

h = load_hourly("data/NQ_1h.csv")
print("last NQ bar:", h.index[-1])
# 1. tonight's (2026-11-09) session has 2 bars in the file: is it in the tables?
x = pd.read_csv("research/extremes/NQ_extremes.csv", index_col="date", parse_dates=True)
p = pd.read_csv("research/extremes/NQ_hourly_panel.csv", parse_dates=["date"])
print("2026-11-09 in extremes:", pd.Timestamp("2026-11-09") in x.index, "| in panel:", (p.date == "2026-11-09").any())
groups = ax._asia_groups(h)
print("tonight's group present in _asia_groups (needs >= 6 bars):", pd.Timestamp("2026-11-10") in groups)
s = build_sessions(h)
print("build_sessions row for 2026-11-09 asia_gdate:", s.loc["2026-11-09", "asia_gdate"] if "2026-11-09" in s.index.strftime("%Y-%m-%d") else "row missing")

# 2. simulate the close of bar k for a past night by truncating the hourly file
def truncated(h, cutoff):
    return h[h.index <= pd.Timestamp(cutoff, tz="America/New_York")]

for cutoff, k in [("2026-11-05 18:00", 0), ("2026-11-05 20:00", 2), ("2026-11-05 22:00", 4), ("2026-11-05 23:00", 5)]:
    ht = truncated(h, cutoff)
    g = ax._asia_groups(ht)
    st = build_sessions(ht)
    has_group = pd.Timestamp("2026-11-06") in g
    ag = st.loc["2026-11-05", "asia_gdate"] if pd.Timestamp("2026-11-05") in st.index else None
    print(f"  cutoff {cutoff} (close of bar k={k}): asia group present={has_group}; build_sessions asia_gdate for 2026-11-05={ag}")

# 3. the 17:20 ET case: no 18:00 bar yet -> is RTH date D in the extremes table at all?
ht = truncated(h, "2026-11-05 17:00")
st = build_sessions(ht)
print("17:20 ET case: 2026-11-05 in build_sessions:", pd.Timestamp("2026-11-05") in st.index, "; asia_gdate:", st.loc["2026-11-05", "asia_gdate"] if pd.Timestamp("2026-11-05") in st.index else None)
# what build_extremes does with it
try:
    xe = ax.build_extremes("NQ", s=None) if False else None
except Exception as e:
    print("build_extremes error:", e)

# 4. call the detectors for tonight
import detector_intrasession as di, detector_preasia as dp
for k in [0, 1]:
    try:
        r = di.predict_now("NQ", "2026-11-09", k)
        print("predict_now 2026-11-09 k", k, "->", r["p_high_done"])
    except Exception as e:
        print(f"predict_now('NQ','2026-11-09',{k}) raised: {type(e).__name__}: {e}")
try:
    r = dp.predict_tonight("NQ", "2026-11-09")
    print("predict_tonight 2026-11-09 ok")
except Exception as e:
    print(f"predict_tonight('NQ','2026-11-09') raised: {type(e).__name__}: {e}")

# 5. the partial-bar case: hourly panel labels for a session with < 9 bars are computed from the partial session
# (high_done = running high == partial-session high -> always 1 at the last available bar)
pp = p[p.n_bars < 9]
print("truncated-session panel rows: last-bar high_done rate", pp[pp.k == pp.n_bars - 1].high_done.mean(), "(labels are relative to the bars present)")

# 6. splice list mismatch between modules
print("preasia NQ splice list:", dp.SPLICE_SESSIONS["NQ"]); print("intrasession NQ splice list:", di.SPLICE_DATES["NQ"])
xx = pd.read_csv("research/extremes/NQ_extremes.csv", index_col="date", parse_dates=True)
for d in ["2025-12-15", "2025-12-16", "2025-12-17"]:
    if pd.Timestamp(d) in xx.index:
        r = xx.loc[d]
        print(f"  NQ {d}: n_bars {r.n_bars} rng_bp {r.rng_bp:.0f} hi_bp {r.hi_bp:.0f} lo_bp {r.lo_bp:.0f} rth_range_bp {r.rth_range_bp:.0f} hi_k {r.hi_k} lo_k {r.lo_k}")
hh = h.loc["2025-12-16 18:00":"2025-12-17 03:00"]
print(hh[["Open", "High", "Low", "Close", "Volume"]].to_string())

# 7. hourly bar timestamps: does yfinance deliver a 17:00 bar (settlement print) and does any code use hour 17?
print("bars at hour 17 in NQ_1h:", (h.index.hour == 17).sum(), "of", len(h), "; last few:", h[h.index.hour == 17].index[-3:].tolist())
# 8. kospi / cross-asset staleness: fraction of RTH dates whose kospi_ret equals the previous row's (ffill artefact)
f = xx[["kospi_ret", "n225_ret", "usdjpy_chg", "vix"]]
print("kospi_ret identical to previous row:", (f.kospi_ret == f.kospi_ret.shift(1)).mean().round(3), "; n225:", (f.n225_ret == f.n225_ret.shift(1)).mean().round(3), "; vix NaN:", f.vix.isna().sum())
