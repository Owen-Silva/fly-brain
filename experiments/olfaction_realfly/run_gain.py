"""Steps for facts F3 and F4: the ORN -> PN transfer curve and lateral inhibition, done the
way Olsen et al. 2010 did it in real flies.

One "private" glomerulus (DL5, DM4, DM1 or VM7d) gets its own ORNs driven at its
spontaneous rate + [0, 5, 10, 20, 40, 80, 160] spikes/s. Every other ORN type gets either
its spontaneous rate only ("no public odour") or spontaneous + 0.5x or 1x the Hallem &
Carlson pentyl acetate response ("public odour"; Olsen 2010 used pentyl acetate the same
way). The private glomerulus is always left out of the public pattern.
Model: recommended fix "al_ln_literature". 3 seeds x 4 trials x 0.5 s per condition.
Saves results/gain_trials.csv (one row per trial: uPN mean rate of the private glomerulus,
KC fraction, LN mean rate).
"""
from __future__ import annotations

import gc
import time

import numpy as np
import pandas as pd

from common import (DEFAULT_SFR_HZ, N_THREADS, RES, groups, load_labels, odour_rates,
                    wait_for_ram)
from sim.sign_fixes import build_brain

GLOMS = ["DL5", "DM4", "DM1", "VM7d"]
PRIVATE_DELTA = [0, 5, 10, 20, 40, 80, 160]
PUBLIC_SCALE = [0.0, 0.5, 1.0]
PUBLIC_ODOUR = "pentyl acetate"
SEEDS = (0, 1, 2)
TRIALS = 4
DUR = 500.0


def main():
    out = RES / "gain_trials.csv"
    done = set()
    if out.exists():
        d = pd.read_csv(out)
        done = set(zip(d.glom, d.private_delta, d.public_scale, d.seed))
    hc = pd.read_csv(RES / "hc_delta.csv", index_col=0)
    pub = hc[hc.odour == PUBLIC_ODOUR].drop(columns="odour").iloc[0].to_dict()
    sfr = pd.read_csv(RES / "hc_sfr.csv", index_col=0)["sfr_hz"].to_dict()
    wait_for_ram()
    brain = build_brain(fix="al_ln_literature", n_threads=N_THREADS)
    lab = load_labels(brain.root_ids)
    g = groups(lab)
    kc = g["kc"]
    ln = g["ln"]
    for glo in GLOMS:
        upn = g["upn"][g["upn_glom"] == glo]
        print(f"{glo}: {upn.size} uPNs, {int((g['orn_glom'] == glo).sum())} ORNs", flush=True)
        for sc in PUBLIC_SCALE:
            for dp in PRIVATE_DELTA:
                rows = []
                t0 = time.perf_counter()
                for seed in SEEDS:
                    if (glo, dp, sc, seed) in done:
                        continue
                    delta = {k: sc * v for k, v in pub.items() if k != glo}
                    delta[glo] = float(dp)
                    rates = odour_rates(brain.root_ids, g, sfr, delta)
                    res = brain.run(excite=rates, duration_ms=DUR, n_trials=TRIALS, seed=seed)
                    for t in range(TRIALS):
                        m = res.trial == t
                        c = np.bincount(res.neuron[m], minlength=brain.n_neurons)
                        rows.append({"glom": glo, "private_delta": dp, "public_scale": sc,
                                     "seed": seed, "trial": t,
                                     "private_orn_hz": float(sfr.get(glo, DEFAULT_SFR_HZ) + dp),
                                     "upn_hz": c[upn].mean() / (DUR / 1000),
                                     "upn_hz_each": ";".join(f"{x / (DUR / 1000):.0f}" for x in c[upn]),
                                     "kc_frac": float((c[kc] > 0).mean()),
                                     "ln_hz": c[ln].mean() / (DUR / 1000),
                                     "total_orn_hz": float(sum(rates.values()))})
                if rows:
                    df = pd.DataFrame(rows)
                    df.to_csv(out, mode="a", header=not out.exists(), index=False)
                    print(f"  pub x{sc} private +{dp:3d} Hz: uPN {df.upn_hz.mean():6.1f} Hz "
                          f"({time.perf_counter()-t0:.1f} s)", flush=True)
    del brain
    gc.collect()


if __name__ == "__main__":
    main()
