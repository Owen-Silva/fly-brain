"""Electrode interface between the conventional core and the living-neuron module.

* N recording channels on a square grid over the dish. Each channel hears every cell near
  it: a spike's amplitude falls as (r0 / d)^2; the channel detects it when amplitude plus
  read noise crosses 5 x the noise level. Noise crossings also give false events.
* Stimulation: a pulse at a site reaches many cells; the chance of firing a cell falls as
  exp(-d / lambda). One electrode reaches a crowd.
* Latency: CL1 frames of 40 us and stimulus 80-120 us after the call (vhc/prices.py).

Published: noise 2.2 uV rms (MaxOne), 25 kHz sampling and 59 electrodes (CL1).
GUESSED: spike amplitude (150 uV at 20 um), stimulation reach (lambda = 60 um), false-event
rate (v0: 1 Hz per channel; v1: 0.05 Hz, bounded by DishBrain's measured mean electrode rate of
0.05-0.1 Hz, which includes any false events; Kagan et al. 2022 Fig 3C). Henze et al. 2000 report units detectable to roughly 100-140 um.
"""
from __future__ import annotations

from math import erf, sqrt

import numpy as np

from ..prices import MAXONE_NOISE_UV

AMP0_UV, R0_UM = 150.0, 20.0        # GUESSED
THRESH_SD = 5.0                     # ASSUMED: usual spike-detection threshold
STIM_LAMBDA_UM = 60.0               # GUESSED
FALSE_HZ = 0.05                     # FITTED (v0: 1.0 GUESSED): at most DishBrain's 0.05-0.1 Hz mean electrode rate


def grid(n, side_um, margin_um=100.0):
    """n points on the most square grid that holds them, filling the dish."""
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))
    xs = np.linspace(margin_um, side_um - margin_um, cols)
    ys = np.linspace(margin_um, side_um - margin_um, rows)
    pts = np.array([(x, y) for y in ys for x in xs])
    return pts[:n]


class ElectrodeArray:
    def __init__(self, n_channels, side_um, noise_uv=MAXONE_NOISE_UV.value):
        self.xy = grid(n_channels, side_um)
        self.noise = noise_uv

    def detect_prob(self, cell_xy):
        """(n_channels, n_cells) chance that a spike of the cell is detected on the channel."""
        d = np.hypot(self.xy[:, None, 0] - cell_xy[None, :, 0], self.xy[:, None, 1] - cell_xy[None, :, 1])
        amp = AMP0_UV * (R0_UM / np.maximum(d, R0_UM)) ** 2
        z = (amp - THRESH_SD * self.noise) / self.noise
        return 0.5 * (1 + np.vectorize(erf)(z / sqrt(2)))

    def read(self, res, cell_xy, bin_ms, n_bins, rng, prob=None):
        """Binned event counts per channel, shape (n_channels * n_bins,)."""
        prob = self.detect_prob(cell_xy) if prob is None else prob
        b = np.minimum((res.spike_steps * res.dt_ms / bin_ms).astype(int), n_bins - 1)
        hit = rng.random((res.spike_neurons.size, prob.shape[0])) < prob[:, res.spike_neurons].T
        out = np.zeros((prob.shape[0], n_bins))
        for k in range(n_bins):
            out[:, k] = hit[b == k].sum(0)
        out += rng.poisson(FALSE_HZ * bin_ms * 1e-3, out.shape)
        return out.ravel()


def stim_reach(site_xy, cell_xy):
    """(n_sites, n_cells) chance that one pulse at a site fires each cell."""
    d = np.hypot(site_xy[:, None, 0] - cell_xy[None, :, 0], site_xy[:, None, 1] - cell_xy[None, :, 1])
    return np.exp(-d / STIM_LAMBDA_UM)
