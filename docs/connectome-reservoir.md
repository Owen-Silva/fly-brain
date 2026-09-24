# The fly's wiring diagram as a reservoir computer (PRELIMINARY)

**In one sentence:** used as a fixed "reservoir" circuit, the fly's real
wiring diagram did **not** compute better than random wiring of the same
size. By the rule written down before the runs it won 0 of 6 comparisons,
lost 4 and tied 2. The main reason: its strongest connections are packed into
a few tight loops, so when it is scaled like the random networks, the rest of
the brain is very quiet. That quietness also makes it much more fragile when
only a few noisy electrodes can read it.

## The result in numbers

Each network was tried at 16 gain and leak settings. Each network is compared
at its own best setting (picked on validation data), as the mean of 3 seeds.
The range across seeds is in brackets. All numbers are PRELIMINARY.

**Headline verdicts** (the pre-registered pass rule, readouts without noise):

| Readout | Task | Real wiring | Shuffled (same degrees) | Random (Erdős-Rényi) | Verdict |
|---|---|---|---|---|---|
| All 1,299 descending neurons | Memory capacity (higher is better) | 17.9 (0.7) | 22.4 (4.1) | 48.0 (38.6) | LOSE |
| All 1,299 descending neurons | NARMA-10 error (lower is better) | 0.45 (0.09) | 0.27 (0.12) | 0.26 (0.19) | LOSE |
| All 1,299 descending neurons | Delayed XOR accuracy | 91.5% | 91.7% | 91.6% | TIE |
| 1,000 random neurons | Memory capacity | 16.3 (3.8) | 22.3 (3.5) | 46.0 (36.3) | LOSE |
| 1,000 random neurons | NARMA-10 error | 0.47 (0.02) | 0.29 (0.16) | 0.26 (0.19) | LOSE |
| 1,000 random neurons | Delayed XOR accuracy | 90.6% | 91.5% | 91.9% | TIE |

- **Pass or fail:** FAIL. The real wiring won no task against either control.
- Against the shuffled wiring it lost 4 and tied 2.
- Against Erdős-Rényi it lost 1 and tied 5. Those ties are mostly an
  artifact.
  - In seed 1 of both random controls, one accidental self-connection set the
    spectral radius (see "Checks"). That made them too quiet and widened
    their seed-to-seed spread.
  - With those two controls re-run without self-connections (a check added
    after the main run):
    - the verdicts are still 0 wins, 4 losses and 2 ties;
    - against Erdős-Rényi it is now 4 losses and 2 ties (the ties are XOR);
    - Erdős-Rényi memory rises to 61.4 (descending) and 58.5 (1,000 random),
      and its NARMA error falls to 0.22.
  - One verdict moves the other way: the descending-neuron memory against the
    shuffle becomes a tie, because the shuffle's spread grew (17.9 against
    23.5, spread 7.4). File: `results/verdicts_noself.csv`.
- On XOR all three networks score about the same, 91-92%. Chance is 50%.
- For scale, a perfect memory of the last 30-100 inputs with no network at
  all gives a NARMA error of 0.37-0.38. So the real wiring (0.45-0.47) did
  worse than a plain delay line, while both random networks (0.26-0.29) did
  better.

**The electrode bottleneck** (random neurons read, no noise, then with noise
of 0.01 added to every reading):

| Neurons read | Memory, real | Memory, shuffled | Memory, random | XOR, real | XOR, shuffled | XOR, random |
|---|---|---|---|---|---|---|
| 10 | 7.8 | 9.6 | 8.7 | 65% | 65% | 78% |
| 100 | 14.5 | 17.8 | 28.0 | 88% | 91% | 92% |
| 1,000 | 16.3 | 22.3 | 46.0 | 91% | 92% | 92% |
| 3,000 | 17.2 | 23.2 | 52.9 | 91% | 92% | 93% |
| 1,000, noisy | 1.5 | 9.0 | 40.9 | 52% | 52% | 69% |
| 1,299 descending, noisy | 2.1 | 10.6 | 42.7 | 52% | 50% | 72% |

