"""Shared helpers for the "does the model smell like a real fly?" lane.

Plain English
-------------
* ``groups(lab)``: which model rows are ORNs (per glomerulus), uniglomerular projection
  neurons (uPNs, per glomerulus), antennal-lobe local neurons (LNs), Kenyon cells (KCs),
  APL, MBONs, DANs and lateral-horn neurons, using the snapshot-630 labels.
* ``odour_rates(...)``: the firing rate to give every ORN for one odour: its glomerulus's
  spontaneous rate plus the measured odour response (Hallem & Carlson 2006), never below 0.
* ``summarise(res, grp)``: spike counts per trial for the read-out groups, plus the
  Phase 6 runaway test (more than 1,500 different neurons firing in any 10 ms slice).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RES = HERE / "results"
PLOTS = HERE / "plots"
RES.mkdir(exist_ok=True)
PLOTS.mkdir(exist_ok=True)
LABELS = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"

#: spontaneous rate for ORN types Hallem & Carlson did not test: the median of the 23
#: tested types (12 spikes/s). An assumption, not a measurement for those types.
DEFAULT_SFR_HZ = 12.0
RUNAWAY_DISTINCT_10MS = 1500     # Phase 6 definition (docs/phase6-runaway-activity.md)
N_THREADS = 3


def free_ram_gb():
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 1e9


def wait_for_ram(min_gb=1.5):
    import time
    while True:
        f = free_ram_gb()
        if f >= min_gb:
            return f
        print(f"  free RAM {f:.2f} GB < {min_gb} GB, waiting 30 s", flush=True)
        time.sleep(30)


def load_labels(root_ids=None):
    cols = ["root_id", "super_class", "cell_class", "cell_sub_class", "hemibrain_type",
            "cell_type", "side"]
    lab = pd.read_parquet(LABELS, columns=cols)
    for c in cols[1:]:
        lab[c] = lab[c].astype(object).where(lab[c].notna(), "").astype(str)
    if root_ids is not None:
        if not np.array_equal(lab.root_id.to_numpy(np.int64), np.asarray(root_ids, np.int64)):
            raise ValueError("label file is not in the brain's row order")
    return lab


def pn_glomerulus(t: str) -> str:
    return str(t).split("_")[0]


def groups(lab):
    cc, hb, sub = lab.cell_class.to_numpy(), lab.hemibrain_type.to_numpy(), lab.cell_sub_class.to_numpy()
    sc = lab.super_class.to_numpy()
    is_orn = (sc == "sensory") & (cc == "olfactory") & np.char.startswith(hb.astype(str), "ORN_")
    g = {
        "orn": np.flatnonzero(is_orn),
        "pn": np.flatnonzero(cc == "ALPN"),
        "upn": np.flatnonzero((cc == "ALPN") & (sub == "uniglomerular")),
        "ln": np.flatnonzero(cc == "ALLN"),
        "kc": np.flatnonzero(cc == "Kenyon_Cell"),
        "apl": np.flatnonzero(hb == "APL"),
        "mbon": np.flatnonzero(cc == "MBON"),
        "dan": np.flatnonzero(cc == "DAN"),
        "lhn": np.flatnonzero(np.isin(cc, ["LHLN", "LHCENT"])),
    }
    g["orn_glom"] = np.array([h.replace("ORN_", "") for h in hb[g["orn"]]])
    g["upn_glom"] = np.array([pn_glomerulus(h) for h in hb[g["upn"]]])
    return g


def readout_rows(g):
    """Rows whose per-trial spike counts are saved, and the slice of each group."""
    order = ["orn", "pn", "ln", "kc", "apl", "mbon", "dan", "lhn"]
    rows = np.concatenate([g[k] for k in order])
    sl, i = {}, 0
    for k in order:
        sl[k] = (i, i + g[k].size)
        i += g[k].size
    return rows, sl


def odour_rates(root_ids, g, sfr_by_glom, delta_by_glom, scale=1.0):
    """{root_id: rate_hz} for every ORN: spontaneous + scale * odour response, >= 0.
    Glomeruli missing from ``sfr_by_glom`` get DEFAULT_SFR_HZ; missing from
    ``delta_by_glom`` (or NaN) get no odour response."""
    out = {}
    for row, glo in zip(g["orn"], g["orn_glom"]):
        s = float(sfr_by_glom.get(glo, DEFAULT_SFR_HZ))
        d = delta_by_glom.get(glo, 0.0)
        d = 0.0 if d is None or not np.isfinite(d) else float(d)
        r = max(0.0, s + scale * d)
        if r > 0:
            out[int(root_ids[row])] = r
    return out


def summarise(res, rows, n_neurons, exclude=None):
    """Per-trial spike counts for ``rows`` (array trials x rows, uint16) and per-trial
    whole-brain stats: total spikes, active neurons, max distinct neurons in a 10 ms slice.
    ``exclude``: rows left out of the runaway count (the driven ORNs: with a whole odour
    up to ~1,400 of them fire in one 10 ms slice, which is input, not runaway)."""
    nt = res.n_trials
    counts = np.zeros((nt, rows.size), np.uint16)
    pos = np.full(n_neurons, -1, np.int64)
    pos[rows] = np.arange(rows.size)
    stats = []
    bin_steps = int(round(10.0 / res.dt_ms))
    for t in range(nt):
        m = res.trial == t
        nrn, stp = res.neuron[m], res.step[m]
        p = pos[nrn]
        k = p >= 0
        c = np.bincount(p[k], minlength=rows.size)
        counts[t] = np.minimum(c, 65535)
        keep = np.ones(nrn.size, bool) if exclude is None else ~np.isin(nrn, exclude)
        if keep.any():
            b = stp[keep] // bin_steps
            key = np.unique(b.astype(np.int64) * n_neurons + nrn[keep])
            distinct = np.bincount(key // n_neurons).max()
        else:
            distinct = 0
        stats.append({"trial": t, "total_spikes": int(nrn.size),
                      "n_active": int(np.unique(nrn).size),
                      "max_distinct_10ms": int(distinct),
                      "runaway": bool(distinct > RUNAWAY_DISTINCT_10MS)})
    return counts, stats
