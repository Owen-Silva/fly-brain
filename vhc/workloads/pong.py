"""Workload (f), new in v1: DishBrain-style closed-loop Pong (Kagan et al. 2022, Neuron).

The game, as DishBrain ran it (settings in vhc/prices.py DISHBRAIN, all PUBLISHED):
  * every 10 ms: motor-region spikes are counted and move the paddle; the game advances;
  * the ball's position RELATIVE to the paddle picks one of 8 stimulation sites (place code),
    at 4 Hz with the ball far away rising to 40 Hz at the paddle wall (rate code), 75 mV;
  * hit: 100 ms of 100 Hz pulses on all 8 sites (predictable feedback);
  * miss: 4 s of 150 mV pulses at 5 Hz on random sites (unpredictable), 4 s rest, next rally;
  * 20-minute sessions; score = hits per rally; T1 = minutes 0-5, T2 = minutes 6-20.
Our choices (labelled):
  * FITTED: paddle half-height, so that a paddle driven by noise scores DishBrain's in-silico
    control (0.80 hits per rally); ball crossing time 3.5 s, DERIVED from 69 rallies per
    session with 8 s of feedback and rest per miss;
  * GUESSED: paddle top speed (1 field height per second), the motor read-out rule
    (paddle speed = top speed x tanh((up - down) / sqrt(up + down + 1))), the layout, and the
    learning rule below. Layout "mid" (default): 8 sites in a row across the middle of the
    dish; every electrode more than 100 um from a site is a motor electrode, in four vertical
    strips "up, down, up, down" (DishBrain's counterbalanced idea). So a site's own neighbours
    push the paddle one way: right for the 4 middle place-code bins, wrong for the 4 outer
    ones. Layout "top" (DishBrain's geometry): sites along the top edge, motor area = lower
    60%; in this model culture activity does not travel that far, so the paddle gets no
    information about the ball (a sensitivity check in the benchmark).

Players:
  * "living": the simulated culture (vhc/cores/living.py) read through N electrodes
    (vhc/cores/electrodes.py) covering the motor area;
  * "silicon": the same network on the neuromorphic core, every cell read exactly, pooled by
    motor strip (no electrode noise, no fatigue; the same plasticity);
  * "random": the paddle driven by noise (DishBrain's in-silico control);
  * "rest": the culture moves the paddle but gets no stimulation at all (DishBrain's RST);
  * "controller": the conventional core moves the paddle toward the place-coded ball
    position (the same 8-bin information the cells get), at the same top speed.

Learning (mechanism and rate both GUESSED, see LEARN): every excitatory synapse keeps an
eligibility trace of recent pre/post co-activity (decays with tau 1 s). The predictable
feedback after a hit strengthens eligible synapses (w *= 1 + eta * e); the unpredictable
feedback after a miss weakens them (w *= 1 - eta * e). A reward-modulated Hebbian stand-in
for DishBrain's free-energy account; nobody has measured the real mechanism. Rates 0.03-1.0 were
tried on held-out seeds; none reproduced DishBrain's improvement, so the rate is not fitted.

The culture here runs with 0.5 ms steps (ASSUMED, for emulator speed; the fly models use
0.1 ms). The emulator's own run time is never a design's speed.
"""
from __future__ import annotations

import numba as nb
import numpy as np

from ..cores import electrodes as E
from ..cores.lif import update_constants
from ..cores.living import Culture, CultureParams
from ..prices import DISHBRAIN

D = {k: p.value for k, p in DISHBRAIN.items()}
TICK_S = D["tick_s"]
DT_MS = 0.5                     # ASSUMED: culture time step in the game (speed)
CROSS_S = 3.5                   # DERIVED (see module docstring)
PADDLE_SPEED = 1.0              # GUESSED: field heights per second
PADDLE_HALF = 0.234             # FITTED by fit_paddle() (3 x 600 min): noise paddle -> 0.82 hits per rally (target 0.80)
MISS_REACH = 1.5                # GUESSED: 150 mV pulses reach 1.5x further than 75 mV ones
LEARN = {"tau_s": 1.0, "eta": 0.1, "w_max": 3.0, "w_min": 0.1}    # all GUESSED (no rate reproduced DishBrain; see docs); caps x initial
PLAYERS = {"living": 0, "silicon": 1, "random": 2, "controller": 3, "rest": 4}
CHANNELS = (8, 16, 32, 59, 128, 256, 1024)
KICK_MV = 68.75                  # a pulse fires the cells it reaches (as in v0)


