import sys, json, time
sys.path.insert(0, './research/extremes')
import pandas as pd
import detector_intrasession as di

t0 = time.time()
for sym, date in (('NQ', '2026-11-06'), ('ES', '2026-11-05')):
    x, p = di.load_tables(sym)
    xr = x.loc[pd.Timestamp(date)]
    print(f'\n=== {sym} {date}: hi_k={int(xr.hi_k)} lo_k={int(xr.lo_k)} hi_bp={xr.hi_bp:.1f} lo_bp={xr.lo_bp:.1f} sunday={int(xr.sunday_open)} ===')
    print(f"{'k':>2} {'hET':>3} {'pHi':>5} {'pLo':>5} {'kHi':>5} {'kLo':>5} | {'up50':>6} {'up80':>6} {'dn50':>6} {'dn80':>6} | {'up80o':>6} {'dn80o':>6} | actual rem_up / rem_dn | top high contribution")
    for k in range(8):
        r = di.predict_now(sym, date, k)
        pr = p[(p.date == pd.Timestamp(date)) & (p.k == k)].iloc[0]
        print(f"{k:>2} {r['hour_et']:>3} {r['p_high_done']:5.2f} {r['p_low_done']:5.2f} {r['k_only_high']:5.2f} {r['k_only_low']:5.2f} | "
              f"{r['rem_up_p50']:6.1f} {r['rem_up_p80']:6.1f} {r['rem_dn_p50']:6.1f} {r['rem_dn_p80']:6.1f} | "
              f"{r['rem_up_p80_if_open']:6.1f} {r['rem_dn_p80_if_open']:6.1f} | {pr.remaining_up_bp:6.1f} {pr.remaining_down_bp:6.1f}  done={int(pr.high_done)}/{int(pr.low_done)} | "
              f"{r['top_contributions_high'][:3]}")
    print('calibrated', r['calibrated'], 'cal sessions', r['calibration_sessions'], 'train sessions', r['n_train_sessions'])
print(f'\nelapsed {time.time()-t0:.1f}s')
r = di.predict_now('NQ', '2026-11-06', 3)
print(json.dumps({k: v for k, v in r.items() if k != 'features'}, indent=1, default=str)[:3000])
