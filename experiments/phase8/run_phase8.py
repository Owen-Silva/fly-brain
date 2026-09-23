"""Phase 8 experiments: conditioning the simulated mushroom body.

Plain English
-------------
Each "fly" (one random seed) goes through a real conditioning experiment:

1. Before training: odor A and odor B are each presented 4 times (1 s each,
   in alternation) and we record how strongly every output neuron type
   (MBON) is driven by the Kenyon cells, and how many spikes it fires.
2. Training: depends on the condition (below).
3. After training: the same 4 + 4 test presentations (new random input).

Learning is ON the whole time (also during the tests), exactly as in a real
fly. The main read-out is the "KC drive" of an output neuron: the total
input it receives from Kenyon cells during the odor (Kenyon cell spikes x the
current synapse strengths). It is the model's version of the synaptic current
that Hige et al. 2015 measured (it fell by 90% after pairing). Spikes are
also recorded, but in the mushroom-body-only circuit most output neurons
barely fire (see docs/phase8-learning.md).

Conditions (DAN = dopamine neuron; "pulses" = four light pulses at 2 Hz
starting 0.2 s after odor onset, as in Hige 2015):
  aversive_paired        A + PPL1-gamma1pedc (PPL101) pulses; then B alone
  aversive_paired_recip  the same with the odors swapped (B paired, A alone)
  aversive_unpaired      PPL101 pulses alone; A alone; B alone (separate trials)
  aversive_backward      PPL101 pulses first; A starts 0.5 s after the last pulse; B alone
  odor_only              A alone; B alone (no dopamine: the "no-DAN" control)
  dan_only               PPL101 pulses alone, no odor
  no_training            nothing (effect of the test presentations themselves)
  appetitive_paired      A + PAM-gamma5 (PAM01) + PAM-beta'2a (PAM02) pulses; B alone
  appetitive_unpaired    PAM01+PAM02 pulses alone; A alone; B alone
  alpha1_paired          A + PAM-alpha1 (PAM11) pulses; B alone
  alpha2_short           A + PPL1-alpha'2alpha2 (PPL105) pulses (1 s); B alone
  alpha2_long            A for 60 s with 120 PPL105 pulses; B alone for 60 s

Usage (one stage per call; everything is saved as it goes and resumes):
  python run_phase8.py calibrate
  python run_phase8.py conditioning <circuit|brain_alln|brain_eln|brain_none|brain_ln53> <modulatory|fast> [seeds] [conditions]
  python run_phase8.py regression <brain_alln|brain_eln|brain_none|brain_ln53>
"""

from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from common import (N_THREADS, ORN_RATE_HZ, PN_RATE_HZ, RES, get_model, odor_input_rows,
                    type_rows, wait_for_ram)
from sim.plasticity import HIGE_PULSES_MS, LearningRule, pulse_blocks

N_TEST = 4
TEST_MS = 1200.0
WINDOW = (0.0, 1100.0)
H = HIGE_PULSES_MS


# ---------------------------------------------------------------------------
# protocols
# ---------------------------------------------------------------------------
def paired(od, dans, on=0.0, off=1000.0, pulses=H, dur=2500.0):
    return dict(odor=od, on=on, off=off, pulses=tuple(pulses), dans=dans, dur=dur)


def alone(od, off=1000.0, dur=2500.0):
    return dict(odor=od, on=0.0, off=off, pulses=(), dans=(), dur=dur)


def dan_alone(dans):
    return dict(odor=None, on=0.0, off=0.0, pulses=H, dans=dans, dur=2500.0)


def backward(od, dans):
    return paired(od, dans, on=2200.0, off=3200.0, dur=3500.0)


