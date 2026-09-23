# Phase 7 upgrades 1-3: whole-brain checks (snapshot 630)

PRELIMINARY (PLAN.md Phase 6 not complete: seeds rerun, parameter variants run for each upgrade, literature check done; no independent review).

Each condition: 3 seeds x 30 trials x 1 s (sugar200_ir94e200: 5 seeds). MN9 rates are means over all trials (sd = trial-to-trial). 'Runaway' = a trial with more than 5x the baseline model's median spike count for that condition.

- **baseline**: `"baseline engine"`
- **baseline_newseeds**: `"baseline engine"`
- **U1_delays**: `{"delays": true, "conductance": false, "adaptation": false, "velocity_m_per_s": 0.2, "distance": "anchor", "delay_ms_mean": 2.3143426599718477, "delay_ms_median": 2.3000000000000003, "delay_ms_p95": 3.0, "delay_ms_max": 4.9}`
- **U1_delays_slow0.129**: `{"delays": true, "conductance": false, "adaptation": false, "velocity_m_per_s": 0.129, "distance": "anchor", "delay_ms_mean": 2.597493051422132, "delay_ms_median": 2.5, "delay_ms_p95": 3.6, "delay_ms_max": 6.6000000000000005}`
- **U1_delays_fast2.07**: `{"delays": true, "conductance": false, "adaptation": false, "velocity_m_per_s": 2.07, "distance": "anchor", "delay_ms_mean": 1.8458194351562978, "delay_ms_median": 1.8, "delay_ms_p95": 1.9000000000000001, "delay_ms_max": 2.1}`
- **U1_delays_soma**: `{"delays": true, "conductance": false, "adaptation": false, "velocity_m_per_s": 0.2, "distance": "soma", "delay_ms_mean": 2.398348906781139, "delay_ms_median": 2.4000000000000004, "delay_ms_p95": 3.1, "delay_ms_max": 5.0}`
- **U2_cond**: `{"delays": false, "conductance": true, "adaptation": false, "E_exc_mV": 0.0, "E_inh_mV": -60.0, "g_exc_per_synapse": 0.005288461538461539, "g_inh_per_synapse": 0.034375}`
- **U2_cond_Ei-70**: `{"delays": false, "conductance": true, "adaptation": false, "E_exc_mV": 0.0, "E_inh_mV": -70.0, "cond_weight_scale": 1.0, "g_exc_per_synapse": 0.005288461538461539, "g_inh_per_synapse": 0.015277777777777779}`
- **U2_diag_exc_only**: `{"delays": false, "conductance": true, "adaptation": false, "E_exc_mV": 0.0, "E_inh_mV": -1000000.0, "cond_weight_scale": 1.0, "g_exc_per_synapse": 0.005288461538461539, "g_inh_per_synapse": 2.750143007436387e-07}`
- **U2_diag_inh_only**: `{"delays": false, "conductance": true, "adaptation": false, "E_exc_mV": 1000000.0, "E_inh_mV": -60.0, "cond_weight_scale": 1.0, "g_exc_per_synapse": 2.749857007435614e-07, "g_inh_per_synapse": 0.034375}`
- **U2_cond_tuned**: `{"delays": false, "conductance": true, "adaptation": false, "E_exc_mV": 0.0, "E_inh_mV": -60.0, "cond_weight_scale": 2.0, "g_exc_per_synapse": 0.010576923076923078, "g_inh_per_synapse": 0.06875}`
- **U3_adapt**: `{"delays": false, "conductance": false, "adaptation": true, "tau_adapt_ms": 100.0, "adapt_mV": 0.9738954166171474}`
- **U3_adapt_half**: `{"delays": false, "conductance": false, "adaptation": true, "tau_adapt_ms": 100.0, "adapt_mV": 0.4869477083085737}`
- **U3_adapt_tau300**: `{"delays": false, "conductance": false, "adaptation": true, "tau_adapt_ms": 300.0, "adapt_mV": 0.312242236510185}`
- **U3_adapt_half_RW**: `{"delays": false, "conductance": false, "adaptation": true, "tau_adapt_ms": 100.0, "adapt_mV": 0.4869477083085737}`
- **U3_adapt_tau300_RW**: `{"delays": false, "conductance": false, "adaptation": true, "tau_adapt_ms": 300.0, "adapt_mV": 0.312242236510185}`
- **U13**: `{"delays": true, "conductance": false, "adaptation": true, "velocity_m_per_s": 0.2, "distance": "anchor", "delay_ms_mean": 2.3143426599718477, "delay_ms_median": 2.3000000000000003, "delay_ms_p95": 3.0, "delay_ms_max": 4.9, "tau_adapt_ms": 100.0, "adapt_mV": 0.9738954166171474}`

