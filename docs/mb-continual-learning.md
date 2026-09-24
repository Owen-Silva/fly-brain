# The mushroom body as a continual learner: does the real wiring beat random wiring?

*Status: PRELIMINARY. A fast rate model on one fly brain (FlyWire), run 2026-09-23. Nobody
outside this project has checked it.*

## 1. The short version

**Question 1: is the mushroom body a good design for a computer that keeps learning
without forgetting?** Half yes.
- **It does not forget.** The task: learn 110 real odours in 10 steps of 11, telling
  every odour apart from every other on noisy single sniffs. At the end, the fly model
  gets **57.5%** (left half) and **58.9%** (right half) right. A standard neural network
  (an MLP) taught the same way gets **14.5% / 15.3%**, because each new step wipes out the
  last. On Shen et al.'s memory-loss score (0 = nothing lost, 1 = everything lost) the fly
  model scores **0.12**; the MLP scores **0.93**. Chance is 0.9%.
- **It learns very cheaply.** Per training example the fly model changes **120**
  synapses, and only 5% of its cells are active. The MLP changes about **115,000**
  (taught step by step) to **276,000** (taught everything at once), with 27-73% of its
  cells active.
- **But its ceiling is low.** An MLP taught all 110 odours at once gets **93.2%**. The fly
  model never gets there. Its learning rule only ever adds, so learning in steps and all
  at once give exactly the same result: 57-59%. In a simpler test (is this odour good or
  bad?) it holds only about **7 odours** before its error passes 10%, and it is wrong on
  **35%** of odours when it has to hold all 110. The MLP taught all at once holds about
  95.
- On handwritten digits (MNIST, 5 steps of 2 digits) the fly model ends at **71-74%**
  and the step-by-step MLP at **19%**. Shen et al. reported 86% and 19% on a similar test
  with better image features (section 2.8).

**Question 2: does the fly's real wiring do better than random wiring?** **No. By the
rule written down before the test, REAL WIRING LOSES.** The real wiring ends at
57.5% / 58.9%. The two random controls with the same cells and the same numbers of inputs
end at **64.4% / 64.0%** (glomeruli drawn with their real frequencies) and **66.8% /
66.8%** (all glomeruli equally likely). The real wiring is lower in all four comparisons,
by **5.0 to 9.2 points**, 10 to 23 times the uncertainty. The same call ("loses") comes out
in all 11 other settings we tried: different sparseness, different noise, a 5-synapse
cut-off, a different KC input model, and a smaller input set. Only on the good/bad
capacity test is there no clear difference.

**What this means for the hybrid computer.**
- The mushroom body's *design* is worth copying for a machine that must keep learning:
  many cells, only a few active at a time, and a local teaching signal that changes only
  the active cells' synapses. It avoids catastrophic forgetting with about 1/1,000 to 1/2,000
  of the synapse changes of backprop. The price is accuracy.
- The fly's *exact wiring* is not worth copying for general tasks. Random wiring with the
  same statistics did better on odours and on digits. The real wiring has a clear
  structure (section 4), but that structure is not for our 110-odour test. It may serve
  things we did not test: food smells in real mixtures, temperature and humidity, and
  innate behaviour.
- The simple "always add" rule is the weak part. An error-driven local rule (change
  synapses only after a mistake) roughly doubled the good/bad capacity and needed fewer
  changes (about 44 per example). This was a check done after seeing the results.

## 2. Results in more detail

Every number is PRELIMINARY: a mean over seeds (20 for the fly, 10 for the MLP unless
stated). "Clear" means the difference is more than 2 standard errors (SE) by both the
paired and unpaired measure, as pre-registered (section 6).

### 2.1 Learning 110 odours in 10 steps (main run)

Accuracy on all odours taught so far, after steps 1, 2, 5 and 10:

