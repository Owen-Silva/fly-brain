"""Scorecard batch 1: score the saved runs with the pre-registered rules.

Plain English
-------------
Reads results/raw/<version>/*.npz (written by run_batch1.py), computes each test's
numbers per seed, applies the MATCH / PARTIAL / MISMATCH rules of
docs/real-fly-scorecard-batch1.md section 1 (unchanged), and writes
  results/measures.csv    every number used, one row per (version, test, measure, seed)
  results/scorecard.csv   one row per (test, version) with the verdict and key numbers
Missing runs are reported as "NOT RUN" rather than guessed.

Usage:  python experiments/scorecard_batch1/analyze.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
RAW = RES / "raw"
G = {k: [int(x) for x in v] for k, v in json.loads((RES / "groups.json").read_text()).items()}
CELLS = pd.read_csv(RES / "cells.csv")
UPN = pd.read_csv(RES / "upn_glomeruli.csv")
SEEDS = (0, 1, 2)
ACTIVE = [0, 1, 2]   # seeds used by the test being scored (set_active)
REST_MV = -52.0

ROWS = []          # measures


def rec(variant, test, measure, seed, value):
    ROWS.append(dict(variant=variant, test=test, measure=measure, seed=seed,
                     value=float(value) if value is not None else np.nan))


class Missing(Exception):
    pass


def seeds_of(variant, cond):
    return [k for k in SEEDS if (RAW / variant / f"{cond}_s{k}.npz").exists()]


def set_active(variant, conds):
    """Use the seeds that exist for ALL of a test's conditions (3, or 1 for the published
    model's runaway conditions under the one-seed time rule)."""
    global ACTIVE
    ks = sorted(set.intersection(*[set(seeds_of(variant, c)) for c in conds]))
    if not ks:
        raise Missing(f"{variant}: no seed common to {conds}")
    ACTIVE = ks
    return ks


_cache = {}


def load(variant, cond, k):
    key = (variant, cond, k)
    if key not in _cache:
        f = RAW / variant / f"{cond}_s{k}.npz"
        if not f.exists():
            raise Missing(f"{variant}/{cond}_s{k}")
        z = np.load(f)
        _cache[key] = {n: z[n] for n in z.files}
    return _cache[key]


def cell_rates(variant, cond, ids, seeds=None):
    """seeds x cells, Hz (spikes per 1 s trial, mean over 30 trials)."""
    out = []
    for k in (ACTIVE if seeds is None else seeds):
        z = load(variant, cond, k)
        pos = pd.Series(np.arange(z["key_ids"].size), index=z["key_ids"])
        out.append(z["key_trials"][pos.loc[ids].to_numpy()].mean(axis=1))
    return np.array(out)


def group_rate(variant, cond, group, seeds=None):
    return cell_rates(variant, cond, G[group], seeds).mean(axis=1)


def trial_counts(variant, cond, rid, k):
    z = load(variant, cond, k)
    pos = int(np.flatnonzero(z["key_ids"] == rid)[0])
    return z["key_trials"][pos].astype(float)


def v_depol(variant, cond, ids, seeds=None):
    """seeds x cells: mean membrane voltage above rest (mV), mean over trials."""
    out = []
    for k in (ACTIVE if seeds is None else seeds):
        z = load(variant, cond, k)
        pos = pd.Series(np.arange(z["rec_ids"].size), index=z["rec_ids"])
        out.append(z["v_mean"][pos.loc[ids].to_numpy()].mean(axis=1) - REST_MV)
    return np.array(out)


def runaway_frac(variant, cond, seeds=None):
    return float(np.mean([(load(variant, cond, k)["max_per_10ms"] > 1500).mean()
                          for k in (ACTIVE if seeds is None else seeds)]))


def counts_change(before, after, direction):
    """The pre-registered 'change counts' rule, per seed: > 20% and > 1 Hz, same
    direction in every seed. direction = -1 (drop) or +1 (rise)."""
    d = (after - before) * direction
    return bool(np.all((d > 1.0) & (d > 0.2 * np.abs(before))))


def fmt(a, nd=1):
    a = np.atleast_1d(a)
    return " / ".join(f"{x:.{nd}f}" for x in a)


def ids_of_type(group, types):
    c = CELLS[(CELLS.group == group) & (CELLS.hemibrain_type.isin(types))]
    return [int(x) for x in c.root_id]


