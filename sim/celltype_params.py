"""Phase 7 upgrade 4: cell-type-specific neuron parameters.

What this is, in plain English
------------------------------
The baseline model (``sim/fast_engine.py``, Shiu et al. 2024) gives every one
of the 127,400 neurons the same settings: it rests at -52 mV, fires when it
gets 7 mV above rest (-45 mV), goes back to rest after a spike, forgets its
input with a 20 ms "membrane time constant", and cannot fire again for 2.2 ms.

Where somebody has actually measured a fly cell type with an electrode, this
upgrade gives that cell type its measured numbers instead. Everything that was
not measured keeps the shared values. The measured numbers, one row per number
with its paper, page/figure and recording conditions, live in
``experiments/phase7_celltype/celltype_params.csv``; this file reads that table.

How a measured number becomes a model setting
---------------------------------------------
The model neuron has only four settings that can differ per neuron:

* membrane time constant ``t_mbr`` (how long the neuron "remembers" input):
  taken directly from the paper (or from the paper's own resistance x
  capacitance, which is the same thing);
* resting potential ``v_0`` (also the reset value after a spike, as in the
  baseline);
* threshold ``v_th``: always set as a GAP above the neuron's own rest
  (measured threshold minus measured rest from the same recordings). In this
  model a synapse pushes the voltage by a fixed number of millivolts whatever
  the voltage is, so only the gap matters: moving rest and threshold together
  changes nothing. A neuron with a measured rest but no measured threshold
  therefore keeps the shared 7 mV gap (its rest alone has no effect);
* refractory period ``t_rfc``: none of the papers read reports one, so every
  neuron keeps 2.2 ms (the code supports it anyway).

What cannot be used: the model has no electrical current (a synapse's effect
is already expressed in millivolts), so an input resistance or a threshold
current (rheobase) has nowhere to go. See docs/phase7-celltype-params.md.

The engine is not edited: ``CellTypeBrain`` is a subclass of ``FastBrain``
with a copy of its compiled loop that looks the four settings up per neuron.
With no measured values (or the switch off) it gives exactly the baseline's
spikes (tests/test_celltype_params.py checks this spike for spike, on small
networks and on the whole brain).

Sources (details and page/figure numbers in the CSV)
----------------------------------------------------
* Gouwens NW, Wilson RI (2009) J Neurosci 29:6239 - projection neuron
  membrane time constant (Table 1) and corrected resting potential (Fig. 7).
* Jeanne JM, Wilson RI (2015) Neuron 88:1014 - projection neuron distance to
  spike threshold, about 10 mV (Fig. 4C).
* Turner GC, Bazhenov M, Laurent G (2008) J Neurophysiol 99:734 - Kenyon cell
  threshold 21.5 mV above rest (p. 741, Fig. 3G), holding potential -57.8 mV,
  one-compartment time constant 11.2 ms (p. 737).
* Turner-Evans D et al. (2017) eLife 6:e23496 - P-EN resting potential and
  spike threshold (Supplementary file 1).
* Sheeba V et al. (2008) J Neurophysiol 99:976 - large LNv resting potential,
  capacitance and input resistance (tau = R x C).
"""

from __future__ import annotations

import csv
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numba as nb
import numpy as np
import pandas as pd

from sim.fast_engine import (
    DEFAULT_PARAMS, PROJECT_ROOT, FastBrain, SimResult, _NEVER, _as_root_ids, _timestep,
    _update_constants,
)

TABLE_PATH = PROJECT_ROOT / "experiments" / "phase7_celltype" / "celltype_params.csv"
LABELS_DIR = PROJECT_ROOT / "data" / "cache"

#: The per-neuron settings a table row can set, and the unit it is given in.
MODEL_PARAMS = ("t_mbr_ms", "v_th_gap_mV", "v_0_mV", "t_rfc_ms")


def _sel_upn(df):
    return ((df["cell_class"] == "ALPN") & (df["cell_sub_class"] == "uniglomerular")
            & (df["top_nt"] == "acetylcholine"))


def _sel_kc(df):
    return df["cell_class"] == "Kenyon_Cell"


