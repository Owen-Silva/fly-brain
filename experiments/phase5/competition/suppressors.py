"""Which neurons carry the bitter suppression of MN9?

Plain English
-------------
When sugar and bitter neurons are driven together, the feeding motor neuron
MN9 goes quiet. In this model only inhibitory neurons (predicted to release
GABA or glutamate) can push a neuron's voltage down, so the suppression has
to travel through inhibitory neurons that bitter switches on.

Step 1 (candidates, from saved firing rates, seed 0):
  inhibitory neurons that fire at least 2 Hz with sugar 100 Hz + bitter
  80 Hz, and at least 2 Hz more than with sugar alone. Each gets a score =
  its firing rate x the number of its (inhibitory) synapses onto neurons that
  are active in the sugar-alone run (the "sugar pathway"), i.e. roughly how
  much inhibition it pours onto the sugar pathway per second.
Step 2 (causal test, needs simulation):
  silence each of the top 15 candidates one at a time with sugar + bitter
  and see how much MN9 comes back ("recovery": 0% = still suppressed,
  100% = back to the sugar-alone rate). Then silence the top 1/3/5/10 and all
  candidates together, with 3 seeds, at bitter 80 and 200 Hz, and as a
  control with sugar alone (silencing a true bitter-specific brake should
  change little when there is no bitter input).

Output: results/suppressor_candidates.csv, results/suppressor_silencing.csv
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from phase5_common import get_brain, labels, out_signs, outgoing, paper_ids, per_trial_rates  # noqa: E402

OUT = HERE / "results"
ids = paper_ids()
brain = get_brain(globals())
lab = labels()
assert np.array_equal(lab.root_id.to_numpy(), brain.root_ids)
MN9_IDX = brain.index_of([ids["MN9"]])
sign = out_signs(brain)

r_s = np.load(OUT / "rates_bitter_s100_o0.npy")
r_sb = np.load(OUT / "rates_bitter_s100_o80.npy")
r_b = np.load(OUT / "rates_bitter_s0_o200.npy")
pathway = r_s >= 1.0
mn9 = int(MN9_IDX[0])

cand = np.flatnonzero((sign < 0) & (r_sb >= 2.0) & (r_sb - r_s >= 2.0))
rows = []
for i in cand:
    post, cnt = outgoing(brain, i)
    onto_path = np.abs(cnt[pathway[post]]).sum()
    onto_mn9 = np.abs(cnt[post == mn9]).sum()
    rows.append(dict(root_id=int(brain.root_ids[i]), row=int(i),
                     rate_sugar=float(r_s[i]), rate_sugar_bitter80=float(r_sb[i]),
                     rate_bitter200_alone=float(r_b[i]),
                     syn_onto_sugar_pathway=int(onto_path), syn_onto_mn9=int(onto_mn9),
                     score=float(r_sb[i] * onto_path)))
cdf = pd.DataFrame(rows)
cdf = cdf.merge(lab[["root_id", "super_class", "cell_class", "cell_type", "hemibrain_type",
                     "side", "top_nt"]], on="root_id", how="left")
cdf = cdf.sort_values("score", ascending=False).reset_index(drop=True)
cdf.to_csv(OUT / "suppressor_candidates.csv", index=False)
print(f"{len(cdf)} inhibitory candidates; top 10:")
print(cdf.head(10)[["root_id", "cell_type", "hemibrain_type", "top_nt", "rate_sugar",
                    "rate_sugar_bitter80", "syn_onto_sugar_pathway", "syn_onto_mn9"]].to_string())


def mn9_rate(sugar, bitter, silence, seed):
    exc = {int(i): float(sugar) for i in ids["SUGAR"]}
    if bitter > 0:
        exc.update({int(i): float(bitter) for i in ids["BITTER"]})
    res = brain.run(excite=exc, silence=silence, duration_ms=1000.0, n_trials=30, seed=seed)
    pt = per_trial_rates(res, MN9_IDX)[:, 0]
    return pt.mean(), pt.std()


SIL_CSV = OUT / "suppressor_silencing.csv"
done = set()
if SIL_CSV.exists():
    d = pd.read_csv(SIL_CSV)
    done = set(zip(d.label, d.sugar_hz, d.bitter_hz, d.seed))


def record(label, silence, sugar, bitter, seed):
    if (label, sugar, bitter, seed) in done:
        return
    m, s = mn9_rate(sugar, bitter, silence, seed)
    row = dict(label=label, n_silenced=len(silence), sugar_hz=sugar, bitter_hz=bitter,
               seed=seed, mn9_mean=m, mn9_sd=s,
               silenced=" ".join(str(x) for x in silence))
    pd.DataFrame([row]).to_csv(SIL_CSV, mode="a", header=not SIL_CSV.exists(), index=False)
    print(f"{label} | sugar {sugar} bitter {bitter} seed {seed}: MN9 {m:.1f} +/- {s:.1f}", flush=True)


top = cdf.root_id.tolist()
# baselines (same seeds, no silencing)
for seed in (0, 1, 2):
    for b in (0, 80, 200):
        record("none", [], 100, b, seed)
# single-neuron silencing, top 15, seed 0, bitter 80
for k, rid in enumerate(top[:15]):
    record(f"single_{k + 1}_{rid}", [rid], 100, 80, 0)
# groups, 3 seeds, bitter 80 and 200, and sugar-alone control
for n in (1, 3, 5, 10, len(top)):
    label = f"top{n}" if n < len(top) else f"all{n}"
    for seed in (0, 1, 2):
        for b in (0, 80, 200):
            record(label, top[:n], 100, b, seed)
