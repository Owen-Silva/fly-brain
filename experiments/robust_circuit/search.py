"""Step 2: search for the smallest hardware-ready circuit (PRELIMINARY).

Scoring: seed 7, 30 trials (amended 02:08 from the first 10 trials), stricter search rule (rcommon.SEARCH_RULE)
in all four versions (weights -20%, +20%, 8-bit, normal), stopping at the first
failed check. Every candidate is a standalone FastBrain.

Stages
  F  strongest-path family (600 ... 200 neurons, the previous lane's path
     score), scored in full, for the size curve
  0  start: the previous lane's 400-neuron robust circuit
  1  neuron blocks, weakest path score first, block size 100 -> 2
  2  single neurons, repeated rounds while time allows
  3  connection floor (drop every connection below c synapses), then
     connection blocks weakest first, down to single connections, while time allows
After every accepted removal, neurons no taste neuron can reach or that cannot
reach MN9 are dropped (this cannot change MN9).

Usage: search.py [budget minutes]
Outputs
  results/search_log.csv        every candidate tested
  results/raw/checkpoints.json  every accepted circuit (for stepping back)
  results/search_summary.json
"""

import csv
import json
import sys
import time

import numpy as np
import pandas as pd

from rcommon import (CONDITIONS, MC_RAW, MC_RES, RAW, RES, RULE, SEARCH_RULE, SEARCH_SEED,
                     SEARCH_TRIALS, VALID_TRIALS, VARIANTS, Timer, load_refs, partial_check,
                     run_cond, score, variant_brain)
from circuit import TouchedGraph

T = Timer()
BUDGET_S = float(sys.argv[1]) * 60 if len(sys.argv) > 1 else 50 * 60
N_TRIALS = 30          # amendment 02:08 (was SEARCH_TRIALS = 10); see docs/robust-circuit.md
FAMILY = [600, 500, 400, 300, 250, 200]


def left():
    return BUDGET_S - (time.perf_counter() - T.t0)


