"""Phase 5 "Unexplored areas": smell (olfaction), which the reference paper
did not study, and the left/right question that Phase 9 depends on.

Plain English
-------------
Flies smell with olfactory receptor neurons (ORNs) on their antennae. All
ORNs that carry the same receptor send their wires to the same small ball of
wiring in the brain (a "glomerulus"). We use two:

* DM1: responds to fruity esters / vinegar (attractive to flies).
* DA2: responds to geosmin, the smell of harmful mould (aversive).

In snapshot 630 these ORNs are labelled in the ``hemibrain_type`` column
(``ORN_DM1``: 68 neurons, 35 left + 33 right; ``ORN_DA2``: 39 neurons,
16 left + 22 right + 1 unlabelled). For each odor channel we stimulate
all of its ORNs, then only the left ones, then only the right ones, at
150 Hz (the model's default input rate), 30 one-second trials, 3 seeds.

We save (a) every neuron's average firing rate per run and (b) the rate of
every descending neuron (the brain's output wires to the body) in every
single trial, so the left/right analysis can use trial-to-trial spread.

Stages (command-line words):
  ``ignite``       every odor x side at 10-150 Hz, 5 trials, seed 0: a quick
                   scan for the input rate where activity spreads brain-wide.
  ``lr:<rate>``    both / left / right at <rate> Hz, 30 trials, seeds 0-2.
  ``lrside:<rate>`` left / right at <rate> Hz, 30 trials, seeds 0-2, plus
                   both sides for seed 0 only (saves time at slow rates).
  Add ``:lnfix`` (e.g. ``lrside:150:lnfix``) to run the EXPLORATORY
  "sign-corrected" variant: the 53 antennal-lobe local neurons whose
  transmitter was predicted (with low confidence) as serotonin or dopamine,
  and which the reference model therefore treats as excitatory, are made
  inhibitory for that run only (they are lLN1 / lLN2T-type LNs, which the
  literature describes as GABAergic). The brain's own numbers are restored
  afterwards and checked. File names get "_lnfix".
  ``:short`` = the published model with 300 ms trials instead of 1 s (for
  the slow runaway runs). File names get "_short".
  ``lnfixcheck``   sanity checks of that variant (sugar -> MN9 unchanged?
                   does a DM1 volley still ignite?).
Runs with fewer than 30 trials get "_t<trials>" in their file names.
Output: results/olf_<odor>_<side>_<rate>Hz_seed<k>_rates.npy (all neurons,
mean over trials), ..._dn_trials.npy (trials x descending neurons),
..._dn_early.npy / _pn_early.npy (trials x 10 ms bins over the first 100 ms x
descending neurons / projection neurons; column order in dn_ids.npy / pn_ids.npy),
results/dn_ids.npy (the column order), results/runs.csv (one row per run).
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "competition"))
from phase5_common import get_brain, labels, per_trial_rates  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
RUNS_CSV = OUT / "runs.csv"
N_TRIALS = 30

lab = labels()
brain = get_brain(globals())
assert np.array_equal(lab["root_id"].to_numpy(), brain.root_ids), "label rows != brain rows"

ORN = {}
for odor in ("DM1", "DA2"):
    rows = lab[(lab.super_class == "sensory") & (lab.cell_class == "olfactory")
               & (lab.hemibrain_type == f"ORN_{odor}")]
    ORN[(odor, "both")] = rows.root_id.tolist()
    ORN[(odor, "left")] = rows[rows.side == "left"].root_id.tolist()
    ORN[(odor, "right")] = rows[rows.side == "right"].root_id.tolist()
DN_IDX = np.flatnonzero((lab.super_class == "descending").to_numpy())
np.save(OUT / "dn_ids.npy", lab.root_id.to_numpy()[DN_IDX])


LNFIX_ROWS = np.flatnonzero(((lab.cell_class == "ALLN")
                             & lab.top_nt.isin(["serotonin", "dopamine"])).to_numpy())


class LnFix:
    """Temporarily make the outgoing synapses of LNFIX_ROWS inhibitory."""

    def __enter__(self):
        self.segs = [(brain._indptr[i], brain._indptr[i + 1]) for i in LNFIX_ROWS]
        self.saved = [brain._count[a:b].copy() for a, b in self.segs]
        self.check = int(brain._count.astype(np.int64).sum())
        for a, b in self.segs:
            brain._count[a:b] = -np.abs(brain._count[a:b])
        return self

    def __exit__(self, *exc):
        for (a, b), v in zip(self.segs, self.saved):
            brain._count[a:b] = v
        assert int(brain._count.astype(np.int64).sum()) == self.check, "restore failed"
        return False


def done():
    if not RUNS_CSV.exists():
        return set()
    d = pd.read_csv(RUNS_CSV)
    if "variant" not in d:
        d["variant"] = "baseline"
    return set(zip(d.odor, d.side, d.rate_hz, d.seed, d.n_trials, d.variant.fillna("baseline")))


PN_IDX = np.flatnonzero((lab.cell_class == "ALPN").to_numpy())
np.save(OUT / "pn_ids.npy", lab.root_id.to_numpy()[PN_IDX])


def early_counts(res, idx, bin_ms=10, n_bins=10):
    """Spike counts of the neurons ``idx`` in 10 ms bins over the first
    100 ms of each trial: array (trials, 10 bins, neurons)."""
    pos = -np.ones(len(lab), np.int64)
    pos[idx] = np.arange(idx.size)
    out = np.zeros((res.n_trials, n_bins, idx.size), np.float32)
    b = (res.step * res.dt_ms // bin_ms).astype(np.int64)
    m = (pos[res.neuron] >= 0) & (b < n_bins)
    np.add.at(out, (res.trial[m], b[m], pos[res.neuron[m]]), 1.0)
    return out


def run(odor, side, rate, seed, n_trials=N_TRIALS, variant="baseline"):
    ids = ORN[(odor, side)]
    t0 = time.perf_counter()
    # variant "short" = the published model with 300 ms trials (used for the
    # slow runaway runs; the runaway reaches its fixed state within 50 ms)
    dur = 300.0 if variant == "short" else 1000.0
    if variant == "lnfix":
        with LnFix():
            res = brain.run(excite=ids, rate_hz=float(rate), duration_ms=dur,
                            n_trials=n_trials, seed=seed)
    else:
        res = brain.run(excite=ids, rate_hz=float(rate), duration_ms=dur,
                        n_trials=n_trials, seed=seed)
    tag = f"olf_{odor}_{side}_{rate}Hz_seed{seed}" + ("" if n_trials == N_TRIALS else f"_t{n_trials}")
    tag += "" if variant == "baseline" else f"_{variant}"
    np.save(OUT / f"{tag}_rates.npy", res.rates_hz.astype(np.float32))
    np.save(OUT / f"{tag}_dn_trials.npy", per_trial_rates(res, DN_IDX).astype(np.float32))
    np.save(OUT / f"{tag}_dn_early.npy", early_counts(res, DN_IDX))
    np.save(OUT / f"{tag}_pn_early.npy", early_counts(res, PN_IDX))
    row = dict(odor=odor, side=side, rate_hz=rate, seed=seed, n_orns=len(ids),
               n_trials=n_trials, n_active=int((res.rates_hz > 0).sum()),
               n_dn_active=int((res.rates_hz[DN_IDX] > 0).sum()),
               wall_s=round(time.perf_counter() - t0, 1), variant=variant)
    pd.DataFrame([row]).to_csv(RUNS_CSV, mode="a", header=not RUNS_CSV.exists(), index=False)
    return row


def lnfix_check():
    """Sugar -> MN9 and DM1-volley ignition, baseline vs sign-corrected LNs."""
    from phase5_common import paper_ids
    ids = paper_ids()
    dm1 = ORN[("DM1", "both")][:10]
    out = []
    for variant in ("baseline", "lnfix"):
        for seed in (0, 1, 2):
            if variant == "lnfix":
                with LnFix():
                    r = brain.run(excite=ids["SUGAR"], rate_hz=100, n_trials=30, seed=seed)
            else:
                r = brain.run(excite=ids["SUGAR"], rate_hz=100, n_trials=30, seed=seed)
            out.append(dict(variant=variant, test=f"sugar 100 Hz, MN9 rate, seed {seed}",
                            value=r.rate(ids["MN9"])))
        ev = [(np.full(len(dm1), 50), dm1)]
        if variant == "lnfix":
            with LnFix():
                r = brain.run_with_input_events(ev, excite=dm1, duration_ms=1000.0)
        else:
            r = brain.run_with_input_events(ev, excite=dm1, duration_ms=1000.0)
        out.append(dict(variant=variant, test="volley 10 DM1 ORNs: neurons active",
                        value=int((r.rates_hz > 0).sum())))
        out.append(dict(variant=variant, test="volley 10 DM1 ORNs: firing in last 100 ms",
                        value=int(np.unique(r.neuron[r.step >= 9000]).size)))
        pd.DataFrame(out).to_csv(OUT / "lnfix_check.csv", index=False)
        print(out[-5:], flush=True)
    print(f"{LNFIX_ROWS.size} LNs flipped in the lnfix variant", flush=True)


def plan(stage):
    odors = ("DM1", "DA2")
    if stage == "ignite":
        return [(o, s, r, 0, 5, "baseline") for r in (10, 20, 30, 50, 75, 100, 150) for o in odors
                for s in ("both", "left", "right")]
    parts = stage.split(":")
    kind, rate = parts[0], int(parts[1])
    v = parts[2] if len(parts) > 2 else "baseline"
    if kind == "lr":
        return [(o, s, rate, k, N_TRIALS, v) for k in (0, 1, 2) for o in odors
                for s in ("both", "left", "right")]
    if kind == "lrside":
        c = [(o, "both", rate, 0, N_TRIALS, v) for o in odors]
        return c + [(o, s, rate, k, N_TRIALS, v) for k in (0, 1, 2) for o in odors
                    for s in ("left", "right")]
    raise ValueError(stage)


if __name__ == "__main__":
    print({k: len(v) for k, v in ORN.items()}, f"{DN_IDX.size} descending neurons", flush=True)
    for stage in (sys.argv[1:] or ["ignite"]):
        if stage == "lnfixcheck":
            lnfix_check()
            continue
        todo = [c for c in plan(stage) if c not in done()]
        print(f"stage {stage}: {len(todo)} runs", flush=True)
        for n, c in enumerate(todo, 1):
            r = run(*c)
            print(f"[{n}/{len(todo)}] {c}: {r['n_active']} neurons active, "
                  f"{r['n_dn_active']} DNs active ({r['wall_s']} s)", flush=True)