@nb.njit(cache=True, nogil=True)
def _game(player, n_ticks, spt, indptr, post, w, exc_syn, delay, rfc, alive,
          c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, noise_v, spont_p, spont_v, kick_v,
          reach, reach_miss, fat_pulse, fat_keep, ro_ptr, ro_ch, ro_p, ch_region, false_p,
          half, pspeed, cross_s, tick_s, rmin, rmax, hit_ticks, miss_ticks, rest_ticks, miss_hz,
          eta, e_keep, w_hi, w_lo, seed):
    np.random.seed(seed)
    n = alive.shape[0]
    neural = player <= 1 or player == 4
    v = np.full(n, v_0)
    g = np.zeros(n)
    ls = np.full(n, -(1 << 40), np.int64)
    ring = delay + 1
    buf = np.zeros((ring, n))                       # delayed synaptic input
    x_now = np.zeros(n, np.int32)
    x_prev = np.zeros(n, np.int32)
    elig = np.zeros(post.shape[0])
    G = 1.0                                         # global decay scale of the eligibility
    eff = np.ones(8)
    fat_rec = np.exp(-tick_s / 20.0)
    n_ch = ch_region.shape[0]
    ch_count = np.zeros(n_ch, np.int64)
    # game state
    bx, by = 1.0, np.random.random()
    vx = -1.0 / cross_s
    vy = (np.random.random() * 2 - 1) / cross_s
    py = 0.5
    phase, phase_left = 0, 0
    acc = 0.0
    hits = 0
    r_start = np.zeros(4096, np.int64)
    r_hits = np.zeros(4096, np.int64)
    n_r = 0
    r_start[0] = 0
    cnt = np.zeros(6)                               # spikes, syn_event, input_event, syn_update, steps, pulses
    t = 0
    for tick in range(n_ticks):
        # ---------------- stimulation for this tick (one pulse per site at most) --------
        pulse = np.zeros(8)                         # 0 none, 1 = 75 mV pulse, 2 = 150 mV pulse
        if player == 4:
            pass                                    # rest: no stimulation at all
        elif phase == 0:
            rel = by - py
            site = int((rel + 1.0) / 2.0 * 8.0)
            site = min(max(site, 0), 7)
            acc += (rmin + (rmax - rmin) * (1.0 - bx)) * tick_s
            if acc >= 1.0:
                acc -= 1.0
                pulse[site] = 1
        elif phase == 1:
            for k in range(8):
                pulse[k] = 1                        # 100 Hz on all sites = one pulse per tick
        elif phase == 2:
            if np.random.random() < miss_hz * tick_s:
                pulse[np.random.randint(0, 8)] = 2
        c1 = 0.0
        c2 = 0.0
        if neural:
            for k in range(8):
                eff[k] = 1.0 - (1.0 - eff[k]) * fat_rec
            for i in range(n):
                x_prev[i] = x_now[i]
                x_now[i] = 0
            n_kick = np.random.poisson(spont_p * n * spt)
            kick_s = np.sort(np.random.randint(0, spt, n_kick))
            kick_n = np.random.randint(0, n, n_kick)
            kp = 0
            for s in range(spt):
                slot = t % ring
                for i in range(n):
                    if t - ls[i] >= rfc:
                        gi = g[i] + buf[slot, i]
                        buf[slot, i] = 0.0
                        vi = c_v0 + c_vg * gi + c_vv * v[i]
                        if noise_v > 0.0:          # uniform noise, same SD (cheaper than normal)
                            vi += noise_v * 3.4641016151377544 * (np.random.random() - 0.5)
                        g[i] = c_g * gi
                        if s == 0:
                            for k in range(8):
                                if pulse[k] > 0:
                                    p = reach[k, i] if pulse[k] == 1 else reach_miss[k, i]
                                    if np.random.random() < p * eff[k]:
                                        vi += kick_v
                                        cnt[2] += 1
                        if vi > v_th and alive[i]:
                            ls[i] = t
                            v[i] = v_rst
                            g[i] = 0.0
                            x_now[i] += 1
                            cnt[0] += 1
                            tgt = (t + delay) % ring
                            for q in range(indptr[i], indptr[i + 1]):
                                buf[tgt, post[q]] += w[q]
                                cnt[1] += 1
                            for q in range(ro_ptr[i], ro_ptr[i + 1]):
                                if np.random.random() < ro_p[q]:
                                    ch_count[ro_ch[q]] += 1
                                    if ch_region[ro_ch[q]] == 0:
                                        c1 += 1.0
                                    else:
                                        c2 += 1.0
                        else:
                            v[i] = vi
                    else:
                        buf[slot, i] = 0.0
                # spontaneous kicks land after the update (like input events in lif._trial)
                while kp < n_kick and kick_s[kp] == s:
                    i = kick_n[kp]
                    kp += 1
                    if ls[i] != t and t - ls[i] >= rfc:
                        v[i] += spont_v
                        cnt[2] += 1
                t += 1
            cnt[4] += spt
            for k in range(8):
                if pulse[k] > 0 and player != 1:
                    eff[k] *= fat_keep
            if false_p > 0.0:
                for c in range(n_ch):
                    if np.random.random() < false_p:
                        ch_count[c] += 1
                        if ch_region[c] == 0:
                            c1 += 1.0
                        else:
                            c2 += 1.0
            # eligibility: co-activity of pre (this or last tick) and post (this tick)
            if eta > 0.0:
                G *= e_keep
                if G < 1e-100:
                    for q in range(elig.shape[0]):
                        elig[q] *= G
                    G = 1.0
                for j in range(n):
                    a = x_now[j] + x_prev[j]
                    if a > 0:
                        for q in range(indptr[j], indptr[j + 1]):
                            if exc_syn[q] and x_now[post[q]] > 0:
                                elig[q] += a * x_now[post[q]] / G
        elif player == 2:
            c1 = float(np.random.poisson(1.0))
            c2 = float(np.random.poisson(1.0))
        # ---------------- paddle and ball -------------------------------------------------
        if phase <= 1:
            if player == 3:
                rel = by - py
                binc = (min(max(int((rel + 1.0) / 2.0 * 8.0), 0), 7) + 0.5) / 8.0 * 2.0 - 1.0
                u = max(-1.0, min(1.0, 8.0 * binc))
            else:
                u = np.tanh((c1 - c2) / np.sqrt(c1 + c2 + 1.0))
            py = min(max(py + pspeed * tick_s * u, 0.0), 1.0)
            bx += vx * tick_s
            by += vy * tick_s
            if by < 0.0:
                by = -by
                vy = -vy
            if by > 1.0:
                by = 2.0 - by
                vy = -vy
            if bx >= 1.0:
                bx = 2.0 - bx
                vx = -vx
            if phase == 1:
                phase_left -= 1
                if phase_left <= 0:
                    phase = 0
            if bx <= 0.0:
                if abs(by - py) <= half:            # hit
                    hits += 1
                    bx = -bx
                    vx = -vx
                    phase, phase_left = 1, hit_ticks
                    if eta > 0.0 and neural:
                        for q in range(elig.shape[0]):
                            if elig[q] > 0.0:
                                w[q] = min(w[q] * (1.0 + eta * elig[q] * G), w_hi[q])
                                cnt[3] += 1
                else:                               # miss: rally over
                    r_hits[n_r] = hits
                    n_r += 1
                    if n_r >= r_start.shape[0]:
                        break
                    hits = 0
                    phase, phase_left = 2, miss_ticks
                    if eta > 0.0 and neural:
                        for q in range(elig.shape[0]):
                            if elig[q] > 0.0:
                                w[q] = max(w[q] * (1.0 - min(0.5, eta * elig[q] * G)), w_lo[q])
                                cnt[3] += 1
        else:
            phase_left -= 1
            if phase_left <= 0:
                if phase == 2:
                    phase, phase_left = 3, rest_ticks
                else:                               # new rally
                    phase = 0
                    bx, by = 1.0, np.random.random()
                    vx = -1.0 / cross_s
                    vy = (np.random.random() * 2 - 1) / cross_s
                    r_start[n_r] = tick
                    acc = 0.0
    return r_start[:n_r].copy(), r_hits[:n_r].copy(), cnt, ch_count, eff, hits


