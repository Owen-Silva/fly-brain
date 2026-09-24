"""Summarise the paper's own grooming output (the pre-registered targets).

Plain English
-------------
Reads the authors' result files fetched by fetch_published.py and writes the
numbers our re-runs will be compared against:

* aBN1 firing vs stimulation rate for JO-CE, JO-F, and JO-F with the three
  inhibitory neurons silenced (Fig. 5g, Ext. Data Fig. 4c);
* the firing of aBN1, aBN2 ("Descending BN2_3"), aDN1 and aDN2 when all 146
  JONs are driven (Fig. 5b / Supp. Table 7A);
* "sufficiency" (Fig. 5c): which of the 300 most JON-responsive neurons,
  driven ALONE, make aDN1 fire (> 0 Hz and > 2 Hz at any rate 25-200 Hz);
* "necessity" (Fig. 5d): which of the 300, when silenced while all JONs fire
  at 140 Hz, cut aDN1 by more than 20% (relative to the no-silencing rate,
  as in Supp. Table 7D's "Normalized" columns).

Output: results/published_summary.json and results/published_top300.csv
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ids  # noqa: E402

PUB = HERE / "results" / "published" / "results"
OUT = HERE / "results"
NAMED = {ids.ABN1: "aBN1", ids.ADN1: "aDN1", ids.ADN2: "aDN2",
         720575940611163610: "aBN2 (Descending BN2_3)"}


def _curve(path, prefix):
    s = pd.read_csv(path, index_col=0).iloc[:, 0]
    s = s[s.index.str.startswith(prefix)]
    rate = s.index.str.extract(r"_(\d+)Hz$")[0].astype(int).to_numpy()
    return {int(r): float(v) for r, v in sorted(zip(rate, s.to_numpy()))}


def main():
    out = {}
    out["aBN1_JO_CE"] = _curve(PUB / "figure_5/data/fig_5g_JON_CE_rate.csv", "JON_CE_")
    out["aBN1_JO_CE_sd"] = _curve(PUB / "figure_5/data/fig_5g_JON_CE_std.csv", "JON_CE_")
    out["aBN1_JO_F"] = _curve(PUB / "figure_5/data/fig_5g_JON_F_rate.csv", "JON_F_")
    out["aBN1_JO_F_sd"] = _curve(PUB / "figure_5/data/fig_5g_JON_F_std.csv", "JON_F_")
    out["aBN1_JO_F_3silenced"] = _curve(PUB / "figure_s5/fig_s5c_JON_F_silenced_rate.csv",
                                        "JON_F_Three_Silenced_")
    out["aBN1_JO_F_3silenced_sd"] = _curve(PUB / "figure_s5/fig_s5c_JON_F_silenced_.csv",
                                           "JON_F_Three_Silenced_")

    # all JONs (Fig. 5b): every neuron that fired, 11 rates
    b = pd.read_csv(PUB / "figure_5/fig_5b_rate.csv", index_col=0)
    cols = sorted([c for c in b.columns if c.startswith("JON_All_")],
                  key=lambda c: int(re.search(r"(\d+)Hz", c).group(1)))
    b = b[cols]
    b.columns = [int(re.search(r"(\d+)Hz", c).group(1)) for c in cols]
    out["all_JON_n_neurons_fired_any_rate"] = int((b.max(axis=1) > 0).sum())
    out["all_JON_n_non_JON_fired_at_220"] = int(((b[220] > 0) & ~b.index.isin(ids.JON_ALL)).sum())
    out["all_JON_named"] = {NAMED[i]: {int(k): float(v) for k, v in b.loc[i].items()}
                            for i in NAMED if i in b.index}

    # top-300 list: the neurons the paper activated / silenced one by one
    c100 = pd.read_csv(PUB / "figure_5/fig_5c_100_hz_rate.csv", index_col=0).iloc[:, 0]
    top300 = [int(re.search(r"_(\d{18})$", n).group(1)) for n in c100.index]
    assert len(top300) == 300 and len(set(top300)) == 300

    # sufficiency (Fig. 5c): aDN1 rate when each is driven alone
    suf = {}
    for f in [25, 50, 75, 100, 125, 150, 175, 200]:
        s = pd.read_csv(PUB / f"figure_5/fig_5c_{f}_hz_rate.csv", index_col=0).iloc[:, 0]
        s.index = [int(re.search(r"_(\d{18})$", n).group(1)) for n in s.index]
        suf[f] = s
    suf = pd.DataFrame(suf).reindex(top300)
    # aDN2 (Ext. Data Fig. 4a)
    suf2 = {}
    for f in [25, 50, 75, 100, 125, 150, 175, 200]:
        s = pd.read_csv(PUB / f"figure_s4/fig_s4a_{f}_hz_rate.csv", index_col=0).iloc[:, 0]
        s.index = [int(re.search(r"_(\d{18})$", n).group(1)) for n in s.index]
        suf2[f] = s
    suf2 = pd.DataFrame(suf2).reindex(top300)

    # necessity (Fig. 5d): aDN1 with all JONs at 140-180 Hz, each silenced
    nec = {}
    for f in [140, 150, 160, 170, 180]:
        s = pd.read_csv(PUB / f"figure_5/fig_5d_{f}_hz_rate.csv", index_col=0).iloc[:, 0]
        s.index = [int(re.search(r"silencing(\d{18})_", n).group(1)) for n in s.index]
        nec[f] = s
    nec = pd.DataFrame(nec).reindex(top300)
    nec2 = {}
    for f in [140, 150, 160, 170, 180]:
        s = pd.read_csv(PUB / f"figure_s4/fig_s4b_{f}_hz_rate.csv", index_col=0).iloc[:, 0]
        s.index = [int(re.search(r"silencing(\d{18})_", n).group(1)) for n in s.index]
        nec2[f] = s
    nec2 = pd.DataFrame(nec2).reindex(top300)

    base_adn1_140 = float(b.loc[ids.ADN1, 140])
    base_adn2_140 = float(b.loc[ids.ADN2, 140])
    t = pd.DataFrame({"root_id": top300})
    t["name"] = [NAMED.get(i, "JON" if i in ids.JON_ALL else "") for i in top300]
    t["all_JON_220Hz_rate"] = b.reindex(top300)[220].to_numpy()
    t["suff_aDN1_max_hz"] = suf.max(axis=1).to_numpy()
    t["suff_aDN1_at_200"] = suf[200].to_numpy()
    t["suff_aDN2_max_hz"] = suf2.max(axis=1).to_numpy()
    t["nec_aDN1_140"] = nec[140].to_numpy()
    t["nec_aDN1_140_norm"] = (nec[140] / base_adn1_140).to_numpy()
    t["nec_aDN2_140"] = nec2[140].to_numpy()
    t["nec_aDN2_140_norm"] = (nec2[140] / base_adn2_140).to_numpy()
    t.to_csv(OUT / "published_top300.csv", index=False)

    out["all_JON_aDN1_140"] = base_adn1_140
    out["all_JON_aDN2_140"] = base_adn2_140
    others = t[t.root_id != ids.ADN1]
    out["sufficient_aDN1_gt0"] = others[others.suff_aDN1_max_hz > 0][["root_id", "name", "suff_aDN1_max_hz"]].to_dict("records")
    out["sufficient_aDN1_gt2"] = others[others.suff_aDN1_max_hz > 2][["root_id", "name", "suff_aDN1_max_hz"]].to_dict("records")
    out["required_aDN1_lt0.8_at140"] = others[others.nec_aDN1_140_norm < 0.8][["root_id", "name", "nec_aDN1_140_norm"]].to_dict("records")
    others2 = t[t.root_id != ids.ADN2]
    out["sufficient_aDN2_gt0"] = others2[others2.suff_aDN2_max_hz > 0][["root_id", "name", "suff_aDN2_max_hz"]].to_dict("records")
    out["required_aDN2_lt0.8_at140"] = others2[others2.nec_aDN2_140_norm < 0.8][["root_id", "name", "nec_aDN2_140_norm"]].to_dict("records")
    (OUT / "published_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = main()
    for k in ["sufficient_aDN1_gt0", "sufficient_aDN1_gt2", "required_aDN1_lt0.8_at140",
              "sufficient_aDN2_gt0", "required_aDN2_lt0.8_at140"]:
        print(k, [(r["root_id"], r["name"], round(list(r.values())[-1], 3)) for r in o[k]])
    print("all-JON named:", {k: {r: round(v, 1) for r, v in d.items() if r in (100, 140, 220)} for k, d in o["all_JON_named"].items()})
    print("n fired:", o["all_JON_n_neurons_fired_any_rate"], "non-JON at 220:", o["all_JON_n_non_JON_fired_at_220"])
