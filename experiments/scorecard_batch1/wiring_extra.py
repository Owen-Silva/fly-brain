"""Scorecard batch 1: extra wiring look-ups used to explain results. NO simulation.

Plain English
-------------
Counts, from the model's own connection list (snapshot 630, the published model's
signs), a few routes the write-up needs:
  * DA1 projection neurons -> each lateral-horn aSP group (test 2)
  * two-step routes LC16 -> X -> MDN (test 9)
  * two-step routes cool sensors -> X -> warm projection neurons, and warm sensors ->
    X -> warm projection neurons, with X's transmitter sign, in the published model and
    with the recommended fix (test 6)
Writes results/wiring_extra.csv and prints a short summary.

Usage:  python experiments/scorecard_batch1/wiring_extra.py
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
G = {k: [int(x) for x in v] for k, v in json.loads((RES / "groups.json").read_text()).items()}


def two_step(pre, post, signed, rows_a, rows_b, lab, top=8):
    """Routes A -> X -> B: per X, synapses in (from A) and out (to B), signed."""
    ma = np.isin(pre, rows_a)
    first = pd.DataFrame({"x": post[ma], "w1": signed[ma]}).groupby("x").w1.sum()
    mb = np.isin(post, rows_b) & np.isin(pre, first.index.to_numpy())
    second = pd.DataFrame({"x": pre[mb], "w2": signed[mb]}).groupby("x").w2.sum()
    t = pd.concat([first, second], axis=1, join="inner")
    t["score"] = t.w1.abs() * t.w2.abs()
    t = t.sort_values("score", ascending=False)
    t["type"] = lab.hemibrain_type.to_numpy()[t.index.to_numpy()]
    t["cell_type"] = lab.cell_type.to_numpy()[t.index.to_numpy()]
    t["class"] = lab.cell_class.to_numpy()[t.index.to_numpy()]
    t["side"] = lab.side.to_numpy()[t.index.to_numpy()]
    return t.head(top), t


def main():
    root_ids, pre, post, signed = S.load_reference_arrays("630")
    lab = S.neuron_table(root_ids)
    row = pd.Series(np.arange(len(root_ids)), index=np.asarray(root_ids, np.int64))
    R = {k: row.loc[v].to_numpy() for k, v in G.items()}
    up = pd.read_csv(RES / "upn_glomeruli.csv")
    da1_pn = up[up.glomerulus == "DA1"].idx.to_numpy()
    out = []

    # test 2: DA1 PNs -> aSP groups (direct)
    for g in ("FC5_read_aSPg", "FC5_read_aSPf", "FC5_read_aSPh"):
        m = np.isin(pre, da1_pn) & np.isin(post, R[g])
        per_cell = pd.Series(signed[m], index=post[m]).groupby(level=0).sum()
        n_cells = len(R[g])
        n_hit = int((per_cell >= 5).sum())
        out.append(dict(test="2 FC5", route=f"DA1 uPNs -> {g}", synapses=int(signed[m].sum()),
                        detail=f"{n_hit} of {n_cells} cells get >= 5 synapses from DA1 uPNs"))
        print(out[-1], flush=True)

    # test 9: LC16 -> X -> MDN
    top, allx = two_step(pre, post, signed, R["SD1_stim_LC16"], R["SD1_read_MDN"], lab)
    out.append(dict(test="9 SD1", route="LC16 -> X -> MDN", synapses=int(len(allx)),
                    detail="; ".join(f"{r.type or r.cell_type} ({r.side}) in {r.w1} out {r.w2}"
                                     for r in top.itertuples())))
    print(out[-1], flush=True)

    # test 6: cool / warm sensors -> X -> warm PNs, published signs and with the fix
    for fix in ("none", "al_ln_literature"):
        p2, q2, s2, _ = S.apply_fix(fix, root_ids, pre, post, signed, lab)
        for src in ("TH_stim_cool", "TH_stim_warm"):
            top, allx = two_step(p2, q2, s2, R[src], R["TH2_read_VP2PN"], lab)
            net = int((np.sign(allx.w1) * allx.w2).sum())
            inh = allx[allx.w2 < 0]
            exc = allx[allx.w2 > 0]
            out.append(dict(test="6 TH2", route=f"[{fix}] {src} -> X -> warm PNs",
                            synapses=net,
                            detail=(f"{len(allx)} relays; inhibitory relays' output to warm PNs "
                                    f"{int(inh.w2.sum())} syn ({len(inh)} cells), excitatory "
                                    f"{int(exc.w2.sum())} ({len(exc)} cells); top: "
                                    + "; ".join(f"{r.type or r.cell_type} ({r['class']}) in "
                                                f"{r.w1} out {r.w2}"
                                                for _, r in top.head(5).iterrows()))))
            print(out[-1], flush=True)
        del p2, q2, s2
    pd.DataFrame(out).to_csv(RES / "wiring_extra.csv", index=False)


if __name__ == "__main__":
    main()
