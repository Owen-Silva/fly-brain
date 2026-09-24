"""Build standalone circuits from the touched-neuron wiring (PRELIMINARY).

A circuit is a set of kept neurons plus a set of kept connections, both taken
from results/raw/touched_graph.npz (every neuron that received any input in
the whole-brain search-seed runs, and the wiring among them). ``build()``
turns it into its own FastBrain with ``FastBrain.from_arrays``: nothing else
of the brain is present.
"""

import heapq

import numpy as np

from common import MN9, RAW, paper_ids


class TouchedGraph:
    def __init__(self):
        z = np.load(RAW / "touched_graph.npz")
        self.root_ids = z["root_ids"]
        self.spiked = z["spiked"]
        idx = {int(r): i for i, r in enumerate(self.root_ids)}
        self.idx = idx
        self.pre = np.array([idx[int(r)] for r in z["pre_root"]], np.int64)
        self.post = np.array([idx[int(r)] for r in z["post_root"]], np.int64)
        self.signed = z["signed"].astype(np.int64)
        self.n = self.root_ids.size
        self.m = self.pre.size
        ids = paper_ids()
        self.ids = ids
        self.mn9 = idx[MN9]
        self.stim = {g: np.array([idx[r] for r in ids[g] if r in idx], np.int64)
                     for g in ("SUGAR", "WATER", "BITTER")}
        self.sources = np.concatenate(list(self.stim.values()))

    # -- building ---------------------------------------------------------
    def edges(self, keep_n, keep_e=None):
        ke = keep_n[self.pre] & keep_n[self.post]
        if keep_e is not None:
            ke &= keep_e
        return ke

    def build(self, keep_n, keep_e=None, params=None):
        from sim.fast_engine import FastBrain
        ke = self.edges(keep_n, keep_e)
        new = np.cumsum(keep_n) - 1
        return FastBrain.from_arrays(self.root_ids[keep_n], new[self.pre[ke]],
                                     new[self.post[ke]], self.signed[ke], params=params,
                                     n_threads=1)

    def stats(self, keep_n, keep_e=None):
        ke = self.edges(keep_n, keep_e)
        return {"n_neurons": int(keep_n.sum()), "n_connections": int(ke.sum()),
                "n_synapses": int(np.abs(self.signed[ke]).sum())}

    # -- lossless cleanup -------------------------------------------------
    def reach(self, keep_n, keep_e, starts, forward=True):
        """Neurons reachable from ``starts`` (forward) or that reach them
        (backward), using kept neurons and connections only."""
        ke = self.edges(keep_n, keep_e)
        a, b = (self.pre[ke], self.post[ke]) if forward else (self.post[ke], self.pre[ke])
        order = np.argsort(a, kind="stable")
        a, b = a[order], b[order]
        ptr = np.searchsorted(a, np.arange(self.n + 1))
        seen = np.zeros(self.n, bool)
        stack = [int(s) for s in starts if keep_n[s]]
        for s in stack:
            seen[s] = True
        while stack:
            u = stack.pop()
            for v in b[ptr[u]:ptr[u + 1]]:
                if not seen[v]:
                    seen[v] = True
                    stack.append(int(v))
        return seen

    def cleanup(self, keep_n, keep_e=None):
        """Drop neurons that no taste neuron can reach or that cannot reach
        MN9. They can never change MN9, so this never changes the result."""
        f = self.reach(keep_n, keep_e, self.sources, True)
        b = self.reach(keep_n, keep_e, [self.mn9], False)
        out = keep_n & f & b
        out[self.mn9] = True
        return out

    # -- path strength ----------------------------------------------------
    def widest(self, strength, keep_n, starts, forward=True):
        """Bottleneck ("widest path") strength from ``starts`` to every neuron
        (forward) or from every neuron to ``starts`` (backward)."""
        ke = self.edges(keep_n) & (strength > 0)
        a, b = (self.pre[ke], self.post[ke]) if forward else (self.post[ke], self.pre[ke])
        w = strength[ke]
        order = np.argsort(a, kind="stable")
        a, b, w = a[order], b[order], w[order]
        ptr = np.searchsorted(a, np.arange(self.n + 1))
        best = np.zeros(self.n)
        heap = []
        for s in starts:
            if keep_n[s]:
                best[s] = np.inf
                heap.append((-np.inf, int(s)))
        heapq.heapify(heap)
        done = np.zeros(self.n, bool)
        while heap:
            negw, u = heapq.heappop(heap)
            if done[u]:
                continue
            done[u] = True
            cu = -negw
            for k in range(ptr[u], ptr[u + 1]):
                v = b[k]
                c = min(cu, w[k])
                if c > best[v]:
                    best[v] = c
                    heapq.heappush(heap, (-c, int(v)))
        return best
