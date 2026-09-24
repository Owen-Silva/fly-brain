| Workload | Design | Time per task | Energy per task | Accuracy | Labels | Note |
|---|---|---|---|---|---|---|
| (a) feeding decision, 36-neuron circuit | hybrid (clocked) = neuromorphic + M33 | 3.08 ms | 19.5 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights | scheduler: rule: spiking -> neuromorphic |
| (a) feeding decision, 36-neuron circuit | neuromorphic only (clocked) | 3.06 ms | 18.9 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights |  |
| (a) feeding decision, 36-neuron circuit | hybrid (event) = neuromorphic + M33 | 91.8 us | 1.25 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights | scheduler: rule: spiking -> neuromorphic |
| (a) feeding decision, 36-neuron circuit | neuromorphic only (event) | 71.5 us | 640 nJ | 100.0% | cost modeled; accuracy sim, 9-bit weights |  |
| (a) feeding decision, 36-neuron circuit | CPU only: laptop x86 | 1.24 ms | 18.7 mJ | 98.5% | cost measured; accuracy sim, float64 |  |
| (a) feeding decision, 36-neuron circuit | CPU only: M33 | 63.8 ms | 1.91 mJ | 98.5% | cost modeled; accuracy sim (float64 stand-in) |  |
| (a) feeding decision, 36-neuron circuit | GPU (T4) | 100 ms | 7 J | 98.5% | cost modeled; accuracy sim, float64 |  |
| (a) feeding decision, 400-neuron circuit | hybrid (clocked) = neuromorphic + M33 | 23.6 ms | 217 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights | scheduler: rule: spiking -> neuromorphic |
| (a) feeding decision, 400-neuron circuit | neuromorphic only (clocked) | 23.6 ms | 217 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights |  |
| (a) feeding decision, 400-neuron circuit | hybrid (event) = neuromorphic + M33 | 4.29 ms | 38.2 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights | scheduler: rule: spiking -> neuromorphic |
| (a) feeding decision, 400-neuron circuit | neuromorphic only (event) | 4.27 ms | 37.6 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights |  |
| (a) feeding decision, 400-neuron circuit | CPU only: laptop x86 | 12.9 ms | 194 mJ | 100.0% | cost measured; accuracy sim, float64 |  |
| (a) feeding decision, 400-neuron circuit | CPU only: M33 | 694 ms | 20.8 mJ | 100.0% | cost modeled; accuracy sim (float64 stand-in) |  |
| (a) feeding decision, 400-neuron circuit | GPU (T4) | 100 ms | 7.02 J | 100.0% | cost modeled; accuracy sim, float64 |  |
| (b) continual odour learning (per labelled sniff) | hybrid (clocked) = neuromorphic + M33 | 316 us | 8.54 uJ | 66.2% | cost modeled; accuracy sim, 8-bit read-out |  |
| (b) continual odour learning (per labelled sniff) | neuromorphic only (clocked) | 296 us | 7.93 uJ | 66.2% | cost modeled; accuracy sim, 8-bit read-out |  |
| (b) continual odour learning (per labelled sniff) | hybrid (event) = neuromorphic + M33 | 721 us | 6.78 uJ | 66.2% | cost modeled; accuracy sim, 8-bit read-out |  |
| (b) continual odour learning (per labelled sniff) | neuromorphic only (event) | 701 us | 6.17 uJ | 66.2% | cost modeled; accuracy sim, 8-bit read-out |  |
| (b) continual odour learning (per labelled sniff) | CPU only: laptop x86 | 145 us | 2.17 mJ | 66.8% | cost measured; accuracy sim, float32 |  |
| (b) continual odour learning (per labelled sniff) | CPU only: M33 | 866 us | 26 uJ | 66.8% | cost modeled; accuracy sim, float32 |  |
| (b) continual odour learning (per labelled sniff) | GPU (T4) | 50 us | 3.5 mJ | 66.8% | cost modeled; accuracy sim, float32 |  |
| (c) exact sum of 50,000 64-bit integers | hybrid = its M33 core | 1.33 ms | 40 uJ | 100.0% | cost modeled; accuracy exact | scheduler: rule: exact -> conventional |
| (c) exact sum of 50,000 64-bit integers | neuromorphic only | n/a | n/a | n/a | cost n/a; accuracy not possible | spiking cores hold 8-9-bit weights and no general memory; exact results unsupported |
| (c) exact sum of 50,000 64-bit integers | CPU only: laptop x86 | 14.5 us | 218 uJ | 100.0% | cost measured; accuracy exact, checked |  |
| (c) exact sum of 50,000 64-bit integers | CPU only: M33 | 1.33 ms | 40 uJ | 100.0% | cost modeled; accuracy exact |  |
| (c) exact sum of 50,000 64-bit integers | GPU (T4) | 64.6 us | 4.52 mJ | 100.0% | cost modeled; accuracy exact (integer) |  |
| (c) sort 50,000 32-bit integers | hybrid = its M33 core | 62.4 ms | 1.87 mJ | 100.0% | cost modeled; accuracy exact | scheduler: rule: exact -> conventional |
| (c) sort 50,000 32-bit integers | neuromorphic only | n/a | n/a | n/a | cost n/a; accuracy not possible | spiking cores hold 8-9-bit weights and no general memory; exact results unsupported |
| (c) sort 50,000 32-bit integers | CPU only: laptop x86 | 284 us | 4.27 mJ | 100.0% | cost measured; accuracy exact, checked |  |
| (c) sort 50,000 32-bit integers | CPU only: M33 | 62.4 ms | 1.87 mJ | 100.0% | cost modeled; accuracy exact |  |
| (c) sort 50,000 32-bit integers | GPU (T4) | 118 us | 8.28 mJ | 100.0% | cost modeled; accuracy exact (integer) |  |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | hybrid (clocked) | 280 us | 1.01 mJ | 95.9% | cost modeled; accuracy sim; log exact | 87.1 J per day |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | neuromorphic only (clocked) | 277 us | 7.53 uJ | 95.9% | cost modeled; accuracy sim; log none (no exact memory) | 0.651 J per day |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | hybrid (event) | 512 us | 1 mJ | 95.9% | cost modeled; accuracy sim; log exact | 86.8 J per day |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | neuromorphic only (event) | 509 us | 4.48 uJ | 95.9% | cost modeled; accuracy sim; log none (no exact memory) | 0.387 J per day |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | CPU only: M33 (modeled) | 854 us | 1.02 mJ | 95.9% | cost modeled; accuracy sim; log exact | 88.5 J per day |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | CPU only: laptop (measured time) | 140 us | 3 J | 95.9% | cost measured time; energy modeled; accuracy sim; log exact | 2.59e+05 J per day |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | GPU (modeled) | 45 us | 13 J | 95.9% | cost modeled; accuracy sim; log exact (host CPU) | 1.12e+06 J per day |
| (e) electrode bottleneck: 8 stimulation patterns | hybrid + living module (CL1-like, 59 channels) | 60.2 ms | 1.5 J | 89.6% | cost modeled; accuracy sim; GUESSED biology | scheduler: rule: adaptive-bio -> living |
| (e) electrode bottleneck: 8 stimulation patterns | hybrid (clocked): culture network on silicon, every cell read | 3.6 ms | 41.2 uJ | 91.7% | cost modeled; accuracy sim; no electrodes, pooled read-out |  |
| (e) electrode bottleneck: 8 stimulation patterns | hybrid (event): culture network on silicon, every cell read | 421 us | 10.7 uJ | 91.7% | cost modeled; accuracy sim; no electrodes, pooled read-out |  |
| (e) electrode bottleneck: 8 stimulation patterns | CPU only: laptop x86 (simulated culture, every cell read) | 1.3 ms | 19.5 mJ | 91.7% | cost measured; accuracy sim, pooled read-out |  |
| (e) electrode bottleneck: 8 stimulation patterns | CPU only: M33 | 101 ms | 3.03 mJ | 91.7% | cost modeled; accuracy sim, pooled read-out |  |
| (e) electrode bottleneck: 8 stimulation patterns | GPU (T4) | 6.07 ms | 425 mJ | 91.7% | cost modeled; accuracy sim, pooled read-out |  |