- **With few electrodes, the wiring hardly matters.** At 10 neurons all three
  networks are close. The gap opens as more neurons are read.
- **The real wiring saturates early.** Reading 100 random neurons already
  gives 14.5 of the 17.2 memory that 3,000 give. Its useful signal is
  low-dimensional, so more electrodes add little.
- **Read noise is what really hurts the real wiring.** With noise of 1% of a
  neuron's full range:
  - its memory falls from 16.3 to 1.5, NARMA becomes no better than guessing
    (0.94), and XOR drops to chance;
  - the Erdős-Rényi network keeps most of its memory (40.9) and 69% on XOR.

**Why: the quiet-brain effect.**
- Before scaling, the real matrix's largest eigenvalue is 1,954. The shuffled
  versions' are 306-373, and Erdős-Rényi's about 96-100.
- So when every network is divided by its own spectral radius, a typical
  connection in the real brain ends up about 6 times weaker than in the
  shuffled network, and about 20 times weaker than in Erdős-Rényi.
- At each network's best setting, a typical random neuron's activity swings
  by:

  | Network | Typical swing | Neurons swinging more than the 0.01 noise |
  |---|---|---|
  | Real brain | 0.0002 | 3% |
  | Shuffled | 0.02-0.03 | 73-85% |
  | Erdős-Rényi | 0.10-0.13 (0.015 in seed 1) | 76-100% |

- **Which neurons set the real brain's spectral radius** (`top_mode.py`).
  - The largest eigenvalue, -1,954, is a negative, inhibition-driven mode. It
    lives on about 8 neurons: its "participation ratio" (how many neurons it
    effectively spans) is 8.3, and the top 10 neurons carry 82% of it.
  - These are GABA (inhibitory) cells of the lobula plate, the fly's
    motion-vision layer: LPi21, another optic-lobe GABA cell, and the DCH and
    VCH centrifugal cells. They come with the motion-sensitive HSE and H2
    cells.
  - They inhibit each other through hundreds of synapses each way. The
    strongest pair has 758 and 695.
  - The next modes (size about 1,644) sit on 4-5 neurons.
  - In the random networks the top mode is spread over 69 (shuffled) to 310
    (Erdős-Rényi) neurons.
  - So the standard scaling is set by a handful of super-connected cells. A
    typical real connection (median 2 synapses) ends up about 1,000 times
    weaker than those loops.
- **A side finding that cross-checks Phase 6.** The published matrix's
  largest eigenvalue, +2,139, is excitatory.
  - It is spread over about 57 antennal-lobe local neurons, mostly lLN1_bc.
  - These are the cells behind the runaway found in Phase 6, and the
    recommended fix disconnects them.
  - So a plain eigenvalue analysis, with no simulation, finds the same
    runaway loop.
- The real network's best memory and NARMA settings sit at the top of the
  gain range tried (rho = 1.5), and it was still improving there. So a
  follow-up pushed the gain to 2-10 (see "Exploratory checks" below).
  - The real wiring did not get better. Its best stayed at rho 1.5-2.
  - Re-picking every network's best setting over the whole range 0.5-10
    still gives 0 wins, 4 losses and 2 ties (`verdicts_extended.csv`).

**The published matrix (check, seed 0 only).**
- Its spectral radius is 2,139, against 1,954 with the fix. So the fix
  removes the published matrix's strongest loop (see the top-loop analysis
  below).
- At seed 0, published versus fixed:

  | | Published | Fixed |
  |---|---|---|
  | Memory (descending / 1,000 random) | 15.5 / 15.2 | 18.1 / 16.9 |
  | NARMA error | 0.38 / 0.38 | 0.40 / 0.47 |
  | XOR | 89% / 91% | 92% / 90% |

