# Pre-registration: mushroom body as a continual learner, real vs random wiring

Frozen 2026-09-23 21:58, before any learning run on the real wiring or the "shuffled"
control. Copied unchanged into `docs/mb-continual-learning.md` (section 6). Nothing below
may change after the main runs start; any later change is listed as a deviation.

**What had been seen before freezing (disclosed).**
- The wiring census (`prep.py`): left half 2,397 KCs and right half 2,423 KCs with
  glomerular input, 55 glomeruli, about 5.2 inputs per KC.
- The wiring-structure analysis (`structure.py`, no learning): the real wiring has many
  more glomerulus pairs that share KCs than chance (left 89 pairs z > 3, right 56; about 6
  expected), and the two halves agree (Spearman 0.70 over glomeruli). The first version of
  the per-glomerulus score (mean z with all other glomeruli) ranked the classic food
  glomeruli (DM1, DM4, VM3, DM3, VA2) at the bottom, so the odour "exposure" measure was
  changed, before any learning run, to Zheng et al.'s community approach (see item S6).
- The pilot (`pilot.py`, seed 999, never used again): MLP trained on all odours at once
  reached 93.3% / 98.8% / 99.9% / 100% test accuracy at noise windows T = 0.05 / 0.1 /
  0.2 / 0.5 s; the fly model on a UNIFORM control wiring (left half) reached 65.1% / 79.5%
  / 85.3% / 85.9%. By the rule fixed in `pilot.py`, T = 0.05 s and MLP = 20 epochs,
  learning rate 0.001. No fly model on the real wiring or on the shuffled control was run.

## Fixed set-up
- Wiring: FlyWire snapshot 630, uniglomerular PN -> KC synapse counts summed per
  glomerulus, all synapses (>= 1), each brain half separately. KCs without glomerular
  input are left out.
- Controls, new random draw for every seed: (a) "shuffled": each KC keeps its number of
  inputs and its synapse counts, glomeruli drawn (distinct within a KC) with the real
  overall glomerulus frequencies of that half; (b) "uniform": the same, all 55 glomeruli
  equally likely.
- Odours: the 110 Hallem & Carlson 2006 odours; receptor input = smell lane's set A (23
  glomeruli, Hallem & Carlson) + set B (23 glomeruli, DoOR consensus, missing = no
  response); PN response = Olsen et al. 2010 equation (smell lane constants); trial noise =
  Poisson spike count in T = 0.05 s on top of 5 Hz spontaneous, per glomerulus.
- KC code: top 5% of KCs (APL-like subtraction of a common level), graded, most active = 1.
- Fly read-out: one output per odour; each training example adds 0.01 x KC activity to the
  synapses from active KCs onto the correct output only; weights capped at 1.
- MLP: 55 inputs -> same number of hidden units as the half's KCs (ReLU) -> outputs;
  softmax cross-entropy, Adam, learning rate 0.001, batch 32, 20 epochs per task
  (sequential) or 20 epochs on everything (joint).
- Class-incremental task: 10 tasks of 11 odours, random order per seed; 20 training and
  20 test trials per odour; after each task, test on all odours taught so far, answer =
  the most active output among them.
- Seeds 0-19 for the fly models; seeds 0-9 for the MLPs.

## Primary outcome and pass rule (real vs random wiring)
Outcome: final accuracy on all 110 odours after task 10 (k = 5%, T = 0.05 s).
For each half (left, right) and each control (shuffled, uniform), with D = accuracy(real)
- accuracy(control) per seed (same seed = same noisy trials and task order):
- "higher" if mean D > 2 x SE_paired AND mean D > 2 x SE_unpaired, where SE_paired =
  SD(D) / sqrt(20) and SE_unpaired = sqrt(SD_real^2 / 20 + SD_control^2 / 20);
  "lower" if mean D < -2 x both; otherwise "no clear difference".
- **REAL WIRING WINS** only if "higher" in all four half x control comparisons.
- **REAL WIRING LOSES** if, for at least one control, "lower" in both halves.
- Otherwise **NO CLEAR DIFFERENCE**.
Sizes are reported in percentage points whatever the call.

## Question 1: is the mushroom body a good continual learner?
Fly model (real wiring) vs MLP trained task by task, each half, seeds 0-9, unpaired 2-SE
rule: "fly forgets less" if its memory loss is lower by more than 2 SE in both halves;
"fly ends more accurate" if its final accuracy is higher by more than 2 SE in both halves.
Memory loss (Shen et al.'s definition): for tasks 1-9, accuracy on that task's odours right
after it was taught minus accuracy on the same odours after task 10, averaged. The MLP
trained on everything at once is reported as the upper bound (no pass/fail).

## Secondary analyses (reported; each uses the same 2-SE call; no overall verdict)
- S1 sparseness: k = 2, 3, 7.5, 10% of KCs active (fly models only).
- S2 noise: T = 0.02, 0.1, 0.2, 0.5 s.
- S3 robustness: only connections with >= 5 synapses; each KC's input divided by its
  total synapses; set A input only.
- S4 capacity: odour -> good/bad (two outputs), N = 5 ... 110 real odours, labels
  alternating along a random order; capacity = N where test error first passes 10%
  (linear interpolation); fly models with capped and with uncapped weights, MLP joint and
  MLP in blocks of 10 odours; real vs controls with the 2-SE rule (seeds where a model
  never passes 10% by N = 110 are reported separately).
- S5 odour groups (main run, final per-odour accuracy): the 10 Hallem & Carlson chemical
  classes, and "fruit fermentation" (esters + alcohols + acids, 57 odours) vs the other 53.
- S6 exposure: glomeruli clustered by their pair z-scores (mean of both halves, average
  linkage, 6 clusters); the cluster with the highest within-cluster z (>= 3 glomeruli) is
  the "core community" (Zheng et al. 2022's approach). Per odour, exposure = share of its
  PN drive through the core community. Test: Spearman correlation over the 110 odours
  between exposure and the odour's real - control accuracy difference (per half and
  control). Zheng et al.'s result predicts a positive correlation.
- S7 cost: synapses changed per training example and fraction of units active.
- S8 (if time) MNIST, 5 tasks of 2 digits, through a fixed random projection to 55 inputs.

Many secondary comparisons are made, so a few may pass 2 SE by chance; they are
exploratory.
