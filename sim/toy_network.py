"""Phase 1: a toy spiking network (100 neurons) to learn the basics.

Plain-English summary
---------------------
Each neuron is a "leaky integrate-and-fire" (LIF) neuron: a bucket of electric
charge with a small leak. Input fills the bucket; the leak slowly empties it.
When the level (the voltage) reaches a fixed line (the threshold), the neuron
"fires" a spike and its voltage snaps back down to the starting level.

The network has 80 excitatory neurons (a spike from one of them pushes the
neurons it connects to TOWARD firing) and 20 inhibitory neurons (a spike pushes
the neurons it connects to AWAY from firing). The neurons are wired to each
other at random.

On top of that, two kinds of outside input can be switched on:
  * "background": a steady random pattern of excitatory kicks to every neuron,
    so the network fires a little on its own (like a brain that is awake).
  * the "test input": an extra random stream of kicks to every neuron that can
    be set to "excitatory" (pushes toward firing), "inhibitory" (pushes away
    from firing) or "none".

The neuron equations and every number marked [REF] below are copied from the
reference paper's code (Shiu et al. 2024, data/reference/model.py,
`default_params`), so what is learned here carries over to the whole-brain
model in Phase 3. Numbers marked [TOY] are choices made only for this small
network (the real brain gets its wiring from the connectome instead).
"""
from dataclasses import dataclass

import numpy as np
from brian2 import (Hz, Network, NeuronGroup, PoissonInput, SpikeMonitor,
                    StateMonitor, Synapses, defaultclock, mV, ms, prefs)
from brian2 import seed as brian_seed

# This machine has no C/C++ compiler, so run Brian2 in its pure-Python mode.
prefs.codegen.target = "numpy"

# --- Neuron model: identical to the reference -------------------------------
# [REF] Values from data/reference/model.py, default_params.
REFERENCE_PARAMS = {
    "v_0": -52 * mV,      # [REF] resting voltage (where the bucket settles)
    "v_rst": -52 * mV,    # [REF] reset voltage right after a spike
    "v_th": -45 * mV,     # [REF] threshold: reach this and the neuron fires
    "t_mbr": 20 * ms,     # [REF] membrane time constant (how fast it leaks)
    "tau": 5 * ms,        # [REF] synaptic time constant (how long a kick lasts)
    "t_rfc": 2.2 * ms,    # [REF] refractory period (rest time after a spike)
    "t_dly": 1.8 * ms,    # [REF] delay before a spike reaches the next neuron
    "w_syn": 0.275 * mV,  # [REF] strength of ONE synapse
}

# [REF] Same equations as the reference. v is the voltage (bucket level); g is
# the incoming synaptic input, which decays away with time constant tau and
# charges v. Neither changes during the refractory period.
EQUATIONS = """
dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)
dg/dt = -g / tau              : volt (unless refractory)
rfc                           : second
"""
THRESHOLD = "v > v_th"          # [REF]
# [REF] The reference reset is 'v = v_rst; w = 0; g = 0 * mV'. Its 'w = 0'
# is left out here: neurons have no variable called w, so it does nothing.
RESET = "v = v_rst; g = 0 * mV"

# --- Toy network layout ------------------------------------------------------
N_NEURONS = 100            # [TOY] total neurons
N_INHIBITORY = 20          # [TOY] the last 20 neurons are inhibitory
CONNECTION_PROB = 0.1      # [TOY] chance any neuron connects to any other
SYNAPSES_PER_CONNECTION = (1, 10)  # [TOY] random synapse count per connection
# [TOY] Inhibitory connections carry 4x the synapses, so the 20 inhibitory
# neurons can hold the 80 excitatory ones in check and activity cannot run away.
INHIBITORY_SCALE = 4

# --- Outside inputs ----------------------------------------------------------
# Each outside input is modelled like the reference's Poisson inputs: random,
# independent input spikes at a fixed average rate. Unlike the reference (which
# jumps v straight over threshold with each input spike, weight w_syn * 250),
# these kicks go into g, like ordinary synapses, so the voltage visibly charges
# up before each spike.
BACKGROUND = {"sources": 100, "rate": 10 * Hz, "synapses": 6}   # [TOY]
TEST_INPUT = {"sources": 50, "rate": 10 * Hz, "synapses": 6}    # [TOY]
INPUT_TYPES = ("excitatory", "inhibitory", "none")

DT = 0.1 * ms  # Brian2's default time step, which the reference also uses.


