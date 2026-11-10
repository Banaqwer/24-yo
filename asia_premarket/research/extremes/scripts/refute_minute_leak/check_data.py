"""Data / knowability checks for the minute lens (M1, M2, M6, M8, M10)."""
import numpy as np, pandas as pd
from scipy.stats import binomtest, binom, fisher_exact, chisquare

ROOT = "."
LM = "research/extremes/scripts/lens_minute"
ET = "America/New_York"

print("=== raw 15m data")
for sym in ("NQ", "ES"):
    d = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv", index_col=0)
    idx = pd.to_datetime(d.index, utc=True).tz_convert(ET)
    print(sym, "rows", len(d), "range", idx.min(), "->", idx.max(), "dup idx", idx.duplicated().sum())
    # bars per Asia session (18:00..02:45)
    h = pd.DataFrame(index=idx); h["hour"] = idx.hour; h["minute"] = idx.minute
    g = pd.Series(idx.date, index=idx); sh = idx.hour >= 18
    g[sh] = (idx[sh] + pd.Timedelta(days=1)).date
    h["gdate"] = g.values
    a = h[h.hour.isin(list(range(18, 24)) + [0, 1, 2])]
    cnt = a.groupby("gdate").size()
    print("   sessions by bar count:", cnt.value_counts().to_dict())
    print("   sessions with <36 bars:", cnt[cnt < 36].to_dict())
    # DST transition: sessions whose 18:00 ET bar is EST
    first = a.groupby("gdate").apply(lambda x: x.index[0])
    dst = first.map(lambda t: t.dst() != pd.Timedelta(0))
    print("   EDT sessions", int(dst.sum()), "EST sessions", int((~dst).sum()), "EST gdates:", [str(x) for x in dst[~dst].index])

print("\n=== M2: is the 18:00 15m-bar Open an artefact (== 17:00 close)?")
for sym in ("NQ", "ES"):
    s = pd.read_csv(f"{LM}/{sym}_q15_sessions.csv", index_col=0, parse_dates=True); s = s[s.n_q == 36]
    tick = 0.25
    eq = (s.open_18 - s.ref_close).abs() < tick / 2
    print(f"{sym}: open_18 == ref_close (17:00 close) in {int(eq.sum())}/{len(s)}; |gap| median {s.gap_open_bp.abs().median():.1f} bp; "
          f"|gap|<1bp in {int((s.gap_open_bp.abs()<1).sum())}")
    # open within 1 tick of the session extreme (not exact equality)
    hi_t = ((s.hi - s.open_18) <= tick + 1e-9); lo_t = ((s.open_18 - s.lo) <= tick + 1e-9)
    print(f"   open within 1 tick of session high {int(hi_t.sum())}/48, of session low {int(lo_t.sum())}/48; exact: {int(s.open_is_high.sum())}, {int(s.open_is_low.sum())}")
    # claim M2 cites ES 1/48 and 2/48 -- those are 'open == q0-bar extreme', not session extreme
    b = pd.read_csv(f"{LM}/{sym}_q15_bars.csv", parse_dates=["date"]); b = b[b.date.isin(s.index)]
    q0 = b[b.q == 0]
    print(f"   open == q0-bar high {int((q0.open==q0.high).sum())}/48, == q0-bar low {int((q0.open==q0.low).sum())}/48 (these are the numbers M2 quotes as 'session' for ES)")

print("\n=== M1/M2: arcsine-law (driftless random walk) null for the location of the extreme")
# continuous arcsine: P(argmax in [a,b]) = (2/pi)(asin(sqrt(b)) - asin(sqrt(a)))
def arc(a, b): return (2 / np.pi) * (np.arcsin(np.sqrt(b)) - np.arcsin(np.sqrt(a)))
pq = np.array([arc(q / 36, (q + 1) / 36) for q in range(36)])
print("arcsine P(extreme in quarter q): q0 %.3f q1 %.3f q2 %.3f q17 %.3f q33 %.3f q34 %.3f q35 %.3f; edges q0+q35 %.3f; uniform 1/36=%.3f" % (pq[0], pq[1], pq[2], pq[17], pq[33], pq[34], pq[35], pq[0] + pq[35], 1 / 36))
print("arcsine P(hour k): ", np.round([arc(k / 9, (k + 1) / 9) for k in range(9)], 3), " population hi_k%: 23.5 8.1 11.1 8.6 5.2 5.5 5.5 8.1 24.4")
print("arcsine P(q0 | k=0) = P(q35 | k=8) = %.3f (M2 uses 25%% uniform-within-hour as the base rate)" % (pq[0] / arc(0, 1 / 9)))
for sym in ("NQ", "ES"):
    s = pd.read_csv(f"{LM}/{sym}_q15_sessions.csv", index_col=0, parse_dates=True); s = s[s.n_q == 36]
    for side in ("hi_q", "lo_q"):
        obs = s[side].value_counts().reindex(range(36), fill_value=0).values
        n = len(s)
        # edge test vs arcsine
        ke = int(obs[0] + obs[35]); p_edge = binomtest(ke, n, pq[0] + pq[35]).pvalue
        k0 = int(obs[0]); k35 = int(obs[35])
        # interior shape vs arcsine: 4 bins (q1-4, q5-17, q18-30, q31-34)
        bins = [(1, 5), (5, 18), (18, 31), (31, 35)]
        ob = np.array([obs[a:b].sum() for a, b in bins]); ex = np.array([pq[a:b].sum() for a, b in bins]); ex = ex / ex.sum() * ob.sum()
        chi = chisquare(ob, ex)
        ex_u = np.full(4, ob.sum() / 34) * np.array([4, 13, 13, 4])
        chi_u = chisquare(ob, ex_u)
        print(f"{sym} {side}: edge {ke}/{n}={ke/n:.3f} vs arcsine {pq[0]+pq[35]:.3f} p={p_edge:.3f} (vs uniform 0.056: p={binomtest(ke,n,2/36).pvalue:.1e}); "
              f"q0 {k0} (arcsine exp {n*pq[0]:.1f}, p={binomtest(k0,n,pq[0]).pvalue:.2f}) q35 {k35} (p={binomtest(k35,n,pq[35]).pvalue:.2f}); "
              f"interior 4-bin obs {ob.tolist()} arcsine-exp {np.round(ex,1).tolist()} chi2 p={chi.pvalue:.2f} | uniform-exp {np.round(ex_u,1).tolist()} p={chi_u.pvalue:.2f}")

