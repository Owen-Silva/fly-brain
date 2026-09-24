"""Workload (a): the feeding decision on the 36- and 400-neuron circuits.

One task = one 1-second taste trial (sugar 100 Hz, bitter 100 Hz, or both) and one decision:
extend the proboscis (feed) or not, read from MN9's firing rate.

Decision rule (fixed before the benchmark runs, 2026-09-24): feed if MN9 fires above 35.7 Hz,
the midpoint of the whole brain's mean MN9 rate for sugar alone (67.0 Hz) and sugar+bitter
(4.3 Hz), both from experiments/minimal_circuit/results/validation.json (3 seeds x 30 trials).
The correct answer for each stimulus is the whole brain's: sugar -> feed, bitter -> no,
sugar+bitter -> no. Caveat: the threshold was chosen knowing the 36-neuron circuit's
sugar+bitter rate (24 Hz, docs/minimal-circuit.md); a threshold below 24 Hz would score it
wrong on that stimulus. The MN9 rate error against the whole brain is reported too.
"""
from __future__ import annotations

import json

import numpy as np

from ..cores.lif import Network, run_poisson
from ..paths import MINIMAL, load_module

CIRCUITS = {"400": "robust_circuit.json", "36": "minimal_circuit.json"}
# v1: the robust 400-neuron circuit is the default (it keeps its answers under 8-bit weights and
# matches the whole brain's bitter brake: 4.9 vs 4.3 Hz); the 36-neuron circuit stays an option.
DEFAULT_CIRCUIT = "400"
TASKS = {"sugar": {"SUGAR": 100.0}, "bitter": {"BITTER": 100.0},
         "sugar+bitter": {"SUGAR": 100.0, "BITTER": 100.0}}
REF_COND = {"sugar": "S100", "bitter": "B100", "sugar+bitter": "S100+B100"}
CORRECT = {"sugar": True, "bitter": False, "sugar+bitter": False}
THRESHOLD_HZ = 35.7
GROUP_ORDER = ("SUGAR", "WATER", "BITTER")
MN9 = 720575940660219265


def paper_ids():
    return load_module("mc_common", MINIMAL / "common.py").paper_ids()


def load_circuit(name=DEFAULT_CIRCUIT):
    """Network + MN9 index + root IDs, in the circuit file's own order."""
    d = json.loads((MINIMAL / "results" / CIRCUITS[name]).read_text())
    rid = [int(n["root_id"]) for n in d["neurons"]]
    pos = {r: i for i, r in enumerate(rid)}
    pre = [pos[int(c["pre"])] for c in d["connections"]]
    post = [pos[int(c["post"])] for c in d["connections"]]
    cnt = [c["signed_synapses"] for c in d["connections"]]
    net = Network.from_edges(len(rid), pre, post, cnt, names=rid)
    return net, pos[MN9], pos


def excite_for(task, ids, pos):
    """{neuron index: rate}, in the engine's order (group order, then the paper's list)."""
    out = {}
    for grp in GROUP_ORDER:
        if grp in TASKS[task]:
            for r in ids[grp]:
                if int(r) in pos:
                    out[pos[int(r)]] = TASKS[task][grp]
    return out


def run(name=DEFAULT_CIRCUIT, n_trials=30, seed=0, bits=None):
    """Run every task; returns {task: {"mn9_hz": array, "counts": mean counts dict}}."""
    net, mn9, pos = load_circuit(name)
    if bits:
        net = net.quantized(bits)
    ids = paper_ids()
    out = {}
    for task in TASKS:
        res = run_poisson(net, excite_for(task, ids, pos), 1000.0, n_trials, seed)
        rates = np.array([np.sum(r.spike_neurons == mn9) for r in res], float)
        keys = res[0].counts.keys()
        mean_counts = {k: float(np.mean([r.counts[k] for r in res])) for k in keys}
        out[task] = {"mn9_hz": rates, "counts": mean_counts}
    return out


def accuracy(results):
    """Fraction of trials (all tasks pooled) where the decision is the whole brain's."""
    ok = [((r["mn9_hz"] > THRESHOLD_HZ) == CORRECT[t]) for t, r in results.items()]
    return float(np.mean(np.concatenate(ok)))


def reference_rates(name=DEFAULT_CIRCUIT):
    """Circuit and whole-brain mean MN9 rates from the minimal-circuit lane (3 seeds x 30)."""
    if name == "36":
        v = json.loads((MINIMAL / "results" / "validation.json").read_text())["heldout"][0]["seeds"]
    else:
        v = json.loads((MINIMAL / "results" / "robust_circuit.json").read_text())["heldout"]
    circ = {c: float(np.mean([v[s]["circuit"][c] for s in v])) for c in REF_COND.values()}
    whole = {c: float(np.mean([v[s]["whole"][c] for s in v])) for c in REF_COND.values()}
    return circ, whole