@dataclass
class ToyResult:
    """What one run of the toy network produced (plain numbers, no units)."""
    spike_times_ms: np.ndarray    # when each spike happened (ms)
    spike_neurons: np.ndarray     # which neuron fired it (0..99)
    is_inhibitory: np.ndarray     # True for each inhibitory neuron
    voltage_time_ms: np.ndarray   # time axis of the voltage trace (ms)
    voltage_mV: np.ndarray        # voltage of the recorded neuron (mV)
    voltage_neuron: int           # which neuron's voltage was recorded
    duration_ms: float
    input_type: str
    background: bool

    @property
    def n_spikes(self) -> int:
        return int(len(self.spike_times_ms))

    @property
    def mean_rate_hz(self) -> float:
        """Average firing rate per neuron (spikes per second)."""
        n = len(self.is_inhibitory)
        return self.n_spikes / n / (self.duration_ms / 1000.0)


def build_connections(seed: int):
    """Random wiring. Returns (pre, post, weight in volts as a plain float).

    Like the reference, weight = sign x synapse count x w_syn, where the sign
    is + for excitatory neurons and - for inhibitory ones.
    """
    rng = np.random.default_rng(seed)
    is_inh = np.arange(N_NEURONS) >= N_NEURONS - N_INHIBITORY
    connected = rng.random((N_NEURONS, N_NEURONS)) < CONNECTION_PROB
    np.fill_diagonal(connected, False)  # no neuron connects to itself
    pre, post = np.nonzero(connected)
    lo, hi = SYNAPSES_PER_CONNECTION
    counts = rng.integers(lo, hi + 1, size=len(pre))
    sign = np.where(is_inh[pre], -INHIBITORY_SCALE, 1)
    weight = sign * counts * float(REFERENCE_PARAMS["w_syn"])
    return pre, post, weight, is_inh


def run_toy_network(input_type: str = "none", background: bool = True,
                    duration=500 * ms, seed: int = 1,
                    voltage_neuron: int = 0) -> ToyResult:
    """Run the toy network once and return its spikes and one voltage trace.

    input_type: "excitatory", "inhibitory" or "none" (the switchable input).
    background: True gives every neuron a steady excitatory background input.
    seed: fixes all randomness, so the same call always gives the same answer.
    """
    if input_type not in INPUT_TYPES:
        raise ValueError(f"input_type must be one of {INPUT_TYPES}")
    brian_seed(seed)
    defaultclock.dt = DT

    neurons = NeuronGroup(
        N_NEURONS, EQUATIONS, threshold=THRESHOLD, reset=RESET,
        refractory="rfc", method="linear", namespace=dict(REFERENCE_PARAMS),
    )
    neurons.v = REFERENCE_PARAMS["v_0"]
    neurons.g = 0 * mV
    neurons.rfc = REFERENCE_PARAMS["t_rfc"]

    pre, post, weight, is_inh = build_connections(seed)
    synapses = Synapses(neurons, neurons, "w : volt", on_pre="g += w",
                        delay=REFERENCE_PARAMS["t_dly"])
    synapses.connect(i=pre, j=post)
    synapses.w = weight * 1000 * mV  # weight is in volts; convert

    objects = [neurons, synapses]
    w_syn = REFERENCE_PARAMS["w_syn"]
    if background:
        objects.append(PoissonInput(
            neurons, "g", BACKGROUND["sources"], BACKGROUND["rate"],
            weight=BACKGROUND["synapses"] * w_syn))
    if input_type != "none":
        sign = 1 if input_type == "excitatory" else -1
        objects.append(PoissonInput(
            neurons, "g", TEST_INPUT["sources"], TEST_INPUT["rate"],
            weight=sign * TEST_INPUT["synapses"] * w_syn))

    spikes = SpikeMonitor(neurons)
    voltage = StateMonitor(neurons, "v", record=voltage_neuron)
    net = Network(*objects, spikes, voltage)
    net.run(duration)

    return ToyResult(
        spike_times_ms=np.asarray(spikes.t / ms),
        spike_neurons=np.asarray(spikes.i),
        is_inhibitory=is_inh,
        voltage_time_ms=np.asarray(voltage.t / ms),
        voltage_mV=np.asarray(voltage.v[0] / mV),
        voltage_neuron=voltage_neuron,
        duration_ms=float(duration / ms),
        input_type=input_type,
        background=background,
    )