| Model | Left 1 | 2 | 5 | 10 | Right 1 | 2 | 5 | 10 |
|---|---|---|---|---|---|---|---|---|
| Fly, real wiring | 90.3 | 81.9 | 68.0 | **57.5** | 90.0 | 82.9 | 69.2 | **58.9** |
| Fly, shuffled | 92.5 | 85.9 | 73.7 | **64.4** | 92.4 | 85.6 | 73.4 | **64.0** |
| Fly, uniform | 93.5 | 87.1 | 75.8 | **66.8** | 93.0 | 87.7 | 76.4 | **66.8** |
| MLP, one step at a time | 99.2 | 55.5 | 19.7 | **14.5** | 99.1 | 55.9 | 19.7 | **15.3** |
| MLP, all at once | | | | **93.2** | | | | **93.2** |

Memory loss (Shen et al.'s score: accuracy on a step's odours right after that step,
minus accuracy on them at the end, averaged over steps 1-9): fly real 0.122 / 0.120,
shuffled 0.109 / 0.112, uniform 0.101 / 0.105, MLP one step at a time 0.937 / 0.928.
The fly model's small loss is not erasure. Its rule never removes anything. Old odours get
harder only because more odours now compete. Figure: `results/fig_incremental.png`.

### 2.2 Question 1: fly (real wiring) vs MLP taught step by step

| Half | Fly final | MLP final | Difference (SE) | Fly loss | MLP loss | Difference (SE) |
|---|---|---|---|---|---|---|
| Left | 57.5% | 14.5% | +43.0 (0.65) | 0.122 | 0.937 | -0.815 (0.009) |
| Right | 58.9% | 15.3% | +43.6 (0.70) | 0.120 | 0.928 | -0.808 (0.008) |

By the pre-registered rule: **the fly ends more accurate** and **the fly forgets less**, in
both halves. The MLP taught everything at once (93.2%) is the upper bound.

### 2.3 Question 2: real vs random wiring (the primary test)

Final accuracy after step 10, real minus control, in percentage points:

| Half | vs shuffled | vs uniform |
|---|---|---|
| Left | **-6.8** (14.6 paired SE) | **-9.2** (22.9 SE) |
| Right | **-5.0** (9.6 SE) | **-7.9** (20.4 SE) |

All four are "lower". **Verdict: REAL WIRING LOSES.**

### 2.4 Cost (pre-registered S7)

| Model | Synapses changed per example | Units active |
|---|---|---|
| Fly (any wiring) | 120 of about 265,000 read-out synapses | 5.0% of KCs |
| MLP, one step at a time | about 114,600 of 400,170 | 27% of hidden units |
| MLP, all at once | about 275,800 of 400,170 | 73% of hidden units |

For the MLP, "changed" counts the weights that get a non-zero error signal. With the Adam
optimiser, in practice all 400,170 weights move a little on every batch. This counts
synapse changes, not energy.

### 2.5 The same test in 11 other settings (pre-registered S1-S3)

Final accuracy (%), real / shuffled / uniform, and the call:

| Setting | Left | Right | Call |
|---|---|---|---|
| 2% of KCs active | 53.0 / 57.7 / 58.9 | 52.2 / 57.4 / 59.0 | loses |
| 3% active | 55.3 / 61.2 / 62.9 | 55.7 / 60.9 / 62.9 | loses |
| **5% active (main)** | **57.5 / 64.4 / 66.8** | **58.9 / 64.0 / 66.8** | **loses** |
| 7.5% active | 59.5 / 66.1 / 69.2 | 60.9 / 65.7 / 69.5 | loses |
| 10% active | 60.9 / 67.0 / 70.5 | 62.1 / 66.8 / 71.0 | loses |
| Noisier (20 ms window) | 31.6 / 35.4 / 36.9 | 31.8 / 35.0 / 36.8 | loses |
| Less noise (100 ms) | 75.1 / 81.4 / 82.5 | 74.9 / 81.4 / 83.5 | loses |
| Less noise (200 ms) | 84.4 / 87.5 / 89.4 | 81.9 / 88.8 / 90.3 | loses |
| Less noise (500 ms) | 86.1 / 88.8 / 90.4 | 82.2 / 90.7 / 91.7 | loses |
| Only connections of 5+ synapses | 57.3 / 63.9 / 65.9 | 58.8 / 64.1 / 66.1 | loses |
| KC input divided by its synapses | 47.2 / 43.4 / 50.5 | 35.7 / 41.9 / 49.4 | loses |
| Only 23 measured glomeruli | 32.6 / 37.3 / 39.2 | 33.8 / 37.5 / 38.9 | loses |

