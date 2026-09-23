"""Whole-brain benchmark and validation of sim/fast_engine.py.

Runs the paper's sugar experiment (21 sugar-sensing GRNs, FlyWire v630) with
30 trials of 1 s each, at 100, 150 and 200 Hz input, plus the three
single-neuron silencing runs from the reference tutorial. Compares every
neuron's firing rate with the reference authors' own Brian2 output shipped in
data/reference/results/example/ and with the paper's MN9 numbers.

Usage:  .venv\\Scripts\\python.exe experiments\\fast_engine\\benchmark.py [--threads 2]
Writes: experiments/fast_engine/results/*.csv and summary.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim.fast_engine import FastBrain, REFERENCE_DIR  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"
SUGAR = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
MN9 = 720575940660219265
MN9_B = 720575940645521262          # second MN9 (exists in v630 only)
PAPER_MN9 = {100: (65.7, 3.3), 200: (93.2, None)}   # Hz, from the paper (30 trials)
REF_EXAMPLE = REFERENCE_DIR / "results" / "example"


def ref_rates(path, n_trials=30, t_run_s=1.0):
    """Per-neuron mean rate and per-trial counts from a reference spike parquet."""
    df = pd.read_parquet(path)
    counts = df.groupby(["flywire_id", "trial"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=range(n_trials), fill_value=0)
    per_trial = counts / t_run_s
    return pd.DataFrame({"mean_hz": per_trial.mean(axis=1), "std_hz": per_trial.std(axis=1, ddof=0)})


def compare(fast_stats, ref_stats, n_trials=30):
    """Neuron-by-neuron comparison of two 30-trial rate tables."""
    both = pd.concat([fast_stats.add_prefix("fast_"), ref_stats.add_prefix("ref_")],
                     axis=1).fillna(0.0)
    diff = both["fast_mean_hz"] - both["ref_mean_hz"]
    # standard error of the difference of two independent 30-trial means
    se = np.sqrt((both["fast_std_hz"] ** 2 + both["ref_std_hz"] ** 2) / n_trials)
    z = diff / se.where(se > 0, np.nan)
    active = both[(both["fast_mean_hz"] > 0) | (both["ref_mean_hz"] > 0)]
    big = both[(both["fast_mean_hz"] >= 1) | (both["ref_mean_hz"] >= 1)]
    return both, {
        "neurons_active_fast": int((both["fast_mean_hz"] > 0).sum()),
        "neurons_active_ref": int((both["ref_mean_hz"] > 0).sum()),
        "pearson_r_all_active": float(np.corrcoef(active["fast_mean_hz"], active["ref_mean_hz"])[0, 1]),
        "max_abs_diff_hz": float(diff.abs().max()),
        "neuron_with_max_diff": int(diff.abs().idxmax()),
        "neurons_rate_ge_1hz": int(len(big)),
        "frac_within_3_se": float((z.loc[big.index].abs().fillna(0) <= 3).mean()),
        "frac_within_4_se": float((z.loc[big.index].abs().fillna(0) <= 4).mean()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--trials", type=int, default=30)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    brain = FastBrain(snapshot="630", n_threads=args.threads)
    load_s = time.perf_counter() - t0
    print(f"loaded v630: {brain.n_neurons} neurons, {brain.n_connections} connections, {load_s:.1f} s")

    # warm-up: compile (or load the compiled cache)
    t0 = time.perf_counter()
    brain.run(excite=SUGAR[:1], duration_ms=10, n_trials=1, seed=0)
    warm_s = time.perf_counter() - t0

    summary = {"snapshot": "630", "n_neurons": brain.n_neurons,
               "n_connections": brain.n_connections, "load_s": load_s,
               "compile_or_cache_s": warm_s, "threads": args.threads, "runs": {}}

    # NOTE: the reference file "sugarR.parquet" was produced with 200 Hz input,
    # not the 150 Hz default in today's model.py: its 21 stimulated GRNs fire
    # at 196.75 Hz, which is what 200 Hz input gives (200 / (1 + 200 dt) =
    # 196.08 Hz; 150 Hz input would give 147.78 Hz). So it is compared with
    # our 200 Hz run.
    runs = [("sugar_100Hz", 100, [], "sugarR_100Hz.parquet"),
            ("sugar_150Hz", 150, [], None),
            ("sugar_200Hz", 200, [], "sugarR.parquet")]
    for f in sorted(REF_EXAMPLE.glob("sugarR-*.parquet")):
        sil = int(f.stem.split("-")[1])
        runs.append((f.stem, 100, [sil], f.name))   # tutorial silencing runs use 100 Hz

    for name, rate, silence, ref_file in runs:
        res = brain.run(excite=SUGAR, silence=silence, rate_hz=rate, duration_ms=1000,
                        n_trials=args.trials, seed=0)
        stats = res.rate_stats()
        stats.to_csv(OUT / f"fast_{name}.csv")
        wall = res.wall_time_s
        entry = {
            "rate_hz": rate, "silenced": silence, "trials": res.n_trials,
            "wall_s": wall, "wall_s_per_trial": wall / res.n_trials,
            "cpu_s_per_trial": wall * args.threads / res.n_trials,
            "spikes_total": int(res.step.size),
            "neurons_reached_mean": float(np.mean(res.neurons_reached)),
            "mn9_hz": res.rate(MN9),
            "mn9_std_hz": float(stats.loc[MN9, "std_hz"]) if MN9 in stats.index else 0.0,
            "mn9b_hz": res.rate(MN9_B),
        }
        if rate in PAPER_MN9 and not silence:
            entry["paper_mn9_hz"] = PAPER_MN9[rate][0]
            entry["paper_mn9_std_hz"] = PAPER_MN9[rate][1]
        entry["stimulated_grn_mean_hz"] = float(stats.reindex(SUGAR)["mean_hz"].mean())
        if ref_file:
            ref = ref_rates(REF_EXAMPLE / ref_file, n_trials=30)
            entry["ref_file"] = ref_file
            entry["ref_stimulated_grn_mean_hz"] = float(ref.reindex(SUGAR)["mean_hz"].mean())
            both, cmp = compare(stats, ref, n_trials=args.trials)
            both.to_csv(OUT / f"compare_{name}.csv")
            cmp["ref_mn9_hz"] = float(ref.loc[MN9, "mean_hz"]) if MN9 in ref.index else 0.0
            cmp["ref_mn9_std_hz"] = float(ref.loc[MN9, "std_hz"]) if MN9 in ref.index else 0.0
            cmp["ref_spikes_total"] = int(pd.read_parquet(REF_EXAMPLE / ref_file).shape[0])
            entry["vs_reference_brian2"] = cmp
        summary["runs"][name] = entry
        print(json.dumps({name: entry}, indent=1))

    # single-thread timing (what one core does per 1 s trial)
    brain.n_threads = 1
    for rate in (100, 200):
        res = brain.run(excite=SUGAR, rate_hz=rate, duration_ms=1000, n_trials=5, seed=1)
        summary[f"single_thread_s_per_trial_{rate}Hz"] = res.wall_time_s / 5
    # a 10 s trial, to check nothing slows down over long runs
    res = brain.run(excite=SUGAR, rate_hz=100, duration_ms=10_000, n_trials=1, seed=2)
    summary["single_thread_s_for_one_10s_trial_100Hz"] = res.wall_time_s
    summary["mn9_hz_10s_trial_100Hz"] = res.rate(MN9)
    del brain

    # v783 loads too; one of the 21 v630 sugar IDs does not exist in v783
    t0 = time.perf_counter()
    b783 = FastBrain(snapshot="783", n_threads=args.threads)
    present = [i for i in SUGAR if i in set(b783.root_ids.tolist())]
    res = b783.run(excite=present, rate_hz=100, duration_ms=1000, n_trials=args.trials, seed=0)
    res.rate_stats().to_csv(OUT / "fast_v783_sugar20_100Hz.csv")
    summary["v783"] = {"n_neurons": b783.n_neurons, "n_connections": b783.n_connections,
                       "load_s": b783.load_time_s, "sugar_ids_present": len(present),
                       "missing": sorted(set(SUGAR) - set(present)),
                       "wall_s_per_trial": res.wall_time_s / res.n_trials,
                       "mn9_hz_100Hz": res.rate(MN9)}
    print(json.dumps({"v783": summary["v783"]}, indent=1))

    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
