"""Phase 8 whole-brain conditioning again, now with the neuromodulator fixes (Phase 7 item 5).

Plain English
-------------
Phase 8 found that in the whole brain (fix "al_ln_literature") a smell alone makes the
"punishment" dopamine neurons PPL1-γ1pedc (PPL101) fire more than the artificial punishment
does, so punishment learning could not be read out. The biggest outside push came from
SMP384 and SMP504, which the model treats as fast excitatory cells although the literature
calls both serotonergic (docs/phase7-neuromodulators.md). This script repeats the Phase 8
whole-brain experiments on the two new brains from sim/sign_fixes.py:

  da_modulatory      = "al_ln_literature+da_modulatory"     (dopamine cells: no fast output)
  da_5ht_modulatory  = "al_ln_literature+da_5ht_modulatory" (dopamine + serotonin cells)
  da_5ht_literature  = "al_ln_literature+da_5ht_literature" (the same, but only cells whose
                       transmitter is known from the literature; added after the first two
                       lowered water -> MN9, see docs/phase7-neuromodulators.md)

Everything else is exactly Phase 8: the same learning rule and calibrated numbers
(experiments/phase8/results/calibration.json), the same odors, rates, protocols, seeds and
read-outs (functions imported from experiments/phase8/run_phase8.py, not copied).

One technical point. sim/plasticity.py needs the 305 mushroom-body dopamine neurons' own
connections to know how much of each cell's dopamine goes to each brain half, and it
switches their outputs off itself ("modulatory" mode). So for the learning runs the brain
is built with those 305 cells' connections kept (``keep_outputs``); the ``equiv`` stage
checks, spike for spike, that this gives the same activity as the brain with them removed.

Stages (python run_aversive.py <stage> <variant> [conditions]):
  equiv  <variant>   spike-for-spike check described above (2 sniffs, learning off)
  trace  <variant>   what drives PPL101 during a sniff (3 seeds x 2 odors, learning off)
  cond   <variant>   conditioning, 3 seeds; default conditions = CONDS below
  trace_diag <diag>  trace on a diagnostic brain (DIAGS; not a new fix): which removed cells
                     matter for PPL101?
  trace_type <variant> <TYPE>  the same trace for another DAN type (e.g. PPL102)
  regression <variant>  Phase 8's sugar -> MN9 check with learning on (results/regression_<v>.csv)
Several stages can be chained: run_aversive.py trace da_5ht_modulatory cond da_5ht_modulatory
Results (appended as they come; every stage resumes): results/equiv_<v>.json,
results/trace_ppl1_<v>.csv, results/cond_<v>.csv, _misc.csv, _weights.csv.
"""

from __future__ import annotations

import gc
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "phase8"))
from common import N_THREADS, ORN_RATE_HZ, odor_input_rows, type_rows, wait_for_ram  # noqa: E402
from run_phase8 import (CONDITIONS, TEST_MS, WINDOW, Readout, load_calibration,  # noqa: E402
                        rule_from, run_sequence)
from sim import sign_fixes as S  # noqa: E402
from sim.plasticity import DAN_COMPARTMENTS, PlasticBrain, load_labels, mb_circuit_rows  # noqa: E402

RES = HERE / "results"
RES.mkdir(exist_ok=True)
VARIANTS = {"da_modulatory": "al_ln_literature+da_modulatory",
            "da_5ht_modulatory": "al_ln_literature+da_5ht_modulatory",
            "da_5ht_literature": "al_ln_literature+da_5ht_literature",
            "alln": "al_ln_literature"}
SEEDS = [0, 1, 2]
CONDS = ["aversive_paired", "aversive_paired_recip", "aversive_unpaired", "aversive_backward",
         "odor_only", "dan_only", "no_training", "appetitive_paired", "appetitive_unpaired"]
DAN_TYPES = ("PPL101", "PAM01", "PAM02", "PAM11", "PPL105")

_cache = {}


def labels():
    if "labels" not in _cache:
        _cache["labels"] = load_labels()
        rid = _cache["labels"].root_id.to_numpy(np.int64)
        _cache["lab_nt"] = S.neuron_table(rid)
    return _cache["labels"]


def compartment_dan_ids(lab):
    cc, hb = lab.cell_class.to_numpy(), lab.hemibrain_type.to_numpy()
    m = (cc == "DAN") & np.isin(hb, list(DAN_COMPARTMENTS))
    return lab.root_id.to_numpy(np.int64)[m]


