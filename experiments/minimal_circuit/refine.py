"""Step 2b: repeat single-neuron and single-connection removal (PRELIMINARY).

search.py did one single-neuron pass and then one single-connection pass.
Removing connections can make more neurons removable, so this repeats both
passes from the last checkpoint until a round removes nothing (or the time
budget runs out). Same search seed, trials and stricter search rule.
Appends to results/search_log.csv and results/checkpoints.json.
"""

import csv
import json
import sys
import time

import numpy as np

import search
from common import RES
from search import Search, log

BUDGET_MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 15


def main():
    search.BUDGET_S = BUDGET_MIN * 60
    search.T0 = time.perf_counter()
    S = Search()
    g = S.g
    old = json.loads((RES / "checkpoints.json").read_text())
    S.checkpoints = old["checkpoints"]
    with open(RES / "search_log.csv", newline="") as f:
        S.rows = list(csv.DictReader(f))
    S.n_eval = len(S.rows)
    last = S.checkpoints[-1]
    keep = np.zeros(g.n, bool)
    keep[last["nodes"]] = True
    ke = np.zeros(g.m, bool)
    ke[last["edges"]] = True
    score = np.load(search.RAW / "path_score.npy")
    rnd = 0
    while search.left() > 0:
        rnd += 1
        before = (int(keep.sum()), int(g.edges(keep, ke).sum()))
        items = [int(i) for i in np.argsort(score, kind="stable") if keep[i]]
        keep, ke, _ = S.greedy(keep, ke, items, "n", f"5-single-neuron-r{rnd + 1}",
                               min_block=1, start_block=1)
        live = np.flatnonzero(g.edges(keep, ke))
        e_items = [int(i) for i in live[np.argsort(S.strength[live], kind="stable")]]
        keep, ke, _ = S.greedy(keep, ke, e_items, "e", f"5-single-conn-r{rnd + 1}",
                               min_block=1, start_block=1)
        after = (int(keep.sum()), int(g.edges(keep, ke).sum()))
        log(f"round {rnd + 1}: {before} -> {after}")
        if after == before:
            break
    S.save()
    summ = json.loads((RES / "search_summary.json").read_text())
    summ["refine"] = {"rounds": rnd, "final": g.stats(keep, ke),
                      "converged": after == before}
    (RES / "search_summary.json").write_text(json.dumps(summ, indent=1))
    log(f"final after refine: {g.stats(keep, ke)}")


if __name__ == "__main__":
    main()
