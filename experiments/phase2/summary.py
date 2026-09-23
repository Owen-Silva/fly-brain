"""Phase 2 summary: what is in the fly brain wiring diagram we loaded.

Prints (and saves to experiments/phase2/summary.txt): load times, neuron /
connection / synapse counts compared with the published FlyWire numbers, the
most connected neurons, the neurotransmitter breakdown, and the sign
cross-check against the reference paper's own file.

Run:  .venv\\Scripts\\python.exe experiments\\phase2\\summary.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import connectome as C  # noqa: E402

OUT = Path(__file__).with_name("summary.txt")
lines: list[str] = []

# Published numbers, Dorkenwald et al. 2024 Nature 634:124 (release 783).
PUB_NEURONS = 139_255
PUB_SYNAPSES = "54.5 million"
PUB_CONN_GE5 = 2_700_513
PUB_NEURONS_GE5 = 134_181
# Shiu et al. 2024 Nature 634:210 (release 630).
PUB_NEURONS_630 = 127_400


def say(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def pct(a, b) -> str:
    return f"{100.0 * a / b:.1f}%"


def timed_loads(version: str):
    cold = C.load_connectome(version, rebuild=True)
    cold_s = cold.load_seconds
    del cold
    warm = C.load_connectome(version)
    t = time.perf_counter()
    warm.matrix("nt")
    return warm, cold_s, time.perf_counter() - t


def top_table(neu: pd.DataFrame, col: str, n: int = 10) -> None:
    top = neu.nlargest(n, col)
    say(f"  {'root_id':>18}  {col:>15}  {'cell_type':<14} {'super_class':<18} "
        "top_nt")
    for _, r in top.iterrows():
        say(f"  {r['root_id']:>18}  {r[col]:>15,}  "
            f"{str(r['cell_type']):<14} {str(r['super_class']):<18} "
            f"{r['top_nt']}")


def main() -> None:
    say("Phase 2 summary: FlyWire whole-brain connectome, as loaded by "
        "sim/connectome.py")
    say(f"(generated {time.strftime('%Y-%m-%d %H:%M')})")
    say()

    brain, cold_s, mat_s = timed_loads("783")
    neu, e = brain.neurons, brain.edges
    say("== Load speed (snapshot 783) ==")
    say(f"cold load (read source files, build, write cache): {cold_s:.1f} s")
    say(f"cached load (parquet cache in data/cache/):        "
        f"{brain.load_seconds:.2f} s")
    say(f"build sparse matrix (first call only):             {mat_s:.2f} s")
    say()

    n, m, s = brain.n_neurons, brain.n_connections, brain.n_synapses
    syn = e["syn_count"].to_numpy()
    ge5 = syn >= 5
    ge5_neurons = np.union1d(e["pre"].to_numpy()[ge5], e["post"].to_numpy()[ge5])
    say("== Size vs published FlyWire numbers (Dorkenwald et al. 2024) ==")
    say(f"{'':34}{'ours':>14}{'published':>14}")
    say(f"{'neurons':34}{n:>14,}{PUB_NEURONS:>14,}")
    say(f"{'synapses between neurons':34}{s:>14,}{PUB_SYNAPSES:>14}")
    say(f"{'connections (any synapse count)':34}{m:>14,}{'not stated':>14}")
    say(f"{'connections with >=5 synapses':34}{int(ge5.sum()):>14,}"
        f"{PUB_CONN_GE5:>14,}")
    say(f"{'neurons in those >=5 connections':34}{len(ge5_neurons):>14,}"
        f"{PUB_NEURONS_GE5:>14,}")
    say(f"missing neurons: {PUB_NEURONS - n} "
        f"({pct(PUB_NEURONS - n, PUB_NEURONS)}); see crosscheck_zenodo.txt: "
        "every one of them has zero synapses with any other neuron")
    say(f"synapses per connection: mean {syn.mean():.2f}, median "
        f"{np.median(syn):.0f}, max {syn.max():,}; "
        f"{pct((syn == 1).sum(), m)} of connections are a single synapse")
    say(f"no threshold in this file: smallest connection = {syn.min()} "
        "synapse")
    say()

    say("== Neuron lists: which source has which neurons ==")
    proof = np.load(C.ensure_proofread_ids()).astype(np.int64)
    ann_ids = pd.read_csv(C.ANNOTATIONS_FILE, sep="\t",
                          usecols=["root_id"])["root_id"].to_numpy()
    ref_ids = neu["root_id"].to_numpy()
    sets = {"reference (Shiu 783)": ref_ids, "FlyWire proofread list": proof,
            "annotations (Schlegel v3.1.0)": ann_ids}
    for name, arr in sets.items():
        say(f"  {name:<32}{len(arr):>9,}")
    names = list(sets)
    for a in names:
        for b in names:
            if a != b:
                k = len(np.setdiff1d(sets[a], sets[b]))
                say(f"  in {a}, not in {b}: {k}")
    say()

    say("== Most connected neurons (by synapse count) ==")
    say("Top 10 senders (total outgoing synapses):")
    top_table(neu, "out_synapses")
    say("Top 10 receivers (total incoming synapses):")
    top_table(neu, "in_synapses")
    say("Top 10 by number of distinct partners they send to:")
    top_table(neu, "n_post_partners")
    say("Top 10 by number of distinct partners they receive from:")
    top_table(neu, "n_pre_partners")
    say()

    say("== Neurotransmitter breakdown (predicted, Eckstein et al. 2024) ==")
    nt = neu["top_nt"].fillna("(none)")
    out_by_nt = neu.groupby(nt)["out_synapses"].sum()
    say(f"  {'neurotransmitter':<16}{'neurons':>9}{'share':>8}"
        f"{'out synapses':>15}{'share':>8}  sign used")
    for name, cnt in nt.value_counts().items():
        sign = C.nt_to_sign(None if name == "(none)" else name)
        say(f"  {name:<16}{cnt:>9,}{pct(cnt, n):>8}"
            f"{int(out_by_nt[name]):>15,}{pct(out_by_nt[name], s):>8}  "
            f"{'+1 excitatory' if sign > 0 else '-1 inhibitory'}")
    for label, col in (("our sign (from NT label)", "sign"),
                       ("reference file's sign", "ref_sign")):
        exc = e[col].to_numpy() > 0
        say(f"  {label}: excitatory {pct(exc.sum(), m)} of connections, "
            f"{pct(syn[exc].sum(), s)} of synapses; inhibitory "
            f"{pct((~exc).sum(), m)} / {pct(syn[~exc].sum(), s)}")
    say()

    say("== Sign cross-check: our NT-derived sign vs the reference file ==")
    senders = neu[neu["ref_sign"] != 0]
    agree = senders["sign"] == senders["ref_sign"]
    say(f"neurons that send synapses: {len(senders):,}; "
        f"signs agree for {agree.sum():,} ({pct(agree.sum(), len(senders))})")
    e_agree = e["sign"].to_numpy() == e["ref_sign"].to_numpy()
    say(f"connections agree: {pct(e_agree.sum(), m)}; "
        f"synapses agree: {pct(syn[e_agree].sum(), s)}")
    say("agreement by predicted neurotransmitter:")
    for name, g in senders.groupby(senders["top_nt"].fillna("(none)")):
        a = (g["sign"] == g["ref_sign"]).mean()
        say(f"  {name:<14} {len(g):>7,} neurons  {100 * a:.1f}% agree")
    say("agreement by prediction confidence (top_nt_conf):")
    bins = pd.cut(senders["top_nt_conf"], [0, .4, .5, .6, .7, .8, .9, 1.0])
    for b, g in senders.groupby(bins, observed=True):
        a = (g["sign"] == g["ref_sign"]).mean()
        say(f"  {str(b):<12} {len(g):>7,} neurons  {100 * a:.1f}% agree")
    dis = senders[~agree]
    say(f"disagreeing neurons by class: "
        f"{dis['super_class'].fillna('(none)').value_counts().head(6).to_dict()}")
    say()

    say("== Super classes (broad neuron categories) ==")
    for name, cnt in neu["super_class"].fillna("(no label)").value_counts(
            ).items():
        say(f"  {name:<20}{cnt:>8,}")
    say(f"neurons with a cell type label: "
        f"{neu['cell_type'].notna().sum():,} of {n:,}; "
        f"with a soma position: {neu['soma_x_nm'].notna().sum():,}; "
        f"with any 3D position: {neu['anchor_x_nm'].notna().sum():,}")
    del brain, neu, e
    say()

    b630, cold630, _ = timed_loads("630")
    s630 = b630.neurons[b630.neurons["ref_sign"] != 0]
    say("== Snapshot 630 (the one the Shiu et al. 2024 paper used) ==")
    say(f"neurons {b630.n_neurons:,} (paper: {PUB_NEURONS_630:,}), "
        f"connections {b630.n_connections:,}, synapses {b630.n_synapses:,}")
    say(f"labelled by the v1.1.0 (630) annotations: "
        f"{int(b630.neurons['in_annotations'].sum()):,}")
    say(f"sign agreement with the reference file: "
        f"{pct((s630['sign'] == s630['ref_sign']).sum(), len(s630))} of "
        f"{len(s630):,} sending neurons")
    say(f"cold load {cold630:.1f} s, cached load {b630.load_seconds:.2f} s")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
