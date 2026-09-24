"""Which neurons does each sign-fix variant change, and do any of them fire here?

Plain English
-------------
The two sign-fix variants only change the OUTGOING connections of some neurons
(sim/sign_fixes.py): ``al_ln_literature`` changes the 150 excitatory
antennal-lobe local neurons; ``al_ln_literature+da_5ht_literature`` also removes
the fast outputs of dopamine and serotonin cells known from the literature.
Such a change cannot matter until one of those neurons fires: up to its first
spike the two models receive the same input and do exactly the same thing.
So if none of the changed neurons fires in a published-model run, the variant
gives the identical result for that run (same seed). This script lists, for
every saved published-model condition, how many changed neurons fired.

Output: results/changed_neurons.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sim import sign_fixes as S  # noqa: E402


def main():
    root_ids = pd.read_csv(ROOT / "data" / "reference" / "2023_03_23_completeness_630_final.csv",
                           index_col=0).index.to_numpy()
    lab = S.neuron_table(root_ids)
    ref = pd.read_parquet(ROOT / "data" / "cache" / "connectome_630_neurons.parquet",
                          columns=["root_id", "ref_sign"]).set_index("root_id").reindex(root_ids)
    ref_sign = ref.ref_sign.fillna(0).to_numpy().astype(int)
    alln = (lab.cell_class.to_numpy() == "ALLN") & (ref_sign == 1)
    mod = S.modulatory_mask(lab, ref_sign, ("dopamine", "serotonin"), ("literature",))
    sets = {"al_ln_literature": np.flatnonzero(alln),
            "al_ln_literature+da_5ht_literature": np.flatnonzero(alln | mod)}
    out = {"n_changed": {k: int(v.size) for k, v in sets.items()},
           "n_monoamine_literature_cells": int(mod.sum()), "fired": {}}
    for f in sorted((HERE / "results" / "none").glob("*.npz")):
        z = np.load(f)
        nz = z["nz_idx"]
        out["fired"][f.stem] = {k: int(np.isin(nz, v).sum()) for k, v in sets.items()}
    fired_any = {k: sorted({c for c, d in out["fired"].items() if d[k] > 0}) for k in sets}
    out["conditions_where_changed_neurons_fired"] = fired_any
    (HERE / "results" / "changed_neurons.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"n_changed": out["n_changed"], "fired_in": fired_any}, indent=1))


if __name__ == "__main__":
    main()
