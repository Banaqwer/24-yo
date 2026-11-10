"""
Asia-session HIGH / LOW characterisation and detector dataset.

Two tables per symbol:

  build_extremes(sym)  -> one row per RTH date D describing the following Asia session
                          (18:00 D .. 02:59 D+1 ET): when the high and the low were made (ET bar
                          index, ET hour, Tokyo-clock hour), where they sit relative to the 17:00
                          close, the RTH range, the prior Asia range, and how the session resolved
                          after each extreme.  Joined with the 18:00-knowable features and the
                          calendar flags.  Also carries the OVERNIGHT extremes (18:00 D .. 08:59 of
                          the following morning = Asia + Europe bars of the same Globex date):
                          ovn_high_bp / ovn_low_bp vs the 17:00 close and the 0/1 flags
                          europe_above_asia_high / europe_below_asia_low (NaN when the six Europe
                          bars 03:00-08:59 of that night are not all in the file).

  hourly_panel(sym)    -> one row per (RTH date D, Asia bar k) with everything known at the CLOSE
                          of bar k (running high/low, bars since each, position in range, bar
                          return/range/volume relative to history) and the labels
                          high_done / low_done (the session extreme is already in), the remaining
                          upside / downside in bp, and overnight_high_done / overnight_low_done
                          (the running extreme at the close of bar k is also the extreme of the
                          whole 18:00-08:59 window; NaN when that night's Europe bars are missing).
                          This is the training table for the "is the Asia high / low in yet?"
                          detector.

Live rows (the night has started, fewer than 6 bars exist, so the tables above have no row yet):

  live_extremes_row(sym, date, h=None, f=None, s=None)
                       -> the 18:00-knowable columns of <SYM>_extremes.csv for RTH date `date`
                          (session-outcome columns NaN).
  live_panel_row(sym, date, k=None, h=None, asof=None)
                       -> the feature columns of <SYM>_hourly_panel.csv at the close of bar k,
                          computed from the COMPLETE bars 0..k of that night only.  A bar stamped
                          ts is complete iff ts + 1 hour <= asof (default: now, US/Eastern);
                          incomplete trailing bars are dropped before anything is computed.
                          k=None means the latest complete bar.  For a historical (date, k) the row
                          equals the stored panel row on every feature column.
  short_session_warning(sym, date)
                       -> a note when the calendar flags holiday_tomorrow / pre_holiday fire.

Both the panel and the live row go through the same per-bar feature function (_bar_features) and
the same per-hour history (_hour_hist), so there is one set of formulas.

Bar index k: 0 = the 18:00 ET bar, ..., 8 = the 02:00 ET bar (fewer on short sessions).
Tokyo cash opens 09:00 JST = 19:00 ET in winter (EST, k=1) and 20:00 ET in summer (EDT, k=2);
Shanghai/HK open 09:30 local = 20:30 ET winter (inside k=2) / 21:30 ET summer (inside k=3).
The DST regime of a night is read from its 18:00 ET timestamp (never from the RTH date: the Friday
before a switch is in the old regime, its Sunday reopen in the new one).
"""
from __future__ import annotations

import os
import warnings
from datetime import timedelta

import numpy as np
import pandas as pd

from sessions import ASIA_HOURS, ET, EUROPE_HOURS, build_sessions, load_hourly, with_prior_context

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "research", "extremes")

MIN_NIGHT_BARS = 6        # a night with fewer Asia bars is not a session in the tables
N_BARS_FULL = 9

# RTH dates whose night is corrupted by a contract splice in the hourly files or by the
# September-2025 roll.  2024-06-21, 2024-12-20 and 2025-03-21 are not in the extremes tables
# (dropped by the session builder) but are listed for safety.  Both NQ and ES toggle between two
# contracts every bar from 2025-12-16 03:00 to 2025-12-17 13:00 ET.  This is the single source of
# truth: both detector modules import it.
SPLICE_SESSIONS = {
    "NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16", "2025-09-17", "2025-12-16", "2025-12-17"],
    "ES": ["2025-09-16", "2025-09-17", "2025-12-16", "2025-12-17"],
}

# columns of build_extremes, in order.  The first eight are knowable at 18:00 (a live row carries
# them); everything else describes the night and is NaN in a live row.
EXTREMES_18H_COLS = ["asia_gdate", "is_dst", "n_bars", "ref_close", "tokyo_open_k", "china_open_k",
                     "rth_ret_bp", "rth_range_bp"]
