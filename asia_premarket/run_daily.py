"""
Daily entry point.  Run after the 17:00 ET futures close and before the 18:00 ET reopen:

    python run_daily.py --refresh            # pull latest data, build NQ and ES reports
    python run_daily.py --sym NQ --date 2026-11-05   # replay a past night

Outputs:
    reports/<RTH date>_<SYM>_preasia.md     the pre-Asia report
    reports/latest_<SYM>.md                 copy of the most recent report
    reports/<RTH date>_<SYM>_agent_brief.md brief for the daily narrative agent
"""
from __future__ import annotations

import argparse
import os
import shutil
import warnings

import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
REPORTS = os.path.join(HERE, "reports")


def refresh_data():
    import yfinance as yf
    os.makedirs(DATA, exist_ok=True)
    for t in ["NQ=F", "ES=F"]:
        d = yf.download(t, period="730d", interval="1h", progress=False, auto_adjust=False)
        d.columns = [c[0] for c in d.columns]
        d.index = d.index.tz_convert("America/New_York")
        d.to_csv(os.path.join(DATA, f"{t.replace('=F','')}_1h.csv"))
        print("refreshed", t, len(d), "bars to", d.index.max())
    b = yf.download("BTC-USD", period="730d", interval="1h", progress=False, auto_adjust=False)
    b.columns = [c[0] for c in b.columns]
    b.index = b.index.tz_convert("America/New_York")
    b.to_csv(os.path.join(DATA, "BTC_1h.csv"))
    daily = {"NQ=F": "NQ", "ES=F": "ES", "^VIX": "VIX", "DX-Y.NYB": "DXY", "^TNX": "US10Y", "^IRX": "US3M", "^N225": "N225",
             "^HSI": "HSI", "JPY=X": "USDJPY", "GC=F": "GOLD", "CL=F": "CRUDE", "BTC-USD": "BTC", "^VVIX": "VVIX",
             "^SOX": "SOX", "^RUT": "RUT", "^STOXX50E": "SX5E", "000001.SS": "SSE", "^KS11": "KOSPI", "^TYX": "US30Y",
             "^FVX": "US5Y", "HG=F": "COPPER"}
    d = yf.download(list(daily.keys()), period="3y", interval="1d", progress=False, auto_adjust=False)
    d["Close"].rename(columns=daily).to_csv(os.path.join(DATA, "daily_close.csv"))
    for fld in ["Open", "High", "Low"]:
        d[fld].rename(columns=daily).to_csv(os.path.join(DATA, f"daily_{fld.lower()}.csv"))
    print("refreshed daily cross-asset closes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sym", default="both", choices=["NQ", "ES", "both"])
    ap.add_argument("--date", default=None, help="RTH date to report on (default: latest in data)")
    ap.add_argument("--refresh", action="store_true", help="download fresh data first")
    args = ap.parse_args()
    if args.refresh:
        refresh_data()
    from model import Engine
    from report import build_report, agent_brief
    os.makedirs(REPORTS, exist_ok=True)
    syms = ["NQ", "ES"] if args.sym == "both" else [args.sym]
    for sym in syms:
        eng = Engine(sym).train()
        asof = pd.Timestamp(args.date) if args.date else eng.f.index[-1]
        if asof not in eng.f.index:
            raise SystemExit(f"{asof:%Y-%m-%d} is not an RTH date in the data")
        rep = build_report(eng, asof)
        p = os.path.join(REPORTS, f"{asof:%Y-%m-%d}_{sym}_preasia.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(rep)
        if not args.date:   # a replayed past night must not overwrite the live "latest" report
            shutil.copy(p, os.path.join(REPORTS, f"latest_{sym}.md"))
        with open(os.path.join(REPORTS, f"{asof:%Y-%m-%d}_{sym}_agent_brief.md"), "w", encoding="utf-8") as fh:
            fh.write(agent_brief(eng, asof))
        print("wrote", p)


if __name__ == "__main__":
    main()
