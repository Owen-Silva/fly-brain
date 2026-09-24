"""POST HOC diagnostics (not pre-registered): WHY does the real wiring code odours worse?

Main settings (k = 5%, T = 0.05 s, set A+B, all synapses), same noisy trials as the main run
(seed s -> rng [s, 101]), 20 seeds, both halves. The fly read-out's final accuracy does not
depend on task order (all changes are >= 0), so "final accuracy" here = train on all 110
odours, test on all 110, exactly as after task 10 in the main run.

D1 "odour channels only": the 9 glomeruli without odour data (DA1, VA7m, VC1, VC3m, VC5,
   VP1d, VP1m, VP2, VP4; the VP ones sense temperature/humidity) are removed from the wiring
   first; KCs left without input are dropped; controls are built from this reduced wiring.
D2 "subtype-matched shuffle": a stricter control. Each KC's glomeruli are drawn with the
   frequencies of ITS OWN lobe class (gamma, alpha/beta, alpha'/beta'), so the known
   subtype preferences are kept and only the finer structure is randomised.
D3 code statistics on the noise-free odour inputs: share of KCs silent to all 110 odours,
   mean correlation between the KC codes of different odours (lower = more distinct), the
   same for the PN input, and the mean overlap of the active sets of two noisy trials of the
   same odour (reliability).
Writes results/diagnostics.csv and results/diagnostics_summary.csv.
"""
import numpy as np
import pandas as pd

from common import (RES, FlyReadout, Wiring, all_glomeruli, control_wiring, glomerulus_kc_table,
                    kc_code, load_odours, log, make_trials, pn_mean, real_wiring, wait_for_ram)
from analyze import compare

N_SEEDS, K, T = 20, 0.05, 0.05
N_TR, N_TE = 20, 20


def lobe(t):
    t = str(t)
    return "g" if t.startswith("KCg") else ("ab" if t.startswith("KCab") else "apbp")


def shuffle_by_type(real, rng):
    """Control (a) done separately within each KC lobe class."""
    out = np.zeros_like(real.W)
    lob = np.array([lobe(t) for t in real.kc_types])
    for L in np.unique(lob):
        rows = np.flatnonzero(lob == L)
        sub = Wiring("real", real.side, real.W[rows], real.gloms, real.kc_types[rows])
        out[rows] = control_wiring(sub, "shuffled", rng).W
    return Wiring("shuffled_by_type", real.side, out, real.gloms, real.kc_types)


def restrict(real, keep):
    W = real.W * keep[None, :]
    rows = W.sum(1) > 0
    return Wiring("real", real.side, W[rows], real.gloms, real.kc_types[rows])


def code_stats(W, P, X2, y2):
    H = kc_code(W, P.astype(np.float32), K)
    act = H > 0
    silent = float((~act.any(0)).mean())
    C = np.corrcoef(H)
    iu = np.triu_indices(H.shape[0], 1)
    Hn = kc_code(W, X2, K) > 0
    a, b = Hn[0::2], Hn[1::2]          # two noisy trials per odour, interleaved
    overlap = (a & b).sum(1) / np.maximum(a.sum(1), 1)
    return {"silent_kc_share": silent, "kc_code_corr": float(np.nanmean(C[iu])),
            "trial_overlap": float(overlap.mean())}


def main():
    wait_for_ram()
    table, _ = glomerulus_kc_table()
    gloms = all_glomeruli()
    od = load_odours(gloms)
    P = pn_mean(od.delta, od.set_a)
    n_od = P.shape[0]
    Cp = np.corrcoef(P)
    iu = np.triu_indices(n_od, 1)
    pn_corr = float(np.nanmean(Cp[iu]))
    rows = []
    for seed in range(N_SEEDS):
        rng_tr = np.random.default_rng([seed, 101])
        Xtr, ytr = make_trials(P, N_TR, T, rng_tr)
        Xte, yte = make_trials(P, N_TE, T, rng_tr)
        X2, y2 = make_trials(P, 2, T, np.random.default_rng([seed, 808]))
        for si, side in enumerate(("left", "right")):
            real = real_wiring(side, table=table, gloms=gloms)
            wr = np.random.default_rng([seed, 303, si])      # same stream as the main run
            sets = {"main": [real, control_wiring(real, "shuffled", wr),
                             control_wiring(real, "uniform", wr)]}
            sets["main"].append(shuffle_by_type(real, np.random.default_rng([seed, 909, si])))
            red = restrict(real, od.has_data)
            wr2 = np.random.default_rng([seed, 910, si])
            sets["odour_channels_only"] = [red, control_wiring(red, "shuffled", wr2),
                                           control_wiring(red, "uniform", wr2)]
            for setname, ws in sets.items():
                for w in ws:
                    Htr, Hte = kc_code(w.W, Xtr, K), kc_code(w.W, Xte, K)
                    fly = FlyReadout(w.W.shape[0], n_od)
                    fly.train(Htr, ytr)
                    acc = float((fly.predict(Hte, np.arange(n_od)) == yte).mean())
                    row = {"seed": seed, "side": side, "set": setname, "wiring": w.name,
                           "n_kc": w.W.shape[0], "final_acc": acc}
                    if seed < 5:
                        row.update(code_stats(w.W, P, X2, y2))
                        lob = np.array([lobe(t) for t in w.kc_types])
                        share = (Hte > 0).mean(0)
                        for L in ("g", "ab", "apbp"):
                            row[f"active_share_{L}"] = float(share[lob == L].sum() / share.sum())
                    rows.append(row)
        log(f"seed {seed} done")
        pd.DataFrame(rows).assign(pn_input_corr=pn_corr).to_csv(RES / "diagnostics.csv", index=False)
    d = pd.DataFrame(rows)
    summ = d.groupby(["set", "side", "wiring"]).mean(numeric_only=True).drop(columns="seed")
    summ.to_csv(RES / "diagnostics_summary.csv")
    comp = []
    for setname in d.set.unique():
        for side in ("left", "right"):
            x = d[(d.set == setname) & (d.side == side)].pivot(index="seed", columns="wiring",
                                                               values="final_acc")
            for ctl in [c for c in x.columns if c != "real"]:
                comp.append({"set": setname, "side": side, "control": ctl,
                             **compare(x["real"], x[ctl])})
    pd.DataFrame(comp).to_csv(RES / "diagnostics_compare.csv", index=False)
    log("done")


if __name__ == "__main__":
    main()