- Against the controls it loses memory to the shuffled wiring and ties
  everything else. It has no wins, so the fix does not change the
  conclusion.
- This check has one seed only; seeds 1-2 were dropped for time.

**Is this new?** Partly a reproduction, partly new.
- **Already done by others:**
  - The whole FlyWire connectome has been used as an echo-state reservoir,
    with an Erdős-Rényi-style control matched for spectral radius (Costi et
    al. 2025). Their result was also mixed: the connectome overfit less, but
    the random control did better once the readout was properly regularised.
  - Fly-connectome reservoirs have been compared with random ones on chaotic
    time series (Morra & Daley 2022; Morra et al. 2023).
  - Region-level fly networks have been tested for memory capacity (Yan et al.
    2025).
  - conn2res (Suárez et al. 2024) compared real connectomes with rewired
    networks that keep each node's degree:
    - human brains (diffusion MRI, region level) had more memory capacity
      than the rewired ones, and so did mouse, rat and macaque;
    - the fruit fly was the exception: "except for the fruit fly (fruit fly:
      p = 0.11 ...)". That was a network built from FlyCircuit
      light-microscopy data, not FlyWire.
    - Our neuron-level result agrees with their fly result: no advantage for
      the real wiring. In our case it was a clear disadvantage.
- **Not found in any published source we could reach**, as far as the search
  went:
  - A degree-preserving shuffle control on the neuron-level whole fly brain.
  - The standard memory / NARMA-10 / XOR benchmark set on it.
  - Readout from the brain's own descending neurons.
  - The electrode-count and read-noise sweep.
  - The explanation that one tight loop sets the spectral radius and so
    silences the rest of the brain when it is scaled.
- Treat these as "not seen", not "new". The search was a few web queries, not
  a systematic review.

**What it means for the hybrid-computer goal.**
- Copying the fly's wiring as-is into neuromorphic silicon is not, by itself,
  a route to a better reservoir. Scaled the standard way, it computes less
  than random wiring and is far more sensitive to read noise.
- For a living-neuron computer read by few electrodes, the lesson is that
  signal size matters more than wiring. A network whose activity is
  concentrated in a few hot loops leaves most electrodes reading near-silence.
- A design that spreads activity evenly (like the random controls) is easier
  to read.
- The exploratory runs below ask whether the real wiring is only
  mis-scaled, or genuinely worse. The answer so far: turning its gain up or
  down does not rescue it.

## Exploratory checks (not pre-registered, PRELIMINARY)

These were added after the main result. They do not change the verdict.
They use only the two main readouts (all descending neurons, and 1,000
random neurons).

**1. Same divisor for every network (real wiring, seed 0).**
- Idea: the real matrix is divided by 1,954, the controls by only 96-373.
  So, as a test, the real matrix was divided by the Erdős-Rényi radius (96)
  instead. Its neurons then get roughly as much drive as the random ones.
- Result: the real network becomes loud but useless.
  - Memory 1.7 (descending) and 2.9 (1,000 random), against about 60 for
    Erdős-Rényi at the same divisor.
  - NARMA-10 error 1.0-1.3. That is no better than always guessing the
    average (error 1.0).
  - XOR 51-54%, which is chance.
  - Activity: a typical neuron now swings by 0.03-0.66, and up to 27% of
    readings sit at the saturation limit.
- Meaning: at this gain the brain's strong loops run on their own and
  ignore the input. The quiet regime of the main run and this loud regime
  both lose.

**2. Higher gain, rho 2-10 (real wiring seeds 0-2; shuffled seeds 0-2, seed 1 without self-connections).**
- Idea: the main grid stopped at rho 1.5, where the real network was still
  improving. So the grid was extended to rho 2, 2.5, 3, 4, 5, 6, 8 and 10.
