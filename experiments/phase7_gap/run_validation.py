"""Validate the electrical-synapse upgrade against al_ln_literature (Phase 7 item 5).

Plain English
-------------
One brain is built (al_ln_literature + the published gap junctions,
sim/gap_junctions.py) and run in several versions by changing only the junction
strength on the same object (so never two brains in memory):

* ``al_ln_check`` : the old engine on this brain (junctions ignored), seed 0,
  trials 0-9 of every condition. Must equal experiments/phase7_signs (and
  phase6/steering for DA1) trial for trial, which proves those files are the
  al_ln_literature baseline for this comparison.
* ``gap_x0_check``: the new engine with every junction at strength 0, same
  trials. Must equal al_ln_check spike totals exactly.
* ``gap_x1`` / ``gap_x0.5`` / ``gap_x2``: junctions at the calibrated strength,
  half and double. 3 seeds x 30 one-second trials per condition, the same
  seeds as the earlier lanes (taste as Phase 3/7, Ir94e as Phase 6, DM1 and
  DA1 as Phase 5/6 steering).
* Diagnostics, DM1 left/right only, 3 seeds x 30 trials:
  ``gap_x1_eln_only`` / ``gap_x1_sister_only`` (one coupling class at a time)
  and ``al_ln_eln_silenced`` (no junctions, the 44 eLNs silenced).

Read-outs per trial: MN9 (feeding), runaway (Phase 6 definition: more than
1,500 different neurons firing in some 10 ms slice), Kenyon cells active,
steering descending neurons, plus antennal-lobe read-outs: mean rate of the 44
eLNs, of the DM1 and DA1 uPNs on each side, and of all other uPNs ("lateral
excitation").
Results are appended every 10 trials and the run resumes where it stopped.
Usage: run_validation.py [config ...]
"""

import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "phase7_signs"))
import common as C  # noqa: E402  (phase7_signs helpers, used read-only)
from sim import gap_junctions as G  # noqa: E402
from sim import sign_fixes as S  # noqa: E402

OUT = HERE / "results"
CNT = OUT / "counts"
CNT.mkdir(parents=True, exist_ok=True)
TRIALS_CSV = OUT / "trials.csv"
N_TRIALS, CHUNK, SEEDS = 30, 10, (0, 1, 2)
TASTE = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz", "sugar100_bitter120"]
CONDS = TASTE + ["ir94e_200Hz", "dm1_both_150Hz", "dm1_left_150Hz", "dm1_right_150Hz",
                 "da1_left_150Hz", "da1_right_150Hz"]
EXTRA = {"da1_left_150Hz": ([("da1_left", 150)], 0), "da1_right_150Hz": ([("da1_right", 150)], 0)}
CONFIGS = {
    "al_ln_check": dict(scale=None, seeds=(0,), n_trials=10),
    "gap_x0_check": dict(scale=0.0, seeds=(0,), n_trials=10),
    "gap_x1": dict(scale=1.0),
    "gap_x0.5": dict(scale=0.5),
    "gap_x2": dict(scale=2.0),
    # diagnostics (which coupling class moves DM1 steering?): one class at a time
    "gap_x1_eln_only": dict(scale=1.0, only="eln_pn",
                            conds=["dm1_left_150Hz", "dm1_right_150Hz"]),
    "gap_x1_sister_only": dict(scale=1.0, only="sister_pn",
                               conds=["dm1_left_150Hz", "dm1_right_150Hz"]),
    # diagnostic: no junctions, but the 44 eLNs silenced (their outputs removed).
    # Tests whether the junction upgrade acts mainly by quieting the eLNs.
    "al_ln_eln_silenced": dict(scale=None, silence="eln",
                               conds=["dm1_left_150Hz", "dm1_right_150Hz"]),
}


def append_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, mode="a", header=not path.exists(), index=False)


def done_trials():
    if not TRIALS_CSV.exists():
        return set()
    d = pd.read_csv(TRIALS_CSV, usecols=["config", "condition", "seed_index", "trial"])
    return set(zip(d.config, d.condition, d.seed_index, d.trial))


def excite_for(cond, sets):
    spec = EXTRA[cond][0] if cond in EXTRA else C.CONDITIONS[cond][0]
    return {int(i): float(r) for s, r in spec for i in sets[s]}


def base_seed(cond):
    return EXTRA[cond][1] if cond in EXTRA else C.CONDITIONS[cond][1]


def al_groups(lab, table):
    """Index groups for the antennal-lobe read-outs."""
    upn = pd.read_csv(OUT / "upn_glomeruli.csv")
    g = {"eln": np.flatnonzero(S.eln_mask(lab))}
    for glom in ("DM1", "DA1"):
        for side, s in (("left", "L"), ("right", "R")):
            g[f"pn_{glom.lower()}_{s}"] = upn[(upn.glomerulus == glom) & (upn.side == side)].idx.to_numpy()
    g["pn_other"] = upn[~upn.glomerulus.isin(["DM1", "DA1"])].idx.to_numpy()
    return g


