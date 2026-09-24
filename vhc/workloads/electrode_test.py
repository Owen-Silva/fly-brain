"""Workload (e): the electrode bottleneck. How much of a culture's response survives when it is
read through N electrodes instead of every cell?

Task: 8 input patterns. Each is 3 pulses on 3 of 8 stimulation sites, in a set order, at 0, 5
and 10 ms. The culture responds for 60 ms; the conventional core reads each channel's event
count in six 10-ms bins and a ridge read-out (trained on the conventional core) names the
pattern. Chance = 12.5%.

Also: a drift check. The read-out is trained on day 0, then the culture ages (drift + cell
death) 7 and 30 days; accuracy with the old read-out vs a retrained one.
"""
from __future__ import annotations

import numpy as np

from ..cores import electrodes as E
from ..cores.living import Culture, CultureParams

N_CLASSES, N_SITES, DUR_MS, BIN_MS, N_BINS = 8, 8, 60.0, 10.0, 6
CHANNELS = (1, 2, 4, 8, 16, 32, 59, 128, 256)
LAMBDAS = (0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0)   # ridge penalties tried by cross-validation


def patterns(seed=0):
    rng = np.random.default_rng([seed, 11])
    out = set()
    while len(out) < N_CLASSES:
        out.add(tuple(rng.choice(N_SITES, 3, replace=False)))
    return sorted(out)


def record(culture, reach, pats, n_per_class, seed):
    """Run trials in random class order; returns (results, labels)."""
    rng = np.random.default_rng([seed, 12])
    y = rng.permutation(np.repeat(np.arange(len(pats)), n_per_class))
    res = []
    for k, c in enumerate(y):
        stim = [(5.0 * j, s) for j, s in enumerate(pats[c])]
        res.append(culture.trial(stim, DUR_MS, reach, seed=int(seed * 100000 + k)))
    return res, y


def features(res, culture, n_channels, seed):
    """(n_trials, features). n_channels=None: every cell, binned, no electrode; "pooled": every
    cell counted exactly but summed into 256 regions (what a silicon copy could read)."""
    rng = np.random.default_rng([seed, 13])
    if n_channels is None or n_channels == "pooled":
        # every cell counted exactly; "pooled" sums cells into a 16 x 16 grid of regions
        if n_channels is None:
            group, n_groups = np.arange(culture.p.n), culture.p.n
        else:
            cell = np.minimum((culture.xy / culture.p.dish_um * 16).astype(int), 15)
            group, n_groups = cell[:, 0] * 16 + cell[:, 1], 256
        out = np.zeros((len(res), n_groups * N_BINS))
        for i, r in enumerate(res):
            b = np.minimum((r.spike_steps * r.dt_ms / BIN_MS).astype(int), N_BINS - 1)
            np.add.at(out[i], group[r.spike_neurons] * N_BINS + b, 1)
        return out
    arr = E.ElectrodeArray(n_channels, culture.p.dish_um)
    prob = arr.detect_prob(culture.xy)
    return np.array([arr.read(r, culture.xy, BIN_MS, N_BINS, rng, prob) for r in res])


class Ridge:
    """Linear read-out (one-hot targets, ridge penalty): what the conventional core trains.
    The penalty is picked by 5-fold cross-validation on the TRAINING trials only."""

    def fit(self, X, y, n_classes=N_CLASSES, lam=None):
        if lam is None:
            lam = self._cv(X, y, n_classes)
        self.lam = lam
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Z = np.c_[(X - self.mu) / self.sd, np.ones(len(X))]
        Y = np.eye(n_classes)[y]
        if Z.shape[1] > Z.shape[0]:        # more features than trials: solve the small side
            self.B = Z.T @ np.linalg.solve(Z @ Z.T + lam * np.eye(len(Z)), Y)
        else:
            self.B = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ Y)
        return self

    def _cv(self, X, y, n_classes, grid=LAMBDAS, folds=5):
        idx = np.random.default_rng(0).permutation(len(y))
        score = []
        for lam in grid:
            ok = 0
            for f in range(folds):
                te = idx[f::folds]
                tr = np.setdiff1d(idx, te)
                m = Ridge().fit(X[tr], y[tr], n_classes, lam)
                ok += int(np.sum(m.predict(X[te]) == y[te]))
            score.append(ok)
        return grid[int(np.argmax(score))]

    def predict(self, X):
        Z = np.c_[(X - self.mu) / self.sd, np.ones(len(X))]
        return np.argmax(Z @ self.B, 1)


def run(n_train=30, n_test=15, seed=0, channels=CHANNELS, drift_days=(7, 30), params=None):
    cult = Culture(params or CultureParams(), seed)
    sites = E.grid(N_SITES, cult.p.dish_um, 300.0)
    reach = E.stim_reach(sites, cult.xy)
    pats = patterns(seed)
    tr, ytr = record(cult, reach, pats, n_train, seed * 10 + 1)
    te, yte = record(cult, reach, pats, n_test, seed * 10 + 2)
    curve = {}
    for ch in list(channels) + [None, "pooled"]:
        m = Ridge().fit(features(tr, cult, ch, 1), ytr)
        key = {None: "all cells", "pooled": "all cells, pooled into 256 regions"}.get(ch, ch)
        curve[key] = float(np.mean(m.predict(features(te, cult, ch, 2)) == yte))
    counts = {k: float(np.mean([r.counts[k] for r in tr + te])) for k in tr[0].counts}
    drift = {}
    if drift_days:
        ch = 59
        old = Ridge().fit(features(tr, cult, ch, 1), ytr)
        done = 0.0
        for d in drift_days:
            cult.age(d - done)
            done = d
            tr2, ytr2 = record(cult, reach, pats, n_train, seed * 10 + 3 + d)
            te2, yte2 = record(cult, reach, pats, n_test, seed * 10 + 4 + d)
            new = Ridge().fit(features(tr2, cult, ch, 1), ytr2)
            f2 = features(te2, cult, ch, 2)
            drift[d] = {"old_readout": float(np.mean(old.predict(f2) == yte2)),
                        "retrained": float(np.mean(new.predict(f2) == yte2)),
                        "alive_frac": float(cult.alive.mean())}
    eff = float(np.mean([cult._efficacy(s) for s in range(N_SITES)]))
    return {"curve": curve, "drift": drift, "counts": counts, "n_cells": cult.p.n,
            "stim_efficacy_end": eff, "culture": cult}
