"""Does an upgrade remove the runaway loop, or only make it harder to set off?

Background (docs/phase6-runaway-activity.md): in the baseline model every
runaway starts at about 40 antennal-lobe "excitatory local neurons" (eLNs,
types lLN1_b/c and lLN2T_a-c). Whether they are really excitatory is disputed
(FlyWire says acetylcholine; the olfaction lane says GABA). Two "forced"
triggers ignite the baseline model EVERY time (Phase 6, lesion_population.csv):
10 DM1 smell neurons firing once (445,000 spikes), and the eLNs firing once
(665,000 spikes). Neither needs any random input, so each is one exact run.

If an upgrade lowers the runaway RATE in "sugar 200 + Ir94e 200" but these
forced triggers still ignite the brain, the loop is still there: the upgrade
only makes it harder to set off (it masks the problem). If the forced triggers
no longer ignite, the upgrade itself breaks the loop.

Same eLN and DM1 definitions as experiments/phase6/runaway/s3b_lesions.py
(read only; nothing there is changed). Writes results/trigger_test.csv.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from sim.realism import REALISM_DEFAULTS, RealisticBrain, calibrate_adaptation  # noqa: E402
from run_phase7 import wait_for_ram  # noqa: E402

RES = HERE / "results"
LABELS = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"
IGNITION_SPIKES = 5 * 9620      # same bar as the runaway definition (5x baseline sugar median)


def main():
    inc100 = calibrate_adaptation(100.0)
    fit = json.loads((RES / "U2_fit.json").read_text())
    scale = next(iter(fit.values()))["scale"]
    configs = {
        "baseline": {},
        "U1_delays": dict(delays=True, velocity_m_per_s=0.20),
        "U2_cond": dict(conductance=True, E_inh_mV=-60.0),
        "U2_cond_tuned": dict(conductance=True, E_inh_mV=-60.0, cond_weight_scale=scale),
        "U3_adapt": dict(adaptation=True, tau_adapt_ms=100.0, adapt_mV=inc100),
        "U3_adapt_half": dict(adaptation=True, tau_adapt_ms=100.0, adapt_mV=inc100 / 2),
        "U3_adapt_tau300": dict(adaptation=True, tau_adapt_ms=300.0,
                                adapt_mV=calibrate_adaptation(300.0)),
        "U13": dict(delays=True, velocity_m_per_s=0.20, adaptation=True,
                    tau_adapt_ms=100.0, adapt_mV=inc100),
    }
    wait_for_ram()
    brain = RealisticBrain(snapshot="630", n_threads=2)
    lab = pd.read_parquet(LABELS, columns=["root_id", "cell_class", "hemibrain_type"])
    lab = lab.set_index("root_id").reindex(brain.root_ids)
    cc = lab.cell_class.astype(object).fillna("").to_numpy()
    ht = lab.hemibrain_type.astype(object).fillna("").to_numpy()
    rid = brain.root_ids
    eln = (cc == "ALLN") & np.isin(ht, ["lLN1_b,lLN1_c", "lLN2T_a", "lLN2T_b", "lLN2T_c"])
    triggers = {
        "10 DM1 smell neurons fire once": rid[ht == "ORN_DM1"][:10],
        f"{int(eln.sum())} eLNs fire once": rid[eln],
    }
    print({k: len(v) for k, v in triggers.items()}, flush=True)
    rows = []
    for name, cfg in configs.items():
        brain.set_realism(**dict(REALISM_DEFAULTS, **cfg))
        for tname, ids in triggers.items():
            t0 = time.perf_counter()
            res = brain.run_with_input_events([(np.full(len(ids), 50), ids)], excite=ids,
                                              duration_ms=1000.0)
            n = int(len(res.neuron))
            rows.append(dict(config=name, trigger=tname, total_spikes=n,
                             neurons_firing=int(np.unique(res.neuron).size),
                             ignites=n > IGNITION_SPIKES))
            pd.DataFrame(rows).to_csv(RES / "trigger_test.csv", index=False)
            print(f"{name:16s} {tname}: {n} spikes, {rows[-1]['neurons_firing']} neurons, "
                  f"ignites={rows[-1]['ignites']} ({time.perf_counter() - t0:.1f} s)", flush=True)
            del res


if __name__ == "__main__":
    main()
