"""Phase 7 item 5 (electrical synapses): the coupling table and the calibration.

Plain English
-------------
1. Lists every pair of neurons that gets an electrical synapse, one row per
   pair, with the paper that justifies it (results/coupling_table.csv).
2. Writes the literature evidence as a small table (results/evidence_table.csv):
   what was measured, where, and whether it is used.
3. Finds the junction strength (kappa = junction conductance / the cell's own
   leak conductance) that makes the model's coupling coefficients equal the
   measured ones, and reports what else follows from it: the coefficient in
   the opposite direction (PN -> eLN), how much each cell's input conductance
   grows, and the size of one spikelet (results/calibration.json).
No simulation; only the wiring table is loaded.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from sim import gap_junctions as G  # noqa: E402
from sim import sign_fixes as S  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(parents=True, exist_ok=True)

EVIDENCE = [
    # class, cells, measurement, value(s), where, read, used
    ("eln_pn", "krasavietz eLN -> PN (antennal lobe)",
     "coupling coefficient, depolarizing step (eLN spiking)",
     "0.010 control; 0.014 Cd2+ (chemical block); ~0 in shakB2 (n=37 control, 19 mutant pairs)",
     "Yaksi & Wilson 2010 Neuron 67:1034, Fig. 4C (bar chart, read by eye)", "full text + figure",
     "yes (target 0.013 = mean of 0.010, 0.014, 0.015)"),
    ("eln_pn", "krasavietz eLN -> PN", "coupling coefficient, hyperpolarizing step",
     "~0.0025 control; ~0 in shakB2", "Yaksi & Wilson 2010 Fig. 4C (read by eye)",
     "full text + figure", "no (reported; model junction is symmetric, not rectifying)"),
    ("eln_pn", "PN -> krasavietz eLN", "coupling coefficient, depol / hyperpol",
     "depol 0.032 control, 0.005 Cd2+; hyperpol ~0.006 control, ~0.004 Cd2+",
     "Yaksi & Wilson 2010 Fig. 4F (read by eye)", "full text + figure",
     "check only (model value reported)"),
    ("eln_pn", "krasavietz eLN <-> PN", "'electrical coupling ratio'",
     "eLN->PN depol ~0.015, hyperpol ~0.007; PN->eLN depol ~0.008, hyperpol ~0.010",
     "Huang et al. 2010 Neuron 67:1021, Fig. 3D (figure only; text not accessible)",
     "abstract + figures", "yes (0.015 in the target mean)"),
    ("eln_pn", "krasavietz eLN -> PN", "spike-triggered average PN response per eLN spike",
     "~0.1-0.7 mV per pair (~60% of the rise before the spike; part chemical)",
     "Huang et al. 2010 Fig. 3E-K", "abstract + figures", "check only (model spikelet reported)"),
    ("eln_pn", "eLN -> all PNs", "connection probability",
     "74 dual recordings: 37 excitatory, 17 inhibitory, rest none; 'each eLN is connected to "
     "most or all PNs'", "Yaksi & Wilson 2010 Results", "full text",
     "yes (rule: eLN coupled to every uPN of every glomerulus it innervates)"),
    ("sister_pn", "homotypic ipsilateral PNs, DM6", "coupling coefficient",
     "hyperpol ~0.013 (control), ~0.011 (Cd2+); depol ~0.034 control, ~0.016 Cd2+; "
     "heterotypic pairs ~0", "Kazama & Wilson 2009 Nat Neurosci 12:1136, Fig. 7b,d (read by eye)",
     "full text + figure", "yes (target 0.016 = depolarizing, Cd2+)"),
    ("sister_pn", "sister PNs, DA1", "coupling coefficient",
     "depol ~0.018, hyperpol ~0.008 (control); ~0 in shakB2 (4+4 pairs)",
     "Yaksi & Wilson 2010 Fig. 6C (read by eye)", "full text + figure", "supports; not in target"),
    ("eln_iln", "eLN -> inhibitory LN", "mixed chemical + electrical",
     "'largely chemical with a smaller electrical component'; iLN types not identifiable in "
     "FlyWire", "Yaksi & Wilson 2010 Fig. 5", "full text (figure 5 not viewed)",
     "no (partners not mappable; chemical part already in model)"),
    ("eln_eln", "eLN <-> eLN", "reciprocal connections",
     "'Reciprocal connections were also found between two krasavietz eLNs' (mechanism not in "
     "abstract)", "Huang et al. 2010 abstract", "abstract only", "no (UNVERIFIED mechanism)"),
    ("apl_dpm", "APL <-> DPM (mushroom body)", "innexin localisation + RNAi behaviour",
     "inx7 in APL, inx6 in DPM; no coupling strength", "Wu et al. 2011 Curr Biol 21:848",
     "abstract only", "no (no strength measured; would need an invented conductance)"),
    ("kc_kc / kc_mbon", "Kenyon cells; KC <-> MBON-b'2mp", "dye coupling, behaviour",
     "dye coupling in 10 of 14 brains between same-subtype KCs; no strength; which KCs "
     "unknown", "Liu et al. 2016 eLife 5:e13238 (full text searched)", "full text (searched)",
     "no (cannot say which of ~5,000 KCs; no strength)"),
    ("vs_hs", "VS/HS lobula plate cells", "shakB needed for stability",
     "partners and strengths not in abstract", "Ammer et al. 2022 Curr Biol", "abstract only",
     "no (UNVERIFIED; visual, outside every check)"),
]


def main():
    rid, pre, post, signed = S.load_reference_arrays()
    lab = S.neuron_table(rid)
    table = G.coupling_table(rid, pre, post, signed, lab)
    upn = G.upn_glomeruli(lab, pre, post, signed)
    del pre, post, signed
    kap = G.calibrate_kappa(table)
    table["kappa"] = table.cls.map(kap)
    pcc = G.pair_cc(table, kap)
    table["model_cc_ab"] = pcc.cc_ab.round(5).to_numpy()
    table["model_cc_ba"] = pcc.cc_ba.round(5).to_numpy()
    table.drop(columns=["a", "b"]).to_csv(OUT / "coupling_table.csv", index=False)
    upn.to_csv(OUT / "upn_glomeruli.csv", index=False)
    pd.DataFrame(EVIDENCE, columns=["class", "cells", "measurement", "values", "source",
                                    "what_was_read", "used"]).to_csv(
        OUT / "evidence_table.csv", index=False)

    n = rid.size
    tot = np.zeros(n)
    np.add.at(tot, table.a.to_numpy(), table.kappa.to_numpy())
    np.add.at(tot, table.b.to_numpy(), table.kappa.to_numpy())
    eln = S.eln_mask(lab)
    is_upn = np.zeros(n, bool)
    is_upn[upn.idx.to_numpy()] = True
    e = table[table.cls == "eln_pn"]
    s = table[table.cls == "sister_pn"]
    t_mbr = 20.0
    info = dict(
        cc_target=G.CC_TARGET,
        kappa=kap,
        two_cell_cc_of_kappa={c: G.two_cell_cc(k) for c, k in kap.items()},
        n_pairs=table.cls.value_counts().to_dict(),
        n_eln=int(e.a.nunique()), n_upn=int(len(upn)), n_upn_coupled_to_eln=int(e.b.nunique()),
        n_glomeruli=int(upn.glomerulus.nunique()),
        upn_per_eln_median=float(e.groupby("a").size().median()),
        eln_per_upn_median=float(e.groupby("b").size().median()),
        sister_groups_with_2plus=int((upn.groupby(["glomerulus", "side"]).size() >= 2).sum()),
        model_cc_eln_to_pn_median=float(np.median(pcc.cc_ab[pcc.cls == "eln_pn"])),
        model_cc_pn_to_eln_median=float(np.median(pcc.cc_ba[pcc.cls == "eln_pn"])),
        measured_cc_pn_to_eln="depol 0.005 (Cd2+) / 0.008 (Huang); hyperpol 0.004-0.010",
        model_cc_sister_median=float(np.median(np.r_[pcc.cc_ab[pcc.cls == "sister_pn"],
                                                     pcc.cc_ba[pcc.cls == "sister_pn"]])),
        total_kappa_eln_median=float(np.median(tot[eln])),
        total_kappa_upn_median=float(np.median(tot[is_upn])),
        input_conductance_factor_eln=float(1 + np.median(tot[eln])),
        input_conductance_factor_upn=float(1 + np.median(tot[is_upn])),
        spike_area_mV_ms=G.SPIKE_AREA_MV_MS,
        spikelet_mV={c: k * G.SPIKE_AREA_MV_MS / t_mbr for c, k in kap.items()},
        dm1_upn_per_side=upn[upn.glomerulus == "DM1"].side.value_counts().to_dict(),
        da1_upn_per_side=upn[upn.glomerulus == "DA1"].side.value_counts().to_dict(),
        dm1_eln_per_side=e[e.glomerulus == "DM1"].groupby("side").a.nunique().to_dict(),
        eln_side=lab[eln].side.value_counts().to_dict(),
        eln_glomerulus_same_side_frac=float((lab.side.to_numpy()[e.a.to_numpy()]
                                             == e.side.to_numpy()).mean()),
    )
    for sc in (0.5, 2.0):
        k2 = {c: k * sc for c, k in kap.items()}
        p2 = G.pair_cc(table, k2)
        info[f"x{sc}"] = dict(kappa=k2,
                              model_cc_eln_to_pn_median=float(np.median(p2.cc_ab[p2.cls == "eln_pn"])),
                              model_cc_sister_median=float(np.median(np.r_[
                                  p2.cc_ab[p2.cls == "sister_pn"], p2.cc_ba[p2.cls == "sister_pn"]])),
                              total_kappa_eln_median=float(np.median(tot[eln]) * sc))
    (OUT / "calibration.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