The real wiring is lower in all four comparisons in 11 of these 12 rows. The exception is
"KC input divided by its synapses": there the left real wiring beats the shuffled one
(+3.8 points) but still loses to the uniform one, and the right half loses to both.
Figure: `results/fig_real_vs_random.png`.

### 2.6 Capacity: how many good/bad odours fit (pre-registered S4)

Odours alternate "good" and "bad" in a random order; two output neurons. Capacity = the
number of odours at which test error passes 10%.

| Model | Capacity, left | Capacity, right | Error with all 110 |
|---|---|---|---|
| Fly, real | 7.7 | 6.5 | 35% |
| Fly, shuffled | 7.3 | 7.1 | 35% |
| Fly, uniform | 7.8 | 7.9 | 34% |
| MLP, all at once (5 seeds) | about 95 | about 94 | 10.5% |
| MLP, 10 odours at a time (5 seeds) | 16.9 | 17.2 | 37% |

- **Real vs random: no clear difference** in any of the eight comparisons (capped and
  uncapped weights; within 2 SE). Capped and uncapped weights give the same capacity,
  because the cap is never reached this early.
- **Caution.** The fly model is already wrong about 10-13% of the time with only 5 odours
  (noisy sniffs, weak odours). So "capacity" here mostly measures that floor. The error
  with all 110 odours is the more useful number.
- For the MLP taught all at once, 2 of 5 seeds never passed 10%. The mean is over the other 3.
- **Post hoc, less noise (500 ms window):** capacity about 8-10 odours in every wiring,
  error at 110 odours 28% (capped) vs 34% (uncapped). The cap helps a little here. Again
  no clear real-vs-random difference.
- **Post hoc, error-driven rule** (`diag_errgate.py`): still local, but synapses change
  only after a wrong answer. The correct output's synapses from active KCs strengthen and
  the wrong one's weaken. Capacity 16.8 / 18.0 / 19.3 (left, real / shuffled / uniform) and
  14.5 / 19.5 / 19.4 (right). Error at 110 odours is 27-29%. About 44 synapses change per
  example, against 120 for the always-add rule.

### 2.7 Which odours lose most? (pre-registered S5, S6; S6b post hoc)

- **Chemical classes (S5).** 34 of the 40 class-by-half-by-control comparisons are
  "lower". 4 are not clear (left acids and ketones vs shuffled; right amines vs both).
  2 are "higher": sulfur compounds in the right half. That class has only 2 odours.
- **Fruit-fermentation odours vs the rest (S5).** Esters, alcohols and acids (57 odours)
  also lose: -5.5 / -8.1 points in the left half, -5.0 / -7.3 in the right. They lose
  *less* than the other 53 odours in the left half (by 2.9 and 2.4 points, clear), but
  not clearly in the right half. This comparison of the two gaps was not pre-registered.
- **Exposure to the pre-registered "core community" (S6).** The correlation between an
  odour's exposure and its real-minus-random difference is about zero (Spearman -0.14 to
  +0.02; p 0.16 to 0.94). This test says little, because that group (DA4m, VL1 and three
  temperature/humidity channels) carries almost no odour signal in our data.
- **Exposure to the food-like community (S6b, post hoc).** Again about zero (Spearman
  -0.08 to -0.02; p 0.40 or more). Odours that lean most on those glomeruli lose slightly
  *more*, not less (left -7.2 vs -6.5 points against shuffled). Zheng et al. found an
  exception for food channels. We did not find it with these odours.

### 2.8 Handwritten digits (MNIST, pre-registered S8)

10 digits in 5 steps of 2. Each image is squeezed through one fixed random projection into
55 numbers, one per glomerulus, and then goes through the same KC wiring. 1,000 training
images per digit, the full 10,000 test images. Fly 5 seeds, MLP 3 seeds.

