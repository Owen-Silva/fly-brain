| Workload | Design | Time per task | Energy per task | Accuracy | Labels | Note |
|---|---|---|---|---|---|---|
| (a) feeding decision, 400-neuron circuit (default) | hybrid (clocked) = neuromorphic + M33 | 65.8 ms | 5.02 mJ | 100.0% | cost modeled; accuracy sim, 9-bit weights | scheduler: rule: spiking -> neuromorphic |
| (a) feeding decision, 400-neuron circuit (default) | neuromorphic only (clocked) | 65.8 ms | 5.02 mJ | 100.0% | cost modeled; accuracy sim, 9-bit weights |  |
| (a) feeding decision, 400-neuron circuit (default) | hybrid (event) = neuromorphic + M33 | 4.29 ms | 350 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights | scheduler: rule: spiking -> neuromorphic |
| (a) feeding decision, 400-neuron circuit (default) | neuromorphic only (event) | 4.27 ms | 349 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights |  |
| (a) feeding decision, 400-neuron circuit (default) | CPU only: laptop x86 | 10 ms | 150 mJ | 100.0% | cost measured; accuracy sim, float64 |  |
| (a) feeding decision, 400-neuron circuit (default) | CPU only: M33 | 694 ms | 20.8 mJ | 100.0% | cost modeled; accuracy sim (float64 stand-in) |  |
| (a) feeding decision, 400-neuron circuit (default) | GPU (T4) | 100 ms | 7.02 J | 100.0% | cost modeled; accuracy sim, float64 |  |
| (a) feeding decision, 36-neuron circuit | hybrid (clocked) = neuromorphic + M33 | 38.1 ms | 2.8 mJ | 100.0% | cost modeled; accuracy sim, 9-bit weights | scheduler: rule: spiking -> neuromorphic |
| (a) feeding decision, 36-neuron circuit | neuromorphic only (clocked) | 38.1 ms | 2.8 mJ | 100.0% | cost modeled; accuracy sim, 9-bit weights |  |
| (a) feeding decision, 36-neuron circuit | hybrid (event) = neuromorphic + M33 | 91.8 us | 6.47 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights | scheduler: rule: spiking -> neuromorphic |
| (a) feeding decision, 36-neuron circuit | neuromorphic only (event) | 71.5 us | 5.86 uJ | 100.0% | cost modeled; accuracy sim, 9-bit weights |  |
| (a) feeding decision, 36-neuron circuit | CPU only: laptop x86 | 1.1 ms | 16.5 mJ | 98.5% | cost measured; accuracy sim, float64 |  |
| (a) feeding decision, 36-neuron circuit | CPU only: M33 | 63.8 ms | 1.91 mJ | 98.5% | cost modeled; accuracy sim (float64 stand-in) |  |
| (a) feeding decision, 36-neuron circuit | GPU (T4) | 100 ms | 7 J | 98.5% | cost modeled; accuracy sim, float64 |  |
| (b) continual odour learning (per labelled sniff) | hybrid (clocked) = neuromorphic + M33 | 806 us | 65.9 uJ | 66.2% | cost modeled; accuracy sim, 8-bit read-out |  |
| (b) continual odour learning (per labelled sniff) | neuromorphic only (clocked) | 786 us | 65.3 uJ | 66.2% | cost modeled; accuracy sim, 8-bit read-out |  |
| (b) continual odour learning (per labelled sniff) | hybrid (event) = neuromorphic + M33 | 721 us | 58 uJ | 66.2% | cost modeled; accuracy sim, 8-bit read-out |  |
| (b) continual odour learning (per labelled sniff) | neuromorphic only (event) | 701 us | 57.4 uJ | 66.2% | cost modeled; accuracy sim, 8-bit read-out |  |
| (b) continual odour learning (per labelled sniff) | CPU only: laptop x86 | 121 us | 1.81 mJ | 66.8% | cost measured; accuracy sim, float32 |  |
| (b) continual odour learning (per labelled sniff) | CPU only: M33 | 866 us | 26 uJ | 66.8% | cost modeled; accuracy sim, float32 |  |
| (b) continual odour learning (per labelled sniff) | GPU (T4) | 50 us | 3.5 mJ | 66.8% | cost modeled; accuracy sim, float32 |  |
| (c) exact sum of 50,000 64-bit integers | hybrid = its M33 core | 1.33 ms | 40 uJ | 100.0% | cost modeled; accuracy exact | scheduler: rule: exact -> conventional |
| (c) exact sum of 50,000 64-bit integers | neuromorphic only | n/a | n/a | n/a | cost n/a; accuracy not possible | spiking cores hold 8-9-bit weights and no general memory; exact results unsupported |
| (c) exact sum of 50,000 64-bit integers | CPU only: laptop x86 | 13 us | 195 uJ | 100.0% | cost measured; accuracy exact, checked |  |
| (c) exact sum of 50,000 64-bit integers | CPU only: M33 | 1.33 ms | 40 uJ | 100.0% | cost modeled; accuracy exact |  |
| (c) exact sum of 50,000 64-bit integers | GPU (T4) | 64.6 us | 4.52 mJ | 100.0% | cost modeled; accuracy exact (integer) |  |
| (c) sort 50,000 32-bit integers | hybrid = its M33 core | 62.4 ms | 1.87 mJ | 100.0% | cost modeled; accuracy exact | scheduler: rule: exact -> conventional |
| (c) sort 50,000 32-bit integers | neuromorphic only | n/a | n/a | n/a | cost n/a; accuracy not possible | spiking cores hold 8-9-bit weights and no general memory; exact results unsupported |
| (c) sort 50,000 32-bit integers | CPU only: laptop x86 | 261 us | 3.91 mJ | 100.0% | cost measured; accuracy exact, checked |  |
| (c) sort 50,000 32-bit integers | CPU only: M33 | 62.4 ms | 1.87 mJ | 100.0% | cost modeled; accuracy exact |  |
| (c) sort 50,000 32-bit integers | GPU (T4) | 118 us | 8.28 mJ | 100.0% | cost modeled; accuracy exact (integer) |  |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | hybrid (clocked) | 702 us | 74 mJ | 95.9% | cost modeled; accuracy sim; log exact | 6.39e+03 J per day (static power low-high: 1.64e+03-2.57e+04) |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | neuromorphic only (clocked) | 699 us | 73 mJ | 95.9% | cost modeled; accuracy sim; log none (no exact memory) | 6.31e+03 J per day (static power low-high: 1.56e+03-2.56e+04) |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | hybrid (event) | 512 us | 74 mJ | 95.9% | cost modeled; accuracy sim; log exact | 6.39e+03 J per day (static power low-high: 1.64e+03-2.57e+04) |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | neuromorphic only (event) | 509 us | 73 mJ | 95.9% | cost modeled; accuracy sim; log none (no exact memory) | 6.31e+03 J per day (static power low-high: 1.56e+03-2.56e+04) |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | CPU only: M33 (modeled) | 854 us | 1.02 mJ | 95.9% | cost modeled; accuracy sim; log exact | 88.5 J per day (static power low-high: 88.5-88.5) |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | CPU only: laptop (measured time) | 115 us | 3 J | 95.9% | cost measured time; energy modeled; accuracy sim; log exact | 2.59e+05 J per day (static power low-high: 2.59e+05-2.59e+05) |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | GPU (modeled) | 45 us | 13 J | 95.9% | cost modeled; accuracy sim; log exact (host CPU) | 1.12e+06 J per day (static power low-high: 1.12e+06-1.12e+06) |
| (e) electrode bottleneck: 8 stimulation patterns | hybrid + living module (CL1-like, 59 channels) | 60.2 ms | 1.5 J | 95.4% | cost modeled; accuracy sim; GUESSED biology | scheduler: rule: adaptive-bio -> living |
| (e) electrode bottleneck: 8 stimulation patterns | hybrid (clocked): culture network on silicon, every cell read | 5.62 ms | 427 uJ | 97.5% | cost modeled; accuracy sim; no electrodes, pooled read-out |  |
| (e) electrode bottleneck: 8 stimulation patterns | hybrid (event): culture network on silicon, every cell read | 341 us | 10.9 uJ | 97.5% | cost modeled; accuracy sim; no electrodes, pooled read-out |  |
| (e) electrode bottleneck: 8 stimulation patterns | CPU only: laptop x86 (simulated culture, every cell read) | 1.14 ms | 17 mJ | 97.5% | cost measured; accuracy sim, pooled read-out |  |
| (e) electrode bottleneck: 8 stimulation patterns | CPU only: M33 | 101 ms | 3.02 mJ | 97.5% | cost modeled; accuracy sim, pooled read-out |  |
| (e) electrode bottleneck: 8 stimulation patterns | GPU (T4) | 6.07 ms | 425 mJ | 97.5% | cost modeled; accuracy sim, pooled read-out |  |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | hybrid + living module (CL1-like, 59 electrodes) | 1 s | 25 J | 45.8% | cost modeled; accuracy sim; GUESSED biology | hits per rally 0.62 (min 0-5: 0.61, min 6-20: 0.64); 5 x 20-min sessions |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | hybrid + living module (MaxOne-like, 1,024 electrodes) | 1 s | 25 J | 62.2% | cost modeled; accuracy sim; GUESSED biology | hits per rally 1.89 (min 0-5: 2.21, min 6-20: 1.81); 5 x 20-min sessions |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | hybrid (clocked): the culture network on the neuromorphic core | 18.7 ms | 74.1 mJ | 98.9% | cost modeled; accuracy sim; sim | hits per rally 41.73 (min 0-5: 45.13, min 6-20: 88.50); 5 x 20-min sessions |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | CPU only: M33 running a simple controller | 46.7 us | 1 mJ | 100.0% | cost modeled; accuracy sim; sim | never missed in 3 x 20-min sessions |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | paddle driven by noise (DishBrain's in-silico control) | n/a | n/a | 46.6% | cost n/a; accuracy sim | hits per rally 0.86 (paddle size FITTED to DishBrain's 0.80) |
