"""Bug checks (PLAN.md Phase 6 step 2) that need no simulation.

1. Controls: edge count, self-connections, degrees, weight lists, Dale's law.
2. Real network: build_brain(fix=FIX) matches the arrays the controls start from.
3. Input: kicks per sensory neuron vs the intended push-pull rates.
4. Readout neurons: none is sensory.
5. (after the main run) measured sensory firing rates in the raw files.
Writes results/checks.json.
"""
import json

import numpy as np

import lib_spk as L

R = L.rlib
R.wait_for_ram(2.0)
out = {}
root_ids, pre, post, signed, rep = L.real_arrays()
n = len(root_ids)
lab = R.labels(root_ids)
sc = lab.super_class.to_numpy()
sens = np.flatnonzero(sc == "sensory")
nonsens = np.flatnonzero(sc != "sensory")
w_sorted = np.sort(signed)
outdeg = np.bincount(pre, minlength=n)
indeg = np.bincount(post, minlength=n)


def mixed_sign_neurons(p, w):
    pos = np.bincount(p, weights=(w > 0), minlength=n) > 0
    neg = np.bincount(p, weights=(w < 0), minlength=n) > 0
    return int((pos & neg).sum())


out["real"] = {"edges": int(pre.size), "self_loops": int((pre == post).sum()),
               "mixed_sign_senders": mixed_sign_neurons(pre, signed)}
for seed in (0, 1, 2):
    p, q, w = R.degree_shuffle(pre, post, signed, seed, no_self=True)
    out[f"shuffle_s{seed}"] = {
        "edges": int(p.size), "self_loops": int((p == q).sum()),
        "out_degree_same": bool(np.array_equal(np.bincount(p, minlength=n), outdeg)),
        "in_degree_same": bool(np.array_equal(np.bincount(q, minlength=n), indeg)),
        "weights_same_list": bool(np.array_equal(np.sort(w), w_sorted)),
        "mixed_sign_senders": mixed_sign_neurons(p, w),
        "frac_edges_same_target": float((q == post).mean())}
    del p, q, w
    p, q, w = R.erdos_renyi(pre, post, signed, n, seed, no_self=True)
    out[f"er_s{seed}"] = {
        "edges": int(p.size), "self_loops": int((p == q).sum()),
        "weights_same_list": bool(np.array_equal(np.sort(w), w_sorted)),
        "mixed_sign_senders": mixed_sign_neurons(p, w),
        "max_out_degree": int(np.bincount(p, minlength=n).max()),
        "real_max_out_degree": int(outdeg.max())}
    del p, q, w

brain = L.make_brain("real", 0, (root_ids, pre, post, signed))
out["build_brain_matches_arrays"] = {
    "connections": brain.n_connections == pre.size,
    "sum_signed": int(brain._count.sum()) == int(signed.sum()),
    "abs_sum": int(np.abs(brain._count).sum()) == int(np.abs(signed).sum())}
del brain

# input: 400 bins, peak 150 Hz
u, _ = R.make_input(400, 0)
signs = L.input_signs(sens.size, 0)
rng = np.random.default_rng(5)
ev_ptr, ev_neu = L.poisson_events(L.rates_for(u, signs, 150.0), sens, rng)
steps = np.repeat(np.arange(ev_ptr.size - 1), np.diff(ev_ptr))
b = steps // L.SUB
col = np.full(n, -1)
col[sens] = np.arange(sens.size)
k = np.zeros((400, sens.size))
np.add.at(k, (b, col[ev_neu]), 1)
plus, minus = signs > 0, signs < 0
got_p = k[:, plus].mean(1) / (L.BIN_MS * 1e-3)
got_m = k[:, minus].mean(1) / (L.BIN_MS * 1e-3)
out["input"] = {"n_plus": int(plus.sum()), "n_minus": int(minus.sum()),
                "all_events_on_sensory": bool(np.isin(ev_neu, sens).all()),
                "corr_plus_rate_vs_u": float(np.corrcoef(got_p, u)[0, 1]),
                "corr_minus_rate_vs_u": float(np.corrcoef(got_m, u)[0, 1]),
                "mean_rate_plus_hz": float(got_p.mean()), "mean_rate_minus_hz": float(got_m.mean()),
                "intended_mean_plus_hz": float((150 * 2 * u).mean()),
                "intended_mean_minus_hz": float((150 * (1 - 2 * u)).mean())}
for seed in (0, 1, 2):
    pool = np.random.default_rng(np.random.SeedSequence([seed, 3])).choice(nonsens, 1000,
                                                                           replace=False)
    out[f"pool_s{seed}_sensory_overlap"] = int(np.isin(pool, sens).sum())

# measured sensory rates from the main run (if present)
meas = {}
for f in sorted(L.RAW.glob("main_*_s0_p*_w100.npz")):
    z = np.load(f)
    meas[f.stem] = float(z["totals"][sens].mean() / 40.0)
out["measured_sensory_mean_rate_hz_seed0"] = meas
(L.RESULTS / "checks.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
