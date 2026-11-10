"""Random-walk OHLC null for the 'mechanical' claims:
M5  P(bar after the session high closes down) - the max-selection effect alone produces a high rate.
M6  |hi - lo| time distribution and P(<=60 min) for a driftless walk with 36 x 15m bars built from 1-minute steps.
M1  share of the extreme in the first / last 15m bar under a pure random walk (edge effect of the max of a walk).
Also a version with fat tails (t5 innovations) and a version with a volatility profile matching the window's quarter medians."""
import numpy as np, pandas as pd
from common import *

L = Log(f"{OUT}/sim_null_log.txt")
NQ_PROFILE = pd.read_csv(f"{LENS}/NQ_quarter_volume_profile.csv")
prof = NQ_PROFILE.rng_med.values / NQ_PROFILE.rng_med.values.mean()   # 36 quarter range multipliers


def simulate(nsess=20000, nmin=15, nq=36, tails="normal", profile=None, seed=1):
    r = np.random.default_rng(seed)
    if tails == "normal": z = r.standard_normal((nsess, nq, nmin))
    else: z = r.standard_t(4, (nsess, nq, nmin)) / np.sqrt(2)
    if profile is not None: z = z * profile[None, :, None]
    path = np.cumsum(z.reshape(nsess, -1), axis=1).reshape(nsess, nq, nmin)
    o = np.concatenate([np.zeros((nsess, 1)), path[:, :-1, -1]], axis=1)  # open = prior close (first open = 0)
    c = path[:, :, -1]; h = np.maximum(path.max(axis=2), o); lo = np.minimum(path.min(axis=2), o)
    hi_q = h.argmax(axis=1); lo_q = lo.argmin(axis=1)
    # next bar after the high / low
    nxt_h = np.where(hi_q + 1 < nq, (c - o)[np.arange(nsess), np.minimum(hi_q + 1, nq - 1)], np.nan)
    nxt_l = np.where(lo_q + 1 < nq, (c - o)[np.arange(nsess), np.minimum(lo_q + 1, nq - 1)], np.nan)
    # next bar after a FAILED new running high: new running high at q (h[q] > max h[:q]) and not the session max
    runmax = np.maximum.accumulate(h, axis=1); prev = np.concatenate([np.full((nsess, 1), -np.inf), runmax[:, :-1]], axis=1)
    newhi = h > prev; fail = newhi & (np.arange(nq)[None, :] != hi_q[:, None]) & (np.arange(nq)[None, :] < nq - 1)
    ret = c - o; nxt = np.concatenate([ret[:, 1:], np.full((nsess, 1), np.nan)], axis=1)
    fail_next = nxt[fail]
    dq = np.abs(hi_q - lo_q)
    # close location of the new-running-high bar vs hold
    cl = (c - lo) / np.where(h - lo > 0, h - lo, np.nan)
    hold = (np.arange(nq)[None, :] == hi_q[:, None])
    interior = newhi & (np.arange(nq)[None, :] > 0) & (np.arange(nq)[None, :] < nq - 1)
    away = cl < 0.5
    p_hold_away = hold[interior & away].mean(); p_hold_toward = hold[interior & ~away].mean()
    return dict(
        P_after_high_down=np.nanmean(nxt_h < 0), P_after_low_up=np.nanmean(nxt_l > 0), med_ret_after_high_sd=np.nanmedian(nxt_h) / np.sqrt(nmin),
        P_after_failed_newhigh_down=np.nanmean(fail_next < 0),
        P_hi_q0=(hi_q == 0).mean(), P_hi_q35=(hi_q == nq - 1).mean(), P_lo_q0=(lo_q == 0).mean(), P_lo_q35=(lo_q == nq - 1).mean(),
        P_edge_hi=((hi_q == 0) | (hi_q == nq - 1)).mean(),
        P_dq_le4=(dq <= 4).mean(), P_dq_le8=(dq <= 8).mean(), P_dq_ge24=(dq >= 24).mean(), med_dq_min=np.median(dq) * 15, same_q=(dq == 0).mean(),
        P_hold_closeaway=p_hold_away, P_hold_closetoward=p_hold_toward, P_hold_newhigh_interior=hold[interior].mean(),
        k0_share_in_q0=(hi_q[hi_q < 4] == 0).mean(), k8_share_in_q35=(hi_q[hi_q >= 32] == nq - 1).mean(),
    )


for name, kw in [("driftless normal, flat vol", dict()), ("t4 fat tails, flat vol", dict(tails="t")), ("normal, window range profile", dict(profile=prof)), ("t4, window range profile", dict(tails="t", profile=prof))]:
    res = simulate(**kw)
    L(f"\n=== null: {name}")
    for k, v in res.items(): L(f"  {k:28s} {v:.3f}")
L.close()
