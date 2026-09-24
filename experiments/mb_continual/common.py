"""Shared pieces for the mushroom-body continual-learning lane (a fast rate model).

Plain English
-------------
* Wiring (``real_wiring``): for one brain half, how many synapses each Kenyon cell (KC)
  receives from the projection neurons (PNs) of each glomerulus (smell channel).
  FlyWire snapshot 630, the mushroom-body circuit file the Phase 8 lane built
  (experiments/phase8/results/circuit_630.npz). Only uniglomerular PNs are used
  (their glomerulus is known; they carry 95.5% of PN->KC synapses). KCs with no such
  input (mostly the visual KCs, KCg-d and KCab-p) are left out.
* Controls (``control_wiring``): the same KCs, each keeping its number of inputs and
  its synapse counts; only WHICH glomerulus each input comes from is re-drawn:
  (a) "shuffled": glomeruli drawn with their real overall frequencies;
  (b) "uniform": every glomerulus equally likely.
* Odours (``load_odours``): real receptor responses from the smell lane's tables
  (Hallem & Carlson 2006 for 23 glomeruli = "set A"; DoOR consensus back-projected to
  spikes/s for 23 more = "set B"; a missing value = no response).
* PN response (``pn_mean``): Olsen et al. 2010's equation, the same constants as the smell
  lane (Rmax 165 Hz, sigma 12 Hz, exponent 1.5, lateral inhibition m = 10.63 / 190 per Hz
  of summed set-A receptor input).
* Trial noise (``make_trials``): each trial, each glomerulus's PN output is a random
  (Poisson) spike count in a window of T seconds on top of a 5 Hz spontaneous rate.
* KC code (``kc_code``): each KC sums its inputs (synapse count x PN response); APL-like
  inhibition subtracts a common level so that only the top k% of KCs stay positive.
* Fly read-out (``FlyReadout``): one output neuron per class; each training example
  strengthens only the synapses from its active KCs onto the correct output (Shen,
  Dasgupta & Navlakha 2021/2023 rule), weights capped at 1. No backpropagation.
* MLP (``MLP``): a standard one-hidden-layer network with the same hidden size, trained
  with backpropagation (Adam, softmax cross-entropy).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RES = HERE / "results"
RAW = RES / "raw"
RES.mkdir(exist_ok=True)
RAW.mkdir(exist_ok=True)
CIRCUIT_NPZ = ROOT / "experiments" / "phase8" / "results" / "circuit_630.npz"
LABELS = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"
SMELL = ROOT / "experiments" / "olfaction_realfly" / "results"

# ---------------------------------------------------------------------------------------
# Fixed model constants (not tuned on the real-vs-random comparison)
# ---------------------------------------------------------------------------------------
RMAX, SIGMA, EXP = 165.0, 12.0, 1.5          # Olsen et al. 2010 generic fit (smell lane)
M_LATERAL, LFP_PER_HZ = 10.63, 190.0         # s = m * sum(set-A receptor input) / 190
PN_SPONT_HZ = 5.0                            # PN spontaneous rate (assumed, not measured)
BETA = 0.01                                  # fly read-out learning rate (Shen et al. MNIST-20)
W_CAP = 1.0                                  # fly read-out weights live in [0, 1] (Shen et al.)

#: Hallem & Carlson 2006 list their 110 odours grouped by chemical class, in this order.
CHEM_CLASSES = [("amines", 3), ("lactones", 5), ("acids", 15), ("sulfur compounds", 2),
                ("terpenes", 16), ("aldehydes", 8), ("ketones", 6), ("aromatics", 13),
                ("alcohols", 18), ("esters", 24)]
#: pre-registered coarse split: products of fermenting fruit (esters, alcohols, acids)
FRUIT_CLASSES = ("esters", "alcohols", "acids")


# ---------------------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------------------
def free_ram_gb():
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / 1e9
    except Exception:
        return float("nan")


def wait_for_ram(min_gb=1.5):
    while True:
        f = free_ram_gb()
        if not (f < min_gb):
            return f
        print(f"  free RAM {f:.2f} GB < {min_gb} GB, waiting 30 s", flush=True)
        time.sleep(30)


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------------------
def _clean(df, cols):
    for c in cols:
        df[c] = df[c].astype(object).where(df[c].notna(), "").astype(str)
    return df


def glomerulus_kc_table():
    """One row per (KC, glomerulus) with the summed uniglomerular-PN synapse count.
    Columns: kc_root, kc_side, kc_type, glom, n. Also returns a small census dict."""
    z = np.load(CIRCUIT_NPZ)
    lab = pd.read_parquet(LABELS, columns=["root_id", "cell_class", "cell_sub_class",
                                           "hemibrain_type", "side"])
    lab = _clean(lab.iloc[z["rows"]].reset_index(drop=True),
                 ["cell_class", "cell_sub_class", "hemibrain_type", "side"])
    if not np.array_equal(lab.root_id.to_numpy(np.int64), z["root_ids"].astype(np.int64)):
        raise ValueError("labels and circuit rows are not aligned")
    pre, post, cnt = z["pre"], z["post"], np.abs(z["signed"])
    cc = lab.cell_class.to_numpy()
    sub = lab.cell_sub_class.to_numpy()
    hb = lab.hemibrain_type.to_numpy()
    side = lab.side.to_numpy()
    to_kc = (cc[pre] == "ALPN") & (cc[post] == "Kenyon_Cell")
    upn = to_kc & (sub[pre] == "uniglomerular")
    census = {"pn_to_kc_synapses_all_pns": int(cnt[to_kc].sum()),
              "pn_to_kc_synapses_upns": int(cnt[upn].sum()),
              "kcs_in_circuit": int((cc == "Kenyon_Cell").sum()),
              "kcs_left": int(((cc == "Kenyon_Cell") & (side == "left")).sum()),
              "kcs_right": int(((cc == "Kenyon_Cell") & (side == "right")).sum())}
    e = pd.DataFrame({"kc_root": lab.root_id.to_numpy()[post[upn]],
                      "kc_side": side[post[upn]], "kc_type": hb[post[upn]],
                      "glom": [str(h).split("_")[0] for h in hb[pre[upn]]],
                      "n": cnt[upn].astype(np.int64)})
    t = e.groupby(["kc_root", "kc_side", "kc_type", "glom"], as_index=False).n.sum()
    return t, census


_GLOM_CACHE = {}


def all_glomeruli():
    """Sorted list of the glomeruli whose uniglomerular PNs reach KCs (both sides)."""
    if "g" not in _GLOM_CACHE:
        t, _ = glomerulus_kc_table()
        _GLOM_CACHE["g"] = sorted(t.glom.unique())
    return list(_GLOM_CACHE["g"])


@dataclass
class Wiring:
    name: str            # "real", "shuffled", "uniform"
    side: str            # "left" / "right"
    W: np.ndarray        # (n_kc, n_glom) synapse counts, float32
    gloms: list
    kc_types: np.ndarray
    seed: int = -1


def real_wiring(side, min_syn=1, table=None, gloms=None):
    """The real glomerulus -> KC synapse-count matrix of one brain half.
    Pairs with fewer than ``min_syn`` synapses are dropped; KCs with no input left out."""
    t = glomerulus_kc_table()[0] if table is None else table
    gloms = all_glomeruli() if gloms is None else gloms
    t = t[(t.kc_side == side) & (t.n >= min_syn)]
    kcs = np.sort(t.kc_root.unique())
    ki = pd.Index(kcs).get_indexer(t.kc_root)
    gi = pd.Index(gloms).get_indexer(t.glom)
    if (gi < 0).any():
        raise ValueError("unknown glomerulus")
    W = np.zeros((kcs.size, len(gloms)), np.float32)
    np.add.at(W, (ki, gi), t.n.to_numpy(np.float32))
    types = t.drop_duplicates("kc_root").set_index("kc_root").kc_type.reindex(kcs).to_numpy()
    return Wiring("real", side, W, list(gloms), types)


def glomerulus_frequency(W):
    """Fraction of all KC-glomerulus connections that involve each glomerulus."""
    f = (W > 0).sum(0).astype(float)
    return f / f.sum()


def control_wiring(real: Wiring, kind: str, rng):
    """A random rewiring of ``real`` that keeps each KC's number of inputs and its
    synapse counts. kind="shuffled": glomeruli drawn with the real frequencies;
    kind="uniform": all glomeruli that reach KCs in this half equally likely.
    Within one KC the glomeruli are distinct (drawn without replacement)."""
    W = real.W
    present = np.flatnonzero((W > 0).any(0))
    if kind == "shuffled":
        p = glomerulus_frequency(W)[present]
    elif kind == "uniform":
        p = np.full(present.size, 1.0 / present.size)
    else:
        raise ValueError(kind)
    out = np.zeros_like(W)
    for k in range(W.shape[0]):
        w = W[k][W[k] > 0]
        g = rng.choice(present, size=w.size, replace=False, p=p)
        out[k, g] = rng.permutation(w)
    return Wiring(kind, real.side, out, real.gloms, real.kc_types)


def edge_swap(real, rng, max_rounds=200):
    """POST HOC control: every real connection keeps its glomerulus AND its synapse count;
    connections are dealt out again at random to the KC input slots (each KC keeps its
    number of inputs; never the same glomerulus twice on one KC)."""
    W = real.W
    kc, gl = np.nonzero(W)
    w = W[kc, gl]
    perm = rng.permutation(kc.size)
    g2, w2 = gl[perm].copy(), w[perm].copy()
    for _ in range(max_rounds):
        key = kc.astype(np.int64) * 1000 + g2
        _, first = np.unique(key, return_index=True)
        dup = np.setdiff1d(np.arange(kc.size), first)
        if dup.size == 0:
            break
        other = rng.integers(0, kc.size, dup.size)
        g2[dup], g2[other] = g2[other].copy(), g2[dup].copy()
        w2[dup], w2[other] = w2[other].copy(), w2[dup].copy()
    else:
        raise RuntimeError("could not remove duplicate glomeruli")
    out = np.zeros_like(W)
    out[kc, g2] = w2
    return Wiring("edge_swap", real.side, out, real.gloms, real.kc_types)


# ---------------------------------------------------------------------------------------
# Odours
# ---------------------------------------------------------------------------------------
@dataclass
class Odours:
    names: list
    chem: np.ndarray        # chemical class per odour (Hallem & Carlson grouping)
    delta: np.ndarray       # (n_odour, n_glom) receptor response, spikes/s, 0 = none
    set_a: np.ndarray       # bool per glomerulus: Hallem & Carlson measured it
    has_data: np.ndarray    # bool per glomerulus: any data (set A or B)
    gloms: list


def load_odours(gloms=None, sets=("A", "B")):
    gloms = all_glomeruli() if gloms is None else gloms
    a = pd.read_csv(SMELL / "hc_delta.csv")
    b = pd.read_csv(SMELL / "door_ext_delta.csv")
    if not (a.inchikey.to_numpy() == b.inchikey.to_numpy()).all():
        raise ValueError("odour tables not aligned")
    delta = np.zeros((len(a), len(gloms)))
    gi = {g: i for i, g in enumerate(gloms)}
    set_a = np.zeros(len(gloms), bool)
    has = np.zeros(len(gloms), bool)
    for c in a.columns[2:]:
        delta[:, gi[c]] = a[c].to_numpy(float)
        set_a[gi[c]] = has[gi[c]] = True
    if "B" in sets:
        for c in b.columns[2:]:
            if set_a[gi[c]]:
                raise ValueError(f"{c} in both sets")
            delta[:, gi[c]] = np.nan_to_num(b[c].to_numpy(float), nan=0.0)
            has[gi[c]] = True
    chem = np.concatenate([[name] * n for name, n in CHEM_CLASSES])
    if chem.size != len(a):
        raise ValueError("chemical-class table does not cover the 110 odours")
    return Odours(a.odour.tolist(), chem, delta, set_a, has, list(gloms))


def pn_mean(delta, set_a):
    """Mean evoked PN response (spikes/s above spontaneous) per odour and glomerulus:
    Olsen et al. 2010, PN = Rmax x^1.5 / (x^1.5 + sigma^1.5 + s^1.5),
    x = receptor response (>= 0), s = m * sum over set-A glomeruli of x / 190."""
    x = np.clip(np.atleast_2d(delta), 0, None)
    s = M_LATERAL * x[:, set_a].sum(1, keepdims=True) / LFP_PER_HZ
    return RMAX * x ** EXP / (x ** EXP + SIGMA ** EXP + s ** EXP)


def make_trials(P, n_trials, T, rng, spont=PN_SPONT_HZ):
    """Noisy single trials. P: (n_odour, n_glom) mean evoked PN rates. Each trial each
    glomerulus fires Poisson(spont + P) * T spikes; the trial's evoked rate is
    count / T - spont. Returns X (n_odour * n_trials, n_glom) float32, y (odour index)."""
    lam = np.repeat((spont + P) * T, n_trials, axis=0)
    X = rng.poisson(lam).astype(np.float32) / np.float32(T) - np.float32(spont)
    y = np.repeat(np.arange(P.shape[0]), n_trials)
    return X, y


# ---------------------------------------------------------------------------------------
# KC code (APL-like k-winners-take-all)
# ---------------------------------------------------------------------------------------
def kc_code(W, X, k_frac=0.05, per_kc_norm=False, chunk=4096):
    """KC activity for inputs X (n, n_glom). Input to KC j = sum_g W[j, g] * X[:, g]
    (optionally divided by KC j's total synapses). APL-like inhibition subtracts, per
    input, the level of the (k+1)-th most driven KC, so at most k KCs stay positive;
    activity is then scaled so the most active KC = 1 (Shen et al.: min-max)."""
    n_kc = W.shape[0]
    k = max(1, int(round(k_frac * n_kc)))
    Wt = W.T.astype(np.float32)
    if per_kc_norm:
        Wt = Wt / np.maximum(Wt.sum(0, keepdims=True), 1e-9)
    out = np.empty((X.shape[0], n_kc), np.float32)
    for a in range(0, X.shape[0], chunk):
        inp = X[a:a + chunk] @ Wt
        thr = -np.partition(-inp, k, axis=1)[:, k]
        h = np.maximum(inp - thr[:, None], 0.0)
        mx = h.max(1, keepdims=True)
        out[a:a + chunk] = np.where(mx > 0, h / np.where(mx > 0, mx, 1.0), 0.0)
    return out


# ---------------------------------------------------------------------------------------
# Fly read-out: local, reward-gated, only active KCs' synapses onto the correct output
# ---------------------------------------------------------------------------------------
class FlyReadout:
    def __init__(self, n_kc, n_class, beta=BETA, cap=W_CAP):
        self.W = np.zeros((n_class, n_kc), np.float32)
        self.beta, self.cap = beta, cap
        self.n_changed = []          # synapses changed per training example

    def train(self, H, y):
        """One pass over the examples. Because every change is >= 0 and the cap is a
        ceiling, applying them one by one equals adding them up and capping once."""
        for c in np.unique(y):
            Hc = H[y == c]
            self.W[c] = np.minimum(self.cap, self.W[c] + self.beta * Hc.sum(0))
        self.n_changed.extend((H > 0).sum(1).tolist())

    def scores(self, H, classes):
        return H @ self.W[classes].T

    def predict(self, H, classes):
        classes = np.asarray(classes)
        return classes[np.argmax(self.scores(H, classes), axis=1)]


# ---------------------------------------------------------------------------------------
# MLP baseline (numpy, backpropagation, Adam)
# ---------------------------------------------------------------------------------------
class MLP:
    def __init__(self, n_in, n_hid, n_out, rng, lr=1e-3):
        self.W1 = (rng.standard_normal((n_in, n_hid)) * np.sqrt(2.0 / n_in)).astype(np.float32)
        self.b1 = np.zeros(n_hid, np.float32)
        self.W2 = (rng.standard_normal((n_hid, n_out)) * np.sqrt(1.0 / n_hid)).astype(np.float32)
        self.b2 = np.zeros(n_out, np.float32)
        self.params = [self.W1, self.b1, self.W2, self.b2]
        self.m = [np.zeros_like(p) for p in self.params]
        self.v = [np.zeros_like(p) for p in self.params]
        self.t = 0
        self.lr = lr
        self.active_frac = []        # fraction of hidden units > 0, per training batch

    def hidden(self, X):
        return np.maximum(X @ self.W1 + self.b1, 0.0)

    def logits(self, X, classes=None):
        z = self.hidden(X) @ self.W2 + self.b2
        return z if classes is None else z[:, classes]

    def predict(self, X, classes):
        classes = np.asarray(classes)
        return classes[np.argmax(self.logits(X, classes), axis=1)]

    def fit(self, X, y, classes, epochs, rng, batch=32):
        """Softmax cross-entropy over ``classes`` (the classes seen so far)."""
        classes = np.asarray(classes)
        pos = np.full(self.W2.shape[1], -1)
        pos[classes] = np.arange(classes.size)
        yy = pos[y]
        b1, b2, e1, e2, eps = 0.9, 0.999, 1e-8, None, None
        for _ in range(epochs):
            order = rng.permutation(X.shape[0])
            for a in range(0, X.shape[0], batch):
                idx = order[a:a + batch]
                x, t = X[idx], yy[idx]
                pre = x @ self.W1 + self.b1
                h = np.maximum(pre, 0.0)
                z = h @ self.W2[:, classes] + self.b2[classes]
                z = z - z.max(1, keepdims=True)
                p = np.exp(z)
                p /= p.sum(1, keepdims=True)
                p[np.arange(idx.size), t] -= 1.0
                p /= idx.size
                gW2 = np.zeros_like(self.W2)
                gb2 = np.zeros_like(self.b2)
                gW2[:, classes] = h.T @ p
                gb2[classes] = p.sum(0)
                dh = (p @ self.W2[:, classes].T) * (pre > 0)
                gW1 = x.T @ dh
                gb1 = dh.sum(0)
                self.active_frac.append(float((h > 0).mean()))
                self.t += 1
                for i, g in enumerate((gW1, gb1, gW2, gb2)):
                    self.m[i] = b1 * self.m[i] + (1 - b1) * g
                    self.v[i] = b2 * self.v[i] + (1 - b2) * g * g
                    mh = self.m[i] / (1 - b1 ** self.t)
                    vh = self.v[i] / (1 - b2 ** self.t)
                    self.params[i] -= (self.lr * mh / (np.sqrt(vh) + e1)).astype(np.float32)


def mlp_changed_per_example(active_frac, n_in, n_hid, n_seen):
    """Weights a plain SGD step on ONE example changes: every weight into and out of each
    active hidden unit (inputs are all non-zero here), plus the output biases.
    (With Adam or momentum, every weight moves on every step; this is the lower bound.)"""
    a = active_frac * n_hid
    return a * (n_in + 1) + a * n_seen + n_seen


def save_json(obj, path):
    Path(path).write_text(json.dumps(obj, indent=1, default=float))