| Model | Final, left | Final, right | Memory loss |
|---|---|---|---|
| Fly, real (capped weights) | 72.1% | 71.3% | 0.08 |
| Fly, shuffled | 72.6% | 73.0% | 0.08 |
| Fly, uniform | 74.3% | 73.8% | 0.08 |
| Fly, uncapped weights (all wirings) | 64-68% | 64-68% | 0.06-0.07 |
| MLP, one step at a time | 19.2% | 19.3% | 0.99 |
| MLP, all at once | 91.9% | 92.0% | |

Real vs random: lower than uniform in both halves, and lower than shuffled in the right
half (left not clear). By the same rule: **REAL WIRING LOSES** (by 0.5-2.5 points). About
1.5% of read-out synapses hit the cap. Shen et al., after 5 tasks on MNIST-20 (better image
features from a trained network, 3,200 KCs with 10 inputs each): FlyModel 0.86, plain
network 0.19. Our plain MLP matches theirs (19%). Our fly model is lower (72%). The
likely reasons are the raw-pixel projection and about 5 inputs per KC. The set-ups are
not identical.

### 2.9 Consistency check

The post-hoc diagnostic scripts retrain the fly model on all 110 odours at once. Because
the fly rule only adds, this must give the same final accuracy as the 10-step main run. It
does, exactly, for all 120 seed x half x wiring runs (largest difference 0.0).

## 3. What we built

**Words used here.**
- **Glomerulus**: one smell channel. Every smell receptor type sends its signal to one
  glomerulus. The fly has about 50 of them.
- **Projection neuron (PN)**: carries one glomerulus's signal to the mushroom body.
- **Kenyon cell (KC)**: the mushroom body's main cells. Each KC listens to only a few PNs
  (about 5 here). A smell is stored as the small set of KCs it switches on.
- **APL**: one big inhibitory neuron per mushroom body. It keeps only a few KCs (about 5%)
  active for any smell.
- **Output neuron (MBON)**: reads the KCs. Learning changes the KC -> output synapses.
- **MLP**: a standard artificial neural network with one hidden layer. It learns by
  **backpropagation** (backprop): after every example, an error signal is sent backwards
  and almost every connection is adjusted a little.
- **Catastrophic forgetting**: a network trained on new things one after another
  overwrites what it learned before.
- **Class-incremental learning**: new categories (here: odours) arrive in batches ("tasks"),
  and after each batch the network must tell apart everything it has seen so far.

**The wiring (both brain halves, separately).** From FlyWire snapshot 630 (the snapshot the
project uses), we counted the synapses from the PNs of each glomerulus onto each KC. We
used the mushroom-body circuit file built by the Phase 8 lane and identified cells the same
way (cell class "ALPN", "Kenyon_Cell"; glomerulus = first part of the PN type). Only
uniglomerular PNs are used, because only their glomerulus is known; they carry 95.5% of
all PN -> KC synapses. KCs with no such input (mostly the visual KCs) are left out. Result:
2,397 KCs in the left half and 2,423 in the right, 55 glomeruli, about 5.2 glomeruli per
KC (`results/wiring_census.json`). We checked the matrix against a direct recount from the
raw connection list for 100 random KCs: all matched.

**The random controls.** Each control has exactly the same KCs, and each KC keeps its
number of inputs and its synapse counts. Only the glomerulus behind each input is drawn
again, new for every seed:
- (a) **shuffled**: glomeruli drawn with their real overall frequencies (a glomerulus that
  feeds 5% of all real KC inputs also feeds about 5% here; checked: correlation 0.998);
- (b) **uniform**: every glomerulus equally likely.

**The odours.** The 110 odours of Hallem & Carlson 2006, with receptor responses from the
smell lane's tables: 23 glomeruli measured by Hallem & Carlson, plus 23 more from the DoOR
database (a missing value counts as no response). Nine glomeruli have no data (DA1, VA7m,
VC1, VC3m, VC5 and the temperature/humidity channels VP1d, VP1m, VP2, VP4); they carry
only noise. Receptor responses become PN responses through the Olsen et al. 2010 equation
(strong inputs saturate; total activity divides everything down), with the smell lane's
constants.

