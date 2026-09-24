"""The closed brain-body loop (Phase 9, first demo: walking toward an odor).

Needs FlyGym 2.1.0, installed only in the separate ``.venv-body``
environment (see requirements-body.txt).

What one trial does, in plain English
-------------------------------------
The trial is cut into fixed windows (50 ms by default, the decision interval
of FlyGym 1.x's odor-taxis example). In every window:

1. **Body -> senses.** Read where the fly's antennae (and palps) are in the
   physics world and compute the odor strength there with the published
   1 / distance^2 rule (sim/body/odor.py).
2. **Senses -> brain.** Turn the left and right antenna strength into firing
   rates for the left and right DM1 smell neurons (sim/body/mapping.py,
   ``SensorMapping``) and run the whole-brain model for the window. The brain
   keeps its state from window to window (sim/body/brain_stepper.py).
3. **Brain -> drive.** Count the spikes of the steering neurons (DNa02, DNa01,
   left and right) and walking neurons (DNg100, DNp09) in the window, convert
   to Hz, and translate them into FlyGym's two-number walking drive
   [left, right] (``DriveMapping``).
4. **Drive -> body.** Step the physics for the window with FlyGym's built-in
   walking controller (``HybridTurningController`` from ``flygym_demo``) using
   that drive. The leg movements, the walking rhythm and the way the drive
   bends the walk into a turn all come from FlyGym: **NOT brain-driven**.

Steering sources (``TrialConfig.steering``):
* "brain"     : steps 2-3 above (brain-driven steering).
* "hand_rule" : FlyGym 1.x's hand-written odor-taxis rule instead of the
                brain (**NOT brain-driven**; the comparison).
* "straight"  : drive [1, 1] always (no steering at all).

Controls (``TrialConfig``): ``silence="dns"`` cuts the output of the read-out
DNs listed in ``TrialConfig.drive_mapping`` (8 by default; they are silenced
in the brain AND the body receives 0 Hz from them);
``silence="orns"`` cuts the output of the DM1 smell neurons; ``odor_on=False``
turns every odor source off (same arena otherwise).

DA1 (cVA) options (added 2026-09-23, experiments/phase9_da1): ``orn_type=
"ORN_DA1"``; ``drive_mapping=mapping.dna02_drive_mapping()`` or
``mapping.dnpe002_drive_mapping()`` (only that DN pair is read and, with
``silence="dns"``, silenced); ``sensor_mapping=SensorMapping(antennae=
"left_only")`` covers the right antenna (a one-antenna fly).

Video hook (added 2026-09-23, experiments/phase9_video): ``run_trial(...,
on_substep=f)`` calls ``f(body)`` after every physics step so a script can
copy the body's state for rendering. It must only READ the state. Left out
(the default), nothing changes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import mujoco
import numpy as np

from flygym.anatomy import BodySegment
from flygym.compose import FlatGroundWorld
from flygym.simulation import Simulation
from flygym.utils.math import Rotation3D
from flygym_demo.complex_terrain import HybridTurningController
from flygym_demo.complex_terrain.common import apply_locomotion_action, make_locomotion_fly
from flygym_demo.complex_terrain.hybrid_controller import HybridControllerObservation

from sim.body.brain_stepper import BrainStepper
from sim.body.mapping import (
    DriveMapping, SensorMapping, orn_ids,
    published_taxis_turn, turn_to_drive,
)
from sim.body.odor import SENSOR_ORDER, OdorWorld, sensor_positions

#: FlyGym 1.x sensor parent names -> FlyGym 2.x body segment names.
PARENT_2X = {"Rostrum": "c_rostrum", "LFuniculus": "l_funiculus", "RFuniculus": "r_funiculus"}
#: Odor source height (mm), as in FlyGym 1.x's simple_odor_taxis example.
SOURCE_Z_MM = 1.5
#: "Reached the odor" radius (mm), the example's ``distance_threshold``.
REACH_MM = 2.0
SPAWN_Z_MM = 0.7


@dataclass
class TrialConfig:
    name: str
    steering: str = "brain"            # "brain" | "hand_rule" | "straight"
    odor_on: bool = True
    silence: str = "none"              # "none" | "dns" | "orns"
    duration_s: float = 3.0
    window_ms: float = 50.0
    source_xy_mm: tuple = (15.0, 0.0)
    spawn_xy_mm: tuple = (0.0, 0.0)
    spawn_heading_rad: float = 0.0     # 0 = facing +x; +y is the fly's left
    seed: int = 0                      # CPG seed (and brain seed unless brain_seed is set)
    brain_seed: int | None = None      # brain Poisson seed (None = use seed)
    stop_at_source: bool = True
    drive_mapping: DriveMapping = field(default_factory=DriveMapping)
    orn_type: str = "ORN_DM1"          # which smell neurons the odor drives
    sensor_mapping: SensorMapping = field(default_factory=SensorMapping)


class Body:
    """FlyGym 2.1.0 NeuroMechFly on flat ground with the hybrid turning
    controller (the setup of FlyGym's "turning" tutorial)."""

    def __init__(self, spawn_xy_mm=(0.0, 0.0), heading_rad=0.0, seed=0):
        self.fly = make_locomotion_fly()
        world = FlatGroundWorld()
        half = heading_rad / 2.0
        quat = (float(np.cos(half)), 0.0, 0.0, float(np.sin(half)))   # yaw about +z
        world.add_fly(self.fly, (float(spawn_xy_mm[0]), float(spawn_xy_mm[1]), SPAWN_Z_MM),
                      Rotation3D("quat", quat))
        self.sim = Simulation(world)
        self.name = self.fly.name
        self.controller = HybridTurningController(timestep=self.sim.timestep)
        order = self.fly.get_bodysegs_order()
        cls = type(self.fly).BODY_SEGMENT_CLASS if hasattr(type(self.fly), "BODY_SEGMENT_CLASS") else BodySegment
        self._thorax = order.index(cls("c_thorax"))
        self._parents = {k: order.index(cls(v)) for k, v in PARENT_2X.items()}
        self.sim.reset()
        self.controller.reset(seed=seed)
        self.sim.warmup()

    @property
    def time_s(self):
        return float(self.sim.mj_data.time)

    def pose(self):
        """(thorax x, y in mm, heading angle in rad: 0 = +x, positive = to the left)."""
        pos = self.sim.get_body_positions(self.name)
        quat = self.sim.get_body_rotations(self.name)[self._thorax]
        m = np.empty(9)
        mujoco.mju_quat2Mat(m, np.asarray(quat, float))
        fwd = m.reshape(3, 3)[:, 0]
        return float(pos[self._thorax, 0]), float(pos[self._thorax, 1]), float(np.arctan2(fwd[1], fwd[0]))

    def thorax_z(self):
        return float(self.sim.get_body_positions(self.name)[self._thorax, 2])

    def odor_sensor_positions(self):
        """World positions (4, 3) of the FlyGym 1.x odor sensors (SENSOR_ORDER)."""
        pos = self.sim.get_body_positions(self.name)
        quats = self.sim.get_body_rotations(self.name)
        ppos, prot = {}, {}
        for k, i in self._parents.items():
            m = np.empty(9)
            mujoco.mju_quat2Mat(m, np.asarray(quats[i], float))
            ppos[k] = pos[i]
            prot[k] = m.reshape(3, 3)
        return sensor_positions(ppos, prot)

    def step(self, drive, duration_s, on_substep=None):
        """Walk for ``duration_s`` with the given [left, right] drive (FlyGym's
        controller; NOT brain-driven). ``on_substep(self)``, if given, is
        called after every physics step (read-only video hook)."""
        n = int(round(duration_s / self.sim.timestep))
        drive = np.asarray(drive, float)
        for _ in range(n):
            obs = HybridControllerObservation.from_sim(self.sim, self.name)
            action = self.controller.step(drive, obs)
            apply_locomotion_action(self.sim, self.name, action)
            self.sim.step()
            if on_substep is not None:
                on_substep(self)

    def close(self):
        try:
            self.sim.close()
        except Exception:
            pass


class BrainInterface:
    """The brain side of the loop: ORN input in (DM1 by default), read-out DN
    rates out. Both ends are swappable: ``orn_type`` and ``mapping``."""

    def __init__(self, brain, silence="none", seed=0, mapping=None, orn_type="ORN_DM1"):
        self.left_ids, self.right_ids = orn_ids(orn_type)
        self.orn_ids = np.concatenate([self.left_ids, self.right_ids])
        mapping = mapping if mapping is not None else DriveMapping()
        ids = mapping.neuron_ids                  # the swappable read-out
        self.dn_names = mapping.readout_names
        self.dn_idx = brain.index_of([ids[n] for n in self.dn_names])
        if silence == "dns":
            sil = [ids[n] for n in self.dn_names]
        elif silence == "orns":
            sil = list(self.orn_ids)
        elif silence == "none":
            sil = []
        else:
            raise ValueError(f"unknown silence {silence!r}")
        self.silence = silence
        self.stepper = BrainStepper(brain, self.orn_ids, silence=sil, seed=seed)

    def run_window(self, orn_rates, window_ms):
        """Returns (rates the BODY receives, rates the DNs actually fired)."""
        w = self.stepper.step(orn_rates, window_ms)
        fired = dict(zip(self.dn_names, w.rates_hz(self.dn_idx).astype(float)))
        seen = dict(fired)
        if self.silence == "dns":          # their output is cut: body gets nothing
            seen = {k: 0.0 for k in fired}
        return seen, fired


def run_trial(cfg: TrialConfig, brain=None, log=None, on_substep=None):
    """Run one closed-loop trial. ``brain`` (a FastBrain) is needed when
    ``cfg.steering == "brain"``. Returns a dict with one row per window.
    ``on_substep``: optional read-only hook, see the module docstring."""
    source = np.array([[cfg.source_xy_mm[0], cfg.source_xy_mm[1], SOURCE_Z_MM]])
    world = OdorWorld(source) if cfg.odor_on else OdorWorld.no_odor(source)
    body = Body(cfg.spawn_xy_mm, cfg.spawn_heading_rad, seed=cfg.seed)
    iface = None
    if cfg.steering == "brain":
        if brain is None:
            raise ValueError("steering='brain' needs a brain")
        bseed = cfg.seed if cfg.brain_seed is None else cfg.brain_seed
        iface = BrainInterface(brain, cfg.silence, bseed, cfg.drive_mapping, cfg.orn_type)
    win_s = cfg.window_ms * 1e-3
    n_win = int(round(cfg.duration_s / win_s))
    rows = []
    t_brain = t_body = 0.0
    reached_at = None
    for k in range(n_win):
        x, y, head = body.pose()
        inten = world.intensity(body.odor_sensor_positions())       # SENSOR_ORDER
        i_l, i_r = inten[SENSOR_ORDER.index("LAntenna")], inten[SENSOR_ORDER.index("RAntenna")]
        row = {"window": k, "t_s": body.time_s, "x_mm": x, "y_mm": y, "heading_rad": head,
               "dist_mm": float(np.hypot(x - source[0, 0], y - source[0, 1])),
               "I_Lpalp": inten[0], "I_Rpalp": inten[1], "I_Lant": i_l, "I_Rant": i_r}
        t0 = time.perf_counter()
        if cfg.steering == "brain":
            sm = cfg.sensor_mapping
            rl, rr = sm.side_rates(i_l, i_r)          # = sm.rate() unless one antenna is covered
            rates = sm.orn_rates(i_l, i_r, iface.left_ids.size, iface.right_ids.size)
            seen, fired = iface.run_window(rates, cfg.window_ms)
            drive, turn, fwd = cfg.drive_mapping.drive(seen)
            row.update({"orn_rate_L": rl, "orn_rate_R": rr})
            row.update({f"{n}_hz": fired[n] for n in fired})
            row["brain_neurons_reached"] = iface.stepper.n_active
        elif cfg.steering == "hand_rule":                            # NOT brain-driven
            turn, fwd = published_taxis_turn(inten), 1.0
            drive = turn_to_drive(turn, fwd)
        elif cfg.steering == "straight":
            turn, fwd, drive = 0.0, 1.0, np.array([1.0, 1.0])
        else:
            raise ValueError(f"unknown steering {cfg.steering!r}")
        t1 = time.perf_counter()
        body.step(drive, win_s, on_substep=on_substep)
        t2 = time.perf_counter()
        t_brain += t1 - t0
        t_body += t2 - t1
        row.update({"turn": turn, "forward": fwd, "drive_L": drive[0], "drive_R": drive[1]})
        rows.append(row)
        if log and k % 10 == 0:
            log(f"  [{cfg.name}] t={row['t_s']:.2f}s dist={row['dist_mm']:.1f}mm turn={turn:+.2f} "
                f"drive=({drive[0]:.2f},{drive[1]:.2f})")
        if row["dist_mm"] < REACH_MM and reached_at is None:
            reached_at = row["t_s"]
            if cfg.stop_at_source:
                break
    x, y, head = body.pose()
    final = {"t_s": body.time_s, "x_mm": x, "y_mm": y, "heading_rad": head,
             "dist_mm": float(np.hypot(x - source[0, 0], y - source[0, 1])),
             "thorax_z_mm": body.thorax_z()}
    if final["dist_mm"] < REACH_MM and reached_at is None:
        reached_at = final["t_s"]
    body.close()
    return {"config": cfg, "rows": rows, "final": final, "reached_at_s": reached_at,
            "wall_brain_s": t_brain, "wall_body_s": t_body}
