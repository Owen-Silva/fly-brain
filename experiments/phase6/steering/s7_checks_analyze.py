"""Phase 6 steering check: tables from s6_checks.py.

Plain English
-------------
* graded_table.csv: when both antennae smell (150/150, 150/100, 100/150 Hz), what
  do the steering pairs say? "turn" = left rate minus right rate (Hz); a working
  read-out turns toward the stronger side: positive for 150/100, negative for 100/150.
  "correct_50ms" = fraction of 50 ms windows (the body loop's window) in which the
  turn has the right sign, counting windows with no spikes on either side as wrong;
  "silent_50ms" = fraction of windows with no spike on either side.
* robustness_table.csv: DA1 left-only vs right-only smell under w_syn 90%/110%,
  a weaker 75 Hz input, and with the il3LN6 local neurons silenced.
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RES = HERE / "results"
CHK = RES / "checks"
PAIRS = ["DNa02", "DNa01", "DNpe002", "DNb05", "DNge041", "DNae007"]


def pair_cols():
    n = pd.read_parquet(ROOT / "data/cache/connectome_630_neurons.parquet",
                        columns=["root_id", "cell_type", "hemibrain_type", "side"]).set_index("root_id")
    ids = np.load(RES / "sim" / "dn_root_ids.npy")
    lab = n.reindex(ids)
    t = lab.cell_type.astype(object).where(lab.cell_type.notna(), lab.hemibrain_type.astype(object)).fillna("")
    s = lab.side.astype(object).fillna("")
    fixed = {"DNa01": (720575940623860202, 720575940644438551)}  # DNa01 by ID (label differs by side in 630)
    out = {}
    for p in PAIRS:
        if p in fixed:
            out[p] = ([int(np.flatnonzero(ids == fixed[p][0])[0])], [int(np.flatnonzero(ids == fixed[p][1])[0])])
        else:
            out[p] = (np.flatnonzero(((t == p) & (s == "left")).to_numpy()),
                      np.flatnonzero(((t == p) & (s == "right")).to_numpy()))
    return out


def main():
    cols = pair_cols()
    rows = []
    for g in ("DA1", "DM1"):
        for rl, rr in ((150, 150), (150, 100), (100, 150)):
            fs = [CHK / f"graded_{g}_L{rl}_R{rr}_s{sd}.npz" for sd in (0, 1, 2)]
            if not all(f.exists() for f in fs):
                continue
            D = [np.load(f) for f in fs]
            want = 0 if rl == rr else (1 if rl > rr else -1)
            for p in PAIRS:
                L, R = cols[p]
                tl = np.concatenate([d["dn"][:, L].mean(1) for d in D])
                tr = np.concatenate([d["dn"][:, R].mean(1) for d in D])
                row = dict(glomerulus=g, left_hz_in=rl, right_hz_in=rr, pair=p,
                           left_dn_hz=round(float(tl.mean()), 2), right_dn_hz=round(float(tr.mean()), 2),
                           turn=round(float((tl - tr).mean()), 2),
                           turn_per_seed="/".join(f"{(d['dn'][:, L].mean(1) - d['dn'][:, R].mean(1)).mean():.1f}"
                                                   for d in D))
                if f"{p}_L" in D[0].files:
                    bl = np.concatenate([d[f"{p}_L"] for d in D]).astype(float)
                    br = np.concatenate([d[f"{p}_R"] for d in D]).astype(float)
                    diff = bl - br
                    row["silent_50ms"] = round(float(((bl + br) == 0).mean()), 3)
                    if want:
                        row["correct_50ms"] = round(float((np.sign(diff) == want).mean()), 3)
                rows.append(row)
    gt = pd.DataFrame(rows)
    gt.to_csv(RES / "graded_table.csv", index=False)
    # per-trial stats for DA1 gradients: d' between 150/100 and 100/150, share of 1 s trials right
    st = []
    for p in ("DNa02", "DNpe002", "DNb05", "DNge041"):
        L, R = cols[p]
        def turns(rl, rr):
            return np.concatenate([(lambda d: d["dn"][:, L].mean(1) - d["dn"][:, R].mean(1))(
                np.load(CHK / f"graded_DA1_L{rl}_R{rr}_s{sd}.npz")) for sd in (0, 1, 2)])
        try:
            a, b, c = turns(150, 100), turns(100, 150), turns(150, 150)
        except FileNotFoundError:
            break
        sd_ = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
        st.append(dict(pair=p, turn_150_100=round(a.mean(), 1), turn_100_150=round(b.mean(), 1),
                       turn_equal=round(c.mean(), 1), dprime_1s=round((a.mean() - b.mean()) / sd_, 2),
                       trials_correct_150_100=round((a > 0).mean(), 2), trials_correct_100_150=round((b < 0).mean(), 2)))
    if st:
        pd.DataFrame(st).to_csv(RES / "graded_trial_stats_DA1.csv", index=False)
    rob = []
    for tag in ("wsyn90", "wsyn110", "rate75", "il3LN6off"):
        fl, fr = CHK / f"{tag}_DA1_left_s0.npz", CHK / f"{tag}_DA1_right_s0.npz"
        if not (fl.exists() and fr.exists()):
            continue
        a, b = np.load(fl), np.load(fr)
        for p in ("DNa02", "DNa01", "DNpe002", "DNb05"):
            L, R = cols[p]
            rob.append(dict(condition=tag, pair=p,
                            left_odor_L=round(float(a["dn"][:, L].mean()), 2), left_odor_R=round(float(a["dn"][:, R].mean()), 2),
                            right_odor_L=round(float(b["dn"][:, L].mean()), 2), right_odor_R=round(float(b["dn"][:, R].mean()), 2),
                            turn_left_odor=round(float(a["dn"][:, L].mean() - a["dn"][:, R].mean()), 2),
                            turn_right_odor=round(float(b["dn"][:, L].mean() - b["dn"][:, R].mean()), 2)))
    rb = pd.DataFrame(rob)
    rb["mirror"] = (rb.turn_left_odor > 0) & (rb.turn_right_odor < 0) if len(rb) else []
    rb.to_csv(RES / "robustness_table.csv", index=False)
    pd.set_option("display.width", 220)
    print(gt.to_string(index=False))
    print(rb.to_string(index=False))


if __name__ == "__main__":
    main()