**Noisy trials.** Every trial, each glomerulus's PN output is a random spike count
(Poisson) in a short window of T = 0.05 s, on top of an assumed 5 spikes/s background.
Real sniffs are noisy too; the noise is what makes the task hard. The window was fixed in
a pilot run on a separate seed (section 6), and we also ran 0.02, 0.1, 0.2 and 0.5 s.

**The fly model (a fast "rate" model, not the spiking brain engine).**
1. Each KC adds up its inputs: synapse count x PN response, for its glomeruli.
2. APL-like inhibition subtracts one common level, so only the top 5% of KCs stay active
   (we also ran 2, 3, 7.5 and 10%). Active KCs keep a graded level, scaled so the most
   active one = 1.
3. One output neuron per odour. After each training trial, only the synapses from the
   active KCs onto the correct output get stronger (by 0.01 x the KC's activity, capped at
   1). Nothing else changes. No backprop. This is the rule of Shen, Dasgupta & Navlakha
   (2021 preprint, 2023 paper). In the real fly, learning mostly weakens KC synapses onto
   the output that drives the opposite behaviour; for a good/bad choice this is the same
   rule seen from the other side.
4. Answer = the output neuron with the largest summed input.

**The MLP.** 55 inputs (the same PN responses), a hidden layer with as many units as the
half has KCs (2,397 or 2,423), one output per odour. Trained by backprop (Adam optimiser,
learning rate 0.001, batches of 32, 20 passes per task). Two versions: **one task at a
time** (the classic forgetting case) and **all odours at once** (the upper bound).

**The tasks.**
- **Class-incremental odours**: the 110 odours in 10 tasks of 11, in a random order per
  seed. 20 training and 20 test trials per odour. After each task, every model is tested
  on all odours taught so far.
- **Capacity**: odour -> good/bad, two output neurons ("approach" and "avoid"); N = 5 to
  110 odours; how many fit before the error passes 10%.
- **Cost**: synapses changed per training example; share of units active.
- **MNIST** (handwritten digits, optional check): 5 tasks of 2 digits, each image squeezed
  through a fixed random projection into 55 numbers, one per glomerulus.

## 4. Why does the real wiring lose? (extra checks, decided after seeing the result)

None of this was pre-registered; it is detective work, labelled post hoc. All numbers are
final accuracy on the 110-odour task, 20 seeds, main settings (files in `results/diag_*`).

**The real wiring really is structured, and the structure replicates.** Counting how often
two glomeruli feed the same KC, the real wiring has far more over-shared pairs than the
frequency-matched random wiring: 89 pairs (left) and 56 (right) are more than 3 standard
deviations above chance, where chance gives about 6. The two halves agree on which
glomeruli over-share (Spearman 0.70 over glomeruli, 0.55 over pairs). Grouping glomeruli by
this over-sharing gives a 14-glomerulus group, DM1-DM5, VA2, VM2, VM3, DP1m, DL2d, DL2v, V,
VA4 and VC4, which looks like the "food-responsive core community" Zheng et al. 2022 found
in the same kind of data (we could not check their exact list, which is in a figure). Our
pre-registered rule picked a different, tighter group instead: DA4m, VL1 and three
temperature/humidity channels (VP1d, VP2, VP4). That group carries almost no odour signal
in our data, so the pre-registered "exposure" test (S6) cannot say much (section 2).

**It is not the non-smell channels.** Removing the 9 glomeruli without odour data first
(including the temperature/humidity ones) leaves the gap almost the same: real 57.4% vs
shuffled 63.6% (left), 58.8% vs 63.5% (right).

**It is not the KC subtypes.** Different KC subtypes (gamma, alpha/beta, alpha'/beta') are
known to prefer different glomeruli. A stricter control that keeps each subtype's own
preferences gives the same gap: real 57.5% vs 64.4% (left), 58.9% vs 63.7% (right).

