"""Validation kit: does a simulation result survive new random seeds and
changed model settings?

What this is, in plain English
------------------------------
PLAN.md Phase 6, step 1 says: before a simulation result counts as a finding,
"re-run with different random seeds and parameter variations. Does it still
hold?" This file does exactly that, the same way every time, so every lane of
the project checks its results by one shared rule.

You give it three things:

1. An **experiment**: a Python function ``experiment(brain, params, seed)``
   that runs the simulation and returns what you measured (the "readout"),
   for example the MN9 firing rate, or a dictionary of several numbers, or a
   pandas Series of per-neuron firing rates.
2. A list of **variations**: "run it again with the synaptic weight 20% lower",
   "run it again with the threshold 10% higher", and so on. The first one is
   always the unchanged model (the "baseline").
3. One or more **claims**: the result written as a yes/no test on the
   readout, for example "MN9 fires at 5 Hz or more".

It re-runs the experiment for every variation and every seed, and returns:

* ``table``: one row per (variation, seed, measured number), a "tidy" table.
* ``verdicts``: one row per (claim, variation) saying **"holds"** or
  **"flips"**. The rule is written out in ``VERDICT_RULE``: a variation
  "holds" only if the claim is true for *every* seed; one failing seed is
  enough for "flips". Strict on purpose: PLAN.md says "results that flip easily
  aren't trustworthy".
* ``summary()``: average readout per variation and its % change from baseline.
* ``ranking_change()``: for per-neuron readouts, how much the ranking of the
  most active neurons changes (Spearman rank correlation and top-k overlap).

Two extra checks run automatically:

* A **new-seeds baseline** (the unchanged model with different random input)
  measures how much results move from randomness alone. A parameter effect
  smaller than that is noise, not an effect.
* An **"identical to baseline" warning**: if a variation gives exactly the same
  numbers as the baseline, the experiment probably ignored that setting (for
  example it hard-coded an input rate). That is flagged, never silently passed.

Typical use (another lane checking its own result)::

    from sim.fast_engine import FastBrain
    from sim import validation as V

    brain = FastBrain("630", n_threads=2)

    def experiment(brain, params, seed):
        res = brain.run(excite=MY_IDS, duration_ms=1000, n_trials=30,
                        seed=seed, params=params)
        return {"mn9": res.rate(MN9)}

    result = V.validate(experiment, brain,
                        claims={"MN9 on": V.at_least("mn9", 5.0)})
    print(result.verdicts)

IMPORTANT for experiments that set input rates themselves: the "Poisson input
rate" variation changes ``params["r_poi"]``. ``brain.run`` only uses that when
you pass a plain list to ``excite`` without ``rate_hz``. If you give explicit
rates (a dict, or ``rate_hz=100``), multiply them by ``rate_factor(params)``,
or the input-rate variation silently does nothing (the "identical to baseline"
warning will then fire).
"""

from __future__ import annotations

import contextlib
import functools
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from sim.fast_engine import DEFAULT_PARAMS

#: The standard one-at-a-time changes: -20%, -10%, +10%, +20%.
LEVELS = (-0.20, -0.10, 0.10, 0.20)

#: The verdict rule, stated once so every report quotes the same words.
VERDICT_RULE = ("A variation 'holds' only if the claim is true for every random seed "
                "tested; if it is false for even one seed the verdict is 'flips'. "
                "seeds_holding shows how many seeds agreed.")

#: Seed offset used for the "same model, new random input" replicate.
NEW_SEEDS_OFFSET = 1000


# ---------------------------------------------------------------------------
# Variations
# ---------------------------------------------------------------------------
@dataclass
class Variation:
    """One way of changing the model before re-running an experiment.

    name       : short unique label, e.g. "w_syn-20%".
    params     : overrides of the model constants handed to the experiment
                 (units as in ``DEFAULT_PARAMS``: mV, ms, Hz).
    parameter  : which setting is being changed ("baseline" for none).
    change     : the fractional change, e.g. -0.2 for -20%.
    context    : optional ``context(brain)`` returning a context manager that
                 changes the brain while this variation runs and yields extra
                 params (used for things a params dict cannot express, such as
                 jittering every connection's weight). It must undo itself.
    seed_offset: added to every seed (used for the new-seeds replicate).
    note       : plain-English description of what was changed.
    """
    name: str
    params: dict = field(default_factory=dict)
    parameter: str = "baseline"
    change: float = 0.0
    context: Callable | None = None
    seed_offset: int = 0
    note: str = ""


