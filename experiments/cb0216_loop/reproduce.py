"""Step 2 (PRELIMINARY): reproduce the CB0216 persistence with the fast engine.

Stages (python reproduce.py <stage>):
  scan    seed 0: which inputs switch the pair on? Each input is on for a while,
          then everything is off for 2 s; "on" = both CB0216 >= 50 Hz in the last
          1 s. Inputs: the Phase 3 taste sets, the reservoir lane's push-pull
          input on all sensory neurons, a single kick to one CB0216, and every
          sensory cell class on its own.     -> results/scan.csv
  mech    which touch-sensor (mechanosensory) groups, and how little input,
          switch it on.                        -> results/scan_mech.csv
  r1r2 <input>   pass rules R1/R2 (input = pushpull400 or mech100): seeds 0-2,
          5 s off; intact, right CB0216 silenced, left CB0216 silenced; the intact
          seed-0 run is also saved binned for the figure.
          -> results/r1r2_<input>.csv, results/trace_<input>.npz
  realism <input>  the same with the project's Phase 7 upgrades switched on one
          at a time (adaptation; conductance-based synapses). -> results/realism_<input>.csv
  weight  the pair's mutual synapse count set by hand (451 ... 20).
          -> results/weight_scan.csv
  offswitch  can the pair's own inhibitory inputs switch it off? -> results/offswitch.csv
Engine: n_threads=1, one simulation at a time; waits for 1.5 GB free RAM.
"""
import json
import sys
import time

import numpy as np
import pandas as pd

import lib_cb as C

sys.path.insert(0, str(C.ROOT / "experiments" / "reservoir_spiking"))
sys.path.insert(0, str(C.ROOT / "experiments" / "reservoir"))

stage = sys.argv[1] if len(sys.argv) > 1 else "scan"
root_ids, pre, post, signed, lab = C.arrays()
n = len(root_ids)
idx = {int(r): i for i, r in enumerate(root_ids)}
PI = [idx[p] for p in C.PAIR]
MI = [idx[m] for m in C.MN9]
sc = lab.super_class if "super_class" in lab.columns else None
import pandas as _pd  # noqa: E402
lab630 = _pd.read_parquet(C.ROOT / "data/cache/connectome_630_neurons.parquet",
                          columns=["root_id", "super_class", "cell_class"]).set_index(
    "root_id").reindex(root_ids)
supc = lab630.super_class.astype(object).where(lab630.super_class.notna(), "").astype(str).to_numpy()
cclass = lab630.cell_class.astype(object).where(lab630.cell_class.notna(), "").astype(str).to_numpy()
SENS = np.flatnonzero(supc == "sensory")
NONSENS = supc != "sensory"


def push_pull(peak, seed=0):
    """The reservoir lane's input: 2 s of u(t) on all sensory neurons (push-pull)."""
    import lib_spk as L
    u, _ = L.rlib.make_input(100, seed)
    rates = L.rates_for(u, L.input_signs(SENS.size, seed), peak)   # (100 bins, n_sens)
    return rates


def pushpull_events(peak, off_ms, seed):
    """Poisson kicks with the reservoir lane's bin-wise rates, then off."""
    rates = push_pull(peak, seed)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 77]))
    sub = 200
    k = rng.binomial(sub, rates * C.DT_MS * 1e-3)
    b, s = np.nonzero(k)
    reps = k[b, s]
    steps = np.repeat(b, reps).astype(np.int64) * sub + rng.integers(0, sub, int(k.sum()))
    neurons = SENS[np.repeat(s, reps)].astype(np.int64)
    key = np.unique(steps * 200_000 + neurons)
    steps, neurons = key // 200_000, key % 200_000
    total = 2000.0 + off_ms
    return C.FastBrain._pack_events(steps, neurons, int(round(total / C.DT_MS))), 2000.0


def measure(step, neuron, on_ms, off_ms, label, **extra):
    end = on_ms + off_ms
    r_last = C.pair_rates(step, neuron, PI, end - 1000, end)
    r_on = C.pair_rates(step, neuron, PI, 0, on_ms)
    mn9_last = C.pair_rates(step, neuron, MI, end - 1000, end)
    cnt_last = C.window_counts(step, neuron, n, end - 1000, end)
    return dict(input=label, on_ms=on_ms, off_ms=off_ms,
                cb_right_on_hz=r_on[0], cb_left_on_hz=r_on[1],
                cb_right_last1s_hz=r_last[0], cb_left_last1s_hz=r_last[1],
                mn9_left_last1s_hz=mn9_last[0], mn9_right_last1s_hz=mn9_last[1],
                n_nonsensory_active_last1s=int(((cnt_last > 0) & NONSENS).sum()),
                spikes_last1s=int(cnt_last.sum()),
                last_spike_cb_right_ms=C.last_spike_ms(step, neuron, PI[0]),
                persistent=bool(min(r_last) >= 50.0), **extra)


