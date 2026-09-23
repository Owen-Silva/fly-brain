# Phase 4: the fly brain explorer app, explained

## What it is

A small website that runs on this computer only. In it you can:

1. **Find neurons** by cell type (for example `CB0701`), by a word in their
   labels (for example `gustatory`), or by their FlyWire id number.
2. **Pick** which ones to **Stimulate** (drive them with random input spikes,
   like shining a light on light-sensitive neurons in a real fly), which to
   **Silence** (switch off their output connections), and which to **Watch**
   (always show their result, even if they stay quiet). Stimulated neurons
   can be split into **groups, each with its own input rate** (for example
   sugar at 100 Hz and bitter at 40 Hz in the same run).
3. **Choose the model**: the published model (the default, exactly as
   before), the recommended neurotransmitter fix, and optional upgrades
   (see "Choosing the model" below).
4. **Run** the whole-brain simulation for a chosen length of time, a chosen
   number of repeats ("trials") and a random seed.
5. **See the result**: a spike raster (each row is one neuron, each tick one
   spike, time runs left to right, replayed as a short animation) and a ranked
   table of the most active neurons.
6. **Save the setup** so the exact same experiment (including the model) can
   be run again later, from the page or from code.

## How to start it

In a terminal, from the project folder (the repository root):

```
.venv\Scripts\python.exe -m app
```

It prints which engine it found, then says
`Open http://127.0.0.1:8765 in your browser`. Open that address. To stop the
app, press **Ctrl+C** in the terminal.

Only this computer can open the page (it listens on 127.0.0.1). Use
`--port 9000` to pick a different port if 8765 is taken.

## How to use it

- **Try the ready-made experiments first.** Under *5. Saved setups*, choose
  one, press **Load**, then **Run simulation**. There are three:
  - *Sugar taste neurons (right side) -> feeding motor neuron MN9*: the
    paper's core experiment, set up like Phase 3's "sugar at 100 Hz" run: 21
    sugar-sensing taste neurons are stimulated at 100 Hz for 1 second, 30
    times, and the feeding motor neuron MN9 should become active (67.6 Hz).
    Both MN9 neurons are on the Watch list, so their firing rate is shown
    right above the table.
  - *Sugar 100 Hz + bitter 40 Hz -> MN9 (taste competition)*: two stimulus
    groups, sugar at 100 Hz and bitter at 40 Hz, published model. MN9 drops
    to **47.7 Hz** (the paper reports 45.3 Hz; Phase 5 got 47.7 Hz with the
    same seed).
  - *DA1 smell, left antenna only -> steering neurons (recommended fix)*:
    the 60 DA1 smell neurons of the left antenna at 150 Hz on the recommended
    neurotransmitter fix, watching the steering neurons DNa02, DNpe002 and
    DNb05 on both sides. The left DNa02 fires at **22.9 Hz** and the right one
    at **0.8 Hz** ("turn left"); DNpe002 46.1 vs 0 Hz, DNb05 47.0 vs 0 Hz
    (docs/phase6-steering.md).
- **Stimulus groups.** Under *Stimulate* each group has a name, an input rate
  in Hz and its neurons. **+ Add a group** makes a new one. The group marked
  **add here** is where the *Stim* button in the search results puts new
  neurons. A neuron can be in only one group (adding it to another moves it).
  The run refuses, with the reason, a group with no neurons or a missing
  rate. With a single group the run is exactly what the app did before
  groups existed.
- **Pick the brain map first.** The first box, *Brain map (FlyWire
  snapshot)*, chooses between two releases of the fly brain data: **630**,
  the one the paper used and Phase 3 checked (the default), and **783**, the
  newer public release. The same neuron can have a different id number in
  each, so when you switch, the app re-checks your picks and marks any id
  that does not exist in the other map in red. Every run and every saved
  setup records which map it used.
- **Start-up takes a few seconds longer** because the app loads the brain's
  wiring for both maps (about 127,000 neurons in 630, 139,000 in 783, and
  millions of connections) before it opens. On this laptop that took about
  2 seconds per map. After that, runs start straight away.
- **How long runs take**: the full sugar experiment (30 trials of 1 second)
  took about 13 to 17 seconds here with the default of one trial at a time.
  The status box shows the time so far. The engine cannot report a
  percentage, so the bar just moves back and forth; after the first run the
  page adds a rough guess of the total time, labelled as a guess.
- **Test whether a neuron matters**: in the results table, press **Silence**
  next to a neuron, then run again. If MN9 goes quiet, that neuron was needed.
