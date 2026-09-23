# Phase 8 summary: brain_ln53_modulatory

Change = after / before - 1, mean over seeds (sd). Score = change(CS+) - change(CS-).

| condition | read-out | measure | seeds | CS+ change | CS- change | score (min..max) | all seeds < 0 | CS+ net of no-training | CS- net | net score (min..max) |
|---|---|---|---|---|---|---|---|---|---|---|
| aversive_paired | MBON11 | drive | 3 | -99.8% (0.0%) | -99.7% (0.1%) | -0.1% (-0.3%..+0.0%) | no | -0.1% (0.1%) | -0.2% (0.2%) | +0.1% (+0.0%..+0.3%) |
| aversive_paired | MBON11 | spikes | 0 | -100.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| aversive_unpaired | MBON11 | drive | 3 | -99.8% (0.0%) | -99.7% (0.1%) | -0.1% (-0.2%..+0.0%) | no | -0.0% (0.0%) | -0.1% (0.2%) | +0.1% (-0.1%..+0.3%) |
| aversive_unpaired | MBON11 | spikes | 0 | -100.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| aversive_backward | MBON11 | drive | 3 | -99.8% (0.0%) | -99.7% (0.1%) | -0.1% (-0.2%..+0.1%) | no | -0.0% (0.0%) | -0.2% (0.2%) | +0.1% (+0.0%..+0.3%) |
| aversive_backward | MBON11 | spikes | 0 | -100.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| odor_only | MBON11 | drive | 3 | -99.8% (0.0%) | -99.7% (0.1%) | -0.1% (-0.2%..+0.1%) | no | -0.0% (0.0%) | -0.2% (0.2%) | +0.1% (+0.0%..+0.3%) |
| odor_only | MBON11 | spikes | 0 | -100.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| dan_only | MBON11 | drive | 3 | -99.8% (0.1%) | -99.6% (0.1%) | -0.2% (-0.3%..-0.1%) | yes | +0.0% (0.0%) | +0.0% (0.0%) | +0.0% (+0.0%..+0.0%) |
| dan_only | MBON11 | spikes | 0 | -100.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| no_training | MBON11 | drive | 3 | -99.8% (0.1%) | -99.6% (0.1%) | -0.2% (-0.3%..-0.1%) | yes | +0.0% (0.0%) | +0.0% (0.0%) | +0.0% (+0.0%..+0.0%) |
| no_training | MBON11 | spikes | 0 | -100.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (nan%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| appetitive_paired | MBON01 | drive | 3 | -98.4% (0.4%) | -6.2% (1.0%) | -92.2% (-93.5%..-91.2%) | yes | -97.4% (3.1%) | -5.8% (1.1%) | -91.6% (-95.1%..-86.9%) |

## Approach minus avoidance (relative change of summed KC drive of MBON11+12 minus that of MBON01-04; 'net' = minus the no-training control)

| condition | role | approach_mean | approach_std | avoid_mean | avoid_std | valence_mean | valence_std | valence_net_mean | valence_net_std |
|---|---|---|---|---|---|---|---|---|---|
| appetitive_paired | CS+ | -0.711 | 0.011 | -0.152 | 0.021 | -0.558 | 0.010 | 0.128 | 0.000 |
| appetitive_paired | CS- | -0.574 | 0.002 | -0.064 | 0.011 | -0.511 | 0.010 | 0.029 | 0.018 |
| aversive_backward | CS+ | -0.711 | 0.011 | -0.025 | 0.023 | -0.685 | 0.012 | 0.002 | 0.002 |
| aversive_backward | CS- | -0.573 | 0.002 | -0.044 | 0.006 | -0.529 | 0.007 | 0.011 | 0.019 |
| aversive_paired | CS+ | -0.711 | 0.011 | -0.025 | 0.023 | -0.685 | 0.013 | 0.001 | 0.002 |
| aversive_paired | CS- | -0.573 | 0.002 | -0.044 | 0.006 | -0.529 | 0.007 | 0.011 | 0.019 |
| aversive_unpaired | CS+ | -0.711 | 0.011 | -0.025 | 0.023 | -0.685 | 0.012 | 0.001 | 0.002 |
| aversive_unpaired | CS- | -0.566 | 0.008 | -0.035 | 0.014 | -0.532 | 0.007 | 0.007 | 0.024 |
| dan_only | CS+ | -0.710 | 0.010 | -0.023 | 0.020 | -0.687 | 0.010 | 0.000 | 0.000 |
| dan_only | CS- | -0.566 | 0.004 | -0.027 | 0.028 | -0.539 | 0.025 | 0.000 | 0.000 |
| no_training | CS+ | -0.710 | 0.010 | -0.023 | 0.020 | -0.687 | 0.010 | 0.000 | 0.000 |
| no_training | CS- | -0.566 | 0.004 | -0.027 | 0.028 | -0.539 | 0.025 | 0.000 | 0.000 |
| odor_only | CS+ | -0.711 | 0.011 | -0.025 | 0.023 | -0.685 | 0.012 | 0.002 | 0.002 |
| odor_only | CS- | -0.573 | 0.002 | -0.044 | 0.006 | -0.529 | 0.007 | 0.011 | 0.019 |

## KC fraction active in test trials

| odor | mean | std |
|---|---|---|
| A | 0.053 | 0.001 |
| B | 0.044 | 0.002 |

## Mean relative KC->MBON weight at the end, types that moved > 1%

| mbon_type | appetitive_paired | aversive_backward | aversive_paired | aversive_unpaired | dan_only | no_training | odor_only |
|---|---|---|---|---|---|---|---|
| MBON01 | 0.975 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| MBON05 | 0.938 | 0.938 | 0.938 | 0.937 | 0.939 | 0.939 | 0.938 |
| MBON11 | 0.875 | 0.875 | 0.874 | 0.874 | 0.875 | 0.875 | 0.875 |
| MBON14 | 0.898 | 0.898 | 0.898 | 0.898 | 0.900 | 0.900 | 0.898 |
| MBON20 | 0.924 | 0.924 | 0.924 | 0.924 | 0.924 | 0.924 | 0.924 |
| MBON21 | 0.930 | 0.934 | 0.934 | 0.933 | 0.935 | 0.935 | 0.934 |
| MBON25,MBON34 | 0.888 | 0.889 | 0.889 | 0.888 | 0.888 | 0.888 | 0.889 |
| MBON29 | 0.924 | 0.928 | 0.928 | 0.927 | 0.929 | 0.929 | 0.928 |
| MBON30 | 0.905 | 0.905 | 0.905 | 0.905 | 0.905 | 0.905 | 0.905 |
