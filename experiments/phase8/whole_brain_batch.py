"""Run all whole-brain Phase 8 jobs one after another in ONE process
(only one whole brain in memory at a time; results saved as they come, and
every stage resumes where it stopped).

Stages (python whole_brain_batch.py <stage> [<stage> ...]):
  reg_<model>  Phase 3 regression (sugar -> MN9, learning on, no training)
  alln         conditioning, recommended fix "al_ln_literature" (MAIN, since 2026-09-23)
  eln          conditioning, "eln_electrical" (recommended on 2026-09-22, since superseded)
  none         conditioning, the published brain, no fix
  ln53         conditioning, Phase 5 "LN-fix" (comparison only; the audit found it wrong
               for 34 cells)
Model names are in common.WHOLE_BRAINS.
"""

import gc
import sys

from run_phase8 import conditioning, regression

SEEDS = [0, 1, 2]
CONDS = ["aversive_paired", "aversive_unpaired", "aversive_backward", "odor_only", "dan_only",
         "no_training", "appetitive_paired"]
# eln_electrical turned out to stay in runaway activity with these odors (every condition
# collapses to ~-100% for both odors), so its run was cut to 5 conditions (2026-09-22).
CONDS_ELN = ["aversive_paired", "aversive_unpaired", "odor_only", "no_training",
             "appetitive_paired"]
# The published brain runs away too and each sequence takes ~10 min, so only the paired
# run and the no-training control (2026-09-23).
CONDS_NONE = ["aversive_paired", "no_training"]

STAGES = {
    "alln": ("brain_alln", CONDS),
    "eln": ("brain_eln", CONDS_ELN),
    "none": ("brain_none", CONDS_NONE),
    "ln53": ("brain_ln53", CONDS),
}

stages = sys.argv[1:] or ["reg_alln", "alln", "reg_none", "none"]
for st in stages:
    print(f"=== stage {st} ===", flush=True)
    if st.startswith("reg_"):
        regression("brain_" + st[4:])
    else:
        model, conds = STAGES[st]
        conditioning(model, "modulatory", SEEDS, conds)
    gc.collect()
print("WHOLE_BRAIN_BATCH_DONE", flush=True)
