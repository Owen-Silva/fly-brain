"""Step 3b: prove which loop sustains the runaway (lesion and volley tests).

Plain English
-------------
Step 3a showed the runaway always starts in the antennal lobe (the fly's
first smell centre), in "local neurons" that the FlyWire annotation lists as
cholinergic (excitatory) from antibody staining (Shang et al. 2007): types
lLN1_b/c and lLN2T_a/b/c, 44 neurons. Here we test that causally.

A. Paired lesion test. We re-run trials that we KNOW ran away (same random
   input), each time with one group of neurons silenced (their output set to
   zero), and count how many still run away. Groups: the 44 cholinergic local
   neurons (eLNs); only lLN1_b/c; all local neurons the model treats as
   excitatory; all 424 local neurons; the 20 neurons that fire first; and a
   control group of 44 random excitatory neurons from outside the antennal
   lobe that also fire during the runaway.
B. A biology-based variant: in real flies, excitatory local neurons talk to
   projection neurons mostly through electrical contacts (gap junctions) and
   drive the INHIBITORY local neurons through chemical synapses (Yaksi &
   Wilson 2010; Huang et al. 2010). The model instead turns every eLN
   synapse into a chemical excitatory one. Variant: keep eLN chemical
   synapses only onto inhibitory neurons. (A diagnostic, not a model upgrade.)
C. Population test: 60 fresh Ir94e-200 trials and the olfaction lane's
   trigger (10 DM1 smell neurons firing once) with the key lesions.
D. The Phase 3 baseline must survive: sugar 100 Hz, MN9 rate, 30 trials.
E. Volley test: make the 20 first-firing neurons fire ONCE with no taste
   input at all. Does the whole brain ignite?
F. How does Ir94e reach the antennal lobe? Shortest excitatory path.

Outputs: results/lesions.csv, results/lesion_population.csv, results/paths.txt
"""
import importlib
import sys
from collections import deque
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
importlib.reload(common)

brain = common.get_brain(globals())
R = common.RESULTS
ids = common.paper_ids()
lab = common.labels(brain)
A = pd.read_csv(common.ROOT / "data/flywire/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                usecols=["root_id", "known_nt"], dtype={"root_id": "int64"},
                low_memory=False).set_index("root_id")
lab["known_nt"] = A.known_nt.reindex(lab.root_id).fillna("").to_numpy()
rid = lab.root_id.to_numpy()
cc, ht = lab.cell_class.to_numpy(), lab.hemibrain_type.to_numpy()
pre = np.repeat(np.arange(brain.n_neurons), np.diff(brain._indptr))
sign = np.zeros(brain.n_neurons, int)
has = np.diff(brain._indptr) > 0
sign[has] = np.sign(brain._count[brain._indptr[:-1][has]])

aln = cc == "ALLN"
eln = aln & np.isin(ht, ["lLN1_b,lLN1_c", "lLN2T_a", "lLN2T_b", "lLN2T_c"])
lln1bc = aln & (ht == "lLN1_b,lLN1_c")
aln_exc = aln & (sign > 0)
rank = pd.read_csv(R / "onset_ranking.csv")
first20 = rank.root_id.head(20).to_numpy(np.int64)
rep = pd.read_csv(R / "reproduce_trials.csv")
# control: random excitatory neurons active in the runaway, outside the antennal lobe
core = pd.read_csv(R / "core_neurons.csv")
cand = core[(core.sign > 0) & (~core.cell_class.isin(["ALLN", "ALPN", "olfactory"]))].root_id.to_numpy(np.int64)
ctrl = np.random.default_rng(1).choice(cand, size=int(eln.sum()), replace=False)
print(f"eLNs {eln.sum()} (lLN1_b/c {lln1bc.sum()}), model-excitatory ALLN {aln_exc.sum()}, "
      f"all ALLN {aln.sum()}, control {ctrl.size}", flush=True)
print("eLN known_nt:", pd.Series(lab.known_nt[eln]).value_counts().to_dict(),
      "predicted:", pd.Series(lab.top_nt[eln]).value_counts().to_dict(), flush=True)

groups = {
    "none (baseline)": np.zeros(0, np.int64),
    "44 cholinergic eLNs": rid[eln],
    "30 lLN1_b/c only": rid[lln1bc],
    f"{aln_exc.sum()} model-excitatory AL local neurons": rid[aln_exc],
    f"all {aln.sum()} AL local neurons": rid[aln],
    "20 first-firing neurons": first20,
    f"control: {ctrl.size} random excitatory runaway neurons outside AL": ctrl,
}


@contextmanager
def eln_to_inhibitory_only():
    """eLN chemical synapses kept only onto inhibitory targets (diagnostic)."""
    m = eln[pre] & (sign[brain._post] > 0)
    saved = brain._count[m].copy()
    brain._count[m] = 0
    try:
        yield int(m.sum())
    finally:
        brain._count[m] = saved


both = {**{i: 200.0 for i in ids["SUGAR"]}, **{i: 200.0 for i in ids["IR94E"]}}
ir = {i: 200.0 for i in ids["IR94E"]}
sug100 = {i: 100.0 for i in ids["SUGAR"]}
known = pd.concat([
    rep[(rep.condition == "sugar200_ir94e200") & rep.runaway].assign(excite="both"),
    rep[(rep.condition == "ir94e200_alone") & rep.runaway].head(10).assign(excite="ir"),
])
EX = {"both": both, "ir": ir}
rows = []


