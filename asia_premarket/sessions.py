"""
Session engine: slices CME Globex hourly bars (US/Eastern) into the sessions
that matter for a pre-Asia-open decision.

All times are US/Eastern. The hourly bar labelled HH:00 covers HH:00-HH:59.

Globex trade date D (for an index future):
    Asia    : 18:00 (D-1 calendar day) .. 02:59  -> bars 18..23 of D-1 and 0..2 of D
    Europe  : 03:00 .. 08:59                      -> bars 3..8 of D
    RTH     : 09:00 .. 15:59 (cash 09:30-16:00)   -> bars 9..15 of D
    PostRTH : 16:00 .. 16:59 (16:15 settle, 17:00 halt) -> bar 16 of D

The decision point is 18:00 ET of calendar day D ("pre-Asia"). The target is
what happens between 18:00 D and 03:00 D+1 ("the Asia session that follows
RTH day D").  We key everything on the RTH date D.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ET = "America/New_York"

ASIA_HOURS = list(range(18, 24)) + [0, 1, 2]
TOKYO_HOURS = list(range(20, 24)) + [0, 1, 2]   # Tokyo cash open ~ 19:00/20:00 ET
EUROPE_HOURS = list(range(3, 9))
RTH_HOURS = list(range(9, 16))
POST_HOURS = [16]


def load_hourly(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, index_col=0)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(ET)
    d = d[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    # drop the stray :30 bars yfinance occasionally emits
    d = d[d.index.minute == 0]
    return d


def _agg(bars: pd.DataFrame) -> dict:
    if bars.empty:
        return {}
    vol = bars["Volume"].values
    tp = (bars["High"] + bars["Low"] + bars["Close"]).values / 3.0
    vwap = float((tp * vol).sum() / vol.sum()) if vol.sum() > 0 else float(np.mean(tp))
    hi_idx = bars["High"].idxmax()
    lo_idx = bars["Low"].idxmin()
    return {
        "open": float(bars["Open"].iloc[0]),
        "high": float(bars["High"].max()),
        "low": float(bars["Low"].min()),
        "close": float(bars["Close"].iloc[-1]),
        "vwap": vwap,
        "volume": float(vol.sum()),
        "n_bars": int(len(bars)),
        "hi_hour": int(hi_idx.hour),
        "lo_hour": int(lo_idx.hour),
    }


def build_sessions(h: pd.DataFrame) -> pd.DataFrame:
    """Return one row per RTH date D with RTH, post, following-Asia, following-Europe stats."""
    h = h.copy()
    h["date"] = h.index.date
    h["hour"] = h.index.hour
    # Globex trade date: bars at >=18:00 belong to the NEXT calendar day's trade date
    gdate = pd.Series(h.index.date, index=h.index)
    shift = h.index.hour >= 18
    gdate[shift] = (h.index[shift] + pd.Timedelta(days=1)).date
    h["gdate"] = gdate.values

    rows = []
    for d, g in h.groupby("date"):
        rth = g[g["hour"].isin(RTH_HOURS)]
        post = g[g["hour"].isin(POST_HOURS)]
        if len(rth) < 5:          # holiday / partial day
            continue
        r = {"date": pd.Timestamp(d)}
        a = _agg(rth)
        r.update({f"rth_{k}": v for k, v in a.items()})
        p = _agg(post)
        r.update({f"post_{k}": v for k, v in p.items()})
        rows.append(r)
    s = pd.DataFrame(rows).set_index("date").sort_index()

    # Following Asia session = Globex trade date D+1 (bars 18:00 D .. 02:59 D+1)
    nxt = {}
    for gd, g in h.groupby("gdate"):
        asia = g[g["hour"].isin(ASIA_HOURS)]
        tokyo = g[g["hour"].isin(TOKYO_HOURS)]
        eur = g[g["hour"].isin(EUROPE_HOURS)]
        if len(asia) < 6:
            continue
        rec = {}
        a = _agg(asia)
        rec.update({f"asia_{k}": v for k, v in a.items()})
        # first-hour of Asia (18:00 bar) for "reopen impulse"
        first = asia.iloc[0]
        rec["asia_first_close"] = float(first["Close"])
        t = _agg(tokyo)
        rec.update({f"tokyo_{k}": v for k, v in t.items()})
        e = _agg(eur)
        rec.update({f"eur_{k}": v for k, v in e.items()})
        # 18:00 calendar date of this Asia session = gd - 1 day; but we key on RTH date,
        # which is the most recent RTH date <= that calendar date.
        nxt[pd.Timestamp(gd)] = rec
    nxt = pd.DataFrame.from_dict(nxt, orient="index").sort_index()

    # map each RTH date D to the next Asia session whose Globex date > D
    gdates = nxt.index
    out = []
    for d in s.index:
        pos = gdates.searchsorted(d, side="right")
        if pos >= len(gdates):
            out.append(pd.Series(dtype=float, name=d))
            continue
        gd = gdates[pos]
        # the Asia session must begin on calendar day D (weekday) or on the Sunday after a Friday
        gap_days = (gd - d).days
        if gap_days > 3:
            out.append(pd.Series(dtype=float, name=d))
            continue
        rec = nxt.loc[gd].copy()
        rec["asia_gdate"] = gd
        rec["asia_gap_days"] = gap_days
        rec.name = d
        out.append(rec)
    nxt_aligned = pd.DataFrame(out)
    s = s.join(nxt_aligned)
    return s


def with_prior_context(s: pd.DataFrame) -> pd.DataFrame:
    """Add prior-session references (settle, previous Asia/Europe moves)."""
    s = s.copy()
    s["prev_settle"] = s["post_close"].shift(1)
    s["prev_rth_close"] = s["rth_close"].shift(1)
    s["prev_rth_high"] = s["rth_high"].shift(1)
    s["prev_rth_low"] = s["rth_low"].shift(1)
    s["prev_rth_vwap"] = s["rth_vwap"].shift(1)
    # the Asia/Europe sessions that preceded today's RTH (i.e. the ones keyed on D-1)
    for k in ["asia_open", "asia_close", "asia_high", "asia_low", "eur_open", "eur_close", "eur_high", "eur_low"]:
        s[f"prior_{k}"] = s[k].shift(1)
    return s


def path_outcomes(h: pd.DataFrame, s: pd.DataFrame,
                  retrace_targets=(0.382, 0.5), stop_mult: float = 1.0,
                  stop_dist: pd.Series | None = None, suffix: str = "") -> pd.DataFrame:
    """
    Walk the Asia bars (18:00 D .. 02:59 D+1) hour by hour and record, for a
    *reversion* trade entered at the 18:00 open against the RTH move:
      - hit_vwap_first      : touched RTH VWAP before the stop
      - hit_r38_first/r50   : retraced 38.2% / 50% of the RTH move before the stop
      - stopped             : stop hit before any target
      - stop (default)      : RTH extreme in the direction of the move + 10% of RTH range
        (for a short after an up day: above RTH high).
      - stop (stop_dist)    : a fixed distance from the 17:00 close in the direction of the
        move (e.g. 0.6 x the recent median Asia range) -> the "wide / range-based" stop.
    If a bar touches both target and stop we count it as stopped (conservative).
    Column names get `suffix` appended (e.g. "_w" for the wide-stop variant).
    """
    h = h.copy()
    h["gdate"] = h.index.date
    shift = h.index.hour >= 18
    g = pd.Series(h.index.date, index=h.index)
    g[shift] = (h.index[shift] + pd.Timedelta(days=1)).date
    h["gdate"] = g.values
    h["hour"] = h.index.hour
    asia_bars = h[h["hour"].isin(ASIA_HOURS)].groupby("gdate")

    rows = {}
    for d, r in s.iterrows():
        if pd.isna(r.get("asia_gdate")) or pd.isna(r.get("rth_vwap")):
            continue
        gd = pd.Timestamp(r["asia_gdate"]).date()
        if gd not in asia_bars.groups:
            continue
        bars = asia_bars.get_group(gd)
        move = r["rth_close"] - r["rth_open"]
        if move == 0:
            continue
        up = move > 0
        rng = r["rth_high"] - r["rth_low"]
        if stop_dist is not None:
            sd = stop_dist.get(d, np.nan)
            if pd.isna(sd):
                continue
            ref = r["post_close"] if not pd.isna(r.get("post_close")) else r["rth_close"]
            stop = ref + sd if up else ref - sd
        else:
            stop = r["rth_high"] + 0.10 * rng * stop_mult if up else r["rth_low"] - 0.10 * rng * stop_mult
        targets = {"vwap": r["rth_vwap"]}
        for rt in retrace_targets:
            targets[f"r{int(rt*1000):03d}"[:4]] = r["rth_close"] - rt * move
        rec = {f"hit_{k}_first": 0 for k in targets}
        rec["stopped"] = 0
        rec["stop_lvl"] = stop
        rec.update({f"tgt_{k}": v for k, v in targets.items()})
        done = set()
        for ts, b in bars.iterrows():
            stop_hit = (b["High"] >= stop) if up else (b["Low"] <= stop)
            if stop_hit:
                rec["stopped"] = 1
                rec["stop_hour"] = ts.hour
                break
            for k, lvl in targets.items():
                if k in done:
                    continue
                hit = (b["Low"] <= lvl) if up else (b["High"] >= lvl)
                if hit:
                    rec[f"hit_{k}_first"] = 1
                    rec[f"hour_{k}"] = ts.hour
                    done.add(k)
            if len(done) == len(targets):
                break
        rows[d] = rec
    out = pd.DataFrame.from_dict(rows, orient="index").reindex(s.index)
    if suffix:
        out.columns = [c + suffix for c in out.columns]
    return out


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "NQ"
    h = load_hourly(f"data/{sym}_1h.csv")
    s = with_prior_context(build_sessions(h))
    s.to_csv(f"data/{sym}_sessions.csv")
    print(s.tail(3).T)
    print(len(s), "RTH days")
