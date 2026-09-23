# Phase 9 research: giving the brain a body

Prepared 2026-09-22, ahead of Phase 9. Anything marked **UNVERIFIED** was not confirmed in
this pass. Version numbers come from PyPI, GitHub or the project pages on the date above.
The FlyGym results in section 2.2 come from a real install and run on this machine.

---

## 1. The short version

- **Recommendation: start with FlyGym 2.1.0 (NeuroMechFly, EPFL).**
  - It is the only body model that installed and ran on our exact setup: Windows 11,
    Python 3.13, no C compiler, no GPU. I test-installed it in a throwaway environment and
    ran a walking/turning example. It worked.
  - The packages it needs (numpy 2.5.3, scipy 1.18.1, matplotlib 3.11.2, numba 0.67.0)
    are the same versions already pinned in our `requirements.txt`. Adding it to the
    project should only add new packages (mujoco 3.9.0 and a few small helpers).
    **UNVERIFIED** until it is actually installed into `.venv`.
- **Big catch:** FlyGym 2.x is a rewrite and dropped the smell (olfaction) module.
  - Vision still works.
  - The old smell features live on in `flygym-gymnasium` (1.x), which does not support
    Python 3.13.
  - Smell is easy to add back ourselves: compute odor strength at the antenna positions
    with the same formula FlyGym 1.x used, intensity ∝ 1 / distance².
- **flybody (Janelia / DeepMind)** cannot be installed on Python 3.13 in its own right. It
  pins numpy 1.26.4, which has no Python 3.13 build. It is tested only on Linux with
  Python 3.10–3.12. However, FlyGym 2.1.0 includes a `FlyBody` class that loads the
  flybody body model, so we can still reach that body later through FlyGym (not tested).
- **Nerve cord wiring exists and is public**, but a brain→leg-muscle connectome path is
  still research-grade. Each dataset is described in section 3.
  - **MANC:** male nerve cord. v1.2, about 23,000 neurons, CC-BY.
  - **MaleCNS v1.0:** the whole male central nervous system, June 2026.
  - **BANC:** female brain + nerve cord in one animal. Nature 2026.
  - **Name matching:** brain descending neurons (DNs) in our FlyWire data are matched by
    type name to nerve-cord DNs (Stürner et al. 2025).
  - **The catch:** DNs rarely connect directly to motor neurons (Cheong et al.), so a
    nerve-cord simulation would be needed in between.
- **First closed-loop demo recommended: walking toward an attractive odor.**
  1. Odor at the left and right antennae drives left and right ORNs in the brain model.
  2. We read left/right steering descending neurons (DNa02, DNa01) and a walking
     command neuron (DNg100).
  3. Those set FlyGym's two-number "descending drive" (left, right) for its built-in
     walking controller.
  4. The leg control itself stays FlyGym's controller and must be labelled
     "not brain-driven".
  - Pass criteria: the fly gets to the odor more often than with the odor off, and stops
    doing so when DNa02 (or the stimulated ORNs) are silenced.

---

## 2. Body models

### 2.1 Comparison table