# ---------------------------------------------------------------------------
def t1_fc2(v):
    set_active(v, ["FC2_SAG"])
    subs = {s: ids_of_type("FC2_read_pC1a" if s == "pC1a" else
                           "FC2_read_pC1b" if s == "pC1b" else "FC2_read_pC1cde", [s])
            for s in ("pC1a", "pC1b", "pC1c", "pC1d", "pC1e")}
    r = {s: cell_rates(v, "FC2_SAG", ids).mean(axis=1) for s, ids in subs.items()}
    dv = {s: v_depol(v, "FC2_SAG", ids).mean(axis=1) for s, ids in subs.items()}
    for s in subs:
        for k in ACTIVE:
            rec(v, "1 FC2", f"{s} rate Hz", k, r[s][k])
            rec(v, "1 FC2", f"{s} depol mV", k, dv[s][k])
    a = r["pC1a"]
    a_resp = bool(np.all(a >= 1.0))
    top = bool(all(np.all(a > r[s]) for s in ("pC1b", "pC1c", "pC1d", "pC1e")))
    ratio = bool(np.all(a >= 2.0 * r["pC1b"]))
    cde_low = bool(all(np.all(r[s] < 0.1 * a) for s in ("pC1c", "pC1d", "pC1e")))
    cde_r = np.max([r[s] for s in ("pC1c", "pC1d", "pC1e")], axis=0)
    cde_v = np.max([dv[s] for s in ("pC1c", "pC1d", "pC1e")], axis=0)
    b_gt = bool(np.all(np.where(r["pC1b"] >= 1.0, r["pC1b"] > cde_r, dv["pC1b"] > cde_v)))
    verdict = ("MATCH" if (a_resp and ratio and cde_low and b_gt) else
               "PARTIAL" if (a_resp and top) else "MISMATCH")
    num = (f"pC1a {fmt(a)} Hz; pC1b {fmt(r['pC1b'])}; pC1c {fmt(r['pC1c'])}; "
           f"pC1d {fmt(r['pC1d'])}; pC1e {fmt(r['pC1e'])} (per seed); "
           f"pC1a/pC1b = {fmt(a / np.maximum(r['pC1b'], 1e-9), 2)}; "
           f"mean voltage rise pC1a {dv['pC1a'].mean():.1f}, pC1b {dv['pC1b'].mean():.1f}, "
           f"pC1c-e max {cde_v.mean():.1f} mV")
    parts = dict(a_responds=a_resp, a_top=top, a_2x_b=ratio, cde_below_10pct=cde_low,
                 b_above_cde=b_gt)
    return verdict, num, parts


def t2_fc5(v):
    set_active(v, ["FC5_DA1_150", "FC5_DA1_50"])
    out = {}
    for cond in ("FC5_DA1_150", "FC5_DA1_50"):
        fr = {}
        for g, lab in (("FC5_read_aSPg", "aSP-g"), ("FC5_read_aSPf", "aSP-f"),
                       ("FC5_read_aSPh", "aSP-h")):
            cr = cell_rates(v, cond, G[g])                       # seeds x cells
            resp = np.all(cr >= 1.0, axis=0)
            fr[lab] = (resp.mean(), int(resp.sum()), resp.size, cr.mean())
            rec(v, "2 FC5", f"{cond} {lab} fraction responding", -1, resp.mean())
            rec(v, "2 FC5", f"{cond} {lab} mean rate Hz", -1, cr.mean())
        ra = runaway_frac(v, cond)
        rec(v, "2 FC5", f"{cond} runaway fraction", -1, ra)
        out[cond] = (fr, ra)
    fr, ra = out["FC5_DA1_150"]
    g, f, h = fr["aSP-g"][0], fr["aSP-f"][0], fr["aSP-h"][0]
    if g >= 0.5 and f <= 0.15 and h < g:
        verdict = "MATCH"
    elif f >= g:
        verdict = "MISMATCH"
    else:
        verdict = "PARTIAL"
    fr50, ra50 = out["FC5_DA1_50"]
    num = "; ".join(f"{k} {n}/{m} respond ({100 * x:.0f}%, mean {mr:.1f} Hz)"
                    for k, (x, n, m, mr) in fr.items())
    num += f"; runaway trials {100 * ra:.0f}%. At 50 Hz: " + "; ".join(
        f"{k} {n}/{m}" for k, (x, n, m, mr) in fr50.items()) + f", runaway {100 * ra50:.0f}%"
    if ra > 0.10:
        num += " [FLAG: >10% runaway at 150 Hz]"
    parts = dict(g_ge_50=g >= 0.5, f_le_15=f <= 0.15, h_lt_g=h < g, runaway_150=ra)
    return verdict, num, parts


