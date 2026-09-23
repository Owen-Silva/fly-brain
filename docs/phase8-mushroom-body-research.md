# Phase 8 research: learning in the mushroom body

Prepared 2026-09-22, ahead of Phase 8. Anything marked **UNVERIFIED** was not confirmed
against a primary source in this pass. Every count below was measured directly from the
project's own data files, not taken from papers, unless a paper is cited.

---

## 1. The short version

- **The whole learning circuit is already in our data.** The reference model
  (`data/reference/Connectivity_783.parquet` + `Completeness_783.csv`) contains all
  5,177 Kenyon cells, 96 output neurons (MBONs), 331 dopamine neurons (DANs), both APL
  and both DPM neurons, and all 685 projection neurons. The labels that pick them out come
  from `data/flywire/Supplemental_file1_neuron_annotations.tsv`, keyed by the same
  FlyWire `root_id`.
- **The learning rule is well measured.** When an odor is on and a dopamine neuron fires
  shortly after, the connection from the odor's Kenyon cells to that compartment's output
  neuron gets much weaker. After a single 1-second pairing, the output neuron's response to
  that odor dropped by about 80% and stayed down for at least 40 minutes. A second, unpaired
  odor barely changed. If the dopamine came *before* the odor, nothing changed. (Hige et al.
  2015)
- **Two data traps to know about before writing code.**
  1. In the annotation file, Kenyon cells are predicted to release **dopamine**
     (`top_nt`), which is wrong: they are cholinergic. The same file's `known_nt` column
     says acetylcholine. The reference model already treats their outputs as excitatory,
     so the simulation is fine. The trap is only for any new loader that reads `top_nt`.
  2. The reference model treats **dopamine neuron outputs as ordinary fast excitatory
     synapses** (sign +1). Real dopamine acts slowly through receptors and mostly changes
     synapse strength. Phase 8 needs to decide how to handle that (see section 3.4).
- **The classic test.** Pair odor A with the punishment dopamine neuron PPL1-γ1pedc
  (FlyWire `PPL101`). Afterwards the output neuron MBON-γ1pedc>α/β (FlyWire `MBON11`)
  should respond much less to odor A than before, and odor B should change only a little.
  Controls: reversing the order (dopamine first), odor alone, and dopamine alone should all
  give no odor-specific change.

---

## 2. Picking out the circuit in FlyWire snapshot 783

### 2.1 Which file and which columns

- **File:** `data/flywire/Supplemental_file1_neuron_annotations.tsv` (from
  github.com/flyconnectome/flywire_annotations). It has 139,248 rows, one per neuron. Its
  columns include `supertype`, `dimorphism` and `synonyms`, which were added in release
  3.0.0, so this is a 3.x release. The exact tag (3.0.0 or 3.1.0) was not recorded when
  the file was downloaded. **UNVERIFIED.**
- **Join key:** `root_id`. This is the same ID used by `Completeness_783.csv` and in the
  `Presynaptic_ID` / `Postsynaptic_ID` columns of `Connectivity_783.parquet`.
- **Columns to filter on:** `cell_class` for the broad group and `cell_type` for the exact
  type. `super_class` is the level above `cell_class`.
- **Coverage check:** all MB neurons listed below are present in the reference model, with
  one exception: 3 of the 2,282 olfactory receptor neurons (ORNs) are missing from
  `Completeness_783.csv`.

### 2.2 The filters and the counts (measured)