## MN9 and network size

| config | condition | trials | mn9_contra_hz | mn9_contra_sd | mn9_contra_seed_means | mn9_ipsi_hz | mn9_ipsi_sd | active_neurons | spikes_per_trial_median | runaway_trials_vs_baseline_median | runaway_trials_vs_own_median | runaway_per_seed | mn9_contra_hz_nonrunaway | mn9_contra_hz_runaway |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | sugar_100Hz | 90 | 67.3 | 4.7 | 68.2/66.9/66.8 | 49.6 | 4.3 | 425 | 9620.5 | 0 | 0 | 0/0/0 |  |  |
| baseline | sugar_200Hz | 90 | 93.5 | 4.8 | 94.7/92.7/93.2 | 62.8 | 5.0 | 456 | 16992.5 | 0 | 0 | 0/0/0 |  |  |
| baseline | water_200Hz | 90 | 30.8 | 5.6 | 29.7/30.6/32.1 | 12.7 | 4.3 | 428 | 7512.0 | 0 | 0 | 0/0/0 |  |  |
| baseline | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 0.0 | 96 | 6442.5 | 0 | 0 | 0/0/0 |  |  |
| baseline | sugar100_bitter120 | 90 | 1.4 | 1.6 | 1.3/1.5/1.3 | 6.7 | 1.9 | 408 | 9333.0 | 0 | 0 | 0/0/0 |  |  |
| baseline | sugar200_ir94e200 | 150 | 63.6 | 7.0 | 66.7/64.3/61.7/63.3/62.1 | 37.6 | 5.5 | 8877 | 20022.5 | 5 | 5 | 1/0/2/0/2 | 64.2 | 47.4 |
| baseline_newseeds | sugar_100Hz | 90 | 68.1 | 5.0 | 67.8/68.2/68.3 | 49.4 | 4.7 | 420 | 9699.5 | 0 | 0 | 0/0/0 |  |  |
| baseline_newseeds | sugar_200Hz | 90 | 93.2 | 4.8 | 92.8/92.1/94.7 | 61.1 | 4.4 | 459 | 16957.5 | 0 | 0 | 0/0/0 |  |  |
| baseline_newseeds | water_200Hz | 90 | 30.8 | 5.4 | 31.3/30.4/30.8 | 12.2 | 4.1 | 413 | 7546.5 | 0 | 0 | 0/0/0 |  |  |
| baseline_newseeds | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 0.0 | 96 | 6460.5 | 0 | 0 | 0/0/0 |  |  |
| baseline_newseeds | sugar100_bitter120 | 90 | 1.6 | 1.5 | 1.6/1.2/2.1 | 7.5 | 1.9 | 420 | 9338.5 | 0 | 0 | 0/0/0 |  |  |
| baseline_newseeds | sugar200_ir94e200 | 90 | 64.4 | 7.8 | 63.8/63.2/66.3 | 37.5 | 5.7 | 8767 | 19772.5 | 2 | 2 | 1/1/0 | 65.3 | 25.0 |
| U1_delays | sugar_100Hz | 90 | 71.1 | 4.5 | 70.6/72.3/70.6 | 51.7 | 4.0 | 465 | 9887.5 | 0 | 0 | 0/0/0 |  |  |
| U1_delays | sugar_200Hz | 90 | 93.3 | 4.8 | 95.4/92.5/92.1 | 63.6 | 4.5 | 456 | 17189.5 | 0 | 0 | 0/0/0 |  |  |
| U1_delays | water_200Hz | 90 | 31.0 | 5.3 | 30.7/30.3/32.0 | 12.5 | 4.2 | 414 | 7510.5 | 0 | 0 | 0/0/0 |  |  |
| U1_delays | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 0.0 | 97 | 6436.5 | 0 | 0 | 0/0/0 |  |  |
| U1_delays | sugar100_bitter120 | 90 | 1.4 | 1.3 | 1.3/1.4/1.4 | 6.8 | 1.7 | 402 | 9339.0 | 0 | 0 | 0/0/0 |  |  |
| U1_delays | sugar200_ir94e200 | 150 | 64.2 | 7.1 | 65.5/65.7/63.9/63.8/61.9 | 37.3 | 5.2 | 8956 | 20548.0 | 6 | 6 | 1/0/2/1/2 | 65.0 | 44.5 |
| U1_delays_slow0.129 | sugar_100Hz | 30 | 71.5 | 4.1 | 71.5 | 51.7 | 4.5 | 401 | 10092.0 | 0 | 0 | 0 |  |  |
| U1_delays_slow0.129 | sugar_200Hz | 30 | 94.1 | 5.1 | 94.1 | 63.9 | 4.5 | 450 | 17252.0 | 0 | 0 | 0 |  |  |
| U1_delays_slow0.129 | water_200Hz | 30 | 30.3 | 5.8 | 30.3 | 12.5 | 4.6 | 358 | 7489.0 | 0 | 0 | 0 |  |  |
| U1_delays_slow0.129 | bitter_200Hz | 30 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 96 | 6441.5 | 0 | 0 | 0 |  |  |
| U1_delays_slow0.129 | sugar100_bitter120 | 30 | 1.4 | 1.5 | 1.4 | 6.9 | 1.8 | 392 | 9305.5 | 0 | 0 | 0 |  |  |
| U1_delays_fast2.07 | sugar_100Hz | 30 | 68.5 | 4.0 | 68.5 | 50.4 | 4.5 | 419 | 9768.5 | 0 | 0 | 0 |  |  |
| U1_delays_fast2.07 | sugar_200Hz | 30 | 93.6 | 5.4 | 93.6 | 61.4 | 4.2 | 447 | 17009.0 | 0 | 0 | 0 |  |  |
| U1_delays_fast2.07 | water_200Hz | 30 | 30.9 | 4.6 | 30.9 | 13.0 | 3.5 | 362 | 7537.5 | 0 | 0 | 0 |  |  |
| U1_delays_fast2.07 | bitter_200Hz | 30 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 93 | 6440.0 | 0 | 0 | 0 |  |  |
| U1_delays_fast2.07 | sugar100_bitter120 | 30 | 2.0 | 1.9 | 2.0 | 6.9 | 1.8 | 374 | 9338.5 | 0 | 0 | 0 |  |  |
| U1_delays_soma | sugar_100Hz | 30 | 70.7 | 4.5 | 70.7 | 51.0 | 3.8 | 413 | 9960.5 | 0 | 0 | 0 |  |  |
| U1_delays_soma | sugar_200Hz | 30 | 94.3 | 4.0 | 94.3 | 63.3 | 4.4 | 451 | 17188.0 | 0 | 0 | 0 |  |  |
| U1_delays_soma | water_200Hz | 30 | 29.6 | 5.2 | 29.6 | 11.7 | 3.6 | 348 | 7493.0 | 0 | 0 | 0 |  |  |
| U1_delays_soma | bitter_200Hz | 30 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 94 | 6440.5 | 0 | 0 | 0 |  |  |
| U1_delays_soma | sugar100_bitter120 | 30 | 1.8 | 1.4 | 1.8 | 6.6 | 2.0 | 378 | 9334.5 | 0 | 0 | 0 |  |  |
| U2_cond | sugar_100Hz | 90 | 6.8 | 3.2 | 6.9/7.2/6.4 | 2.8 | 2.0 | 296 | 4985.0 | 0 | 0 | 0/0/0 |  |  |
| U2_cond | sugar_200Hz | 90 | 25.6 | 5.8 | 27.4/23.5/26.0 | 9.5 | 3.6 | 337 | 10071.5 | 0 | 0 | 0/0/0 |  |  |
| U2_cond | water_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 0.0 | 110 | 5791.0 | 0 | 0 | 0/0/0 |  |  |
| U2_cond | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 0.0 | 82 | 5861.5 | 0 | 0 | 0/0/0 |  |  |
| U2_cond | sugar100_bitter120 | 90 | 0.1 | 0.2 | 0.1/0.1/0.1 | 0.1 | 0.4 | 246 | 7609.0 | 0 | 0 | 0/0/0 |  |  |
| U2_cond | sugar200_ir94e200 | 150 | 0.0 | 0.1 | 0.0/0.0/0.0/0.0/0.0 | 0.0 | 0.0 | 252 | 11951.0 | 0 | 0 | 0/0/0/0/0 |  |  |
| U2_cond_Ei-70 | sugar_100Hz | 30 | 26.1 | 6.4 | 26.1 | 15.7 | 4.4 | 317 | 5882.0 | 0 | 0 | 0 |  |  |
| U2_cond_Ei-70 | sugar_200Hz | 30 | 67.5 | 5.1 | 67.5 | 40.6 | 4.9 | 369 | 12400.0 | 0 | 0 | 0 |  |  |
| U2_cond_Ei-70 | water_200Hz | 30 | 0.1 | 0.3 | 0.1 | 0.0 | 0.0 | 122 | 5987.5 | 0 | 0 | 0 |  |  |
| U2_cond_Ei-70 | bitter_200Hz | 30 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 83 | 5934.5 | 0 | 0 | 0 |  |  |
| U2_cond_Ei-70 | sugar100_bitter120 | 30 | 0.1 | 0.2 | 0.1 | 0.6 | 0.6 | 251 | 7975.5 | 0 | 0 | 0 |  |  |
| U2_diag_exc_only | sugar_100Hz | 30 | 53.3 | 5.3 | 53.3 | 39.2 | 4.5 | 354 | 7553.5 | 0 | 0 | 0 |  |  |
| U2_diag_exc_only | sugar100_bitter120 | 30 | 0.2 | 0.5 | 0.2 | 2.2 | 1.3 | 291 | 8204.5 | 0 | 0 | 0 |  |  |
| U2_diag_inh_only | sugar_100Hz | 30 | 25.0 | 4.6 | 25.0 | 15.1 | 3.2 | 348 | 6322.5 | 0 | 0 | 0 |  |  |
| U2_diag_inh_only | sugar100_bitter120 | 30 | 0.1 | 0.3 | 0.1 | 0.5 | 0.6 | 292 | 8567.0 | 0 | 0 | 0 |  |  |
| U2_cond_tuned | sugar_100Hz | 90 | 52.6 | 5.7 | 52.7/52.0/53.1 | 38.0 | 4.5 | 9494 | 12888.5 | 2 | 1 | 0/1/1 | 52.7 | 47.0 |
| U2_cond_tuned | sugar_200Hz | 90 | 71.7 | 6.1 | 72.5/70.6/71.9 | 43.8 | 5.2 | 9132 | 18780.5 | 2 | 2 | 0/1/1 | 71.7 | 73.0 |
| U2_cond_tuned | water_200Hz | 90 | 20.6 | 7.4 | 20.5/19.5/21.7 | 9.6 | 5.6 | 11197 | 22024.0 | 19 | 14 | 7/7/5 | 22.3 | 13.9 |
| U2_cond_tuned | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 0.0 | 9560 | 11470.5 | 4 | 2 | 1/2/1 | 0.0 | 0.0 |
| U2_cond_tuned | sugar100_bitter120 | 90 | 4.4 | 2.6 | 4.3/4.1/4.7 | 4.7 | 2.4 | 3706 | 14155.0 | 0 | 0 | 0/0/0 |  |  |
| U2_cond_tuned | sugar200_ir94e200 | 90 | 13.7 | 4.7 | 15.4/12.4/13.3 | 13.1 | 3.6 | 9920 | 22164.5 | 5 | 5 | 1/2/2 | 14.0 | 9.2 |
| U3_adapt | sugar_100Hz | 90 | 43.9 | 3.8 | 43.8/43.7/44.1 | 29.7 | 3.2 | 423 | 6624.5 | 0 | 0 | 0/0/0 |  |  |
| U3_adapt | sugar_200Hz | 90 | 67.0 | 4.2 | 67.9/67.1/65.9 | 43.4 | 3.5 | 455 | 12671.0 | 0 | 0 | 0/0/0 |  |  |
| U3_adapt | water_200Hz | 90 | 11.0 | 3.4 | 11.9/10.5/10.6 | 5.2 | 2.6 | 360 | 5964.0 | 0 | 0 | 0/0/0 |  |  |
| U3_adapt | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 0.0 | 94 | 5793.0 | 0 | 0 | 0/0/0 |  |  |
| U3_adapt | sugar100_bitter120 | 90 | 3.2 | 1.9 | 2.9/3.5/3.0 | 3.5 | 1.4 | 401 | 7814.5 | 0 | 0 | 0/0/0 |  |  |
| U3_adapt | sugar200_ir94e200 | 150 | 32.0 | 3.7 | 31.6/32.7/32.3/32.4/31.2 | 17.5 | 3.0 | 896 | 14206.0 | 0 | 0 | 0/0/0/0/0 |  |  |
| U3_adapt_half | sugar_100Hz | 30 | 54.0 | 4.3 | 54.0 | 39.6 | 3.8 | 403 | 7881.0 | 0 | 0 | 0 |  |  |
| U3_adapt_half | sugar_200Hz | 30 | 79.7 | 4.0 | 79.7 | 53.1 | 3.7 | 448 | 14612.0 | 0 | 0 | 0 |  |  |
| U3_adapt_half | water_200Hz | 30 | 19.5 | 4.2 | 19.5 | 9.3 | 3.3 | 385 | 6704.0 | 0 | 0 | 0 |  |  |
| U3_adapt_half | bitter_200Hz | 30 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 93 | 6052.0 | 0 | 0 | 0 |  |  |
| U3_adapt_half | sugar100_bitter120 | 30 | 2.5 | 1.5 | 2.5 | 4.5 | 1.3 | 377 | 8360.5 | 0 | 0 | 0 |  |  |
| U3_adapt_tau300 | sugar_100Hz | 30 | 47.8 | 3.9 | 47.8 | 32.3 | 2.9 | 392 | 6992.0 | 0 | 0 | 0 |  |  |
| U3_adapt_tau300 | sugar_200Hz | 30 | 72.3 | 3.6 | 72.3 | 48.0 | 3.5 | 457 | 13424.0 | 0 | 0 | 0 |  |  |
| U3_adapt_tau300 | water_200Hz | 30 | 13.8 | 3.4 | 13.8 | 6.8 | 2.8 | 375 | 6229.0 | 0 | 0 | 0 |  |  |
| U3_adapt_tau300 | bitter_200Hz | 30 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 94 | 5882.0 | 0 | 0 | 0 |  |  |
| U3_adapt_tau300 | sugar100_bitter120 | 30 | 2.9 | 1.4 | 2.9 | 4.1 | 1.5 | 376 | 7996.5 | 0 | 0 | 0 |  |  |
| U3_adapt_half_RW | sugar200_ir94e200 | 150 | 43.8 | 5.1 | 45.2/44.8/42.5/43.7/42.7 | 24.5 | 4.0 | 1016 | 16028.0 | 0 | 0 | 0/0/0/0/0 |  |  |
| U3_adapt_tau300_RW | sugar200_ir94e200 | 150 | 34.8 | 4.0 | 36.7/35.2/34.1/33.7/34.2 | 19.3 | 3.6 | 1012 | 14744.0 | 0 | 0 | 0/0/0/0/0 |  |  |
| U13 | sugar_100Hz | 90 | 45.3 | 3.3 | 46.6/44.1/45.1 | 30.2 | 2.8 | 419 | 6628.5 | 0 | 0 | 0/0/0 |  |  |
| U13 | sugar_200Hz | 90 | 69.6 | 3.7 | 70.2/69.9/68.6 | 44.9 | 3.5 | 457 | 12750.0 | 0 | 0 | 0/0/0 |  |  |
| U13 | water_200Hz | 90 | 10.0 | 3.5 | 11.3/9.2/9.6 | 4.5 | 2.4 | 355 | 5924.0 | 0 | 0 | 0/0/0 |  |  |
| U13 | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 0.0 | 94 | 5789.5 | 0 | 0 | 0/0/0 |  |  |
| U13 | sugar100_bitter120 | 90 | 3.6 | 1.9 | 3.6/3.5/3.6 | 3.9 | 1.5 | 397 | 7801.5 | 0 | 0 | 0/0/0 |  |  |
| U13 | sugar200_ir94e200 | 150 | 31.9 | 3.8 | 33.5/31.1/30.3/32.9/31.7 | 17.6 | 3.0 | 936 | 14189.0 | 0 | 0 | 0/0/0/0/0 |  |  |

