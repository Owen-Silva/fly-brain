# Phase 7 upgrade 4 (cell-type-specific parameters): whole-brain checks (snapshot 630)

PRELIMINARY (PLAN.md Phase 6 not complete: seeds rerun and variants run; no independent review).

Each check condition: 3 seeds x 30 trials x 1 s (variants: 1 seed). Runaway conditions: 5 seeds = 150 trials. Runaway (Phase 6 definition) = a trial where more than 1500 different neurons fire in one 10 ms slice.

- Baseline here vs experiments/phase7/results/baseline (same seeds): 20/20 files identical (MN9 per trial and spikes per trial).

- **baseline**: baseline engine
- **baseline_newseeds**: baseline engine
- **CT_main**: 5477 neurons changed; `{"uPN_ACh": {"n_neurons": 251, "t_mbr": 22.9, "gap": 10.0}, "KC": {"n_neurons": 5177, "t_mbr": 11.2, "gap": 21.5}, "PEN": {"n_neurons": 42, "t_mbr": 20.0, "gap": 12.0}, "lLNv": {"n_neurons": 7, "t_mbr": 3.66, "gap": 7.0}}`
- **CT_only_uPN**: 251 neurons changed; `{"uPN_ACh": {"n_neurons": 251, "t_mbr": 22.9, "gap": 10.0}}`
- **CT_only_KC**: 5177 neurons changed; `{"KC": {"n_neurons": 5177, "t_mbr": 11.2, "gap": 21.5}}`
- **CT_PNgap17.8**: 5477 neurons changed; `{"uPN_ACh": {"n_neurons": 251, "t_mbr": 22.9, "gap": 17.8}, "KC": {"n_neurons": 5177, "t_mbr": 11.2, "gap": 21.5}, "PEN": {"n_neurons": 42, "t_mbr": 20.0, "gap": 12.0}, "lLNv": {"n_neurons": 7, "t_mbr": 3.66, "gap": 7.0}}`
- **CT_KCtau200**: 5477 neurons changed; `{"uPN_ACh": {"n_neurons": 251, "t_mbr": 22.9, "gap": 10.0}, "KC": {"n_neurons": 5177, "t_mbr": 200.0, "gap": 21.5}, "PEN": {"n_neurons": 42, "t_mbr": 20.0, "gap": 12.0}, "lLNv": {"n_neurons": 7, "t_mbr": 3.66, "gap": 7.0}}`

## MN9 and network size