| Circuit part | Filter | Count | Notes |
|---|---|---|---|
| Olfactory receptor neurons (ORNs) | `super_class == "sensory"` and `cell_class == "olfactory"` | 2,282 | 53 `ORN_*` types (e.g. `ORN_DA1` 126, `ORN_DM1` 68, `ORN_V` 67). Side labelled (1,118 left, 1,134 right, 30 "na"). 2,122 come in through the antennal nerve and 160 through the palp nerve (`nerve` column). |
| Projection neurons (PNs), all | `cell_class == "ALPN"` | 685 | `cell_sub_class`: 277 uniglomerular, 400 multiglomerular, 8 blank. `top_nt`: 474 acetylcholine, 203 GABA, 8 glutamate. |
| PNs that feed Kenyon cells | the ALPN rows above that have synapses onto KCs | — | 329,394 ALPN→KC synapses, 314,662 of them (96%) from uniglomerular PNs. |
| Kenyon cells (KCs), all | `cell_class == "Kenyon_Cell"` | 5,177 | 2,580 left and 2,597 right. |
| KC γ | `cell_type` starts with `KCg` | 2,490 | `KCg-m` 2,189, `KCg-d` 295, `KCg-s1/s2/s3` 5. `cell_sub_class == "KCg"`. |
| KC α/β | `cell_type` is `KCab` or `KCab-p` | 1,771 | `KCab` 1,643 (`cell_sub_class == "KCab"`), `KCab-p` 128 (its `cell_sub_class` is blank). |
| KC α′/β′ | `cell_type` starts with `KCapbp` **or** equals `KCa'b'-ap1` | 917 | `KCapbp-m` 338, `KCapbp-ap2` 298, `KCapbp-ap1` 280, plus 1 neuron spelled `KCa'b'-ap1`. `cell_sub_class` is **blank** for these, so filter by `cell_type`. |
| MBONs | `cell_class == "MBON"` | 96 | 48 per side. Types are `MBON01`…`MBON35` (see table 2.4). There is no `MBON08`; `MBON09` has 4 cells instead. The hemibrain looks the same. |
| DANs | `cell_class == "DAN"` | 331 | 303 PAM (`PAM01`…`PAM15`) and 24 PPL1/PPL2 (`PPL101`…`PPL108`, `PPL201`…`PPL204`, 2 each). `cell_sub_class` is blank, so use the `cell_type` prefix `PAM` or `PPL1` / `PPL2`. |
| APL (the giant inhibitory feedback neuron) | `cell_type == "APL"` | 2 | `cell_class == "MBIN"`. GABA (known and predicted). |
| DPM | `cell_type == "DPM"` | 2 | `cell_class == "MBIN"`. `known_nt` is serotonin, GABA and the amnesiac peptide. Its `top_nt` says dopamine, which is wrong. |

Some KCs (about 290 of 5,177) get no PN input at all. Some KC subtypes (e.g. `KCg-d`,
`KCab-p`) are known to receive visual rather than olfactory input.

### 2.3 How the pieces connect in the reference model (measured from `Connectivity_783.parquet`)

| Connection | Synapses | Sign in reference model |
|---|---|---|
| PN → KC | 329,394 | + (from cholinergic PNs) |
| KC → MBON | 256,719 (67% of all MBON input, which is 381,461) | + |
| KC → KC | 379,338 | + (real KC-KC contacts exist. In the model they add a lot of recurrent excitation, so watch for runaway activity.) |
| KC → APL | 116,878 | + |
| APL → KC | 98,654 | − |
| KC → DAN | 125,133 | + |
| KC → DPM / DPM → KC | 88,051 / 9,280 | + / + |
| DAN → KC | 60,657 | **+ (treated as fast excitation)** |
| DAN → MBON | 15,284 | **+ (treated as fast excitation)** |
| MBON → DAN | 8,912 | mixed |
| MBON → MBON | 19,983 | mixed |

Other facts measured from the same data:

- The median KC gets input from 6 distinct PNs (mean 5.7). This matches the known
  "about 6–7 claws per KC" anatomy.
- Every KC→anything connection has sign +1, and every DAN→anything connection has
  sign +1. The reference model must be treating dopamine (and serotonin, octopamine) as
  excitatory, and only GABA and glutamate as inhibitory.
- For comparison, the hemibrain (a different fly, right side only) has 1,927 KCs:
  889 α/β, 337 α′/β′ and 701 γ (Li et al. 2020, eLife 9:e62576). That is fewer γ cells per
  side than FlyWire has.

### 2.4 Which compartment each MBON and DAN type belongs to

The FlyWire type names are numbers. The compartment names used in the learning papers
come from the hemibrain "instance" names in
`flyconnectome/flywire_annotations/supplemental_files/Supplemental_file5_hemibrain_meta.csv`
(downloaded and read in this pass). The FlyWire `hemibrain_type` column confirms the
numbers correspond one to one. Compartment letters: γ = gamma lobe, α/β = alpha/beta,
α′/β′ = alpha-prime/beta-prime, and numbers are positions along each lobe. "pedc" is the
peduncle.

