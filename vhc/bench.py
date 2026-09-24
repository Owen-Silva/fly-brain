"""Run every benchmark (v1) and write vhc/results/results.json, table.md and compare.md
(v0 against v1, side by side; v0's own results are kept in results_v0.json / table_v0.md).

Usage: .venv\\Scripts\\python.exe -m vhc.bench   (about 5-8 minutes; run vhc.calibrate first)

v1: the neuromorphic core is priced with the timing calibrated on real Loihi 2 and with
static power (vhc/neurocal.py, cores/neuromorphic.py); v0's pricing of the same counts is
kept next to it in every neuromorphic row. New workload (f): DishBrain-style Pong.

Honesty rule: a design's time and energy come ONLY from counted operations x the price list
(or, for "CPU only: laptop", from timing the laptop itself). The emulator's own run time is
recorded under "emulator_wall_s" and never used as any design's speed.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from concurrent.futures import ProcessPoolExecutor

from . import neurocal
from .cores import conventional, gpu, living, neuromorphic
from .cores.lif import Network, kernel, poisson_events, prepare
from .paths import ENERGY, RESULTS, wait_for_ram
from .prices import CL1_POWER_W, M33_SLEEP_W, SANDIA_CORES
from .scheduler import HYBRID, HYBRID_LIVING, Job, route
from .workloads import electrode_test, exact, feeding, hybrid_watch, odour, pong

ROWS = []
POOLED = "all cells, pooled into 256 regions"


def row(workload, design, cost=None, accuracy=None, acc_label="", time_s=None, energy_J=None,
        label=None, note="", v0=None, rng=None):
    """``v0``: the same counts priced v0's way (neuromorphic rows); ``rng``: v1's (best, worst)."""
    ROWS.append({"workload": workload, "design": design,
                 "time_s": cost.time_s if cost else time_s,
                 "energy_J": cost.energy_J if cost else energy_J,
                 "cost_label": cost.label if cost else label,
                 "accuracy": accuracy, "accuracy_label": acc_label, "note": note,
                 "v0_time_s": v0.time_s if v0 else None, "v0_energy_J": v0.energy_J if v0 else None,
                 "range_time_s": [rng[0].time_s, rng[1].time_s] if rng else None,
                 "range_energy_J": [rng[0].energy_J, rng[1].energy_J] if rng else None})


def neuro(c, mode, extra=None):
    """v1 cost, v0 cost and v1 range of neuromorphic counts ``c`` (+ an optional extra Cost)."""
    v1, v0 = neuromorphic.price(c, mode), neuromorphic.price(c, mode, version="v0")
    lo, hi = neuromorphic.price_range(c, mode)
    if extra is not None:
        v1, v0, lo, hi = v1 + extra, v0 + extra, lo + extra, hi + extra
    return v1, v0, (lo, hi)


def lif_ops(c):
    return {"neuron_update": c["neurons"] * c["steps"], "syn_event": c["syn_event"],
            "input_event": c["input_event"], "spike": c["spikes"], "step_overhead": c["steps"]}


def feeding_bench(out):
    decide = {"select": 1, "log_write": 1}          # read MN9's count, compare, record
    for name in feeding.CIRCUITS:                          # "400" (default) first, then "36"
        wl = f"(a) feeding decision, {name}-neuron circuit" + (" (default)" if name == feeding.DEFAULT_CIRCUIT else "")
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
            m33 = conventional.price(decide, "m33", wake=True)
            v1, v0, rng = neuro(c, mode, m33)
            row(wl, f"hybrid ({mode}) = neuromorphic + M33", v1, acc_q[9], "sim, 9-bit weights",
                note=f"scheduler: {route_[1]}", v0=v0, rng=rng)
            v1, v0, rng = neuro(c, mode)
            row(wl, f"neuromorphic only ({mode})", v1, acc_q[9], "sim, 9-bit weights", v0=v0, rng=rng)
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
        v1, v0, rng = neuro(c, mode, teach)
        row(wl, f"hybrid ({mode}) = neuromorphic + M33", v1, acc_8, "sim, 8-bit read-out", v0=v0, rng=rng)
        v1, v0, rng = neuro(c, mode)
        row(wl, f"neuromorphic only ({mode})", v1, acc_8, "sim, 8-bit read-out", v0=v0, rng=rng)
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
    days0 = hybrid_watch.per_day(res, s, x86_t, version="v0")
    days_lo = hybrid_watch.per_day(res, s, x86_t, static="low")
    days_hi = hybrid_watch.per_day(res, s, x86_t, static="high")
    acc = res["end_to_end_accuracy"]
    for design, d in days.items():
        ROWS.append({"workload": wl, "design": design, "time_s": d["time_s"],
                     "energy_J": d["J_per_day"] / 86400, "cost_label": d["label"], "accuracy": acc,
                     "accuracy_label": "sim; log " + d["log"],
                     "note": f"{d['J_per_day']:.3g} J per day (static power low-high: "
                             f"{days_lo[design]['J_per_day']:.3g}-{days_hi[design]['J_per_day']:.3g})",
                     "v0_time_s": days0[design]["time_s"], "v0_energy_J": days0[design]["J_per_day"] / 86400,
                     "range_time_s": None,
                     "range_energy_J": [days_lo[design]["J_per_day"] / 86400, days_hi[design]["J_per_day"] / 86400]})
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
        v1, v0, rng = neuro(c, mode, conventional.price(ro_all, "m33"))
        row(wl, f"hybrid ({mode}): culture network on silicon, every cell read", v1, r["curve"][POOLED],
            "sim; no electrodes, pooled read-out", v0=v0, rng=rng)
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
    """v1: fit the neuromorphic timing to Sandia's Loihi 2 runs (vhc/neurocal.py). The energy
    lane's sugar counts are re-read here to check the copy inside neurocal."""
    d = pd.read_csv(ENERGY / "results" / "decision_summary.csv")
    s = d[(d.model == "al_ln_literature") & (d.decision == "sugar")].iloc[0]
    same = (abs(s.spikes - neurocal.SUGAR["spikes"]) < 0.01 and abs(s.conn_events - neurocal.SUGAR["syn_event"]) < 10
            and abs(s.stim_spikes - neurocal.SUGAR["input_event"]) < 0.01)
    f = neurocal.fit()
    c = {"steps": 10000, "neurons": 127400, "spikes": s.spikes, "syn_event": s.conn_events,
         "input_event": s.stim_spikes}
    whole = {v: neuromorphic.price(c, "clocked", n_cores=SANDIA_CORES, version=v) for v in ("v0", "v1")}
    out["calibration_sandia"] = {**f, "counts_match_energy_lane": bool(same),
                                 "whole_brain_sugar_energy_J": {v: x.energy_J for v, x in whole.items()},
                                 "whole_brain_sugar_time_s": {v: x.time_s for v, x in whole.items()}}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "neuro_calibration.json").write_text(json.dumps(f, indent=1))


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


