# Reference notes: Shiu et al. 2024 whole-brain LIF model

Research pass, 2026-09-22. Every number below was read from a primary source (paper,
repo file, data file header, or the authors' published result CSVs) unless it is marked
**UNVERIFIED** or **ESTIMATE**.

Primary sources:
- Paper: Shiu et al., *Nature* 634, 210-219 (2024), doi:10.1038/s41586-024-07763-9,
  open access (full text read via Europe PMC, PMC11446845).
- Code: https://github.com/philshiu/Drosophila_brain_model, `main` at commit
  `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960` (last push 2024-09-14).
- Published model output: Edmond archive doi:10.17617/3.CZODIW (the paper's "Data availability").
  Its 4.5 GB `results.zip` was not downloaded. Individual result CSVs were pulled out of it
  with HTTP byte-range requests, which is where the "published model output" numbers below come from.

---

## 0. Decisions in one screen

| Question | Decision |
|---|---|
| Snapshot for Phase 3 | **FlyWire v630**, using the repo's preprocessed files. Every neuron ID in the paper is a v630 ID. In v783, six of the paper's stimulus and readout IDs are gone (one of them is the second MN9), and so are 64 of the 372 SEZ cell-type IDs (see section 3.4). The paper's ID lists therefore fail against v783. Move to v783 after Phase 3 passes. |
| Compute path | **Brian2 2.10.1 from pip on the existing Python 3.13 venv, with `prefs.codegen.target = "numpy"` set explicitly.** Measured on this machine: about 20-40 s per 1 s simulated trial, about 1.2 GB peak RAM per process. Install MSVC Build Tools only when Phase 5 sweeps need a 10x speedup. |
| Versions to pin | The versions already in `.venv`, which ran the benchmark: Python 3.13.12, brian2 2.10.1, numpy 2.5.3, pandas 3.0.6, pyarrow 25.0.1, Cython 3.1.3 (brian2 2.10.1 requires `cython<3.1.4`), scipy 1.18.1, matplotlib 3.11.2, pytest 9.1.1. Add joblib if trials run in parallel (it is not installed yet). |
| License posture | FlyWire data is **CC BY-NC 4.0** (non-commercial) according to flywire.ai. Shiu's code is **MIT**. Eon's PyTorch port is **GPL-2.0-or-later**, so don't copy it. |

---

## 1. Reference repository

### 1.1 Files (from the GitHub tree API; byte sizes)

| Path | Bytes | What it is |
|---|---:|---|
| `model.py` | 11,900 | The whole model: parameters, `create_model`, `poi`, `silence`, `run_trial`, `run_exp` |
| `utils.py` | 2,176 | `load_exps` (reads result parquet files), `get_rate` (spike counts to Hz mean/sd over trials) |
| `example.ipynb` | 10,282 | Tutorial: sugar activation, 100 Hz variant, silencing top 3 (outputs stripped) |
| `figures.ipynb` | 33,229 | Every simulation behind the paper's figures, with all stimulus ID lists |
| `environment.yml` | 174 | Loose conda environment |
| `environment_full.yml` | 3,445 | Exact conda lockfile used for the paper (Windows build) |
| `2023_03_23_completeness_630_final.csv` | 3,057,611 | v630 neuron list, 127,400 rows |
| `2023_03_23_connectivity_630_final.parquet` | 86,630,944 | v630 connections, 14,687,178 rows |
| `Completeness_783.csv` | 3,327,347 | v783 neuron list, 138,639 rows |
| `Connectivity_783.parquet` | 100,804,642 | v783 connections, 15,091,983 rows |
| `sez_neurons.pickle` | 5,114 | dict of 106 SEZ cell-type names to lists of v630 IDs (372 IDs total), used for Fig. 2 |
| `results/example/*.parquet` | 0.54-0.95 MB each | Output of example.ipynb (sugarR, sugarR_100Hz, 3 silencing runs) |
| `LICENSE`, `Readme.md`, `.gitignore` | small | MIT; `.gitignore` contains only `__pycache__` |

The data files are committed as ordinary git blobs. There is no `.gitattributes` and no Git LFS.
`Connectivity_783.parquet` is 96.1 MiB, just under GitHub's 100 MiB per-file limit. A full
`git clone` pulls about 190 MB because it includes both snapshots.

### 1.2 Versions the authors used

- `environment.yml`: `python=3.10`, `brian2=2.5.1`, `numpy=1.24`, plus unpinned `jupyter`, `ipykernel`,
  `pandas`, `joblib`, `pyarrow`.
- `environment_full.yml` (exact builds; this is a **Windows** conda environment: `pywin32`, `vc=14.2`,
  `vs2015_runtime`, `m2w64-gcc-libs`): python 3.10.11, brian2 2.5.1 (py310hc781a3c_0), numpy 1.22.3,
  pandas 1.4.3, pyarrow 11.0.0, scipy 1.8.1, sympy 1.12, cython 0.29.33, joblib 1.2.0, jinja2 2.11.3.
  It contains **no C++ compiler**. The m2w64 packages are runtime libraries only.
- Notebook metadata: example.ipynb kernel "brian2", Python 3.10.11. figures.ipynb is a Colab notebook,
  Python 3.10.13. `figures.ipynb` runs with `n_proc: 15`.
- The code never sets `prefs.codegen.target` or `set_device`, so it ran in Brian2 **runtime mode with
  target `auto`**: Cython if a compiler works, otherwise numpy. The paper does not say which target
  it got. The README warns that the conda install "may install Brian 2 with limited performance".

### 1.3 Will it break on current Brian2 / Python 3.13?

I tested each idiom on the project venv (brian2 2.10.1, numpy 2.5.3, pandas 3.0.6, Python 3.13.12):

| Idiom from the repo | Result |
|---|---|
| brian2 wheel for cp313 on win_amd64 | Available (2.8.0 was the first release with cp313; 2.10.1 has cp312/cp313/cp314). 2.10.1 requires Python >=3.12, numpy >=2.0 and `cython>=0.29.21,<3.1.4`. |
| Equations, `method='linear'`, `refractory='rfc'`, per-neuron `rfc` | Works |
| Reset `'v = v_rst; w = 0; g = 0 * mV'` | Works. `w` is not a neuron variable, so Brian2 treats `w = 0` as a throwaway temporary. |
| `PoissonInput(target=neu[i], ...)` per neuron, `neu[i].rfc = 0*ms` | Works |
| `syn.w[' {} == i'.format(i)] = 0*mV` (silencing) | Works. It prints a harmless `resolution_conflict` warning when a Python variable named `i` exists in the calling scope. |
| `float(l)` on spike-time Quantities; assigning `len/t_run` (a Hz Quantity) into a numpy array | Works |
| `df.loc[:, 't'] = ....astype(float)` under pandas 3 | Works (column already float). `exp_name` becomes pandas' new string dtype, which is harmless. |
| Default `auto` target, no compiler | Prints "Cannot use Cython, a test compilation failed: Microsoft Visual C++ 14.0 or greater is required", then falls back to numpy. Set `prefs.codegen.target = "numpy"` to skip the failed compile attempt. |

Conclusion: nothing in `model.py` or `utils.py` breaks on the current stack. The problems are
operational and specific to Windows (section 5.4).

Repo inconsistencies to know about:
- The README says silencing zeroes synapses "to and from" a neuron. The code zeroes **outgoing**
  synapses only (`i == idx`). The paper agrees with the code ("eliminating all output of that neuron").
- The example notebook says the default stimulation is 200 Hz. The code default is **150 Hz**
  (`r_poi`). The code is authoritative.
- The code comment calls the synapse "alpha", but it is a single-exponential current (one ODE for `g`).
- The notebooks mutate the shared `default_params` dict in place (`params['r_poi'] = ...`).

---

## 2. Model

### 2.1 Parameters (`model.py` `default_params`, cross-checked against the paper's Methods)

| Symbol (paper) | Code key | Value | Units | Source cited in code or paper |
|---|---|---:|---|---|
| V_resting | `v_0` | -52 | mV | Kakaria & de Bivort 2017 |
| V_reset | `v_rst` | -52 | mV | same |
| V_threshold | `v_th` | -45 | mV | same |
| T_mbr = C_mbr x R_mbr | `t_mbr` | 20 | ms | C_mbr = 2 uF/cm^2, R_mbr = 10 kOhm cm^2 (paper). The code comment says ".002 uF * 10 Mohm". |
| tau (synaptic decay) | `tau` | 5 | ms | Jurgensen et al. 2021 |
| T_refractory | `t_rfc` | 2.2 | ms | Lazar et al. 2021 |
| T_dly (spike to postsynaptic effect) | `t_dly` | 1.8 | ms | Paul et al. 2015. One homogeneous delay for every synapse. |
| W_syn (the one free parameter) | `w_syn` | 0.275 | mV per synapse | Chosen so that sugar GRNs at 100 Hz give about 80% of maximal MN9 firing |
| Poisson rate, set 1 | `r_poi` | 150 (default) | Hz | Figures sweep 10-260 Hz |
| Poisson rate, set 2 | `r_poi2` | 0 (default) | Hz | Second stimulus class (bitter, Ir94e, water) |
| Poisson kick scale | `f_poi` | 250 | (unitless) | Each Poisson event adds `w_syn*f_poi` = **68.75 mV** to `v` |
| Trial duration | `t_run` | 1000 | ms | Paper: "30 simulations of 1,000 ms" |
| Trials per condition | `n_run` | 30 | count | same |
| Time step | (Brian2 default) | 0.1 | ms | Never set in code. Brian2 `defaultclock.dt` = 0.1 ms (confirmed at runtime). |
| Integrator | `method='linear'` | exact | - | Exact solution of the linear ODE system |
| Initial state | - | v = -52 mV, g = 0 | - | `neu.v = params['v_0']; neu.g = 0` |
| Baseline firing | - | 0 Hz | - | No background input and no noise. Inhibition onto a silent neuron does nothing. |
| Random seed | - | none set | - | Trials differ only through Poisson input randomness |
| Network size | - | 127,400 neurons (v630) | - | "All 127,400 proofread neurons from Flywire materialization v.630" |

Stimulated neurons get `rfc = 0 ms` (no refractory period), so every Poisson event
(68.75 mV, far above the 7 mV gap to threshold) becomes exactly one spike. Each stimulated
neuron gets its own `PoissonInput` with `N=1`, so it fires at most once per 0.1 ms step.

### 2.2 Equations and statements, verbatim from `model.py`

Neuron model (`'eqs'`, after `dedent`):
```
dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)
dg/dt = -g / tau               : volt (unless refractory) 
rfc                            : second
```
Threshold (`'eq_th'`):
```
v > v_th
```
Reset (`'eq_rst'`):
```
v = v_rst; w = 0; g = 0 * mV
```
NeuronGroup:
```python
neu = NeuronGroup( # create neurons
    N=len(df_comp),
    model=params['eqs'],
    method='linear',
    threshold=params['eq_th'],
    reset=params['eq_rst'],
    refractory='rfc',
    name='default_neurons',
    namespace=params,
)
```
Synapses, including the `on_pre` statement:
```python
syn = Synapses(neu, neu, 'w : volt', on_pre='g += w', delay=params['t_dly'], name='default_synapses')
```
Weights:
```python
syn.w = df_con.loc[:,'Excitatory x Connectivity'].values * params['w_syn']
```
Poisson stimulation:
```python
p = PoissonInput(
    target=neu[i], 
    target_var='v', 
    N=1, 
    rate=params['r_poi'], 
    weight=params['w_syn']*params['f_poi']
    )
neu[i].rfc = 0 * ms # no refractory period for Poisson targets
```
Silencing:
```python
syn.w[' {} == i'.format(i)] = 0*mV
```
Paper form (Methods): dv_i/dt = (g_i - (v_i - V_resting))/T_mbr; dg_i/dt = -g_i/tau;
g_i <- g_i + w_j,i on each spike from neuron j.

Subtleties that a reimplementation must copy exactly:
1. `(unless refractory)` freezes both `v` and `g` during the 2.2 ms refractory period. `on_pre`
   still runs during that time, so input that arrives while a neuron is refractory **accumulates in
   `g`**. It is not dropped. (Eon's PyTorch port drops it. See 5.3.)
2. Reset zeroes `g`, so any synaptic drive already in flight when the neuron spikes is lost.
3. `g` is in volts. It is the voltage the membrane relaxes toward, above rest. It is not a conductance
   in siemens.
4. The trial result is the spike count divided by 1 s, averaged over 30 trials (`utils.get_rate`). The
   reported sd is across trials.

### 2.3 How weight and sign are derived

- `Connectivity` = number of synapses from pre to post, summed over the whole brain.
  No threshold was applied: the minimum is 1 in both snapshots.
- `Excitatory` = +1 or -1 **per presynaptic neuron**. Paper Methods: synapse-level NT predictions from
  Eckstein et al. 2024 with a cleft score cutoff of 50. Each presynaptic site takes its top NT. If more
  than half of a neuron's presynaptic sites are GABA or glutamate, the whole neuron is inhibitory (-1).
  ACh, dopamine, octopamine and serotonin are all treated as excitatory (+1).
- `Excitatory x Connectivity` = signed synapse count (range -2358..+1801 in v630, -729..+571 in the
  first row group of v783).
- w_j,i = sign(j) x count(j to i) x 0.275 mV. Excitatory and inhibitory synapses have equal magnitude.
- Stated assumptions (paper): glutamate is inhibitory. If glutamate is made excitatory, the bitter and
  Ir94e inhibition results disappear. Robustness checks: W_syn +/-30% and the I:E ratio +/-50% kept
  90-96% of predictions unchanged.
- The repo files carry **only the sign**, not the neurotransmitter name. A per-NT breakdown for
  Phase 2 (ACh, GABA, Glu, DA, 5-HT, OA) needs Codex `neurons.csv.gz` (v783) or the Eckstein
  predictions. From the repo files alone we can only split excitatory from inhibitory. Paper figure
  for the whole volume: about 55% ACh, 24% Glu, 14% GABA, 7% DA/OA/5-HT.

---

## 3. Data files

### 3.1 Files and download URLs

| File | Snapshot | Format | Rows | Bytes | Hosting | Direct URL |
|---|---|---|---:|---:|---|---|
| `2023_03_23_completeness_630_final.csv` | v630 | CSV, LF line endings | 127,400 | 3,057,611 | GitHub (plain git) + Edmond | https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/2023_03_23_completeness_630_final.csv, or https://edmond.mpg.de/api/access/datafile/214095 |
| `2023_03_23_connectivity_630_final.parquet` | v630 | Parquet, brotli, 1 row group (pyarrow 9.0.0) | 14,687,178 | 86,630,944 | GitHub + Edmond | https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/2023_03_23_connectivity_630_final.parquet, or https://edmond.mpg.de/api/access/datafile/214091 |
| `Completeness_783.csv` | v783 | CSV | 138,639 | 3,327,347 | GitHub | https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/Completeness_783.csv |
| `Connectivity_783.parquet` | v783 | Parquet, brotli, 15 row groups (pyarrow 14.0.2) | 15,091,983 | 100,804,642 | GitHub | https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/Connectivity_783.parquet |
| `sez_neurons.pickle` | v630 | Python pickle (dict of lists of int) | 106 types / 372 IDs | 5,114 | GitHub + Edmond (214087) | https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/sez_neurons.pickle |
| `results.zip` (all published model output) | v630 | zip of spike parquets + rate CSVs, 11,172 entries | - | 4,499,610,373 | Edmond only | https://edmond.mpg.de/api/access/datafile/223847 (dataset license MIT) |

Checksum: after download, verify sizes against this table. The pinned commit is `91bdd1e7dc...`.
Download only the two v630 files by raw URL. Cloning the repo is unnecessary.

### 3.2 Columns

Completeness CSV: a blank-named index column holding the FlyWire root ID (int64), plus `Completed`
(all `True` in both snapshots). **Row order is the Brian2 neuron index**: `flyid2i = {id: row}`, and
rows are sorted by ascending ID (verified).

Connectivity parquet (same schema in both snapshots, all int64):

| Column | Meaning | v630 range |
|---|---|---|
| `Presynaptic_ID` | FlyWire root ID of the sender | - |
| `Postsynaptic_ID` | FlyWire root ID of the receiver | - |
| `Presynaptic_Index` | Row in the completeness CSV (Brian2 index) | 0..127399 |
| `Postsynaptic_Index` | same, for the receiver | 0..127399 |
| `Connectivity` | synapse count for this pair | 1..2358 |
| `Excitatory` | sign of the presynaptic neuron | -1 or +1 |
| `Excitatory x Connectivity` | signed count | -2358..+1801 |
| `__index_level_0__` | leftover pandas index, ignore | - |

Reading brotli parquet with pyarrow 25.0.1 works (`pa.Codec.is_available('brotli')` is True).

### 3.3 Other official hosts (not needed for Phase 3)

- Zenodo doi:10.5281/zenodo.10676866, "FlyWire Whole-brain Connectome Connectivity Data", v783.0,
  2024-06-02, license CC-BY-4.0 on Zenodo:
  `proofread_connections_783.feather` (852,022,274 B), `proofread_root_ids_783.npy`
  (1,114,168 B, which is 139,255 IDs), `flywire_synapses_783.feather` (9.49 GB, every synapse with
  per-NT probabilities), `per_neuron_neuropil_count_pre/post_783.feather`.
- Neuron counts differ between sources: 139,255 proofread neurons in v783 (Dorkenwald 2024 and
  Zenodo) versus 138,639 in Shiu's `Completeness_783.csv`. **Why 616 are missing is UNVERIFIED.**
  Shiu's v630 file matches the paper's 127,400.

### 3.4 v630 IDs versus v783 (why Phase 3 uses v630)

FlyWire root IDs change whenever a neuron is edited. Checked against the two completeness CSVs:
106,220 IDs are shared. Missing from v783:
- sugar GRNs (paper's main set): `720575940620900446`
- bitter GRNs: `720575940618600651`
- other-side sugar set: `720575940627961104`
- JON-CE: `720575940626307902`
- the 3 inhibitory neurons in Ext. Data Fig. 4c: `720575940636066222`
- **the second MN9, `720575940645521262`**
- 64 of the 372 SEZ split-GAL4 IDs (Fig. 2)

`run_exp` does `flyid2i[n]` for each ID, so these raise `KeyError` on v783. The main MN9
`720575940660219265`, aDN1, aDN2, aBN1, and every water and Ir94e GRN are present in both.
Eon Systems' v783 benchmark uses a 21-ID sugar list that replaces `...620900446` with
`720575940639259967`. That is presumably the edited successor. **UNVERIFIED**: confirm with
a CAVE/Codex ID lookup before relying on it.

### 3.5 Left/right labels are inverted in the code

Schlegel et al. 2024 (Ext. Data Fig. 1) found that the FAFB image mosaics were stored with the
left-right axis flipped. The paper calls the main 21-neuron sugar set **left**-hemisphere GRNs. The
code comments call the same list "right hemisphere" and call MN9 `...660219265` "left". The data
agree with the paper: `...660219265` is the MN9 **contralateral** to the 21-neuron set and fires more
strongly. **Trust IDs, never side labels.**

---

## 4. Experiments to reproduce

### 4.1 Readout neurons (v630 IDs)

| Name | ID | Notes |
|---|---|---|
| MN9, contralateral to the main sugar/water/bitter sets | `720575940660219265` | Default MN9 in every notebook cell. Present in v783. |
| MN9, ipsilateral | `720575940645521262` | Only in Fig. 1c/Fig. 2 outputs. **Not in v783.** |
| aDN1 | `720575940616185531` | Grooming readout (Fig. 5c,d) |
| aDN2 | `720575940629806974` | Ext. Data Fig. 4a,b |
| aBN1 | `720575940630907434` | Fig. 5g |

### 4.2 Stimulus sets (v630 IDs, copied from `figures.ipynb`)

Cell-type identity (paper): labellar GRNs classified in Engert et al. 2022 (paper ref. 23), then
verified by connectivity clustering (Ext. Data Fig. 1a-c). Sugar = Gr5a/Gr64f-class
("sugar-sensing gustatory receptor neurons"). The Codex cell-type names for these IDs are
**UNVERIFIED** (Codex requires sign-in).

- Sugar GRNs, main set (21). The paper calls them left; the code calls them "right hemisphere":
  `720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345, 720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367, 720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538, 720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919, 720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663, 720575940611875570`
- Sugar GRNs, other side (10), for Ext. Data Fig. 1d (code: `neu_sugar_left`):
  `720575940620589838, 720575940631147148, 720575940608305161, 720575940629388135, 720575940630968335, 720575940606801282, 720575940617398502, 720575940616167218, 720575940620296641, 720575940627961104`
- Water GRNs (18):
  `720575940612950568, 720575940631898285, 720575940606002609, 720575940612579053, 720575940622902535, 720575940616177458, 720575940660292225, 720575940622486922, 720575940613786774, 720575940629852866, 720575940625861168, 720575940613996959, 720575940617857694, 720575940644965399, 720575940625203504, 720575940630553415, 720575940635172191, 720575940634796536`
- Bitter GRNs (21):
  `720575940621778381, 720575940602353632, 720575940617094208, 720575940619197093, 720575940626287336, 720575940618600651, 720575940627692048, 720575940630195909, 720575940646212996, 720575940610483162, 720575940645743412, 720575940627578156, 720575940622298631, 720575940621008895, 720575940629146711, 720575940610259370, 720575940610481370, 720575940619028208, 720575940614281266, 720575940613061118, 720575940604027168`
- Ir94e GRNs (18):
  `720575940614211295, 720575940638218173, 720575940628832256, 720575940626016017, 720575940621375231, 720575940612920386, 720575940614273292, 720575940628198503, 720575940626241636, 720575940619387814, 720575940624604560, 720575940615274425, 720575940610683315, 720575940627265265, 720575940624079544, 720575940629211607, 720575940615089369, 720575940631082124`
- JONs: 70 JO-CE + 60 JO-F + 16 JO-D/m = 146 IDs in `figures.ipynb` (Figure 5 cell). The paper
  text says 147. That discrepancy is **UNVERIFIED**.
- Three inhibitory neurons (Ext. Data Fig. 4c): `720575940636066222, 720575940609957315, 720575940624986407`

### 4.3 Numbers to match side by side

"Published output" = mean over 30 trials (+/- sd where given), read from the authors' own result
CSVs inside Edmond `results.zip`. MN9 always means `...660219265` unless stated. The figure
numbers are the Nature ones. The code's `fig_3a` and `fig_3b` are Nature Fig. 3b and 3c.

| # | Stimulated set | Readout | Stim rate(s) | Published output / paper claim | Direction to reproduce | Figure | Result file in results.zip |
|---|---|---|---|---|---|---|---|
| 1 | Sugar 21 | MN9 contra | 10 / 20 / 30 / 40 / 50 Hz | 0.0 / 0.0 / 0.3 / 4.8 / 19.4 +/- 6.5 Hz | onset between 30 and 40 Hz | Fig. 1c,d | figure_1/fig_1d_rate.csv |
| 2 | Sugar 21 | MN9 contra | 100 Hz | **65.7 +/- 3.3 Hz**. Paper: MN9 active in 100% of simulations; W_syn tuned so 100 Hz gives about 80% of max | up | Fig. 1c,d | same |
| 3 | Sugar 21 | MN9 contra | 150 Hz (code default) | 83.7 +/- 5.1 Hz | up | Fig. 1d | same |
| 4 | Sugar 21 | MN9 contra | 200 Hz | **93.2 +/- 5.2 Hz** | monotonic rise with rate | Fig. 1d | same |
| 5 | Sugar 21 | MN9 ipsi (`...645521262`) | 100 / 200 Hz | 49.7 +/- 4.4 / 62.9 +/- 3.6 Hz | contra > ipsi | Fig. 1c | same |
| 6 | Sugar 21 | count of neurons firing >0 Hz | 10 / 100 / 200 Hz | 45 / 410 / 455 (paper text says 45 and 455; the CSV agrees) | network grows with rate | Fig. 1d, Supp. Table 1 | same |
| 7 | Sugar other side 10 | MN9 `...645521262` vs `...660219265` | 100 / 200 Hz | 6.8 vs 8.9 / 50.8 vs 38.1 Hz | contra > ipsi at >=140 Hz (reversed at 80-120 Hz in their own data) | Ext. Data Fig. 1d | figure_s1/fig_s1d_rate.csv |
| 8 | Sugar 21 + silence one neuron | MN9 | 50-120 Hz | 47 neurons both sugar-responsive and sufficient for MN9; 14 of those also required (silencing drops MN9 to <=80%) | per-neuron | Fig. 1e-h | fig_1e_*, fig_1f_* |
| 9 | Water 18 | MN9 contra | 120 / 140 / 160 Hz | 0.1 / 3.4 / 10.0 +/- 3.2 Hz | onset about 130 Hz, much later than sugar | Fig. 4a | figure_4/fig_4a_rate.csv |
| 10 | Water 18 | MN9 contra | 200 / 260 Hz | **30.7 +/- 5.4 / 50.3 +/- 5.1 Hz** (ipsi: 13.0 / 23.4) | up | Fig. 4a | same |
| 11 | Water 18 | top-200 sufficiency/necessity | 25-200 / 160-220 Hz | 39 water-responsive neurons sufficient for MN9 (30 also sugar-driven); 9 both necessary and sufficient | - | Fig. 4b,c; Ext. Data 2d,e | fig_4b_*, fig_4c_* |
| 12 | Bitter 21 alone | MN9 | 20-200 Hz | 0.0 at every rate | no activation | Fig. 3b (first row) | figure_3/fig_3a_rate.csv |
| 13 | Sugar 100 Hz + bitter | MN9 | bitter 0 / 40 / 80 / 120 / 200 Hz | 67.0 / 45.3 / 11.7 / 1.5 / 0.0 Hz | **bitter suppresses MN9** | Fig. 3b | same |
| 14 | Sugar 200 Hz + bitter 200 Hz | MN9 | - | 11.2 Hz (sugar alone 94.9) | strong bitter nearly abolishes strong sugar | Fig. 3b | same |
| 15 | Sugar + Ir94e 18 | MN9 | sugar 100 / 200 Hz with Ir94e 200 Hz | 2.5 / **64.3 Hz** (sugar alone 67.6 / 93.1) | Ir94e inhibits but does **not** abolish strong sugar | Fig. 3c | figure_3/fig_3b_rate.csv |
| 16 | Sugar + water | MN9 | sugar 40 Hz + water 200 Hz | 61.2 Hz (sugar alone 6.3, water alone 30.9) | additive or synergistic | Fig. 4e | figure_4/fig_4e_rate.csv |
| 17 | Sugar / water / bitter / Ir94e at the MN9-40 Hz operating point | active-neuron sets | - | sugar 377, water 391, 250 shared; sugar and bitter share 2; sugar and Ir94e share 30 | appetitive vs aversive segregation | Fig. 3f | **not recomputed (UNVERIFIED by us)** |
| 18 | 106 SEZ cell types (sez_neurons.pickle), each alone | MN9 | 50 Hz | Paper: 11 predicted to activate MN9, 10 of those confirmed optogenetically. In the CSV, MN9 contra > 0 for Roundup 79.5, Bract 33.7, Diatom 29.1, Fdg 22.5, Sink_sync 22.2, G2N-1 12.4, Clavicle 10.5, Kitty 7.3, Rattle 1.9, FMIn 0.4 Hz. TH_VUM drives only ipsi MN9 (2.5). Peacock and Peahen are >0 but <0.05. The paper's exact criterion for "11" is **UNVERIFIED**. | - | Fig. 2a-c | figure_2/fig_2_50_hz_rate.csv |
| 19 | JO-CE 70 | aBN1 | 100 / 220 Hz | 25.4 / 73.1 Hz | robust | Fig. 5g | figure_5/data/fig_5g_JON_CE_rate.csv |
| 20 | JO-F 60 | aBN1 | 100 / 220 Hz | 0.9 / 4.6 Hz | weak despite 78 direct synapses | Fig. 5g | fig_5g_JON_F_rate.csv |
| 21 | JO-F 60 + silence the 3 inhibitory | aBN1 | 100 / 220 Hz | 22.4 / 66.4 Hz | un-silencing restores aBN1 | Ext. Data Fig. 4c | figure_s5/fig_s5c_JON_F_silenced_rate.csv |
| 22 | All JONs | aDN1 | 25-200 Hz (single-neuron activation), 140 Hz (silencing) | Only aBN1, aDN2 and 2 weak (<2 Hz) neurons drive aDN1. Only aBN1, a descending BN2 and aDN2 cut it by >20%. | - | Fig. 5c-f | fig_5c_*, fig_5d_* |
| 23 | Whole paper | - | - | 91% of 164 testable predictions matched experiment (84% excluding Fig. 2) | - | Supp. Tables 9-10 | - |
| 24 | Sugar 100 Hz, weights shuffled | MN9 | 100 Hz | MN9 active in 1 of 100 shuffled networks vs 100% with the real connectome | the connectome matters | Supp. Table 1d | **UNVERIFIED by us** |

Phase 3 pass criterion (from PLAN.md): same direction for rows 2, 4, 5, 10, 12, 13, 15. Rates
within about 1-2 sd are a bonus, not a requirement. Our numbers will not match exactly because every
trial draws its own Poisson input.

The rest of the Edmond archive is also available by byte range: 160 small CSVs and pickles plus
11,012 spike parquets. `results/example/*.parquet` in the GitHub repo is the only output that
does not need that trick.

---

## 5. Compute

### 5.1 Their setup

- Paper Methods: "Simulation of sugar neuron activation takes approximately 5 min per 1,000 ms trial
  per central processing unit thread." `figures.ipynb` runs 15 processes in parallel (joblib `loky`).
  The example notebook says a 30-trial run takes "roughly 20 minutes" on Colab.
- Codegen target: **not stated**. Runtime mode, `auto` target (section 1.2). Their locked environment
  is a Windows conda env without MSVC, which suggests they got the numpy fallback. **UNVERIFIED
  inference.**
- Each trial re-reads the neuron CSV and the 86 MB parquet and rebuilds the whole network
  (`run_trial` calls `create_model`), so the 5 min includes rebuild time.

### 5.2 Measured on this machine (2026-09-22)

Machine: i3-1215U (2 P-cores + 4 E-cores, 8 threads), 11.7 GB RAM (3.9 GB free during the test),
no MSVC. Throwaway script in the session scratchpad, not in the project. Synthetic network of the
**same size as v630**: 127,400 neurons, 14,687,178 random connections, the exact equations and
parameters from section 2, target `numpy`, dt 0.1 ms, 1 s of simulated time.

| Load | Wall time for 1 s simulated | Build (connect + weights) | Peak RAM |
|---|---:|---:|---:|
| 21 driven neurons at 150 Hz (3,066 spikes) | 21.3 s | about 1 s | 1.17 GB |
| 110 driven neurons at 150 Hz (16,268 spikes, 144 active) | 39.7 s | about 1 s | 1.17 GB |

The second row roughly matches the real sugar 200 Hz spike load: Eon measured 16,567 spikes and
380 active neurons in 1 s on v783. Random wiring does not reproduce real hub fan-out, so budget
**about 25-60 s per real trial (ESTIMATE)**. That makes a 30-trial condition about 15-25 min
serial, or about 6-10 min with 3 worker processes.

Reference points for compiled code (Eon Systems `fly-brain`, `data/results/nature_2026_07`,
Brian2 2.8.0 `cpp_standalone` on Linux under WSL2, sugar 200 Hz, v783): 1 s simulated =
2.9 s simulation + about 3 s setup/build, 6.1 s total. 8 trials of 1 s = 13.6 s total. That is
about **10x faster than the numpy target**. Not measured here.

### 5.3 Options compared

| Option | Works here today | Speed | Setup | Fidelity to the paper | Main risk |
|---|---|---|---|---|---|
| **A. pip Brian2 2.10.1, numpy target** | **Yes, tested** | about 20-40 s per trial | none (already installed) | **Identical**: same equations, same exact `linear` integrator. Only the random streams differ. | Big sweeps are slow |
| B. Install MSVC Build Tools, then Brian2 `cython` runtime or `cpp_standalone` | After a multi-GB install that needs an admin prompt | About 10x faster than A (standalone; Eon's numbers, not measured here) | "Desktop development with C++" / VCTools workload plus the Windows SDK (Brian2 docs) | Identical | Compile caches, rebuilds after parameter changes (standalone), a large installer on a small machine |
| C. conda with a bundled compiler | **No.** The Brian2 install docs say conda installs a C++ compiler automatically only on Linux and macOS. On Windows, Cython still needs Visual Studio Build Tools. The authors' conda env had no compiler either. | Same as A until MSVC is installed | New env pinned to Python 3.10 | Identical | Solves nothing on Windows |
| D. Existing PyTorch port: Eon Systems `eonsystemspbc/fly-brain` `code/run_pytorch.py` (the only serious one; 903 stars; backends Brian2, Brian2CUDA, PyTorch, NEST GPU, GeNN) | Runs on CPU in principle. Built and tested for CUDA on Linux/WSL2; this machine has no NVIDIA GPU. | Dense sparse-matrix multiply over all 15M synapses every 0.1 ms step. **Likely slower on CPU than Brian2's event-driven delivery (UNVERIFIED)** | torch install | **Not identical** (read from its source): forward-Euler instead of exact integration. During refractory, arriving synaptic input is multiplied by 0 (Brian2 accumulates it in `g`), `g` keeps decaying (Brian2 freezes it), and `v` is not clamped. Validated only statistically against Brian2 (Jaccard overlap and rate correlation). | **GPL-2.0-or-later**: copying it makes our code GPL |
| E. Other ports | `Kisame76/drosophila-brain-mlx` is Apple Silicon only. Many 2026 browser/WebGPU/Rust hobby ports (see `cobanov/awesome-fly`) are unvalidated. Shiu's repo has one branch and ships no PyTorch version. | - | - | - | - |

### 5.4 Recommendation

**Use option A: Brian2 2.10.1 from pip on the existing Python 3.13 venv, with
`prefs.codegen.target = "numpy"` set explicitly.** Reasons:
1. It already runs on this machine, at full brain scale, with no installs and 1.2 GB per process.
2. It runs the reference model's exact math through the same simulator the paper used, so any Phase 3
   mismatch is our bug and not a porting artifact. Swapping the codegen target later cannot change
   results beyond Poisson randomness.
3. Phase 3 needs a few dozen 30-trial conditions (rows 1-16 above): hours at most. Timings are
   ESTIMATES from section 5.2.
4. Options C and D either don't solve the Windows compiler problem or change the model (and D's license).

Re-evaluate at Phase 5. Silencing screens are large: the paper's Fig. 1f alone is
200 neurons x 8 rates x 30 trials = 48,000 trials, about 300+ hours on numpy. **At that point
install MSVC Build Tools and switch to `cpp_standalone`.** Until then, cut trials for exploration
(10 instead of 30) and keep 30 for anything reported.

Adapting the reference runner for this machine (design notes, not code):
- Build the network **once per worker process** and reuse it across trials with
  `net.store()` / `net.restore()`. By default the random state is not restored, so each trial still
  gets fresh Poisson input. Do not re-read the parquet for every trial.
- Read only the needed parquet columns (`Presynaptic_Index`, `Postsynaptic_Index`,
  `Excitatory x Connectivity`). All 8 int64 columns take about 0.94 GB in pandas.
- **Cap parallel workers at 2-3.** The reference default `n_proc=-1` means 8 workers, each around
  1.5-2 GB. That exceeds this machine's RAM and will page or crash.

### 5.5 Things that will bite us on Windows

1. Bare `python` is the Microsoft Store stub on this machine: it printed "Python was not found".
   Always call the project's own `.venv\Scripts\python.exe` (from the repository root).
2. No compiler means `auto` target wastes a failed Cython test compile and prints warnings on every
   fresh process. Set the numpy target explicitly.
3. `n_proc=-1` plus per-trial reloads will exhaust 11.7 GB of RAM (section 5.4).
4. 18-digit root IDs must stay int64. The authors' own `fig_3a_rate.csv` header holds MN9 as the float
   `7.205759406602193e+17`, which has lost digits. Never open the ID files in Excel.
5. `git clone` on Windows with `core.autocrlf=true` rewrites the CSVs to CRLF. Eon's copies are
   exactly 1 byte per line bigger. pandas doesn't care, but file sizes and checksums will stop
   matching. Download by raw URL instead of cloning.
6. Paper ID lists against v783 fail with `KeyError` (section 3.4).
7. Side labels in the code are mirrored relative to the paper (section 3.5).

---

## 6. License and citations

### 6.1 Licenses

- **FlyWire data**: flywire.ai/guidelines says "FlyWire's public release data is made available under
  license **CC BY-NC 4.0**". v783 is the latest public release (October 2023 snapshot). The Zenodo
  connectivity deposit (10.5281/zenodo.10676866) is labeled **CC-BY-4.0**. The official page is
  stricter, so **treat all FlyWire-derived data (v630 and v783) as CC BY-NC 4.0**: attribution
  required and **no commercial use**. The preprocessed tables in Shiu's repo are derived FlyWire data,
  so the repo's MIT license covers the code, not the data's terms (**my interpretation, not legal
  advice**).
- **Shiu repo code**: MIT License, "Copyright (c) 2023 Philip Shiu and Nico Spiller". The Edmond
  archive is also tagged MIT. MIT requires keeping the copyright and permission notice in any copy
  or substantial portion. If we copy `model.py` logic verbatim, include that notice.
- **Paper text and figures**: CC BY 4.0 (Nature open access).
- **Eon `fly-brain`**: GPL-2.0-or-later. Its bundled copy of Shiu's code stays MIT.

### 6.2 What FlyWire requires us to cite

Their citation sheet, linked from flywire.ai/guidelines, says: "When using the FlyWire resource,
please co-cite the Dorkenwald et al. and Schlegel et al. manuscripts". It adds per-data-type
credits. For what we use (reconstruction, synapses and connectivity, neurotransmitter
predictions), that means Dorkenwald, Schlegel, Zheng 2018, Buhmann 2021, Heinrich 2018 and
Eckstein 2024. Add Matsliah 2024 if we use optic-lobe cell types.

### 6.3 Citation strings for the README

1. Dorkenwald, S. et al. Neuronal wiring diagram of an adult brain. *Nature* **634**, 124-138 (2024). https://doi.org/10.1038/s41586-024-07558-y
2. Schlegel, P. et al. Whole-brain annotation and multi-connectome cell typing of *Drosophila*. *Nature* **634**, 139-152 (2024). https://doi.org/10.1038/s41586-024-07686-5
3. Eckstein, N. et al. Neurotransmitter classification from electron microscopy images at synaptic sites in *Drosophila melanogaster*. *Cell* **187**, 2574-2594.e23 (2024). https://doi.org/10.1016/j.cell.2024.03.016
4. Shiu, P. K. et al. A *Drosophila* computational brain model reveals sensorimotor processing. *Nature* **634**, 210-219 (2024). https://doi.org/10.1038/s41586-024-07763-9
5. Zheng, Z. et al. A complete electron microscopy volume of the brain of adult *Drosophila melanogaster*. *Cell* **174**, 730-743.e22 (2018). https://doi.org/10.1016/j.cell.2018.06.019
6. Buhmann, J. et al. Automatic detection of synaptic partners in a whole-brain *Drosophila* electron microscopy data set. *Nature Methods* **18**, 771-774 (2021). https://doi.org/10.1038/s41592-021-01183-7
7. Heinrich, L. et al. Synaptic cleft segmentation in non-isotropic volume electron microscopy of the complete *Drosophila* brain. In *MICCAI 2018*, Lecture Notes in Computer Science, 317-325 (Springer, 2018). https://doi.org/10.1007/978-3-030-00934-2_36
8. Code and data: Shiu, P. K. & Spiller, N. Drosophila_brain_model (GitHub, MIT License), commit 91bdd1e7dc, https://github.com/philshiu/Drosophila_brain_model. Model output archive: https://doi.org/10.17617/3.CZODIW
9. Simulator: Stimberg, M., Brette, R. & Goodman, D. F. M. Brian 2, an intuitive and efficient neural simulator. *eLife* **8**, e47314 (2019). https://doi.org/10.7554/eLife.47314 (the paper's ref. 22; checked against Crossref)
10. Optional, only if we use their cell-type annotations for the optic lobe: Matsliah, A. et al. Neuronal parts list and wiring diagram for a visual system. *Nature* **634**, 166-180 (2024). https://doi.org/10.1038/s41586-024-07981-1

---

## 7. Codex (if we skip the preprocessed files)

- **Account: yes.** Codex's FAQ says the interactive apps "require Google sign-in". Bulk files come
  from `https://codex.flywire.ai/api/download?dataset=fafb` and are fetched with
  `https://codex.flywire.ai/api/download_resource?data_product=...&dataset=fafb&api_token=...`,
  using a Codex API token copied from the Account page. A CAVE/FlyWire token is only needed for live
  operations such as root-ID remapping. Codex serves only the current public release (v783), not v630.
- Files we would need. Names are from Codex's own loader code (`murthylab/codex`,
  `codex/data/local_data_loader.py`); I could not see the download portal itself without signing in:
  - `neurons.csv.gz`: `root_id`, `group`, `nt_type`, `nt_type_score`, `ach_avg`, `gaba_avg`,
    `glut_avg`, `ser_avg`, `oct_avg`, `da_avg`. Neuron list plus per-neuron NT prediction, which
    replaces the sign column and gives the NT breakdown.
  - `connections.csv.gz`: columns in order `pre_root_id, post_root_id, neuropil, syn_count, nt_type`.
    **Caveat:** there is one row per pair **per neuropil**, and Codex's FAFB default is a **5-synapse
    minimum** (FAQ). The Codex home page shows 3,732,460 thresholded connections for 139,255 neurons,
    versus 15,091,983 unthresholded pairs in Shiu's v783 file. To match Shiu we would need the
    unthresholded product, summed over neuropils. Codex offering an unthresholded file is
    **UNVERIFIED**. The Zenodo `proofread_connections_783.feather` (852 MB) is an alternative.
  - `classification.csv.gz` (flow, super_class, class, sub_class, cell_type, side, ...) and
    `consolidated_cell_types.csv.gz`, for searching by cell type in the app.
  - `coordinates.csv.gz` (optional, for the Phase 4 3D view), plus `labels.csv.gz` and
    `cell_stats.csv.gz` (optional).
- To rebuild Shiu's sign rule from Codex, use `nt_type` with GABA or GLUT as inhibitory and
  everything else excitatory. That is close to, **but not provably identical to**, Shiu's rule of
  "more than half of presynaptic sites inhibitory at cleft score 50" (section 2.3).