def t3_fc1(v):
    set_active(v, ["FC1_A_vpoEN", "FC1_B_pC1", "FC1_C_both"])
    r = {c: group_rate(v, c, "FC1_read_vpoDN") for c in ("FC1_A_vpoEN", "FC1_B_pC1", "FC1_C_both")}
    for c, x in r.items():
        for k in ACTIVE:
            rec(v, "3 FC1", f"{c} vpoDN Hz", k, x[k])
    A, B, Cc = r["FC1_A_vpoEN"], r["FC1_B_pC1"], r["FC1_C_both"]
    ra, rb = bool(np.all(A >= 1)), bool(np.all(B >= 1))
    both = bool(np.all(Cc >= np.maximum(A, B)))
    verdict = ("MATCH" if (ra and rb and both) else
               "MISMATCH" if not (ra or rb) else "PARTIAL")
    num = f"vpoDN: vpoEN {fmt(A)} Hz; pC1 {fmt(B)}; both {fmt(Cc)}"
    return verdict, num, dict(vpoEN_excites=ra, pC1_excites=rb, both_highest=both)


def t4_sd4(v):
    dl, dr = G["SD4_read_DNa02"][1], G["SD4_read_DNa02"][0]   # prep order: right, left
    assert CELLS.set_index("root_id").side[dl] == "left" and CELLS.set_index("root_id").side[dr] == "right"
    a1 = {s: int(CELLS.set_index("root_id").loc[x].side == "left") for s, x in
          zip(("x", "y"), G["SD4_read_DNa01"])}
    d1l = [x for x in G["SD4_read_DNa01"] if CELLS.set_index("root_id").side[x] == "left"][0]
    d1r = [x for x in G["SD4_read_DNa01"] if CELLS.set_index("root_id").side[x] == "right"][0]
    set_active(v, ["SD4_PFL3_left", "SD4_PFL3_right"])
    res = {}
    for side, cond in (("left", "SD4_PFL3_left"), ("right", "SD4_PFL3_right")):
        tow, body, L, R = [], [], [], []
        for k in ACTIVE:
            l, r = trial_counts(v, cond, dl, k), trial_counts(v, cond, dr, k)
            s = (l - r) + 0.5 * (trial_counts(v, cond, d1l, k) - trial_counts(v, cond, d1r, k))
            t = (l > r) if side == "left" else (r > l)
            b = (s > 0) if side == "left" else (s < 0)
            tow.append(t)
            body.append(b)
            L.append(l.mean())
            R.append(r.mean())
            rec(v, "4 SD4", f"{side} stim: DNa02 L Hz", k, l.mean())
            rec(v, "4 SD4", f"{side} stim: DNa02 R Hz", k, r.mean())
            rec(v, "4 SD4", f"{side} stim: fraction toward", k, t.mean())
        tow = np.concatenate(tow)
        body = np.concatenate(body)
        res[side] = (tow.mean(), body.mean(), np.array(L), np.array(R))
    fl, fr = res["left"][0], res["right"][0]
    if fl >= 0.8 and fr >= 0.8:
        verdict = "MATCH"
    elif min(fl, fr) <= 0.5:
        verdict = "MISMATCH"
    elif max(fl, fr) >= 0.8:
        verdict = "PARTIAL"
    else:
        verdict = "PARTIAL"
    num = (f"left-ending PFL3: turn toward the stimulated side in {100 * fl:.0f}% of 90 trials "
           f"(DNa02 L {fmt(res['left'][2])} vs R {fmt(res['left'][3])} Hz); right-ending: "
           f"{100 * fr:.0f}% (DNa02 L {fmt(res['right'][2])} vs R {fmt(res['right'][3])} Hz); "
           f"body-loop signal incl. DNa01: {100 * res['left'][1]:.0f}% / {100 * res['right'][1]:.0f}%")
    return verdict, num, dict(frac_left=fl, frac_right=fr)