def build(variant, keep=True, dan_mode="modulatory"):
    """PlasticBrain for ``variant``. keep=True: the 305 compartment DANs keep their
    connections in the file (plasticity switches their outputs off itself)."""
    _cache.pop("pb", None)
    gc.collect()
    wait_for_ram()
    lab = labels()
    fix = VARIANTS[variant]
    keep_ids = compartment_dan_ids(lab) if (keep and fix in S.NEUROMOD_FIXES) else None
    t0 = time.perf_counter()
    brain, rep = S.build_brain(fix, n_threads=N_THREADS, return_report=True,
                               lab=_cache["lab_nt"], keep_outputs=keep_ids)
    pb = PlasticBrain(brain, lab, rule_from(load_calibration()), dan_mode=dan_mode)
    print(f"built {variant} (keep={keep}, {dan_mode}) in {time.perf_counter() - t0:.0f} s: "
          f"{rep.summary()}", flush=True)
    return pb, rep


def sniff(pb, od, seed):
    """The first test sniff of the conditioning runs (same input and seed), learning off."""
    odors = odor_input_rows(labels(), "orn")
    rng_seed = [seed, 1, 0, 0 if od == "A" else 1]
    return pb.run([(odors[od], ORN_RATE_HZ, 0.0, 1000.0)], TEST_MS, rng_seed, plastic=False)


def stage_equiv(variant):
    out = RES / f"equiv_{variant}.json"
    if out.exists():
        print(out.read_text())
        return
    runs = {}
    pb, _ = build(variant, keep=False, dan_mode="fast")      # 305 DANs removed from the file
    for od in ("A", "B"):
        r = sniff(pb, od, 0)
        runs[od] = (r.step.copy(), r.neuron.copy())
    del pb
    gc.collect()
    pb, _ = build(variant, keep=True, dan_mode="modulatory")  # kept, silenced at run time
    _cache["pb"] = (variant, pb)
    res = {}
    for od in ("A", "B"):
        r = sniff(pb, od, 0)
        same = (np.array_equal(r.step, runs[od][0]) and np.array_equal(r.neuron, runs[od][1]))
        res[od] = dict(identical=bool(same), spikes_removed_brain=int(runs[od][0].size),
                       spikes_kept_brain=int(r.step.size))
    out.write_text(json.dumps(res, indent=1))
    print(f"equiv {variant}: {res}", flush=True)


def get_pb(variant):
    if "pb" in _cache and _cache["pb"][0] == variant:
        return _cache["pb"][1]
    pb, _ = build(variant, keep=True, dan_mode="modulatory")
    _cache["pb"] = (variant, pb)
    return pb


def stage_trace(variant):
    """Same method as experiments/phase8/trace_ppl1.py, on this brain."""
    if (RES / f"trace_ppl1_{variant}.csv").exists():
        print(f"trace_ppl1_{variant}.csv exists")
        return
    _trace(get_pb(variant), variant)


#: Diagnostic brains (trace only; NOT new fixes): which removed cells matter?
DIAGS = ("alln_minus_smp384_smp504", "da_5ht_literature_only")


def stage_trace_diag(diag):
    """al_ln_literature with only some outputs removed, built here from the arrays:
    alln_minus_smp384_smp504: only the 4 SMP384/SMP504 cells lose their outputs;
    da_5ht_literature_only: only cells whose dopamine/serotonin identity comes from the
    literature (not from the prediction). The 305 compartment DANs are kept in the file and
    switched off by plasticity's modulatory mode, as in the other runs."""
    from sim.fast_engine import FastBrain
    tag = f"diag_{diag}"
    if (RES / f"trace_ppl1_{tag}.csv").exists():
        print(f"trace_ppl1_{tag}.csv exists")
        return
    _cache.pop("pb", None)
    gc.collect()
    wait_for_ram()
    lab = labels()
    nt = _cache["lab_nt"]
    rid, pre, post, signed = S.load_reference_arrays()
    p0, q0, s0, _ = S.apply_fix("al_ln_literature", rid, pre, post, signed, nt)
    del pre, post, signed
    sign0 = S.neuron_signs(len(rid), p0, s0)
    if diag == "alln_minus_smp384_smp504":
        hb = lab.hemibrain_type.to_numpy()
        target = np.isin(hb, ["SMP384", "SMP504"])
    else:
        _, ev = S.monoamine_of(nt)
        target = S.modulatory_mask(nt, sign0, ("dopamine", "serotonin")) & (ev == "literature")
    target &= ~np.isin(rid, compartment_dan_ids(lab))
    keep = ~target[p0]
    brain = FastBrain.from_arrays(rid, p0[keep], q0[keep], s0[keep], n_threads=N_THREADS)
    del p0, q0, s0
    print(f"{tag}: outputs removed for {int(target.sum())} cells "
          f"({int((~keep).sum())} connections)", flush=True)
    pb = PlasticBrain(brain, lab, rule_from(load_calibration()), dan_mode="modulatory")
    _trace(pb, tag)
    del pb, brain
    gc.collect()