def _sel_pen(df):
    return df["hemibrain_type"].isin(["PEN_a(PEN1)", "PEN_b(PEN2)"])


def _sel_llnv(df):
    return df["hemibrain_type"] == "l-LNv"


#: Which FlyWire neurons belong to each cell group of the table (the CSV's
#: ``flywire_selector`` column says the same thing in words).
SELECTORS = {
    "uPN_ACh": _sel_upn,   # cholinergic uniglomerular antennal lobe projection neurons
    "KC": _sel_kc,         # Kenyon cells
    "PEN": _sel_pen,       # central-complex P-EN neurons (both FlyWire PEN types)
    "lLNv": _sel_llnv,     # large ventral lateral clock neurons
}


def read_table(path=TABLE_PATH):
    """All rows of the parameter table (list of dicts, strings as written)."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def applied_values(rows=None, path=TABLE_PATH):
    """{cell_group: {model_param: value}} for the rows that are used in the
    model (``model_param`` not '-'). Raises if a group sets the same parameter
    twice or a used row has no source."""
    rows = read_table(path) if rows is None else rows
    out = {}
    for r in rows:
        mp = (r.get("model_param") or "-").strip()
        if mp in ("", "-"):
            continue
        if mp not in MODEL_PARAMS:
            raise ValueError(f"row {r['row']}: unknown model_param {mp!r}")
        if not r.get("source", "").strip():
            raise ValueError(f"row {r['row']}: a value used in the model needs a source")
        g = r["cell_group"].strip()
        d = out.setdefault(g, {})
        if mp in d:
            raise ValueError(f"cell group {g} sets {mp} twice")
        d[mp] = float(r["model_value"])
    return out


def group_members(labels, selectors=SELECTORS):
    """{cell_group: row numbers} from a label table in the engine's neuron
    order. Raises if one neuron would belong to two groups."""
    out = {}
    taken = np.zeros(len(labels), bool)
    for g, sel in selectors.items():
        m = sel(labels).fillna(False).to_numpy(bool)
        if (taken & m).any():
            raise ValueError(f"cell group {g} overlaps another group")
        taken |= m
        out[g] = np.flatnonzero(m)
    return out


@nb.njit(cache=True, nogil=True)
def _simulate_trial_ct(n_steps, indptr, post, count, w_syn, silenced, rfc_steps,
                       ev_ptr, ev_neuron, w_poi, delay_steps, c_g, grp,
                       q_c_v0, q_c_vg, q_c_vv, q_v0, q_vth, q_vrst, rec_idx):
    """``fast_engine._simulate_trial`` with the resting potential, threshold,
    reset and membrane time constant looked up per neuron.

    Neurons are sorted into parameter groups (``grp``; group 0 = the shared
    values). Every per-step multiplier of the baseline becomes a small array
    indexed by group, computed with the baseline's own formula, and each group
    keeps its own "resting trajectory" for neurons nobody has touched yet.
    With one group this performs the same arithmetic, in the same order, as
    the baseline loop, so the spikes are identical. Voltages in volts.
    """
    n_neurons = rfc_steps.shape[0]
    n_grp = q_c_v0.shape[0]
    slot = np.full(n_neurons, -1, np.int32)
    act_id = np.empty(n_neurons, np.int32)
    v_a = np.empty(n_neurons)
    g_a = np.empty(n_neurons)
    ls_a = np.empty(n_neurons, np.int64)
    rf_a = np.empty(n_neurons, np.int64)
    q_a = np.empty(n_neurons, np.int32)            # slot -> parameter group
    n_active = 0
    rest = q_v0.copy()

    cap = 4096
    sp_step = np.empty(cap, np.int32)
    sp_neu = np.empty(cap, np.int32)
    n_sp = 0
    deliver = 0

    n_rec = rec_idx.shape[0]
    vrec = np.empty((n_steps, n_rec))

    for n in range(n_steps):
        for r in range(n_rec):
            i = rec_idx[r]
            k = slot[i]
            vrec[n, r] = v_a[k] if k >= 0 else rest[grp[i]]

        if n_sp + n_active > cap:
            cap = 2 * (n_sp + n_active)
            tmp_s = np.empty(cap, np.int32)
            tmp_n = np.empty(cap, np.int32)
            tmp_s[:n_sp] = sp_step[:n_sp]
            tmp_n[:n_sp] = sp_neu[:n_sp]
            sp_step = tmp_s
            sp_neu = tmp_n

        for q in range(n_grp):
            rest[q] = q_c_v0[q] + ((q_c_vg[q] * 0.0) + (q_c_vv[q] * rest[q]))
        first_new = n_sp
        for k in range(n_active):
            if n - ls_a[k] >= rf_a[k]:
                gi = g_a[k]
                if -1e-200 < gi < 1e-200:
                    gi = 0.0
                q = q_a[k]
                vi = q_c_v0[q] + ((q_c_vg[q] * gi) + (q_c_vv[q] * v_a[k]))
                g_a[k] = c_g * gi
                if vi > q_vth[q]:
                    sp_step[n_sp] = n
                    sp_neu[n_sp] = act_id[k]
                    n_sp += 1
                    ls_a[k] = n
                    v_a[k] = q_vrst[q]
                    g_a[k] = 0.0
                else:
                    v_a[k] = vi

        for a in range(first_new + 1, n_sp):
            x = sp_neu[a]
            b = a - 1
            while b >= first_new and sp_neu[b] > x:
                sp_neu[b + 1] = sp_neu[b]
                b -= 1
            sp_neu[b + 1] = x

        for e in range(ev_ptr[n], ev_ptr[n + 1]):
            i = ev_neuron[e]
            k = slot[i]
            if k < 0:
                k = n_active
                n_active += 1
                slot[i] = k
                act_id[k] = i
                q_a[k] = grp[i]
                v_a[k] = rest[grp[i]]
                g_a[k] = 0.0
                ls_a[k] = _NEVER
                rf_a[k] = rfc_steps[i]
            if ls_a[k] != n and n - ls_a[k] >= rf_a[k]:
                v_a[k] += w_poi

        target_step = n - delay_steps
        while deliver < n_sp and sp_step[deliver] == target_step:
            j = sp_neu[deliver]
            deliver += 1
            if silenced[j]:
                continue
            for s in range(indptr[j], indptr[j + 1]):
                i = post[s]
                k = slot[i]
                if k < 0:
                    k = n_active
                    n_active += 1
                    slot[i] = k
                    act_id[k] = i
                    q_a[k] = grp[i]
                    v_a[k] = rest[grp[i]]
                    g_a[k] = 0.0
                    ls_a[k] = _NEVER
                    rf_a[k] = rfc_steps[i]
                if ls_a[k] != n and n - ls_a[k] >= rf_a[k]:
                    g_a[k] += count[s] * w_syn

    return sp_step[:n_sp].copy(), sp_neu[:n_sp].copy(), vrec, n_active


class CellTypeBrain(FastBrain):
    """The baseline whole-brain model with measured per-cell-type parameters.

    Same interface and results as ``FastBrain`` (same random input for the same
    seed). The upgrade is switched with ``set_celltype``:

    >>> brain = CellTypeBrain("630", n_threads=2)          # upgrade ON, full table
    >>> brain.set_celltype(groups=["KC"])                  # only Kenyon cells
    >>> brain.set_celltype(overrides={"KC": {"t_mbr_ms": 200.0}})   # a variant
    >>> brain.set_celltype(enabled=False)                  # every neuron shared values
    >>> res = brain.run_baseline(...)                      # the untouched baseline loop
    """

    def __init__(self, snapshot="630", params=None, n_threads=1, table=TABLE_PATH, **kw):
        super().__init__(snapshot, params, n_threads, **kw)
        try:                       # give back memory pyarrow keeps after loading
            import pyarrow as pa
            pa.default_memory_pool().release_unused()
        except Exception:  # noqa: BLE001 - only a memory courtesy
            pass
        f = LABELS_DIR / f"connectome_{self.snapshot}_neurons.parquet"
        if not f.exists():
            raise FileNotFoundError(f"{f} missing: build it with sim.connectome.load_connectome('{self.snapshot}')")
        labels = pd.read_parquet(f, columns=["root_id", "cell_class", "cell_sub_class",
                                             "cell_type", "hemibrain_type", "top_nt"])
        if not np.array_equal(labels["root_id"].to_numpy(np.int64), self.root_ids):
            raise ValueError("label table is not in the engine's neuron order")
        self._init_celltype(group_members(labels), applied_values(path=table))

    @classmethod
    def from_arrays(cls, root_ids, pre_index, post_index, signed_count, params=None,
                    n_threads=1, members=None, values=None):
        """Tiny test networks. ``members``: {group: list of root IDs};
        ``values``: {group: {model_param: value}}."""
        self = super().from_arrays(root_ids, pre_index, post_index, signed_count,
                                   params=params, n_threads=n_threads)
        idx = {g: self.index_of(ids) for g, ids in (members or {}).items()}
        self._init_celltype(idx, dict(values or {}))
        return self

    def _init_celltype(self, members, values):
        self.members = {g: np.asarray(m, np.int64) for g, m in members.items()}
        self.table_values = {g: dict(v) for g, v in values.items()}
        unknown = set(self.table_values) - set(self.members)
        if unknown:
            raise KeyError(f"table has values for group(s) with no selector: {sorted(unknown)}")
        self.celltype = {"enabled": True, "groups": None, "overrides": {}}

    def set_celltype(self, enabled=True, groups=None, overrides=None):
        """Switch the upgrade. ``groups``: only these cell groups get their
        measured values (None = all in the table). ``overrides``:
        {group: {model_param: value}} replaces table values (variants)."""
        overrides = {g: dict(v) for g, v in (overrides or {}).items()}
        for g, v in overrides.items():
            if g not in self.members:
                raise KeyError(f"unknown cell group {g}")
            bad = set(v) - set(MODEL_PARAMS)
            if bad:
                raise KeyError(f"unknown parameter(s) {sorted(bad)}; known: {MODEL_PARAMS}")
        if groups is not None:
            bad = set(groups) - set(self.members)
            if bad:
                raise KeyError(f"unknown cell group(s) {sorted(bad)}")
        self.celltype = {"enabled": bool(enabled),
                         "groups": None if groups is None else list(groups),
                         "overrides": overrides}
        return self

    def group_values(self, p=None):
        """{group: its full settings in mV / ms} for the groups in use, after
        filling anything not measured with the shared value."""
        p = self._params_for(p)
        ct = self.celltype
        if not ct["enabled"]:
            return {}
        names = list(self.members) if ct["groups"] is None else ct["groups"]
        out = {}
        for g in names:
            v = dict(self.table_values.get(g, {}))
            v.update(ct["overrides"].get(g, {}))
            if not v:
                continue                       # no measured value: stays in group 0
            v0 = v.get("v_0_mV", p["v_0"])
            gap = v.get("v_th_gap_mV", p["v_th"] - p["v_0"])
            out[g] = {"n_neurons": int(self.members[g].size), "v_0": v0, "v_th": v0 + gap,
                      "v_rst": v0 + (p["v_rst"] - p["v_0"]), "gap": gap,
                      "t_mbr": v.get("t_mbr_ms", p["t_mbr"]),
                      "t_rfc": v.get("t_rfc_ms", p["t_rfc"]),
                      "measured": sorted(v)}
        return out

    def describe(self, p=None):
        """Plain summary of what is switched on."""
        gv = self.group_values(p)
        return {"enabled": self.celltype["enabled"], "groups": gv,
                "n_neurons_changed": int(sum(v["n_neurons"] for v in gv.values()))}

    def run_baseline(self, *args, **kw):
        """Run the UNMODIFIED baseline loop (sim/fast_engine.py) on this same
        brain object, ignoring the upgrade. Same arguments as ``run``."""
        self._use_baseline_engine = True
        try:
            return self.run(*args, **kw)
        finally:
            self._use_baseline_engine = False

    def _group_arrays(self, p):
        """Per-neuron group numbers and per-group constants (volts, steps)."""
        dt_s = p["dt"] * 1e-3
        gv = self.group_values(p)
        grp = np.zeros(self.n_neurons, np.int32)
        shared = {"v_0": p["v_0"], "v_th": p["v_th"], "v_rst": p["v_rst"],
                  "t_mbr": p["t_mbr"], "t_rfc": p["t_rfc"]}
        settings = [shared]
        for k, (g, v) in enumerate(gv.items(), start=1):
            grp[self.members[g]] = k
            settings.append(v)
        nq = len(settings)
        c_v0, c_vg, c_vv = np.empty(nq), np.empty(nq), np.empty(nq)
        v0, vth, vrst = np.empty(nq), np.empty(nq), np.empty(nq)
        rfc_q = np.empty(nq, np.int64)
        for q, s in enumerate(settings):
            pq = dict(p, t_mbr=s["t_mbr"], v_0=s["v_0"])
            _, c_v0[q], c_vg[q], c_vv[q] = _update_constants(pq)
            v0[q], vth[q], vrst[q] = s["v_0"] * 1e-3, s["v_th"] * 1e-3, s["v_rst"] * 1e-3
            rfc_q[q] = _timestep(s["t_rfc"] * 1e-3, dt_s)
        return grp, c_v0, c_vg, c_vv, v0, vth, vrst, rfc_q[grp]

    def _run_events(self, events, exc_idx, silence, n_steps, p, record_v):
        if getattr(self, "_use_baseline_engine", False):
            return FastBrain._run_events(self, events, exc_idx, silence, n_steps, p, record_v)
        t0 = time.perf_counter()
        dt_s = p["dt"] * 1e-3
        c_g = _update_constants(p)[0]                 # synaptic decay: shared
        grp, q_c_v0, q_c_vg, q_c_vv, q_v0, q_vth, q_vrst, rfc = self._group_arrays(p)
        rfc = rfc.astype(np.int64)
        rfc[exc_idx] = 0                              # model.poi: no refractory period
        silenced = np.zeros(self.n_neurons, np.bool_)
        sil_ids = _as_root_ids(silence)
        silenced[self.index_of(sil_ids)] = True
        rec_ids = _as_root_ids(record_v)
        rec_idx = self.index_of(rec_ids).astype(np.int64)
        delay_steps = int(p["t_dly"] * 1e-3 / dt_s + 0.5)
        w_syn = p["w_syn"] * 1e-3
        w_poi = w_syn * p["f_poi"]

        def one(ev):
            return _simulate_trial_ct(n_steps, self._indptr, self._post, self._count, w_syn,
                                      silenced, rfc, ev[0], ev[1], w_poi, delay_steps, c_g,
                                      grp, q_c_v0, q_c_vg, q_c_vv, q_v0, q_vth, q_vrst, rec_idx)

        if self.n_threads > 1 and len(events) > 1:
            with ThreadPoolExecutor(self.n_threads) as pool:
                outs = list(pool.map(one, events))
        else:
            outs = [one(ev) for ev in events]

        trial = np.concatenate([np.full(o[0].size, k, np.int32) for k, o in enumerate(outs)]) \
            if outs else np.zeros(0, np.int32)
        step = np.concatenate([o[0] for o in outs]) if outs else np.zeros(0, np.int32)
        neuron = np.concatenate([o[1] for o in outs]) if outs else np.zeros(0, np.int32)
        voltages = {int(rid): np.stack([o[2][:, r] for o in outs])
                    for r, rid in enumerate(rec_ids)}
        pr = dict(p)
        pr["celltype"] = self.describe(p)
        return SimResult(
            root_ids=self.root_ids, n_trials=len(events), duration_ms=n_steps * p["dt"],
            dt_ms=p["dt"], seed=None, excite={}, silence=[int(s) for s in sil_ids],
            params=pr, trial=trial, neuron=neuron, step=step,
            neurons_reached=[int(o[3]) for o in outs], voltages_V=voltages,
            wall_time_s=time.perf_counter() - t0,
        )


__all__ = ["CellTypeBrain", "SELECTORS", "MODEL_PARAMS", "TABLE_PATH", "applied_values",
           "group_members", "read_table", "DEFAULT_PARAMS"]
