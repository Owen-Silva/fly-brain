"""Small helpers shared by the Phase 5 competition and olfaction scripts.

Plain English
-------------
* ``paper_ids()`` reads the paper's neuron ID lists (sugar, bitter, water,
  Ir94e GRNs and MN9) straight out of sim/shiu_model.py *without importing it*
  (importing it would load Brian2, which costs memory we do not have). IDs
  stay whole 64-bit integers, never floats.
* ``labels()`` loads the per-neuron labels (cell type, side, transmitter) for
  snapshot 630 from the Phase 2 cache, in the same row order as the brain.
* ``get_brain()`` hands back the brain that the job server already built, or
  builds one if a script is run on its own.
* ``per_trial_rates()`` turns a simulation result into a (trials x neurons)
  table of firing rates, so we can report spread across trials, not just means.
* ``out_signs()`` gives each neuron's sign as the model uses it (+1 excites
  its targets, -1 inhibits them), read from the brain's own connection list.
"""

import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SHIU_MODEL = ROOT / "sim" / "shiu_model.py"
LABELS_630 = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"


def paper_ids():
    """{'SUGAR': [...], 'BITTER': [...], 'WATER': [...], 'IR94E': [...],
    'MN9': int, 'MN9_IPSI': int} as Python ints (exact, 18 digits)."""
    tree = ast.parse(SHIU_MODEL.read_text(encoding="utf-8"))
    wanted = {"SUGAR_R_630": "SUGAR", "BITTER_R_630": "BITTER", "WATER_R_630": "WATER",
              "IR94E_630": "IR94E", "MN9_LEFT": "MN9", "MN9_RIGHT_630": "MN9_IPSI"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], "id", None)
            if name in wanted:
                out[wanted[name]] = ast.literal_eval(node.value)
    missing = set(wanted.values()) - set(out)
    if missing:
        raise KeyError(f"could not find {missing} in {SHIU_MODEL}")
    sizes = {k: len(v) for k, v in out.items() if isinstance(v, list)}
    assert sizes == {"SUGAR": 21, "BITTER": 21, "WATER": 18, "IR94E": 18}, sizes
    return out


def labels(columns=("root_id", "super_class", "cell_class", "cell_sub_class", "cell_type",
                    "hemibrain_type", "side", "top_nt", "sign", "ref_sign")):
    df = pd.read_parquet(LABELS_630, columns=list(columns))
    assert df["root_id"].dtype == np.int64
    # Missing labels become "" (not pandas NA), so yes/no filters never hit
    # "the truth value of NA is ambiguous".
    for c in df.columns:
        if c not in ("root_id", "sign", "ref_sign"):
            df[c] = df[c].astype(object).where(df[c].notna(), "").astype(str)
    return df


def get_brain(g):
    """The job server passes ``brain`` in the script's globals; else build one."""
    if "brain" in g and g["brain"] is not None:
        return g["brain"]
    from sim.fast_engine import FastBrain
    return FastBrain(snapshot="630", n_threads=2)


def per_trial_rates(res, idx):
    """Rates (Hz) per trial for neuron row numbers ``idx``: shape (trials, len(idx))."""
    idx = np.asarray(idx, np.int64)
    out = np.zeros((res.n_trials, idx.size))
    pos = -np.ones(len(res.root_ids), np.int64)
    pos[idx] = np.arange(idx.size)
    m = pos[res.neuron] >= 0
    np.add.at(out, (res.trial[m], pos[res.neuron[m]]), 1.0)
    return out / (res.duration_ms * 1e-3)


def out_signs(brain):
    """+1 / -1 / 0 per neuron: the sign of its outgoing connections in the model."""
    first = np.zeros(brain.n_neurons, np.int64)
    has = np.diff(brain._indptr) > 0
    first[has] = np.sign(brain._count[brain._indptr[:-1][has]])
    return first


def outgoing(brain, i):
    """(targets, signed synapse counts) of neuron row ``i``."""
    a, b = brain._indptr[i], brain._indptr[i + 1]
    return brain._post[a:b].astype(np.int64), brain._count[a:b].astype(np.int64)