LAYOUT = "mid"          # GUESSED layout (default); "top" = DishBrain's own geometry; see layout()
SENSE_KEEP_UM = 100.0   # ASSUMED: electrodes/cells this close to a stimulation site are not motor


def layout(side_um, kind=None):
    """8 stimulation sites in a row. "top": near the top edge, motor area = lower 60% of the dish.
    "mid": across the middle, and every electrode not next to a site is a motor electrode
    (DishBrain: 'the remaining output electrodes were divided into predefined motor regions')."""
    kind = kind or LAYOUT
    y = 0.15 if kind == "top" else 0.5
    return np.c_[np.linspace(0.15, 0.85, 8) * side_um, np.full(8, y * side_um)]


def _motor_mask(xy, side_um, kind=None):
    kind = kind or LAYOUT
    if kind == "top":
        return xy[:, 1] >= 0.4 * side_um
    s = layout(side_um, kind)
    d = np.hypot(xy[:, None, 0] - s[None, :, 0], xy[:, None, 1] - s[None, :, 1]).min(1)
    return d > SENSE_KEEP_UM


def strip(xy, side_um):
    """Motor strip of a point: 0 = 'up' (strips 1 and 3), 1 = 'down' (strips 2 and 4)."""
    return (np.minimum((xy[:, 0] / side_um * 4).astype(int), 3) % 2).astype(np.int8)