def t5_th3(v, mv="8mV"):
    T0, T1, T2 = (f"TH3_T{i}_{mv}" for i in range(3))
    set_active(v, [T0, T1, T2])
    vp0, vp1 = group_rate(v, T0, "TH3_read_VP3vPN"), group_rate(v, T1, "TH3_read_VP3vPN")
    d0, d1, d2 = (group_rate(v, c, "TH3_read_DN1a") for c in (T0, T1, T2))
    for k in ACTIVE:
        rec(v, "5 TH3", f"{mv} VP3+_vPN T0 Hz", k, vp0[k])
        rec(v, "5 TH3", f"{mv} VP3+_vPN T1 Hz", k, vp1[k])
        for nm, x in (("T0", d0), ("T1", d1), ("T2", d2)):
            rec(v, "5 TH3", f"{mv} DN1a {nm} Hz", k, x[k])
    a = bool(np.all(vp1 - vp0 >= 1.0))
    b = counts_change(d0, d1, -1)
    c = bool(np.all((d0 - d2) < 0.5 * (d0 - d1)))
    same_dir = bool(np.all(d1 < d0))
    verdict = ("MATCH" if (a and b and c) else
               "PARTIAL" if ((a and b) or same_dir) else "MISMATCH")
    num = (f"[{mv}] VP3+_vPN {fmt(vp0)} -> {fmt(vp1)} Hz with cool; DN1a {fmt(d0)} (background) "
           f"-> {fmt(d1)} (cool) -> {fmt(d2)} (cool, VP3+_vPN silenced)")
    return verdict, num, dict(vPN_responds=a, DN1a_drop_counts=b, drop_gone_when_silenced=c)


def t6_th2(v):
    set_active(v, ["TH2_W", "TH2_WC", "TH1_C"])
    w, wc = group_rate(v, "TH2_W", "TH2_read_VP2PN"), group_rate(v, "TH2_WC", "TH2_read_VP2PN")
    c = group_rate(v, "TH1_C", "TH1_read_VP3PN")
    cl = cell_rates(v, "TH1_C", G["TH1_read_VP3PN"]).mean(axis=0)
    for k in ACTIVE:
        rec(v, "6 TH2", "warm PNs W Hz", k, w[k])
        rec(v, "6 TH2", "warm PNs W+C Hz", k, wc[k])
        rec(v, "6 TH2", "cool PNs C Hz", k, c[k])
    a = counts_change(w, wc, -1)
    b = bool(np.all(c >= 1.0))
    fall = bool(np.all(wc < w))
    if a and b:
        verdict = "MATCH"
    elif (b and fall) or (a and not b):
        verdict = "PARTIAL"
    else:
        verdict = "MISMATCH"
    per_type = []
    for t in ("VP2_adPN", "VP2+_adPN", "VP2_l2PN"):
        ids = ids_of_type("TH2_read_VP2PN", [t])
        x0 = cell_rates(v, "TH2_W", ids).mean()
        x1 = cell_rates(v, "TH2_WC", ids).mean()
        per_type.append(f"{t} {x0:.1f}->{x1:.1f}")
    num = (f"warm PNs {fmt(w)} Hz (warm) -> {fmt(wc)} (warm + cool) [{', '.join(per_type)}]; "
           f"cool PNs to cool alone {fmt(c)} Hz ({int((cl >= 1).sum())} of {cl.size} cells >= 1 Hz)")
    return verdict, num, dict(warm_drop_counts=a, cool_PNs_respond=b, warm_falls_every_seed=fall)


def os4_corr(v, cond, k, bin_steps=50):
    z = load(v, cond, k)
    n_trials = 30
    nb = 10000 // bin_steps
    M = np.zeros((len(UPN), n_trials * nb), np.float32)
    col = z["pn_col"].astype(np.int64)
    b = z["pn_trial"].astype(np.int64) * nb + z["pn_step"].astype(np.int64) // bin_steps
    np.add.at(M, (col, b), 1.0)
    rate = M.sum(axis=1) / n_trials            # spikes per 1 s trial = Hz
    ok = rate >= 1.0
    with np.errstate(invalid="ignore", divide="ignore"):
        C = np.corrcoef(M)
    lpn = (UPN.hemibrain_type == "DA1_lPN").to_numpy()
    side = UPN.side.to_numpy()
    glom = UPN.glomerulus.to_numpy()
    sis, cross, dropped_s, dropped_c = [], [], 0, 0
    for i in np.flatnonzero(lpn):
        for j in np.flatnonzero(lpn):
            if j <= i or side[j] != side[i]:
                continue
            if ok[i] and ok[j]:
                sis.append(C[i, j])
            else:
                dropped_s += 1
        for j in np.flatnonzero((glom != "DA1") & (side == side[i])):
            if ok[i] and ok[j]:
                cross.append(C[i, j])
            else:
                dropped_c += 1
    da1_rate = rate[lpn].mean()
    return (np.median(sis) if sis else np.nan, np.median(cross) if cross else np.nan,
            len(sis), dropped_s, len(cross), dropped_c, da1_rate, rate[~(glom == "DA1")].mean())


