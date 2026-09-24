"""Step 2: search for the smallest circuit that passes (PRELIMINARY).

Search scoring uses seed 7, first 10 trials, against the whole brain on the
same 10 trials, with the stricter search rule (common.SEARCH_RULE). Every
candidate is a standalone FastBrain built with FastBrain.from_arrays.

Stages
  0  every neuron that received any input (the start set)
  1  only neurons that spiked, plus the taste neurons and MN9
  2  path pruning: keep the neurons on the strongest taste -> MN9 paths
     (widest path; connection strength = presynaptic rate x synapse count),
     a nested family of sizes, which gives the size-vs-match curve
  3  greedy neuron removal in blocks (weakest path score first)
  4  connection pruning: a synapse-count floor, then greedy blocks
  5  single-neuron removal, then single-connection removal, while time allows
After every accepted removal, neurons that no taste neuron can reach or that
cannot reach MN9 are dropped (this cannot change MN9).

Outputs
  results/search_log.csv       every candidate tested
  results/checkpoints.json     every accepted circuit (for stepping back)
  results/raw/search.log       progress log
"""

import csv
import json
import sys
import time

import numpy as np
import pandas as pd

from circuit import TouchedGraph
from common import (CONDITIONS, RAW, RES, RULE, SEARCH_RULE, SEARCH_SEED, SEARCH_TRIALS,
                    VALID_TRIALS, check_rule, means, run_conditions, wait_for_ram)

T0 = time.perf_counter()
BUDGET_S = float(sys.argv[1]) * 60 if len(sys.argv) > 1 else 50 * 60
FAMILY = [3000, 2000, 1500, 1000, 800, 600, 500, 400, 300, 250, 200, 160, 130, 100, 80,
          60, 50, 40, 30, 25, 20, 15]


def log(msg):
    print(f"[{time.perf_counter() - T0:7.1f}s] {msg}", flush=True)


def left():
    return BUDGET_S - (time.perf_counter() - T0)


