# Data licence

This repository mixes code and data, and they are under different licences.

| What | Licence |
|---|---|
| Source code and documentation: every `.py`, `.sh`, `.js`, `.html`, `.css`, `.md` and `.ini` file, and `requirements*.txt`, anywhere in the repo, plus `vhc/results/*.json` (hardware cost-model output, no connectome data) | MIT, see [LICENSE](LICENSE) |
| Code copied or adapted from Shiu & Spiller's Drosophila_brain_model (`sim/shiu_model.py`, `sim/fast_engine.py`) | MIT, Copyright (c) 2023 Philip Shiu and Nico Spiller, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |
| FlyWire-derived data and results (scope below) | **CC BY-NC 4.0**, not MIT |
| Three DoOR-derived tables (listed below) | **CC BY-SA 4.0**, not MIT |

## FlyWire-derived files: CC BY-NC 4.0

FlyWire's public release data is made available under the Creative Commons
Attribution-NonCommercial 4.0 International licence (CC BY-NC 4.0,
https://creativecommons.org/licenses/by-nc/4.0/). Source: https://flywire.ai/guidelines .
The Zenodo deposit of the connectome (doi 10.5281/zenodo.10676866) is labelled CC BY 4.0;
this project follows the stricter NC terms.

**Scope.** These files are covered by CC BY-NC 4.0 (except the three DoOR files below):

- every data, result, figure and video file under `experiments/`, that is every file there
  with the extension `.csv`, `.npz`, `.npy`, `.parquet`, `.json`, `.txt`, `.png` or `.mp4`;
- `app/setups/*.json` (saved experiment setups that list FlyWire neuron IDs).

They are simulation outputs, figures and tables computed from, or keyed by, the FlyWire
connectome (releases 630 and 783). Some of them are direct extracts of FlyWire connectivity:

- `experiments/phase8/results/circuit_630.npz` (a 6,289-neuron, 570,433-edge subgraph of release 630)
- `experiments/minimal_circuit/results/robust_circuit.json`
- `experiments/phase7_gap/results/coupling_table.csv`
- small edge lists and input tables such as `experiments/phase6/runaway/results/strong_loop_edges.csv`,
  `experiments/phase5/unexplored/results/dn_inputs.csv`,
  `experiments/scorecard_batch1/results/direct_wiring.csv`,
  `experiments/cb0216_loop/results/loop_candidates.csv` and the `upn_glomeruli.csv` tables
- `experiments/banc_asymmetry/results/*.csv`: per-glomerulus tables built from FlyWire 630 and 783,
  and also from BANC, the hemibrain and maleCNS (see "Other connectomes" below). Their own terms
  apply as well; because FlyWire data is mixed in, these files stay CC BY-NC 4.0 as a whole.

**You may** share and adapt these files for non-commercial purposes, with attribution.
**Attribution:** cite FlyWire as asked at https://codex.flywire.ai/about_flywire
(Dorkenwald et al. 2024, Nature 634:124-138; Schlegel et al. 2024, Nature 634:139-152; see
the citation table on that page for the full list) and follow https://flywire.ai/guidelines .
Also cite Shiu et al. 2024 (Nature 634:210-219) for the model, and this repository.

The raw FlyWire downloads themselves are not in this repository (`data/` is git-ignored);
the README explains how to fetch them.

## Other connectomes (BANC, hemibrain, maleCNS)

Only `experiments/banc_asymmetry/` uses them. The tables were read from the BANC team's public
bucket (https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/,
`compiled_data/banc_888`, `hemibrain_121`, `malecns_09`); the raw downloads are not in this repo.

| Dataset | Licence | Source of that statement | Cite |
|---|---|---|---|
| BANC, release v888 | CC BY 4.0 | The bucket's README states no licence, but says the data are mirrored, with the same documentation, at https://doi.org/10.7910/DVN/7WTH1N. That Harvard Dataverse deposit (v3.0) is licensed CC BY 4.0. We have not seen a separate licence for the bucket copy itself. | Bates et al., *Nature* 656, 957-970 (2026), https://doi.org/10.1038/s41586-026-10735-w, and the Dataverse DOI |
| hemibrain v1.2.1 | CC BY 4.0 | https://www.janelia.org/project-team/flyem/hemibrain : "Hemibrain is licensed under CC-BY" (links CC BY 4.0). The statement names no version, so coverage of v1.2.1 specifically is not confirmed. | Scheffer et al., *eLife* 9, e57443 (2020), https://doi.org/10.7554/eLife.57443 |
| maleCNS v0.9 | CC BY 4.0 | https://male-cns.janelia.org : "The Male CNS dataset is licensed under CC-BY" (links CC BY 4.0). The statement names no version, so coverage of v0.9 specifically is not confirmed. | Berg et al., *Cell* 189, 5504-5526.e15 (2026), https://doi.org/10.1016/j.cell.2026.08.015 |

All three are attribution licences, compatible with the CC BY-NC 4.0 terms the combined
result files carry.

## DoOR-derived files: CC BY-SA 4.0

These three tables are derived from DoOR.data (Münch & Galizia 2016, which includes the
Hallem & Carlson 2006 receptor responses), published under CC BY-SA 4.0
(https://creativecommons.org/licenses/by-sa/4.0/; source: the DESCRIPTION file of
https://github.com/ropensci/DoOR.data):

- `experiments/olfaction_realfly/results/hc_delta.csv`
- `experiments/olfaction_realfly/results/hc_sfr.csv`
- `experiments/olfaction_realfly/results/door_ext_delta.csv`

Changes (by `experiments/olfaction_realfly/prep_inputs.py`): values were selected and
reshaped into odour x glomerulus tables, the spontaneous rate was separated out, and for
`door_ext_delta.csv` DoOR consensus responses were scaled back to spikes/s. If you share these
files or adaptations of them, credit DoOR (Münch & Galizia 2016, *Scientific Reports* 6, 21841,
https://doi.org/10.1038/srep21841; Hallem & Carlson 2006, *Cell* 125, 143-160,
https://doi.org/10.1016/j.cell.2006.01.050) and
share them under CC BY-SA 4.0.

## Not legal advice

This file states which licence each part of the repository is offered under. If a file's
status is unclear, treat it as data under CC BY-NC 4.0.