def baseline():
    """The unchanged model."""
    return Variation("baseline", note="unchanged model")


def new_seeds_baseline(offset=NEW_SEEDS_OFFSET):
    """The unchanged model with different random input: the noise floor."""
    return Variation("baseline_new_seeds", parameter="seed_noise", seed_offset=offset,
                     note=f"unchanged model, every seed + {offset} (fresh random input)")


def _scaled(key):
    def rule(base, f):
        return {key: base[key] * (1 + f)}
    return rule


def _weight_rule(base, f):
    # Change the connection weight but keep the size of each Poisson input
    # "kick" (w_syn x f_poi = 68.75 mV) fixed, so only brain-internal
    # connections change, not how hard the stimulated neurons are driven.
    w = base["w_syn"] * (1 + f)
    return {"w_syn": w, "f_poi": base["w_syn"] * base["f_poi"] / w}


def _threshold_gap_rule(base, f):
    # Change the distance from resting voltage to threshold (7 mV by default),
    # not the absolute mV value: -45 mV x 1.2 = -54 mV would put the threshold
    # BELOW rest and make every neuron fire on its own. Rest and reset stay
    # at v_0.
    gap = base["v_th"] - base["v_0"]
    return {"v_th": base["v_0"] + gap * (1 + f)}


#: What each named parameter variation changes, in plain English, and how.
PARAMETER_RULES = {
    "w_syn": ("synaptic weight per synapse (Poisson input kick held fixed)", _weight_rule),
    "threshold_gap": ("rest-to-threshold gap v_th - v_0 (rest and reset unchanged)",
                      _threshold_gap_rule),
    "t_mbr": ("membrane time constant", _scaled("t_mbr")),
    "tau": ("synaptic time constant", _scaled("tau")),
    "t_rfc": ("refractory period (rounded to whole 0.1 ms steps by the engine)",
              _scaled("t_rfc")),
    "t_dly": ("synaptic delay (rounded to whole 0.1 ms steps by the engine)",
              _scaled("t_dly")),
    "r_poi": ("Poisson input rate to the stimulated neurons", _scaled("r_poi")),
}


def one_at_a_time(parameters=None, levels=LEVELS, base=None):
    """Variations that change ONE setting at a time by each level.

    parameters : names from ``PARAMETER_RULES`` (default: all of them).
    levels     : fractional changes (default -20%, -10%, +10%, +20%).
    base       : the model constants to start from (default ``DEFAULT_PARAMS``).
    """
    base = {**DEFAULT_PARAMS, **(base or {})}
    out = []
    for name in parameters or PARAMETER_RULES:
        if name not in PARAMETER_RULES:
            raise KeyError(f"unknown parameter {name!r}; known: {sorted(PARAMETER_RULES)}")
        label, rule = PARAMETER_RULES[name]
        for f in levels:
            out.append(Variation(f"{name}{f:+.0%}", rule(base, f), name, float(f), note=label))
    return out


def rate_factor(params, base=None):
    """How much an experiment should scale its own explicit input rates:
    ``params['r_poi'] / baseline r_poi`` (1.0 when r_poi is not changed)."""
    ref = (base or DEFAULT_PARAMS)["r_poi"]
    return float(params.get("r_poi", ref)) / ref


def effective_steps(params, base=None):
    """The refractory period and delay the engine really uses, in 0.1 ms steps
    (both are rounded to whole steps, exactly as in sim/fast_engine.py)."""
    p = {**DEFAULT_PARAMS, **(base or {}), **params}
    dt = p["dt"] * 1e-3
    return {"t_rfc_steps": int((p["t_rfc"] * 1e-3 + 1e-3 * dt) / dt),
            "t_dly_steps": int(p["t_dly"] * 1e-3 / dt + 0.5)}