| config | condition | trials | mn9_contra_hz | mn9_contra_sd | mn9_contra_seed_means | mn9_ipsi_hz | active_neurons | spikes_per_trial_median | runaway_trials | mn9_contra_hz_healthy_trials |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | sugar_100Hz | 90 | 67.3 | 4.7 | 68.2/66.9/66.8 | 49.6 | 425 | 9620.5 | 0 | 67.3 |
| baseline | sugar_200Hz | 90 | 93.5 | 4.8 | 94.7/92.7/93.2 | 62.8 | 456 | 16992.5 | 0 | 93.5 |
| baseline | water_200Hz | 90 | 30.8 | 5.6 | 29.7/30.6/32.1 | 12.7 | 428 | 7512.0 | 0 | 30.8 |
| baseline | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 96 | 6442.5 | 0 | 0.0 |
| baseline | sugar100_bitter120 | 90 | 1.4 | 1.6 | 1.3/1.5/1.3 | 6.7 | 408 | 9333.0 | 0 | 1.4 |
| baseline | sugar200_ir94e200 | 150 | 63.6 | 7.0 | 66.7/64.3/61.7/63.3/62.1 | 37.6 | 8877 | 20022.5 | 6 | 64.1 |
| baseline | ir94e_200Hz | 150 | 0.0 | 0.0 | 0.0/0.0/0.0/0.0/0.0 | 0.0 | 8826 | 8063.0 | 19 | 0.0 |
| baseline | dm1_orn_150Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.2 | 8822 | 465537.5 | 90 |  |
| baseline_newseeds | sugar_100Hz | 90 | 68.1 | 5.0 | 67.8/68.2/68.3 | 49.4 | 420 | 9699.5 | 0 | 68.1 |
| baseline_newseeds | sugar_200Hz | 90 | 93.2 | 4.8 | 92.8/92.1/94.7 | 61.1 | 459 | 16957.5 | 0 | 93.2 |
| baseline_newseeds | water_200Hz | 90 | 30.8 | 5.4 | 31.3/30.4/30.8 | 12.2 | 413 | 7546.5 | 0 | 30.8 |
| baseline_newseeds | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 96 | 6460.5 | 0 | 0.0 |
| baseline_newseeds | sugar100_bitter120 | 90 | 1.6 | 1.5 | 1.6/1.2/2.1 | 7.5 | 420 | 9338.5 | 0 | 1.6 |
| CT_main | sugar_100Hz | 90 | 67.3 | 4.7 | 68.2/66.9/66.8 | 49.6 | 425 | 9620.5 | 0 | 67.3 |
| CT_main | sugar_200Hz | 90 | 93.5 | 4.8 | 94.7/92.7/93.2 | 62.8 | 456 | 16992.5 | 0 | 93.5 |
| CT_main | water_200Hz | 90 | 30.8 | 5.6 | 29.7/30.6/32.1 | 12.7 | 428 | 7512.0 | 0 | 30.8 |
| CT_main | bitter_200Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 96 | 6442.5 | 0 | 0.0 |
| CT_main | sugar100_bitter120 | 90 | 1.4 | 1.6 | 1.3/1.5/1.3 | 6.7 | 408 | 9333.0 | 0 | 1.4 |
| CT_main | sugar200_ir94e200 | 150 | 63.6 | 7.0 | 66.7/64.3/61.8/63.1/61.9 | 37.6 | 5136 | 20022.5 | 6 | 64.1 |
| CT_main | ir94e_200Hz | 150 | 0.0 | 0.0 | 0.0/0.0/0.0/0.0/0.0 | 0.0 | 5068 | 8063.0 | 19 | 0.0 |
| CT_main | dm1_orn_150Hz | 90 | 0.0 | 0.0 | 0.0/0.0/0.0 | 0.0 | 5031 | 260306.5 | 90 |  |
| CT_only_uPN | sugar200_ir94e200 | 150 | 63.5 | 7.2 | 66.6/64.3/61.8/63.2/61.6 | 37.6 | 8037 | 20022.5 | 6 | 64.1 |
| CT_only_uPN | ir94e_200Hz | 150 | 0.0 | 0.0 | 0.0/0.0/0.0/0.0/0.0 | 0.0 | 7989 | 8063.0 | 19 | 0.0 |
| CT_only_uPN | dm1_orn_150Hz | 30 | 0.0 | 0.0 | 0.0 | 0.1 | 7872 | 381094.5 | 30 |  |
| CT_only_KC | sugar200_ir94e200 | 150 | 63.5 | 7.3 | 66.6/64.3/61.7/63.3/61.6 | 37.5 | 5674 | 20022.5 | 6 | 64.1 |
| CT_only_KC | ir94e_200Hz | 150 | 0.0 | 0.0 | 0.0/0.0/0.0/0.0/0.0 | 0.0 | 5605 | 8063.0 | 19 | 0.0 |
| CT_only_KC | dm1_orn_150Hz | 30 | 0.0 | 0.0 | 0.0 | 0.0 | 5490 | 297508.0 | 30 |  |
| CT_PNgap17.8 | sugar200_ir94e200 | 150 | 63.5 | 7.4 | 66.8/64.3/61.8/63.2/61.4 | 37.5 | 4620 | 20022.5 | 6 | 64.1 |
| CT_PNgap17.8 | ir94e_200Hz | 150 | 0.0 | 0.0 | 0.0/0.0/0.0/0.0/0.0 | 0.0 | 4551 | 8063.0 | 19 | 0.0 |
| CT_PNgap17.8 | dm1_orn_150Hz | 30 | 0.0 | 0.0 | 0.0 | 0.0 | 4407 | 223372.0 | 30 |  |
| CT_KCtau200 | sugar200_ir94e200 | 150 | 63.5 | 7.3 | 66.6/64.3/61.9/63.2/61.6 | 37.6 | 5065 | 20022.5 | 6 | 64.1 |
| CT_KCtau200 | ir94e_200Hz | 150 | 0.0 | 0.0 | 0.0/0.0/0.0/0.0/0.0 | 0.0 | 4970 | 8063.0 | 19 | 0.0 |
| CT_KCtau200 | dm1_orn_150Hz | 30 | 0.0 | 0.0 | 0.0 | 0.0 | 4851 | 255932.5 | 30 |  |

