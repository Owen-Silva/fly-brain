"""Scorecard batch 1: run the 10 pre-registered real-fly tests on each model version.

Plain English
-------------
One Python process. For each model version it builds the whole brain ONCE, runs every
condition of docs/real-fly-scorecard-batch1.md section 1 (3 seeds x 30 trials x 1 s),
and saves each seed to its own file as soon as it finishes
(results/raw/<version>/<condition>_s<k>.npz). Files that already exist are skipped, so
a crash or a restart only loses the seed that was running.

Model versions
  none              the published model (sim/sign_fixes "none" = FastBrain("630")),
                    built as a GapBrain with NO electrical synapses so that test 5 can
                    give DN1a a steady current (GapBrain.set_test_current). Every other
                    condition runs on sim/fast_engine's own loop (run_baseline).
  al_ln_literature  the recommended sign fix, built with the Phase 7 gap junctions
                    (build_gap_brain). The junctions are used ONLY in the "gap" runs of
                    test 7; everything else runs without them (run_baseline, or for
                    test 5 the junction strength set to 0).

Usage:
  python experiments/scorecard_batch1/run_batch1.py [--variants none,al_ln_literature]
                                                    [--threads 2] [--only NAME,NAME]
"""

from __future__ import annotations

import argparse
import ctypes
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

RES = HERE / "results"
RAW = RES / "raw"
N_TRIALS = 30
SEEDS = (0, 1, 2)
DURATION_MS = 1000.0
IN_RUN_MIN_GB = 0.8

G = {k: [int(x) for x in v] for k, v in json.loads((RES / "groups.json").read_text()).items()}

#: Cells whose spikes are kept per trial (every read-out of every test).
KEY_GROUPS = ["FC2_read_pC1a", "FC2_read_pC1b", "FC2_read_pC1cde", "FC5_read_aSPg",
              "FC5_read_aSPf", "FC5_read_aSPh", "FC1_read_vpoDN", "SD4_read_DNa02",
              "SD4_read_DNa01", "TH3_read_VP3vPN", "TH3_read_DN1a", "TH2_read_VP2PN",
              "TH1_read_VP3PN", "OS4_read_DA1PN", "LL1_read_MBON01", "LL1_read_MBON02",
              "LL1_read_MBON0304", "LL1_read_MBON18", "LL1_read_MBON1617", "SD1_read_MDN",
              "TF4_read_Usnea", "TF4_read_Phantom", "TF4_read_Clavicle", "TF4_read_Fdg",
              "FC2_stim_SAG", "FC1_stim_vpoEN", "SD4_stim_PFL3", "LL1_stim_MBON11",
              "TH_stim_cool", "TH_stim_warm"]
KEY_IDS = list(dict.fromkeys(x for g in KEY_GROUPS for x in G[g]))

UPN_IDS = [int(x) for x in pd.read_csv(RES / "upn_glomeruli.csv").root_id]

DA1_ORN = set(G["OS4_stim_DA1_ORN"])
OS4_S = [(x, 10.0) for x in G["OS4_stim_allORN"]]
OS4_O = [(x, 50.0 if x in DA1_ORN else 10.0) for x in G["OS4_stim_allORN"]]


def stim(*pairs):
    """[(group, rate), ...] -> [(root_id, rate), ...], order kept (so paired conditions
    that start with the same groups get the same random input for them)."""
    out = []
    for grp, rate in pairs:
        out += [(x, float(rate)) for x in G[grp]]
    return out


READ_TH3 = ["TH3_read_DN1a", "TH3_read_VP3vPN"]
READ_TF4 = ["TF4_read_Usnea", "TF4_read_Phantom", "TF4_read_Clavicle", "TF4_read_Fdg"]
READ_LL1 = ["LL1_read_MBON01", "LL1_read_MBON02", "LL1_read_MBON0304", "LL1_read_MBON18",
            "LL1_read_MBON1617"]
READ_FC2 = ["FC2_read_pC1a", "FC2_read_pC1b", "FC2_read_pC1cde"]

