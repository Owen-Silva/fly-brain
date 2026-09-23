"""Analyse the saved olfaction runs (no simulation; no brain needed).

Plain English
-------------
1. Region map: for each odor channel (DM1 = vinegar/esters, DA2 = geosmin),
   how many neurons fire in each brain area and how fast.
2. Top responders (excluding the stimulated ORNs), with their labels.
3. Left/right test for Phase 9: for every steering/walking descending
   neuron, its rate when only the LEFT ORNs are driven versus only the RIGHT
   ORNs: per seed, over the whole 1 s trial AND over the first 100 ms, with
   a Welch t-test across the 30 trials. Plus a scan of all 1,299 descending
   neurons.
4. Projection neurons (PNs) in the first 100 ms: does the PN on the same
   side as the stimulated ORNs fire earlier / more than the opposite one?
   Real flies: ipsilateral PNs fire a few ms earlier and 30-50% faster
   (Gaudry et al. 2013, Nature).

Usage: analyze_olfaction.py [rate_hz] [variant]   (defaults: 150, baseline)
variant "lnfix" = the exploratory run where 53 antennal-lobe local neurons are
made inhibitory (see run_olfaction.py); its outputs get "_lnfix" in the name.
Output: results/*.csv listed below and PNG plots in this folder.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "competition"))
sys.path.insert(0, str(HERE))
from phase5_common import labels  # noqa: E402
from steering_ids import STEERING  # noqa: E402

RES = HERE / "results"
RATE = int(sys.argv[1]) if len(sys.argv) > 1 else 150
VARIANT = sys.argv[2] if len(sys.argv) > 2 else "baseline"
SUFFIX = "" if VARIANT == "baseline" else f"_{VARIANT}"
TITLE_NOTE = {"baseline": "", "lnfix": " [LN-sign-corrected variant]",
              "short": " [published model, 300 ms trials]"}.get(VARIANT, f" [{VARIANT}]")
SEEDS = (0, 1, 2)
ODORS = ("DM1", "DA2")
lab = labels()
dn_ids = np.load(RES / "dn_ids.npy")
dn_col = {int(r): k for k, r in enumerate(dn_ids)}
pn_ids = np.load(RES / "pn_ids.npy")

INK, INK2, MUTED, SURF = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "text.color": INK, "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1",
                     "grid.linewidth": 0.6})


def f(odor, side, seed, kind):
    return RES / f"olf_{odor}_{side}_{RATE}Hz_seed{seed}{SUFFIX}_{kind}.npy"


def load(odor, side, seed, kind):
    p = f(odor, side, seed, kind)
    return np.load(p).astype(float) if p.exists() else None


def seeds_for(odor, side, kind="rates"):
    return [s for s in SEEDS if f(odor, side, s, kind).exists()]


# ---- 1. region map -------------------------------------------------------
ht, cc, sc = lab.hemibrain_type, lab.cell_class, lab.super_class
is_orn = ht.str.startswith("ORN_")


def group_masks(odor):
    same_pn = (cc == "ALPN") & ht.str.startswith(f"{odor}_")
    g = {
        "ORNs of this type (driven)": is_orn & (ht == f"ORN_{odor}"),
        "ORNs, other types": is_orn & (ht != f"ORN_{odor}"),
        "PNs of this glomerulus": same_pn,
        "PNs, other uniglomerular": (cc == "ALPN") & (lab.cell_sub_class == "uniglomerular") & ~same_pn,
        "PNs, multiglomerular": (cc == "ALPN") & (lab.cell_sub_class != "uniglomerular"),
        "AL local neurons": cc == "ALLN",
        "Lateral horn neurons (LHLN or LH* type)": (cc == "LHLN") | (ht.str.startswith("LH") & (cc != "LHCENT")),
        "Lateral horn centrifugal": cc == "LHCENT",
        "Kenyon cells": cc == "Kenyon_Cell",
        "MBONs": cc == "MBON",
        "DANs": cc == "DAN",
        "APL": (lab.cell_type == "APL") | (ht == "APL"),
        "Descending neurons": sc == "descending",
    }
    used = np.zeros(len(lab), bool)
    for m in g.values():
        used |= m.to_numpy()
    g["Everything else"] = pd.Series(~used)
    return {k: np.asarray(m, bool) for k, m in g.items()}


rows = []
for odor in ODORS:
    masks = group_masks(odor)
    for side in ("both", "left", "right"):
        ss = seeds_for(odor, side)
        if not ss:
            continue
        r = np.mean([load(odor, side, s, "rates") for s in ss], axis=0)
        for gname, m in masks.items():
            for hemi in ("left", "right"):
                mm = m & (lab.side == hemi).to_numpy()
                on = r[mm] > 0.5
                rows.append(dict(odor=odor, stim_side=side, n_seeds=len(ss), group=gname,
                                 hemisphere=hemi, n_in_group=int(mm.sum()), n_active=int(on.sum()),
                                 pct_active=round(100 * on.mean(), 1) if mm.any() else 0.0,
                                 mean_rate_active=round(float(r[mm][on].mean()), 1) if on.any() else 0.0))
region = pd.DataFrame(rows)
region.to_csv(RES / f"region_map{SUFFIX}.csv", index=False)

# plot: % of each group active, DM1 vs DA2, both sides driven
fig, ax = plt.subplots(figsize=(9, 4.6))
reg = region[region.stim_side == "both"].groupby(["odor", "group"]).agg(
    n_active=("n_active", "sum"), n=("n_in_group", "sum")).reset_index()
order = list(group_masks("DM1"))
y = np.arange(len(order))
for k, odor in enumerate(ODORS):
    d = reg[reg.odor == odor].set_index("group").reindex(order)
    pct = 100 * d.n_active / d.n.replace(0, np.nan)
    ax.barh(y + (k - 0.5) * 0.38, pct, height=0.34, color=SERIES[k],
            label=f"{odor} ORNs driven ({'vinegar' if odor == 'DM1' else 'geosmin'})")
ax.set_yticks(y, order)
ax.invert_yaxis()
ax.set_xlabel("% of the group firing (both antennae, 150 Hz, mean of seeds)")
ax.set_title("Share of each area firing when one smell channel is driven" + TITLE_NOTE,
             loc="left", fontsize=11)
ax.legend(frameon=False, fontsize=8, loc="lower right")
fig.tight_layout()
fig.savefig(HERE / f"region_map{SUFFIX}.png", dpi=150)
plt.close(fig)

# ---- 2. top responders ---------------------------------------------------
tops = []
for odor in ODORS:
    ss = seeds_for(odor, "both")
    if not ss:
        continue
    r = np.mean([load(odor, "both", s, "rates") for s in ss], axis=0)
    r[(is_orn & (ht == f"ORN_{odor}")).to_numpy()] = 0
    for i in np.argsort(-r)[:30]:
        L = lab.iloc[i]
        tops.append(dict(odor=odor, root_id=int(L.root_id), rate_hz=round(float(r[i]), 1),
                         super_class=L.super_class, cell_class=L.cell_class, cell_type=L.cell_type,
                         hemibrain_type=L.hemibrain_type, side=L.side, top_nt=L.top_nt))
pd.DataFrame(tops).to_csv(RES / f"top_responders{SUFFIX}.csv", index=False)


# ---- 3. steering DNs, left-only vs right-only ----------------------------
def welch(a, b):
    if a.std() + b.std() == 0:
        return np.nan if a.mean() == b.mean() else 0.0
    return stats.ttest_ind(a, b, equal_var=False).pvalue


lr = []
for odor in ODORS:
    for s in SEEDS:
        A, B = load(odor, "left", s, "dn_trials"), load(odor, "right", s, "dn_trials")
        EA, EB = load(odor, "left", s, "dn_early"), load(odor, "right", s, "dn_early")
        if A is None or B is None:
            continue
        for name, rid in STEERING.items():
            k = dn_col[int(rid)]
            row = dict(odor=odor, neuron=name, seed=s,
                       leftstim_hz=A[:, k].mean(), leftstim_sd=A[:, k].std(),
                       rightstim_hz=B[:, k].mean(), rightstim_sd=B[:, k].std(),
                       p_welch_1s=welch(A[:, k], B[:, k]))
            if EA is not None:
                ea, eb = EA[:, :, k].sum(1) * 10, EB[:, :, k].sum(1) * 10   # Hz over 0-100 ms
                row.update(leftstim_hz_0_100ms=ea.mean(), rightstim_hz_0_100ms=eb.mean(),
                           p_welch_0_100ms=welch(ea, eb))
            lr.append(row)
lr = pd.DataFrame(lr)
lr.to_csv(RES / f"steering_lr{SUFFIX}.csv", index=False)

# per-pair turn signal (left DN minus right DN), per trial
turn = []
for odor in ODORS:
    for pair in ("DNa02", "DNa01", "DNa03", "DNp09", "DNg100"):
        kl, kr = dn_col[STEERING[f"{pair}_L"]], dn_col[STEERING[f"{pair}_R"]]
        for s in SEEDS:
            for side in ("left", "right"):
                t = load(odor, side, s, "dn_trials")
                e = load(odor, side, s, "dn_early")
                if t is None:
                    continue
                d = t[:, kl] - t[:, kr]
                row = dict(odor=odor, pair=pair, seed=s, stim_side=side,
                           L_hz=t[:, kl].mean(), R_hz=t[:, kr].mean(),
                           L_minus_R=d.mean(), L_minus_R_sd=d.std())
                if e is not None:
                    de = (e[:, :, kl] - e[:, :, kr]).sum(1) * 10
                    row.update(L_minus_R_0_100ms=de.mean(), L_minus_R_0_100ms_sd=de.std())
                turn.append(row)
turn = pd.DataFrame(turn)
turn.to_csv(RES / f"steering_turn_signal{SUFFIX}.csv", index=False)

# plot: steering DN rates, left-stim vs right-stim (mean of seeds, error = sd across seeds)
if not lr.empty:
    names = [n for n in STEERING if n.startswith(("DNa02", "DNa01", "DNa03", "DNg100", "DNp09"))]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, odor in zip(axes, ODORS):
        d = lr[lr.odor == odor].groupby("neuron").agg(
            L=("leftstim_hz", "mean"), Lsd=("leftstim_hz", "std"),
            R=("rightstim_hz", "mean"), Rsd=("rightstim_hz", "std")).reindex(names)
        x = np.arange(len(names))
        ax.bar(x - 0.2, d.L, 0.36, yerr=d.Lsd, color=SERIES[0], label="left ORNs driven",
               error_kw=dict(ecolor=INK2, lw=1))
        ax.bar(x + 0.2, d.R, 0.36, yerr=d.Rsd, color=SERIES[1], label="right ORNs driven",
               error_kw=dict(ecolor=INK2, lw=1))
        ax.set_xticks(x, [n.replace("_", " ") for n in names], rotation=45, ha="right", fontsize=8)
        ax.set_title(f"{odor} ORNs ({'vinegar' if odor == 'DM1' else 'geosmin'})",
                     loc="left", fontsize=10)
        ax.legend(frameon=False, fontsize=8)
    axes[0].set_ylabel("Firing rate over the trial (Hz)")
    fig.suptitle(f"Steering / walking descending neurons, one side's ORNs driven at {RATE} Hz"
                 f"{TITLE_NOTE}\nmean of 3 seeds x 30 trials; error bars = seed-to-seed sd",
                 x=0.01, ha="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(HERE / f"steering_lr{SUFFIX}.png", dpi=150)
    plt.close(fig)

# ---- scan all DNs (whole trial and first 100 ms) --------------------------
scan = []
dn_lab = lab.set_index("root_id").loc[dn_ids]
for odor in ODORS:
    A = [load(odor, "left", s, "dn_trials") for s in SEEDS]
    B = [load(odor, "right", s, "dn_trials") for s in SEEDS]
    if any(a is None for a in A + B):
        continue
    A, B = np.stack(A), np.stack(B)
    for k in np.flatnonzero((A.mean((0, 1)) > 0.5) | (B.mean((0, 1)) > 0.5)):
        d = A[:, :, k].mean(1) - B[:, :, k].mean(1)
        ps = [welch(A[s, :, k], B[s, :, k]) for s in range(len(SEEDS))]
        scan.append(dict(odor=odor, root_id=int(dn_ids[k]), cell_type=dn_lab.cell_type.iloc[k],
                         hemibrain_type=dn_lab.hemibrain_type.iloc[k], side=dn_lab.side.iloc[k],
                         leftstim_hz=A[:, :, k].mean(), rightstim_hz=B[:, :, k].mean(),
                         diff_s0=d[0], diff_s1=d[1], diff_s2=d[2],
                         consistent_sign=bool(d[0] != 0 and np.all(np.sign(d) == np.sign(d[0]))),
                         max_p_over_seeds=np.nanmax(ps) if not np.all(np.isnan(ps)) else np.nan))
scan = pd.DataFrame(scan)
scan.to_csv(RES / f"dn_lr_scan{SUFFIX}.csv", index=False)

# ---- 4. PNs in the first 100 ms: ipsilateral vs contralateral ------------
pn_rows = []
pn_lab = lab.set_index("root_id").loc[pn_ids]
for odor in ODORS:
    for s in SEEDS:
        for side in ("left", "right"):
            e = load(odor, side, s, "pn_early")
            if e is None:
                continue
            for hemi in ("left", "right"):
                for which, m in (("this glomerulus", pn_lab.hemibrain_type.str.startswith(f"{odor}_")),
                                 ("all PNs", pd.Series(True, index=pn_lab.index))):
                    cols = np.flatnonzero((m & (pn_lab.side == hemi)).to_numpy())
                    if cols.size == 0:
                        continue
                    c = e[:, :, cols]                          # trials x bins x PNs
                    first_bin = [np.flatnonzero(c[t].sum(1) > 0)[:1] for t in range(c.shape[0])]
                    fb = np.array([b[0] * 10 if b.size else np.nan for b in first_bin], float)
                    pn_rows.append(dict(odor=odor, seed=s, stim_side=side, pn_side=hemi,
                                        ipsi=(hemi == side), pn_group=which, n_pns=cols.size,
                                        hz_0_20ms=c[:, :2].sum((1, 2)).mean() / cols.size * 50,
                                        hz_0_100ms=c.sum((1, 2)).mean() / cols.size * 10,
                                        first_spike_bin_ms=np.nanmean(fb)))
pn = pd.DataFrame(pn_rows)
pn.to_csv(RES / f"pn_ipsi_contra{SUFFIX}.csv", index=False)
print("analysis files written;", len(lr), "steering rows,", len(scan), "active DNs scanned,",
      len(pn), "PN rows")
