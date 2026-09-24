"""Scorecard batch 1: which active inputs drive a read-out cell in a given run. NO new simulation.

Plain English
-------------
For a saved run (results/raw/<version>/<condition>_s0.npz) and a read-out group, list the
presynaptic cells that actually fired in that run, ranked by (their firing rate) x (their
signed synapses onto the group). Positive = net excitation, negative = net inhibition.
This is a look-up in the saved spikes and the connection list, not a new experiment.
Writes results/explain.csv.

Usage:  python experiments/scorecard_batch1/explain.py
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

RES = HERE / "results"
RAW = RES / "raw"
G = {k: [int(x) for x in v] for k, v in json.loads((RES / "groups.json").read_text()).items()}

#: (version, condition, read-out group, label)
CASES = [
    ("none", "FC2_SAG", "FC2_read_pC1b", "1 FC2 pC1b"),
    ("none", "FC2_SAG", "FC2_read_pC1cde", "1 FC2 pC1c-e"),
    ("none", "SD1_LC16_both_100", "SD1_read_MDN", "9 SD1 MDN"),
    ("none", "SD2_LC16_left_100", "SD1_read_MDN", "9 SD2 MDN (left LC16)"),
    ("none", "TF4_sugar", "TF4_read_Usnea", "10 TF4 Usnea (sugar)"),
    ("none", "TF4_water", "TF4_read_Clavicle", "10 TF4 Clavicle (water)"),
    ("al_ln_literature", "FC5_DA1_150", "FC5_read_aSPg", "2 FC5 aSP-g (fix)"),
    ("al_ln_literature", "LL1_O", "LL1_read_MBON0304", "8 LL1 MBON03/04 (fix)"),
    ("al_ln_literature", "LL1_O", "LL1_read_MBON02", "8 LL1 MBON02 (fix, odour)"),
    ("al_ln_literature", "LL1_OM", "LL1_read_MBON02", "8 LL1 MBON02 (fix, odour + MVP2)"),
    ("al_ln_literature", "LL1_O", "LL1_read_MBON18", "8 LL1 MBON18 (fix, odour)"),
    ("al_ln_literature", "TH2_WC", "TH2_read_VP2PN", "6 TH2 warm PNs (fix, warm+cool)"),
    ("al_ln_literature", "TH3_T1_8mV", "TH3_read_DN1a", "5 TH3 DN1a (fix, cool)"),
]


def main():
    root_ids, pre, post, signed = S.load_reference_arrays("630")
    lab = S.neuron_table(root_ids)
    fixed = {"none": (pre, post, signed)}
    p2, q2, s2, _ = S.apply_fix("al_ln_literature", root_ids, pre, post, signed, lab)
    fixed["al_ln_literature"] = (p2, q2, s2)
    row = pd.Series(np.arange(len(root_ids)), index=np.asarray(root_ids, np.int64))
    out = []
    for ver, cond, grp, label in CASES:
        f = RAW / ver / f"{cond}_s0.npz"
        if not f.exists():
            print("missing", f, flush=True)
            continue
        z = np.load(f)
        n_trials = z["key_trials"].shape[1]
        rate = np.zeros(len(root_ids))
        rate[z["nz_idx"]] = z["nz_count"] / n_trials           # Hz (1 s trials)
        P, Q, W = fixed[ver]
        tgt = row.loc[G[grp]].to_numpy()
        m = np.isin(Q, tgt) & (rate[P] > 0)
        d = pd.DataFrame({"pre": P[m], "w": W[m]}).groupby("pre").w.sum()
        drive = d * rate[d.index.to_numpy()]
        t = pd.DataFrame({"signed_synapses": d, "rate_hz": rate[d.index.to_numpy()],
                          "drive": drive}).sort_values("drive", key=np.abs, ascending=False)
        tot_exc = float(drive[drive > 0].sum())
        tot_inh = float(drive[drive < 0].sum())
        for rank, (i, r) in enumerate(t.head(6).iterrows()):
            out.append(dict(case=label, version=ver, condition=cond, rank=rank + 1,
                            pre_root_id=int(root_ids[i]),
                            pre_type=lab.hemibrain_type[i] or lab.cell_type[i],
                            pre_class=lab.cell_class[i], pre_side=lab.side[i],
                            signed_synapses=int(r.signed_synapses), rate_hz=round(r.rate_hz, 1),
                            drive=round(r.drive, 0), total_exc_drive=round(tot_exc, 0),
                            total_inh_drive=round(tot_inh, 0)))
        top = "; ".join(f"{o['pre_type']} ({o['pre_side'][:1]}) {o['signed_synapses']} syn x "
                        f"{o['rate_hz']} Hz" for o in out[-min(6, len(t)):])
        print(f"{label}: exc {tot_exc:.0f}, inh {tot_inh:.0f} | {top}", flush=True)
    pd.DataFrame(out).to_csv(RES / "explain.csv", index=False)


if __name__ == "__main__":
    main()
