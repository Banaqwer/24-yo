# OTE Sensitivity / Ablation Study

All numbers are total net R (sum of R-multiples after costs) over the full history, default rules unless stated. Positive = profitable. Trade counts in brackets.

## 1. Fill assumption on bars that touch both stop and target

| market          |   trades |   sl_first_R |   tp_first_R |   ambiguous_bars |
|:----------------|---------:|-------------:|-------------:|-----------------:|
| NQ=F hourly     |      118 |        -18.8 |        -18.8 |                0 |
| ES=F hourly     |      123 |        -18.7 |        -18.7 |                0 |
| GC=F hourly     |      133 |         -5.7 |         -5.7 |                0 |
| CL=F hourly     |      152 |        -42.5 |        -42.5 |                0 |
| EURUSD=X hourly |      173 |         -5.7 |         -5.7 |                0 |
| GBPUSD=X hourly |      180 |        -25   |        -25   |                0 |
| USDJPY=X hourly |      165 |        -18.4 |        -15.1 |                1 |
| BTC-USD hourly  |      199 |         10   |         10   |                0 |
| ETH-USD hourly  |      186 |        -38.5 |        -38.5 |                0 |
| SPY daily       |       41 |          8.9 |          8.9 |                0 |
| QQQ daily       |       42 |          2.6 |          2.6 |                0 |
| GLD daily       |       48 |        -10.2 |        -10.2 |                0 |
| TLT daily       |       45 |         -2.8 |         -2.8 |                0 |
| NVDA daily      |       41 |         -1.9 |         -1.9 |                0 |
| AAPL daily      |       38 |         -8   |         -8   |                0 |
| BTC-USD daily   |       33 |          1.5 |          1.5 |                0 |

Across all markets: stop-first -173.2 R, target-first -169.9 R (1 ambiguous bars out of 1717 trades).

## 2. Full-sample parameter grid (144 sets, in-sample, best case)

| market          |   sets |   positive_pct |   median_R |   best_R |   best_trades |   best_win |   worst_R |
|:----------------|-------:|---------------:|-----------:|---------:|--------------:|-----------:|----------:|
| NQ=F hourly     |    144 |             11 |      -11.5 |      6.2 |            36 |         39 |     -42.3 |
| ES=F hourly     |    144 |              0 |      -14.9 |     -1.9 |            51 |         22 |     -36.3 |
| GC=F hourly     |    144 |             46 |       -0.7 |     28   |           154 |         28 |     -31.8 |
| CL=F hourly     |    144 |              1 |      -18.7 |      0.7 |           143 |         30 |     -45   |
| EURUSD=X hourly |    144 |             17 |       -8.3 |     26.3 |           136 |         29 |     -19.7 |
| GBPUSD=X hourly |    144 |              3 |      -12.7 |      3.3 |           127 |         34 |     -36.6 |
| USDJPY=X hourly |    144 |             38 |       -3.3 |     21.7 |           171 |         27 |     -27.5 |
| BTC-USD hourly  |    144 |             35 |       -4.6 |     18.2 |           179 |         32 |     -60.5 |
| ETH-USD hourly  |    144 |             22 |      -13.8 |     13   |            39 |         36 |     -57.9 |
| SPY daily       |    108 |             93 |        6.2 |     24.2 |            45 |         42 |      -2.3 |
| QQQ daily       |    128 |             42 |       -0.8 |     17.2 |            53 |         38 |     -10.1 |
| GLD daily       |    102 |             40 |       -1.6 |     13.5 |            40 |         32 |     -19.7 |
| TLT daily       |    108 |             52 |        0.4 |     22.5 |            50 |         34 |      -8.9 |
| NVDA daily      |    122 |             34 |       -2   |     14.7 |            45 |         29 |      -9.3 |
| AAPL daily      |     90 |              0 |       -7.5 |     -0.4 |            11 |         36 |     -17   |
| BTC-USD daily   |     90 |             38 |       -2.1 |      6.1 |            45 |         24 |     -11.4 |

Best parameter set per market (in-sample, so optimistic):

