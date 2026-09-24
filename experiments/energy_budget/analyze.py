"""Turn the counted spikes into energy per decision: fly, neuromorphic chips, this laptop.

Run after run_decisions.py (both models) and validate.py. Writes (all PRELIMINARY):
  results/decision_summary.csv   spikes, neurons, synaptic events, sparsity, MN9 timing
  results/energy_per_decision.csv  every energy estimate, low / mid / high
  results/summary.json           headline numbers used in docs/energy-budget.md
  results/fig_energy_per_decision.png, results/fig_runaway_cost.png
"""
from __future__ import annotations

import json

import matplotlib
import matplotlib.ticker
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import constants as K  # noqa: E402
from common import DECISION_SPECS, MODELS, RAW, RES  # noqa: E402

LEVELS = ("low", "mid", "high")
ORDER = list(DECISION_SPECS)
SHORT = {"sugar": "Sugar -> feed", "bitter": "Bitter", "water": "Water", "smell_DA1": "Smell DA1",
         "smell_DM1": "Smell DM1", "groom_JO": "Grooming (JO)", "cool": "Cool", "warm": "Warm"}


def read_power(path):
    """typeperf CSV -> time, package mW, cores mW, total CPU % (one row per second)."""
    pw = pd.read_csv(path)
    pw.columns = ["time", "pkg_mW", "pp0_mW", "cpu_pct"]
    pw["time"] = pd.to_datetime(pw["time"], format="%m/%d/%Y %H:%M:%S.%f")
    for c in ("pkg_mW", "pp0_mW", "cpu_pct"):
        pw[c] = pd.to_numeric(pw[c], errors="coerce")
    return pw.dropna()


def timing_power(tim):
    """Mean CPU package power (W) while the timing pass ran."""
    pw = read_power(RAW / "power_timing.csv")
    t0, t1 = pd.to_datetime(tim.t_start).min(), pd.to_datetime(tim.t_end).max()
    w = pw[(pw.time >= t0) & (pw.time <= t1)]
    return float(w.pkg_mW.mean() / 1e3)


def power_windows(df):
    """Mean CPU package power (Intel RAPL counter, logged by typeperf) while each decision
    ran, and the share of all busy CPU time on the machine that was this lane's."""
    rows, base = [], {}
    for m in MODELS:
        pw = read_power(RAW / f"power_{m}.csv")
        sub = df[df.model == m]
        first = pd.to_datetime(sub.t_start).min()
        pre = pw[pw.time < first]
        base[m] = dict(pkg_W_before_runs=float(pre.pkg_mW.mean() / 1e3) if len(pre) else None,
                       pkg_W_whole_run=float(pw.pkg_mW.mean() / 1e3),
                       cpu_pct_whole_run=float(pw.cpu_pct.mean()))
        for dec, g in sub.groupby("decision"):
            t0, t1 = pd.to_datetime(g.t_start).min(), pd.to_datetime(g.t_end).max()
            w = pw[(pw.time >= t0) & (pw.time <= t1 + pd.Timedelta(seconds=1))]
            dur = (t1 - t0).total_seconds()
            p_w = w.pkg_mW.mean() / 1e3
            busy = w.cpu_pct.mean() / 100 * K.LOGICAL_CPUS * dur
            mine = g.cpu_s.sum()
            rows.append(dict(model=m, decision=dec, window_s=dur, power_samples=len(w), pkg_W=p_w,
                             cpu_busy_s=busy, lane_cpu_s=mine,
                             lane_share=float(min(1.0, mine / busy)) if busy > 0 else np.nan))
    return pd.DataFrame(rows), base