**MBONs** (transmitter = the most common FlyWire `top_nt` for that type):

| FlyWire type | Compartment | Transmitter | FlyWire cells |
|---|---|---|---|
| MBON01 | γ5β′2a | glutamate | 2 |
| MBON02 | β2β′2a | glutamate | 2 |
| MBON03 | β′2mp | glutamate | 2 |
| MBON04 | β′2mp_bilateral | glutamate | 2 |
| MBON05 | γ4>γ1γ2 | glutamate | 2 |
| MBON06 | β1>α | glutamate | 2 |
| MBON07 | α1 | glutamate | 4 |
| MBON09 | γ3β′1 | GABA | 4 |
| MBON10 | β′1 | GABA | 9 |
| MBON11 | γ1pedc>α/β | GABA | 2 |
| MBON12 | γ2α′1 | acetylcholine | 4 |
| MBON13 | α′2 | acetylcholine | 2 |
| MBON14 | α3 | acetylcholine | 4 |
| MBON15 (+ MBON15-like) | α′1 | acetylcholine | 4 (+5) |
| MBON16 | α′3ap | acetylcholine | 2 |
| MBON17 (+ MBON17-like) | α′3m | acetylcholine | 2 (+2) |
| MBON18 | α2sc | acetylcholine | 2 |
| MBON19 | α2p3p | acetylcholine | 4 |
| MBON20 | γ1γ2 | GABA | 2 |
| MBON21 | γ4γ5 | acetylcholine | 2 |
| MBON22 | calyx | acetylcholine | 2 |
| MBON23 | α2sp | acetylcholine | 2 |
| MBON24 | β2γ5 | acetylcholine | 2 |
| "MBON25,MBON34" (one combined FlyWire label) | γ1γ2 (MBON25) / γ2 (MBON34) | glutamate | 6 |
| MBON26 | β′2d | acetylcholine | 2 |
| MBON27 | γ5d | acetylcholine | 2 |
| MBON28 | not in the hemibrain instance name, **UNVERIFIED** | acetylcholine | 2 |
| MBON29 | γ4γ5 | acetylcholine | 2 |
| MBON30 | γ1γ2γ3 | glutamate | 2 |
| MBON31 | α′1a | GABA | 2 |
| MBON32 | γ2 | GABA | 2 |
| MBON33 | γ2γ3 | acetylcholine | 2 |
| MBON35 | γ2 | acetylcholine | 2 |

Aso et al. 2014 described 21 "typical" MBON types (MBON01–MBON21). The hemibrain paper
(Li et al. 2020) added "14 additional types" of "atypical" MBONs, whose dendrites also
reach outside the MB lobes. That fits MBON22–MBON35 being the 14 atypical ones, but the
exact numbering split was inferred here, not quoted. **UNVERIFIED.**

**DANs:**

| FlyWire type | Compartment | FlyWire cells |
|---|---|---|
| PAM01 | γ5 | 41 |
| PAM02 | β′2a | 16 |
| PAM03 | β2β′2a | 10 |
| PAM04 | β2 | 32 |
| PAM05 | β′2p | 21 |
| PAM06 | β′2m | 30 |
| PAM07 | γ4<γ1γ2 | 18 |
| PAM08 | γ4 | 45 |
| PAM09 | β1ped | 9 |
| PAM10 | β1 | 15 |
| PAM11 | α1 | 16 |
| PAM12 | γ3 | 23 |
| PAM13 | β′1ap | 12 |
| PAM14 | β′1m | 16 |
| PAM15 | γ5β′2a | 3 |
| PPL101 | γ1pedc | 2 |
| PPL102 | γ1 | 2 |
| PPL103 | γ2α′1 | 2 |
| PPL104 | α′3 | 2 |
| PPL105 | α′2α2 | 2 |
| PPL106 | α3 | 2 |
| PPL107, PPL108 | hemibrain instance gives only a cell-body tract (PDL05), not a compartment. **UNVERIFIED** whether they innervate the MB lobes. | 2 each |
| PPL201–PPL204 | PPL2 cluster. Compartment not in the instance name, **UNVERIFIED** (PPL2 neurons are generally described as innervating the calyx and lateral horn). | 2 each |

