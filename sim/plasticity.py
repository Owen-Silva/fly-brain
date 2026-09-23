"""Phase 8: learning in the mushroom body (dopamine-gated depression of the
Kenyon cell -> output neuron synapses).

What this is, in plain English
------------------------------
The fly learns smells in the mushroom body. A smell switches on a small,
smell-specific set of Kenyon cells (KCs). The KCs talk to about 35 types of
mushroom body output neurons (MBONs), whose activity tells the fly "go
towards" or "go away". Dopamine neurons (DANs) carry "that was good" or
"that hurt" signals. The mushroom body is split into ~15 compartments along
the KC axons; each compartment has its own DAN type(s) and its own MBON
type(s).

The published learning rule (Hige et al. 2015; Handler et al. 2019): when a
compartment's dopamine neuron fires while (or shortly after) a Kenyon cell
was active, that Kenyon cell's synapses onto the MBONs of THAT compartment
get weaker, and stay weaker. Nothing changes if the dopamine comes without
KC activity, or if it comes before the smell.

This file adds exactly that rule to the whole-brain model (``sim/fast_engine.py``
is not changed; this file has its own copy of the inner loop):

* Every KC keeps a "recently active" tag (an eligibility trace ``x``):
  +1 per KC spike, fading with time constant ``tau_kc`` (1 s).
* Every compartment keeps a dopamine level: +1 per DAN spike (divided by the
  number of cells of that DAN type, so it means "average spikes per DAN
  cell"), fading with time constant ``tau_da`` (0.2 s).
* Every time step, each KC -> MBON synapse in a compartment shrinks by the
  factor ``exp(-eta * x * dopamine * dt)``. So a synapse only changes when its
  KC was recently active AND there is dopamine in its compartment. Weights
  shrink smoothly and can never become negative or change sign.
* No other synapse is ever changed. No forgetting inside an experiment
  (Hige 2015: the change lasted >= 40 min).
* At the end of each simulated trial, whatever tag and dopamine are left
  are allowed to finish fading with no more spikes (computed exactly), and
  the next trial starts with both at zero. So two separate trials behave
  like two events many seconds apart.

Which synapse is in which compartment
-------------------------------------
The connectome gives one number per KC -> MBON pair (a synapse count), not
where each synapse sits. We place the pair in the compartments that the
MBON type's dendrites occupy AND that the KC's lobe runs through (gamma KCs
only run through the gamma lobe, alpha/beta KCs through alpha/beta and the
peduncle, alpha'/beta' KCs through alpha'/beta'). Example: MBON-gamma5beta'2a
gets gamma KC synapses in gamma5 and alpha'/beta' KC synapses in beta'2a.
If a pair has several compartments, its dopamine is the average of theirs.
The synapse sits in the KC's own hemisphere (KC axons never cross), and each
DAN's dopamine is split between the two hemispheres in proportion to its
measured KC output synapses on each side (some DANs, e.g. PPL1-gamma1pedc,
innervate both mushroom bodies in FlyWire).

Dopamine neurons' fast synapses (a decision; see docs/phase8-learning.md)
-------------------------------------------------------------------------
The published model gives every dopamine neuron output a +1 sign, i.e. fast
excitation, because only GABA and glutamate are treated as inhibitory. Real
dopamine acts through slow G-protein coupled receptors (DopR1/Dop1R1 and
DopR2/Dop1R2; Handler 2019), and its measured effect on the KC -> MBON
pathway is the plasticity, located at the KC -> MBON synapse, not a change in
KC excitability (Hige 2015). With fast excitation, stimulating a DAN alone
would also fire KCs and so "teach" whatever KCs it happens to excite. So:

* ``dan_mode="modulatory"`` (our default for Phase 8): the fast output
  synapses of the DANs that have a known compartment are switched off (the
  same mechanism as "silencing"); their spikes still feed the dopamine
  signal. Inputs TO the DANs (from KCs, MBONs, anything) are untouched.
* ``dan_mode="fast"``: the published model's treatment (fast +1 synapses),
  plus the dopamine signal. Results are reported both ways.

Sources (full notes in docs/phase8-mushroom-body-research.md)
--------------------------------------------------------------
* Rule, timing and the 80% target: Hige T, Aso Y, Modi MN, Rubin GM,
  Turner GC (2015) "Heterosynaptic plasticity underlies aversive olfactory
  learning in Drosophila", Neuron 88:985-998. One 1-s odor paired with
  PPL1-gamma1pedc stimulation (four 1-ms light pulses at 2 Hz starting 0.2 s
  after odor onset) cut MBON-gamma1pedc>a/b odor spiking by 80 +/- 5.7%
  (118 -> 24 spikes); the unpaired odor went 110 -> 83 spikes (-25%);
  backward pairing (odor 0.5 s after the last pulse): no change; the same
  1-s pairing in alpha2 did nothing, 1 min of odor with 120 pulses did.
* Timing window: Handler A et al. (2019) "Distinct dopamine receptor pathways
  underlie the temporal sensitivity of associative learning", Cell
  178:60-75 (depression at KC-then-DAN intervals of 0 and +0.5 s, minimal
  at 6 s; DAN-first gives potentiation via DopR2, not modelled here).
* Compartments are separate: Cohn R, Morantte I, Ruta V (2015) Cell
  163:1742-1755. Which DAN teaches what: Aso Y, Rubin GM (2016) eLife
  5:e16135 (PPL1-gamma1pedc aversive, fast; PPL1-alpha3 slow; PAM-gamma5 +
  PAM-beta'2a appetitive).
* Compartment of every MBON / DAN type: hemibrain instance names
  (flyconnectome/flywire_annotations Supplemental_file5_hemibrain_meta.csv;
  table in docs/phase8-mushroom-body-research.md section 2.4), cross-checked
  here against the FlyWire DAN -> MBON synapses (experiments/phase8).
* Parameters NOT from the literature (calibrated or chosen, UNVERIFIED):
  ``tau_da`` (0.2 s), the light-pulse model (a 10-ms burst of ~3 spikes),
  ``eta`` (calibrated to Hige's 80%), ``slow_ratio`` (calibrated to Hige's
  alpha2 result), and the compartment assignment of MBON28 (data-driven).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numba as nb
import numpy as np
import pandas as pd

from sim.fast_engine import (DEFAULT_PARAMS, FastBrain, _NEVER, _timestep,
                             _update_constants)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LABELS_630 = PROJECT_ROOT / "data" / "cache" / "connectome_630_neurons.parquet"

# ---------------------------------------------------------------------------
# Compartments
# ---------------------------------------------------------------------------
#: Compartment short names -> the KC lobe that runs through it.
#: g = gamma lobe, ab = alpha/beta lobe (and the peduncle, "pedc"),
#: apbp = alpha'/beta' lobe. The calyx holds KC dendrites of all lobes.
COMPARTMENT_LOBE = {
    "g1": "g", "g2": "g", "g3": "g", "g4": "g", "g5": "g",
    "pedc": "ab", "a1": "ab", "a2": "ab", "a3": "ab", "b1": "ab", "b2": "ab",
    "ap1": "apbp", "ap2": "apbp", "ap3": "apbp", "bp1": "apbp",
    "bp2a": "apbp", "bp2m": "apbp", "bp2p": "apbp", "bp2d": "apbp",
    "calyx": "all",
}

#: MBON type (FlyWire hemibrain_type, snapshot 630) -> compartments of its
#: KC-input dendrites. From the hemibrain instance names (research doc 2.4).
MBON_COMPARTMENTS = {
    "MBON01": ("g5", "bp2a"),            # gamma5beta'2a
    "MBON02": ("b2", "bp2a"),            # beta2beta'2a
    "MBON03": ("bp2m", "bp2p"),          # beta'2mp
    "MBON04": ("bp2m", "bp2p"),          # beta'2mp_bilateral
    "MBON05": ("g4",),                   # gamma4>gamma1gamma2 (dendrites in gamma4)
    "MBON06": ("b1",),                   # beta1>alpha
    "MBON07": ("a1",),                   # alpha1
    "MBON09": ("g3", "bp1"),             # gamma3beta'1
    "MBON10": ("bp1",),                  # beta'1
    "MBON11": ("g1", "pedc"),            # gamma1pedc>alpha/beta
    "MBON12": ("g2", "ap1"),             # gamma2alpha'1
    "MBON13": ("ap2",),                  # alpha'2
    "MBON14": ("a3",),                   # alpha3
    "MBON15": ("ap1",),                  # alpha'1
    "MBON15-like": ("ap1",),
    "MBON16": ("ap3",),                  # alpha'3ap
    "MBON17": ("ap3",),                  # alpha'3m
    "MBON17-like": ("ap3",),
    "MBON18": ("a2",),                   # alpha2sc
    "MBON19": ("a2", "a3"),              # alpha2p3p
    "MBON20": ("g1", "g2"),              # gamma1gamma2
    "MBON21": ("g4", "g5"),              # gamma4gamma5
    "MBON22": ("calyx",),                # calyx
    "MBON23": ("a2",),                   # alpha2sp
    "MBON24": ("b2", "g5"),              # beta2gamma5
    "MBON25,MBON34": ("g1", "g2"),       # gamma1gamma2 / gamma2
    "MBON26": ("bp2d",),                 # beta'2d
    "MBON27": ("g5",),                   # gamma5d
    "MBON28": ("ap3",),                  # UNVERIFIED: not in the hemibrain name;
                                         # its main DAN input is PPL104 (alpha'3)
                                         # and its KC input is alpha'/beta' (measured)
    "MBON29": ("g4", "g5"),              # gamma4gamma5
    "MBON30": ("g1", "g2", "g3"),        # gamma1gamma2gamma3
    "MBON31": ("ap1",),                  # alpha'1a
    "MBON32": ("g2",),                   # gamma2
    "MBON33": ("g2", "g3"),              # gamma2gamma3
    "MBON35": ("g2",),                   # gamma2
}

#: DAN type -> compartments it releases dopamine in (research doc 2.4).
#: PPL107 and PPL201-203 have no known compartment: their spikes do not feed
#: the dopamine signal, and they keep their fast synapses in every mode.
DAN_COMPARTMENTS = {
    "PAM01": ("g5",), "PAM02": ("bp2a",), "PAM03": ("b2", "bp2a"), "PAM04": ("b2",),
    "PAM05": ("bp2p",), "PAM06": ("bp2m",), "PAM07": ("g4",), "PAM08": ("g4",),
    "PAM09": ("b1", "pedc"), "PAM10": ("b1",), "PAM11": ("a1",), "PAM12": ("g3",),
    "PAM13": ("bp1",), "PAM14": ("bp1",), "PAM15": ("g5", "bp2a"),
    "PPL101": ("g1", "pedc"), "PPL102": ("g1",), "PPL103": ("g2", "ap1"),
    "PPL104": ("ap3",), "PPL105": ("ap2", "a2"), "PPL106": ("a3",),
}

#: Compartments that learn slowly: alpha2 (Hige 2015: a single 1-s pairing did
#: nothing, 1 min with 120 pulses gave robust depression) and alpha3 (Aso &
#: Rubin 2016: barely any memory after one pairing, strong after repeats).
SLOW_COMPARTMENTS = ("a2", "a3")

#: Behavioural meaning of MBON types (Aso et al. 2014 eLife 3:e04580; Owald
#: 2015; Perisse 2016), for read-outs only.
AVOIDANCE_MBONS = ("MBON01", "MBON03", "MBON04", "MBON02")
APPROACH_MBONS = ("MBON11", "MBON12")


def kc_lobe(hemibrain_type: str) -> str:
    """'g', 'ab' or 'apbp' from a KC hemibrain_type (KCg-m, KCab-s, KCa'b'-m...)."""
    t = str(hemibrain_type)
    if t.startswith("KCg"):
        return "g"
    if t.startswith("KCab"):
        return "ab"
    if t.startswith("KCa'b'") or t.startswith("KCapbp"):
        return "apbp"
    return ""


def load_labels(path=LABELS_630):
    """Per-neuron labels for snapshot 630 in the brain's row order (the Phase 2
    cache). Missing text labels become "" so filters never hit NA."""
    cols = ["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type",
            "hemibrain_type", "side", "top_nt", "top_nt_conf"]
    df = pd.read_parquet(path, columns=cols)
    for c in cols:
        if c not in ("root_id", "top_nt_conf"):
            df[c] = df[c].astype(object).where(df[c].notna(), "").astype(str)
    return df


def mb_rows(labels):
    """Row numbers of the mushroom-body circuit parts (in ``labels`` order)."""
    cc, hb = labels.cell_class.to_numpy(), labels.hemibrain_type.to_numpy()
    return {
        "kc": np.flatnonzero(cc == "Kenyon_Cell"),
        "mbon": np.flatnonzero(cc == "MBON"),
        "dan": np.flatnonzero(cc == "DAN"),
        "apl": np.flatnonzero(hb == "APL"),
        "dpm": np.flatnonzero(hb == "DPM"),
        "pn": np.flatnonzero(cc == "ALPN"),
        "upn": np.flatnonzero((cc == "ALPN")
                              & (labels.cell_sub_class.to_numpy() == "uniglomerular")),
    }


def glomerulus_of_pn(hemibrain_type: str) -> str:
    """'DM1' from 'DM1_lPN'."""
    return str(hemibrain_type).split("_")[0]


def odor_rows(labels, glomeruli, kind="orn", side="both"):
    """Rows that carry one "odor": the ORNs (kind='orn') or uniglomerular PNs
    (kind='pn') of the given glomeruli. In snapshot 630 the ORN type is in the
    hemibrain_type column (e.g. 'ORN_DM1')."""
    g = set(glomeruli)
    lab = labels
    if kind == "orn":
        m = ((lab.super_class == "sensory") & (lab.cell_class == "olfactory")
             & lab.hemibrain_type.str.replace("ORN_", "", regex=False).isin(g)
             & lab.hemibrain_type.str.startswith("ORN_"))
    elif kind == "pn":
        m = ((lab.cell_class == "ALPN") & (lab.cell_sub_class == "uniglomerular")
             & lab.hemibrain_type.map(glomerulus_of_pn).isin(g))
    else:
        raise ValueError("kind must be 'orn' or 'pn'")
    if side != "both":
        m &= lab.side == side
    return np.flatnonzero(m.to_numpy())


# ---------------------------------------------------------------------------
# The learning rule's parameters
# ---------------------------------------------------------------------------
@dataclass
class LearningRule:
    """Parameters of the dopamine-gated depression rule.

    tau_kc_ms : KC eligibility trace time constant (Handler 2019: depression
        at 0 and +0.5 s KC-to-DAN intervals, almost none at 6 s).
    tau_da_ms : dopamine trace time constant. UNVERIFIED modelling choice:
        must be short compared with the 0.5 s gap of Hige's backward protocol
        (no change), because the DAN-first potentiation branch that would
        otherwise cancel it (Handler 2019, DopR2) is not modelled.
    eta : learning rate (1/s per unit tag x dopamine), calibrated so that the
        Hige 2015 protocol cuts MBON-gamma1pedc>a/b odor spiking by ~80%.
    slow_ratio : eta multiplier for SLOW_COMPARTMENTS (alpha2, alpha3),
        calibrated so the 1-s protocol gives < 10% there but 1 min gives a
        large change (Hige 2015).
    """
    tau_kc_ms: float = 1000.0
    tau_da_ms: float = 200.0
    eta: float = 1.0
    slow_ratio: float = 0.05


# ---------------------------------------------------------------------------
# Compiled inner loop: the baseline trial + the learning rule
# ---------------------------------------------------------------------------
@nb.njit(cache=True, nogil=True)
def _plastic_trial(n_steps, indptr, post, count, w_syn, silenced, rfc_steps,
                   ev_ptr, ev_neuron, w_poi, delay_steps,
                   c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, rec_idx,
                   kc_of, kc_wbase, wk,
                   dan_ptr, dan_grp, dan_inc,
                   pair_ptr, pair_grp, pair_eptr, pair_ent,
                   eta, c_x, c_d, dt_s, tail_s, plastic_on):
    """One trial. Identical to fast_engine._simulate_trial except that
    (1) a KC's outgoing weights are read from ``wk`` (float, initialised to
    count x w_syn, so identical numbers when nothing has been learned), and
    (2) when ``plastic_on``, KC spikes feed the tag ``x``, DAN spikes feed
    the dopamine level ``D`` (per synapse group) and the plastic entries of
    ``wk`` are multiplied by exp(-eta * x * D * dt) every step. ``wk`` is
    changed in place. Returns (spike_steps, spike_neurons, voltages, n_touched).
    """
    n_neurons = rfc_steps.shape[0]
    n_kc = kc_wbase.shape[0]
    n_grp = 0                                    # number of synapse groups
    for p in range(pair_grp.shape[0]):
        if pair_grp[p] + 1 > n_grp:
            n_grp = pair_grp[p] + 1
    for e in range(dan_grp.shape[0]):
        if dan_grp[e] + 1 > n_grp:
            n_grp = dan_grp[e] + 1
    x = np.zeros(n_kc)
    D = np.zeros(n_grp)
    x_live = False

    slot = np.full(n_neurons, -1, np.int32)
    act_id = np.empty(n_neurons, np.int32)
    v_a = np.empty(n_neurons)
    g_a = np.empty(n_neurons)
    ls_a = np.empty(n_neurons, np.int64)
    rf_a = np.empty(n_neurons, np.int64)
    n_active = 0
    rest = v_0

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

        rest = c_v0 + ((c_vg * 0.0) + (c_vv * rest))
        first_new = n_sp
        for k in range(n_active):
            if n - ls_a[k] >= rf_a[k]:
                gi = g_a[k]
                if -1e-200 < gi < 1e-200:
                    gi = 0.0
                vi = c_v0 + ((c_vg * gi) + (c_vv * v_a[k]))
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
            xs = sp_neu[a]
            b = a - 1
            while b >= first_new and sp_neu[b] > xs:
                sp_neu[b + 1] = sp_neu[b]
                b -= 1
            sp_neu[b + 1] = xs

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
            kk = kc_of[j]
            if plastic_on:
                # the spike arrives at its targets now: tag / dopamine go up
                if kk >= 0:
                    x[kk] += 1.0
                    x_live = True
                for e in range(dan_ptr[j], dan_ptr[j + 1]):
                    D[dan_grp[e]] += dan_inc[e]
            if silenced[j]:
                continue
            if kk >= 0:
                base = kc_wbase[kk] - indptr[j]
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
                        g_a[k] += wk[base + s]
            else:
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

        if plastic_on:
            any_d = False
            for gq in range(n_grp):
                if D[gq] > 1e-12:
                    any_d = True
                    break
            if any_d and x_live:
                for kk in range(n_kc):
                    xk = x[kk]
                    if xk > 1e-9:
                        for p in range(pair_ptr[kk], pair_ptr[kk + 1]):
                            dg = D[pair_grp[p]]
                            if dg > 1e-12:
                                f = np.exp(-eta * xk * dg * dt_s)
                                for e in range(pair_eptr[p], pair_eptr[p + 1]):
                                    wk[pair_ent[e]] *= f
            # both traces fade by one step
            if x_live:
                live = False
                for kk in range(n_kc):
                    if x[kk] > 0.0:
                        x[kk] *= c_x
                        if x[kk] < 1e-12:
                            x[kk] = 0.0
                        else:
                            live = True
                x_live = live
            if any_d:
                for gq in range(n_grp):
                    D[gq] *= c_d

    # After the trial: let what is left of tag and dopamine finish fading
    # with no further spikes. Integral of x*D over the rest of time
    # = x_end * D_end * tail_s, tail_s = tau_kc*tau_da/(tau_kc+tau_da).
    if plastic_on:
        for kk in range(n_kc):
            xk = x[kk]
            if xk > 1e-9:
                for p in range(pair_ptr[kk], pair_ptr[kk + 1]):
                    dg = D[pair_grp[p]]
                    if dg > 1e-12:
                        f = np.exp(-eta * xk * dg * tail_s)
                        for e in range(pair_eptr[p], pair_eptr[p + 1]):
                            wk[pair_ent[e]] *= f

    return sp_step[:n_sp].copy(), sp_neu[:n_sp].copy(), vrec, n_active


# ---------------------------------------------------------------------------
# Results and learning state
# ---------------------------------------------------------------------------
@dataclass
class TrialResult:
    """Spikes of one trial: ``step`` and ``neuron`` (row number), one entry
    per spike, plus bookkeeping."""
    step: np.ndarray
    neuron: np.ndarray
    n_steps: int
    dt_ms: float
    voltages_V: dict = field(default_factory=dict)
    wall_time_s: float = 0.0
    n_touched: int = 0

    def counts(self, rows, t0_ms=0.0, t1_ms=None, n_neurons=None):
        """Spike count of each row in ``rows`` within [t0, t1) ms."""
        t1 = self.n_steps * self.dt_ms if t1_ms is None else t1_ms
        s0, s1 = int(round(t0_ms / self.dt_ms)), int(round(t1 / self.dt_ms))
        m = (self.step >= s0) & (self.step < s1)
        rows = np.asarray(rows, np.int64)
        if rows.size == 0:
            return np.zeros(0, np.int64)
        nn = int(max(rows.max() + 1, self.neuron.max() + 1 if self.neuron.size else 0))
        return np.bincount(self.neuron[m], minlength=nn)[rows]

    def active(self, rows, t0_ms=0.0, t1_ms=None):
        """Boolean: which rows spiked at least once in the window."""
        return self.counts(rows, t0_ms, t1_ms) > 0


class LearningState:
    """The learned weights of one "fly" (one experiment sequence). Each
    sequence gets its own copy, so sequences can run side by side."""

    def __init__(self, brain: "PlasticBrain"):
        self.brain = brain
        self.wk = brain.wk0.copy()

    def copy(self):
        s = LearningState.__new__(LearningState)
        s.brain, s.wk = self.brain, self.wk.copy()
        return s

    def relative_weights(self):
        """Current / initial weight of every plastic KC->MBON pair
        (order = brain.plastic_table rows)."""
        idx = self.brain.plastic_table["wk_index"].to_numpy()
        return self.wk[idx] / self.brain.wk0[idx]

    def mbon_type_weight(self, mbon_type=None):
        """Synapse-count-weighted mean relative weight per MBON type
        (or for one type)."""
        t = self.brain.plastic_table
        rel = self.relative_weights()
        w0 = self.brain.wk0[t["wk_index"].to_numpy()]
        df = pd.DataFrame({"type": t["mbon_type"].to_numpy(), "w0": w0, "w": w0 * rel})
        g = df.groupby("type")[["w0", "w"]].sum()
        s = g["w"] / g["w0"]
        return float(s[mbon_type]) if mbon_type is not None else s


# ---------------------------------------------------------------------------
# The plastic brain
# ---------------------------------------------------------------------------
class PlasticBrain:
    """A FastBrain (whole brain, a sign-fixed brain, or a sub-circuit) plus
    the mushroom-body learning rule.

    Parameters
    ----------
    brain : FastBrain whose rows match ``labels`` row for row.
    labels : DataFrame with root_id, cell_class, hemibrain_type, side
        (``load_labels()``, or its rows for a sub-circuit).
    rule : LearningRule.
    dan_mode : "modulatory" (default: DANs with a known compartment have no
        fast output synapses; their spikes act only through dopamine) or
        "fast" (published model: DAN outputs are fast excitatory synapses).
    """

    def __init__(self, brain: FastBrain, labels: pd.DataFrame, rule: LearningRule | None = None,
                 dan_mode: str = "modulatory"):
        if not np.array_equal(np.asarray(labels["root_id"], np.int64), brain.root_ids):
            raise ValueError("labels rows must match the brain's rows exactly")
        if dan_mode not in ("modulatory", "fast"):
            raise ValueError("dan_mode must be 'modulatory' or 'fast'")
        self.brain = brain
        self.labels = labels.reset_index(drop=True)
        self.rule = rule or LearningRule()
        self.dan_mode = dan_mode
        self.params = dict(brain.params)
        self.n_threads = brain.n_threads
        self.root_ids = brain.root_ids
        self.n_neurons = brain.n_neurons
        self._build_tables()

    # -- construction --------------------------------------------------------
    def _build_tables(self):
        b, lab = self.brain, self.labels
        indptr, post, count = b._indptr, b._post, b._count
        w_syn = self.params["w_syn"] * 1e-3
        cc = lab.cell_class.to_numpy()
        hb = lab.hemibrain_type.to_numpy()
        side = lab.side.to_numpy()
        n = self.n_neurons

        kc_rows = np.flatnonzero(cc == "Kenyon_Cell")
        self.kc_rows = kc_rows
        kc_of = np.full(n, -1, np.int32)
        kc_of[kc_rows] = np.arange(kc_rows.size, dtype=np.int32)
        out_n = (indptr[kc_rows + 1] - indptr[kc_rows]).astype(np.int64)
        kc_wbase = np.zeros(kc_rows.size, np.int64)
        if kc_rows.size:
            kc_wbase[1:] = np.cumsum(out_n)[:-1]
        wk0 = np.empty(int(out_n.sum()), np.float64)
        for k, j in enumerate(kc_rows):
            a, z = indptr[j], indptr[j + 1]
            wk0[kc_wbase[k]:kc_wbase[k] + (z - a)] = count[a:z].astype(np.float64) * w_syn
        self.kc_of, self.kc_wbase, self.wk0 = kc_of, kc_wbase, wk0

        # --- plastic KC -> MBON pairs and their synapse groups -------------
        mbon_comp = {r: MBON_COMPARTMENTS.get(hb[r]) for r in np.flatnonzero(cc == "MBON")}
        groups = {}             # (side, comps) -> group id
        rows = []               # plastic table rows
        pair_ptr = np.zeros(kc_rows.size + 1, np.int64)
        pair_grp, pair_eptr, pair_ent = [], [0], []
        for k, j in enumerate(kc_rows):
            lobe = kc_lobe(hb[j])
            ks = side[j] if side[j] in ("left", "right") else "left"
            by_grp = {}
            a, z = indptr[j], indptr[j + 1]
            for s in range(a, z):
                m = int(post[s])
                comps = mbon_comp.get(m)
                if not comps:
                    continue            # not an MBON, or an MBON with no compartment
                inter = tuple(c for c in comps
                              if COMPARTMENT_LOBE[c] in (lobe, "all"))
                if not inter:
                    inter = tuple(comps)   # e.g. an alpha'/beta' KC onto gamma1pedc
                key = (ks, inter)
                gid = groups.setdefault(key, len(groups))
                widx = kc_wbase[k] + (s - a)
                by_grp.setdefault(gid, []).append(widx)
                rows.append((j, m, int(s), int(widx), gid, hb[m], ks, "+".join(inter),
                             int(count[s])))
            for gid, ents in by_grp.items():
                pair_grp.append(gid)
                pair_ent.extend(ents)
                pair_eptr.append(len(pair_ent))
            pair_ptr[k + 1] = len(pair_grp)
        self.groups = groups
        self.group_keys = sorted(groups, key=groups.get)
        self.pair_ptr = pair_ptr
        self.pair_grp = np.asarray(pair_grp, np.int32)
        self.pair_eptr = np.asarray(pair_eptr, np.int64)
        self.pair_ent = np.asarray(pair_ent, np.int64)
        self.plastic_table = pd.DataFrame(rows, columns=[
            "kc_row", "mbon_row", "conn", "wk_index", "group", "mbon_type", "side",
            "compartments", "count"])

        # --- DAN -> dopamine increments ------------------------------------
        dan_rows = np.flatnonzero((cc == "DAN") & np.isin(hb, list(DAN_COMPARTMENTS)))
        is_kc = kc_of >= 0
        frac_left = {}
        for d in dan_rows:
            a, z = indptr[d], indptr[d + 1]
            tg = post[a:z]
            m = is_kc[tg]
            w = np.abs(count[a:z][m]).astype(float)
            sides = side[tg[m]]
            tot = w.sum()
            if tot > 0:
                frac_left[d] = float(w[sides == "left"].sum() / tot)
            else:
                frac_left[d] = 1.0 if side[d] == "left" else 0.0
        n_eff = {}
        for d in dan_rows:
            for sd, f in (("left", frac_left[d]), ("right", 1.0 - frac_left[d])):
                n_eff[(hb[d], sd)] = n_eff.get((hb[d], sd), 0.0) + f
        self.dan_rows = dan_rows
        self.dan_frac_left = pd.Series(frac_left, name="frac_left")
        # per DAN: list of (group, fast part, slow part)
        per_dan = {}
        for d in dan_rows:
            cover = set(DAN_COMPARTMENTS[hb[d]])
            lst = []
            for (gs, comps), gid in groups.items():
                hit = [c for c in comps if c in cover]
                if not hit:
                    continue
                f = frac_left[d] if gs == "left" else 1.0 - frac_left[d]
                if f <= 0 or n_eff.get((hb[d], gs), 0) <= 0:
                    continue
                scale = f / n_eff[(hb[d], gs)] / len(comps)
                fast = sum(1 for c in hit if c not in SLOW_COMPARTMENTS) * scale
                slow = sum(1 for c in hit if c in SLOW_COMPARTMENTS) * scale
                lst.append((gid, fast, slow))
            per_dan[d] = lst
        dan_ptr = np.zeros(n + 1, np.int64)
        cnt = np.zeros(n, np.int64)
        for d, lst in per_dan.items():
            cnt[d] = len(lst)
        np.cumsum(cnt, out=dan_ptr[1:])
        m_tot = int(dan_ptr[-1])
        self.dan_ptr = dan_ptr
        self.dan_grp = np.zeros(m_tot, np.int32)
        self._dan_fast = np.zeros(m_tot)
        self._dan_slow = np.zeros(m_tot)
        for d, lst in per_dan.items():
            for q, (gid, fast, slow) in enumerate(lst):
                e = dan_ptr[d] + q
                self.dan_grp[e], self._dan_fast[e], self._dan_slow[e] = gid, fast, slow

    def dan_increments(self):
        """Dopamine added to each group per DAN spike, with the slow
        compartments scaled by rule.slow_ratio."""
        return self._dan_fast + self.rule.slow_ratio * self._dan_slow

    def new_state(self) -> LearningState:
        return LearningState(self)

    def index_of(self, root_ids):
        return self.brain.index_of(root_ids)

    def rows_of_type(self, hemibrain_type):
        return np.flatnonzero(self.labels.hemibrain_type.to_numpy() == hemibrain_type)

    # -- stimulation ------------------------------------------------------
    def make_events(self, blocks, n_steps, rng):
        """Poisson input from ``blocks``: a list of (rows, rate_hz, t_on_ms,
        t_off_ms). In each step of [t_on, t_off) each row gets a kick with
        probability rate x dt (like the reference PoissonInput)."""
        dt = self.params["dt"]
        steps, neurons = [], []
        for rows, rate, t0, t1 in blocks:
            s0 = max(0, int(round(t0 / dt)))
            s1 = min(n_steps, int(round(t1 / dt)))
            if s1 <= s0 or rate <= 0:
                continue
            p = rate * dt * 1e-3
            if not 0 <= p <= 1:
                raise ValueError("rate x dt must be between 0 and 1")
            for i in np.asarray(rows, np.int64):
                k = rng.binomial(s1 - s0, p)
                if k:
                    steps.append(s0 + rng.choice(s1 - s0, size=k, replace=False))
                    neurons.append(np.full(k, i, np.int64))
        if steps:
            steps, neurons = np.concatenate(steps), np.concatenate(neurons)
        else:
            steps = neurons = np.zeros(0, np.int64)
        return FastBrain._pack_events(steps, neurons, n_steps)

    # -- running -----------------------------------------------------------
    def run(self, blocks, duration_ms, seed, state: LearningState | None = None,
            plastic=True, silence=(), record_v=(), events=None, excite_rows=None):
        """Simulate one trial.

        blocks : list of (rows, rate_hz, t_on_ms, t_off_ms) Poisson inputs.
        state : the learning state to use AND UPDATE (weights change in
            place). None = a fresh state that is thrown away.
        plastic : False = learning switched off (weights read, never changed).
        silence : row numbers whose outputs are set to zero.
        events : optional pre-packed (ev_ptr, ev_neuron) instead of blocks
            (then excite_rows lists the stimulated rows).
        """
        p = self.params
        n_steps = int(round(duration_ms / p["dt"]))
        if events is None:
            rng = np.random.default_rng(seed)
            events = self.make_events(blocks, n_steps, rng)
            exc = (np.unique(np.concatenate([np.asarray(r, np.int64) for r, *_ in blocks]))
                   if blocks else np.zeros(0, np.int64))
        else:
            exc = np.asarray(excite_rows if excite_rows is not None else [], np.int64)
        if state is None:
            state = self.new_state()
        dt_s = p["dt"] * 1e-3
        c_g, c_v0, c_vg, c_vv = _update_constants(p)
        rfc = np.full(self.n_neurons, _timestep(p["t_rfc"] * 1e-3, dt_s), np.int64)
        rfc[exc] = 0
        silenced = np.zeros(self.n_neurons, np.bool_)
        silenced[np.asarray(silence, np.int64)] = True
        if self.dan_mode == "modulatory":
            silenced[self.dan_rows] = True
        rec_idx = np.asarray(record_v, np.int64)
        delay_steps = int(p["t_dly"] * 1e-3 / dt_s + 0.5)
        w_syn = p["w_syn"] * 1e-3
        w_poi = w_syn * p["f_poi"]
        v_0, v_th, v_rst = p["v_0"] * 1e-3, p["v_th"] * 1e-3, p["v_rst"] * 1e-3
        r = self.rule
        tkc, tda = r.tau_kc_ms * 1e-3, r.tau_da_ms * 1e-3
        c_x, c_d = float(np.exp(-dt_s / tkc)), float(np.exp(-dt_s / tda))
        tail_s = tkc * tda / (tkc + tda)
        t0 = time.perf_counter()
        st, ne, vrec, n_t = _plastic_trial(
            n_steps, self.brain._indptr, self.brain._post, self.brain._count, w_syn,
            silenced, rfc, events[0], events[1], w_poi, delay_steps,
            c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, rec_idx,
            self.kc_of, self.kc_wbase, state.wk,
            self.dan_ptr, self.dan_grp, self.dan_increments(),
            self.pair_ptr, self.pair_grp, self.pair_eptr, self.pair_ent,
            float(r.eta), c_x, c_d, dt_s, tail_s, bool(plastic))
        return TrialResult(step=st, neuron=ne, n_steps=n_steps, dt_ms=p["dt"],
                           voltages_V={int(i): vrec[:, q] for q, i in enumerate(rec_idx)},
                           wall_time_s=time.perf_counter() - t0, n_touched=int(n_t))


# ---------------------------------------------------------------------------
# A mushroom-body-only circuit
# ---------------------------------------------------------------------------
def extract_circuit(brain: FastBrain, rows, n_threads=None):
    """A FastBrain made of only ``rows`` of ``brain`` and the connections
    among them (same counts, same signs, same order). Returns (circuit, rows)."""
    rows = np.unique(np.asarray(rows, np.int64))
    new_of = np.full(brain.n_neurons, -1, np.int64)
    new_of[rows] = np.arange(rows.size)
    pre_l, post_l, cnt_l = [], [], []
    for j in rows:
        a, z = brain._indptr[j], brain._indptr[j + 1]
        tg = new_of[brain._post[a:z]]
        keep = tg >= 0
        pre_l.append(np.full(int(keep.sum()), new_of[j], np.int64))
        post_l.append(tg[keep])
        cnt_l.append(brain._count[a:z][keep].astype(np.int64))
    circ = FastBrain.from_arrays(brain.root_ids[rows], np.concatenate(pre_l),
                                 np.concatenate(post_l), np.concatenate(cnt_l),
                                 params=brain.params,
                                 n_threads=brain.n_threads if n_threads is None else n_threads)
    return circ, rows


def mb_circuit_rows(labels):
    """The mushroom-body circuit: all projection neurons, Kenyon cells, MBONs,
    DANs, APL and DPM."""
    r = mb_rows(labels)
    return np.unique(np.concatenate([r["pn"], r["kc"], r["mbon"], r["dan"], r["apl"], r["dpm"]]))


# ---------------------------------------------------------------------------
# Standard protocols (times in ms)
# ---------------------------------------------------------------------------
#: Hige 2015: four 1-ms light pulses at 2 Hz starting 0.2 s after odor onset.
HIGE_PULSES_MS = (200.0, 700.0, 1200.0, 1700.0)
#: Our model of one 1-ms light pulse: the DAN is driven for 10 ms at 300 Hz
#: (about 3 spikes). UNVERIFIED: the real number of spikes per pulse is not
#: known to us; eta is calibrated on the whole protocol, so this sets only
#: the scale of eta.
PULSE_MS = 10.0
PULSE_RATE_HZ = 300.0


def pulse_blocks(rows, onsets_ms, width_ms=PULSE_MS, rate_hz=PULSE_RATE_HZ):
    return [(rows, rate_hz, t, t + width_ms) for t in onsets_ms]


def odor_block(rows, rate_hz, t_on_ms=0.0, t_off_ms=1000.0):
    return [(rows, rate_hz, t_on_ms, t_off_ms)]
