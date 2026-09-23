"""Step 1c: how close to a tipping point does the model sit?

Plain English
-------------
``w_syn`` is the strength of one synapse (0.275 mV in the paper; they tuned
it by hand). We make every synapse 10% and 5% weaker or stronger and count
runaway trials again. Seed 0 is used everywhere, so trial k gets exactly the
same taste input as trial k of seed 0 in step 1a: only the synapse strength
differs. The single-input conditions (sugar 200, Ir94e 200, sugar 100) are
included at +10% to see how their runaway rate changes.

Output: results/wsyn.csv, results/wsyn_series.npz
"""
import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
importlib.reload(common)

brain = common.get_brain(globals())
ids = common.paper_ids()
W0 = brain.params["w_syn"]
both = {**{i: 200.0 for i in ids["SUGAR"]}, **{i: 200.0 for i in ids["IR94E"]}}
sug200 = {i: 200.0 for i in ids["SUGAR"]}
sug100 = {i: 100.0 for i in ids["SUGAR"]}
ir200 = {i: 200.0 for i in ids["IR94E"]}
conds = []
for f in (0.9, 0.95, 1.05, 1.1):
    conds.append(dict(name=f"sugar200_ir94e200_w{f}", stim="sugar200_ir94e200", w_factor=f,
                      excite=both, params={"w_syn": W0 * f}, seed=0, n_trials=30))
for f in (1.1,):
    for nm, ex in (("sugar200_alone", sug200), ("ir94e200_alone", ir200), ("sugar100_alone", sug100)):
        conds.append(dict(name=f"{nm}_w{f}", stim=nm, w_factor=f, excite=ex,
                          params={"w_syn": W0 * f}, seed=0, n_trials=30))
common.run_batch(brain, conds, "wsyn", ids)
print("finished", flush=True)
