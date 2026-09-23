"""Shared helpers for the Phase 7 neurotransmitter-sign lane.

Plain English
-------------
* ``paper_ids()``: the paper's taste-neuron and MN9 IDs, read as text from
  sim/shiu_model.py (importing that file would load Brian2).
* ``input_sets(lab)``: which neurons get input in each experiment.
* ``run_chunk``: simulates trials a..b-1 of one seed exactly as
  ``FastBrain.run(seed=seed, n_trials=30)`` would (trial k is the same trial
  whatever the chunking), so results line up with earlier lanes' seeds.
* ``trial_rows``: measures every trial (runaway, MN9, Kenyon cells, steering
  neurons). RUNAWAY = more than 1,500 different neurons fire in some 10 ms
  slice (the Phase 6 definition).
"""

import ast
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "phase5" / "unexplored"))

from steering_ids import STEERING  # noqa: E402

RUNAWAY_DISTINCT_10MS = 1500


def free_ram_gb():
    import ctypes

    class MEMSTAT(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEMSTAT()
    m.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2 ** 30


def wait_for_ram(min_gb=1.5):
    import time
    while free_ram_gb() < min_gb:
        print(f"  free RAM {free_ram_gb():.2f} GB < {min_gb}; waiting 30 s", flush=True)
        time.sleep(30)


def paper_ids():
    tree = ast.parse((ROOT / "sim" / "shiu_model.py").read_text(encoding="utf-8"))
    wanted = {"SUGAR_R_630": "SUGAR", "BITTER_R_630": "BITTER", "WATER_R_630": "WATER",
              "IR94E_630": "IR94E", "MN9_LEFT": "MN9", "MN9_RIGHT_630": "MN9_IPSI"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in wanted:
            out[wanted[node.targets[0].id]] = ast.literal_eval(node.value)
    assert set(out) == set(wanted.values())
    return out


def input_sets(lab):
    """{name: array of root IDs}: taste sets from the paper, DM1 ORNs (Phase 5
    filter: hemibrain_type ORN_DM1) all / left / right."""
    ids = paper_ids()
    rid = lab.root_id.to_numpy()
    dm1 = (lab.hemibrain_type.to_numpy() == "ORN_DM1")
    side = lab.side.to_numpy()
    out = {k.lower(): np.array(ids[k], np.int64) for k in ("SUGAR", "BITTER", "WATER", "IR94E")}
    out["dm1"] = rid[dm1]
    out["dm1_left"] = rid[dm1 & (side == "left")]
    out["dm1_right"] = rid[dm1 & (side == "right")]
    assert (out["dm1"].size, out["dm1_left"].size, out["dm1_right"].size) == (68, 35, 33)
    return out


# name: (list of (input set, rate Hz), base seed). Taste base seeds as in
# Phase 3 / Phase 7 upgrades 1-3; Ir94e and DM1 seeds as in Phase 6 / Phase 5.
CONDITIONS = {
    "sugar_100Hz": ([("sugar", 100)], 1_000),
    "sugar_200Hz": ([("sugar", 200)], 2_000),
    "water_200Hz": ([("water", 200)], 3_000),
    "bitter_200Hz": ([("bitter", 200)], 4_000),
    "sugar100_bitter120": ([("sugar", 100), ("bitter", 120)], 6_000),
    "ir94e_200Hz": ([("ir94e", 200)], 0),
    "dm1_both_150Hz": ([("dm1", 150)], 0),
    "dm1_left_150Hz": ([("dm1_left", 150)], 0),
    "dm1_right_150Hz": ([("dm1_right", 150)], 0),
}


def excite_for(cond, sets):
    ex = {}
    for s, r in CONDITIONS[cond][0]:
        for i in sets[s]:
            ex[int(i)] = float(r)
    return ex


def run_chunk(brain, excite, seed, a, b, duration_ms=1000.0, params=None):
    """Trials a..b-1 of ``seed``, identical to those trials of brain.run."""
    p = brain._params_for(params)
    ids = np.array(list(excite.keys()), np.int64)
    rates = np.array(list(excite.values()), float)
    exc_idx = brain.index_of(ids)
    n_steps = int(round(duration_ms / p["dt"]))
    prob = rates * p["dt"] * 1e-3
    seqs = np.random.SeedSequence(seed).spawn(b)[a:b]
    ev = [brain._poisson_events(np.random.default_rng(s), exc_idx, prob, n_steps) for s in seqs]
    return brain._run_events(ev, exc_idx, (), n_steps, p, ())


def run_volley(brain, trig_ids, duration_ms=1000.0, at_step=50):
    trig = np.asarray(trig_ids, np.int64)
    return brain.run_with_input_events([(np.full(trig.size, at_step), trig)], excite=trig,
                                       duration_ms=duration_ms)


class Readout:
    """Index arrays for the things measured in every trial."""

    def __init__(self, brain, lab):
        ids = paper_ids()
        self.n = brain.n_neurons
        self.mn9 = brain.index_of([ids["MN9"], ids["MN9_IPSI"]])
        cc = lab.cell_class.to_numpy()
        self.kc = np.flatnonzero(cc == "Kenyon_Cell")
        self.is_kc = cc == "Kenyon_Cell"
        self.steer_names = list(STEERING)
        self.steer = brain.index_of([STEERING[k] for k in self.steer_names])


def trial_rows(res, rd, meta, dt_ms=0.1):
    """One dict per trial, plus the per-neuron spike counts summed over trials."""
    rows = []
    n_steps = int(round(res.duration_ms / dt_ms))
    per10 = int(round(10 / dt_ms))
    n10 = n_steps // per10
    last100 = n_steps - int(round(100 / dt_ms))
    counts = np.bincount(res.neuron, minlength=rd.n).astype(np.int64)
    dur_s = res.duration_ms * 1e-3
    for t in range(res.n_trials):
        m = res.trial == t
        st, nu = res.step[m].astype(np.int64), res.neuron[m].astype(np.int64)
        key = np.unique((st // per10) * 1_000_000 + nu)
        d10 = np.bincount(key // 1_000_000, minlength=n10)[:n10]
        uniq = np.unique(nu)
        row = dict(meta, trial=meta.get("trial0", 0) + t,
                   total_spikes=int(st.size), n_active=int(uniq.size),
                   max_distinct_10ms=int(d10.max()) if d10.size else 0,
                   runaway=bool(d10.size and d10.max() > RUNAWAY_DISTINCT_10MS),
                   distinct_last_100ms=int(np.unique(nu[st >= last100]).size),
                   mn9_hz=float((nu == rd.mn9[0]).sum() / dur_s),
                   mn9_ipsi_hz=float((nu == rd.mn9[1]).sum() / dur_s),
                   kc_active=int(rd.is_kc[uniq].sum()))
        sc = np.bincount(nu[np.isin(nu, rd.steer)], minlength=rd.n)[rd.steer]
        for name, c in zip(rd.steer_names, sc):
            row[name] = float(c / dur_s)
        row.pop("trial0", None)
        rows.append(row)
    return rows, counts
