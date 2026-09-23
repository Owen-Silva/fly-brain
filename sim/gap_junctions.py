"""Electrical synapses (gap junctions) for the whole-brain model (Phase 7 item 5).

What this is, in plain English
------------------------------
Neurons talk in two ways. Most connections are *chemical*: a spike releases a
transmitter that excites or inhibits the next cell. That is all the FlyWire
wiring diagram (and so the Shiu et al. 2024 model) contains. Some neurons are
also joined by *electrical synapses* (gap junctions): tiny pores that connect
the insides of two cells, so current flows from the cell with the higher
voltage to the one with the lower voltage, both ways, instantly. Electron
microscopy cannot see them, so the connectome has none.

This file adds them back, only where recordings in adult flies have measured
them, on top of the recommended sign fix ``al_ln_literature``
(sim/sign_fixes.py), which removed the chemical synapses of excitatory
antennal-lobe local neurons onto projection neurons precisely because real
ones reach projection neurons mainly electrically (Yaksi & Wilson 2010).

Which cells are coupled (details and quotes: docs/phase7-electrical-synapses.md)
* ``eln_pn``: each of the 44 literature-typed excitatory local neurons (eLNs;
  ``sign_fixes.eln_mask``) with every uniglomerular projection neuron (uPN) of
  each glomerulus it innervates. "Innervates" = the eLN and that glomerulus's
  uPNs (same side) share at least ``MIN_CONTACT_SYNAPSES`` chemical synapses
  in either direction, i.e. their membranes touch there. Evidence: paired
  recordings, Yaksi & Wilson 2010 (Neuron 67:1034) and Huang et al. 2010
  (Neuron 67:1021); "each eLN is connected to most or all PNs" (Yaksi & Wilson).
* ``sister_pn``: every pair of uPNs of the same glomerulus on the same side
  ("sister" PNs). Evidence: Kazama & Wilson 2009 (Nat Neurosci 12:1136), DM6;
  Yaksi & Wilson 2010 Fig. 6, DA1. Pairs from different glomeruli were not
  coupled in the recordings ("Coupling is negligible between heterotypic PN
  pairs"), so they are not coupled here.
* A uPN's glomerulus is the ORN glomerulus that gives it at least half of its
  ORN synapses and at least 20 of them (the definition used by
  experiments/phase6/steering/s1_anatomy.py).

How a gap junction becomes numbers in this model
------------------------------------------------
The model neuron has no capacitance or resistance; its voltage obeys
``dv/dt = (v_0 - v + g) / t_mbr`` with ``g`` already in volts. For a real
neuron with leak conductance g_L, ``C dv/dt = g_L (v_0 - v) + I``, i.e.
``dv/dt = (v_0 - v + I/g_L) / t_mbr``. A gap junction of conductance g_gap
carries ``I = g_gap (v_j - v_i)``, so in the model's units it adds

    kappa * (v_j - v_i)   to the bracket, with   kappa = g_gap / g_L.

kappa is a pure number ("junction conductance as a fraction of the cell's own
leak conductance"). The papers report the *coupling coefficient* CC instead:
inject a steady current into one cell, and CC = (voltage change in the other
cell) / (voltage change in the injected cell). For two cells alone,
CC = kappa / (1 + kappa). In the network each cell has many junctions, so
``calibrate_kappa`` picks, per coupling class, the one kappa for which the
model, probed exactly like the experiment (steady current into one cell of the
full coupled network), gives the measured CC (median over all coupled pairs).

Spikes. The model's spike is not a voltage waveform (the voltage just jumps
from threshold back to reset), but a real spike briefly drives the voltage far
up and pushes charge through the junction: a "spikelet" in the partner. Each
spike therefore adds ``kappa * SPIKE_AREA / t_mbr`` to every partner's voltage,
where SPIKE_AREA is the spike's voltage-time area (mV x ms). With 40 mV x 1 ms
(ASSUMED shape; 40 mV is the soma spike height in Yaksi & Wilson 2010) and
kappa ~0.013 this is ~0.03 mV per spike.

Numerics: inside one 0.1 ms step the junction current is held at its value at
the start of the step (voltages before the update) and integrated exactly like
a constant current: ``v += (1 - exp(-dt/t_mbr)) * kappa * (v_j - v_i)``. A
refractory neuron's voltage is frozen, so it ignores junction current and
spikelets (Brian2's "unless refractory" rule, as for chemical input), but it
still pushes current into its partners. A silenced neuron (``silence=``) has
no effect on anyone: its junctions do not drive its partners either.

With no couplings the compiled loop does exactly the arithmetic of
sim/fast_engine.py, so the result is identical spike for spike
(tests/test_gap_junctions.py). sim/fast_engine.py itself is not changed.
"""