**Cross-check to run in Phase 8:** DANs make direct synapses onto MBONs (15,284 in total).
In each compartment, the DAN→MBON synapses should mostly join the DAN and MBON types that
share a compartment in the tables above. If they don't, the name mapping is wrong.

---

## 3. The learning rule

### 3.1 What the experiments show

**Hige et al. 2015, Neuron 88:985–998 (doi:10.1016/j.neuron.2015.11.003).** Whole-cell
recordings from MBON-γ1pedc>α/β (our `MBON11`). The punishment DAN PPL1-γ1pedc (our
`PPL101`) was switched on with light. Numbers are quoted from the paper's text:

- **Protocol:** odor on for 1 s; four 1-ms light pulses at 2 Hz, starting 0.2 s after odor
  onset; one single pairing.
- **Effect on the paired odor:** odor response fell from 118 ± 8.3 to 24 ± 7.4 spikes.
  The paper reports an "80 ± 5.7 % reduction in spiking". The synaptic current fell by
  90 ± 3.7%.
- **Effect on the unpaired odor:** 110 ± 11 to 83 ± 14 spikes, a small drop.
- **How long it lasts:** "persisted throughout the duration of the recordings, which lasted
  at least 40 min, and showed only a small sign of recovery."
- **Order matters:** in backward pairing, the odor started 0.5 s after the last light
  pulse. This produced "no change in odor responses".
- **Location:** the change is at the KC→MBON synapse (depression), not in KC excitability.
- **Compartments learn at different speeds:** the same 1-s pairing in the α2 compartment
  (PPL1-α′2α2 → MBON-α2sc, our `PPL105` → `MBON18`) did nothing. A longer protocol
  (1 min of odor with 120 light pulses) gave "robust, stimulus-specific LTD".

**Cohn, Morantte & Ruta 2015, Cell 163:1742–1755 (doi:10.1016/j.cell.2015.11.019).**
Dopamine's effect is confined to its own compartment. The same KC can send different
signals to different MBONs depending on which compartment's dopamine is active. The DANs
behave as an interconnected network that reports the fly's context and internal state.

**Aso & Rubin 2016, eLife 5:e16135 (doi:10.7554/eLife.16135).** Behaviour after
optogenetic DAN activation paired with odor:

- **Aversive memory:** PPL1-γ1pedc (driver line MB320C). Also MB099C, which labels
  PPL1-γ2α′1, α′2α2, α′3 and α3 (the four-type list is from Hige 2015). Also PPL1-α3
  (MB630B).
- **Appetitive memory:** PAM-α1 (MB043C), MB213B (which includes PAM-β1), and the
  combination PAM-γ5 + PAM-β′2a (MB315C + MB109B).
- **Speed and persistence differ by compartment:** γ1pedc forms memory after a single
  training round, and the memory "largely decayed by 24 hr". α3 barely forms memory after
  one pairing but forms 4-day memory after repeated training. For most lines, 60-s
  training worked better than 10-s training.
- **Timing window:** PPL1-γ1pedc activation "within a 30-s time window following the
  onset of a 10-s odor presentation" made an aversive memory. DAN activation that
  *preceded* the odor by 20–60 s made an *appetitive* memory.
- **Updating:** activating the same DAN again without odor almost abolished the memory.
  Pairing the DAN with a new odor weakened the old memory (γ1pedc keeps only the most
  recent one; α1 can hold two).

**Handler et al. 2019, Cell 178:60–75 (doi:10.1016/j.cell.2019.05.040).**

- **Direction depends on timing:** depression "when DAN stimulation was concurrent or
  followed KC activation". Potentiation "when DAN stimulation preceded KC activation".
  The γ4 compartment showed significant change at inter-stimulus intervals of −1.2 s,
  0 s and +0.5 s. Stretching the interval to 6 s gave "minimal plasticity".
- **Mechanism:** two dopamine receptors. DopR1 drives the depression and DopR2 drives the
  potentiation.
- **Reversible in one trial:** one forward pairing depresses the synapse, and a single
  backward pairing reverses it.

### 3.2 The rule in a form we can implement

Everything in this subsection is a **modelling choice for us to calibrate**. It is built
from the findings above but is not itself a published equation.