@contextlib.contextmanager
def jittered_weights(brain, frac=0.2, draw=0, resolution=1000):
    """Temporarily give every connection its own random weight change.

    Each connection's weight is multiplied by a random factor drawn uniformly
    between (1 - frac) and (1 + frac), e.g. 0.8 to 1.2. This models noise in
    the synapse counts the connectome is built from. ``draw`` picks the random
    pattern (same draw = same pattern).

    How: the engine stores whole-number synapse counts, and half of all
    connections have a count of 1, so rounding a jittered count back to a
    whole number would erase most of the jitter. Instead every count is
    multiplied by ``resolution`` (1000) before rounding, and the per-synapse
    weight is divided by the same number; the Poisson input kick is kept
    fixed. So jitter is applied in steps of 0.1% of one synapse.

    The brain's own connection array is swapped in place (no second copy of
    the whole brain is built) and restored when the block ends, even on error.
    Yields the params overrides the experiment must use while jittered.
    """
    original = brain._count
    rng = np.random.default_rng([int(draw), 0x5E75])
    # computed in place (one float64 array) to keep memory low on the whole brain
    scaled = rng.uniform(1.0 - frac, 1.0 + frac, original.size)
    scaled *= resolution
    scaled *= original
    np.rint(scaled, out=scaled)
    if scaled.size and max(scaled.max(), -scaled.min()) >= 2 ** 31:
        raise OverflowError("jittered counts do not fit in int32; lower `resolution`")
    base = brain.params
    try:
        brain._count = np.ascontiguousarray(scaled, dtype=np.int32)
        del scaled
        yield {"w_syn": base["w_syn"] / resolution, "f_poi": base["f_poi"] * resolution}
    finally:
        brain._count = original


def weight_jitter(frac=0.2, draws=3, resolution=1000, control=True):
    """Variations that jitter every connection's weight by up to +/- ``frac``
    (``draws`` different random patterns). With ``control=True`` a first
    variation applies the same x1000 rescaling with NO jitter; it should match
    the baseline almost exactly and proves the rescaling itself is harmless."""
    out = []
    if control:
        out.append(Variation("jitter_control", parameter="jitter_control", change=0.0,
                             context=functools.partial(jittered_weights, frac=0.0, draw=0,
                                                       resolution=resolution),
                             note="weights rescaled x1000 / w_syn / 1000, no jitter"))
    for d in range(draws):
        out.append(Variation(f"jitter{frac:.0%}_draw{d}", parameter="weight_jitter",
                             change=float(frac),
                             context=functools.partial(jittered_weights, frac=frac, draw=d,
                                                       resolution=resolution),
                             note=f"every connection weight x uniform({1 - frac:.2f}, "
                                  f"{1 + frac:.2f}), random pattern {d}"))
    return out


def standard_variations(parameters=None, levels=LEVELS, jitter_frac=0.2, jitter_draws=3,
                        base=None):
    """The full standard set: baseline, new-seeds baseline, one-at-a-time
    changes of every model constant, and weight jitter (with its control)."""
    out = [baseline(), new_seeds_baseline()]
    out += one_at_a_time(parameters, levels, base)
    if jitter_draws:
        out += weight_jitter(jitter_frac, jitter_draws)
    return out


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------
@dataclass
class Claim:
    """A result written as a yes/no test on one seed's readouts.

    text : the rule in plain words (it is copied into every report).
    test : function(readouts dict) -> True if the claim holds for that seed.
    """
    text: str
    test: Callable[[dict], bool]


def at_least(key, threshold, text=None):
    """Claim: readout ``key`` is at least ``threshold``."""
    return Claim(text or f"{key} >= {threshold:g}", lambda r: bool(r[key] >= threshold))


def at_most(key, threshold, text=None):
    """Claim: readout ``key`` is at most ``threshold``."""
    return Claim(text or f"{key} <= {threshold:g}", lambda r: bool(r[key] <= threshold))


def suppressed(test_key, control_key, max_ratio=0.5, control_min=0.0, text=None):
    """Claim: ``test_key`` is at most ``max_ratio`` x ``control_key`` (same seed),
    and the control itself is at least ``control_min`` (you cannot suppress a
    response that is not there)."""
    def test(r):
        return bool(r[control_key] >= control_min and r[test_key] <= max_ratio * r[control_key])
    return Claim(text or (f"{test_key} <= {max_ratio:g} x {control_key} "
                          f"and {control_key} >= {control_min:g}"), test)


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------
def _split_readout(out):
    """Scalar numbers go into the tidy table; Series / arrays are kept aside."""
    if not isinstance(out, dict):
        out = {"value": out}
    scalars, vectors = {}, {}
    for k, v in out.items():
        if isinstance(v, (pd.Series, np.ndarray, list, tuple)):
            vectors[k] = v if isinstance(v, pd.Series) else pd.Series(np.asarray(v))
        else:
            scalars[k] = float(v)
    return scalars, vectors


