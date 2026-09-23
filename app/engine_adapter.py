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

FLYBRAIN_APP_FAKE=1 forces the stand-in engine and stand-in neuron list (the
fast automated tests use it; nothing else ever falls back to it).
FLYBRAIN_APP_THREADS=n lets the fast engine run n trials at once (default 1,
because the computer is shared).
"""
from __future__ import annotations

import hashlib
import importlib
import os
import threading
import time
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

    def __init__(self, all_ids: list[int], seconds_per_trial: float = 0.02):
        self._ids = np.array(sorted(all_ids), dtype=np.int64)
        self._pause = seconds_per_trial

    def run(self, excite, silence, duration_ms, n_trials, seed, rate_hz, progress=None):
        silence_set = set(silence)
        exc = [e for e in excite if e not in silence_set]
        rates: dict[int, float] = {e: float(rate_hz) for e in exc}
        if exc:
            # Same stimulated set -> same pretend-downstream neurons.
            key = int(hashlib.sha256(",".join(map(str, sorted(exc))).encode()).hexdigest()[:8], 16)
            pool = np.array([i for i in self._ids if i not in rates and i not in silence_set])
            if len(pool):
                pick = np.random.default_rng(key).choice(pool, size=min(25, len(pool)), replace=False)
                for rank, rid in enumerate(pick):
                    rates[int(rid)] = float(rate_hz) * 0.5 * (0.85 ** rank)
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
        out = self._mod.run_trials(excite_ids=excite, silence_ids=silence, duration_ms=duration_ms,
                                   n_trials=n_trials, rate_hz=rate_hz, seed=seed,
                                   dataset=self.snapshot)
        spikes = out.spikes.rename(columns={"t": "t_s", "flywire_id": "root_id"})
        return {"spikes": spikes, "rates": out.rates, "rate_sd": out.rate_std}


class FastBrainEngine:
    """Wraps sim/fast_engine.py's FastBrain (built once per snapshot, run many times)."""

    def __init__(self, mod, snapshot: str, n_threads: int = 1):
        self.brain = mod.FastBrain(snapshot=snapshot, n_threads=n_threads)
        self.snapshot = snapshot

    def run(self, excite, silence, duration_ms, n_trials, seed, rate_hz, progress=None):
        res = self.brain.run(excite=excite, silence=silence, duration_ms=duration_ms,
                             n_trials=n_trials, seed=seed, rate_hz=rate_hz)
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
        self._lock = threading.RLock()
        self._tables: dict[str, _Table] = {}
        self._engines: dict[str, Any] = {}   # one built network per snapshot, reused
        self._engine_errors: dict[str, str] = {}
        self._probe_modules()
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

    @property
    def runs_enabled(self) -> bool:
        return self._engine_kind != "none"

    def table(self, snapshot: str) -> _Table:
        """The neuron list for one snapshot (loaded on first use, then kept)."""
        snapshot = check_snapshot(snapshot)
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
        for snap, err in self._engine_errors.items():
            parts.append(f"The real engine failed to start for snapshot {snap}: {err}")
        for snap, t in self._tables.items():
            if t.info.get("missing"):
                parts.append(f"No neuron list for snapshot {snap}. Why: {t.info['reason']}.")
            elif t.info["is_fake"]:
                parts.append(f"The snapshot {snap} neuron list is made up (stand-in). "
                             f"Why: {t.info['reason']}.")
            elif t.info["is_fallback"]:
                parts.append(f"Snapshot {snap} neuron labels: {t.info['reason']}.")
        return " ".join(parts) or None

    def status(self) -> dict[str, Any]:
        return {"engine": dict(self.engine_info, built_for=sorted(self._engines),
                               start_errors=dict(self._engine_errors)),
                "neurons": {s: dict(t.info) for s, t in self._tables.items()},
                "snapshots": list(SNAPSHOTS), "default_snapshot": DEFAULT_SNAPSHOT,
                "runs_enabled": self.runs_enabled,
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
    def engine_built(self, snapshot: str = DEFAULT_SNAPSHOT) -> bool:
        return check_snapshot(snapshot) in self._engines

    def engine(self, snapshot: str = DEFAULT_SNAPSHOT):
        """The built engine for a snapshot (built once, then kept and reused)."""
        snapshot = check_snapshot(snapshot)
        if not self.runs_enabled:
            raise EngineError("runs are switched off because no fly brain simulator could be "
                              "loaded: " + self.engine_info["reason"])
        with self._lock:
            if snapshot in self._engines:
                return self._engines[snapshot]
            try:
                if self._engine_kind == "fast":
                    eng = FastBrainEngine(self._engine_mod, snapshot, _app_threads())
                elif self._engine_kind == "shiu":
                    eng = ShiuModelEngine(self._engine_mod, snapshot)
                else:
                    eng = FakeEngine(self.table(snapshot).df["root_id"].tolist(), self._fake_pause)
            except Exception as exc:  # noqa: BLE001
                self._engine_errors[snapshot] = f"{type(exc).__name__}: {exc}"
                raise EngineError(f"the engine ({self.engine_info['module']}) could not be built for "
                                  f"snapshot {snapshot}: {self._engine_errors[snapshot]}") from exc
            self._engine_errors.pop(snapshot, None)
            self._engines[snapshot] = eng
            return eng

    def warm_up(self, snapshots=SNAPSHOTS) -> dict[str, float]:
        """Build the network for each snapshot now (the app does this at start-up)."""
        took = {}
        for snap in snapshots:
            t0 = time.perf_counter()
            self.table(snap)
            self.engine(snap)
            took[snap] = time.perf_counter() - t0
        return took

    def run(self, excite, silence, duration_ms: float, n_trials: int, seed: int, rate_hz: float,
            progress: Callable[[float], None] | None = None,
            snapshot: str = DEFAULT_SNAPSHOT) -> RunResult:
        excite, silence = _to_int_ids(excite), _to_int_ids(silence)
        eng = self.engine(snapshot)
        t0 = time.perf_counter()
        raw = eng.run(excite, silence, duration_ms, n_trials, seed, rate_hz, progress)
        wall = time.perf_counter() - t0
        trials, rates, sd, notes = _normalise_result(raw, n_trials, duration_ms)
        return RunResult(trials=trials, rates_hz=rates, rate_sd_hz=sd, duration_ms=duration_ms,
                         n_trials=len(trials), engine=dict(self.engine_info), snapshot=snapshot,
                         wall_seconds=wall, notes=notes)


_ADAPTER: EngineAdapter | None = None
_ADAPTER_LOCK = threading.Lock()


def get_adapter() -> EngineAdapter:
    global _ADAPTER
    with _ADAPTER_LOCK:
        if _ADAPTER is None:
            _ADAPTER = EngineAdapter()
        return _ADAPTER