def t7_os4(v, gap=False, s_cond="OS4_S", o_cond="OS4_O", test="7 OS4"):
    sfx = "_gap" if gap else ""
    lab = v + ("+gap" if gap else "")
    set_active(v, [s_cond + sfx, o_cond + sfx])
    S = [os4_corr(v, s_cond + sfx, k) for k in ACTIVE]
    O = [os4_corr(v, o_cond + sfx, k) for k in ACTIVE]
    sS, cS = np.array([x[0] for x in S]), np.array([x[1] for x in S])
    sO, cO = np.array([x[0] for x in O]), np.array([x[1] for x in O])
    for k in ACTIVE:
        rec(lab, test, "S sister median r", k, sS[k])
        rec(lab, test, "S cross median r", k, cS[k])
        rec(lab, test, "O sister median r", k, sO[k])
        rec(lab, test, "O cross median r", k, cO[k])
        rec(lab, test, "S DA1 lPN rate Hz", k, S[k][6])
        rec(lab, test, "S other uPN rate Hz", k, S[k][7])
        rec(lab, test, "O DA1 lPN rate Hz", k, O[k][6])
    ra = runaway_frac(v, s_cond + sfx), runaway_frac(v, o_cond + sfx)
    a = bool(np.all((sS >= 3 * cS) & (sS - cS >= 0.1)))
    b = bool(np.all(sO > 1.2 * sS))
    # Section 1.1: pairs with a cell under 1 Hz are left out; if no sister or no cross
    # pair is left in the spontaneous condition, the precondition fails.
    no_pairs = any(x[2] == 0 or x[4] == 0 for x in S)
    verdict = ("CAN'T TELL" if no_pairs else
               "MATCH" if (a and b) else "PARTIAL" if a else "MISMATCH")
    num = (f"sister r {fmt(sS, 2)} vs cross r {fmt(cS, 2)} (spontaneous); sister r with DA1 "
           f"odour {fmt(sO, 2)}; pairs used: {S[0][2]} sister (dropped {S[0][3]}), {S[0][4]} "
           f"cross (dropped {S[0][5]}); DA1 lPN rate {np.mean([x[6] for x in S]):.1f} Hz "
           f"spont., {np.mean([x[6] for x in O]):.1f} Hz odour; runaway {100 * ra[0]:.0f}% / "
           f"{100 * ra[1]:.0f}%")
    return verdict, num, dict(sister_3x_cross=a, odour_raises_sync=b, runaway=ra)


