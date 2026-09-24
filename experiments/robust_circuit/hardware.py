"""Step 4: RP2350 arithmetic and the compact firmware file (PRELIMINARY).

Same method and cycle assumptions as experiments/minimal_circuit/hardware.py:
25 cycles per neuron update, 10 per synaptic event, 12 per random draw; one
Cortex-M33 core at 150 MHz; 520 KB SRAM; 0.1 ms steps; 1.8 ms delay (18 steps).
Firing rates come from running the circuit itself in its 8-bit version (the
version the firmware would run), seed 0, 30 trials; the 16-bit version is
reported next to it.

Usage: hardware.py [checkpoint index]  (default: the chosen one in validation.json)
Outputs
  results/hardware.json
  results/robust_circuit_firmware.json   neurons, types, integer weights, parameters
"""

import json
import sys
import time

import numpy as np

from rcommon import (CONDITIONS, FIX, MN9, RAW, RES, VALID_TRIALS, Timer, paper_ids, quantize,
                     run_cond, variant_brain)
from circuit import TouchedGraph
from common import labels

T = Timer()
DT_MS = 0.1
STEPS_PER_S = int(1000 / DT_MS)
DELAY_STEPS = 18
CYC_NEURON, CYC_EVENT, CYC_RAND = 25, 10, 12
CLOCK_HZ, SRAM_B = 150e6, 520 * 1024


def memory(N, C, n_inputs, wb):
    idx_b = 1 if N <= 256 else 2 if N <= 65536 else 4
    ptr_b = 2 if C < 65536 else 4
    conn = C * (idx_b + wb)
    rowptr = (N + 1) * ptr_b
    state = N * (4 + 4 + 1)
    delay = (DELAY_STEPS + 1) * N * 4
    inputs = n_inputs * 2 + 64
    total = conn + rowptr + state + delay + inputs
    return {"connections_B": conn, "row_pointers_B": rowptr, "neuron_state_B": state,
            "delay_buffer_B": delay, "inputs_B": inputs, "total_B": total,
            "total_KB": round(total / 1024, 2), "share_of_520KB": round(total / SRAM_B, 5)}


def ops(rate, outdeg, N, n_inputs, inp):
    spikes = float(rate.sum())
    syn = float((rate * outdeg).sum())
    clock = N * STEPS_PER_S * CYC_NEURON + syn * CYC_EVENT + n_inputs * STEPS_PER_S * CYC_RAND
    ev = (syn + inp) * (CYC_NEURON + CYC_EVENT) + inp * CYC_RAND
    return {"spikes_per_s": spikes, "synaptic_events_per_s": syn, "input_kicks_per_s": inp,
            "clock_driven": {"neuron_updates_per_s": N * STEPS_PER_S,
                             "random_draws_per_s": n_inputs * STEPS_PER_S,
                             "cycles_per_s": clock, "share_of_one_core": clock / CLOCK_HZ,
                             "realtime_margin_x": CLOCK_HZ / clock},
            "event_driven": {"events_per_s": syn + inp, "cycles_per_s": ev,
                             "share_of_one_core": ev / CLOCK_HZ,
                             "realtime_margin_x": CLOCK_HZ / ev if ev > 0 else None}}


