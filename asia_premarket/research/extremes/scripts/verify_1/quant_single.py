import os, sys, numpy as np, pandas as pd
RUN="research/extremes/scripts/verify_1/run"; sys.path.insert(0,RUN)
import detector_preasia as dp
def pinball(pred,y,q):
    d=np.asarray(y)-np.asarray(pred); return float(np.mean(np.maximum(q*d,(q-1)*d)))
for sym in ["NQ","ES"]:
    x=dp.load_extremes(sym); F=dp.make_features(x)
    o=pd.read_csv(f"{RUN}/oos_preasia_{sym}.csv",index_col="date",parse_dates=True); h1=np.asarray(o.index<dp.H1_END)
    print(f"\n{sym} rng_bp: single-feature linear quantile regression, pinball skill vs expanding unconditional quantile (q20/q50/q80), H1/H2 for q50")
    for feats in [["asia_rng_med20_bp"],["asia_rng_prev_bp"],["rth_range_bp"],["vix"],["abs_post_bp"],["lsd_high","lsd_low"],["rth_range_bp","asia_rng_med20_bp"],["rth_range_bp","asia_rng_med20_bp","vix","asia_rng_prev_bp"],dp.FEATURES_QUANT]:
        oq=dp.walk_forward_quantile(F[feats],x["rng_bp"])
        sk=[1-pinball(oq[f"q{int(q*100)}"],oq.y,q)/pinball(oq[f"base_q{int(q*100)}"],oq.y,q) for q in dp.QUANTILES]
        s50h=[1-pinball(oq.q50[m],oq.y[m],.5)/pinball(oq.base_q50[m],oq.y[m],.5) for m in (h1,~h1)]
        print(f"  {str(feats)[:70]:70s}: {sk[0]:+.3f} {sk[1]:+.3f} {sk[2]:+.3f} | q50 H1 {s50h[0]:+.3f} H2 {s50h[1]:+.3f}")
    print(f"{sym} hi_bp q80 single-feature:")
    for feats in [["asia_rng_med20_bp"],["rth_range_bp"],["lsd_high"],["clv"],["rth_range_bp","lsd_high"],dp.FEATURES_QUANT]:
        oq=dp.walk_forward_quantile(F[feats],x["hi_bp"],qs=(0.8,))
        print(f"  {str(feats)[:70]:70s}: q80 {1-pinball(oq.q80,oq.y,.8)/pinball(oq.base_q80,oq.y,.8):+.3f}")
