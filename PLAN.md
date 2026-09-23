# Fly Brain Simulator — Project Plan

## Goal
Build a working simulation of the real fruit fly brain using the public FlyWire connectome (~140,000 neurons, ~50 million synapses), confirm it reproduces known published results, then wrap it in an interactive app for running experiments: stimulating neurons, silencing them, and watching activity spread.

The owner of this project does not write code. Claude Code writes and runs everything. Explain every result in plain English.

## How to use this file (for Claude Code)
- Put this file in the repo root as `PLAN.md` and treat it as the source of truth.
- Work one phase at a time. Don't start a phase until the previous phase's checkpoint passes.
- At each checkpoint, stop and show the owner what was built, what it shows, and whether it passed.
- Keep `EXPERIMENTS.md` as a running log. Every experiment gets the date, what was changed, what happened, and whether the result was validated.
- Commit to git after every working step.
- Never present a simulation result as a finding without running the validation steps in Phase 6.

---

## Phase 0 — Setup
- Create a Python project (virtual environment, `requirements.txt`, git repo).
- Core libraries: `numpy`, `pandas`, `pyarrow`, `matplotlib`, and `brian2` (spiking neural network simulator used by the reference paper). Add `scipy` and `pytest`.
- Folders: `data/`, `sim/`, `experiments/`, `app/`, `tests/`.

**Checkpoint:** Environment installs cleanly and a hello-world Brian2 script runs.

## Phase 1 — Toy spiking network (learn the basics)
- Implement a small network (10–100 neurons) of leaky integrate-and-fire (LIF) neurons.
- Include excitatory and inhibitory connections.
- Produce a spike raster plot (dots showing which neuron fired when) and a voltage trace for one neuron.
- Write a short plain-English explanation of what a LIF neuron is and what the plots show.

**Checkpoint:** Excitatory input increases firing, inhibitory input decreases it, and zero input produces no spikes. Add these as automated tests.

## Phase 2 — Load the real fly brain
- Get the data from FlyWire Codex (codex.flywire.ai; a free account may be required). Files needed: neuron list with cell types, connections with synapse counts, and predicted neurotransmitter per neuron.
- Also check the reference paper's GitHub repo (search "Drosophila_brain_model" by Philip Shiu). It includes preprocessed connectome files for the same data snapshot the paper used. Using the same snapshot makes Phase 3 comparisons fair.
- Check the data license and add proper FlyWire citations to the README.
- Build a loader that turns the data into a connection matrix:
  - Weight = synapse count.
  - Sign from neurotransmitter: acetylcholine = excitatory; GABA and glutamate = inhibitory (standard assumption in the reference paper; note it as an assumption).
- Print summary stats: number of neurons, number of connections, most connected neurons, breakdown by neurotransmitter.

**Checkpoint:** Counts roughly match published FlyWire numbers, and loading is fast enough to iterate (cache to parquet if needed).

## Phase 3 — Reproduce the published result (most important phase)
Reference: Shiu et al., "A Drosophila computational brain model reveals sensorimotor processing," *Nature*, 2024. They ran a LIF model on the whole connectome and it predicted real behaviors.

