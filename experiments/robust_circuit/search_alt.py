"""Step 2b: a second removal order, neurons only (PRELIMINARY).

Same rule, scoring and start as search.py, but neurons are tried in a random
order (numpy seed 1) instead of weakest path score first. Neuron blocks
100 -> 2, then single-neuron rounds until a round removes nothing. No
connection pruning. Tells us whether the main search's size depends on the
removal order.

Usage: search_alt.py [budget minutes]
Outputs
  results/search_log_alt.csv
  results/raw/checkpoints_alt.json
"""

import csv
import json
import sys

import numpy as np

import search as S0
from rcommon import MC_RES, RAW, RES

S0.BUDGET_S = float(sys.argv[1]) * 60 if len(sys.argv) > 1 else 15 * 60
T = S0.T


class AltSearch(S0.Search):
    def save(self):
        keys = []
        for r in self.rows:
            keys += [k for k in r if k not in keys]
        with open(RES / "search_log_alt.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(self.rows)
        (RAW / "checkpoints_alt.json").write_text(json.dumps(
            {"label": "PRELIMINARY", "order": "random, numpy seed 1",
             "checkpoints": self.checkpoints}))


def main():
    S = AltSearch()
    g = S.g
    cps = json.loads((MC_RES / "checkpoints.json").read_text())["checkpoints"]
    kn = np.zeros(g.n, bool)
    kn[cps[2]["nodes"]] = True
    ke = g.edges(kn, np.ones(g.m, bool))
    ok, row = S.evaluate(kn, ke, "0-start", "400-neuron start", full=True)
    S.accept(kn, ke, "0-start", row)
    rng = np.random.default_rng(1)
    base_order = [int(i) for i in rng.permutation(np.flatnonzero(kn))]
    kn, ke, _ = S.greedy(kn, ke, base_order, "n", "1-neuron-blocks", min_block=2,
                         start_block=100, floor=0.3 * S0.BUDGET_S)
    rnd = 0
    while S0.left() > 0:
        rnd += 1
        items = [i for i in base_order if kn[i]]
        n0 = int(kn.sum())
        kn, ke, fin = S.greedy(kn, ke, items, "n", f"2-single-neuron-r{rnd}", min_block=1,
                               start_block=1, floor=0.0)
        if fin and int(kn.sum()) == n0:
            break
    S.save()
    T.log(f"alt final: {g.stats(kn, ke)}; {S.n_eval} evaluations; rounds {rnd}")


if __name__ == "__main__":
    main()
