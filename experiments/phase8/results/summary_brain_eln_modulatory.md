# Phase 8 summary: brain_fix_modulatory

Change = after / before - 1, mean over seeds (sd). Score = change(CS+) - change(CS-).

| condition | read-out | measure | seeds | CS+ change | CS- change | score (min..max) | all seeds < 0 | CS+ net of no-training | CS- net | net score (min..max) |
|---|---|---|---|---|---|---|---|---|---|---|
| aversive_paired | MBON11 | drive | 3 | -100.0% (0.0%) | -99.7% (0.2%) | -0.3% (-0.5%..-0.1%) | yes | -0.0% (0.0%) | -0.1% (0.1%) | +0.1% (+0.0%..+0.2%) |
| aversive_paired | MBON11 | spikes | 0 | -100.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| aversive_unpaired | MBON11 | drive | 3 | -100.0% (0.0%) | -99.7% (0.3%) | -0.3% (-0.6%..-0.1%) | yes | -0.0% (0.0%) | -0.1% (0.0%) | +0.0% (+0.0%..+0.0%) |
| aversive_unpaired | MBON11 | spikes | 0 | -100.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| odor_only | MBON11 | drive | 3 | -100.0% (0.0%) | -99.7% (0.2%) | -0.3% (-0.5%..-0.1%) | yes | -0.0% (0.0%) | -0.1% (0.1%) | +0.1% (+0.0%..+0.2%) |
| odor_only | MBON11 | spikes | 0 | -100.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| no_training | MBON11 | drive | 3 | -100.0% (0.0%) | -99.6% (0.3%) | -0.4% (-0.7%..-0.2%) | yes | +0.0% (0.0%) | +0.0% (0.0%) | +0.0% (+0.0%..+0.0%) |
| no_training | MBON11 | spikes | 0 | -100.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) | no | +0.0% (0.0%) | +nan% (nan%) | +nan% (+nan%..+nan%) |
| appetitive_paired | MBON01 | drive | 3 | -99.8% (0.1%) | -93.3% (0.6%) | -6.4% (-6.9%..-5.9%) | yes | -100.4% (0.3%) | -93.7% (1.1%) | -6.7% (-7.5%..-6.0%) |
| appetitive_paired | MBON01 | spikes | 0 | +nan% (nan%) | -100.0% (0.0%) | +nan% (+nan%..+nan%) | no | +nan% (nan%) | -105.6% (15.8%) | +nan% (+nan%..+nan%) |

## Approach minus avoidance (relative change of summed KC drive of MBON11+12 minus that of MBON01-04; 'net' = minus the no-training control)

| condition | role | approach_mean | approach_std | avoid_mean | avoid_std | valence_mean | valence_std | valence_net_mean | valence_net_std |
|---|---|---|---|---|---|---|---|---|---|
| appetitive_paired | CS+ | -0.417 | 0.002 | -0.994 | 0.001 | 0.576 | 0.003 | 0.798 | 0.001 |
| appetitive_paired | CS- | -0.066 | 0.008 | -0.871 | 0.004 | 0.804 | 0.008 | 0.825 | 0.008 |
| aversive_paired | CS+ | -0.417 | 0.003 | -0.198 | 0.001 | -0.220 | 0.003 | 0.002 | 0.000 |
| aversive_paired | CS- | -0.065 | 0.006 | -0.049 | 0.007 | -0.016 | 0.001 | 0.005 | 0.002 |
| aversive_unpaired | CS+ | -0.417 | 0.003 | -0.198 | 0.001 | -0.220 | 0.002 | 0.002 | 0.000 |
| aversive_unpaired | CS- | -0.066 | 0.007 | -0.048 | 0.007 | -0.017 | 0.001 | 0.004 | 0.001 |
| no_training | CS+ | -0.417 | 0.003 | -0.195 | 0.001 | -0.222 | 0.002 | 0.000 | 0.000 |
| no_training | CS- | -0.066 | 0.007 | -0.045 | 0.006 | -0.021 | 0.002 | 0.000 | 0.000 |
| odor_only | CS+ | -0.417 | 0.003 | -0.198 | 0.001 | -0.220 | 0.003 | 0.002 | 0.000 |
| odor_only | CS- | -0.065 | 0.006 | -0.049 | 0.007 | -0.016 | 0.001 | 0.005 | 0.002 |

## KC fraction active in test trials

| odor | mean | std |
|---|---|---|
| A | 0.222 | 0.003 |
| B | 0.189 | 0.002 |

## Mean relative KC->MBON weight at the end, types that moved > 1%

| mbon_type | appetitive_paired | aversive_paired | aversive_unpaired | no_training | odor_only |
|---|---|---|---|---|---|
| MBON01 | 0.693 | 1.000 | 1.000 | 1.000 | 1.000 |
| MBON02 | 0.808 | 0.808 | 0.809 | 0.810 | 0.808 |
| MBON04 | 0.915 | 0.914 | 0.914 | 0.917 | 0.914 |
| MBON05 | 0.639 | 0.639 | 0.639 | 0.645 | 0.639 |
| MBON06 | 0.795 | 0.795 | 0.796 | 0.797 | 0.795 |
| MBON11 | 0.634 | 0.633 | 0.634 | 0.636 | 0.633 |
| MBON14 | 0.767 | 0.767 | 0.767 | 0.770 | 0.767 |
| MBON16 | 0.990 | 0.990 | 0.990 | 0.990 | 0.990 |
| MBON19 | 0.986 | 0.986 | 0.986 | 0.986 | 0.986 |
| MBON20 | 0.632 | 0.631 | 0.633 | 0.637 | 0.631 |
| MBON21 | 0.606 | 0.610 | 0.610 | 0.617 | 0.610 |
| MBON24 | 0.753 | 0.769 | 0.770 | 0.772 | 0.769 |
| MBON25,MBON34 | 0.535 | 0.536 | 0.538 | 0.540 | 0.536 |
| MBON27 | 0.898 | 1.000 | 1.000 | 1.000 | 1.000 |
| MBON28 | 0.983 | 0.983 | 0.982 | 0.983 | 0.983 |
| MBON29 | 0.556 | 0.560 | 0.561 | 0.568 | 0.560 |
| MBON30 | 0.545 | 0.544 | 0.545 | 0.549 | 0.544 |
