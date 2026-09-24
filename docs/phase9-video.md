# Phase 9 video: the simulated fly, steered by the brain model

*Written 2026-09-23. Files: `experiments/phase9_video/`. The trials shown are four of the
142 trials in `docs/phase9-da1-demo.md`, re-run exactly. Status: **PRELIMINARY**, the
same as that demo (section 6 below).*

## The short version

- **What it is.** A 48-second video (`phase9_video.mp4`) with four short clips of the
  physics fly walking, each after a title card, at **half speed**. Every clip is
  1.5 s of fly time (clip D stops earlier, when the fly reaches the source).
- **A. One antenna covered, the brain steers (DNa02):** only the left antenna can smell;
  the fly turns **left, toward the smelling side** (+73° in the first second). This is
  the behaviour behind the Phase 9 checkpoint's PARTIAL verdict.
- **B. The same trial with DNa02 silenced:** the brain's turn signal is cut; the fly
  **walks straight** (+9°: the body's own drift, the same in every silenced trial of
  this seed).
- **C. Normal fly, both antennae, source on the right:** the honest failure. The brain
  turns the fly **LEFT anyway** (+72°), away from the source.
- **D. Hand-written rule, NOT brain-driven:** the reference. A simple rule that
  compares left and right smell turns the fly right and **reaches the source** in
  0.60 s.
- **In every clip the brain only chooses left or right.** Leg movements, walking rhythm
  and walking speed come from FlyGym's built-in controller: **NOT brain-driven**. The
  caption bar says so on every frame.
- **Checked:** each re-run followed the saved trial's path exactly (differences below
  2e-14, i.e. rounding in the saved file), and the fly drawn in the video sits exactly
  on that path (section 4).

## 1. Files

All in `experiments/phase9_video/`. H.264, yuv420p, 1280 x 1136 pixels, 30 frames per
second.

| File | What | Size | Length |
|---|---|---|---|
| `phase9_video.mp4` | intro card, the four clips each after a title card, closing card | 1.49 MB (1,488,320 bytes) | 48.2 s |
| `clip_a_one_antenna_brain.mp4` | clip A alone | 0.31 MB (311,458 bytes) | 4.2 s |
| `clip_b_dna02_silenced.mp4` | clip B alone | 0.33 MB (332,472 bytes) | 4.2 s |
| `clip_c_normal_fly.mp4` | clip C alone | 0.34 MB (342,363 bytes) | 4.2 s |
| `clip_d_hand_rule.mp4` | clip D alone | 0.23 MB (226,553 bytes) | 2.5 s |
| `poster.png` | one frame of clip A (fly time 1.00 s, mid-turn) | 0.13 MB (131,736 bytes), 1280 x 1136 | |
| `simulate_clips.py` | step 1: re-runs the four trials, saves the fly's pose every 1 ms | | |
| `render_video.py` | step 2: draws the frames, adds captions, writes the videos | | |
| `states/clip_*.npz` | the saved poses (input to step 2) | | |
| `results/` | per-window numbers of each re-run, the checks, logs | | |
| `log-entry.md` | the EXPERIMENTS.md entry | | |

The four clips were put **in sequence with a title card each** rather than in a 2 x 2
grid: in a grid each quarter would be 640 pixels wide, and on a phone the caption text
would be too small to read.

## 2. What each clip shows

All four use replicate 0 of the DA1 demo (walking-rhythm seed 0, brain seed 0), sign fix
`al_ln_literature`, the source 6 mm from the fly's start, 1.5 s per trial, 50 ms loop
windows. The numbers below are from the saved trials
(`experiments/phase9_da1/results/da1_trials.csv`).

