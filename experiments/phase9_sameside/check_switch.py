"""Checks for the same-side release switch, run BEFORE any body trial.

1. Anatomy (no simulation): each glomerulus's 2x2 ORN -> PN table
   (uniglomerular PNs, the Phase 6 / banc_asymmetry rule: 50% or more of a
   PN's ORN synapses from one ORN type, and at least 20), for the old model,
   arm 1 and arm 2. The old model's table must equal
   experiments/banc_asymmetry/results/flywire_630_glomerulus_map.csv.
   How many glomeruli "mirror" (a left-only smell gives the left PNs more
   input, and a right-only smell the right PNs)?
2. Machinery: variant "unit" (x1024 scaling, no change) must reproduce the
   old model spike for spike (sugar 200 Hz, 30 trials; DA1 input in the body
   loop's 50 ms windows).
3. Realism rule: the Phase 3 taste tests with the switch ON (arm 1): sugar
   100 / 200 Hz, water 200 Hz, bitter 200 Hz, sugar 100 + bitter 120 Hz, 3
   seeds x 30 trials each, the seeds of the Phase 7 lanes. Compared with
   experiments/phase7_signs/results/table_phase3.csv (al_ln_literature rows)
   and, for sugar 200 Hz, neuron by neuron with the switch OFF.

Outputs (results/): anatomy_glomeruli.csv, anatomy_summary.csv,
identity_check.csv, phase3_check.csv, check_switch.log.
Run: .venv\\Scripts\\python.exe experiments/phase9_sameside/check_switch.py
"""

from __future__ import annotations

