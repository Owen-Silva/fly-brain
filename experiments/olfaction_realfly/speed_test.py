"""Quick check before the main runs: how long does one odour trial take, and does the
spontaneous-only input (no odour) stay quiet in each model?"""
import gc
import sys
import time

import numpy as np
import pandas as pd

from common import (N_THREADS, RES, groups, load_labels, odour_rates, readout_rows,
                    summarise, wait_for_ram)
from sim.sign_fixes import build_brain

fixes = sys.argv[1:] or ["al_ln_literature", "none"]
hc = pd.read_csv(RES / "hc_delta.csv", index_col=0)
sfr = pd.read_csv(RES / "hc_sfr.csv", index_col=0)["sfr_hz"].to_dict()
for fix in fixes:
    wait_for_ram()
    t0 = time.perf_counter()
    brain = build_brain(fix=fix, n_threads=N_THREADS)
    lab = load_labels(brain.root_ids)
    g = groups(lab)
    rows, sl = readout_rows(g)
    print(f"{fix}: built in {time.perf_counter()-t0:.0f} s", flush=True)
    for name in ["baseline", "1-hexanol", "ethyl butyrate"]:
        if name == "baseline":
            d = {}
        else:
            d = hc[hc.odour == name].drop(columns="odour").iloc[0].to_dict()
        rates = odour_rates(brain.root_ids, g, sfr, d)
        t0 = time.perf_counter()
        res = brain.run(excite=rates, duration_ms=500.0, n_trials=3, seed=0)
        dt = time.perf_counter() - t0
        counts, stats = summarise(res, rows, brain.n_neurons, exclude=g["orn"])
        kc = counts[:, sl["kc"][0]:sl["kc"][1]]
        upn_rows = np.searchsorted(rows[sl["pn"][0]:sl["pn"][1]], g["upn"]) + sl["pn"][0]
        up = counts[:, upn_rows] / 0.5
        print(f"  {name}: {dt:.1f} s for 3 x 0.5 s; spikes/trial {np.mean([s['total_spikes'] for s in stats]):.0f}; "
              f"runaway {[s['runaway'] for s in stats]}; max10ms {[s['max_distinct_10ms'] for s in stats]}; "
              f"KC>=1 spike {100*(kc>0).mean():.2f}%; uPN mean {up.mean():.1f} Hz; "
              f"APL {counts[:, sl['apl'][0]:sl['apl'][1]].mean()/0.5:.1f} Hz", flush=True)
    del brain
    gc.collect()
