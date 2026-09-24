"""Which neurons keep firing after the input stops? (Phase 6 biology check)

Real network (and optionally the controls), seed 0: 2 s of the task input at
one peak rate, then 1 s with the input off. Lists the neurons that spike in
the last 800 ms (200-1000 ms after the input stopped), with their cell types.
Usage: python persist.py <peak_hz> [real shuffle er]
Writes results/persist_<peak>.csv and prints a summary.
"""
import sys

import numpy as np
import pandas as pd

import lib_spk as L

R = L.rlib
peak = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0
nets = sys.argv[2:] or ["real"]
R.wait_for_ram(1.5)
root_ids, pre, post, signed, rep = L.real_arrays()
arrays = (root_ids, pre, post, signed)
lab = pd.read_parquet(R.LABELS_630, columns=["root_id", "super_class", "cell_class", "cell_type",
                                              "top_nt"]).set_index("root_id").reindex(root_ids)
lab = lab.astype(object).where(lab.notna(), "").astype(str)
sens = np.flatnonzero(lab.super_class.to_numpy() == "sensory")
u, _ = R.make_input(100, 0)
u_seg = np.concatenate([u, np.full(50, np.nan)])      # 2 s on, 1 s off
rows = []
for kind in nets:
    R.wait_for_ram(1.5)
    brain = L.make_brain(kind, 0, arrays)
    rng = np.random.default_rng(np.random.SeedSequence([0, 77]))
    p = brain._params_for(None)
    ev = L.poisson_events(L.rates_for(u_seg, L.input_signs(sens.size, 0), peak), sens, rng)
    res = brain._run_events([ev], sens, (), u_seg.size * L.SUB, p, ())
    t_ms = res.step * L.DT_MS
    late = t_ms >= 2200
    cnt = np.bincount(res.neuron[late], minlength=len(root_ids))
    on = np.bincount(res.neuron[t_ms < 2000], minlength=len(root_ids))
    idx = np.flatnonzero(cnt)
    last_ms = pd.Series(t_ms[late]).groupby(res.neuron[late]).max() if late.any() else pd.Series()
    print(f"{kind} peak={peak:g}: {idx.size} neurons spike 200-1000 ms after input off, "
          f"{int(cnt.sum())} spikes; last spike at {t_ms.max():.1f} ms", flush=True)
    for i in idx:
        rows.append({"network": kind, "root_id": int(root_ids[i]),
                     "super_class": lab.super_class.iloc[i], "cell_class": lab.cell_class.iloc[i],
                     "cell_type": lab.cell_type.iloc[i], "top_nt": lab.top_nt.iloc[i],
                     "rate_off_hz": cnt[i] / 0.8, "rate_on_hz": on[i] / 2.0,
                     "last_spike_ms": float(last_ms.get(i, np.nan))})
    del brain, res
df = pd.DataFrame(rows).sort_values(["network", "rate_off_hz"], ascending=[True, False])
df.to_csv(L.RESULTS / f"persist_{int(peak)}.csv", index=False)
pd.set_option("display.width", 200)
print(df.head(40).to_string(index=False))
