"""The ONE place where the explorer app talks to the simulator (sim/).

Plain English: the app never reaches into the simulator directly. It asks this
file. This file looks for the real fly brain simulator and the real neuron
list. If the engine cannot be loaded, runs are switched off and the web page
shows a banner, which cannot be closed, saying why. The app never makes up
results in its place. The small STAND-IN ("fake") engine below is only a test
double for the automated tests (FLYBRAIN_APP_FAKE=1); when it is on, every
status and result is flagged and the banner says "Not the fly brain model".

Two FlyWire "snapshots" (releases of the brain map) are supported, because
neuron ids change between releases:
  630  the release the Shiu et al. 2024 paper used; Phase 3 uses it, so it is
       the app's default and the ready-made sugar setup uses it.
  783  the newer public release (current cell type labels are made for it).
Every run and every saved setup records which snapshot it used.

How the real modules are wired in (checked 2026-09-22):
  sim/fast_engine.py   FastBrain(snapshot, n_threads) is built once per
                       snapshot, then .run(excite, silence, duration_ms,
                       n_trials, seed, rate_hz) -> SimResult (spikes as
                       trial / neuron row / time step arrays; rate_stats()
                       gives mean and spread). See FastBrainEngine.
  sim/shiu_model.py    run_trials(excite_ids, silence_ids, duration_ms,
                       n_trials, rate_hz, seed, dataset) -> TrialResult. The
                       slow Brian2 port, used only if the fast engine
                       cannot be imported (the banner says so). See ShiuModelEngine.
  sim/connectome.py    load_connectome(snapshot).neurons -> the neuron list
                       (root_id, cell_type, hemibrain_type, super_class,
                       cell_class, top_nt, side; row order = simulator order).
If one of these cannot be loaded, the banner names what is missing and why,
and runs are switched off (or the slow engine is used, and labelled).

Model variants (added 2026-09-23). Besides the published model, a run can use
a VALIDATED variant (snapshot 630 only):
  sim/sign_fixes.py    build_brain(fix=..., snapshot="630", n_threads) -> a
                       FastBrain with a neurotransmitter-sign fix applied.
                       Only the fixes listed in FIX_CHOICES are offered (the
                       recommended "al_ln_literature"); other names in
                       sign_fixes.FIXES are not exposed.
  sim/realism.py       RealisticBrain("630", n_threads, realism={"delays":
                       bool, "adaptation": bool}) -> upgrades 1 and 3.
                       Upgrade 2 (conductance) is NOT validated and not offered.
  sim/celltype_params.py  CellTypeBrain("630", n_threads) -> measured
                       cell-type settings (on its own only).
Each variant's brain is built on first use and kept; at most
MAX_BRAINS_IN_MEMORY brains are kept at once (least recently used is dropped).
A variant that cannot be built is reported (run error, banner, model panel);
the app never runs a different model in its place.

FLYBRAIN_APP_FAKE=1 forces the stand-in engine and stand-in neuron list (the
fast automated tests use it; nothing else ever falls back to it).
FLYBRAIN_APP_THREADS=n lets the fast engine run n trials at once (default 1,
because the computer is shared).
"""
from __future__ import annotations

import gc
import hashlib
import importlib
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FORCE_FAKE_ENV = "FLYBRAIN_APP_FAKE"
THREADS_ENV = "FLYBRAIN_APP_THREADS"

SNAPSHOTS = ("630", "783")
DEFAULT_SNAPSHOT = "630"
_ANNOTATION_FILES = {  # only used if sim/connectome.py cannot give a neuron list
    "783": ROOT / "data" / "flywire" / "Supplemental_file1_neuron_annotations.tsv",
    "630": ROOT / "data" / "flywire" / "Supplemental_file1_annotations_v1.1.0_630.tsv",
}

FAKE_ENGINE_NAME = "stand-in (fake) engine"
FAKE_ENGINE_VERSION = "app-fake-1"

# The 21 right-side sugar-sensing taste neurons (labellar sugar GRNs) and the
# feeding motor neuron MN9, from data/reference/example.ipynb / figures.ipynb.
# In snapshot 783 one sugar neuron and MN9-right have new ids (ID_630_TO_783 in
# sim/shiu_model.py). The stand-in list includes both versions so the sugar
# setup can at least be loaded and exercised when the app is faked.
SUGAR_GRN_IDS_630 = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
SUGAR_GRN_IDS_783 = [720575940639259967 if i == 720575940620900446 else i for i in SUGAR_GRN_IDS_630]
MN9_LEFT_ID = 720575940660219265          # "MN9 left" in figures.ipynb (same id in 630 and 783)
MN9_RIGHT_IDS = {"630": 720575940645521262, "783": 720575940618238523}
# Bitter taste neurons (sim/shiu_model.py BITTER_R_630, the paper's Fig. 3A list).
BITTER_GRN_IDS_630 = [
    720575940621778381, 720575940602353632, 720575940617094208, 720575940619197093, 720575940626287336,
    720575940618600651, 720575940627692048, 720575940630195909, 720575940646212996, 720575940610483162,
    720575940645743412, 720575940627578156, 720575940622298631, 720575940621008895, 720575940629146711,
    720575940610259370, 720575940610481370, 720575940619028208, 720575940614281266, 720575940613061118,
    720575940604027168,
]
# DA1 (cVA pheromone) smell neurons of the LEFT antenna in snapshot 630: cell_class
# "olfactory", hemibrain_type "ORN_DA1", side "left", in model row order (the
# selection of experiments/phase6/steering/s2_simulate.py).
DA1_LEFT_ORN_IDS_630 = [
    720575940606165606, 720575940606227890, 720575940606922674, 720575940607090306, 720575940608044501,
    720575940612443827, 720575940614569414, 720575940614586690, 720575940614982654, 720575940615708466,
    720575940616526292, 720575940617486081, 720575940618080566, 720575940619498887, 720575940619591872,
    720575940619873472, 720575940620101614, 720575940620687425, 720575940621368685, 720575940622198664,
    720575940622712810, 720575940623080132, 720575940623122685, 720575940623137930, 720575940623358954,
    720575940623747086, 720575940623927956, 720575940626269468, 720575940626585481, 720575940626606223,
    720575940627048018, 720575940627777265, 720575940628251947, 720575940628314217, 720575940629266767,
    720575940629336770, 720575940629471682, 720575940629847678, 720575940630062587, 720575940630368965,
    720575940630428227, 720575940630442745, 720575940630461994, 720575940631012664, 720575940631229800,
    720575940632679379, 720575940632765388, 720575940634538080, 720575940634702431, 720575940635708267,
    720575940636165743, 720575940638216420, 720575940638807485, 720575940644191012, 720575940644530030,
    720575940644683031, 720575940646583172, 720575940654436769, 720575940658814849, 720575940659996033,
]
# Steering descending neurons (docs/phase6-steering.md), snapshot 630: (name, left id, right id).
STEERING_DN_IDS_630 = [("DNa02", 720575940629327659, 720575940604737708),
                       ("DNpe002", 720575940629428215, 720575940620642940),
                       ("DNb05", 720575940620266689, 720575940629461442)]