| | FlyGym 2.1.0 (NeuroMechFly) | flygym-gymnasium 1.3.2 (old FlyGym 1.x API) | flybody |
|---|---|---|---|
| Who | EPFL (Ramdya lab) | EPFL | Janelia (Turaga lab) + Google DeepMind |
| Latest release | 2.1.0 on PyPI, 2026-06-24 (2.0.0 was 2026-04-01) | 1.3.2 on PyPI, 2026-04-01 | v0.1.0 tag, 2024-05-16; last commit 2025-07-30. Not on PyPI. |
| Python | ≥3.12, <3.15 (3.13 OK) | ≥3.10, **<3.13** | CI tests 3.10–3.12 only; docs use conda `python=3.10` |
| MuJoCo | `mujoco>=3.9,<3.10` (3.9.0 installed) | pins `mujoco==3.2.7`, `dm_control==1.0.27` | via `dm_control` (latest dm_control needs `mujoco>=3.14`) |
| Install | `pip install flygym` (pure-Python wheel; all dependencies have Windows/Python 3.13 wheels) | `pip install flygym-gymnasium`. It fails on 3.13: `numba==0.60.0` and `dm_tree==0.1.8` have no Python 3.13 Windows wheels. Would need a separate Python 3.12 environment. **Not tested.** | `pip install git+https://github.com/TuragaLab/flybody.git`. Pins `numpy==1.26.4`, which has no Python 3.13 wheel, so pip would try to compile numpy and fail without a C compiler. **Expected, not tested.** |
| Windows | **Works: tested, see 2.2** | Unknown | Not documented; Linux (`MUJOCO_GL=egl`) instructions only. **UNVERIFIED.** |
| GPU needed? | No. Optional GPU speed-up via Warp / MJWarp. | No | No for the body. ML training extras use TensorFlow/CUDA. |
| Vision | Yes: compound eyes, 721 ommatidia per eye, yellow/pale channels | Yes | Yes (eye cameras used for vision-guided flight tasks) |
| Smell | **No** (no odor code anywhere in the 2.1.0 package) | Yes: `OdorArena`, odor at 2 antennae + 2 palps; plume-tracking examples | No |
| Touch / taste | Ground-contact info and per-body-segment contact forces; no taste model | Contact sensors; no taste model | Contact / adhesion; no taste model |
| Control inputs | Joint position targets (42 actuated leg DoFs in the walking fly), tendon actuators (musculoskeletal variant), leg adhesion on/off. Demo controllers in `flygym_demo`: CPG, rule-based, hybrid, and **hybrid turning controller driven by a 2-number descending signal [left, right]** | Same controllers, plus the 2-number descending drive | Neural-network controllers trained by reinforcement learning (walking action has 59 numbers); high-level steering commands |
| Bodies available | NeuroMechFly, musculoskeletal variant, **flybody body (`FlyBody` class)** | NeuroMechFly | flybody |
| Papers | Wang-Chen et al. 2024, *Nat Methods* (NeuroMechFly v2), doi:10.1038/s41592-024-02497-y | same | Vaxenburg et al. 2025, *Nature*, doi:10.1038/s41586-025-09029-4 |

FlyGym 2.x README (quoted): "This version is not backward compatible, and not all features
from FlyGym 1.x.x are available." It claims about a 10x CPU speed-up over 1.x. The
NeuroMechFly v2 paper's smell and plume work used the 1.x API.

### 2.2 What happened when I installed and ran FlyGym here

- **Install.** A throwaway venv in the scratchpad (deleted afterwards), Python 3.13.12
  (Windows 11 10.0.26200). `pip install flygym==2.1.0` finished with exit code 0 and no
  compiler errors. It pulled in mujoco 3.9.0, numba 0.67.0, numpy 2.5.3, scipy 1.18.1 and
  matplotlib 3.11.2. It also installed a second package, `flygym_demo`, which holds the
  walking controllers used in the tutorials.
- **Run 1: walking and turning (headless).** Adapted from the official tutorial "4d.
  Turning locomotion controller". Each run is 0.5 s of fly time with the hybrid turning
  controller.
  - Import took 39 s (first-time compilation).
  - Drive [1.0, 1.0] (straight): moved 5.81 mm forward, 1.74 mm sideways. Wall time 24.7 s.
  - Drive [1.2, 0.4]: moved 3.26 mm forward, −2.56 mm sideways (veered right). 24.2 s.
  - Drive [0.4, 1.2]: moved 2.27 mm forward, +4.20 mm sideways (veered left). 25.4 s.
  - **Meaning:** lowering one side's number makes the fly turn toward that side (fly faces
    +x, and +y is its left). This is the steering "knob" the brain would turn.
  - **Speed:** with the controller in the loop, about 0.02x real time, so 1 s of fly time
    takes about 50 s. The machine was shared with other jobs, so a quiet machine may do
    better.
- **Run 2: raw physics and vision.**
  - Physics alone, with no controller: 0.5 s of fly time in 2.59 s (0.19x real time). The
    controller's Python code, not the physics, is the main cost.
  - Vision works on Windows. `get_ommatidia_readouts` returned an array of shape
    (2 eyes, 721 ommatidia, 2 channels). The first call took 25 s (compilation). After
    that, each call took about 111 ms, so vision should be sampled only every so often,
    not every physics step.
- **Not tested:** the flybody body inside FlyGym, the interactive viewer, video rendering
  to file, and GPU mode.

### 2.3 How to get smell back in FlyGym 2.x