## Phase 3 checks (a check holds only if it passes for every seed)

| check | baseline | baseline_newseeds | CT_main |
|---|---|---|---|
| bitter alone: MN9 silent (<= 1 Hz) | pass/pass/pass | pass/pass/pass | pass/pass/pass |
| sugar 100 + bitter 120: MN9 near 0 (<= 10% of sugar alone) | pass/pass/pass | pass/pass/pass | pass/pass/pass |
| sugar 100 Hz drives MN9 (>= 20 Hz) | pass/pass/pass | pass/pass/pass | pass/pass/pass |
| sugar 200 + Ir94e 200: MN9 lower than sugar alone, not abolished (>= 10 Hz) | pass/pass/pass |  | pass/pass/pass |
| sugar 200 Hz > sugar 100 Hz | pass/pass/pass | pass/pass/pass | pass/pass/pass |
| sugar: contra MN9 > ipsi MN9 | pass/pass/pass | pass/pass/pass | pass/pass/pass |
| water 200 Hz drives MN9 (>= 5 Hz), less than sugar 200 | pass/pass/pass | pass/pass/pass | pass/pass/pass |

## Runaway activity (Phase 6 definition)

| config | condition | trials | runaway_trials | fraction | 95% range | p vs baseline (Fisher) | median onset (ms) |
|---|---|---|---|---|---|---|---|
| baseline | sugar200_ir94e200 | 150 | 6 | 0.040 | 0.018-0.085 |  | 641 |
| baseline | ir94e_200Hz | 150 | 19 | 0.127 | 0.083-0.189 |  | 609 |
| CT_main | sugar200_ir94e200 | 150 | 6 | 0.040 | 0.018-0.085 | 1 | 646 |
| CT_main | ir94e_200Hz | 150 | 19 | 0.127 | 0.083-0.189 | 1 | 560 |
| CT_only_uPN | sugar200_ir94e200 | 150 | 6 | 0.040 | 0.018-0.085 | 1 | 644 |
| CT_only_uPN | ir94e_200Hz | 150 | 19 | 0.127 | 0.083-0.189 | 1 | 558 |
| CT_only_KC | sugar200_ir94e200 | 150 | 6 | 0.040 | 0.018-0.085 | 1 | 644 |
| CT_only_KC | ir94e_200Hz | 150 | 19 | 0.127 | 0.083-0.189 | 1 | 611 |
| CT_PNgap17.8 | sugar200_ir94e200 | 150 | 6 | 0.040 | 0.018-0.085 | 1 | 649 |
| CT_PNgap17.8 | ir94e_200Hz | 150 | 19 | 0.127 | 0.083-0.189 | 1 | 565 |
| CT_KCtau200 | sugar200_ir94e200 | 150 | 6 | 0.040 | 0.018-0.085 | 1 | 646 |
| CT_KCtau200 | ir94e_200Hz | 150 | 19 | 0.127 | 0.083-0.189 | 1 | 560 |

## Neuron by neuron vs the baseline (stimulated neurons excluded; same seeds)

Noise floor = `baseline_newseeds` vs `baseline`.

