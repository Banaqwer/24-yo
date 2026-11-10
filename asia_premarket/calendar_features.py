"""
Calendar / scheduled-event features known at 18:00 ET on RTH date D.

Two sources:
  1. research/event_calendar.csv (built by the research agent, verified from
     official sources).  Columns: date,event,category,time_et,notes
  2. A hard-coded fallback for the structurally known dates (FOMC statement
     days 2024-2026, 3rd-Friday opex, quarterly roll Thursdays, US holidays),
     so the engine runs even if the research file is missing.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

FOMC_DECISION_DAYS = [
    # 2024
    "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
    "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29",
    "2026-09-16", "2026-10-28", "2026-12-09",
]

US_HOLIDAYS = [
    "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
    "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01",
]


def third_friday(year: int, month: int) -> pd.Timestamp:
    d = pd.Timestamp(year=year, month=month, day=1)
    # weekday(): Monday=0 ... Friday=4
    off = (4 - d.weekday()) % 7
    return d + pd.Timedelta(days=off + 14)


def structural_calendar(start="2024-01-01", end="2027-12-31") -> pd.DataFrame:
    rows = []
    for d in FOMC_DECISION_DAYS:
        rows.append((pd.Timestamp(d), "FOMC", "fed"))
    for d in US_HOLIDAYS:
        rows.append((pd.Timestamp(d), "US_HOLIDAY", "holiday"))
    for y in range(2024, 2028):
        for m in range(1, 13):
            tf = third_friday(y, m)
            rows.append((tf, "OPEX", "opex"))
            if m in (3, 6, 9, 12):
                rows.append((tf, "WITCHING", "witching"))
                rows.append((tf - pd.Timedelta(days=8), "ROLL", "roll"))  # roll Thursday, week before
    cal = pd.DataFrame(rows, columns=["date", "event", "category"])
    cal["time_et"] = ""
    cal["notes"] = "structural"
    return cal[(cal.date >= start) & (cal.date <= end)]


def load_calendar() -> pd.DataFrame:
    cal = structural_calendar()
    p = os.path.join(HERE, "research", "event_calendar.csv")
    if os.path.exists(p):
        try:
            r = pd.read_csv(p)
            r["date"] = pd.to_datetime(r["date"], errors="coerce")
            r = r.dropna(subset=["date"])
            r["event"] = r["event"].astype(str).str.upper().str.strip()
            r["category"] = r["category"].astype(str).str.lower().str.strip()
            for c in ("time_et", "notes"):
                if c not in r:
                    r[c] = ""
            cal = pd.concat([cal, r[["date", "event", "category", "time_et", "notes"]]], ignore_index=True)
        except Exception as e:  # keep running on a malformed research file
            print("calendar: could not read research/event_calendar.csv:", e)
    cal = cal.drop_duplicates(subset=["date", "event"]).sort_values("date").reset_index(drop=True)
    return cal


# category -> feature name (event ON date D, i.e. already happened by 18:00 unless it is an
# Asia-hours event, which we treat as "tonight")
TODAY_FLAGS = {
    "fed": "fomc_today",
    "fed_minutes": "fed_minutes_today",
    "us_data_tier1": "tier1_data_today",
    "us_data_tier2": "tier2_data_today",
    "opex": "opex_today",
    "witching": "witching_today",
    "roll": "roll_today",
    "earnings": "megacap_earnings_tonight",   # released ~16:05 ET, trades in Asia
    "election": "election_today",
    "politics": "politics_today",
}
TONIGHT_FLAGS = {            # happen inside the Asia session that follows D
    "boj": "boj_tonight",
    "jp_data": "jp_data_tonight",
    "cn_data": "cn_data_tonight",
    "cn_policy": "cn_policy_tonight",
    "rba": "rba_tonight",
}
TOMORROW_FLAGS = {           # scheduled for D+1 (US morning) -> Asia session is "pre-event"
    "fed": "fomc_tomorrow",
    "us_data_tier1": "tier1_data_tomorrow",
    "us_data_tier2": "tier2_data_tomorrow",
    "ecb": "ecb_tomorrow",
    "boe": "boe_tomorrow",
    "opex": "opex_tomorrow",
    "holiday": "holiday_tomorrow",
}


def _next_trading_day(d: pd.Timestamp, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None:
    pos = trading_days.searchsorted(d, side="right")
    return trading_days[pos] if pos < len(trading_days) else None


def calendar_features(dates: pd.DatetimeIndex, cal: pd.DataFrame | None = None) -> pd.DataFrame:
    """Binary/scalar event features for each RTH date in `dates`."""
    cal = load_calendar() if cal is None else cal
    dates = pd.DatetimeIndex(dates).normalize()
    by_date = cal.groupby(cal["date"].dt.normalize())["category"].agg(lambda s: set(s))
    ev_by_date = cal.groupby(cal["date"].dt.normalize())["event"].agg(lambda s: set(s))

    # "tonight" events live on the *Japan/China* calendar date, which is D+1 in ET terms
    # (e.g. BoJ decides Friday Tokyo time -> Thursday night ET).  Research CSV uses the
    # local release date, so BoJ dated D+1 => tonight relative to RTH date D.
    out = pd.DataFrame(index=dates)
    all_cal_days = pd.DatetimeIndex(sorted(by_date.index))
    holidays = {pd.Timestamp(h) for h in US_HOLIDAYS}

    cols = list(TODAY_FLAGS.values()) + list(TONIGHT_FLAGS.values()) + list(TOMORROW_FLAGS.values())
    for c in cols:
        out[c] = 0
    out["days_to_fomc"] = np.nan
    out["days_since_fomc"] = np.nan
    out["sunday_open"] = 0          # D is Friday -> the following Asia session is Sunday 18:00
    out["month_end"] = 0
    out["quarter_end"] = 0
    out["dow"] = dates.dayofweek
    out["pre_holiday"] = 0

    fomc_days = pd.DatetimeIndex(sorted({pd.Timestamp(x) for x in FOMC_DECISION_DAYS}))
    for d in dates:
        cats_today = by_date.get(d, set())
        for cat, col in TODAY_FLAGS.items():
            if cat in cats_today:
                out.at[d, col] = 1
        d1 = d + pd.Timedelta(days=1)
        # next calendar day(s) up to the next trading day count as "tonight/tomorrow"
        nxt = d1
        while nxt.dayofweek >= 5 or nxt in holidays:
            nxt = nxt + pd.Timedelta(days=1)
        cats_tonight = by_date.get(d1, set()) | (by_date.get(nxt, set()) if nxt != d1 else set())
        for cat, col in TONIGHT_FLAGS.items():
            if cat in cats_tonight:
                out.at[d, col] = 1
        cats_tmrw = by_date.get(nxt, set())
        for cat, col in TOMORROW_FLAGS.items():
            if cat in cats_tmrw:
                out.at[d, col] = 1
        if d.dayofweek == 4:
            out.at[d, "sunday_open"] = 1
        if (d + pd.Timedelta(days=1)).month != d.month or (nxt.month != d.month):
            out.at[d, "month_end"] = 1
            if d.month in (3, 6, 9, 12):
                out.at[d, "quarter_end"] = 1
        if nxt in holidays or (d1 in holidays):
            out.at[d, "pre_holiday"] = 1
        pos = fomc_days.searchsorted(d, side="left")
        if pos < len(fomc_days):
            out.at[d, "days_to_fomc"] = (fomc_days[pos] - d).days
        if pos > 0:
            out.at[d, "days_since_fomc"] = (d - fomc_days[pos - 1]).days
    out["events_today"] = [";".join(sorted(ev_by_date.get(d, set()))) for d in dates]
    out["events_tonight_tomorrow"] = [
        ";".join(sorted(ev_by_date.get(d + pd.Timedelta(days=1), set()) | ev_by_date.get(d + pd.Timedelta(days=2), set()) if d.dayofweek == 4 else ev_by_date.get(d + pd.Timedelta(days=1), set())))
        for d in dates
    ]
    return out


if __name__ == "__main__":
    cal = load_calendar()
    print(cal.tail(20))
    f = calendar_features(pd.date_range("2026-10-20", "2026-11-10", freq="B"), cal)
    print(f.T)