**It is not that the average odour codes are more alike.** Without noise, the real
wiring's KC codes for different odours are no more alike than random ones (mean
correlation 0.24 vs 0.28-0.30 left, 0.28 vs 0.28-0.29 right), and each odour's closest
competitor is about as close (0.74-0.77 in all wirings). The same trial repeated gives
about the same KC overlap (48-50%) in all wirings. So the difference shows up only in how
codes and noise interact across many odours, not in any one simple number.

**About half of the gap (left half) comes from which channels meet on one KC.** A third
control keeps every real connection with its glomerulus and its exact synapse count, and
only re-deals the connections among KCs ("edge swap"). It lands between the two: left
real 57.5%, edge swap 61.1%, shuffled 64.4%; right 58.9%, 59.9%, 64.0%. So in the left half
about half of the gap is the co-convergence Zheng et al. described (-3.5 points), and the
rest is linked to how connection strength is spread across glomeruli and KCs; in the right
half it is mostly the latter. (We checked one guess, that glomeruli with more PNs make
stronger connections: the link is weak, Spearman 0.2, not significant.)

**The size of the gap depends on how a KC weighs its inputs.** In the main model a KC with
many synapses gets more input, so the same well-connected KCs keep winning: over half the
KCs never respond to any of the 110 odours, in every wiring. Two other KC models:
- Each KC's input divided by its total synapses (pre-registered S3): accuracy falls for
  every wiring (36-51%), and the halves disagree: the left real wiring beats the shuffled
  control (+3.8 points) but loses to the uniform one (-3.4); the right loses to both (-6.2,
  -13.7).
- Each KC balances its own excitability (its input is compared with its own usual level;
  every KC now gets used): accuracy about 43% for all, and the real wiring's gap shrinks
  to 1-2 points (left -1.8 vs shuffled, -1.0 vs uniform; right -1.5 vs shuffled, +0.4 vs
  uniform, not clear). Here the real wiring beats the edge swap by 2 points.
So in no KC model we tried does the real wiring beat both controls in both halves, but
how much it loses (1-9 points) depends on a part of the model that the wiring diagram does
not tell us.

## 5. How far to trust this

**Status: PRELIMINARY.** Checks done (PLAN.md Phase 6, steps 1-5; step 6, sharing, skipped):
1. **Seeds and parameter changes.** 20 seeds for every fly result (10 for the MLP, 5 for
   MLP capacity, 3 for MLP on MNIST). Pre-registered variations: 4 other sparseness levels,
   4 other noise levels, a 5-synapse threshold, per-KC-normalised input, and a smaller
   input set. By the pre-registered rule, all 12 settings (main plus 11 variations) come
   out REAL WIRING LOSES. The real wiring is lower in all four comparisons in 11 of the 12.
   The exception is the per-KC-normalised model, where the left-half real wiring beats the
   shuffled control (sections 2.5 and 4). The good/bad capacity test shows no clear
   difference, also with less noise (post hoc) and with an error-driven rule (post hoc).
2. **Bugs.** The wiring matrix matched a direct recount from the raw connection list for
   100 of 100 random KCs. Every control keeps each KC's number of inputs and synapse counts
   (checked by assertion) and the shuffled control reproduces the real glomerulus
   frequencies (correlation 0.998). The diagnostic runs, which train on everything at once,
   reproduce the main run's task-10 accuracies (checked in section 2), as they must,
   because the fly rule only ever adds. Bugs found and fixed: a parsing error made the
   per-KC-normalised variant crash once (re-run, same seeds); the MLP's cost count first
   assumed all 110 outputs during task-by-task training (corrected in `analyze.py`).
3. **Literature.** Zheng et al. 2022, working on the same kind of electron-microscopy data,
   found the same direction: in their model the observed wiring discriminated odours
   worse than random wiring, except when all input came through their over-connected,
   mostly food-responsive channels. We found the structure and the loss; we did not find
   the exception in our odours (section 2, S6b). Caron et al. 2013 had called the wiring
   random-looking from 200 traced KCs; the full connectome shows the structure.
