"""Run every v0 benchmark and write vhc/results/results.json and vhc/results/table.md.

Usage: .venv\\Scripts\\python.exe -m vhc.bench   (about 3-5 minutes; run vhc.calibrate first)

Honesty rule: a design's time and energy come ONLY from counted operations x the price list
(or, for "CPU only: laptop", from timing the laptop itself). The emulator's own run time is
recorded under "emulator_wall_s" and never used as any design's speed.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from .cores import conventional, gpu, living, neuromorphic
from .cores.lif import Network, kernel, poisson_events, prepare
from .paths import ENERGY, RESULTS, wait_for_ram
from .prices import SANDIA_CORES, SANDIA_WALL_S_PER_SIM_S_DT01
from .scheduler import HYBRID, HYBRID_LIVING, Job, route
from .workloads import electrode_test, exact, feeding, hybrid_watch, odour

ROWS = []
POOLED = "all cells, pooled into 256 regions"


def row(workload, design, cost=None, accuracy=None, acc_label="", time_s=None, energy_J=None,
        label=None, note=""):
    ROWS.append({"workload": workload, "design": design,
                 "time_s": cost.time_s if cost else time_s,
                 "energy_J": cost.energy_J if cost else energy_J,
                 "cost_label": cost.label if cost else label,
                 "accuracy": accuracy, "accuracy_label": acc_label, "note": note})


def lif_ops(c):
    return {"neuron_update": c["neurons"] * c["steps"], "syn_event": c["syn_event"],
            "input_event": c["input_event"], "spike": c["spikes"], "step_overhead": c["steps"]}


def feeding_bench(out):
    decide = {"select": 1, "log_write": 1}          # read MN9's count, compare, record
    for name in ("36", "400"):
        wl = f"(a) feeding decision, {name}-neuron circuit"
        seeds = (0, 1, 2)
        exact_runs = [feeding.run(name, 30, s) for s in seeds]
        acc = float(np.mean([feeding.accuracy(r) for r in exact_runs]))
        rates = {t: float(np.mean([r[t]["mn9_hz"].mean() for r in exact_runs])) for t in feeding.TASKS}
        circ_ref, whole_ref = feeding.reference_rates(name)
        q = {b: feeding.run(name, 30, 0, bits=b) for b in (8, 9)}
        acc_q = {b: feeding.accuracy(r) for b, r in q.items()}
        rates_q = {b: {t: float(r[t]["mn9_hz"].mean()) for t in feeding.TASKS} for b, r in q.items()}
        c = {k: float(np.mean([r[t]["counts"][k] for r in exact_runs for t in feeding.TASKS]))
             for k in exact_runs[0]["sugar"]["counts"]}
        # measured laptop time: the compiled kernel only, median of 30 trials of each task
        net, mn9, pos = feeding.load_circuit(name)
        ids = feeding.paper_ids()
        ts = []
        for task in feeding.TASKS:
            exc = feeding.excite_for(task, ids, pos)
            idx = np.array(list(exc))
            p = np.array(list(exc.values())) * net.params["dt"] * 1e-3
            for k in range(10):
                st, ne = poisson_events(np.random.default_rng([k, 5]), idx, p, 10000)
                args = prepare(net, (st, ne), 10000, excited_idx=idx)
                kernel(args)                                   # warm caches
                t0 = time.perf_counter()
                kernel(args)
                ts.append(time.perf_counter() - t0)
        x86_t = float(np.median(ts))
        route_ = route(Job("feeding", "spiking"), HYBRID)
        for mode in neuromorphic.MODES:
            nc = neuromorphic.price(c, mode)
            m33 = conventional.price(decide, "m33", wake=True)
            row(wl, f"hybrid ({mode}) = neuromorphic + M33", nc + m33, acc_q[9], "sim, 9-bit weights",
                note=f"scheduler: {route_[1]}")
            row(wl, f"neuromorphic only ({mode})", nc, acc_q[9], "sim, 9-bit weights")
        row(wl, "CPU only: laptop x86", conventional.x86_measured(x86_t, "LIF kernel"), acc, "sim, float64")
        row(wl, "CPU only: M33", conventional.price(lif_ops(c), "m33"), acc, "sim (float64 stand-in)")
        row(wl, "GPU (T4)", gpu.lif_price(c), acc, "sim, float64")
        out[f"feeding_{name}"] = {
            "decision_accuracy_float64": acc, "decision_accuracy_bits": acc_q,
            "mn9_hz_vhc": rates, "mn9_hz_vhc_bits_seed0": rates_q,
            "mn9_hz_minimal_circuit_lane": circ_ref, "mn9_hz_whole_brain": whole_ref,
            "mean_counts_per_decision": c, "x86_measured_s": x86_t,
            "x86_model_s": conventional.price(lif_ops(c), "x86").time_s,
            "threshold_hz": feeding.THRESHOLD_HZ}


def odour_bench(out):
    wl = "(b) continual odour learning (per labelled sniff)"
    wait_for_ram(1.5)
    accs = {None: [], 8: []}
    setups = {}
    last = None
    for side in ("left", "right"):
        for seed in range(5):
            s = odour.real_setup(side, seed)
            setups[(side, seed)] = s
            for bits in accs:
                r = odour.run_protocol(s, seed, bits)
                accs[bits].append(r["accuracy"])
                if bits is None and last is None:
                    last = (s, r)
    s, r = last
    n_od = r["n_classes"]
    c = odour.neuro_counts(s, r["Xtr"], r["Htr"], n_od, train=True)
    acc_f, acc_8 = float(np.mean(accs[None])), float(np.mean(accs[8]))
    x86_t = odour.measure_x86(s)
    teach = conventional.price({"log_write": 1}, "m33", wake=True)
    for mode in neuromorphic.MODES:
        nc = neuromorphic.price(c, mode)
        row(wl, f"hybrid ({mode}) = neuromorphic + M33", nc + teach, acc_8, "sim, 8-bit read-out")
        row(wl, f"neuromorphic only ({mode})", nc, acc_8, "sim, 8-bit read-out")
    row(wl, "CPU only: laptop x86", conventional.x86_measured(x86_t, "one sniff: code, recognise, learn"),
        acc_f, "sim, float32")
    row(wl, "CPU only: M33", odour.m33_cost(s, r["active_per_sniff"], n_od), acc_f, "sim, float32")
    row(wl, "GPU (T4)", odour.gpu_cost(s, n_od), acc_f, "sim, float32")
    out["odour"] = {"accuracy_float_mean": acc_f, "accuracy_8bit_mean": acc_8,
                    "accuracy_float_runs": accs[None], "accuracy_8bit_runs": accs[8],
                    "lane_reference": "docs/mb-continual-learning.md: uniform random wiring 66.8% / 66.8%",
                    "counts_per_sniff": c, "active_per_sniff": r["active_per_sniff"],
                    "n_kc": int(s.W.shape[0]), "x86_measured_s": x86_t}
    return setups


def exact_bench(out):
    for kind, title in (("sum", "(c) exact sum of 50,000 64-bit integers"),
                        ("sort", "(c) sort 50,000 32-bit integers")):
        core, why = route(Job(kind, "exact", 1.0), HYBRID)
        t, ok = exact.measure_x86(kind)
        m33 = exact.m33_cost(kind)
        row(title, "hybrid = its M33 core", m33, 1.0, "exact", note=f"scheduler: {why}")
        row(title, "neuromorphic only", None, None, "not possible", label="n/a",
            note="spiking cores hold 8-9-bit weights and no general memory; exact results unsupported")
        row(title, "CPU only: laptop x86", conventional.x86_measured(t, kind), 1.0 if ok else 0.0, "exact, checked")
        row(title, "CPU only: M33", m33, 1.0, "exact")
        row(title, "GPU (T4)", exact.gpu_cost(kind), 1.0, "exact (integer)")
        out[f"exact_{kind}"] = {"x86_measured_s": t, "correct": ok,
                                "x86_model_s": conventional.price(exact.ops(kind), "x86").time_s}


def watch_bench(out, setups):
    wl = "(d) hybrid odour watch with exact log (per sniff; energy per day in note)"
    s = setups[("left", 0)]
    r = odour.run_protocol(s, 0, 8)
    res = hybrid_watch.run(s, r["readout"], 5000, 0)
    x86_t = odour.measure_x86(s)
    days = hybrid_watch.per_day(res, s, x86_t)
    acc = res["end_to_end_accuracy"]
    for design, d in days.items():
        row(wl, design, None, acc, "sim; log " + d["log"], time_s=d["time_s"], energy_J=d["J_per_day"] / 86400,
            label=d["label"], note=f"{d['J_per_day']:.3g} J per day")
    out["watch"] = {k: v for k, v in res.items() if k != "neuro_counts"}
    out["watch"]["neuro_counts"] = res["neuro_counts"]
    out["watch"]["per_day"] = days


def electrode_bench(out):
    wl = "(e) electrode bottleneck: 8 stimulation patterns"
    t0 = time.time()
    r = electrode_test.run(n_train=40, n_test=30, seed=0)
    emu = time.time() - t0
    cult = r.pop("culture")
    c = r["counts"]
    readout = {"mac": 59 * 6 * 8, "select": 8}
    core, why = route(Job("patterns", "adaptive-bio"), HYBRID_LIVING)
    row(wl, "hybrid + living module (CL1-like, 59 channels)",
        living.price(electrode_test.DUR_MS * 1e-3, 3) + conventional.price(readout, "m33"),
        r["curve"][59], "sim; GUESSED biology", note=f"scheduler: {why}")
    ro_all = {"mac": 256 * 6 * 8, "select": 8}          # pooled read-out: 256 regions x 6 bins x 8 classes
    for mode in neuromorphic.MODES:
        row(wl, f"hybrid ({mode}): culture network on silicon, every cell read",
            neuromorphic.price(c, mode) + conventional.price(ro_all, "m33"), r["curve"][POOLED],
            "sim; no electrodes, pooled read-out")
    # laptop: time the same network (one trial) with the compiled kernel
    net = Network.from_edges(cult.p.n, cult.pre, cult.post, cult.w)
    rng = np.random.default_rng(0)
    k = int(c["input_event"])
    args = prepare(net, (rng.integers(0, 600, k), rng.integers(0, cult.p.n, k)), 600)
    ts = []
    for _ in range(20):
        t1 = time.perf_counter()
        kernel(args)
        ts.append(time.perf_counter() - t1)
    row(wl, "CPU only: laptop x86 (simulated culture, every cell read)",
        conventional.x86_measured(float(np.median(ts[2:])), "culture trial kernel"), r["curve"][POOLED], "sim, pooled read-out")
    row(wl, "CPU only: M33", conventional.price(lif_ops(c), "m33") + conventional.price(ro_all, "m33"),
        r["curve"][POOLED], "sim, pooled read-out")
    row(wl, "GPU (T4)", gpu.lif_price(c), r["curve"][POOLED], "sim, pooled read-out")
    out["electrode"] = {**{k: v for k, v in r.items()}, "emulator_wall_s": emu}


def calibration(out):
    """Price the whole-brain sugar decision (energy lane's counts) and compare with Sandia."""
    d = pd.read_csv(ENERGY / "results" / "decision_summary.csv")
    s = d[(d.model == "al_ln_literature") & (d.decision == "sugar")].iloc[0]
    c = {"steps": 10000, "neurons": 127400, "spikes": s.spikes, "syn_event": s.conn_events,
         "input_event": s.stim_spikes}
    pred = neuromorphic.price(c, "clocked", n_cores=SANDIA_CORES)
    out["calibration_sandia"] = {
        "predicted_s_per_sim_s": pred.time_s, "measured_s_per_sim_s": SANDIA_WALL_S_PER_SIM_S_DT01.value,
        "ratio_measured_over_predicted": SANDIA_WALL_S_PER_SIM_S_DT01.value / pred.time_s,
        "note": "Loihi 1 per-op timings, 1,440 cores, even load; Sandia ran Loihi 2 (12 chips)"}


def fmt_t(t):
    if t is None:
        return "n/a"
    for unit, f in (("s", 1), ("ms", 1e-3), ("us", 1e-6), ("ns", 1e-9)):
        if t >= f:
            return f"{t / f:.3g} {unit}"
    return f"{t:.2g} s"


def fmt_e(e):
    if e is None:
        return "n/a"
    for unit, f in (("J", 1), ("mJ", 1e-3), ("uJ", 1e-6), ("nJ", 1e-9), ("pJ", 1e-12)):
        if e >= f:
            return f"{e / f:.3g} {unit}"
    return f"{e:.2g} J"


def table_md(rows):
    lines = ["| Workload | Design | Time per task | Energy per task | Accuracy | Labels | Note |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        acc = "n/a" if r["accuracy"] is None else f"{100 * r['accuracy']:.1f}%"
        lines.append(f"| {r['workload']} | {r['design']} | {fmt_t(r['time_s'])} | {fmt_e(r['energy_J'])} "
                     f"| {acc} | cost {r['cost_label']}; accuracy {r['accuracy_label']} | {r['note']} |")
    return "\n".join(lines)


def main():
    t0 = time.time()
    out = {"label": "PRELIMINARY", "date": time.strftime("%Y-%m-%d %H:%M")}
    calibration(out)
    feeding_bench(out)
    print(f"feeding done {time.time() - t0:.0f} s", flush=True)
    setups = odour_bench(out)
    print(f"odour done {time.time() - t0:.0f} s", flush=True)
    exact_bench(out)
    watch_bench(out, setups)
    print(f"watch done {time.time() - t0:.0f} s", flush=True)
    electrode_bench(out)
    out["rows"] = ROWS
    out["emulator_wall_s_total"] = time.time() - t0
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "results.json").write_text(json.dumps(out, indent=1, default=float))
    (RESULTS / "table.md").write_text(table_md(ROWS) + "\n")
    print(table_md(ROWS))
    print(f"total emulator time {time.time() - t0:.0f} s (NOT a design's speed)")


if __name__ == "__main__":
    main()