## Runaway activity (sugar200_ir94e200, 5 seeds x 30 trials)

| config | trials | runaway_trials | fraction | 95% range | p vs baseline (Fisher) | MN9 contra, non-runaway trials (Hz) |
|---|---|---|---|---|---|---|
| baseline | 150 | 5 | 0.033 | 0.014-0.076 |  | 64.2 |
| baseline_newseeds | 90 | 2 | 0.022 | 0.006-0.077 | 0.714 | 65.3 |
| U1_delays | 150 | 6 | 0.040 | 0.018-0.085 | 1 | 65.0 |
| U2_cond | 150 | 0 | 0.000 | 0.000-0.025 | 0.0604 | 0.0 |
| U2_cond_tuned | 90 | 5 | 0.056 | 0.024-0.124 | 0.508 | 14.0 |
| U3_adapt | 150 | 0 | 0.000 | 0.000-0.025 | 0.0604 | 32.0 |
| U3_adapt_half_RW | 150 | 0 | 0.000 | 0.000-0.025 | 0.0604 | 43.8 |
| U3_adapt_tau300_RW | 150 | 0 | 0.000 | 0.000-0.025 | 0.0604 | 34.8 |
| U13 | 150 | 0 | 0.000 | 0.000-0.025 | 0.0604 | 31.9 |