PPL = ("PPL101",)
PAM_APP = ("PAM01", "PAM02")
LONG_PULSES = tuple(200.0 + 500.0 * i for i in range(120))
CONDITIONS = {
    "aversive_paired": dict(readout="MBON11", train=[paired("A", PPL), alone("B")]),
    "aversive_paired_recip": dict(readout="MBON11", train=[paired("B", PPL), alone("A")]),
    "aversive_unpaired": dict(readout="MBON11", train=[dan_alone(PPL), alone("A"), alone("B")]),
    "aversive_backward": dict(readout="MBON11", train=[backward("A", PPL), alone("B")]),
    "odor_only": dict(readout="MBON11", train=[alone("A"), alone("B")]),
    "dan_only": dict(readout="MBON11", train=[dan_alone(PPL)]),
    "no_training": dict(readout="MBON11", train=[]),
    "appetitive_paired": dict(readout="MBON01", train=[paired("A", PAM_APP), alone("B")]),
    "appetitive_unpaired": dict(readout="MBON01",
                                train=[dan_alone(PAM_APP), alone("A"), alone("B")]),
    "alpha1_paired": dict(readout="MBON07", train=[paired("A", ("PAM11",)), alone("B")]),
    "alpha2_short": dict(readout="MBON18", train=[paired("A", ("PPL105",)), alone("B")]),
    "alpha2_long": dict(readout="MBON18",
                        train=[paired("A", ("PPL105",), off=60000.0, pulses=LONG_PULSES,
                                      dur=60500.0),
                               alone("B", off=60000.0, dur=60500.0)]),
}
MAIN = [c for c in CONDITIONS if c != "alpha2_long"]


# ---------------------------------------------------------------------------
# read-outs
# ---------------------------------------------------------------------------
class Readout:
    """Fast per-trial read-outs for one PlasticBrain."""

    def __init__(self, pb, lab):
        self.pb = pb
        t = pb.plastic_table
        self.types = sorted(t.mbon_type.unique())
        code = {k: i for i, k in enumerate(self.types)}
        self.pt_kc = t.kc_row.to_numpy()
        self.pt_w = t.wk_index.to_numpy()
        self.pt_code = t.mbon_type.map(code).to_numpy()
        hb = lab.hemibrain_type.to_numpy()
        cc = lab.cell_class.to_numpy()
        self.mbon_rows = np.flatnonzero((cc == "MBON") & np.isin(hb, self.types))
        self.mbon_code = np.array([code[h] for h in hb[self.mbon_rows]])
        self.n_cells = np.bincount(self.mbon_code, minlength=len(self.types))
        self.dan_rows = np.flatnonzero(cc == "DAN")
        self.dan_types = hb[self.dan_rows]
        self.kc_rows = pb.kc_rows

    def __call__(self, res, wk_before):
        s0, s1 = int(WINDOW[0] / res.dt_ms), int(WINDOW[1] / res.dt_ms)
        m = (res.step >= s0) & (res.step < s1)
        c = np.bincount(res.neuron[m], minlength=self.pb.n_neurons)
        drive = np.bincount(self.pt_code, weights=c[self.pt_kc] * wk_before[self.pt_w] * 1e3,
                            minlength=len(self.types))            # mV (sum of g jumps)
        spk = np.bincount(self.mbon_code, weights=c[self.mbon_rows],
                          minlength=len(self.types)) / self.n_cells
        kc = c[self.kc_rows]
        dan = pd.Series(c[self.dan_rows], index=self.dan_types).groupby(level=0).sum()
        return drive, spk, dict(kc_frac=float((kc > 0).mean()), kc_spikes=int(kc.sum()),
                                total_spikes=int(res.step.size), touched=res.n_touched,
                                dan=";".join(f"{k}:{v}" for k, v in dan[dan > 0].items()))


