"""Neuromorphic core: prices a spiking workload's operation counts with Loihi's published
per-operation time and energy (vhc/prices.py), in two modes and two versions.

Mode "clocked" (Loihi-style): every resident neuron is updated every time step, whether or
not anything happened to it; each step ends with a barrier sync. Cores run in parallel.

Mode "event" (ideal event-driven): a neuron is touched only when an event arrives for it
(and once more when it spikes); no clock, no barrier. This is a best case no shipping chip
reaches; it bounds what event-driven design can buy.

Version "v0": Loihi (2018) per-op constants only; static/leakage power excluded.
Version "v1" (default):
  * clocked timing CALIBRATED on real Loihi 2 (vhc/neurocal.py): + A per time step and
    + B per spike (fitted to Sandia's whole-fly-brain runs; a 12-chip system, so for a
    one-chip job it is a pessimistic figure; the event mode is a bound and is not calibrated);
  * static (leakage) power of every chip used, for the whole busy time: low / mid / high =
    18 / 73 / 296 mW per Loihi 2 chip (DERIVED from Shrestha et al. 2024; prices.py).
Counts used (all per task): steps, neurons, spikes, syn_event (synaptic deliveries),
input_event (sensor spikes arriving), syn_update (learning writes).
"""
from __future__ import annotations

import math

from ..ledger import Cost
from ..prices import LOIHI, LOIHI2_CORES_PER_CHIP, NEURO_STATIC_W_CHIP

MODES = ("clocked", "event")
VERSIONS = ("v0", "v1")
STATIC = tuple(NEURO_STATIC_W_CHIP)          # "low", "mid", "high"


def n_cores_for(neurons):
    return max(1, math.ceil(neurons / LOIHI["neurons_per_core"].value))


def chips_for(cores):
    return max(1, math.ceil(cores / LOIHI2_CORES_PER_CHIP.value))


def static_W(cores, static="mid"):
    """Leakage power of the chips holding ``cores`` cores (v1)."""
    return chips_for(cores) * NEURO_STATIC_W_CHIP[static].value


def price(c, mode="clocked", n_cores=None, version="v1", static="mid"):
    """Modeled time (s) and energy (J) for counts ``c`` (a dict)."""
    if version not in VERSIONS:
        raise ValueError(version)
    L = {k: p.value for k, p in LOIHI.items()}
    steps, neurons = c.get("steps", 0), c.get("neurons", 0)
    spikes, syn, inp, upd = (c.get("spikes", 0), c.get("syn_event", 0), c.get("input_event", 0),
                             c.get("syn_update", 0))
    events = syn + inp
    cores = n_cores or n_cores_for(neurons)
    notes = ["Loihi per-op constants (Davies 2018, pre-silicon)"]
    if mode == "clocked":
        e = (neurons * steps * L["nu_inactive_J"] + spikes * (L["nu_active_J"] - L["nu_inactive_J"])
             + events * L["synop_J"] + spikes * L["spike_route_J"] + upd * L["syn_update_J"])
        barrier = L["barrier_s_1tile"] if cores <= 4 else L["barrier_s_32tile"]
        # cores work in parallel; work is assumed evenly spread over cores (optimistic)
        t = (steps * ((neurons / cores) * L["nu_inactive_s"] + barrier)
             + (spikes * (L["nu_active_s"] - L["nu_inactive_s"]) + events * L["synop_s"]
                + upd * L["syn_update_s"]) / cores)
        notes.append(f"{cores} core(s), even load assumed")
    elif mode == "event":
        touched = events + spikes
        e = (touched * L["nu_active_J"] + events * L["synop_J"] + spikes * L["spike_route_J"]
             + upd * L["syn_update_J"])
        t = touched * L["nu_active_s"] + events * L["synop_s"] + upd * L["syn_update_s"]
        notes.append("ideal event-driven: no clock, no barrier, one core, serial")
    else:
        raise ValueError(mode)
    if version == "v0":
        notes.append("v0: static power excluded; timing not calibrated")
        return Cost(t, e, "modeled", f"neuromorphic-{mode}", notes)
    if mode == "clocked":
        from ..neurocal import fit
        cal = fit()
        t += steps * cal["A_s_per_step"] + (spikes + inp) * cal["B_s_per_spike"]
        notes.append("v1: timing calibrated on Sandia's 12-chip Loihi 2 runs (pessimistic for one chip)")
    p_static = static_W(cores, static)
    e += p_static * t
    notes.append(f"v1: static power {p_static * 1e3:.0f} mW ({static}) x busy time")
    return Cost(t, e, "modeled", f"neuromorphic-{mode}", notes)


def price_range(c, mode="clocked", n_cores=None):
    """v1's honest range: (best, worst). Best = v0's uncalibrated timing (a one-chip job may
    not pay the 12-chip overheads; Loihi 2's minimum step is 200 ns) with the low static power;
    worst = calibrated timing with the high static power."""
    lo = price(c, mode, n_cores, version="v0")
    lo = Cost(lo.time_s, lo.energy_J + static_W(n_cores or n_cores_for(c.get("neurons", 0)), "low") * lo.time_s,
              "modeled", lo.core, ["v1 best case"])
    hi = price(c, mode, n_cores, version="v1", static="high")
    return lo, hi
