# Phase 8 summary: brain_alln_modulatory

Change = after / before - 1, mean over seeds (sd). Score = change(CS+) - change(CS-).

| condition | read-out | measure | seeds | CS+ change | CS- change | score (min..max) | all seeds < 0 | CS+ net of no-training | CS- net | net score (min..max) |
|---|---|---|---|---|---|---|---|---|---|---|
| aversive_paired | MBON11 | drive | 3 | -99.8% (0.1%) | -99.6% (0.1%) | -0.2% (-0.4%..-0.0%) | yes | -0.1% (0.0%) | -0.0% (0.2%) | -0.1% (-0.3%..+0.1%) |
| aversive_unpaired | MBON11 | drive | 3 | -99.8% (0.1%) | -99.4% (0.2%) | -0.4% (-0.6%..-0.2%) | yes | -0.1% (0.1%) | +0.2% (0.1%) | -0.3% (-0.5%..-0.1%) |
| aversive_backward | MBON11 | drive | 3 | -99.8% (0.1%) | -99.6% (0.1%) | -0.2% (-0.4%..-0.0%) | yes | -0.1% (0.0%) | -0.0% (0.2%) | -0.1% (-0.2%..+0.1%) |
| odor_only | MBON11 | drive | 3 | -99.8% (0.1%) | -99.6% (0.1%) | -0.2% (-0.4%..-0.0%) | yes | -0.1% (0.0%) | -0.0% (0.2%) | -0.1% (-0.2%..+0.1%) |
| dan_only | MBON11 | drive | 3 | -99.7% (0.1%) | -99.6% (0.1%) | -0.1% (-0.2%..+0.0%) | no | +0.0% (0.0%) | +0.0% (0.0%) | +0.0% (+0.0%..+0.0%) |
| no_training | MBON11 | drive | 3 | -99.7% (0.1%) | -99.6% (0.1%) | -0.1% (-0.2%..+0.0%) | no | +0.0% (0.0%) | +0.0% (0.0%) | +0.0% (+0.0%..+0.0%) |
| appetitive_paired | MBON01 | drive | 3 | -98.5% (0.6%) | -4.1% (0.4%) | -94.4% (-95.3%..-93.8%) | yes | -97.5% (3.1%) | -4.6% (1.1%) | -92.9% (-97.7%..-90.0%) |

## Approach minus avoidance (relative change of summed KC drive of MBON11+12 minus that of MBON01-04; 'net' = minus the no-training control)

| condition | role | approach_mean | approach_std | avoid_mean | avoid_std | valence_mean | valence_std | valence_net_mean | valence_net_std |
|---|---|---|---|---|---|---|---|---|---|
| appetitive_paired | CS+ | -0.705 | 0.011 | -0.147 | 0.015 | -0.558 | 0.004 | 0.128 | 0.003 |
| appetitive_paired | CS- | -0.580 | 0.010 | -0.029 | 0.008 | -0.551 | 0.002 | 0.014 | 0.002 |
| aversive_backward | CS+ | -0.705 | 0.011 | -0.020 | 0.017 | -0.685 | 0.006 | 0.001 | 0.003 |
| aversive_backward | CS- | -0.578 | 0.013 | -0.008 | 0.019 | -0.570 | 0.014 | -0.006 | 0.012 |
| aversive_paired | CS+ | -0.705 | 0.011 | -0.020 | 0.017 | -0.685 | 0.006 | 0.001 | 0.003 |
| aversive_paired | CS- | -0.578 | 0.013 | -0.008 | 0.019 | -0.570 | 0.014 | -0.006 | 0.012 |
| aversive_unpaired | CS+ | -0.707 | 0.013 | -0.025 | 0.021 | -0.682 | 0.008 | 0.004 | 0.005 |
| aversive_unpaired | CS- | -0.575 | 0.006 | -0.016 | 0.007 | -0.560 | 0.001 | 0.005 | 0.005 |
| dan_only | CS+ | -0.706 | 0.012 | -0.020 | 0.019 | -0.685 | 0.008 | 0.000 | 0.000 |
| dan_only | CS- | -0.576 | 0.009 | -0.011 | 0.006 | -0.565 | 0.004 | 0.000 | 0.000 |
| no_training | CS+ | -0.706 | 0.012 | -0.020 | 0.019 | -0.685 | 0.008 | 0.000 | 0.000 |
| no_training | CS- | -0.576 | 0.009 | -0.011 | 0.006 | -0.565 | 0.004 | 0.000 | 0.000 |
| odor_only | CS+ | -0.705 | 0.011 | -0.020 | 0.017 | -0.685 | 0.006 | 0.001 | 0.003 |
| odor_only | CS- | -0.578 | 0.013 | -0.008 | 0.019 | -0.570 | 0.014 | -0.006 | 0.012 |

## KC fraction active in test trials

| odor | mean | std |
|---|---|---|
| A | 0.048 | 0.002 |
| B | 0.042 | 0.002 |

## Mean relative KC->MBON weight at the end, types that moved > 1%

| mbon_type | appetitive_paired | aversive_backward | aversive_paired | aversive_unpaired | dan_only | no_training | odor_only |
|---|---|---|---|---|---|---|---|
| MBON01 | 0.978 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| MBON05 | 0.948 | 0.948 | 0.948 | 0.948 | 0.949 | 0.949 | 0.948 |
| MBON11 | 0.880 | 0.880 | 0.880 | 0.879 | 0.880 | 0.880 | 0.880 |
| MBON14 | 0.906 | 0.905 | 0.905 | 0.907 | 0.909 | 0.909 | 0.905 |
| MBON20 | 0.932 | 0.931 | 0.931 | 0.932 | 0.932 | 0.932 | 0.931 |
| MBON21 | 0.939 | 0.944 | 0.944 | 0.944 | 0.946 | 0.946 | 0.944 |
| MBON25,MBON34 | 0.897 | 0.897 | 0.897 | 0.896 | 0.897 | 0.897 | 0.897 |
| MBON29 | 0.936 | 0.943 | 0.943 | 0.942 | 0.944 | 0.944 | 0.943 |
| MBON30 | 0.915 | 0.915 | 0.914 | 0.914 | 0.916 | 0.916 | 0.915 |
