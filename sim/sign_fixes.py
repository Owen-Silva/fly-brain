"""Phase 7, upgrade 5 ("missing pieces"): switchable neurotransmitter-sign fixes.

What this is, in plain English
------------------------------
The published model (Shiu et al. 2024) decides whether each neuron excites or
inhibits its partners from a machine-learning GUESS of its transmitter
(Eckstein et al. 2024): acetylcholine excites, GABA and glutamate inhibit,
everything else (dopamine, serotonin, octopamine, no guess) excites.

Phase 6 found that about 44 excitatory "local neurons" in the antennal lobe
(the fly's first smell centre) make the whole simulated brain lock into
non-stop firing ("runaway"). This file builds the brain with a named fix
applied, so every result can be compared with and without it. Nothing on
disk is changed; the fix is applied to the connection list in memory, and
the brain is then built with ``FastBrain.from_arrays`` exactly as the normal
loader builds it (same neuron order, same connection order).

The fixes (``FIXES``)
---------------------
``"none"``
    The paper's model, untouched. Reproduces ``FastBrain("630")`` spike for
    spike (tests/test_sign_fixes.py checks this).

``"eln_electrical"``  (the narrow eLN fix: only the 44 literature-typed eLNs)
    The 44 excitatory local neurons (eLNs) KEEP their excitatory sign, but
    their chemical synapses are kept only onto neurons the model treats as
    inhibitory; their chemical synapses onto every other neuron (projection
    neurons, other eLNs, ...) are removed. Why:

    * They are cholinergic (excitatory). FlyWire's literature column
      (``known_nt``, Schlegel et al. 2024) lists these 44 as acetylcholine,
      citing antibody staining in Shang et al. 2007 (Cell 128:601), who found
      "a previously unidentified population of cholinergic local neurons".
      The transmitter-prediction paper itself says their serotonin/dopamine
      guesses are probably wrong: "we find ~13 lLN2T_abc neurons that have a
      cell body placement and general morphology most similar to reported
      cholinergic local neurons" and nearby lLN1_bc neurons "predicted to be
      dopaminergic" are suspected mispredictions (Eckstein et al. 2024, Cell
      187:2574, STAR Methods). So making them inhibitory would contradict
      the sources.
    * Their excitation of projection neurons is electrical, not chemical:
      "eLN-to-iLN synapses are largely cholinergic, whereas eLN-to-PN
      synapses are mainly or purely electrical" (Yaksi & Wilson 2010, Neuron
      67:1034). The model has no electrical synapses, so the faithful thing
      the model CAN do is to drop the chemical eLN -> non-inhibitory
      connections and keep eLN -> inhibitory ones. The electrical coupling
      itself is still missing (see docs/phase7-neurotransmitter-audit.md).
    * Caveat kept on record: Huang et al. 2010 (Neuron 67:1021, abstract)
      reported eLN -> PN connections "mediated by dendrodendritic cholinergic
      synapses and gap junctions", i.e. a chemical part too. The two papers
      disagree on that point.
    * Validated result: stops the taste (Ir94e) runaway but NOT strong smell
      input (DM1 150 Hz still runs away in 90 of 90 trials), because ~100
      other local neurons the model treats as excitatory keep the loop.

``"al_ln_literature"``  (RECOMMENDED; see docs/phase7-neurotransmitter-audit.md)
    The eLN rule applied to the whole antennal-lobe local-neuron population.
    Two rules, both for antennal-lobe local neurons (cell_class ALLN) only:

    1. An LN the model treats as excitatory but whose literature transmitter
       (``known_nt``) is GABA or glutamate becomes inhibitory (13 neurons:
       9 lLN2P_b "gaba, MIP" Sizemore et al. 2023; 2 il3LN6 GABA Tanaka et
       al. 2012; 2 v2LN36 glutamate Chou et al. 2022; ...).
    2. Every remaining LN the model treats as excitatory (137, including the
       44 eLNs) keeps its excitatory sign but, like the measured eLNs (Yaksi
       & Wilson 2010), keeps chemical synapses only onto inhibitory neurons.
       The extension from the 44 literature-typed eLNs to all excitatory LNs
       is an inference, not a measurement: in this model an excitatory LN IS
       an eLN, and the only excitatory LNs ever recorded behave this way.
       Why it is needed: with the 44 alone, strong smell input (68 DM1 smell
       neurons at 150 Hz) still self-sustains through the other excitatory
       LNs (experiments/phase7_signs/results/diag_variants.csv).

``"known_nt"``
    Wherever FlyWire's literature transmitter (``known_nt``) names exactly
    one kind of FAST transmitter (acetylcholine -> +1; GABA or glutamate ->
    -1, the paper's own rule) and that sign differs from the reference
    file's sign, the neuron's sign is set to the literature one. Monoamines,
    histamine, neuropeptides and mixed entries are NOT applied (the paper's
    "monoamines excite" rule is a modelling assumption, not something this
    variant tries to fix). Note: the eLNs are unaffected (literature and
    model both say excitatory).

``"ln53_inhibitory"``  (comparison only; NOT literature-backed)
    The Phase 5 olfaction lane's "LN-fix": the 53 antennal-lobe local
    neurons predicted serotonin or dopamine are made inhibitory. Kept so its
    numbers can be reproduced; the sources above contradict it for the 34
    literature-typed eLNs among them.

Where the neuron labels come from
---------------------------------
Cell class / type / predicted transmitter: data/cache/connectome_630_neurons
(FlyWire annotation v1.1.0 for snapshot 630). ``known_nt`` only exists in the
newer v783 annotation (data/flywire/Supplemental_file1_neuron_annotations.tsv),
whose root IDs differ; it is carried over to snapshot 630 through each
neuron's representative supervoxel ID (a fixed piece of the EM volume listed
in both annotation files), with the root ID as a fallback. 127,218 of the
127,400 model neurons are matched this way (77,161 of them have a
``known_nt`` entry).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from sim.fast_engine import REFERENCE_DIR, SNAPSHOTS, FastBrain

ROOT = Path(__file__).resolve().parents[1]
LABELS_630 = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"
ANN_630 = ROOT / "data" / "flywire" / "Supplemental_file1_annotations_v1.1.0_630.tsv"
ANN_783 = ROOT / "data" / "flywire" / "Supplemental_file1_neuron_annotations.tsv"

FIXES = ("none", "eln_electrical", "al_ln_literature", "known_nt", "ln53_inhibitory")
#: The recommended default (see docs/phase7-neurotransmitter-audit.md).
RECOMMENDED_FIX = "al_ln_literature"

#: Fast transmitters and the sign the paper's rule gives them.
FAST_SIGN = {"acetylcholine": 1, "gaba": -1, "glutamate": -1}
MONOAMINES = ("dopamine", "serotonin", "octopamine", "tyramine")

#: Where the eLN set comes from: FlyWire known_nt source for these types.
ELN_SOURCE = "Shang et al., 2007"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_reference_arrays(snapshot="630"):
    """The reference connection list exactly as ``FastBrain.__init__`` reads
    it: (root_ids, pre_index, post_index, signed_count), file order kept."""
    comp_name, con_name = SNAPSHOTS[str(snapshot)]
    root_ids = pd.read_csv(REFERENCE_DIR / comp_name, index_col=0).index.to_numpy()
    table = pq.read_table(REFERENCE_DIR / con_name, columns=[
        "Presynaptic_ID", "Presynaptic_Index", "Postsynaptic_Index",
        "Excitatory x Connectivity"])
    pre = table.column("Presynaptic_Index").to_numpy()
    if not np.array_equal(root_ids[pre], table.column("Presynaptic_ID").to_numpy()):
        raise ValueError("Presynaptic_Index does not match the completeness file")
    post = table.column("Postsynaptic_Index").to_numpy()
    signed = table.column("Excitatory x Connectivity").to_numpy()
    return root_ids, pre, post, signed


def known_nt_sign(text):
    """Classify one FlyWire ``known_nt`` entry.

    Returns (sign, kind): sign is +1 / -1 when the entry names exactly one
    kind of fast transmitter (ignoring "...-negative" results), else 0.
    kind is one of "none", "fast", "mixed_fast", "monoamine", "histamine",
    "other" (neuropeptides, nitric oxide only, ...).
    """
    if text is None or (isinstance(text, float) and np.isnan(text)) or text is pd.NA:
        return 0, "none"
    toks = [t.strip().lower() for t in re.split(r"[;,]", str(text)) if t.strip()]
    toks = [t for t in toks if not t.endswith("negative")]
    if not toks:
        return 0, "none"
    if "histamine" in toks:
        # Histamine (photoreceptors, some others) is not covered by the
        # paper's sign rule; entries naming it (even with acetylcholine,
        # e.g. R7/R8) are left alone and only flagged in the audit.
        return 0, "histamine"
    signs = {FAST_SIGN[t] for t in toks if t in FAST_SIGN}
    if len(signs) == 1:
        return signs.pop(), "fast"
    if len(signs) > 1:
        return 0, "mixed_fast"
    if any(t in MONOAMINES for t in toks):
        return 0, "monoamine"
    return 0, "other"


def neuron_table(root_ids):
    """Labels for every model neuron, in the model's row order.

    Columns: root_id, cell_class, cell_type, hemibrain_type, side, top_nt,
    top_nt_conf (630 annotation), known_nt, known_nt_source (v783, carried
    over by supervoxel), known_sign, known_kind.
    """
    root_ids = np.asarray(root_ids, dtype=np.int64)
    lab = pd.read_parquet(LABELS_630, columns=[
        "root_id", "super_class", "cell_class", "cell_type", "hemibrain_type",
        "side", "top_nt", "top_nt_conf"])
    lab = lab.set_index("root_id").reindex(root_ids)
    lab.index.name = "root_id"
    lab = lab.reset_index()
    for c in ("super_class", "cell_class", "cell_type", "hemibrain_type", "side", "top_nt"):
        lab[c] = lab[c].astype(object).where(lab[c].notna(), "").astype(str)

    a630 = pd.read_csv(ANN_630, sep="\t", usecols=["supervoxel_id", "root_id"],
                       dtype={"root_id": "int64", "supervoxel_id": "int64"})
    a630 = a630.drop_duplicates("root_id").set_index("root_id").supervoxel_id
    a783 = pd.read_csv(ANN_783, sep="\t",
                       usecols=["supervoxel_id", "root_id", "known_nt", "known_nt_source"],
                       dtype={"root_id": "int64", "supervoxel_id": "int64",
                              "known_nt": "string", "known_nt_source": "string"})
    by_sv = a783.set_index("supervoxel_id")
    by_rid = a783.set_index("root_id")
    known = np.full(root_ids.size, "", dtype=object)
    source = np.full(root_ids.size, "", dtype=object)
    matched = np.zeros(root_ids.size, bool)
    has_sv = np.isin(root_ids, a630.index.to_numpy())
    sv = a630.reindex(root_ids[has_sv]).to_numpy(np.int64)  # exact ints, no NaN here
    in783 = np.isin(sv, by_sv.index.to_numpy())
    rows = np.flatnonzero(has_sv)[in783]
    hit = by_sv.loc[sv[in783]]
    known[rows] = hit.known_nt.fillna("").to_numpy(object)
    source[rows] = hit.known_nt_source.fillna("").to_numpy(object)
    matched[rows] = True
    rest = np.flatnonzero(~matched & np.isin(root_ids, by_rid.index.to_numpy()))
    if rest.size:
        hit = by_rid.loc[root_ids[rest]]
        known[rest] = hit.known_nt.fillna("").to_numpy(object)
        source[rest] = hit.known_nt_source.fillna("").to_numpy(object)
        matched[rest] = True
    lab["known_nt"] = known
    lab["known_nt_source"] = source
    lab["matched_783"] = matched
    ks = [known_nt_sign(k if k else None) for k in known]
    lab["known_sign"] = np.array([s for s, _ in ks], np.int8)
    lab["known_kind"] = [k for _, k in ks]
    return lab


def neuron_signs(n_neurons, pre, signed):
    """Each neuron's sign in the reference file (+1, -1, or 0 = no outgoing
    connections). Raises if any neuron has mixed signs."""
    s = np.sign(signed).astype(np.int64)
    pos = np.bincount(pre, weights=(s > 0), minlength=n_neurons)
    neg = np.bincount(pre, weights=(s < 0), minlength=n_neurons)
    if ((pos > 0) & (neg > 0)).any():
        raise ValueError("a neuron has both signs in the reference file")
    return np.where(pos > 0, 1, np.where(neg > 0, -1, 0)).astype(np.int8)


def eln_mask(lab):
    """The excitatory antennal-lobe local neurons: antennal-lobe local neurons
    (cell_class ALLN) whose FlyWire literature transmitter is acetylcholine,
    citing Shang et al. 2007. In snapshot 630: 30 lLN1_bc, 4 lLN2T_b,
    4 lLN2T_c and 6 lLN2X03 (= hemibrain lLN2T_a) = 44 neurons."""
    return ((lab.cell_class.to_numpy() == "ALLN")
            & (lab.known_sign.to_numpy() == 1)
            & lab.known_nt_source.astype(str).str.contains(ELN_SOURCE, regex=False).to_numpy())


def ln53_mask(lab):
    """Phase 5's 53 antennal-lobe local neurons predicted serotonin/dopamine."""
    return ((lab.cell_class.to_numpy() == "ALLN")
            & np.isin(lab.top_nt.to_numpy(), ["serotonin", "dopamine"]))


