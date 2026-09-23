"""Write the ready-made setups that come with the app (run once; safe to re-run).

    .venv\\Scripts\\python.exe -m app.make_ready_setups

Plain English: this writes app/setups/sugar_bitter_competition.json and
app/setups/da1_left_smell_fix.json with the real engine's name and code
fingerprints, so loading them later can tell whether the code has changed.
The neuron ids come from app/engine_adapter.py (the paper's lists and the
Phase 6 steering selection). The expected numbers in the descriptions were
measured through the app on 2026-09-23 (see docs/phase4-app-explained.md).
"""
from __future__ import annotations

from . import engine_adapter as ea
from . import setups as st

MN9 = [str(ea.MN9_LEFT_ID), str(ea.MN9_RIGHT_IDS["630"])]

READY = [
    {
        "name": "sugar_bitter_competition",
        "title": "Sugar 100 Hz + bitter 40 Hz -> MN9 (taste competition)",
        "description": (
            "Phase 5 competition experiment, the paper's Fig. 3b point. Two stimulus groups on "
            "the published model, map 630: the 21 right-side sugar taste neurons at 100 Hz and the "
            "21 bitter taste neurons (the paper's list, sim/shiu_model.py BITTER_R_630) at 40 Hz. "
            "1000 ms x 30 trials, seed 0. Both MN9 neurons are watched. Expected: MN9 "
            "(720575940660219265) drops from 67.6 Hz with sugar alone to {mn9} Hz here "
            "(paper: 45.3 Hz; our Phase 5 run with seed 0: 47.7 Hz). Bitter at 80 Hz takes it to "
            "about 13 Hz and at 120 Hz to about 1.4 Hz (docs/phase5-competition.md)."),
        "stim_groups": [{"name": "Sugar", "rate_hz": 100.0, "ids": [str(i) for i in ea.SUGAR_GRN_IDS_630]},
                        {"name": "Bitter", "rate_hz": 40.0, "ids": [str(i) for i in ea.BITTER_GRN_IDS_630]}],
        "watch": MN9,
        "variant": {"fix": "none", "upgrades": []},
    },
    {
        "name": "da1_left_smell_fix",
        "title": "DA1 smell, left antenna only -> steering neurons (recommended fix)",
        "description": (
            "Phase 6 steering experiment. The 60 DA1 smell neurons (ORN_DA1, the cVA pheromone "
            "channel) of the LEFT antenna at 150 Hz, 1000 ms x 30 trials, seed 0, on the "
            "recommended neurotransmitter fix (map 630). Watched: the steering descending neurons "
            "DNa02, DNpe002 and DNb05, left and right. Expected (docs/phase6-steering.md): the LEFT "
            "DNa02 fires much more than the right one, i.e. 'turn left' (Phase 6 result, mean of "
            "3 seeds: 22.7 vs 1.0 Hz; this setup, seed 0: {dna02}). DA1 is the only smell channel "
            "that steers this way, and only with the fix; on the published model the smell centre "
            "runs away and every smell says 'turn left'."),
        "stim_groups": [{"name": "DA1 smell, left antenna", "rate_hz": 150.0,
                         "ids": [str(i) for i in ea.DA1_LEFT_ORN_IDS_630]}],
        "watch": [str(i) for _, left, right in ea.STEERING_DN_IDS_630 for i in (left, right)],
        "variant": {"fix": "al_ln_literature", "upgrades": []},
    },
]


# Measured through the app on 2026-09-23 (seed 0, 30 trials); used in the descriptions.
MEASURED = {"mn9": "47.7",
            "dna02": "left 22.9 Hz vs right 0.8 Hz; DNpe002 46.1 vs 0 Hz; DNb05 47.0 vs 0 Hz"}


def main(measured: dict[str, str] | None = None):
    measured = {**MEASURED, **(measured or {})}
    adapter = ea.EngineAdapter(force_fake=False)
    if adapter.engine_info.get("is_fake") or adapter.engine_info["name"] != "sim.fast_engine":
        raise SystemExit("refusing to write ready-made setups without the real fast engine: "
                         + adapter.engine_info["reason"])
    for r in READY:
        body = {**r, "description": r["description"].format(
                    mn9=measured.get("mn9", "about 47-48"), dna02=measured.get("dna02", "see the app")),
                "silence": [], "duration_ms": 1000.0, "n_trials": 30, "seed": 0, "snapshot": "630"}
        s = st.save_setup(body, adapter.engine_info, overwrite=True)
        print(f"wrote app/setups/{s['name']}.json  ({s['variant']['label']}; {st.groups_text(s['stim_groups'])})")


if __name__ == "__main__":
    import sys
    main(dict(a.split("=", 1) for a in sys.argv[1:]))
