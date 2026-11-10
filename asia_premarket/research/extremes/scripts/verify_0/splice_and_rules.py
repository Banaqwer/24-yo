import sys, numpy as np, pandas as pd
sys.path.insert(0, "research/extremes/scripts/verify_0/run")
import detector_intrasession as det
V = "research/extremes/scripts/verify_0"
R = "./research/extremes"
def brier(y, p): return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))
for sym in ["NQ", "ES"]:
    x = pd.read_csv(f"{R}/{sym}_extremes.csv", index_col="date", parse_dates=True)
    oos = pd.read_csv(f"{V}/orig/oos_intrasession_{sym}.csv", parse_dates=["date"])
    print(f"\n=== {sym}: suspected unexcluded roll-artefact sessions ===")
    for dstr in ["2025-09-16", "2025-09-17", "2025-12-15", "2025-12-18"]:
        if pd.Timestamp(dstr) in x.index:
            r = x.loc[pd.Timestamp(dstr)]
            ino = (oos["date"] == pd.Timestamp(dstr)).sum()
            print(f"  {dstr}: hi_k {int(r.hi_k)} lo_k {int(r.lo_k)} hi_bp {r.hi_bp:+.0f} lo_bp {r.lo_bp:+.0f} rng_bp {r.rng_bp:.0f} n_bars {int(r.n_bars)} | rows in OOS: {ino}")
        else:
            print(f"  {dstr}: not in extremes index")
    bad = oos["date"].isin(pd.to_datetime(["2025-09-16", "2025-09-17"]))
    for s in ["high", "low"]:
        t = f"{s}_done"
        print(f"  {t}: pooled Brier final all {brier(oos[t], oos[f'p_{s}_done']):.4f} vs excl. those sessions {brier(oos[~bad][t], oos[~bad][f'p_{s}_done']):.4f}; k-only {brier(oos[t], oos[f'kbase_{s}']):.4f} vs {brier(oos[~bad][t], oos[~bad][f'kbase_{s}']):.4f}")
    # T6 rule check on the OOS rows
    d = det.build_dataset(sym)[["date", "k", "bars_since_hi", "bars_since_lo", "pos_in_range", "run_rng_vs_med20"]]
    m = oos.merge(d, on=["date", "k"], how="left")
    r6 = m[(m.k >= 2) & (m.k <= 6) & (m.bars_since_hi >= 2) & (m.pos_in_range < .35) & (m.run_rng_vs_med20 >= 1)]
    print(f"  T6 high rule k2..6: n={len(r6)} precision {r6.high_done.mean():.3f} model mean p {r6.p_high_done.mean():.3f}; "
          f"p<.90 n={(r6.p_high_done<.9).sum()} obs {r6[r6.p_high_done<.9].high_done.mean():.3f}; .90-.97 n={((r6.p_high_done>=.9)&(r6.p_high_done<.97)).sum()} obs {r6[(r6.p_high_done>=.9)&(r6.p_high_done<.97)].high_done.mean():.3f}; >=.97 n={(r6.p_high_done>=.97).sum()} obs {r6[r6.p_high_done>=.97].high_done.mean():.3f}")
    r6l = m[(m.k >= 2) & (m.k <= 6) & (m.bars_since_lo >= 2) & (m.pos_in_range > .65) & (m.run_rng_vs_med20 >= 1)]
    print(f"  LOW rule k2..6 (bars_since_lo>=2 & pos>.65 & rng>=1): n={len(r6l)} precision {r6l.low_done.mean():.3f} model mean p {r6l.p_low_done.mean():.3f}")
    b0 = m[m.bars_since_hi == 0]
    print(f"  bars_since_hi==0: n={len(b0)} done-rate {b0.high_done.mean():.3f} model mean p {b0.p_high_done.mean():.3f}")
    # bars_since_hi >= 2 by k: observed vs model mean (the base-rate table in the brief)
    print("  P(high in | bars_since_hi>=2) OOS by k=2..7: " + " ".join(f"{m[(m.k==kk)&(m.bars_since_hi>=2)].high_done.mean():.2f}" for kk in range(2, 8)))
    # feature-importance sanity: GB-only vs LR-only skill at k=0 (first-bar statistics)
    k0 = oos[oos.k == 0]
    print(f"  k=0 Brier: k-only {brier(k0.high_done, k0.kbase_high):.4f} LR {brier(k0.high_done, k0.p_high_lr):.4f} GB {brier(k0.high_done, k0.p_high_gb):.4f}")

# 18:00 bars with zero volume and the 15m check for 2026-11-05
D = "./data"
for sym in ["NQ", "ES"]:
    h = pd.read_csv(f"{D}/{sym}_1h.csv"); t = h.columns[0]
    h[t] = pd.to_datetime(h[t], utc=True).dt.tz_convert("America/New_York"); h = h.set_index(t).sort_index()
    b18 = h[h.index.hour == 18]
    print(f"\n{sym}: 18:00 bars {len(b18)}, with Volume==0: {(b18.Volume==0).sum()} ({(b18.Volume==0).mean():.1%}); median range bp zero-vol {((b18[b18.Volume==0].High-b18[b18.Volume==0].Low)/b18[b18.Volume==0].Close*1e4).median():.1f} vs nonzero {((b18[b18.Volume>0].High-b18[b18.Volume>0].Low)/b18[b18.Volume>0].Close*1e4).median():.1f}")
    m15 = pd.read_csv(f"{D}/{sym}_15m.csv"); t15 = m15.columns[0]
    m15[t15] = pd.to_datetime(m15[t15], utc=True).dt.tz_convert("America/New_York"); m15 = m15.set_index(t15).sort_index()
    for day in ["2026-11-05"]:
        w = m15.loc[f"{day} 17:00":f"{day} 19:15"][["Open", "High", "Low", "Close", "Volume"]]
        print(f"{sym} 15m bars {day} 17:00-19:15:"); print(w.to_string())
        print(f"{sym} hourly 17:00-19:00:"); print(h.loc[f"{day} 17:00":f"{day} 19:00"][["Open", "High", "Low", "Close", "Volume"]].to_string())
