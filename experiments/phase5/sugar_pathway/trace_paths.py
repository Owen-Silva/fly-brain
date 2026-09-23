"""Pathway tracing: sugar-sensing neurons -> MN9 (FlyWire snapshot 630).

Plain English
-------------
This is pure wiring-diagram analysis, no simulation. Think of the brain as a
road map: every neuron is a town and every connection "A sends N synapses to
B" is a one-way road. We ask two questions, separately for each of the two
MN9 feeding motor neurons:

(a) Fewest hops: what is the smallest number of connections a signal must
    cross to get from any of the 21 sugar-sensing neurons (GRNs) to MN9, and
    which neurons sit on those shortest routes?
(b) Strongest routes: give every road a "cost" that is low when the road is
    a big share of the receiving neuron's input:
        cost(A->B) = -log( synapses A->B / all input synapses of B ).
    Adding costs along a route = multiplying those input shares, so the
    cheapest route is the one where each neuron is the biggest possible
    share of the next one's input. We list the 20 strongest routes.

Sign matters. In this model a neuron that releases GABA or glutamate is
inhibitory: its spikes push the next neuron AWAY from firing. Every neuron in
the model is silent unless driven, so a route that passes through an
inhibitory neuron can never carry "go" to MN9. We therefore report
strongest routes twice: over all connections (inhibitory neurons flagged),
and over "excitatory-only" routes (every neuron on the route is excitatory),
which are the only ones that can actually carry the sugar signal to MN9.

The sign used is ``ref_sign``, the same sign the simulator uses (the
reference paper's own per-neuron sign).

Outputs (results/):
  paths_hops_<mn9>.csv        neurons on the fewest-hop routes, by layer
  paths_strongest_<mn9>.csv   top-20 strongest routes (all / excitatory-only)
  paths_summary.json          headline numbers
"""
import heapq
import json
import math
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from ids import SUGAR, MN9, MN9_B  # noqa: E402

CACHE = ROOT / "data" / "cache"
RES = HERE / "results"
K_PATHS = 20


def paper_name_map():
    """root_id -> the name the paper uses (ST1A names + SEZ split-GAL4 types)."""
    m = {}
    a = pd.read_csv(HERE / "paper_reference" / "paper_ST1A_sugar_firing.csv",
                    dtype={"Flywire ID": str})
    for rid, nm in zip(a["Flywire ID"], a["Neuron Name"]):
        if isinstance(rid, str) and rid.strip().isdigit() and isinstance(nm, str):
            m[int(rid)] = nm
    with open(ROOT / "data" / "reference" / "sez_neurons.pickle", "rb") as f:
        sez = pickle.load(f)
    for typ, ids in sez.items():
        for rid in ids:
            m.setdefault(int(rid), typ)
    return m


def load():
    nr = pd.read_parquet(CACHE / "connectome_630_neurons.parquet",
                         columns=["root_id", "cell_type", "hemibrain_type", "super_class",
                                  "cell_class", "side", "top_nt", "ref_sign"])
    nr["root_id"] = nr["root_id"].astype(np.int64)
    ed = pd.read_parquet(CACHE / "connectome_630_edges.parquet",
                         columns=["pre", "post", "syn_count", "ref_sign"])
    return nr, ed


