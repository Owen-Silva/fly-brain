"""Phase 9 video, step 2 of 2: draw the four clips, add the caption bars and
write the MP4s.

Plain English: step 1 (simulate_clips.py) re-ran four trials of the DA1 demo
and saved the fly's full pose every 1 ms. This script poses the fly in each
saved pose and photographs it with a fixed camera, marks the smell source,
draws the path walked so far, and adds a caption bar with the numbers the
loop used in each 50 ms window (results/clip_<k>_windows.csv, which step 1
checked against the saved DA1 trials). Nothing here re-runs the brain or the
physics: the fly is only posed, never stepped.

Colours, light and floor shade are changed on a separate, render-only copy
of the body model. The physics model that produced the trials is untouched.

Outputs (experiments/phase9_video/):
  clip_a_one_antenna_brain.mp4, clip_b_dna02_silenced.mp4,
  clip_c_normal_fly.mp4, clip_d_hand_rule.mp4   the four clips
  phase9_video.mp4     the four clips in sequence, each after a title card
  poster.png           one frame of clip a
  results/render_check.csv   posed fly vs the trial's own path, per window
  results/render.log

Run: .venv-body\\Scripts\\python.exe experiments/phase9_video/render_video.py [--test]
(--test writes a few still frames to results/test_frames/ and no video)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import mujoco
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sim.body.loop import REACH_MM, SOURCE_Z_MM, Body  # noqa: E402

HERE = ROOT / "experiments" / "phase9_video"
STATES, RESULTS = HERE / "states", HERE / "results"

# ---------------------------------------------------------------------------
# Frame and video settings
# ---------------------------------------------------------------------------
W = 1280                        # output width (px); the brief allows at most 1280
TOP_H, VIEW_H, BOT_H = 118, 780, 238
H = TOP_H + VIEW_H + BOT_H      # 1136 = 71 x 16
FPS = 30                        # output frames per second
SPEED = 0.5                     # half speed: 1 s of fly time = 2 s of video
HOLD_S = 1.2                    # last frame held at the end of each clip
CARD_S = 5.0                    # title card before each clip (composite only)
INTRO_S, END_S = 6.0, 7.0
CRF = 18                        # H.264 quality (lower = better and bigger)
POSTER_T = 1.0                  # fly time of the poster frame (clip a)
DN_AVG_WINDOWS = 5              # DNa02 rate shown = mean of the last 5 x 50 ms

# Colours (3D, 0-1) and panel colours (0-255)
SOURCE_RGB = (0.50, 0.20, 0.70)
TRAIL_RGB = (0.12, 0.30, 0.58)
FLY_BODY = (0.80, 0.63, 0.42, 1.0)
FLY_EYE = (0.62, 0.12, 0.10, 1.0)
FLY_WING = (0.86, 0.86, 0.90, 0.30)
TRAIL_SMOOTH_S = 0.083          # path drawn = thorax position averaged over one stride
TRAIL_EVERY_S = 0.005           # (FlyGym's walking rhythm is 12 Hz: 83 ms per stride)
FLOOR = (196, 214)              # the two checker shades
BG, TEXT, MUTED = (30, 31, 34), (242, 242, 242), (172, 174, 179)
C_BRAIN, C_RULE, C_NONE = (126, 205, 160), (242, 178, 82), (190, 192, 197)
C_LEFT, C_RIGHT, C_TRACK = (104, 166, 236), (236, 150, 88), (62, 64, 70)
LABEL_RGB = (74, 24, 104)

# The four clips. Condition names and texts are plain English on purpose.
CLIPS = {
    "a": dict(
        file="clip_a_one_antenna_brain.mp4", pair="ab",
        title="A. One antenna covered, brain steers (DNa02)",
        sub="Right antenna covered: only the left one smells. Source on the fly's left.",
        turning=("Turning: brain-driven (DNa02)", C_BRAIN),
        card=["A. One antenna covered, the brain steers",
              "Only the LEFT antenna can smell. The source is on the fly's left.",
              "Watch: it turns left, toward the side that smells."]),
    "b": dict(
        file="clip_b_dna02_silenced.mp4", pair="ab",
        title="B. Same trial, DNa02 silenced (control)",
        sub="DNa02's output is cut, so the body gets no turn command at all.",
        turning=("Turning: none from the brain (DNa02 silenced)", C_NONE),
        card=["B. The same trial with DNa02 silenced",
              "The brain's steering neurons are cut off from the body.",
              "Watch: it walks straight. (The slight drift comes from the body.)"]),
    "c": dict(
        file="clip_c_normal_fly.mp4", pair="cd",
        title="C. Normal fly, both antennae, source on the right",
        sub="Both antennae smell. The source is front-right of the fly.",
        turning=("Turning: brain-driven (DNa02)", C_BRAIN),
        card=["C. Normal fly, both antennae, source on the right",
              "The antennae are 0.3 mm apart, so both smell almost the same.",
              "Watch: the brain turns it LEFT anyway, away from the source."]),
    "d": dict(
        file="clip_d_hand_rule.mp4", pair="cd",
        title="D. Hand-written rule, NOT brain-driven (reference)",
        sub="No brain here: FlyGym 1.x's smell rule compares left and right.",
        turning=("Turning: NOT brain-driven (hand-written rule)", C_RULE),
        card=["D. Hand-written rule, NOT brain-driven",
              "No brain: a simple rule steers toward the stronger-smelling side.",
              "Watch: it turns right and reaches the source."]),
}
INTRO = ["Can a brain model steer a simulated fly to a smell?",
         "Purple ball = smell source (cVA, a fly pheromone).",
         "The brain only chooses LEFT or RIGHT.",
         "Legs, rhythm and speed come from FlyGym, NOT from the brain.",
         "Shown at half speed. Each clip is up to 1.5 s of fly time."]
OUTRO = ["Result: PARTIAL (preliminary)",
         "One antenna covered: the brain turns toward the smelling side.",
         "With both antennae it turns left, whichever side the smell is on.",
         "Walking itself was never brain-driven."]
LEGS_LINE = "Legs, walking rhythm and speed: FlyGym's built-in controller, NOT brain-driven."

# One fixed camera per pair, so a vs b and c vs d are seen identically
# (azimuth, elevation in degrees). a/b: from the fly's right side (the fly
# starts facing right; its left is the far side). c/d: from behind the fly
# (it starts facing away; its left is screen-left). Each direction was chosen
# because it shows that pair's paths with the largest fly. Where it looks and
# how far away it is are computed so both paths and the source stay in view.
PAIRS = {"ab": dict(az=90.0, el=-50.0), "cd": dict(az=0.0, el=-50.0)}
FRAME_MARGIN_PX = 36


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "render.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_clip(k):
    z = np.load(STATES / f"clip_{k}.npz")
    meta = json.loads(str(z["meta"]))
    rows = pd.read_csv(RESULTS / f"clip_{k}_windows.csv")
    return dict(key=k, steps=z["steps"], qpos=z["qpos"], pre_steps=z["pre_steps"],
                pre_qpos=z["pre_qpos"], meta=meta, rows=rows, t0=float(z["window_t0"]),
                **CLIPS[k])


def trial_end_s(clip):
    return len(clip["rows"]) * clip["meta"]["window_ms"] * 1e-3


# ---------------------------------------------------------------------------
# The render-only model
# ---------------------------------------------------------------------------
class Stage:
    """A fresh Body built exactly like the trial's (same spawn and seed), used
    only to pose and photograph the fly. Visual settings are edited on this
    copy only; it is never stepped."""

    def __init__(self, meta, cam):
        self.body = Body(tuple(meta["spawn_xy_mm"]), meta["spawn_heading_rad"], seed=meta["seed"])
        m, d = self.body.sim.mj_model, self.body.sim.mj_data
        self.m, self.d = m, d
        self.q0 = np.array(d.qpos)          # = the state at the start of the trial
        self.dt = float(m.opt.timestep)
        for i in range(m.ngeom):            # colour the fly (render copy only)
            if m.geom_bodyid[i] == 0:
                continue
            name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i) or ""
            m.geom_rgba[i] = FLY_EYE if "eye" in name else FLY_WING if "wing" in name else FLY_BODY
        for t in range(m.ntex):             # lighter floor checker
            if m.tex_type[t] != mujoco.mjtTexture.mjTEXTURE_2D:
                continue
            a, n = m.tex_adr[t], m.tex_width[t] * m.tex_height[t] * m.tex_nchannel[t]
            px = np.array(m.tex_data[a:a + n]).reshape(-1, m.tex_nchannel[t]).astype(float)
            dark = px[:, :3].mean(1) < px[:, :3].mean()
            px[dark, :3], px[~dark, :3] = FLOOR[0], FLOOR[1]
            m.tex_data[a:a + n] = px.astype(np.uint8).ravel()
        m.mat_reflectance[:] = 0.0          # no mirror image of the source in the floor
        m.vis.headlight.ambient[:] = 0.25
        m.vis.headlight.diffuse[:] = 0.30
        m.vis.headlight.specular[:] = 0.05
        m.stat.extent = 30.0                # sets the shadow area (render copy only)
        m.vis.map.znear = 0.002
        m.vis.map.zfar = 20.0
        self.r = mujoco.Renderer(m, VIEW_H, W)
        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.cam.lookat[:] = cam["lookat"]
        self.cam.distance = cam["dist"]
        self.cam.azimuth = cam["az"]
        self.cam.elevation = cam["el"]

    def pose(self, q):
        self.d.qpos[:] = q
        self.d.qvel[:] = 0.0
        mujoco.mj_forward(self.m, self.d)
        return self.body.pose()

    def _geom(self, gtype, size, pos, rgba, mat=None):
        scn = self.r.scene
        if scn.ngeom >= scn.maxgeom:
            return None
        g = scn.geoms[scn.ngeom]
        scn.ngeom += 1
        mujoco.mjv_initGeom(g, gtype, np.asarray(size, float), np.asarray(pos, float),
                            (np.eye(3) if mat is None else mat).ravel().astype(float),
                            np.asarray(rgba, np.float32))
        return g

    def _segment(self, p0, p1, radius, rgba):
        g = self._geom(mujoco.mjtGeom.mjGEOM_CAPSULE, [0, 0, 0], [0, 0, 0], rgba)
        if g is not None:
            mujoco.mjv_connector(g, mujoco.mjtGeom.mjGEOM_CAPSULE, radius,
                                 np.asarray(p0, float), np.asarray(p1, float))

    def photo(self, q, source_xy, trail_xy, start_xy, markers=()):
        self.pose(q)
        self.r.update_scene(self.d, camera=self.cam)
        scn = self.r.scene
        # One overhead light with shadows (added to the picture, not the model).
        if scn.nlight < len(scn.lights):
            L = scn.lights[scn.nlight]
            scn.nlight += 1
            L.type = mujoco.mjtLightType.mjLIGHT_DIRECTIONAL
            dvec = np.array([0.25, 0.35, -1.0])
            L.dir[:] = dvec / np.linalg.norm(dvec)
            L.pos[:] = np.array([self.cam.lookat[0], self.cam.lookat[1], 0.0]) - 40.0 * L.dir
            L.castshadow = True
            L.headlight = False
            L.ambient[:] = 0.05
            L.diffuse[:] = 0.45
            L.specular[:] = 0.10
            L.attenuation[:] = [1.0, 0.0, 0.0]
            L.cutoff, L.exponent = 180.0, 0.0
        sx, sy = source_xy
        # "Reached" zone: a ring 2 mm around the source.
        ang = np.linspace(0, 2 * np.pi, 61)
        ring = np.c_[sx + REACH_MM * np.cos(ang), sy + REACH_MM * np.sin(ang), np.full(61, 0.02)]
        for p0, p1 in zip(ring[:-1], ring[1:]):
            self._segment(p0, p1, 0.03, (*SOURCE_RGB, 0.75))
        # Stalk down to the floor and the source ball (1.5 mm above the floor).
        self._segment([sx, sy, 0.0], [sx, sy, SOURCE_Z_MM], 0.045, (*SOURCE_RGB, 0.9))
        g = self._geom(mujoco.mjtGeom.mjGEOM_SPHERE, [0.38, 0, 0], [sx, sy, SOURCE_Z_MM],
                       (*SOURCE_RGB, 1.0))
        if g is not None:
            g.emission = 0.25
        # Start mark and the path walked so far.
        self._geom(mujoco.mjtGeom.mjGEOM_CYLINDER, [0.28, 0.003, 0], [*start_xy, 0.008],
                   (0.25, 0.25, 0.28, 0.55))
        for p0, p1 in zip(trail_xy[:-1], trail_xy[1:]):
            self._segment([*p0, 0.03], [*p1, 0.03], 0.06, (*TRAIL_RGB, 1.0))
        for mk in markers:                  # test mode only
            self._geom(mujoco.mjtGeom.mjGEOM_SPHERE, [0.12, 0, 0], mk, (0.9, 0.1, 0.1, 1))
        return self.r.render().copy()

    def close(self):
        self.r.close()
        self.body.close()


# ---------------------------------------------------------------------------
# Camera framing
# ---------------------------------------------------------------------------
def cam_axes(az, el):
    a, e = np.radians(az), np.radians(el)
    f = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    u = np.array([-np.sin(e) * np.cos(a), -np.sin(e) * np.sin(a), np.cos(e)])
    return f, u, np.cross(f, u)


def project(P, cam, fovy=45.0, w=W, h=VIEW_H):
    """World points (n, 3) -> pixel x, y in the 3D view (MuJoCo free camera)."""
    f, u, r = cam_axes(cam["az"], cam["el"])
    pos = np.asarray(cam["lookat"], float) - cam["dist"] * f
    rel = np.atleast_2d(np.asarray(P, float)) - pos
    zc = rel @ f
    s = (h / 2) / np.tan(np.radians(fovy) / 2)
    return w / 2 + (rel @ r) / zc * s, h / 2 - (rel @ u) / zc * s, zc


def fit_camera(P, az, el, fovy=45.0, margin=FRAME_MARGIN_PX):
    P = np.asarray(P, float)
    cam = dict(az=az, el=el, lookat=np.array([(P[:, 0].min() + P[:, 0].max()) / 2,
                                              (P[:, 1].min() + P[:, 1].max()) / 2, 0.0]),
               dist=100.0)
    f, _, r = cam_axes(az, el)
    fg = np.array([f[0], f[1], 0.0]) / np.hypot(f[0], f[1])
    for it in range(10):
        if it:
            px, py, _ = project(P, cam, fovy)
            cx = (px.min() + px.max()) / 2 - W / 2
            cy = (py.min() + py.max()) / 2 - VIEW_H / 2
            k = cam["dist"] * np.tan(np.radians(fovy) / 2) / (VIEW_H / 2)
            cam["lookat"] = cam["lookat"] + r * cx * k - fg * cy * k / abs(np.sin(np.radians(el)))
        lo, hi = 1.0, 2000.0
        for _ in range(60):
            cam["dist"] = (lo + hi) / 2
            px, py, zc = project(P, cam, fovy)
            ok = ((zc > 1.0).all() and px.min() >= margin and px.max() <= W - margin
                  and py.min() >= margin and py.max() <= VIEW_H - margin)
            lo, hi = (lo, cam["dist"]) if ok else (cam["dist"], hi)
        cam["dist"] = hi
    return cam


def framing_points(clip):
    rows, meta = clip["rows"], clip["meta"]
    xy = np.vstack([rows[["x_mm", "y_mm"]].to_numpy(),
                    [[meta["final"]["x_mm"], meta["final"]["y_mm"]]]])
    pts = []
    for dx, dy in ((1.7, 0), (-1.7, 0), (0, 1.7), (0, -1.7)):   # room for the fly's body
        for z in (0.0, 0.9):
            pts.append(np.c_[xy + [dx, dy], np.full(len(xy), z)])
    sx, sy = meta["source_xy_mm"]
    r = REACH_MM + 0.3                                  # the whole 2 mm ring
    pts.append(np.array([[sx, sy, SOURCE_Z_MM + 0.4], [sx - r, sy, 0], [sx + r, sy, 0],
                         [sx, sy - r, 0], [sx, sy + r, 0]]))
    return np.vstack(pts)


def smoothed_path(xy_1ms):
    """Thorax path averaged over the last stride (causal), one point per 5 ms.
    The thorax sways sideways with every step; this shows the walking line."""
    n = int(round(TRAIL_SMOOTH_S / 1e-3))
    c = np.cumsum(np.vstack([[0.0, 0.0], xy_1ms]), axis=0)
    i = np.arange(1, len(xy_1ms) + 1)
    lo = np.maximum(0, i - n)
    return (c[i] - c[lo]) / (i - lo)[:, None]


# ---------------------------------------------------------------------------
# Captions
# ---------------------------------------------------------------------------
def _font(size, bold=False):
    names = ["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(str(Path("C:/Windows/Fonts") / n), size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


F = {"title": _font(40, True), "sub": _font(30), "time": _font(40, True),
     "row": _font(33), "rowb": _font(35, True), "small": _font(29), "label": _font(30, True),
     "note": _font(34, True), "card_t": _font(54, True), "card": _font(40),
     "card_s": _font(34)}


def _w(draw, text, font):
    return draw.textlength(text, font=font)


def _fit(draw, text, font_key, max_w):
    f = F[font_key]
    size = f.size
    while _w(draw, text, f) > max_w and size > 16:
        size -= 1
        f = _font(size, bold=font_key in ("title", "time", "rowb", "label", "note", "card_t"))
    return f


def frame_info(clip, t):
    """Values shown at fly time t (s since the trial started): those the loop
    used in the 50 ms window containing t."""
    rows = clip["rows"]
    win = clip["meta"]["window_ms"] * 1e-3
    j = min(int(np.floor(t / win + 1e-9)), len(rows) - 1)
    r = rows.iloc[j]
    lo = max(0, j - DN_AVG_WINDOWS + 1)
    info = {"t": t, "window": j, "I_L": float(r.I_Lant), "I_R": float(r.I_Rant),
            "turn": float(r.turn), "turn_avg": float(rows.turn.iloc[lo:j + 1].mean()),
            "drive_L": float(r.drive_L), "drive_R": float(r.drive_R)}
    if "DNa02_L_hz" in rows:
        info["dn_L"] = float(rows.DNa02_L_hz.iloc[lo:j + 1].mean())
        info["dn_R"] = float(rows.DNa02_R_hz.iloc[lo:j + 1].mean())
    return info


def _bar(draw, x, y, w, h, frac, colour):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=C_TRACK)
    frac = float(np.clip(frac, 0.0, 1.0))
    if frac > 0.004:
        draw.rounded_rectangle([x, y, x + max(h, int(w * frac)), y + h], radius=h // 2, fill=colour)


SOURCE_LABEL = "smell source (cVA)"


def source_label_anchor(src, path_xy, cam):
    """Top-left corner of the source label, fixed for the whole clip: above,
    right of, left of or below the ball, whichever stays furthest from the
    fly's path (so the label never covers the fly)."""
    dr = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw, th = _w(dr, SOURCE_LABEL, F["label"]) + 16, 42
    bx, by, _ = project([[src[0], src[1], SOURCE_Z_MM]], cam)
    bx, by = float(bx[0]), float(by[0]) + TOP_H
    gy = float(project([[src[0], src[1], 0.0]], cam)[1][0]) + TOP_H
    px, py, _ = project(np.c_[path_xy[::10], np.full(len(path_xy[::10]), 0.3)], cam)
    py = py + TOP_H
    cands = [(bx - tw / 2, by - 40 - th), (bx + 34, by - th / 2), (bx - 34 - tw, by - th / 2),
             (bx - tw / 2, max(by, gy) + 34)]
    best, best_score = None, -1.0
    for n, (x0, y0) in enumerate(cands):
        x1, y1 = x0 + tw, y0 + th
        if x0 < 6 or x1 > W - 6 or y0 < TOP_H + 6 or y1 > TOP_H + VIEW_H - 6:
            continue
        dx = np.maximum.reduce([x0 - px, np.zeros_like(px), px - x1])
        dy = np.maximum.reduce([y0 - py, np.zeros_like(py), py - y1])
        score = float(np.hypot(dx, dy).min()) - 5.0 * n       # prefer "above" if close
        if score > best_score:
            best, best_score = (x0 + 8, y0 + 2), score
    return None if best is None else (int(best[0]), int(best[1]))


