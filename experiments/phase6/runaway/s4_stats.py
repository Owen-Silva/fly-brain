"""Summary statistics for the write-up (reads saved results; no simulation).

* Runaway rate per condition with a 95% confidence range (Clopper-Pearson).
* Does the Phase 3 "5x the median" rule agree with our definition?
* Brian2 (2 of 5) vs fast engine: how likely is 2+ runaways in 5 trials at
  the fast engine's rate, and a Fisher exact test.
* MN9 in runaway vs healthy trials.

Output: results/summary_stats.txt
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import RESULTS, add_5x_rule  # noqa: E402

out = []


def say(s=""):
    out.append(s)
    print(s)


def ci(k, n):
    lo = stats.beta.ppf(0.025, k, n - k + 1) if k > 0 else 0.0
    hi = stats.beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return lo, hi


def rate_line(name, d):
    k, n = int(d.runaway.sum()), len(d)
    lo, hi = ci(k, n)
    return f"{name}: {k}/{n} runaway = {100 * k / n:.1f}% (95% range {100 * lo:.1f}-{100 * hi:.1f}%)"


rep = add_5x_rule(pd.read_csv(RESULTS / "reproduce_trials.csv"), ["condition", "seed"])
say("== Step 1a: 30 trials x 5 seeds, 1 s each (fast engine) ==")
for c, d in rep.groupby("condition", sort=False):
    say(rate_line(c, d) + f"; per seed {d.groupby('seed').runaway.sum().tolist()}; "
        f"median spikes healthy {d[~d.runaway].total_spikes.median():.0f}, runaway "
        f"{d[d.runaway].total_spikes.median() if d.runaway.any() else float('nan'):.0f}")
agree = (rep.runaway == rep.runaway_5x_median).mean()
say(f"Phase 3 rule (spikes > 5x median of its condition+seed) agrees with our definition in "
    f"{100 * agree:.1f}% of {len(rep)} trials; disagreements: "
    f"{rep[rep.runaway != rep.runaway_5x_median][['condition', 'seed', 'trial', 'total_spikes', 'onset_ms']].to_dict('records')}")
gap = rep[~rep.runaway].max_distinct_10ms.max(), rep[rep.runaway].max_distinct_10ms.min()
say(f"Most neurons firing in any 10 ms slice: healthy trials max {gap[0]}, runaway trials min {gap[1]} "
    f"(threshold 1,500): the two groups do not overlap.")
hh = rep[~rep.runaway].sort_values("max_distinct_10ms", ascending=False)
say(f"  top healthy values: {hh.max_distinct_10ms.head(3).tolist()} "
    f"({hh.iloc[0].condition} seed {hh.iloc[0].seed} trial {hh.iloc[0].trial} has "
    f"{hh.iloc[0].distinct_last_100ms} neurons firing in its last 100 ms: it was starting to run "
    f"away in its final 10 ms, so it is a borderline case counted as healthy)")
m = rep[rep.condition == "sugar200_ir94e200"]
say(f"MN9 (contra) sugar200+Ir94e200: healthy {m[~m.runaway].mn9_hz.mean():.1f} +/- "
    f"{m[~m.runaway].mn9_hz.std(ddof=0):.1f} Hz (n={int((~m.runaway).sum())}), runaway "
    f"{m[m.runaway].mn9_hz.mean():.1f} +/- {m[m.runaway].mn9_hz.std(ddof=0):.1f} Hz "
    f"(n={int(m.runaway.sum())}); all trials {m.mn9_hz.mean():.1f} Hz (paper 64.3)")
say(f"Onsets (ms): main {sorted(m.onset_ms.dropna().astype(int).tolist())}; Ir94e alone "
    f"{sorted(rep[rep.condition == 'ir94e200_alone'].onset_ms.dropna().astype(int).tolist())}")

say("\n== Step 2: Brian2 vs fast engine ==")
b2 = pd.read_csv(RESULTS / "brian2_replay.csv")
say(f"Same input replayed: spike totals identical in {int((b2.brian2_total == b2.fast_total).sum())}/5 "
    f"trials; runaway flags identical {int((b2.brian2_runaway == b2.fast_runaway).sum())}/5; onsets "
    f"{b2.brian2_onset_ms.tolist()} vs {b2.fast_onset_ms.tolist()}")
k, n = int(m.runaway.sum()), len(m)
p = k / n
p_ge2 = 1 - stats.binom.cdf(1, 5, p)
lo, hi = ci(k, n)
say(f"If the true rate is {100 * p:.1f}%, the chance of 2+ runaways in 5 trials is {100 * p_ge2:.1f}% "
    f"(at the top of the 95% range, {100 * hi:.1f}%: {100 * (1 - stats.binom.cdf(1, 5, hi)):.1f}%).")
odds, pf = stats.fisher_exact([[2, 3], [k, n - k]])
say(f"Fisher exact test, Brian2 2/5 vs fast engine {k}/{n}: p = {pf:.3f}")
pool = rep[rep.condition == "sugar200_ir94e200"]
extra = []
for f in ("grid.csv", "duration.csv", "wsyn.csv"):
    if (RESULTS / f).exists():
        extra.append(f)
if (RESULTS / "grid.csv").exists():
    g = pd.read_csv(RESULTS / "grid.csv")
    say("\n== Step 1b: grid (seed 10) ==")
    for nm, d in g.groupby("name", sort=False):
        say(rate_line(nm, d) + f", MN9 {d.mn9_hz.mean():.1f} Hz")
if (RESULTS / "duration.csv").exists():
    d = pd.read_csv(RESULTS / "duration.csv")
    say("\n== Step 1d: 3-s trials (seed 20) ==")
    say(rate_line("sugar200_ir94e200, 3 s", d) + f"; onsets {sorted(d.onset_ms.dropna().astype(int).tolist())}")
    on = d.onset_ms.dropna()
    say(f"  ran away within 1 s: {int((on < 1000).sum())}, 1-2 s: {int(((on >= 1000) & (on < 2000)).sum())}, "
        f"2-3 s: {int((on >= 2000).sum())}; still firing in the last 100 ms of every runaway: "
        f"{bool((d[d.runaway].distinct_last_100ms > 1500).all()) if d.runaway.any() else 'n/a'}")
    both1 = pd.concat([m.runaway, d.assign(r1=(d.onset_ms < 1000)).r1])
    say(f"  pooled 1-s estimate incl. first second of 3-s trials: {int(both1.sum())}/{len(both1)}")
if (RESULTS / "persistence.csv").exists():
    ps = pd.read_csv(RESULTS / "persistence.csv")
    say("\n== Step 1d: input switched off ==")
    for t, d in ps.groupby("test", sort=False):
        say(f"{t}: {int(d.runaway.sum())}/{len(d)} ran away; neurons firing in the last 100 ms: "
            f"{d.distinct_last_100ms.tolist()}")
if (RESULTS / "wsyn.csv").exists():
    w = pd.read_csv(RESULTS / "wsyn.csv")
    say("\n== Step 1c: synapse strength (seed 0, same inputs) ==")
    for nm, d in w.groupby("name", sort=False):
        say(rate_line(nm, d) + f", MN9 {d.mn9_hz.mean():.1f} Hz")
say("\n== Step 3: lesion and trigger tests ==")
f_p = stats.fisher_exact([[9, 51], [0, 60]])[1]
say(f"Ir94e 200 Hz, 60 trials: intact 9/60 vs a group silenced 0/60 -> Fisher p = {f_p:.4f}")
for f in ("lesion_population.csv", "lesion_controls.csv", "strong_loops_tests.csv",
          "sustain_tests.csv", "v2ln30_flip.csv"):
    if (RESULTS / f).exists():
        d = pd.read_csv(RESULTS / f)
        cols = [c for c in ("test", "variant", "group", "trigger_size", "n", "runaway", "mn9_mean_hz",
                            "median_spikes") if c in d.columns]
        say(f"-- {f}")
        say(d[cols].to_string(index=False))
if (RESULTS / "lesions.csv").exists():
    l = pd.read_csv(RESULTS / "lesions.csv")
    say("-- lesions.csv (paired re-runs of 16 known runaway trials; confounded, see doc)")
    say(l.groupby("group", sort=False).runaway.agg(["sum", "size"]).to_string())
(RESULTS / "summary_stats.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