EXTREMES_COLS = [
    "asia_gdate", "is_dst", "n_bars", "ref_close", "asia_open", "asia_high", "asia_low", "asia_close",
    "hi_k", "lo_k", "hi_hour_et", "lo_hour_et", "hi_hour_jst", "lo_hour_jst", "tokyo_open_k", "china_open_k",
    "hi_first", "same_bar_extremes", "bars_between", "hi_bp", "lo_bp", "rng_bp", "open_bp", "close_bp",
    "close_loc", "open_loc", "hi_vs_rth_high_bp", "lo_vs_rth_low_bp", "high_above_rth_high", "low_below_rth_low",
    "hi_vs_rth_vwap_bp", "lo_vs_rth_vwap_bp", "hi_vs_prior_asia_high_bp", "lo_vs_prior_asia_low_bp",
    "high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar",
    "high_at_tokyo_open", "low_at_tokyo_open", "high_by_tokyo_open", "low_by_tokyo_open",
    "high_at_china_open", "low_at_china_open", "drop_after_hi_bp", "rally_after_lo_bp",
    "hi_bar_wick", "lo_bar_wick", "hi_bar_ret_bp", "lo_bar_ret_bp", "hi_bar_vol_share", "lo_bar_vol_share",
    "first_bar_ret_bp", "first_bar_rng_bp", "gap_open_bp", "asia_ret_bp", "rth_ret_bp", "rth_range_bp",
    "move_after_first_extreme_bp",
    "ovn_high_bp", "ovn_low_bp", "europe_above_asia_high", "europe_below_asia_low",
]
# panel columns that are labels (NaN in a live row)
PANEL_LABEL_COLS = ["high_done", "low_done", "remaining_up_bp", "remaining_down_bp",
                    "high_in_next_bar", "low_in_next_bar", "hi_k", "lo_k",
                    "overnight_high_done", "overnight_low_done"]
# panel columns that need the whole night (NaN in a live row)
PANEL_WHOLE_NIGHT_COLS = ["n_bars", "bars_left"]
# extra columns a live panel row carries
PANEL_LIVE_COLS = ["bar_ts", "latest_complete_k", "partial_bar_dropped", "n_bars_so_far"]


# --------------------------------------------------------------------------------------------------
# time helpers
# --------------------------------------------------------------------------------------------------
def load_h(sym: str, h: pd.DataFrame | None = None) -> pd.DataFrame:
    """The hourly frame (tz-aware ET index) for `sym`, or `h` when one is passed in."""
    return h if h is not None else load_hourly(os.path.join(DATA, f"{sym}_1h.csv"))


