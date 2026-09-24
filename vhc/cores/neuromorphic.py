"""Neuromorphic core: prices a spiking workload's operation counts with Loihi's published
per-operation time and energy (vhc/prices.py), in two modes.

Mode "clocked" (Loihi-style): every resident neuron is updated every time step, whether or
not anything happened to it; each step ends with a barrier sync. Cores run in parallel.

Mode "event" (ideal event-driven): a neuron is touched only when an event arrives for it
(and once more when it spikes); no clock, no barrier. This is a best case no shipping chip
reaches; it bounds what event-driven design can buy.

Both use the same per-operation prices, so the gap between them is the cost of the clock.
Counts used (all per task): steps, neurons, spikes, syn_event (synaptic deliveries),
input_event (sensor spikes arriving), syn_update (learning writes).
Static/leakage power is EXCLUDED (not published per core); every report says so.
"""
from __future__ import annotations

import math

from ..ledger import Cost
from ..prices import LOIHI

MODES = ("clocked", "event")


def n_cores_for(neurons):
    return max(1, math.ceil(neurons / LOIHI["neurons_per_core"].value))


def price(c, mode="clocked", n_cores=None):
    """Modeled time (s) and energy (J) for counts ``c`` (a dict)."""
    L = {k: p.value for k, p in LOIHI.items()}
    steps, neurons = c.get("steps", 0), c.get("neurons", 0)
    spikes, syn, inp, upd = (c.get("spikes", 0), c.get("syn_event", 0), c.get("input_event", 0),
                             c.get("syn_update", 0))
    events = syn + inp
    cores = n_cores or n_cores_for(neurons)
    notes = ["Loihi constants (Davies 2018, pre-silicon); static power excluded"]
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
    return Cost(t, e, "modeled", f"neuromorphic-{mode}", notes)
