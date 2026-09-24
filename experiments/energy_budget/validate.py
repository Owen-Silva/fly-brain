"""Checks for the energy-budget lane (PRELIMINARY). Run after run_decisions.py.

1. No-input control: with no stimulus the model must produce 0 spikes (it has no
   spontaneous background activity), on both model versions.
2. The per-neuron output-synapse and output-connection counts used for "synaptic events"
   are recomputed a second, independent way: straight from the paper's connection file,
   grouped by presynaptic root ID with pandas, using the unsigned "Connectivity" column.
3. Parameter variation (PLAN.md Phase 6 step 1): sugar and the DM1 smell on the fixed
   model with the weight per synapse at 80% and 120%, 10 trials, a new seed (21).
   Shows how much the spike and synaptic-event totals (and so the energy) move.

Writes results/validation.json.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from common import (DURATION_MS, RES, ROOT, decisions, free_ram_gb, load_labels, run_trial,
                    wait_for_ram, wiring_counts)

REF = ROOT / "data" / "reference" / "2023_03_23_connectivity_630_final.parquet"


def main():
    out = {}
    wait_for_ram(1.5)
    # --- 2. independent wiring count -------------------------------------------------
    t = pd.read_parquet(REF, columns=["Presynaptic_ID", "Connectivity"])
    g = t.groupby("Presynaptic_ID")["Connectivity"].agg(["sum", "size"])
    del t
    raw = np.load(RES / "raw" / "neuron_counts_none.npz")
    rid = raw["root_ids"]
    syn_ind = g["sum"].reindex(rid).fillna(0).to_numpy().astype(np.int64)
    conn_ind = g["size"].reindex(rid).fillna(0).to_numpy().astype(np.int64)
    out["wiring_check"] = dict(
        out_synapses_identical=bool(np.array_equal(syn_ind, raw["syn_phys"])),
        out_connections_identical=bool(np.array_equal(conn_ind, raw["conn_phys"])),
        total_synapses=int(syn_ind.sum()), total_connections=int(conn_ind.sum()),
        mean_out_synapses=float(syn_ind.mean()), median_out_synapses=float(np.median(syn_ind)),
        max_out_synapses=int(syn_ind.max()), neurons_with_no_outputs=int((conn_ind == 0).sum()))
    lab_all = pd.read_parquet(ROOT / "data" / "cache" / "connectome_630_neurons.parquet",
                              columns=["root_id", "out_synapses"]).set_index("root_id")
    fw = lab_all["out_synapses"].reindex(rid).to_numpy()
    ok = np.isfinite(fw)
    out["wiring_check"]["flywire_table_out_synapses_total"] = float(np.nansum(fw))
    out["wiring_check"]["corr_with_flywire_table"] = float(np.corrcoef(fw[ok], syn_ind[ok])[0, 1])
    print(json.dumps(out["wiring_check"], indent=1), flush=True)

    fixed = np.load(RES / "raw" / "neuron_counts_al_ln_literature.npz")
    changed = np.flatnonzero(fixed["syn_model"] != fixed["syn_phys"])
    lab = load_labels().set_index("root_id").reindex(rid).reset_index()
    out["fix_changes_outputs_of"] = dict(
        n_neurons=int(changed.size),
        cell_classes=lab.cell_class.iloc[changed].fillna("?").value_counts().to_dict(),
        synapses_removed=int((fixed["syn_phys"] - fixed["syn_model"]).sum()))
    print(out["fix_changes_outputs_of"], flush=True)

    # --- 1 and 3 need a brain ------------------------------------------------------------
    from sim.sign_fixes import build_brain
    decs = decisions(lab)
    reach_rows = []
    for model in ("none", "al_ln_literature"):
        wait_for_ram(1.5)
        brain = build_brain(fix=model, n_threads=1)
        res = brain.run(excite=[], duration_ms=DURATION_MS, n_trials=2, seed=0)
        out[f"no_input_spikes_{model}"] = int(res.neuron.size)
        print(model, "no-input spikes:", res.neuron.size, flush=True)
        # "touched" neurons (got any input at all, so the engine must update them) and a
        # same-seed-same-answer check against the main run (trials 0-2 of seed 11)
        main = pd.read_csv(RES / f"trials_{model}.csv")
        p0 = brain._params_for(None)
        n_steps = int(round(DURATION_MS / p0["dt"]))
        for name, d in decs.items():
            exc_idx = brain.index_of(d["ids"])
            prob = np.full(exc_idx.size, d["rate_hz"] * p0["dt"] * 1e-3)
            for k in range(3):
                r = run_trial(brain, exc_idx, prob, 11, k, n_steps, p0)
                ref = main[(main.decision == name) & (main.seed == 11) & (main.trial == k)]
                reach_rows.append(dict(model=model, decision=name, trial=k,
                                       neurons_touched=int(r.neurons_reached[0]),
                                       total_spikes=int(r.neuron.size),
                                       same_as_main_run=bool(int(ref.total_spikes.iloc[0]) == r.neuron.size)))
        print(model, "touched:", {n: np.mean([x["neurons_touched"] for x in reach_rows
                                              if x["model"] == model and x["decision"] == n]) for n in decs},
              flush=True)
        if model == "none":
            del brain
            continue
        syn_m, conn_m = wiring_counts(brain)
        rows = []
        for scale in (0.8, 1.0, 1.2):
            p = brain._params_for({"w_syn": p0["w_syn"] * scale})
            n_steps = int(round(DURATION_MS / p["dt"]))
            for name in ("sugar", "smell_DM1"):
                d = decs[name]
                exc_idx = brain.index_of(d["ids"])
                prob = np.full(exc_idx.size, d["rate_hz"] * p["dt"] * 1e-3)
                for k in range(10):
                    t0 = time.perf_counter()
                    r = run_trial(brain, exc_idx, prob, 21, k, n_steps, p)
                    nu = r.neuron.astype(np.int64)
                    st = r.step.astype(np.int64)
                    key = np.unique((st // 100) * 1_000_000 + nu)
                    d10 = np.bincount(key // 1_000_000)
                    rows.append(dict(w_scale=scale, decision=name, trial=k, total_spikes=int(nu.size),
                                     n_active=int(np.unique(nu).size),
                                     syn_events_phys=int(fixed["syn_phys"][nu].sum()),
                                     conn_events=int(conn_m[nu].sum()),
                                     runaway=bool(d10.size and d10.max() > 1500),
                                     wall_s=time.perf_counter() - t0))
                sub = [x for x in rows if x["w_scale"] == scale and x["decision"] == name]
                print(f"w x{scale} {name}: spikes {np.mean([x['total_spikes'] for x in sub]):,.0f}, "
                      f"runaway {sum(x['runaway'] for x in sub)}/10, free RAM {free_ram_gb():.2f} GB", flush=True)
        df = pd.DataFrame(rows)
        df.to_csv(RES / "sensitivity_wsyn.csv", index=False)
        summ = df.groupby(["decision", "w_scale"]).agg(
            spikes=("total_spikes", "mean"), active=("n_active", "mean"),
            syn_events=("syn_events_phys", "mean"), conn_events=("conn_events", "mean"),
            runaway=("runaway", "sum")).reset_index()
        out["wsyn_sensitivity_fixed_model"] = summ.to_dict(orient="records")
        del brain
    rd = pd.DataFrame(reach_rows)
    rd.to_csv(RES / "neurons_touched.csv", index=False)
    out["same_seed_same_spikes"] = bool(rd.same_as_main_run.all())
    out["neurons_touched_mean"] = {f"{m}|{d}": float(v) for (m, d), v in
                                   rd.groupby(["model", "decision"]).neurons_touched.mean().items()}
    (RES / "validation.json").write_text(json.dumps(out, indent=1, default=float))
    print("wrote", RES / "validation.json", flush=True)


if __name__ == "__main__":
    main()
