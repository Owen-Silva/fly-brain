"""Shared helpers for the energy-budget lane (PRELIMINARY).

Plain English
-------------
* ``decisions(lab)`` gives, for every "decision" we simulate, which sensory neurons are
  driven and how fast. Every list and rate is reused from an earlier lane, never chosen
  here (the source is written next to each one).
* ``wiring_counts(brain)`` gives every neuron's number of OUTPUT SYNAPSES (FlyWire
  synapse count summed over its outgoing connections) and number of OUTPUT CONNECTIONS
  (how many different neurons it contacts).
* ``run_trial`` runs trial k of a seed exactly as ``FastBrain.run`` would, one trial at a
  time, so that memory stays small even in the runaway trials.
* ``free_ram_gb`` / ``wait_for_ram``: the shared-machine rule (1.5 GB free before heavy work).
"""
from __future__ import annotations

import ast
import ctypes
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RES = HERE / "results"
RAW = RES / "raw"
RES.mkdir(exist_ok=True)
RAW.mkdir(exist_ok=True)
LABELS = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"

MODELS = ("none", "al_ln_literature")          # published model, recommended fix
MODEL_NAME = {"none": "published", "al_ln_literature": "fixed (al_ln_literature)"}
SEEDS = (11, 12)
TRIALS_PER_SEED = 20
DURATION_MS = 1000.0
RUNAWAY_DISTINCT_10MS = 1500     # Phase 6 definition (docs/phase6-runaway-activity.md)

MN9 = 720575940660219265         # MN9, the side the paper reads (sim/shiu_model.py MN9_LEFT)
MN9_IPSI = 720575940645521262    # MN9 on the other side (MN9_RIGHT_630)
ABN1 = 720575940630907434        # grooming read-out (experiments/heldout/ids.py)


def free_ram_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 1e9


def wait_for_ram(min_gb=1.5):
    while True:
        f = free_ram_gb()
        if f >= min_gb:
            return f
        print(f"  free RAM {f:.2f} GB < {min_gb} GB, waiting 30 s", flush=True)
        time.sleep(30)


def paper_ids():
    """Sugar / bitter / water taste-neuron lists from sim/shiu_model.py, read as text
    (importing that file would load Brian2)."""
    tree = ast.parse((ROOT / "sim" / "shiu_model.py").read_text(encoding="utf-8"))
    wanted = {"SUGAR_R_630": "sugar", "BITTER_R_630": "bitter", "WATER_R_630": "water"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in wanted:
            out[wanted[node.targets[0].id]] = [int(x) for x in ast.literal_eval(node.value)]
    assert set(out) == set(wanted.values())
    return out


def jo_ce_ids():
    """The paper's 70 JO-C/E neuron IDs (experiments/heldout/ids.py, copied from the
    paper's own Figure 5 code)."""
    spec = importlib.util.spec_from_file_location("heldout_ids", ROOT / "experiments" / "heldout" / "ids.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [int(x) for x in mod.JON_CE]


def load_labels():
    return pd.read_parquet(LABELS, columns=["root_id", "super_class", "cell_class",
                                            "hemibrain_type", "cell_type", "side"])


#: name: (label, how the input set is found, rate Hz, where the set and rate come from)
DECISION_SPECS = {
    "sugar": ("Sugar -> feeding (MN9)", "paper:sugar", 100.0,
              "paper sugar list (sim/shiu_model.py); 100 Hz = paper Fig. 1 / Phase 3 standard"),
    "bitter": ("Bitter taste", "paper:bitter", 200.0,
               "paper bitter list; 200 Hz as in Phase 3 / Phase 7 (experiments/phase7_signs)"),
    "water": ("Water taste", "paper:water", 200.0,
              "paper water list; 200 Hz as in Phase 3 / Phase 7 (experiments/phase7_signs)"),
    "smell_DA1": ("Smell: DA1 (cVA pheromone)", "hb:ORN_DA1", 150.0,
                  "all 126 DA1 receptor neurons, both antennae, 150 Hz = scorecard FC5 main condition"),
    "smell_DM1": ("Smell: DM1", "hb:ORN_DM1", 150.0,
                  "all 68 DM1 receptor neurons, both sides, 150 Hz = Phase 5 / Phase 7 runaway condition"),
    "groom_JO": ("Grooming (Johnston's organ JO-C/E)", "jo_ce", 220.0,
                 "paper's 70 JO-C/E neurons; 220 Hz = paper Fig. 5 top rate (experiments/heldout)"),
    "cool": ("Temperature: cool", "hb:TRN_VP3a|TRN_VP3b", 150.0,
             "9 cool receptor neurons (TRN_VP3a/b), 150 Hz = scorecard TH1"),
    "warm": ("Temperature: warm", "hb:TRN_VP2", 150.0,
             "7 warm receptor neurons (TRN_VP2), 150 Hz = scorecard TH2"),
}


def decisions(lab):
    """{name: dict(label, ids (np.int64), rate_hz, source)}."""
    pids = paper_ids()
    hb = lab.hemibrain_type.fillna("").to_numpy()
    rid = lab.root_id.to_numpy()
    out = {}
    for name, (label, how, rate, src) in DECISION_SPECS.items():
        if how.startswith("paper:"):
            ids = np.array(pids[how.split(":")[1]], np.int64)
        elif how.startswith("hb:"):
            types = how.split(":")[1].split("|")
            ids = rid[np.isin(hb, types)].astype(np.int64)
        elif how == "jo_ce":
            ids = np.array(jo_ce_ids(), np.int64)
        else:
            raise ValueError(how)
        out[name] = dict(label=label, ids=ids, rate_hz=rate, source=src)
    sizes = {k: v["ids"].size for k, v in out.items()}
    assert sizes["smell_DA1"] == 126 and sizes["smell_DM1"] == 68, sizes
    assert sizes["cool"] == 9 and sizes["warm"] == 7 and sizes["groom_JO"] == 70, sizes
    return out


def wiring_counts(brain):
    """(out_synapses, out_connections) per neuron row, from the brain's own wiring."""
    counts = np.diff(brain._indptr)
    pre = np.repeat(np.arange(brain.n_neurons, dtype=np.int64), counts)
    syn = np.bincount(pre, weights=np.abs(brain._count).astype(np.float64),
                      minlength=brain.n_neurons)
    return np.rint(syn).astype(np.int64), counts.astype(np.int64)


def run_trial(brain, exc_idx, prob, seed, k, n_steps, p):
    """Trial k of ``seed``: the same random input as trial k of FastBrain.run(seed=seed)."""
    ss = np.random.SeedSequence(seed).spawn(k + 1)[k]
    ev = brain._poisson_events(np.random.default_rng(ss), exc_idx, prob, n_steps)
    return brain._run_events([ev], exc_idx, (), n_steps, p, ())