print("\n=== M6: population (579 sessions, hourly) rates of same-bar / adjacent-bar extremes")
for sym in ("NQ", "ES"):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True)
    bad = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16", "2025-09-15"], "ES": ["2025-12-16", "2025-12-15"]}[sym]
    x = x.drop(pd.to_datetime(bad), errors="ignore")
    full = x[x.n_bars == 9]
    d = (full.hi_k - full.lo_k).abs()
    a = full[full.index < "2025-09-01"]; b = full[full.index >= "2025-09-01"]
    def ci(v):
        v = np.asarray(v, float); rng = np.random.default_rng(3); i = rng.integers(0, len(v), (5000, len(v)))
        return np.round(np.percentile(v[i].mean(1), [5, 95]), 3)
    print(f"{sym}: n={len(full)} same_bar_extremes {int(full.same_bar_extremes.sum())}={full.same_bar_extremes.mean():.3f} CI{ci(full.same_bar_extremes)}; "
          f"|hi_k-lo_k|<=1 (<=~2h) {int((d<=1).sum())}={(d<=1).mean():.3f} CI{ci(d<=1)}; |dk|>=6 {(d>=6).mean():.3f}; median |dk| {d.median()} h")
    print(f"   halves same-bar: A {int(a.same_bar_extremes.sum())}/{len(a)}={a.same_bar_extremes.mean():.3f}  B {int(b.same_bar_extremes.sum())}/{len(b)}={b.same_bar_extremes.mean():.3f}; "
          f"|dk|<=1: A {((a.hi_k-a.lo_k).abs()<=1).mean():.3f} B {((b.hi_k-b.lo_k).abs()<=1).mean():.3f}")
    w = full[(full.index >= "2026-08-31") & (full.index <= "2026-11-06")]
    print(f"   window subset n={len(w)}: same-bar {int(w.same_bar_extremes.sum())}, |dk|<=1 {int(((w.hi_k-w.lo_k).abs()<=1).sum())}; rule-of-three upper bound for 0/48 = {3/48:.3f}")
    # which sessions have same-bar extremes (any splice?)
    sb = full[full.same_bar_extremes == 1]
    print("   same-bar dates:", [str(t.date()) for t in sb.index[:30]], "rng_bp med", sb.rng_bp.median() if len(sb) else None)

print("\n=== M8: DST composition and DST-conditional population rates for the low/high-by-Tokyo-open stats")
x = pd.read_csv(f"{ROOT}/research/extremes/NQ_extremes.csv", index_col=0, parse_dates=True)
full = x[x.n_bars == 9]
for c in ("low_by_tokyo_open", "high_by_tokyo_open", "low_in_last_bar", "low_in_first_bar"):
    print(f"  {c}: pop all {full[c].mean():.3f} (EDT {full[full.is_dst==1][c].mean():.3f} n={int((full.is_dst==1).sum())}; EST {full[full.is_dst==0][c].mean():.3f} n={int((full.is_dst==0).sum())})")
w = full[(full.index >= "2026-08-31") & (full.index <= "2026-11-06")]
print(f"  window: n={len(w)} EDT={int(w.is_dst.sum())}; low_by_tokyo_open {w.low_by_tokyo_open.mean():.3f}; vs EDT-pop {full[full.is_dst==1].low_by_tokyo_open.mean():.3f}: p={binomtest(int(w.low_by_tokyo_open.sum()), len(w), full[full.is_dst==1].low_by_tokyo_open.mean()).pvalue:.4f}")
print(f"  window tokyo_open_k values: {w.tokyo_open_k.value_counts().to_dict()}; EST sessions: {[str(t.date()) for t in w[w.is_dst==0].index]}")

print("\n=== M10: power of the zone tests (n=48, single quarter, p0=1/36)")
for mult in (2, 3, 4):
    p1 = mult / 36
    print(f"  true hazard = {mult}x uniform: P(observe <=2 of 48) = {binom.cdf(2, 48, p1):.3f}; P(observe <=4) = {binom.cdf(4, 48, p1):.3f}")
print(f"  ES Tokyo-open-quarter lows 4/48 = {4/48:.3f} = {4/48*36:.1f}x uniform; NQ Tokyo-open 2/48 = {2/48*36:.1f}x uniform")
# China-data sessions: which actually have a release inside 09:30-10:15 CST?
cal = pd.read_csv(f"{ROOT}/research/event_calendar.csv"); cal["date"] = pd.to_datetime(cal["date"])
ev = cal[(cal.date >= "2026-08-31") & (cal.date <= "2026-11-10") & (cal.category == "cn_data")]
print("  cn_data events in window:\n", ev[["date", "event", "time_et"]].to_string(index=False))