For every KC→MBON connection (KC `k`, MBON `m`, in compartment `c`):

1. **KC "recently active" tag (eligibility trace) `x_k`.** Add 1 each time KC `k` spikes.
   Let it decay back to zero with time constant `τ_KC`. Start at `τ_KC` ≈ 1 s: Handler saw
   depression at 0 and +0.5 s but almost nothing at 6 s.
2. **Compartment dopamine level `D_c`.** Add 1 each time any DAN of compartment `c`
   spikes, using the DAN table in 2.4. Let it decay with `τ_DA` ≈ 0.3–1 s
   (**UNVERIFIED**, needs calibration).
3. **Depression (the core rule).** Whenever there is dopamine in compartment `c`, weaken
   each active KC's synapse in proportion to its tag:
   `Δw_km = −η_c · x_k · D_c · w_km` per time step. The weight can never go below 0, and
   the rule is applied only to synapses onto MBONs in compartment `c`. Because the change
   is proportional to `w`, the weight shrinks gradually and can never flip sign.
4. **Learning rate per compartment `η_c`.**
   - Calibrate `η` for γ1pedc so that the exact Hige protocol (1-s odor; 4 DAN pulses at
     2 Hz starting 0.2 s after odor onset) lowers `MBON11`'s response to that odor by
     about 80%.
   - Calibrate α2 and α3 so that the same short protocol gives almost no change (under
     about 10%), but 1 min of odor with 120 pulses gives a large change.
5. **No forgetting inside an experiment.** Hige measured stability for at least 40 min.
   Weights stay changed until something reverses them.
6. **Optional second stage: potentiation (for reversal and extinction).**
   - If dopamine arrives while a KC's tag is near zero, and the KC then fires within about
     1–2 s, strengthen that synapse back toward its original value `w0`:
     `Δw = +η⁺_c · (w0 − w)`.
   - This covers the "DAN first" potentiation (Handler 2019) and the memory erasure seen
     when the DAN is activated alone (Aso & Rubin 2016).
   - Leave it out of the first version so the first checkpoint tests only the core rule.

The starting weights are the reference model's: synapse count × 0.275 mV (`w_syn` in
`data/reference/model.py`). The same KC→MBON pair has a single weight in the model (the
count), so the rule scales that one number.

### 3.3 How to give the model an "odor"

- **Simplest:** pick two sets of ORN types (e.g. a few `ORN_*` types each, no overlap) as
  "odor A" and "odor B". Drive them with Poisson input, the same way Phase 3 drives sugar
  neurons.
- **More realistic later:** use published receptor response tables (Hallem & Carlson 2006;
  the DoOR database) to build ORN activation patterns for the real training odors,
  3-octanol (OCT) and 4-methylcyclohexanol (MCH). **UNVERIFIED:** it has not been checked
  that DoOR covers both odors or how to download it.
- **Sanity check before any learning:** an odor should activate only a small fraction of
  KCs (sparse coding). This is commonly cited as roughly 5–10% (Turner et al. 2008;
  Honegger et al. 2011) and depends on APL inhibition (Lin et al. 2014). **UNVERIFIED:**
  the exact percentage was not re-checked in this pass. If far more KCs fire, the
  representation is not sparse. Learning would then spread to the unpaired odor too, and
  the control would fail.

### 3.4 Decision needed: what to do with the dopamine neurons' fast synapses

In the reference model, DAN spikes excite KCs (60,657 synapses) and MBONs (15,284) like
ordinary fast synapses. Biologically, dopamine acts through slow receptors (DopR1 / DopR2).
Recommended:

- **Default:** keep the reference behaviour so the Phase 3 baseline stays identical.
- **Switch:** add an option to send DAN spikes only into the plasticity signal `D_c` and
  not into the fast synapses.
- **Report both:** show results with the switch on and off.
- **Keep other signs as they are:** the MBON→DAN feedback loops and KC→DAN input can stay
  as they are. They are part of how DAN activity is shaped.

---

## 4. Good and bad: which neurons mean punishment, reward, approach, avoidance

### 4.1 Dopamine neurons