# ---------------------------------------------------------------------------
# Applying a fix
# ---------------------------------------------------------------------------
@dataclass
class FixReport:
    """What a fix changed, counted."""
    fix: str
    n_connections_before: int
    n_connections_after: int
    removed_connections: int = 0
    removed_synapses: int = 0
    flipped_neurons: list = field(default_factory=list)      # root IDs
    flipped_connections: int = 0
    flipped_synapses: int = 0
    to_inhibitory: int = 0
    to_excitatory: int = 0
    target_neurons: list = field(default_factory=list)       # root IDs the fix is about
    notes: str = ""

    def summary(self):
        return (f"{self.fix}: connections {self.n_connections_before:,} -> "
                f"{self.n_connections_after:,} (removed {self.removed_connections:,}, "
                f"{self.removed_synapses:,} synapses); sign flipped for "
                f"{len(self.flipped_neurons)} neurons ({self.to_inhibitory} to inhibitory, "
                f"{self.to_excitatory} to excitatory; {self.flipped_connections:,} "
                f"connections, {self.flipped_synapses:,} synapses)")


def apply_fix(fix, root_ids, pre, post, signed, lab=None):
    """Return (pre, post, signed, report) with ``fix`` applied. The inputs are
    not modified. Connection order is kept (removed ones are just left out)."""
    if fix not in FIXES:
        raise ValueError(f"unknown fix {fix!r}; choose one of {FIXES}")
    n = len(root_ids)
    rep = FixReport(fix, int(pre.size), int(pre.size))
    if fix == "none":
        return pre, post, signed, rep
    if lab is None:
        lab = neuron_table(root_ids)
    sign = neuron_signs(n, pre, signed)
    rid = np.asarray(root_ids, dtype=np.int64)

    if fix == "eln_electrical":
        eln = eln_mask(lab)
        drop = eln[pre] & (sign[post] != -1)
        keep = ~drop
        rep.removed_connections = int(drop.sum())
        rep.removed_synapses = int(np.abs(signed[drop]).sum())
        rep.target_neurons = rid[eln].tolist()
        rep.notes = ("eLN chemical synapses kept only onto neurons with reference sign -1 "
                     "(Yaksi & Wilson 2010); eLN sign stays +1 (Shang et al. 2007)")
        pre, post, signed = pre[keep], post[keep], signed[keep]
        rep.n_connections_after = int(pre.size)
        return pre, post, signed, rep

    if fix == "al_ln_literature":
        al = lab.cell_class.to_numpy() == "ALLN"
        ks = lab.known_sign.to_numpy()
        to_inh = al & (sign == 1) & (ks == -1)
        new_sign = np.where(to_inh, -1, sign)
        exc_ln = al & (new_sign == 1)
        drop = exc_ln[pre] & (new_sign[post] != -1)
        flip_rows = to_inh[pre] & ~drop
        signed = signed.copy()
        signed[flip_rows] = -signed[flip_rows]
        rep.flipped_neurons = rid[to_inh].tolist()
        rep.to_inhibitory = int(to_inh.sum())
        rep.flipped_connections = int(flip_rows.sum())
        rep.flipped_synapses = int(np.abs(signed[flip_rows]).sum())
        rep.removed_connections = int(drop.sum())
        rep.removed_synapses = int(np.abs(signed[drop]).sum())
        rep.target_neurons = rid[exc_ln | to_inh].tolist()
        rep.notes = (f"{int(to_inh.sum())} ALLNs with literature GABA/glutamate made inhibitory; "
                     f"{int(exc_ln.sum())} excitatory ALLNs keep chemical synapses only onto "
                     "inhibitory neurons (Yaksi & Wilson 2010 rule)")
        keep = ~drop
        pre, post, signed = pre[keep], post[keep], signed[keep]
        rep.n_connections_after = int(pre.size)
        return pre, post, signed, rep

    if fix == "known_nt":
        ks = lab.known_sign.to_numpy()
        flip = (ks != 0) & (sign != 0) & (ks != sign)
        rep.notes = "literature fast transmitter (FlyWire known_nt) overrides the predicted sign"
    else:  # ln53_inhibitory
        flip = ln53_mask(lab) & (sign == 1)
        rep.notes = "Phase 5 LN-fix: 53 serotonin/dopamine-predicted AL local neurons made inhibitory"
    rep.target_neurons = rid[flip].tolist()
    rep.flipped_neurons = rid[flip].tolist()
    rep.to_inhibitory = int((flip & (sign == 1)).sum())
    rep.to_excitatory = int((flip & (sign == -1)).sum())
    m = flip[pre]
    signed = signed.copy()
    signed[m] = -signed[m]
    rep.flipped_connections = int(m.sum())
    rep.flipped_synapses = int(np.abs(signed[m]).sum())
    return pre, post, signed, rep


def build_brain(fix="none", snapshot="630", params=None, n_threads=1, return_report=False,
                lab=None):
    """A FastBrain with ``fix`` applied (snapshot 630 only).

    ``fix="none"`` gives the paper's model, identical spike for spike to
    ``FastBrain("630")``. Use ``return_report=True`` to also get a
    ``FixReport`` saying exactly what changed.
    """
    if str(snapshot) != "630":
        raise ValueError("sign fixes are defined for snapshot 630 only")
    root_ids, pre, post, signed = load_reference_arrays(snapshot)
    pre2, post2, signed2, rep = apply_fix(fix, root_ids, pre, post, signed, lab)
    del pre, post, signed
    brain = FastBrain.from_arrays(root_ids, pre2, post2, signed2, params=params,
                                  n_threads=n_threads)
    brain.snapshot = f"630+{fix}"
    brain.sign_fix = fix
    return (brain, rep) if return_report else brain