def readout(cult, player, n_channels):
    """CSR (per neuron) of (channel, detection probability) for the motor read-out."""
    side = cult.p.dish_um
    in_motor = _motor_mask(cult.xy, side)
    if player == "silicon":                          # every cell, exactly, pooled by strip
        ch = np.where(in_motor, strip(cult.xy, side), -1)
        ptr = np.r_[0, np.cumsum(ch >= 0)].astype(np.int64)
        return ptr, ch[ch >= 0].astype(np.int64), np.ones(int(ptr[-1])), np.array([0, 1], np.int8), 0.0
    arr = E.ElectrodeArray(max(n_channels, 1), side)
    if LAYOUT == "top":
        g = E.grid(n_channels, side, 60.0)
        arr.xy = np.c_[g[:, 0], 0.4 * side + (g[:, 1] - g[:, 1].min()) / max(np.ptp(g[:, 1]), 1.0) * 0.55 * side]
    else:
        # place n motor electrodes on a grid over the dish, skipping spots next to the sites
        k = n_channels
        while True:
            g = E.grid(k, side, 60.0)
            g = g[_motor_mask(g, side)]
            if len(g) >= n_channels or k > 4 * n_channels + 16:
                break
            k += 1
        arr.xy = g[:n_channels]
    prob = arr.detect_prob(cult.xy)                   # (channels, cells)
    prob[prob < 1e-3] = 0.0
    ptr, chs, ps = [0], [], []
    for i in range(cult.p.n):
        nz = np.flatnonzero(prob[:, i])
        chs.extend(nz.tolist())
        ps.extend(prob[nz, i].tolist())
        ptr.append(len(chs))
    return (np.array(ptr, np.int64), np.array(chs, np.int64), np.array(ps, float),
            strip(arr.xy, side), E.FALSE_HZ * TICK_S)


def play(player="living", n_channels=59, minutes=20.0, seed=0, eta=None, params=None, culture=None,
         layout=None):
    """Play one session. Returns a dict of scores and the operation counts."""
    global LAYOUT
    keep = LAYOUT
    LAYOUT = layout or LAYOUT
    try:
        return _play(player, n_channels, minutes, seed, eta, params, culture)
    finally:
        LAYOUT = keep