TABLE_COLUMNS = ["root_id", "cell_type", "name", "super_class", "cell_class", "nt", "side"]
_COLUMN_CANDIDATES = {
    "cell_type": ["cell_type", "celltype", "type", "primary_type"],
    "name": ["name", "hemibrain_type", "label", "synonyms"],
    "super_class": ["super_class", "superclass"],
    "cell_class": ["cell_class", "class"],
    "nt": ["neurotransmitter", "nt", "top_nt", "nt_type", "predicted_nt"],
    "side": ["side", "hemisphere"],
}


class EngineError(RuntimeError):
    """Raised when the engine cannot run or returns something we cannot read."""


@dataclass
class RunResult:
    """One finished run, in the app's own format (independent of the engine)."""
    trials: list[dict[int, np.ndarray]]      # per trial: root_id -> spike times (ms)
    rates_hz: dict[int, float]               # mean rate over trials; missing = 0 Hz
    rate_sd_hz: dict[int, float]             # spread of the rate across trials
    duration_ms: float
    n_trials: int
    engine: dict[str, Any]
    snapshot: str = DEFAULT_SNAPSHOT
    wall_seconds: float = 0.0
    notes: list[str] = field(default_factory=list)
    variant: dict[str, Any] = field(default_factory=dict)      # variant_record(): model + code fingerprints
    stim_groups: list[dict[str, Any]] = field(default_factory=list)  # [{name, rate_hz, ids}]


def check_snapshot(s) -> str:
    s = str(s).strip()
    if s not in SNAPSHOTS:
        raise ValueError(f"snapshot must be one of {', '.join(SNAPSHOTS)} (got {s!r})")
    return s


def _file_hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return None


# --------------------------------------------------------------------------
# Model variants
# --------------------------------------------------------------------------
# Only VALIDATED variants are offered. Each has a one-line plain-English
# description and its doc (served by the app at /api/docs/<file>).
PUBLISHED_VARIANT = {"fix": "none", "upgrades": []}
MAX_BRAINS_IN_MEMORY = 2
VARIANT_SNAPSHOT = "630"          # every variant is defined for snapshot 630 only
# The model the page opens on (Owen, 2026-09-23): the recommended fix, i.e.
# sim.sign_fixes.RECOMMENDED_FIX (tests/test_app.py checks the two agree). Where
# it cannot be used, the page opens on the published model and says why
# (EngineAdapter.default_variant). A run request or saved setup WITHOUT a model
# is still the published model: that is how older setups were saved.
DEFAULT_FIX = "al_ln_literature"

FIX_CHOICES = {
    "none": {
        "label": "Published model (Shiu et al. 2024)",
        "short": "Published model",
        "about": "The paper's model exactly as published, the one Phase 3 checked. Use it to compare with the paper.",
        "doc": "phase3-explained.md",
    },
    "al_ln_literature": {
        "label": "Recommended neurotransmitter fix (default)",
        "short": "Recommended neurotransmitter fix",
        "about": ("Corrects about 150 smell-centre (antennal lobe) local neurons to match published "
                  "recordings. Stops the non-stop 'runaway' firing after strong smell input; taste "
                  "results stay identical to the published model."),
        "doc": "phase7-neurotransmitter-audit.md",
    },
}
UPGRADE_CHOICES = {
    "delays": {
        "label": "Distance-based delays",
        "short": "distance delays",
        "about": ("Each spike also needs travel time along the wire (distance / 0.2 m/s) on top of the "
                  "fixed 1.8 ms synapse delay. Changes very little. Preliminary."),
        "doc": "phase7-realism.md",
    },
    "adaptation": {
        "label": "Adaptation",
        "short": "adaptation",
        "about": ("Neurons driven for a long time slow down (a brake that fades over about 100 ms). "
                  "Every response gets weaker: sugar 100 Hz gives MN9 about 44 Hz instead of 67. Preliminary."),
        "doc": "phase7-realism.md",
    },
    "celltype": {
        "label": "Measured cell-type settings",
        "short": "cell-type settings",
        "about": ("The few cell types measured with electrodes (Kenyon cells, projection neurons, P-EN, "
                  "clock neurons; 4% of neurons) get their measured settings. No effect on taste. Preliminary."),
        "doc": "phase7-celltype-params.md",
    },
}
UPGRADE_ORDER = tuple(UPGRADE_CHOICES)
# Docs the page may link to (served as plain text by /api/docs/<file>).
DOCS_DIR = ROOT / "docs"
SERVED_DOCS = sorted({c["doc"] for c in (*FIX_CHOICES.values(), *UPGRADE_CHOICES.values())}
                     | {"phase4-app-explained.md", "phase5-competition.md", "phase6-steering.md"})

# Which files make up each piece of a variant (their fingerprints are recorded).
_CODE_FILES = {
    "base": ["sim/fast_engine.py"],
    "fix": ["sim/sign_fixes.py"],
    "delays": ["sim/realism.py"],
    "adaptation": ["sim/realism.py"],
    "celltype": ["sim/celltype_params.py", "experiments/phase7_celltype/celltype_params.csv"],
}


def combination_problem(fix: str, upgrades: list[str], snapshot: str = DEFAULT_SNAPSHOT) -> str | None:
    """Why this combination is not offered (plain English), or None if it is."""
    if (fix != "none" or upgrades) and snapshot != VARIANT_SNAPSHOT:
        return (f"Model variants exist for the {VARIANT_SNAPSHOT} brain map only (the fixes and "
                "upgrades were built and checked on it). Switch the brain map to 630, or use the "
                "published model.")
    if "celltype" in upgrades and (fix != "none" or len(upgrades) > 1):
        return ("Measured cell-type settings can only be used on their own, with the published "
                "model: the simulator has no version that combines them with other changes, and "
                "the combination was never tested (docs/phase7-celltype-params.md).")
    if fix != "none" and upgrades:
        return ("Delays and adaptation were checked on the published model only. Together with the "
                "neurotransmitter fix they were never tested, so the app does not offer that yet.")
    return None