class Search:
    def __init__(self):
        self.g = g = TouchedGraph()
        ref = np.load(RAW / "reference_mn9.npz")
        self.whole = {c: float(np.mean(ref[f"seed{SEARCH_SEED}|{c}"][:SEARCH_TRIALS]))
                      for c in CONDITIONS}
        log("whole brain, search seed: " + ", ".join(f"{c}={v:.1f}" for c, v in self.whole.items()))
        cz = np.load(RAW / "reference_counts.npz")
        gi = pd.Index(cz["root_ids"]).get_indexer(g.root_ids)
        assert (gi >= 0).all()
        rate = np.max([cz[f"seed{SEARCH_SEED}|{c}"][gi] for c in CONDITIONS], axis=0) / VALID_TRIALS
        self.rate = rate
        self.strength = rate[g.pre] * np.abs(g.signed)
        self.rows = []
        self.checkpoints = []
        self.n_eval = 0

    def evaluate(self, keep_n, keep_e, stage, note=""):
        wait_for_ram(log=log)
        brain = self.g.build(keep_n, keep_e)
        m = means(run_conditions(brain, self.g.ids, SEARCH_SEED, SEARCH_TRIALS))
        del brain
        ok, d = check_rule(m, self.whole, **SEARCH_RULE)
        ok_rule, _ = check_rule(m, self.whole, **RULE)
        self.n_eval += 1
        row = {"eval": self.n_eval, "t_s": round(time.perf_counter() - T0, 1), "stage": stage,
               "note": note, **self.g.stats(keep_n, keep_e), "pass_search": ok,
               "pass_rule_seed7": ok_rule,
               **{f"mn9_{c}": round(v, 2) for c, v in m.items()},
               "err_S100": round(d["err_S100"], 4), "err_S200": round(d["err_S200"], 4),
               "brake_ratio": round(d["brake_ratio"], 3), "water_ok": d["water_ok"],
               "bitter_ok": d["bitter_ok"]}
        self.rows.append(row)
        return ok, row

    def accept(self, keep_n, keep_e, stage, row):
        g = self.g
        ke = g.edges(keep_n, keep_e)
        self.checkpoints.append({
            "stage": stage, **g.stats(keep_n, keep_e), "row": row,
            "nodes": np.flatnonzero(keep_n).tolist(),
            "edges": np.flatnonzero(ke).tolist() if ke.sum() < 200000 else None})

    def save(self):
        with open(RES / "search_log.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(self.rows[0].keys()))
            w.writeheader()
            w.writerows(self.rows)
        (RES / "checkpoints.json").write_text(json.dumps(
            {"label": "PRELIMINARY", "whole_brain_seed7_10trials": self.whole,
             "checkpoints": self.checkpoints}))

    # -- greedy block removal ---------------------------------------------
    def greedy(self, keep_n, keep_e, items, kind, stage, min_block=1, start_block=None,
               time_floor=0.0):
        """Remove neurons (kind='n') or connections (kind='e') in blocks.
        ``items`` is the removal order (weakest first)."""
        g = self.g
        bs = start_block or max(1, len(items) // 4)
        while True:
            if kind == "n":
                live = [i for i in items if keep_n[i] and i != g.mn9]
            else:
                ke = g.edges(keep_n, keep_e)
                live = [i for i in items if ke[i]]
            if not live:
                break
            bs = min(bs, len(live))
            acc = 0
            for s in range(0, len(live), bs):
                if left() < time_floor:
                    log(f"  {stage}: time budget reached at block size {bs}")
                    return keep_n, keep_e, False
                blk = np.array(live[s:s + bs])
                tn, te = keep_n.copy(), keep_e.copy()
                if kind == "n":
                    if not keep_n[blk].any():
                        continue
                    tn[blk] = False
                else:
                    if not te[blk].any():
                        continue
                    te[blk] = False
                tn = g.cleanup(tn, te)
                ok, row = self.evaluate(tn, te, stage, f"block {bs}")
                if ok:
                    keep_n, keep_e = tn, te
                    acc += 1
                    self.accept(keep_n, keep_e, stage, row)
                    log(f"  {stage} bs={bs}: removed -> {row['n_neurons']} neurons, "
                        f"{row['n_connections']} conns (err {row['err_S100']:+.3f}/"
                        f"{row['err_S200']:+.3f}, brake {row['brake_ratio']:.2f})")
            self.save()
            log(f"  {stage}: block size {bs} done, {acc} accepted; now "
                f"{int(keep_n.sum())} neurons, {int(g.edges(keep_n, keep_e).sum())} conns")
            if bs <= min_block:
                break
            bs = max(min_block, bs // 2)
        return keep_n, keep_e, True


def main():
    S = Search()
    g = S.g
    all_e = np.ones(g.m, bool)
    log(f"start set: {g.n} neurons, {g.m} connections; budget {BUDGET_S / 60:.0f} min")

    # stage 0: every touched neuron
    keep = np.ones(g.n, bool)
    ok, row = S.evaluate(keep, all_e, "0-touched")
    S.accept(keep, all_e, "0-touched", row)
    log(f"stage 0: {row['n_neurons']} neurons pass={ok} err {row['err_S100']:+.4f}/{row['err_S200']:+.4f}")

    # stage 1: spiking neurons only (+ taste neurons + MN9)
    keep = g.spiked.copy()
    keep[g.sources] = True
    keep[g.mn9] = True
    keep = g.cleanup(keep, all_e)
    ok, row = S.evaluate(keep, all_e, "1-spiking")
    S.accept(keep, all_e, "1-spiking", row)
    log(f"stage 1: {row['n_neurons']} neurons, {row['n_connections']} conns pass={ok} "
        f"err {row['err_S100']:+.4f}/{row['err_S200']:+.4f} brake {row['brake_ratio']:.2f}")
    base = keep.copy()
    S.save()

    # stage 2: path family
    fw = g.widest(S.strength, base, g.sources, True)
    bw = g.widest(S.strength, base, [g.mn9], False)
    score = np.minimum(fw, bw)
    score[~base] = 0
    np.save(RAW / "path_score.npy", score)
    order = np.argsort(-score, kind="stable")
    n_pos = int((score > 0).sum())
    passing = []
    for k in [n for n in FAMILY if n < n_pos]:
        thr = score[order[k - 1]]
        kn = (score >= thr) & base
        kn[g.mn9] = True
        kn = g.cleanup(kn, all_e)
        ok, row = S.evaluate(kn, all_e, "2-path", f"top {k} (score >= {thr:.0f})")
        log(f"stage 2 top {k}: {row['n_neurons']} neurons, {row['n_connections']} conns pass={ok} "
            f"err {row['err_S100']:+.3f}/{row['err_S200']:+.3f} brake {row['brake_ratio']:.2f} "
            f"water {row['water_ok']} bitter {row['bitter_ok']}")
        if ok:
            passing.append((row["n_neurons"], kn, row))
    S.save()
    if passing:
        n0, keep, row = min(passing, key=lambda t: t[0])
        S.accept(keep, all_e, "2-path", row)
    else:
        keep = base
    log(f"stage 2 start for greedy: {int(keep.sum())} neurons")

    # stage 3: greedy neuron blocks (weakest path score first), down to block 2
    items = [int(i) for i in np.argsort(score, kind="stable") if keep[i]]
    keep, ke, _ = S.greedy(keep, all_e.copy(), items, "n", "3-neuron-blocks", min_block=2,
                           time_floor=0.45 * BUDGET_S)

    # stage 4: connection floor, then greedy connection blocks
    best_c = 1
    for c in (2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30):
        te = ke & (np.abs(g.signed) >= c)
        tn = g.cleanup(keep, te)
        ok, row = S.evaluate(tn, te, "4-conn-floor", f"synapses >= {c}")
        log(f"stage 4 floor {c}: {row['n_neurons']} neurons, {row['n_connections']} conns "
            f"pass={ok} err {row['err_S100']:+.3f}/{row['err_S200']:+.3f} brake {row['brake_ratio']:.2f}")
        if ok:
            best_c, best = c, (tn, te, row)
        else:
            break
    if best_c > 1:
        keep, ke, row = best
        S.accept(keep, ke, "4-conn-floor", row)
    S.save()
    live_e = np.flatnonzero(g.edges(keep, ke))
    e_items = [int(i) for i in live_e[np.argsort(S.strength[live_e], kind="stable")]]
    keep, ke, _ = S.greedy(keep, ke, e_items, "e", "4-conn-blocks", min_block=2,
                           time_floor=0.25 * BUDGET_S)

    # stage 5: single neurons, then single connections, while time allows
    items = [int(i) for i in np.argsort(score, kind="stable") if keep[i]]
    keep, ke, done_n = S.greedy(keep, ke, items, "n", "5-single-neuron", min_block=1,
                                start_block=1, time_floor=0.0)
    done_e = False
    if done_n and left() > 0:
        live_e = np.flatnonzero(g.edges(keep, ke))
        e_items = [int(i) for i in live_e[np.argsort(S.strength[live_e], kind="stable")]]
        keep, ke, done_e = S.greedy(keep, ke, e_items, "e", "5-single-conn", min_block=1,
                                    start_block=1, time_floor=0.0)
    S.save()
    st = g.stats(keep, ke)
    (RES / "search_summary.json").write_text(json.dumps({
        "label": "PRELIMINARY", "final": st, "single_neuron_pass_complete": done_n,
        "single_connection_pass_complete": done_e, "n_evaluations": S.n_eval,
        "wall_s": time.perf_counter() - T0, "budget_s": BUDGET_S,
        "search_rule": SEARCH_RULE, "fixed_rule": RULE}, indent=1))
    log(f"final: {st}; {S.n_eval} evaluations")


if __name__ == "__main__":
    main()