def record(test, group, cond, seed, trial, res, **kw):
    row, _, _ = common.trial_summary(res, brain, ids)
    rows.append(dict(test=test, group=group, condition=cond, seed=seed, trial=trial, **kw, **row))
    pd.DataFrame(rows).to_csv(R / "lesions.csv", index=False)


# ---- A + B: paired tests on known runaway trials ----------------------------------------
def paired(label, silence):
    n_run = 0
    for _, t in known.iterrows():
        res = common.run_one(brain, EX[t.excite], int(t.seed), int(t.trial), 1000.0, silence=silence)
        record("A paired", label, t.condition, int(t.seed), int(t.trial), res)
        n_run += rows[-1]["runaway"]
    print(f"[A] silence {label}: {n_run}/{len(known)} known-runaway trials still run away", flush=True)


for label, sil in groups.items():
    paired(label, sil)
with eln_to_inhibitory_only() as n_cut:
    print(f"[B] cut {n_cut} eLN->excitatory-neuron connections", flush=True)
    paired("eLN chemical output only onto inhibitory neurons", ())

# ---- C + D + E: population, olfactory trigger, sugar baseline, volley --------------------
dm1 = rid[ht == "ORN_DM1"][:10]


def volley(ids_, silence=()):
    return brain.run_with_input_events([(np.full(len(ids_), 50), ids_)], excite=ids_,
                                       duration_ms=1000.0, silence=silence)


pop = []


def pop_row(test, variant, res_rows):
    d = pd.DataFrame(res_rows)
    pop.append(dict(test=test, variant=variant, n=len(d), runaway=int(d.runaway.sum()),
                    mn9_mean_hz=round(d.mn9_hz.mean(), 2), mn9_sd_hz=round(d.mn9_hz.std(ddof=0), 2),
                    median_spikes=int(d.total_spikes.median())))
    pd.DataFrame(pop).to_csv(R / "lesion_population.csv", index=False)
    print(f"[{test}] {variant}: {pop[-1]}", flush=True)


def population(variant, silence=(), ctx=None):
    for test, ex, seeds, n in (("C Ir94e 200, 60 trials", ir, (0, 1), 30),
                               ("D sugar 100 (Phase 3 baseline), 30 trials", sug100, (0,), 30)):
        rr = []
        for s in seeds:
            for k in range(n):
                res = common.run_one(brain, ex, s, k, 1000.0, silence=silence)
                rr.append(common.trial_summary(res, brain, ids)[0])
        pop_row(test, variant, rr)
    res = volley(dm1, silence)
    pop_row("C olfactory trigger: 10 DM1 ORNs fire once", variant, [common.trial_summary(res, brain, ids)[0]])


population("intact model")
population("44 eLNs silenced", silence=rid[eln])
with eln_to_inhibitory_only():
    population("eLN output only onto inhibitory neurons")
res = volley(first20)
pop_row("E volley: 20 first-firing neurons fire once, no taste input", "intact model",
        [common.trial_summary(res, brain, ids)[0]])
res = volley(rid[eln])
pop_row("E volley: 44 eLNs fire once, no taste input", "intact model",
        [common.trial_summary(res, brain, ids)[0]])

# ---- F: path from Ir94e (and sugar) to the eLNs -----------------------------------------
lines = []
target = set(np.flatnonzero(eln).tolist())
for name in ("IR94E", "SUGAR"):
    src = brain.index_of(ids[name])
    prev = {int(s): -1 for s in src}
    q = deque(int(s) for s in src)
    hit = None
    while q and hit is None:
        u = q.popleft()
        a, b = brain._indptr[u], brain._indptr[u + 1]
        for v, c in zip(brain._post[a:b], brain._count[a:b]):
            v = int(v)
            if c >= 5 and v not in prev:        # excitatory, at least 5 synapses
                prev[v] = u
                if v in target:
                    hit = v
                    break
                q.append(v)
    if hit is None:
        lines.append(f"{name}: no excitatory (>=5 synapse) path to the eLNs")
        continue
    path = [hit]
    while prev[path[-1]] != -1:
        path.append(prev[path[-1]])
    path = path[::-1]
    desc = []
    for i, u in enumerate(path):
        w = ""
        if i:
            a, b = brain._indptr[path[i - 1]], brain._indptr[path[i - 1] + 1]
            w = f" <-{int(brain._count[a:b][brain._post[a:b] == u][0])} syn- "
        desc.append(f"{w}{rid[u]} [{cc[u] or lab.super_class[u]}/{ht[u] or lab.cell_type[u] or '-'} {lab.top_nt[u]}]")
    lines.append(f"{name}: shortest excitatory path to an eLN has {len(path) - 1} steps: " + "".join(desc))
# direct strong targets of Ir94e GRNs
src = brain.index_of(ids["IR94E"])
tg = {}
for u in src:
    a, b = brain._indptr[u], brain._indptr[u + 1]
    for v, c in zip(brain._post[a:b], brain._count[a:b]):
        tg[int(v)] = tg.get(int(v), 0) + int(c)
top = sorted(tg.items(), key=lambda x: -abs(x[1]))[:15]
lines.append("Ir94e GRNs' 15 strongest targets (summed signed synapses): " + "; ".join(
    f"{rid[v]} {cc[v] or lab.super_class[v]}/{ht[v] or lab.cell_type[v] or '-'} {s:+d}" for v, s in top))
(R / "paths.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines), flush=True)
print("finished", flush=True)
