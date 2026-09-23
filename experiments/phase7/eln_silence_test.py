"""Are the NEW runaways of tuned upgrade 2 the same antennal-lobe loop?

With conductance synapses and every synapse 2x stronger (U2_cond_tuned), the
brain runs away even with water or bitter alone (never in the baseline). Phase 6
showed every baseline runaway starts at the antennal-lobe excitatory local
neurons (eLNs, lLN1_b/c + lLN2T_a-c; same definition as
experiments/phase6/runaway/s3b_lesions.py, read only). Here the same trials
(same seed, so the same input spikes) are re-run with those eLNs silenced.
If the runaways vanish, the upgrade made the existing eLN loop easier to set
off; if they remain, the upgrade created a new unstable loop of its own.
Writes results/eln_silence_test.csv.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from sim.realism import REALISM_DEFAULTS, RealisticBrain  # noqa: E402
from run_phase7 import CONDITIONS, MN9_CONTRA, SETS, wait_for_ram  # noqa: E402

RES = HERE / "results"
LABELS = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"
CASES = [("water_200Hz", 0), ("bitter_200Hz", 1)]   # (condition, seed index) with runaways


def main():
    scale = next(iter(json.loads((RES / "U2_fit.json").read_text()).values()))["scale"]
    wait_for_ram()
    brain = RealisticBrain(snapshot="630", n_threads=2)
    brain.set_realism(**dict(REALISM_DEFAULTS, conductance=True, E_inh_mV=-60.0,
                             cond_weight_scale=scale))
    lab = pd.read_parquet(LABELS, columns=["root_id", "cell_class", "hemibrain_type"])
    lab = lab.set_index("root_id").reindex(brain.root_ids)
    cc = lab.cell_class.astype(object).fillna("").to_numpy()
    ht = lab.hemibrain_type.astype(object).fillna("").to_numpy()
    eln = brain.root_ids[(cc == "ALLN") & np.isin(ht, ["lLN1_b,lLN1_c", "lLN2T_a",
                                                      "lLN2T_b", "lLN2T_c"])]
    mn9 = brain.index_of([MN9_CONTRA])[0]
    rows = []
    for cond, k in CASES:
        inputs, base_seed = CONDITIONS[cond]
        excite = {int(i): float(r) for s, r in inputs for i in SETS[s]}
        base = np.concatenate([np.load(f)["per_trial_total"]
                               for f in sorted((RES / "baseline").glob(f"{cond}_s*.npz"))])
        bar = 5 * np.median(base)
        intact = np.load(RES / "U2_cond_tuned" / f"{cond}_s{k}.npz")
        res = brain.run(excite=excite, silence=eln, duration_ms=1000.0, n_trials=30,
                        seed=base_seed + k)
        tot = np.bincount(res.trial, minlength=30)
        m = np.bincount(res.trial[res.neuron == mn9], minlength=30)
        rows.append(dict(condition=cond, seed=base_seed + k, n_eln_silenced=len(eln),
                         runaway_intact=int((intact["per_trial_total"] > bar).sum()),
                         runaway_eln_silenced=int((tot > bar).sum()),
                         mn9_hz_intact=float(intact["mn9"][0].mean()),
                         mn9_hz_eln_silenced=float(m.mean()),
                         median_spikes_intact=float(np.median(intact["per_trial_total"])),
                         median_spikes_eln_silenced=float(np.median(tot))))
        pd.DataFrame(rows).to_csv(RES / "eln_silence_test.csv", index=False)
        print(rows[-1], flush=True)
        del res


if __name__ == "__main__":
    main()
