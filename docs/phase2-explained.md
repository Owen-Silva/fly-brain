# Phase 2 explained: loading the real fly brain

## What the data is

Scientists took the brain of one adult female fruit fly, cut it into about
7,000 ultra-thin slices, and photographed every slice with an electron
microscope. Computers then traced every nerve cell (**neuron**) through the
slices, and hundreds of people checked and corrected the tracing by hand
(**proofreading**). This project is called **FlyWire**.

From those pictures we get two lists:

- a **neuron list**: one entry per neuron. Each neuron has a long id number,
  called a `root_id` (for example `720575940624963786`), and labels such as its
  **cell type** (a name like `APL` or `MBON11`) and where its cell body sits.
- a **connection list**: "neuron A touches neuron B at N places". Each touching
  place is a **synapse**, the spot where one neuron passes a signal to the next.
  N is the **synapse count**. We use it as the strength of the connection.

A computer also looked at every synapse and guessed which chemical messenger
(**neurotransmitter**) it uses (Eckstein et al. 2024). That guess is how we
decide whether a neuron excites or inhibits the neurons it talks to.

## Where our copy comes from

| What | From | Needs an account? |
|---|---|---|
| Neuron list and connection list | The reference paper's own preprocessed files (Shiu et al. 2024, `data/reference/`) | No |
| Cell types, classes, neurotransmitter guess, 3D positions | Schlegel et al. 2024 label table on GitHub (`data/flywire/`) | No |
| Official FlyWire lists, used only to double-check | FlyWire's Zenodo release (`data/flywire/`) | No |

Codex, FlyWire's own download site, needs a Google sign-in, so we did not need
it. Exact web addresses and versions are in [README.md](../README.md).

### Two versions of the brain

FlyWire has published the brain more than once. Each time neurons are
corrected, their id numbers change. Two versions matter here:

- **Release 783** (October 2023): the latest public version. The labels are
  made for it. This is what the loader gives you by default.
- **Release 630**: the older version the reference paper actually used. Six of
  the neuron ids the paper names (including one of the two feeding motor
  neurons, MN9) do not exist in 783. So **Phase 3 will use 630**, which makes
  the comparison with the paper fair. The loader can load either.

## What the numbers mean (release 783)

Full output: [experiments/phase2/summary.txt](../experiments/phase2/summary.txt)
and [experiments/phase2/crosscheck_zenodo.txt](../experiments/phase2/crosscheck_zenodo.txt).

| | Our copy | Published (Dorkenwald et al. 2024) |
|---|---:|---:|
| Neurons | 138,639 | 139,255 |
| Synapses between neurons | 54,492,922 | "54.5 million" |
| Connections (pairs of neurons that touch at least once) | 15,091,983 | not stated |
| Connections with 5 or more synapses | 2,700,513 | 2,700,513 |
| Neurons in those strong connections | 134,181 | 134,181 |

**The synapse count and the strong-connection counts match the paper
exactly.** We also compared our connection list, pair by pair, with FlyWire's
own official table on Zenodo: all 15,091,983 pairs are there, every synapse
count is identical, and nothing is missing.

**Why 616 neurons are missing (0.4%).** FlyWire's official list has 139,255
neurons; ours has 138,639. We checked each of the 616 missing ones against
FlyWire's official connection table: **every one of them has zero synapses
with any other neuron.** Most are sensory neurons (552), for example nerve
fibres that enter the brain but make no counted synapse with a proofread
neuron. A neuron with no connections can never receive or send a signal in the
simulation, so leaving them out changes nothing.

**Why the paper talks about "at least 5 synapses".** The synapse finder is
automatic and nobody checked each synapse by hand, so the paper only counts a
connection as "real" when it has 5 or more synapses. Our file keeps every
connection, down to a single synapse, exactly like the reference model does.
Half of all connections (49.7%) are a single synapse. They are weak: in the
simulation, a connection's push is proportional to its synapse count.

**Other things worth knowing:**

- The average connection has 3.6 synapses; the strongest has 2,405.
- 137,147 neurons have a cell type name; 118,086 have a marked cell body
  position (the rest have another 3D anchor point, useful for the Phase 4 3D
  view). Positions are stored in nanometres.
- 14 neurons in the reference list have no labels at all in the Schlegel
  table (their ids were probably edited after the labels were made).

### The most connected neurons

The biggest senders and receivers are a handful of giant "broadcast" neurons
that touch thousands of others, almost all using GABA (inhibitory):

- **CT1** (optic lobe, the vision part): about 100,000 outgoing synapses to
  roughly 9,700 neurons each. It helps sharpen motion vision.
