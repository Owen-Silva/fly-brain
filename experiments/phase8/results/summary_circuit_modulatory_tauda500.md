# Phase 8 summary: circuit_modulatory_tauda500

Change = after / before - 1, mean over seeds (sd). Score = change(CS+) - change(CS-).

| condition | read-out | measure | seeds | CS+ change | CS- change | score (min..max) | all seeds < 0 | CS+ net of no-training | CS- net | net score (min..max) |
|---|---|---|---|---|---|---|---|---|---|---|
| aversive_paired | MBON11 | drive | 5 | -93.0% (2.0%) | -5.0% (12.3%) | -88.1% (-107.9%..-76.7%) | yes | -91.3% (5.5%) | -8.6% (2.0%) | -82.7% (-87.5%..-75.1%) |
| aversive_unpaired | MBON11 | drive | 5 | -1.6% (6.4%) | +3.6% (13.7%) | -5.2% (-21.3%..+10.5%) | no | +0.1% (0.4%) | +0.0% (0.0%) | +0.1% (-0.3%..+0.7%) |
| aversive_backward | MBON11 | drive | 5 | -60.6% (7.1%) | +0.4% (13.6%) | -61.0% (-73.1%..-45.9%) | yes | -58.9% (7.7%) | -3.2% (0.7%) | -55.7% (-66.8%..-47.7%) |
| no_training | MBON11 | drive | 5 | -1.7% (6.4%) | +3.6% (13.7%) | -5.3% (-22.0%..+10.8%) | no | +0.0% (0.0%) | +0.0% (0.0%) | +0.0% (+0.0%..+0.0%) |

## Approach minus avoidance (relative change of summed KC drive of MBON11+12 minus that of MBON01-04; 'net' = minus the no-training control)

| condition | role | approach_mean | approach_std | avoid_mean | avoid_std | valence_mean | valence_std | valence_net_mean | valence_net_std |
|---|---|---|---|---|---|---|---|---|---|
| aversive_backward | CS+ | -0.556 | 0.067 | -0.019 | 0.063 | -0.537 | 0.078 | -0.533 | 0.070 |
| aversive_backward | CS- | 0.002 | 0.133 | 0.041 | 0.149 | -0.039 | 0.026 | -0.028 | 0.006 |
| aversive_paired | CS+ | -0.850 | 0.019 | -0.019 | 0.063 | -0.831 | 0.053 | -0.827 | 0.052 |
| aversive_paired | CS- | -0.044 | 0.121 | 0.041 | 0.149 | -0.085 | 0.036 | -0.073 | 0.017 |
| aversive_unpaired | CS+ | -0.021 | 0.061 | -0.019 | 0.063 | -0.003 | 0.011 | 0.001 | 0.001 |
| aversive_unpaired | CS- | 0.029 | 0.133 | 0.041 | 0.149 | -0.012 | 0.024 | 0.000 | 0.000 |
| no_training | CS+ | -0.022 | 0.060 | -0.019 | 0.063 | -0.004 | 0.012 | 0.000 | 0.000 |
| no_training | CS- | 0.029 | 0.133 | 0.041 | 0.149 | -0.012 | 0.024 | 0.000 | 0.000 |

## KC fraction active in test trials

| odor | mean | std |
|---|---|---|
| A | 0.054 | 0.005 |
| B | 0.043 | 0.007 |

## Mean relative KC->MBON weight at the end, types that moved > 1%

| mbon_type | aversive_backward | aversive_paired | aversive_unpaired | no_training |
|---|---|---|---|---|
| MBON11 | 0.976 | 0.944 | 1.000 | 1.000 |
| MBON14 | 0.983 | 0.983 | 0.983 | 0.984 |
| MBON20 | 0.996 | 0.983 | 1.000 | 1.000 |
| MBON25,MBON34 | 0.993 | 0.971 | 1.000 | 1.000 |
| MBON30 | 0.996 | 0.980 | 1.000 | 1.000 |