def taste_sets():
    import sim.shiu_model as sm
    return {"sugar": sm.SUGAR_R_630, "bitter": sm.BITTER_R_630, "water": sm.WATER_R_630,
            "ir94e": sm.IR94E_630}


if stage == "scan":
    brain = C.brain_from(root_ids, pre, post, signed)
    rows = []
    OFF = 2000.0
    tests = []
    ts = taste_sets()
    for nm, rate in (("sugar", 100), ("sugar", 200), ("bitter", 200), ("water", 200),
                     ("ir94e", 200)):
        tests.append((f"{nm}_{rate}Hz_1s", [idx[i] for i in ts[nm]], rate, 1000.0))
    tests.append(("pair_both_200Hz_50ms", PI, 200, 50.0))
    for peak in (150, 400):
        tests.append((f"pushpull_all_sensory_{peak}Hz_2s", "pushpull", peak, 2000.0))
    classes = pd.Series(cclass[SENS]).value_counts()
    for cl, k in classes.items():
        tests.append((f"class_{cl or 'unlabelled'}_{k}n_100Hz_1s", SENS[cclass[SENS] == cl], 100, 1000.0))
    for label, exc, rate, on_ms in tests:
        C.wait_for_ram(1.5)
        if isinstance(exc, str):
            ev, on_ms = pushpull_events(rate, OFF, 0)
            st, nr, wall = C.run_onoff(brain, SENS, None, on_ms, OFF, 0, events=ev)
        else:   # internal neurons (the pair) keep their normal refractory period
            st, nr, wall = C.run_onoff(brain, exc, rate, on_ms, OFF, 0,
                                       keep_refractory=label.startswith("pair_"))
        row = measure(st, nr, on_ms, OFF, label, wall_s=round(wall, 1))
        rows.append(row)
        print(f"{label:45s} on {row['cb_right_on_hz']:6.1f}/{row['cb_left_on_hz']:6.1f} "
              f"last {row['cb_right_last1s_hz']:6.1f}/{row['cb_left_last1s_hz']:6.1f} "
              f"MN9 {row['mn9_left_last1s_hz']:5.1f}/{row['mn9_right_last1s_hz']:5.1f} "
              f"act {row['n_nonsensory_active_last1s']:5d} wall {wall:5.1f}s", flush=True)
        del st, nr
    # single kick: one Poisson-sized kick (68.75 mV) to the right CB0216 at 10 ms
    for who, i in (("right", PI[0]), ("left", PI[1])):
        ev = C.FastBrain._pack_events(np.array([100]), np.array([i]), int(round(2010 / C.DT_MS)))
        st, nr, wall = C.run_onoff(brain, np.zeros(0, np.int64), None, 10.0, 2000.0, 0, events=ev)
        row = measure(st, nr, 10.0, 2000.0, f"single_kick_{who}_CB0216", wall_s=round(wall, 1))
        rows.append(row)
        print(f"single kick {who}: last {row['cb_right_last1s_hz']:.1f}/{row['cb_left_last1s_hz']:.1f} "
              f"MN9 {row['mn9_left_last1s_hz']:.1f}/{row['mn9_right_last1s_hz']:.1f}", flush=True)
    pd.DataFrame(rows).to_csv(C.RESULTS / "scan.csv", index=False)
    print("wrote results/scan.csv")