from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor

import numba as nb
import numpy as np
import pandas as pd

from sim.fast_engine import (_NEVER, FastBrain, SimResult, _as_root_ids, _timestep,
                             _update_constants)

# ---------------------------------------------------------------------------
# Evidence-derived constants (docs/phase7-electrical-synapses.md, section 2)
# ---------------------------------------------------------------------------
#: Measured soma-to-soma coupling coefficients (depolarizing steps), read by eye
#: from bar charts (reading uncertainty about +/-0.002):
#: eLN -> PN: Yaksi & Wilson 2010 Fig. 4C 0.010 (control), 0.014 (Cd2+, chemical
#: transmission blocked); Huang et al. 2010 Fig. 3D 0.015 -> mean 0.013.
#: sister PNs: Kazama & Wilson 2009 Fig. 7d 0.016 (depolarizing, Cd2+: the
#: electrical part only; the chemical part is already in the connectome).
CC_TARGET = {"eln_pn": 0.013, "sister_pn": 0.016}
COUPLING_CLASSES = tuple(CC_TARGET)

SOURCES = {
    "eln_pn": "Yaksi & Wilson 2010 Neuron 67:1034 (Fig. 4C; shakB2 abolishes); "
              "Huang et al. 2010 Neuron 67:1021 (Fig. 3D)",
    "sister_pn": "Kazama & Wilson 2009 Nat Neurosci 12:1136 (Fig. 7, DM6); "
                 "Yaksi & Wilson 2010 Neuron 67:1034 (Fig. 6, DA1)",
}

#: Voltage-time area of one spike above the model's voltage (mV x ms).
#: ASSUMED: ~40 mV soma spike (Yaksi & Wilson 2010: "full-sized spikes (~40 mV
#: amplitude)") x ~1 ms width (width not taken from a paper).
SPIKE_AREA_MV_MS = 40.0

#: eLN "innervates" a glomerulus if it shares at least this many chemical
#: synapses (either direction) with that glomerulus's uPNs (same side).
MIN_CONTACT_SYNAPSES = 5

#: uPN definition (experiments/phase6/steering/s1_anatomy.py).
UPN_MIN_PURITY = 0.5
UPN_MIN_ORN_SYNAPSES = 20


# ---------------------------------------------------------------------------
# Which cells are coupled
# ---------------------------------------------------------------------------
def upn_glomeruli(lab, pre, post, signed):
    """Uniglomerular PNs: DataFrame (idx, root_id, glomerulus, side, purity,
    orn_synapses), one row per uPN, sorted by idx."""
    cc = lab.cell_class.to_numpy()
    ht = pd.Series(lab.hemibrain_type.to_numpy(), dtype=object).astype(str)
    orn = (cc == "olfactory") & ht.str.startswith("ORN_").to_numpy()
    pn = cc == "ALPN"
    glom = np.where(orn, ht.str.replace("ORN_", "", regex=False).to_numpy(), "")
    m = orn[pre] & pn[post]
    e = pd.DataFrame({"p": post[m], "g": glom[pre[m]], "w": np.abs(signed[m]).astype(np.int64)})
    per = e.groupby(["p", "g"]).w.sum().reset_index()
    tot = per.groupby("p").w.sum()
    best = per.sort_values(["w", "g"], ascending=[False, True]).drop_duplicates("p").set_index("p")
    best["purity"] = best.w / tot.reindex(best.index)
    up = best[(best.purity >= UPN_MIN_PURITY) & (best.w >= UPN_MIN_ORN_SYNAPSES)].sort_index()
    idx = up.index.to_numpy(np.int64)
    return pd.DataFrame({"idx": idx, "root_id": lab.root_id.to_numpy()[idx],
                         "glomerulus": up.g.to_numpy(), "side": lab.side.to_numpy()[idx],
                         "purity": up.purity.round(3).to_numpy(),
                         "orn_synapses": up.w.to_numpy()})


