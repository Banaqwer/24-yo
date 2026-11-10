"""Variant: add the other contract's state at the same (date, k) as confirming features (T13).
Classification only (quantile models switched off to save CPU). Same walk-forward protocol."""
import sys, os
sys.path.insert(0, './research/extremes')
import numpy as np, pandas as pd
import detector_intrasession as di

OUT = 'research/extremes/scripts/builder_a'
XCOLS = ['x_pos_in_range', 'x_bars_since_hi', 'x_bars_since_lo']

_orig_build = di.build_dataset
_orig_design = di.lr_design


def build_cross(sym, x=None, p=None, full_sessions_only=True):
    d = _orig_build(sym, x, p, full_sessions_only)
    other = 'ES' if sym == 'NQ' else 'NQ'
    xo, po = di.load_tables(other)
    po = po[~po['date'].isin(pd.to_datetime(di.SPLICE_DATES.get(other, [])))]
    po = po[['date', 'k', 'pos_in_range', 'bars_since_hi', 'bars_since_lo']].rename(
        columns={'pos_in_range': 'x_pos_in_range', 'bars_since_hi': 'x_bars_since_hi', 'bars_since_lo': 'x_bars_since_lo'})
    d = d.merge(po, on=['date', 'k'], how='left')
    return d.sort_values(['date', 'k']).reset_index(drop=True)


def design_cross(X):
    D = _orig_design(X)
    D['x_pos_in_range'] = X['x_pos_in_range'].fillna(X['pos_in_range'])
    D['x_bars_since_hi==0'] = (X['x_bars_since_hi'].fillna(X['bars_since_hi']) == 0).astype(float)
    D['x_bars_since_lo==0'] = (X['x_bars_since_lo'].fillna(X['bars_since_lo']) == 0).astype(float)
    D['x_log1p_bars_since_hi'] = np.log1p(X['x_bars_since_hi'].fillna(X['bars_since_hi']))
    D['x_log1p_bars_since_lo'] = np.log1p(X['x_bars_since_lo'].fillna(X['bars_since_lo']))
    return D


di.build_dataset = build_cross
di.lr_design = design_cross
di.FEATURES = di.FEATURES + XCOLS
di.QUANTILES = []

for sym in sys.argv[1:] or ['NQ', 'ES']:
    oos = di.train_walk_forward(sym, verbose=False)
    oos.to_csv(os.path.join(OUT, f'oos_cross_{sym}.csv'), index=False)
    pd.set_option('display.width', 220); pd.set_option('display.float_format', lambda v: f'{v:.3f}')
    h1 = oos[oos['date'] < di.H2_START]; h2 = oos[oos['date'] >= di.H2_START]
    for side in ('high', 'low'):
        print(f'=== {sym} CROSS variant {side}_done ===')
        print(di.classification_table(oos, side)[['n', 'rate', 'brier_konly', 'brier_ens_raw', 'brier_final', 'auc_final', 'skill_vs_konly']].to_string())
        for nm, g in (('H1', h1), ('H2', h2)):
            t = di.classification_table(g, side).loc['pooled']
            print(f'  {nm}: brier_konly {t.brier_konly:.4f} final {t.brier_final:.4f} auc {t.auc_final:.3f} skill {t.skill_vs_konly:+.3f}')
