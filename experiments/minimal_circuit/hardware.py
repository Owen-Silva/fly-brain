"""Step 4: does the chosen circuit fit an RP2350 microcontroller? (PRELIMINARY)

Arithmetic only, from the circuit's size and its measured firing rates, plus
quick simulations: the circuit's speed on this PC, and whether storing each
connection's synapse count in 8 bits (clipped to +/-127, or rescaled so the
largest count is 127) still passes the rule (seed 0, 30 trials).

RP2350 (Raspberry Pi product page, checked 2026-09-23): two Arm Cortex-M33
cores at 150 MHz with single-precision floating point, 520 KB on-chip SRAM.

Cycle costs are ASSUMPTIONS (not measured on the chip): 25 cycles per neuron
update (load v and g, 3 multiplies, 2 adds, threshold compare, refractory
check, store), 10 cycles per synaptic event (load target and weight, add into
the delay buffer), 12 cycles per random-number draw for the taste input.

Usage: hardware.py [circuit json] [output json]
  default: results/minimal_circuit.json -> results/hardware.json
Firing rates come from running the circuit itself (seed 0, 30 trials).
"""

import json
import sys
import time

import numpy as np

from common import (CONDITIONS, RES, RULE, VALID_TRIALS, check_rule, means, paper_ids,
                    run_conditions)

DT_MS = 0.1
STEPS_PER_S = int(1000 / DT_MS)
DELAY_STEPS = 18                  # 1.8 ms synaptic delay at 0.1 ms steps
CYC_NEURON, CYC_EVENT, CYC_RAND = 25, 10, 12
CLOCK_HZ, CORES, SRAM_B = 150e6, 2, 520 * 1024


