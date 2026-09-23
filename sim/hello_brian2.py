"""Phase 0 checkpoint: prove Brian2 runs on this machine.

One leaky integrate-and-fire neuron driven by a constant input strong enough
to reach threshold. If Brian2 works, it fires at a regular rate.
"""
from brian2 import (NeuronGroup, SpikeMonitor, StateMonitor, defaultclock,
                    mV, ms, prefs, run, start_scope)


def main():
    start_scope()
    defaultclock.dt = 0.1 * ms

    # dv/dt pulls v toward v_rest and is pushed up by a constant drive.
    eqs = "dv/dt = (v_rest - v + drive) / tau : volt"
    neuron = NeuronGroup(
        1, eqs, threshold="v > v_th", reset="v = v_reset", method="exact",
        namespace={"v_rest": -52 * mV, "v_th": -45 * mV, "v_reset": -52 * mV,
                   "drive": 10 * mV, "tau": 20 * ms},
    )
    neuron.v = -52 * mV

    spikes = SpikeMonitor(neuron)
    StateMonitor(neuron, "v", record=0)
    run(200 * ms)

    print(f"codegen target: {prefs.codegen.target}")
    print(f"spikes in 200 ms: {spikes.num_spikes}")
    assert spikes.num_spikes > 0, "neuron never fired: Brian2 is not working"
    print("Brian2 hello-world OK")


if __name__ == "__main__":
    main()
