"""Shared helpers for the "does the runaway, and its fix, hold on snapshot 783?" lane.

Plain English
-------------
* The brain wiring comes in two FlyWire releases ("snapshots"): 630, the one
  the Shiu et al. 2024 paper used and all our earlier work used, and 783, the
  newer public release. A neuron's ID number changes whenever it is edited, so
  the same cell can have different IDs in the two snapshots.
* ``labels(snapshot, root_ids)``: a label table (cell class, cell type, side,
  literature transmitter ``known_nt``) for every model neuron, in the model's
  row order. For 630 it is exactly ``sim/sign_fixes.neuron_table`` (the labels
  the fix was defined with). For 783 every label is read straight from
  FlyWire's snapshot-783 annotation file by root ID; the ORN types live in the
  ``cell_type`` column there (630 keeps them in ``hemibrain_type``; see
  experiments/banc_asymmetry/a0_check_port_flywire.py).
* ``fix_al_ln_literature(...)``: our own re-implementation of the recommended
  fix "al_ln_literature" (sim/sign_fixes.py). It only needs, per neuron: "is it
  an antennal-lobe local neuron (cell class ALLN)?" and "what sign does its
  literature transmitter give (+1 / -1 / 0)?", so it runs on either snapshot.
  s1_port_check.py proves that on 630 it gives exactly the same connections
  as ``build_brain(fix="al_ln_literature")``.
* ``map_630_to_783``: finds a 630 neuron's 783 ID through its representative
  supervoxel (a fixed piece of the microscope volume, listed in both annotation
  files), with "same root ID" as the fallback. This is how the fix's own 630
  cells are looked up in 783.
* ``run_chunk`` / ``trial_rows``: copied from experiments/phase7_signs/common.py
  (same trial seeding, same runaway rule), with a ``silence`` option and a
  783-safe read-out (the second MN9 does not exist in 783).
  RUNAWAY = more than 1,500 different neurons fire in some 10 ms slice.
"""

from __future__ import annotations

import ast
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / "results"
PLOTS = HERE / "plots"
RESULTS.mkdir(exist_ok=True)
PLOTS.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

from sim import sign_fixes as S  # noqa: E402  (read-only use)
from sim.fast_engine import FastBrain  # noqa: E402

ANN_630 = ROOT / "data" / "flywire" / "Supplemental_file1_annotations_v1.1.0_630.tsv"
ANN_783 = ROOT / "data" / "flywire" / "Supplemental_file1_neuron_annotations.tsv"
RUNAWAY_DISTINCT_10MS = 1500
ONSET_SPIKES_PER_MS = 200
MN9 = 720575940660219265
ELN_SOURCE = "Shang et al., 2007"


# ---------------------------------------------------------------------------
# Memory guard (RAM is shared with another lane)
# ---------------------------------------------------------------------------
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
    while free_ram_gb() < min_gb:
        print(f"  free RAM {free_ram_gb():.2f} GB < {min_gb}; waiting 30 s", flush=True)
        time.sleep(30)


