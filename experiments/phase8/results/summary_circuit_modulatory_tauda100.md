# Phase 8 summary: circuit_modulatory_tauda100

Change = after / before - 1, mean over seeds (sd). Score = change(CS+) - change(CS-).

| condition | read-out | measure | seeds | CS+ change | CS- change | score (min..max) | all seeds < 0 | CS+ net of no-training | CS- net | net score (min..max) |
|---|---|---|---|---|---|---|---|---|---|---|
| aversive_paired | MBON11 | drive | 5 | -93.0% (1.5%) | -4.9% (12.6%) | -88.1% (-107.6%..-77.2%) | yes | -91.4% (5.8%) | -8.5% (1.6%) | -82.9% (-88.2%..-74.8%) |
| aversive_unpaired | MBON11 | drive | 5 | -1.5% (6.6%) | +3.6% (13.7%) | -5.1% (-21.2%..+11.0%) | no | +0.1% (0.2%) | -0.0% (0.1%) | +0.1% (-0.2%..+0.5%) |
| aversive_backward | MBON11 | drive | 5 | -2.0% (6.4%) | +3.6% (13.8%) | -5.6% (-21.5%..+10.0%) | no | -0.5% (0.6%) | -0.0% (0.0%) | -0.5% (-1.1%..+0.2%) |
| no_training | MBON11 | drive | 5 | -1.5% (6.6%) | +3.6% (13.8%) | -5.2% (-21.7%..+11.0%) | no | +0.0% (0.0%) | +0.0% (0.0%) | +0.0% (+0.0%..+0.0%) |

## Approach minus avoidance (relative change of summed KC drive of MBON11+12 minus that of MBON01-04; 'net' = minus the no-training control)

| condition | role | approach_mean | approach_std | avoid_mean | avoid_std | valence_mean | valence_std | valence_net_mean | valence_net_std |
|---|---|---|---|---|---|---|---|---|---|
| aversive_backward | CS+ | -0.024 | 0.061 | -0.018 | 0.063 | -0.006 | 0.012 | -0.003 | 0.002 |
| aversive_backward | CS- | 0.029 | 0.134 | 0.041 | 0.150 | -0.012 | 0.025 | -0.000 | 0.000 |
| aversive_paired | CS+ | -0.850 | 0.016 | -0.018 | 0.062 | -0.832 | 0.053 | -0.829 | 0.052 |
| aversive_paired | CS- | -0.043 | 0.124 | 0.041 | 0.149 | -0.085 | 0.034 | -0.073 | 0.014 |
| aversive_unpaired | CS+ | -0.019 | 0.063 | -0.017 | 0.064 | -0.003 | 0.011 | 0.000 | 0.001 |
| aversive_unpaired | CS- | 0.029 | 0.133 | 0.041 | 0.149 | -0.012 | 0.024 | 0.000 | 0.000 |
| no_training | CS+ | -0.020 | 0.063 | -0.017 | 0.065 | -0.003 | 0.011 | 0.000 | 0.000 |
| no_training | CS- | 0.029 | 0.134 | 0.041 | 0.150 | -0.012 | 0.025 | 0.000 | 0.000 |

## KC fraction active in test trials

| odor | mean | std |
|---|---|---|
| A | 0.054 | 0.005 |
| B | 0.043 | 0.007 |

## Mean relative KC->MBON weight at the end, types that moved > 1%

| mbon_type | aversive_backward | aversive_paired | aversive_unpaired | no_training |
|---|---|---|---|---|
| MBON11 | 1.000 | 0.944 | 1.000 | 1.000 |
| MBON14 | 0.984 | 0.984 | 0.984 | 0.985 |
| MBON20 | 1.000 | 0.982 | 1.000 | 1.000 |
| MBON25,MBON34 | 1.000 | 0.970 | 1.000 | 1.000 |
| MBON30 | 1.000 | 0.980 | 1.000 | 1.000 |
