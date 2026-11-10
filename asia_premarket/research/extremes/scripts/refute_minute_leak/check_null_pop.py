"""(1) Monte-Carlo driftless random-walk null for the 15m claims (M1, M2, M6, M9).
   (2) Population (561 NQ sessions, hourly, DST-aware) test of a Tokyo-open-hour / China-open-hour bump (M10).
   (3) M5: next-bar reversal conditional on the next bar NOT exceeding the running extreme."""
import numpy as np, pandas as pd
from scipy.stats import binomtest, fisher_exact

ROOT = "."
LM = "research/extremes/scripts/lens_minute"
rng = np.random.default_rng(42)

# ---------- (1) Monte-Carlo null ----------
N, Q, SUB = 200_000, 36, 12   # sessions, quarters, sub-steps per quarter (price path sampled every 75 s)
steps = rng.standard_normal((N, Q * SUB)).cumsum(1)
path = steps.reshape(N, Q, SUB)
qhi = path.max(2); qlo = path.min(2)
hi_q = qhi.argmax(1); lo_q = qlo.argmin(1)
hi_k = hi_q // 4; lo_k = lo_q // 4
print("=== Monte-Carlo random-walk null (N=200k sessions, 36 quarters x 12 sub-steps)")
print(f"  P(high in q0)={np.mean(hi_q==0):.3f} P(q35)={np.mean(hi_q==35):.3f} edge={np.mean((hi_q==0)|(hi_q==35)):.3f} (uniform 0.028/0.056)")
print(f"  P(high in hour k): {np.round(np.bincount(hi_k, minlength=9)/N, 3).tolist()}  (pop hi_k%: 23.5 8.1 11.1 8.6 5.2 5.5 5.5 8.1 24.4)")
cum = np.cumsum(np.bincount(hi_k, minlength=9) / N)
print(f"  P(high already in | close of bar k): {np.round(cum,3).tolist()}  (pop: .23 .32 .43 .51 .56 .62 .67 .75 1.0)")
print(f"  P(q0 | k=0)={np.mean(hi_q[hi_k==0]==0):.3f}; P(q35 | k=8)={np.mean(hi_q[hi_k==8]==35):.3f}  (M2 uses 25% uniform-within-hour; observed 46-78% / 31-64%)")
print(f"  interior quarter mass: q1 {np.mean(hi_q==1):.3f} q2 {np.mean(hi_q==2):.3f} q17 {np.mean(hi_q==17):.3f} q34 {np.mean(hi_q==34):.3f}; "
      f"near-edge hours (q1-4,q31-34) share of interior extremes = {np.mean(((hi_q>=1)&(hi_q<=4))|((hi_q>=31)&(hi_q<=34)))/np.mean((hi_q>=1)&(hi_q<=34)):.3f} (uniform 8/34=0.235)")
# M6
dq = np.abs(hi_q - lo_q); dk = np.abs(hi_k - lo_k)
print(f"  M6 null: P(same hourly bar)={np.mean(dk==0):.3f} P(|dk|<=1)={np.mean(dk<=1):.3f} P(|dq|<=4)={np.mean(dq<=4):.3f} P(|dq|<=8)={np.mean(dq<=8):.3f} "
      f"median |dq|*15={np.median(dq)*15:.0f} min; P(>=6h)={np.mean(dq>=24):.3f}; edge sessions median |dq|*15={np.median(dq[(hi_q==0)|(lo_q==0)|(hi_q==35)|(lo_q==35)])*15:.0f} vs interior {np.median(dq[~((hi_q==0)|(lo_q==0)|(hi_q==35)|(lo_q==35))])*15:.0f}")
print(f"     (population hourly: same-bar 0.020, |dk|<=1 0.073, median |dk| 5 h; window 15m: median 345/330 min, P(>=6h) .48/.46, edge 412/420 vs interior 262/255)")
# M9: P(session high in bar 0 | sub-quarter of the first-hour high)
sub = qhi[:, :4].argmax(1)
for j in range(4):
    m = sub == j
    print(f"  M9 null: first-hour high in sub-quarter {j}: P(session high in bar 0)={np.mean(hi_k[m]==0):.3f} (n share {m.mean():.3f})   [observed NQ 41/30/17/11%, ES 32/45/12/10%]")
m0 = sub == 0; m1 = sub > 0
print(f"  M9 null contrast: set in q0 {np.mean(hi_k[m0]==0):.3f} vs later {np.mean(hi_k[m1]==0):.3f} (ratio {np.mean(hi_k[m0]==0)/np.mean(hi_k[m1]==0):.2f}; observed NQ 0.41 vs 0.19 = 2.2x, ES 0.32 vs 0.24)")
# f15 bar direction (M9 last part): first quarter down -> f15 high holds?
f15_dn = path[:, 0, -1] < 0
print(f"  M9 null: P(f15 high holds | f15 bar down)={np.mean(hi_q[f15_dn]==0):.3f} vs up {np.mean(hi_q[~f15_dn]==0):.3f}  [observed NQ .23 vs .08, ES .22 vs .04]")
# M4 close-away null: new running high bar closes in lower half -> P(hold)
run_hi = np.maximum.accumulate(qhi, 1)
is_new = np.zeros_like(qhi, bool); is_new[:, 0] = True; is_new[:, 1:] = qhi[:, 1:] > run_hi[:, :-1]
close = path[:, :, -1]; opn = np.concatenate([np.zeros((N, 1)), path[:, :-1, -1]], 1)
cl = (close - qlo) / np.maximum(qhi - qlo, 1e-9)
hold = (np.arange(Q)[None, :] == hi_q[:, None])
inner = is_new & (np.arange(Q)[None, :] > 0) & (np.arange(Q)[None, :] < 35)
away = cl < 0.5
print(f"  M4 null (interior new-high bars): P(hold | closes lower half)={np.mean(hold[inner & away]):.3f} vs upper half {np.mean(hold[inner & ~away]):.3f}  [observed NQ .25 vs .09 pooled]")
# M5 null: next bar down after a new running high -> P(hold)
nxt_dn = np.zeros_like(qhi, bool); nxt_dn[:, :-1] = close[:, 1:] < close[:, :-1]
has_next = np.arange(Q)[None, :] < 35
sel = is_new & has_next
print(f"  M5 null: P(hold | next bar down)={np.mean(hold[sel & nxt_dn]):.3f} vs next up {np.mean(hold[sel & ~nxt_dn]):.3f}; P(next down | session high)={np.mean(nxt_dn[hold & has_next]):.3f}  [observed NQ .23 vs .05; .80]")