- **Blank seed**: if you leave *Random seed* empty the app picks one, fills it
  in, and keeps it with the run, so every run can be repeated exactly.
- **Download**: the link under the table saves every neuron's rate as a CSV
  file (it opens in Excel).
- **Narrow windows** work: below about 820 px wide the page becomes one
  column; at about 400 px the table hides two less important columns.

## Choosing the model (section 3 of the page)

Each choice has a one-line description and a **read more** link to its full
write-up.

| Choice | What it is | Write-up |
| --- | --- | --- |
| **Published model (Shiu et al. 2024)** (default) | The paper's model exactly as published, the one Phase 3 checked. | docs/phase3-explained.md |
| **Recommended neurotransmitter fix** | Corrects about 150 smell-centre local neurons to match published recordings. Stops the runaway firing after strong smell input; taste results stay identical. | docs/phase7-neurotransmitter-audit.md |
| Upgrade: **Distance-based delays** | Adds the travel time along the wire (distance / 0.2 m/s) to the 1.8 ms synapse delay. Changes very little. Preliminary. | docs/phase7-realism.md |
| Upgrade: **Adaptation** | Neurons driven for a long time slow down. Every response gets weaker (sugar 100 Hz: MN9 about 44 Hz instead of 67). Preliminary. | docs/phase7-realism.md |
| Upgrade: **Measured cell-type settings** | The few measured cell types (4% of neurons) get their measured settings. No effect on taste. Preliminary. | docs/phase7-celltype-params.md |

Only choices whose write-ups say they were checked are offered. Not offered:
conductance-based synapses (they failed their checks) and the other sign
fixes in `sim/sign_fixes.py`. Some combinations are switched off, and the page
says why next to the option:

- Delays and adaptation can be used alone or together, but only with the
  **published** model. They were never tested together with the fix.
- Measured cell-type settings only on their own (the simulator has no version
  that combines them with anything else).
- All choices other than the published model exist for the **630** brain
  map only.