def coupling_table(root_ids, pre, post, signed, lab, classes=COUPLING_CLASSES,
                   min_contact=MIN_CONTACT_SYNAPSES):
    """Every coupled pair, one row each (unordered pairs; for ``eln_pn`` a is the
    eLN and b the PN). Built from the UNFIXED reference connections (chemical
    contacts show where membranes touch, whatever the sign fix does)."""
    from sim import sign_fixes as S
    unknown = set(classes) - set(COUPLING_CLASSES)
    if unknown:
        raise ValueError(f"unknown coupling class(es) {sorted(unknown)}")
    rid = np.asarray(root_ids, np.int64)
    n = rid.size
    upn = upn_glomeruli(lab, pre, post, signed)
    key = (upn.glomerulus + "|" + upn.side).to_numpy()
    typ = lab.cell_type.to_numpy().astype(object)
    htyp = lab.hemibrain_type.to_numpy().astype(object)
    label = np.where(htyp != "", htyp, typ)
    rows = []
    if "eln_pn" in classes:
        eln = S.eln_mask(lab)
        upn_key = np.full(n, "", object)
        upn_key[upn.idx.to_numpy()] = key
        is_upn = upn_key != ""
        w = np.abs(signed)
        m1 = eln[pre] & is_upn[post]
        m2 = is_upn[pre] & eln[post]
        c = pd.DataFrame({"e": np.r_[pre[m1], post[m2]],
                          "k": np.r_[upn_key[post[m1]], upn_key[pre[m2]]],
                          "w": np.r_[w[m1], w[m2]].astype(np.int64)})
        c = c.groupby(["e", "k"]).w.sum().reset_index()
        inn = c[c.w >= min_contact]
        pairs = inn.merge(pd.DataFrame({"k": key, "p": upn.idx.to_numpy()}), on="k")
        for r in pairs.itertuples(index=False):
            g, s = r.k.split("|")
            rows.append(dict(cls="eln_pn", a=int(r.e), b=int(r.p), glomerulus=g, side=s,
                             contact_synapses=int(r.w)))
    if "sister_pn" in classes:
        for (g, s), grp in upn.groupby(["glomerulus", "side"]):
            ids = grp.idx.to_numpy()
            for i in range(ids.size):
                for j in range(i + 1, ids.size):
                    rows.append(dict(cls="sister_pn", a=int(ids[i]), b=int(ids[j]),
                                     glomerulus=g, side=s, contact_synapses=-1))
    t = pd.DataFrame(rows, columns=["cls", "a", "b", "glomerulus", "side", "contact_synapses"])
    t = t.sort_values(["cls", "a", "b"]).reset_index(drop=True)
    t.insert(3, "root_id_a", rid[t.a.to_numpy()])
    t.insert(4, "root_id_b", rid[t.b.to_numpy()])
    t["type_a"] = label[t.a.to_numpy()]
    t["type_b"] = label[t.b.to_numpy()]
    t["cc_target"] = t.cls.map(CC_TARGET)
    t["source"] = t.cls.map(SOURCES)
    return t


