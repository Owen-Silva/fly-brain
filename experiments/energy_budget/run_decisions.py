"""Run every decision on one model version and count what the brain spends (PRELIMINARY).

Usage (one simulation process at a time, one thread):
    .venv\\Scripts\\python.exe experiments\\energy_budget\\run_decisions.py --model none
    .venv\\Scripts\\python.exe experiments\\energy_budget\\run_decisions.py --model al_ln_literature

For each trial (1 s of simulated time) it records: total spikes in the whole brain, how
many neurons fired at all, synaptic events (each spike x that neuron's output synapses,
and x its output connections), the runaway test, MN9 / aBN1 first-spike times, and the
wall time and CPU time the laptop needed. Spikes are summarised and thrown away trial by
trial, so memory stays small. While it runs, Windows' own CPU energy meter (Intel RAPL,
"Energy Meter" performance counter) is logged once a second with typeperf.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import time

import numpy as np
import pandas as pd

from common import (ABN1, DURATION_MS, MN9, MN9_IPSI, RAW, RES, RUNAWAY_DISTINCT_10MS, SEEDS,
                    TRIALS_PER_SEED, decisions, free_ram_gb, load_labels, run_trial,
                    wait_for_ram, wiring_counts)

COUNTERS = [r"\Energy Meter(rapl_package0_pkg)\Power", r"\Energy Meter(rapl_package0_pp0)\Power",
            r"\Processor(_Total)\% Processor Time"]


def physical_counts():
    """Output synapses / connections per neuron in the PUBLISHED wiring (FlyWire 630 as
    the paper uses it). Used for the fly's own energy, whatever model is simulated."""
    from sim.sign_fixes import load_reference_arrays
    root_ids, pre, post, signed = load_reference_arrays("630")
    n = len(root_ids)
    syn = np.rint(np.bincount(pre, weights=np.abs(signed).astype(np.float64), minlength=n)).astype(np.int64)
    conn = np.bincount(pre, minlength=n).astype(np.int64)
    del pre, post, signed
    return np.asarray(root_ids, np.int64), syn, conn