FlyGym 1.x computed odor with a very simple formula. We read it in the flygym-gymnasium
source (`arena/sensory_environment.py`):

- odor sources at fixed points;
- intensity = peak × distance⁻² (the default `diffuse_func = lambda x: x**-2`);
- sampled at 4 sensors: 2 antennae and 2 maxillary palps.

FlyGym 2.1.0 still lets us read the positions of the antenna segments (`pedicel`,
`funiculus` and `arista` exist in its anatomy) through `get_body_positions`. So we can
compute the same numbers ourselves. That is about 20 lines of code and reproduces the
published odor environment. The old odor-taxis example (`simple_odor_taxis.py`) steers
like this: every 50 ms it compares left and right intensity and lowers one side of the
[left, right] descending drive by up to 0.8. **Our brain model would replace exactly that
hand-written step.**

---

## 3. Nerve cord connectomes (the fly's "spinal cord")

| Dataset | What | Status | Size | Access |
|---|---|---|---|---|
| **MANC** (Male Adult Nerve Cord) | Nerve cord of one male | v1.2, released 2024-03-11 (neuPrint shows `manc:v1.2.1`) | "about 23,000 neurons, 10 million pre-synaptic sites, and 74 million post-synaptic densities" (Janelia page) | neuPrint (neuprint.janelia.org). Also a public Google Cloud bucket of flat files, `flyem-manc-exports`. CC-BY. neuPrint's programmatic access uses a personal token from signing in (**UNVERIFIED** for the current site). The bucket needs no account. |
| **MaleCNS** | Whole central nervous system (brain + nerve cord) of one male | v1.0, 2026-06-08 (v0.9 was 2025-10-03). A 2026 *Cell* paper is cited on the site. | About 166,700 neurons (flyconnecto.me summary; not on the dataset page itself) | neuPrint dataset `male-cns:v1.0`; downloads page; CC-BY |
| **BANC** (Brain And Nerve Cord) | Brain + nerve cord of one **female** (same sex as FlyWire) | Published: Bates et al. 2026, *Nature*, "Distributed control circuits across a brain-and-cord connectome", doi:10.1038/s41586-026-10735-w. Data version v888. | Project README: "approximately 188,000 neurons and 199 million predicted synapses". Another summary says 142k neurons, so the numbers disagree. **UNVERIFIED which is current.** | FlyWire Codex (codex.flywire.ai/banc; sign-in probably required, **UNVERIFIED**); Harvard Dataverse doi:10.7910/DVN/7WTH1N (no account); Python package `banc`; CC BY 4.0 |
| **FANC** | Female nerve cord | Partial reconstruction | about 14.6k neurons (flyconnecto.me) | fanc.community |

### 3.1 Matching our brain's descending neurons to the nerve cord

- **Stürner, Brooks et al. 2025.** "Comparative connectomics of Drosophila descending and
  ascending neurons", *Nature* 643:158–172, doi:10.1038/s41586-025-08925-z.
  - Matched all neck-connective neurons across FlyWire (our brain), FANC and MANC, and 51%
    of DN types to genetic driver lines.
  - The tables are in github.com/flyconnectome/2023neckconnective (`Supplemental_files/`).
    `Supplemental_file5_FAFB_DNs.tsv` has 1,315 FlyWire DN rows keyed by 783 `root_id`
    with a `type` column. `Supplemental_file7_MANC_DNs.tsv` has 1,327 MANC DN rows keyed
    by `bodyid` with the same `type` names.
  - Checked: DNa01's FlyWire root ID 720575940644438551 is the same in their file and in
    ours.
- **Our annotation file was also cross-typed against MaleCNS v0.9.** This is
  flywire_annotations 3.x, with a `supertype` column. So FlyWire type names line up with
  MaleCNS names too.