def t8_ll1(v):
    set_active(v, ["LL1_O", "LL1_OM"])
    m0 = cell_rates(v, "LL1_O", G["LL1_read_MBON01"] + G["LL1_read_MBON02"]
                    + G["LL1_read_MBON0304"]).mean(axis=1)
    m1 = cell_rates(v, "LL1_OM", G["LL1_read_MBON01"] + G["LL1_read_MBON02"]
                    + G["LL1_read_MBON0304"]).mean(axis=1)
    v0 = cell_rates(v, "LL1_O", G["LL1_read_MBON18"] + G["LL1_read_MBON1617"]).mean(axis=1)
    v1 = cell_rates(v, "LL1_OM", G["LL1_read_MBON18"] + G["LL1_read_MBON1617"]).mean(axis=1)
    for k in ACTIVE:
        rec(v, "8 LL1", "M4/6 odour Hz", k, m0[k])
        rec(v, "8 LL1", "M4/6 odour+MVP2 Hz", k, m1[k])
        rec(v, "8 LL1", "V2 odour Hz", k, v0[k])
        rec(v, "8 LL1", "V2 odour+MVP2 Hz", k, v1[k])
    pre = bool(np.all(m0 >= 1.0))
    mdrop = counts_change(m0, m1, -1)
    v_resp = bool(np.all(v0 >= 1.0))
    v_changed = counts_change(v0, v1, -1) or counts_change(v0, v1, +1)
    if not pre:
        verdict = "CAN'T TELL"
    elif mdrop and v_resp and not v_changed:
        verdict = "MATCH"
    elif mdrop:
        verdict = "PARTIAL"
    else:
        verdict = "MISMATCH"
    per = []
    for g in ("LL1_read_MBON01", "LL1_read_MBON02", "LL1_read_MBON0304", "LL1_read_MBON18",
              "LL1_read_MBON1617"):
        a0 = cell_rates(v, "LL1_O", G[g]).mean()
        a1 = cell_rates(v, "LL1_OM", G[g]).mean()
        per.append(f"{g.split('_')[-1]} {a0:.1f}->{a1:.1f}")
    num = (f"M4/6 {fmt(m0)} -> {fmt(m1)} Hz with MVP2; V2 {fmt(v0)} -> {fmt(v1)} "
           f"[{', '.join(per)}]; runaway {100 * runaway_frac(v, 'LL1_O'):.0f}%")
    return verdict, num, dict(M46_respond=pre, M46_drop_counts=mdrop, V2_responds=v_resp,
                              V2_change_counts=v_changed)


def t9_sd1(v):
    set_active(v, ["SD1_LC16_both_100", "SD1_LC16_both_50", "SD2_LC16_left_100",
                   "SD2_LC16_right_100"])
    mdn = G["SD1_read_MDN"]
    ml = [x for x in mdn if CELLS.set_index("root_id").side[x] == "left"]
    mr = [x for x in mdn if CELLS.set_index("root_id").side[x] == "right"]
    b100 = cell_rates(v, "SD1_LC16_both_100", mdn).mean(axis=1)
    b50 = cell_rates(v, "SD1_LC16_both_50", mdn).mean(axis=1)
    out = {}
    for s, c in (("left", "SD2_LC16_left_100"), ("right", "SD2_LC16_right_100")):
        out[s] = (cell_rates(v, c, ml).mean(axis=1), cell_rates(v, c, mr).mean(axis=1))
    for k in ACTIVE:
        rec(v, "9 SD1", "MDN both-sided LC16 100 Hz", k, b100[k])
        rec(v, "9 SD1", "MDN both-sided LC16 50 Hz", k, b50[k])
        for s in out:
            rec(v, "9 SD1", f"{s} LC16: MDN left Hz", k, out[s][0][k])
            rec(v, "9 SD1", f"{s} LC16: MDN right Hz", k, out[s][1][k])
    responds = bool(np.all(b100 >= 1.0))

    def differ(l, r):
        big, small = np.maximum(l, r), np.minimum(l, r)
        return bool(np.all((big - small > 1.0) & (big > 1.2 * small)))
    d_l = differ(*out["left"])
    d_r = differ(*out["right"])
    sgn_l = np.sign(out["left"][0] - out["left"][1])
    sgn_r = np.sign(out["right"][0] - out["right"][1])
    flips = bool(np.all(sgn_l * sgn_r < 0))
    one_sided = d_l and d_r and flips
    verdict = ("MATCH" if (responds and one_sided) else
               "MISMATCH" if not responds else "PARTIAL")
    num = (f"MDN {fmt(b100)} Hz (both-sided LC16, 100 Hz), {fmt(b50)} (50 Hz); left LC16: MDN "
           f"L {fmt(out['left'][0])} vs R {fmt(out['left'][1])}; right LC16: L "
           f"{fmt(out['right'][0])} vs R {fmt(out['right'][1])}")
    return verdict, num, dict(MDN_respond=responds, one_sided_differ_and_flip=one_sided)