PONG_MIN = 20.0


def _pong_job(args):
    player, ch, seed, eta, lay = args
    return pong.play(player, ch, minutes=PONG_MIN, seed=seed, eta=eta, layout=lay)


def _agg(rs):
    keys = ("rally_length", "rally_length_t1", "rally_length_t2", "hit_rate", "aces_pct", "long_rallies_pct")
    out = {k: float(np.nanmean([r[k] for r in rs])) for k in keys}
    out.update({f"{k}_sd": float(np.nanstd([r[k] for r in rs])) for k in ("rally_length", "hit_rate")})
    out["learning_t2_minus_t1"] = out["rally_length_t2"] - out["rally_length_t1"]
    out["seeds"] = len(rs)
    out["never_missed"] = all(r.get("never_missed") for r in rs)
    for k in ("electrode_mean_hz", "electrode_max_hz", "stim_efficacy_end", "motor_channels"):
        vals = [r[k] for r in rs if r.get(k) is not None]
        out[k] = float(np.mean(vals)) if vals else None
    return out


def pong_bench(out):
    """(f) DishBrain-style Pong: living module vs its silicon copy vs a simple controller."""
    wl = "(f) Pong, DishBrain-style (per game-second; accuracy = hit rate)"
    wait_for_ram(1.5)
    seeds, few = (0, 1, 2, 3, 4), (0, 1, 2)
    jobs = [("living", ch, s, None, None) for ch in (59, 1024) for s in seeds]
    jobs += [("living", ch, s, None, None) for ch in pong.CHANNELS if ch not in (59, 1024) for s in (0, 1)]
    jobs += [("living", 1024, s, 0.0, None) for s in seeds]    # same culture, learning switched off
    jobs += [("living", 1024, s, None, "top") for s in few]    # DishBrain's own geometry
    jobs += [("rest", 1024, s, None, None) for s in few]       # no stimulation at all (DishBrain RST)
    jobs += [("silicon", 0, s, None, None) for s in seeds]
    jobs += [("silicon", 0, s, 0.0, None) for s in few]
    jobs += [("random", 0, s, None, None) for s in seeds] + [("controller", 0, s, None, None) for s in few]
    t0 = time.time()
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_pong_job, jobs))
    emu = time.time() - t0
    groups = {}
    for (player, ch, seed, eta, lay), r in zip(jobs, res):
        key = (f"{player}" + (f" {ch} electrodes" if player in ("living", "rest") else "")
               + (" no learning" if eta == 0.0 else "") + (f" layout {lay}" if lay else ""))
        groups.setdefault(key, []).append(r)
    agg = {k: _agg(v) for k, v in groups.items()}
    by_ch = {}
    for ch in pong.CHANNELS:
        rs = [r for (pl, c, _, e, lay), r in zip(jobs, res) if pl == "living" and c == ch and e is None and lay is None]
        by_ch[ch] = _agg(rs)
    costs = {k: pong.price_per_game_s(v[0]) for k, v in groups.items() if not k.startswith("random")}
    costs0 = {k: pong.price_per_game_s(v[0], version="v0") for k, v in groups.items() if not k.startswith("random")}
    for key, design in (("living 59 electrodes", "hybrid + living module (CL1-like, 59 electrodes)"),
                        ("living 1024 electrodes", "hybrid + living module (MaxOne-like, 1,024 electrodes)"),
                        ("silicon", "hybrid (clocked): the culture network on the neuromorphic core"),
                        ("controller", "CPU only: M33 running a simple controller")):
        a = agg[key]
        note = (f"hits per rally {a['rally_length']:.2f} (min 0-5: {a['rally_length_t1']:.2f}, "
                f"min 6-20: {a['rally_length_t2']:.2f}); {a['seeds']} x 20-min sessions")
        if a["never_missed"]:
            note = f"never missed in {a['seeds']} x 20-min sessions"
        row(wl, design, costs[key], a["hit_rate"], "sim; " + ("GUESSED biology" if "living" in key else "sim"),
            note=note, v0=costs0[key] if key == "silicon" else None)
    a = agg["random"]
    row(wl, "paddle driven by noise (DishBrain's in-silico control)", None, a["hit_rate"], "sim",
        label="n/a", note=f"hits per rally {a['rally_length']:.2f} (paddle size FITTED to DishBrain's 0.80)")
    out["pong"] = {"groups": agg, "by_channels": {str(k): v for k, v in by_ch.items()},
                   "costs_per_game_s": {k: c.as_dict() for k, c in costs.items()},
                   "costs_per_game_s_v0": {k: c.as_dict() for k, c in costs0.items()},
                   "settings": {"layout": pong.LAYOUT, "paddle_half": pong.PADDLE_HALF, "cross_s": pong.CROSS_S,
                                "paddle_speed": pong.PADDLE_SPEED, "learn": pong.LEARN, "dt_ms": pong.DT_MS,
                                "minutes": PONG_MIN},
                   "dishbrain": {k: p.value for k, p in pong.DISHBRAIN.items() if k.startswith("rally") or k.startswith("aces")},
                   "emulator_wall_s": emu}