def _gdates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Globex trade date of each bar: bars at >= 18:00 belong to the next calendar day (tz-naive)."""
    day = pd.DatetimeIndex(index.tz_localize(None).normalize())
    return day + pd.to_timedelta((index.hour >= 18).astype(int), unit="D")


def _asof(asof) -> pd.Timestamp:
    """`asof` as a tz-aware ET timestamp (None = now).  A naive value is wall-clock ET; inside the
    repeated hour of the autumn switch it is read as the first (EDT, earlier) instant and inside the
    skipped hour of the spring switch it is shifted forward, so a naive string never raises.  (Both
    switches happen 02:00 Sunday, before the 18:00 reopen, so no Asia bar is affected.)"""
    if asof is None:
        return pd.Timestamp.now(tz=ET)
    ts = pd.Timestamp(asof)
    if ts.tzinfo is None:
        return ts.tz_localize(ET, ambiguous=True, nonexistent="shift_forward")
    return ts.tz_convert(ET)


def _is_dst(ts: pd.Timestamp) -> bool:
    return ts.dst() != timedelta(0)


def tokyo_open_bar(ts: pd.Timestamp) -> int:
    """Bar index of the Tokyo cash open (09:00 JST) inside the Asia session that starts at ts."""
    return 2 if _is_dst(ts) else 1


def china_open_bar(ts: pd.Timestamp) -> int:
    """Bar index containing the Shanghai/HK open (09:30 local)."""
    return 3 if _is_dst(ts) else 2


def _jst_hour(ts: pd.Timestamp) -> int:
    return (ts.hour + (13 if _is_dst(ts) else 14)) % 24


def _asia_groups(h: pd.DataFrame, min_bars: int = MIN_NIGHT_BARS) -> dict:
    """{Globex date -> Asia bars (18:00 .. 02:59)} for nights with at least `min_bars` bars."""
    a = h[np.isin(h.index.hour, ASIA_HOURS)]
    out = {}
    for gd, grp in a.groupby(_gdates(a.index)):
        if len(grp) >= min_bars:
            out[pd.Timestamp(gd)] = grp.sort_index()
    return out


def _europe_groups(h: pd.DataFrame) -> dict:
    """{Globex date -> Europe bars (03:00 .. 08:59 of that calendar day)}."""
    e = h[np.isin(h.index.hour, EUROPE_HOURS)]
    return {pd.Timestamp(gd): grp.sort_index() for gd, grp in e.groupby(_gdates(e.index))}


def _europe_complete(eur: pd.DataFrame | None) -> bool:
    return eur is not None and len(eur) >= len(EUROPE_HOURS)


def night_gdate(h: pd.DataFrame, date) -> pd.Timestamp:
    """Globex date of the night that follows RTH date `date`: the first Globex date with Asia bars
    in `h` after `date` (within 3 days), else the calendar rule (D+1; Friday -> Monday)."""
    date = pd.Timestamp(date).normalize()
    a = h.index[np.isin(h.index.hour, ASIA_HOURS)]
    gds = pd.DatetimeIndex(np.unique(_gdates(a)))
    cand = gds[(gds > date) & (gds <= date + pd.Timedelta(days=3))]
    if len(cand):
        return pd.Timestamp(cand[0])
    return date + pd.Timedelta(days=3 if date.dayofweek == 4 else 1)


def night_bars(h: pd.DataFrame, date, asof=None) -> tuple[pd.DataFrame, bool, pd.Timestamp]:
    """(complete Asia bars of the night that follows RTH date `date`, partial_bar_dropped, gdate).

    A bar stamped ts is complete iff ts + 1 hour <= asof; incomplete trailing bars are dropped.
    """
    gd = night_gdate(h, date)
    a = h[np.isin(h.index.hour, ASIA_HOURS)]
    raw = a[_gdates(a.index) == gd].sort_index()
    cut = _asof(asof)
    done = raw[(raw.index + pd.Timedelta(hours=1)) <= cut]
    return done, bool(len(done) < len(raw)), gd


def night_start_ts(h: pd.DataFrame, date) -> pd.Timestamp:
    """18:00 ET timestamp that opens the night after RTH date `date` (the bar's own timestamp when
    the file has it, else the wall-clock 18:00 of the calendar day before the Globex date)."""
    raw, _, gd = night_bars(h, date, asof=pd.Timestamp.max.tz_localize("UTC"))
    if len(raw):
        return raw.index[0]
    return pd.Timestamp((gd - pd.Timedelta(days=1)).strftime("%Y-%m-%d") + " 18:00", tz=ET)


def latest_rth_date(sym: str, h: pd.DataFrame | None = None) -> pd.Timestamp:
    """The most recent RTH date in the hourly data (what a live call defaults to)."""
    s = build_sessions(load_h(sym, h))
    return pd.Timestamp(s.index[-1])


# --------------------------------------------------------------------------------------------------
# extremes table
# --------------------------------------------------------------------------------------------------
def build_extremes(sym: str = "NQ", s: pd.DataFrame | None = None, h: pd.DataFrame | None = None) -> pd.DataFrame:
    h = load_h(sym, h)
    if s is None:
        s = with_prior_context(build_sessions(h))
    groups = _asia_groups(h)
    europe = _europe_groups(h)
    rows = []
    for d, r in s.iterrows():
        if pd.isna(r.get("asia_gdate")):
            continue
        gd = pd.Timestamp(r["asia_gdate"])
        if gd not in groups:
            continue
        g = groups[gd]
        ts0 = g.index[0]
        ref = float(r["post_close"])
        hi_k = int(np.argmax(g["High"].values))
        lo_k = int(np.argmin(g["Low"].values))
        hi = float(g["High"].iloc[hi_k]); lo = float(g["Low"].iloc[lo_k])
        n = len(g)
        close = float(g["Close"].iloc[-1]); opn = float(g["Open"].iloc[0])
        rng = hi - lo
        # what happened after each extreme
        after_hi = g.iloc[hi_k + 1:]
        after_lo = g.iloc[lo_k + 1:]
        drop_after_hi = (hi - after_hi["Low"].min()) / ref * 1e4 if len(after_hi) else (hi - float(g["Low"].iloc[hi_k])) / ref * 1e4
        rally_after_lo = (after_lo["High"].max() - lo) / ref * 1e4 if len(after_lo) else (float(g["High"].iloc[lo_k]) - lo) / ref * 1e4
        # bar-level: did the extreme bar close near its extreme (rejection wick)?
        hb = g.iloc[hi_k]; lb = g.iloc[lo_k]
        hi_bar_wick = (hb["High"] - max(hb["Open"], hb["Close"])) / max(hb["High"] - hb["Low"], 1e-9)
        lo_bar_wick = (min(lb["Open"], lb["Close"]) - lb["Low"]) / max(lb["High"] - lb["Low"], 1e-9)
        # running-extreme hold: the bar index after which the running high never changed = hi_k
        tko = tokyo_open_bar(ts0); cno = china_open_bar(ts0)
        rec = dict(
            date=d, asia_gdate=gd, is_dst=int(_is_dst(ts0)), n_bars=n, ref_close=ref,
            asia_open=opn, asia_high=hi, asia_low=lo, asia_close=close,
            hi_k=hi_k, lo_k=lo_k, hi_hour_et=int(g.index[hi_k].hour), lo_hour_et=int(g.index[lo_k].hour),
            hi_hour_jst=_jst_hour(g.index[hi_k]), lo_hour_jst=_jst_hour(g.index[lo_k]),
            tokyo_open_k=tko, china_open_k=cno,
            hi_first=int(hi_k < lo_k), same_bar_extremes=int(hi_k == lo_k), bars_between=abs(hi_k - lo_k),
            hi_bp=(hi / ref - 1) * 1e4, lo_bp=(lo / ref - 1) * 1e4, rng_bp=rng / ref * 1e4,
            open_bp=(opn / ref - 1) * 1e4, close_bp=(close / ref - 1) * 1e4,
            close_loc=(close - lo) / rng if rng > 0 else np.nan,
            open_loc=(opn - lo) / rng if rng > 0 else np.nan,
            hi_vs_rth_high_bp=(hi / r["rth_high"] - 1) * 1e4, lo_vs_rth_low_bp=(lo / r["rth_low"] - 1) * 1e4,
            high_above_rth_high=int(hi > r["rth_high"]), low_below_rth_low=int(lo < r["rth_low"]),
            hi_vs_rth_vwap_bp=(hi / r["rth_vwap"] - 1) * 1e4, lo_vs_rth_vwap_bp=(lo / r["rth_vwap"] - 1) * 1e4,
            hi_vs_prior_asia_high_bp=(hi / r["prior_asia_high"] - 1) * 1e4 if pd.notna(r.get("prior_asia_high")) else np.nan,
            lo_vs_prior_asia_low_bp=(lo / r["prior_asia_low"] - 1) * 1e4 if pd.notna(r.get("prior_asia_low")) else np.nan,
            high_in_first_bar=int(hi_k == 0), low_in_first_bar=int(lo_k == 0),
            high_in_last_bar=int(hi_k == n - 1), low_in_last_bar=int(lo_k == n - 1),
            high_at_tokyo_open=int(hi_k == tko), low_at_tokyo_open=int(lo_k == tko),
            high_by_tokyo_open=int(hi_k <= tko), low_by_tokyo_open=int(lo_k <= tko),
            high_at_china_open=int(hi_k == cno), low_at_china_open=int(lo_k == cno),
            drop_after_hi_bp=drop_after_hi, rally_after_lo_bp=rally_after_lo,
            hi_bar_wick=hi_bar_wick, lo_bar_wick=lo_bar_wick,
            hi_bar_ret_bp=(hb["Close"] / hb["Open"] - 1) * 1e4, lo_bar_ret_bp=(lb["Close"] / lb["Open"] - 1) * 1e4,
            hi_bar_vol_share=float(hb["Volume"] / max(g["Volume"].sum(), 1)),
            lo_bar_vol_share=float(lb["Volume"] / max(g["Volume"].sum(), 1)),
            first_bar_ret_bp=(float(g["Close"].iloc[0]) / opn - 1) * 1e4,
            first_bar_rng_bp=(float(g["High"].iloc[0]) - float(g["Low"].iloc[0])) / ref * 1e4,
            gap_open_bp=(opn / ref - 1) * 1e4,
            asia_ret_bp=(close / opn - 1) * 1e4,
            rth_ret_bp=(r["rth_close"] / r["rth_open"] - 1) * 1e4,
            rth_range_bp=(r["rth_high"] - r["rth_low"]) / ref * 1e4,
        )
        # the "opposite extreme after the first extreme" = the realised move available after the first extreme
        rec["move_after_first_extreme_bp"] = rec["drop_after_hi_bp"] if rec["hi_first"] else rec["rally_after_lo_bp"]
        # overnight window = this night's Asia bars + the Europe bars 03:00-08:59 of the same Globex date
        eur = europe.get(gd)
        if _europe_complete(eur):
            e_hi = float(eur["High"].max()); e_lo = float(eur["Low"].min())
            rec.update(ovn_high_bp=(max(hi, e_hi) / ref - 1) * 1e4, ovn_low_bp=(min(lo, e_lo) / ref - 1) * 1e4,
                       europe_above_asia_high=int(e_hi > hi), europe_below_asia_low=int(e_lo < lo))
        else:
            rec.update(ovn_high_bp=np.nan, ovn_low_bp=np.nan, europe_above_asia_high=np.nan, europe_below_asia_low=np.nan)
        rows.append(rec)
    x = pd.DataFrame(rows).set_index("date").sort_index()
    assert list(x.columns) == EXTREMES_COLS, "EXTREMES_COLS is out of sync with build_extremes"
    return x


# --------------------------------------------------------------------------------------------------
# per-bar features (shared by the panel and the live row)
# --------------------------------------------------------------------------------------------------
def _hour_hist(groups: dict) -> pd.DataFrame:
    """Per-bar rolling 20-session medians of volume and bar range by ET hour, from the PRIOR
    sessions only (shift(1) semantics): the value stamped on a bar is the median of the previous
    20 bars at that hour (at least 10 required), the bar itself excluded."""
    allbars = pd.concat(list(groups.values())).sort_index()
    allbars = allbars.assign(rng=allbars["High"] - allbars["Low"])
    hist = {}
    for hr, grp in allbars.groupby(allbars.index.hour):
        grp = grp.sort_index()
        hist[hr] = pd.DataFrame({
            "vol_med20": grp["Volume"].shift(1).rolling(20, min_periods=10).median(),
            "rng_med20": grp["rng"].shift(1).rolling(20, min_periods=10).median(),
        }, index=grp.index)
    return pd.concat(hist.values()).sort_index()


def _prior_range_median(x: pd.DataFrame, date) -> float:
    """Ex-ante session range reference: median realised Asia range (bp) of the 20 sessions strictly
    before `date` in the extremes table (at least 10 required), i.e. x['rng_bp'].shift(1).rolling(20,
    min_periods=10).median() evaluated at `date`."""
    prior = x.loc[x.index < pd.Timestamp(date), "rng_bp"].tail(20)
    return float(prior.median()) if prior.notna().sum() >= 10 else np.nan


def _bar_features(g: pd.DataFrame, k: int, ref: float, srow: pd.Series, med_rng: float, hh: pd.Series,
                  tko: int, cno: int) -> dict:
    """Everything known at the close of bar k of a night whose bars are `g` (only rows 0..k are used).

    ref      17:00 reference close;  srow  the sessions row of the RTH date (RTH levels, prior Asia levels)
    med_rng  ex-ante 20-session median Asia range in bp (NaN allowed)
    hh       per-hour medians for this bar (vol_med20, rng_med20) from the prior 20 sessions
    tko/cno  Tokyo / China open bar index of this night (from its 18:00 timestamp)
    """
    sub = g.iloc[:k + 1]
    hi_v = sub["High"].values; lo_v = sub["Low"].values
    k_hi = int(np.argmax(hi_v)); k_lo = int(np.argmin(lo_v))      # first bar that set the running extreme
    run_hi = float(hi_v[k_hi]); run_lo = float(lo_v[k_lo])
    b = g.iloc[k]; ts = g.index[k]
    c = float(b["Close"])
    rr = run_hi - run_lo
    return dict(
        k=k, hour_et=int(ts.hour), hour_jst=_jst_hour(ts), is_dst=int(_is_dst(ts)),
        tokyo_open_k=tko, china_open_k=cno,
        after_tokyo_open=int(k >= tko), after_china_open=int(k >= cno),
        run_hi_bp=(run_hi / ref - 1) * 1e4, run_lo_bp=(run_lo / ref - 1) * 1e4, run_rng_bp=rr / ref * 1e4,
        run_rng_vs_med20=(rr / ref * 1e4) / med_rng if pd.notna(med_rng) and med_rng > 0 else np.nan,
        bars_since_hi=k - k_hi, bars_since_lo=k - k_lo,
        pos_in_range=(c - run_lo) / rr if rr > 0 else 0.5,
        cum_ret_bp=(c / ref - 1) * 1e4, bar_ret_bp=(c / b["Open"] - 1) * 1e4,
        bar_rng_bp=(b["High"] - b["Low"]) / ref * 1e4,
        bar_rng_rel=(b["High"] - b["Low"]) / hh["rng_med20"] if pd.notna(hh["rng_med20"]) and hh["rng_med20"] > 0 else np.nan,
        bar_vol_rel=b["Volume"] / hh["vol_med20"] if pd.notna(hh["vol_med20"]) and hh["vol_med20"] > 0 else np.nan,
        bar_close_loc=(c - b["Low"]) / (b["High"] - b["Low"]) if b["High"] > b["Low"] else 0.5,
        run_hi_above_rth_high=int(run_hi > srow["rth_high"]), run_lo_below_rth_low=int(run_lo < srow["rth_low"]),
        dist_rth_high_bp=(srow["rth_high"] / c - 1) * 1e4, dist_rth_low_bp=(srow["rth_low"] / c - 1) * 1e4,
        dist_rth_vwap_bp=(srow["rth_vwap"] / c - 1) * 1e4,
        dist_prior_asia_high_bp=(srow["prior_asia_high"] / c - 1) * 1e4 if pd.notna(srow.get("prior_asia_high")) else np.nan,
        dist_prior_asia_low_bp=(srow["prior_asia_low"] / c - 1) * 1e4 if pd.notna(srow.get("prior_asia_low")) else np.nan,
        _run_hi=run_hi, _run_lo=run_lo, _close=c,          # internal, used for the labels; stripped below
    )


_LEAD = ("k", "hour_et", "hour_jst", "is_dst")
_INTERNAL = ("_run_hi", "_run_lo", "_close")


def _panel_record(date, feat: dict, n_bars, bars_left) -> dict:
    """Assemble the panel column order: date, k, hour_et, hour_jst, is_dst, n_bars, bars_left, features."""
    rec = {"date": date}
    for key in _LEAD:
        rec[key] = feat[key]
    rec["n_bars"] = n_bars; rec["bars_left"] = bars_left
    rec.update({kk: v for kk, v in feat.items() if kk not in _LEAD and kk not in _INTERNAL})
    return rec


def hourly_panel(sym: str = "NQ", x: pd.DataFrame | None = None, s: pd.DataFrame | None = None,
                 h: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per (RTH date, Asia bar k) with information known at the close of bar k, plus labels."""
    h = load_h(sym, h)
    if s is None:
        s = with_prior_context(build_sessions(h))
    if x is None:
        x = build_extremes(sym, s, h)
    groups = _asia_groups(h)
    europe = _europe_groups(h)
    hist = _hour_hist(groups)
    med_rng = x["rng_bp"].shift(1).rolling(20, min_periods=10).median()

    rows = []
    for d, r in x.iterrows():
        gd = pd.Timestamp(r["asia_gdate"])
        g = groups[gd]
        ref = r["ref_close"]; srow = s.loc[d]
        hi, lo = r["asia_high"], r["asia_low"]
        eur = europe.get(gd)
        if _europe_complete(eur):
            ovn_hi = max(hi, float(eur["High"].max())); ovn_lo = min(lo, float(eur["Low"].min()))
        else:
            ovn_hi = ovn_lo = np.nan
        tko, cno = int(r["tokyo_open_k"]), int(r["china_open_k"])
        n = len(g)
        for k in range(n):
            ts = g.index[k]
            hh = hist.loc[ts] if ts in hist.index else pd.Series({"vol_med20": np.nan, "rng_med20": np.nan})
            feat = _bar_features(g, k, ref, srow, med_rng.loc[d], hh, tko, cno)
            run_hi, run_lo, c = feat["_run_hi"], feat["_run_lo"], feat["_close"]
            rec = _panel_record(d, feat, n, n - 1 - k)
            rec.update(
                high_done=int(run_hi >= hi - 1e-9), low_done=int(run_lo <= lo + 1e-9),
                remaining_up_bp=(hi / c - 1) * 1e4, remaining_down_bp=(lo / c - 1) * 1e4,
                high_in_next_bar=int(r["hi_k"] == k + 1), low_in_next_bar=int(r["lo_k"] == k + 1),
                hi_k=r["hi_k"], lo_k=r["lo_k"],
                overnight_high_done=int(run_hi >= ovn_hi - 1e-9) if pd.notna(ovn_hi) else np.nan,
                overnight_low_done=int(run_lo <= ovn_lo + 1e-9) if pd.notna(ovn_lo) else np.nan,
            )
            rows.append(rec)
    return pd.DataFrame(rows)