- **Can this map brain DNs to leg motor neurons?** Partly.
  - Cheong et al. (eLife, doi:10.7554/eLife.96084): "direct DN-MN connections are
    infrequent". Most DN signals go through networks of nerve-cord interneurons. So there
    is no simple lookup table from DN to leg muscle. We would need to simulate the nerve
    cord too.
  - **Pugliese et al.** ("Connectome simulations identify a central pattern generator
    circuit for fly walking", bioRxiv doi:10.1101/2025.09.12.675944) did that.
    - They simulated the MANC, FANC, MaleCNS and BANC nerve cords.
    - DNg100 came out as the top driver of rhythmic leg motor activity.
    - A 3-neuron walking rhythm circuit was found in all four datasets.
    - DNb08 drives leg rhythm too, confirmed with optogenetics.
  - Turning motor neuron spikes into FlyGym joint movements is a further, unsolved step.
    FlyGym's musculoskeletal fly has tendon actuators, but a motor-neuron-to-muscle map
    for it was not checked. **UNVERIFIED.**
- **Practical conclusion:** for the first demos, use FlyGym's built-in walking controller
  below the DNs. Label it as not brain-driven. Plan "real nerve-cord wiring drives the
  legs" as a later stage, probably built on BANC, which is female like FlyWire and
  includes the brain.

---

## 4. Brain→body loops that already exist

| Work | What was closed-loop | Relevance |
|---|---|---|
| NeuroMechFly v2 (Wang-Chen et al. 2024, *Nat Methods*) | Vision, smell and ascending feedback in a physics fly. Odor-plume navigation. Fly-following using a **connectome-constrained visual network** (not the whole brain). Brain-level decisions reach the legs through the 2-number descending drive. | The template for our loop and its interface. Peer reviewed. |
| flybody (Vaxenburg et al. 2025, *Nature*) | Walking and flight driven by neural networks trained with reinforcement learning, including vision-guided flight | Body realism. Controllers are not connectome-based. |
| Pugliese et al. (bioRxiv, 2025/2026) | Nerve-cord connectome simulations → leg rhythm | Path to brain-driven legs later |
| Braun et al. 2024, *Nature* (doi:10.1038/s41586-024-07523-9) | Not a body model. Shows "command-like" DNs recruit networks of other DNs. | Warning: reading out one or two DNs is a simplification |
| erojasoficial-byte/fly-brain (Zenodo 2026, not peer reviewed) | Shiu-style LIF brain on FlyWire 783 (same 15,091,983 connections as our parquet) + NeuroMechFly v2 body; hand-written DN→drive "bridge"; GPU/PyTorch | Closest thing to our plan. Useful for ideas, not as validation. |
| Eon Systems (eonsystemspbc/fly-brain; "Virtual Embodied Fly" announcement) | Speed-ups of the Shiu model (Brian2, GPU, neuromorphic); claims an embodied NeuroMechFly demo | Details of the DN mapping were not published on the pages read. **UNVERIFIED.** |
| FlyGM (arXiv 2602.17997, 2026) | Whole-brain connectome used as a graph network, *trained* by reinforcement learning to walk | Not a biophysical model |

No peer-reviewed paper was found in which the full Shiu FlyWire LIF brain drives a physics
body. The search was not exhaustive. **UNVERIFIED.**

---

## 5. Which neurons to use (all present in our reference model)

Root IDs come from `data/flywire/Supplemental_file1_neuron_annotations.tsv` and the
reference notebook `data/reference/example.ipynb`.

| Job | Neuron (FlyWire `cell_type`) | Root IDs | Evidence |
|---|---|---|---|
| Steering, fast and strong | **DNa02** | 720575940629327659 (left), 720575940604737708 (right) | Rayshubskiy et al. 2025, *eLife* (doi:10.7554/eLife.102230): DNa02 "predicts transient high-gain steering". One-sided activation gave "a small average steering bias in the ipsilateral direction". Left and right work as a see-saw. |
| Steering, slow and gentle | **DNa01** | 720575940627787609 (left), 720575940644438551 (right) | Same paper: DNa01 = sustained low-gain steering |
| Forward walking command | **DNg100** (also called BDN2) | 720575940640978048 (left), 720575940647228468 (right) | Pugliese et al.: "a known command neuron for walking", top driver of leg rhythm |
| Forward walking with same-side turning | **DNp09** (= "P9") | 720575940635872101 (left), 720575940627652358 (right) | Bidaye et al. 2020, *Neuron* (doi:10.1016/j.neuron.2020.07.032): "P9 drives forward walking with ipsilateral turning". Caution: FlyWire type `DNp71` also carries `hemibrain_type` DNp09. |
| Backward walking | **MDN** (moonwalker) | 4 cells, `cell_type == "MDN"` | Bidaye et al. 2014, *Science*. Background knowledge, not re-read in this pass. |
| Leg rhythm, second pathway | **DNb08** | 4 cells | Pugliese et al. (confirmed with optogenetics) |
| Proboscis extension | **MN9**: a motor neuron *in the brain*, so no nerve cord needed | 720575940660219265 (from `example.ipynb`; FlyWire `cell_type` CB0701, right side; a left CB0701 also exists) | Shiu et al. 2024 (our Phase 3 read-out) |

Senses available in the brain model:

- **Smell.**
  - 2,282 ORNs in 53 `ORN_*` types, labelled left/right. Antenna: 2,122 via the antennal
    nerve. Palps: 160.
  - Attractive candidates: vinegar-type odors are linked to glomeruli DM1 and VA2
    (Semmelhack & Wang 2009). `ORN_DM1` has 68 cells and `ORN_VA2` 67.
  - Aversive candidates: CO₂ → `ORN_V` (67 cells; Suh et al. 2004); geosmin → `ORN_DA2`
    (39 cells; Stensmyr et al. 2012).
  - These odor→glomerulus links are background knowledge, not re-read in this pass.
    **UNVERIFIED.**
- **Taste.**
  - Mouthpart taste neurons in the brain model: 65 bitter, 129 sugar/water, 19 low-salt.
  - There are also 74 leg taste neurons that ascend into the brain (`sensory_ascending`,
    sub-class `SA_VTV_pro_meso_meta`), but their taste type is **not labelled**.
  - Most leg taste processing happens in the nerve cord, which our model lacks. So
    "turning away from bitter under the feet" is poorly supported by a brain-only model.
    Bitter on the mouthparts is well supported (Shiu's bitter experiments).
- **Vision.** FlyGym supplies 2 × 721 ommatidia values. Mapping these onto FlyWire
  photoreceptor and optic-lobe neurons is a bigger job (the NeuroMechFly v2 paper used the
  separate "flyvis" model). Leave for later.

---

## 6. Recommendation and the minimal first demo

### 6.1 Body model: FlyGym 2.1.0 with the NeuroMechFly body

Why:

- **It runs here.** It is tested on our exact Windows / Python 3.13 / no-GPU setup, and its
  dependencies match our pins.
- **It has the right interface.** Its walking controller already takes a left/right
  "descending drive", which is where brain output naturally plugs in.
- **It has the senses we need.** Vision is built in. Smell is a 20-line addition using the
  published 1.x formula.
- **flybody stays reachable.** Its body can be loaded inside FlyGym later without a second
  toolchain.
- **Only fallback if FlyGym 2.x misses something vital:** flygym-gymnasium 1.x in a
  separate Python 3.12 environment. That needs a second Python install, so avoid it unless
  necessary.

### 6.2 Demo 1: walk toward an attractive odor (odor taxis)

**Loop,** every 50 ms of fly time. This matches the NeuroMechFly odor-taxis example's
decision interval.

1. **World → senses.** Compute odor intensity at the left and right antennae (distance⁻²
   from the source).
2. **Senses → brain.** Set Poisson input rates for left-side and right-side `ORN_DM1`
   (and/or `ORN_VA2`) proportional to each antenna's intensity. Run the brain model for
   50 ms.
3. **Brain → drive.**
   - Count spikes in left/right DNa02 (plus DNa01) and in DNg100 / DNp09.
   - Forward drive = f(DNg100 + DNp09 activity).
   - Turn = g(left DNa02 − right DNa02).
   - Drive = [forward − turn, forward + turn], clipped to the tutorial's range (about
     0.4–1.2).
   - Section 2.2 showed that a lower left number turns the fly left, and more left DNa02
     should mean a left turn. Confirm this sign in a test, don't assume it.
4. **Drive → body.** Step FlyGym's hybrid turning controller for 50 ms (500 physics
   steps). Label it "leg control from FlyGym, not brain-driven".
