"""Print the Markdown tables used in docs/phase5-sugar-pathway.md (and save
them to results/tables.md), straight from the result CSVs, so no number in
the write-up is typed by hand."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE / "results"


def md(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else
                                     (f"{v:.2f}" if isinstance(v, float) else str(v)) for v in r) + " |")
    return "\n".join(out)


def name(r):
    for k in ("paper_name", "cell_type"):
        v = r.get(k)
        if isinstance(v, str) and v:
            return v
    return "unlabelled"


def main():
    s = pd.read_csv(RES / "silencing_singles.csv")
    s["neuron"] = [f"{name(r)} (...{str(r['root_id'])[-6:]})" for _, r in s.iterrows()]
    s["sign"] = np.where(s["ref_sign"] > 0, "exc", "inh")
    parts = []
    # class counts
    cc = s.groupby(["stim_hz", "class"]).size().unstack(fill_value=0)
    parts.append("### Class counts (single neurons)\n\n" + md(cc.reset_index()))
    for hz in (100, 50):
        x = s[s["stim_hz"] == hz]
        pcol = f"paper_ratio_{hz}hz"
        keep = x[x["class"] != "redundant"].sort_values("ratio")
        t = keep[["neuron", "cell_type", "sign", "n_trials", "mn9_hz", "ratio", "q_bh", "class", pcol]].copy()
        t.columns = ["neuron", "FlyWire type", "sign", "trials", "MN9 Hz", "ours (x baseline)", "q (BH)",
                     "class", "paper (x control)"]
        t["q (BH)"] = [f"{q:.1g}" for q in t["q (BH)"]]
        parts.append(f"### Non-redundant single neurons at {hz} Hz (baseline MN9 "
                     f"{x.loc[x['n_trials'] == 30, 'mn9_base_hz'].iloc[0]:.1f} Hz)\n\n" + md(t))
    # named cell types vs paper ST2 (paper's 50 Hz value)
    st2 = pd.read_csv(HERE / "paper_reference" / "paper_ST2_sugar_named_celltypes.csv")
    rows = []
    g = pd.read_csv(RES / "silencing_groups.csv") if (RES / "silencing_groups.csv").exists() else pd.DataFrame()
    for _, r in st2.iterrows():
        nm = r["Neuron Name"]
        if nm == "MN9":
            continue
        key = nm.lower().replace("-", "_")
        mem = s[s["paper_name"].fillna("").str.lower().str.replace("-", "_").str.startswith(key)]
        m50 = mem[mem["stim_hz"] == 50]
        m100 = mem[mem["stim_hz"] == 100]
        gname = f"named-{nm.replace('-', '-')}"
        g50 = g[(g["stim_hz"] == 50) & g["cond_id"].str.endswith(gname)] if not g.empty else g
        g100 = g[(g["stim_hz"] == 100) & g["cond_id"].str.endswith(gname)] if not g.empty else g
        rows.append({
            "cell type": nm,
            "required in real flies? (ST2)": r["Required for proboscis extension to 50 mM Sucrose?"].split(" (")[0],
            "paper model, 50 Hz": float(r["Change to MN9 as a result of silencing, 50 Hz Sugar"]),
            "ours single, 50 Hz (lowest member)": m50["ratio"].min() if len(m50) else np.nan,
            "ours all members, 50 Hz": g50["ratio"].iloc[0] if len(g50) else np.nan,
            "ours single, 100 Hz (lowest)": m100["ratio"].min() if len(m100) else np.nan,
            "ours all members, 100 Hz": g100["ratio"].iloc[0] if len(g100) else np.nan,
        })
    parts.append("### The paper's named cell types (Supp. Table 2) side by side\n\n" + md(pd.DataFrame(rows)))
    if not g.empty:
        t = g[g["source"].isin(["named", "pathway", "topk"])][["label", "stim_hz", "n_silenced", "ratio",
                                                               "q_bh", "class"]].copy()
        t["q_bh"] = [f"{q:.1g}" for q in t["q_bh"]]
        parts.append("### Group silencing (named, pathway, top-k)\n\n" + md(t))
        ct = g[g["source"] == "celltype"]
        t = ct[ct["class"] != "redundant"][["label", "stim_hz", "n_trials", "ratio", "q_bh", "class",
                                            "lowest_single_ratio", "all_members_singly_redundant"]].copy()
        t["q_bh"] = [f"{q:.1g}" for q in t["q_bh"]]
        parts.append(f"### Cell-type groups that are not redundant ({len(t)} of {len(ct)})\n\n" + md(t))
    if (RES / "robustness_summary.csv").exists():
        rb = pd.read_csv(RES / "robustness_summary.csv")
        t = rb[["base_cond", "label", "stim_hz", "ratio_seed0", "ratios_seeds123", "class_seed0",
                "same_class_all_4_seeds"]]
        parts.append("### Robustness: seeds 1, 2, 3 (each against its own baseline)\n\n" + md(t))
    txt = "\n\n".join(parts) + "\n"
    (RES / "tables.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
