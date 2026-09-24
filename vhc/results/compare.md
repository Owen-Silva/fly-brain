| Workload | Design | v0 time | v1 time | v0 energy | v1 energy | v1 range (energy) | v0 acc | v1 acc |
|---|---|---|---|---|---|---|---|---|
| (a) feeding decision, 400-neuron circuit (default) | hybrid (clocked) = neuromorphic + M33 | 23.6 ms | 65.8 ms | 217 uJ | 5.02 mJ | 642 uJ - 19.7 mJ | 100.0% | 100.0% |
| (a) feeding decision, 400-neuron circuit (default) | neuromorphic only (clocked) | 23.6 ms | 65.8 ms | 217 uJ | 5.02 mJ | 641 uJ - 19.7 mJ | 100.0% | 100.0% |
| (a) feeding decision, 400-neuron circuit (default) | hybrid (event) = neuromorphic + M33 | 4.29 ms | 4.29 ms | 38.2 uJ | 350 uJ | 115 uJ - 1.3 mJ | 100.0% | 100.0% |
| (a) feeding decision, 400-neuron circuit (default) | neuromorphic only (event) | 4.27 ms | 4.27 ms | 37.6 uJ | 349 uJ | 114 uJ - 1.3 mJ | 100.0% | 100.0% |
| (a) feeding decision, 400-neuron circuit (default) | CPU only: laptop x86 | 12.9 ms | 10 ms | 194 mJ | 150 mJ |  | 100.0% | 100.0% |
| (a) feeding decision, 400-neuron circuit (default) | CPU only: M33 | 694 ms | 694 ms | 20.8 mJ | 20.8 mJ |  | 100.0% | 100.0% |
| (a) feeding decision, 400-neuron circuit (default) | GPU (T4) | 100 ms | 100 ms | 7.02 J | 7.02 J |  | 100.0% | 100.0% |
| (a) feeding decision, 36-neuron circuit | hybrid (clocked) = neuromorphic + M33 | 3.08 ms | 38.1 ms | 19.5 uJ | 2.8 mJ | 74.6 uJ - 11.3 mJ | 100.0% | 100.0% |
| (a) feeding decision, 36-neuron circuit | neuromorphic only (clocked) | 3.06 ms | 38.1 ms | 18.9 uJ | 2.8 mJ | 74 uJ - 11.3 mJ | 100.0% | 100.0% |
| (a) feeding decision, 36-neuron circuit | hybrid (event) = neuromorphic + M33 | 91.8 us | 91.8 us | 1.25 uJ | 6.47 uJ | 2.54 uJ - 22.4 uJ | 100.0% | 100.0% |
| (a) feeding decision, 36-neuron circuit | neuromorphic only (event) | 71.5 us | 71.5 us | 640 nJ | 5.86 uJ | 1.93 uJ - 21.8 uJ | 100.0% | 100.0% |
| (a) feeding decision, 36-neuron circuit | CPU only: laptop x86 | 1.24 ms | 1.1 ms | 18.7 mJ | 16.5 mJ |  | 98.5% | 98.5% |
| (a) feeding decision, 36-neuron circuit | CPU only: M33 | 63.8 ms | 63.8 ms | 1.91 mJ | 1.91 mJ |  | 98.5% | 98.5% |
| (a) feeding decision, 36-neuron circuit | GPU (T4) | 100 ms | 100 ms | 7 J | 7 J |  | 98.5% | 98.5% |
| (b) continual odour learning (per labelled sniff) | hybrid (clocked) = neuromorphic + M33 | 316 us | 806 us | 8.54 uJ | 65.9 uJ | 13.9 uJ - 241 uJ | 66.2% | 66.2% |
| (b) continual odour learning (per labelled sniff) | neuromorphic only (clocked) | 296 us | 786 us | 7.93 uJ | 65.3 uJ | 13.3 uJ - 241 uJ | 66.2% | 66.2% |
| (b) continual odour learning (per labelled sniff) | hybrid (event) = neuromorphic + M33 | 721 us | 721 us | 6.78 uJ | 58 uJ | 19.4 uJ - 214 uJ | 66.2% | 66.2% |
| (b) continual odour learning (per labelled sniff) | neuromorphic only (event) | 701 us | 701 us | 6.17 uJ | 57.4 uJ | 18.8 uJ - 214 uJ | 66.2% | 66.2% |
| (b) continual odour learning (per labelled sniff) | CPU only: laptop x86 | 145 us | 121 us | 2.17 mJ | 1.81 mJ |  | 66.8% | 66.8% |
| (b) continual odour learning (per labelled sniff) | CPU only: M33 | 866 us | 866 us | 26 uJ | 26 uJ |  | 66.8% | 66.8% |
| (b) continual odour learning (per labelled sniff) | GPU (T4) | 50 us | 50 us | 3.5 mJ | 3.5 mJ |  | 66.8% | 66.8% |
| (c) exact sum of 50,000 64-bit integers | hybrid = its M33 core | 1.33 ms | 1.33 ms | 40 uJ | 40 uJ |  | 100.0% | 100.0% |
| (c) exact sum of 50,000 64-bit integers | neuromorphic only | n/a | n/a | n/a | n/a |  | n/a | n/a |
| (c) exact sum of 50,000 64-bit integers | CPU only: laptop x86 | 14.5 us | 13 us | 218 uJ | 195 uJ |  | 100.0% | 100.0% |
| (c) exact sum of 50,000 64-bit integers | CPU only: M33 | 1.33 ms | 1.33 ms | 40 uJ | 40 uJ |  | 100.0% | 100.0% |
| (c) exact sum of 50,000 64-bit integers | GPU (T4) | 64.6 us | 64.6 us | 4.52 mJ | 4.52 mJ |  | 100.0% | 100.0% |
| (c) sort 50,000 32-bit integers | hybrid = its M33 core | 62.4 ms | 62.4 ms | 1.87 mJ | 1.87 mJ |  | 100.0% | 100.0% |
| (c) sort 50,000 32-bit integers | neuromorphic only | n/a | n/a | n/a | n/a |  | n/a | n/a |
| (c) sort 50,000 32-bit integers | CPU only: laptop x86 | 284 us | 261 us | 4.27 mJ | 3.91 mJ |  | 100.0% | 100.0% |
| (c) sort 50,000 32-bit integers | CPU only: M33 | 62.4 ms | 62.4 ms | 1.87 mJ | 1.87 mJ |  | 100.0% | 100.0% |
| (c) sort 50,000 32-bit integers | GPU (T4) | 118 us | 118 us | 8.28 mJ | 8.28 mJ |  | 100.0% | 100.0% |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | hybrid (clocked) | 280 us | 702 us | 1.01 mJ | 74 mJ | 19 mJ - 297 mJ | 95.9% | 95.9% |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | neuromorphic only (clocked) | 277 us | 699 us | 7.53 uJ | 73 mJ | 18 mJ - 296 mJ | 95.9% | 95.9% |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | hybrid (event) | 512 us | 512 us | 1 mJ | 74 mJ | 19 mJ - 297 mJ | 95.9% | 95.9% |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | neuromorphic only (event) | 509 us | 509 us | 4.48 uJ | 73 mJ | 18 mJ - 296 mJ | 95.9% | 95.9% |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | CPU only: M33 (modeled) | 854 us | 854 us | 1.02 mJ | 1.02 mJ | 1.02 mJ - 1.02 mJ | 95.9% | 95.9% |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | CPU only: laptop (measured time) | 115 us | 115 us | 3 J | 3 J | 3 J - 3 J | 95.9% | 95.9% |
| (d) hybrid odour watch with exact log (per sniff; energy per day in note) | GPU (modeled) | 45 us | 45 us | 13 J | 13 J | 13 J - 13 J | 95.9% | 95.9% |
| (e) electrode bottleneck: 8 stimulation patterns | hybrid + living module (CL1-like, 59 channels) | 60.2 ms | 60.2 ms | 1.5 J | 1.5 J |  | 89.6% | 95.4% |
| (e) electrode bottleneck: 8 stimulation patterns | hybrid (clocked): culture network on silicon, every cell read | 3.58 ms | 5.62 ms | 41.1 uJ | 427 uJ | 99.6 uJ - 1.61 mJ | 91.7% | 97.5% |
| (e) electrode bottleneck: 8 stimulation patterns | hybrid (event): culture network on silicon, every cell read | 341 us | 341 us | 9.96 uJ | 10.9 uJ | 10.2 uJ - 13.7 uJ | 91.7% | 97.5% |
| (e) electrode bottleneck: 8 stimulation patterns | CPU only: laptop x86 (simulated culture, every cell read) | 1.3 ms | 1.14 ms | 19.5 mJ | 17 mJ |  | 91.7% | 97.5% |
| (e) electrode bottleneck: 8 stimulation patterns | CPU only: M33 | 101 ms | 101 ms | 3.03 mJ | 3.02 mJ |  | 91.7% | 97.5% |
| (e) electrode bottleneck: 8 stimulation patterns | GPU (T4) | 6.07 ms | 6.07 ms | 425 mJ | 425 mJ |  | 91.7% | 97.5% |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | hybrid + living module (CL1-like, 59 electrodes) | n/a | 1 s | n/a | 25 J |  | new | 45.8% |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | hybrid + living module (MaxOne-like, 1,024 electrodes) | n/a | 1 s | n/a | 25 J |  | new | 62.2% |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | hybrid (clocked): the culture network on the neuromorphic core | 11 ms | 18.7 ms | 1.11 mJ | 74.1 mJ |  | new | 98.9% |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | CPU only: M33 running a simple controller | n/a | 46.7 us | n/a | 1 mJ |  | new | 100.0% |
| (f) Pong, DishBrain-style (per game-second; accuracy = hit rate) | paddle driven by noise (DishBrain's in-silico control) | n/a | n/a | n/a | n/a |  | new | 46.6% |