# ---------------------------------------------------------------------------
# one simulated fly
# ---------------------------------------------------------------------------
def run_sequence(pb, lab, ro, odors, dan_rows_of, rate, cond, seed, n_test=N_TEST):
    spec = CONDITIONS[cond]
    state = pb.new_state()
    rows, misc = [], []

    def test(phase, rep, od):
        rng_seed = [seed, 1 if phase == "pre" else 2, rep, 0 if od == "A" else 1]
        before = state.wk.copy()
        res = pb.run([(odors[od], rate, 0.0, 1000.0)], TEST_MS, rng_seed, state=state)
        drive, spk, info = ro(res, before)
        for i, t in enumerate(ro.types):
            rows.append((cond, seed, phase, rep, od, t, drive[i], spk[i]))
        misc.append(dict(condition=cond, seed=seed, phase=phase, rep=rep, odor=od,
                         wall_s=res.wall_time_s, **info))

    for rep in range(n_test):
        for od in ("A", "B"):
            test("pre", rep, od)
    for k, tr in enumerate(spec["train"]):
        blocks = []
        if tr["odor"] is not None:
            blocks.append((odors[tr["odor"]], rate, tr["on"], tr["off"]))
        if tr["pulses"]:
            drows = np.concatenate([dan_rows_of[d] for d in tr["dans"]])
            blocks += pulse_blocks(drows, tr["pulses"])
        before = state.wk.copy()
        res = pb.run(blocks, tr["dur"], [seed, 3, k], state=state)
        _, _, info = ro(res, before)
        misc.append(dict(condition=cond, seed=seed, phase="train", rep=k,
                         odor=tr["odor"] or "-", wall_s=res.wall_time_s, **info))
    wts = state.mbon_type_weight()
    for rep in range(n_test):
        for od in ("A", "B"):
            test("post", rep, od)
    wts_end = state.mbon_type_weight()
    w_rows = [(cond, seed, t, float(wts[t]), float(wts_end[t])) for t in wts.index]
    return rows, misc, w_rows


def calib_path(tag=""):
    return RES / f"calibration{tag}.json"


def load_calibration(tag=""):
    p = calib_path(tag)
    if not p.exists():
        raise SystemExit(f"run the calibrate stage first ({p.name})")
    return json.loads(p.read_text())


def rule_from(cal):
    return LearningRule(eta=cal["eta"], slow_ratio=cal["slow_ratio"],
                        tau_kc_ms=cal.get("tau_kc_ms", 1000.0),
                        tau_da_ms=cal.get("tau_da_ms", 200.0))


def conditioning(model, dan_mode, seeds, conds, n_test=N_TEST, tag=""):
    cal = load_calibration(tag)
    rule = rule_from(cal)
    pb, lab, kind = get_model(model, dan_mode=dan_mode, rule=rule)
    ro = Readout(pb, lab)
    odors = odor_input_rows(lab, kind)
    rate = PN_RATE_HZ if kind == "pn" else ORN_RATE_HZ
    dan_rows_of = {d: type_rows(lab, d) for d in
                   ("PPL101", "PAM01", "PAM02", "PAM11", "PPL105")}
    name = f"{model}_{dan_mode}{tag}"
    f_main, f_misc, f_w = (RES / f"cond_{name}.csv", RES / f"cond_{name}_misc.csv",
                           RES / f"cond_{name}_weights.csv")
    done = set()
    if f_w.exists():
        d = pd.read_csv(f_w)
        done = set(zip(d.condition, d.seed))
    todo = [(c, s) for c in conds for s in seeds if (c, s) not in done]
    print(f"{name}: rule {rule}; {len(todo)} sequences to run", flush=True)
    lock = threading.Lock()

    def job(cs):
        c, s = cs
        t0 = time.perf_counter()
        rows, misc, w_rows = run_sequence(pb, lab, ro, odors, dan_rows_of, rate, c, s, n_test)
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
        print(f"  {c} seed {s}: {r} drive A {x['pre','A']:.0f}->{x['post','A']:.0f}, "
              f"B {x['pre','B']:.0f}->{x['post','B']:.0f}  ({time.perf_counter() - t0:.0f} s)",
              flush=True)

    with ThreadPoolExecutor(N_THREADS) as pool:
        list(pool.map(job, todo))