def _play(player, n_channels, minutes, seed, eta, params, culture):
    if player in ("random", "controller") and culture is None and params is None:
        params, n_channels = CultureParams(n=40, dish_um=400.0, k_local=5), 8   # no neurons are run
    cult = culture or Culture(params or CultureParams(), seed)
    p = cult.p
    net_p = {"dt": DT_MS}
    from ..cores.lif import DEFAULT
    prm = dict(DEFAULT)
    prm.update(net_p)
    c_g, c_v0, c_vg, c_vv = update_constants(prm)
    dt_s = DT_MS * 1e-3
    rfc = int((prm["t_rfc"] * 1e-3 + 1e-3 * dt_s) / dt_s)
    delay = int(prm["t_dly"] * 1e-3 / dt_s + 0.5)
    net = cult.network()
    w = net.count * prm["w_syn"] * 1e-3
    exc = w > 0
    w_hi = np.where(exc, w * LEARN["w_max"], w)
    w_lo = np.where(exc, w * LEARN["w_min"], w)
    sites = layout(p.dish_um)
    reach = E.stim_reach(sites, cult.xy)
    lam = E.STIM_LAMBDA_UM
    d = np.hypot(sites[:, None, 0] - cult.xy[None, :, 0], sites[:, None, 1] - cult.xy[None, :, 1])
    reach_miss = np.exp(-d / (lam * MISS_REACH))
    ro = readout(cult, player, n_channels)
    eta = LEARN["eta"] if eta is None else eta
    if player in ("random", "controller"):
        eta = 0.0
    n_ticks = int(round(minutes * 60 / TICK_S))
    spt = int(round(TICK_S / dt_s))
    noise = p.noise_mV * np.sqrt(DT_MS / 0.1) * 1e-3   # same stationary noise as at 0.1 ms steps
    rs, rh, cnt, ch_count, eff, open_hits = _game(
        PLAYERS[player], n_ticks, spt, net.indptr, net.post, w, exc, delay, rfc, cult.alive,
        c_g, c_v0, c_vg, c_vv, prm["v_0"] * 1e-3, prm["v_th"] * 1e-3, prm["v_rst"] * 1e-3,
        noise, p.spont_hz * dt_s, p.spont_kick_mV * 1e-3, KICK_MV * 1e-3,
        reach, reach_miss, p.fatigue_per_pulse, 1 - p.fatigue_per_pulse, *ro,
        PADDLE_HALF, PADDLE_SPEED, CROSS_S, TICK_S, D["rate_min_hz"], D["rate_max_hz"],
        int(round(D["hit_s"] / TICK_S)), int(round(D["miss_s"] / TICK_S)),
        int(round(D["rest_s"] / TICK_S)), D["miss_hz"], eta, np.exp(-TICK_S / LEARN["tau_s"]),
        w_hi, w_lo, seed)
    game_s = n_ticks * TICK_S
    return summarise(rs * TICK_S, rh, game_s, open_hits) | {
        "player": player, "channels": n_channels if player in ("living", "rest") else None, "eta": eta,
        "counts_per_game_s": {"steps": cnt[4] / game_s, "neurons": int(cult.alive.sum()) if player in ("living", "silicon", "rest") else 0,
                              "spikes": cnt[0] / game_s, "syn_event": cnt[1] / game_s,
                              "input_event": cnt[2] / game_s, "syn_update": cnt[3] / game_s},
        "electrode_mean_hz": float(ch_count.mean() / game_s) if player in ("living", "rest") else None,
        "electrode_max_hz": float(ch_count.max() / game_s) if player in ("living", "rest") else None,
        "stim_efficacy_end": float(eff.mean()), "game_s": game_s, "dt_ms": DT_MS,
        "motor_channels": int(len(ro[3])) if player in ("living", "rest") else None, "layout": LAYOUT}


def summarise(start_s, hits, game_s, open_hits=0):
    """Scores. A player that never misses has no finished rally: its rally length is then
    reported as the hits of its one open rally (a lower bound) and flagged."""
    hits = np.asarray(hits, float)
    if hits.size == 0:
        return {"rallies": 0, "hits": int(open_hits), "rally_length": float(open_hits),
                "rally_length_t1": float(open_hits), "rally_length_t2": float(open_hits),
                "hit_rate": 1.0 if open_hits else float("nan"), "aces_pct": 0.0,
                "long_rallies_pct": 100.0, "never_missed": True}
    t1 = start_s < 300.0
    t2 = start_s >= 360.0
    n_hit, n_miss = hits.sum() + open_hits, hits.size
    return {"rallies": int(n_miss), "hits": int(n_hit), "never_missed": False,
            "rally_length": float(hits.mean()) if hits.size else float("nan"),
            "rally_length_t1": float(hits[t1].mean()) if t1.any() else float("nan"),
            "rally_length_t2": float(hits[t2].mean()) if t2.any() else float("nan"),
            "hit_rate": float(n_hit / (n_hit + n_miss)) if n_hit + n_miss else float("nan"),
            "aces_pct": float(100 * np.mean(hits == 0)) if hits.size else float("nan"),
            "long_rallies_pct": float(100 * np.mean(hits > 3)) if hits.size else float("nan")}