5. Repeat.

**Before closing the loop, run an open-loop check.**

- Stimulate only the left DM1 ORNs, then only the right ones.
- Do left and right DNa02 respond differently?
- If the whole-brain model shows no left/right difference, that is a result in itself.
  Report it, and try other DNs (DNa01, DNp09) or other glomeruli before building the loop.

**Checkpoint tests (Phase 9 in PLAN.md):**

- With the odor on, the fly ends closer to the source, or reaches it more often, than with
  the odor off. Use several random seeds and starting angles.
- Silencing DNa02 on both sides, or the stimulated ORNs, removes the steering.
- Optional: swapping left and right odor inputs makes the fly steer the wrong way.

**Time budget:** measured body speed was about 50 s of wall time per 1 s of fly time.
Brain time per 50 ms step comes on top. **UNVERIFIED:** Phase 3 will measure it. A 5-s
trial therefore takes several minutes, so keep trials short and few at first.

### 6.3 Next demos (in order)

1. **Bitter on the mouthparts → proboscis retraction / stop feeding.** Uses the Phase 3
   bitter circuit and MN9. The body side is small: FlyGym has proboscis segments
   (`rostrum`, `haustellum`).
2. **Aversive odor avoidance** (`ORN_V` for CO₂): should steer the opposite way to Demo 1.
3. **Phase 8 + 9 together.**
   - Train an avoidance of odor A (pair it with `PPL101`).
   - Check that the embodied fly now approaches A less than an untrained fly does.
   - This depends on MBON output reaching the steering DNs through the rest of the brain.
     Measure that pathway open-loop first.