# ---------------------------------------------------------------------------
# calibration (MB circuit, modulatory DANs)
# ---------------------------------------------------------------------------
def _training_integrals(pb, ro, odors, dan_rows_of, rate, seed, od, dan, n_test,
                        long=False):
    """Pre/post KC spike counts for odor ``od`` and the per-synapse integral
    I = -log(w_after / w0) / eta of one paired training (learning off in the
    tests, so they measure only the training)."""
    eta_small = 1e-6
    pb.rule = LearningRule(eta=eta_small, slow_ratio=1.0, tau_kc_ms=pb.rule.tau_kc_ms,
                           tau_da_ms=pb.rule.tau_da_ms)
    state = pb.new_state()
    pre, post = [], []

    def kc_counts(phase, rep):
        res = pb.run([(odors[od], rate, 0.0, 1000.0)], TEST_MS,
                     [seed, 1 if phase == "pre" else 2, rep, 0 if od == "A" else 1],
                     state=state, plastic=False)
        s1 = int(WINDOW[1] / res.dt_ms)
        m = res.step < s1
        return np.bincount(res.neuron[m], minlength=pb.n_neurons)

    for rep in range(n_test):
        pre.append(kc_counts("pre", rep))
    if long:
        tr = CONDITIONS["alpha2_long"]["train"][0]
    else:
        tr = paired(od, (dan,))
    blocks = [(odors[od], rate, tr["on"], tr["off"])] + pulse_blocks(dan_rows_of[dan],
                                                                     tr["pulses"])
    pb.run(blocks, tr["dur"], [seed, 3, 0], state=state)
    I = -np.log(state.wk / pb.wk0) / eta_small
    for rep in range(n_test):
        post.append(kc_counts("post", rep))
    return np.array(pre), np.array(post), I


def _drop(pb, ro, pre, post, I, eta, target_type):
    m = ro.pt_code == ro.types.index(target_type)
    kc, wi = ro.pt_kc[m], ro.pt_w[m]
    w0 = pb.wk0[wi]
    d_pre = (pre[:, kc] * w0).sum(1).mean()
    d_post = (post[:, kc] * w0 * np.exp(-eta * I[wi])).sum(1).mean()
    return 1.0 - d_post / d_pre


def calibrate(seeds=(900, 901, 902, 903, 904), target=0.90, target_80=0.80,
              alpha2_short_target=0.05, tau_da_ms=200.0, tag=""):
    from scipy.optimize import brentq
    pb, lab, kind = get_model("circuit", dan_mode="modulatory",
                              rule=LearningRule(tau_da_ms=tau_da_ms))
    ro = Readout(pb, lab)
    odors = odor_input_rows(lab, kind)
    dan_rows_of = {d: type_rows(lab, d) for d in ("PPL101", "PPL105")}
    out = {"seeds": list(seeds), "target_drive_drop_gamma1pedc": target,
           "pn_rate_hz": PN_RATE_HZ, "tau_kc_ms": pb.rule.tau_kc_ms, "tau_da_ms": tau_da_ms}
    runs = [_training_integrals(pb, ro, odors, dan_rows_of, PN_RATE_HZ, s, "A", "PPL101",
                                N_TEST) for s in seeds]

    def mean_drop(eta):
        return float(np.mean([_drop(pb, ro, *r, eta, "MBON11") for r in runs]))

    eta = brentq(lambda e: mean_drop(e) - target, 1e-4, 1e3, xtol=1e-6)
    eta80 = brentq(lambda e: mean_drop(e) - target_80, 1e-4, 1e3, xtol=1e-6)
    out.update(eta=eta, eta_for_80pct=eta80,
               per_seed_drop_at_eta=[_drop(pb, ro, *r, eta, "MBON11") for r in runs])
    print(f"eta = {eta:.5g} (90% drive drop); eta for 80% = {eta80:.5g}", flush=True)
    # slow compartment (alpha2): 1-s pairing with PPL105 should do almost nothing
    runs2 = [_training_integrals(pb, ro, odors, dan_rows_of, PN_RATE_HZ, s, "A", "PPL105",
                                 N_TEST) for s in seeds]

    def mean_drop2(ratio):
        return float(np.mean([_drop(pb, ro, *r, eta * ratio, "MBON18") for r in runs2]))

    fast_equiv = mean_drop2(1.0)
    ratio = brentq(lambda q: mean_drop2(q) - alpha2_short_target, 1e-6, 1.0, xtol=1e-9)
    out.update(slow_ratio=ratio, alpha2_short_drop_if_fast=fast_equiv,
               alpha2_short_target=alpha2_short_target)
    print(f"slow_ratio = {ratio:.5g} (alpha2 1-s drop {alpha2_short_target:.0%}; "
          f"would be {fast_equiv:.1%} if alpha2 learned as fast as gamma1pedc)", flush=True)
    calib_path(tag).write_text(json.dumps(out, indent=2))
    print("saved", calib_path(tag))