def build_all(sym: str = "NQ", write: bool = True):
    from features import build_feature_table
    f, s = build_feature_table(sym, "ES" if sym == "NQ" else "NQ")
    x = build_extremes(sym, s)
    keep = [c for c in f.columns if c not in x.columns]
    xf = x.join(f[keep], how="left")
    p = hourly_panel(sym, x, s)
    if write:
        os.makedirs(OUT, exist_ok=True)
        xf.to_csv(os.path.join(OUT, f"{sym}_extremes.csv"))
        p.to_csv(os.path.join(OUT, f"{sym}_hourly_panel.csv"), index=False)
    return xf, p


# --------------------------------------------------------------------------------------------------
# live rows (the night has started; the tables have no row for it yet)
# --------------------------------------------------------------------------------------------------
def live_extremes_row(sym: str, date, h: pd.DataFrame | None = None, f: pd.DataFrame | None = None,
                      s: pd.DataFrame | None = None) -> pd.DataFrame:
    """One-row frame (index = RTH date) with every 18:00-knowable column of <SYM>_extremes.csv:
    the features.build_feature_table columns plus ref_close (= post_close), is_dst, tokyo_open_k,
    china_open_k, rth_ret_bp, rth_range_bp, asia_gdate; n_bars and every session-outcome column NaN.
    The DST regime comes from the night's 18:00 ET timestamp (the bar itself when `h` has it).

    `f`/`s` may be a pre-built feature table / sessions table (build_feature_table output); the
    row's 18:00 features do not depend on the night's bars, so a truncated `h` only moves the DST
    lookup.  Raises ValueError when `date` is not an RTH date in `f`.
    """
    date = pd.Timestamp(date).normalize()
    if f is None:
        from features import build_feature_table
        f, s_built = build_feature_table(sym, "ES" if sym == "NQ" else "NQ")
        s = s if s is not None else s_built
    if date not in f.index:
        raise ValueError(f"{date.date()} is not an RTH date in the {sym} feature table "
                         f"(first {f.index[0].date()}, last {f.index[-1].date()})")
    h = load_h(sym, h)
    fr = f.loc[date]
    if s is not None and date in s.index:
        sr = s.loc[date]
        ref, o, hi, lo, c = (float(sr[k]) for k in ("post_close", "rth_open", "rth_high", "rth_low", "rth_close"))
    else:
        ref, o, hi, lo, c = (float(fr[k]) for k in ("lvl_post_close", "lvl_rth_open", "lvl_rth_high", "lvl_rth_low", "lvl_rth_close"))
    if not np.isfinite(ref):
        raise ValueError(f"{sym} {date.date()}: no 17:00 reference close (post_close) in the hourly data")
    gd = night_gdate(h, date)
    ts0 = night_start_ts(h, date)
    rec = {col: np.nan for col in EXTREMES_COLS}
    rec.update(asia_gdate=gd, is_dst=int(_is_dst(ts0)), n_bars=np.nan, ref_close=ref,
               tokyo_open_k=tokyo_open_bar(ts0), china_open_k=china_open_bar(ts0),
               rth_ret_bp=(c / o - 1) * 1e4, rth_range_bp=(hi - lo) / ref * 1e4)
    x1 = pd.DataFrame([rec], index=pd.DatetimeIndex([date], name="date"))
    keep = [col for col in f.columns if col not in x1.columns]
    return x1.join(f.loc[[date], keep], how="left")