| config | vs | condition | pearson_r | top50_overlap | n_compared | active_only_in_baseline | active_only_in_this |
|---|---|---|---|---|---|---|---|
| baseline_newseeds | baseline | sugar_100Hz | 0.9999 | 50 | 412 | 13 | 8 |
| baseline_newseeds | baseline | sugar_200Hz | 1.0000 | 50 | 444 | 6 | 9 |
| baseline_newseeds | baseline | water_200Hz | 1.0000 | 50 | 424 | 29 | 14 |
| baseline_newseeds | baseline | bitter_200Hz | 1.0000 | 50 | 75 | 0 | 0 |
| baseline_newseeds | baseline | sugar100_bitter120 | 0.9999 | 49 | 391 | 13 | 25 |
| CT_main | baseline | sugar_100Hz | 1.0000 | 50 | 404 | 0 | 0 |
| CT_main | baseline | sugar_200Hz | 1.0000 | 50 | 435 | 0 | 0 |
| CT_main | baseline | water_200Hz | 1.0000 | 50 | 410 | 0 | 0 |
| CT_main | baseline | bitter_200Hz | 1.0000 | 50 | 75 | 0 | 0 |
| CT_main | baseline | sugar100_bitter120 | 1.0000 | 50 | 366 | 0 | 0 |
| CT_main | baseline | sugar200_ir94e200 | 0.9988 | 50 | 8935 | 3838 | 97 |
| CT_main | baseline | ir94e_200Hz | 0.9534 | 49 | 8923 | 3873 | 115 |
| CT_main | baseline | dm1_orn_150Hz | 0.8506 | 45 | 8902 | 3939 | 148 |
| CT_only_uPN | baseline | sugar200_ir94e200 | 0.9999 | 50 | 8901 | 903 | 63 |
| CT_only_uPN | baseline | ir94e_200Hz | 0.9949 | 49 | 8867 | 896 | 59 |
| CT_only_uPN | baseline | dm1_orn_150Hz | 0.9848 | 47 | 8724 | 920 | 60 |
| CT_only_KC | baseline | sugar200_ir94e200 | 0.9987 | 49 | 8992 | 3357 | 154 |
| CT_only_KC | baseline | ir94e_200Hz | 0.9523 | 49 | 8968 | 3381 | 160 |
| CT_only_KC | baseline | dm1_orn_150Hz | 0.8549 | 47 | 8829 | 3407 | 165 |
| CT_PNgap17.8 | baseline | sugar200_ir94e200 | 0.9988 | 50 | 8925 | 4344 | 87 |
| CT_PNgap17.8 | baseline | ir94e_200Hz | 0.9515 | 49 | 8905 | 4372 | 97 |
| CT_PNgap17.8 | baseline | dm1_orn_150Hz | 0.8376 | 43 | 8802 | 4463 | 138 |
| CT_KCtau200 | baseline | sugar200_ir94e200 | 0.9987 | 50 | 8942 | 3916 | 104 |
| CT_KCtau200 | baseline | ir94e_200Hz | 0.9506 | 49 | 8919 | 3967 | 111 |
| CT_KCtau200 | baseline | dm1_orn_150Hz | 0.8398 | 45 | 8795 | 4012 | 131 |

## Changed cell groups: mean rate per neuron (Hz)

