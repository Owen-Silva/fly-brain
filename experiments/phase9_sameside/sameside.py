"""Same-side release switch (arm 1) and the "un-lopsided map" diagnostic (arm 2).

Plain English
-------------
In a real fly each smell receptor neuron (ORN) sends one axon branch to the
antennal lobe on its own side and one to the other side. Gaudry et al. 2013
found that a spike releases about 40% more transmitter from the same-side
branch. A wiring diagram counts synapses, so it cannot contain this, and the
model weights every synapse the same.

Variants (``VARIANTS``):

* ``off``      the old model exactly: ``sim.sign_fixes.build_brain(FIX)``.
* ``unit``     machinery check: every weight x1024 and the weight per synapse
               / 1024, with NO change. Must reproduce ``off`` spike for spike.
* ``release``  ARM 1, the realism upgrade: every same-side ORN -> PN
               connection x1.39.
               Source: Gaudry Q, Hong EJ, Kain J, de Bivort BL, Wilson RI
               (2013) "Asymmetric neurotransmitter release enables rapid
               odour lateralization in Drosophila", Nature 493:424-428,
               doi:10.1038/nature11747, PMC3590906. Fig. 3e: "ipsilateral
               sEPSCs were 39% larger than their contralateral counterparts"
               (n = 15 pairs of DM6 PNs, p < 0.05). Abstract: "each ORN spike
               releases ~40% more neurotransmitter from the axon branch
               ipsilateral to the soma".
* ``map``      ARM 2, DIAGNOSTIC ONLY (not a realism claim): ``release`` plus
               (a) same-side ORN -> PN x a further 1.30 (FlyWire's median
               same-side ratio 1.25 vs about 1.63 in BANC, maleCNS and the
               hemibrain, docs/banc-asymmetry.md), total x1.807; and (b) each
               glomerulus's left/right PN size imbalance removed: ORN -> PN
               input to its left PNs x 1/sqrt(rho), to its right PNs
               x sqrt(rho), rho = sqrt(LL*RL / (LR*RR)) from
               experiments/banc_asymmetry/results/flywire_630_glomerulus_map.csv.
* ``map_same_only`` / ``map_balance_only``: arm 2's two parts separately
               (brain-only screen only).

"Same side" uses the label table's ``side`` column for both the ORN (the
side its nerve enters) and the PN (cell body), as in docs/phase6-steering.md.
ORN = cell_class "olfactory" with an ``ORN_*`` hemibrain_type; PN = cell_class
"ALPN" (all of them, as Phase 6's exploratory ``al_ln_ipsi``). Every other
connection (ORN -> local neuron included) is unchanged.

Exact weights: the engine stores whole-number synapse counts. Every count is
multiplied by RES = 1024 before the factor is applied and rounded, and the
weight per synapse is divided by 1024 (the Poisson input kick w_syn x f_poi is
kept by multiplying f_poi by 1024). 1024 is a power of two, so an unchanged
connection gives bit-for-bit the same number as before; with factor 1.0 the
brain is the old one spike for spike (``unit``; checked by check_switch.py).
Factors are then applied in steps of 1/1024 of a synapse.

The old model stays runnable: ``build("off")`` is ``build_brain(FIX)``.
Nothing in sim/ is changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIX = "al_ln_literature"
RELEASE_FACTOR = 1.39          # Gaudry et al. 2013, Fig. 3e (39% larger same-side sEPSCs)
MAP_EXTRA = 1.30               # DIAGNOSTIC: 1.63 (other flies) / 1.25 (FlyWire 630), banc-asymmetry.md
RES = 1024                     # power of two -> exact arithmetic for unchanged connections
GLOM_MAP = ROOT / "experiments" / "banc_asymmetry" / "results" / "flywire_630_glomerulus_map.csv"
LABELS = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"

VARIANTS = {
    "off": None,
    "unit": dict(same=1.0, balance=False),
    "release": dict(same=RELEASE_FACTOR, balance=False),
    "map": dict(same=RELEASE_FACTOR * MAP_EXTRA, balance=True),
    "map_same_only": dict(same=RELEASE_FACTOR * MAP_EXTRA, balance=False),
    "map_balance_only": dict(same=RELEASE_FACTOR, balance=True),
}

DNAE007 = {"DNae007_L": 720575940609097429, "DNae007_R": 720575940614403178}


def labels(root_ids=None):
    lab = pd.read_parquet(LABELS, columns=["root_id", "super_class", "cell_class",
                                           "hemibrain_type", "side"])
    for c in ("super_class", "cell_class", "hemibrain_type", "side"):
        lab[c] = lab[c].astype(object).where(lab[c].notna(), "")
    if root_ids is not None:
        lab = lab.set_index("root_id").reindex(root_ids).fillna("").reset_index()
    return lab


def glomerulus_rho():
    """{glomerulus: (rho, w, LL, LR, RL, RR)} from the banc_asymmetry 630 table
    (uniglomerular PNs, docs/banc-asymmetry.md). Glomeruli with a zero count
    are left out (rho undefined)."""
    gm = pd.read_csv(GLOM_MAP)
    out = {}
    for _, r in gm.iterrows():
        LL, LR, RL, RR = (float(r.Lorn_to_Lpn), float(r.Lorn_to_Rpn),
                          float(r.Rorn_to_Lpn), float(r.Rorn_to_Rpn))
        if min(LL, LR, RL, RR) <= 0:
            continue
        out[str(r.glomerulus)] = (np.sqrt(LL * RL / (LR * RR)), np.sqrt(LL * RR / (LR * RL)),
                                  LL, LR, RL, RR)
    return out


def orn_pn_info(root_ids, pre, post, lab=None):
    """Masks for ORN -> PN connections: (is_orn_pn, same_side, pre_glom,
    post_side), all per connection."""
    lab = labels(root_ids) if lab is None else lab
    ht = lab.hemibrain_type.to_numpy(object)
    is_orn = ((lab.cell_class.to_numpy(object) == "olfactory")
              & np.array([str(h).startswith("ORN_") for h in ht]))
    is_pn = lab.cell_class.to_numpy(object) == "ALPN"
    side = lab.side.to_numpy(object)
    lr = np.isin(side, ["left", "right"])
    conn = is_orn[pre] & is_pn[post]
    same = conn & (side[pre] == side[post]) & lr[pre] & lr[post]
    glom = np.where(is_orn, np.array([str(h)[4:] for h in ht], object), "")
    return conn, same, glom, side


def factors(variant, root_ids, pre, post, lab=None):
    """Per-connection weight factor (float64 array) and a small report dict."""
    spec = VARIANTS[variant]
    f = np.ones(pre.size)
    conn, same, glom, side = orn_pn_info(root_ids, pre, post, lab)
    rep = {"variant": variant, "same_side_factor": spec["same"], "balance": spec["balance"],
           "orn_pn_connections": int(conn.sum()), "same_side_connections": int(same.sum())}
    f[same] *= spec["same"]
    if spec["balance"]:
        rho = glomerulus_rho()
        idx = np.flatnonzero(conn)
        g_of = glom[pre[idx]]
        pside = side[post[idx]]
        n_bal = 0
        for g, (r, *_rest) in rho.items():
            k = idx[g_of == g]
            left = side[post[k]] == "left"
            right = side[post[k]] == "right"
            f[k[left]] /= np.sqrt(r)
            f[k[right]] *= np.sqrt(r)
            n_bal += int(left.sum() + right.sum())
        del pside
        rep["balanced_glomeruli"] = len(rho)
        rep["balanced_connections"] = n_bal
    return f, rep


def modified_counts(variant, root_ids, pre, post, signed, lab=None):
    """Signed counts x RES x factor, rounded (int64), plus the report."""
    f, rep = factors(variant, root_ids, pre, post, lab)
    new = np.rint(signed.astype(np.float64) * RES * f).astype(np.int64)
    if np.abs(new).max() >= 2 ** 31:
        raise OverflowError("scaled counts do not fit in int32")
    conn, same, *_ = orn_pn_info(root_ids, pre, post, lab)
    rep["orn_pn_synapses_before"] = int(signed[conn].sum())
    rep["orn_pn_synapses_after"] = float(new[conn].sum() / RES)
    rep["same_side_synapses_before"] = int(signed[same].sum())
    rep["same_side_synapses_after"] = float(new[same].sum() / RES)
    changed = new != signed.astype(np.int64) * RES
    rep["connections_changed"] = int(changed.sum())
    rep["changed_outside_orn_pn"] = int((changed & ~conn).sum())
    return new, rep


def build(variant, n_threads=2, return_report=False):
    """A FastBrain for ``variant`` (see module docstring)."""
    from sim.fast_engine import FastBrain
    from sim.sign_fixes import apply_fix, build_brain, load_reference_arrays
    if VARIANTS[variant] is None:
        brain = build_brain(FIX, n_threads=n_threads)
        rep = {"variant": "off", "note": "sim.sign_fixes.build_brain(FIX), unchanged"}
        return (brain, rep) if return_report else brain
    root_ids, pre, post, signed = load_reference_arrays("630")
    pre, post, signed, _ = apply_fix(FIX, root_ids, pre, post, signed)
    new, rep = modified_counts(variant, root_ids, pre, post, signed)
    del signed
    from sim.fast_engine import DEFAULT_PARAMS
    params = {"w_syn": DEFAULT_PARAMS["w_syn"] / RES, "f_poi": DEFAULT_PARAMS["f_poi"] * RES}
    brain = FastBrain.from_arrays(root_ids, pre, post, new, params=params, n_threads=n_threads)
    del pre, post, new
    brain.snapshot = f"630+{FIX}+sameside:{variant}"
    brain.sign_fix = FIX
    brain.sameside_variant = variant
    return (brain, rep) if return_report else brain