- Result: the real wiring peaks at about rho 1.5-2 and then gets worse.
  - Best memory at high gain: 17.2, 13.8 and 12.1 (seeds 0, 1, 2), no better
    than the main grid's 17.9.
  - NARMA-10 error 0.45-0.47 at best. XOR 82-84% at best, below the main
    grid's 91%.
  - At rho 10, 85-98% of neurons swing more than the noise, but memory falls
    to 0.7-2.9.
- With every network's best setting re-picked over the whole range 0.5-10:

  | Clean readout, task | Real | Shuffled | Erdős-Rényi | Verdict |
  |---|---|---|---|---|
  | Descending, memory | 17.9 | 26.1 | 61.4 | LOSE |
  | Descending, NARMA-10 error | 0.45 | 0.26 | 0.22 | LOSE |
  | Descending, XOR | 91.5% | 92.1% | 91.0% | TIE |
  | 1,000 random, memory | 16.3 | 25.9 | 58.5 | LOSE |
  | 1,000 random, NARMA-10 error | 0.50 | 0.28 | 0.22 | LOSE |
  | 1,000 random, XOR | 90.6% | 91.6% | 91.4% | TIE |

  - Still 0 wins, 4 losses and 2 ties. The shuffled network also gains a
    little from higher gain (memory 22 to 26).
  - With read noise 0.01, the real wiring's best memory rises from 1.5-2.1
    to 4.2-7.1 at higher gain, but the controls keep 21-61.
  - Both control columns use the self-connection-free seed 1 (see
    "Checks"). Erdős-Rényi keeps its rho 0.5-1.5 runs, because its best
    settings were already inside that range.
  - The real 1,000-random NARMA error (0.50) is slightly worse than in the
    main grid (0.47). The validation data picked rho 2, which then did a
    little worse on test data.

## How it was done

**Reservoir computing in one paragraph.** Take a big network whose wiring
never changes (the "reservoir"). Feed a signal into some of its neurons. The
activity spreads and echoes through the network, so at any moment the
neurons hold a mixed-up trace of the recent input. Then train only a
"readout": one weighted sum of the activity of the neurons you can see. If
the readout can recover what the task asks for, the fixed network did the
hard work. This matches a living-neuron computer: you cannot rewire the
tissue, you can only stimulate it and read it with electrodes.

**The network.**
- The wiring diagram is the model's own: FlyWire snapshot 630 as used by Shiu
  et al. 2024, with the recommended antennal-lobe fix (`al_ln_literature`).
  That is 127,400 neurons and 14,635,639 connections.
- Each connection's strength is its signed synapse count, exactly as the fast
  engine uses it. The sign comes from the predicted transmitter: excitatory
  (acetylcholine and others) is +, GABA and glutamate are -.
- The build was checked against the engine's own connection list. The
  targets and counts of 300 random neurons match exactly.
- Unlike the spiking engine, each neuron here is a simple "rate" unit. Its
  activity is a number between -1 and 1, updated once per time step:
  x(t) = (1 - a) x(t-1) + a tanh(rho W x(t-1) + input).
  - tanh is a smooth S-shaped squashing function.
  - a is the leak. At a = 1 a neuron keeps nothing of its own past; at
    a = 0.3 it fades slowly.
  - rho is the gain applied to the wiring. This setup is called an
    echo-state network.
- **Spectral radius.** This is the size of the matrix's largest eigenvalue.
  Roughly, it is how much the strongest self-reinforcing pattern in the
  network grows on each pass around its loops. Every network was divided by
  its own spectral radius, so rho = 1 means that pattern neither grows nor
  shrinks. That is the usual way to compare reservoirs "at the same
  stability".

**The two random controls.** Each uses the same neurons, the same number of
connections and the same list of connection strengths:
- **Shuffled (degree-preserving).** Every connection keeps its sending neuron
  and its strength, but its receiving neuron is swapped at random with
  another connection's. So every neuron keeps how many inputs and outputs it
  has, and every neuron keeps its sign. Only who-talks-to-whom is scrambled.
- **Erdős-Rényi random.** Connections are placed between random pairs of
  neurons, with the strengths dealt out at random. This loses the hubs, the
  per-neuron sign rule and all structure.