def check_variant(v, snapshot: str = DEFAULT_SNAPSHOT) -> dict[str, Any]:
    """Tidy a model choice into {"fix", "upgrades"}; ValueError says why it is refused.

    Missing (None or {}) means the published model, which is how setups saved
    before variants existed are read."""
    if v in (None, "", {}):
        return {"fix": "none", "upgrades": []}
    if not isinstance(v, dict):
        raise ValueError("'variant' must be an object like {\"fix\": \"none\", \"upgrades\": []}")
    fix = str(v.get("fix") or "none").strip()
    if fix not in FIX_CHOICES:
        raise ValueError(f"unknown model '{fix}'. The app offers: "
                         + ", ".join(f"'{k}' ({c['label']})" for k, c in FIX_CHOICES.items()))
    ups = v.get("upgrades") or []
    if not isinstance(ups, (list, tuple)):
        raise ValueError("'upgrades' must be a list, e.g. [\"adaptation\"]")
    bad = [str(u) for u in ups if str(u) not in UPGRADE_CHOICES]
    if bad:
        raise ValueError(f"unknown upgrade(s) {', '.join(bad)}. The app offers: "
                         + ", ".join(UPGRADE_ORDER) + " (conductance-based synapses are not validated)")
    ups = [u for u in UPGRADE_ORDER if u in {str(x) for x in ups}]
    problem = combination_problem(fix, ups, check_snapshot(snapshot))
    if problem:
        raise ValueError(problem)
    return {"fix": fix, "upgrades": ups}


def is_published(v: dict[str, Any]) -> bool:
    return v.get("fix", "none") == "none" and not v.get("upgrades")


def variant_key(v: dict[str, Any]) -> str:
    return "published" if is_published(v) else "+".join([v["fix"], *v["upgrades"]])


def variant_label(v: dict[str, Any]) -> str:
    base = FIX_CHOICES[v["fix"]]["short"]
    ups = [UPGRADE_CHOICES[u]["short"] for u in v.get("upgrades", [])]
    return base + (" + " + " + ".join(ups) if ups else "")


def variant_record(v: dict[str, Any]) -> dict[str, Any]:
    """Everything needed to say exactly which model ran: names, switches and
    the fingerprint (first 12 characters of the SHA-256) of every file it used."""
    files = list(_CODE_FILES["base"])
    if v["fix"] != "none":
        files += _CODE_FILES["fix"]
    for u in v["upgrades"]:
        files += [f for f in _CODE_FILES[u] if f not in files]
    return {"fix": v["fix"], "upgrades": list(v["upgrades"]), "key": variant_key(v),
            "label": variant_label(v), "code": {f: _file_hash(ROOT / f) for f in files}}


def _to_int_ids(ids) -> list[int]:
    out = []
    for i in ids or []:
        if isinstance(i, (int, np.integer)):
            out.append(int(i))
        else:
            s = str(i).strip()
            if not s.isdigit():
                raise ValueError(f"'{i}' is not a FlyWire root id (digits only)")
            out.append(int(s))
    return out


def _app_threads() -> int:
    try:
        return max(1, min(8, int(os.environ.get(THREADS_ENV, "1"))))
    except ValueError:
        return 1


# --------------------------------------------------------------------------
# Stand-in neuron list and engine
# --------------------------------------------------------------------------

def _fake_table() -> pd.DataFrame:
    """A tiny made-up neuron list. Only the sugar and MN9 ids are real ids."""
    rows = []
    for ids in (SUGAR_GRN_IDS_630, SUGAR_GRN_IDS_783):
        for i, rid in enumerate(ids):
            rows.append((rid, "FAKE-sugarGRN", f"sugar_{i + 1}", "sensory", "gustatory",
                         "acetylcholine", "right"))
    for rid in (MN9_LEFT_ID, *MN9_RIGHT_IDS.values()):
        rows.append((rid, "FAKE-MN9", "MN9", "motor", "brain_motor_neuron", "acetylcholine", ""))
    # So the other ready-made setups can be loaded and exercised with the stand-in too.
    for i, rid in enumerate(BITTER_GRN_IDS_630):
        rows.append((rid, "FAKE-bitterGRN", f"bitter_{i + 1}", "sensory", "gustatory", "acetylcholine", "right"))
    for i, rid in enumerate(DA1_LEFT_ORN_IDS_630):
        rows.append((rid, "FAKE-ORN_DA1", f"orn_da1_{i + 1}", "sensory", "olfactory", "acetylcholine", "left"))
    for name, left, right in STEERING_DN_IDS_630:
        rows.append((left, f"FAKE-{name}", name, "descending", "", "acetylcholine", "left"))
        rows.append((right, f"FAKE-{name}", name, "descending", "", "acetylcholine", "right"))
    kinds = [("FAKE-interA", "central", "acetylcholine"), ("FAKE-interB", "central", "gaba"),
             ("FAKE-interC", "central", "glutamate"), ("FAKE-descend", "descending", "acetylcholine"),
             ("FAKE-motor", "motor", "acetylcholine")]
    for k in range(60):
        ct, sc, nt = kinds[k % len(kinds)]
        rows.append((900000000000000000 + k, ct, f"{ct.lower()}_{k}", sc, "", nt,
                     "left" if k % 2 else "right"))
    return pd.DataFrame(rows, columns=TABLE_COLUMNS).drop_duplicates("root_id").reset_index(drop=True)


class FakeEngine:
    """Stand-in engine. Produces made-up spikes with the right SHAPE only.

    Stimulated neurons fire random (Poisson) spikes at the input rate. A fixed
    handful of other neurons ("pretend downstream") fire at lower rates. There
    is no wiring, no physics and no biology here. Never read meaning into it.
    """

    def __init__(self, all_ids: list[int], seconds_per_trial: float = 0.02, variant_key: str = "published"):
        self._ids = np.array(sorted(all_ids), dtype=np.int64)
        self._pause = seconds_per_trial
        self.variant_key = variant_key

    def run(self, excite, silence, duration_ms, n_trials, seed, rate_hz, progress=None):
        silence_set = set(silence)
        # excite: a list (all at rate_hz) or {root_id: rate}, like FastBrain.run.
        per = dict(excite) if isinstance(excite, dict) else {e: rate_hz for e in excite}
        rates: dict[int, float] = {e: float(r) for e, r in per.items() if e not in silence_set}
        exc = list(rates)
        drive = float(np.mean(list(rates.values()))) if rates else 0.0
        if exc:
            # Same stimulated set (and model variant) -> same pretend-downstream neurons.
            tag = ",".join(map(str, sorted(exc))) + ("" if self.variant_key == "published"
                                                     else "|" + self.variant_key)
            key = int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)
            pool = np.array([i for i in self._ids if i not in rates and i not in silence_set])
            if len(pool):
                pick = np.random.default_rng(key).choice(pool, size=min(25, len(pool)), replace=False)
                for rank, rid in enumerate(pick):
                    rates[int(rid)] = drive * 0.5 * (0.85 ** rank)
        rng = np.random.default_rng(seed)
        trials = []
        for t in range(n_trials):
            spikes = {}
            for rid, r in rates.items():
                n = rng.poisson(r * duration_ms / 1000.0)
                if n:
                    spikes[rid] = np.sort(rng.uniform(0, duration_ms, n))
            trials.append(spikes)
            if self._pause:
                time.sleep(self._pause)
            if progress:
                progress((t + 1) / n_trials)
        return {"spikes": trials}


# --------------------------------------------------------------------------
# The real modules
# --------------------------------------------------------------------------