- **APL** (one per side, in the mushroom body, the learning centre): about
  50,000 to 60,000 outgoing synapses. It quiets the smell-learning neurons so
  only a few respond to each smell. This matters in Phase 8.
- **DPM** (mushroom body): one of the biggest receivers.
- **Li33, LPi15, LPi13, Am1** (optic lobe) and **cM15** (feedback into the
  eye region).

This is plausible: all of these are known "wide-field" neurons whose branches
spread across a whole brain region, so they touch a great many cells.

### Neurotransmitter breakdown

| Messenger | Neurons | Share of neurons | Share of outgoing synapses | Treated as |
|---|---:|---:|---:|---|
| acetylcholine | 86,025 | 62.0% | 55.9% | excitatory (+) |
| glutamate | 24,858 | 17.9% | 17.4% | inhibitory (-) |
| GABA | 19,147 | 13.8% | 23.1% | inhibitory (-) |
| dopamine | 5,905 | 4.3% | 2.5% | excitatory (+) |
| serotonin | 2,201 | 1.6% | 0.8% | excitatory (+) |
| octopamine | 210 | 0.2% | 0.3% | excitatory (+) |
| no guess | 293 | 0.2% | 0.0% | excitatory (+) |

Overall about **60% of synapses are excitatory and 40% inhibitory**.

## The sign assumption, and its limits

Every connection needs a **sign**: does it push the next neuron toward firing
(**excitatory**, +) or away from it (**inhibitory**, -)? We use the same rule
as the reference paper:

- acetylcholine = excitatory
- GABA and glutamate = inhibitory
- everything else (dopamine, serotonin, octopamine, no guess) = excitatory

**This is an assumption, not a measurement.** Its limits:

1. **The messenger is a computer guess.** It is right most of the time, but it
   is least reliable when the computer was unsure.
2. **Glutamate is not always inhibitory.** In flies it is inhibitory at many
   brain synapses, but it excites muscles and some neurons. It depends on the
   receiving neuron's receptors, which the images cannot show.
3. **Dopamine, serotonin and octopamine are not simple on/off pushes.** They
   act slowly and change how other neurons behave. Calling them "excitatory" is
   a placeholder.
4. **One neuron, one sign.** Some neurons release two messengers.

### How well our signs match the reference file

We worked out each neuron's sign from its messenger label, then compared it
with the sign already stored in the reference paper's file:

| | Agree |
|---|---:|
| Neurons that send synapses (138,005) | 95.6% |
| Connections | 98.8% |
| Synapses | 98.9% |
| Same comparison for release 630 (the paper's version) | 98.5% of neurons |

The disagreements are almost all neurons where the messenger guess was
unsure: when the computer's confidence is above 70%, agreement is over 99%;
below 40%, it drops to 70%. The most likely reason is that the paper decided each
neuron's sign in a slightly different way. It looked at every output synapse
separately and called the neuron inhibitory if more than half of them looked
like GABA or glutamate. We use one overall label per neuron. For a confident
neuron the two methods give the same answer. For an unsure one they can
differ. Using FlyWire's official table we got closer (96.9% agreement), but
matching exactly would need a 9.5 GB file of every single synapse, which we
did not download.

**What this means for the project:** the loader keeps **both** signs side by
side (`sign` = ours, `ref_sign` = the reference file's). Phase 3 will use the
reference file's sign, so our simulation is wired exactly like the paper's.

## Is it fast enough?

| | Time |
|---|---:|
| First load (read the original files, build, save a cache) | 5 to 13 seconds (depends on how busy the machine is) |
| Every later load (from the cache in `data/cache/`) | about 0.3 to 0.5 seconds |
| Building the big connection grid (matrix) | about 1 to 1.6 seconds |

The cache rebuilds itself automatically if any source file changes.

## Checkpoint

- **Counts roughly match published FlyWire numbers: PASS.** Synapses and
  strong connections match exactly; the neuron count is 0.4% lower, and we
  showed why (the missing neurons have no connections).
- **Loading is fast enough to iterate: PASS.** Under half a second from cache.

## For Claude Code: how to use the loader

```python
from sim.connectome import load_connectome
brain = load_connectome()            # release 783; load_connectome("630") for the paper's
brain.n_neurons, brain.n_connections, brain.n_synapses
brain.index_of([720575940624963786]) # FlyWire id -> row number
brain.root_id_of([69093])            # row number -> FlyWire id
brain.by_cell_type("APL")            # exact cell type (ignores upper/lower case)
brain.search("MBON")                 # any label containing the text
brain.partners(720575940613583001, "out", top=10)
M = brain.matrix("reference")        # sparse grid, M[sender, receiver] = signed synapse count
```
