"""Operation counts and costs: the virtual computer's bookkeeping.

A workload produces ``Ops`` (how many of each operation it needed). A core turns Ops into a
``Cost`` (modeled time and energy) with its price list. The emulator's own wall-clock time is
NEVER used as a design's speed; only ``Cost`` is.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


class Ops(Counter):
    """Counts of operations, e.g. Ops(neuron_update=360000, syn_event=12000)."""

    def scaled(self, f):
        return Ops({k: v * f for k, v in self.items()})

    def plus(self, other):
        out = Ops(self)
        for k, v in other.items():
            out[k] = out.get(k, 0) + v
        return out


@dataclass
class Cost:
    time_s: float
    energy_J: float
    label: str                      # "measured", "modeled" or "guessed" (worst input wins)
    core: str
    notes: list = field(default_factory=list)

    def __add__(self, other):
        order = ["measured", "modeled", "guessed"]
        lab = order[max(order.index(self.label), order.index(other.label))]
        return Cost(self.time_s + other.time_s, self.energy_J + other.energy_J, lab,
                    f"{self.core}+{other.core}", self.notes + other.notes)

    def as_dict(self):
        return {"time_s": self.time_s, "energy_J": self.energy_J, "label": self.label,
                "core": self.core, "notes": list(self.notes)}