def first_ms(steps, dt_ms):
    return float(steps.min() * dt_ms) if steps.size else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["none", "al_ln_literature"])
    ap.add_argument("--trials", type=int, default=TRIALS_PER_SEED)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--probe", action="store_true", help="1 trial per decision, no files")
    args = ap.parse_args()

    print(f"free RAM {free_ram_gb():.2f} GB", flush=True)
    wait_for_ram(1.5)
    rid_phys, syn_phys, conn_phys = physical_counts()
    wait_for_ram(1.5)
    from sim.sign_fixes import build_brain
    t0 = time.perf_counter()
    brain, rep = build_brain(fix=args.model, n_threads=1, return_report=True)
    print(f"built {brain.snapshot}: {brain.n_neurons} neurons, {brain.n_connections} connections "
          f"in {time.perf_counter() - t0:.1f} s; free RAM {free_ram_gb():.2f} GB", flush=True)
    assert np.array_equal(rid_phys, brain.root_ids)
    syn_m, conn_m = wiring_counts(brain)
    sizes = dict(model=args.model, n_neurons=int(brain.n_neurons),
                 n_connections=int(brain.n_connections), n_synapses=int(syn_m.sum()),
                 n_connections_published=int(conn_phys.sum()), n_synapses_published=int(syn_phys.sum()),
                 fix_notes=getattr(rep, "notes", ""),
                 removed_connections=int(getattr(rep, "removed_connections", 0) or 0),
                 removed_synapses=int(getattr(rep, "removed_synapses", 0) or 0))
    print(json.dumps(sizes), flush=True)

    lab = load_labels().set_index("root_id").reindex(brain.root_ids).reset_index()
    decs = decisions(lab)
    names = args.only or list(decs)
    p = brain._params_for(None)
    n_steps = int(round(DURATION_MS / p["dt"]))
    dt_ms = p["dt"]
    per10 = int(round(10 / dt_ms))
    mn9_i, mn9b_i, abn1_i = brain.index_of([MN9, MN9_IPSI, ABN1])

    # compile / load the compiled kernel before anything is timed
    brain.run(excite=decs["sugar"]["ids"][:1].tolist(), duration_ms=10, n_trials=1, seed=0)

    tag = "probe" if args.probe else args.model
    logger = None
    if not args.probe:
        power_csv = RAW / f"power_{tag}.csv"
        logger = subprocess.Popen(["typeperf", *COUNTERS, "-si", "1", "-o", str(power_csv), "-y"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)   # a few baseline samples before the first trial

    rows, counts_by_dec, bins_by_dec = [], {}, {}
    seeds = SEEDS[:1] if args.probe else SEEDS
    n_trials = 1 if args.probe else args.trials
    try:
        for name in names:
            d = decs[name]
            exc_idx = brain.index_of(d["ids"])
            prob = np.full(exc_idx.size, d["rate_hz"] * dt_ms * 1e-3)
            is_stim = np.zeros(brain.n_neurons, bool)
            is_stim[exc_idx] = True
            counts = np.zeros(brain.n_neurons, np.int64)
            bins = np.zeros(n_steps // per10, np.int64)
            wait_for_ram(1.0)
            for seed in seeds:
                for k in range(n_trials):
                    ta = dt.datetime.now()
                    c0, w0 = time.process_time(), time.perf_counter()
                    res = run_trial(brain, exc_idx, prob, seed, k, n_steps, p)
                    c1, w1 = time.process_time(), time.perf_counter()
                    tb = dt.datetime.now()
                    nu = res.neuron.astype(np.int64)
                    st = res.step.astype(np.int64)
                    counts += np.bincount(nu, minlength=brain.n_neurons)
                    b = np.bincount(st // per10, minlength=bins.size)[:bins.size]
                    bins += b
                    key = np.unique((st // per10) * 1_000_000 + nu)
                    d10 = np.bincount(key // 1_000_000, minlength=bins.size)
                    uniq = np.unique(nu)
                    rows.append(dict(
                        model=args.model, decision=name, seed=seed, trial=k,
                        n_stim=int(exc_idx.size), rate_hz=d["rate_hz"],
                        total_spikes=int(nu.size), stim_spikes=int(is_stim[nu].sum()),
                        n_active=int(uniq.size), n_active_nonstim=int((~is_stim[uniq]).sum()),
                        syn_events=int(syn_m[nu].sum()), conn_events=int(conn_m[nu].sum()),
                        syn_events_phys=int(syn_phys[nu].sum()), conn_events_phys=int(conn_phys[nu].sum()),
                        max_distinct_10ms=int(d10.max()) if d10.size else 0,
                        runaway=bool(d10.size and d10.max() > RUNAWAY_DISTINCT_10MS),
                        mn9_spikes=int((nu == mn9_i).sum()), mn9_first_ms=first_ms(st[nu == mn9_i], dt_ms),
                        mn9_ipsi_spikes=int((nu == mn9b_i).sum()),
                        mn9_ipsi_first_ms=first_ms(st[nu == mn9b_i], dt_ms),
                        abn1_spikes=int((nu == abn1_i).sum()), abn1_first_ms=first_ms(st[nu == abn1_i], dt_ms),
                        wall_sim_s=float(res.wall_time_s), wall_total_s=w1 - w0, cpu_s=c1 - c0,
                        t_start=ta.isoformat(timespec="milliseconds"),
                        t_end=tb.isoformat(timespec="milliseconds")))
                    del res, nu, st, key
                r = [x for x in rows if x["decision"] == name and x["seed"] == seed]
                print(f"{args.model:>17} {name:<10} seed {seed}: spikes {np.mean([x['total_spikes'] for x in r]):,.0f}, "
                      f"active {np.mean([x['n_active'] for x in r]):,.0f}, runaway {sum(x['runaway'] for x in r)}/{len(r)}, "
                      f"MN9 {np.mean([x['mn9_spikes'] for x in r]):.1f}, wall/trial {np.mean([x['wall_total_s'] for x in r]):.2f} s, "
                      f"free RAM {free_ram_gb():.2f} GB", flush=True)
            counts_by_dec[name] = counts
            bins_by_dec[name] = bins
    finally:
        if logger is not None:
            time.sleep(3)   # a few samples after the last trial
            logger.terminate()
            logger.wait(timeout=10)

    if args.probe:
        print(pd.DataFrame(rows)[["decision", "total_spikes", "n_active", "runaway", "wall_total_s"]].to_string())
        return
    pd.DataFrame(rows).to_csv(RES / f"trials_{tag}.csv", index=False)
    np.savez_compressed(RAW / f"neuron_counts_{tag}.npz", root_ids=brain.root_ids,
                        syn_model=syn_m, conn_model=conn_m, syn_phys=syn_phys, conn_phys=conn_phys,
                        **{f"counts_{k}": v for k, v in counts_by_dec.items()},
                        **{f"bins10ms_{k}": v for k, v in bins_by_dec.items()})
    sizes["trials_per_seed"] = n_trials
    sizes["seeds"] = list(seeds)
    (RES / f"model_size_{tag}.json").write_text(json.dumps(sizes, indent=1))
    print("wrote", RES / f"trials_{tag}.csv", flush=True)


if __name__ == "__main__":
    main()
