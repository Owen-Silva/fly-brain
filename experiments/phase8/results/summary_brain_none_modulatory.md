# Phase 8 summary: brain_none_modulatory

Change = after / before - 1, mean over seeds (sd). Score = change(CS+) - change(CS-).

| condition | read-out | measure | seeds | CS+ change | CS- change | score (min..max) | all seeds < 0 | CS+ net of no-training | CS- net | net score (min..max) |
|---|---|---|---|---|---|---|---|---|---|---|
| aversive_paired | MBON11 | drive | 3 | -100.0% (0.0%) | -97.3% (1.9%) | -2.7% (-4.9%..-1.3%) | yes | -0.0% (0.0%) | +0.3% (1.0%) | -0.3% (-1.3%..+0.7%) |
| aversive_paired | MBON11 | spikes | 0 | -100.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| no_training | MBON11 | drive | 3 | -100.0% (0.0%) | -97.6% (1.0%) | -2.4% (-3.6%..-1.6%) | yes | +0.0% (0.0%) | +0.0% (0.0%) | +0.0% (+0.0%..+0.0%) |
| no_training | MBON11 | spikes | 0 | -100.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) |

## Approach minus avoidance (relative change of summed KC drive of MBON11+12 minus that of MBON01-04; 'net' = minus the no-training control)

| condition | role | approach_mean | approach_std | avoid_mean | avoid_std | valence_mean | valence_std | valence_net_mean | valence_net_std |
|---|---|---|---|---|---|---|---|---|---|
| aversive_paired | CS+ | -1.000 | 0.000 | -0.999 | 0.000 | -0.001 | 0.000 | 0.001 | 0.000 |
| aversive_paired | CS- | -0.975 | 0.019 | -0.961 | 0.005 | -0.015 | 0.023 | 0.042 | 0.005 |
| no_training | CS+ | -1.000 | 0.000 | -0.999 | 0.000 | -0.001 | 0.000 | 0.000 | 0.000 |
| no_training | CS- | -0.979 | 0.007 | -0.923 | 0.012 | -0.056 | 0.018 | 0.000 | 0.000 |

## KC fraction active in test trials

| odor | mean | std |
|---|---|---|
| A | 0.618 | 0.002 |
| B | 0.617 | 0.001 |

## Mean relative KC->MBON weight at the end, types that moved > 1%

| mbon_type | aversive_paired | no_training |
|---|---|---|
| MBON01 | 0.267 | 0.267 |
| MBON02 | 0.355 | 0.356 |
| MBON03 | 0.990 | 0.990 |
| MBON04 | 0.762 | 0.763 |
| MBON05 | 0.201 | 0.202 |
| MBON06 | 0.360 | 0.362 |
| MBON07 | 0.306 | 0.307 |
| MBON09 | 0.445 | 0.446 |
| MBON11 | 0.191 | 0.191 |
| MBON12 | 0.611 | 0.612 |
| MBON13 | 0.990 | 0.990 |
| MBON14 | 0.289 | 0.290 |
| MBON15-like | 0.988 | 0.988 |
| MBON16 | 0.978 | 0.978 |
| MBON17 | 0.989 | 0.989 |
| MBON18 | 0.260 | 0.261 |
| MBON19 | 0.929 | 0.929 |
| MBON20 | 0.241 | 0.242 |
| MBON21 | 0.138 | 0.139 |
| MBON23 | 0.365 | 0.367 |
| MBON24 | 0.300 | 0.301 |
| MBON25,MBON34 | 0.080 | 0.083 |
| MBON27 | 0.742 | 0.742 |
| MBON28 | 0.963 | 0.963 |
| MBON29 | 0.085 | 0.085 |
| MBON30 | 0.098 | 0.099 |
| MBON31 | 0.971 | 0.971 |
| MBON32 | 0.335 | 0.336 |
| MBON33 | 0.573 | 0.574 |
| MBON35 | 0.324 | 0.325 |