**Brains are built when first used and kept in memory.** The first run with
a new choice builds its brain; the run status says so ("Building the brain
for the model ..."), and the model box says whether the chosen model is
ready, not built yet, or being built. On this laptop each build took 2 to 5
seconds; the first run with distance delays also spends about 10 seconds
working out the delays. **At most two built brains are kept**; building a
third drops the one used longest ago, and the model box says in advance which
one will be dropped. Nothing else changes: switching back simply rebuilds it.

**No silent substitutes.** If a model cannot be built (for example, not
enough memory, or its code in `sim/` fails to load), the run fails and shows
the reason, the banner at the top repeats it, and the model box shows it.
The app never runs a different model in its place.

## The warning banner (important)

Across the top, under the title, the app always says which engine it is
using.

- If the real fast engine is working, there is no warning.
- If the app had to fall back to the **slow** engine (`sim/shiu_model.py`, the
  faithful Brian2 copy of the paper's code), a grey note says so. Results are
  real but runs take many minutes.
- If no engine could be loaded at all, a **yellow banner** says **"No
  simulator"** and why (for example "sim/fast_engine.py failed to import"),
  and the Run button is switched off. The app never makes up results in its
  place.
- The automated tests use a made-up **stand-in engine** (switched on only by
  `FLYBRAIN_APP_FAKE=1`). If you ever see it, the yellow banner says **"Not
  the fly brain model"**, every result is tagged *STAND-IN ENGINE*, and the
  CSV download starts with a warning line. Never read meaning into those
  numbers.

## What "the same result" means (the Phase 4 checkpoint)

A saved setup is a small text file in `app/setups/` holding everything needed
to re-run the experiment: which neurons were stimulated (in which groups, at
which rates), silenced and watched, the run length, the number of trials,
the seed, the brain map (snapshot), the **model** (its name, its switches and
a fingerprint of every code file it uses, for example `sim/sign_fixes.py`),
and which engine (with a fingerprint of its code) it was saved with. If any
of that code has changed since, the page says which file when you load the
setup. Results record the same model details, and the CSV download lists
them in its first lines.

Setups saved before model choices existed (like the sugar one) have no model
in them; the app reads that as **the published model**, and their single
input rate as one stimulus group. The page says so when you load one.

To check that the app gives the same answer as running the experiment from
code, run in a terminal:

```
.venv\Scripts\python.exe -m app.run_setup sugar_grn_right --compare
```

This runs the saved setup twice with the same seed: once straight through the
fast engine, the way a Phase 3 script would, and once through the app's own
web requests (start a run, wait, download the rates). It then compares the
firing rate of every neuron that fired and prints **SAME RESULT** or
**DIFFERENT**. Without `--compare` it just runs the setup from code and prints
the top neurons. `--trials 2 --duration 200` makes a quick, shortened run
(the printout says it differs from the saved setup).

**Result on 2026-09-22:** SAME RESULT. MN9 (720575940660219265) fired at
67.63 Hz both ways, the other MN9 at 49.60 Hz both ways, and all 409 neurons
that fired had exactly the same rate. The web page showed the same 67.63 Hz.
The same comparison is also an automated test
(`test_checkpoint_sugar_setup_app_equals_direct_fast_engine` in
`tests/test_app.py`). It builds its own copy of the fast engine, so no app
code sits between the engine and the number it checks.

**Re-checked on 2026-09-23, after adding model choices and stimulus groups:**
SAME RESULT again. MN9 67.63 Hz and 49.60 Hz both ways, all 409 neurons that
fired identical. Also checked the same day:
- sugar 100 Hz + bitter 40 Hz: SAME RESULT both ways (428 neurons), MN9
  47.70 Hz, exactly the Phase 5 number for the same seed;
- DA1 left smell on the recommended fix: SAME RESULT both ways (216 neurons),
  and every neuron's rate equals the Phase 6 steering run saved in
  `experiments/phase6/steering/results/sim/al_ln_DA1_left_s0.npz` (made by a
  separate script, `experiments/phase6/steering/s2_simulate.py`);
- every offered model built and ran through the app (3 short trials of
  sugar 100 Hz): MN9 67.3 Hz published, 71.7 with delays, 42.7 with
  adaptation, 45.0 with delays + adaptation, 67.3 with cell-type settings
  (in line with docs/phase7-realism.md and docs/phase7-celltype-params.md).

The two new setups have their own automated tests (marked slow), and
`.venv\Scripts\python.exe -m app.run_setup <setup name> --compare` works for
any setup, including ones on a model variant.

## Where things are

| File | What it does |
| --- | --- |
| `app/engine_adapter.py` | The only door to the simulator. Finds the fast engine (or the slow one, or the stand-in) and the neuron list, and says which one it used and why. |
| `app/jobs.py` | Runs simulations in the background, one at a time. |
| `app/main.py` | The web server's answers (search, start run, status, results, setups). |
| `app/results.py` | Turns a finished run into the table, raster and CSV. |
| `app/setups.py`, `app/setups/` | Saving and loading setups (old ones still load: no model = published). |
| `app/run_setup.py` | Runs a saved setup from code; `--compare` is the checkpoint. |
| `app/make_ready_setups.py` | Writes the two newer ready-made setups (competition, DA1 steering). |
| `app/static/` | The page itself (plain HTML, CSS and JavaScript, no internet needed). |
| `tests/test_app.py` | Automated checks of the app. |

## Settings and limits

- The fast engine runs trials one at a time by default, because this computer
  is shared. Setting the environment variable `FLYBRAIN_APP_THREADS=2` before
  starting the app lets it run two trials at once.
- `FLYBRAIN_APP_FAKE=1` forces the stand-in engine (the fast automated tests use
  it). The banner then says so.
- Limits per run: up to 10,000 ms, up to 100 trials, input rate up to
  1,000 Hz, up to 5,000 neurons per list, up to 8 stimulus groups.
- At most two built brains (models) are kept in memory at once.
- The neuron list and the engine always use the same snapshot. The
  ready-made sugar setup uses 630, so the paper's ids work as written. To try
  it on 783, switch the map: one sugar neuron and the right MN9 have new ids
  there (`720575940620900446` became `720575940639259967`, and
  `720575940645521262` became `720575940618238523`), so swap those two in.
- Neurons with no cell type in the labels are shown by their class instead,
  for example "gustatory (no type)" for the sugar taste neurons in 630.
- Runs are kept in memory only; restarting the app forgets them. Saved setups
  stay.

## Known gaps

- The 3D view of neuron positions is not built yet (optional in the plan).
- Delays or adaptation together with the neurotransmitter fix are not
  offered (never tested). `sim/realism.py`'s builder for that combination
  would also, as far as reading its code shows, look for a neuron-position
  file named after the fix and fail with delays switched on; not run, noted
  for whoever owns `sim/`.
- Model choices exist for the 630 brain map only.
- The start-up still builds the published model for both maps; building a
  third model drops one of them (the 783 one first).