- NQ=F hourly: {'swing_len': 4, 'confirm_mode': 'consolidation', 'eval_tp_index': 1, 'min_leg_atr': 1.5, 'require_sweep': True} -> +6.2 R, 36 trades, win 39%
- ES=F hourly: {'swing_len': 5, 'confirm_mode': 'touch', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': True} -> -1.9 R, 51 trades, win 22%
- GC=F hourly: {'swing_len': 4, 'confirm_mode': 'touch', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': False} -> +28.0 R, 154 trades, win 28%
- CL=F hourly: {'swing_len': 4, 'confirm_mode': 'consolidation', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': False} -> +0.7 R, 143 trades, win 30%
- EURUSD=X hourly: {'swing_len': 10, 'confirm_mode': 'touch', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': False} -> +26.3 R, 136 trades, win 29%
- GBPUSD=X hourly: {'swing_len': 10, 'confirm_mode': 'reclaim', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': False} -> +3.3 R, 127 trades, win 34%
- USDJPY=X hourly: {'swing_len': 5, 'confirm_mode': 'touch', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': False} -> +21.7 R, 171 trades, win 27%
- BTC-USD hourly: {'swing_len': 5, 'confirm_mode': 'consolidation', 'eval_tp_index': 2, 'min_leg_atr': 2.5, 'require_sweep': False} -> +18.2 R, 179 trades, win 32%
- ETH-USD hourly: {'swing_len': 10, 'confirm_mode': 'touch', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': True} -> +13.0 R, 39 trades, win 36%
- SPY daily: {'swing_len': 4, 'confirm_mode': 'touch', 'eval_tp_index': 1, 'min_leg_atr': 1.5, 'require_sweep': False} -> +24.2 R, 45 trades, win 42%
- QQQ daily: {'swing_len': 4, 'confirm_mode': 'touch', 'eval_tp_index': 1, 'min_leg_atr': 1.5, 'require_sweep': False} -> +17.2 R, 53 trades, win 38%
- GLD daily: {'swing_len': 7, 'confirm_mode': 'touch', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': False} -> +13.5 R, 40 trades, win 32%
- TLT daily: {'swing_len': 4, 'confirm_mode': 'touch', 'eval_tp_index': 2, 'min_leg_atr': 2.5, 'require_sweep': False} -> +22.5 R, 50 trades, win 34%
- NVDA daily: {'swing_len': 5, 'confirm_mode': 'touch', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': False} -> +14.7 R, 45 trades, win 29%
- AAPL daily: {'swing_len': 5, 'confirm_mode': 'touch', 'eval_tp_index': 0, 'min_leg_atr': 1.5, 'require_sweep': True} -> -0.4 R, 11 trades, win 36%
- BTC-USD daily: {'swing_len': 4, 'confirm_mode': 'touch', 'eval_tp_index': 2, 'min_leg_atr': 1.5, 'require_sweep': False} -> +6.1 R, 45 trades, win 24%

## 3. One rule switched at a time

| market          | default     | no HTF bias   | no structure break   | no consolidation (touch 0.705)   | reclaim close instead   | require sweep   | scalp to range extreme (tp0)   | target -0.62 (tp2)   | symmetrical -1.0 (tp3)   | range bias (discount/premium)   |
|:----------------|:------------|:--------------|:---------------------|:---------------------------------|:------------------------|:----------------|:-------------------------------|:---------------------|:-------------------------|:--------------------------------|
| NQ=F hourly     | -18.8 (118) | -25.0 (167)   | -26.2 (161)          | -27.1 (142)                      | -15.8 (110)             | -11.0 (26)      | -32.4 (123)                    | -19.3 (111)          | -9.8 (108)               | -11.6 (45)                      |
| ES=F hourly     | -18.7 (123) | -17.6 (164)   | -26.8 (162)          | -26.9 (140)                      | -21.4 (114)             | -5.4 (43)       | -28.9 (135)                    | -26.5 (113)          | -21.8 (105)              | -2.2 (33)                       |
| GC=F hourly     | -5.7 (133)  | -2.3 (194)    | -2.8 (196)           | +5.9 (143)                       | -3.2 (124)              | -2.3 (33)       | -6.1 (147)                     | -1.3 (124)           | +10.9 (111)              | +12.2 (42)                      |
| CL=F hourly     | -42.5 (152) | -59.3 (199)   | -35.4 (195)          | -30.0 (161)                      | -21.8 (134)             | -15.8 (46)      | -41.2 (162)                    | -28.1 (140)          | -22.1 (131)              | -8.5 (42)                       |
| EURUSD=X hourly | -5.7 (173)  | -10.1 (245)   | -16.1 (230)          | -2.7 (189)                       | -13.5 (162)             | -15.3 (57)      | -6.0 (182)                     | -2.9 (158)           | +14.6 (149)              | -1.3 (61)                       |
| GBPUSD=X hourly | -25.0 (180) | -18.8 (255)   | -15.6 (244)          | -9.0 (204)                       | -10.3 (164)             | -17.9 (62)      | -35.3 (189)                    | -30.2 (167)          | -13.0 (160)              | -16.5 (67)                      |
| USDJPY=X hourly | -18.4 (165) | -27.8 (250)   | -47.9 (249)          | +6.7 (182)                       | -13.1 (156)             | -3.9 (52)       | -24.9 (184)                    | -2.9 (153)           | -14.2 (142)              | -26.3 (68)                      |
| BTC-USD hourly  | +10.0 (199) | -1.6 (285)    | -32.9 (261)          | -9.0 (220)                       | -0.7 (178)              | -11.1 (65)      | -19.4 (215)                    | +16.6 (183)          | +34.6 (172)              | +11.4 (76)                      |
| ETH-USD hourly  | -38.5 (186) | -20.9 (261)   | -41.3 (273)          | -51.2 (209)                      | -32.0 (167)             | -4.1 (60)       | -53.6 (198)                    | -31.1 (177)          | -25.4 (167)              | +0.1 (71)                       |
| SPY daily       | +8.9 (41)   | -3.9 (61)     | +3.4 (48)            | +20.5 (42)                       | +7.4 (38)               | +4.6 (15)       | -1.7 (42)                      | +18.3 (38)           | +24.4 (35)               | -9.8 (17)                       |
| QQQ daily       | +2.6 (42)   | +0.1 (63)     | -0.1 (51)            | +13.0 (48)                       | +2.6 (41)               | +4.8 (10)       | -3.3 (43)                      | -4.0 (39)            | -5.6 (35)                | +6.5 (18)                       |
| GLD daily       | -10.2 (48)  | -7.8 (68)     | -5.9 (64)            | -12.8 (53)                       | -7.1 (42)               | -1.9 (11)       | -8.1 (52)                      | -3.0 (45)            | +1.8 (45)                | +1.7 (20)                       |
| TLT daily       | -2.8 (45)   | -5.2 (67)     | +1.1 (60)            | +0.2 (49)                        | -3.5 (44)               | +1.0 (11)       | -7.0 (47)                      | +2.2 (42)            | +3.5 (36)                | -4.7 (20)                       |
| NVDA daily      | -1.9 (41)   | -9.9 (60)     | +5.9 (53)            | +8.0 (47)                        | +2.5 (43)               | -5.4 (14)       | -4.8 (44)                      | +2.7 (40)            | -7.4 (34)                | -4.4 (9)                        |
| AAPL daily      | -8.0 (38)   | -15.8 (64)    | -6.8 (49)            | -15.8 (45)                       | -7.5 (36)               | -3.2 (10)       | -11.1 (40)                     | -7.6 (36)            | -3.8 (35)                | -9.6 (21)                       |
| BTC-USD daily   | +1.5 (33)   | +4.8 (57)     | -14.9 (66)           | -6.8 (38)                        | +3.4 (30)               | -1.5 (4)        | -0.2 (35)                      | +3.7 (33)            | +10.7 (31)               | +2.7 (23)                       |

Sum over all markets:
- default: -173.2 R
- no HTF bias: -221.1 R
- no structure break: -262.3 R
- no consolidation (touch 0.705): -137.0 R
- reclaim close instead: -134.0 R
- require sweep: -88.4 R
- scalp to range extreme (tp0): -284.0 R
- target -0.62 (tp2): -113.4 R
- symmetrical -1.0 (tp3): -22.6 R
- range bias (discount/premium): -60.3 R

## 4. Session filter, index futures (hourly bars, exchange time)

| market      | session_ET   |   trades |   total_R |   win_pct |
|:------------|:-------------|---------:|----------:|----------:|
| NQ=F hourly | 08:00-11:00  |       72 |      -7   |      33.3 |
| NQ=F hourly | 09:00-12:00  |       61 |       6.5 |      37.7 |
| NQ=F hourly | 13:00-16:00  |       74 |       2.5 |      36.5 |
| ES=F hourly | 08:00-11:00  |       77 |      -9.2 |      36.4 |
| ES=F hourly | 09:00-12:00  |       65 |     -10.7 |      36.9 |
| ES=F hourly | 13:00-16:00  |       70 |      -6.4 |      31.4 |
