"""Read the paper's own supplementary tables (Shiu et al. 2024, Nature,
Supplementary Tables 1-12, file 41586_2024_7763_MOESM2_ESM.xlsx from
static-content.springer.com). The sheets we need were converted to CSV and
saved in ``paper_reference/``:

* ST1B: MN9 firing when each of the paper's top-200 sugar-responsive neurons
  is stimulated on its own (25-200 Hz).
* ST1C: the paper's silencing screen. Sugar GRNs driven at 50-120 Hz while
  each of the top-200 neurons is silenced; MN9 rate, its s.d., and the rate
  normalised to the unsilenced control.
* ST2: the ten named cell types from the earlier experimental work
  (Shiu, Sterne et al. 2022) with the paper's model predictions.

Neuron IDs are parsed as Python ints (int64), never floats.
"""
import csv
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REF = HERE / "paper_reference"
FREQS_1C = [50, 60, 70, 80, 90, 100, 110, 120]
FREQS_1B = [25, 50, 75, 100, 125, 150, 175, 200]


def _rows(name):
    with open(REF / name, encoding="utf-8") as f:
        return list(csv.reader(f))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def st1c():
    """Paper silencing screen: one row per silenced neuron (200 rows).
    Columns: root_id (int64), paper_name, rate_<f>, sd_<f>, norm_<f>."""
    rows = _rows("paper_ST1C_sugar_top200_silencing.csv")
    out = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        r = r + [""] * (40 - len(r))
        d = {"root_id": int(r[0]), "paper_name": r[1]}
        for k, f in enumerate(FREQS_1C):
            d[f"rate_{f}"] = _num(r[2 + k])
            d[f"sd_{f}"] = _num(r[11 + k])
            d[f"norm_{f}"] = _num(r[20 + k])
        out.append(d)
    df = pd.DataFrame(out)
    df["root_id"] = df["root_id"].astype(np.int64)
    return df


def st1b():
    """Paper activation screen: MN9 rate when each top-200 neuron is
    stimulated alone. Columns: root_id, paper_name, act_<f>."""
    rows = _rows("paper_ST1B_sugar_top200_activation.csv")
    out = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        d = {"root_id": int(r[0]), "paper_name": r[1]}
        for k, f in enumerate(FREQS_1B):
            d[f"act_{f}"] = _num(r[2 + k])
        out.append(d)
    df = pd.DataFrame(out)
    df["root_id"] = df["root_id"].astype(np.int64)
    return df


def st2():
    rows = _rows("paper_ST2_sugar_named_celltypes.csv")
    return pd.DataFrame(rows[1:], columns=rows[0])


if __name__ == "__main__":
    c = st1c()
    print(len(c), c["root_id"].dtype, c[["paper_name", "rate_100", "norm_100", "norm_50"]].head())
    print("min norm_100:", c["norm_100"].min(), "rows with any norm<=0.8:",
          int((c[[f"norm_{f}" for f in FREQS_1C]] <= 0.8).any(axis=1).sum()))
    b = st1b()
    print(len(b), "activators (act_200>0):", int((b["act_200"] > 0).sum()))