# ---------------------------------------------------------------------------
# The paper's IDs
# ---------------------------------------------------------------------------
def paper_ids():
    """The paper's 630 ID lists and the Phase 3 630->783 successor map, read as
    text from sim/shiu_model.py (importing it would load Brian2)."""
    tree = ast.parse((ROOT / "sim" / "shiu_model.py").read_text(encoding="utf-8"))
    wanted = {"SUGAR_R_630": "SUGAR", "BITTER_R_630": "BITTER", "WATER_R_630": "WATER",
              "IR94E_630": "IR94E", "MN9_LEFT": "MN9", "MN9_RIGHT_630": "MN9_IPSI",
              "ID_630_TO_783": "MAP"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in wanted:
            out[wanted[node.targets[0].id]] = ast.literal_eval(node.value)
    assert set(out) == set(wanted.values())
    return out


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
def labels(snapshot, root_ids):
    """Label table in the model's row order (see module docstring).

    Columns always present: root_id, super_class, cell_class, cell_type,
    hemibrain_type, side, top_nt, known_nt, known_nt_source, known_sign,
    known_kind, matched.
    """
    root_ids = np.asarray(root_ids, dtype=np.int64)
    if str(snapshot) == "630":
        lab = S.neuron_table(root_ids)
        lab["matched"] = lab["matched_783"]
        return lab
    cols = ["root_id", "supervoxel_id", "super_class", "cell_class", "cell_type",
            "hemibrain_type", "side", "top_nt", "known_nt", "known_nt_source"]
    a = pd.read_csv(ANN_783, sep="\t", usecols=cols, dtype={c: "string" for c in cols[2:]}
                    | {"root_id": "int64", "supervoxel_id": "int64"})
    a = a.drop_duplicates("root_id").set_index("root_id")
    matched = np.isin(root_ids, a.index.to_numpy())
    a = a.reindex(root_ids)
    a.index.name = "root_id"
    lab = a.reset_index()
    for c in cols[2:]:
        lab[c] = lab[c].astype(object).where(lab[c].notna(), "").astype(str)
    ks = [S.known_nt_sign(k if k else None) for k in lab.known_nt.to_numpy()]
    lab["known_sign"] = np.array([s for s, _ in ks], np.int8)
    lab["known_kind"] = [k for _, k in ks]
    lab["matched"] = matched
    return lab


def eln_mask(lab):
    """Same rule as sim/sign_fixes.eln_mask: ALLN, literature acetylcholine,
    citing Shang et al. 2007."""
    return ((lab.cell_class.to_numpy() == "ALLN")
            & (lab.known_sign.to_numpy() == 1)
            & lab.known_nt_source.astype(str).str.contains(ELN_SOURCE, regex=False).to_numpy())


def map_630_to_783(ids630):
    """{630 root ID: (783 root ID or -1, method)}; method is "supervoxel",
    "same_root_id" (fallback) or "not_found". The 783 ID must be a model neuron
    (listed in Completeness_783.csv)."""
    ids630 = np.asarray(ids630, np.int64)
    a630 = pd.read_csv(ANN_630, sep="\t", usecols=["supervoxel_id", "root_id"],
                       dtype={"root_id": "int64", "supervoxel_id": "int64"})
    a630 = a630.drop_duplicates("root_id").set_index("root_id").supervoxel_id
    a783 = pd.read_csv(ANN_783, sep="\t", usecols=["supervoxel_id", "root_id"],
                       dtype={"root_id": "int64", "supervoxel_id": "int64"})
    sv2rid = a783.drop_duplicates("supervoxel_id").set_index("supervoxel_id").root_id
    model783 = set(pd.read_csv(ROOT / "data" / "reference" / "Completeness_783.csv",
                               index_col=0).index.astype(np.int64).tolist())
    out = {}
    for i in ids630.tolist():
        rid, how = -1, "not_found"
        if i in a630.index:
            sv = int(a630.loc[i])
            if sv in sv2rid.index and int(sv2rid.loc[sv]) in model783:
                rid, how = int(sv2rid.loc[sv]), "supervoxel"
        if rid < 0 and i in model783:
            rid, how = i, "same_root_id"
        out[i] = (rid, how)
    return out


# ---------------------------------------------------------------------------
# The fix, re-implemented (rule of sim/sign_fixes.apply_fix, "al_ln_literature")
# ---------------------------------------------------------------------------
def neuron_signs(n, pre, signed):
    """+1 / -1 / 0 (no outgoing connections) per neuron from the signed list."""
    s = np.sign(signed).astype(np.int64)
    pos = np.bincount(pre, weights=(s > 0), minlength=n)
    neg = np.bincount(pre, weights=(s < 0), minlength=n)
    if ((pos > 0) & (neg > 0)).any():
        raise ValueError("a neuron has both signs")
    return np.where(pos > 0, 1, np.where(neg > 0, -1, 0)).astype(np.int8)


def fix_al_ln_literature(pre, post, signed, is_alln, known_sign):
    """Return (pre, post, signed, info) with the al_ln_literature rule applied:

    1. an antennal-lobe local neuron (ALLN) the model makes excitatory whose
       literature transmitter is GABA or glutamate becomes inhibitory;
    2. every other excitatory ALLN keeps its sign but keeps chemical
       connections only onto neurons that are inhibitory (after rule 1).
    Connection order is kept; removed connections are left out.
    """
    n = int(np.asarray(is_alln).size)
    sign = neuron_signs(n, pre, signed)
    is_alln = np.asarray(is_alln, bool)
    known_sign = np.asarray(known_sign)
    to_inh = is_alln & (sign == 1) & (known_sign == -1)
    new_sign = np.where(to_inh, -1, sign)
    exc_ln = is_alln & (new_sign == 1)
    drop = exc_ln[pre] & (new_sign[post] != -1)
    flip = to_inh[pre] & ~drop
    signed2 = signed.copy()
    signed2[flip] = -signed2[flip]
    keep = ~drop
    info = dict(to_inhibitory=int(to_inh.sum()), excitatory_lns=int(exc_ln.sum()),
                removed_connections=int(drop.sum()), removed_synapses=int(np.abs(signed[drop]).sum()),
                flipped_connections=int(flip.sum()), flipped_synapses=int(np.abs(signed[flip]).sum()),
                to_inh_idx=np.flatnonzero(to_inh), exc_ln_idx=np.flatnonzero(exc_ln))
    return pre[keep], post[keep], signed2[keep], info


def same_cells_masks(rid783):
    """For the "same cells" variant on 783: (is_target, known_sign) arrays that
    make the rule pick exactly the 630 fix's own cells, found in 783 by
    supervoxel (results/fix_cells_630_in_783.csv, written by s0): the 13 cells
    made inhibitory in 630 get literature sign -1; all 150 are the targets
    (a target the 783 model already makes inhibitory is left alone by the rule)."""
    f = pd.read_csv(RESULTS / "fix_cells_630_in_783.csv")
    f = f[f.root_id_783 > 0]
    rid783 = np.asarray(rid783, np.int64)
    target = np.isin(rid783, f.root_id_783.to_numpy(np.int64))
    ks = np.zeros(rid783.size, np.int8)
    ks[np.isin(rid783, f[f.role_630 == "to_inhibitory"].root_id_783.to_numpy(np.int64))] = -1
    return target, ks


def build(snapshot, fix, lab=None, n_threads=2, return_info=False):
    """A FastBrain for ``snapshot`` ("630"/"783"): fix "none" (the published
    model, same arrays as FastBrain(snapshot)), "al_ln_literature" (the rule,
    ported: applied to that snapshot's own labels) or, 783 only,
    "same_cells" (the rule applied to exactly the 630 fix's cells)."""
    rid, pre, post, signed = S.load_reference_arrays(str(snapshot))
    info = {}
    if fix == "al_ln_literature":
        if lab is None:
            lab = labels(snapshot, rid)
        pre, post, signed, info = fix_al_ln_literature(
            pre, post, signed, lab.cell_class.to_numpy() == "ALLN", lab.known_sign.to_numpy())
    elif fix == "same_cells":
        if str(snapshot) != "783":
            raise ValueError("same_cells is a 783 variant")
        target, ks = same_cells_masks(rid)
        pre, post, signed, info = fix_al_ln_literature(pre, post, signed, target, ks)
    elif fix != "none":
        raise ValueError(fix)
    brain = FastBrain.from_arrays(rid, pre, post, signed, n_threads=n_threads)
    brain.snapshot = f"{snapshot}+{fix}(port)"
    return (brain, info) if return_info else brain


# ---------------------------------------------------------------------------
# Running and measuring (after experiments/phase7_signs/common.py)
# ---------------------------------------------------------------------------
def run_chunk(brain, excite, seed, a, b, duration_ms=1000.0, params=None, silence=()):
    """Trials a..b-1 of ``seed``, identical to those trials of
    brain.run(seed=seed, n_trials>=b)."""
    p = brain._params_for(params)
    ids = np.array(list(excite.keys()), np.int64)
    rates = np.array(list(excite.values()), float)
    exc_idx = brain.index_of(ids)
    n_steps = int(round(duration_ms / p["dt"]))
    prob = rates * p["dt"] * 1e-3
    seqs = np.random.SeedSequence(seed).spawn(b)[a:b]
    ev = [brain._poisson_events(np.random.default_rng(s), exc_idx, prob, n_steps) for s in seqs]
    return brain._run_events(ev, exc_idx, silence, n_steps, p, ())


def run_volley(brain, trig_ids, duration_ms=1000.0, at_step=50, silence=()):
    """The given neurons each fire once at ``at_step`` (5 ms); no other input."""
    trig = np.asarray(trig_ids, np.int64)
    return brain.run_with_input_events([(np.full(trig.size, at_step), trig)], excite=trig,
                                       silence=silence, duration_ms=duration_ms)


class Readout:
    def __init__(self, brain, lab):
        self.n = brain.n_neurons
        self.mn9 = int(brain.index_of([MN9])[0])
        self.is_kc = lab.cell_class.to_numpy() == "Kenyon_Cell"


def trial_rows(res, rd, meta, dt_ms=0.1):
    """One dict per trial, plus the spikes per neuron summed over the trials."""
    rows = []
    n_steps = int(round(res.duration_ms / dt_ms))
    per10 = int(round(10 / dt_ms))
    per1 = int(round(1 / dt_ms))
    n10 = n_steps // per10
    last100 = n_steps - int(round(100 / dt_ms))
    counts = np.bincount(res.neuron, minlength=rd.n).astype(np.int64)
    dur_s = res.duration_ms * 1e-3
    for t in range(res.n_trials):
        m = res.trial == t
        st, nu = res.step[m].astype(np.int64), res.neuron[m].astype(np.int64)
        key = np.unique((st // per10) * 1_000_000 + nu)
        d10 = np.bincount(key // 1_000_000, minlength=n10)[:n10]
        per_ms = np.bincount(st // per1, minlength=n_steps // per1)
        on = np.flatnonzero(per_ms > ONSET_SPIKES_PER_MS)
        uniq = np.unique(nu)
        row = dict(meta, trial=meta.get("trial0", 0) + t,
                   total_spikes=int(st.size), n_active=int(uniq.size),
                   max_distinct_10ms=int(d10.max()) if d10.size else 0,
                   runaway=bool(d10.size and d10.max() > RUNAWAY_DISTINCT_10MS),
                   onset_ms=int(on[0]) if on.size else -1,
                   distinct_last_100ms=int(np.unique(nu[st >= last100]).size),
                   mn9_hz=float((nu == rd.mn9).sum() / dur_s),
                   kc_active=int(rd.is_kc[uniq].sum()))
        row.pop("trial0", None)
        rows.append(row)
    return rows, counts


def append_csv(path, rows):
    df = pd.DataFrame(rows)
    df.to_csv(path, mode="a", header=not Path(path).exists(), index=False)
