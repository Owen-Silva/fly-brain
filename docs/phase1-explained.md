# Phase 1 explained: a toy network of 100 neurons

## What a "leaky integrate-and-fire" neuron is

Picture each neuron as a **bucket with a small hole in the bottom**.

- The water level is the neuron's **voltage**. An empty-ish bucket sits at the
  **resting level, -52 millivolts**.
- Incoming signals from other neurons pour water in (**integrate**).
- The hole lets water drain out all the time (**leaky**), so a trickle of input
  is not enough: the level just settles a little above rest.
- When the level reaches a line painted on the side, the **threshold at -45
  millivolts**, the neuron **fires** a spike, and the bucket is instantly tipped
  back to -52. It then ignores all input for 2.2 milliseconds (the
  **refractory period**) before it starts filling again.

That is the whole model. It is simple on purpose: the same model, with the same
numbers, runs every one of the ~140,000 neurons in the whole-brain simulation
from the reference paper (Shiu et al. 2024). Every neuron number here was copied
from that paper's code, and a test checks they still match.

## Excitatory and inhibitory

When a neuron fires, the signal travels (after a 1.8 millisecond delay) to every
neuron it connects to.

- An **excitatory** connection pours water **in**: it pushes the next neuron
  toward firing. In the fly, these neurons use acetylcholine.
- An **inhibitory** connection **drains** water out: it pushes the next neuron
  away from firing. The reference model treats fly neurons that use GABA or
  glutamate as inhibitory (a standard assumption).

A connection's strength is its number of synapses (contact points) times a fixed
amount per synapse, exactly as in the reference model.

## The toy network

- 100 neurons: 80 excitatory (numbers 0 to 79), 20 inhibitory (80 to 99).
- Each neuron is wired to about 10 others, chosen at random.
- **Background input**: a steady random stream of excitatory kicks to every
  neuron, so the network fires a little on its own.
- **Test input**: an extra random stream that can be switched to excitatory,
  inhibitory, or off.

The random choices are fixed by a "seed" number, so the same run always gives
exactly the same result.

## How to read the plots

### Spike raster: [experiments/phase1/raster.png](../experiments/phase1/raster.png)

Each **dot is one spike**: the dot's left-right position is **when** it happened
(in milliseconds), and its height is **which neuron** fired. Blue dots are
excitatory neurons, orange dots are inhibitory. More dots means more activity.

The four panels are the same network with four different inputs (500 ms each):

| Panel | Spikes | Average per neuron |
|---|---|---|
| No input at all | 0 | 0 per second |
| Background only (the baseline) | 1,010 | 20 per second |
| Background + excitatory test input | 1,919 | 38 per second |
| Background + inhibitory test input | 80 | 1.6 per second |

So: nothing in gives nothing out; adding excitation nearly doubles the firing;
adding inhibition almost silences the network.

### Voltage trace: [experiments/phase1/voltage_trace.png](../experiments/phase1/voltage_trace.png)

This follows **one neuron's voltage** (neuron 0, background input only) over the
first 250 milliseconds. You can see the bucket at work:

- The line **climbs** from -52 as input pours in. The climb is wobbly because
  the input arrives at random moments.
- When it touches the **dashed line (-45, the threshold)** the neuron fires. The
  short upward tick marks the spike (the model itself has no spike shape; it
  just resets, so the tick is drawn in to make each spike easy to see).
- The line then **drops straight back to the dotted line (-52)** and sits flat
  for a moment (the refractory period) before climbing again.
- Sometimes the climb stalls (for example around 135 ms): either the random
  input went quiet for a moment and the leak caught up, or a signal from an
  inhibitory neuron drained some charge. Either way, that spike came later.

## The Phase 1 checkpoint (automated tests)

`tests/test_toy_network.py` checks, with fixed seeds:

1. Excitatory input increases firing (at least 1.5 times the baseline).
2. Inhibitory input decreases firing (at most half the baseline).
3. Zero input produces zero spikes, and the voltage stays exactly at rest.

Plus two safety checks: the same seed gives the same result every time, and
every neuron number still matches the reference paper's code.

To redraw the plots: `.venv\Scripts\python.exe experiments\phase1\run_phase1.py`