| condition | group | baseline | baseline_newseeds | CT_main | CT_only_uPN | CT_only_KC | CT_PNgap17.8 | CT_KCtau200 |
|---|---|---|---|---|---|---|---|---|
| bitter_200Hz | KC | 0.0 | 0.0 | 0.0 |  |  |  |  |
| bitter_200Hz | PEN | 0.0 | 0.0 | 0.0 |  |  |  |  |
| bitter_200Hz | lLNv | 0.0 | 0.0 | 0.0 |  |  |  |  |
| bitter_200Hz | uPN_ACh | 0.0 | 0.0 | 0.0 |  |  |  |  |
| dm1_orn_150Hz | KC | 30.232 |  | 0.924 | 20.829 | 2.161 | 0.257 | 0.057 |
| dm1_orn_150Hz | PEN | 0.0 |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| dm1_orn_150Hz | lLNv | 0.0 |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| dm1_orn_150Hz | uPN_ACh | 123.878 |  | 100.403 | 99.318 | 124.883 | 73.621 | 100.591 |
| ir94e_200Hz | KC | 1.771 |  | 0.045 | 1.195 | 0.113 | 0.011 | 0.002 |
| ir94e_200Hz | PEN | 0.0 |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| ir94e_200Hz | lLNv | 0.0 |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| ir94e_200Hz | uPN_ACh | 7.459 |  | 6.05 | 5.986 | 7.52 | 4.424 | 6.061 |
| sugar100_bitter120 | KC | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar100_bitter120 | PEN | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar100_bitter120 | lLNv | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar100_bitter120 | uPN_ACh | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar200_ir94e200 | KC | 0.48 |  | 0.012 | 0.324 | 0.031 | 0.003 | 0.0 |
| sugar200_ir94e200 | PEN | 0.0 |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| sugar200_ir94e200 | lLNv | 0.0 |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| sugar200_ir94e200 | uPN_ACh | 2.031 |  | 1.641 | 1.624 | 2.047 | 1.197 | 1.646 |
| sugar_100Hz | KC | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar_100Hz | PEN | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar_100Hz | lLNv | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar_100Hz | uPN_ACh | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar_200Hz | KC | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar_200Hz | PEN | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar_200Hz | lLNv | 0.0 | 0.0 | 0.0 |  |  |  |  |
| sugar_200Hz | uPN_ACh | 0.0 | 0.0 | 0.0 |  |  |  |  |
| water_200Hz | KC | 0.0 | 0.0 | 0.0 |  |  |  |  |
| water_200Hz | PEN | 0.0 | 0.0 | 0.0 |  |  |  |  |
| water_200Hz | lLNv | 0.0 | 0.0 | 0.0 |  |  |  |  |
| water_200Hz | uPN_ACh | 0.0 | 0.0 | 0.0 |  |  |  |  |

## Kenyon cells and PNs per trial (runs saved with per-trial group counts)

Turner et al. 2008 (p. 739): on average 6 +/- 5% of Kenyon cells respond to a given odor (their own response criterion).

| config | condition | trials | runaway_trials | DM1 PN rate (Hz) | KCs firing per healthy trial (mean) | % of 5,177 KCs (healthy) | uPNs firing per healthy trial | KCs firing per runaway trial (mean) | % of 5,177 KCs (runaway) | uPNs firing per runaway trial |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | dm1_orn_150Hz | 90 | 90 | 283.0 |  |  |  | 3324.7 | 64.22 | 239.0 |
| CT_main | dm1_orn_150Hz | 90 | 90 | 260.9 |  |  |  | 212.0 | 4.1 | 237.0 |
| CT_only_uPN | dm1_orn_150Hz | 30 | 30 | 259.5 |  |  |  | 2764.7 | 53.4 | 237.0 |
| CT_only_uPN | ir94e_200Hz | 150 | 19 | 11.7 | 0.0 | 0.0 | 0.0 | 2667.9 | 51.53 | 235.4 |
| CT_only_uPN | sugar200_ir94e200 | 150 | 6 | 3.2 | 0.0 | 0.0 | 0.0 | 2701.3 | 52.18 | 236.3 |
| CT_only_KC | dm1_orn_150Hz | 30 | 30 | 284.2 |  |  |  | 467.2 | 9.02 | 239.0 |
| CT_only_KC | ir94e_200Hz | 150 | 19 | 13.7 | 0.0 | 0.0 | 0.1 | 388.8 | 7.51 | 238.7 |
| CT_only_KC | sugar200_ir94e200 | 150 | 6 | 3.7 | 0.0 | 0.0 | 0.0 | 405.0 | 7.82 | 239.0 |
| CT_PNgap17.8 | dm1_orn_150Hz | 30 | 30 | 226.7 |  |  |  | 73.1 | 1.41 | 224.0 |
| CT_PNgap17.8 | ir94e_200Hz | 150 | 19 | 10.0 | 0.0 | 0.0 | 0.0 | 52.3 | 1.01 | 222.3 |
| CT_PNgap17.8 | sugar200_ir94e200 | 150 | 6 | 2.7 | 0.0 | 0.0 | 0.0 | 51.3 | 0.99 | 223.3 |
| CT_KCtau200 | dm1_orn_150Hz | 30 | 30 | 261.2 |  |  |  | 159.3 | 3.08 | 237.0 |
| CT_KCtau200 | ir94e_200Hz | 150 | 19 | 11.9 | 0.0 | 0.0 | 0.0 | 60.5 | 1.17 | 235.5 |
| CT_KCtau200 | sugar200_ir94e200 | 150 | 6 | 3.2 | 0.0 | 0.0 | 0.0 | 49.3 | 0.95 | 236.5 |

