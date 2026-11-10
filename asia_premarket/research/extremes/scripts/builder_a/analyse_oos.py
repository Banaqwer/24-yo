"""Post-hoc analysis of the walk-forward OOS file: bootstrap CIs, quantile coverage on not-done rows,
T6 rule sanity check, precision/recall of a high-confidence flag, LR coefficients of the final fit."""
import sys, os
sys.path.insert(0, './research/extremes')
import numpy as np, pandas as pd
import detector_intrasession as di

sym = sys.argv[1] if len(sys.argv) > 1 else 'NQ'
oos = pd.read_csv(os.path.join(di.HERE, f'oos_intrasession_{sym}.csv'), parse_dates=['date'])
d = di.build_dataset(sym)
oos = oos.merge(d[['date'] + di.FEATURES], on=['date', 'k'], how='left')
rng = np.random.default_rng(0)
sessions = oos['date'].unique()
h1 = oos[oos['date'] < di.H2_START]; h2 = oos[oos['date'] >= di.H2_START]


def skill(g, side, col=None):
    col = col or f'p_{side}_done'
    y = g[f'{side}_done'].values
    return 1 - di._brier(y, g[col]) / di._brier(y, g[f'kbase_{side}'])


def boot_ci(g, fn, n=1000):
    ds = g['date'].unique(); idx = {dd: i for i, dd in enumerate(ds)}
    grp = [g[g['date'] == dd] for dd in ds]
    vals = []
    for _ in range(n):
        pick = rng.integers(0, len(ds), len(ds))
        vals.append(fn(pd.concat([grp[i] for i in pick])))
    return np.percentile(vals, [5, 95])


print(f'=== {sym}: session-bootstrap 90% CI of pooled Brier skill vs k-only (1000 resamples) ===')
for side in ('high', 'low'):
    for nm, g in (('all', oos), ('H1', h1), ('H2', h2)):
        s = skill(g, side); ci = boot_ci(g, lambda gg: skill(gg, side), 400)
        sr = skill(g, side, f'p_{side}_raw')
        print(f'  {side:5s} {nm:3s}: skill_final {s:+.3f} CI [{ci[0]:+.3f}, {ci[1]:+.3f}]  (raw ensemble {sr:+.3f}; LR {skill(g, side, f"p_{side}_lr"):+.3f}; GB {skill(g, side, f"p_{side}_gb"):+.3f})')

print(f'\n=== {sym}: per-k 90% CI of skill (final) ===')
for side in ('high', 'low'):
    row = []
    for kk in range(8):
        g = oos[oos['k'] == kk]
        ci = boot_ci(g, lambda gg: skill(gg, side), 300)
        row.append(f'k{kk} {skill(g, side):+.2f} [{ci[0]:+.2f},{ci[1]:+.2f}]')
    print(f'  {side}: ' + ' | '.join(row))

print(f'\n=== {sym}: high-confidence flag p>=thr: precision (share of flagged rows where the extreme really was in) and recall ===')
for side in ('high', 'low'):
    y = oos[f'{side}_done']
    for thr in (0.8, 0.9, 0.95):
        f = oos[f'p_{side}_done'] >= thr
        prec = y[f].mean() if f.sum() else np.nan
        rec = f[y == 1].mean()
        per_k = ' '.join(f'{(oos[(oos.k==kk)][f"p_{side}_done"]>=thr).mean():.2f}' for kk in range(8))
        pk_prec = ' '.join(f'{y[(oos.k==kk)&f].mean():.2f}' if ((oos.k==kk)&f).sum()>=20 else ' -- ' for kk in range(8))
        print(f'  {side} p>={thr}: flagged {f.mean():.2%} of rows, precision {prec:.3f} (n={f.sum()}), recall {rec:.3f}; H1 prec {y[f & (oos.date<di.H2_START)].mean():.3f}, H2 {y[f & (oos.date>=di.H2_START)].mean():.3f}')
        print(f'      share flagged per k: {per_k} | precision per k: {pk_prec}')
    # the 'open' side: p<=thr
    for thr in (0.1, 0.2):
        f = oos[f'p_{side}_done'] <= thr
        print(f'  {side} p<={thr}: flagged {f.mean():.2%}, observed done-rate {y[f].mean():.3f} (n={f.sum()}); H1 {y[f & (oos.date<di.H2_START)].mean():.3f}, H2 {y[f & (oos.date>=di.H2_START)].mean():.3f}')