class Search:
    def __init__(self):
        self.g = g = TouchedGraph()
        self.ref = load_refs()
        for v in ("seed7_w-20|S100", "seed7_w+20|S100"):
            assert v in self.ref, f"missing whole-brain reference {v}"
        cz = np.load(MC_RAW / "reference_counts.npz")
        gi = pd.Index(cz["root_ids"]).get_indexer(g.root_ids)
        assert (gi >= 0).all()
        rate = np.max([cz[f"seed{SEARCH_SEED}|{c}"][gi] for c in CONDITIONS], axis=0) / VALID_TRIALS
        self.strength = rate[g.pre] * np.abs(g.signed)
        self.pscore = np.load(MC_RAW / "path_score.npy")
        self.rows, self.checkpoints, self.n_eval = [], [], 0

    def arrays(self, kn, ke):
        g = self.g
        ek = g.edges(kn, ke)
        new = np.cumsum(kn) - 1
        return g.root_ids[kn], new[g.pre[ek]], new[g.post[ek]], g.signed[ek]

    def evaluate(self, kn, ke, stage, note="", full=False):
        rid, pre, post, cnt = self.arrays(kn, ke)
        ok, res, ff = score(rid, pre, post, cnt, self.g.ids, self.ref, SEARCH_SEED,
                            N_TRIALS, SEARCH_RULE, early_exit=not full, water=full,
                            trial_slice=N_TRIALS, log=T.log)
        self.n_eval += 1
        row = {"eval": self.n_eval, "t_s": round(time.perf_counter() - T.t0, 1), "stage": stage,
               "note": note, **self.g.stats(kn, ke), "pass_search": ok,
               "first_fail": ff or ""}
        worst = 0.0
        for v in VARIANTS:
            r = res.get(v, {})
            for k in ("err_S100", "err_S200", "brake_ratio"):
                row[f"{v}_{k}"] = round(float(r[k]), 4) if k in r else ""
            if "err_S100" in r:
                worst = max(worst, abs(r["err_S100"]), abs(r.get("err_S200", 0.0)))
            c = r.get("circuit", {})
            row[f"{v}_bitter_max"] = (round(max(c["B100"], c.get("B200", 0.0)), 2)
                                      if "B100" in c else "")
        row["worst_sugar_err_tested"] = round(worst, 4)
        if full:
            row["pass_rule_seed7"] = all(
                partial_check(res[v]["circuit"], res[v]["whole"], **RULE)[0] for v in VARIANTS)
            n = res["normal"]
            row["normal_W100"] = round(n["circuit"]["W100"], 2)
            row["normal_W200"] = round(n["circuit"]["W200"], 2)
        else:
            row["pass_rule_seed7"] = ""
            row["normal_W100"] = row["normal_W200"] = ""
        self.rows.append(row)
        return ok, row

    def water(self, kn, ke, row):
        """MN9 at water 100/200 Hz, normal weights (reported only)."""
        rid, pre, post, cnt = self.arrays(kn, ke)
        b = variant_brain(rid, pre, post, cnt, "normal")
        for c in ("W100", "W200"):
            row[f"normal_{c}"] = round(float(np.mean(run_cond(b, self.g.ids, c, SEARCH_SEED,
                                                              N_TRIALS))), 2)

    def accept(self, kn, ke, stage, row):
        if row.get("normal_W200", "") == "":
            self.water(kn, ke, row)
        ek = self.g.edges(kn, ke)
        self.checkpoints.append({"stage": stage, **self.g.stats(kn, ke), "row": row,
                                 "nodes": np.flatnonzero(kn).tolist(),
                                 "edges": np.flatnonzero(ek).tolist()})

    def save(self):
        keys = []
        for r in self.rows:
            keys += [k for k in r if k not in keys]
        with open(RES / "search_log.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(self.rows)
        (RAW / "checkpoints.json").write_text(json.dumps(
            {"label": "PRELIMINARY", "checkpoints": self.checkpoints}))

    def greedy(self, kn, ke, items, kind, stage, min_block=1, start_block=None, floor=0.0):
        g = self.g
        bs = start_block or max(1, len(items) // 4)
        while True:
            if kind == "n":
                live = [i for i in items if kn[i] and i != g.mn9]
            else:
                ek = g.edges(kn, ke)
                live = [i for i in items if ek[i]]
            if not live:
                return kn, ke, True
            bs = min(bs, len(live))
            acc = 0
            for s in range(0, len(live), bs):
                if left() < floor:
                    T.log(f"  {stage}: time floor reached at block size {bs}")
                    self.save()
                    return kn, ke, False
                blk = np.array(live[s:s + bs])
                tn, te = kn.copy(), ke.copy()
                if kind == "n":
                    if not kn[blk].any():
                        continue
                    tn[blk] = False
                else:
                    if not g.edges(kn, ke)[blk].any():
                        continue
                    te[blk] = False
                tn = g.cleanup(tn, te)
                ok, row = self.evaluate(tn, te, stage, f"block {bs}")
                if ok:
                    kn, ke = tn, te
                    acc += 1
                    self.accept(kn, ke, stage, row)
                    T.log(f"  {stage} bs={bs}: -> {row['n_neurons']} neurons, "
                          f"{row['n_connections']} conns (normal {row['normal_err_S100']:+.3f}/"
                          f"{row['normal_err_S200']:+.3f}, -20% {row['w-20_err_S100']:+.3f}, "
                          f"+20% {row['w+20_err_S100']:+.3f}, int8 {row['int8_err_S100']:+.3f})")
            self.save()
            T.log(f"  {stage}: block size {bs} done, {acc} accepted; now {int(kn.sum())} "
                  f"neurons, {int(g.edges(kn, ke).sum())} conns; {left() / 60:.1f} min left")
            if bs <= min_block:
                return kn, ke, acc == 0
            bs = max(min_block, bs // 2)


def main():
    S = Search()
    g = S.g
    all_e = np.ones(g.m, bool)
    T.log(f"budget {BUDGET_S / 60:.0f} min")
    cps = json.loads((MC_RES / "checkpoints.json").read_text())["checkpoints"]
    base = np.zeros(g.n, bool)
    base[cps[1]["nodes"]] = True                      # the 642 spiking neurons
    start = np.zeros(g.n, bool)
    start[cps[2]["nodes"]] = True                     # the 400-neuron robust circuit
    assert cps[2]["n_neurons"] == 400 and cps[2]["stage"] == "2-path"

    # stage F: strongest-path family, scored in full
    sc = S.pscore.copy()
    sc[~base] = 0
    order = np.argsort(-sc, kind="stable")
    fam_pass = {}
    for k in FAMILY:
        thr = sc[order[k - 1]]
        kn = (sc >= thr) & base
        kn[g.mn9] = True
        kn = g.cleanup(kn, all_e)
        ok, row = S.evaluate(kn, all_e, "F-path", f"top {k}", full=True)
        fam_pass[k] = ok
        T.log(f"family top {k}: {row['n_neurons']} neurons pass_search={ok} "
              f"pass_rule={row['pass_rule_seed7']} " + ", ".join(
                  f"{v} {row[f'{v}_err_S100']:+.3f}/{row[f'{v}_err_S200']:+.3f} b{row[f'{v}_brake_ratio']:.2f}"
                  for v in ("w-20", "w+20", "int8", "normal")) + f" W200 {row['normal_W200']}")
        if k == 400:
            assert (kn == start).all(), "family 400 differs from robust_circuit"
            start_row = row
    S.save()

    if not start_row["pass_search"]:
        # Amendment 02:08: start from the 400-neuron circuit anyway; only
        # candidates that pass the search rule are accepted from here on.
        T.log("note: the 400-neuron start circuit misses the stricter search version; "
              "starting from it anyway (amendment 02:08)")
    kn, ke = start.copy(), g.edges(start, all_e)
    S.accept(kn, ke, "0-start", start_row)
    S.save()

    # stage 1: neuron blocks
    items = [int(i) for i in np.argsort(S.pscore, kind="stable") if kn[i]]
    kn, ke, _ = S.greedy(kn, ke, items, "n", "1-neuron-blocks", min_block=2, start_block=100,
                         floor=0.55 * BUDGET_S)
    # stage 2: single neurons, rounds until nothing is removed
    rnd, done_n = 0, False
    while left() > 0.35 * BUDGET_S:
        rnd += 1
        items = [int(i) for i in np.argsort(S.pscore, kind="stable") if kn[i]]
        n0 = int(kn.sum())
        kn, ke, finished = S.greedy(kn, ke, items, "n", f"2-single-neuron-r{rnd}", min_block=1,
                                    start_block=1, floor=0.35 * BUDGET_S)
        if finished and int(kn.sum()) == n0:
            done_n = True
            break
    # stage 3: connection floor, then connection blocks
    best_c = 1
    for c in (2, 3, 4, 5, 6, 8, 10, 12, 15):
        if left() < 0.1 * BUDGET_S:
            break
        te = ke & (np.abs(g.signed) >= c)
        tn = g.cleanup(kn, te)
        ok, row = S.evaluate(tn, te, "3-conn-floor", f"synapses >= {c}")
        T.log(f"floor {c}: {row['n_neurons']} neurons, {row['n_connections']} conns pass={ok}"
              f" first_fail={row['first_fail']}")
        if ok:
            best_c, best = c, (tn, te, row)
        else:
            break
    if best_c > 1:
        kn, ke, row = best
        S.accept(kn, ke, "3-conn-floor", row)
    S.save()
    done_e = False
    if left() > 0:
        live = np.flatnonzero(g.edges(kn, ke))
        e_items = [int(i) for i in live[np.argsort(S.strength[live], kind="stable")]]
        kn, ke, done_e = S.greedy(kn, ke, e_items, "e", "3-conn-blocks", min_block=1,
                                  floor=0.0)
    S.save()
    st = g.stats(kn, ke)
    fails = pd.Series([r["first_fail"] for r in S.rows if not r["pass_search"]]).value_counts()
    (RES / "search_summary.json").write_text(json.dumps({
        "label": "PRELIMINARY", "final": st, "single_neuron_rounds": rnd,
        "single_neuron_local_minimum": done_n, "connection_pass_complete": done_e,
        "n_evaluations": S.n_eval, "n_accepted": len(S.checkpoints),
        "first_failing_test_counts": {k: int(v) for k, v in fails.items()},
        "family_pass_search": fam_pass, "wall_s": time.perf_counter() - T.t0,
        "budget_s": BUDGET_S, "search_rule": SEARCH_RULE, "fixed_rule": RULE}, indent=1))
    T.log(f"final: {st}; {S.n_eval} evaluations")


if __name__ == "__main__":
    main()
