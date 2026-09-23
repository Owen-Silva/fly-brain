"""Shared helpers for the Phase 6 runaway-activity checks.

Plain English
-------------
* ``paper_ids()`` reads the paper's neuron ID lists (sugar, bitter, water,
  Ir94e taste neurons, MN9) out of sim/shiu_model.py as text, without
  importing it (importing it would load Brian2 and cost memory). IDs stay
  whole 64-bit integers.
* ``labels(brain)`` gives cell type / side / transmitter for every neuron, in
  the same row order as the brain (checked, not assumed).
* ``make_input`` draws the random ("Poisson") taste input for one trial
  exactly the way ``FastBrain.run`` does, so trial k of seed s here is the
  same trial k of seed s there. It can also switch the input off after a
  chosen time (used to test whether runaway activity keeps itself going).
* ``run_one`` simulates one trial and ``trial_summary`` measures it.

The runaway definition used everywhere
--------------------------------------
In the Brian2 trials a healthy 10 ms slice never has more than ~350
different neurons firing; a runaway slice has ~4,000. We call a trial
RUNAWAY if in at least one 10 ms slice more than 1,500 different neurons fire.
The ONSET is the first 1 ms bin with more than 200 spikes (a healthy trial
has about 20 spikes per ms). The Phase 3 rule ("more than 5x the median
trial of the same condition") is reported next to it as a cross-check.
"""

import ast
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = HERE / "results"
PLOTS = HERE / "plots"
RESULTS.mkdir(exist_ok=True)
PLOTS.mkdir(exist_ok=True)

SHIU_MODEL = ROOT / "sim" / "shiu_model.py"
LABELS_630 = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"

RUNAWAY_DISTINCT_10MS = 1500   # different neurons firing in one 10 ms slice
ONSET_SPIKES_1MS = 200         # spikes in one 1 ms bin


def free_ram_gb():
    """Free physical memory in GB (Windows), or None if it cannot be read."""
    try:
        import ctypes

        class MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEMSTAT()
        m.dwLength = ctypes.sizeof(MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / 1024 ** 3
    except Exception:
        return None


def paper_ids():
    """{'SUGAR': [...], 'BITTER': [...], 'WATER': [...], 'IR94E': [...],
    'MN9': int (contra), 'MN9_IPSI': int} as exact Python ints."""
    tree = ast.parse(SHIU_MODEL.read_text(encoding="utf-8"))
    wanted = {"SUGAR_R_630": "SUGAR", "BITTER_R_630": "BITTER", "WATER_R_630": "WATER",
              "IR94E_630": "IR94E", "MN9_LEFT": "MN9", "MN9_RIGHT_630": "MN9_IPSI"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], "id", None)
            if name in wanted:
                out[wanted[name]] = ast.literal_eval(node.value)
    assert set(out) == set(wanted.values()), out.keys()
    return out


def labels(brain, columns=("root_id", "super_class", "cell_class", "cell_sub_class",
                           "cell_type", "hemibrain_type", "side", "top_nt", "sign",
                           "ref_sign", "nerve", "flow")):
    df = pd.read_parquet(LABELS_630, columns=list(columns))
    assert df["root_id"].dtype == np.int64
    df = df.set_index("root_id").reindex(brain.root_ids)
    for c in df.columns:
        if c not in ("sign", "ref_sign"):
            df[c] = df[c].astype(object).where(df[c].notna(), "").astype(str)
    df = df.reset_index()
    assert np.array_equal(df["root_id"].to_numpy(), brain.root_ids)
    return df


def make_input(brain, excite, seed, trial, duration_ms, params=None, cutoff_ms=None):
    """Poisson input for trial ``trial`` of seed ``seed``, identical to what
    ``brain.run(excite=excite, seed=seed, n_trials>trial)`` gives that trial.
    ``excite`` is {root_id: rate_hz}. With ``cutoff_ms`` the input stops then."""
    p = brain._params_for(params)
    ids = np.array(list(excite.keys()), dtype=np.int64)
    rates = np.array([float(r) for r in excite.values()])
    exc_idx = brain.index_of(ids)
    n_steps = int(round(duration_ms / p["dt"]))
    prob = rates * p["dt"] * 1e-3
    seq = np.random.SeedSequence(seed).spawn(trial + 1)[trial]
    ev_ptr, ev_neuron = brain._poisson_events(np.random.default_rng(seq), exc_idx, prob, n_steps)
    if cutoff_ms is not None:
        steps = np.repeat(np.arange(n_steps), np.diff(ev_ptr))
        keep = steps < int(round(cutoff_ms / p["dt"]))
        ev_ptr, ev_neuron = brain._pack_events(steps[keep], ev_neuron[keep].astype(np.int64), n_steps)
    return (ev_ptr, ev_neuron), exc_idx, n_steps, p


def run_one(brain, excite, seed, trial, duration_ms=1000.0, params=None, silence=(),
            cutoff_ms=None):
    """Simulate one trial; returns a SimResult with n_trials = 1."""
    ev, exc_idx, n_steps, p = make_input(brain, excite, seed, trial, duration_ms, params,
                                         cutoff_ms)
    return brain._run_events([ev], exc_idx, silence, n_steps, p, ())


def run_events(brain, ev_steps, ev_ids, excite_ids, duration_ms=1000.0, params=None,
               silence=()):
    """Simulate one trial with explicit input kicks (step, root_id)."""
    return brain.run_with_input_events([(ev_steps, ev_ids)], excite=excite_ids,
                                       duration_ms=duration_ms, params=params,
                                       silence=silence)


