"""Bug check: rebuild the circuit from robust_circuit_firmware.json alone and
confirm it reproduces the expected MN9 rates (seed 0, 30 trials). (PRELIMINARY)

Uses only what the firmware file contains (indices, 8-bit weights, parameters),
so it also checks that the file is complete.
"""

import json

import numpy as np

from rcommon import CONDITIONS, RES, paper_ids, run_cond


def main():
    from sim.fast_engine import DEFAULT_PARAMS, FastBrain
    fw = json.loads((RES / "robust_circuit_firmware.json").read_text())
    rid = np.array([int(n[1]) for n in fw["neurons"]])
    c = np.array(fw["connections"], np.int64)
    unit = fw["weights"]["w_int8_unit_mV"]
    kick = fw["parameters"]["input_kick_mV"]
    b = FastBrain.from_arrays(rid, c[:, 0], c[:, 1], c[:, 2], n_threads=1,
                              params={"w_syn": unit, "f_poi": kick / unit})
    ids = paper_ids()
    exp = fw["expected_mn9_hz_seed0_30trials"]["int8"]
    worst = 0.0
    for cond in CONDITIONS:
        got = float(np.mean(run_cond(b, ids, cond, 0, 30)))
        worst = max(worst, abs(got - exp[cond]))
        print(f"{cond}: rebuilt {got:.2f} Hz, expected {exp[cond]:.2f} Hz")
    assert abs(DEFAULT_PARAMS["w_syn"] * DEFAULT_PARAMS["f_poi"] - kick) < 1e-9
    print(f"largest difference {worst:.3f} Hz ->", "OK" if worst < 1e-6 else "MISMATCH")


if __name__ == "__main__":
    main()
