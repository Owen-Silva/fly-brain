"""Tables for the neuromodulator-fix validation (Phase 7 item 5).

Plain English
-------------
Reads results/trials.csv (this lane) and experiments/phase7_signs/results/trials.csv (the
al_ln_literature numbers, same seeds and trials) and writes:
* results/identity_check.csv: the al_ln_literature trials re-run here (seed 0, trials 0-9 of
  every condition) must match the stored ones exactly (same code, same input);
* results/table_validation.csv / .md: per model and check, MN9 rate, runaway count, Kenyon
  cells active, total spikes, with the verdict for each Phase 3 / Phase 6 check;
* results/top_changed_<config>__<condition>.csv: the neurons whose firing changed most
  compared with al_ln_literature (spikes per trial, summed over 3 seeds x 30 trials).
"""

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RES = HERE / "results"
P7 = ROOT / "experiments" / "phase7_signs" / "results"
CONDS = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz", "sugar100_bitter120",
         "ir94e_200Hz", "dm1_both_150Hz"]
N_KC = 5177
KEYS = ["condition", "seed_index", "trial"]
MEAS = ["total_spikes", "n_active", "max_distinct_10ms", "mn9_hz", "kc_active"]

mine = pd.read_csv(RES / "trials.csv")
ref = pd.read_csv(P7 / "trials.csv")
ref = ref[ref.config == "al_ln_literature"]

# 1. identity check
chk = mine[mine.config == "al_ln_check"].merge(ref, on=KEYS, suffixes=("_new", "_stored"))
for m in MEAS:
    chk[f"{m}_same"] = chk[f"{m}_new"] == chk[f"{m}_stored"]
chk["all_same"] = chk[[f"{m}_same" for m in MEAS]].all(axis=1)
chk[KEYS + ["all_same"] + [f"{m}_{s}" for m in MEAS for s in ("new", "stored")]].to_csv(
    RES / "identity_check.csv", index=False)
print(f"identity check: {int(chk.all_same.sum())} of {len(chk)} re-run al_ln_literature trials "
      f"identical to the stored ones")

# 2. validation table
models = {"al_ln_literature": ref,
          "+da_modulatory": mine[mine.config == "da_modulatory"],
          "+da_5ht_modulatory": mine[mine.config == "da_5ht_modulatory"],
          "+da_5ht_literature": mine[mine.config == "da_5ht_literature"]}
rows = []
for name, d in models.items():
    for c in CONDS:
        x = d[d.condition == c]
        if x.empty:
            continue
        seed_means = x.groupby("seed_index").mn9_hz.mean()
        rows.append(dict(model=name, condition=c, trials=len(x),
                         mn9_hz=x.mn9_hz.mean(), mn9_seed_min=seed_means.min(),
                         mn9_seed_max=seed_means.max(), runaway=int(x.runaway.sum()),
                         kc_active=x.kc_active.mean(), kc_pct=100 * x.kc_active.mean() / N_KC,
                         total_spikes=x.total_spikes.mean()))
t = pd.DataFrame(rows)
base = t[t.model == "al_ln_literature"].set_index("condition")


def verdict(r):
    b = base.loc[r.condition]
    c = r.condition
    if c in ("sugar_100Hz", "sugar_200Hz", "water_200Hz"):
        ok = r.mn9_hz > 10 and abs(r.mn9_hz - b.mn9_hz) <= 0.1 * b.mn9_hz
        return ("PASS" if ok else "FAIL") + f" (MN9 {r.mn9_hz:.1f} vs {b.mn9_hz:.1f} Hz)"
    if c == "bitter_200Hz":
        return ("PASS" if r.mn9_hz < 1 else "FAIL") + f" (MN9 {r.mn9_hz:.2f} Hz)"
    if c == "sugar100_bitter120":
        return ("PASS" if r.mn9_hz < 5 else "FAIL") + f" (MN9 {r.mn9_hz:.2f} Hz; sugar alone {base.loc['sugar_100Hz'].mn9_hz:.1f})"
    if c == "ir94e_200Hz":
        return ("PASS" if r.runaway == 0 else "FAIL") + f" (runaway {r.runaway}/{r.trials})"
    ok = r.runaway == 0 and r.kc_pct <= 10
    return ("PASS" if ok else "FAIL") + (f" (runaway {r.runaway}/{r.trials}; KCs active "
                                         f"{r.kc_active:.0f} = {r.kc_pct:.1f}%)")


t["verdict"] = t.apply(verdict, axis=1)
t.to_csv(RES / "table_validation.csv", index=False)
md = ["| check | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
for c in CONDS:
    cells = []
    for name in models:
        r = t[(t.model == name) & (t.condition == c)]
        cells.append(r.verdict.iloc[0] if len(r) else "not run")
    md.append(f"| {c} | " + " | ".join(cells) + " |")
(RES / "table_validation.md").write_text("\n".join(md), encoding="utf-8")
print("\n".join(md))

# 3. which neurons changed most (vs al_ln_literature, same trials)
try:
    import sys
    sys.path.insert(0, str(ROOT))
    from sim.sign_fixes import load_reference_arrays, neuron_table
    rid = load_reference_arrays()[0]
    lab = neuron_table(rid)
    name = np.where(lab.hemibrain_type != "", lab.hemibrain_type, lab.cell_type)

    def counts(folder, cfg, cond):
        tot = np.zeros(rid.size, np.int64)
        for k in (0, 1, 2):
            z = np.load(folder / f"{cfg}__{cond}__s{k}.npz")
            tot[z["nz_idx"]] += z["nz_count"]
        return tot / 90.0

    for cfg in ("da_modulatory", "da_5ht_modulatory", "da_5ht_literature"):
        for cond in ("sugar_100Hz", "water_200Hz", "dm1_both_150Hz"):
            a = counts(P7 / "counts", "al_ln_literature", cond)
            b = counts(RES / "counts", cfg, cond)
            diff = b - a
            o = np.argsort(-np.abs(diff))[:25]
            pd.DataFrame(dict(root_id=rid[o], cell_type=name[o], cell_class=lab.cell_class.to_numpy()[o],
                              top_nt=lab.top_nt.to_numpy()[o], al_ln_hz=a[o], variant_hz=b[o],
                              change_hz=diff[o])).to_csv(RES / f"top_changed_{cfg}__{cond}.csv",
                                                         index=False)
            print(f"{cfg} {cond}: neurons changed by >1 Hz: {int((np.abs(diff) > 1).sum())}; "
                  f"largest: {name[o[0]]} {a[o[0]]:.1f} -> {b[o[0]]:.1f} Hz")
except FileNotFoundError as e:
    print(f"top-changed lists skipped: {e}")
