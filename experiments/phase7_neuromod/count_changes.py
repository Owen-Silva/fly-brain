"""Count exactly what the two neuromodulator fixes change, and check who drives PPL1-γ1pedc.

Plain English
-------------
1. For each new fix ("al_ln_literature+da_modulatory", "al_ln_literature+da_5ht_modulatory"
   and "al_ln_literature+da_5ht_literature", sim/sign_fixes.py) this lists every cell type whose
   fast outgoing connections are removed: how many cells, connections and synapses, whether
   the cell's transmitter comes from the literature (FlyWire known_nt) or only from the
   machine prediction, and the prediction's confidence.
2. Identity check: the neurons that push the "punishment" dopamine neurons PPL1-γ1pedc
   (PPL101) during a sniff in Phase 8 (experiments/phase8/results/trace_ppl1_brain_alln.csv):
   predicted transmitter and confidence, literature transmitter and source, and what each
   new fix does to them.

Nothing is simulated here (no brain is built). Writes results/fix_reports.json,
results/removed_by_type_<fix>.csv and results/identity_ppl101_inputs.csv.
"""

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
RES.mkdir(exist_ok=True)

rid, pre, post, signed = S.load_reference_arrays()
lab = S.neuron_table(rid)
amine, evidence = S.monoamine_of(lab)
p0, q0, s0, rep0 = S.apply_fix("al_ln_literature", rid, pre, post, signed, lab)
del pre, post, signed
sign0 = S.neuron_signs(len(rid), p0, s0)
syn_out = np.bincount(p0, weights=np.abs(s0), minlength=len(rid))
con_out = np.bincount(p0, minlength=len(rid))
conf = pd.to_numeric(lab.top_nt_conf, errors="coerce").to_numpy()
name = np.where(lab.hemibrain_type != "", lab.hemibrain_type, lab.cell_type)
name = np.where(name != "", name, "untyped")

reports = {"al_ln_literature": dict(summary=rep0.summary())}
masks = {}
for fix, amines in S.NEUROMOD_FIXES.items():
    # applied to the reference arrays (the fix starts from al_ln_literature itself)
    r_ids, r_pre, r_post, r_signed = S.load_reference_arrays()
    p1, q1, s1, rep = S.apply_fix(fix, r_ids, r_pre, r_post, r_signed, lab)
    del r_pre, r_post, r_signed, p1, q1, s1
    reports[fix] = dict(summary=rep.summary(), notes=rep.notes, **rep.details)
    m = S.modulatory_mask(lab, sign0, amines,
                          S.NEUROMOD_EVIDENCE.get(fix, ("literature", "prediction")))
    masks[fix] = m
    d = pd.DataFrame(dict(cell_type=name[m], super_class=lab.super_class.to_numpy()[m],
                          cell_class=lab.cell_class.to_numpy()[m], amine=amine[m],
                          evidence=evidence[m], predicted=lab.top_nt.to_numpy()[m],
                          pred_conf=conf[m], known_nt=lab.known_nt.to_numpy()[m],
                          known_nt_source=lab.known_nt_source.to_numpy()[m],
                          connections=con_out[m], synapses=syn_out[m]))
    g = (d.groupby(["cell_type", "super_class", "cell_class", "amine", "evidence", "predicted",
                    "known_nt", "known_nt_source"], dropna=False)
         .agg(neurons=("synapses", "size"), connections=("connections", "sum"),
              synapses=("synapses", "sum"), mean_pred_conf=("pred_conf", "mean"))
         .reset_index().sort_values("synapses", ascending=False))
    g.to_csv(RES / f"removed_by_type_{fix.replace('+', '_')}.csv", index=False)
    print(f"\n=== {fix}: {rep.summary()}")
    print(json.dumps(rep.details["by_amine_and_evidence"]))
    print(g.head(12)[["cell_type", "amine", "evidence", "neurons", "synapses"]].to_string(index=False))

# neurons left out of the masks on purpose (so the counts are on record)
for label, m in {
    "monoamine by rule but model sign -1 or 0 (left alone)": np.isin(amine, ["dopamine", "serotonin"]) & (sign0 != 1),
    "antennal-lobe local neurons with a monoamine label (al_ln rule instead)": np.isin(amine, ["dopamine", "serotonin"]) & (lab.cell_class.to_numpy() == "ALLN"),
    "sensory neurons known only by prediction (left alone)": np.isin(amine, ["dopamine", "serotonin"]) & (evidence == "prediction") & (lab.super_class.to_numpy() == "sensory"),
    "CSD (fast acetylcholine reported)": np.isin(name, ["CSD"]),
    "octopamine / tyramine cells, sign +1 (not changed)": np.isin(amine, ["octopamine", "tyramine"]) & (sign0 == 1),
}.items():
    reports.setdefault("left_alone", {})[label] = dict(neurons=int(m.sum()),
                                                       synapses=int(syn_out[m].sum()))
(RES / "fix_reports.json").write_text(json.dumps(reports, indent=1))

# ---- identity check of PPL101's inputs --------------------------------------
tr = pd.read_csv(ROOT / "experiments" / "phase8" / "results" / "trace_ppl1_brain_alln.csv")
tr = tr[tr.drive_per_sniff.abs() >= 100].copy()
rows = []
for _, r in tr.iterrows():
    m = name == r.input_type
    if not m.any() or r.input_type == "untyped":
        continue
    rows.append(dict(
        input_type=r.input_type, drive_per_sniff=round(r.drive_per_sniff, 1),
        in_mb_circuit=r.in_circuit, cells=int(m.sum()),
        predicted="/".join(sorted(set(lab.top_nt.to_numpy()[m]))),
        pred_conf=(f"{np.nanmin(conf[m]):.2f}-{np.nanmax(conf[m]):.2f}" if m.sum() > 1
                   else f"{conf[m][0]:.2f}"),
        known_nt="; ".join(sorted(set(lab.known_nt.to_numpy()[m]) - {""}))[:80],
        known_nt_source="; ".join(sorted(set(lab.known_nt_source.to_numpy()[m]) - {""}))[:120],
        amine_rule="/".join(sorted(set(amine[m]) - {""})),
        evidence="/".join(sorted(set(evidence[m]) - {""})),
        model_sign=int(sign0[m][0]),
        **{f"cells_removed_by_{f.split('+')[1]}": f"{int(masks[f][m].sum())}/{int(m.sum())}" for f in masks}))
idt = pd.DataFrame(rows)
idt.to_csv(RES / "identity_ppl101_inputs.csv", index=False)
print("\n=== PPL1-gamma1pedc (PPL101) inputs (|drive| >= 100 per sniff, Phase 8 trace) ===")
print(idt.drop(columns=["known_nt_source"]).to_string(index=False))