def main():
    from sim.fast_engine import FastBrain
    src = sys.argv[1] if len(sys.argv) > 1 else "minimal_circuit.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "hardware.json"
    mc = json.loads((RES / src).read_text())
    ids = paper_ids()
    rid = [int(n["root_id"]) for n in mc["neurons"]]
    pos = {r: i for i, r in enumerate(rid)}
    N = len(rid)
    pre = np.array([pos[int(c["pre"])] for c in mc["connections"]], np.int64)
    post = np.array([pos[int(c["post"])] for c in mc["connections"]], np.int64)
    sg = np.array([c["signed_synapses"] for c in mc["connections"]], np.int64)
    C = pre.size
    n_inputs = sum(1 for n in mc["neurons"] if n["role"].endswith("GRN"))
    outdeg = np.bincount(pre, minlength=N)
    b = FastBrain.from_arrays(np.array(rid), pre, post, sg, n_threads=1)
    _, cnt = run_conditions(b, ids, 0, VALID_TRIALS, counts=True)
    rate_of = {c: cnt[c] / VALID_TRIALS for c in CONDITIONS}

    # --- memory ---------------------------------------------------------
    idx_b = 1 if N <= 256 else 2 if N <= 65536 else 4
    ptr_b = 2 if C < 65536 else 4
    mem = {}
    for wb in (1, 2):
        conn = C * (idx_b + wb)
        rowptr = (N + 1) * ptr_b
        state = N * (4 + 4 + 1)               # v, g as float32; refractory counter
        delay = (DELAY_STEPS + 1) * N * 4     # ring buffer of pending input per neuron
        inputs = n_inputs * 2 + 64            # input neuron list + RNG state
        total = conn + rowptr + state + delay + inputs
        mem[f"{8 * wb}-bit weights"] = {
            "connections_B": conn, "row_pointers_B": rowptr, "neuron_state_B": state,
            "delay_buffer_B": delay, "inputs_B": inputs, "total_B": total,
            "total_KB": round(total / 1024, 2), "share_of_520KB": round(total / SRAM_B, 5)}
    max_abs = int(np.abs(sg).max())
    n_clip = int((np.abs(sg) > 127).sum())

    # --- operations per simulated second ---------------------------------
    ops = {}
    for c in CONDITIONS:
        r = rate_of[c]
        spikes = float(r.sum())
        syn_events = float((r * outdeg).sum())
        inp = sum(CONDITIONS[c].get(g, 0) * sum(1 for x in ids[g] if int(x) in pos)
                  for g in ("SUGAR", "WATER", "BITTER"))
        clock_updates = N * STEPS_PER_S
        clock_rand = n_inputs * STEPS_PER_S
        clock_cyc = clock_updates * CYC_NEURON + syn_events * CYC_EVENT + clock_rand * CYC_RAND
        # Event-driven: work only when something happens. Each synaptic event or
        # input kick also costs one neuron update (decay to "now", add, check).
        ev_updates = syn_events + inp
        ev_cyc = ev_updates * (CYC_NEURON + CYC_EVENT) + inp * CYC_RAND
        ops[c] = {"spikes_per_s": spikes, "synaptic_events_per_s": syn_events,
                  "input_kicks_per_s": inp,
                  "clock_driven": {"neuron_updates_per_s": clock_updates,
                                   "random_draws_per_s": clock_rand,
                                   "cycles_per_s": clock_cyc,
                                   "share_of_one_core": clock_cyc / CLOCK_HZ},
                  "event_driven": {"events_per_s": ev_updates, "cycles_per_s": ev_cyc,
                                   "share_of_one_core": ev_cyc / CLOCK_HZ}}
    worst = max(ops, key=lambda c: ops[c]["clock_driven"]["cycles_per_s"])

    # --- two quick simulations -------------------------------------------
    t = time.perf_counter()
    res = b.run(excite={int(x): 200.0 for x in ids["SUGAR"] if int(x) in pos},
                duration_ms=1000.0, n_trials=10, seed=0)
    pc_s_per_sim_s = (time.perf_counter() - t) / 10
    del res
    # 8-bit weights. (a) clip counts to +/-127; (b) scale so the largest count
    # is 127 (weight step = max/127 synapses), rounding to the nearest step.
    # (b) is emulated exactly by multiplying w_syn by the step and dividing
    # f_poi by it, so the taste-input kick stays the same.
    from sim.fast_engine import DEFAULT_PARAMS
    ref = np.load(RES / "raw" / "reference_mn9.npz")
    whole0 = {c: float(np.mean(ref[f"seed0|{c}"])) for c in CONDITIONS}
    step = max_abs / 127.0
    sq = np.round(sg / step).astype(np.int64)
    bq_clip = FastBrain.from_arrays(np.array(rid), pre, post, np.clip(sg, -127, 127), n_threads=1)
    bq_scale = FastBrain.from_arrays(
        np.array(rid), pre, post, sq, n_threads=1,
        params={"w_syn": DEFAULT_PARAMS["w_syn"] * step, "f_poi": DEFAULT_PARAMS["f_poi"] / step})
    q = {"whole_brain_seed0": whole0, "weight_step_synapses": step,
         "connections_rounded_to_zero": int(((sq == 0) & (sg != 0)).sum())}
    for tag, br in (("16bit_exact", b), ("int8_clipped", bq_clip), ("int8_scaled", bq_scale)):
        m = means(run_conditions(br, ids, 0, VALID_TRIALS))
        ok, d = check_rule(m, whole0, **RULE)
        q[tag] = {"mn9": m, "pass_rule_seed0": ok, "err_S100": d["err_S100"],
                  "err_S200": d["err_S200"], "brake_ratio": d["brake_ratio"]}

    out = {"label": "PRELIMINARY", "circuit_file": src, "n_neurons": N, "n_connections": C,
           "n_synapses": int(np.abs(sg).sum()), "n_input_neurons": n_inputs,
           "max_synapses_per_connection": max_abs, "connections_over_127": n_clip,
           "n_inhibitory_connections": int((sg < 0).sum()),
           "weight_precision_test_seed0": q, "memory": mem, "ops_per_simulated_second": ops,
           "worst_condition": worst,
           "assumed_cycles": {"per_neuron_update": CYC_NEURON, "per_synaptic_event": CYC_EVENT,
                              "per_random_draw": CYC_RAND},
           "rp2350": {"clock_hz": CLOCK_HZ, "cores": CORES, "sram_bytes": SRAM_B,
                      "source": "https://www.raspberrypi.com/products/rp2350/ (2026-09-23)"},
           "pc_wall_s_per_simulated_s": pc_s_per_sim_s}
    (RES / dst).write_text(json.dumps(out, indent=1))
    w = ops[worst]
    print(f"N={N} C={C} max|count|={max_abs} clipped={n_clip}")
    print("memory:", {k: v["total_KB"] for k, v in mem.items()}, "KB")
    print(f"worst {worst}: clock {w['clock_driven']['cycles_per_s'] / 1e6:.1f} Mcyc/s "
          f"({100 * w['clock_driven']['share_of_one_core']:.1f}% of one core), event "
          f"{w['event_driven']['cycles_per_s'] / 1e6:.2f} Mcyc/s; PC {pc_s_per_sim_s * 1000:.1f} ms/sim-s")
    for tag in ("16bit_exact", "int8_clipped", "int8_scaled"):
        v = q[tag]
        print(f"{tag}: pass={v['pass_rule_seed0']} err {v['err_S100']:+.3f}/{v['err_S200']:+.3f} "
              f"brake {v['brake_ratio']:.2f}")


if __name__ == "__main__":
    main()