- Three different random versions (seeds) of each were run.

**Input and output.**
- The input is one random number per step, between 0 and 0.5.
- It drives all 9,145 sensory neurons, each with weight +1 or -1 at random.
  All modalities were used so the whole brain is driven.
- Two readouts:
  - all 1,299 descending neurons, the cells that carry the brain's commands
    to the body;
  - N neurons picked at random anywhere outside the sensory neurons, like
    electrodes landing wherever they land.

**The three tasks** (standard benchmarks, all scored on held-out test data):
- **Memory capacity** (Jaeger 2001). Can the readout say what the input was
  1, 2, 3 ... 100 steps ago? Each delay scores 0 (no idea) to 1 (perfect),
  and the scores are added up. A perfect memory of the last K inputs scores
  about K; we checked this, and it gives 10.2, 30.2 and 100.0 for K = 10,
  30 and 100.
- **NARMA-10** (Atiya & Parlos 2000). The readout must produce a signal built
  from the last 10 inputs with multiplications, so it needs both memory and
  nonlinearity. The score is the error relative to the signal's own spread.
  1.0 means no better than always guessing the average; lower is better. A
  perfect linear memory of the last 30-100 inputs, with no network, scores
  0.37-0.38.
- **Delayed XOR.** Each input becomes a bit (above or below 0.25). The
  readout must say whether two consecutive bits differ. A weighted sum cannot
  do this from the raw inputs (a linear memory scores 50%, which is chance),
  so it tests whether the network adds nonlinearity. The last 10 inputs plus
  all their pairwise products score 91%.

**Fair settings.**
- Every network was tried at 16 settings: rho from 0.5 to 1.5 (8 values),
  times leak 0.3 or 1.
- Every setting and the readout penalty were chosen on separate validation
  data. Only test scores are reported.
- The 16 settings run side by side in one pass, so one pass of the whole
  brain takes about 60-140 ms per step, depending on how busy the laptop is.

## Checks done (PLAN.md Phase 6)

- **Seeds and variations.**
  - Three seeds per network. The real network's seeds change the input, the
    input weights and the random readout neurons.
  - The full grid of gains and leaks.
  - The published matrix run as well (see the results).
  - An exploratory rerun with all networks divided by the same number (real
    network, seed 0).
  - A re-run of the two seed-1 controls without self-connections (see
    below).
  - NOT done: the spiking check with the real engine. It was dropped for
    time, because other jobs on the laptop made the sweep 2-4 times slower
    than timed.
- **Bugs.**
  - A flaw in the controls was found and checked. Randomly rewiring
    connections creates a few self-connections (a neuron wired to itself),
    which the real brain does not have (0 of 14.6 million).
    - In seed 1 of both controls, one such self-connection was strong enough
      to set the whole network's spectral radius on its own. Erdős-Rényi seed
      1 has a -177 self-connection, so its radius is 177.0 instead of about
      96. Shuffle seed 1 has a +335 one, so its radius is 334.7.
    - Those two controls were therefore scaled down too far and ran quieter.
      This favours the real wiring. Its Erdős-Rényi memory is 23.5, against
      58-62 in the other seeds.
    - Both were re-run without self-connections (results above).
  - The matrix matches the engine's connection list.
  - The fast compiled network code gives the same numbers as a plain version
    to within 3 in 10 million.
  - The fast tanh formula is accurate to 3 in 10 million.
  - The task code passes the no-network checks above.
  - The random readout neurons exclude all sensory neurons, so no readout
    neuron is fed the input directly.
- **Literature.** See "Is this new?" below.
- **Biology.** This is a computing test, not a claim about fly behaviour. The
  one biological observation, which neurons set the spectral radius, is
  checked against the connection list directly.

## Limits

- **Rate units, not spikes.** Each neuron is a tanh unit with no threshold,
  no refractory period, no delay and no bias. No spiking check was run, so it
  is unknown whether the spiking model gives the same picture.