- Match their model parameters as closely as possible (from the paper's methods and their code).
- Reproduce their core experiment: activate sugar-sensing gustatory neurons and check that motor neurons for feeding (e.g., MN9, involved in proboscis extension) become active.
- Reproduce at least one more result from the paper (e.g., water-sensing or bitter-sensing neurons).
- Compare our numbers with theirs side by side.

**Checkpoint:** Our simulation qualitatively matches the paper, meaning the same neurons respond in the same direction. If it doesn't, debug before moving on. Everything after this phase depends on this one being right.

## Phase 4 — Interactive explorer app
- Backend: Python (FastAPI) wrapping the simulator, with endpoints for "stimulate these neurons," "silence these neurons," and "run for N milliseconds."
- Frontend: web app to:
  - Search neurons by cell type or name.
  - Pick neurons to stimulate or silence.
  - Run the simulation and see a live or replayed activity view (raster plot plus a list of the most active neurons downstream).
  - Optional later: a 3D view of neuron positions (FlyWire provides coordinates) that lights up as neurons fire.
- Save and reload experiment setups so any result can be re-run exactly.

**Checkpoint:** Running the Phase 3 sugar experiment through the app gives the same result as running it from code.

## Phase 5 — Experiments
Start with questions like these and log everything in `EXPERIMENTS.md`:
- **Silencing:** In the sugar → feeding pathway, which single neurons, when silenced, block the response? Which are redundant?
- **Pathway tracing:** What are the shortest and strongest paths from a sensory neuron to a motor neuron?
- **Competition:** What happens when sugar and bitter neurons are stimulated together?
- **Sensitivity:** How much do results change if parameters (thresholds, synapse strength) change by ±20%? Results that flip easily aren't trustworthy.
- **Unexplored areas:** Pick a sensory system the reference paper didn't focus on and map where its activity goes.

## Phase 6 — If something surprising shows up
Before treating anything as a real finding:
1. Re-run with different random seeds and parameter variations. Does it still hold?
2. Check for bugs: sign errors, wrong neuron IDs, indexing mistakes.
3. Search the literature to see whether it's already known.
4. Check whether it contradicts known fly biology. If so, suspect the model first.
5. Write it up clearly: the setup, the result, and how it was validated.
6. If it survives all of that, share it with the FlyWire community or the reference paper's authors.

---

## Realism rule (applies to Phases 7–9)
The goal is maximum biological realism, but realism only counts if it's validated. Every upgrade must:
- Be added one at a time, never several at once.
- Be based on published fly biology or data, with the source noted in the code and in `EXPERIMENTS.md`.
- Be re-checked against the Phase 3 baseline. If an upgrade breaks the known sugar → feeding result, it's wrong or needs tuning.
- Keep the old version runnable, so every result can be compared with and without the upgrade.

If an upgrade makes the whole-brain simulation too slow to use, apply it only to the circuit being studied and keep the rest of the brain on the simpler model.

## Phase 7 — Make the neurons and synapses more realistic
Add these one at a time, in roughly this order:
1. **Synaptic delays:** Signals take time to travel. Add realistic transmission delays.
2. **Conductance-based synapses:** Replace simple current injection with synapses that behave more like real ion channels.
3. **Spike-frequency adaptation:** Real neurons fire less when they're stimulated for a long time. Add adaptation.
4. **Cell-type-specific parameters:** Where published measurements exist for a cell type (thresholds, time constants), use them instead of one shared value for all neurons.
5. **Missing pieces:** The connectome doesn't include electrical synapses (gap junctions) or neuromodulators like dopamine and octopamine. Research published data on where these matter and add them only where there's evidence.

**Checkpoint:** After each upgrade, Phase 3 results still hold, and the change in behavior is logged.

## Phase 8 — Real learning (mushroom body)
The part of the fly brain that learns smells, the mushroom body, is one of the best-understood learning circuits in any animal, so it's the most realistic place to add learning.
- Model the circuit using the real connectome: odor-sensing neurons feed Kenyon cells, which feed mushroom body output neurons (MBONs), with dopamine neurons (DANs) acting as the reward or punishment signal.
- Implement the published learning rule: when a dopamine neuron is active at the same time as a Kenyon cell, that Kenyon cell's connection to the output neuron weakens.
- Reproduce classic fly conditioning experiments in the simulation: pair an odor with punishment, then check whether the output neurons that drive avoidance respond differently to that odor afterward.

**Checkpoint:** The simulated fly "learns" in the same direction real flies do in published conditioning experiments, and doesn't learn when odor and reinforcement aren't paired (the control condition).

## Phase 9 — Give the brain a body
Connect the brain to a physics-simulated fly so it can see, smell, and move in a virtual world instead of just producing motor neuron activity.
- Use an existing, published fly body model rather than building one. Two options, both built on the MuJoCo physics engine:
  - **FlyGym / NeuroMechFly** (EPFL): Python package with a realistic fly body, legs, vision, and smell. Probably the easiest starting point.
  - **flybody** (Janelia and Google DeepMind): detailed whole-body fly model for walking and flight.
  Check the current versions and docs of each before choosing.
- Look for newer connectome data that includes the ventral nerve cord (the "spinal cord" that controls the legs), such as MANC (male nerve cord) or a combined brain-and-nerve-cord dataset (BANC). This would let the real wiring drive the legs instead of a simplified controller.
- Connect the loop:
  1. The world produces sensory input (the fly's eyes and smell sensors in the physics sim).
  2. That input drives the matching sensory neurons in the brain model.
  3. Motor/descending neuron activity is translated into movement commands for the body.
  4. The body moves and the world updates, and the loop repeats.
- Where no connectome-based link exists yet (e.g., exact leg control), use the body model's built-in controller and clearly label that part as not brain-driven.
- Start with simple behaviors: walking toward an attractive odor, turning away from a bitter taste.
- Then combine with Phase 8: train the fly to avoid an odor, and check whether its body actually steers away from that odor afterward.
- Add a 3D view in the app showing the fly moving alongside its brain activity.

**Checkpoint:** The embodied fly shows at least one behavior that matches real fly behavior in the right direction (e.g., approaching food odor), and the behavior disappears when the responsible neurons are silenced.

---

## Known limitations (keep these in mind)
- The model is a simplification: real neurons have much more complex dynamics than LIF.
- Weights come from synapse counts, and signs from predicted neurotransmitters. Both are approximations.
- Outside the mushroom body (Phase 8), the connections are fixed. Real fly brains change in many more places.
- FlyWire covers the brain of one adult female fly. Until Phase 9, there's no nerve cord or body, so behavior is inferred from motor neuron activity. Even in Phase 9, parts of the body control may come from the body model rather than the real wiring.
- More realism means slower simulations. Some upgrades may only be practical on small circuits, not the whole brain.
- Maximum realism is still far from a real fly. The model can match real behavior without working the same way the real brain does.
- A result that looks right can still be wrong. That's why Phase 3 and Phase 6 exist.
