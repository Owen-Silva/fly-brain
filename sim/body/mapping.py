"""The two translation tables of the brain-body loop, written out explicitly.

1. SENSES -> BRAIN: antenna odor strength -> firing rate of the smell
   neurons (DM1 olfactory receptor neurons, ORNs) on that side.
2. BRAIN -> BODY: firing of the steering / walking descending neurons (DNs)
   -> FlyGym's two-number walking drive [left, right].

Plus the hand-written "body only" steering rule from FlyGym 1.x, which is
NOT brain-driven and is kept only as a comparison.

Every number below is a modelling choice unless a source is given. They were
fixed BEFORE the first closed-loop run and are not tuned to make the brain
look good.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LABELS_630 = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"

# ---------------------------------------------------------------------------
# Neurons (snapshot 630 root IDs)
# ---------------------------------------------------------------------------
#: Steering and walking descending neurons, copied from
#: experiments/phase5/unexplored/steering_ids.py (which converted the IDs in
#: docs/phase9-body-research.md section 5 to snapshot 630). The left DNa01 and
#: the left DNg100 (630 label "DNge162") were matched by LABEL, not by wiring.
DN_IDS = {
    "DNa02_L": 720575940629327659, "DNa02_R": 720575940604737708,
    "DNa01_L": 720575940623860202, "DNa01_R": 720575940644438551,
    "DNg100_L": 720575940612364530, "DNg100_R": 720575940647228468,
    "DNp09_L": 720575940635872101, "DNp09_R": 720575940627652358,
}
#: The default read-out neurons (the ones "silenced" in the DN control).
DRIVE_DNS = tuple(DN_IDS)


def orn_ids(hemibrain_type="ORN_DM1", labels=None):
    """Left and right ORN root IDs of one glomerulus type (snapshot 630).

    Filter (docs/phase5-olfaction.md section 2): super_class == sensory,
    cell_class == olfactory, hemibrain_type == ``hemibrain_type`` (in the 630
    labels the ORN type sits in ``hemibrain_type``, not ``cell_type``).
    "left"/"right" is the label table's ``side`` column. We treat "left" ORNs
    as those whose antenna is the left one (an assumption: the ``side`` of a
    sensory neuron is where it enters the brain).
    """
    import pandas as pd
    lab = labels if labels is not None else pd.read_parquet(
        LABELS_630, columns=["root_id", "super_class", "cell_class", "hemibrain_type", "side"])
    m = ((lab.super_class == "sensory") & (lab.cell_class == "olfactory")
         & (lab.hemibrain_type == hemibrain_type))
    d = lab[m]
    left = np.sort(d.loc[d.side == "left", "root_id"].to_numpy(np.int64))
    right = np.sort(d.loc[d.side == "right", "root_id"].to_numpy(np.int64))
    if left.size == 0 or right.size == 0:
        raise ValueError(f"no left/right ORNs found for {hemibrain_type!r}")
    return left, right


def dm1_orn_ids(labels=None):
    """Left and right DM1 ORNs: 35 left, 33 right. DM1 = Or42b ORNs; vinegar /
    fruity esters, attractive (Semmelhack & Wang 2009; background knowledge,
    not re-read)."""
    return orn_ids("ORN_DM1", labels)


# ---------------------------------------------------------------------------
# 1. Senses -> brain
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SensorMapping:
    """Antenna odor strength -> ORN firing rate (Hz), same for every DM1 ORN
    on that side:

        rate = r_max x I / (I + i_half)

    * A saturating curve because real ORNs saturate (a standard
      dose-response shape; background knowledge, not fitted to Or42b data).
    * r_max = 150 Hz: the model's default input rate (Shiu et al. 2024), so
      "full smell" equals what earlier phases used.
    * i_half = 0.01: the strength 10 mm from a peak-1 source, so the rate is
      half of r_max at 10 mm, ~30 Hz at 20 mm and ~120 Hz at 5 mm.
    * No spontaneous firing (rate 0 with no odor), like the rest of the
      project's model. Real ORNs fire a few Hz spontaneously; that is left
      out because the published model has no background activity anywhere.
    * Only the ANTENNA strength is used (DM1 ORNs sit on the antenna); the
      palp sensors are used only by the hand-written comparison rule.
    """
    r_max_hz: float = 150.0
    i_half: float = 0.01
    #: Which antennae can smell (added 2026-09-23 for experiments/phase9_da1):
    #: "both" (default, unchanged behaviour), "left_only" or "right_only".
    #: "left_only" = the RIGHT antenna is covered, the lab manipulation of
    #: removing or covering one antenna (e.g. Borst & Heisenberg 1982;
    #: Duistermars et al. 2009). The covered side's ORNs get 0 Hz. It is a
    #: fixed property of the trial, NOT computed from where the odor is, so
    #: it adds no hand-written left/right decision.
    antennae: str = "both"

    def __post_init__(self):
        if self.antennae not in ("both", "left_only", "right_only"):
            raise ValueError(f"unknown antennae {self.antennae!r}")

    def rate(self, intensity):
        i = np.clip(np.asarray(intensity, float), 0.0, None)
        return self.r_max_hz * i / (i + self.i_half)

    def side_rates(self, i_left_antenna, i_right_antenna):
        """(left rate, right rate) in Hz after applying ``antennae``."""
        rl = float(self.rate(i_left_antenna)) if self.antennae != "right_only" else 0.0
        rr = float(self.rate(i_right_antenna)) if self.antennae != "left_only" else 0.0
        return rl, rr

    def orn_rates(self, i_left_antenna, i_right_antenna, n_left, n_right):
        """Rates for the concatenated [left ORNs, right ORNs] list."""
        rl, rr = self.side_rates(i_left_antenna, i_right_antenna)
        return np.concatenate([np.full(n_left, rl), np.full(n_right, rr)])


# ---------------------------------------------------------------------------
# 2. Brain -> body
# ---------------------------------------------------------------------------
def turn_to_drive(turn, forward=1.0, max_modulation=0.8):
    """Turn command -> FlyGym's [left, right] descending drive.

    ``turn`` is between -1 and +1; positive = turn LEFT. As in FlyGym 1.x's
    odor-taxis example, turning lowers ONE side's drive by up to
    ``max_modulation`` (0.8) x |turn|; the other side stays at ``forward``.
    A lower LEFT number makes the FlyGym fly turn LEFT (measured in
    docs/phase9-body-research.md section 2.2 and re-checked by
    experiments/phase9/walk_and_sign_check.py).
    """
    t = float(np.clip(turn, -1.0, 1.0))
    left = forward * (1.0 - max_modulation * max(t, 0.0))
    right = forward * (1.0 - max_modulation * max(-t, 0.0))
    return np.array([left, right])


#: Default turning read-out: neuron name -> weight (positive = pushes LEFT).
DEFAULT_TURN_WEIGHTS = {"DNa02_L": 1.0, "DNa02_R": -1.0, "DNa01_L": 0.5, "DNa01_R": -0.5}
#: Default forward read-out: neuron name -> weight (a plain mean of the four).
DEFAULT_FORWARD_WEIGHTS = {"DNg100_L": 0.25, "DNg100_R": 0.25, "DNp09_L": 0.25, "DNp09_R": 0.25}


@dataclass(frozen=True)
class DriveMapping:
    """Descending-neuron rates (Hz) -> [left, right] drive.

    SWAPPABLE: the whole read-out is this one object (``TrialConfig.drive_mapping``).
    To try a different steering read-out (e.g. one recommended by a later
    Phase 6 steering study), pass other ``neuron_ids`` / ``turn_weights`` /
    ``forward_weights``; the loop reads, silences and records exactly the
    neurons listed in ``neuron_ids``.

    Turning (brain-driven), default weights:
        s = [(DNa02_L - DNa02_R) + 0.5 x (DNa01_L - DNa01_R)] / turn_scale_hz
        turn = tanh(s)          (positive = left)
      * More LEFT DNa02 means a LEFT turn: one-sided DNa02 activation gives an
        ipsilateral steering bias (Rayshubskiy et al. 2025, eLife,
        doi:10.7554/eLife.102230). DNa01 is the slower, weaker steering
        neuron of the same paper, so it gets half the weight.
      * turn_scale_hz = 20: a 20 Hz left-right difference gives tanh(1) = 0.76
        of the maximum turn. A modelling choice.

    Forward drive (``forward_mode``):
      * "fixed" (default for the first demo): forward = 1.0 always. The
        walking itself is then NOT brain-driven; only steering is. The Shiu
        model has no spontaneous activity, so a brain-driven forward drive
        would make the fly stand still whenever the smell is weak or absent,
        which would mix "does it walk?" with "does it steer?".
      * "brain": forward = min(1, weighted sum of ``forward_weights`` /
        forward_ref_hz); by default the mean of DNg100_L/R and DNp09_L/R.
        DNg100 (BDN2) is a walking command neuron (Pugliese et al. bioRxiv
        2025); DNp09 (P9) drives forward walking (Bidaye et al. 2020).
        forward_ref_hz = 20 is a modelling choice.
    The leg movements themselves always come from FlyGym's built-in
    controller: NOT brain-driven.
    """
    neuron_ids: dict = field(default_factory=lambda: dict(DN_IDS))
    turn_weights: dict = field(default_factory=lambda: dict(DEFAULT_TURN_WEIGHTS))
    forward_weights: dict = field(default_factory=lambda: dict(DEFAULT_FORWARD_WEIGHTS))
    turn_scale_hz: float = 20.0
    max_modulation: float = 0.8
    forward_mode: str = "fixed"
    forward_fixed: float = 1.0
    forward_ref_hz: float = 20.0

    def __post_init__(self):
        missing = (set(self.turn_weights) | set(self.forward_weights)) - set(self.neuron_ids)
        if missing:
            raise KeyError(f"weights name neurons not in neuron_ids: {sorted(missing)}")

    @property
    def readout_names(self):
        return list(self.neuron_ids)

    def turn(self, r):
        s = sum(w * r[n] for n, w in self.turn_weights.items()) / self.turn_scale_hz
        return float(np.tanh(s))

    def forward(self, r):
        if self.forward_mode == "fixed":
            return float(self.forward_fixed)
        if self.forward_mode == "brain":
            f = sum(w * r[n] for n, w in self.forward_weights.items())
            return float(min(1.0, max(0.0, f) / self.forward_ref_hz))
        raise ValueError(f"unknown forward_mode {self.forward_mode!r}")

    def drive(self, rates):
        """``rates``: dict neuron name -> Hz (names as in ``neuron_ids``).
        Returns (drive [left, right], turn, forward)."""
        t = self.turn(rates)
        f = self.forward(rates)
        return turn_to_drive(t, f, self.max_modulation), t, f


# ---------------------------------------------------------------------------
# DA1 (cVA) read-outs (added 2026-09-23 for experiments/phase9_da1)
# ---------------------------------------------------------------------------
#: DNpe002 (hemibrain type VES068), snapshot 630; side from the label table's
#: ``side`` column. The best left/right DA1 read-out for BOTH antennae
#: smelling in docs/phase6-steering.md section 4d (PRELIMINARY).
DNPE002_IDS = {"DNpe002_L": 720575940629428215, "DNpe002_R": 720575940620642940}


def dna02_drive_mapping(**kw):
    """DA1 demo read-out 1: ONLY the DNa02 pair (read and, in the "dns"
    control, silenced). turn = tanh((DNa02_L - DNa02_R) / 20 Hz), positive =
    left. Sign from biology: more DNa02 on one side turns the fly to that
    side (Rayshubskiy et al. 2025, eLife, doi:10.7554/eLife.102230). DNa01 is
    left out because it is silent for DA1 (docs/phase6-steering.md 4a).
    Forward drive fixed at 1.0 (NOT brain-driven)."""
    ids = {k: DN_IDS[k] for k in ("DNa02_L", "DNa02_R")}
    base = dict(neuron_ids=ids, turn_weights={"DNa02_L": 1.0, "DNa02_R": -1.0},
                forward_weights={})
    base.update(kw)
    return DriveMapping(**base)


def dnpe002_drive_mapping(**kw):
    """DA1 demo read-out 2: ONLY the DNpe002 pair.
    turn = tanh((DNpe002_L - DNpe002_R) / 20 Hz), positive = left.

    ASSUMPTION (UNVERIFIED): nobody has shown what DNpe002 does in a real
    fly, so "more left DNpe002 = turn left" is our choice, made by analogy
    with DNa02 (ipsilateral). Because the sign is chosen, a DNpe002-driven
    fly that turns TOWARD cVA shows only that the brain tells left from
    right; the DIRECTION of the behaviour is then our assumption, not the
    brain's. Forward drive fixed at 1.0 (NOT brain-driven)."""
    base = dict(neuron_ids=dict(DNPE002_IDS),
                turn_weights={"DNpe002_L": 1.0, "DNpe002_R": -1.0}, forward_weights={})
    base.update(kw)
    return DriveMapping(**base)


