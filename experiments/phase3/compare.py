"""Compare the Phase 3 Brian2 results with the paper and with the reference
code's own saved output, and draw the plots.

Run after run_experiments.py (missing experiments are skipped):
    .venv/Scripts/python.exe experiments/phase3/compare.py

Writes to experiments/phase3/:
    results/phase3_rates.parquet     every experiment's per-neuron rates (long table, machine-readable)
    results/phase3_rates_mn9.csv     just the MN9 rows, one line per experiment
    results/reference_example_rates.csv   per-neuron rates from the reference repo's own saved runs
    comparison_table.csv / .md       ours vs paper, side by side, with a verdict per row
    per_neuron_vs_reference.csv      neuron-by-neuron check against the reference's saved runs
    plots/*.png
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim import shiu_model as sm  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = ROOT / "experiments" / "phase3"
RES = HERE / "results"
PLOTS = HERE / "plots"
REF_EX = sm.REF_DIR / "results" / "example"
MN9C, MN9I = sm.MN9_LEFT, sm.MN9_RIGHT_630          # contra / ipsi to the stimulated GRNs (630 IDs)
OURS_C, PAPER_C = "#2a78d6", "#eb6834"               # categorical slots 1 and 2 (dataviz default palette)
INK, MUTED = "#222222", "#6b6b6b"

# ---------------------------------------------------------------------------
# Paper numbers. Sources:
#  "repo"  = computed here from the reference repo's own saved output
#            (data/reference/results/example/*.parquet, 30 trials, snapshot 630).
#  "text"  = stated in the Nature paper's text (checked in the Europe PMC full text, PMC11446845).
#  "notes" = docs/reference-notes.md table 4.3 (authors' result CSVs from the Edmond archive);
#            the number itself was NOT re-checked by the Phase 3 agent -> UNVERIFIED.
# ---------------------------------------------------------------------------
PAPER = [
    # exp, readout, paper value, paper sd, source, expected direction, paper claim
    ("sugar_100Hz", "MN9 contra", 65.7, 3.3, "notes; repo run gives 67.0",
     "up", "MN9 fires in 100% of simulations at 100 Hz sugar (text)"),
    ("sugar_100Hz", "MN9 ipsi", 49.7, 4.4, "notes; repo run gives 48.6", "up, below contra", ""),
    ("sugar_100Hz", "active neurons", 410, None, "notes; repo run gives 404", "network grows with rate", ""),
    ("sugar_200Hz", "MN9 contra", 93.2, 5.2, "notes; repo run gives 93.3", "up, above 100 Hz value", ""),
    ("sugar_200Hz", "MN9 ipsi", 62.9, 3.6, "notes; repo run gives 61.8", "up, below contra", ""),
    ("sugar_200Hz", "active neurons", 455, None, "text (455 neurons at 200 Hz); repo run gives 448",
     "network grows with rate", ""),
    ("water_200Hz", "MN9 contra", 30.7, 5.4, "notes (UNVERIFIED number); text: water activates MN9",
     "up, weaker than sugar", ""),
    ("water_200Hz", "MN9 ipsi", 13.0, None, "notes (UNVERIFIED number)", "up, below contra", ""),
    ("bitter_200Hz", "MN9 contra", 0.0, None, "notes (UNVERIFIED number)", "zero", ""),
    ("sugar100_bitter40", "MN9 contra", 45.3, None, "notes (UNVERIFIED number); text: bitter inhibits MN9",
     "down vs sugar alone", ""),
    ("sugar100_bitter120", "MN9 contra", 1.5, None, "notes (UNVERIFIED number); text: bitter inhibits MN9",
     "down, near zero", ""),
    ("sugar200_ir94e200", "MN9 contra", 64.3, None,
     "notes (UNVERIFIED number); text: strong Ir94e does not eliminate strong sugar",
     "down vs sugar alone, not abolished", ""),
]


def load_ours():
    """{(snapshot, exp): (rates DataFrame, settings dict, spikes DataFrame)}"""
    out = {}
    for d in sorted(RES.glob("v*")):
        for f in sorted(d.glob("*_settings.json")):
            name = f.name[: -len("_settings.json")]
            st = json.loads(f.read_text())
            rates = pd.read_csv(d / f"{name}_rates.csv", index_col="flywire_id")
            spikes = pd.read_parquet(d / f"{name}_spikes.parquet")
            out[(st["snapshot"], name)] = (rates, st, spikes)
    return out


def per_trial_rate(spikes, flyid, n_trials, dur_s=1.0):
    c = spikes[spikes.flywire_id == flyid].groupby("trial").size()
    return c.reindex(range(n_trials), fill_value=0).to_numpy() / dur_s


def reference_example():
    """Rates from the reference repo's own saved 30-trial runs (snapshot 630).

    sugarR.parquet: the sugar GRNs fire ~197 Hz in it, and the notebook text says
    "By default, the neurons are excited at 200 Hz", so it is a 200 Hz run even
    though model.py's default is now 150 Hz. sugarR_100Hz.parquet is 100 Hz.
    """
    runs = {"sugar_200Hz": "sugarR.parquet", "sugar_100Hz": "sugarR_100Hz.parquet"}
    out = {}
    for exp, fn in runs.items():
        df = pd.read_parquet(REF_EX / fn)
        r, s = sm.rates_from_spikes(df, 1.0, 30)
        out[exp] = (pd.DataFrame({"rate_hz": r, "rate_std_hz": s}), df)
    return out


def to_md(df):
    """Plain markdown table (pandas' to_markdown needs the optional 'tabulate')."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(lines)


def fmt(m, s=None):
    if m is None or (isinstance(m, float) and np.isnan(m)):
        return "n/a"
    return f"{m:.1f} ± {s:.1f}" if s is not None and not np.isnan(s) else f"{m:.1f}"


def main():
    PLOTS.mkdir(parents=True, exist_ok=True)
    ours = load_ours()
    if not ours:
        print("no results yet")
        return
    ref = reference_example()

    # ---- 1. machine-readable rates -------------------------------------------------
    rows = []
    for (ds, name), (rates, st, _) in ours.items():
        df = rates.reset_index()
        df.insert(0, "exp_name", name)
        df.insert(0, "snapshot", ds)
        for k in ["excite_set", "rate_hz", "excite2_set", "rate2_hz", "silence_ids", "n_trials", "duration_ms"]:
            v = st.get(k)
            df[k] = json.dumps(v) if isinstance(v, list) else v
        df["seed_first"] = st["seeds"][0]
        rows.append(df)
    long = pd.concat(rows, ignore_index=True)
    long["flywire_id"] = long["flywire_id"].astype("int64")
    long.to_parquet(RES / "phase3_rates.parquet", index=False)

    refrows = []
    for exp, (r, _) in ref.items():
        d = r.reset_index().rename(columns={"index": "flywire_id"})
        d.insert(0, "exp_name", exp)
        refrows.append(d)
    pd.concat(refrows).to_csv(RES / "reference_example_rates.csv", index=False)

    mn9rows = []
    for (ds, name), (rates, st, spikes) in ours.items():
        c, i = sm.mn9_ids(ds)
        n = st["n_trials"]
        pc, pi = per_trial_rate(spikes, c, n), per_trial_rate(spikes, i, n)
        tot = spikes.groupby("trial").size().reindex(range(n), fill_value=0).to_numpy()
        mn9rows.append({"snapshot": ds, "exp_name": name, "n_trials": n,
                        "mn9_contra_hz": pc.mean(), "mn9_contra_sd": pc.std(),
                        "mn9_ipsi_hz": pi.mean(), "mn9_ipsi_sd": pi.std(),
                        "active_neurons": int((rates["rate_hz"] > 0).sum()),
                        "mn9_contra_per_trial": json.dumps(pc.tolist()),
                        "spikes_per_trial": json.dumps(tot.tolist()),
                        # a trial with > 5x the median spike count = whole-network runaway activity
                        "runaway_trials": json.dumps([int(k) for k in np.nonzero(tot > 5 * np.median(tot))[0]])})
    mn9 = pd.DataFrame(mn9rows)
    mn9.to_csv(RES / "phase3_rates_mn9.csv", index=False)
    m = mn9.set_index(["snapshot", "exp_name"])

    def ours_val(exp, readout, ds="630"):
        if (ds, exp) not in m.index:
            return None, None
        row = m.loc[(ds, exp)]
        if readout == "MN9 contra":
            return row.mn9_contra_hz, row.mn9_contra_sd
        if readout == "MN9 ipsi":
            return row.mn9_ipsi_hz, row.mn9_ipsi_sd
        return float(row.active_neurons), None

    # ---- 2. side-by-side table with a verdict per row ------------------------------
    sugar100 = ours_val("sugar_100Hz", "MN9 contra")[0]
    sugar200 = ours_val("sugar_200Hz", "MN9 contra")[0]
    table = []
    for exp, readout, pv, psd, src, direction, _ in PAPER:
        ov, osd = ours_val(exp, readout)
        if ov is None:
            continue
        refv = None
        if exp in ref and readout.startswith("MN9"):
            fid = MN9C if readout == "MN9 contra" else MN9I
            refv = ref[exp][0]["rate_hz"].get(fid, 0.0)
        elif exp in ref:
            refv = float((ref[exp][0]["rate_hz"] > 0).sum())
        # direction verdict
        if direction == "zero":
            ok = ov == 0
        elif readout == "active neurons":
            ok = ov > 300 if exp == "sugar_100Hz" else (ov > ours_val("sugar_100Hz", readout)[0] if sugar100 else ov > 300)
        elif "below contra" in direction:
            ok = 0 < ov < ours_val(exp, "MN9 contra")[0]
        elif exp == "sugar_200Hz":
            ok = sugar100 is not None and ov > sugar100
        elif exp == "water_200Hz":
            ok = 0 < ov < (sugar200 or np.inf)
        elif exp == "sugar100_bitter40":
            ok = sugar100 is not None and ov < sugar100
        elif exp == "sugar100_bitter120":
            ok = sugar100 is not None and ov < 0.1 * sugar100
        elif exp == "sugar200_ir94e200":
            ok = sugar200 is not None and 0 < ov < sugar200
        else:
            ok = ov > 10
        n = int(m.loc[("630", exp)].n_trials)
        within = ""
        if psd:
            se = np.hypot(psd / np.sqrt(30), (osd or 0) / np.sqrt(n))
            within = "yes" if abs(ov - pv) <= 2 * max(psd, osd or 0) else "no"
            within += f" (diff {ov - pv:+.1f} Hz, {abs(ov - pv) / se:.1f} SE)"
        table.append({
            "condition (snapshot 630)": exp, "readout": readout,
            "ours": fmt(ov, osd) + ("" if readout == "active neurons" else " Hz"),
            "trials (ours)": n,
            "paper": fmt(pv, psd) + ("" if readout == "active neurons" else " Hz"),
            "reference repo run (30 trials)": "" if refv is None else fmt(refv),
            "paper source": src,
            "expected direction": direction,
            "direction matches": "YES" if ok else "NO",
            "number within 2 sd of paper": within,
        })
    tab = pd.DataFrame(table)
    tab.to_csv(HERE / "comparison_table.csv", index=False)

    # snapshot 783 secondary rows
    t783 = []
    for exp in ["v783_sugar_100Hz", "v783_sugar100_bitter120"]:
        if ("783", exp) in m.index:
            base = exp.replace("v783_", "")
            a, b = ours_val(exp, "MN9 contra", "783"), ours_val(base, "MN9 contra", "630")
            ai, bi = ours_val(exp, "MN9 ipsi", "783"), ours_val(base, "MN9 ipsi", "630")
            t783.append({"condition": base,
                         "783: MN9 contra / ipsi (Hz)": f"{fmt(*a)} / {fmt(*ai)}",
                         "630: MN9 contra / ipsi (Hz)": f"{fmt(*b)} / {fmt(*bi)}",
                         "trials 783 / 630": f"{int(m.loc[('783', exp)].n_trials)} / "
                                             f"{int(m.loc[('630', base)].n_trials) if ('630', base) in m.index else 'n/a'}"})
    t783 = pd.DataFrame(t783)

    # ---- 3. neuron-by-neuron check against the reference's saved runs --------------
    pn_rows, pn_summary = [], []
    for exp, (rref, _) in ref.items():
        if ("630", exp) not in ours:
            continue
        ro, st, _ = ours[("630", exp)]
        n_o = st["n_trials"]
        u = ro.index.union(rref.index)
        a = ro.reindex(u).fillna(0.0)
        b = rref.reindex(u).fillna(0.0)
        se = np.sqrt(a.rate_std_hz ** 2 / n_o + b.rate_std_hz ** 2 / 30)
        se = se.where(se > 0, np.nan)
        z = (a.rate_hz - b.rate_hz) / se
        d = pd.DataFrame({"exp_name": exp, "flywire_id": u, "ours_hz": a.rate_hz.values,
                          "reference_hz": b.rate_hz.values, "z": z.values})
        pn_rows.append(d)
        both = (a.rate_hz > 0) & (b.rate_hz > 0)
        only_o = (a.rate_hz > 0) & (b.rate_hz == 0)
        only_r = (a.rate_hz == 0) & (b.rate_hz > 0)
        strong_r = b.rate_hz >= 5
        top50_o = set(a.rate_hz.nlargest(50).index)
        top50_r = set(b.rate_hz.nlargest(50).index)
        pn_summary.append({
            "condition": exp,
            "active (ours / reference)": f"{int((a.rate_hz > 0).sum())} / {int((b.rate_hz > 0).sum())}",
            "active in both": int(both.sum()),
            "only ours (max rate)": f"{int(only_o.sum())} ({a.rate_hz[only_o].max() if only_o.any() else 0:.2f} Hz)",
            "only reference (max rate)": f"{int(only_r.sum())} ({b.rate_hz[only_r].max() if only_r.any() else 0:.2f} Hz)",
            "reference neurons >= 5 Hz also active in ours": f"{int((strong_r & (a.rate_hz > 0)).sum())} / {int(strong_r.sum())}",
            "Pearson r": round(float(np.corrcoef(a.rate_hz, b.rate_hz)[0, 1]), 4),
            "top-50 overlap": len(top50_o & top50_r),
            "neurons with |z| > 4": int((z.abs() > 4).sum()),
        })
    pn_sum = pd.DataFrame(pn_summary)
    if pn_rows:
        pd.concat(pn_rows).sort_values(["exp_name", "reference_hz"], ascending=[True, False]).to_csv(
            HERE / "per_neuron_vs_reference.csv", index=False)

    # ---- 4. markdown ----------------------------------------------------------------
    md = ["# Phase 3 comparison: our Brian2 port vs the paper", "",
          "Generated by `experiments/phase3/compare.py`. Snapshot 630 (the paper's data). "
          "REDUCED protocol: our runs use 10 trials of 1 s for the main conditions and 5 for the "
          "control and dose conditions (the paper used 30). The ± value is the trial-to-trial "
          "standard deviation.", "",
          "## MN9 and network size, ours vs paper", "", to_md(tab), ""]
    if len(pn_sum):
        md += ["## Every neuron vs the reference code's own saved runs (30 trials)", "",
               to_md(pn_sum), ""]
    health = mn9.reset_index()[["snapshot", "exp_name", "n_trials", "spikes_per_trial", "runaway_trials"]]
    md += ["## Trial health (total spikes in each 1 s trial)", "",
           "A trial with more than 5x the median spike count is flagged as runaway: the whole "
           "network tips into a self-sustaining high-activity state.", "", to_md(health), ""]
    if len(t783):
        md += ["## Snapshot 783 (secondary check, 5 trials)", "", to_md(t783), ""]
    (HERE / "comparison_table.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))

    # ---- 5. plots ---------------------------------------------------------------------
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                         "axes.spines.right": False})
    # (a) MN9: ours vs paper per condition
    t = tab[tab.readout == "MN9 contra"]
    if len(t):
        labels, ov, osd, pv, psd = [], [], [], [], []
        for _, r in t.iterrows():
            exp = r["condition (snapshot 630)"]
            o = ours_val(exp, "MN9 contra")
            p = next(x for x in PAPER if x[0] == exp and x[1] == "MN9 contra")
            name = (exp.replace("sugar100_", "sugar 100 + ").replace("sugar200_", "sugar 200 + ")
                    .replace("_", " ").replace("Hz", " Hz").replace("bitter", "bitter ").replace("ir94e", "Ir94e ")
                    .replace("  ", " "))
            labels.append(f"{name}  (n={int(m.loc[('630', exp)].n_trials)})")
            ov.append(o[0]); osd.append(o[1]); pv.append(p[2]); psd.append(p[3] or 0)
        y = np.arange(len(labels))[::-1]
        fig, ax = plt.subplots(figsize=(8, 0.6 * len(labels) + 1.8))
        h = 0.38
        ax.barh(y + h / 2, ov, h, xerr=osd, color=OURS_C, edgecolor="white", lw=1,
                label="ours (Brian2 port; n = our trial count)", error_kw=dict(ecolor=INK, lw=1, capsize=2))
        ax.barh(y - h / 2, pv, h, xerr=[s if s else np.nan for s in psd], color=PAPER_C, edgecolor="white", lw=1,
                label="paper (30 trials; sd only where published)", error_kw=dict(ecolor=INK, lw=1, capsize=2))
        for yy, a, sa, b, sb in zip(y, ov, osd, pv, psd):
            ax.text(a + (sa or 0) + 1.5, yy + h / 2, f"{a:.1f}", va="center", fontsize=8, color=INK)
            ax.text(b + (sb or 0) + 1.5, yy - h / 2, f"{b:.1f}", va="center", fontsize=8, color=INK)
        ax.set_yticks(y, labels)
        ax.set_xlim(0, max(max(ov), max(pv)) * 1.15)
        ax.set_xlabel("MN9 firing rate (spikes per second), snapshot 630")
        fig.suptitle("MN9 (proboscis motor neuron) response: ours vs paper", x=0.01, ha="left", color=INK)
        ax.grid(axis="x", color="#e5e5e5", lw=0.8)
        ax.set_axisbelow(True)
        ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=8)
        fig.tight_layout()
        fig.savefig(PLOTS / "mn9_ours_vs_paper.png", dpi=150)
        plt.close(fig)

    # (b) every neuron: ours vs reference saved runs
    if pn_rows:
        fig, axes = plt.subplots(1, len(pn_rows), figsize=(5.2 * len(pn_rows), 4.8))
        axes = np.atleast_1d(axes)
        for ax, d in zip(axes, pn_rows):
            exp = d.exp_name.iloc[0]
            lim = max(d.ours_hz.max(), d.reference_hz.max()) * 1.05
            ax.plot([0, lim], [0, lim], color=MUTED, lw=1, ls="--", zorder=1)
            ax.scatter(d.reference_hz, d.ours_hz, s=12, color=OURS_C, alpha=0.7, edgecolor="white", lw=0.4, zorder=2)
            for fid, name in [(MN9C, "MN9 contra"), (MN9I, "MN9 ipsi")]:
                row = d[d.flywire_id == fid]
                if len(row):
                    ax.scatter(row.reference_hz, row.ours_hz, s=40, color=PAPER_C, edgecolor=INK, lw=0.6, zorder=3)
                    ax.annotate(name, (row.reference_hz.iloc[0], row.ours_hz.iloc[0]), xytext=(6, -10),
                                textcoords="offset points", fontsize=8, color=INK)
            r = np.corrcoef(d.ours_hz, d.reference_hz)[0, 1]
            ax.set_title(f"{exp.replace('_', ' ')}: {len(d)} neurons, r = {r:.4f}", loc="left", color=INK)
            ax.set_xlabel("reference code's saved run (Hz, 30 trials)")
            ax.set_ylabel("our port (Hz, 10 trials)")
            ax.set_xlim(0, lim); ax.set_ylim(0, lim)
            ax.grid(color="#eeeeee", lw=0.8); ax.set_axisbelow(True)
        fig.tight_layout()
        fig.savefig(PLOTS / "per_neuron_vs_reference.png", dpi=150)
        plt.close(fig)

    # (c) raster of one trial of the sugar 100 Hz run
    if ("630", "sugar_100Hz") in ours:
        rates, st, spikes = ours[("630", "sugar_100Hz")]
        top = rates.sort_values("rate_hz", ascending=False).index[:60].tolist()
        for f in (MN9C, MN9I):
            if f not in top:
                top.append(f)
        sp = spikes[(spikes.trial == 0) & spikes.flywire_id.isin(top)]
        pos = {f: k for k, f in enumerate(top)}
        fig, ax = plt.subplots(figsize=(8, 6))
        sugar = set(sm.SUGAR_R_630)
        colors = [PAPER_C if f in (MN9C, MN9I) else (MUTED if f in sugar else OURS_C) for f in sp.flywire_id]
        ax.scatter(sp.t * 1000, [pos[f] for f in sp.flywire_id], s=2, c=colors, marker="|", linewidths=0.8)
        ax.set_ylim(len(top), -1)
        ax.set_yticks([pos[MN9C], pos[MN9I]], ["MN9 contra", "MN9 ipsi"])
        ax.set_xlabel("time (ms)")
        ax.set_ylabel("the 60 most active neurons (sugar sensors grey, others blue)")
        ax.set_title("Sugar sensors driven at 100 Hz: one 1-second trial (snapshot 630)", loc="left", color=INK)
        fig.tight_layout()
        fig.savefig(PLOTS / "raster_sugar_100Hz.png", dpi=150)
        plt.close(fig)
    print("plots in", PLOTS)


if __name__ == "__main__":
    main()