def main():
    df = pd.concat([pd.read_csv(RES / f"trials_{m}.csv") for m in MODELS], ignore_index=True)
    sizes = {m: json.loads((RES / f"model_size_{m}.json").read_text()) for m in MODELS}
    touched = pd.read_csv(RES / "neurons_touched.csv").groupby(["model", "decision"]).neurons_touched.mean()
    val = json.loads((RES / "validation.json").read_text())
    n = sizes["none"]["n_neurons"]
    steps01, steps1 = 10_000, 1_000

    # ------------------------------------------------------------------ counts ---------
    g = df.groupby(["model", "decision"])
    summ = g.agg(trials=("trial", "size"), spikes=("total_spikes", "mean"), spikes_sd=("total_spikes", "std"),
                 stim_spikes=("stim_spikes", "mean"), neurons_fired=("n_active", "mean"),
                 syn_events=("syn_events_phys", "mean"), conn_events=("conn_events", "mean"),
                 syn_events_model=("syn_events", "mean"), runaway_trials=("runaway", "sum"),
                 mn9_hz=("mn9_spikes", "mean"), abn1_hz=("abn1_spikes", "mean"),
                 wall_s_mean=("wall_total_s", "mean"), wall_s_min=("wall_total_s", "min"),
                 cpu_s_mean=("cpu_s", "mean")).reset_index()
    seed_means = df.groupby(["model", "decision", "seed"]).total_spikes.mean().unstack()
    summ["spikes_seed_a"] = [seed_means.loc[(r.model, r.decision)].iloc[0] for r in summ.itertuples()]
    summ["spikes_seed_b"] = [seed_means.loc[(r.model, r.decision)].iloc[1] for r in summ.itertuples()]
    summ["frac_fired"] = summ.neurons_fired / n
    summ["neurons_touched"] = [touched.get((r.model, r.decision), np.nan) for r in summ.itertuples()]
    summ["frac_touched"] = summ.neurons_touched / n
    summ["spikes_per_neuron_step"] = summ.spikes / (n * steps01)
    summ["conn_events_frac_of_dense"] = [r.conn_events / (sizes[r.model]["n_connections"] * steps01)
                                         for r in summ.itertuples()]
    fired_union = {}
    for m in MODELS:
        z = np.load(RAW / f"neuron_counts_{m}.npz")
        for d in ORDER:
            fired_union[(m, d)] = int((z[f"counts_{d}"] > 0).sum())
    summ["neurons_fired_any_trial"] = [fired_union[(r.model, r.decision)] for r in summ.itertuples()]
    for col in ("mn9_first_ms", "mn9_ipsi_first_ms", "abn1_first_ms"):
        summ[col + "_median"] = g[col].median().to_numpy()
        summ[col + "_q25"] = g[col].quantile(0.25).to_numpy()
        summ[col + "_q75"] = g[col].quantile(0.75).to_numpy()
    summ["decision"] = pd.Categorical(summ.decision, ORDER)
    summ = summ.sort_values(["model", "decision"]).reset_index(drop=True)
    summ["decision"] = summ.decision.astype(str)

    # ------------------------------------------------------------------ energy ---------
    pw, base = power_windows(df)
    e = summ[["model", "decision", "spikes", "syn_events", "conn_events", "neurons_fired",
              "wall_s_mean", "wall_s_min", "cpu_s_mean"]].merge(pw, on=["model", "decision"])
    for lv in LEVELS:
        atp = e.spikes * K.ATP_PER_SPIKE[lv] + e.syn_events * K.ATP_PER_SYN_EVENT[lv]
        e[f"fly_ATP_{lv}"] = atp
        e[f"fly_J_{lv}"] = atp * K.J_PER_ATP[lv]
    e["fly_share_spikes_mid"] = e.spikes * K.ATP_PER_SPIKE["mid"] / e.fly_ATP_mid
    e["fly_frac_of_brain_power_mid"] = e.fly_J_mid / (K.BRAIN_POWER_W * 1.0)

    L1, L2 = K.LOIHI1, K.LOIHI2
    clock01 = n * steps01 * L1["neuron_update_inactive_J"]
    e["loihi1_dt01_J"] = clock01 + e.spikes * (L1["neuron_update_active_J"] - L1["neuron_update_inactive_J"]) \
        + e.conn_events * L1["synop_J"]
    e["loihi1_dt1_J"] = n * steps1 * L1["neuron_update_inactive_J"] \
        + e.spikes * (L1["neuron_update_active_J"] - L1["neuron_update_inactive_J"]) + e.conn_events * L1["synop_J"]
    e["loihi2_dt1_J"] = n * steps1 * L2["neuron_update_J"] + e.conn_events * L2["synop_J"]
    e["loihi2_dt01_J"] = n * steps01 * L2["neuron_update_J"] + e.conn_events * L2["synop_J"]
    e["loihi_low_J"], e["loihi_mid_J"], e["loihi_high_J"] = e.loihi2_dt1_J, e.loihi1_dt1_J, e.loihi1_dt01_J
    e["loihi1_dt01_share_clock"] = clock01 / e.loihi1_dt01_J
    e["loihi1_synops_only_J"] = e.conn_events * L1["synop_J"]
    e["truenorth_events_J"] = e.conn_events * K.TRUENORTH["synevent_J"]
    e["spinnaker_low_J"] = e.conn_events * K.SPINNAKER["synevent_J"][0]
    e["spinnaker_high_J"] = e.conn_events * K.SPINNAKER["synevent_J"][1]
    e["gpu_low_J"] = e.conn_events * K.GPU["synevent_J"][0]
    e["gpu_high_J"] = e.conn_events * K.GPU["synevent_J"][1]
    # a clock-driven design: every neuron AND every connection handled every 0.1 ms step
    ncon = e.model.map(lambda m: sizes[m]["n_connections"])
    e["dense_dt01_J"] = n * steps01 * L1["neuron_update_inactive_J"] + ncon * steps01 * L1["synop_J"]
    e["dense_ops"] = n * steps01 + ncon * steps01
    e["loihi_style_ops"] = n * steps01 + e.conn_events
    e["event_ops"] = 2 * e.conn_events + e.spikes
    e["event_ideal_J"] = (e.conn_events + e.spikes) * L1["neuron_update_active_J"] + e.conn_events * L1["synop_J"]
    e["saving_dense_vs_loihi_style"] = e.dense_dt01_J / e.loihi1_dt01_J
    e["saving_dense_vs_event"] = e.dense_dt01_J / e.event_ideal_J
    e["saving_loihi_style_vs_event"] = e.loihi1_dt01_J / e.event_ideal_J
    # this laptop: wall time per simulated second x CPU power.
    #   fastest = quickest trial seen in any pass (least slowed by other lanes);
    #   typical = median of the back-to-back timing pass (timing.py), under shared load.
    #   low = fastest x measured package power; mid = fastest x 15 W (Intel base power);
    #   high = typical x 15 W. lane_share_J = main-run time x package power x this job's
    #   share of all busy CPU time (a lower bound that charges other lanes their part).
    tim = pd.read_csv(RES / "laptop_timing.csv")
    # Decisions whose every trial gives exactly the same spikes on both models are the same
    # computation (the fix never comes into play), so their timings are pooled across models.
    piv = df.pivot_table(index=["decision", "seed", "trial"], columns="model", values="total_spikes")
    same = {d for d, gg in piv.groupby(level=0) if (gg[MODELS[0]] == gg[MODELS[1]]).all()}
    allw = pd.concat([df[["model", "decision", "wall_total_s"]], tim[["model", "decision", "wall_total_s"]]])
    for frame in (allw, tim):
        frame["pool"] = [("both" if d in same else m) for m, d in zip(frame.model, frame.decision)]
    fastest = allw.groupby(["pool", "decision"]).wall_total_s.min()
    typical = tim.groupby(["pool", "decision"]).wall_total_s.median()
    e["same_computation_both_models"] = e.decision.isin(same)
    e["pool"] = [("both" if d in same else m) for m, d in zip(e.model, e.decision)]
    p_meas = timing_power(tim)
    e["wall_fastest_s"] = [fastest[(r.pool, r.decision)] for r in e.itertuples()]
    e["wall_typical_s"] = [typical[(r.pool, r.decision)] for r in e.itertuples()]
    e["laptop_low_J"] = e.wall_fastest_s * p_meas
    e["laptop_mid_J"] = e.wall_fastest_s * K.LAPTOP_SPEC_W["base"]
    e["laptop_high_J"] = e.wall_typical_s * K.LAPTOP_SPEC_W["base"]
    e["laptop_lane_share_J"] = e.wall_s_mean * e.pkg_W * e.lane_share

    e["decision"] = pd.Categorical(e.decision, ORDER)
    e = e.sort_values(["model", "decision"]).reset_index(drop=True)
    e["decision"] = e.decision.astype(str)
    summ.to_csv(RES / "decision_summary.csv", index=False, float_format="%.6g")
    e.to_csv(RES / "energy_per_decision.csv", index=False, float_format="%.6g")

    # ------------------------------------------------------------- headline json --------
    def row(m, d):
        return e[(e.model == m) & (e.decision == d)].iloc[0]

    runaway = {}
    for d in ("smell_DA1", "smell_DM1", "cool", "warm"):
        a, b = row("none", d), row("al_ln_literature", d)
        runaway[d] = dict(spikes_x=a.spikes / b.spikes, neurons_fired_x=a.neurons_fired / b.neurons_fired,
                          syn_events_x=a.syn_events / b.syn_events, fly_J_x=a.fly_J_mid / b.fly_J_mid,
                          loihi1_dt01_x=a.loihi1_dt01_J / b.loihi1_dt01_J,
                          loihi1_synops_x=a.loihi1_synops_only_J / b.loihi1_synops_only_J,
                          laptop_fastest_x=a.wall_fastest_s / b.wall_fastest_s,
                          laptop_typical_x=a.wall_typical_s / b.wall_typical_s,
                          published_fly_J_mid=a.fly_J_mid, fixed_fly_J_mid=b.fly_J_mid,
                          published_frac_brain_power=a.fly_frac_of_brain_power_mid)
    mean_out_syn = val["wiring_check"]["mean_out_synapses"]
    j_per_avg_spike = {lv: (K.ATP_PER_SPIKE[lv] + mean_out_syn * K.ATP_PER_SYN_EVENT[lv]) * K.J_PER_ATP[lv]
                       for lv in LEVELS}
    affordable_hz = {lv: K.BRAIN_POWER_W / j_per_avg_spike[lv] / n for lv in LEVELS}
    fx = e[e.model == "al_ln_literature"]
    sugar = summ[(summ.model == "al_ln_literature") & (summ.decision == "sugar")].iloc[0]
    out = dict(
        n_neurons=n, connections={m: sizes[m]["n_connections"] for m in MODELS},
        synapses={m: sizes[m]["n_synapses"] for m in MODELS},
        constants=dict(atp_per_spike=K.ATP_PER_SPIKE, atp_per_syn_event=K.ATP_PER_SYN_EVENT,
                       j_per_atp=K.J_PER_ATP, loihi1=K.LOIHI1, loihi2_derived=K.LOIHI2),
        j_per_average_spike_incl_synapses=j_per_avg_spike,
        brain_power_affordable_mean_rate_hz=affordable_hz,
        fixed_model_ranges=dict(
            neurons_fired=[float(fx.neurons_fired.min()), float(fx.neurons_fired.max())],
            frac_fired=[float(fx.neurons_fired.min() / n), float(fx.neurons_fired.max() / n)],
            spikes=[float(fx.spikes.min()), float(fx.spikes.max())],
            fly_J_mid=[float(fx.fly_J_mid.min()), float(fx.fly_J_mid.max())],
            loihi_mid_J=[float(fx.loihi_mid_J.min()), float(fx.loihi_mid_J.max())],
            laptop_mid_J=[float(fx.laptop_mid_J.min()), float(fx.laptop_mid_J.max())],
            laptop_high_J=[float(fx.laptop_high_J.min()), float(fx.laptop_high_J.max())],
            laptop_low_J=[float(fx.laptop_low_J.min()), float(fx.laptop_low_J.max())],
            laptop_lane_share_J=[float(fx.laptop_lane_share_J.min()), float(fx.laptop_lane_share_J.max())],
            saving_dense_vs_event=[float(fx.saving_dense_vs_event.min()), float(fx.saving_dense_vs_event.max())],
            saving_loihi_style_vs_event=[float(fx.saving_loihi_style_vs_event.min()),
                                         float(fx.saving_loihi_style_vs_event.max())],
            loihi1_dt01_share_clock=[float(fx.loihi1_dt01_share_clock.min()),
                                     float(fx.loihi1_dt01_share_clock.max())]),
        mn9_first_spike_ms_sugar=dict(median=sugar.mn9_first_ms_median, q25=sugar.mn9_first_ms_q25,
                                      q75=sugar.mn9_first_ms_q75),
        runaway_cost=runaway, laptop_power=base, laptop_measured_pkg_W_timing_pass=p_meas,
        sandia_sugar_ceiling_J=dict(
            dt01=K.SANDIA["chips"] * K.LOIHI2["max_W_per_chip"] * K.SANDIA["sugar_wall_s_dt01"],
            dt1=K.SANDIA["chips"] * K.LOIHI2["max_W_per_chip"] * K.SANDIA["sugar_wall_s_dt1"]),
        truenorth_realtime_floor_J_per_chip=K.TRUENORTH["chip_W"] * 1.0,
    )
    (RES / "summary.json").write_text(json.dumps(out, indent=1, default=float))
    constant_sensitivity(e, val)
    figures(e, summ, n)
    print(e[["model", "decision", "spikes", "neurons_fired", "fly_J_mid", "loihi_mid_J", "wall_fastest_s", "laptop_mid_J",
             "laptop_high_J", "lane_share"]].to_string(float_format=lambda v: f"{v:.3g}"))
    print(json.dumps({k: out[k] for k in ("brain_power_affordable_mean_rate_hz", "mn9_first_spike_ms_sugar",
                                          "sandia_sugar_ceiling_J", "laptop_power")}, indent=1, default=float))