def yen(adj, src, dst, k):
    """k cheapest loop-free paths from src to dst (Yen's algorithm).
    adj: {u: {v: cost}}. Returns list of (cost, [nodes])."""
    def dij(s, t, banned_nodes, banned_edges):
        dist = {s: 0.0}
        prev = {}
        pq = [(0.0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == t:
                path = [t]
                while path[-1] != s:
                    path.append(prev[path[-1]])
                return d, path[::-1]
            if d > dist.get(u, math.inf):
                continue
            for v, c in adj.get(u, {}).items():
                if v in banned_nodes or (u, v) in banned_edges:
                    continue
                nd = d + c
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        return None

    first = dij(src, dst, set(), set())
    if first is None:
        return []
    A = [first]
    B = []
    seen = {tuple(first[1])}
    while len(A) < k:
        _, last = A[-1]
        for i in range(len(last) - 1):
            spur = last[i]
            root = last[: i + 1]
            root_cost = sum(adj[root[j]][root[j + 1]] for j in range(i))
            banned_e = {(p[1][i], p[1][i + 1]) for p in A
                        if len(p[1]) > i + 1 and p[1][: i + 1] == root}
            banned_n = set(root[:-1])
            r = dij(spur, dst, banned_n, banned_e)
            if r is None:
                continue
            path = root[:-1] + r[1]
            if tuple(path) in seen:
                continue
            seen.add(tuple(path))
            heapq.heappush(B, (root_cost + r[0], path))
        if not B:
            break
        A.append(heapq.heappop(B))
    return A


def main():
    RES.mkdir(exist_ok=True)
    nr, ed = load()
    n = len(nr)
    names = paper_name_map()
    rid = nr["root_id"].to_numpy()
    idx_of = pd.Series(np.arange(n), index=rid)
    src = idx_of.loc[SUGAR].to_numpy()
    targets = {"MN9_main": MN9, "MN9_second": MN9_B}

    # --- bug checks -------------------------------------------------------
    sign_pre = nr["ref_sign"].to_numpy()[ed["pre"].to_numpy()]
    mism = int((sign_pre != ed["ref_sign"].to_numpy()).sum())
    checks = {"edge_sign_vs_neuron_sign_mismatches": mism,
              "mn9_cell_types": {k: str(nr.loc[idx_of[v], "cell_type"]) for k, v in targets.items()},
              "sugar_grn_cell_types": nr.loc[src, "cell_type"].astype(str).value_counts().to_dict(),
              "sugar_grn_signs": nr.loc[src, "ref_sign"].value_counts().to_dict()}
    print(json.dumps(checks))

    pre = ed["pre"].to_numpy()
    post = ed["post"].to_numpy()
    w = ed["syn_count"].to_numpy().astype(np.float64)
    in_tot = np.bincount(post, weights=w, minlength=n)
    frac = w / in_tot[post]
    cost = -np.log(frac)
    cost = np.maximum(cost, 1e-12)          # csgraph treats 0 as "no edge"
    exc = sign_pre > 0
    # pooled sugar input: all 21 GRNs treated as one source; share of each
    # target's total input that comes from the sugar GRNs together
    from_grn = np.isin(pre, src) & ~np.isin(post, src)
    grn_syn = np.bincount(post[from_grn], weights=w[from_grn], minlength=n)
    pooled_cols = np.flatnonzero(grn_syn > 0)
    pooled_cost = np.maximum(-np.log(grn_syn[pooled_cols] / in_tot[pooled_cols]), 1e-12)
    del ed, frac, w, in_tot, from_grn

    # hop counts use the same matrices with unweighted=True (saves memory)
    A_cost = sp.csr_matrix((cost, (pre, post)), shape=(n, n))
    A_cost_exc = sp.csr_matrix((cost[exc], (pre[exc], post[exc])), shape=(n, n))
    frac_lookup = {}  # filled per subgraph

    def label(i):
        if i == n:
            return "SUGAR_GRNs(21 pooled)(+)"
        r = int(rid[i])
        ct = nr.at[i, "cell_type"]
        ct = ct if isinstance(ct, str) and ct else "?"
        pn = names.get(r, "")
        sgn = "+" if nr.at[i, "ref_sign"] > 0 else "-"
        return f"{ct}{'/' + pn if pn else ''}({sgn})"

    summary = {"checks": checks, "targets": {}}
    for tname, tid in targets.items():
        t = int(idx_of[tid])
        out = {}
        # (a) fewest hops ------------------------------------------------
        for variant, H in (("all", A_cost), ("exc_only", A_cost_exc)):
            ds = dijkstra(H, directed=True, indices=src, unweighted=True, min_only=True)
            dt = dijkstra(H.T.tocsr(), directed=True, indices=[t], unweighted=True, min_only=True)
            D = ds[t]
            on = np.flatnonzero(np.isfinite(ds) & np.isfinite(dt) & (ds + dt == D))
            # number of shortest routes through each node (forward x backward counts)
            fwd = {i: 1 for i in on if ds[i] == 0}
            bwd = {t: 1}
            Hc = H.tocsr()
            HT = H.T.tocsr()
            onset = set(on.tolist())
            for layer in range(1, int(D) + 1):
                for v in on[ds[on] == layer]:
                    preds = HT.indices[HT.indptr[v]:HT.indptr[v + 1]]
                    fwd[v] = sum(fwd.get(u, 0) for u in preds if u in onset and ds[u] == layer - 1)
            for layer in range(int(D) - 1, -1, -1):
                for v in on[ds[on] == layer]:
                    succ = Hc.indices[Hc.indptr[v]:Hc.indptr[v + 1]]
                    bwd[v] = sum(bwd.get(u, 0) for u in succ if u in onset and ds[u] == layer + 1)
            n_routes = fwd[t]
            rows = pd.DataFrame({
                "root_id": rid[on].astype(np.int64), "hop_from_grn": ds[on].astype(int),
                "routes_through": [fwd[i] * bwd[i] for i in on],
                "cell_type": nr.loc[on, "cell_type"].to_numpy(),
                "super_class": nr.loc[on, "super_class"].to_numpy(),
                "side": nr.loc[on, "side"].to_numpy(),
                "top_nt": nr.loc[on, "top_nt"].to_numpy(),
                "sign": nr.loc[on, "ref_sign"].to_numpy(),
                "paper_name": [names.get(int(r), "") for r in rid[on]],
            }).sort_values(["hop_from_grn", "routes_through"], ascending=[True, False])
            rows["share_of_routes"] = rows["routes_through"] / n_routes
            rows.to_csv(RES / f"paths_hops_{tname}_{variant}.csv", index=False)
            out[f"hops_{variant}"] = {
                "min_hops": int(D), "n_shortest_routes": int(n_routes),
                "n_neurons_on_shortest_routes_excl_grn_and_mn9": int(len(on) - (ds[on] == 0).sum() - 1),
                "n_inhibitory_on_routes": int((rows["sign"] < 0).sum()),
            }
            print(tname, variant, out[f"hops_{variant}"])

        # (b) strongest routes -------------------------------------------
        allrows = []
        for variant, C0, pooled in (("all_pooled", A_cost, True), ("exc_only_pooled", A_cost_exc, True),
                                    ("all_per_grn", A_cost, False), ("exc_only_per_grn", A_cost_exc, False)):
            if pooled:   # extra node n = "all sugar GRNs together"
                C = sp.csr_matrix((np.concatenate([C0.data, pooled_cost]),
                                   np.concatenate([C0.indices, pooled_cols]),
                                   np.concatenate([C0.indptr, [C0.indptr[-1] + len(pooled_cols)]])),
                                  shape=(n + 1, n + 1))
                srcs = [n]
            else:
                C = C0
                srcs = src
            ds = dijkstra(C, directed=True, indices=srcs, min_only=True)
            dt = dijkstra(C.T.tocsr(), directed=True, indices=[t], min_only=True)
            best = ds[t]
            margin = math.log(1000.0)
            while True:
                keep = np.flatnonzero(ds + dt <= best + margin)
                if len(keep) <= 4000 or margin < 1:
                    break
                margin *= 0.7
            keep_set = set(keep.tolist())
            Cc = C.tocsr()
            adj = {"S": {int(s): 0.0 for s in srcs if s in keep_set}}
            for u in keep:
                cols = Cc.indices[Cc.indptr[u]:Cc.indptr[u + 1]]
                vals = Cc.data[Cc.indptr[u]:Cc.indptr[u + 1]]
                d = {int(v): float(c) for v, c in zip(cols, vals) if v in keep_set and v not in src}
                if d:
                    adj[int(u)] = d
            paths = yen(adj, "S", t, K_PATHS)
            for rank, (c, p) in enumerate(paths, 1):
                p = p[1:]
                signs = [int(nr.at[i, "ref_sign"]) for i in p[:-1] if i < n]
                inhib = [label(i) for i in p[1:-1] if i < n and nr.at[i, "ref_sign"] < 0]
                allrows.append({
                    "variant": variant, "rank": rank, "strength": math.exp(-c), "cost": c,
                    "n_hops": len(p) - 1,
                    "route": " -> ".join(label(i) for i in p),
                    "route_ids": " ".join("GRNS" if i == n else str(int(rid[i])) for i in p),
                    "passes_inhibitory": bool(inhib), "inhibitory_neurons": "; ".join(inhib),
                    "net_sign": int(np.prod(signs)),
                    "edge_input_shares": " ".join(f"{math.exp(-adj[a][b]):.3f}" for a, b in zip(p[:-1], p[1:])),
                })
            out[f"strongest_{variant}"] = {"best_strength": float(math.exp(-best)),
                                           "subgraph_neurons": int(len(keep)),
                                           "n_paths_listed": len(paths)}
            print(tname, variant, out[f"strongest_{variant}"])
            del C, Cc
        pd.DataFrame(allrows).to_csv(RES / f"paths_strongest_{tname}.csv", index=False)
        summary["targets"][tname] = out
    (RES / "paths_summary.json").write_text(json.dumps(summary, indent=1, default=int),
                                            encoding="utf-8")


if __name__ == "__main__":
    main()