def series(step, neuron, n_steps, dt_ms=0.1):
    """Spikes per 1 ms bin and different neurons per 10 ms slice."""
    per_ms = int(round(1.0 / dt_ms))
    n_ms = n_steps // per_ms
    spikes_1ms = np.bincount(step // per_ms, minlength=n_ms)[:n_ms]
    b10 = step // (10 * per_ms)
    n10 = n_ms // 10
    key = np.unique(b10.astype(np.int64) * 1_000_000 + neuron)
    distinct_10ms = np.bincount(key // 1_000_000, minlength=n10)[:n10]
    return spikes_1ms, distinct_10ms


def trial_summary(res, brain, ids, dt_ms=0.1):
    """One row of numbers for a one-trial SimResult."""
    n_steps = int(round(res.duration_ms / dt_ms))
    step, neuron = res.step.astype(np.int64), res.neuron.astype(np.int64)
    s1, d10 = series(step, neuron, n_steps, dt_ms)
    runaway = bool(d10.max() > RUNAWAY_DISTINCT_10MS) if d10.size else False
    onset = np.nan
    if runaway:
        over = np.flatnonzero(s1 > ONSET_SPIKES_1MS)
        onset = float(over[0]) if over.size else np.nan
    dur_s = res.duration_ms * 1e-3
    mn9 = brain.index_of([ids["MN9"], ids["MN9_IPSI"]])
    last = step >= n_steps - int(round(100 / dt_ms))
    row = dict(
        total_spikes=int(step.size),
        n_active=int(np.unique(neuron).size),
        max_distinct_10ms=int(d10.max()) if d10.size else 0,
        distinct_last_100ms=int(np.unique(neuron[last]).size),
        runaway=runaway,
        onset_ms=onset,
        mn9_hz=float((neuron == mn9[0]).sum() / dur_s),
        mn9_ipsi_hz=float((neuron == mn9[1]).sum() / dur_s),
        wall_s=round(res.wall_time_s, 2),
    )
    return row, s1, d10


def sparse_neuron_stats(res):
    """(neuron row, spike count, first spike step) for every neuron that fired."""
    neuron, step = res.neuron.astype(np.int64), res.step.astype(np.int64)
    u, inv, cnt = np.unique(neuron, return_inverse=True, return_counts=True)
    first = np.full(u.size, np.iinfo(np.int64).max)
    np.minimum.at(first, inv, step)
    return u.astype(np.int32), cnt.astype(np.int32), first.astype(np.int32)


def run_batch(brain, conds, out_name, ids=None):
    """Run a list of conditions, saving after each one.
    ``conds``: list of dicts with keys name, excite ({root_id: Hz}), seed,
    n_trials, and optionally duration_ms, params, silence, cutoff_ms, plus any
    extra keys (copied into the table). Writes results/<out_name>.csv and
    results/<out_name>_series.npz."""
    ids = ids or paper_ids()
    rows, s1_all, d10_all, keys = [], [], [], []
    extra_skip = {"excite", "params", "silence"}
    for c in conds:
        dur = c.get("duration_ms", 1000.0)
        for k in range(c["n_trials"]):
            res = run_one(brain, c["excite"], c["seed"], k, dur, c.get("params"),
                          c.get("silence", ()), c.get("cutoff_ms"))
            row, s1, d10 = trial_summary(res, brain, ids)
            meta = {kk: vv for kk, vv in c.items() if kk not in extra_skip}
            rows.append(dict(**meta, trial=k, **row))
            s1_all.append(s1)
            d10_all.append(d10)
            keys.append(f"{c['name']}|{c['seed']}|{k}")
            del res
        df = pd.DataFrame(rows)
        df.to_csv(RESULTS / f"{out_name}.csv", index=False)
        d = df[df.name == c["name"]]
        print(f"{c['name']}: runaway {int(d.runaway.sum())}/{len(d)}, median spikes "
              f"{d.total_spikes.median():.0f}, MN9 {d.mn9_hz.mean():.1f} Hz, onsets "
              f"{sorted(d.onset_ms.dropna().astype(int).tolist())}, free RAM {free_ram_gb():.1f} GB",
              flush=True)
    lens = {len(s) for s in s1_all}
    if len(lens) == 1:
        np.savez_compressed(RESULTS / f"{out_name}_series.npz", keys=np.array(keys),
                            spikes_1ms=np.array(s1_all, np.int32),
                            distinct_10ms=np.array(d10_all, np.int32))
    else:
        np.savez_compressed(RESULTS / f"{out_name}_series.npz", keys=np.array(keys),
                            **{f"s1_{i}": s for i, s in enumerate(s1_all)},
                            **{f"d10_{i}": s for i, s in enumerate(d10_all)})
    return pd.DataFrame(rows)


def get_brain(g):
    brain = g.get("brain")
    if brain is None:
        import sys
        sys.path.insert(0, str(ROOT))
        from sim.fast_engine import FastBrain
        brain = FastBrain("630", n_threads=1)
    return brain


def add_5x_rule(df, group_cols):
    """Phase 3 cross-check rule: total spikes > 5 x the median of its condition."""
    med = df.groupby(group_cols)["total_spikes"].transform("median")
    df = df.copy()
    df["runaway_5x_median"] = df["total_spikes"] > 5 * med
    return df