# ---------- (2) population Tokyo-open-hour test, DST-aware ----------
print("\n=== M10 at hourly resolution on the 561-session NQ population (DST-aware): is the Tokyo-open hour / China-open hour special?")
null_k = np.bincount(hi_k, minlength=9) / N   # MC arcsine null per hour
for sym in ("NQ", "ES"):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True)
    bad = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-15", "2025-09-16"], "ES": ["2025-12-15", "2025-12-16"]}[sym]
    x = x.drop(pd.to_datetime(bad), errors="ignore"); full = x[x.n_bars == 9]
    for name, col in (("tokyo_open_k", "tokyo_open_k"), ("china_open_k", "china_open_k")):
        for side in ("hi_k", "lo_k"):
            hit = (full[side] == full[col]).astype(int)
            p0_arc = np.mean([null_k[k] for k in full[col]]); p0_uni = 1 / 9
            k = int(hit.sum()); n = len(hit)
            a = full[full.index < "2025-09-01"]; b = full[full.index >= "2025-09-01"]
            ha = int((a[side] == a[col]).sum()); hb = int((b[side] == b[col]).sum())
            print(f"  {sym} {side}=={name}: {k}/{n}={k/n:.3f}; arcsine null {p0_arc:.3f} (p={binomtest(k,n,p0_arc).pvalue:.4f}, ratio {k/n/p0_arc:.2f}x); uniform 1/9 (p={binomtest(k,n,p0_uni).pvalue:.3f}); "
                  f"halves {ha}/{len(a)}={ha/len(a):.3f} | {hb}/{len(b)}={hb/len(b):.3f}; by DST: EDT {np.mean((full[full.is_dst==1][side]==full[full.is_dst==1][col])):.3f} EST {np.mean((full[full.is_dst==0][side]==full[full.is_dst==0][col])):.3f}")
    # whole hourly histogram vs arcsine null, observed/expected ratio per bar (NQ only, by DST)
    for dst in (1, 0):
        f = full[full.is_dst == dst]
        obs_h = np.bincount(f.hi_k, minlength=9) / len(f); obs_l = np.bincount(f.lo_k, minlength=9) / len(f)
        print(f"  {sym} {'EDT' if dst else 'EST'} n={len(f)}: obs/arcsine ratio by hour k (high): {np.round(obs_h/null_k,2).tolist()} | (low): {np.round(obs_l/null_k,2).tolist()}  [Tokyo open k={2 if dst else 1}, China open k={3 if dst else 2}]")

# ---------- (3) M5 cleaner comparison ----------
print("\n=== M5: next-bar direction given the next bar did NOT exceed the running extreme (incremental over bars_since>=1)")
for sym in ("NQ", "ES"):
    s = pd.read_csv(f"{LM}/{sym}_q15_sessions.csv", index_col=0, parse_dates=True); s = s[s.n_q == 36].sort_index()
    b = pd.read_csv(f"{LM}/{sym}_q15_bars.csv", parse_dates=["date"]); b = b[b.date.isin(s.index)].sort_values(["date", "q"]).reset_index(drop=True)
    g = b.groupby("date")
    b["next_ret"] = g.ret_bp.shift(-1); b["next_high"] = g.high.shift(-1); b["next_low"] = g.low.shift(-1)
    for side, flag, since, sgn in (("high", "is_hi_bar", "q_since_hi", -1), ("low", "is_lo_bar", "q_since_lo", 1)):
        new = b[(b[since] == 0) & b.next_ret.notna()]
        nx = new[new.next_high <= new.high] if side == "high" else new[new.next_low >= new.low]
        rev = nx[sgn * nx.next_ret > 0]; nrev = nx[sgn * nx.next_ret <= 0]
        p = fisher_exact([[int(rev[flag].sum()), len(rev) - int(rev[flag].sum())], [int(nrev[flag].sum()), len(nrev) - int(nrev[flag].sum())]])[1]
        print(f"  {sym} {side}: next bar did not exceed: n={len(nx)} P(hold)={nx[flag].mean():.3f}; | next reverses {int(rev[flag].sum())}/{len(rev)}={rev[flag].mean():.3f} vs | next continues-but-no-new-extreme {int(nrev[flag].sum())}/{len(nrev)}={nrev[flag].mean():.3f} Fisher p={p:.3f}")