def constant_sensitivity(e, val):
    """One-at-a-time: how far the fly's energy for sugar and the DM1 smell (fixed model)
    moves when ONE constant goes to its low or high value, the rest staying at mid; and when
    the model's weight per synapse is 80% / 120% (validate.py runs, seed 21)."""
    rows = []
    mid = dict(spike=K.ATP_PER_SPIKE["mid"], syn=K.ATP_PER_SYN_EVENT["mid"], j=K.J_PER_ATP["mid"])
    for d in ("sugar", "smell_DM1"):
        r = e[(e.model == "al_ln_literature") & (e.decision == d)].iloc[0]

        def energy(sp, sy, spike=mid["spike"], syn=mid["syn"], j=mid["j"]):
            return (sp * spike + sy * syn) * j
        base = energy(r.spikes, r.syn_events)
        for name, key, table in (("ATP per spike", "spike", K.ATP_PER_SPIKE),
                                 ("ATP per synaptic event", "syn", K.ATP_PER_SYN_EVENT),
                                 ("joules per ATP", "j", K.J_PER_ATP)):
            lo = energy(r.spikes, r.syn_events, **{key: table["low"]})
            hi = energy(r.spikes, r.syn_events, **{key: table["high"]})
            rows.append(dict(decision=d, varied=name, x_low=lo / base, x_high=hi / base, mid_J=base))
        w = {x["w_scale"]: x for x in val["wsyn_sensitivity_fixed_model"] if x["decision"] == d}
        w_base = energy(w[1.0]["spikes"], w[1.0]["syn_events"])
        rows.append(dict(decision=d, varied="model weight per synapse 80% / 120%",
                         x_low=energy(w[0.8]["spikes"], w[0.8]["syn_events"]) / w_base,
                         x_high=energy(w[1.2]["spikes"], w[1.2]["syn_events"]) / w_base, mid_J=base))
    pd.DataFrame(rows).to_csv(RES / "fly_energy_sensitivity.csv", index=False, float_format="%.4g")