## Phase 3 checks (a check holds only if it passes for every seed)

| check | baseline | baseline_newseeds | U1_delays | U1_delays_slow0.129 | U1_delays_fast2.07 | U1_delays_soma | U2_cond | U2_cond_Ei-70 | U2_cond_tuned | U3_adapt | U3_adapt_half | U3_adapt_tau300 | U13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bitter alone: MN9 silent (<= 1 Hz) | pass/pass/pass | pass/pass/pass | pass/pass/pass | pass | pass | pass | pass/pass/pass | pass | pass/pass/pass | pass/pass/pass | pass | pass | pass/pass/pass |
| sugar 100 + bitter 120: MN9 near 0 (<= 10% of sugar alone) | pass/pass/pass | pass/pass/pass | pass/pass/pass | pass | pass | pass | pass/pass/pass | pass | pass/pass/pass | pass/pass/pass | pass | pass | pass/pass/pass |
| sugar 100 Hz drives MN9 (>= 20 Hz) | pass/pass/pass | pass/pass/pass | pass/pass/pass | pass | pass | pass | FAIL/FAIL/FAIL | pass | pass/pass/pass | pass/pass/pass | pass | pass | pass/pass/pass |
| sugar 200 + Ir94e 200: MN9 lower than sugar alone, not abolished (>= 10 Hz) | pass/pass/pass | pass/pass/pass | pass/pass/pass |  |  |  | FAIL/FAIL/FAIL |  | pass/pass/pass | pass/pass/pass |  |  | pass/pass/pass |
| sugar 200 Hz > sugar 100 Hz | pass/pass/pass | pass/pass/pass | pass/pass/pass | pass | pass | pass | pass/pass/pass | pass | pass/pass/pass | pass/pass/pass | pass | pass | pass/pass/pass |
| sugar: contra MN9 > ipsi MN9 | pass/pass/pass | pass/pass/pass | pass/pass/pass | pass | pass | pass | pass/pass/pass | pass | pass/pass/pass | pass/pass/pass | pass | pass | pass/pass/pass |
| water 200 Hz drives MN9 (>= 5 Hz), less than sugar 200 | pass/pass/pass | pass/pass/pass | pass/pass/pass | pass | pass | pass | FAIL/FAIL/FAIL | FAIL | pass/pass/pass | pass/pass/pass | pass | pass | pass/pass/pass |