| Meaning | DAN (FlyWire type) | Evidence |
|---|---|---|
| Punishment (aversive), fast, short-lived | PPL1-γ1pedc (`PPL101`) | Hige 2015; Aso & Rubin 2016 |
| Punishment (aversive) | PPL1-γ2α′1 (`PPL103`), PPL1-α′2α2 (`PPL105`) | Aso & Rubin 2016 (driver MB099C) |
| Punishment (aversive), slow, long-lasting | PPL1-α3 (`PPL106`) | Aso & Rubin 2016 (MB630B) |
| Reward (appetitive) | PAM-α1 (`PAM11`) | Aso & Rubin 2016 (MB043C) |
| Reward (appetitive) | PAM-β1 (`PAM10`) and partners in MB213B | Aso & Rubin 2016 |
| Reward (appetitive) | PAM-γ5 (`PAM01`) + PAM-β′2a (`PAM02`) | Aso & Rubin 2016 (MB315C + MB109B) |
| Reward, broad | the PAM cluster as a whole (driver R58E02, about 90 PAM DANs) | Liu et al. 2012, as cited in Aso & Rubin 2016 |
| Other PAM types (γ3, γ4, β2, β′1, β′2m/p, …) | — | Not pinned down in this pass. **UNVERIFIED.** |

Rule of thumb: the PPL1 cluster signals punishment and the PAM cluster mostly signals
reward.

### 4.2 Output neurons (Aso et al. 2014, eLife 3:e04580; Owald et al. 2015; Perisse et al. 2016)

- **Activating these makes flies avoid:** the glutamatergic "M4/M6" group:
  MBON-γ5β′2a (`MBON01`), MBON-β′2mp (`MBON03`) and MBON-β′2mp_bilateral (`MBON04`)
  (driver MB011B). Owald 2015 also counts MBON-β2β′2a (`MBON02`) in M4/6.
- **Activating these makes flies approach:** MBON-γ1pedc>α/β (`MBON11`, GABA, driver
  MB112C) and MBON-γ2α′1 (`MBON12`, acetylcholine, driver MB077B).
- **General pattern (Aso 2014, quoted):** "all MBONs eliciting aversion were glutamatergic
  and all the MBONs eliciting attraction were either GABAergic or cholinergic."
- **The effect adds up:** co-activating two same-sign MBON types gave a stronger response,
  and opposite signs gave an intermediate one. So a simple "approach score minus avoidance
  score" read-out is reasonable.
- **How aversive learning works (Perisse 2016):** it depresses the odor drive to
  `MBON11` (also called MVP2). `MBON11` normally inhibits the avoidance MBONs, so after
  learning the odor releases that brake and avoidance wins.
- **Opposite direction (Owald 2015):** appetitive and aversive training change the relative
  odor drive of MBON-β′2mp (`MBON03`) in opposite directions. Blocking M4/6 in untrained
  flies turns odor avoidance into approach.

### 4.3 What result to expect

**Aversive training.** Odor A is paired with `PPL101` (forward, overlapping). Odor B is
presented unpaired.

| Read-out | Expected after training |
|---|---|
| `MBON11` response to A | Large drop, about 80% in Hige's single-pairing protocol |
| `MBON11` response to B | Small drop at most |
| Avoidance MBONs (`MBON01/03/04`) response to A vs B | A relatively higher. `MBON11` no longer inhibits them for odor A. This is a network effect and may be weaker in the model. |
| Approach-minus-avoidance score for A | Goes down (the fly "dislikes" A) |

**Appetitive training.** Odor A is paired with `PAM01` + `PAM02`: the KC→`MBON01`
(γ5β′2a) synapses for A are depressed, so avoidance drive for A goes down and the score
goes up.

### 4.4 Controls the checkpoint needs

1. **Backward pairing:** DAN pulses first, odor starting 0.5 s after the last pulse. Expect
   no change, as in Hige 2015.
2. **Explicitly unpaired:** DAN and odor separated by many seconds (well over the 6-s gap
   where Handler saw almost no plasticity). Expect no odor-specific change.
3. **Odor alone:** no DAN. Expect no change. The core rule cannot change anything without
   dopamine.
4. **DAN alone:** no odor. Expect no odor-specific change.
5. **Specificity:** the change for the paired odor must be much larger than for the
   unpaired one.
6. **Compartment check:** pairing with `PPL101` must not change the α2/α3 MBONs, and the
   short protocol in α2 must do little (Hige 2015).