def extra_rows(res, groups, rows):
    dur = res.duration_ms * 1e-3
    for t, row in enumerate(rows):
        nu = res.neuron[res.trial == t]
        for name, idx in groups.items():
            row[name + "_hz"] = float(np.isin(nu, idx).sum() / (idx.size * dur))
    return rows


def run_chunk(brain, excite, seed, a, b, silence=()):
    """C.run_chunk (trials a..b-1 of ``seed``, identical to brain.run) plus an
    optional list of silenced root IDs."""
    if not len(silence):
        return C.run_chunk(brain, excite, seed, a, b)
    p = brain._params_for(None)
    ids = np.array(list(excite.keys()), np.int64)
    rates = np.array(list(excite.values()), float)
    exc_idx = brain.index_of(ids)
    n_steps = int(round(1000.0 / p["dt"]))
    prob = rates * p["dt"] * 1e-3
    seqs = np.random.SeedSequence(seed).spawn(b)[a:b]
    ev = [brain._poisson_events(np.random.default_rng(q), exc_idx, prob, n_steps) for q in seqs]
    return brain._run_events(ev, exc_idx, silence, n_steps, p, ())


def run_config(brain, name, cfg, lab, sets, rd, groups, table):
    silence = brain.root_ids[groups["eln"]] if cfg.get("silence") == "eln" else ()
    kappa_all = brain.gap_kappa.copy()
    if cfg.get("only"):
        brain.gap_kappa = np.where(table.cls.to_numpy() == cfg["only"], kappa_all, 0.0)
    brain._use_baseline_engine = cfg["scale"] is None
    brain.gap_scale = 1.0 if cfg["scale"] is None else float(cfg["scale"])
    done = done_trials()
    n_trials = cfg.get("n_trials", N_TRIALS)
    print(f"=== {name} (scale {cfg['scale']})", flush=True)
    for cond in cfg.get("conds", CONDS):
        excite = excite_for(cond, sets)
        for k in cfg.get("seeds", SEEDS):
            f = CNT / f"{name}__{cond}__s{k}.npz"
            if f.exists():
                continue
            counts = np.zeros(brain.n_neurons, np.int64)
            ts = time.perf_counter()
            for a in range(0, n_trials, CHUNK):
                part = CNT / f"_part_{name}__{cond}__s{k}__{a}.npy"
                if all((name, cond, k, t) in done for t in range(a, a + CHUNK)) and part.exists():
                    counts += np.load(part)
                    continue
                C.wait_for_ram()
                res = run_chunk(brain, excite, base_seed(cond) + k, a, a + CHUNK, silence)
                meta = dict(config=name, scale=cfg["scale"], condition=cond, seed_index=k,
                            seed=base_seed(cond) + k, trial0=a)
                rows, cnt = C.trial_rows(res, rd, meta)
                rows = extra_rows(res, groups, rows)
                del res
                np.save(part, cnt)
                append_csv(TRIALS_CSV, rows)
                counts += cnt
            nz = np.flatnonzero(counts)
            np.savez_compressed(f, nz_idx=nz.astype(np.int32), nz_count=counts[nz],
                                n_trials=n_trials)
            for a in range(0, n_trials, CHUNK):
                (CNT / f"_part_{name}__{cond}__s{k}__{a}.npy").unlink(missing_ok=True)
            d = pd.read_csv(TRIALS_CSV)
            d = d[(d.config == name) & (d.condition == cond) & (d.seed_index == k)]
            print(f"  {cond} s{k}: MN9 {d.mn9_hz.mean():.2f} Hz, runaway {int(d.runaway.sum())}/"
                  f"{len(d)}, KC/trial {d.kc_active.mean():.0f}, DNa02 L/R {d.DNa02_L.mean():.1f}/"
                  f"{d.DNa02_R.mean():.1f}, eLN {d.eln_hz.mean():.1f} Hz, other uPN "
                  f"{d.pn_other_hz.mean():.2f} Hz ({time.perf_counter() - ts:.0f} s)", flush=True)
    brain._use_baseline_engine = False
    brain.gap_kappa = kappa_all


def main(names):
    C.wait_for_ram(2.0)
    t0 = time.perf_counter()
    brain, table = G.build_gap_brain("al_ln_literature", n_threads=2, return_table=True)
    rid = brain.root_ids
    lab = S.neuron_table(rid)
    print(f"built in {time.perf_counter() - t0:.0f} s; kappa {brain.kappa_by_class}; "
          f"{len(table)} pairs", flush=True)
    (OUT / "run_info.json").write_text(json.dumps(dict(
        kappa=brain.kappa_by_class, n_pairs=int(len(table)),
        spike_area_mV_ms=brain.spike_area_mV_ms), indent=1))
    sets = C.input_sets(lab)
    ht, side = lab.hemibrain_type.to_numpy(), lab.side.to_numpy()
    for s in ("left", "right"):
        sets[f"da1_{s}"] = rid[(lab.cell_class.to_numpy() == "olfactory") & (ht == "ORN_DA1") & (side == s)]
    rd = C.Readout(brain, lab)
    groups = al_groups(lab, table)
    for name in names:
        run_config(brain, name, CONFIGS[name], lab, sets, rd, groups, table)
    del brain
    gc.collect()
    print("VALIDATION_DONE", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or list(CONFIGS))