def _trace(pb, variant, target_type="PPL101"):
    tag = "ppl1" if target_type == "PPL101" else target_type.lower()
    col = "ppl101_spikes" if target_type == "PPL101" else f"{tag}_spikes"
    out = RES / f"trace_{tag}_{variant}.csv"
    lab = labels()
    b = pb.brain
    target = type_rows(lab, target_type)
    pre_of_edge = np.repeat(np.arange(b.n_neurons), np.diff(b._indptr))
    m = np.isin(b._post, target)
    e_pre, e_cnt = pre_of_edge[m], b._count[m].astype(np.int64)
    e_cnt = np.where(np.isin(e_pre, pb.dan_rows), 0, e_cnt)    # silenced in modulatory mode
    in_circ = np.isin(e_pre, mb_circuit_rows(lab))
    typ = lab.hemibrain_type.fillna("").to_numpy()
    ctype = lab.cell_type.fillna("").to_numpy()
    cls = lab.cell_class.fillna("").to_numpy()
    name = np.where(typ[e_pre] != "", typ[e_pre], ctype[e_pre])
    name = np.where(name != "", name, "untyped")
    rows, sn = [], []
    for od in ("A", "B"):
        for seed in SEEDS:
            res = sniff(pb, od, seed)
            s0, s1 = int(WINDOW[0] / res.dt_ms), int(WINDOW[1] / res.dt_ms)
            w = (res.step >= s0) & (res.step < s1)
            c = np.bincount(res.neuron[w], minlength=b.n_neurons)
            drive = c[e_pre] * e_cnt
            kc = c[pb.kc_rows]
            sn.append(dict(odor=od, seed=seed, **{col: int(c[target].sum())},
                           net_input=int(drive.sum()),
                           outside_circuit=int(drive[~in_circ].sum()),
                           kc_frac=float((kc > 0).mean()), total_spikes=int(w.sum())))
            print(f"  {variant} odor {od} seed {seed}: {sn[-1]}", flush=True)
            rows.append(pd.DataFrame(dict(odor=od, seed=seed, input_type=name,
                                          input_class=cls[e_pre], in_circuit=in_circ,
                                          synapses=e_cnt, pre_spikes=c[e_pre], drive=drive)))
    pd.DataFrame(sn).to_csv(RES / f"sniff_{tag}_{variant}.csv", index=False)
    d = pd.concat(rows)
    g = (d.groupby(["input_type", "input_class", "in_circuit"])
         .agg(n_links=("synapses", "size"), synapses=("synapses", "sum"),
              drive_per_sniff=("drive", "sum")).reset_index())
    g[["n_links", "synapses", "drive_per_sniff"]] /= 6.0
    g = g.sort_values("drive_per_sniff", ascending=False)
    g.to_csv(out, index=False)
    print(g.head(10).to_string(index=False), flush=True)


def stage_trace_type(variant, target_type):
    """The same trace for another dopamine-neuron type (e.g. PPL102 = PPL1-γ1)."""
    if (RES / f"trace_{target_type.lower()}_{variant}.csv").exists():
        print(f"trace_{target_type.lower()}_{variant}.csv exists")
        return
    _trace(get_pb(variant), variant, target_type)