# name: dict(excite=[(id, rate)], silence=[group], current={group: mV}, mode, record=[group],
#            base=seed base, seeds=..., variants=..., pn=save uPN spikes)
C = {
    "silent": dict(excite=[], base=0, seeds=(0,)),
    # 1 FC2
    "FC2_SAG": dict(excite=stim(("FC2_stim_SAG", 150)), record=READ_FC2, base=1000),
    # 2 FC5
    "FC5_DA1_150": dict(excite=stim(("FC5_stim_DA1_ORN", 150)), base=2000),
    "FC5_DA1_50": dict(excite=stim(("FC5_stim_DA1_ORN", 50)), base=2100),
    # 3 FC1 (A and C share the vpoEN input)
    "FC1_A_vpoEN": dict(excite=stim(("FC1_stim_vpoEN", 150)), record=["FC1_read_vpoDN"], base=3000),
    "FC1_B_pC1": dict(excite=stim(("FC1_stim_pC1", 150)), record=["FC1_read_vpoDN"], base=3100),
    "FC1_C_both": dict(excite=stim(("FC1_stim_vpoEN", 150), ("FC1_stim_pC1", 150)),
                       record=["FC1_read_vpoDN"], base=3000),
    # 4 SD4
    "SD4_PFL3_left": dict(excite=stim(("SD4_stim_PFL3_toL", 150)), base=4000),
    "SD4_PFL3_right": dict(excite=stim(("SD4_stim_PFL3_toR", 150)), base=4100),
    # 5 TH3 (T1 and T2 share the cool input); steady current into DN1a
    "TH3_T0_8mV": dict(excite=[], current={"TH3_read_DN1a": 8.0}, mode="current",
                       record=READ_TH3, base=5000),
    "TH3_T1_8mV": dict(excite=stim(("TH_stim_cool", 150)), current={"TH3_read_DN1a": 8.0},
                       mode="current", record=READ_TH3, base=5000),
    "TH3_T2_8mV": dict(excite=stim(("TH_stim_cool", 150)), current={"TH3_read_DN1a": 8.0},
                       silence=["TH3_read_VP3vPN"], mode="current", record=READ_TH3, base=5000),
    "TH3_T0_10mV": dict(excite=[], current={"TH3_read_DN1a": 10.0}, mode="current",
                        record=READ_TH3, base=5100),
    "TH3_T1_10mV": dict(excite=stim(("TH_stim_cool", 150)), current={"TH3_read_DN1a": 10.0},
                        mode="current", record=READ_TH3, base=5100),
    "TH3_T2_10mV": dict(excite=stim(("TH_stim_cool", 150)), current={"TH3_read_DN1a": 10.0},
                        silence=["TH3_read_VP3vPN"], mode="current", record=READ_TH3, base=5100),
    # demonstration only: Poisson background cannot be slowed by inhibition
    "TH3_demo_poisson_T0": dict(excite=stim(("TH3_read_DN1a", 23)), base=5200, seeds=(0,),
                                variants=("none",)),
    "TH3_demo_poisson_T1": dict(excite=stim(("TH3_read_DN1a", 23), ("TH_stim_cool", 150)),
                                base=5200, seeds=(0,), variants=("none",)),
    # 6 TH2 / TH1 (W and W+C share the warm input)
    "TH2_W": dict(excite=stim(("TH_stim_warm", 150)), record=["TH2_read_VP2PN"], base=6000),
    "TH2_WC": dict(excite=stim(("TH_stim_warm", 150), ("TH_stim_cool", 150)),
                   record=["TH2_read_VP2PN"], base=6000),
    "TH1_C": dict(excite=stim(("TH_stim_cool", 150)), base=6100),
    # 7 OS4 (the gap runs use the same input as the no-gap runs of the fix)
    "OS4_S": dict(excite=OS4_S, base=7000, pn=True),
    "OS4_O": dict(excite=OS4_O, base=7100, pn=True),
    "OS4_S_gap": dict(excite=OS4_S, base=7000, pn=True, mode="gap",
                      variants=("al_ln_literature",)),
    "OS4_O_gap": dict(excite=OS4_O, base=7100, pn=True, mode="gap",
                      variants=("al_ln_literature",)),
    # POST-HOC, NOT SCORED (added 21:00, after the pre-registered 10 Hz runs left the DA1
    # projection neurons of the fix model silent): the same test at 30 Hz spontaneous input,
    # DA1 at 150 Hz (the same 5x step), fix and fix + gap junctions only.
    "OS4post_S30": dict(excite=[(x, 30.0) for x in G["OS4_stim_allORN"]], base=7200, pn=True,
                        variants=("al_ln_literature",)),
    "OS4post_O30": dict(excite=[(x, 150.0 if x in DA1_ORN else 30.0) for x in G["OS4_stim_allORN"]],
                        base=7300, pn=True, variants=("al_ln_literature",)),
    "OS4post_S30_gap": dict(excite=[(x, 30.0) for x in G["OS4_stim_allORN"]], base=7200, pn=True,
                            mode="gap", variants=("al_ln_literature",)),
    "OS4post_O30_gap": dict(excite=[(x, 150.0 if x in DA1_ORN else 30.0)
                                    for x in G["OS4_stim_allORN"]],
                            base=7300, pn=True, mode="gap", variants=("al_ln_literature",)),
    # 8 LL1 (O and O+M share the odour input)
    "LL1_O": dict(excite=stim(("LL1_odourA_ORN", 100)), record=READ_LL1, base=8000),
    "LL1_OM": dict(excite=stim(("LL1_odourA_ORN", 100), ("LL1_stim_MBON11", 150)),
                   record=READ_LL1, base=8000),
    # 9 SD1 / SD2
    "SD1_LC16_both_100": dict(excite=stim(("SD1_stim_LC16", 100)), record=["SD1_read_MDN"],
                              base=9000),
    "SD1_LC16_both_50": dict(excite=stim(("SD1_stim_LC16", 50)), base=9100),
    "SD2_LC16_left_100": dict(excite=stim(("SD2_stim_LC16_L", 100)), base=9200),
    "SD2_LC16_right_100": dict(excite=stim(("SD2_stim_LC16_R", 100)), base=9300),
    # 10 TF4
    "TF4_water": dict(excite=stim(("TF4_stim_water", 150)), record=READ_TF4, base=10000),
    "TF4_sugar": dict(excite=stim(("TF4_stim_sugar", 150)), record=READ_TF4, base=10100),
}


