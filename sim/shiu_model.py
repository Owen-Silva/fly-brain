# Portions of this file are copied or adapted from Drosophila_brain_model by Philip Shiu
# and Nico Spiller (https://github.com/philshiu/Drosophila_brain_model, commit 91bdd1e),
# used under the MIT License. Their copyright and permission notice:
#
# MIT License
#
# Copyright (c) 2023 Philip Shiu and Nico Spiller
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# This project's own code is also MIT-licensed: see LICENSE and THIRD_PARTY_NOTICES.md.

"""Port of the Shiu et al. (Nature 2024) whole-brain fly model to this machine.

What this file is, in plain English
-----------------------------------
Shiu and colleagues published a computer model of the whole fruit fly brain:
every one of the ~130,000 neurons is a simple "leaky integrate-and-fire"
neuron, and every connection comes from the FlyWire wiring diagram. Their
code lives, unmodified, in ``data/reference/model.py``. This file is a
faithful copy of that code, changed only where it had to be so it runs here
(Windows, no C++ compiler, newer versions of Brian2 and pandas).

Every parameter, equation, weight and sign rule below is IDENTICAL to the
reference. The places where something *had* to change are marked
``# PORT NOTE`` and are listed here:

1. Brian2 is told to use its pure-Python ("numpy") engine, because this
   machine has no C++ compiler. The maths is the same; it is just slower.
2. The reference rebuilt the whole brain from disk for every single trial and
   spread trials over CPU cores with ``joblib``. Here the brain is built once
   per experiment, a snapshot is stored, and each trial restarts from that
   snapshot (``Network.store`` / ``Network.restore``). The starting state of
   every trial is exactly the same as in the reference; only the loading work
   is skipped. Trials run one after another (no multiprocessing tricks, which
   are fragile on Windows).
3. The reference never set a random seed, so its trials cannot be repeated
   exactly. Here trial ``k`` uses seed ``seed + k``, so any run can be
   reproduced bit for bit.
4. Silencing: the reference zeroes each silenced neuron's outgoing synapses
   with a Brian2 string condition, one neuron at a time. Here the same
   synapses are zeroed with a numpy mask before the weights are loaded. The
   resulting weights are identical (only OUTGOING synapses are zeroed, exactly
   like the reference code, even though the reference README says "to and
   from").
5. Firing rates are computed exactly like ``utils.get_rate`` (spike count per
   trial divided by trial length, then mean and population standard
   deviation over trials, with zero for trials where the neuron was silent).

Data: the reference's own files in ``data/reference/``. ``dataset="783"``
(the public FlyWire release, the default for this project) or
``dataset="630"`` (the older snapshot the paper itself used).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent

import numpy as np
import pandas as pd

import brian2
from brian2 import (
    Hz,
    Network,
    NeuronGroup,
    PoissonInput,
    SpikeMonitor,
    Synapses,
    defaultclock,
    mV,
    ms,
    prefs,
)

# PORT NOTE 1: no C/C++ compiler on this machine, so force Brian2's numpy
# code generation target (identical equations, pure-Python execution).
prefs.codegen.target = "numpy"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REF_DIR = PROJECT_ROOT / "data" / "reference"

DATASETS = {
    "783": (REF_DIR / "Completeness_783.csv", REF_DIR / "Connectivity_783.parquet"),
    "630": (
        REF_DIR / "2023_03_23_completeness_630_final.csv",
        REF_DIR / "2023_03_23_connectivity_630_final.parquet",
    ),
}

# ---------------------------------------------------------------------------
# Model parameters: copied verbatim from data/reference/model.py
# (``default_params``). Do not edit; tests check these against the reference.
# ---------------------------------------------------------------------------
DEFAULT_PARAMS = {
    # trials
    't_run'     : 1000 * ms,              # duration of trial
    'n_run'     : 30,                     # number of runs

    # network constants
    # Kakaria and de Bivort 2017 https://doi.org/10.3389/fnbeh.2017.00008
    'v_0'       : -52 * mV,               # resting potential
    'v_rst'     : -52 * mV,               # reset potential after spike
    'v_th'      : -45 * mV,               # threshold for spiking
    't_mbr'     :  20 * ms,               # membrane time scale (capacitance * resistance = .002 * uF * 10. * Mohm)

    # Jürgensen et al https://doi.org/10.1088/2634-4386/ac3ba6
    'tau'       : 5 * ms,                 # time constant

    # Lazar et al https://doi.org/10.7554/eLife.62362
    't_rfc'     : 2.2 * ms,               # refractory period

    # Paul et al 2015 doi: 10.3389/fncel.2015.00029
    't_dly'     : 1.8*ms,                 # delay for changes in post-synaptic neuron

    # Free parameter
    'w_syn'     : .275 * mV,              # weight per synapse (note: modulated by exponential decay)
    # Default activation rates
    'r_poi'     : 150*Hz,                 # default rate of the Poisson inputs
    'r_poi2'    :   0*Hz,                 # default rate of a 2nd class of Poisson inputs
    'f_poi'     : 250,                    # scaling factor for Poisson synapse; 250 is sufficient to cause spiking

    # equations for neurons               # alpha synapse https://doi.org/10.1017/CBO9780511815706; See https://brian2.readthedocs.io/en/stable/user/converting_from_integrated_form.html
    'eqs'       : dedent(''' 
                    dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)
                    dg/dt = -g / tau               : volt (unless refractory) 
                    rfc                            : second
                    '''),
    # condition for spike
    'eq_th'     : 'v > v_th',
    # rules for spike
    'eq_rst'    : 'v = v_rst; w = 0; g = 0 * mV',
}

# ---------------------------------------------------------------------------
# Neuron IDs used by the paper (copied from data/reference/figures.ipynb).
# These are FlyWire "root IDs" from snapshot 630.
# ---------------------------------------------------------------------------
# Labellar sugar-sensing gustatory receptor neurons, right hemisphere (Fig 1).
SUGAR_R_630 = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345, 720575940617000768,
    720575940630797113, 720575940632889389, 720575940621754367, 720575940621502051, 720575940640649691,
    720575940639332736, 720575940616885538, 720575940639198653, 720575940620900446, 720575940617937543,
    720575940632425919, 720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
# Bitter-sensing gustatory receptor neurons (Fig 3A).
BITTER_R_630 = [
    720575940621778381, 720575940602353632, 720575940617094208, 720575940619197093, 720575940626287336,
    720575940618600651, 720575940627692048, 720575940630195909, 720575940646212996, 720575940610483162,
    720575940645743412, 720575940627578156, 720575940622298631, 720575940621008895, 720575940629146711,
    720575940610259370, 720575940610481370, 720575940619028208, 720575940614281266, 720575940613061118,
    720575940604027168,
]
# Water-sensing gustatory receptor neurons, right hemisphere (Fig 4A).
WATER_R_630 = [
    720575940612950568, 720575940631898285, 720575940606002609, 720575940612579053, 720575940622902535,
    720575940616177458, 720575940660292225, 720575940622486922, 720575940613786774, 720575940629852866,
    720575940625861168, 720575940613996959, 720575940617857694, 720575940644965399, 720575940625203504,
    720575940630553415, 720575940635172191, 720575940634796536,
]
# Ir94e gustatory receptor neurons (Fig 3C; the code's fig_3b).
IR94E_630 = [
    720575940614211295, 720575940638218173, 720575940628832256, 720575940626016017, 720575940621375231,
    720575940612920386, 720575940614273292, 720575940628198503, 720575940626241636, 720575940619387814,
    720575940624604560, 720575940615274425, 720575940610683315, 720575940627265265, 720575940624079544,
    720575940629211607, 720575940615089369, 720575940631082124,
]
# MN9, the proboscis motor neuron the paper reads out. "LEFT"/"RIGHT" follow
# the labels in the reference code (figures.ipynb cell 17). The paper's own
# side labels are mirrored (FlyWire images were stored left-right flipped), so
# trust the IDs: MN9_LEFT is the MN9 on the OPPOSITE side to the sugar set
# ("contralateral") and is the default readout in every notebook cell.
MN9_LEFT = 720575940660219265
MN9_RIGHT_630 = 720575940645521262

# Snapshot 783 renamed three of these neurons (a neuron gets a new root ID
# whenever its reconstruction is edited). Each successor was found by
# comparing connection "fingerprints" between the two snapshots. The method is
# written up in experiments/phase3/map_ids_630_to_783.py; the numbers below come
# from an interactive run of the same method (the script itself, which would
# write id_map_630_to_783.csv, has not been run yet).
ID_630_TO_783 = {
    720575940620900446: 720575940639259967,  # sugar GRN, same 557 output synapses, cosine 0.98
    720575940618600651: 720575940619072513,  # bitter GRN, same 302 output synapses, cosine 0.87
    720575940645521262: 720575940618238523,  # MN9 right, 5886 vs 5874 input synapses, cosine 0.67 (MN9 left vs itself: 0.73)
}


def ids_for(dataset: str, ids_630) -> list[int]:
    """Translate paper (snapshot 630) IDs to the chosen dataset."""
    if dataset == "630":
        return [int(i) for i in ids_630]
    return [int(ID_630_TO_783.get(int(i), int(i))) for i in ids_630]


SUGAR_R_783 = ids_for("783", SUGAR_R_630)
BITTER_R_783 = ids_for("783", BITTER_R_630)
WATER_R_783 = ids_for("783", WATER_R_630)
IR94E_783 = ids_for("783", IR94E_630)
MN9_RIGHT_783 = ID_630_TO_783[MN9_RIGHT_630]


def mn9_ids(dataset: str) -> tuple[int, int]:
    """(left, right) MN9 IDs for a dataset."""
    return MN9_LEFT, (MN9_RIGHT_630 if dataset == "630" else MN9_RIGHT_783)


# ---------------------------------------------------------------------------
# Connectome loading (cached in memory, one copy per dataset per process)
# ---------------------------------------------------------------------------
@dataclass
class Connectome:
    dataset: str
    flyids: np.ndarray          # position k = Brian2 neuron index k
    flyid2i: dict               # FlyWire ID -> Brian2 index
    i_pre: np.ndarray
    i_post: np.ndarray
    exc_x_conn: np.ndarray      # signed synapse count ("Excitatory x Connectivity")

    @property
    def n(self) -> int:
        return len(self.flyids)


_CACHE: dict[str, Connectome] = {}


def load_connectome(dataset: str = "783") -> Connectome:
    """Load the reference's completeness + connectivity files.

    Exactly as the reference: neuron k in the simulation is row k of the
    completeness CSV, connections come from the ``Presynaptic_Index`` /
    ``Postsynaptic_Index`` columns, and the signed weight is the
    ``Excitatory x Connectivity`` column (synapse count, negative for
    GABA/glutamate neurons).
    """
    if dataset in _CACHE:
        return _CACHE[dataset]
    path_comp, path_con = DATASETS[dataset]
    df_comp = pd.read_csv(path_comp, index_col=0)
    flyids = df_comp.index.to_numpy(dtype=np.int64)
    cols = ["Presynaptic_ID", "Postsynaptic_ID", "Presynaptic_Index",
            "Postsynaptic_Index", "Excitatory x Connectivity"]
    df_con = pd.read_parquet(path_con, columns=cols)
    i_pre = df_con["Presynaptic_Index"].to_numpy(dtype=np.int64)
    i_post = df_con["Postsynaptic_Index"].to_numpy(dtype=np.int64)
    # Guard against an index mismatch: the stored indices must point at the
    # same neuron as the stored IDs (the reference relies on this silently).
    if not (np.array_equal(flyids[i_pre], df_con["Presynaptic_ID"].to_numpy())
            and np.array_equal(flyids[i_post], df_con["Postsynaptic_ID"].to_numpy())):
        raise ValueError(f"dataset {dataset}: connectivity indices do not match completeness order")
    conn = Connectome(
        dataset=dataset,
        flyids=flyids,
        flyid2i={int(f): i for i, f in enumerate(flyids)},
        i_pre=i_pre,
        i_post=i_post,
        exc_x_conn=df_con["Excitatory x Connectivity"].to_numpy(dtype=np.float64),
    )
    del df_con
    _CACHE[dataset] = conn
    return conn


def to_indices(conn: Connectome, ids) -> list[int]:
    """FlyWire IDs -> Brian2 indices, with a clear error for unknown IDs."""
    missing = [int(i) for i in ids if int(i) not in conn.flyid2i]
    if missing:
        raise KeyError(f"IDs not in dataset {conn.dataset}: {missing}")
    return [conn.flyid2i[int(i)] for i in ids]


# ---------------------------------------------------------------------------
# Network construction: create_model + poi + silence from the reference
# ---------------------------------------------------------------------------
def build_network(conn: Connectome, exc, exc2=(), slnc=(), params=None):
    """Build the Brian2 network exactly as the reference's run_trial does.

    ``exc``, ``exc2``, ``slnc`` are Brian2 indices (not FlyWire IDs).
    Returns (net, neu, syn, spk_mon).
    """
    params = DEFAULT_PARAMS if params is None else params

    # --- create_model() ---
    neu = NeuronGroup(  # create neurons
        N=conn.n,
        model=params['eqs'],
        method='linear',
        threshold=params['eq_th'],
        reset=params['eq_rst'],
        refractory='rfc',
        name='default_neurons',
        namespace=params,
    )
    neu.v = params['v_0']  # initialize values
    neu.g = 0
    neu.rfc = params['t_rfc']

    syn = Synapses(neu, neu, 'w : volt', on_pre='g += w', delay=params['t_dly'], name='default_synapses')
    syn.connect(i=conn.i_pre, j=conn.i_post)

    # --- define connection weight, with silence() folded in ---
    # PORT NOTE 4: the reference sets syn.w = weights, then for each silenced
    # neuron i runs syn.w['i == <i>'] = 0 mV. Zeroing the same rows first
    # gives identical weights and avoids one full pass per silenced neuron.
    w = conn.exc_x_conn.copy()
    if len(slnc):
        w[np.isin(conn.i_pre, np.asarray(list(slnc), dtype=np.int64))] = 0.0
    syn.w = w * params['w_syn']

    spk_mon = SpikeMonitor(neu)

    # --- poi() ---
    pois = []
    for i in exc:
        i = int(i)
        p = PoissonInput(
            target=neu[i],
            target_var='v',
            N=1,
            rate=params['r_poi'],
            weight=params['w_syn']*params['f_poi']
            )
        neu[i].rfc = 0 * ms  # no refractory period for Poisson targets
        pois.append(p)

    for i in exc2:
        i = int(i)
        p = PoissonInput(
            target=neu[i],
            target_var='v',
            N=1,
            rate=params['r_poi2'],
            weight=params['w_syn']*params['f_poi']
            )
        neu[i].rfc = 0 * ms  # no refractory period for Poisson targets
        pois.append(p)

    net = Network(neu, syn, spk_mon, *pois)
    return net, neu, syn, spk_mon


# ---------------------------------------------------------------------------
# Running trials
# ---------------------------------------------------------------------------
@dataclass
class TrialResult:
    spikes: pd.DataFrame        # one row per spike: t (s), trial, flywire_id, exp_name (reference format)
    rates: pd.Series            # mean rate (Hz) per FlyWire ID over trials, neurons with >= 1 spike
    rate_std: pd.Series         # std (ddof=0) of the per-trial rate, same index
    settings: dict = field(default_factory=dict)

    def rate_of(self, flyid) -> float:
        return float(self.rates.get(int(flyid), 0.0))

    def spike_trains(self, trial: int) -> dict:
        """{flywire_id: array of spike times in seconds} for one trial."""
        d = self.spikes[self.spikes["trial"] == trial]
        return {int(k): g["t"].to_numpy() for k, g in d.groupby("flywire_id")}


def rates_from_spikes(spikes: pd.DataFrame, duration_s: float, n_trials: int):
    """Same arithmetic as the reference's utils.get_rate, for one experiment."""
    if spikes.empty:
        empty = pd.Series(dtype=float, name="rate_hz")
        return empty, empty.copy()
    counts = spikes.groupby(["flywire_id", "trial"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=range(n_trials), fill_value=0)
    per_trial = counts.to_numpy(dtype=float) / duration_s
    rates = pd.Series(per_trial.mean(axis=1), index=counts.index, name="rate_hz")
    std = pd.Series(per_trial.std(axis=1), index=counts.index, name="rate_std_hz")
    order = rates.sort_values(ascending=False, kind="stable").index
    return rates.loc[order], std.loc[order]


def run_trials(excite_ids, silence_ids=(), duration_ms=1000, n_trials=30, rate_hz=150,
               excite2_ids=(), rate2_hz=0, seed=0, dataset="783", params=None,
               exp_name="exp", verbose=False, progress_ids=()) -> TrialResult:
    """Run one experiment: drive ``excite_ids`` with Poisson input, silence
    ``silence_ids``, repeat ``n_trials`` times.

    Defaults are the reference defaults (1000 ms, 30 trials, 150 Hz).
    ``excite2_ids`` get a second Poisson rate ``rate2_hz`` (the reference's
    ``neu_exc2`` / ``r_poi2``, used for sugar + bitter co-activation).
    Trial ``k`` is seeded with ``seed + k``. With ``verbose``, one line per
    trial is printed, including the spike counts of ``progress_ids``.
    """
    base = DEFAULT_PARAMS if params is None else params
    p = dict(base)
    p['r_poi'] = rate_hz * Hz
    p['r_poi2'] = rate2_hz * Hz
    p['t_run'] = duration_ms * ms
    p['n_run'] = n_trials

    t0 = time.perf_counter()
    # ``dataset`` may also be a ready-made Connectome (used by the unit tests
    # to run the exact same code on a tiny hand-built network).
    conn = dataset if isinstance(dataset, Connectome) else load_connectome(dataset)
    exc = to_indices(conn, excite_ids)
    exc2 = to_indices(conn, excite2_ids)
    slnc = to_indices(conn, silence_ids)
    t_load = time.perf_counter() - t0

    brian2.start_scope()
    net, neu, syn, spk_mon = build_network(conn, exc, exc2, slnc, p)
    net.store('trial_start')  # PORT NOTE 2: every trial starts from this state
    t_build = time.perf_counter() - t0 - t_load

    frames, trial_secs = [], []
    for k in range(n_trials):
        tk = time.perf_counter()
        net.restore('trial_start')
        brian2.seed(seed + k)  # PORT NOTE 3: reproducible trials
        net.run(p['t_run'])
        idx = np.asarray(spk_mon.i[:], dtype=np.int64)
        ts = np.asarray(spk_mon.t_[:], dtype=float)  # seconds
        frames.append(pd.DataFrame({
            't': ts,
            'trial': np.full(len(ts), k, dtype=np.int64),
            'flywire_id': conn.flyids[idx],
            'exp_name': exp_name,
        }))
        trial_secs.append(time.perf_counter() - tk)
        if verbose:
            watch = {int(f): int(np.sum(idx == conn.flyid2i[int(f)]))
                     for f in progress_ids if int(f) in conn.flyid2i}
            print(f"  [{exp_name}] trial {k + 1}/{n_trials}: {len(ts)} spikes, "
                  f"{trial_secs[-1]:.1f} s, watched counts {watch}", flush=True)

    spikes = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=['t', 'trial', 'flywire_id', 'exp_name'])
    rates, std = rates_from_spikes(spikes, duration_ms / 1000.0, n_trials)

    settings = {
        'exp_name': exp_name,
        'dataset': conn.dataset,
        'excite_ids': [int(i) for i in excite_ids],
        'excite2_ids': [int(i) for i in excite2_ids],
        'silence_ids': [int(i) for i in silence_ids],
        'rate_hz': float(rate_hz),
        'rate2_hz': float(rate2_hz),
        'duration_ms': float(duration_ms),
        'n_trials': int(n_trials),
        'seeds': [seed + k for k in range(n_trials)],
        'dt_ms': float(defaultclock.dt / ms),
        'brian2_version': brian2.__version__,
        'codegen_target': prefs.codegen.target,
        'load_s': round(t_load, 2),
        'build_s': round(t_build, 2),
        'trial_s': [round(s, 2) for s in trial_secs],
        'total_s': round(time.perf_counter() - t0, 2),
    }
    del net, neu, syn, spk_mon
    return TrialResult(spikes=spikes, rates=rates, rate_std=std, settings=settings)
