"""Step 4: score the model against the pre-registered real-fly facts
(results/preregistration.md). Reads results/counts/*/ and results/gain_trials.csv,
writes results/scores.csv, results/summary.json, results/per_odour.csv and plots/.
Works on partial results (reports how many odours each number is based on).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import optimize, stats

from common import PLOTS, RES, ROOT, groups, load_labels

DOOR = ROOT / "data" / "olfaction" / "door"
RMAX, SIGMA, EXP = 165.0, 12.0, 1.5          # Olsen et al. 2010, generic fit
M_VM7, M_DL5, LFP_PER_HZ = 10.63, 4.19, 190.0  # s = m * sum(r_i) / 190 (Olsen 2010 eq. 6)
OLSEN_GLOM = {"DM4": (170, 16.3), "DL5": (167, 11.8), "VM7d": (163, 12.4), "DM1": (144, 44.8)}


def load_config(name):
    d = RES / "counts" / name
    if not (d / "meta.json").exists():
        return None
    meta = json.loads((d / "meta.json").read_text())
    data = {}
    for f in sorted(d.glob("[0-9][0-9][0-9].npz")):
        z = np.load(f)
        data[int(f.stem)] = {"counts": z["counts"], "stats": json.loads(str(z["stats"])),
                             "name": str(z["name"]), "orn": z["orn_rates"]}
    meta["data"] = data
    return meta


def lifetime_sparseness(r):
    r = np.clip(np.asarray(r, float), 0, None)
    n = r.size
    if n < 2 or (r ** 2).sum() == 0:
        return np.nan
    return (1 - (r.mean() ** 2) / (r ** 2).mean()) / (1 - 1 / n)


def mean_offdiag_corr(X):
    """X: odours x units. Mean Pearson correlation over all odour pairs."""
    X = X[:, X.std(0) > 0] if X.shape[1] > 1 else X
    C = np.corrcoef(X)
    iu = np.triu_indices_from(C, 1)
    return float(np.nanmean(C[iu])), C


def pn_eq(x, s, rmax=RMAX, sigma=SIGMA):
    x = np.clip(x, 0, None)
    return rmax * x ** EXP / (x ** EXP + sigma ** EXP + np.clip(s, 0, None) ** EXP)


class Cfg:
    """One simulation config: per-odour KC / uPN / other read-outs."""

    def __init__(self, name, g, trial_idx=None):
        m = load_config(name)
        self.ok = m is not None and 0 in (m or {}).get("data", {})
        if not self.ok:
            return
        self.name, self.meta, self.data = name, m, m["data"]
        sl = m["slices"]
        self.sl = {k: slice(*v) for k, v in sl.items()}
        self.dur_s = m["dur"] / 1000
        self.trial_idx = trial_idx
        pn_rows = g["pn"]
        self.upn_pos = sl["pn"][0] + np.searchsorted(pn_rows, g["upn"])
        self.upn_glom = g["upn_glom"]
        self.idx = sorted(i for i in self.data if i > 0)
        self.names = [self.data[i]["name"] for i in self.idx]

    def counts(self, i):
        c = self.data[i]["counts"].astype(float)
        return c if self.trial_idx is None else c[self.trial_idx]

    def rate(self, i, key):
        return self.counts(i)[:, self.sl[key]].mean(0) / self.dur_s

    def kc(self):
        base = self.counts(0)[:, self.sl["kc"]]
        bmean = base.mean(0)
        out = []
        for i in self.idx:
            C = self.counts(i)[:, self.sl["kc"]]
            resp = ((C > 0).mean(0) >= 0.5) & (C.mean(0) > bmean)
            out.append({"i": i, "odour": self.data[i]["name"], "kc_resp_frac": resp.mean(),
                        "kc_ge1_per_trial": (C > 0).mean(), "kc_ge2_per_trial": (C >= 2).mean(),
                        "kc_ge3_per_trial": (C >= 3).mean(),
                        "spikes_per_resp": C.mean(0)[resp].tolist(),
                        "runaway_frac": np.mean([s["runaway"] for s in self.data[i]["stats"]]),
                        "tip_ms": [s.get("tip_ms", -1) for s in self.data[i]["stats"]]})
        return pd.DataFrame(out), {"baseline_ge1_per_trial": float((base > 0).mean()),
                                   "baseline_resp_frac": float(((base > 0).mean(0) >= 0.5).mean())}

    def evoked(self, key):
        """odours x neurons evoked rate (Hz): odour rate - baseline rate."""
        b = self.rate(0, key)
        return np.array([self.rate(i, key) - b for i in self.idx])

    def upn_by_glom(self):
        b = self.counts(0)[:, self.upn_pos].mean(0) / self.dur_s
        rows = []
        for i in self.idx:
            r = self.counts(i)[:, self.upn_pos].mean(0) / self.dur_s - b
            s = pd.Series(r).groupby(self.upn_glom).mean()
            rows.append(s)
        return pd.DataFrame(rows, index=self.names)


def verdict(value, match, partial):
    if match(value):
        return "MATCH"
    if partial(value):
        return "PARTIAL"
    return "MISMATCH"


def main():
    lab = load_labels()
    g = groups(lab)
    hc = pd.read_csv(RES / "hc_delta.csv", index_col=0)
    sfr = pd.read_csv(RES / "hc_sfr.csv", index_col=0)["sfr_hz"]
    gl = [c for c in hc.columns if c != "odour"]
    or33b = pd.read_csv(DOOR / "Or33b.csv", sep=";").set_index("InChIKey")["Hallem.2006.EN"]
    total24 = hc[gl].sum(axis=1) + or33b.reindex(hc.index).fillna(0)
    summary, scores = {}, []

    A = Cfg("alln_A", g)
    per_odour = None
    if A.ok:
        kcA, baseA = A.kc()
        per_odour = kcA[["odour", "kc_resp_frac", "kc_ge1_per_trial", "kc_ge2_per_trial"]].copy()
        per_odour["total_orn_delta_hz"] = total24.reindex(hc.index[[i - 1 for i in A.idx]]).to_numpy()
        n = len(kcA)
        f = kcA.kc_resp_frac
        summary["F1_setA"] = {"n_odours": n, "mean_pct": 100 * f.mean(), "median_pct": 100 * f.median(),
                              "max_pct": 100 * f.max(), "max_odour": kcA.odour[f.idxmax()],
                              "n_above_10pct": int((f > 0.10).sum()), "n_above_20pct": int((f > 0.20).sum()),
                              "n_below_1pct": int((f < 0.01).sum()),
                              "ge1_per_trial_mean_pct": 100 * kcA.kc_ge1_per_trial.mean(),
                              "ge2_per_trial_mean_pct": 100 * kcA.kc_ge2_per_trial.mean(),
                              "ge3_per_trial_mean_pct": 100 * kcA.kc_ge3_per_trial.mean(),
                              **{k: 100 * v for k, v in baseA.items()}}
        v = verdict(f, lambda x: 0.03 <= x.mean() <= 0.10 and x.max() <= 0.20,
                    lambda x: 0.015 <= x.mean() <= 0.20)
        scores.append(("F1", "KC sparseness, set A (23 measured glomeruli)",
                       "~5% mean (Honegger 2011), 6% (Turner 2008); no odour mean > 10%",
                       f"{100*f.mean():.1f}% mean (median {100*f.median():.1f}%, max {100*f.max():.1f}%, "
                       f"{int((f > 0.10).sum())} of {n} odours > 10%)", v))
        # F8 spikes per responding KC
        spk = np.concatenate([np.asarray(x) for x in kcA.spikes_per_resp]) if n else np.array([])
        summary["F8"] = {"n_pairs": int(spk.size), "median_spikes_per_0p5s": float(np.median(spk)),
                         "p90": float(np.percentile(spk, 90)), "max": float(spk.max())}
        scores.append(("F8", "Responding KCs fire only a few spikes", "'a few spikes' (Lin 2014; Turner 2008)",
                       f"median {np.median(spk):.1f} spikes per 0.5 s (90th pct {np.percentile(spk, 90):.1f})",
                       verdict(np.median(spk), lambda x: x <= 5, lambda x: x <= 10)))

        # F2 lifetime sparseness ORN vs PN per glomerulus
        pn = A.upn_by_glom()
        odour_keys = hc.index[[i - 1 for i in A.idx]]
        orn_ev = hc.loc[odour_keys, gl].clip(lower=-sfr[gl], axis=1)
        ls = []
        for glo in gl:
            ls.append({"glomerulus": glo, "S_orn": lifetime_sparseness(orn_ev[glo].to_numpy()),
                       "S_pn": lifetime_sparseness(pn[glo].to_numpy()),
                       "pn_max_evoked_hz": float(pn[glo].max()), "orn_max_evoked_hz": float(orn_ev[glo].max())})
        ls = pd.DataFrame(ls)
        ls.to_csv(RES / "lifetime_sparseness.csv", index=False)
        n_nan = int(ls[["S_pn", "S_orn"]].isna().any(axis=1).sum())
        ls = ls.dropna(subset=["S_pn", "S_orn"])
        k = int((ls.S_pn < ls.S_orn).sum())
        p = float(stats.wilcoxon(ls.S_pn, ls.S_orn).pvalue)
        summary["F2"] = {"n_glomeruli": len(ls), "n_dropped_no_response": n_nan,
                         "pn_less_selective": k, "wilcoxon_p": p,
                         "median_S_orn": float(ls.S_orn.median()), "median_S_pn": float(ls.S_pn.median())}
        frac = k / len(ls)
        v = "MATCH" if frac >= 0.8 and p < 0.05 else ("PARTIAL" if frac >= 0.5 else "MISMATCH")
        scores.append(("F2", "PNs more broadly tuned than their ORNs",
                       "PN < ORN lifetime sparseness in 7 of 7 glomeruli (Bhandawat 2007)",
                       f"PN < ORN in {k} of {len(ls)} glomeruli; median S {ls.S_orn.median():.2f} (ORN) vs "
                       f"{ls.S_pn.median():.2f} (PN); Wilcoxon p = {p:.2g}", v))

        # F5 Olsen 2010 equation vs model uPN responses
        tot = total24.reindex(odour_keys).to_numpy()
        pred, pred_ff, mod = [], [], []
        for glo in gl:
            x = hc.loc[odour_keys, glo].to_numpy()
            pred.append(pn_eq(x, M_VM7 * tot / LFP_PER_HZ))
            pred_ff.append(pn_eq(x, 0.0))
            mod.append(pn[glo].to_numpy())
        pred, pred_ff, mod = map(np.concatenate, (pred, pred_ff, mod))
        r = float(np.corrcoef(pred, mod)[0, 1])
        r_ff = float(np.corrcoef(pred_ff, mod)[0, 1])
        rho = float(stats.spearmanr(pred, mod).statistic)
        summary["F5"] = {"n_pairs": int(mod.size), "pearson_r": r, "spearman_rho": rho,
                         "pearson_r_no_normalization": r_ff,
                         "model_pn_evoked_mean_hz": float(mod.mean()), "eq_pn_mean_hz": float(pred.mean()),
                         "model_pn_evoked_p95_hz": float(np.percentile(mod, 95)),
                         "eq_pn_p95_hz": float(np.percentile(pred, 95))}
        pd.DataFrame({"model_pn_evoked_hz": mod, "olsen_eq_hz": pred, "olsen_eq_no_norm_hz": pred_ff}).to_csv(
            RES / "pn_vs_olsen_eq.csv", index=False)
        scores.append(("F5", "PN odour responses vs the real-fly normalization equation",
                       "equation explained 95% / 87% of real VM7 / DL5 PN variance (Olsen 2010)",
                       f"r = {r:.2f} (Spearman {rho:.2f}) over {mod.size} glomerulus-odour pairs; "
                       f"mean {mod.mean():.0f} Hz model vs {pred.mean():.0f} Hz equation",
                       verdict(r, lambda x: x >= 0.7, lambda x: x >= 0.4)))

        # F6 correlations ORN / uPN / KC
        kc_ev = A.evoked("kc")
        upn_ev = np.array([A.counts(i)[:, A.upn_pos].mean(0) / A.dur_s for i in A.idx]) - \
            A.counts(0)[:, A.upn_pos].mean(0) / A.dur_s
        c_orn, _ = mean_offdiag_corr(orn_ev.to_numpy())
        c_pn, _ = mean_offdiag_corr(upn_ev)
        c_kc, _ = mean_offdiag_corr(kc_ev)
        c_pn23, _ = mean_offdiag_corr(pn[gl].to_numpy())   # same 23-glomerulus space as the ORNs
        c_pn_tested, _ = mean_offdiag_corr(upn_ev[:, np.isin(A.upn_glom, gl)])  # uPNs of measured glomeruli
        kc_bin = np.array([((A.counts(i)[:, A.sl["kc"]] > 0).mean(0) >= 0.5) for i in A.idx], float)
        c_kcbin, _ = mean_offdiag_corr(kc_bin)
        summary["F6"] = {"corr_orn": c_orn, "corr_upn": c_pn, "corr_kc": c_kc,
                         "corr_upn_23glom_means": c_pn23, "corr_upn_measured_glomeruli_neurons": c_pn_tested, "corr_kc_binary_responders": c_kcbin}
        v = "MATCH" if (c_kc < c_pn and c_kc < c_orn) else ("PARTIAL" if (c_kc < c_pn or c_kc < c_orn) else "MISMATCH")
        scores.append(("F6", "Odour representations decorrelate from ORNs/PNs to KCs",
                       "less correlated in KCs than ORNs (Turner 2008); KC coding decorrelated (Lin 2014)",
                       f"mean inter-odour r: ORN {c_orn:.2f}, uPN {c_pn:.2f} (23-glomerulus means "
                       f"{c_pn23:.2f}), KC {c_kc:.2f} (binary responders {c_kcbin:.2f})", v))

        # descriptive: APL, MBON, LN, LHN
        for key in ("apl", "mbon", "ln", "lhn", "dan"):
            ev = A.evoked(key)
            per_odour[f"{key}_mean_evoked_hz"] = ev.mean(1)
            if key == "mbon":
                per_odour["mbon_n_above_5hz"] = (ev > 5).sum(1)
        per_odour["upn_mean_evoked_hz"] = upn_ev.mean(1)
        summary["descriptive_setA"] = {
            "apl_evoked_hz_median": float(per_odour.apl_mean_evoked_hz.median()),
            "mbon_n_above_5hz_median": float(per_odour.mbon_n_above_5hz.median()),
            "mbon_total": int(g["mbon"].size),
            "upn_evoked_hz_median": float(per_odour.upn_mean_evoked_hz.median()),
            "ln_evoked_hz_median": float(per_odour.ln_mean_evoked_hz.median()),
            "lhn_evoked_hz_median": float(per_odour.lhn_mean_evoked_hz.median()),
            "dan_evoked_hz_median": float(per_odour.dan_mean_evoked_hz.median()),
            "kc_frac_vs_total_orn_spearman": float(stats.spearmanr(per_odour.total_orn_delta_hz,
                                                                   per_odour.kc_resp_frac).statistic),
        }

        # F7 APL block, paired on trials 0-1 of each seed
        pair_idx = np.array([0, 1, 4, 5, 8, 9])
        N = Cfg("alln_A_noAPL", g)
        if N.ok and len(N.idx) >= 5:
            Ap = Cfg("alln_A", g, trial_idx=pair_idx)
            kc_i, _ = Ap.kc()
            kc_n, base_n = N.kc()
            common = sorted(set(kc_i.i) & set(kc_n.i))
            fi = kc_i.set_index("i").loc[common, "kc_resp_frac"]
            fn = kc_n.set_index("i").loc[common, "kc_resp_frac"]
            keep = [Ap.idx.index(i) for i in common]
            keepn = [N.idx.index(i) for i in common]
            ci, _ = mean_offdiag_corr(Ap.evoked("kc")[keep])
            cn, _ = mean_offdiag_corr(N.evoked("kc")[keepn])
            apl_ok = int(fn.mean() > fi.mean()) + int(cn > ci)   # numpy bools would OR, not add
            summary["F7"] = {"n_odours": len(common), "kc_frac_intact_mean_pct": 100 * fi.mean(),
                             "kc_frac_noAPL_mean_pct": 100 * fn.mean(),
                             "fold": float(fn.mean() / fi.mean()) if fi.mean() > 0 else None,
                             "n_odours_denser": int((fn > fi).sum()),
                             "corr_kc_intact": ci, "corr_kc_noAPL": cn,
                             "baseline_noAPL_ge1_pct": 100 * base_n["baseline_ge1_per_trial"],
                             "wilcoxon_p": float(stats.wilcoxon(fn, fi).pvalue)}
            v = "MATCH" if apl_ok == 2 else ("PARTIAL" if apl_ok == 1 else "MISMATCH")
            scores.append(("F7", "Blocking APL makes KC responses denser and more correlated",
                           "denser + more correlated (Lin 2014; size not stated in text)",
                           f"KC responding {100*fi.mean():.1f}% -> {100*fn.mean():.1f}% "
                           f"({int((fn > fi).sum())} of {len(common)} odours denser); inter-odour r "
                           f"{ci:.2f} -> {cn:.2f}", v))
            per_odour = per_odour.merge(pd.DataFrame({"odour": kc_n.odour, "kc_resp_frac_noAPL_6tr": kc_n.kc_resp_frac}),
                                        on="odour", how="left")

    # set B (Hallem + DoOR-extended)
    B = Cfg("alln_B", g)
    if B.ok:
        kcB, baseB = B.kc()
        f = kcB.kc_resp_frac
        summary["F1_setB"] = {"n_odours": len(kcB), "mean_pct": 100 * f.mean(), "median_pct": 100 * f.median(),
                              "max_pct": 100 * f.max(), "max_odour": kcB.odour[f.idxmax()],
                              "n_above_10pct": int((f > 0.10).sum()), "n_above_20pct": int((f > 0.20).sum()),
                              "ge1_per_trial_mean_pct": 100 * kcB.kc_ge1_per_trial.mean(),
                              **{k: 100 * v for k, v in baseB.items()}}
        v = verdict(f, lambda x: 0.03 <= x.mean() <= 0.10 and x.max() <= 0.20,
                    lambda x: 0.015 <= x.mean() <= 0.20)
        scores.append(("F1b", "KC sparseness, set B (46 glomeruli incl. DoOR estimates; 6 trials)",
                       "~5% mean (Honegger 2011), 6% (Turner 2008); no odour mean > 10%",
                       f"{100*f.mean():.1f}% mean (median {100*f.median():.1f}%, max {100*f.max():.1f}%, "
                       f"{int((f > 0.10).sum())} of {len(kcB)} odours > 10%)", v))
        if per_odour is not None:
            per_odour = per_odour.merge(pd.DataFrame({"odour": kcB.odour, "kc_resp_frac_setB": f}),
                                        on="odour", how="left")

    # published brain: runaway per odour
    for cname in ("none_A", "none_evoked"):
        C = Cfg(cname, g)
        if not C.ok:
            continue
        kc, base = C.kc()
        tips = [t for x in kc.tip_ms for t in x if t >= 0]
        base_stats = C.data[0]["stats"]
        summary[cname] = {"n_odours": len(kc), "n_odours_any_runaway": int((kc.runaway_frac > 0).sum()),
                          "n_odours_all_trials_runaway": int((kc.runaway_frac == 1).sum()),
                          "baseline_runaway": [s["runaway"] for s in base_stats],
                          "baseline_tip_ms": [s.get("tip_ms", -1) for s in base_stats],
                          "tip_ms_median": float(np.median(tips)) if tips else None,
                          "tip_ms_range": [int(min(tips)), int(max(tips))] if tips else None,
                          "kc_ge1_per_trial_mean_pct": 100 * kc.kc_ge1_per_trial.mean()}
        if per_odour is not None:
            per_odour = per_odour.merge(pd.DataFrame({
                "odour": kc.odour, f"{cname}_runaway_frac": kc.runaway_frac,
                f"{cname}_tip_ms_mean": [np.mean([t for t in x if t >= 0]) if any(t >= 0 for t in x) else np.nan
                                         for x in kc.tip_ms]}), on="odour", how="left")
        if cname == "none_evoked" and per_odour is not None:
            ok = per_odour[f"{cname}_tip_ms_mean"].notna()
            if ok.sum() > 3:
                summary[cname]["tip_vs_total_orn_spearman"] = float(stats.spearmanr(
                    per_odour.total_orn_delta_hz[ok], per_odour[f"{cname}_tip_ms_mean"][ok]).statistic)

    # F3 / F4 gain experiment
    gp = RES / "gain_trials.csv"
    if gp.exists():
        gd = pd.read_csv(gp)
        f3, f4 = [], []
        pub = hc[hc.odour == "pentyl acetate"].iloc[0]
        pub_total = {glo: float(pub[gl].drop(labels=[glo], errors="ignore").sum()
                                + or33b.get(hc.index[hc.odour == "pentyl acetate"][0], 0.0))
                     for glo in ("DL5", "DM4", "DM1", "VM7d")}
        for glo, d in gd.groupby("glom"):
            mm = d.groupby(["public_scale", "private_delta"]).upn_hz.mean()
            if 0.0 not in mm.index.get_level_values(0):
                continue
            base = mm.loc[(0.0, 0)]
            curve = mm.loc[0.0] - base
            x, y = curve.index.to_numpy(float), curve.to_numpy(float)
            try:
                (rmax, sig), _ = optimize.curve_fit(lambda xx, a, b: a * xx ** EXP / (xx ** EXP + b ** EXP),
                                                    x, y, p0=(150, 20), bounds=([0, 0.1], [2000, 2000]))
            except Exception:  # noqa: BLE001
                rmax, sig = np.nan, np.nan
            gain_lo = y[x == 10][0] / 10 if (x == 10).any() else np.nan
            gain_hi = (y[x == 160][0] - y[x == 80][0]) / 80 if (x == 160).any() else np.nan
            f3.append({"glomerulus": glo, "rmax_fit": rmax, "sigma_fit": sig, "gain_0_10": gain_lo,
                       "gain_80_160": gain_hi, "sat_ratio": gain_lo / gain_hi if gain_hi else np.nan,
                       **{f"pn_evoked_at_{int(k)}": float(v) for k, v in zip(x, y)}})
            for sc in (0.5, 1.0):
                if sc not in mm.index.get_level_values(0):
                    continue
                for dp in (20, 40, 80):
                    if (sc, dp) not in mm.index:
                        continue
                    mod_ratio = (mm.loc[(sc, dp)] - base) / (mm.loc[(0.0, dp)] - base)
                    eq = {}
                    for mname, mval in (("m_vm7", M_VM7), ("m_dl5", M_DL5)):
                        s0 = mval * dp / LFP_PER_HZ
                        s1 = mval * (dp + sc * pub_total[glo]) / LFP_PER_HZ
                        eq[mname] = float(pn_eq(dp, s1) / pn_eq(dp, s0))
                    f4.append({"glomerulus": glo, "public_scale": sc, "private_delta": dp,
                               "model_ratio": float(mod_ratio), "eq_ratio_m_vm7": eq["m_vm7"],
                               "eq_ratio_m_dl5": eq["m_dl5"],
                               "public_alone_evoked_hz": float(mm.loc[(sc, 0)] - base)})
        f3, f4 = pd.DataFrame(f3), pd.DataFrame(f4)
        f3.to_csv(RES / "gain_transfer_fits.csv", index=False)
        f4.to_csv(RES / "gain_lateral_inhibition.csv", index=False)
        summary["F3"] = f3.to_dict("records")
        if len(f3):
            sat = (f3.sat_ratio > 2).all()
            inband = ((f3.sigma_fit.between(6, 24)) & (f3.rmax_fit.between(83, 330))).all()
            v = "MATCH" if (sat and inband) else ("PARTIAL" if sat else "MISMATCH")
            scores.append(("F3", "Weak ORN input amplified, strong input saturates",
                           "Rmax 165 Hz, sigma 12 Hz (Olsen 2010; per glomerulus Rmax 144-170, sigma 12-45)",
                           "; ".join(f"{r.glomerulus}: Rmax {r.rmax_fit:.0f}, sigma {r.sigma_fit:.0f} Hz, "
                                     f"gain ratio {r.sat_ratio:.1f}" for r in f3.itertuples()), v))
        if len(f4):
            full = f4[f4.public_scale == 1.0]
            summary["F4"] = f4.to_dict("records")
            supp = full.groupby("glomerulus").model_ratio.mean()
            eq_lo = full.groupby("glomerulus")[["eq_ratio_m_vm7", "eq_ratio_m_dl5"]].mean().min(1)
            eq_hi = full.groupby("glomerulus")[["eq_ratio_m_vm7", "eq_ratio_m_dl5"]].mean().max(1)
            # suppression amount = 1 - ratio; "within 2x" of the equation band
            s_mod = 1 - supp
            s_lo, s_hi = 1 - eq_hi, 1 - eq_lo
            present = (s_mod > 0.05)
            within = (s_mod >= s_lo / 2) & (s_mod <= s_hi * 2)
            if present.all() and within.all():
                v = "MATCH"
            elif present.sum() >= 2:
                v = "PARTIAL"
            else:
                v = "MISMATCH"
            scores.append(("F4", "Lateral inhibition from other glomeruli (pentyl acetate x1 as 'public' odour)",
                           "; ".join(f"{k}: {100*s_lo[k]:.0f}-{100*s_hi[k]:.0f}% less" for k in s_mod.index)
                           + " (Olsen 2010 equation, m = 4.19-10.63)",
                           "; ".join(f"{k}: {100*s_mod[k]:.0f}% less" for k in s_mod.index), v))

    sc = pd.DataFrame(scores, columns=["fact", "what", "real_fly", "model", "verdict"])
    sc.to_csv(RES / "scores.csv", index=False)
    (RES / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    if per_odour is not None:
        per_odour.to_csv(RES / "per_odour.csv", index=False)
    for r in sc.itertuples():
        print(f"{r.fact:4s} {r.verdict:8s} {r.model}")
    return summary


if __name__ == "__main__":
    main()
