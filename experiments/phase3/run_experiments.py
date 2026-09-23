"""Run the Phase 3 experiments with the Brian2 port and save the results.

Usage (from the project root):
    .venv/Scripts/python.exe experiments/phase3/run_experiments.py NAME [NAME ...]
    .venv/Scripts/python.exe experiments/phase3/run_experiments.py --list

Each experiment writes three files to experiments/phase3/results/<snapshot>/:
    <name>_spikes.parquet   every spike: t (seconds), trial, flywire_id, exp_name
                            (the same layout the reference code writes)
    <name>_rates.csv        per-neuron mean firing rate and std over trials (Hz)
    <name>_settings.json    exact settings, seeds, versions and timings
An experiment whose files already exist is skipped (like the reference's
force_overwrite=False), so an interrupted queue can simply be restarted.

PROTOCOL NOTE: the paper ran 30 trials of 1 s per condition. On this machine
one 1 s trial takes about 55 s for snapshot 630 when run alone (100-120 s when
two run side by side) and about 3x longer for 783, so a full 30-trial condition
would take 30-60 min. These runs are therefore REDUCED: 10 trials of 1 s for the
main conditions, 5 for the control/dose conditions, 3 for the 783 cross-check.
(783 is slower here only because its 138,639-neuron arrays are just over the
size where Windows hands out fresh memory for every temporary numpy array.)
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim import shiu_model as sm  # noqa: E402

OUT = ROOT / "experiments" / "phase3" / "results"


def S(ds):
    return {
        "sugar": sm.ids_for(ds, sm.SUGAR_R_630),
        "bitter": sm.ids_for(ds, sm.BITTER_R_630),
        "water": sm.ids_for(ds, sm.WATER_R_630),
        "ir94e": sm.ids_for(ds, sm.IR94E_630),
    }


# name: (snapshot, excite set, rate, excite2 set, rate2, n_trials, seed)
EXPERIMENTS = {
    # --- snapshot 630 (the paper's data): primary comparison ---
    "sugar_100Hz":              ("630", "sugar", 100, None, 0, 10, 1_000),
    "sugar_200Hz":              ("630", "sugar", 200, None, 0, 10, 2_000),
    "water_200Hz":              ("630", "water", 200, None, 0, 10, 3_000),
    "bitter_200Hz":             ("630", "bitter", 200, None, 0, 5, 4_000),
    "sugar100_bitter40":        ("630", "sugar", 100, "bitter", 40, 5, 5_000),
    "sugar100_bitter120":       ("630", "sugar", 100, "bitter", 120, 10, 6_000),
    "sugar200_ir94e200":        ("630", "sugar", 200, "ir94e", 200, 5, 7_000),
    # --- snapshot 783 (public release): secondary check ---
    # NOT RUN: dropped on 2026-09-22 for time and RAM (machine shared with other
    # lanes); the fast engine covers 783. Kept here so they can be run later.
    "v783_sugar_100Hz":         ("783", "sugar", 100, None, 0, 3, 11_000),
    "v783_sugar100_bitter120":  ("783", "sugar", 100, "bitter", 120, 3, 16_000),
}


def run_one(name):
    ds, exc, rate, exc2, rate2, n_trials, seed = EXPERIMENTS[name]
    out = OUT / f"v{ds}"
    out.mkdir(parents=True, exist_ok=True)
    f_spk, f_rate, f_set = (out / f"{name}_spikes.parquet", out / f"{name}_rates.csv",
                            out / f"{name}_settings.json")
    if f_spk.exists() and f_rate.exists() and f_set.exists():
        print(f">>> skip {name}: results exist", flush=True)
        return
    sets = S(ds)
    mn9 = sm.mn9_ids(ds)
    print(f">>> {name}: snapshot {ds}, {exc} {rate} Hz"
          + (f" + {exc2} {rate2} Hz" if exc2 else "") + f", {n_trials} x 1000 ms, seed {seed}", flush=True)
    res = sm.run_trials(sets[exc], duration_ms=1000, n_trials=n_trials, rate_hz=rate,
                        excite2_ids=sets[exc2] if exc2 else (), rate2_hz=rate2,
                        seed=seed, dataset=ds, exp_name=name, verbose=True, progress_ids=mn9)
    res.spikes.to_parquet(f_spk, compression="brotli", index=False)
    df = res.rates.to_frame().join(res.rate_std)
    df.index.name = "flywire_id"
    df.to_csv(f_rate)
    st = dict(res.settings)
    st.update({"excite_set": exc, "excite2_set": exc2, "snapshot": ds,
               "protocol": f"REDUCED: {n_trials} trials x 1000 ms (paper: 30 x 1000 ms)",
               "mn9_left_contra": mn9[0], "mn9_right_ipsi": mn9[1],
               "finished": time.strftime("%Y-%m-%d %H:%M:%S")})
    f_set.write_text(json.dumps(st, indent=1))
    print(f"<<< {name}: MN9 contra {res.rate_of(mn9[0]):.1f} Hz, ipsi {res.rate_of(mn9[1]):.1f} Hz, "
          f"{len(res.rates)} active neurons, {st['total_s']:.0f} s", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--list"]:
        print("\n".join(EXPERIMENTS))
        sys.exit(0)
    for a in args:
        run_one(a)