elif stage == "mech":
    # which mechanosensory neurons, and how little input, switch the pair on?
    sub = _pd.read_parquet(C.ROOT / "data/cache/connectome_630_neurons.parquet",
                           columns=["root_id", "cell_sub_class"]).set_index("root_id").reindex(
        root_ids).cell_sub_class.astype(object).fillna("").astype(str).to_numpy()
    MECH = SENS[cclass[SENS] == "mechanosensory"]
    brain = C.brain_from(root_ids, pre, post, signed)
    rows = []
    OFF = 2000.0
    tests = [(f"mech_all_{r}Hz_1s", MECH, r, 1000.0) for r in (2, 5, 10, 20, 50)]
    tests += [(f"mech_all_100Hz_{ms:g}ms", MECH, 100, ms) for ms in (5.0, 20.0, 100.0)]
    for sc_, k in pd.Series(sub[MECH]).value_counts().items():
        tests.append((f"mech_sub_{sc_ or 'none'}_{k}n_100Hz_1s", MECH[sub[MECH] == sc_], 100, 1000.0))
    for label, exc, rate, on_ms in tests:
        C.wait_for_ram(1.5)
        st, nr, wall = C.run_onoff(brain, exc, rate, on_ms, OFF, 0)
        row = measure(st, nr, on_ms, OFF, label, wall_s=round(wall, 1))
        rows.append(row)
        print(f"{label:50s} on {row['cb_right_on_hz']:6.1f}/{row['cb_left_on_hz']:6.1f} "
              f"last {row['cb_right_last1s_hz']:6.1f}/{row['cb_left_last1s_hz']:6.1f}", flush=True)
    pd.DataFrame(rows).to_csv(C.RESULTS / "scan_mech.csv", index=False)
    print("wrote results/scan_mech.csv")

elif stage == "offswitch":
    # can the pair's own inhibitory inputs switch it OFF again? Touch input 1 s,
    # 1 s of free persistence, then drive the pair's inhibitory inputs at 200 Hz
    # for 100 ms (normal refractory period kept), then 2 s with no input.
    INH = {"GABA_x2_unlabelled": [720575940640096976, 720575940613958194],
           "DNge160_x2": [720575940623338281, 720575940630810486]}
    INH["all_four"] = INH["GABA_x2_unlabelled"] + INH["DNge160_x2"]
    MECH = SENS[cclass[SENS] == "mechanosensory"]
    brain = C.brain_from(root_ids, pre, post, signed)
    rows = []
    T_INH, OFF_END = 2000.0, 4100.0
    for nm, ids in INH.items():
        gi = np.array([idx[i] for i in ids], np.int64)
        for seed in (0, 1, 2):
            rng = np.random.default_rng(np.random.SeedSequence([seed, 216]))
            n_steps = int(round(OFF_END / C.DT_MS))
            (p1, n1), _ = C.onoff_events(MECH, 100, 1000.0, OFF_END, rng)
            s1 = np.repeat(np.arange(n_steps), np.diff(p1))
            k = rng.binomial(1000, 200 * C.DT_MS * 1e-3, gi.size)
            s2 = np.concatenate([int(T_INH / C.DT_MS) + rng.choice(1000, kk, replace=False)
                                 for kk in k])
            n2 = np.repeat(gi, k)
            ev = C.FastBrain._pack_events(np.concatenate([s1, s2]),
                                          np.concatenate([n1.astype(np.int64), n2]), n_steps)
            p = brain._params_for(None)
            res = brain._run_events([ev], MECH, (), n_steps, p, ())
            st, nr = res.step.astype(np.int64), res.neuron.astype(np.int64)
            before = C.pair_rates(st, nr, PI, T_INH - 500, T_INH)
            during = C.pair_rates(st, nr, PI, T_INH, T_INH + 100)
            row = measure(st, nr, 1000.0, OFF_END - 1000.0, f"mech100_then_inhibit_{nm}",
                          seed=seed, cb_before_inh_hz=float(np.mean(before)),
                          cb_during_inh_hz=float(np.mean(during)))
            rows.append(row)
            print(f"{nm:20s} seed {seed}: before {np.mean(before):.0f} during {np.mean(during):.0f} "
                  f"last {row['cb_right_last1s_hz']:.0f}/{row['cb_left_last1s_hz']:.0f} Hz", flush=True)
    pd.DataFrame(rows).to_csv(C.RESULTS / "offswitch.csv", index=False)
    print("wrote results/offswitch.csv")