- **The normalisation drives the headline.** Dividing by the spectral radius
  is standard, but in the real brain that radius is set by a small, very
  strongly wired group of neurons (see the results). A different but also
  reasonable scaling (the exploratory same-divisor run) changes the
  network's behaviour completely, from almost silent to loud and
  input-blind. It made the real wiring worse, not better. Other scalings
  (for example, one that tames only the hot loop) were not tried.
- **Only one input scaling (weight ±1) and one noise level (0.01)** were
  tried. Only 1,000 training steps were used, so readouts of 1,000-3,000
  neurons are limited by data as well as by the network.
- **The two exploratory runs are thinner.** The same-divisor run used one
  seed of the real wiring. The high-gain run did not include Erdős-Rényi (its
  best settings were already inside the main grid, and clearly ahead) or the
  published matrix. Neither
  run looked at the 10-3,000 neuron sweep.
- **The input is artificial.** It is one random number driving every sensory
  neuron at once, with random signs. That is nothing like what a fly senses.
- **The controls were built from the fixed matrix.** The published matrix was
  compared against those same controls. The fix changes 0.35% of the
  connections.
- **"Descending neurons" in a control are the same neuron numbers.** In a
  shuffled network they are not the network's output cells in any special
  sense.
- Three seeds give only a rough idea of the spread.
- Everything here is PRELIMINARY. There has been no independent review.

## Sources (all links opened on 2026-09-23)

Reservoir computing with brain wiring:
- Suárez, Richards, Lajoie & Misic 2021, "Learning function from structure in
  neuromorphic networks", *Nature Machine Intelligence* 3:771-786. Human
  connectomes from diffusion MRI (region level), used as reservoirs on a
  memory task; they performed best near critical dynamics.
  https://www.nature.com/articles/s42256-021-00376-1
- Damicelli, Hilgetag & Goulas 2022, "Brain connectivity meets reservoir
  computing", *PLOS Comput Biol* 18:e1010639. Connectome-based echo-state
  networks match classical random ones once they have a minimum of
  randomness and diversity in their connections.
  https://journals.plos.org/ploscompbiol/article?id=10.1371%2Fjournal.pcbi.1010639
- Suárez et al. 2024, "Connectome-based reservoir computing with the conn2res
  toolbox", *Nature Communications* 15.
  - At criticality, human memory capacity beat degree-preserving rewired
    networks.
  - Across species, the fly (FlyCircuit data) was the one case with no
    significant advantage (p = 0.11).
  - https://www.nature.com/articles/s41467-024-44900-4 (full text read at
    https://pmc.ncbi.nlm.nih.gov/articles/PMC10803782/)

Fly connectome as a reservoir (found in the literature check):
- Costi, Hadjiivanov, Dold, Hale & Izzo 2025, "The Drosophila Connectome as a
  Computational Reservoir for Time-Series Prediction", *Biomimetics* 10:341.
  - FlyWire, as subsets of 50-1,500 neurons and as the whole connectome
    (104,909 neurons after their filtering).
  - Task: predicting a chaotic three-body orbit.
  - Control: Erdős-Rényi-style, matched for sparsity and spectral radius.
  - Result: the connectome overfit less at low regularisation, but the random
    control did better at higher regularisation.
  - Note: they treated glutamate as excitatory, unlike Shiu et al.
  - https://pmc.ncbi.nlm.nih.gov/articles/PMC12109256/
  - Also: ESA project page, https://www.esa.int/gsp/ACT/projects/fly_connectome/
- Morra & Daley 2022, "Imposing Connectome-Derived Topology on an Echo State
  Network" (arXiv). A fruit-fly-connectome ESN beat, or had lower variance
  than, random ESNs on chaotic time series.
  https://arxiv.org/abs/2201.09359
  - Follow-up: https://arxiv.org/abs/2206.02094
