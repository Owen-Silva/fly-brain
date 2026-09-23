# Fly Brain Simulator

A simulation of the whole fruit fly (*Drosophila melanogaster*) brain, built
from the real wiring diagram mapped by the FlyWire project: about 139,000
neurons joined by about 54 million synapses. The plan is to reproduce a
published whole-brain model (Shiu et al. 2024, *Nature*), check that it gives
the same answers as the paper, and then wrap it in an app for running
experiments: switch neurons on, silence them, and watch activity spread.

- [PLAN.md](PLAN.md): the phases and their checkpoints (source of truth).
- [EXPERIMENTS.md](EXPERIMENTS.md): dated log of every experiment and whether
  it was validated.
- [docs/](docs/): plain-English explanations of each phase, for example
  [docs/phase2-explained.md](docs/phase2-explained.md) (the brain data).

## Setup (Windows)

Needs Python 3.13. No C/C++ compiler is required (Brian2 runs in its slower
pure-Python mode without one).

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Get the data

The data is large and is never committed (`data/` is in `.gitignore`).

```powershell
# 1. The reference paper's code and preprocessed connectome (required, ~190 MB)
git clone https://github.com/philshiu/Drosophila_brain_model data/reference
git -C data/reference checkout 91bdd1e7dcf193f3e7ca5a8933497fcef63b7960

# 2. Neuron labels: downloaded automatically (checksum-pinned) the first
#    time the loader runs, into data/flywire/.
.venv\Scripts\python.exe -c "from sim.connectome import load_connectome; load_connectome('783'); load_connectome('630')"
```

Optional, only for the cross-check script
`experiments/phase2/crosscheck_zenodo.py`: download
`proofread_connections_783.feather` (852 MB) from the Zenodo record below into
`data/flywire/` (`proofread_root_ids_783.npy` is fetched automatically).

## Run the tests

```powershell
.venv\Scripts\python.exe -m pytest -m "not slow"   # quick checks, seconds
.venv\Scripts\python.exe -m pytest -m slow         # loads the whole brain
```

Tests marked `slow` need the data above. Judge a run by pytest's last summary
line (for example `20 passed, 7 deselected`).

## Load the brain in code

```python
from sim.connectome import load_connectome
brain = load_connectome()          # FlyWire release 783 (default)
paper = load_connectome("630")     # release 630, the one the paper used
brain.by_cell_type("APL")          # look up neurons by cell type
M = brain.matrix("reference")      # sparse matrix: M[sender, receiver] = signed synapse count
```

The first load takes 5 to 13 s and writes a cache to `data/cache/`; later loads
take about half a second. Summary numbers:
`.venv\Scripts\python.exe experiments\phase2\summary.py`.

## Data sources

All sources below are downloadable without an account.

| Data | Version | Where | Used for |
|---|---|---|---|
| Preprocessed connectome (neuron list + connection list with synapse counts and signs), FlyWire releases 630 and 783 | GitHub commit `91bdd1e7dc` (2024-09-14) | https://github.com/philshiu/Drosophila_brain_model (files `Connectivity_783.parquet`, `Completeness_783.csv`, `2023_03_23_connectivity_630_final.parquet`, `2023_03_23_completeness_630_final.csv`) | The wiring the simulator uses |
| Neuron annotations for release 783 (cell type, class, predicted neurotransmitter, soma and anchor positions) | flywire_annotations tag `v3.1.0`, commit `8587524c17`; SHA-256 `9a4f8b2f...81d1be` | https://raw.githubusercontent.com/flyconnectome/flywire_annotations/8587524c1748ce5ef2080822a2fc890fc03bf597/supplemental_files/Supplemental_file1_neuron_annotations.tsv | Labels, search, 3D positions |
| Neuron annotations for release 630 | flywire_annotations tag `v1.1.0`, commit `df6bb136f5`; SHA-256 `55c99c61...2e2e76` | https://raw.githubusercontent.com/flyconnectome/flywire_annotations/df6bb136f5b3d91c3992df4e8de2642329e2a384/supplemental_files/Supplemental_file1_annotations.tsv | Labels for the paper's release |
| Official FlyWire release 783 connectivity (`proofread_root_ids_783.npy`, `proofread_connections_783.feather`) | Zenodo v783.0 (2024-06-02) | https://doi.org/10.5281/zenodo.10676866 | Cross-checks only |