def compose(clip, view, info, label_at=None, note=None):
    im = Image.new("RGB", (W, H), BG)
    im.paste(Image.fromarray(view), (0, TOP_H))
    dr = ImageDraw.Draw(im)
    pad = 26
    # --- top band: condition name, set-up, time
    t_txt = f"{info['t']:.2f} s"
    t_w = _w(dr, t_txt, F["time"])
    dr.text((W - pad - t_w, 12), t_txt, font=F["time"], fill=TEXT)
    hs = "half speed"
    dr.text((W - pad - _w(dr, hs, F["small"]), 66), hs, font=F["small"], fill=MUTED)
    dr.text((pad, 12), clip["title"], font=_fit(dr, clip["title"], "title", W - 3 * pad - t_w),
            fill=TEXT)
    dr.text((pad, 66), clip["sub"], font=_fit(dr, clip["sub"], "sub", W - 3 * pad - 150),
            fill=MUTED)
    # --- label next to the source ball (in the 3D view)
    if label_at is not None:
        x, y = label_at
        tw = _w(dr, SOURCE_LABEL, F["label"])
        dr.rounded_rectangle([x - 8, y - 2, x + tw + 8, y + 38], radius=8, fill=(250, 250, 250))
        dr.text((x, y), SOURCE_LABEL, font=F["label"], fill=LABEL_RGB)
    # scale: the floor squares are 4 mm (checked with markers every 4 mm, --test)
    sc = "floor squares: 4 mm"
    sx0, sy0 = 14, TOP_H + VIEW_H - 50
    dr.rounded_rectangle([sx0, sy0, sx0 + _w(dr, sc, F["small"]) + 20, sy0 + 38], radius=8,
                         fill=(246, 246, 246))
    dr.text((sx0 + 10, sy0 + 1), sc, font=F["small"], fill=(70, 70, 76))
    if note:
        nw = _w(dr, note, F["note"])
        x, y = int((W - nw) / 2), TOP_H + 16
        dr.rounded_rectangle([x - 16, y - 6, x + nw + 16, y + 48], radius=10, fill=BG)
        dr.text((x, y), note, font=F["note"], fill=TEXT)
    # --- bottom panel
    y0 = TOP_H + VIEW_H + 14
    label, colour = clip["turning"]
    turn = info["turn_avg"]             # same 0.25 s as the DNa02 rates below
    if clip["key"] == "b":
        steer = "steering: none"
    elif abs(turn) < 0.005:
        steer = "steering: straight"
    else:
        steer = f"steering: {'LEFT' if turn > 0 else 'RIGHT'} {abs(turn) * 100:.0f}%"
    if clip["key"] == "d":
        steer = "rule " + steer
    sw = _w(dr, steer, F["rowb"])
    sw_max = _w(dr, ("rule " if clip["key"] == "d" else "") + "steering: RIGHT 100%", F["rowb"])
    dr.text((W - pad - sw, y0), steer, font=F["rowb"], fill=TEXT)
    dr.text((pad, y0), label, font=_fit(dr, label, "rowb", W - 3 * pad - sw_max), fill=colour)
    col_l, col_r, bar_w, bar_h = 330, 790, 190, 22
    # row: DNa02
    y1 = y0 + 56
    dr.text((pad, y1), "DNa02 firing", font=F["row"], fill=MUTED)
    if "dn_L" in info:
        for x, side, val, c in ((col_l, "Left", info["dn_L"], C_LEFT),
                                (col_r, "Right", info["dn_R"], C_RIGHT)):
            dr.text((x, y1), side, font=F["row"], fill=TEXT)
            _bar(dr, x + 88, y1 + 12, bar_w, bar_h, val / 25.0, c)
            dr.text((x + 100 + bar_w, y1), f"{val:.0f} Hz", font=F["row"], fill=TEXT)
    else:
        dr.text((col_l, y1), "not used: no brain in this clip", font=F["row"], fill=TEXT)
    # row: antenna smell
    y2 = y1 + 50
    dr.text((pad, y2), "Smell at antenna", font=F["row"], fill=MUTED)
    ant = clip["meta"]["antennae"]
    for x, side, val, c, covered in ((col_l, "Left", info["I_L"], C_LEFT, ant == "right_only"),
                                     (col_r, "Right", info["I_R"], C_RIGHT, ant == "left_only")):
        dr.text((x, y2), side, font=F["row"], fill=TEXT)
        if covered:
            _bar(dr, x + 88, y2 + 12, bar_w, bar_h, 0.0, c)
            dr.text((x + 100 + bar_w, y2), "covered", font=F["row"], fill=MUTED)
        else:
            _bar(dr, x + 88, y2 + 12, bar_w, bar_h, val / (val + 0.01), c)
            dr.text((x + 100 + bar_w, y2), f"{val:.3f}", font=F["row"], fill=TEXT)
    # row: what is never brain-driven
    y3 = y2 + 54
    dr.text((pad, y3), LEGS_LINE, font=_fit(dr, LEGS_LINE, "small", W - 2 * pad), fill=MUTED)
    return np.asarray(im)