elif stage == "weight":
    # how many mutual synapses does the loop need? Set BOTH directions of the
    # pair's mutual connection to N synapses (everything else unchanged), give
    # one kick to the right CB0216 (and, separately, all mechanosensory input at
    # 100 Hz for 1 s), then 3 s with no input. Seeds 0-2 for the mech input.
    m = ((pre == PI[0]) & (post == PI[1])) | ((pre == PI[1]) & (post == PI[0]))
    assert m.sum() == 2, "expected one connection row per direction"
    MECH = SENS[cclass[SENS] == "mechanosensory"]
    rows = []
    OFF = 3000.0
    for N in (451, 300, 237, 205, 150, 100, 70, 50, 40, 30, 20):
        s_mod = signed.copy()
        s_mod[m] = N
        brain = C.brain_from(root_ids, pre, post, s_mod)
        ev = C.FastBrain._pack_events(np.array([100]), np.array([PI[0]]),
                                      int(round((10 + OFF) / C.DT_MS)))
        st, nr, wall = C.run_onoff(brain, np.zeros(0, np.int64), None, 10.0, OFF, 0, events=ev)
        row = measure(st, nr, 10.0, OFF, "single_kick_right", mutual_syn=N, seed=0)
        rows.append(row)
        print(f"N={N:4d} kick: last {row['cb_right_last1s_hz']:.1f}/{row['cb_left_last1s_hz']:.1f} "
              f"MN9 {row['mn9_left_last1s_hz']:.1f}/{row['mn9_right_last1s_hz']:.1f}", flush=True)
        for seed in (0, 1, 2):
            st, nr, wall = C.run_onoff(brain, MECH, 100, 1000.0, OFF, seed)
            row = measure(st, nr, 1000.0, OFF, "mech100", mutual_syn=N, seed=seed)
            rows.append(row)
            print(f"N={N:4d} mech100 seed {seed}: on {row['cb_right_on_hz']:.1f}/"
                  f"{row['cb_left_on_hz']:.1f} last {row['cb_right_last1s_hz']:.1f}/"
                  f"{row['cb_left_last1s_hz']:.1f}", flush=True)
        del brain, s_mod
    pd.DataFrame(rows).to_csv(C.RESULTS / "weight_scan.csv", index=False)
    print("wrote results/weight_scan.csv")

elif stage in ("r1r2", "realism"):
    which = sys.argv[2] if len(sys.argv) > 2 else "sugar200"
    OFF = 5000.0
    rows = []
    if stage == "r1r2":
        variants = [("intact", None, ()), ("silence_right", None, (C.PAIR[0],)),
                    ("silence_left", None, (C.PAIR[1],))]
    else:
        variants = [("adaptation", {"adaptation": True}, ()),
                    ("conductance", {"conductance": True}, ())]
    ts = taste_sets()
    for vname, realism, sil in variants:
        brain = C.brain_from(root_ids, pre, post, signed, realism=realism)
        for seed in (0, 1, 2):
            C.wait_for_ram(1.5)
            if which.startswith("pushpull"):
                peak = float(which.replace("pushpull", ""))
                ev, on_ms = pushpull_events(peak, OFF, seed)
                st, nr, wall = C.run_onoff(brain, SENS, None, on_ms, OFF, seed, silence=sil,
                                           events=ev)
            elif which == "pairkick":
                on_ms = 50.0
                st, nr, wall = C.run_onoff(brain, PI, 200, on_ms, OFF, seed, silence=sil,
                                           keep_refractory=True)
            elif which.startswith("mech"):   # all mechanosensory neurons, e.g. mech100
                on_ms = 1000.0
                st, nr, wall = C.run_onoff(brain, SENS[cclass[SENS] == "mechanosensory"],
                                           float(which[4:]), on_ms, OFF, seed, silence=sil)
            else:
                nm, rate = which[:-3], int(which[-3:])
                on_ms = 1000.0
                st, nr, wall = C.run_onoff(brain, [idx[i] for i in ts[nm]], rate, on_ms, OFF,
                                           seed, silence=sil)
            row = measure(st, nr, on_ms, OFF, which, variant=vname, seed=seed,
                          wall_s=round(wall, 1))
            rows.append(row)
            print(f"{vname:14s} seed {seed}: on {row['cb_right_on_hz']:.1f}/{row['cb_left_on_hz']:.1f} "
                  f"last {row['cb_right_last1s_hz']:.1f}/{row['cb_left_last1s_hz']:.1f} "
                  f"MN9 {row['mn9_left_last1s_hz']:.1f}/{row['mn9_right_last1s_hz']:.1f} "
                  f"act {row['n_nonsensory_active_last1s']} wall {wall:.1f}s", flush=True)
            if stage == "r1r2" and vname == "intact" and seed == 0:
                # 20 ms binned rates of the pair and MN9 for the figure
                nb = int((on_ms + OFF) / 20)
                b = (st * C.DT_MS // 20).astype(np.int64)
                tr = {k: np.bincount(b[nr == i], minlength=nb)[:nb] / 0.02
                      for k, i in (("cb_right", PI[0]), ("cb_left", PI[1]),
                                   ("mn9_left", MI[0]), ("mn9_right", MI[1]))}
                np.savez_compressed(C.RESULTS / f"trace_{which}.npz", on_ms=on_ms, **tr)
            del st, nr
        del brain
    out = C.RESULTS / f"{stage}_{which}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print("wrote", out.name)