# ---------------------------------------------------------------------------
# From coupling coefficients to kappa
# ---------------------------------------------------------------------------
def _cc_matrix(a, b, kappa):
    """Steady-state coupling coefficients of the coupled network (leak = 1).
    Returns (nodes, CC) with CC[j, i] = dV_j / dV_i for current into i."""
    nodes = np.unique(np.r_[a, b])
    ia = np.searchsorted(nodes, a)
    ib = np.searchsorted(nodes, b)
    m = nodes.size
    G = np.eye(m)
    np.add.at(G, (ia, ib), -kappa)
    np.add.at(G, (ib, ia), -kappa)
    np.add.at(G, (ia, ia), kappa)
    np.add.at(G, (ib, ib), kappa)
    Ginv = np.linalg.inv(G)
    return nodes, Ginv / np.diag(Ginv)[None, :]


def pair_cc(table, kappa_by_class):
    """Model coupling coefficient of every pair, both directions:
    DataFrame with cc_ab (current into a, a = eLN for eln_pn) and cc_ba."""
    a = table.a.to_numpy()
    b = table.b.to_numpy()
    k = table.cls.map(kappa_by_class).to_numpy(float)
    nodes, CC = _cc_matrix(a, b, k)
    ia, ib = np.searchsorted(nodes, a), np.searchsorted(nodes, b)
    return pd.DataFrame({"cls": table.cls.to_numpy(), "cc_ab": CC[ib, ia], "cc_ba": CC[ia, ib]})


def _class_median_cc(table, pcc):
    out = {}
    for c in table.cls.unique():
        m = (pcc.cls == c).to_numpy()
        if c == "eln_pn":           # the measured direction: current into the eLN
            vals = pcc.cc_ab.to_numpy()[m]
        else:                       # sisters: both directions
            vals = np.r_[pcc.cc_ab.to_numpy()[m], pcc.cc_ba.to_numpy()[m]]
        out[c] = float(np.median(vals))
    return out


def calibrate_kappa(table, targets=None, tol=1e-6, max_iter=200):
    """kappa per class so that the model's median coupling coefficient (probed
    like the experiments, in the full coupled network) equals the target."""
    targets = dict(CC_TARGET if targets is None else targets)
    classes = [c for c in COUPLING_CLASSES if (table.cls == c).any()]
    kap = {c: targets[c] / (1.0 - targets[c]) for c in classes}   # two-cell value
    for _ in range(max_iter):
        med = _class_median_cc(table, pair_cc(table, kap))
        err = max(abs(med[c] / targets[c] - 1.0) for c in classes)
        if err < tol:
            break
        kap = {c: kap[c] * targets[c] / med[c] for c in classes}
    else:
        raise RuntimeError("kappa calibration did not converge")
    return kap


def two_cell_cc(kappa):
    """Coupling coefficient of two cells joined only by one junction."""
    return kappa / (1.0 + kappa)


