"""Conventional (digital) core: operations -> cycles -> time and energy.

Two profiles:
  "m33": an Arm Cortex-M33 at 150 MHz (one RP2350 core). Cycles per operation are ASSUMED
         (vhc/prices.py M33_CYCLES); power is the published ~30 mW active figure.
  "x86": one core of this laptop (Intel i3-1215U). Nanoseconds per operation are MEASURED
         by vhc/calibrate.py; energy = time x 15 W rated base power (ASSUMED attribution).

The same operation names are used by every workload (see M33_CYCLES for the list).
"""
from __future__ import annotations

from ..ledger import Cost
from ..prices import (M33_ACTIVE_W, M33_CLOCK_HZ, M33_CYCLES, M33_SLEEP_W, M33_WAKE_S,
                      X86_POWER_W, x86_ns_per_op)

PROFILES = ("m33", "x86")


def m33_cycles(ops):
    unknown = set(ops) - set(M33_CYCLES)
    if unknown:
        raise KeyError(f"no M33 cycle price for {sorted(unknown)}")
    return sum(v * M33_CYCLES[k].value for k, v in ops.items())


def price(ops, profile="m33", wake=False):
    """Modeled time and energy of ``ops`` (a dict {operation: count})."""
    if profile == "m33":
        cyc = m33_cycles(ops)
        t = cyc / M33_CLOCK_HZ.value
        e = t * M33_ACTIVE_W.value
        notes = ["M33 cycles per op ASSUMED; 30 mW active (published)"]
        if wake:
            t += M33_WAKE_S.value
            e += M33_WAKE_S.value * M33_ACTIVE_W.value
            notes.append("wake-up latency GUESSED")
        return Cost(t, e, "modeled", "m33", notes)
    if profile == "x86":
        ns = x86_ns_per_op()
        if ns is None:
            raise RuntimeError("run python -m vhc.calibrate first (x86 ns per op not measured)")
        missing = set(ops) - set(ns)
        if missing:
            raise KeyError(f"no measured x86 price for {sorted(missing)}")
        t = sum(v * ns[k] for k, v in ops.items()) * 1e-9
        return Cost(t, t * X86_POWER_W.value, "modeled", "x86",
                    ["ns per op MEASURED on this laptop; energy = time x 15 W (ASSUMED)"])
    raise ValueError(profile)


def sleep_energy(seconds):
    """Energy of an M33 asleep for ``seconds`` (GUESSED sleep power)."""
    return seconds * M33_SLEEP_W.value


def x86_measured(seconds, what):
    """Wrap a measured laptop wall time as a Cost (energy = time x 15 W, ASSUMED)."""
    return Cost(seconds, seconds * X86_POWER_W.value, "measured", "x86-laptop",
                [f"{what}: wall time MEASURED on this laptop (median); energy = time x 15 W"])