def compare_md(rows, v0_rows):
    """v0 against v1, side by side, for every row that exists in both (or is priced both ways)."""
    def key(r):
        return (r["workload"].replace(" (default)", ""), r["design"])
    old = {key(r): r for r in v0_rows}
    lines = ["| Workload | Design | v0 time | v1 time | v0 energy | v1 energy | v1 range (energy) | v0 acc | v1 acc |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        o = old.get(key(r))
        t0 = r.get("v0_time_s") if r.get("v0_time_s") is not None else (o["time_s"] if o else None)
        e0 = r.get("v0_energy_J") if r.get("v0_energy_J") is not None else (o["energy_J"] if o else None)
        a0 = "new" if o is None else ("n/a" if o["accuracy"] is None else f"{100 * o['accuracy']:.1f}%")
        a1 = "n/a" if r["accuracy"] is None else f"{100 * r['accuracy']:.1f}%"
        rg = r.get("range_energy_J")
        rg = f"{fmt_e(rg[0])} - {fmt_e(rg[1])}" if rg else ""
        lines.append(f"| {r['workload']} | {r['design']} | {fmt_t(t0)} | {fmt_t(r['time_s'])} | {fmt_e(e0)} "
                     f"| {fmt_e(r['energy_J'])} | {rg} | {a0} | {a1} |")
    return "\n".join(lines)


def main():
    t0 = time.time()
    out = {"label": "PRELIMINARY", "version": "v1", "date": time.strftime("%Y-%m-%d %H:%M")}
    calibration(out)
    feeding_bench(out)
    print(f"feeding done {time.time() - t0:.0f} s", flush=True)
    setups = odour_bench(out)
    print(f"odour done {time.time() - t0:.0f} s", flush=True)
    exact_bench(out)
    watch_bench(out, setups)
    print(f"watch done {time.time() - t0:.0f} s", flush=True)
    electrode_bench(out)
    print(f"electrodes done {time.time() - t0:.0f} s", flush=True)
    pong_bench(out)
    print(f"pong done {time.time() - t0:.0f} s", flush=True)
    out["rows"] = ROWS
    out["emulator_wall_s_total"] = time.time() - t0
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "results.json").write_text(json.dumps(out, indent=1, default=float))
    (RESULTS / "table.md").write_text(table_md(ROWS) + "\n")
    v0f = RESULTS / "results_v0.json"
    if v0f.exists():
        (RESULTS / "compare.md").write_text(compare_md(ROWS, json.loads(v0f.read_text())["rows"]) + "\n")
    print(table_md(ROWS))
    print(f"total emulator time {time.time() - t0:.0f} s (NOT a design's speed)")


if __name__ == "__main__":
    main()
