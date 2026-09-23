"""PLAN.md Phase 6 checks on the surprising olfaction result ("a few smell
neurons firing once start activity that keeps itself going across ~8,000
neurons").

Plain English
-------------
1. Is it a bug in our fast engine? We re-simulate the same model with a
   completely separate, deliberately simple program written here (a plain
   sparse-matrix loop, the textbook solution of the two model equations, a
   ring buffer for the 1.8 ms delay). If it also shows self-sustained
   activity, the effect belongs to the model + wiring, not to the engine.
2. Does it survive parameter changes? Synapse strength w_syn at 80%, 90%,
   110%, 120% of the paper's value.
3. How many ORNs does it take? Volleys of 2, 3, 5 DM1 ORNs.
4. Is it specific to DM1? A volley of 10 DA2 ORNs.
5. Control: a volley of all 21 sugar GRNs (the paper's circuit). If the
   whole model just "ignites" from anything, this would ignite too.
6. Other random seeds for low-rate input (2 Hz, seeds 1 and 2).

Output: results/phase6_ignition_check.csv
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "competition"))
from phase5_common import get_brain, labels, paper_ids  # noqa: E402

OUT = HERE / "results"
brain = get_brain(globals())
lab = labels()
ht = lab.hemibrain_type
dm1 = lab.root_id[ht == "ORN_DM1"].tolist()
da2 = lab.root_id[ht == "ORN_DA2"].tolist()
sugar = paper_ids()["SUGAR"]
rows = []


def log(test, n_active, n_last, engine, extra=None):
    row = dict(test=test, engine=engine, n_active=int(n_active), n_firing_in_last_100ms=int(n_last))
    row.update(extra or {})
    rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "phase6_ignition_check.csv", index=False)
    print(row, flush=True)


def fast_volley(ids, params=None):
    res = brain.run_with_input_events([(np.full(len(ids), 50), ids)], excite=ids,
                                      duration_ms=1000.0, params=params)
    last = res.step >= 9000
    return (res.rates_hz > 0).sum(), np.unique(res.neuron[last]).size


# ---- 1. independent re-implementation --------------------------------------
def simple_sim(kick_ids, duration_ms=1000.0, p=brain.params):
    """Textbook version of the same model, written independently of
    sim/fast_engine.py. One kick of 68.75 mV to each listed neuron at 5 ms."""
    dt, tm, tau = p["dt"], p["t_mbr"], p["tau"]              # ms
    v0, vth, vr = p["v_0"], p["v_th"], p["v_rst"]            # mV
    w = p["w_syn"]                                           # mV per synapse
    n = brain.n_neurons
    # columns = sending neuron, rows = receiving neuron (signed synapse counts)
    W = sp.csc_matrix((brain._count.astype(np.float64) * w, brain._post, brain._indptr), shape=(n, n))
    a_g = np.exp(-dt / tau)
    a_v = np.exp(-dt / tm)
    b_vg = tau / (tau - tm) * (np.exp(-dt / tau) - np.exp(-dt / tm))   # effect of g on v over dt
    n_steps = int(round(duration_ms / dt))
    d_steps = int(round(p["t_dly"] / dt))
    r_steps = int(round(p["t_rfc"] / dt))
    v = np.full(n, v0)
    g = np.zeros(n)
    ref_until = np.full(n, -1)
    kick = brain.index_of(kick_ids)
    no_refr = np.zeros(n, bool)
    no_refr[kick] = True
    queue = [np.zeros(0, np.int64)] * (d_steps + 1)
    counts = np.zeros(n, np.int64)
    last_window = set()
    for t in range(n_steps):
        free = ref_until < t
        vn = v0 + (v - v0) * a_v + g * b_vg
        v = np.where(free, vn, v)
        g = np.where(free, g * a_g, g)
        spk = np.flatnonzero(v > vth)
        arriving = queue[t % (d_steps + 1)]
        if arriving.size:
            inp = np.asarray(W[:, arriving].sum(axis=1)).ravel()
            ok = free.copy()
            ok[spk] = False
            g[ok] += inp[ok]
        if t == 50:
            v[kick] += w * p["f_poi"]
        v[spk] = vr
        g[spk] = 0.0
        ref_until[spk] = np.where(no_refr[spk], t, t + r_steps)
        counts[spk] += 1
        queue[t % (d_steps + 1)] = np.zeros(0, np.int64)
        queue[(t + d_steps) % (d_steps + 1)] = spk
        if t >= n_steps - 1000:
            last_window.update(spk.tolist())
    return (counts > 0).sum(), len(last_window)


t0 = time.perf_counter()
na, nl = simple_sim(dm1[:10])
log("volley 10 DM1 ORNs", na, nl, "independent simple sim",
    dict(wall_s=round(time.perf_counter() - t0)))
na, nl = fast_volley(dm1[:10])
log("volley 10 DM1 ORNs", na, nl, "fast engine")
na, nl = simple_sim(sugar)
log("volley 21 sugar GRNs (control)", na, nl, "independent simple sim")

# ---- 2-5. fast engine variations -------------------------------------------
for f in (0.8, 0.9, 1.1, 1.2):
    na, nl = fast_volley(dm1[:10], params={"w_syn": brain.params["w_syn"] * f})
    log(f"volley 10 DM1 ORNs, w_syn x{f}", na, nl, "fast engine")
for k in (2, 3, 5):
    na, nl = fast_volley(dm1[:k])
    log(f"volley {k} DM1 ORNs", na, nl, "fast engine")
na, nl = fast_volley(da2[:10])
log("volley 10 DA2 ORNs", na, nl, "fast engine")
na, nl = fast_volley(sugar)
log("volley 21 sugar GRNs (control)", na, nl, "fast engine")
res = brain.run(excite=sugar, rate_hz=100, n_trials=1, seed=0, duration_ms=1000.0)
log("sugar GRNs 100 Hz for 1 s (control)", (res.rates_hz > 0).sum(),
    np.unique(res.neuron[res.step >= 9000]).size, "fast engine")

# ---- 6. other seeds ----------------------------------------------------------
for seed in (1, 2):
    res = brain.run(excite=dm1, rate_hz=2, n_trials=2, seed=seed)
    log(f"DM1 ORNs 2 Hz, seed {seed}", (res.rates_hz > 0).sum(),
        np.unique(res.neuron[res.step >= 9000]).size, "fast engine")
