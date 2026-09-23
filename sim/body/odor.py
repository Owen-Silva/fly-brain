"""The smell world: odor sources and how strong the odor is at the antennae.

Plain English
-------------
FlyGym 2.x (the body model we use) dropped the smell module that FlyGym 1.x
had, so we add it back with the SAME published rule:

    odor strength at a sensor = peak strength x (distance to the source) ** -2

summed over all sources. This is the default ``diffuse_func = lambda x: x**-2``
of ``OdorArena.get_olfaction`` in FlyGym 1.x (flygym-gymnasium 1.3.2,
``arena/sensory_environment.py``; read from the released wheel on
2026-09-22), the arena used for the odor-taxis work in the NeuroMechFly v2
paper (Wang-Chen et al. 2024, Nature Methods, doi:10.1038/s41592-024-02497-y).
Distances are in mm; strength is in arbitrary units (1.0 = the strength 1 mm
from a source of peak 1).

Where the sensors sit (also copied from FlyGym 1.x, ``config.yaml`` ->
``olfaction.sensor_positions``), in the order FlyGym 1.x used:

    0 left maxillary palp   parent body Rostrum,     offset (-0.15,  0.15, -0.15) mm
    1 right maxillary palp  parent body Rostrum,     offset (-0.15, -0.15, -0.15) mm
    2 left antenna          parent body LFuniculus,  offset ( 0.02,  0.00, -0.10) mm
    3 right antenna         parent body RFuniculus,  offset ( 0.02,  0.00, -0.10) mm

Each offset is in the parent body's own frame (it turns with the body part).

What this does NOT model (same as FlyGym 1.x): wind, turbulence, plumes that
take time to spread, or odor being blocked by the body. It is a smooth,
steady "odor cloud".
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: FlyGym 1.x odor sensor placement: name -> (parent body, offset in mm).
#: FlyGym 1.x names; ``loop.py`` maps them to FlyGym 2.x body names.
SENSOR_ORDER = ("LPalp", "RPalp", "LAntenna", "RAntenna")
SENSOR_OFFSETS_MM = {
    "LPalp": ("Rostrum", np.array([-0.15, 0.15, -0.15])),
    "RPalp": ("Rostrum", np.array([-0.15, -0.15, -0.15])),
    "LAntenna": ("LFuniculus", np.array([0.02, 0.00, -0.10])),
    "RAntenna": ("RFuniculus", np.array([0.02, 0.00, -0.10])),
}


def inverse_square(distance_mm):
    """FlyGym 1.x default diffusion rule: relative strength = distance ** -2."""
    return np.asarray(distance_mm, float) ** -2


@dataclass
class OdorWorld:
    """Fixed odor sources in the arena.

    sources_mm : array (n_sources, 3), x/y/z positions in mm.
    peak : array (n_sources,), peak strength of each source (0 = odor off).
    """
    sources_mm: np.ndarray
    peak: np.ndarray = field(default=None)

    def __post_init__(self):
        self.sources_mm = np.atleast_2d(np.asarray(self.sources_mm, float))
        if self.sources_mm.shape[1] != 3:
            raise ValueError("sources_mm must have shape (n, 3)")
        if self.peak is None:
            self.peak = np.ones(len(self.sources_mm))
        self.peak = np.asarray(self.peak, float).reshape(len(self.sources_mm))

    @classmethod
    def no_odor(cls, sources_mm):
        """Same arena and source marker positions, but every source is off
        (the "no-odor arena" control)."""
        s = np.atleast_2d(np.asarray(sources_mm, float))
        return cls(s, np.zeros(len(s)))

    def intensity(self, points_mm):
        """Odor strength at each point: sum over sources of
        peak x distance ** -2 (FlyGym 1.x ``get_olfaction``, one odor
        dimension). ``points_mm``: array (n_points, 3). Returns (n_points,)."""
        pts = np.atleast_2d(np.asarray(points_mm, float))
        d = np.linalg.norm(pts[:, None, :] - self.sources_mm[None, :, :], axis=2)
        return (self.peak[None, :] * inverse_square(d)).sum(axis=1)


def sensor_positions(parent_pos, parent_rot):
    """World positions of the 4 FlyGym 1.x odor sensors.

    parent_pos : dict name -> (3,) world position of the parent body
        ("Rostrum", "LFuniculus", "RFuniculus").
    parent_rot : dict name -> (3, 3) rotation matrix of the parent body
        (body frame -> world frame).
    Returns an array (4, 3) in ``SENSOR_ORDER``.
    """
    out = np.empty((4, 3))
    for k, name in enumerate(SENSOR_ORDER):
        parent, offset = SENSOR_OFFSETS_MM[name]
        out[k] = np.asarray(parent_pos[parent], float) + np.asarray(parent_rot[parent], float) @ offset
    return out
