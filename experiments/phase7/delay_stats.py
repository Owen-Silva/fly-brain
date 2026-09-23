"""Upgrade 1 facts: what positions exist for snapshot 630, and what delays the
distance rule gives (weighted by connections and by synapses).
Writes experiments/phase7/results/delay_stats.json."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sim.realism import RealisticBrain  # noqa: E402

brain = RealisticBrain("630")
out = {}
for dist in ["anchor", "soma"]:
    L = brain.connection_lengths_um(dist)
    w = np.abs(brain._count).astype(float)
    q = lambda x, ww=None: {p: float(np.percentile(x, p)) for p in (5, 25, 50, 75, 95, 99)}
    out[f"{dist}_length_um"] = {"mean": float(L.mean()), "percentiles": q(L),
                                "synapse_weighted_mean": float((L * w).sum() / w.sum())}
    for v in [0.129, 0.20, 2.07]:
        brain.set_realism(delays=True, velocity_m_per_s=v, distance=dist)
        d = brain.delay_steps_per_connection() * 0.1
        out[f"{dist}_v{v}_delay_ms"] = {
            "mean": float(d.mean()), "synapse_weighted_mean": float((d * w).sum() / w.sum()),
            "percentiles": q(d), "max": float(d.max()),
            "frac_equal_to_1.8ms": float((d == 1.8).mean())}
out["position_notes"] = brain.distance_notes
(ROOT / "experiments/phase7/results").mkdir(parents=True, exist_ok=True)
(ROOT / "experiments/phase7/results/delay_stats.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