- Morra, Flynn, Amann & Daley 2023, "Multifunctionality in a Connectome-Based
  Reservoir Computer" (arXiv). The fly reservoir was more multifunctional than
  an Erdős-Rényi one. https://arxiv.org/abs/2306.01885
- Yan et al. 2025, cross-species connectome comparison (bioRxiv). Fly, mouse,
  rat and macaque matrices, taken from the conn2res toolbox, had higher memory
  capacity than weight-shuffled controls.
  https://www.biorxiv.org/content/10.1101/2025.10.29.685101v1
- Guragain et al. 2026 (arXiv). Includes a 49-node, region-level Drosophila
  network, not neuron level. https://arxiv.org/abs/2606.09902

Tasks and hardware context:
- Jaeger, "Short term memory in echo state networks", GMD Report 152
  (2001; some cite 2002). This is the memory-capacity definition. Its
  existence was confirmed through citing papers; the report itself was not
  opened.
- Atiya & Parlos 2000, *IEEE Trans Neural Netw* 11:697-709 (the NARMA tasks).
  https://pubmed.ncbi.nlm.nih.gov/18249797/
- Wringe, Trefzer & Stepney 2024, "Reservoir Computing Benchmarks: a review,
  a taxonomy, some best practices". Gives the NARMA-10 equation and input
  range used here. https://arxiv.org/abs/2405.06561
- Wang et al. 2025, "Neuromorphic Simulation of Drosophila Melanogaster Brain
  Connectome on Loihi 2". The whole FlyWire connectome ran on 12 Loihi 2
  chips. https://arxiv.org/abs/2508.16792
- Cai et al. 2023, "Brain organoid reservoir computing for artificial
  intelligence", *Nature Electronics* 6:1032-1039. A living human brain
  organoid used as a reservoir, read through a high-density electrode array.
  https://www.nature.com/articles/s41928-023-01069-w

## Files

In `experiments/reservoir/`:
- `lib.py`: builds the matrices and controls, runs the network, defines the
  tasks and the readout.
- `timing.py`: checks the matrix against the engine and times one run.
- `run_grid.py`: the main sweep. Options for the exploratory runs:
  `--samegain` (same divisor for every network), `--highgain` (rho 2-10) and
  `--lite` (only the two main readouts).
- `analyze.py`: applies the pass rule and draws the figures.
- `baselines.py`: the no-network checks.
- `top_mode.py`: which neurons set the spectral radius.

In `results/`:
- `grid.csv`: every run, setting, readout and task.
- `best_settings.csv`, `verdicts.csv`, `summary.json`.
- `radii.json`, `top_mode.json`, `baselines.csv`.
- `noself_grid.csv` and `verdicts_noself.csv` (the self-connection re-run).
- `samegain_grid.csv` and `samegain_best.csv` (exploratory, same divisor).
- `highgain_grid.csv` (exploratory, rho 2-10), and `best_settings_extended.csv`
  and `verdicts_extended.csv` (best settings re-picked over rho 0.5-10).
- `fig_bottleneck.png`, `fig_memory.png`.

`results/raw/` holds logs and per-delay memory curves. It is small and can
be regenerated.

## Pre-registration (written 2026-09-23 21:45, before any comparison run; not changed afterwards)

**What is being tested.** A "reservoir computer" keeps a network's wiring
fixed and trains only a simple readout: a weighted sum of some neurons'
activity. We ask whether the fly's real wiring works better as a fixed circuit
than random wiring with the same neurons, the same connection count and the
same connection strengths.

**Networks.**
- Real: the whole-brain signed matrix of snapshot 630 with the recommended fix
  (`al_ln_literature`), built exactly as the fast engine builds its connection
  list. 127,400 neurons and 14,635,639 connections. Weight = signed synapse count.
- Check: the published matrix (`none`), run the same way.
- Control (a), degree-preserving shuffle: the target of every connection is
  shuffled. Each neuron keeps its number of inputs, its number of outputs, and
  its outgoing weights and signs.