4. **Brain-driven legs** via a BANC or MANC nerve-cord simulation (Pugliese-style). This is
   research-level work.

---

## 7. UNVERIFIED list

- flybody on Windows, and its exact failure mode on Python 3.13 (predicted from the
  numpy 1.26.4 pin, not run).
- flygym-gymnasium failure on 3.13 (predicted from missing wheels, not run).
- FlyGym 2.1.0 installed into the project `.venv` (only tested in a throwaway venv; the
  versions match).
- The `FlyBody` (flybody body) class inside FlyGym 2.1.0: present in the code, not run.
- BANC neuron count (188k vs 142k); whether Codex requires sign-in; whether neuPrint
  requires sign-in for tokens.
- MaleCNS neuron count (from a secondary summary).
- Odor→glomerulus links (DM1/VA2 attractive, V for CO₂, DA2 for geosmin) and the MDN
  citation: background knowledge, not re-read.
- Whether the Shiu model produces left/right-different DNa02 activity from one-sided
  odor. This is the key open question for Demo 1.
- Motor-neuron-to-muscle mapping for FlyGym's musculoskeletal model.

## 8. Sources

- FlyGym: pypi.org/project/flygym (2.1.0), github.com/NeLy-EPFL/flygym (README),
  neuromechfly.org (tutorials, migration page); flygym-gymnasium on PyPI (1.3.2) and
  GitHub (`arena/sensory_environment.py`, `examples/olfaction/simple_odor_taxis.py`).
- flybody: github.com/TuragaLab/flybody (README, pyproject.toml, CI workflow, releases).
- Wang-Chen S et al. (2024). NeuroMechFly v2. *Nat Methods*. doi:10.1038/s41592-024-02497-y.
- Vaxenburg R et al. (2025). Whole-body physics simulation of fruit fly locomotion.
  *Nature*. doi:10.1038/s41586-025-09029-4.
- Stürner T, Brooks P et al. (2025). *Nature* 643:158–172. doi:10.1038/s41586-025-08925-z;
  data at github.com/flyconnectome/2023neckconnective.
- Bates AS et al. (2026). *Nature*. doi:10.1038/s41586-026-10735-w; github.com/htem/BANC-project.
- Cheong HSJ et al. Organization of circuits linking descending input to motor output in
  the Drosophila MANC connectome. *eLife*. doi:10.7554/eLife.96084.
- Pugliese et al. Connectome simulations identify a central pattern generator circuit for
  fly walking. bioRxiv doi:10.1101/2025.09.12.675944.
- Rayshubskiy A et al. (2025). Neural circuit mechanisms for steering control in walking
  Drosophila. *eLife*. doi:10.7554/eLife.102230.
- Bidaye SS et al. (2020). Two brain pathways initiate distinct forward walking programs in
  Drosophila. *Neuron*. doi:10.1016/j.neuron.2020.07.032.
- Braun J et al. (2024). Descending networks transform command signals into population
  motor control. *Nature*. doi:10.1038/s41586-024-07523-9.
- Janelia MANC page (janelia.org/project-team/flyem/manc-connectome); male-cns.janelia.org;
  flyconnecto.me "The Adult Drosophila Connectome Ecosystem" (2026-09-04).