def _cache_file(cache_dir, var, seed):
    safe = re.sub(r"[^A-Za-z0-9_.+-]", "_", var.name)
    return Path(cache_dir) / f"{safe}__seed{seed}.pkl"


def run_validation(experiment, variations, seeds=(0, 1, 2), claims=None, brain=None,
                   cache_dir=None, log=print):
    """Run ``experiment(brain, params, seed)`` for every variation and seed.

    variations : list of ``Variation`` (the first one named "baseline" is the
                 reference for % changes; add one if missing).
    seeds      : seeds to run each variation with (the seed chooses the random
                 input; the same seed gives the same input in every variation
                 unless the input rate itself is changed).
    claims     : {name: Claim}; a verdict is given for each.
    brain      : handed to the experiment, and to variation contexts.
    cache_dir  : if given, each (variation, seed) readout is saved there as it
                 finishes, and a re-run skips work already on disk (so a long
                 sweep can be stopped and resumed). A cached file is reused
                 only if its params match the variation's current params.
    log        : function taking one progress line (``None`` for silence).

    Returns a ``ValidationResult``.
    """
    variations = list(variations)
    if not any(v.name == "baseline" for v in variations):
        variations.insert(0, baseline())
    names = [v.name for v in variations]
    if len(set(names)) != len(names):
        raise ValueError("variation names must be unique")
    seeds = [int(s) for s in seeds]
    if cache_dir is not None:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
    rows, vectors = [], {}
    t_start = time.perf_counter()
    for i, var in enumerate(variations):
        results = {}
        todo = []
        for s in seeds:
            f = _cache_file(cache_dir, var, s) if cache_dir is not None else None
            if f is not None and f.exists():
                saved = pd.read_pickle(f)
                if saved.get("params") == repr(sorted(var.params.items())):
                    results[s] = (saved["scalars"], saved["vectors"])
                    continue
            todo.append(s)
        if todo:
            ctx = var.context(brain) if var.context else contextlib.nullcontext({})
            with ctx as extra:
                params = {**var.params, **(extra or {})}
                for s in todo:
                    t0 = time.perf_counter()
                    scalars, vecs = _split_readout(experiment(brain, params, s + var.seed_offset))
                    results[s] = (scalars, vecs)
                    if cache_dir is not None:
                        pd.to_pickle({"variation": var.name, "seed": s,
                                      "params": repr(sorted(var.params.items())),
                                      "scalars": scalars, "vectors": vecs},
                                     _cache_file(cache_dir, var, s))
                    if log:
                        short = ", ".join(f"{k}={v:.3g}" for k, v in list(scalars.items())[:4])
                        log(f"[{i + 1}/{len(variations)}] {var.name} seed {s + var.seed_offset}: "
                            f"{short} ({time.perf_counter() - t0:.1f} s, "
                            f"total {time.perf_counter() - t_start:.0f} s)")
        for s in seeds:
            scalars, vecs = results[s]
            for k, v in scalars.items():
                rows.append({"variation": var.name, "parameter": var.parameter,
                             "change": var.change, "seed": s + var.seed_offset,
                             "readout": k, "value": v})
            for k, v in vecs.items():
                vectors[(var.name, s + var.seed_offset, k)] = v
    table = pd.DataFrame(rows, columns=["variation", "parameter", "change", "seed",
                                        "readout", "value"])
    return ValidationResult(table=table, vectors=vectors, variations=variations,
                            claims=dict(claims or {}))


def validate(experiment, brain, claims, seeds=(0, 1, 2), parameters=None, levels=LEVELS,
             jitter_frac=0.2, jitter_draws=3, cache_dir=None, log=print):
    """One call for the standard Phase 6 step-1 check: baseline, new-seeds
    baseline, every model constant at -20/-10/+10/+20%, and weight jitter."""
    return run_validation(experiment,
                          standard_variations(parameters, levels, jitter_frac, jitter_draws),
                          seeds=seeds, claims=claims, brain=brain, cache_dir=cache_dir, log=log)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
