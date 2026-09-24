"""Measure this laptop's time per operation (the x86 price list). Writes
vhc/results/x86_calibration.json. Single thread; other lanes share the machine, so each
number is the MEDIAN of several repeats and is labelled MEASURED (under shared load).

Usage: .venv\\Scripts\\python.exe -m vhc.calibrate
"""
from __future__ import annotations

import datetime as dt
import json
import time

import numpy as np

from .cores.lif import Network, kernel, prepare, run_trial
from .paths import RESULTS


def _median_time(fn, reps=7):
    fn()                               # warm-up (JIT compile, caches)
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return float(np.median(ts))


def measure():
    rng = np.random.default_rng(0)
    steps = 10_000
    ns = {}
    # Only the compiled kernel is timed (event packing is excluded).
    empty = (np.zeros(0, np.int64), np.zeros(0, np.int64))

    def ktime(net, ev, exc=()):
        args = prepare(net, ev, steps, excited_idx=exc)
        return _median_time(lambda: kernel(args), 5), run_trial(net, ev, steps, excited_idx=exc)

    # 1. neuron updates: 2,000 unconnected neurons, no input (minus a 1-neuron run)
    n = 2000
    t_idle, _ = ktime(Network.from_edges(n, [], [], []), empty)
    t_one, _ = ktime(Network.from_edges(1, [], [], []), empty)
    ns["step_overhead"] = t_one / steps * 1e9
    ns["neuron_update"] = (t_idle - t_one) / (n * steps) * 1e9
    # 2. input events: 200 of the neurons get 200,000 random kicks; 1 mV kicks never make a
    #    spike, 68.75 mV kicks always do (the difference prices a spike)
    m, k = 200, 200_000
    st, ne = rng.integers(0, steps, k), rng.integers(0, m, k)
    bare = Network.from_edges(n, [], [], [])
    t_quiet, r_q = ktime(bare, (st, ne, np.full(k, 1.0)), np.arange(m))
    t_spk, r_s = ktime(bare, (st, ne), np.arange(m))
    ns["input_event"] = max(0.0, t_quiet - t_idle) / r_q.counts["input_event"] * 1e9
    ns["spike"] = max(0.0, t_spk - t_quiet) / max(1, r_s.counts["spikes"]) * 1e9
    # 3. synaptic events: the same spiking drive; each driven neuron has 500 targets
    pre = np.repeat(np.arange(m), 500)
    post = rng.integers(m, n, pre.size)
    syn = Network.from_edges(n, pre, post, np.full(pre.size, 0.01))
    t_syn, r = ktime(syn, (st, ne), np.arange(m))
    ns["syn_event"] = max(0.0, t_syn - t_spk) / r.counts["syn_event"] * 1e9
    # 4. exact integer sum (numpy, int64) and sort (numpy introsort, int32)
    a = rng.integers(-2**40, 2**40, 1_000_000, dtype=np.int64)
    ns["int64_add"] = _median_time(lambda: int(a.sum())) / a.size * 1e9
    b = rng.integers(-2**31, 2**31 - 1, 1_000_000, dtype=np.int32)
    ns["sort_cmp"] = _median_time(lambda: np.sort(b)) / (b.size * np.log2(b.size)) * 1e9
    # 5. dense multiply-accumulate (BLAS matrix x vector batch)
    W = rng.random((2000, 54), dtype=np.float32)
    X = rng.random((512, 54), dtype=np.float32)
    ns["mac"] = _median_time(lambda: X @ W.T) / (W.size * X.shape[0]) * 1e9
    return ns


def main():
    ns = measure()
    out = {"label": "MEASURED on this laptop (Intel i3-1215U), single thread, shared load, median",
           "date": dt.datetime.now().isoformat(timespec="seconds"), "ns_per_op": ns}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "x86_calibration.json").write_text(json.dumps(out, indent=1))
    for k, v in ns.items():
        print(f"{k:15s} {v:9.3f} ns")


if __name__ == "__main__":
    main()