| Clip | Saved trial (condition / layout / seed) | Set-up | What happens | Turning comes from |
|---|---|---|---|---|
| A | `one_dna02` / `B_Lonly+90` / 0 | right antenna covered; source 6 mm to the fly's LEFT | turns left: +73° in the first second (+81° by 1.5 s); left DNa02 fires 9.3 Hz on average, right 0 Hz; closest to the source 5.55 mm (started 6.02 mm away): it turns but does not reach it | **the brain** (left minus right DNa02) |
| B | `one_dna02_off` / `B_Lonly+90` / 0 | the same, with DNa02 silenced | walks straight: +9° (the body's own drift); DNa02 still fires (4.7 Hz left) but its output is cut, so the body gets the straight command in every window | **nothing**: no turn command reaches the body |
| C | `dna02` / `A-45` / 0 | both antennae smell; source 6 mm away, front-right (45° right) | turns LEFT: +72° in the first second, away from the source; left DNa02 7.3 Hz, right 0 Hz, while the two antennae smell almost the same (smell-neuron input 75 vs 77 Hz, the right slightly stronger); closest 5.31 mm, farther than the silenced fly of the same layout (4.90 mm) | **the brain** (its built-in left bias) |
| D | `hand_rule` / `A-45` / 0 | the same arena as C, no brain | turns right (-44°) and reaches the source (within 2 mm) at 0.60 s; the trial stops at 0.65 s, 1.13 mm from it | **the hand-written rule**: NOT brain-driven |

Why these four trials:

- **A** is the second-strongest of the 12 one-antenna DNa02 trials. It turned 63° more
  than the silenced fly of the same seed; the 12 trials range from 8° to 75°
  (`results/da1_paired_trials.csv` of the DA1 demo). It is not typical of all of them:
  with the right antenna smelling, the turns to the right were much weaker (8-35°
  beyond the drift; `docs/phase9-da1-demo.md` 4.2).
- **B** is the same trial (same layout, same seeds) with DNa02 silenced, so any
  difference from A is the brain's turn command.
- **C** uses the source at front-right (-45°) rather than directly right (-90°): both
  show the failure, but here the left turn is larger (+72° vs +37°) and the steering
  neuron fires more (7.3 vs 4.0 Hz), so it is easier to see.
- **D** uses the same arena as C, so C and D differ only in what steers.

## 3. What is brain-driven and what is not

| Part of what you see | Where it comes from |
|---|---|
| Which way the fly turns in A and C | **brain-driven**: antenna smell -> DA1 smell neurons -> whole-brain model -> left minus right DNa02 firing |
| That more left DNa02 means a left turn | biology (Rayshubskiy et al. 2025); built into the loop, not chosen by the brain |
| The small drift in B (and part of the turn in A and C) | FlyGym's walking controller: **NOT brain-driven** (+9° for seed 0 in every silenced or no-odor trial) |
| Every turn in D | FlyGym 1.x's hand-written smell rule: **NOT brain-driven** |
| Leg movements, walking rhythm, how a left/right command becomes a turn | FlyGym's built-in controller: **NOT brain-driven**, in every clip |
| Walking speed (always full) | a fixed number: **NOT brain-driven**, in every clip |

The caption bar has one line per clip for the steering source:
- A and C: "Turning: brain-driven (DNa02)".
- B: "Turning: none from the brain (DNa02 silenced)". It does not say "brain-driven",
  because the only turn in B is the body's own drift.
- D: "Turning: NOT brain-driven (hand-written rule)".
- Every frame also says: "Legs, walking rhythm and speed: FlyGym's built-in controller,
  NOT brain-driven."

## 4. How it was made and checked

**Step 1, re-running the trials (`simulate_clips.py`).** The script loads the DA1 demo
script itself (`experiments/phase9_da1/run_da1.py`) and builds each trial exactly as it
did: same condition settings, layout, seeds, source distance, trial length and window,
the same brain (`al_ln_literature`, built with 2 threads). The only addition is a
read-only hook in the loop (`sim/body/loop.py`, `run_trial(..., on_substep=...)`, added
for this video; left out, nothing changes) that copies the fly's pose (all 73 numbers
that place its body and joints) every 1 ms.

- **Same path as the saved trial: yes, for all four** (`results/path_check.csv`). Window
  by window, the position, heading, antenna smell, smell-neuron rates, DNa02 and DNpe002
  firing, turn command and drive all equal the saved values. The largest difference in
  any column is 1.4e-14 (rounding in the saved text file); positions differ by at most
  1.8e-15 mm. Same number of windows (30, 30, 30 and 13).

**Step 2, drawing (`render_video.py`).** The fly is posed in each saved pose and
photographed. The brain and the physics are not re-run.

- **The fly in the video sits exactly on the saved path** (`results/render_check.csv`):
  at every window start and at the end (30 checkpoints per clip, 13 for D), the posed
  fly is at most 1.8e-15 mm and 1.3e-14° from the logged position (step 1 also saves
  the pose one physics step before every window boundary for this). A first version of
  this check showed gaps of up to 0.003 mm and 0.08°. The cause: right after a physics
  step, MuJoCo still reports the body positions from before that step, so the loop's
  logged position belongs to the pose one step (0.1 ms) earlier. Comparing with that
  pose gives the exact match. The frames themselves use the pose nearest to each frame
  time (within 0.5 ms), so they can be up to one physics step ahead of the logged
  numbers. That is 0.003 mm at most, far below one pixel.