# ------------------------------------------------------------------- figures ----------
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_CHIP, C_LAPTOP, C_FLY = "#2a78d6", "#eb6834", "#1baf7a"   # validated palette slots 1-3


def _style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=15)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def _fmt_j(v):
    for unit, f in (("J", 1), ("mJ", 1e-3), ("µJ", 1e-6), ("nJ", 1e-9), ("pJ", 1e-12)):
        if v >= f:
            return f"{v / f:.2g} {unit}"
    return f"{v:.1g} J"


def _log_ticks(ax, ticks, labels):
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=15, color=INK2)
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())


def figures(e, summ, n):
    fx = e[e.model == "al_ln_literature"].set_index("decision").loc[ORDER]
    fig, ax = plt.subplots(figsize=(7.2, 9.6), dpi=170)
    fig.patch.set_facecolor(SURF)
    _style(ax)
    ys = np.arange(len(ORDER))[::-1] * 1.0
    series = [("Fly brain", C_FLY, "fly_J_low", "fly_J_mid", "fly_J_high", 0.26),
              ("Loihi-class chip", C_CHIP, "loihi_low_J", "loihi_mid_J", "loihi_high_J", 0.0),
              ("This laptop", C_LAPTOP, "laptop_low_J", "laptop_mid_J", "laptop_high_J", -0.26)]
    for name, col, lo, mid, hi, off in series:
        y = ys + off
        ax.hlines(y, fx[lo], fx[hi], color=col, lw=5, alpha=0.9, capstyle="round")
        ax.plot(fx[mid], y, "o", ms=9, color=col, mec=SURF, mew=2, label=name)
    ax.set_xscale("log")
    ax.set_xlim(1e-10, 200)
    _log_ticks(ax, [1e-9, 1e-6, 1e-3, 1], ["1 nJ", "1 µJ", "1 mJ", "1 J"])
    ax.set_yticks(ys)
    ax.set_yticklabels([SHORT[d] for d in ORDER], fontsize=15, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Energy for one 1-second decision (log scale)", fontsize=15, color=INK)
    sug = fx.loc["sugar"]
    y0 = ys[0]
    ax.text(sug.fly_J_high * 1.6, y0 + 0.26, _fmt_j(sug.fly_J_mid), va="center", fontsize=13, color=INK)
    ax.text(sug.loihi_high_J * 1.6, y0, _fmt_j(sug.loihi_mid_J), va="center", fontsize=13, color=INK)
    ax.text(sug.laptop_low_J / 1.6, y0 - 0.26, _fmt_j(sug.laptop_mid_J), va="center", ha="right",
            fontsize=13, color=INK)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, 1.075), ncol=3, frameon=False, fontsize=13.5,
              handletextpad=0.3, columnspacing=1.0, labelcolor=INK)
    ax.set_title("Energy per decision (fixed model)", fontsize=18, color=INK, pad=34, loc="left")
    fig.text(0.02, 0.012, "Dot = middle estimate, bar = low-high range. PRELIMINARY.\n"
             "Chip = its operations only (idle power not included).", fontsize=11.5, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(RES / "fig_energy_per_decision.png", facecolor=SURF)
    plt.close(fig)

    # --- runaway cost: spikes per decision, published vs fixed (dot plot, log axis) -------
    s = summ.set_index(["model", "decision"])
    fig, ax = plt.subplots(figsize=(7.2, 8.2), dpi=170)
    fig.patch.set_facecolor(SURF)
    _style(ax)
    for i, d in enumerate(ORDER):
        y = len(ORDER) - 1 - i
        a, b = s.loc[("none", d)], s.loc[("al_ln_literature", d)]
        ratio = a.spikes / b.spikes
        ax.hlines(y, min(a.spikes, b.spikes), max(a.spikes, b.spikes), color=GRID, lw=3)
        ax.plot(a.spikes, y + 0.14, "o", ms=11, color=C_LAPTOP, mec=SURF, mew=2,
                label="Published model" if i == 0 else None)
        ax.plot(b.spikes, y - 0.14, "o", ms=11, color=C_CHIP, mec=SURF, mew=2,
                label="Fixed model" if i == 0 else None)
        txt = f"{ratio:.0f}x more" if ratio > 1.5 else "same"
        ax.text(max(a.spikes, b.spikes) * 1.5, y, txt, va="center", fontsize=14, color=INK,
                fontweight="bold" if ratio > 1.5 else "normal")
    ax.set_xscale("log")
    ax.set_xlim(3e3, 4e6)
    _log_ticks(ax, [1e4, 1e5, 1e6], ["10,000", "100,000", "1 million"])
    ax.set_yticks(range(len(ORDER)))
    ax.set_yticklabels([SHORT[d] for d in ORDER][::-1], fontsize=15, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.6, len(ORDER) - 0.4)
    ax.set_xlabel("Spikes in the whole brain per decision (log scale)", fontsize=15, color=INK)
    ax.legend(loc="upper center", bbox_to_anchor=(0.42, 1.08), ncol=2, frameon=False, fontsize=14,
              labelcolor=INK, handletextpad=0.2)
    ax.set_title("The runaway's cost", fontsize=18, color=INK, pad=36, loc="left")
    fig.text(0.02, 0.012, "Mean of 40 one-second trials (2 seeds). PRELIMINARY.", fontsize=11.5, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(RES / "fig_runaway_cost.png", facecolor=SURF)
    plt.close(fig)


if __name__ == "__main__":
    main()