def _import(modname: str):
    """Import sim.<modname>; return (module, None) or (None, reason)."""
    path = ROOT / "sim" / f"{modname}.py"
    if not path.exists():
        return None, f"sim/{modname}.py does not exist yet"
    try:
        return importlib.import_module(f"sim.{modname}"), None
    except Exception as exc:  # noqa: BLE001 - we report every failure
        return None, f"sim/{modname}.py exists but failed to import: {type(exc).__name__}: {exc}"


def _normalise_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "root_id" not in df.columns:
        if df.index.name in ("root_id", "id") or np.issubdtype(df.index.dtype, np.integer):
            df = df.reset_index().rename(columns={df.index.name or "index": "root_id"})
        else:
            raise ValueError("neuron table has no root_id column or integer index")
    out = pd.DataFrame({"root_id": pd.to_numeric(df["root_id"]).astype("int64")})
    for col, cands in _COLUMN_CANDIDATES.items():
        src = next((c for c in cands if c in df.columns), None)
        out[col] = df[src].astype("string").fillna("") if src else ""
    out["nt"] = out["nt"].str.lower()
    return out[TABLE_COLUMNS].drop_duplicates("root_id").reset_index(drop=True)


class ShiuModelEngine:
    """Wraps sim/shiu_model.py (the slow, faithful Brian2 port of the paper's code).

    run_trials() seeds trial k with seed + k and returns spikes in the
    reference format (t in SECONDS, trial, flywire_id) plus mean rate and
    population standard deviation per neuron. It keeps the wiring in memory.
    """

    def __init__(self, mod, snapshot: str):
        self._mod, self.snapshot = mod, snapshot

    def run(self, excite, silence, duration_ms, n_trials, seed, rate_hz, progress=None):
        extra = {}
        if isinstance(excite, dict):
            # The Brian2 port has exactly two input rates (the paper's r_poi / r_poi2).
            by_rate: dict[float, list[int]] = {}
            for rid, r in excite.items():
                by_rate.setdefault(float(r), []).append(rid)
            if len(by_rate) > 2:
                raise EngineError("the slow engine (sim/shiu_model.py) supports at most two different "
                                  f"input rates in one run; this run has {len(by_rate)}")
            (rate_hz, excite), *rest = by_rate.items()
            if rest:
                extra = {"rate2_hz": rest[0][0], "excite2_ids": rest[0][1]}
        out = self._mod.run_trials(excite_ids=excite, silence_ids=silence, duration_ms=duration_ms,
                                   n_trials=n_trials, rate_hz=rate_hz, seed=seed,
                                   dataset=self.snapshot, **extra)
        spikes = out.spikes.rename(columns={"t": "t_s", "flywire_id": "root_id"})
        return {"spikes": spikes, "rates": out.rates, "rate_sd": out.rate_std}


class FastBrainEngine:
    """Wraps sim/fast_engine.py's FastBrain, or a brain built by one of the
    variant builders (same run() interface; built once, run many times)."""

    def __init__(self, mod, snapshot: str, n_threads: int = 1, brain=None):
        self.brain = brain if brain is not None else mod.FastBrain(snapshot=snapshot, n_threads=n_threads)
        self.snapshot = snapshot

    def run(self, excite, silence, duration_ms, n_trials, seed, rate_hz, progress=None):
        # excite is a list (every neuron at rate_hz, exactly as before variants
        # existed) or {root_id: rate} for per-group rates (FastBrain.run's own
        # form for the reference's second input rate).
        res = self.brain.run(excite=excite, silence=silence, duration_ms=duration_ms,
                             n_trials=n_trials, seed=seed,
                             rate_hz=None if isinstance(excite, dict) else rate_hz)
        spikes = pd.DataFrame({"trial": res.trial, "root_id": res.root_ids[res.neuron],
                               "t_ms": res.time_ms})
        # Mean rates from the engine's own SimResult.rates() (the same numbers a
        # script calling the engine directly gets); the spread from rate_stats().
        return {"spikes": spikes, "rates": res.rates(), "rate_sd": res.rate_stats()["std_hz"]}


def _get(obj, *names):
    for n in names:
        if isinstance(obj, dict) and n in obj:
            return obj[n]
        if not isinstance(obj, dict) and hasattr(obj, n):
            return getattr(obj, n)
    return None


def _normalise_result(raw, n_trials: int, duration_ms: float):
    """Turn what an engine returned into (trials, rates, sd, notes).

    Accepted spike shapes:
      * list (one per trial) of {root_id: array of spike times in ms}
      * pandas DataFrame with a trial column, a root_id/flywire_id column and
        a time column: t_ms / time_ms are milliseconds; t / time / t_s /
        time_s are SECONDS (the reference repo's spike files use 't' in s)
    Rates: {root_id: Hz} or a pandas Series indexed by root_id; if missing
    they are computed from the spikes. The spread across trials is the
    engine's own if given (rate_sd), else the population standard deviation
    (ddof=0, as in the reference utils.get_rate).
    """
    notes = []
    spikes = _get(raw, "spikes")
    rates = _get(raw, "rates")
    rate_sd = _get(raw, "rate_sd")

    trials: list[dict[int, np.ndarray]] = [dict() for _ in range(n_trials)]
    if isinstance(spikes, pd.DataFrame):
        df = spikes
        tcol = next((c for c in ("trial", "trial_idx", "run") if c in df.columns), None)
        ncol = next((c for c in ("root_id", "flywire_id", "neuron") if c in df.columns), None)
        xcol = next((c for c in ("t_ms", "time_ms", "t_s", "time_s", "t", "time") if c in df.columns), None)
        if ncol is None or xcol is None:
            raise EngineError(f"spike table columns not understood: {list(df.columns)}")
        scale = 1.0 if xcol in ("t_ms", "time_ms") else 1000.0
        tr_arr = df[tcol].to_numpy(dtype=np.int64) if tcol else np.zeros(len(df), dtype=np.int64)
        id_arr = df[ncol].to_numpy(dtype=np.int64)
        t_arr = df[xcol].to_numpy(dtype=float) * scale
        if len(t_arr) and (t_arr.max() > duration_ms + 1.0 or t_arr.min() < 0):
            raise EngineError(f"spike times run from {t_arr.min():.3f} to {t_arr.max():.3f} ms, outside "
                              f"the {duration_ms:g} ms run; the time unit of column '{xcol}' is wrong")
        if len(tr_arr) and tr_arr.max() >= n_trials:
            raise EngineError(f"engine returned trial number {tr_arr.max()} but only {n_trials} were run")
        order = np.lexsort((t_arr, id_arr, tr_arr))
        tr_arr, id_arr, t_arr = tr_arr[order], id_arr[order], t_arr[order]
        if len(order):
            cut = np.flatnonzero((np.diff(tr_arr) != 0) | (np.diff(id_arr) != 0)) + 1
            starts, ends = np.concatenate(([0], cut)), np.concatenate((cut, [len(order)]))
            for s, e in zip(starts, ends):
                trials[int(tr_arr[s])][int(id_arr[s])] = t_arr[s:e]
    elif isinstance(spikes, (list, tuple)):
        if len(spikes) != n_trials:
            notes.append(f"engine returned {len(spikes)} trials, {n_trials} were requested")
            trials = [dict() for _ in range(len(spikes))]
        for t, tr in enumerate(spikes):
            if not isinstance(tr, dict):
                raise EngineError(f"trial {t} spikes are {type(tr).__name__}, expected a dict")
            trials[t] = {int(k): np.sort(np.asarray(v, dtype=float)) for k, v in tr.items() if len(v)}
    else:
        raise EngineError(f"engine spikes are {type(spikes).__name__}; expected list of dicts or DataFrame")

    n = max(len(trials), 1)
    counts: dict[int, np.ndarray] = {}
    for t, tr in enumerate(trials):
        for rid, ts in tr.items():
            counts.setdefault(rid, np.zeros(n))[t] = len(ts)
    per_trial_hz = {rid: c / (duration_ms / 1000.0) for rid, c in counts.items()}
    sd = {rid: float(v.std()) for rid, v in per_trial_hz.items()}
    if isinstance(rate_sd, (pd.Series, dict)):
        sd = {int(k): float(v) for k, v in rate_sd.items()}
    if rates is None:
        out_rates = {rid: float(v.mean()) for rid, v in per_trial_hz.items()}
        notes.append("rates computed by the app from the spikes (engine returned none)")
    elif isinstance(rates, (pd.Series, dict)):
        out_rates = {int(k): float(v) for k, v in rates.items() if v}
    else:
        raise EngineError(f"engine rates are {type(rates).__name__}; expected a dict or Series")
    return trials, out_rates, sd, notes