4. **Biology.** A real fly's mushroom body also serves temperature, humidity and vision,
   and some channels matter for survival beyond these 110 lab odours (pheromones, the
   mould smell geosmin). Wiring that is worse for our 110-odour test is not a
   contradiction: the fly is not built for our test.
5. **Write-up.** This document; code and logs in `experiments/mb_continual/`.

**Limits.**
- A rate model, not the spiking whole-brain engine: KC activity is a number, APL is an
  idealised "keep the top 5%", PNs are pooled per glomerulus with one noise draw per trial.
- The noise model and the KC input model are our choices. The size of the real-vs-random
  gap depends on the second (1-9 points).
- Odour inputs: one concentration; for 23 of the 46 glomeruli with data, 47-95% of
  odour values are missing in DoOR and were treated as "no response".
- One fly: FlyWire is one female brain; its two halves are two wirings, not two animals.
- The fly read-out is Shen et al.'s simple rule, not the Phase 8 compartment model.
- The MLP is a plain baseline. Continual-learning tricks (replay, weight protection) would
  shrink its forgetting; Shen et al. compared against some of them (section 7).
- Capacity used the 110 real odours only; no synthetic odours were added. The fly model's
  error with only 5 odours is already near the 10% line, so the capacity numbers mostly
  measure that floor.
- MNIST used 5 fly seeds and 3 MLP seeds (fewer than the odour runs) and a raw-pixel
  projection, not Shen et al.'s trained features.

## 6. Pre-registration (frozen before the main runs, copied unchanged)


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

### Fixed set-up
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

### Primary outcome and pass rule (real vs random wiring)
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

### Question 1: is the mushroom body a good continual learner?
Fly model (real wiring) vs MLP trained task by task, each half, seeds 0-9, unpaired 2-SE
rule: "fly forgets less" if its memory loss is lower by more than 2 SE in both halves;
"fly ends more accurate" if its final accuracy is higher by more than 2 SE in both halves.
Memory loss (Shen et al.'s definition): for tasks 1-9, accuracy on that task's odours right
after it was taught minus accuracy on the same odours after task 10, averaged. The MLP
trained on everything at once is reported as the upper bound (no pass/fail).

### Secondary analyses (reported; each uses the same 2-SE call; no overall verdict)
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

### Deviations (added after the runs; not part of the frozen text above)
- None in the set-up, seeds or rules.
- The per-KC-normalised variant (S3) crashed on its first try, because of a parsing bug.
  It was re-run unchanged after the fix.
- S6 was run as written. Its "core community" turned out to be a group with almost no odour
  signal. A second version using the food-like community (S6b) was added after seeing
  this, and is labelled post hoc.
- Everything in section 4 was added after the main result was known.
- Two capacity checks were added after the capacity result was known: the same test with
  a 500 ms noise window, and an error-driven local rule (`diag_errgate.py`). Both are
  post hoc (section 2.6).
- The comparison of the fruit-odour gap with the other odours' gap (section 2.7) and the
  high/low food-community split were added after the runs.
- The pre-registration did not fix MNIST seed counts; we used 5 (fly) and 3 (MLP).

## 7. Sources (all checked online on 2026-09-23)

- Shen Y, Dasgupta S, Navlakha S. *Algorithmic insights on continual learning from fruit
  flies.* arXiv:2107.07617 (2021), https://arxiv.org/abs/2107.07617. Published as
  *Reducing catastrophic forgetting with associative learning: a lesson from fruit flies.*
  Neural Computation 35(11):1797-1819 (2023),
  https://direct.mit.edu/neco/article/35/11/1797/117579. We read the PDF,
  https://cseweb.ucsd.edu/~dasgupta/papers/SDN23.pdf. **Correction:** the brief called
  it a 2021 PNAS paper. We found no PNAS version; it is an arXiv preprint (2021) and a
  Neural Computation paper (2023). Numbers we quote from it:
  - Set-up: MNIST-20 (MNIST plus Fashion-MNIST, 84 features from a LeNet5 network trained
    on another dataset), 3,200 KCs, each summing 10 random inputs, top 5% kept, 10 tasks of
    2 classes.
  - Accuracy after 5 tasks: FlyModel 0.86, BI-R 0.77, GEM 0.69, EWC 0.58, plain network
    ("Vanilla") 0.19.
  - Final FlyModel accuracy 0.75 (sparse coding with logistic regression instead: 0.54).
  - Average memory loss: FlyModel 0.07, GEM 0.24, EWC 0.27, BI-R 0.42, plain network
    close to 1.
- Dasgupta S, Stevens CF, Navlakha S. *A neural algorithm for a fundamental computing
  problem.* Science 358:793-796 (2017), https://doi.org/10.1126/science.aam9868 (abstract
  read).