#: Published-model runaway conditions that were already run with 3 seeds before the
#: one-seed time rule (kept as they are).
LEGACY_3_SEEDS = {"FC5_DA1_150", "FC5_DA1_50", "TH3_T1_8mV", "TH3_T2_8mV", "TH3_T1_10mV",
                  "TH3_T2_10mV"}


def free_ram_gb():
    class MEMSTAT(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEMSTAT()
    m.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2**30


def wait_for_ram(min_gb=1.5):
    while free_ram_gb() < min_gb:
        print(f"    free RAM {free_ram_gb():.2f} GB < {min_gb} GB, waiting 30 s", flush=True)
        time.sleep(30)


def build(variant, lab, n_threads):
    from sim.gap_junctions import build_gap_brain
    if variant == "none":
        b = build_gap_brain(fix="none", classes=(), lab=lab, n_threads=n_threads)
    elif variant == "al_ln_literature":
        b = build_gap_brain(fix="al_ln_literature", lab=lab, n_threads=n_threads)
    else:
        raise ValueError(variant)
    return b


def max_neurons_per_10ms(res):
    """Per trial: the largest number of different neurons firing in one 10 ms slice."""
    out = np.zeros(res.n_trials, np.int64)
    slice_steps = int(round(10.0 / res.dt_ms))
    n = int(res.root_ids.size)
    for t in range(res.n_trials):
        m = res.trial == t
        if not m.any():
            continue
        key = (res.step[m].astype(np.int64) // slice_steps) * n + res.neuron[m]
        u = np.unique(key)
        out[t] = np.bincount(u // n).max()
    return out


def run_one(brain, variant, name, spec, k, sd, out):
    ex = spec.get("excite", [])
    excite = {rid: rate for rid, rate in ex}
    silence = [x for g in spec.get("silence", []) for x in G[g]]
    record = [x for g in spec.get("record", []) for x in G[g]]
    mode = spec.get("mode", "plain")
    kw = dict(excite=excite, silence=silence, duration_ms=DURATION_MS, n_trials=N_TRIALS,
              seed=sd, record_v=record)
    t0 = time.perf_counter()
    if mode == "plain":
        res = brain.run_baseline(**kw)
    elif mode == "current":
        cur = {x: mv for g, mv in spec["current"].items() for x in G[g]}
        saved = brain.gap_scale
        brain.gap_scale = 0.0            # junctions (if any) off: pure test current
        brain.set_test_current(cur)
        try:
            res = brain.run(**kw)
        finally:
            brain.set_test_current({})
            brain.gap_scale = saved
    elif mode == "gap":
        if brain.gap_a.size == 0:
            raise RuntimeError("gap run on a brain without junctions")
        saved = brain.gap_scale
        brain.gap_scale = 1.0
        try:
            res = brain.run(**kw)
        finally:
            brain.gap_scale = saved
    else:
        raise ValueError(mode)
    wall = time.perf_counter() - t0

    counts = np.bincount(res.neuron, minlength=brain.n_neurons)
    nz = np.flatnonzero(counts)
    key_idx = brain.index_of(KEY_IDS)
    pos = np.full(brain.n_neurons, -1, np.int64)
    pos[key_idx] = np.arange(key_idx.size)
    kp = pos[res.neuron]
    km = kp >= 0
    key_trials = np.zeros((key_idx.size, N_TRIALS), np.int32)
    np.add.at(key_trials, (kp[km], res.trial[km]), 1)
    extra = {}
    if record:
        extra["rec_ids"] = np.array(record, np.int64)
        extra["v_mean"] = np.stack([res.voltages_mV[int(r)].mean(axis=1) for r in record])
    if spec.get("pn"):
        up_idx = brain.index_of(UPN_IDS)
        upos = np.full(brain.n_neurons, -1, np.int64)
        upos[up_idx] = np.arange(up_idx.size)
        up = upos[res.neuron]
        m = up >= 0
        extra["pn_trial"] = res.trial[m].astype(np.int16)
        extra["pn_col"] = up[m].astype(np.int16)
        extra["pn_step"] = res.step[m].astype(np.int32)
    mx = max_neurons_per_10ms(res)
    np.savez_compressed(out, key_ids=np.array(KEY_IDS, np.int64), key_trials=key_trials,
                        nz_idx=nz.astype(np.int32), nz_count=counts[nz].astype(np.int64),
                        per_trial_total=np.bincount(res.trial, minlength=N_TRIALS),
                        max_per_10ms=mx, reached=np.array(res.neurons_reached),
                        seed=sd, wall_s=wall, **extra)
    n_run = int((mx > 1500).sum())
    if variant == "none" and k == 0 and n_run >= 0.9 * N_TRIALS:
        # Time rule added at 20:28 (after 18 of 18 published-model seeds with >= 90%
        # runaway had come out alike): a runaway condition of the published model gets
        # ONE seed; the other seeds are skipped and listed in skipped_seeds.txt.
        with open(out.parent / "skipped_seeds.txt", "a", encoding="utf-8") as fh:
            fh.write(f"{name}: seed 0 had {n_run}/{N_TRIALS} runaway trials; "
                     "seeds 1-2 skipped" + chr(10))
    print(f"  [{variant}] {name} seed {sd}: {int(counts.sum())} spikes, "
          f"{nz.size} neurons fired, runaway trials {n_run}/{N_TRIALS}, {wall:.1f} s",
          flush=True)
    del res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="none,al_ln_literature")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = [x for x in a.only.split(",") if x]
    manifest = {k: {kk: (vv if kk != "excite" else f"{len(vv)} neurons, rates "
                         f"{sorted(set(r for _, r in vv))}")
                    for kk, vv in v.items()} for k, v in C.items()}
    (RES / "conditions.json").write_text(json.dumps(manifest, indent=1, default=str),
                                         encoding="utf-8")
    from sim import sign_fixes as S
    wait_for_ram()
    from sim.fast_engine import REFERENCE_DIR, SNAPSHOTS
    root_ids = pd.read_csv(REFERENCE_DIR / SNAPSHOTS["630"][0], index_col=0).index.to_numpy()
    lab = S.neuron_table(root_ids)
    del root_ids
    gc.collect()
    for variant in a.variants.split(","):
        todo = [(n, s) for n, s in C.items()
                if variant in s.get("variants", ("none", "al_ln_literature"))
                and (not only or n in only)]
        out_dir = RAW / variant
        out_dir.mkdir(parents=True, exist_ok=True)
        missing = [(n, s) for n, s in todo
                   if any(not (out_dir / f"{n}_s{k}.npz").exists()
                          for k in range(len(s.get("seeds", SEEDS))))]
        if not missing:
            print(f"=== {variant}: nothing to do", flush=True)
            continue
        wait_for_ram()
        t0 = time.perf_counter()
        brain = build(variant, lab, a.threads)
        try:
            import pyarrow as pa
            pa.default_memory_pool().release_unused()
        except Exception:  # noqa: BLE001
            pass
        gc.collect()
        cfg = dict(variant=variant, snapshot=brain.snapshot, n_trials=N_TRIALS, seeds=list(SEEDS),
                   duration_ms=DURATION_MS, gap_pairs=int(brain.gap_a.size),
                   gap_kappa=getattr(brain, "kappa_by_class", {}),
                   build_s=round(time.perf_counter() - t0, 1))
        (out_dir / "config.json").write_text(json.dumps(cfg, indent=1, default=str),
                                             encoding="utf-8")
        print(f"=== {variant}: built in {cfg['build_s']} s ({cfg['gap_pairs']} junction pairs); "
              f"free RAM {free_ram_gb():.2f} GB", flush=True)
        for name, spec in missing:
            for k in range(len(spec.get("seeds", SEEDS))):
                f = out_dir / f"{name}_s{k}.npz"
                if f.exists():
                    continue
                skip = out_dir / "skipped_seeds.txt"
                if k > 0 and skip.exists() and any(
                        ln.startswith(name + ":") for ln in skip.read_text().splitlines()):
                    continue
                if (k > 0 and variant == "none" and name not in LEGACY_3_SEEDS
                        and (out_dir / f"{name}_s0.npz").exists()):
                    z0 = np.load(out_dir / f"{name}_s0.npz")
                    if (z0["max_per_10ms"] > 1500).sum() >= 0.9 * N_TRIALS:
                        continue
                wait_for_ram(IN_RUN_MIN_GB)
                sd = spec["base"] + spec.get("seeds", SEEDS)[k]
                run_one(brain, variant, name, spec, k, sd, f)
        print(f"=== {variant}: done in {time.perf_counter() - t0:.0f} s", flush=True)
        del brain
        gc.collect()


if __name__ == "__main__":
    main()
