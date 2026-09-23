"""Shared helpers for the Phase 8 experiments (learning in the mushroom body).

Plain English
-------------
* Two made-up "odors", A and B, each = 4 olfactory channels (glomeruli)
  with no overlap. They were picked so both reach the Kenyon cells equally
  strongly (about 43,000 projection-neuron -> Kenyon-cell synapses each) and
  have the same number of smell neurons (215 ORNs each). They are NOT meant
  to be any particular real odor.
* Three model versions ("models"):
  - ``circuit``: only the mushroom-body circuit (all 685 projection neurons,
    5,177 Kenyon cells, 97 output neurons, 326 dopamine neurons, APL, DPM)
    with its real connections; the odor is given directly to the projection
    neurons of the odor's glomeruli. Fast, and free of the antennal-lobe
    runaway problem.
  - ``brain_alln``: the whole brain with the recommended sign fix
    (sim/sign_fixes.py RECOMMENDED_FIX = "al_ln_literature" since 2026-09-23;
    evidence in docs/phase7-neurotransmitter-audit.md). MAIN whole-brain model.
    The odor is given to the smell receptor neurons (ORNs).
  - ``brain_eln``: the fix that was recommended on 2026-09-22 ("eln_electrical",
    since superseded); kept because it was run.
  - ``brain_none``: the whole published brain, no fix (for comparison).
  - ``brain_ln53``: the Phase 5 "LN-fix" ("ln53_inhibitory"); the audit found it
    wrong for 34 cells. Comparison only.
* ``get_model`` builds one (never two whole brains at once).
"""

from __future__ import annotations

import gc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.fast_engine import FastBrain  # noqa: E402
from sim.plasticity import (HIGE_PULSES_MS, LearningRule, PlasticBrain,  # noqa: E402
                            extract_circuit, load_labels, mb_circuit_rows, odor_rows,
                            pulse_blocks)

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
PLOTS = HERE / "plots"
RES.mkdir(exist_ok=True)
PLOTS.mkdir(exist_ok=True)
CIRCUIT_NPZ = RES / "circuit_630.npz"

ODOR_GLOMERULI = {
    "A": ("DM1", "DC1", "VA2", "DM4"),
    "B": ("DP1m", "DM2", "DL1", "VA6"),
}

#: Input rates. PN rate for the circuit and ORN rate for the whole brain
#: (set in the odor-calibration step, see run_phase8.py "odors").
PN_RATE_HZ = 100.0
ORN_RATE_HZ = 100.0

N_THREADS = 2

# whole-brain model name -> sign fix in sim/sign_fixes.py (explicit, so a later change of
# RECOMMENDED_FIX can never silently relabel results already on disk)
WHOLE_BRAINS = {"brain_alln": "al_ln_literature", "brain_eln": "eln_electrical",
                "brain_none": "none", "brain_ln53": "ln53_inhibitory"}


def free_ram_gb():
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / 1e9
    except Exception:
        return float("nan")


def wait_for_ram(min_gb=1.5):
    import time
    while True:
        f = free_ram_gb()
        if not (f < min_gb):
            return f
        print(f"  free RAM {f:.2f} GB < {min_gb} GB, waiting 30 s", flush=True)
        time.sleep(30)


def _build_circuit_arrays(labels):
    """Extract the MB circuit from the published whole brain once, save it."""
    wait_for_ram()
    brain = FastBrain(snapshot="630", n_threads=1)
    rows = mb_circuit_rows(labels)
    circ, rows = extract_circuit(brain, rows, n_threads=N_THREADS)
    # recover (pre, post, signed) from the circuit's CSR
    pre = np.repeat(np.arange(circ.n_neurons), np.diff(circ._indptr))
    np.savez_compressed(CIRCUIT_NPZ, rows=rows, root_ids=circ.root_ids, pre=pre,
                        post=circ._post.astype(np.int64), signed=circ._count.astype(np.int64))
    del brain
    gc.collect()


def get_model(name, dan_mode="modulatory", rule=None, labels=None):
    """(PlasticBrain, labels_for_its_rows, stim_kind) for model ``name``."""
    labels = load_labels() if labels is None else labels
    rule = rule or LearningRule()
    if name == "circuit":
        if not CIRCUIT_NPZ.exists():
            _build_circuit_arrays(labels)
        z = np.load(CIRCUIT_NPZ)
        brain = FastBrain.from_arrays(z["root_ids"], z["pre"], z["post"], z["signed"],
                                      n_threads=N_THREADS)
        lab = labels.iloc[z["rows"]].reset_index(drop=True)
        return PlasticBrain(brain, lab, rule, dan_mode=dan_mode), lab, "pn"
    if name in WHOLE_BRAINS:
        from sim.sign_fixes import build_brain
        wait_for_ram()
        fix = WHOLE_BRAINS[name]
        print(f"building whole brain with sign fix '{fix}'", flush=True)
        brain = build_brain(fix=fix, snapshot="630", n_threads=N_THREADS)
        gc.collect()
        return PlasticBrain(brain, labels, rule, dan_mode=dan_mode), labels, "orn"
    raise ValueError(name)


def odor_input_rows(lab, kind):
    return {k: odor_rows(lab, g, kind=kind) for k, g in ODOR_GLOMERULI.items()}


def type_rows(lab, prefix_or_types):
    hb = lab.hemibrain_type.to_numpy()
    if isinstance(prefix_or_types, str):
        prefix_or_types = (prefix_or_types,)
    return np.flatnonzero(np.isin(hb, list(prefix_or_types)))
