"""GPU cost model (NVIDIA T4, published specs; nothing measured: this laptop has no CUDA GPU).

time = kernel launches x launch overhead + max(FLOPs / peak, bytes / memory bandwidth)
       + host<->device copies (latency + bytes / PCIe bandwidth)
energy = time x 70 W board power (an upper bound: small kernels draw less).

Latency mode only: one task at a time, as a sensor would deliver them. Batching many tasks
would amortise the launch overhead; the report says so where it matters.
"""
from __future__ import annotations

from ..ledger import Cost
from ..prices import GPU


def price(launches=0, flops=0.0, mem_bytes=0.0, copies=0, copy_bytes=0.0):
    g = {k: p.value for k, p in GPU.items()}
    t = (launches * g["launch_s"] + max(flops / g["flops"], mem_bytes / g["mem_Bps"])
         + copies * g["pcie_latency_s"] + copy_bytes / g["pcie_Bps"])
    return Cost(t, t * g["power_W"], "modeled", "gpu-T4",
                ["T4 datasheet specs; launch/PCIe overheads ASSUMED; energy at 70 W (upper bound)"])


def lif_price(counts, kernels_per_step=2):
    """A clock-driven GPU spiking simulator (GeNN-style): per time step one neuron kernel and
    one synapse kernel, plus one copy in and one out per task."""
    steps, neurons = counts["steps"], counts["neurons"]
    ev = counts["syn_event"] + counts["input_event"]
    flops = steps * neurons * 6 + ev * 2
    mem = steps * neurons * 3 * 8 + ev * 12
    # the whole input spike train is uploaded once; spike counts come back once
    return price(launches=steps * kernels_per_step, flops=flops, mem_bytes=mem, copies=2,
                 copy_bytes=counts["input_event"] * 8 + neurons * 4)