# --------------------------------------------------------------------------
# The adapter
# --------------------------------------------------------------------------

@dataclass
class _Table:
    df: pd.DataFrame
    info: dict[str, Any]

    def __post_init__(self):
        self.by_id = self.df.set_index("root_id")
        self.id_str = self.df["root_id"].astype(str)


class EngineAdapter:
    """Finds the engine and neuron lists once, then serves the app."""

    def __init__(self, force_fake: bool | None = None, fake_seconds_per_trial: float = 0.02):
        if force_fake is None:
            force_fake = os.environ.get(FORCE_FAKE_ENV, "") not in ("", "0", "false")
        self.force_fake = force_fake
        self._fake_pause = fake_seconds_per_trial
        self._lock = threading.RLock()        # neuron lists
        self._build_lock = threading.RLock()  # building / dropping brains
        self._tables: dict[str, _Table] = {}
        # Built brains, keyed (snapshot, variant key), least recently used first.
        self._engines: OrderedDict[tuple[str, str], Any] = OrderedDict()
        self._engine_errors: dict[tuple[str, str], str] = {}
        self._build_seconds: dict[tuple[str, str], float] = {}
        self._building: dict[str, Any] | None = None
        self._dropped: list[str] = []         # plain-English log of brains dropped to save memory
        self._probe_modules()
        self._probe_variants()
        self.table(DEFAULT_SNAPSHOT)          # load the default neuron list now

    # ---- discovery -------------------------------------------------------
    def _probe_modules(self):
        why_fake = f"forced by the {FORCE_FAKE_ENV}=1 setting (used by automated tests)"
        self._conn_mod, self._conn_reason = (None, why_fake) if self.force_fake else _import("connectome")
        if self._conn_mod is not None and not callable(getattr(self._conn_mod, "load_connectome", None)):
            self._conn_mod, self._conn_reason = None, "sim/connectome.py has no load_connectome()"

        self._engine_kind = "fake" if self.force_fake else "none"
        reasons = [why_fake] if self.force_fake else []
        if not self.force_fake:
            fast, err = _import("fast_engine")
            if fast is not None and hasattr(fast, "FastBrain"):
                self._engine_kind, self._engine_mod = "fast", fast
            else:
                reasons.append(err or "sim/fast_engine.py has no FastBrain class")
                slow, err2 = _import("shiu_model")
                if slow is not None and callable(getattr(slow, "run_trials", None)):
                    self._engine_kind, self._engine_mod = "shiu", slow
                else:
                    reasons.append(err2 or "sim/shiu_model.py has no run_trials()")
        if self._engine_kind == "fast":
            nb = getattr(self._engine_mod, "nb", None)
            self.engine_info = {
                "name": "sim.fast_engine", "module": "sim/fast_engine.py",
                "version": f"FastBrain, numba {getattr(nb, '__version__', '?')}, {_app_threads()} thread(s)",
                "code_hash": _file_hash(ROOT / "sim" / "fast_engine.py"),
                "is_fake": False, "is_fallback": False,
                "reason": "real engine: sim/fast_engine.py (FastBrain)"}
        elif self._engine_kind == "shiu":
            b2 = getattr(self._engine_mod, "brian2", None)
            self.engine_info = {
                "name": "sim.shiu_model", "module": "sim/shiu_model.py",
                "version": f"Brian2 {getattr(b2, '__version__', '?')} numpy mode",
                "code_hash": _file_hash(ROOT / "sim" / "shiu_model.py"),
                "is_fake": False, "is_fallback": True,
                "reason": ("real but slow engine: sim/shiu_model.py, the Brian2 port of the paper's "
                           "code (whole-brain runs take many minutes); the fast engine is unavailable "
                           "because " + "; ".join(reasons))}
        elif self._engine_kind == "fake":
            self.engine_info = {
                "name": FAKE_ENGINE_NAME, "module": "app/engine_adapter.py",
                "version": FAKE_ENGINE_VERSION, "code_hash": _file_hash(Path(__file__)),
                "is_fake": True, "is_fallback": False, "reason": "; ".join(reasons)}
        else:
            self.engine_info = {
                "name": "none", "module": None, "version": None, "code_hash": None,
                "is_fake": False, "is_fallback": False, "missing": True,
                "reason": "; ".join(reasons)}

    def _probe_variants(self):
        """Can each offered fix / upgrade be built here? {option: None or why not}."""
        self._variant_mods: dict[str, Any] = {}
        self.option_problems: dict[str, str | None] = {}
        if self._engine_kind == "fake":
            self.option_problems = {k: None for k in (*FIX_CHOICES, *UPGRADE_CHOICES)}
            return
        for k in (*FIX_CHOICES, *UPGRADE_CHOICES):
            self.option_problems[k] = None
        self.option_problems["none"] = None if self.runs_enabled else "no simulator"
        if self._engine_kind != "fast":
            why = ("model variants need the fast engine (sim/fast_engine.py), which is not available: "
                   + self.engine_info["reason"])
            for k in (*[f for f in FIX_CHOICES if f != "none"], *UPGRADE_CHOICES):
                self.option_problems[k] = why
            return
        sf, err = _import("sign_fixes")
        for k in (f for f in FIX_CHOICES if f != "none"):
            if sf is None:
                self.option_problems[k] = err
            elif not callable(getattr(sf, "build_brain", None)):
                self.option_problems[k] = "sim/sign_fixes.py has no build_brain()"
            elif k not in getattr(sf, "FIXES", ()):
                self.option_problems[k] = f"sim/sign_fixes.py no longer defines the fix '{k}'"
        self._variant_mods["sign_fixes"] = sf
        rl, err = _import("realism")
        for k in ("delays", "adaptation"):
            if rl is None:
                self.option_problems[k] = err
            elif not hasattr(rl, "RealisticBrain"):
                self.option_problems[k] = "sim/realism.py has no RealisticBrain class"
            elif k not in getattr(rl, "REALISM_DEFAULTS", {}):
                self.option_problems[k] = f"sim/realism.py has no '{k}' switch"
        self._variant_mods["realism"] = rl
        ct, err = _import("celltype_params")
        if ct is None:
            self.option_problems["celltype"] = err
        elif not hasattr(ct, "CellTypeBrain"):
            self.option_problems["celltype"] = "sim/celltype_params.py has no CellTypeBrain class"
        self._variant_mods["celltype_params"] = ct

    def default_variant(self, snapshot: str) -> tuple[dict[str, Any], str | None]:
        """The model the page opens on for this brain map, and the plain-English
        reason when that is the published model instead of the recommended fix
        (the page shows it; the app never swaps models without saying so)."""
        snapshot = check_snapshot(snapshot)
        if snapshot != VARIANT_SNAPSHOT:
            return dict(PUBLISHED_VARIANT, upgrades=[]), (
                f"the recommended fix is built into the simulator (sim/) for brain map "
                f"{VARIANT_SNAPSHOT} only. It was ported to map 783 for one experiment "
                "(experiments/runaway_783/, docs/runaway-783.md), but that copy is not part "
                f"of sim/, so on map {snapshot} the app runs the published model. Switch the "
                f"brain map to {VARIANT_SNAPSHOT} to use the fix.")
        why = self.option_problems.get(DEFAULT_FIX)
        if why:
            return dict(PUBLISHED_VARIANT, upgrades=[]), (
                f"the recommended fix cannot be built here ({why}), so the app runs the "
                "published model.")
        return {"fix": DEFAULT_FIX, "upgrades": []}, None

    def variant_unavailable(self, v: dict[str, Any]) -> str | None:
        """Why this (already checked) variant cannot be built here, or None."""
        for k in (v["fix"], *v["upgrades"]):
            why = self.option_problems.get(k)
            if why:
                name = (FIX_CHOICES.get(k) or UPGRADE_CHOICES.get(k))["label"]
                return f"'{name}' is not available: {why}"
        return None

    @property
    def runs_enabled(self) -> bool:
        return self._engine_kind != "none"

    def table(self, snapshot: str) -> _Table:
        """The neuron list for one snapshot (loaded on first use, then kept)."""
        snapshot = check_snapshot(snapshot)
        t = self._tables.get(snapshot)
        if t is not None:                      # no waiting while a brain is being built
            return t
        with self._lock:
            if snapshot in self._tables:
                return self._tables[snapshot]
            reasons = [self._conn_reason] if self._conn_mod is None else []
            df = info = None
            if self._conn_mod is not None:
                try:
                    # Only the small neuron list is kept; the connection list is let go.
                    df = _normalise_table(self._conn_mod.load_connectome(snapshot).neurons)
                    info = {"source": f"sim/connectome.py (snapshot {snapshot})", "is_fake": False,
                            "is_fallback": False, "reason": "real FlyWire neuron list"}
                except Exception as exc:  # noqa: BLE001
                    reasons.append(f"sim/connectome.py could not load snapshot {snapshot}: "
                                   f"{type(exc).__name__}: {exc}")
            ann = _ANNOTATION_FILES[snapshot]
            if df is None and not self.force_fake and ann.exists():
                raw = pd.read_csv(ann, sep="\t", dtype=str)
                df = _normalise_table(raw)
                info = {"source": str(ann.relative_to(ROOT)).replace("\\", "/"), "is_fake": False,
                        "is_fallback": True,
                        "reason": ("real FlyWire labels read directly by the app, not via "
                                   "sim/connectome.py, because " + "; ".join(reasons))}
            if df is None and self.force_fake:
                df = _fake_table()
                info = {"source": "stand-in list inside app/engine_adapter.py", "is_fake": True,
                        "is_fallback": False, "reason": "; ".join(reasons)}
            if df is None:
                df = pd.DataFrame({c: pd.Series(dtype="int64" if c == "root_id" else "string")
                                   for c in TABLE_COLUMNS})
                info = {"source": "none", "is_fake": False, "is_fallback": False, "missing": True,
                        "reason": "; ".join(reasons) or "no neuron list found"}
            info.update(snapshot=snapshot, count=int(len(df)))
            self._tables[snapshot] = _Table(df, info)
            return self._tables[snapshot]

    # ---- status ------------------------------------------------------------
    @property
    def is_fake(self) -> bool:
        return bool(self.engine_info["is_fake"] or any(t.info["is_fake"] for t in self._tables.values()))

    def banner(self) -> str | None:
        parts = []
        if self.engine_info["is_fake"]:
            parts.append("Results are NOT from the fly brain model: the app is using a stand-in "
                         "engine that makes up spikes. Why: " + self.engine_info["reason"] + ".")
        elif self.engine_info.get("missing"):
            parts.append("Runs are switched off: no working fly brain simulator was found. Why: "
                         + self.engine_info["reason"] + ".")
        elif self.engine_info["is_fallback"]:
            parts.append("Using the slow engine. " + self.engine_info["reason"] + ".")
        for (snap, key), err in list(self._engine_errors.items()):
            if key == "published":
                parts.append(f"The real engine failed to start for snapshot {snap}: {err}")
            else:
                parts.append(f"The model '{self._label_of(key)}' could not be built (snapshot {snap}): "
                             f"{err}. Runs with it are refused; no other model is run in its place.")
        for snap, t in self._tables.items():
            if t.info.get("missing"):
                parts.append(f"No neuron list for snapshot {snap}. Why: {t.info['reason']}.")
            elif t.info["is_fake"]:
                parts.append(f"The snapshot {snap} neuron list is made up (stand-in). "
                             f"Why: {t.info['reason']}.")
            elif t.info["is_fallback"]:
                parts.append(f"Snapshot {snap} neuron labels: {t.info['reason']}.")
        return " ".join(parts) or None

    @staticmethod
    def _label_of(key: str) -> str:
        if key == "published":
            return variant_label(PUBLISHED_VARIANT)
        fix, *ups = key.split("+")
        return variant_label({"fix": fix, "upgrades": ups})

    def _mem_entry(self, snap: str, key: str) -> dict[str, Any]:
        return {"snapshot": snap, "key": key, "label": self._label_of(key),
                "build_seconds": (None if (snap, key) not in self._build_seconds
                                  else round(self._build_seconds[(snap, key)], 1))}

    def models_status(self) -> dict[str, Any]:
        """What the page's Model panel shows: the offered choices, what is in memory,
        what is being built, and every build failure with its reason."""
        def opt(k, c):
            return {"id": k, "label": c["label"], "about": c["about"], "doc": c["doc"],
                    "available": self.option_problems.get(k) is None,
                    "problem": self.option_problems.get(k)}
        b = self._building
        return {
            "fixes": [opt(k, c) for k, c in FIX_CHOICES.items()],
            "upgrades": [opt(k, c) for k, c in UPGRADE_CHOICES.items()],
            "variant_snapshot": VARIANT_SNAPSHOT, "max_in_memory": MAX_BRAINS_IN_MEMORY,
            # The model the page opens on, per brain map ("fallback": why it is not
            # the recommended fix there, or None).
            "default_fix": DEFAULT_FIX,
            "defaults": {s: {"fix": v["fix"], "fallback": why}
                         for s in SNAPSHOTS for v, why in [self.default_variant(s)]},
            "in_memory": [self._mem_entry(s, k) for (s, k) in reversed(self._engines)],  # newest first
            "building": None if b is None else {**b, "for_s": round(time.time() - b["since"], 1)},
            "errors": [{**self._mem_entry(s, k), "reason": e} for (s, k), e in self._engine_errors.items()],
            "dropped": self._dropped[-5:],
        }

    def variant_state(self, v: dict[str, Any], snapshot: str) -> dict[str, Any]:
        """Memory / build state of one (checked) variant, for the Model panel."""
        k = (snapshot, variant_key(v))
        will_drop = None
        if k not in self._engines and len(self._engines) >= MAX_BRAINS_IN_MEMORY:
            s, key = next(iter(self._engines))
            will_drop = f"{self._label_of(key)} (map {s})"
        b = self._building
        return {"in_memory": k in self._engines,
                "building": bool(b and (b["snapshot"], b["key"]) == k),
                "other_building": None if not b or (b["snapshot"], b["key"]) == k else b["label"],
                "last_build_s": None if k not in self._build_seconds else round(self._build_seconds[k], 1),
                "error": self._engine_errors.get(k), "unavailable": self.variant_unavailable(v),
                "will_drop": will_drop}

    def status(self) -> dict[str, Any]:
        return {"engine": dict(self.engine_info,
                               built_for=sorted({s for (s, _k) in self._engines}),
                               start_errors={f"{s} {k}": e for (s, k), e in self._engine_errors.items()}),
                "neurons": {s: dict(t.info) for s, t in self._tables.items()},
                "snapshots": list(SNAPSHOTS), "default_snapshot": DEFAULT_SNAPSHOT,
                "runs_enabled": self.runs_enabled, "models": self.models_status(),
                "is_fake": self.is_fake, "banner": self.banner()}

    # ---- neuron lookup -------------------------------------------------
    def neuron_record(self, rid: int, snapshot: str = DEFAULT_SNAPSHOT) -> dict[str, Any]:
        t = self.table(snapshot)
        if rid in t.by_id.index:
            row = t.by_id.loc[rid]
            return {"root_id": str(rid), "known": True,
                    **{c: str(row[c]) for c in TABLE_COLUMNS if c != "root_id"}}
        return {"root_id": str(rid), "known": False, "cell_type": "", "name": "",
                "super_class": "", "cell_class": "", "nt": "", "side": ""}

    def lookup(self, ids, snapshot: str = DEFAULT_SNAPSHOT) -> list[dict[str, Any]]:
        return [self.neuron_record(i, snapshot) for i in _to_int_ids(ids)]

    def unknown_ids(self, ids: list[int], snapshot: str = DEFAULT_SNAPSHOT) -> list[int]:
        idx = self.table(snapshot).by_id.index
        return [i for i in ids if i not in idx]

    def search(self, query: str, limit: int = 50, snapshot: str = DEFAULT_SNAPSHOT) -> dict[str, Any]:
        q = (query or "").strip()
        tab = self.table(snapshot)
        if not q:
            return {"query": q, "snapshot": snapshot, "total": 0, "results": []}
        t = tab.df
        if q.isdigit():
            ranked = t[tab.id_str.str.startswith(q)]
        else:
            ql = q.lower()
            ct, nm = t["cell_type"].str.lower(), t["name"].str.lower()
            exact = (ct == ql) | (nm == ql)
            prefix = ct.str.startswith(ql) | nm.str.startswith(ql)
            contains = (ct.str.contains(ql, regex=False) | nm.str.contains(ql, regex=False)
                        | t["super_class"].str.lower().eq(ql) | t["cell_class"].str.lower().eq(ql))
            score = np.where(exact, 0, np.where(prefix, 1, np.where(contains, 2, 9)))
            ranked = t.assign(_s=score)[score < 9].sort_values(["_s", "cell_type", "root_id"])
        rows = ranked.head(max(1, min(limit, 5000)))
        results = [{"root_id": str(r.root_id), "known": True, "cell_type": r.cell_type,
                    "name": r.name, "super_class": r.super_class, "cell_class": r.cell_class,
                    "nt": r.nt, "side": r.side} for r in rows.itertuples()]
        return {"query": q, "snapshot": snapshot, "total": int(len(ranked)), "results": results}

    # ---- running -----------------------------------------------------------
    def _variant(self, variant, snapshot: str) -> dict[str, Any]:
        try:
            return check_variant(variant, snapshot)
        except ValueError as exc:
            raise EngineError(str(exc)) from None

    def engine_built(self, snapshot: str = DEFAULT_SNAPSHOT, variant=None) -> bool:
        snapshot = check_snapshot(snapshot)
        return (snapshot, variant_key(self._variant(variant, snapshot))) in self._engines

    def last_build_seconds(self, snapshot: str = DEFAULT_SNAPSHOT, variant=None) -> float | None:
        snapshot = check_snapshot(snapshot)
        return self._build_seconds.get((snapshot, variant_key(self._variant(variant, snapshot))))

    def _build(self, snapshot: str, v: dict[str, Any]):
        """Build one brain for (snapshot, variant). No caching here."""
        key = variant_key(v)
        if self._engine_kind == "fake":
            return FakeEngine(self.table(snapshot).df["root_id"].tolist(), self._fake_pause, variant_key=key)
        if self._engine_kind == "shiu":
            if not is_published(v):
                raise EngineError("model variants need the fast engine; the slow engine runs the "
                                  "published model only")
            return ShiuModelEngine(self._engine_mod, snapshot)
        threads = _app_threads()
        if is_published(v):
            # Exactly what the app built before variants existed (the Phase 4 checkpoint path).
            return FastBrainEngine(self._engine_mod, snapshot, threads)
        ups = set(v["upgrades"])
        if v["fix"] != "none" and not ups:
            brain = self._variant_mods["sign_fixes"].build_brain(fix=v["fix"], snapshot=snapshot,
                                                                 n_threads=threads)
        elif v["fix"] == "none" and ups == {"celltype"}:
            brain = self._variant_mods["celltype_params"].CellTypeBrain(snapshot, n_threads=threads)
        elif v["fix"] == "none" and ups and ups <= {"delays", "adaptation"}:
            brain = self._variant_mods["realism"].RealisticBrain(
                snapshot, n_threads=threads,
                realism={"delays": "delays" in ups, "adaptation": "adaptation" in ups})
        else:  # never reached while check_variant refuses these; never guess a substitute
            raise EngineError(f"the app has no way to build '{variant_label(v)}'")
        return FastBrainEngine(None, snapshot, brain=brain)

    @staticmethod
    def _release_memory():
        gc.collect()
        try:                                   # pyarrow keeps freed memory parked; hand it back
            import sys
            pa = sys.modules.get("pyarrow")
            if pa is not None:
                pa.default_memory_pool().release_unused()
        except Exception:  # noqa: BLE001 - only a memory courtesy
            pass

    def engine(self, snapshot: str = DEFAULT_SNAPSHOT, variant=None):
        """The built brain for (snapshot, model variant): built on first use, then kept.

        At most MAX_BRAINS_IN_MEMORY brains are kept; the least recently used is
        dropped (before the new one is built, so memory never holds three). A
        failure is recorded and raised with its reason; nothing else is run instead.
        """
        snapshot = check_snapshot(snapshot)
        v = self._variant(variant, snapshot)
        if not self.runs_enabled:
            raise EngineError("runs are switched off because no fly brain simulator could be "
                              "loaded: " + self.engine_info["reason"])
        why = self.variant_unavailable(v)
        if why:
            raise EngineError(why + ". Nothing was run in its place.")
        k = (snapshot, variant_key(v))
        with self._build_lock:
            if k in self._engines:
                self._engines.move_to_end(k)
                return self._engines[k]
            while len(self._engines) >= MAX_BRAINS_IN_MEMORY:
                (s, key), old = self._engines.popitem(last=False)
                del old
                self._dropped.append(f"{time.strftime('%H:%M:%S')}: dropped '{self._label_of(key)}' "
                                     f"(map {s}) from memory to make room for '{variant_label(v)}'")
                self._release_memory()
            self._building = {"snapshot": snapshot, "key": k[1], "label": variant_label(v),
                              "since": time.time()}
            t0 = time.perf_counter()
            try:
                eng = self._build(snapshot, v)
            except Exception as exc:  # noqa: BLE001 - recorded, shown, never swallowed
                self._engine_errors[k] = f"{type(exc).__name__}: {exc}"
                self._release_memory()
                if is_published(v):
                    raise EngineError(f"the engine ({self.engine_info['module']}) could not be built for "
                                      f"snapshot {snapshot}: {self._engine_errors[k]}") from exc
                raise EngineError(f"the model '{variant_label(v)}' could not be built for snapshot "
                                  f"{snapshot}: {self._engine_errors[k]}. Nothing was run in its "
                                  "place.") from exc
            finally:
                self._building = None
            self._build_seconds[k] = time.perf_counter() - t0
            self._engine_errors.pop(k, None)
            self._engines[k] = eng
            return eng

    def warm_up(self, snapshots=SNAPSHOTS) -> dict[str, float]:
        """Build the model the page opens on (default_variant: the recommended fix
        on 630, the published model on 783) for each snapshot now (the app does
        this at start-up). The default snapshot is built last, so it is the one
        kept longest when a model variant needs the room."""
        took = {}
        for snap in sorted(snapshots, key=lambda s: s == DEFAULT_SNAPSHOT):
            t0 = time.perf_counter()
            self.table(snap)
            self.engine(snap, self.default_variant(snap)[0])
            took[snap] = time.perf_counter() - t0
        return took

    def run(self, excite, silence, duration_ms: float, n_trials: int, seed: int, rate_hz: float | None,
            progress: Callable[[float], None] | None = None,
            snapshot: str = DEFAULT_SNAPSHOT, variant=None,
            stim_groups: list[dict[str, Any]] | None = None) -> RunResult:
        """One run. Either ``excite`` + ``rate_hz`` (every stimulated neuron at one
        rate, as before) or ``stim_groups`` = [{"name", "rate_hz", "ids"}, ...]
        (each group at its own rate). ``variant`` None = the published model."""
        silence = _to_int_ids(silence)
        if stim_groups:
            groups = [{"name": str(g.get("name") or f"Group {n}"), "rate_hz": float(g["rate_hz"]),
                       "ids": _to_int_ids(g.get("ids"))} for n, g in enumerate(stim_groups, 1)]
        else:
            groups = [{"name": "Stimulated", "rate_hz": None if rate_hz is None else float(rate_hz),
                       "ids": _to_int_ids(excite)}]
        seen: dict[int, str] = {}
        for g in groups:
            for i in g["ids"]:
                if i in seen:
                    raise EngineError(f"neuron {i} is in two stimulus groups ('{seen[i]}' and "
                                      f"'{g['name']}')")
                seen[i] = g["name"]
        rates = {g["rate_hz"] for g in groups if g["ids"]}
        if len(rates) <= 1:
            # One rate for everyone: exactly the call the app made before per-group rates.
            eng_in = [i for g in groups for i in g["ids"]]
            eng_rate = rates.pop() if rates else rate_hz
        else:
            # Different rates: {root_id: rate}, in group order (the order sets which
            # random numbers each neuron gets, so it is kept exactly as saved).
            eng_in = {i: g["rate_hz"] for g in groups for i in g["ids"]}
            eng_rate = None
        v = self._variant(variant, snapshot)
        eng = self.engine(snapshot, v)
        t0 = time.perf_counter()
        raw = eng.run(eng_in, silence, duration_ms, n_trials, seed, eng_rate, progress)
        wall = time.perf_counter() - t0
        trials, rates_hz, sd, notes = _normalise_result(raw, n_trials, duration_ms)
        return RunResult(trials=trials, rates_hz=rates_hz, rate_sd_hz=sd, duration_ms=duration_ms,
                         n_trials=len(trials), engine=dict(self.engine_info), snapshot=snapshot,
                         wall_seconds=wall, notes=notes, variant=variant_record(v),
                         stim_groups=[{"name": g["name"], "rate_hz": g["rate_hz"],
                                       "ids": [str(i) for i in g["ids"]]} for g in groups])


_ADAPTER: EngineAdapter | None = None
_ADAPTER_LOCK = threading.Lock()


def get_adapter() -> EngineAdapter:
    global _ADAPTER
    with _ADAPTER_LOCK:
        if _ADAPTER is None:
            _ADAPTER = EngineAdapter()
        return _ADAPTER