- **Camera:** fixed for the whole clip, raised 50° above the floor. Clips A and B share
  one camera, as do C and D, so each pair is seen identically. A and B are seen from the
  fly's right side: the fly starts facing right and its left is the far side of the
  picture. C and D are seen from behind: the fly starts facing away, and its left is
  the left of the picture. The two directions were chosen because they show each
  pair's paths with the largest fly (about 120-130 pixels long).
- **Frame rate:** 30 frames per second of video at half speed (one frame every 1/60 s
  of fly time). At real speed the legs, which step 12 times per second (FlyGym's
  default rhythm), would get only 2.5 frames per step and look jerky.

**What the caption numbers are.**

- **Time:** fly time since the trial started.
- **DNa02 firing, left and right:** the firing rate the loop recorded, averaged over the
  last 0.25 s (five 50 ms windows). DNa02 is one neuron per side, so in a single 50 ms
  window it usually reads 0 or 20 Hz (0 or 1 spike). The raw values would flicker.
- **Steering:** the loop's turn command averaged over the same 0.25 s. 100% is the
  strongest turn the loop can give. In the loop itself the command changes every 50 ms.
- **Smell at antenna:** the odor strength at each antenna in the current 50 ms window,
  exactly as the loop used it. Units are arbitrary (strength 1 at 1 mm from the source).
  The bars use the smell neurons' own curve (strength / (strength + 0.01)), so a full
  bar means the smell neurons are near their maximum. "covered" means that antenna
  sends nothing to the brain.

**What is drawn but is NOT data:**

- The fly's colours, the floor's grey shades, the light and the shadows. These were
  changed on a separate copy of the model used only for drawing; the physics model was
  not touched.
- The purple ball (radius 0.38 mm) marks the source, which in the model is a point
  1.5 mm above the floor. The thin stalk shows the spot on the floor beneath it.
- The purple ring is the 2 mm "reached" zone around the source (the demo's reach
  distance).
- The blue line is the path of the fly's thorax, averaged over one stride (83 ms). The
  thorax sways sideways with every step, and the average shows the walking line.
- The floor squares are 4 mm wide. This was checked by drawing markers every 4 mm
  (`render_video.py --test`).

## 5. What to take from it

- **Clips A and B show the one positive result:** with only one antenna smelling, the
  brain turns the fly toward that side, and silencing DNa02 removes the turn.
- **Clips C and D show the main negative result:** with both antennae smelling (a normal
  fly), the brain does not tell left from right and turns left whatever the side. The
  same body with a simple left-versus-right rule finds the source. The problem is the
  missing left/right signal in the brain model, not the body or the smell world.

## 6. Caveats (the partial checkpoint)

From `docs/phase9-da1-demo.md` sections 5 and 7:

- **Checkpoint verdict: PARTIAL, and PRELIMINARY. Not passed for a normal fly.** The
  behaviour appears in the expected direction and vanishes when silenced, but only in a
  one-antenna fly (a lab manipulation), not in a normal fly walking in a cVA gradient.
- In A the fly turns but does not reach the source. The right-antenna trials (not shown)
  turn much less than the left-antenna ones: the model's left bias again.
- The silencing controls are weak tests in this model. It has no other activity, so
  cutting any link of the chain has to give the straight walk.
- The real-fly evidence is indirect. Attraction to cVA depends on context (virgin
  females, food present), and close to a real male, flies turn away. Whether a
  one-antenna female steers toward cVA specifically was not found.
- The smell world is a smooth, still cloud that reaches the fly at 6 mm. Real cVA is
  detected only within a few mm, so the cloud is generous.
- The video shows one seed per condition. The statistics (3 seeds, 142 trials) are in
  `docs/phase9-da1-demo.md` section 4.

## 7. How to re-make it

```
.venv-body\Scripts\python.exe experiments/phase9_video/simulate_clips.py   (about 2 min)
.venv-body\Scripts\python.exe experiments/phase9_video/render_video.py      (under a minute)
.venv-body\Scripts\python.exe experiments/phase9_video/render_video.py --test   (still frames only)
```

The body environment needs no new package: the encoder (`imageio-ffmpeg==0.6.0`, with
its own ffmpeg) was already pinned in `requirements-body.txt`.