## Neuron by neuron (stimulated neurons excluded)

Noise floor = `baseline_newseeds` vs `baseline`: how much two runs of the SAME model differ from randomness alone.

| config | vs | condition | pearson_r | top50_overlap | n_compared | active_only_in_reference | active_only_in_this |
|---|---|---|---|---|---|---|---|
| baseline_newseeds | baseline | sugar_100Hz | 0.9999 | 50 | 412 | 13 | 8 |
| baseline_newseeds | baseline | sugar_200Hz | 1.0000 | 50 | 444 | 6 | 9 |
| baseline_newseeds | baseline | water_200Hz | 1.0000 | 50 | 424 | 29 | 14 |
| baseline_newseeds | baseline | bitter_200Hz | 1.0000 | 50 | 75 | 0 | 0 |
| baseline_newseeds | baseline | sugar100_bitter120 | 0.9999 | 49 | 391 | 13 | 25 |
| baseline_newseeds | baseline | sugar200_ir94e200 | 1.0000 | 49 | 8899 | 171 | 61 |
| U1_delays | baseline | sugar_100Hz | 0.9988 | 50 | 448 | 4 | 44 |
| U1_delays | baseline | sugar_200Hz | 0.9995 | 49 | 443 | 8 | 8 |
| U1_delays | baseline | water_200Hz | 0.9997 | 50 | 417 | 21 | 7 |
| U1_delays | baseline | bitter_200Hz | 1.0000 | 50 | 76 | 0 | 1 |
| U1_delays | baseline | sugar100_bitter120 | 0.9998 | 49 | 373 | 13 | 7 |
| U1_delays | baseline | sugar200_ir94e200 | 0.9988 | 49 | 9005 | 88 | 167 |
| U1_delays_slow0.129 | baseline | sugar_100Hz | 0.9971 | 48 | 409 | 29 | 5 |
| U1_delays_slow0.129 | baseline | sugar_200Hz | 0.9989 | 48 | 439 | 10 | 4 |
| U1_delays_slow0.129 | baseline | water_200Hz | 0.9997 | 49 | 412 | 72 | 2 |
| U1_delays_slow0.129 | baseline | bitter_200Hz | 1.0000 | 50 | 75 | 0 | 0 |
| U1_delays_slow0.129 | baseline | sugar100_bitter120 | 0.9998 | 49 | 382 | 32 | 16 |
| U1_delays_fast2.07 | baseline | sugar_100Hz | 0.9997 | 50 | 408 | 10 | 4 |
| U1_delays_fast2.07 | baseline | sugar_200Hz | 0.9999 | 49 | 436 | 10 | 1 |
| U1_delays_fast2.07 | baseline | water_200Hz | 0.9999 | 49 | 411 | 67 | 1 |
| U1_delays_fast2.07 | baseline | bitter_200Hz | 1.0000 | 50 | 75 | 3 | 0 |
| U1_delays_fast2.07 | baseline | sugar100_bitter120 | 0.9999 | 48 | 368 | 36 | 2 |
| U1_delays_soma | baseline | sugar_100Hz | 0.9988 | 50 | 407 | 15 | 3 |
| U1_delays_soma | baseline | sugar_200Hz | 0.9993 | 48 | 439 | 9 | 4 |
| U1_delays_soma | baseline | water_200Hz | 0.9996 | 49 | 414 | 84 | 4 |
| U1_delays_soma | baseline | bitter_200Hz | 1.0000 | 50 | 75 | 2 | 0 |
| U1_delays_soma | baseline | sugar100_bitter120 | 0.9998 | 48 | 373 | 37 | 7 |
| U2_cond | baseline | sugar_100Hz | 0.8140 | 33 | 408 | 133 | 4 |
| U2_cond | baseline | sugar_200Hz | 0.8482 | 36 | 444 | 128 | 9 |
| U2_cond | baseline | water_200Hz | 0.9614 | 46 | 410 | 318 | 0 |
| U2_cond | baseline | bitter_200Hz | 0.9876 | 46 | 75 | 14 | 0 |
| U2_cond | baseline | sugar100_bitter120 | 0.9606 | 43 | 366 | 162 | 0 |
| U2_cond | baseline | sugar200_ir94e200 | 0.8361 | 38 | 8843 | 8630 | 5 |
| U2_cond_Ei-70 | baseline | sugar_100Hz | 0.8907 | 35 | 406 | 110 | 2 |
| U2_cond_Ei-70 | baseline | sugar_200Hz | 0.9516 | 43 | 440 | 92 | 5 |
| U2_cond_Ei-70 | baseline | water_200Hz | 0.9704 | 46 | 410 | 306 | 0 |
| U2_cond_Ei-70 | baseline | bitter_200Hz | 0.9920 | 48 | 75 | 13 | 0 |
| U2_cond_Ei-70 | baseline | sugar100_bitter120 | 0.9771 | 46 | 366 | 157 | 0 |
| U2_diag_exc_only | baseline | sugar_100Hz | 0.9753 | 40 | 404 | 71 | 0 |
| U2_diag_exc_only | baseline | sugar100_bitter120 | 0.9851 | 46 | 366 | 117 | 0 |
| U2_diag_inh_only | baseline | sugar_100Hz | 0.9075 | 37 | 404 | 77 | 0 |
| U2_diag_inh_only | baseline | sugar100_bitter120 | 0.9855 | 42 | 367 | 117 | 1 |
| U2_cond_tuned | baseline | sugar_100Hz | 0.9264 | 36 | 9474 | 1 | 9070 |
| U2_cond_tuned | baseline | sugar_200Hz | 0.9483 | 40 | 9112 | 1 | 8677 |
| U2_cond_tuned | baseline | water_200Hz | 0.6441 | 41 | 11181 | 2 | 10771 |
| U2_cond_tuned | baseline | bitter_200Hz | 0.9035 | 45 | 9540 | 1 | 9465 |
| U2_cond_tuned | baseline | sugar100_bitter120 | 0.8880 | 34 | 3665 | 1 | 3299 |
| U2_cond_tuned | baseline | sugar200_ir94e200 | 0.8970 | 40 | 11914 | 2033 | 3076 |
| U3_adapt | baseline | sugar_100Hz | 0.9468 | 38 | 436 | 34 | 32 |
| U3_adapt | baseline | sugar_200Hz | 0.9583 | 43 | 454 | 20 | 19 |
| U3_adapt | baseline | water_200Hz | 0.9718 | 42 | 417 | 75 | 7 |
| U3_adapt | baseline | bitter_200Hz | 0.9912 | 47 | 79 | 6 | 4 |
| U3_adapt | baseline | sugar100_bitter120 | 0.9723 | 45 | 381 | 22 | 15 |
| U3_adapt | baseline | sugar200_ir94e200 | 0.9472 | 40 | 8859 | 8002 | 21 |
| U3_adapt_half | baseline | sugar_100Hz | 0.9831 | 42 | 404 | 22 | 0 |
| U3_adapt_half | baseline | sugar_200Hz | 0.9867 | 45 | 442 | 15 | 7 |
| U3_adapt_half | baseline | water_200Hz | 0.9861 | 44 | 422 | 55 | 12 |
| U3_adapt_half | baseline | bitter_200Hz | 0.9973 | 48 | 75 | 3 | 0 |
| U3_adapt_half | baseline | sugar100_bitter120 | 0.9872 | 46 | 374 | 39 | 8 |
| U3_adapt_tau300 | baseline | sugar_100Hz | 0.9553 | 39 | 408 | 37 | 4 |
| U3_adapt_tau300 | baseline | sugar_200Hz | 0.9695 | 43 | 451 | 15 | 16 |
| U3_adapt_tau300 | baseline | water_200Hz | 0.9771 | 43 | 418 | 61 | 8 |
| U3_adapt_tau300 | baseline | bitter_200Hz | 0.9933 | 47 | 77 | 4 | 2 |
| U3_adapt_tau300 | baseline | sugar100_bitter120 | 0.9783 | 45 | 373 | 39 | 7 |
| U3_adapt_half_RW | baseline | sugar200_ir94e200 | 0.9772 | 43 | 8848 | 7871 | 10 |
| U3_adapt_tau300_RW | baseline | sugar200_ir94e200 | 0.9579 | 40 | 8864 | 7891 | 26 |
| U13 | baseline | sugar_100Hz | 0.9457 | 38 | 419 | 21 | 15 |
| U13 | U1_delays | sugar_100Hz | 0.9343 | 38 | 457 | 59 | 13 |
| U13 | baseline | sugar_200Hz | 0.9607 | 43 | 454 | 18 | 19 |
| U13 | U1_delays | sugar_200Hz | 0.9544 | 42 | 455 | 19 | 20 |
| U13 | baseline | water_200Hz | 0.9716 | 42 | 418 | 81 | 8 |
| U13 | U1_delays | water_200Hz | 0.9704 | 42 | 401 | 64 | 5 |
| U13 | baseline | bitter_200Hz | 0.9914 | 47 | 79 | 6 | 4 |
| U13 | U1_delays | bitter_200Hz | 0.9912 | 47 | 79 | 6 | 3 |
| U13 | baseline | sugar100_bitter120 | 0.9694 | 45 | 379 | 24 | 13 |
| U13 | U1_delays | sugar100_bitter120 | 0.9658 | 44 | 380 | 25 | 20 |
| U13 | baseline | sugar200_ir94e200 | 0.9478 | 40 | 8859 | 7962 | 21 |
| U13 | U1_delays | sugar200_ir94e200 | 0.9355 | 39 | 8939 | 8042 | 22 |