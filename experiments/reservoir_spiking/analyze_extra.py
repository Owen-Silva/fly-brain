"""The +/-20% synapse-weight check and the exploratory 5 ms-bin run.

Writes results/wsyn_check.csv and results/bin5_verdicts.csv and prints both.
"""
import pandas as pd

import lib_spk as L
import analyze as ranalyze
from analyze_spk import best_settings

TASKS = ranalyze.TASKS
pd.set_option("display.width", 220)
KEEP = ["network", "wsyn", "readout", "N", "mc", "narma_nrmse", "xor_acc"]


def head_rows(g):
    return g[(g.noise == 0) & ((g.readout == "DN") | (g.N == 1000))]


# --- +/-20% synapse weight, seed 0, 400 Hz
main = pd.read_csv(L.RESULTS / "main_grid.csv")
m0 = main[(main.seed == 0) & (main.peak_hz == 400) & (main.wsyn == 1.0)]
w = pd.read_csv(L.RESULTS / "wsyn_grid.csv")
ws = pd.concat([head_rows(m0), head_rows(w)])[KEEP].sort_values(["readout", "wsyn", "network"])
act = pd.concat([pd.read_csv(L.RESULTS / "main_activity.csv").query("seed == 0 and peak_hz == 400"),
                 pd.read_csv(L.RESULTS / "wsyn_activity.csv")])
act = act[["network", "wsyn", "frac_active", "mean_rate_hz", "frac_gt_100hz", "dn_frac_active",
           "pop_off_late_hz", "runaway"]]
ws = ws.merge(act, on=["network", "wsyn"])
# does the real network stay below both controls on each measure?
rank = []
for (ro, wv), d in ws.groupby(["readout", "wsyn"]):
    d = d.set_index("network")
    rank.append({"readout": ro, "wsyn": wv,
                 "real_lowest_mc": d.mc["real_fix"] < d.mc.drop("real_fix").min(),
                 "real_worst_narma": d.narma_nrmse["real_fix"] > d.narma_nrmse.drop("real_fix").max(),
                 "real_lowest_xor": d.xor_acc["real_fix"] < d.xor_acc.drop("real_fix").min()})
ws.to_csv(L.RESULTS / "wsyn_check.csv", index=False)
print(ws.round(3).to_string(index=False))
print(pd.DataFrame(rank).to_string(index=False))

# --- exploratory 5 ms bins, 3 seeds, 400 Hz
p = L.RESULTS / "bin5_grid.csv"
if p.exists():
    g = pd.read_csv(p)
    bs = best_settings(g)
    v = ranalyze.verdicts(bs)
    v.to_csv(L.RESULTS / "bin5_verdicts.csv", index=False)
    h = v[(v.noise == 0) & ((v.readout == "DN") | (v.N == 1000))]
    print(h[["readout", "N", "task", "real_mean", "real_range", "shuffle_mean", "shuffle_range",
             "er_mean", "er_range", "vs_shuffle", "vs_er", "overall"]].round(3).to_string(index=False))
    print("all bin5 verdicts:", v.overall.value_counts().to_dict())
    a = pd.read_csv(L.RESULTS / "bin5_activity.csv")
    print(a.groupby("network")[["frac_active", "mean_rate_hz", "runaway"]].mean().round(3))
    c = pd.read_csv(L.RAW / "bin5_mc_curves.csv", header=None)
    c = c[(c[4] == "DN") & (c[6] == 0)]
    for net, d in c.groupby(0):
        mcurve = d.iloc[:, 7:].to_numpy().mean(0)
        print(net, "memory by delay (5 ms bins):", " ".join(f"{x:.2f}" for x in mcurve[:14]))
