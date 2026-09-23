"""Phase 1: run the toy network and save the two plots.

Run from the project folder:
    .venv\\Scripts\\python.exe experiments\\phase1\\run_phase1.py

Saves, next to this file:
    raster.png         which neuron fired when, in four input conditions
    voltage_trace.png  one neuron's voltage charging up and resetting
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # draw straight to files, no window
import matplotlib.pyplot as plt  # noqa: E402
from brian2 import mV, ms  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from sim.toy_network import REFERENCE_PARAMS, run_toy_network  # noqa: E402

SEED = 1
DURATION = 500 * ms

# Colours: blue = excitatory, orange = inhibitory (checked colour-blind safe).
EXC_COLOR = "#2a78d6"
INH_COLOR = "#eb6834"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10,
})

CONDITIONS = [
    ("No input at all", False, "none"),
    ("Background input only (the baseline)", True, "none"),
    ("Background + EXCITATORY test input", True, "excitatory"),
    ("Background + INHIBITORY test input", True, "inhibitory"),
]


def plot_raster(results):
    fig, axes = plt.subplots(len(results), 1, figsize=(9, 10), sharex=True)
    for ax, (title, res) in zip(axes, results):
        inh = res.is_inhibitory[res.spike_neurons]
        ax.scatter(res.spike_times_ms[~inh], res.spike_neurons[~inh], s=4,
                   color=EXC_COLOR, linewidths=0, label="excitatory neuron")
        ax.scatter(res.spike_times_ms[inh], res.spike_neurons[inh], s=4,
                   color=INH_COLOR, linewidths=0, label="inhibitory neuron")
        ax.set_title(f"{title}: {res.n_spikes} spikes, "
                     f"average {res.mean_rate_hz:.1f} spikes per second "
                     f"per neuron", loc="left", fontsize=10, color=INK)
        ax.set_ylim(-2, len(res.is_inhibitory) + 1)
        ax.set_xlim(0, res.duration_ms)
        ax.set_ylabel("Neuron number")
    axes[-1].set_xlabel("Time (milliseconds)")
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=lab)
               for c, lab in [(EXC_COLOR, "excitatory neurons (0-79)"),
                              (INH_COLOR, "inhibitory neurons (80-99)")]]
    fig.legend(handles=handles, loc="upper right", ncol=2, frameon=False)
    fig.suptitle("Spike raster: each dot is one neuron firing once",
                 x=0.01, ha="left", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out = HERE / "raster.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_voltage(res, window_ms=250):
    v_th = float(REFERENCE_PARAMS["v_th"] / mV)
    v_rest = float(REFERENCE_PARAMS["v_0"] / mV)
    keep = res.voltage_time_ms <= window_ms
    t, v = res.voltage_time_ms[keep], res.voltage_mV[keep]
    own = res.spike_times_ms[(res.spike_neurons == res.voltage_neuron)
                             & (res.spike_times_ms <= window_ms)]

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axhline(v_th, color=MUTED, ls="--", lw=1)
    ax.axhline(v_rest, color=MUTED, ls=":", lw=1)
    ax.plot(t, v, color=EXC_COLOR, lw=1.5)
    # The model resets instantly, so the recorded voltage never shows the spike
    # itself. Draw a short upward tick at each spike time to mark it.
    ax.vlines(own, v_th, v_th + 3, color=EXC_COLOR, lw=1.5)
    ax.text(window_ms, v_th + 0.3, "threshold (-45 mV): fires here",
            ha="right", va="bottom", color=INK_2, fontsize=9)
    ax.text(window_ms, v_rest - 0.3, "rest and reset level (-52 mV)",
            ha="right", va="top", color=INK_2, fontsize=9)
    if len(own) and own[0] > 30:
        # Label the first climb, placed under the curve halfway to the spike.
        mid = own[0] / 2
        ax.text(mid, v[t <= mid][-1] - 1.2, "charging up", ha="left",
                va="top", color=INK_2, fontsize=9)
    if len(own):
        ax.annotate("spike, then instant reset", xy=(own[0], v_th + 3),
                    xytext=(own[0] + 12, v_th + 4.2), color=INK_2, fontsize=9,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set_xlim(0, window_ms)
    ax.set_ylim(v_rest - 3, v_th + 5.5)
    ax.set_xlabel("Time (milliseconds)")
    ax.set_ylabel("Voltage (millivolts)")
    ax.set_title(f"Voltage of neuron {res.voltage_neuron} with background "
                 f"input: {len(own)} spikes in the first {window_ms} ms",
                 loc="left", fontsize=11)
    fig.tight_layout()
    out = HERE / "voltage_trace.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def main():
    results = []
    for title, background, input_type in CONDITIONS:
        res = run_toy_network(input_type, background, DURATION, SEED)
        results.append((title, res))
        print(f"{title:40s} {res.n_spikes:5d} spikes, "
              f"{res.mean_rate_hz:5.1f} Hz per neuron")
    print("saved", plot_raster(results))
    print("saved", plot_voltage(results[1][1]))


if __name__ == "__main__":
    main()