7. **Phase 3 regression:** the sugar → MN9 result must still hold with plasticity
   switched on but no training.

---

## 5. Existing models to compare against

| Model | What it is | Use for us |
|---|---|---|
| Eschbach et al. 2020, Nat Neurosci 23:544–555 (doi:10.1038/s41593-020-0607-9) | Larval MB connectome; recurrent DAN/MBON feedback that regulates learning | Ideas for MBON→DAN feedback. Larva, not adult. |
| Jiang & Litwin-Kumar 2021, PLoS Comput Biol 17:e1009205 (doi:10.1371/journal.pcbi.1009205) | Adult MB model constrained by hemibrain-style architecture; dopamine-gated plasticity with many different DAN signals | Closest peer-reviewed adult model of the plasticity rule and DAN diversity |
| Li et al. 2020, eLife 9:e62576 | Hemibrain MB connectome (data, not a model) | Source of compartment names and "atypical" MBONs; second fly for comparison |
| Community projects on FlyWire / MaleCNS (FlyTris, "fly-brain" by erojasoficial-byte, etc.) | Hobby projects, not peer reviewed. The erojas project uses a Hebbian rule, not dopamine-gated. | Only as a reality check. Do not treat as validation. |

A peer-reviewed adult whole-brain FlyWire model with dopamine-gated KC→MBON plasticity was
not found in this pass. The search was not exhaustive. **UNVERIFIED.**

---

## 6. Open items and UNVERIFIED list

- Exact release tag of the annotation TSV (3.0.0 vs 3.1.0).
- Compartment for MBON28, PPL107/108 and PPL201–204.
- Valence of the PAM types not listed in 4.1.
- The dopamine decay time `τ_DA` and all `η` values. These are to be calibrated, not taken
  from the literature.
- KC sparseness percentage (quoted as "roughly 5–10%" from memory of the literature).
- Whether DoOR / Hallem-Carlson data cover OCT and MCH, and how to download them.
- Whether the model's MBON11 → avoidance-MBON inhibition is strong enough to show the
  network-level effect in 4.3.

## 7. Sources (all fetched or read in this pass unless noted)

- Hige T, Aso Y, Modi MN, Rubin GM, Turner GC (2015). Heterosynaptic plasticity underlies
  aversive olfactory learning in Drosophila. *Neuron* 88:985–998. PMC4674068.
- Cohn R, Morantte I, Ruta V (2015). Coordinated and compartmentalized neuromodulation
  shapes sensory processing in Drosophila. *Cell* 163:1742–1755. PMC4732734.
- Aso Y, Rubin GM (2016). Dopaminergic neurons write and update memories with
  cell-type-specific rules. *eLife* 5:e16135. PMC4987137.
- Handler A et al. (2019). Distinct dopamine receptor pathways underlie the temporal
  sensitivity of associative learning. *Cell* 178:60–75. PMC9012144.
- Aso Y et al. (2014). Mushroom body output neurons encode valence and guide memory-based
  action selection in Drosophila. *eLife* 3:e04580. PMC4273436.
- Owald D et al. (2015). Activity of defined mushroom body output neurons underlies learned
  olfactory behavior in Drosophila. *Neuron* 86:417–427.
- Perisse E et al. (2016). Aversive learning and appetitive motivation toggle feed-forward
  inhibition in the Drosophila mushroom body. *Neuron* 90:1086–1099.
- Li F et al. (2020). The connectome of the adult Drosophila mushroom body provides
  insights into function. *eLife* 9:e62576.
- Eschbach C et al. (2020). *Nat Neurosci* 23:544–555. Jiang L, Litwin-Kumar A (2021).
  *PLoS Comput Biol* 17:e1009205 (abstracts only).
- Cited but not re-read in this pass: Turner et al. 2008; Honegger et al. 2011; Lin et al.
  2014; Liu et al. 2012; Hallem & Carlson 2006; DoOR.
- Data: flyconnectome/flywire_annotations (`Supplemental_file1_neuron_annotations.tsv`,
  `Supplemental_file5_hemibrain_meta.csv`); philshiu/Drosophila_brain_model
  (`Connectivity_783.parquet`, `Completeness_783.csv`).
