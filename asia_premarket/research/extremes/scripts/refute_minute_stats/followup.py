"""Follow-up checks: M3 knowable stop-run, M5 corrected denominators, M9 incremental value, M10 second-half Tokyo-open share."""
import numpy as np, pandas as pd
from scipy.stats import binomtest, fisher_exact
ROOT = "."
OUT = "research/extremes/scripts/refute_minute_stats"
rng = np.random.default_rng(5)
def bci(v, B=5000):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    idx = rng.integers(0, len(v), (B, len(v))); return tuple(np.round(np.percentile([v[i].mean() for i in idx], [5, 95]), 3))
def bp(k, n, p0): return binomtest(int(k), int(n), p0).pvalue

for sym in ("NQ", "ES"):
    s = pd.read_csv(f"{OUT}/{sym}_sessions.csv", index_col=0, parse_dates=True)
    b = pd.read_csv(f"{OUT}/{sym}_bars.csv", parse_dates=["date"])
    print(f"\n===== {sym}")
    # ---- M3 knowable stop-run: first bar that breaks f15 high, break<10bp at that bar AND bar closes back below f15h
    bb = b.merge(s[["f15_rng_bp", "ref"]], left_on="date", right_index=True)
    # reconstruct f15 high/low from q0 bars
    q0 = b[b.q == 0].set_index("date")
    f15h = q0.close_loc * 0  # placeholder
    # need raw highs: rebuild from the raw 15m file
    d = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True).tz_convert("America/New_York")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    rows = []
    for date, r in s.iterrows():
        gd = pd.Timestamp(date) + pd.Timedelta(days=1)
        # find session bars: from date 18:00 ... (handles Fri->Sun via the extremes asia_gdate; use the session's actual rows via q bars)
        pass
    # simpler: use the per-bar table which has close_loc etc but not raw H/L; recompute from raw by matching date -> we stored ref, hi, lo; rebuild session groups like recompute.py
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True); x["asia_gdate"] = pd.to_datetime(x["asia_gdate"])
    gd_to_date = {pd.Timestamp(g).date(): dt for dt, g in x["asia_gdate"].items()}
    h = d.copy(); g = pd.Series(h.index.date, index=h.index); sh = h.index.hour >= 18; g[sh] = (h.index[sh] + pd.Timedelta(days=1)).date; h["gdate"] = g.values
    a = h[h.index.hour.isin(list(range(18, 24)) + [0, 1, 2])]
    res = []
    for gd, grp in a.groupby("gdate"):
        if gd not in gd_to_date: continue
        grp = grp.sort_index()
        if len(grp) != 36: continue
        date = gd_to_date[gd]; ref = float(x.loc[date, "ref_close"])
        H = grp.High.values; L = grp.Low.values; C = grp.Close.values
        hi = H.max(); lo = L.min(); hq = H.argmax(); lq = L.argmin()
        f15h, f15l = H[0], L[0]
        ih = next((i for i in range(1, 36) if H[i] > f15h), None); il = next((i for i in range(1, 36) if L[i] < f15l), None)
        rec = dict(date=date)
        if ih is not None:
            rec.update(h_brk_bp=(H[ih] - f15h) / ref * 1e4, h_close_back=int(C[ih] < f15h), h_is_sess_high=int(ih == hq), h_final_within10=int((hi - f15h) / ref * 1e4 < 10))
        if il is not None:
            rec.update(l_brk_bp=(f15l - L[il]) / ref * 1e4, l_close_back=int(C[il] > f15l), l_is_sess_low=int(il == lq), l_final_within10=int((f15l - lo) / ref * 1e4 < 10))
        res.append(rec)
    R = pd.DataFrame(res)
    thr = 10 if sym == "NQ" else 5
    for side in ("h", "l"):
        m = R.dropna(subset=[f"{side}_brk_bp"])
        rule = m[(m[f"{side}_brk_bp"] < thr) & (m[f"{side}_close_back"] == 1)]
        notrule = m[~((m[f"{side}_brk_bp"] < thr) & (m[f"{side}_close_back"] == 1))]
        print(f"M3 {side}: first-break bars n={len(m)}; KNOWABLE rule (break<{thr}bp AND bar closes back inside f15): n={len(rule)}: that bar is the session extreme {int(rule[f'{side}_is_sess_high' if side=='h' else f'{side}_is_sess_low'].sum())}/{len(rule)}; final break stays <10bp {int(rule[f'{side}_final_within10'].sum())}/{len(rule)} | not-rule: session extreme {int(notrule[f'{side}_is_sess_high' if side=='h' else f'{side}_is_sess_low'].sum())}/{len(notrule)}, final<10 {int(notrule[f'{side}_final_within10'].sum())}/{len(notrule)}")

    # ---- M5 corrected denominators (sessions where a next bar exists)
    hn = s.hi_next_ret.dropna(); ln = s.lo_next_ret.dropna()
    print(f"M5 corrected: after-high down {int((hn<0).sum())}/{len(hn)}={(hn<0).mean():.3f} CI{bci(hn<0)}; after-low up {int((ln>0).sum())}/{len(ln)}={(ln>0).mean():.3f} CI{bci(ln>0)}; lens denominators 48 (sessions with the extreme in q35 counted as 'not reversed': high {int((s.hi_q==35).sum())}, low {int((s.lo_q==35).sum())})")
    newh = b[(b.new_hi == 1) & b.next_ret.notna()]; newl = b[(b.new_lo == 1) & b.next_ret.notna()]
    print(f"   base: next bar down after a FAILED new high {((newh[newh.is_hi_bar==0].next_ret)<0).mean():.3f} (n={int((newh.is_hi_bar==0).sum())}); up after failed new low {((newl[newl.is_lo_bar==0].next_ret)>0).mean():.3f}")
    # median next-bar return after the high: mechanical truncation check -> compare with next-bar return after a failed new high whose next bar did not make a new high
    nxt_new = b.groupby("date").new_hi.shift(-1).reindex(newh.index)
    fail_nonew = newh[(newh.is_hi_bar == 0) & (nxt_new == 0)]
    print(f"   next-bar after FAILED new high whose next bar made no new high: P(down) {(fail_nonew.next_ret<0).mean():.3f} (n={len(fail_nonew)}) median {fail_nonew.next_ret.median():.1f} bp  vs after the session high P(down) {(hn<0).mean():.3f} median {hn.median():.1f}")

    # ---- M9: does the sub-quarter add anything beyond bar-0 close location?
    lowhalf = s[s.bar0_close_loc < 0.5]; uphalf = s[s.bar0_close_loc >= 0.5]
    for nm, part in (("close lower half", lowhalf), ("close upper half", uphalf)):
        a1 = part[part.bar0_hi_sub == 0]; a0 = part[part.bar0_hi_sub > 0]
        print(f"M9 high | {nm}: sub==0 -> {int((a1.hi_k==0).sum())}/{len(a1)}; sub>0 -> {int((a0.hi_k==0).sum())}/{len(a0)}")
    for nm, part in (("close upper half", uphalf), ("close lower half", lowhalf)):
        a1 = part[part.bar0_lo_sub == 0]; a0 = part[part.bar0_lo_sub > 0]
        print(f"M9 low  | {nm}: sub==0 -> {int((a1.lo_k==0).sum())}/{len(a1)}; sub>0 -> {int((a0.lo_k==0).sum())}/{len(a0)}")
    # Fisher for close-loc alone in the window
    print(f"M9 close-loc alone (window): high {int((lowhalf.hi_k==0).sum())}/{len(lowhalf)} vs {int((uphalf.hi_k==0).sum())}/{len(uphalf)} Fisher p={fisher_exact([[int((lowhalf.hi_k==0).sum()), len(lowhalf)-int((lowhalf.hi_k==0).sum())],[int((uphalf.hi_k==0).sum()), len(uphalf)-int((uphalf.hi_k==0).sum())]])[1]:.4f}; low {int((uphalf.lo_k==0).sum())}/{len(uphalf)} vs {int((lowhalf.lo_k==0).sum())}/{len(lowhalf)} Fisher p={fisher_exact([[int((uphalf.lo_k==0).sum()), len(uphalf)-int((uphalf.lo_k==0).sum())],[int((lowhalf.lo_k==0).sum()), len(lowhalf)-int((lowhalf.lo_k==0).sum())]])[1]:.4f}")

    # ---- M10 population: Tokyo-open bar share by half, with p vs 1/9, and vs neighbours
    xx = x[x.n_bars == 9]
    for nm, part in (("pre", xx[xx.index < "2025-09-01"]), ("post", xx[xx.index >= "2025-09-01"])):
        kh = int(part.high_at_tokyo_open.sum()); kl = int(part.low_at_tokyo_open.sum()); n = len(part)
        rel = part.hi_k - part.tokyo_open_k; rell = part.lo_k - part.tokyo_open_k
        print(f"M10 {nm} n={n}: high at Tokyo-open bar {kh}/{n}={kh/n:.3f} p vs 1/9={bp(kh,n,1/9):.3f}; low {kl}/{n}={kl/n:.3f} p={bp(kl,n,1/9):.3f}; hi_k-tko (-2..+3) {[int((rel==d).sum()) for d in range(-2,4)]}; lo {[int((rell==d).sum()) for d in range(-2,4)]}; DST share {part.is_dst.mean():.2f}")
    # Tokyo-open bar vs the average of its two neighbours (local bump test), whole population
    rel = xx.hi_k - xx.tokyo_open_k; rell = xx.lo_k - xx.tokyo_open_k
    for nm, r in (("high", rel), ("low", rell)):
        at = int((r == 0).sum()); nb = int((r == -1).sum()) + int((r == 1).sum())
        print(f"M10 {nm}: Tokyo-open bar {at} vs mean of neighbours {nb/2:.1f}; binom p (at vs at+nb, p0=1/3) = {bp(at, at+nb, 1/3):.3f}")
    # 15m: window Tokyo-open quarter vs its neighbours (q_tko-1, q_tko+1)
    at = int(sum(r.hi_q == r.tko for r in s.itertuples())); nb = int(sum(abs(r.hi_q - r.tko) == 1 for r in s.itertuples()))
    atl = int(sum(r.lo_q == r.tko for r in s.itertuples())); nbl = int(sum(abs(r.lo_q - r.tko) == 1 for r in s.itertuples()))
    print(f"M10 15m window: Tokyo-open quarter high {at} vs neighbours {nb}; low {atl} vs {nbl}")