## Largest single-neuron changes, CT_main vs baseline (all trials)

| condition | root_id | type | class | in_changed_group | baseline_hz | CT_main_hz |
|---|---|---|---|---|---|---|
| ir94e_200Hz | 720575940631741613 | KCab | Kenyon_Cell | True | 4.96 | 0.0 |
| ir94e_200Hz | 720575940609781966 | KCab | Kenyon_Cell | True | 4.92 | 0.0 |
| ir94e_200Hz | 720575940643919982 | KCab | Kenyon_Cell | True | 5.16 | 0.26 |
| ir94e_200Hz | 720575940606687499 | KCab | Kenyon_Cell | True | 4.89 | 0.0 |
| ir94e_200Hz | 720575940611669145 | KCab | Kenyon_Cell | True | 4.86 | 0.0 |
| ir94e_200Hz | 720575940628581123 | KCab | Kenyon_Cell | True | 4.84 | 0.0 |
| ir94e_200Hz | 720575940626227202 | KCab | Kenyon_Cell | True | 4.82 | 0.0 |
| ir94e_200Hz | 720575940625529477 | KCg-m | Kenyon_Cell | True | 4.95 | 0.15 |
| ir94e_200Hz | 720575940628137969 | KCab | Kenyon_Cell | True | 4.95 | 0.17 |
| ir94e_200Hz | 720575940625175845 | KCg-m | Kenyon_Cell | True | 5.47 | 0.7 |
| ir94e_200Hz | 720575940637132389 | DPM | MBIN | False | 17.76 | 0.0 |
| ir94e_200Hz | 720575940623495827 | DPM | MBIN | False | 16.02 | 0.0 |
| ir94e_200Hz | 720575940630496374 | MBON05 | MBON | False | 15.14 | 0.0 |
| ir94e_200Hz | 720575940623201833 | MBON11 | MBON | False | 18.63 | 3.74 |
| ir94e_200Hz | 720575940617749538 | MBON11 | MBON | False | 17.78 | 3.69 |
| ir94e_200Hz | 720575940638028607 | MBON06 | MBON | False | 13.96 | 0.0 |
| ir94e_200Hz | 720575940621164720 | MBON05 | MBON | False | 13.69 | 0.0 |
| ir94e_200Hz | 720575940621040737 | PPL101 | DAN | False | 16.9 | 3.71 |
| ir94e_200Hz | 720575940628779563 | MBON09 | MBON | False | 14.07 | 1.03 |
| ir94e_200Hz | 720575940617691170 | PPL101 | DAN | False | 16.4 | 3.66 |
| sugar200_ir94e200 | 720575940631741613 | KCab | Kenyon_Cell | True | 1.35 | 0.0 |
| sugar200_ir94e200 | 720575940609781966 | KCab | Kenyon_Cell | True | 1.34 | 0.0 |
| sugar200_ir94e200 | 720575940628581123 | KCab | Kenyon_Cell | True | 1.33 | 0.0 |
| sugar200_ir94e200 | 720575940606687499 | KCab | Kenyon_Cell | True | 1.33 | 0.0 |
| sugar200_ir94e200 | 720575940625529477 | KCg-m | Kenyon_Cell | True | 1.35 | 0.03 |
| sugar200_ir94e200 | 720575940643919982 | KCab | Kenyon_Cell | True | 1.4 | 0.08 |
| sugar200_ir94e200 | 720575940611669145 | KCab | Kenyon_Cell | True | 1.31 | 0.0 |
| sugar200_ir94e200 | 720575940628137969 | KCab | Kenyon_Cell | True | 1.35 | 0.03 |
| sugar200_ir94e200 | 720575940626227202 | KCab | Kenyon_Cell | True | 1.31 | 0.0 |
| sugar200_ir94e200 | 720575940625175845 | KCg-m | Kenyon_Cell | True | 1.47 | 0.18 |
| sugar200_ir94e200 | 720575940637132389 | DPM | MBIN | False | 4.79 | 0.0 |
| sugar200_ir94e200 | 720575940623495827 | DPM | MBIN | False | 4.33 | 0.0 |
| sugar200_ir94e200 | 720575940630496374 | MBON05 | MBON | False | 4.1 | 0.0 |
| sugar200_ir94e200 | 720575940623201833 | MBON11 | MBON | False | 5.99 | 2.01 |
| sugar200_ir94e200 | 720575940617749538 | MBON11 | MBON | False | 5.69 | 1.89 |
| sugar200_ir94e200 | 720575940638028607 | MBON06 | MBON | False | 3.77 | 0.0 |
| sugar200_ir94e200 | 720575940621164720 | MBON05 | MBON | False | 3.75 | 0.0 |
| sugar200_ir94e200 | 720575940621040737 | PPL101 | DAN | False | 5.57 | 2.02 |
| sugar200_ir94e200 | 720575940628779563 | MBON09 | MBON | False | 3.8 | 0.27 |
| sugar200_ir94e200 | 720575940617691170 | PPL101 | DAN | False | 5.37 | 1.91 |
| dm1_orn_150Hz | 720575940616009729 | KCab | Kenyon_Cell | True | 85.14 | 0.2 |
| dm1_orn_150Hz | 720575940628581123 | KCab | Kenyon_Cell | True | 87.59 | 2.99 |
| dm1_orn_150Hz | 720575940632179364 | KCab | Kenyon_Cell | True | 83.97 | 0.0 |
| dm1_orn_150Hz | 720575940609781966 | KCab | Kenyon_Cell | True | 83.79 | 0.0 |
| dm1_orn_150Hz | 720575940606687499 | KCab | Kenyon_Cell | True | 83.12 | 0.0 |
| dm1_orn_150Hz | 720575940626227202 | KCab | Kenyon_Cell | True | 82.76 | 0.0 |
| dm1_orn_150Hz | 720575940623689148 | KCab | Kenyon_Cell | True | 82.91 | 0.38 |
| dm1_orn_150Hz | 720575940611669145 | KCab | Kenyon_Cell | True | 82.49 | 0.0 |
| dm1_orn_150Hz | 720575940625427210 | KCab | Kenyon_Cell | True | 82.3 | 0.02 |
| dm1_orn_150Hz | 720575940630448860 | KCab | Kenyon_Cell | True | 82.22 | 0.02 |
| dm1_orn_150Hz | 720575940637132389 | DPM | MBIN | False | 300.4 | 0.0 |
| dm1_orn_150Hz | 720575940623495827 | DPM | MBIN | False | 266.39 | 0.0 |
| dm1_orn_150Hz | 720575940630496374 | MBON05 | MBON | False | 255.41 | 0.0 |
| dm1_orn_150Hz | 720575940623201833 | MBON11 | MBON | False | 250.37 | 0.0 |
| dm1_orn_150Hz | 720575940638028607 | MBON06 | MBON | False | 239.79 | 0.0 |
| dm1_orn_150Hz | 720575940617749538 | MBON11 | MBON | False | 235.29 | 0.0 |
| dm1_orn_150Hz | 720575940621164720 | MBON05 | MBON | False | 225.96 | 0.0 |
| dm1_orn_150Hz | 720575940621040737 | PPL101 | DAN | False | 221.96 | 0.0 |
| dm1_orn_150Hz | 720575940628779563 | MBON09 | MBON | False | 237.2 | 22.63 |
| dm1_orn_150Hz | 720575940617691170 | PPL101 | DAN | False | 213.67 | 0.0 |