# ---------------------------------------------------------------------------
# The compiled inner loop: sim/fast_engine._simulate_trial plus gap junctions
# ---------------------------------------------------------------------------
@nb.njit(cache=True, nogil=True)
def _simulate_trial_gap(n_steps, indptr, post, count, w_syn, silenced, rfc_steps,
                        ev_ptr, ev_neuron, w_poi, delay_steps,
                        c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, rec_idx,
                        pre_ids, gap_ptr, gap_nbr, gap_k, spk_v, c_in, ext_v):
    """One trial. Identical to fast_engine._simulate_trial except for the
    neurons in ``pre_ids`` (every neuron with a gap junction, plus any with a
    constant test current ``ext_v``): they get slots 0..n_pre-1 at the start
    (they sit exactly on the resting trajectory until something moves them)
    and each step receive ``c_in * (ext_v + sum kappa (v_j - v_i))``;
    each spike of a coupled neuron adds ``spk_v`` to its partners.
    ``gap_ptr/gap_nbr/gap_k/spk_v`` are indexed by pre slot (0..n_pre-1)."""
    n_neurons = rfc_steps.shape[0]
    slot = np.full(n_neurons, -1, np.int32)
    act_id = np.empty(n_neurons, np.int32)
    v_a = np.empty(n_neurons)
    g_a = np.empty(n_neurons)
    ls_a = np.empty(n_neurons, np.int64)
    rf_a = np.empty(n_neurons, np.int64)
    n_active = 0
    rest = v_0

    n_pre = pre_ids.shape[0]
    for q in range(n_pre):
        i = pre_ids[q]
        slot[i] = n_active
        act_id[n_active] = i
        v_a[n_active] = rest
        g_a[n_active] = 0.0
        ls_a[n_active] = _NEVER
        rf_a[n_active] = rfc_steps[i]
        n_active += 1
    inc = np.zeros(n_pre)

    cap = 4096
    sp_step = np.empty(cap, np.int32)
    sp_neu = np.empty(cap, np.int32)
    n_sp = 0
    deliver = 0

    n_rec = rec_idx.shape[0]
    vrec = np.empty((n_steps, n_rec))

    for n in range(n_steps):
        for r in range(n_rec):
            k = slot[rec_idx[r]]
            vrec[n, r] = v_a[k] if k >= 0 else rest

        if n_sp + n_active > cap:
            cap = 2 * (n_sp + n_active)
            tmp_s = np.empty(cap, np.int32)
            tmp_n = np.empty(cap, np.int32)
            tmp_s[:n_sp] = sp_step[:n_sp]
            tmp_n[:n_sp] = sp_neu[:n_sp]
            sp_step = tmp_s
            sp_neu = tmp_n

        # Gap-junction current from the voltages at the start of the step
        # (slots 0..n_pre-1 are the pre-allocated coupled neurons).
        for q in range(n_pre):
            vq = v_a[q]
            s = ext_v[q]
            for e in range(gap_ptr[q], gap_ptr[q + 1]):
                p = gap_nbr[e]
                if silenced[act_id[p]]:
                    continue
                s += gap_k[e] * (v_a[p] - vq)
            inc[q] = c_in * s

        rest = c_v0 + ((c_vg * 0.0) + (c_vv * rest))
        first_new = n_sp
        for k in range(n_active):
            if n - ls_a[k] >= rf_a[k]:
                gi = g_a[k]
                if -1e-200 < gi < 1e-200:
                    gi = 0.0
                vi = c_v0 + ((c_vg * gi) + (c_vv * v_a[k]))
                if k < n_pre:
                    vi = vi + inc[k]
                g_a[k] = c_g * gi
                if vi > v_th:
                    sp_step[n_sp] = n
                    sp_neu[n_sp] = act_id[k]
                    n_sp += 1
                    ls_a[k] = n
                    v_a[k] = v_rst
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

        # Spikelets: this step's spikes of coupled neurons reach their partners
        # at once (electrical synapses have no delay).
        if n_pre > 0:
            for a in range(first_new, n_sp):
                j = sp_neu[a]
                q = slot[j]
                if q >= n_pre or silenced[j]:
                    continue
                for e in range(gap_ptr[q], gap_ptr[q + 1]):
                    p = gap_nbr[e]
                    if ls_a[p] != n and n - ls_a[p] >= rf_a[p]:
                        v_a[p] += spk_v[e]

        for e in range(ev_ptr[n], ev_ptr[n + 1]):
            i = ev_neuron[e]
            k = slot[i]
            if k < 0:
                k = n_active
                n_active += 1
                slot[i] = k
                act_id[k] = i
                v_a[k] = rest
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
                    v_a[k] = rest
                    g_a[k] = 0.0
                    ls_a[k] = _NEVER
                    rf_a[k] = rfc_steps[i]
                if ls_a[k] != n and n - ls_a[k] >= rf_a[k]:
                    g_a[k] += count[s] * w_syn

    return sp_step[:n_sp].copy(), sp_neu[:n_sp].copy(), vrec, n_active


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------
class GapBrain(FastBrain):
    """FastBrain plus electrical synapses. Same interface and results object.

    ``set_couplings(a_idx, b_idx, kappa)``: symmetric junctions between rows
    a and b (kappa = junction conductance / leak conductance). ``gap_scale``
    multiplies every kappa (sensitivity runs). With no couplings the results
    are identical to FastBrain's, spike for spike."""

    def _init_gap(self):
        self.gap_a = np.zeros(0, np.int64)
        self.gap_b = np.zeros(0, np.int64)
        self.gap_kappa = np.zeros(0)
        self.gap_scale = 1.0
        self.spike_area_mV_ms = SPIKE_AREA_MV_MS
        self.coupling = None
        self._ext = {}

    @classmethod
    def from_arrays(cls, root_ids, pre_index, post_index, signed_count, params=None,
                    n_threads=1):
        self = super().from_arrays(root_ids, pre_index, post_index, signed_count,
                                   params=params, n_threads=n_threads)
        self._init_gap()
        return self

    def set_couplings(self, a_idx, b_idx, kappa, spike_area_mV_ms=SPIKE_AREA_MV_MS):
        a = np.asarray(a_idx, np.int64)
        b = np.asarray(b_idx, np.int64)
        k = np.broadcast_to(np.asarray(kappa, float), a.shape).copy()
        if not (a.shape == b.shape == k.shape):
            raise ValueError("a_idx, b_idx and kappa must have the same length")
        if (a == b).any():
            raise ValueError("a neuron cannot be coupled to itself")
        if a.size and (min(a.min(), b.min()) < 0 or max(a.max(), b.max()) >= self.n_neurons):
            raise IndexError("coupling index out of range")
        if (k < 0).any():
            raise ValueError("kappa must be >= 0")
        self.gap_a, self.gap_b, self.gap_kappa = a, b, k
        self.spike_area_mV_ms = float(spike_area_mV_ms)
        return self

    def set_test_current(self, currents_mV):
        """TESTS ONLY: constant current into some neurons, given as the steady
        depolarization (mV) it would cause in an uncoupled neuron:
        {root_id: mV}. Empty dict switches it off."""
        self._ext = {int(k): float(v) for k, v in currents_mV.items()}
        return self

    def run_baseline(self, *args, **kw):
        """Run sim/fast_engine.py's own compiled loop on this brain (couplings
        ignored), for with/without comparisons without a second brain."""
        self._use_baseline_engine = True
        try:
            return self.run(*args, **kw)
        finally:
            self._use_baseline_engine = False

    def _gap_arrays(self, p):
        """Slot-indexed CSR arrays for the kernel."""
        ext_ids = self.index_of(list(self._ext)) if self._ext else np.zeros(0, np.int64)
        coupled = np.unique(np.r_[self.gap_a, self.gap_b, ext_ids]).astype(np.int64)
        n_pre = coupled.size
        qa = np.searchsorted(coupled, self.gap_a)
        qb = np.searchsorted(coupled, self.gap_b)
        k = self.gap_kappa * float(self.gap_scale)
        src = np.r_[qa, qb]
        dst = np.r_[qb, qa]
        kk = np.r_[k, k]
        order = np.lexsort((dst, src))
        src, dst, kk = src[order], dst[order], kk[order]
        ptr = np.zeros(n_pre + 1, np.int64)
        np.cumsum(np.bincount(src, minlength=n_pre), out=ptr[1:])
        t_mbr_s = p["t_mbr"] * 1e-3
        spk = kk * (self.spike_area_mV_ms * 1e-6) / t_mbr_s      # volts per spike
        c_in = 1.0 - math.exp(-p["dt"] / p["t_mbr"])
        ext = np.zeros(n_pre)
        for rid, mv in self._ext.items():
            ext[np.searchsorted(coupled, self.index_of([rid])[0])] = mv * 1e-3
        return (coupled.astype(np.int64), ptr, np.ascontiguousarray(dst, np.int32),
                np.ascontiguousarray(kk), np.ascontiguousarray(spk), c_in, ext)

    def _run_events(self, events, exc_idx, silence, n_steps, p, record_v):
        if getattr(self, "_use_baseline_engine", False):
            return FastBrain._run_events(self, events, exc_idx, silence, n_steps, p, record_v)
        t0 = time.perf_counter()
        dt_s = p["dt"] * 1e-3
        c_g, c_v0, c_vg, c_vv = _update_constants(p)
        rfc = np.full(self.n_neurons, _timestep(p["t_rfc"] * 1e-3, dt_s), np.int64)
        rfc[exc_idx] = 0
        silenced = np.zeros(self.n_neurons, np.bool_)
        sil_ids = _as_root_ids(silence)
        silenced[self.index_of(sil_ids)] = True
        rec_ids = _as_root_ids(record_v)
        rec_idx = self.index_of(rec_ids).astype(np.int64)
        delay_steps = int(p["t_dly"] * 1e-3 / dt_s + 0.5)
        w_syn = p["w_syn"] * 1e-3
        w_poi = w_syn * p["f_poi"]
        v_0, v_th, v_rst = p["v_0"] * 1e-3, p["v_th"] * 1e-3, p["v_rst"] * 1e-3
        pre_ids, gptr, gnbr, gk, spk, c_in, ext = self._gap_arrays(p)

        def one(ev):
            return _simulate_trial_gap(n_steps, self._indptr, self._post, self._count, w_syn,
                                       silenced, rfc, ev[0], ev[1], w_poi, delay_steps,
                                       c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, rec_idx,
                                       pre_ids, gptr, gnbr, gk, spk, c_in, ext)

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
        pr["gap_junctions"] = dict(n_pairs=int(self.gap_a.size), scale=float(self.gap_scale),
                                   spike_area_mV_ms=self.spike_area_mV_ms)
        return SimResult(
            root_ids=self.root_ids, n_trials=len(events), duration_ms=n_steps * p["dt"],
            dt_ms=p["dt"], seed=None, excite={}, silence=[int(s) for s in sil_ids],
            params=pr, trial=trial, neuron=neuron, step=step,
            neurons_reached=[int(o[3]) for o in outs], voltages_V=voltages,
            wall_time_s=time.perf_counter() - t0,
        )


