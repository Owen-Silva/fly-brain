"""Which neurons set each network's spectral radius?

For the real matrix (recommended fix and published) and one shuffled control:
the top eigenvector's participation ratio (how many neurons it effectively
spans) and the neurons that carry it. Also the strongest two-neuron loops.
Writes results/top_mode.json and prints a short report.

Run: .venv\\Scripts\\python.exe experiments\\reservoir\\top_mode.py
"""
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_v] = "2"
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse.linalg import eigs

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

lib.wait_for_ram(1.5)
out = {}
lab_full = pd.read_parquet(lib.LABELS_630, columns=["root_id", "super_class", "cell_class",
                                                   "cell_type", "hemibrain_type", "top_nt"])
for name in ("real_fix", "real_none", "shuffle_0", "er_0"):
    fix = "none" if name == "real_none" else "al_ln_literature"
    root_ids, pre, post, w, _ = lib.load_edges(fix)
    n = root_ids.size
    if name == "shuffle_0":
        pre, post, w = lib.degree_shuffle(pre, post, w, 0)
    elif name == "er_0":
        pre, post, w = lib.erdos_renyi(pre, post, w, n, 0)
    m = lib.to_csr(pre, post, w, n).astype(np.float64)
    vals, vecs = eigs(m, k=6, which="LM", tol=1e-8, ncv=40, maxiter=20000)
    order = np.argsort(-np.abs(vals))
    vals, vecs = vals[order], vecs[:, order]
    lab = lab_full.set_index("root_id").reindex(root_ids).reset_index()
    res = {"eigenvalues": [[float(v.real), float(v.imag)] for v in vals], "modes": []}
    for k in range(3):
        v = vecs[:, k]
        p = np.abs(v) ** 2
        p /= p.sum()
        pr = float(1.0 / (p ** 2).sum())                 # participation ratio
        top = np.argsort(-p)[:8]
        res["modes"].append({
            "eigenvalue": [float(vals[k].real), float(vals[k].imag)],
            "participation_ratio_neurons": pr,
            "share_of_top_10_neurons": float(np.sort(p)[::-1][:10].sum()),
            "top_neurons": [{"root_id": int(root_ids[i]), "weight_share": float(p[i]),
                             "super_class": str(lab.super_class[i]),
                             "cell_class": str(lab.cell_class[i]),
                             "cell_type": str(lab.cell_type[i]),
                             "hemibrain_type": str(lab.hemibrain_type[i]),
                             "top_nt": str(lab.top_nt[i])} for i in top]})
    if name.startswith("real"):
        # strongest reciprocal excitatory pairs: sqrt(w_ij * w_ji) is the
        # eigenvalue of that two-neuron loop on its own
        mt = m.T.tocsr()
        both = m.multiply(mt).tocoo()          # w_ij * w_ji for pairs connected both ways
        keep = both.row < both.col
        r, c, prod = both.row[keep], both.col[keep], both.data[keep]
        posmask = prod > 0
        r, c, prod = r[posmask], c[posmask], prod[posmask]
        top = np.argsort(-prod)[:5]
        res["strongest_two_neuron_loops"] = [
            {"a": int(root_ids[r[i]]), "b": int(root_ids[c[i]]),
             "types": [str(lab.cell_type[r[i]]), str(lab.cell_type[c[i]])],
             "w_ab": float(m[c[i], r[i]]), "w_ba": float(m[r[i], c[i]]),
             "loop_gain_sqrt": float(np.sqrt(prod[i]))} for i in top]
    out[name] = res
    md = res["modes"][0]
    print(f"{name}: top eigenvalue {vals[0].real:.1f}{vals[0].imag:+.1f}j; participation "
          f"ratio {md['participation_ratio_neurons']:.1f} neurons; top-10 share "
          f"{md['share_of_top_10_neurons']:.2f}; top neurons "
          f"{[(t['cell_type'], round(t['weight_share'], 3)) for t in md['top_neurons'][:4]]}",
          flush=True)
    if "strongest_two_neuron_loops" in res:
        print("  strongest loops:", [(l["types"], round(l["loop_gain_sqrt"], 1))
                                     for l in res["strongest_two_neuron_loops"][:3]], flush=True)
    del m, pre, post, w, vecs
json.dump(out, open(lib.RESULTS / "top_mode.json", "w"), indent=1)
