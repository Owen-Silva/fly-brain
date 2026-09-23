"""Wider audit: where does the model's excitatory/inhibitory sign disagree
with (a) the literature transmitter (FlyWire ``known_nt``) or (b) the
machine-learning prediction's own top label, and how much could it matter?

Plain English
-------------
Every neuron with outgoing connections gets one sign in the reference file
(+1 excite / -1 inhibit). We compare it with:

A. literature (``known_nt`` names one fast transmitter: acetylcholine -> +1,
   GABA / glutamate -> -1). Disagreements are what the "known_nt" fix flips.
B. the prediction's top label (``top_nt``) turned into a sign with the paper's
   rule, where there is no literature entry. They can disagree because the
   paper decided each neuron's sign by a majority of its individual synapse
   predictions, not by the top label.
C. monoamine neurons (dopamine / serotonin / octopamine, predicted or known):
   the paper treats them as fast excitatory. That is a modelling assumption
   (these act mostly slowly, through other receptors), flagged, not fixed.
D. histamine neurons (mostly photoreceptors): the paper's rule makes them
   excitatory; flagged, not fixed.

"How much could it matter" = outgoing synapses, and whether the neurons are
active in the paper's taste experiments (Phase 3 conditions). Activity comes from our own baseline runs
(config "none" in run_validation.py): a neuron is ACTIVE in a condition if its
mean rate over 90 trials is above 0.5 Hz (the Phase 5 threshold).
Outputs: results/audit_by_type.csv, results/audit_summary.txt
"""

import numpy as np
import pandas as pd

import common as C
from sim import sign_fixes as S

TASTE = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz", "sugar100_bitter120"]
PAPER_RULE = {"acetylcholine": 1, "gaba": -1, "glutamate": -1}

rid, pre, post, signed = S.load_reference_arrays()
lab = S.neuron_table(rid)
n = len(rid)
sign = S.neuron_signs(n, pre, signed)
out_syn = np.bincount(pre, weights=np.abs(signed), minlength=n).astype(np.int64)
del pre, post, signed

# activity in the baseline runs
rates = {}
for cond in TASTE + ["ir94e_200Hz", "dm1_both_150Hz"]:
    tot = np.zeros(n)
    k = 0
    for f in sorted((C.RESULTS / "counts").glob(f"none__{cond}__s*.npz")):
        z = np.load(f)
        tot[z["nz_idx"]] += z["nz_count"]
        k += int(z["n_trials"])
    rates[cond] = tot / max(k, 1)          # 1-s trials -> Hz
missing = [c for c in rates if not rates[c].any()]
taste_active = np.zeros(n, bool)
for c in TASTE:
    taste_active |= rates[c] > 0.5
dm1_active = rates["dm1_both_150Hz"] > 0.5
ir_active = rates["ir94e_200Hz"] > 0.5
taste_max = np.max([rates[c] for c in TASTE], axis=0)

top = lab.top_nt.str.lower().to_numpy()
top_sign = np.array([PAPER_RULE.get(t, 1) for t in top], np.int8)
ks = lab.known_sign.to_numpy()
kind = lab.known_kind.to_numpy()
has_out = sign != 0
mono_pred = np.isin(top, ["dopamine", "serotonin", "octopamine"])

cat = np.full(n, "", object)
cat[has_out & (ks != 0) & (ks != sign)] = "A literature disagrees with model sign (fixed by known_nt)"
cat[has_out & (cat == "") & (ks == 0) & (kind != "histamine") & (top_sign != sign)] = \
    "B top label disagrees with model sign (no literature; paper's per-synapse rule)"
cat[has_out & (cat == "") & (kind == "monoamine")] = "C known monoamine, treated as fast excitatory (assumption)"
cat[has_out & (cat == "") & (ks == 0) & (kind != "histamine") & mono_pred] = \
    "C predicted monoamine, no literature, treated as fast excitatory (assumption)"
cat[has_out & (cat == "") & (kind == "histamine")] = "D histamine (literature), model sign kept (assumption)"
eln = S.eln_mask(lab)
cat[has_out & (cat == "") & (ks != 0) & (ks == sign) & mono_pred] = \
    "E sign agrees with literature but predicted label is a monoamine (e.g. the eLNs)"

typ = np.where(lab.cell_type != "", lab.cell_type,
               np.where(lab.hemibrain_type != "", lab.hemibrain_type, "(" + lab.cell_class + ")"))
d = pd.DataFrame(dict(category=cat, cell_class=lab.cell_class, type=typ, ref_sign=sign,
                      top_nt=lab.top_nt, conf=lab.top_nt_conf, known_nt=lab.known_nt,
                      source=lab.known_nt_source, out=out_syn, taste_active=taste_active,
                      ir_active=ir_active, dm1_active=dm1_active, taste_max_hz=taste_max,
                      active_out=np.where(taste_active, out_syn, 0)))
d = d[d.category != ""]


def mode(s):
    s = s[s != ""]
    return s.value_counts().index[0] if len(s) else ""


g = (d.groupby(["category", "cell_class", "type"])
     .agg(n=("type", "size"), ref_sign=("ref_sign", lambda s: "/".join(map(str, sorted(set(s))))),
          top_nt=("top_nt", mode), mean_conf=("conf", "mean"), known_nt=("known_nt", mode),
          source=("source", mode), out_synapses=("out", "sum"),
          taste_active_neurons=("taste_active", "sum"), ir94e_active_neurons=("ir_active", "sum"),
          dm1_active_neurons=("dm1_active", "sum"),
          taste_max_hz=("taste_max_hz", "max"), active_out_synapses=("active_out", "sum"))
     .reset_index()
     .sort_values(["category", "active_out_synapses", "out_synapses"], ascending=[True, False, False]))
g["mean_conf"] = g.mean_conf.round(2)
g["taste_max_hz"] = g.taste_max_hz.round(1)
g.to_csv(C.RESULTS / "audit_by_type.csv", index=False)

lines = [f"neurons with outgoing connections: {int(has_out.sum()):,}",
         f"known_nt available (mapped from v783): {int((lab.known_nt != '').sum()):,}; "
         f"one fast transmitter: {int((ks != 0).sum()):,}",
         f"activity files missing for: {missing}" if missing else "activity: baseline runs found",
         ""]
for c, dd in d.groupby("category"):
    lines.append(f"{c}: {len(dd):,} neurons, {dd.out.sum():,} outgoing synapses, "
                 f"{int(dd.taste_active.sum())} active in the Phase 3 taste runs "
                 f"({dd.active_out.sum():,} synapses), {int(dd.ir_active.sum())} under Ir94e "
                 f"(runaway-contaminated), {int(dd.dm1_active.sum())} under DM1 (all runaway)")
    gg = g[g.category == c].head(8)
    for _, r in gg.iterrows():
        lines.append(f"    {r['type']} ({r.cell_class}) n={r.n} sign {r.ref_sign} top={r.top_nt} "
                     f"conf={r.mean_conf:.2f} known='{r.known_nt}' out={r.out_synapses:,} "
                     f"taste-active={r.taste_active_neurons} (max {r.taste_max_hz} Hz) "
                     f"ir94e-active={r.ir94e_active_neurons} dm1-active={r.dm1_active_neurons}")
aa = d[d.category.str.startswith("A")]
lines += ["", "A by direction: to inhibitory "
          f"{int((aa.ref_sign == 1).sum())}, to excitatory {int((aa.ref_sign == -1).sum())}",
          "E includes the 44 eLNs: " + str(int((eln & (cat != '') & np.char.startswith(cat.astype(str), 'E')).sum()))]
(C.RESULTS / "audit_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
