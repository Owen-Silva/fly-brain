"""Simulated living-neuron module: a small cortical-culture-like network with biology's flaws.

THIS IS THE WEAKEST PART OF THE VIRTUAL COMPUTER. No validated model exists of how a CL1
culture learns, drifts or dies (docs/hybrid-roadmap.md 6.8). Every setting below is labelled;
GUESSED ones are placeholders for Stage 4 to measure.

What is modelled:
  * base network: N neurons scattered on a square dish, mostly local wiring plus a few
    long-range links ("small-world"), 80% excitatory / 20% inhibitory
    (Maheswaranathan et al. 2012 used 500-800-neuron small-world culture models);
  * noise: spontaneous input kicks and membrane noise;
  * fatigue: a site stimulated often responds less, and recovers with rest
    (Eytan et al. 2003, J Neurosci 23:9349; rates GUESSED);
  * drift: slow random change of every synapse's strength (rate GUESSED);
  * cell death: slow loss of neurons (rate GUESSED; CL1 cultures last up to 6 months);
  * slow plasticity: co-active excitatory pairs strengthen a little (Hebbian; rate GUESSED).
Neurons use the same LIF equations as the fly model (a simplification: cortical cells differ).
Time is real time only; energy is the CL1 box's life support (vhc/prices.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..ledger import Cost
from ..prices import CL1_FRAME_S, CL1_POWER_W, CL1_STIM_LATENCY_S
from .lif import Network, run_trial


@dataclass
class CultureParams:
    n: int = 1000                  # ASSUMED: model size (a CL1 has ~800,000 cells)
    dish_um: float = 1400.0        # ASSUMED: square dish side; CL1-like 8x8 grid at 200 um pitch
    frac_inh: float = 0.2          # ASSUMED: ~20% inhibitory, typical of cortical cultures
    k_local: int = 30              # GUESSED: local outgoing links per neuron
    local_um: float = 150.0        # GUESSED: length scale of local links
    p_long: float = 0.1            # ASSUMED: share of links rewired to random targets (small-world)
    w_exc: float = 6.0             # GUESSED: excitatory weight, in units of w_syn (0.275 mV)
    w_inh: float = -18.0           # GUESSED: inhibitory weight
    spont_hz: float = 2.0          # GUESSED: spontaneous input kicks per neuron per second
    spont_kick_mV: float = 8.0     # GUESSED: size of a spontaneous kick
    noise_mV: float = 0.3          # GUESSED: membrane noise per 0.1 ms step (SD)
    fatigue_per_pulse: float = 0.03   # GUESSED: stimulation efficacy lost per pulse at a site
    fatigue_recovery_s: float = 20.0  # GUESSED: efficacy recovers with this time constant
    drift_sd_per_day: float = 0.05    # GUESSED: log-normal random walk of each weight per day
    death_per_day: float = 0.004      # GUESSED: ~50% of cells left after 6 months
    hebb_rate: float = 0.002          # GUESSED: relative strengthening per co-active pair spike
    labels: dict = field(default_factory=lambda: {
        "n": "ASSUMED", "dish_um": "ASSUMED", "frac_inh": "ASSUMED", "k_local": "GUESSED",
        "local_um": "GUESSED", "p_long": "ASSUMED", "w_exc": "GUESSED", "w_inh": "GUESSED",
        "spont_hz": "GUESSED", "spont_kick_mV": "GUESSED", "noise_mV": "GUESSED",
        "fatigue_per_pulse": "GUESSED", "fatigue_recovery_s": "GUESSED",
        "drift_sd_per_day": "GUESSED", "death_per_day": "GUESSED", "hebb_rate": "GUESSED"})


class Culture:
    def __init__(self, params: CultureParams | None = None, seed=0):
        self.p = p = params or CultureParams()
        rng = np.random.default_rng([seed, 1])
        self.rng = np.random.default_rng([seed, 2])
        self.xy = rng.random((p.n, 2)) * p.dish_um
        self.inh = rng.random(p.n) < p.frac_inh
        pre, post = [], []
        for i in range(p.n):
            d = np.hypot(*(self.xy - self.xy[i]).T)
            pr = np.exp(-d / p.local_um)
            pr[i] = 0.0
            tgt = rng.choice(p.n, p.k_local, replace=False, p=pr / pr.sum())
            longr = rng.random(p.k_local) < p.p_long
            tgt[longr] = rng.integers(0, p.n, longr.sum())
            tgt = tgt[tgt != i]
            pre.append(np.full(tgt.size, i))
            post.append(tgt)
        self.pre = np.concatenate(pre)
        self.post = np.concatenate(post)
        self.w = np.where(self.inh[self.pre], p.w_inh, p.w_exc).astype(float)
        self.alive = np.ones(p.n, bool)
        self.age_days = 0.0
        self.efficacy = {}            # stimulation site -> current efficacy (fatigue)
        self.last_stim_s = {}
        self.clock_s = 0.0

    # --------------------------------------------------------------- biology over time -----
    def network(self):
        return Network.from_edges(self.p.n, self.pre, self.post, self.w)

    def age(self, days):
        """Drift and cell death over ``days``."""
        p = self.p
        self.w *= np.exp(p.drift_sd_per_day * np.sqrt(days) * self.rng.standard_normal(self.w.size))
        die = self.rng.random(p.n) < 1 - np.exp(-p.death_per_day * days)
        self.alive &= ~die
        self.age_days += days
        self.clock_s += days * 86400.0

    def hebbian(self, spike_counts):
        """Slow plasticity: excitatory links whose two ends both fired strengthen a little."""
        both = np.minimum(spike_counts[self.pre], spike_counts[self.post])
        exc = ~self.inh[self.pre]
        self.w[exc] *= 1 + self.p.hebb_rate * both[exc]
        return int((both[exc] > 0).sum())

    def _efficacy(self, site):
        """Current efficacy of a stimulation site after rest since its last use."""
        e = self.efficacy.get(site, 1.0)
        rest = self.clock_s - self.last_stim_s.get(site, -1e9)
        return 1 - (1 - e) * np.exp(-rest / self.p.fatigue_recovery_s)

    # --------------------------------------------------------------- one trial -------------
    def trial(self, stim, duration_ms, reach, iti_s=1.0, seed=0):
        """Run one trial. ``stim``: list of (time_ms, site); ``reach``: (n_sites, n) chance that
        a pulse at a site fires each cell (from the electrode model). Returns TrialResult."""
        p = self.p
        rng = np.random.default_rng([seed, 3])
        dt = 0.1
        n_steps = int(round(duration_ms / dt))
        st, ne, wv = [], [], []
        for t_ms, site in stim:
            eff = self._efficacy(site)
            hit = np.flatnonzero((rng.random(p.n) < reach[site] * eff) & self.alive)
            st.append(np.full(hit.size, int(t_ms / dt)))
            ne.append(hit)
            wv.append(np.full(hit.size, 68.75))        # a pulse fires the cells it reaches
            self.efficacy[site] = eff * (1 - p.fatigue_per_pulse)
            self.last_stim_s[site] = self.clock_s + t_ms * 1e-3
        k = rng.poisson(p.spont_hz * p.n * duration_ms * 1e-3)
        st.append(rng.integers(0, n_steps, k))
        ne.append(rng.integers(0, p.n, k))
        wv.append(np.full(k, p.spont_kick_mV))
        res = run_trial(self.network(), (np.concatenate(st), np.concatenate(ne), np.concatenate(wv)),
                        n_steps, alive=self.alive, noise_mV=p.noise_mV, noise_seed=seed)
        self.clock_s += duration_ms * 1e-3 + iti_s
        return res


def price(duration_s, n_pulses):
    """A living module works in real time only. Energy = CL1 life support x (trial + loop)."""
    t = duration_s + CL1_STIM_LATENCY_S.value + CL1_FRAME_S.value
    return Cost(t, t * CL1_POWER_W.value, "modeled", "living-CL1",
                ["real time only; energy = 25 W CL1 box x time (cells alone are negligible)"])
