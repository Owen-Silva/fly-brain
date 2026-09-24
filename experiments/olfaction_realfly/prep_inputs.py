"""Step 1: real receptor responses -> per-glomerulus ORN firing rates for the model.

Sources (downloaded to data/olfaction/door/, never committed):
* DoOR.data (Muench & Galizia 2016, Sci Rep 6:21841; github.com/ropensci/DoOR.data,
  folder data/). Each receptor file (e.g. Or22a.csv) holds every published dataset for
  that receptor. The column ``Hallem.2006.EN`` is Hallem & Carlson 2006 (Cell 125:143):
  24 receptors x 110 odours, 10^-2 dilution, odour response in spikes/s with the
  spontaneous rate (row "SFR") already subtracted.
* door_mappings.csv: receptor -> glomerulus.
* door_response_matrix.csv: DoOR's consensus response (0-1 scale, all datasets merged),
  used only for the "extended" input set (glomeruli Hallem & Carlson did not test).

Outputs (experiments/olfaction_realfly/results/):
* hc_delta.csv       odours x glomeruli, Hallem & Carlson odour response (spikes/s, SFR removed)
* hc_sfr.csv         spontaneous rate per glomerulus (Hallem & Carlson)
* door_ext_delta.csv odours x extra glomeruli, DoOR consensus back-projected to spikes/s
* coverage.csv       one row per FlyWire ORN type: n ORNs, receptor, data source
* backproject_fit.json  the DoOR -> spikes/s fit and its quality
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOOR = ROOT / "data" / "olfaction" / "door"
RES = HERE / "results"
RES.mkdir(exist_ok=True)
LABELS = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"

#: Hallem & Carlson receptor -> FlyWire 630 ``hemibrain_type`` glomerulus.
#: From door_mappings.csv; two naming notes:
#: * Or35a -> DoOR "VC3". FlyWire's cell_type calls hemibrain VC3l "ORN_VC3", so VC3 -> VC3l.
#: * Or33b is co-expressed with Or47a (DM3) and with Or85a (DM5). We drive DM3 from Or47a
#:   and DM5 from Or85a (the class-defining receptors) and leave Or33b out; its responses are
#:   small (checked below) so this changes little.
HC_GLOM = {
    "Or2a": "DA4m", "Or7a": "DL5", "Or9a": "VM3", "Or10a": "DL1", "Or19a": "DC1",
    "Or22a": "DM2", "Or23a": "DA3", "Or35a": "VC3l", "Or43a": "DA4l", "Or43b": "VM2",
    "Or47a": "DM3", "Or47b": "VA1v", "Or49b": "VA5", "Or59b": "DM4", "Or65a": "DL3",
    "Or67a": "DM6", "Or67c": "VC4", "Or82a": "VA6", "Or85a": "DM5", "Or85b": "VM5d",
    "Or85f": "DL4", "Or88a": "VA1d", "Or98a": "VM5v",
}

#: DoOR glomerulus names that differ from FlyWire 630 hemibrain names, or are unsafe.
DOOR_RENAME = {"VC3": "VC3l"}
DOOR_SKIP = {"VC5"}  # Ir41a "VC5": FlyWire renames hemibrain VC5 -> VM6, VC3m -> VC5; ambiguous


def load_hc():
    rows, sfr = {}, {}
    names = {}
    for rec in list(HC_GLOM) + ["Or33b"]:
        d = pd.read_csv(DOOR / f"{rec}.csv", sep=";")
        h = d[["Name", "InChIKey", "Hallem.2006.EN"]].dropna(subset=["Hallem.2006.EN"])
        s = h[h.InChIKey == "SFR"]["Hallem.2006.EN"]
        sfr[rec] = float(s.iloc[0]) if len(s) else np.nan
        h = h[h.InChIKey != "SFR"]
        rows[rec] = h.set_index("InChIKey")["Hallem.2006.EN"].astype(float)
        names.update(dict(zip(h.InChIKey, h.Name)))
    mat = pd.DataFrame(rows)
    return mat, pd.Series(sfr), names


def orn_types():
    lab = pd.read_parquet(LABELS, columns=["super_class", "cell_class", "hemibrain_type"])
    o = lab[(lab.super_class == "sensory") & (lab.cell_class == "olfactory")
            & lab.hemibrain_type.fillna("").str.startswith("ORN_")]
    return o.hemibrain_type.str.replace("ORN_", "", regex=False).value_counts()


def main():
    mat, sfr, names = load_hc()
    print(f"Hallem & Carlson: {mat.shape[0]} odours x {mat.shape[1]} receptors "
          f"(incl. Or33b); missing values: {int(mat.isna().sum().sum())}")
    print(f"Or33b: max |response| {mat['Or33b'].abs().max():.0f} Hz, mean {mat['Or33b'].mean():.1f}")
    hc = mat[list(HC_GLOM)].rename(columns=HC_GLOM)
    hc.index.name = "inchikey"
    hc.insert(0, "odour", [names[k] for k in hc.index])
    hc.to_csv(RES / "hc_delta.csv")
    hc_sfr = sfr[list(HC_GLOM)].rename(index=HC_GLOM)
    hc_sfr.rename("sfr_hz").to_csv(RES / "hc_sfr.csv", header=True)
    print("SFR (Hz): median %.1f, range %.1f-%.1f" % (hc_sfr.median(), hc_sfr.min(), hc_sfr.max()))

    # ---- DoOR consensus, back-projected to spikes/s (extended set) --------------------
    rm = pd.read_csv(DOOR / "door_response_matrix.csv", sep=";", index_col=0)
    rm = rm - rm.loc["SFR"]          # DoOR's resetSFR: 0 = spontaneous rate
    rm = rm.drop(index="SFR")
    mp = pd.read_csv(DOOR / "door_mappings.csv", sep=";")
    mp = mp[mp["code"].notna()][["receptor", "code"]]
    glom_col = {}
    for rec, glo in zip(mp.receptor, mp.code):
        glo = DOOR_RENAME.get(glo, glo)
        if glo in DOOR_SKIP or rec not in rm.columns:
            continue
        glom_col.setdefault(glo, rec)
    # fit: Hallem delta ~ a * DoOR(reset) over the Hallem receptors x odours (pooled)
    xs, ys = [], []
    for rec, glo in HC_GLOM.items():
        if rec not in rm.columns:
            continue
        common = hc.index.intersection(rm.index)
        x = rm.loc[common, rec].to_numpy(float)
        y = hc.loc[common, glo].to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(y)
        xs.append(x[ok]); ys.append(y[ok])
    x, y = np.concatenate(xs), np.concatenate(ys)
    a = float((x @ y) / (x @ x))                     # through the origin: 0 -> 0
    r = float(np.corrcoef(x, y)[0, 1])
    fit = {"model": "hallem_delta = a * door_consensus_minus_sfr (least squares, no intercept)",
           "a_hz_per_unit": a, "pearson_r": r, "n_pairs": int(x.size)}
    print(f"DoOR back-projection: a = {a:.0f} Hz per unit, r = {r:.3f} over {x.size} pairs")
    ext = {}
    types = orn_types()
    for glo, rec in glom_col.items():
        if glo in hc.columns or glo not in types.index:
            continue
        col = rm[rec].reindex(hc.index) * a
        if col.notna().sum() == 0:
            continue
        ext[glo] = col
    ext = pd.DataFrame(ext)
    ext.insert(0, "odour", hc.odour)
    ext.to_csv(RES / "door_ext_delta.csv")
    fit["extended_glomeruli"] = {g: glom_col[g] for g in ext.columns if g != "odour"}
    fit["extended_nonmissing_per_glomerulus"] = {g: int(ext[g].notna().sum())
                                                 for g in ext.columns if g != "odour"}
    (RES / "backproject_fit.json").write_text(json.dumps(fit, indent=1))

    # ---- coverage -----------------------------------------------------------------
    rec_of = {v: k for k, v in HC_GLOM.items()}
    cov = pd.DataFrame({"n_orns": types})
    cov.index.name = "glomerulus"
    cov["hallem_receptor"] = [rec_of.get(g, "") for g in cov.index]
    cov["door_column"] = [glom_col.get(g, "") if g in ext.columns else "" for g in cov.index]
    cov["source"] = np.where(cov.hallem_receptor != "", "Hallem2006",
                             np.where(cov.door_column != "", "DoOR_backprojected", "none"))
    cov.to_csv(RES / "coverage.csv")
    for s, g in cov.groupby("source"):
        print(f"  {s}: {len(g)} glomeruli, {int(g.n_orns.sum())} ORNs")
    print("  no data:", ", ".join(cov.index[cov.source == "none"]))


if __name__ == "__main__":
    main()