def t10_tf4(v):
    set_active(v, ["TF4_water", "TF4_sugar"])
    r = {}
    for c in ("TF4_water", "TF4_sugar"):
        for g in ("Usnea", "Phantom", "Clavicle", "Fdg"):
            x = cell_rates(v, c, G[f"TF4_read_{g}"])            # seeds x 2 (right, left)
            r[(c, g)] = x.mean(axis=1)
            for k in ACTIVE:
                rec(v, "10 TF4", f"{g} {c.split('_')[1]} Hz", k, x[k].mean())
    W = {g: r[("TF4_water", g)] for g in ("Usnea", "Phantom", "Clavicle", "Fdg")}
    S = {g: r[("TF4_sugar", g)] for g in ("Usnea", "Phantom", "Clavicle", "Fdg")}
    us = bool(np.all((W["Usnea"] >= 1.0) & ((S["Usnea"] < 0.2 * W["Usnea"]) | (S["Usnea"] < 1.0))))
    ratio = S["Phantom"] / np.maximum(W["Phantom"], 1e-9)
    ph = bool(np.all((W["Phantom"] >= 1) & (S["Phantom"] >= 1) & (ratio >= 0.5) & (ratio <= 2)))
    cl = bool(np.all(S["Clavicle"] >= 1.0)) and counts_change(W["Clavicle"], S["Clavicle"], +1)
    n_ok = us + ph + cl
    verdict = "MATCH" if n_ok == 3 else "PARTIAL" if n_ok == 2 else "MISMATCH"
    num = "; ".join(f"{g} water {fmt(W[g])} / sugar {fmt(S[g])} Hz" for g in W)
    return verdict, num, dict(Usnea_ok=us, Phantom_ok=ph, Clavicle_ok=cl)


TESTS = [("1 FC2", t1_fc2), ("2 FC5", t2_fc5), ("3 FC1", t3_fc1), ("4 SD4", t4_sd4),
         ("5 TH3", t5_th3), ("6 TH2", t6_th2), ("7 OS4", t7_os4), ("8 LL1", t8_ll1),
         ("9 SD1", t9_sd1), ("10 TF4", t10_tf4)]


def main():
    out = []
    variants = [p.name for p in sorted(RAW.iterdir()) if p.is_dir()] if RAW.exists() else []
    for v in ("none", "al_ln_literature"):
        if v not in variants:
            continue
        try:
            z = load(v, "silent", 0)
            rec(v, "0 control", "spikes with no input", 0, z["per_trial_total"].sum())
        except Missing:
            pass
        jobs = list(TESTS) + [("5 TH3 (10 mV check)", lambda vv: t5_th3(vv, "10mV"))]
        if v == "al_ln_literature":
            jobs.append(("7 OS4 (+gap)", lambda vv: t7_os4(vv, gap=True)))
            # POST-HOC, NOT SCORED: 30 Hz spontaneous input (see run_batch1.py)
            jobs.append(("7 OS4 post-hoc 30 Hz", lambda vv: t7_os4(
                vv, s_cond="OS4post_S30", o_cond="OS4post_O30", test="7 OS4 post-hoc")))
            jobs.append(("7 OS4 post-hoc 30 Hz (+gap)", lambda vv: t7_os4(
                vv, gap=True, s_cond="OS4post_S30", o_cond="OS4post_O30", test="7 OS4 post-hoc")))
        for name, fn in jobs:
            try:
                verdict, num, parts = fn(v)
            except Missing as e:
                verdict, num, parts = "NOT RUN", f"missing {e}", {}
            out.append(dict(test=name, variant=v + ("+gap" if "gap" in name else ""),
                            verdict=verdict, n_seeds=len(ACTIVE) if verdict != "NOT RUN" else 0,
                            numbers=num,
                            parts=json.dumps(parts, default=lambda x: bool(x) if isinstance(
                                x, np.bool_) else float(x))))
    # demonstration: Poisson background into DN1a
    try:
        d0 = group_rate("none", "TH3_demo_poisson_T0", "TH3_read_DN1a", seeds=[0])
        d1 = group_rate("none", "TH3_demo_poisson_T1", "TH3_read_DN1a", seeds=[0])
        rec("none", "5 TH3", "demo Poisson-driven DN1a T0 Hz", 0, d0[0])
        rec("none", "5 TH3", "demo Poisson-driven DN1a T1 Hz", 0, d1[0])
    except Missing:
        pass
    sc = pd.DataFrame(out)
    sc.to_csv(RES / "scorecard.csv", index=False)
    pd.DataFrame(ROWS).to_csv(RES / "measures.csv", index=False)
    for r in sc.itertuples():
        print(f"{r.test:22s} {r.variant:22s} {r.verdict:10s} [{r.n_seeds} seeds] {r.numbers}")


if __name__ == "__main__":
    sys.exit(main())