import ast
import gc
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import sameside as S  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
TASTE = {"sugar_100Hz": ([("SUGAR", 100)], 1_000), "sugar_200Hz": ([("SUGAR", 200)], 2_000),
         "water_200Hz": ([("WATER", 200)], 3_000), "bitter_200Hz": ([("BITTER", 200)], 4_000),
         "sugar100_bitter120": ([("SUGAR", 100), ("BITTER", 120)], 6_000)}


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(OUT / "check_switch.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def paper_ids():
    tree = ast.parse((ROOT / "sim" / "shiu_model.py").read_text(encoding="utf-8"))
    want = {"SUGAR_R_630": "SUGAR", "BITTER_R_630": "BITTER", "WATER_R_630": "WATER",
            "MN9_LEFT": "MN9", "MN9_RIGHT_630": "MN9_IPSI"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in want:
            out[want[node.targets[0].id]] = ast.literal_eval(node.value)
    assert set(out) == set(want.values())
    return out


def anatomy():
    from sim.sign_fixes import apply_fix, load_reference_arrays
    root_ids, pre, post, signed = load_reference_arrays("630")
    pre, post, signed, _ = apply_fix(S.FIX, root_ids, pre, post, signed)
    lab = S.labels(root_ids)
    conn, same, glom, side = S.orn_pn_info(root_ids, pre, post, lab)
    idx = np.flatnonzero(conn)
    e = pd.DataFrame({"pre": pre[idx], "post": post[idx], "glom": glom[pre[idx]],
                      "oside": side[pre[idx]], "pside": side[post[idx]],
                      "c_off": signed[idx].astype(float)})
    for v in ("release", "map"):
        new, rep = S.modified_counts(v, root_ids, pre, post, signed, lab)
        e["c_" + v] = new[idx] / S.RES
        log(f"anatomy {v}: {rep}")
        del new
    # uniglomerular PNs from the OLD counts (fixed PN set for every variant)
    pg = e.groupby(["post", "glom"]).c_off.sum().reset_index()
    tot = pg.groupby("post").c_off.sum()
    best = pg.sort_values("c_off", ascending=False).drop_duplicates("post").set_index("post")
    best["purity"] = best.c_off / tot.reindex(best.index)
    upn = best[(best.purity >= 0.5) & (best.c_off >= 20)]
    e = e[e.post.isin(upn.index) & (e.glom == upn.glom.reindex(e.post).to_numpy())]
    rows = []
    for g, d in e.groupby("glom"):
        if not ((d.pside == "left").any() and (d.pside == "right").any()):
            continue
        r = {"glomerulus": g}
        for v in ("off", "release", "map"):
            c = d.groupby(["oside", "pside"])["c_" + v].sum()
            LL, LR = c.get(("left", "left"), 0.0), c.get(("left", "right"), 0.0)
            RL, RR = c.get(("right", "left"), 0.0), c.get(("right", "right"), 0.0)
            r.update({f"LL_{v}": LL, f"LR_{v}": LR, f"RL_{v}": RL, f"RR_{v}": RR,
                      f"mirror_{v}": bool(LL > LR and RR > RL)})
            if min(LL, LR, RL, RR) > 0:
                r[f"w_{v}"] = np.sqrt(LL * RR / (LR * RL))
                r[f"rho_{v}"] = np.sqrt(LL * RL / (LR * RR))
        rows.append(r)
    t = pd.DataFrame(rows)
    ref = pd.read_csv(S.GLOM_MAP).set_index("glomerulus")
    tt = t.set_index("glomerulus").reindex(ref.index)
    same_as_ref = bool(np.allclose(tt[["LL_off", "LR_off", "RL_off", "RR_off"]].to_numpy(float),
                                   ref[["Lorn_to_Lpn", "Lorn_to_Rpn", "Rorn_to_Lpn",
                                        "Rorn_to_Rpn"]].to_numpy(float)))
    t.to_csv(OUT / "anatomy_glomeruli.csv", index=False, float_format="%.4f")
    summ = []
    for v in ("off", "release", "map"):
        summ.append({"variant": v, "glomeruli": len(t), "mirror": int(t[f"mirror_{v}"].sum()),
                     "median_w": float(t[f"w_{v}"].median()),
                     "median_abs_log_rho": float(np.abs(np.log(t[f"rho_{v}"])).median()),
                     "DA1_w": float(t.set_index("glomerulus").loc["DA1", f"w_{v}"]),
                     "DA1_rho": float(t.set_index("glomerulus").loc["DA1", f"rho_{v}"]),
                     "DM1_w": float(t.set_index("glomerulus").loc["DM1", f"w_{v}"]),
                     "DM1_rho": float(t.set_index("glomerulus").loc["DM1", f"rho_{v}"]),
                     "old_table_matches_banc_csv": same_as_ref})
    s = pd.DataFrame(summ)
    s.to_csv(OUT / "anatomy_summary.csv", index=False, float_format="%.4f")
    log("anatomy summary:\n" + s.to_string(index=False))
    del pre, post, signed, e
    gc.collect()


def excite_for(cond, ids):
    ex = {}
    for key, rate in TASTE[cond][0]:
        for i in ids[key]:
            ex[int(i)] = float(rate)
    return ex


def identity_and_phase3():
    from sim.body.brain_stepper import BrainStepper
    from sim.body.mapping import DN_IDS, DNPE002_IDS, orn_ids
    ids = paper_ids()
    rows = []
    log("building 'off' (old model) and 'unit' (x1024, no change)")
    off = S.build("off", n_threads=2)
    unit = S.build("unit", n_threads=2)
    ex = excite_for("sugar_200Hz", ids)
    a = off.run(excite=ex, duration_ms=1000.0, n_trials=30, seed=2000)
    b = unit.run(excite=ex, duration_ms=1000.0, n_trials=30, seed=2000)
    same = bool(np.array_equal(a.trial, b.trial) and np.array_equal(a.neuron, b.neuron)
                and np.array_equal(a.step, b.step))
    rows.append({"test": "unit vs off, sugar 200 Hz, seed 2000, 30 trials, all neurons",
                 "identical": same, "total_spikes_off": int(a.spike_counts.sum()),
                 "total_spikes_unit": int(b.spike_counts.sum())})
    log(f"identity sugar: {rows[-1]}")
    left, right = orn_ids("ORN_DA1")
    inp = np.concatenate([left, right])
    rates = np.concatenate([np.full(left.size, 121.3), np.full(right.size, 118.2)])
    read = [DN_IDS["DNa02_L"], DN_IDS["DNa02_R"], *DNPE002_IDS.values(), *S.DNAE007.values()]
    outs = []
    for br in (off, unit):
        st = BrainStepper(br, inp, seed=0)
        ridx = br.index_of(read)
        outs.append(np.array([st.step(rates, 50.0).rates_hz(ridx) for _ in range(20)]))
    rows.append({"test": "unit vs off, DA1 121/118 Hz, 20 x 50 ms windows, DNa02/DNpe002/DNae007",
                 "identical": bool(np.array_equal(outs[0], outs[1])),
                 "total_spikes_off": float(outs[0].sum()), "total_spikes_unit": float(outs[1].sum())})
    log(f"identity DA1 windows: {rows[-1]}")
    del unit
    gc.collect()
    rel = S.build("release", n_threads=2)
    c = rel.run(excite=ex, duration_ms=1000.0, n_trials=30, seed=2000)
    rows.append({"test": "release (switch ON) vs off, sugar 200 Hz, seed 2000, 30 trials, all neurons",
                 "identical": bool(np.array_equal(a.trial, c.trial)
                                   and np.array_equal(a.neuron, c.neuron)
                                   and np.array_equal(a.step, c.step)),
                 "total_spikes_off": int(a.spike_counts.sum()),
                 "total_spikes_unit": int(c.spike_counts.sum())})
    log(f"identity release vs off, sugar: {rows[-1]}")
    pd.DataFrame(rows).to_csv(OUT / "identity_check.csv", index=False)
    del off, a, b, c
    gc.collect()
    # Phase 3 taste tests, switch ON
    ref = pd.read_csv(ROOT / "experiments" / "phase7_signs" / "results" / "table_phase3.csv")
    ref = ref[ref.config == "al_ln_literature"].set_index("condition")
    mn9 = rel.index_of([ids["MN9"], ids["MN9_IPSI"]])
    p3 = []
    for cond, (_, base) in TASTE.items():
        seed_means, ipsi_means = [], []
        for k in range(3):
            r = rel.run(excite=excite_for(cond, ids), duration_ms=1000.0, n_trials=30, seed=base + k)
            hz = r.rates_hz               # mean rate per neuron over the 30 trials
            seed_means.append(float(hz[mn9[0]]))
            ipsi_means.append(float(hz[mn9[1]]))
        rf = ref.loc[cond]
        p3.append({"condition": cond, "mn9_hz_switch_on": np.mean(seed_means),
                   "seed_means_on": "/".join(f"{x:.1f}" for x in seed_means),
                   "mn9_hz_switch_off": rf.mn9_hz, "seed_means_off": rf.seed_means,
                   "mn9_ipsi_hz_on": np.mean(ipsi_means), "mn9_ipsi_hz_off": rf.mn9_ipsi_hz,
                   "change_hz": np.mean(seed_means) - rf.mn9_hz, "paper": rf.paper})
        log(f"phase3 {cond}: MN9 {p3[-1]['mn9_hz_switch_on']:.2f} Hz on vs {rf.mn9_hz} off")
    pd.DataFrame(p3).to_csv(OUT / "phase3_check.csv", index=False, float_format="%.2f")


if __name__ == "__main__":
    what = sys.argv[1:] or ["anatomy", "run"]
    if "anatomy" in what:
        anatomy()
    if "run" in what:
        identity_and_phase3()
    log("done")
