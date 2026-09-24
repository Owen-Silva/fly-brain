"""The scheduler: sends each job to a core.

Two steps:
  1. Rules (the design rule of docs/hybrid-roadmap.md 6.1): a job that must be exact goes to
     the conventional core; spiking circuits and on-the-fly learning go to the neuromorphic
     core; slow adaptive jobs may go to the living module; big dense maths to a GPU block.
  2. Among the cores the rules allow, pick the one with the lowest modeled energy whose
     accuracy meets the job's requirement (if estimates are supplied).
"""
from __future__ import annotations

from dataclasses import dataclass

ALLOWED = {
    "exact": ("conventional",),
    "spiking": ("neuromorphic", "conventional"),
    "learning": ("neuromorphic", "conventional"),
    "adaptive-bio": ("living", "neuromorphic"),
    "dense": ("gpu", "conventional"),
    "bookkeeping": ("conventional",),
}


@dataclass
class Job:
    name: str
    kind: str                  # a key of ALLOWED
    min_accuracy: float = 0.0  # exact jobs: 1.0


def route(job: Job, available, estimates=None):
    """Returns (core, reason). ``estimates``: {core: (accuracy, energy_J)} (optional)."""
    allowed = [c for c in ALLOWED[job.kind] if c in available]
    if not allowed:
        raise ValueError(f"no available core can run a {job.kind} job ({job.name})")
    if not estimates:
        return allowed[0], f"rule: {job.kind} -> {allowed[0]}"
    ok = [c for c in allowed if c in estimates and estimates[c][0] >= job.min_accuracy]
    if not ok:
        return allowed[0], "rule (no estimate met the accuracy requirement)"
    best = min(ok, key=lambda c: estimates[c][1])
    return best, f"cheapest allowed core meeting accuracy {job.min_accuracy:g}"


HYBRID = ("neuromorphic", "conventional")
HYBRID_LIVING = ("neuromorphic", "conventional", "living")