def fit_paddle(target=None, minutes=600.0, seeds=(0, 1, 2)):
    """Paddle half-height at which the noise-driven paddle scores DishBrain's in-silico control
    (0.80 hits per rally). Cheap: no neurons are simulated. Returns (half, score)."""
    global PADDLE_HALF
    target = D["rally_random"] if target is None else target
    tiny = CultureParams(n=40, dish_um=400.0, k_local=5)
    keep = PADDLE_HALF
    lo, hi = 0.05, 0.45
    for _ in range(14):
        PADDLE_HALF = 0.5 * (lo + hi)
        s = np.mean([play("random", minutes=minutes, seed=k, params=tiny)["rally_length"] for k in seeds])
        if s < target:
            lo = PADDLE_HALF
        else:
            hi = PADDLE_HALF
    half = 0.5 * (lo + hi)
    PADDLE_HALF = half
    score = float(np.mean([play("random", minutes=minutes, seed=k, params=tiny)["rally_length"] for k in seeds]))
    PADDLE_HALF = keep
    return half, score


# ------------------------------------------------------------------ prices per game-second ----
GAME_OPS = {"mac": 12, "select": 1}      # ASSUMED, per 10-ms tick: ball and paddle update, place-code bin
CONTROLLER_OPS = {"mac": 3}              # ASSUMED, per tick: compare ball and paddle, set speed


def price_per_game_s(r, version="v1", static="mid"):
    """Modeled time and energy per game-second of play, played in real time (the world moves at
    game speed, so every design stays powered for the whole second). Time = compute time the
    design needs per game-second (the living module needs exactly 1 s: real time only)."""
    from ..cores import conventional, neuromorphic
    from ..ledger import Cost
    from ..prices import CL1_POWER_W, M33_SLEEP_W
    ticks = 1.0 / TICK_S
    ops = {k: v * ticks for k, v in GAME_OPS.items()}
    player = r["player"]
    if player in ("living", "rest"):
        ops["mac"] += r["motor_channels"] * ticks            # add up each channel's count
        m = conventional.price(ops, "m33")
        return Cost(1.0, CL1_POWER_W.value * 1.0 + m.energy_J + M33_SLEEP_W.value * (1 - m.time_s),
                    "modeled", "living-CL1+m33",
                    ["real time only; 25 W CL1 box (published) x 1 s; electrode count does not change it (ASSUMED)"])
    if player == "silicon":
        ops["mac"] += 2 * ticks
        m = conventional.price(ops, "m33")
        c = r["counts_per_game_s"]
        nc = neuromorphic.price(c, "clocked", version=version, static=static)
        e = nc.energy_J
        if version == "v1" and nc.time_s < 1.0:              # chip stays powered between steps
            e += neuromorphic.static_W(neuromorphic.n_cores_for(c["neurons"]), static) * (1.0 - nc.time_s)
        return Cost(nc.time_s + m.time_s, e + m.energy_J + M33_SLEEP_W.value * (1 - m.time_s), "modeled",
                    "neuromorphic+m33", nc.notes + ["played in real time: chip powered the whole game-second"])
    if player == "controller":
        for k, v in CONTROLLER_OPS.items():
            ops[k] = ops.get(k, 0) + v * ticks
        m = conventional.price(ops, "m33")
        return Cost(m.time_s, m.energy_J + M33_SLEEP_W.value * (1 - m.time_s), "modeled", "m33",
                    ["M33 cycles ASSUMED; asleep (GUESSED 1 mW) the rest of each second"])
    raise ValueError(player)