def card(lines):
    im = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(im)
    pad = 70
    title, body = lines[0], lines[1:]
    ft = _fit(dr, title, "card_t", W - 2 * pad)
    heights = [ft.size + 36] + [F["card"].size + 26] * len(body)
    y = int((H - sum(heights)) / 2)
    dr.text((pad, y), title, font=ft, fill=TEXT)
    y += heights[0]
    for line in body:
        f = _fit(dr, line, "card", W - 2 * pad)
        dr.text((pad, y), line, font=f, fill=TEXT if line.startswith("Watch") else MUTED)
        y += F["card"].size + 26
    return np.asarray(im)


# ---------------------------------------------------------------------------
# Video writing
# ---------------------------------------------------------------------------
def writer(path):
    w = imageio_ffmpeg.write_frames(
        str(path), (W, H), fps=FPS, codec="libx264", pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p", quality=None, macro_block_size=16,
        output_params=["-crf", str(CRF), "-preset", "slow", "-movflags", "+faststart"])
    w.send(None)
    return w


def probe(path):
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    r = subprocess.run([exe, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    lines = [ln.strip() for ln in r.stderr.splitlines() if "Duration" in ln or "Video:" in ln]
    return " | ".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def clip_frames(clip, stage, cam, check_rows):
    """Yields composed frames for one clip; appends the pose check rows."""
    meta, rows = clip["meta"], clip["rows"]
    assert abs(stage.dt - meta["physics_dt_s"]) < 1e-12, "physics timestep changed"
    pre = {int(s): i for i, s in enumerate(clip["pre_steps"])}
    win_steps = int(round(meta["window_ms"] * 1e-3 / stage.dt))
    # 1) Posed fly vs the trial's own logged path, at every window start
    #    (j >= 1) and at the end. The loop logs body positions right after a
    #    physics step, and MuJoCo computes those from the state BEFORE that
    #    step, so the logged pose of window j belongs to the state saved one
    #    step before the boundary (step j*500 - 1). Window 0's is inside the
    #    warm-up, which is not recorded.
    for j in range(1, len(rows) + 1):
        s = j * win_steps - 1
        if s not in pre:
            continue
        q = clip["pre_qpos"][pre[s]]
        x, y, h = stage.pose(q)
        ref = rows.iloc[j] if j < len(rows) else pd.Series(
            {"x_mm": meta["final"]["x_mm"], "y_mm": meta["final"]["y_mm"],
             "heading_rad": meta["final"]["heading_rad"]})
        check_rows.append({"clip": clip["key"], "window": j, "dx_mm": abs(x - ref.x_mm),
                           "dy_mm": abs(y - ref.y_mm),
                           "dheading_deg": abs(np.degrees(np.angle(np.exp(1j * (h - ref.heading_rad))))),
                           "trail_vs_thorax_mm": float(np.hypot(*(np.asarray(q[:2]) - [x, y])))})
    # 2) Frames.
    t_end = trial_end_s(clip)
    n_frames = int(np.floor(t_end * FPS / SPEED + 1e-9)) + 1
    all_xy = np.vstack([stage.q0[:2], clip["qpos"][:, :2]])          # thorax path, 1 ms
    all_steps = np.concatenate([[0], clip["steps"]])
    path = smoothed_path(all_xy)
    every = int(round(TRAIL_EVERY_S / 1e-3))
    src = meta["source_xy_mm"]
    start_xy = stage.q0[:2]
    label_at = source_label_anchor(src, all_xy, cam)
    last = None
    for k in range(n_frames):
        t = k * SPEED / FPS
        step = int(round(t / stage.dt))
        i = int(np.argmin(np.abs(all_steps - step)))
        q = stage.q0 if i == 0 else clip["qpos"][i - 1]
        trail = np.vstack([path[: i + 1: every], path[i]])
        view = stage.photo(q, src, trail, start_xy)
        info = frame_info(clip, t)
        last = (view, info)
        yield compose(clip, view, info, label_at), t
    view, info = last
    if meta["reached_at_s"] is not None:
        note = f"Reached the source (within 2 mm) at {meta['reached_at_s'] - clip['t0']:.2f} s: trial stops"
    else:
        note = f"End of trial ({t_end:.1f} s of fly time)"
    held = compose(clip, view, info, label_at, note=note)
    for _ in range(int(round(HOLD_S * FPS))):
        yield held, None


def main(test=False):
    clips = {k: load_clip(k) for k in CLIPS}
    cams = {}
    for pair, p in PAIRS.items():
        pts = np.vstack([framing_points(c) for c in clips.values() if c["pair"] == pair])
        cams[pair] = fit_camera(pts, p["az"], p["el"])
        c = cams[pair]
        log(f"camera {pair}: azimuth {c['az']:.0f}, elevation {c['el']:.0f}, lookat "
            f"({c['lookat'][0]:.2f}, {c['lookat'][1]:.2f}), distance {c['dist']:.2f} mm")
    check_rows = []
    if test:
        out = RESULTS / "test_frames"
        out.mkdir(parents=True, exist_ok=True)
        for k, clip in clips.items():
            cam = cams[clip["pair"]]
            stage = Stage(clip["meta"], cam)
            frames = list(clip_frames(clip, stage, cam, check_rows))
            for fr, t in frames[:: max(1, len(frames) // 3)] + [frames[-1]]:
                name = f"clip_{k}_{'hold' if t is None else f'{t:.2f}s'}.png"
                Image.fromarray(fr).save(out / name)
            # checker size test: red dots every 4 mm near the start
            marks = [[4.0 * i, 4.0 * j, 0.02] for i in range(-1, 5) for j in range(-2, 4)]
            view = stage.photo(stage.q0, clip["meta"]["source_xy_mm"], stage.q0[None, :2],
                               stage.q0[:2], markers=marks)
            Image.fromarray(view).save(out / f"clip_{k}_grid4mm.png")
            stage.close()
        pd.DataFrame(check_rows).to_csv(out / "render_check_test.csv", index=False)
        log(f"test frames written to {out}")
        return
    composite = writer(HERE / "phase9_video.mp4")
    for _ in range(int(INTRO_S * FPS)):
        composite.send(card(INTRO))
    for k, clip in clips.items():
        cam = cams[clip["pair"]]
        stage = Stage(clip["meta"], cam)
        cf = card(clip["card"])
        for _ in range(int(CARD_S * FPS)):
            composite.send(cf)
        w = writer(HERE / clip["file"])
        n = 0
        for fr, t in clip_frames(clip, stage, cam, check_rows):
            w.send(fr)
            composite.send(fr)
            n += 1
            if k == "a" and t is not None and abs(t - POSTER_T) < 1e-9:
                Image.fromarray(fr).save(HERE / "poster.png")
        w.close()
        stage.close()
        log(f"clip {k}: {n} frames -> {clip['file']} ({(HERE / clip['file']).stat().st_size / 1e6:.2f} MB)")
    oc = card(OUTRO)
    for _ in range(int(END_S * FPS)):
        composite.send(oc)
    composite.close()
    chk = pd.DataFrame(check_rows)
    chk.to_csv(RESULTS / "render_check.csv", index=False)
    for k, g in chk.groupby("clip"):
        log(f"clip {k}: posed fly vs trial path, largest difference x {g.dx_mm.max():.2g} mm, "
            f"y {g.dy_mm.max():.2g} mm, heading {g.dheading_deg.max():.2g} deg "
            f"({len(g)} window starts); trail point vs thorax {g.trail_vs_thorax_mm.max():.2g} mm")
    for p in [HERE / "phase9_video.mp4"] + [HERE / c["file"] for c in CLIPS.values()]:
        log(f"{p.name}: {p.stat().st_size / 1e6:.2f} MB; {probe(p)}")
    log(f"poster.png: {(HERE / 'poster.png').stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main(test="--test" in sys.argv[1:])