Codex (https://codex.flywire.ai) serves the same release-783 data but needs a
Google sign-in; this project does not use it.

## License terms

- **FlyWire data** (everything under `data/`, including the reference repo's
  preprocessed tables, which are derived from FlyWire): FlyWire's own
  guidelines (https://flywire.ai) state the public release data is licensed
  **CC BY-NC 4.0**: you must credit the sources below and **may not use it
  commercially**. The Zenodo deposit is labelled CC BY 4.0, which is less
  strict; this project follows the stricter CC BY-NC 4.0 terms for all
  FlyWire-derived data. (This is our reading of the terms, not legal advice.)
- **Reference model code** (Shiu & Spiller, `data/reference/model.py` etc.):
  MIT License, Copyright (c) 2023 Philip Shiu and Nico Spiller. Any code copied
  from it must keep that copyright and permission notice.
- **flywire_annotations** repository: no license file; its README asks users
  to cite the papers listed under "Annotations" below.
- The papers themselves are open access under CC BY 4.0.

## Citations

Please cite these when using this project or its results.

FlyWire connectome (FlyWire asks that both be cited whenever the resource is
used):

1. Dorkenwald, S. et al. Neuronal wiring diagram of an adult brain. *Nature*
   **634**, 124-138 (2024). https://doi.org/10.1038/s41586-024-07558-y
2. Schlegel, P. et al. Whole-brain annotation and multi-connectome cell typing
   of *Drosophila*. *Nature* **634**, 139-152 (2024).
   https://doi.org/10.1038/s41586-024-07686-5

Neurotransmitter predictions (used for excitatory/inhibitory signs):

3. Eckstein, N. et al. Neurotransmitter classification from electron
   microscopy images at synaptic sites in *Drosophila melanogaster*. *Cell*
   **187**, 2574-2594.e23 (2024). https://doi.org/10.1016/j.cell.2024.03.016

Reference model (and its preprocessed data files):

4. Shiu, P. K. et al. A *Drosophila* computational brain model reveals
   sensorimotor processing. *Nature* **634**, 210-219 (2024).
   https://doi.org/10.1038/s41586-024-07763-9
5. Shiu, P. K. & Spiller, N. Drosophila_brain_model (code and data, MIT
   License), commit 91bdd1e7dc. https://github.com/philshiu/Drosophila_brain_model.
   Model output archive: https://doi.org/10.17617/3.CZODIW

Annotations (flywire_annotations v3.x asks for these in addition to 1 and 2):

6. Matsliah, A. et al. Neuronal parts list and wiring diagram for a visual
   system. *Nature* **634**, 166-180 (2024).
   https://doi.org/10.1038/s41586-024-07981-1
7. Berg, S. et al. Sexual dimorphism in the complete connectome of the
   *Drosophila* male central nervous system. *bioRxiv* (2025).
   https://doi.org/10.1101/2025.10.09.680999

Underlying data products that FlyWire credits (electron microscopy volume,
synapse detection):

8. Zheng, Z. et al. A complete electron microscopy volume of the brain of adult
   *Drosophila melanogaster*. *Cell* **174**, 730-743.e22 (2018).
   https://doi.org/10.1016/j.cell.2018.06.019
9. Buhmann, J. et al. Automatic detection of synaptic partners in a
   whole-brain *Drosophila* electron microscopy data set. *Nature Methods*
   **18**, 771-774 (2021). https://doi.org/10.1038/s41592-021-01183-7
10. Heinrich, L. et al. Synaptic cleft segmentation in non-isotropic volume
    electron microscopy of the complete *Drosophila* brain. *MICCAI 2018*,
    Lecture Notes in Computer Science, 317-325 (2018).
    https://doi.org/10.1007/978-3-030-00934-2_36

Simulator:

11. Stimberg, M., Brette, R. & Goodman, D. F. M. Brian 2, an intuitive and
    efficient neural simulator. *eLife* **8**, e47314 (2019).
    https://doi.org/10.7554/eLife.47314

Connectome data: FlyWire Consortium, FlyWire Whole-brain Connectome
Connectivity Data 783, Zenodo (2024). https://doi.org/10.5281/zenodo.10676866
