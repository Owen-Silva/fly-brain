"""Check on the REAL brain (127,400 neurons) that running it in 50 ms windows
with the state carried over (sim/body/brain_stepper.py) gives exactly the
same spikes as one uninterrupted FastBrain run. The unit test does this on
tiny networks; this does it once on the full connectome, in the runaway
regime (the hardest case: ~100,000 neurons touched).

Output: experiments/phase9/results/stepper_full_brain_check.txt
Run: .venv-body\\Scripts\\python.exe experiments/phase9/stepper_full_brain_check.py [fix]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sim import sign_fixes  # noqa: E402
from sim.body.brain_stepper import BrainStepper  # noqa: E402
from sim.body.mapping import dm1_orn_ids  # noqa: E402
from sim.fast_engine import FastBrain  # noqa: E402

DUR_MS, WIN_MS, RATE_HZ = 300.0, 50.0, 75.0


def main(fix):
    left, right = dm1_orn_ids()
    orns = np.concatenate([left, right])
    brain = sign_fixes.build_brain(fix)
    n_steps = int(DUR_MS / 0.1)
    ptr, neu = FastBrain._poisson_events(np.random.default_rng(7), brain.index_of(orns),
                                         np.full(orns.size, RATE_HZ * 1e-4), n_steps)
    steps = np.repeat(np.arange(n_steps), np.diff(ptr))
    ids = brain.root_ids[neu]
    t0 = time.perf_counter()
    ref = brain.run_with_input_events([(steps, ids)], excite=orns, duration_ms=DUR_MS)
    t_ref = time.perf_counter() - t0
    st = BrainStepper(brain, orns)
    w = int(WIN_MS / 0.1)
    got_s, got_n = [], []
    t0 = time.perf_counter()
    for t in range(0, n_steps, w):
        sel = (steps >= t) & (steps < t + w)
        r = st.step_events(steps[sel] - t, ids[sel], WIN_MS)
        got_s.append(r.spike_steps)
        got_n.append(r.spike_index)
    t_win = time.perf_counter() - t0
    gs, gn = np.concatenate(got_s), np.concatenate(got_n)
    same = np.array_equal(gs, ref.step) and np.array_equal(gn, ref.neuron)
    text = (f"fix={fix}; {DUR_MS:.0f} ms, DM1 ORNs at {RATE_HZ:.0f} Hz, {WIN_MS:.0f} ms windows\n"
            f"one FastBrain run: {ref.step.size} spikes, {ref.neurons_reached[0]} neurons touched, "
            f"{t_ref:.1f} s\n"
            f"windowed stepper : {gs.size} spikes, {st.n_active} neurons touched, {t_win:.1f} s\n"
            f"IDENTICAL spike for spike: {same}\n")
    print(text)
    out = ROOT / "experiments" / "phase9" / "results" / "stepper_full_brain_check.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    return same


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else "none") else 1)
