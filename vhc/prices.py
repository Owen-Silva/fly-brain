"""The price list: time and energy per operation for every part of the virtual computer.

Every constant carries a label:
  PUBLISHED - taken from a datasheet or paper (source given);
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
# 1,440 cores, sugar experiment. Used only to CALIBRATE the timing model.
SANDIA_WALL_S_PER_SIM_S_DT01 = Price(53.76e-3, "s", "PUBLISHED", "Wang et al. 2025 (Sandia), arXiv:2508.16792")
SANDIA_CORES = 1440

# ------------------------------------------------------------------ conventional cores ----
# Cortex-M33 at 150 MHz = one core of a Raspberry Pi RP2350 (product page: 2 x M33, 150 MHz,
# single-precision FPU, 520 KB SRAM).
M33_CLOCK_HZ = Price(150e6, "Hz", "PUBLISHED", "Raspberry Pi RP2350 product brief")
M33_SRAM_B = Price(520 * 1024, "B", "PUBLISHED", "Raspberry Pi RP2350 product brief")
# Active power: Niedermeier and Krichmar (arXiv:2604.16474) ran 1,200 LIF neurons on an RP2350
# at about 30 mW (quoted in docs/hybrid-roadmap.md section 6.2). Used as whole-chip power while
# one core computes.
M33_ACTIVE_W = Price(30e-3, "W", "PUBLISHED", "Niedermeier & Krichmar 2026, arXiv:2604.16474 (via hybrid-roadmap 6.2)")
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
# NVIDIA T4 (the GPU in AWS g4dn.xlarge, hybrid-roadmap 6.7). Datasheet: 70 W, 8.1 TFLOPS FP32,
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
CL1_POWER_W = Price(25.0, "W", "PUBLISHED", "The Next Web: about 25 W per CL1 box (hybrid-roadmap 6.2)")
CL1_ELECTRODES = Price(59, "electrodes", "PUBLISHED", "IEEE Spectrum (hybrid-roadmap section 4)")
CL1_SAMPLE_HZ = Price(25e3, "Hz", "PUBLISHED", "CL API paper arXiv:2602.11632 (hybrid-roadmap section 4)")
CL1_FRAME_S = Price(40e-6, "s", "PUBLISHED", "CL API paper: 40 us frames")
CL1_STIM_LATENCY_S = Price(100e-6, "s", "PUBLISHED", "CL API paper: stimulus 80-120 us after the call (mid)")
MAXONE_NOISE_UV = Price(2.2, "uV rms", "PUBLISHED", "MaxWell MaxOne product page")


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
    for group, d in (("loihi", LOIHI), ("m33_cycles", M33_CYCLES), ("gpu", GPU)):
        for k, p in d.items():
            rows.append((f"{group}.{k}", p.value, p.unit, p.label, p.source))
    for name in ("NEURO_STATIC_W", "SANDIA_WALL_S_PER_SIM_S_DT01", "M33_CLOCK_HZ", "M33_SRAM_B",
                 "M33_ACTIVE_W", "M33_SLEEP_W", "M33_WAKE_S", "X86_POWER_W", "X86_IDLE_W", "GPU_IDLE_W",
                 "CL1_POWER_W", "CL1_ELECTRODES", "CL1_SAMPLE_HZ", "CL1_FRAME_S",
                 "CL1_STIM_LATENCY_S", "MAXONE_NOISE_UV"):
        p = globals()[name]
        rows.append((name, p.value, p.unit, p.label, p.source))
    return rows
