"""Step 1b: map WHEN runaway happens (rates grid + other taste pairings).

Plain English
-------------
We stimulate the 21 sugar neurons and the 18 Ir94e neurons at every
combination of 0, 100, 200 and 300 spikes per second (20 one-second trials
each), and count how often the brain runs away. As a check on whether Ir94e
is special, we also pair sugar 200 Hz with the bitter or the water taste
neurons at 200 Hz (the same kind of "two strong tastes at once" input).

Output: results/grid.csv, results/grid_series.npz
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
SEED, N = 10, 20
conds = []
for s in (0, 100, 200, 300):
    for r in (0, 100, 200, 300):
        if s == 0 and r == 0:
            continue
        ex = {**{i: float(s) for i in ids["SUGAR"] if s}, **{i: float(r) for i in ids["IR94E"] if r}}
        conds.append(dict(name=f"sugar{s}_ir94e{r}", sugar_hz=s, ir94e_hz=r, other="",
                          excite=ex, seed=SEED, n_trials=N))
for other in ("BITTER", "WATER"):
    ex = {**{i: 200.0 for i in ids["SUGAR"]}, **{i: 200.0 for i in ids[other]}}
    conds.append(dict(name=f"sugar200_{other.lower()}200", sugar_hz=200, ir94e_hz=0,
                      other=f"{other.lower()} 200", excite=ex, seed=SEED, n_trials=N))
common.run_batch(brain, conds, "grid", ids)
print("finished", flush=True)