print(f'\n=== {sym}: T6 rule check in OOS rows (k=2..6) ===')
g = oos[(oos.k >= 2) & (oos.k <= 6)]
r = (g.bars_since_hi >= 2) & (g.pos_in_range < 0.35) & (g.run_rng_vs_med20 >= 1.0)
print(f'  HIGH rule: n={r.sum()}, precision {g.high_done[r].mean():.3f}; model mean p on those rows {g.p_high_done[r].mean():.3f}; base {g.high_done.mean():.3f}')
r0 = g.bars_since_hi == 0
print(f'  bars_since_hi==0: n={r0.sum()}, high_done rate {g.high_done[r0].mean():.3f}; model mean p {g.p_high_done[r0].mean():.3f}')
rl = (g.bars_since_lo >= 2) & (g.pos_in_range > 0.65) & (g.run_rng_vs_med20 >= 1.0)
print(f'  LOW rule: n={rl.sum()}, precision {g.low_done[rl].mean():.3f}; model mean p {g.p_low_done[rl].mean():.3f}')
# does the model add to the rule? among rule rows, split by model p
for nm, mask in (('HIGH rule rows', r),):
    gg = g[mask]
    for lo, hi in ((0, 0.9), (0.9, 0.97), (0.97, 1.01)):
        m = (gg.p_high_done >= lo) & (gg.p_high_done < hi)
        if m.sum(): print(f'    {nm} with p in [{lo},{hi}): n={m.sum()}, observed {gg.high_done[m].mean():.3f}')

print(f'\n=== {sym}: remaining-move quantiles on rows where the extreme is NOT yet in (ex-post subset) ===')
for side, ycol, sgn, done in (('up', 'remaining_up_bp', 1, 'high_done'), ('dn', 'remaining_down_bp', -1, 'low_done')):
    g = oos[oos[done] == 0]
    y = sgn * g[ycol]
    for q in ('p50', 'p80'):
        qm = sgn * g[f'rem_{side}_{q}']; qk = sgn * g[f'kq_{side}_{q}']
        print(f'  rem_{side} {q} | not done (n={len(g)}): coverage model {np.mean(y <= qm):.3f} vs k-only {np.mean(y <= qk):.3f}; '
              f'median actual {y.median():.1f} bp, median model q {qm.median():.1f}, k-only q {qk.median():.1f}')
    per_k = ' '.join(f'k{kk}:{np.mean(sgn*g[g.k==kk][ycol] <= sgn*g[g.k==kk][f"rem_{side}_p80"]):.2f}' for kk in range(8))
    print(f'    P80 coverage per k (not done): {per_k}')
    # the pinball comparison vs an ORACLE k-only baseline that knows the extreme is not in (training quantile on not-done rows is not stored; use OOS own quantile as the oracle)
    for q, qq in (('p50', .5), ('p80', .8)):
        qm = sgn * g[f'rem_{side}_{q}']
        oracle = g.groupby('k')[ycol].transform(lambda s: (sgn * s).quantile(qq))
        print(f'    pinball {q}: model {di._pinball(y, qm, qq):.2f} vs in-sample oracle per-k quantile of the not-done rows {di._pinball(y, oracle, qq):.2f}')
g = oos[oos.high_done == 1]
print(f'  rem_up | high done (n={len(g)}): remaining_up == dist_run_hi_bp mechanically; model P50 median abs error {np.median(np.abs(g.remaining_up_bp - g.rem_up_p50)):.1f} bp, coverage P80 {np.mean(g.remaining_up_bp <= g.rem_up_p80):.3f}')

print(f'\n=== {sym}: logistic coefficients (standardised design), fitted on ALL full sessions (for interpretation only) ===')
m = di.fit_models(d)
for t in di.TARGETS:
    coef = pd.Series(m[f'lr_{t}'][-1].coef_[0], index=m['design_cols'])
    top = coef.reindex(coef.abs().sort_values(ascending=False).index).head(14)
    print(f'  {t}: ' + ', '.join(f'{n} {v:+.2f}' for n, v in top.items()))

print(f'\n=== {sym}: calibrated vs raw by half (Brier) ===')
for side in ('high', 'low'):
    for nm, g in (('H1', h1), ('H2', h2)):
        y = g[f'{side}_done']
        print(f'  {side} {nm}: raw {di._brier(y, g[f"p_{side}_raw"]):.4f} final {di._brier(y, g[f"p_{side}_done"]):.4f} k-only {di._brier(y, g[f"kbase_{side}"]):.4f}')
print('\n=== calibration of the RAW ensemble (5 buckets) ===')
for side in ('high', 'low'):
    print(side); print(di.calibration_table(oos, side, f'p_{side}_raw').to_string())