def live_panel_row(sym: str, date, k: int | None = None, h: pd.DataFrame | None = None, asof=None,
                   s: pd.DataFrame | None = None, x: pd.DataFrame | None = None) -> pd.DataFrame:
    """One-row frame with every feature column of <SYM>_hourly_panel.csv at the close of bar k of
    the night that follows RTH date `date`, computed from the COMPLETE bars 0..k of that night only.

    Completeness: a bar stamped ts is complete iff ts + 1 hour <= asof (default now, US/Eastern;
    str / Timestamp accepted, naive = ET).  Incomplete trailing bars are dropped before anything is
    computed.  k=None -> the latest complete bar; k beyond it -> ValueError naming latest_complete_k.
    The per-hour 20-session medians and the 20-session median Asia range come from sessions
    strictly before the night (shift(1) semantics), so for a historical (date, k) the row equals
    the stored panel row on every feature column.  Labels, n_bars and bars_left are NaN; the extra
    columns bar_ts, latest_complete_k, partial_bar_dropped, n_bars_so_far are appended.
    `s` / `x` (sessions / extremes tables built from `h`) can be passed to skip rebuilding them.
    A night whose first bar in `h` is not stamped 18:00 raises ValueError: k is positional in the
    night's bars, so a missing 18:00 bar would shift every bar index.
    """
    date = pd.Timestamp(date).normalize()
    h = load_h(sym, h)
    if s is None:
        s = with_prior_context(build_sessions(h))
    if date not in s.index:
        raise ValueError(f"{date.date()} is not an RTH date in the {sym} hourly data (last {s.index[-1].date()})")
    if x is None:
        x = build_extremes(sym, s, h)
    cut = _asof(asof)
    g, dropped, gd = night_bars(h, date, cut)
    if g.empty:
        raise ValueError(f"{sym} {date.date()}: no complete Asia bar as of {cut:%Y-%m-%d %H:%M %Z}")
    if g.index[0].hour != 18:
        # k is positional in the night's bars: without the 18:00 bar every k (and the hour-based
        # semantics of tokyo_open_k / after_tokyo_open) would be shifted, so the row is refused
        raise ValueError(f"{sym} {date.date()}: the first Asia bar in the data is stamped {g.index[0]:%H:%M %Z}, "
                         f"not 18:00 - bar index k would be shifted (missing 18:00 bar?); no live row is served")
    latest = len(g) - 1
    if k is None:
        k = latest
    k = int(k)
    if k < 0 or k > latest:
        raise ValueError(f"{sym} {date.date()}: bar k={k} is not complete as of {cut:%Y-%m-%d %H:%M %Z} "
                         f"(latest_complete_k={latest})")
    if k >= N_BARS_FULL:
        raise ValueError(f"{sym} {date.date()}: k={k} beyond the last Asia bar (k <= {N_BARS_FULL - 1})")
    srow = s.loc[date]
    ref = float(srow["post_close"])
    if not np.isfinite(ref):
        raise ValueError(f"{sym} {date.date()}: no 17:00 reference close (post_close) in the hourly data")
    ts0 = g.index[0]
    tko, cno = tokyo_open_bar(ts0), china_open_bar(ts0)
    # per-hour history from the nights strictly before this one, this night's complete bars appended
    # (shift(1) excludes them, so they only serve as the lookup rows)
    groups = {gdd: grp for gdd, grp in _asia_groups(h).items() if gdd < gd}
    groups[gd] = g
    hist = _hour_hist(groups)
    ts = g.index[k]
    hh = hist.loc[ts] if ts in hist.index else pd.Series({"vol_med20": np.nan, "rng_med20": np.nan})
    feat = _bar_features(g, k, ref, srow, _prior_range_median(x, date), hh, tko, cno)
    rec = _panel_record(date, feat, np.nan, np.nan)
    rec.update({col: np.nan for col in PANEL_LABEL_COLS})
    rec.update(bar_ts=str(ts), latest_complete_k=latest, partial_bar_dropped=bool(dropped), n_bars_so_far=len(g))
    return pd.DataFrame([rec])


def short_session_warning(sym: str, date) -> str | None:
    """A note when the calendar flags holiday_tomorrow / pre_holiday fire for RTH date `date`: the
    Globex session around a US holiday may halt at 13:00 ET and the night may have fewer than the
    9 bars the detectors were trained on.  None otherwise."""
    from calendar_features import calendar_features
    date = pd.Timestamp(date).normalize()
    cf = calendar_features(pd.DatetimeIndex([date])).iloc[0]
    flags = [c for c in ("holiday_tomorrow", "pre_holiday") if int(cf.get(c, 0)) == 1]
    if not flags:
        return None
    return (f"{sym} {date.date()}: calendar flag(s) {', '.join(flags)} fire - the Globex session around a US "
            f"holiday may halt at 13:00 ET and this night may have fewer than {N_BARS_FULL} Asia bars; the "
            f"detectors are trained on full {N_BARS_FULL}-bar nights only, so read the outputs with care.")


if __name__ == "__main__":
    import sys
    import time
    for sym in (sys.argv[1:] or ["NQ", "ES"]):
        t0 = time.time()
        xf, p = build_all(sym)
        print(sym, "extremes", xf.shape, "panel", p.shape, "->", OUT, f"({time.time() - t0:.1f}s)")