# ---------------------------------------------------------------------------
# Phase 3 regression: sugar -> MN9 with learning on but not triggered
# ---------------------------------------------------------------------------
def regression(model, seeds=(0, 1, 2), n_trials=10):
    sys.path.insert(0, str(RES.parents[1] / "phase5" / "competition"))
    from phase5_common import paper_ids
    cal = load_calibration()
    ids = paper_ids()
    out = RES / f"regression_{model}.csv"
    rows = []
    pb, lab, _ = get_model(model, dan_mode="modulatory", rule=rule_from(cal))
    brain = pb.brain
    sugar = brain.index_of(ids["SUGAR"])
    mn9 = brain.index_of([ids["MN9"], ids["MN9_IPSI"]])
    from sim.plasticity import PlasticBrain
    pb_fast = PlasticBrain(brain, lab, pb.rule, dan_mode="fast")
    for rate in (100.0, 200.0):
        for sd in seeds:
            states = {"modulatory": pb.new_state(), "fast": pb_fast.new_state()}
            for t in range(n_trials):
                n_steps = 10000
                ev = pb.make_events([(sugar, rate, 0.0, 1000.0)], n_steps,
                                    np.random.default_rng([sd, t, int(rate)]))
                steps = np.repeat(np.arange(n_steps), np.diff(ev[0]))
                base = brain.run_with_input_events([(steps, brain.root_ids[ev[1]])],
                                                   excite=brain.root_ids[sugar],
                                                   duration_ms=1000.0)
                row = dict(model=model, rate=rate, seed=sd, trial=t,
                           base_mn9=int((base.neuron == mn9[0]).sum()),
                           base_mn9_ipsi=int((base.neuron == mn9[1]).sum()),
                           base_spikes=int(base.step.size))
                for mode, p in (("modulatory", pb), ("fast", pb_fast)):
                    st = states[mode]
                    before = st.wk.copy()
                    r = p.run(None, 1000.0, None, state=st, events=ev, excite_rows=sugar)
                    row[f"{mode}_mn9"] = int((r.neuron == mn9[0]).sum())
                    row[f"{mode}_mn9_ipsi"] = int((r.neuron == mn9[1]).sum())
                    row[f"{mode}_spikes"] = int(r.step.size)
                    row[f"{mode}_identical_to_base"] = bool(
                        np.array_equal(r.step, base.step) and np.array_equal(r.neuron, base.neuron))
                    row[f"{mode}_max_weight_change"] = float(
                        np.max(np.abs(st.wk / p.wk0 - 1.0)))
                    row[f"{mode}_trial_weight_change"] = float(
                        np.max(np.abs(st.wk / before - 1.0)))
                rows.append(row)
            print(pd.DataFrame(rows).query("rate == @rate and seed == @sd")[
                ["base_mn9", "modulatory_mn9", "fast_mn9", "fast_identical_to_base",
                 "modulatory_max_weight_change", "fast_max_weight_change"]].mean().round(4)
                .to_dict(), flush=True)
            pd.DataFrame(rows).to_csv(out, index=False)
    print("saved", out)


if __name__ == "__main__":
    stage = sys.argv[1]
    if stage == "calibrate":
        if len(sys.argv) > 2:          # tau_da sensitivity: calibrate <tau_da_ms>
            calibrate(tau_da_ms=float(sys.argv[2]), tag=f"_tauda{int(float(sys.argv[2]))}")
        else:
            calibrate()
    elif stage == "conditioning":
        model, mode = sys.argv[2], sys.argv[3]
        seeds = [int(s) for s in sys.argv[4].split(",")] if len(sys.argv) > 4 else [0, 1, 2, 3, 4]
        conds = sys.argv[5].split(",") if len(sys.argv) > 5 else MAIN
        n_test = int(sys.argv[6]) if len(sys.argv) > 6 else N_TEST
        tag = sys.argv[7] if len(sys.argv) > 7 else ""
        conditioning(model, mode, seeds, conds, n_test, tag)
    elif stage == "regression":
        regression(sys.argv[2])
    else:
        raise SystemExit(__doc__)
