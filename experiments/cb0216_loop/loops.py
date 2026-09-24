"""Step 2b (PRELIMINARY): are there OTHER loops that can hold activity on their own?

1. Search the default model's wiring (fix "al_ln_literature") for
   * autapses (a neuron exciting itself),
   * reciprocal excitatory pairs (a->b and b->a both excitatory),
   * excitatory 3-cycles (a->b->c->a),
   ranked by their weakest link (synapses). For scale: in this model one spike
   through n synapses raises the target by at most about 0.043 mV x n
   (w_syn 0.275 mV x 0.157, the peak of the 5 ms / 20 ms double exponential),
   so about 162 synapses let a single spike fire the target on its own
   (threshold is 7 mV above rest); at high rates much weaker links can add up.
2. Test candidates: drive the loop's members at 200 Hz for 200 ms (normal
   refractory period kept), then no input for 3 s. Pass rule R3 (docs/cb0216-loop.md):
   the loop self-sustains if every member fires >= 20 Hz in the last 1 s
   (seed 0; hits repeated on seeds 1 and 2).
Writes results/loop_candidates.csv and results/loop_tests.csv.
"""
import sys

import numpy as np
import pandas as pd

import lib_cb as C

MIN_W = 30            # weakest link considered (synapses)
MAX_PAIRS = 60
MAX_TRI = 30
ON_MS, OFF_MS, RATE = 200.0, 3000.0, 200.0

root_ids, pre, post, signed, lab = C.arrays()
n = len(root_ids)
key = pre.astype(np.int64) * n + post.astype(np.int64)
uk, inv = np.unique(key, return_inverse=True)
w = np.bincount(inv, weights=signed).astype(np.int64)      # one weight per (pre, post)
a_, b_ = uk // n, uk % n
ctype = lab.cell_type.to_numpy()
nt = lab.top_nt.to_numpy()


def name(i):
    return f"{ctype[i] or '?'}[{lab.side[i][:1]}]"


rows = []
# autapses
auto = (a_ == b_) & (w > 0)
for i, ww in zip(a_[auto], w[auto]):
    rows.append(dict(kind="autapse", members=str(int(i)), names=name(i), w_min=int(ww),
                     weights=str(int(ww))))
# reciprocal excitatory pairs
exc = (w >= MIN_W) & (a_ != b_)
ek = uk[exc]
rev = b_[exc] * n + a_[exc]
pos = np.searchsorted(uk, rev)
pos[pos >= uk.size] = 0
has = (uk[pos] == rev) & (w[pos] >= MIN_W)
sel = np.flatnonzero(has)
for j in sel:
    i1, i2 = int(a_[exc][j]), int(b_[exc][j])
    if i1 < i2:
        w12, w21 = int(w[exc][j]), int(w[pos[j]])
        rows.append(dict(kind="pair", members=f"{i1} {i2}", names=f"{name(i1)} <-> {name(i2)}",
                         w_min=min(w12, w21), weights=f"{w12} {w21}"))
# excitatory 3-cycles (weakest link >= MIN_W), excluding ones that contain a pair
strong = pd.DataFrame({"a": a_[exc], "b": b_[exc], "w": w[exc]})
out_nb = strong.groupby("a").apply(lambda d: dict(zip(d.b, d.w))).to_dict()
pairset = {tuple(sorted(map(int, r["members"].split()))) for r in rows if r["kind"] == "pair"}
seen = set()
for x, nb in out_nb.items():
    for y, wxy in nb.items():
        for z, wyz in out_nb.get(y, {}).items():
            if z == x or z == y:
                continue
            wzx = out_nb.get(z, {}).get(x)
            if wzx is None:
                continue
            cyc = tuple(sorted((int(x), int(y), int(z))))
            if cyc in seen:
                continue
            seen.add(cyc)
            if any(tuple(sorted(p)) in pairset for p in ((x, y), (y, z), (z, x))):
                continue
            rows.append(dict(kind="triangle", members=f"{x} {y} {z}",
                             names=f"{name(x)} -> {name(y)} -> {name(z)}",
                             w_min=int(min(wxy, wyz, wzx)), weights=f"{wxy} {wyz} {wzx}"))
cand = pd.DataFrame(rows).sort_values(["kind", "w_min"], ascending=[True, False])
cand["root_ids"] = [" ".join(str(int(root_ids[int(i)])) for i in m.split()) for m in cand.members]
cand["top_nt"] = [" ".join(nt[int(i)] for i in m.split()) for m in cand.members]
cand.to_csv(C.RESULTS / "loop_candidates.csv", index=False)
print(cand.groupby("kind").size().to_string())
print(cand.groupby("kind").head(8)[["kind", "names", "weights", "top_nt"]].to_string(index=False))
if len(sys.argv) > 1 and sys.argv[1] == "search":
    sys.exit(0)

# ---- tests -----------------------------------------------------------------
PI = [int(np.flatnonzero(root_ids == p)[0]) for p in C.PAIR]
test = pd.concat([cand[cand.kind == "autapse"], cand[cand.kind == "pair"].head(MAX_PAIRS),
                  cand[cand.kind == "triangle"].head(MAX_TRI)])
brain = C.brain_from(root_ids, pre, post, signed)
res_rows = []


def one(mem, seed):
    st, nr, wall = C.run_onoff(brain, mem, RATE, ON_MS, OFF_MS, seed, keep_refractory=True)
    end = ON_MS + OFF_MS
    r = C.pair_rates(st, nr, mem, end - 1000, end)
    cb = C.pair_rates(st, nr, PI, end - 1000, end)
    cnt = C.window_counts(st, nr, n, end - 1000, end)
    return r, cb, int((cnt > 0).sum()), wall


for _, c in test.iterrows():
    mem = [int(i) for i in c.members.split()]
    if set(mem) == set(PI):
        label = "CB0216 pair (positive control)"
    else:
        label = ""
    C.wait_for_ram(1.5)
    r, cb, nact, wall = one(mem, 0)
    sustain = min(r) >= 20.0
    row = dict(kind=c.kind, names=c.names, weights=c.weights, root_ids=c.root_ids,
               top_nt=c.top_nt, note=label, seed0_member_hz=" ".join(f"{x:.0f}" for x in r),
               seed0_cb0216_hz=" ".join(f"{x:.0f}" for x in cb), seed0_n_active_last1s=nact,
               sustains_seed0=sustain)
    if sustain:
        ok = []
        for s in (1, 2):
            r2, _, _, _ = one(mem, s)
            ok.append(min(r2) >= 20.0)
        row["sustains_seeds12"] = all(ok)
    res_rows.append(row)
    print(f"{c.kind:8s} {c.names:45s} w {c.weights:12s} -> {row['seed0_member_hz']:14s} "
          f"CB0216 {row['seed0_cb0216_hz']:8s} act {nact:4d} {'SUSTAINS' if sustain else ''}",
          flush=True)
pd.DataFrame(res_rows).to_csv(C.RESULTS / "loop_tests.csv", index=False)
print("wrote results/loop_tests.csv")
