"""Phase 2 cross-check: the reference's 783 files vs FlyWire's official tables.

Compares the reference paper's preprocessed connection list
(data/reference/Connectivity_783.parquet) with FlyWire's own release-783
files on Zenodo (doi:10.5281/zenodo.10676866, no account needed):

* proofread_root_ids_783.npy       - the official list of 139,255 neurons
* proofread_connections_783.feather - every neuron pair, split by brain
  region ("neuropil"), with synapse counts and the average neurotransmitter
  prediction of those synapses (852 MB; streamed in chunks here)

Answers: do the connection counts match? Why are 616 neurons missing from
the reference neuron list? Can the reference's +/- sign be re-derived from
FlyWire's neurotransmitter predictions? How many connections pass the
5-synapse threshold used in Dorkenwald et al. 2024?

Run:  .venv\\Scripts\\python.exe experiments\\phase2\\crosscheck_zenodo.py
Writes experiments/phase2/crosscheck_zenodo.txt
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.ipc as ipc

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import connectome as C  # noqa: E402

OUT = Path(__file__).with_name("crosscheck_zenodo.txt")
FEATHER = C.FLYWIRE_DIR / "proofread_connections_783.feather"
FEATHER_URL = ("https://zenodo.org/records/10676866/files/"
               "proofread_connections_783.feather")
NT_COLS = ["ach_avg", "gaba_avg", "glut_avg", "da_avg", "ser_avg", "oct_avg"]
NT_NAMES = ["acetylcholine", "gaba", "glutamate", "dopamine", "serotonin",
            "octopamine"]

lines: list[str] = []


def say(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def pct(a, b) -> str:
    return f"{100.0 * a / b:.2f}%"


def main() -> None:
    if not FEATHER.exists():
        raise SystemExit(f"Missing {FEATHER}. Download it (852 MB, no "
                         f"account) from:\n  {FEATHER_URL}")
    t0 = time.perf_counter()
    proof = np.load(C.ensure_proofread_ids()).astype(np.int64)
    pidx = pd.Index(proof)
    NP = len(proof)

    # ---- stream the official connection table ---------------------------
    reader = ipc.open_file(FEATHER)
    nt_sum = np.zeros((NP, len(NT_COLS)))     # synapse-weighted NT sums
    out_syn = np.zeros(NP)
    in_syn = np.zeros(NP)
    keys, counts = [], []
    n_rows = rows_ge5 = unknown_ids = null_nt_rows = 0
    for b in range(reader.num_record_batches):
        batch = reader.get_batch(b)
        pre = pidx.get_indexer(batch.column("pre_pt_root_id").to_numpy())
        post = pidx.get_indexer(batch.column("post_pt_root_id").to_numpy())
        syn = batch.column("syn_count").to_numpy().astype(np.int64)
        unknown_ids += int((pre < 0).sum() + (post < 0).sum())
        n_rows += len(syn)
        rows_ge5 += int((syn >= 5).sum())
        for k, col in enumerate(NT_COLS):
            # A few rows have no prediction (null); count them as zero.
            vals = batch.column(col).to_numpy(zero_copy_only=False)
            if k == 0:
                null_nt_rows += int(np.isnan(vals).sum())
            nt_sum[:, k] += np.bincount(
                pre, weights=syn * np.nan_to_num(vals), minlength=NP)
        out_syn += np.bincount(pre, weights=syn, minlength=NP)
        in_syn += np.bincount(post, weights=syn, minlength=NP)
        keys.append(pre.astype(np.int64) * NP + post)
        counts.append(syn.astype(np.int32))
    keys = np.concatenate(keys)
    counts = np.concatenate(counts)
    # Sum each pair over brain regions -> one row per neuron pair.
    zkeys, inv = np.unique(keys, return_inverse=True)
    zsyn = np.bincount(inv, weights=counts).astype(np.int64)
    del keys, counts, inv
    zpre, zpost = zkeys // NP, zkeys % NP
    autapse = zpre == zpost

    say("Phase 2 cross-check: reference 783 files vs FlyWire Zenodo 783 tables")
    say(f"(generated {time.strftime('%Y-%m-%d %H:%M')}, "
        f"took {time.perf_counter() - t0:.0f} s to stream the table)")
    say()
    say("== 1. The official connection table ==")
    say(f"rows (pair x brain region):           {n_rows:,}")
    say(f"root ids not in the official list:    {unknown_ids}")
    say(f"rows with no neurotransmitter value:  {null_nt_rows}")
    say(f"neuron pairs after summing regions:   {len(zkeys):,}")
    say(f"  of which self-connections:          {int(autapse.sum()):,} "
        f"({int(zsyn[autapse].sum()):,} synapses)")
    say(f"total synapses:                       {int(zsyn.sum()):,}")
    say(f"total synapses without self-links:    {int(zsyn[~autapse].sum()):,}")
    say(f"rows (pair x region) with >=5 syn:    {rows_ge5:,}")
    ge5 = (zsyn >= 5) & ~autapse
    ge5_neurons = np.union1d(zpre[ge5], zpost[ge5])
    say(f"neuron pairs with >=5 synapses:       {int(ge5.sum()):,} "
        f"between {len(ge5_neurons):,} neurons")
    say("  published (Dorkenwald 2024): 2,700,513 connections between "
        "134,181 neurons at >=5 synapses")
    say()

    # ---- compare with the reference connection list ----------------------
    brain = C.load_connectome("783")
    ids = brain.neurons["root_id"].to_numpy()
    rpre = pidx.get_indexer(ids[brain.edges["pre"].to_numpy()])
    rpost = pidx.get_indexer(ids[brain.edges["post"].to_numpy()])
    rkeys = rpre.astype(np.int64) * NP + rpost
    rsyn = brain.edges["syn_count"].to_numpy()
    pos = np.searchsorted(zkeys, rkeys)
    pos[pos == len(zkeys)] = 0
    found = zkeys[pos] == rkeys
    same = found & (zsyn[pos] == rsyn)
    zkeys_noauto = zkeys[~autapse]
    in_ref = np.isin(zkeys_noauto, rkeys)
    say("== 2. Reference connection list vs official table ==")
    say(f"reference pairs:                      {len(rkeys):,}")
    say(f"  found in official table:            {int(found.sum()):,} "
        f"({pct(found.sum(), len(rkeys))})")
    say(f"  with identical synapse count:       {int(same.sum()):,} "
        f"({pct(same.sum(), len(rkeys))})")
    say(f"official pairs (no self-links) missing from reference: "
        f"{int((~in_ref).sum()):,} "
        f"({int(zsyn[~autapse][~in_ref].sum()):,} synapses)")
    say()

    # ---- the 616 neurons missing from the reference -----------------------
    missing = ~pidx.isin(ids)
    m_out, m_in = out_syn[missing], in_syn[missing]
    # synapses to/from other neurons only (self-links excluded)
    self_syn = np.zeros(NP)
    np.add.at(self_syn, zpre[autapse], zsyn[autapse])
    ext_total = (m_out + m_in - 2 * self_syn[missing])
    say("== 3. Neurons in FlyWire's list but not in the reference ==")
    say(f"count:                                {int(missing.sum())}")
    say(f"  with zero synapses to/from any other neuron: "
        f"{int((ext_total == 0).sum())}")
    say(f"  with only self-connections:         "
        f"{int(((ext_total == 0) & (self_syn[missing] > 0)).sum())}")
    say(f"  with some connections:              {int((ext_total > 0).sum())}"
        f" (max {int(ext_total.max())} synapses)")
    kept = ~missing
    kept_ext = out_syn[kept] + in_syn[kept] - 2 * self_syn[kept]
    say(f"reference neurons with zero connections: {int((kept_ext == 0).sum())}")
    ann = pd.read_csv(C.ANNOTATIONS_FILE, sep="\t",
                      usecols=["root_id", "super_class"])
    sc = ann.set_index("root_id")["super_class"].reindex(proof[missing])
    say(f"  super classes of the missing: "
        f"{sc.fillna('(no label)').value_counts().to_dict()}")
    say()

    # ---- re-derive the reference sign from FlyWire's NT predictions -------
    has_out = out_syn > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = nt_sum / out_syn[:, None]
    top = np.array(NT_NAMES)[np.argmax(frac, axis=1)]
    sign_top = np.where(np.isin(top, ["gaba", "glutamate"]), -1, 1)
    inhib_mass = frac[:, 1] + frac[:, 2]
    sign_mass = np.where(inhib_mass > 0.5, -1, 1)
    ref = pd.Series(brain.neurons["ref_sign"].to_numpy(), index=ids)
    ref_p = ref.reindex(proof).fillna(0).to_numpy()
    sel = has_out & (ref_p != 0)
    ours = pd.Series(brain.neurons["sign"].to_numpy(), index=ids
                     ).reindex(proof).fillna(0).to_numpy()
    say("== 4. Can the reference's +/- sign be re-derived? ==")
    say(f"neurons that send synapses (in both): {int(sel.sum()):,}")
    say("rule A, top NT averaged over the neuron's synapses (official table): "
        f"{pct((sign_top[sel] == ref_p[sel]).sum(), sel.sum())} agree")
    say("rule B, GABA+glutamate share of synapses > 50%:                      "
        f"{pct((sign_mass[sel] == ref_p[sel]).sum(), sel.sum())} agree")
    say("our loader (Schlegel et al. top_nt label):                           "
        f"{pct((ours[sel] == ref_p[sel]).sum(), sel.sum())} agree")
    say("rule A vs our loader:                                                "
        f"{pct((sign_top[sel] == ours[sel]).sum(), sel.sum())} agree")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
