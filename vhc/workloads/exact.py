"""Workload (c): exact arithmetic and sorting (the conventional core's home ground).

Sizes are chosen to fit the M33's 520 KB of on-chip memory:
  * sum: 50,000 signed 64-bit integers (400 KB), exact;
  * sort: 50,000 signed 32-bit integers (200 KB + a 200 KB merge buffer).
Accuracy is checked exactly against Python's big integers / a sortedness check.
"""
from __future__ import annotations

import time

import numpy as np

from ..cores import conventional, gpu

N = 50_000


def data(seed=0):
    rng = np.random.default_rng(seed)
    return (rng.integers(-2**40, 2**40, N, dtype=np.int64),
            rng.integers(-2**31, 2**31 - 1, N, dtype=np.int32))


def ops(kind, n=N):
    if kind == "sum":
        return {"int64_add": n}
    if kind == "sort":
        return {"sort_cmp": int(np.ceil(n * np.log2(n)))}
    raise ValueError(kind)


def measure_x86(kind, reps=21, seed=0):
    """Measured laptop wall time (median) and exactness."""
    a, b = data(seed)
    if kind == "sum":
        fn = lambda: int(a.sum())                       # noqa: E731
        truth = sum(int(x) for x in a)
        check = lambda r: r == truth                    # noqa: E731
    else:
        fn = lambda: np.sort(b)                         # noqa: E731
        check = lambda r: bool(np.all(r[1:] >= r[:-1])) and np.array_equal(np.sort(r), np.sort(b))  # noqa: E731
    r = fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return float(np.median(ts)), check(r)


def gpu_cost(kind, n=N):
    if kind == "sum":        # one reduction kernel + a second pass; copy data in, result out
        return gpu.price(launches=2, flops=n, mem_bytes=n * 8, copies=2, copy_bytes=n * 8 + 8)
    # radix sort of 32-bit keys: 4 passes of 8 bits, ~3 kernels per pass (CUB-style)
    return gpu.price(launches=12, mem_bytes=4 * 2 * n * 4, copies=2, copy_bytes=2 * n * 4)


def m33_cost(kind):
    return conventional.price(ops(kind), "m33")
