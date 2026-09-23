"""Time one 100 ms trial of the sugar experiment with the Brian2 port."""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim import shiu_model as sm

dataset = sys.argv[1] if len(sys.argv) > 1 else "783"
dur = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
t0 = time.perf_counter()
sm.load_connectome(dataset)
print(f"load {time.perf_counter()-t0:.1f} s", flush=True)
sugar = sm.SUGAR_R_630 if dataset == "630" else sm.SUGAR_R_783
res = sm.run_trials(sugar, duration_ms=dur, n_trials=1, rate_hz=150, seed=0, dataset=dataset, exp_name="timing", verbose=True)
s = res.settings
print(json.dumps({k: s[k] for k in ["build_s", "trial_s", "total_s"]}))
print("spikes", len(res.spikes), "active", len(res.rates))
print("MN9 L/R", [res.rate_of(i) for i in sm.mn9_ids(dataset)])
