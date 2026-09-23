"""Compare the fast engine with the Phase 3 Brian2 port, neuron by neuron.

For every finished Phase 3 condition (experiments/phase3/results/v*/<name>_settings.json
plus <name>_spikes.parquet), run the fast engine with the same snapshot,
stimulated neurons, rates, silenced neurons, duration and number of trials,
and compare every neuron's firing rate. The two runs use different random
input (Brian2's generator vs numpy's), so they agree only up to trial-to-trial
noise; "within 3 standard errors" is the test for that.

Usage:  .venv\\Scripts\\python.exe experiments\\fast_engine\\compare_phase3.py
Writes: experiments/fast_engine/results/phase3_compare.json (+ one CSV per condition)
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim.fast_engine import FastBrain  # noqa: E402

PHASE3 = ROOT / "experiments" / "phase3" / "results"
OUT = Path(__file__).resolve().parent / "results"
MN9 = 720575940660219265


def per_trial_stats(spikes, n_trials, dur_s):
    counts = spikes.groupby(["flywire_id", "trial"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=range(n_trials), fill_value=0) / dur_s
    return pd.DataFrame({"mean_hz": counts.mean(axis=1), "std_hz": counts.std(axis=1, ddof=0)})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    brains, report = {}, {}
    for f_set in sorted(PHASE3.glob("v*/*_settings.json")):
        name = f_set.name[: -len("_settings.json")]
        f_spk = f_set.with_name(f"{name}_spikes.parquet")
        if not f_spk.exists():
            continue
        st = json.loads(f_set.read_text())
        snap = str(st["dataset"])
        if snap not in brains:
            brains[snap] = FastBrain(snapshot=snap, n_threads=2)
        brain = brains[snap]
        n, dur = int(st["n_trials"]), float(st["duration_ms"])
        excite = {int(i): float(st["rate_hz"]) for i in st["excite_ids"]}
        excite.update({int(i): float(st["rate2_hz"]) for i in st.get("excite2_ids", [])})
        # With 10 or fewer Brian2 trials the noise is large, so run 30 fast
        # trials (the paper's protocol) and account for both in the error bars.
        n_fast = max(30, n)
        res = brain.run(excite=excite, silence=st.get("silence_ids", []), duration_ms=dur,
                        n_trials=n_fast, seed=12345)
        fast = res.rate_stats()
        b2 = per_trial_stats(pd.read_parquet(f_spk), n, dur / 1000)
        both = pd.concat([fast.add_prefix("fast_"), b2.add_prefix("brian2_")], axis=1).fillna(0.0)
        diff = both["fast_mean_hz"] - both["brian2_mean_hz"]
        se = np.sqrt(both["fast_std_hz"] ** 2 / n_fast + both["brian2_std_hz"] ** 2 / n)
        z = (diff / se.where(se > 0, np.nan)).fillna(0)
        big = (both["fast_mean_hz"] >= 1) | (both["brian2_mean_hz"] >= 1)
        both.to_csv(OUT / f"phase3_compare_{name}.csv")
        report[name] = {
            "snapshot": snap, "brian2_trials": n, "fast_trials": n_fast,
            "pearson_r": float(np.corrcoef(both["fast_mean_hz"], both["brian2_mean_hz"])[0, 1]),
            "max_abs_diff_hz": float(diff.abs().max()),
            "neurons_rate_ge_1hz": int(big.sum()),
            "frac_within_3_se": float((z[big].abs() <= 3).mean()),
            "frac_within_4_se": float((z[big].abs() <= 4).mean()),
            "mn9_fast_hz": float(both.loc[MN9, "fast_mean_hz"]) if MN9 in both.index else 0.0,
            "mn9_brian2_hz": float(both.loc[MN9, "brian2_mean_hz"]) if MN9 in both.index else 0.0,
            "brian2_s_per_trial": float(np.mean(st.get("trial_s", [np.nan]))),
            "fast_s_per_trial_2threads": res.wall_time_s / n_fast,
        }
        print(json.dumps({name: report[name]}, indent=1), flush=True)
    (OUT / "phase3_compare.json").write_text(json.dumps(report, indent=1))
    if not report:
        print("no finished Phase 3 results yet")


if __name__ == "__main__":
    main()