- Control (b), Erdős-Rényi random: the same number of connections with the
  same weight values, placed between random pairs of neurons.
- Controls are built from the fixed matrix, one per seed (3 seeds each).
- Every network is divided by its own spectral radius (the size of its largest
  eigenvalue), so all start at radius 1. The radii found before this was
  written: real 1,954; shuffle (seed 0) 306; Erdős-Rényi (seed 0) 96.

**Model.** A rate network (echo-state network):
x(t) = (1 - a) x(t-1) + a tanh(rho W x(t-1) + W_in u(t)).
- rho (gain) in {0.5, 0.65, 0.8, 0.95, 1.05, 1.2, 1.35, 1.5}.
- a (leak) in {0.3, 1.0}.

**Input.** One number per time step, u(t), drawn at random between 0 and 0.5.
- It goes into all 9,145 sensory neurons (every modality).
- Each sensory neuron gets weight +1 or -1 at random.

**Timeline.** 3,000 steps per run: 200 to settle, then 1,500 to train the
readout, 500 to validate (choose settings), and 800 to test. Only test scores
are reported.

**Tasks.** All three use the same run.
- Memory capacity (Jaeger 2001): how well past inputs u(t-k) can be recovered,
  summed over delays k = 0 to 100. Higher is better. Score: the squared
  correlation on test data.
- NARMA-10: a standard nonlinear prediction target that depends on the last 10
  inputs. Score: the normalised error (NRMSE). Lower is better; 1.0 means no
  better than guessing the average. The readout may answer up to 10 steps
  late; the lag is chosen on validation data.
- Delayed XOR: turn each input into a bit (above or below 0.25), then give the
  XOR of two consecutive bits. The delay is chosen from 0-15 on validation
  data. Score: test accuracy, where chance is 50%.

**Readout.** Ridge regression (linear regression with a penalty against large
weights). The penalty is chosen on validation data from 10^-8 to 10^0 of the
mean feature size.
- Readout A: all 1,299 descending neurons.
- Readout B: N random neurons, not sensory neurons. N is 10, 30, 100, 300,
  1,000 or 3,000, taken from one random pool of 3,000 per seed (nested).
- Each readout is computed both clean and with read noise. The noise is
  Gaussian with a standard deviation of 0.01, which is 1% of a neuron's full
  range, added at every step.

**Seeds.** Seeds 0, 1 and 2. A seed fixes the input sequence, the input
weights, the random readout pool, the noise and the control's wiring. So the
real and control networks see identical input at each seed.

**Best settings.** For each network, task and readout, the (rho, a) with the
best validation score averaged over the 3 seeds. Test scores at that setting
are compared.

**Pass rule.** For one task and one readout:
- **Spread** is the larger of the two networks' seed-to-seed ranges (highest
  minus lowest of the 3 test scores).
- **WIN** against a control: the real network's mean test score is better than
  the control's by more than the spread.
- **LOSE**: the control is better by more than the spread.
- Otherwise it is a **TIE**.
- The real wiring wins a task only if it wins against both controls.

The headline verdicts use the two clean primary readouts: all descending
neurons, and 1,000 random neurons. That gives 3 tasks x 2 readouts = 6
verdicts. The noisy readouts, the N sweep and the published matrix are
reported but are not part of the headline.

All results are PRELIMINARY.

**Amendment, 21:55, before the main run (for compute time only).**
- A short debug run (700 steps, seed 0, one batch per network) showed the
  whole-brain step costs about 130 ms for 16 settings at once. Two other lanes
  were using about 3.4 of the laptop's cores, which is why.
- The timeline was therefore shortened to 2,200 steps: 200 to settle, 1,000 to
  train, 400 to validate and 600 to test.
- The published-matrix check runs seed 0 first, and seeds 1-2 only if time
  allows.
- Nothing else changed: not the pass rule, the grid, the tasks or the readouts.