def spearman(a, b):
    """Spearman rank correlation of two equal-length sequences (ties get their
    average rank). NaN if either side is constant."""
    ra = pd.Series(np.asarray(a, float)).rank()
    rb = pd.Series(np.asarray(b, float)).rank()
    if ra.nunique() < 2 or rb.nunique() < 2:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def top_k_change(base, other, k=50, exclude=()):
    """How the top-``k`` most active neurons change between two rate Series
    (indexed by neuron ID). Returns (spearman, overlap):

    spearman : rank correlation of the baseline's top-k neurons' rates in
               ``base`` vs ``other`` (1 = same order, 0 = unrelated).
    overlap  : fraction of the baseline's top-k that are still in the other
               run's top-k.
    ``exclude`` removes neurons (e.g. the stimulated ones) before ranking.
    """
    base = base.drop(list(exclude), errors="ignore")
    other = other.drop(list(exclude), errors="ignore")
    top = base.sort_values(ascending=False, kind="stable").index[:k]
    other_top = other.sort_values(ascending=False, kind="stable").index[:k]
    rho = spearman(base.reindex(top).fillna(0.0), other.reindex(top).fillna(0.0))
    overlap = len(set(top) & set(other_top)) / max(len(top), 1)
    return rho, overlap


@dataclass
class ValidationResult:
    """Everything ``run_validation`` produced (see the module docstring)."""
    table: pd.DataFrame
    vectors: dict
    variations: list
    claims: dict

    def _meta(self):
        return pd.DataFrame([{"variation": v.name, "parameter": v.parameter,
                              "change": v.change, "note": v.note} for v in self.variations])

    def _wide(self, name):
        t = self.table[self.table["variation"] == name]
        return t.pivot(index="seed", columns="readout", values="value")

    def _identical_to_baseline(self, name):
        if name == "baseline":
            return False
        a, b = self._wide("baseline"), self._wide(name)
        if a.shape != b.shape or not np.array_equal(a.index, b.index):
            return False
        return bool(np.array_equal(a.to_numpy(), b[a.columns].to_numpy(), equal_nan=True))

    @property
    def verdicts(self):
        """One row per (claim, variation): seeds_holding, verdict, and a
        warning flag if the variation's numbers equal the baseline's exactly."""
        rows = []
        for cname, claim in self.claims.items():
            for v in self.variations:
                wide = self._wide(v.name)
                ok = [bool(claim.test(r)) for _, r in wide.iterrows()]
                rows.append({"claim": cname, "variation": v.name, "parameter": v.parameter,
                             "change": v.change, "seeds_holding": int(sum(ok)),
                             "n_seeds": len(ok),
                             "verdict": "holds" if ok and all(ok) else "flips",
                             "identical_to_baseline": self._identical_to_baseline(v.name),
                             "rule": claim.text})
        return pd.DataFrame(rows)

    def robust(self, claim):
        """True if ``claim`` holds in every variation (the plan's standard)."""
        v = self.verdicts
        return bool((v[v["claim"] == claim]["verdict"] == "holds").all())

    def summary(self, readout):
        """Per variation: mean and sd over seeds, and % change from baseline."""
        t = self.table[self.table["readout"] == readout]
        g = t.groupby("variation", sort=False)["value"]
        s = pd.DataFrame({"mean": g.mean(), "sd_over_seeds": g.std(ddof=1)})
        base = s.loc["baseline", "mean"]
        s["change_pct"] = 100.0 * (s["mean"] - base) / base if base != 0 else np.nan
        return self._meta().set_index("variation").join(s, how="right")

    def pooled_vector(self, variation, key):
        """Mean over seeds of a per-neuron readout (missing neurons count as 0)."""
        parts = [v for (n, _, k), v in self.vectors.items() if n == variation and k == key]
        if not parts:
            raise KeyError(f"no vector readout {key!r} for variation {variation!r}")
        return pd.concat(parts, axis=1).fillna(0.0).mean(axis=1)

    def ranking_change(self, key, k=50, exclude=()):
        """Per variation: Spearman rank correlation and top-k overlap of the
        seed-pooled per-neuron readout ``key`` against the baseline's top k."""
        base = self.pooled_vector("baseline", key)
        rows = []
        for v in self.variations:
            rho, ov = top_k_change(base, self.pooled_vector(v.name, key), k, exclude)
            rows.append({"variation": v.name, "parameter": v.parameter, "change": v.change,
                         "spearman_top%d" % k: rho, "overlap_top%d" % k: ov})
        return pd.DataFrame(rows)
