# Phase 4: the fly brain explorer app, explained

## What it is

A small website that runs on this computer only. In it you can:

1. **Find neurons** by cell type (for example `CB0701`), by a word in their
   labels (for example `gustatory`), or by their FlyWire id number.
2. **Pick** which ones to **Stimulate** (drive them with random input spikes,
   like shining a light on light-sensitive neurons in a real fly), which to
   **Silence** (switch off their output connections), and which to **Watch**
   (always show their result, even if they stay quiet).
3. **Run** the whole-brain simulation for a chosen length of time, a chosen
   number of repeats ("trials"), a chosen input rate and a random seed.
4. **See the result**: a spike raster (each row is one neuron, each tick one
   spike, time runs left to right, replayed as a short animation) and a ranked
   table of the most active neurons.
5. **Save the setup** so the exact same experiment can be run again later,
   from the page or from code.

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

- **Try the ready-made experiment first.** Under *4. Saved setups*, choose
  *Sugar taste neurons (right side) -> feeding motor neuron MN9*, press
  **Load**, then **Run simulation**. This is the paper's core experiment, set
  up like Phase 3's "sugar at 100 Hz" run: 21 sugar-sensing taste neurons are
  stimulated at 100 Hz for 1 second, 30 times, and the feeding motor neuron
  MN9 should become active. Both MN9 neurons are on the Watch list, so their
  firing rate is shown right above the table.
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
to re-run the experiment: which neurons were stimulated, silenced and
watched, the run length, the number of trials, the seed, the input rate, the
brain map (snapshot), and which engine (with a fingerprint of its code) it
was saved with. If the engine
code has changed since, the page says so when you load the setup.

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

## Where things are

| File | What it does |
| --- | --- |
| `app/engine_adapter.py` | The only door to the simulator. Finds the fast engine (or the slow one, or the stand-in) and the neuron list, and says which one it used and why. |
| `app/jobs.py` | Runs simulations in the background, one at a time. |
| `app/main.py` | The web server's answers (search, start run, status, results, setups). |
| `app/results.py` | Turns a finished run into the table, raster and CSV. |
| `app/setups.py`, `app/setups/` | Saving and loading setups. |
| `app/run_setup.py` | Runs a saved setup from code; `--compare` is the checkpoint. |
| `app/static/` | The page itself (plain HTML, CSS and JavaScript, no internet needed). |
| `tests/test_app.py` | Automated checks of the app. |

## Settings and limits

- The fast engine runs trials one at a time by default, because this computer
  is shared. Setting the environment variable `FLYBRAIN_APP_THREADS=2` before
  starting the app lets it run two trials at once.
- `FLYBRAIN_APP_FAKE=1` forces the stand-in engine (the fast automated tests use
  it). The banner then says so.
- Limits per run: up to 10,000 ms, up to 100 trials, input rate up to
  1,000 Hz, up to 5,000 neurons per list.
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
- The "second input rate" the paper used for sugar-plus-bitter experiments is
  not in the app yet; each run has one input rate for all stimulated neurons.