# ---------------------------------------------------------------------------
# Comparison: the hand-written rule (NOT brain-driven)
# ---------------------------------------------------------------------------
def published_taxis_turn(intensities_4, gain=-500.0, palp_antenna_weights=(1.0, 9.0)):
    """FlyGym 1.x's hand-coded attractive odor-taxis rule, NOT brain-driven.

    Copied from flygym-gymnasium 1.3.2 ``examples/olfaction/simple_odor_taxis.py``
    (attractive odor only): average palp and antenna strength per side with
    weights 1:9, bias = gain x (left - right) / mean, squash with
    tanh(bias**2) x sign(bias), and lower the side the fly should turn to by
    0.8 x |that|. Returned here as a ``turn`` (positive = left) so it goes
    through the same ``turn_to_drive`` as the brain's command; that gives
    exactly the example's [left, right] control signal.

    ``intensities_4``: strengths in ``odor.SENSOR_ORDER``
    (LPalp, RPalp, LAntenna, RAntenna).
    """
    x = np.asarray(intensities_4, float).reshape(2, 2)       # rows: palps, antennae
    per_side = np.average(x, axis=0, weights=palp_antenna_weights)  # [left, right]
    mean = per_side.mean()
    if mean <= 0:
        return 0.0
    bias = gain * (per_side[0] - per_side[1]) / mean
    norm = np.tanh(bias ** 2) * np.sign(bias)
    # Example: side_to_modulate = int(norm > 0) -> norm < 0 lowers LEFT = left turn.
    return float(-norm)