def stage_regression(variant, seeds=(0, 1, 2), n_trials=10):
    """Phase 8's sugar -> MN9 check with learning ON (experiments/phase8/run_phase8.py
    regression(), modulatory mode): does learning change anything during sugar input?
    Compares, spike for spike, the learning-on run with the plain engine on the same brain
    and the same random input, and records every change in KC -> MBON strength."""
    out = RES / f"regression_{variant}.csv"
    if out.exists():
        print(f"{out.name} exists")
        return
    sys.path.insert(0, str(ROOT / "experiments" / "phase5" / "competition"))
    from phase5_common import paper_ids
    ids = paper_ids()
    pb = get_pb(variant)
    brain = pb.brain
    sugar = brain.index_of(ids["SUGAR"])
    mn9 = brain.index_of([ids["MN9"], ids["MN9_IPSI"]])
    rows = []
    for rate in (100.0, 200.0):
        for sd in seeds:
            st = pb.new_state()
            for t in range(n_trials):
                n_steps = 10000
                ev = pb.make_events([(sugar, rate, 0.0, 1000.0)], n_steps,
                                    np.random.default_rng([sd, t, int(rate)]))
                steps = np.repeat(np.arange(n_steps), np.diff(ev[0]))
                base = brain.run_with_input_events([(steps, brain.root_ids[ev[1]])],
                                                   excite=brain.root_ids[sugar],
                                                   duration_ms=1000.0)
                before = st.wk.copy()
                r = pb.run(None, 1000.0, None, state=st, events=ev, excite_rows=sugar)
                rows.append(dict(
                    variant=variant, rate=rate, seed=sd, trial=t,
                    base_mn9=int((base.neuron == mn9[0]).sum()),
                    learning_mn9=int((r.neuron == mn9[0]).sum()),
                    base_spikes=int(base.step.size), learning_spikes=int(r.step.size),
                    identical=bool(np.array_equal(r.step, base.step)
                                   and np.array_equal(r.neuron, base.neuron)),
                    max_weight_change=float(np.max(np.abs(st.wk / pb.wk0 - 1.0))),
                    trial_weight_change=float(np.max(np.abs(st.wk / before - 1.0)))))
            d = pd.DataFrame(rows)
            x = d[(d.rate == rate) & (d.seed == sd)]
            print(f"  sugar {rate:.0f} Hz seed {sd}: MN9 base {x.base_mn9.mean():.1f} / learning "
                  f"{x.learning_mn9.mean():.1f} Hz; identical {int(x.identical.sum())}/{len(x)}; "
                  f"max weight change {x.max_weight_change.max():.2e}", flush=True)
            d.to_csv(out, index=False)


def stage_cond(variant, conds):
    pb = get_pb(variant)
    lab = labels()
    ro = Readout(pb, lab)
    odors = odor_input_rows(lab, "orn")
    dan_rows_of = {d: type_rows(lab, d) for d in DAN_TYPES}
    f_main, f_misc, f_w = (RES / f"cond_{variant}.csv", RES / f"cond_{variant}_misc.csv",
                           RES / f"cond_{variant}_weights.csv")
    done = set()
    if f_w.exists():
        d = pd.read_csv(f_w)
        done = set(zip(d.condition, d.seed))
    todo = [(c, s) for c in conds for s in SEEDS if (c, s) not in done]
    print(f"cond {variant}: rule {pb.rule}; {len(todo)} sequences to run", flush=True)
    lock = threading.Lock()

    def job(cs):
        c, s = cs
        t0 = time.perf_counter()
        rows, misc, w_rows = run_sequence(pb, lab, ro, odors, dan_rows_of, ORN_RATE_HZ, c, s)
        with lock:
            pd.DataFrame(rows, columns=["condition", "seed", "phase", "rep", "odor",
                                        "mbon_type", "drive_mV", "spikes_per_cell"]).to_csv(
                f_main, mode="a", header=not f_main.exists(), index=False)
            pd.DataFrame(misc).to_csv(f_misc, mode="a", header=not f_misc.exists(), index=False)
            pd.DataFrame(w_rows, columns=["condition", "seed", "mbon_type", "rel_w_after_train",
                                          "rel_w_end"]).to_csv(
                f_w, mode="a", header=not f_w.exists(), index=False)
        d = pd.DataFrame(rows, columns=["c", "s", "phase", "rep", "odor", "t", "drive", "spk"])
        r = CONDITIONS[c]["readout"]
        x = d[d.t == r].groupby(["phase", "odor"]).drive.mean()
        print(f"  {c} seed {s}: {r} drive A {x['pre', 'A']:.0f}->{x['post', 'A']:.0f}, "
              f"B {x['pre', 'B']:.0f}->{x['post', 'B']:.0f}  ({time.perf_counter() - t0:.0f} s)",
              flush=True)

    with ThreadPoolExecutor(N_THREADS) as pool:
        list(pool.map(job, todo))


STAGE_NAMES = ("equiv", "trace", "trace_diag", "trace_type", "regression", "cond")


def main(argv):
    i = 0
    while i < len(argv):
        st, variant = argv[i], argv[i + 1]
        i += 2
        conds = CONDS
        if i < len(argv) and argv[i] not in STAGE_NAMES:
            conds = argv[i].split(",")
            i += 1
        print(f"=== {st} {variant} ===", flush=True)
        {"equiv": lambda: stage_equiv(variant), "trace": lambda: stage_trace(variant),
         "trace_diag": lambda: stage_trace_diag(variant),
         "trace_type": lambda: stage_trace_type(variant, conds[0]),
         "regression": lambda: stage_regression(variant),
         "cond": lambda: stage_cond(variant, conds)}[st]()
    print("AVERSIVE_BATCH_DONE", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
