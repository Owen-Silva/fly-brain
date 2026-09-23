"""Why do 19 of 90 Ir94e trials differ from the stored al_ln_literature run, by the
same amount at junction strength 0.5x, 1x and 2x?

Re-runs a few Ir94e trials (seed 0) on one brain with: the old engine, the new
engine at strength 0, 1 and 2, and prints total spikes (and spikes of coupled cells) next to the stored numbers.
Writes results/check_ir94e.txt.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_validation as V  # noqa: E402

TRIALS = [0, 10, 12, 17, 20]
COND = "ir94e_200Hz"


def main():
    V.C.wait_for_ram(2.0)
    brain = V.G.build_gap_brain("al_ln_literature", n_threads=2)
    lab = V.S.neuron_table(brain.root_ids)
    sets = V.C.input_sets(lab)
    rd = V.C.Readout(brain, lab)
    excite = V.excite_for(COND, sets)
    seed = V.base_seed(COND)
    stored = pd.read_csv(ROOT_SIGNS)
    stored = stored[(stored.config == "al_ln_literature") & (stored.condition == COND)
                    & (stored.seed == seed)].set_index("trial").total_spikes
    mine = pd.read_csv(V.TRIALS_CSV)
    mine = mine[(mine.config == "gap_x1") & (mine.condition == COND)
                & (mine.seed == seed)].set_index("trial").total_spikes
    coupled = np.unique(np.r_[brain.gap_a, brain.gap_b])
    runs = [("old engine", True, 1.0), ("new, strength 0", False, 0.0),
            ("new, strength 1", False, 1.0), ("new, strength 2", False, 2.0)]
    lines = [f"{COND}, seed {seed}: total spikes per trial",
             "(in brackets: spikes of the 379 coupled cells)",
             "trial | stored al_ln | stored gap_x1 | " + " | ".join(r[0] for r in runs)]
    for t in TRIALS:
        got = []
        for _, base, scale in runs:
            brain._use_baseline_engine = base
            brain.gap_scale = scale
            res = V.C.run_chunk(brain, excite, seed, t, t + 1)
            rows, _ = V.C.trial_rows(res, rd, dict(config="x", scale=scale, condition=COND,
                                                   seed_index=0, seed=seed, trial0=t))
            n_cpl = int(np.isin(res.neuron, coupled).sum())
            got.append(f'{int(rows[0]["total_spikes"])} ({n_cpl})')
        lines.append(f"{t} | {stored.get(t)} | {mine.get(t)} | " + " | ".join(map(str, got)))
        print(lines[-1], flush=True)
    (HERE / "results" / "check_ir94e.txt").write_text("\n".join(lines) + "\n")


ROOT_SIGNS = HERE.parents[1] / "experiments" / "phase7_signs" / "results" / "trials.csv"

if __name__ == "__main__":
    main()
