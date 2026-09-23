"""PLAN.md Phase 5 "Sensitivity": do the paper's three MN9 results survive
+/-20% changes to every model constant?

The three results (Shiu et al. 2024, snapshot 630, MN9 = 720575940660219265):
  1. sugar GRNs (21) at 100 Hz        -> MN9 fires  (paper: 65.7 Hz)
  2. water GRNs (18) at 200 Hz        -> MN9 fires  (paper: 30.7 Hz)
  3. sugar 100 Hz + bitter GRNs (21) at 120 Hz -> MN9 much lower than sugar
     alone (paper: 1.5 Hz vs 67.0 Hz)

For every variation (see sim/validation.py: baseline, the same model with new
random seeds, each constant at -20/-10/+10/+20% one at a time, and every
connection's weight jittered by up to +/-20% in several random patterns) each
of the three conditions is run for 30 trials x 1 s with each of 3 seeds.
"Poisson input rate" scales all three stimulus rates together.

Each (variation, seed) is saved to cache/ as soon as it finishes, so the run
can be stopped and restarted without losing work.

Usage:
  .venv\\Scripts\\python.exe experiments\\phase5\\sensitivity\\run_sensitivity.py
      [--threads 2] [--trials 30] [--quick]
"""

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from sim import validation as V  # noqa: E402

CACHE = HERE / "cache"

MN9 = 720575940660219265
SUGAR = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
WATER = [
    720575940612950568, 720575940631898285, 720575940606002609, 720575940612579053,
    720575940622902535, 720575940616177458, 720575940660292225, 720575940622486922,
    720575940613786774, 720575940629852866, 720575940625861168, 720575940613996959,
    720575940617857694, 720575940644965399, 720575940625203504, 720575940630553415,
    720575940635172191, 720575940634796536,
]
BITTER = [
    720575940621778381, 720575940602353632, 720575940617094208, 720575940619197093,
    720575940626287336, 720575940618600651, 720575940627692048, 720575940630195909,
    720575940646212996, 720575940610483162, 720575940645743412, 720575940627578156,
    720575940622298631, 720575940621008895, 720575940629146711, 720575940610259370,
    720575940610481370, 720575940619028208, 720575940614281266, 720575940613061118,
    720575940604027168,
]
SUGAR_HZ, WATER_HZ, BITTER_HZ = 100.0, 200.0, 120.0
SEEDS = (0, 1, 2)
ON_HZ = 5.0            # "MN9 is on" cut-off (Hz, mean of 30 trials)
MAX_RATIO = 0.5        # "bitter suppresses": sugar+bitter MN9 <= 50% of sugar alone
#: Random weight-jitter patterns. The first pass ran 5; one of them (draw 1) pushed
#: water-driven MN9 down to the 5 Hz cut-off, so 10 more were added (same cache,
#: run after the first pass) to see how often that happens.
JITTER_DRAWS = 15

#: Stimulated neurons per condition (excluded from the top-50 ranking).
STIMULATED = {"sugar": SUGAR, "water": WATER, "sugar_bitter": SUGAR + BITTER}

CLAIMS = {
    "sugar_on": V.at_least("sugar_mn9", ON_HZ,
                           f"sugar GRNs at 100 Hz drive MN9 to >= {ON_HZ:g} Hz"),
    "water_on": V.at_least("water_mn9", ON_HZ,
                           f"water GRNs at 200 Hz drive MN9 to >= {ON_HZ:g} Hz"),
    "bitter_suppresses": V.suppressed(
        "sugar_bitter_mn9", "sugar_mn9", MAX_RATIO, ON_HZ,
        f"adding bitter GRNs at 120 Hz cuts sugar-driven MN9 to <= {MAX_RATIO:.0%} of "
        f"sugar alone (same seed), and sugar alone is >= {ON_HZ:g} Hz"),
}


def make_experiment(n_trials=30, duration_ms=1000.0):
    """The experiment handed to sim/validation.py: three conditions, one seed."""
    def experiment(brain, params, seed):
        f = V.rate_factor(params)
        sugar = dict.fromkeys(SUGAR, SUGAR_HZ * f)
        conditions = {
            "sugar": sugar,
            "water": dict.fromkeys(WATER, WATER_HZ * f),
            # sugar first: with the same seed the sugar input spikes are then
            # identical to the sugar-alone run (a paired comparison)
            "sugar_bitter": {**sugar, **dict.fromkeys(BITTER, BITTER_HZ * f)},
        }
        out = {}
        for name, excite in conditions.items():
            res = brain.run(excite=excite, duration_ms=duration_ms, n_trials=n_trials,
                            seed=seed, params=params)
            rates = res.rates()                      # neurons that fired, Hz
            out[f"{name}_mn9"] = res.rate(MN9)
            out[f"{name}_active"] = float(len(rates))
            out[f"{name}_rates"] = rates.astype("float32")
            del res
        s = out["sugar_mn9"]
        out["bitter_ratio"] = out["sugar_bitter_mn9"] / s if s > 0 else float("nan")
        return out
    return experiment


def ordered_variations(jitter_draws=JITTER_DRAWS):
    """Most informative first, so a stopped run still has the key points:
    baseline, new seeds, every +/-20% end point, jitter, then the +/-10% points."""
    allv = V.standard_variations(jitter_draws=jitter_draws)
    first = [v for v in allv if v.parameter in ("baseline", "seed_noise")]
    ends = [v for v in allv if v.parameter in V.PARAMETER_RULES and abs(v.change) > 0.15]
    jit = [v for v in allv if v.parameter in ("jitter_control", "weight_jitter")]
    mids = [v for v in allv if v.parameter in V.PARAMETER_RULES and abs(v.change) <= 0.15]
    return first + ends + jit + mids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--quick", action="store_true",
                    help="timing check only: 2 trials, 1 seed, 3 variations, no cache")
    args = ap.parse_args()

    from sim.fast_engine import FastBrain
    t0 = time.perf_counter()
    brain = FastBrain(snapshot="630", n_threads=args.threads)
    brain.run(excite=SUGAR[:1], duration_ms=10, n_trials=1, seed=0)   # compile / warm up
    print(f"loaded v630 ({brain.n_neurons} neurons, {brain.n_connections} connections) "
          f"in {time.perf_counter() - t0:.1f} s", flush=True)

    def log(line):
        print(time.strftime("%H:%M:%S ") + line, flush=True)

    if args.quick:
        vs = ordered_variations()
        pick = [vs[0], next(v for v in vs if v.name == "w_syn+20%"),
                next(v for v in vs if v.parameter == "weight_jitter")]
        res = V.run_validation(make_experiment(2), pick, seeds=(0,), claims=CLAIMS,
                               brain=brain, log=log)
        print(res.verdicts[["claim", "variation", "verdict"]].to_string(), flush=True)
        return

    variations = ordered_variations()
    res = V.run_validation(make_experiment(args.trials), variations, seeds=SEEDS,
                           claims=CLAIMS, brain=brain, cache_dir=CACHE, log=log)
    print("DONE", len(res.table), "rows", flush=True)


if __name__ == "__main__":
    main()