- Caron SJC, Ruta V, Abbott LF, Axel R. *Random convergence of olfactory inputs in the
  Drosophila mushroom body.* Nature 497:113-117 (2013),
  https://doi.org/10.1038/nature12063 (abstract read: 200 traced KCs, "apparently random"
  combinations of glomeruli).
- Zheng Z, Li F, Fisher C, et al., Bock DD. *Structured sampling of olfactory input by the
  fly mushroom body.* Current Biology 32:3334-3349 (2022),
  https://doi.org/10.1016/j.cub.2022.06.031; full text
  https://pmc.ncbi.nlm.nih.gov/articles/PMC9413950/. We read the abstract and parts of
  the results. They found food-responsive PN types over-converging on KCs, mainly
  alpha/beta and alpha'/beta' KCs. In their simulation the observed network did worse at
  discrimination than a random one, except when all signal flowed through the
  over-converging types. Their "random glomerulus" model performed best.
- Hallem EA, Carlson JR. *Coding of odors by a receptor repertoire.* Cell 125:143-160
  (2006), https://doi.org/10.1016/j.cell.2006.01.050. We used the data through the smell
  lane's tables (`experiments/olfaction_realfly/`).
- Olsen SR, Bhandawat V, Wilson RI. *Divisive normalization in olfactory population
  codes.* Neuron 66:287-299 (2010), https://doi.org/10.1016/j.neuron.2010.04.009. We used
  the equation and constants as the smell lane did.
- Münch D, Galizia CG. *DoOR 2.0 - comprehensive mapping of Drosophila melanogaster
  odorant responses.* Sci Rep 6:21841 (2016), https://doi.org/10.1038/srep21841. Used via
  the smell lane.
- MNIST handwritten digits: the four standard files (60,000 training and 10,000 test
  images), downloaded from https://ossci-datasets.s3.amazonaws.com/mnist/ into
  `results/raw/mnist/`. They are not committed.

## 8. Files

All in `experiments/mb_continual/`:
- `common.py`: wiring, controls, odours, noise, KC code, fly read-out, MLP.
- `prep.py`: census and checks, which write `results/wiring_census.json` and
  `glomerulus_table.csv`.
- `pilot.py`: noise and MLP settings on seed 999, written to `results/pilot.json`.
- `structure.py`: over-sharing of glomeruli, written to `results/overconvergence.csv`,
  `communities.csv`, `odour_exposure.csv` and `structure.json`.
- `run_incremental.py`: the class-incremental runs, main and variants.
- `run_capacity.py`: the good/bad capacity runs (`--T 0.5 --tag _T0.5` for the post-hoc
  low-noise run, written to `results/capacity_*_T0.5.csv`).
- `run_mnist.py`: the MNIST check.
- `analyze.py`: all tables and verdicts, written to `results/*.csv` and `summary.json`.
- `plots.py`: the two figures, `results/fig_incremental.png` and
  `fig_real_vs_random.png`.
- Post hoc diagnostics (sections 2.6 and 4): `diagnostics.py`, `diag_nn.py`,
  `diag_swap.py`, `diag_kcz.py` and `diag_errgate.py`, written to `results/diag*.csv`.
- `run_queue.sh`: runs the variants, capacity and MNIST one after another.
- `results/preregistration.md` (a copy of section 6).
- `results/raw/`: big per-trial outputs and logs (git-ignored). `log-entry.md` holds the
  EXPERIMENTS.md entry.
