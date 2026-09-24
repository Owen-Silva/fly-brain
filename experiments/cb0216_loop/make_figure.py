"""The one figure for docs/cb0216-loop.md (PRELIMINARY).

Left: firing rate (50 ms bins) of the two CB0216 neurons and the two MN9
motor neurons, default model, 1 s of touch-sensor (mechanosensory) input at
100 Hz, then 5 s with no input at all (seed 0).
Right: rate of the pair in the last second after input off, against the number
of synapses in each direction of their mutual connection (set by hand; the
rest of the brain unchanged); single kick and 1 s touch input, seeds 0-2.
Marked: FlyWire's count (451/455) and BANC's (205/237).
Writes results/fig_cb0216_loop.png.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import lib_cb as C  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False})

fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.5, 1]})
fig.patch.set_facecolor("#fcfcfb")

tr = np.load(C.RESULTS / "trace_mech100.npz")
on_s = float(tr["on_ms"]) / 1000


def smooth(x, k=5):   # 20 ms bins -> 100 ms running mean (no zero padding at the ends)
    return pd.Series(x).rolling(k, center=True, min_periods=1).mean().to_numpy()


t = (np.arange(tr["cb_right"].size) + 0.5) * 0.02
cb = (tr["cb_right"] + tr["cb_left"]) / 2
mn = (tr["mn9_left"] + tr["mn9_right"]) / 2
a1.axvspan(0, on_s, color=GRID, lw=0)
a1.text(on_s / 2, 185, "touch input on", ha="center", color=INK2, fontsize=8)
a1.text(on_s + 0.1, 185, "all input off", ha="left", color=INK2, fontsize=8)
a1.plot(t, smooth(cb), color=BLUE, lw=2)
a1.plot(t, smooth(mn), color=ORANGE, lw=2)
a1.text(t[-1], 165, "CB0216 pair (mean)", ha="right", color=INK, fontsize=8)
a1.text(t[-1], 92, "MN9 proboscis motor neurons (mean)", ha="right",
        color=INK, fontsize=8)
a1.set_xlim(0, t[-1])
a1.set_ylim(0, 200)
a1.set_xlabel("time (s)")
a1.set_ylabel("firing rate (Hz)")
a1.set_title("Default model: the pair never switches off", loc="left", color=INK, fontsize=10)
a1.grid(axis="y", color=GRID, lw=0.8)

w = pd.read_csv(C.RESULTS / "weight_scan.csv")
w["pair_hz"] = w[["cb_right_last1s_hz", "cb_left_last1s_hz"]].mean(axis=1)
d = w[w.input == "single_kick_right"].groupby("mutual_syn").pair_hz.mean().sort_index()
a2.plot(d.index, d.values, color=BLUE, lw=2, marker="o", ms=6, label="one spike in one CB0216",
        markeredgecolor="#fcfcfb", markeredgewidth=1.5, zorder=2)
d = w[w.input == "mech100"]
a2.plot(d.mutual_syn * 1.04, d.pair_hz, ls="none", color=ORANGE, marker="s", ms=6,
        label="1 s touch input (each of 3 seeds)", markeredgecolor="#fcfcfb",
        markeredgewidth=1.5, zorder=3)
for x, txt in ((453, "FlyWire\n451/455"), (221, "BANC\n205/237")):
    a2.axvline(x, color=INK2, lw=0.8, ls=":")
    a2.text(x, 175, txt, ha="center", va="top", color=INK2, fontsize=7.5,
            bbox=dict(fc="#fcfcfb", ec="none", pad=1))
a2.set_xscale("log")
a2.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
a2.set_xticks([20, 30, 50, 100, 200, 450])
a2.set_xticklabels(["20", "30", "50", "100", "200", "450"])
a2.set_ylim(-5, 200)
a2.set_xlabel("synapses each way between the two CB0216 (set by hand)", fontsize=8.5)
a2.set_ylabel("pair rate, last 1 s after input off (Hz)")
a2.set_title("How strong the link must be", loc="left", color=INK, fontsize=10)
a2.grid(axis="y", color=GRID, lw=0.8)
a2.legend(frameon=False, fontsize=8, loc="center left")
for ax in (a1, a2):
    ax.set_facecolor("#fcfcfb")
fig.text(0.01, 0.01, "PRELIMINARY. Fast engine, fix al_ln_literature, snapshot 630.",
         color=INK2, fontsize=7)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(C.RESULTS / "fig_cb0216_loop.png", dpi=150, facecolor=fig.get_facecolor())
print("wrote results/fig_cb0216_loop.png")