def main():
    from sim.fast_engine import DEFAULT_PARAMS, _update_constants
    g = TouchedGraph()
    ids = paper_ids()
    val = json.loads((RES / "validation.json").read_text())
    ci = int(sys.argv[1]) if len(sys.argv) > 1 else val["chosen_checkpoint"]
    cp = json.loads((RAW / "checkpoints.json").read_text())["checkpoints"][ci]
    kn = np.zeros(g.n, bool)
    kn[cp["nodes"]] = True
    ek = np.zeros(g.m, bool)
    ek[cp["edges"]] = True
    ek &= kn[g.pre] & kn[g.post]
    new = np.cumsum(kn) - 1
    rid, pre, post, cnt = g.root_ids[kn], new[g.pre[ek]], new[g.post[ek]], g.signed[ek]
    N = rid.size
    q, step = quantize(cnt)
    nz = q != 0
    group = {int(r): grp for grp in ("SUGAR", "WATER", "BITTER") for r in ids[grp]}
    n_inputs = sum(1 for r in rid if int(r) in group)

    res = {}
    for tag, variant, C, od in (("int8", "int8", int(nz.sum()), np.bincount(pre[nz], minlength=N)),
                                ("16bit", "normal", cnt.size, np.bincount(pre, minlength=N))):
        b = variant_brain(rid, pre, post, cnt, variant)
        mn9, per_cond = {}, {}
        for c in CONDITIONS:
            per, sc = run_cond(b, ids, c, 0, VALID_TRIALS, counts=True)
            mn9[c] = float(np.mean(per))
            rate = sc / VALID_TRIALS
            inp = sum(CONDITIONS[c].get(gr, 0) * sum(1 for r in rid if group.get(int(r)) == gr)
                      for gr in ("SUGAR", "WATER", "BITTER"))
            per_cond[c] = ops(rate, od, N, n_inputs, inp)
        worst = max(per_cond, key=lambda c: per_cond[c]["clock_driven"]["cycles_per_s"])
        res[tag] = {"n_connections_stored": C, "memory": memory(N, C, n_inputs, 1 if tag == "int8" else 2),
                    "mn9_seed0_hz": mn9, "ops_per_simulated_second": per_cond,
                    "worst_condition": worst, "worst": per_cond[worst]}
        T.log(f"{tag}: {C} conns, {res[tag]['memory']['total_KB']} KB; worst {worst}: clock "
              f"{per_cond[worst]['clock_driven']['cycles_per_s'] / 1e6:.2f} Mcyc/s "
              f"({100 * per_cond[worst]['clock_driven']['share_of_one_core']:.1f}%, "
              f"x{per_cond[worst]['clock_driven']['realtime_margin_x']:.1f}); event "
              f"{per_cond[worst]['event_driven']['cycles_per_s'] / 1e6:.3f} Mcyc/s "
              f"(x{per_cond[worst]['event_driven']['realtime_margin_x']:.0f})")
        if tag == "16bit":
            t = time.perf_counter()
            b.run(excite={int(x): 200.0 for x in ids["SUGAR"] if int(x) in set(rid.tolist())},
                  duration_ms=1000.0, n_trials=10, seed=0)
            res["pc_wall_s_per_simulated_s"] = (time.perf_counter() - t) / 10
        del b

    out = {"label": "PRELIMINARY", "checkpoint": ci, "stage": cp["stage"], "n_neurons": N,
           "n_connections": int(cnt.size), "n_synapses": int(np.abs(cnt).sum()),
           "n_input_neurons": n_inputs, "max_synapses_per_connection": int(np.abs(cnt).max()),
           "int8_step_synapses": step, "int8_connections_rounded_to_zero": int((~nz).sum()),
           "n_inhibitory_connections": int((cnt < 0).sum()), **res,
           "assumed_cycles": {"per_neuron_update": CYC_NEURON, "per_synaptic_event": CYC_EVENT,
                              "per_random_draw": CYC_RAND},
           "rp2350": {"clock_hz": CLOCK_HZ, "cores": 2, "sram_bytes": SRAM_B,
                      "source": "https://www.raspberrypi.com/products/rp2350/ (checked 2026-09-23 by the minimal-circuit lane)"}}
    (RES / "hardware.json").write_text(json.dumps(out, indent=1))

    # ---- compact firmware file ------------------------------------------
    lab = labels()
    c_g, c_v0, c_vg, c_vv = _update_constants(DEFAULT_PARAMS)
    P = DEFAULT_PARAMS
    role = {r: ("MN9" if r == MN9 else group[r].lower() if r in group else "relay")
            for r in map(int, rid)}
    neurons = []
    for i, r in enumerate(map(int, rid)):
        L = lab.loc[r] if r in lab.index else None
        neurons.append([i, str(r), role[r], (L["cell_type"] if L is not None else "") or "",
                        (L["top_nt"] if L is not None else "") or ""])
    order = np.lexsort((post[nz], pre[nz]))
    conns = np.stack([pre[nz][order], post[nz][order], q[nz][order], cnt[nz][order]], 1)
    fw = {
        "label": "PRELIMINARY",
        "what": "Smallest hardware-ready fly feeding circuit (docs/robust-circuit.md): a reduction "
                "of the Shiu et al. 2024 whole-brain model (FlyWire 630, fix " + FIX + ").",
        "n_neurons": N, "n_connections": int(nz.sum()),
        "neuron_columns": ["index", "flywire_root_id", "role", "cell_type", "transmitter"],
        "neurons": neurons,
        "readout_index": int(np.flatnonzero(rid == MN9)[0]),
        "input_indices": {grp.lower(): [int(i) for i, r in enumerate(rid) if group.get(int(r)) == grp]
                          for grp in ("SUGAR", "BITTER", "WATER")},
        "connection_columns": ["pre_index", "post_index", "w_int8", "synapses_signed"],
        "connections": conns.astype(int).tolist(),
        "weights": {"w_int8_unit_mV": P["w_syn"] * step, "synapses_per_unit": step,
                    "w_syn_mV_per_synapse": P["w_syn"],
                    "note": "g += w_int8 x w_int8_unit_mV (8-bit) or synapses_signed x "
                            "w_syn_mV_per_synapse (exact). Negative = inhibitory."},
        "parameters": {"dt_ms": P["dt"], "v_rest_mV": P["v_0"], "v_reset_mV": P["v_rst"],
                       "v_threshold_mV": P["v_th"], "t_membrane_ms": P["t_mbr"],
                       "tau_synapse_ms": P["tau"], "refractory_steps": int(round(P["t_rfc"] / P["dt"])),
                       "delay_steps": int(round(P["t_dly"] / P["dt"])),
                       "input_kick_mV": P["w_syn"] * P["f_poi"],
                       "step_constants_SI": {"c_g": c_g, "c_v0_V": c_v0, "c_vg": c_vg, "c_vv": c_vv}},
        "update_rule": [
            "Each 0.1 ms step, for every neuron not refractory: v_new = c_v0 + c_vg*g + c_vv*v; "
            "g_new = c_g*g (volts; the exact solution of dv/dt=(v_0-v+g)/t_mbr, dg/dt=-g/tau).",
            "If v_new > v_threshold: spike; v = v_reset, g = 0, refractory for refractory_steps "
            "(v and g frozen, arriving input discarded).",
            "Taste input: each input neuron, each step, with probability rate_Hz x dt, gets "
            "v += input_kick_mV and its refractory counter is cleared.",
            "A spike reaches each target delay_steps later and adds its weight to the target's g.",
            "Order within a step: update v and g, check threshold, deliver input, reset "
            "(Brian2's default schedule; see sim/fast_engine.py)."],
        "stimuli_hz": CONDITIONS,
        "expected_mn9_hz_seed0_30trials": {"int8": res["int8"]["mn9_seed0_hz"],
                                           "exact": res["16bit"]["mn9_seed0_hz"]},
    }
    (RES / "robust_circuit_firmware.json").write_text(json.dumps(fw, separators=(",", ":")))
    T.log(f"firmware file: {N} neurons, {int(nz.sum())} connections; "
          f"{(RES / 'robust_circuit_firmware.json').stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