def build_gap_brain(fix="al_ln_literature", classes=COUPLING_CLASSES, scale=1.0,
                    n_threads=1, params=None, lab=None, kappa=None, return_table=False):
    """The whole brain with sign fix ``fix`` plus the published gap junctions.

    ``classes=()`` gives exactly ``sign_fixes.build_brain(fix)`` (no junctions).
    ``scale`` multiplies every junction (sensitivity: 0.5, 2). ``kappa``:
    optional {class: kappa} to skip the calibration. With ``return_table``
    also returns the coupling table (one row per pair, kappa included)."""
    from sim import sign_fixes as S
    root_ids, pre, post, signed = S.load_reference_arrays("630")
    if lab is None:
        lab = S.neuron_table(root_ids)
    table = coupling_table(root_ids, pre, post, signed, lab, classes) if classes else None
    pre2, post2, signed2, _ = S.apply_fix(fix, root_ids, pre, post, signed, lab)
    del pre, post, signed
    brain = GapBrain.from_arrays(root_ids, pre2, post2, signed2, params=params,
                                 n_threads=n_threads)
    del pre2, post2, signed2
    brain.snapshot = f"630+{fix}+gap"
    brain.sign_fix = fix
    if table is not None and len(table):
        kap = dict(kappa) if kappa is not None else calibrate_kappa(table)
        table["kappa"] = table.cls.map(kap).astype(float)
        brain.set_couplings(table.a.to_numpy(), table.b.to_numpy(), table.kappa.to_numpy())
        brain.kappa_by_class = kap
    else:
        brain.kappa_by_class = {}
    brain.gap_scale = float(scale)
    brain.coupling = table
    return (brain, table) if return_table else brain
