"""The price list: time and energy per operation for every part of the virtual computer.

Every constant carries a label:
  PUBLISHED - taken from a datasheet or paper (source given);
  DERIVED   - computed by simple arithmetic from published measurements (working given);
  FITTED    - fitted to published measurements (vhc/neurocal.py, vhc/workloads/pong.py);
  MEASURED  - measured on this laptop (vhc/calibrate.py writes vhc/results/x86_calibration.json);
  ASSUMED   - an engineering estimate (reason given);
  GUESSED   - no good source; a placeholder to be replaced by a measurement.

Nothing in here is tuned to make any design win. Change a number here and every result moves.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


@dataclass(frozen=True)
class Price:
    value: float
    unit: str
    label: str      # PUBLISHED / MEASURED / ASSUMED / GUESSED
    source: str


# ------------------------------------------------------------------ neuromorphic core -----
# Intel Loihi (Davies et al. 2018, IEEE Micro 38(1), Table 2, pre-silicon, 0.75 V).
# Checked against the paper's PDF on 2026-09-24.
DAVIES = "Davies et al. 2018, IEEE Micro, Table 2 (Loihi, pre-silicon)"
LOIHI = {
    "synop_J": Price(23.6e-12, "J", "PUBLISHED", DAVIES + ": energy per synaptic spike op (min)"),
    "synop_s": Price(3.5e-9, "s", "PUBLISHED", DAVIES + ": time per synaptic spike op (max)"),
    "syn_update_J": Price(120e-12, "J", "PUBLISHED", DAVIES + ": energy per synaptic update (STDP)"),
    "syn_update_s": Price(6.1e-9, "s", "PUBLISHED", DAVIES + ": time per synaptic update (STDP)"),
    "nu_active_J": Price(81e-12, "J", "PUBLISHED", DAVIES + ": energy per neuron update, active"),
    "nu_inactive_J": Price(52e-12, "J", "PUBLISHED", DAVIES + ": energy per neuron update, inactive"),
    "nu_active_s": Price(8.4e-9, "s", "PUBLISHED", DAVIES + ": time per neuron update, active"),
    "nu_inactive_s": Price(5.3e-9, "s", "PUBLISHED", DAVIES + ": time per neuron update, inactive"),
    "spike_route_J": Price(1.7e-12, "J", "PUBLISHED", DAVIES + ": within-tile spike energy"),
    "barrier_s_1tile": Price(113e-9, "s", "PUBLISHED", DAVIES + ": barrier sync, 1 tile"),
    "barrier_s_32tile": Price(465e-9, "s", "PUBLISHED", DAVIES + ": barrier sync, 32 tiles"),
    "neurons_per_core": Price(1024, "neurons", "PUBLISHED", DAVIES + ": 1,024 neural compartments per core"),
}
# Static (leakage) power of a neuromorphic core is not published per core. v0 leaves it OUT
# of the neuromorphic numbers and says so in every report.
NEURO_STATIC_W = Price(0.0, "W", "ASSUMED", "static power excluded: not published per core")

# Sandia (Wang et al. 2025, arXiv:2508.16792): whole FlyWire brain on 12 Loihi 2 chips,
# 1,440 cores, sugar experiment. Used only to CALIBRATE the timing model (vhc/neurocal.py).
SANDIA = "Wang et al. 2025 (Sandia), arXiv:2508.16792"
SANDIA_WALL_S_PER_SIM_S_DT01 = Price(53.76e-3, "s", "PUBLISHED", SANDIA + ": sugar, 0.1 ms steps (+-0.896 ms)")
SANDIA_WALL_S_PER_SIM_S_DT1 = Price(12.40e-3, "s", "PUBLISHED", SANDIA + ": sugar, 1 ms steps (+-0.279 ms)")
SANDIA_CORES = 1440
SANDIA_CHIPS = 12
SANDIA_NEURONS = 138000        # "about 0.3% of the 138K total neurons"
SANDIA_CONNECTIONS = 15e6      # "50 million synapses condensed into about 15 million weighted connections"
# Background-activity sweep (same paper, checked 2026-09-24): every neuron spikes at the given
# rate on its own (on-chip probabilistic spiking, input weights negligible). Wall seconds per
# simulated second, for 0.1 ms and 1 ms steps.
SANDIA_SWEEP_HZ = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0)
SANDIA_SWEEP_S_DT01 = (0.189, 0.277, 0.464, 0.948, 1.748, 3.216, 5.793)
SANDIA_SWEEP_S_DT1 = (0.0958, 0.178, 0.333, 0.757, 1.414, 2.627, 4.800)

# Loihi 2 extra facts for v1.
LOIHI2_CORES_PER_CHIP = Price(120, "cores", "PUBLISHED", SANDIA + ": 1,440 neurocores on 12 chips")
LOIHI2_MIN_STEP_S = Price(200e-9, "s", "PUBLISHED",
                          "Real-time continual learning on Loihi 2, arXiv:2511.01553: 'the shortest timestep possible is 200 ns'")
# Static (leakage) power of one Loihi 2 chip. Intel publishes no figure. DERIVED from Shrestha
# et al. 2024 (ICASSP; arXiv:2310.03251), Table 1, single-chip Oheo Gulch, measured with Intel
# SoC Watch: static energy per sample = total - dynamic. PilotNet SDNN: (0.09-0.05) mJ and
# (1.26-0.07) mJ per sample. Divided by latency (1.21 ms, 65.41 ms) this is 33 mW and 18 mW;
# divided by the time between samples (1/7,404 s, 1/137.6 s) it is 296 mW and 164 mW. The paper
# does not say which, so the range spans both. Ceiling: Hala Point's 2,600 W max / 1,152 chips
# = 2.26 W per chip (whole system, incl. power supplies; docs/energy-budget.md).
SHRESTHA = "Shrestha et al. 2024, arXiv:2310.03251, Table 1 (derived: (total - dynamic energy) / time)"
NEURO_STATIC_W_CHIP = {
    "low": Price(0.018, "W", "DERIVED", SHRESTHA + ", IO-limited PilotNet, per latency"),
    "mid": Price(0.073, "W", "ASSUMED", "geometric middle of the derived 18-296 mW range"),
    "high": Price(0.296, "W", "DERIVED", SHRESTHA + ", PilotNet without IO, per sample interval"),
}
HALA_POINT_W_CHIP_MAX = Price(2.26, "W", "PUBLISHED", "Hala Point: at most 2,600 W for 1,152 Loihi 2 chips (Intel)")

# ------------------------------------------------------------------ conventional cores ----
# Cortex-M33 at 150 MHz = one core of a Raspberry Pi RP2350 (product page: 2 x M33, 150 MHz,
# single-precision FPU, 520 KB SRAM).
M33_CLOCK_HZ = Price(150e6, "Hz", "PUBLISHED", "Raspberry Pi RP2350 product brief")
M33_SRAM_B = Price(520 * 1024, "B", "PUBLISHED", "Raspberry Pi RP2350 product brief")
# Active power: Niedermeier and Krichmar (arXiv:2604.16474) ran 1,200 LIF neurons on an RP2350
# at about 30 mW (quoted in the hybrid-computer plan (not in this repo) section 6.2). Used as whole-chip power while
# one core computes.
M33_ACTIVE_W = Price(30e-3, "W", "PUBLISHED", "Niedermeier & Krichmar 2026, arXiv:2604.16474 (via hybrid-computer plan 6.2)")
M33_SLEEP_W = Price(1e-3, "W", "GUESSED", "RP2350 sleep power not checked; 1 mW placeholder")
M33_WAKE_S = Price(20e-6, "s", "GUESSED", "wake-from-sleep latency not checked; 20 us placeholder")
# Cycles per operation (ASSUMED; not measured on a chip). The first three are the
# minimal-circuit lane's numbers (experiments/minimal_circuit/hardware.py).
M33_CYCLES = {
    "neuron_update": Price(25, "cycles", "ASSUMED", "minimal-circuit lane: load v,g; 3 mul; 2 add; compare; store"),
    "syn_event": Price(10, "cycles", "ASSUMED", "minimal-circuit lane: load target+weight, add into delay buffer"),
    "rand": Price(12, "cycles", "ASSUMED", "minimal-circuit lane: one random draw"),
    "input_event": Price(10, "cycles", "ASSUMED", "same as a synaptic event"),
    "spike": Price(10, "cycles", "ASSUMED", "reset, record the spike, queue it for delivery"),
    "mac": Price(4, "cycles", "ASSUMED", "LDR index + LDR weight + VFMA (single-cycle FPU MAC) + loop"),
    "int64_add": Price(4, "cycles", "ASSUMED", "LDRD (2) + ADDS/ADC (2) per element"),
    "sort_cmp": Price(12, "cycles", "ASSUMED", "per comparison of a merge sort (load, compare, branch, store)"),
    "select": Price(10, "cycles", "ASSUMED", "per element of a quickselect (k-winners)"),
    "log_write": Price(40, "cycles", "ASSUMED", "append one 16-byte record (timestamp, id, count) to RAM"),
    "syn_update": Price(12, "cycles", "ASSUMED", "read-modify-write one weight with a cap"),
    "step_overhead": Price(50, "cycles", "ASSUMED", "per simulated time step: loop, delay-buffer rotate"),
}

# This laptop: Intel Core i3-1215U. Time per operation is MEASURED by calibrate.py.
# Energy = time x package power. Intel's rated base power is 15 W; the energy lane measured
# about 12 W package power under shared load (docs/energy-budget.md). Charging a whole 15 W to
# one busy core is an upper-end ASSUMPTION.
X86_POWER_W = Price(15.0, "W", "PUBLISHED", "Intel i3-1215U product page: 15 W processor base power")
X86_IDLE_W = Price(3.0, "W", "GUESSED", "laptop package idle power, not measured on this machine")

# ------------------------------------------------------------------ GPU -------------------
# NVIDIA T4 (the GPU in AWS g4dn.xlarge, hybrid-computer plan 6.7). Datasheet: 70 W, 8.1 TFLOPS FP32,
# 320 GB/s, PCIe Gen3 x16.
T4 = "NVIDIA T4 datasheet"
GPU = {
    "power_W": Price(70.0, "W", "PUBLISHED", T4 + ": 70 W board power (used as the power while busy: an upper bound)"),
    "flops": Price(8.1e12, "FLOP/s", "PUBLISHED", T4 + ": 8.1 TFLOPS FP32 peak"),
    "mem_Bps": Price(320e9, "B/s", "PUBLISHED", T4 + ": 320 GB/s"),
    "pcie_Bps": Price(12e9, "B/s", "ASSUMED", "PCIe Gen3 x16 effective ~12 GB/s"),
    "launch_s": Price(5e-6, "s", "ASSUMED", "typical CUDA kernel launch overhead (3-10 us); not measured here"),
    "pcie_latency_s": Price(10e-6, "s", "ASSUMED", "one small host<->device copy"),
}
GPU_IDLE_W = Price(10.0, "W", "GUESSED", "T4 idle power not checked; 10 W placeholder")
# Cross-check only: GPU spiking simulation measured at 0.3-0.47 uJ per synaptic event
# (Knight & Nowotny 2018, via Rhodes et al. 2020; experiments/energy_budget/constants.py).
GPU_SYNEVENT_J = (0.3e-6, 0.47e-6)

# ------------------------------------------------------------------ living module ---------
CL1_POWER_W = Price(25.0, "W", "PUBLISHED", "The Next Web: about 25 W per CL1 box (hybrid-computer plan 6.2)")
CL1_ELECTRODES = Price(59, "electrodes", "PUBLISHED", "IEEE Spectrum (hybrid-computer plan section 4)")
CL1_SAMPLE_HZ = Price(25e3, "Hz", "PUBLISHED", "CL API paper arXiv:2602.11632 (hybrid-computer plan section 4)")
CL1_FRAME_S = Price(40e-6, "s", "PUBLISHED", "CL API paper: 40 us frames")
CL1_STIM_LATENCY_S = Price(100e-6, "s", "PUBLISHED", "CL API paper: stimulus 80-120 us after the call (mid)")
MAXONE_NOISE_UV = Price(2.2, "uV rms", "PUBLISHED", "MaxWell MaxOne product page")

# DishBrain: Kagan et al. 2022, Neuron 110:3952, doi:10.1016/j.neuron.2022.09.001 (open access,
# PMC9747182; full text read 2026-09-24). "Fig" values were read off the published figures by eye
# (about +-0.05 on rally length, +-2 points on percentages) and are labelled so.
KAGAN = "Kagan et al. 2022, Neuron (DishBrain)"
KHAJ = "Khajehnejad et al. 2024, arXiv:2405.16946 (DishBrain vs deep RL)"
DISHBRAIN = {
    "cells_plated": Price(1e6, "cells", "PUBLISHED", KAGAN + ": approximately 10^6 cells plated per MEA"),
    "mea_electrodes": Price(26400, "electrodes", "PUBLISHED", KAGAN + ": MaxOne, 26,400 electrodes over 8 mm2"),
    "mea_channels": Price(1024, "channels", "PUBLISHED", KAGAN + ": reads up to 1,024 of them at once"),
    "sample_hz": Price(20e3, "Hz", "PUBLISHED", KAGAN + ": 20,000 samples per second"),
    "tick_s": Price(10e-3, "s", "PUBLISHED", KAGAN + ": motor spikes counted per 10 ms; game updated every 10 ms"),
    "sensory_sites": Price(8, "electrodes", "PUBLISHED", KAGAN + ": 8 stimulation electrodes, place-coded ball position"),
    "rate_min_hz": Price(4.0, "Hz", "PUBLISHED", KAGAN + ": rate code 4 Hz with the ball far away"),
    "rate_max_hz": Price(40.0, "Hz", "PUBLISHED", KAGAN + ": rising linearly to 40 Hz at the paddle wall"),
    "sense_mV": Price(75.0, "mV", "PUBLISHED", KAGAN + ": sensory stimulation 75 mV"),
    "hit_hz": Price(100.0, "Hz", "PUBLISHED", KAGAN + ": after a hit, 75 mV at 100 Hz for 100 ms, all sites"),
    "hit_s": Price(0.1, "s", "PUBLISHED", KAGAN + ": predictable feedback lasts 100 ms"),
    "miss_mV": Price(150.0, "mV", "PUBLISHED", KAGAN + ": after a miss, 150 mV at 5 Hz, random sites, 4 s"),
    "miss_hz": Price(5.0, "Hz", "PUBLISHED", KAGAN + ": unpredictable feedback rate"),
    "miss_s": Price(4.0, "s", "PUBLISHED", KAGAN + ": unpredictable feedback lasts 4 s"),
    "rest_s": Price(4.0, "s", "PUBLISHED", KAGAN + ": then 4 s with no stimulation, then the next rally"),
    "session_s": Price(1200.0, "s", "PUBLISHED", KAGAN + ": 20-minute sessions; T1 = 0-5 min, T2 = 6-20 min"),
    "rallies_per_session": Price(69.04, "rallies", "PUBLISHED", KHAJ + ": 69.04 +- 7.95 rallies per session"),
    "rally_random": Price(0.80, "hits/rally", "PUBLISHED", KAGAN + " Fig 5B (read off): in-silico control, paddle driven by noise"),
    "rally_hcc_t1": Price(0.68, "hits/rally", "PUBLISHED", KAGAN + " Fig 5B (read off): human cortical cells, first 5 min"),
    "rally_hcc_t2": Price(1.10, "hits/rally", "PUBLISHED", KAGAN + " Fig 5B (read off): human cortical cells, 6-20 min"),
    "rally_mcc_t1": Price(0.78, "hits/rally", "PUBLISHED", KAGAN + " Fig 5B (read off): mouse cortical cells, first 5 min"),
    "rally_mcc_t2": Price(1.00, "hits/rally", "PUBLISHED", KAGAN + " Fig 5B (read off): mouse cortical cells, 6-20 min"),
    "aces_t1_pct": Price(55.0, "%", "PUBLISHED", KAGAN + " Fig 5C (read off): rallies with no hit, HCC first 5 min"),
    "aces_t2_pct": Price(48.0, "%", "PUBLISHED", KAGAN + " Fig 5C (read off): HCC 6-20 min"),
    "learn_within_s": Price(300.0, "s", "PUBLISHED", KAGAN + ": 'apparent learning within five minutes of real-time gameplay'"),
    "elec_mean_hz": Price(0.07, "Hz", "PUBLISHED", KAGAN + " Fig 3C (read off): mean firing per electrode 0.05-0.1 Hz (primary, DSI); NGN2 up to 0.45 Hz"),
    "elec_max_hz": Price(20.0, "Hz", "PUBLISHED", KAGAN + " Fig 3B (read off): busiest electrode 6-22 Hz"),
    "ready_div_mouse": Price(10, "days", "PUBLISHED", KAGAN + ": mouse cultures used from about DIV 10 (bursting by DIV 14)"),
    "ready_div_human": Price(80, "days", "PUBLISHED", KAGAN + ": human (DSI) cultures ready around DIV 80; kept on MEA > 3 months"),
}
# FinalSpark Neuroplatform: Jordan et al. 2024, Front. Artif. Intell. 7:1376042 (PMC11097343).
JORDAN = "Jordan et al. 2024, Front. Artif. Intell. (FinalSpark Neuroplatform)"
FINALSPARK = {
    "lifetime_days": Price(100.0, "days", "PUBLISHED", JORDAN + ": organoid lifetime 'up to 100 days in best cases' (at first only hours)"),
    "electrodes_per_organoid": Price(8, "electrodes", "PUBLISHED", JORDAN + ": 4 organoids per MEA, 8 electrodes each"),
    "sample_hz": Price(30e3, "Hz", "PUBLISHED", JORDAN + ": 30 kHz, 16 bit"),
    "stim_uA": Price(4.0, "uA", "PUBLISHED", JORDAN + ": example optimal pulse 4 uA, biphasic, 100 us per phase"),
    "response_window_s": Price(0.2, "s", "PUBLISHED", JORDAN + ": evoked spikes counted for 200 ms after a 10 ms artifact gap"),
}
CL1_LIFETIME_DAYS = Price(180.0, "days", "PUBLISHED", "CL1 cultures last up to 6 months (hybrid-computer plan section 4)")


# ------------------------------------------------------------------ measured x86 ----------
def x86_ns_per_op():
    """Measured ns per operation on this laptop (calibrate.py). Returns None if not run."""
    f = RESULTS / "x86_calibration.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())["ns_per_op"]


def table():
    """Every constant as rows (name, value, unit, label, source) for the report."""
    rows = []
    for group, d in (("loihi", LOIHI), ("m33_cycles", M33_CYCLES), ("gpu", GPU),
                     ("neuro_static_w_chip", NEURO_STATIC_W_CHIP), ("dishbrain", DISHBRAIN),
                     ("finalspark", FINALSPARK)):
        for k, p in d.items():
            rows.append((f"{group}.{k}", p.value, p.unit, p.label, p.source))
    for name in ("NEURO_STATIC_W", "SANDIA_WALL_S_PER_SIM_S_DT01", "SANDIA_WALL_S_PER_SIM_S_DT1",
                 "LOIHI2_CORES_PER_CHIP", "LOIHI2_MIN_STEP_S", "HALA_POINT_W_CHIP_MAX",
                 "M33_CLOCK_HZ", "M33_SRAM_B",
                 "M33_ACTIVE_W", "M33_SLEEP_W", "M33_WAKE_S", "X86_POWER_W", "X86_IDLE_W", "GPU_IDLE_W",
                 "CL1_POWER_W", "CL1_ELECTRODES", "CL1_SAMPLE_HZ", "CL1_FRAME_S",
                 "CL1_STIM_LATENCY_S", "MAXONE_NOISE_UV", "CL1_LIFETIME_DAYS"):
        p = globals()[name]
        rows.append((name, p.value, p.unit, p.label, p.source))
    return rows
