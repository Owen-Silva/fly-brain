# Phase 6 step 3: is it already known? (literature check of three findings)

*Written 2026-09-23. This is PLAN.md Phase 6 step 3 ("search the literature to see whether
it's already known") for three PRELIMINARY findings. No simulations were run. A few
read-only look-ups were made in the local data files (FlyWire annotation tables, the
snapshot 630 connection list, the snapshot 783 connection table) and in the public
Virtual Fly Brain database. Nothing was posted, sent or shared.*

**Labels used in this document** (adapted from docs/phase5-competition.md for claims about
papers):
- **VALIDATED** = read in a primary source (full text, or the exact database record),
  or two independent lines of evidence agree.
- **PRELIMINARY** = one line of evidence only, or the source was read only in part
  (abstract, an automated extract, or a search-engine excerpt).
- **UNVERIFIED** = not checked against any source.

**Terms used below** (each defined once):
- *GRN* (gustatory receptor neuron): a taste neuron. *Sugar GRNs* and *bitter GRNs* sense
  sugar and bitter chemicals.
- *MN9*: the motor neuron that extends the proboscis (the fly's feeding tube).
- *Premotor neuron*: a neuron one step before a motor neuron. What our Phase 5 doc called
  the sugar pathway's "middle stage" is what the papers call the "feeding initiation
  premotor neurons".
- *SEZ* (subesophageal zone): the fly's taste and feeding centre. Its main part is the
  *GNG* (gnathal ganglia).
- *FlyWire*: the female whole-brain wiring diagram our model is built on. *Snapshot 630 /
  783*: two releases of it. *Root ID*: FlyWire's ID for one neuron; it changes when the
  neuron is edited.
- *Male CNS connectome* (Berg et al. 2025): a second, male fly's brain and nerve cord,
  with its own cell-type names (for example "GNG087"). *BANC*: a third dataset (another
  lane covers it).
- *Virtual Fly Brain (VFB)*: a public database that links the same neuron across
  datasets and to the published literature.
- *NBLAST*: a score for how similar two neuron shapes are (1 = identical).
- *ORN* (olfactory receptor neuron): a smell neuron in the antenna. *PN* (projection
  neuron): the antennal lobe's output cell. *Glomerulus*: one of ~50 ball-shaped units of
  the antennal lobe; each receives one ORN type. *eLN*: excitatory local neuron of the
  antennal lobe.

---

## The short version

- **Finding 1, the "bitter brake" CB0219: KNOWN.** CB0219 is the neuron the Scott lab
  named **"Scapula"** in 2022 (Shiu et al., eLife). The male CNS connectome calls the same
  type **GNG087**. Its role in our model (bitter GRNs -> glutamate brake -> feeding
  premotor neurons -> MN9) is exactly the circuit that paper proposed from the wiring and
  supported with calcium imaging in real flies: bitter suppresses the premotor neuron
  Roundup, not the earlier sugar neurons. A 2024 paper that ran connectome-based
  simulations (Jacobs et al., *Cell Reports*; very likely the same Shiu model, not
  confirmed) reportedly found that silencing Scapula abolishes bitter's suppression of
  Roundup and MN9. That wording was seen only in search-engine excerpts; the full text
  was blocked. So our result reproduces published work; it is
  not a discovery. **No real-fly experiment that silences or activates Scapula itself
  was found.** That is still the open test.
- **Finding 2, the runaway: PARTLY KNOWN.** No peer-reviewed paper reports it. One
  public hobby project (GitHub, September 2026) reports the same state on snapshot 783
  (smell input, about 8,300 neurons firing, never recovering), but says it "did not
  localise the runaway". Other modellers expected instability and scaled their weights
  down to avoid it. **Our cause (the antennal lobe's excitatory local neurons) and our
  literature-based fix were not found anywhere.** On transmitters: FlyWire's guesses
  for these cells are known to be unreliable (Eckstein et al. 2024). The newer male CNS
  predictions call them acetylcholine, which agrees with our Phase 7 audit.
- **Finding 3, the left/right imbalance: PARTLY KNOWN.** The FlyWire papers say the
  brain is "mostly" symmetric. About 1 cell type in 6 differs in number between the two
  sides. Technical factors also differ by side and by region: how completely synapses
  were attached to neurons, and a dark-staining artefact that hides synapses and is
  "much" more common in sensory neurons. **A DM1-specific imbalance is not reported
  anywhere we looked.** In the published annotation table, DM1 has 35 left vs 33 right
  ORNs, so the 52% synapse difference is not a difference in ORN numbers. Real flies do
  turn toward a one-sided DM1 signal (Gaudry et al. 2013), so the model's DM1 behaviour
  contradicts biology.
- **Worth telling anyone?** Only finding 2, after two more checks (section 5). Finding
  1 is a reproduction. Finding 3 waits on the BANC comparison.

---

## 1. What was searched

| Source | Why | How much was read |
|---|---|---|
| Shiu, Sterne, Engert, Dickson & Scott 2022, *eLife* 11:e79887 (PMC9292995) | the bitter pathway, Scapula | full text via PubMed Central (key passages extracted) |
| Shiu et al. 2024, *Nature* (PMC11446845) and its 2023 bioRxiv version (PMC10187186) | the model paper | full text, searched for Scapula, bitter, runaway, smell |
| Jacobs, ... & Devineni 2024, *Cell Reports* 43:114782 | the same model used on the sugar/bitter circuit | **abstract only** (Europe PMC); Scapula sentences seen only as search-engine excerpts; publisher and bioRxiv blocked automated access |
| Bohra, Kallman, Reichert & VijayRaghavan 2018, *Curr Biol* 28:847 | a pair of bitter interneurons | abstract, plus an automated extract of the bioRxiv preprint |
| Engert, Sterne, Bock & Scott 2022, *eLife* (PMC9170244) | bitter GRN wiring | full text; it covers only GRN-to-GRN wiring |
| Walker, Pena-Garcia & Devineni 2025, *Sci Rep* (PMC11821855) | taste circuits in FlyWire | full text via extract; no Scapula |
| Tastekin et al. 2025 bioRxiv / 2026 *Cell* ("complete gustatory connectome") | taste connectome of the male CNS | extract of bioRxiv v2 (no Scapula found in it); the Europe PMC index says the preprint mentions Scapula, not read |
| Chu et al. 2014 *Curr Biol* 24:1978; French et al. 2015 *J Neurosci* 35:3990; Lee et al. 2025 *PNAS* 122:e2413134122 | other bitter-vs-sugar mechanisms | abstracts |
| Virtual Fly Brain (public search index and graph database) | cross-dataset identity of CB0219, male CNS transmitter guesses | exact records read |
| philshiu/Drosophila_brain_model issues (GitHub API, read-only) | reports of runaway | all 10 titles |
| Pospisil et al. 2024 *Nature* (PMC11446844) | the "effectome" | automated extract of the full text |
| Wang et al. 2025, arXiv 2508.16792 (Loihi 2) | a port of the model | full text searched |
| Zanichelli, ..., Shiu & Arkhipov 2025, arXiv 2510.15745 ("State of Brain Emulation") | review co-written by the model's author | full text searched |
| Li, Ping, Zhang & Wang 2026, bioRxiv 2026.08.21.745055 | fitted whole-brain model | abstract (Europe PMC); one more sentence seen as a search excerpt |
| Bossard et al. 2026 (arXiv 2608.00306); Jin et al. 2026 (arXiv 2602.17997) | later papers citing the model | full text searched |
| GitHub READMEs: Jadog1122/fly-with-a-real-brain, Kisame76/drosophila-brain-mlx, gianlucamazza/flymsg, eonsystemspbc/fly-brain, neuroflyapp/neurofly | public ports of the model | READMEs read |
| Schlegel et al. 2024 *Nature* (PMC11446831); Dorkenwald et al. 2024 *Nature* (PMC11446842) | FlyWire left/right | full text searched (Europe PMC XML) |
| Schlegel et al. 2021 *eLife* (PMC8298098); Gruber et al. 2025 *eLife* 12:RP88824 (PMC12537010) | antennal lobe connectomes | full text searched |
| Gaudry, Hong, Kain, de Bivort & Wilson 2013 *Nature* 493:424 (PMC3590906) | same-side advantage, DM1 behaviour | automated extract of the full text |
| Berg et al. 2025 bioRxiv 10.1101/2025.10.09.680999 (male CNS) | transmitter guesses | abstract; its per-neuron predictions read via Virtual Fly Brain |

---

## 2. Finding 1: CB0219 is "Scapula"

### 2a. The identification

Five separate lines of evidence point to the same answer:

1. **The Scott lab's own tracing matches CB0219 by shape.** Virtual Fly Brain holds the
   2022 tracing "Scapula#1 (FAFB:16887116)" from Shiu et al. 2022. Its best NBLAST match
   among all FlyWire neurons is **720575940624600840, our CB0219-left (score 0.81)**. The
   second best is **720575940626826288 (0.66)**, which is our CB0219-right under its
   snapshot 783 ID (630 ID 720575940620062288; same supervoxel and cell-body position).
   The next best match scores 0.59. **VALIDATED** (database record read directly).
2. **The FlyBase anatomy ontology** has a class "adult CB0219 neuron" (FBbt:20004033) with
   the synonym **GNG087**. Its members are the two FlyWire CB0219 cells, three male CNS
   cells named GNG087 (one left, two right) and two BANC cells. A separate class, "adult
   scapula subesophageal neuron" (FBbt:00052224), is defined as an "Adult interneuron
   that receives a large amount of input from bitter-sensing gustatory neurons in the
   subesophageal zone and sends inhibitory (predicted glutamatergic) input to feeding
   premotor neurons (Shiu et al., 2022)." **VALIDATED** (records read directly).
3. **The wiring matches the 2022 description.** Shiu et al. 2022: Scapula "receives over
   150 synapses from bitter GRNs and is the second-most strongly connected cell type with
   bitter GRNs", "is predicted to release glutamate", and "synapses directly onto two
   feeding initiation premotor neurons, Roundup and Rounddown, but not onto second- or
   third-order appetitive taste neurons". Our look-up in snapshot 630 found:
   - The model's 21 bitter GRNs make 359 synapses onto the two CB0219 cells (247 left,
     112 right) and none onto them from sugar GRNs. Among named cell types this is the
     **second-largest bitter input**, after CB0159 (GABA, 781 synapses onto its two
     cells).
   - CB0219's outputs include **Roundup** (CB0553; 47 synapses left, 36 right),
     **Rounddown** (DNge080; 105 and 105) and **Roundtree** (CB0493; 142 and 141). These
     names come from the model paper's own tables, as mapped by the Phase 5 sugar lane
     (`experiments/phase5/sugar_pathway/build_groups.py`).
   - It sends at most 8 synapses to any of the other named sugar-pathway neurons
     (Rattle, Usnea, Phantom, Clavicle, G2N-1, FMIn, Fdg).
   - In snapshot 783, 93-95% of its output synapses and 72-78% of its inputs lie in the
     GNG. Most of the rest lie in the prow (PRW), also part of the SEZ. It is a local
     SEZ cell.
   **VALIDATED** (paper full text plus our own look-up).
4. **The model paper names the same link.** Shiu et al. 2024 (*Nature*): "Phantom
   strongly synapses onto Scapula—a neuron that is also predicted to be inhibitory;
   Scapula, in turn, synapses onto Roundup". Our connection list has Phantom-left ->
   CB0219-left (66 synapses) -> Roundup-left (47), found independently by the Phase 5
   sugar lane (docs/phase5-sugar-pathway.md, item C). **VALIDATED.**
5. **The same transmitter guess in a second brain.** The male CNS predicts glutamate for
   all three GNG087 cells (confidence 0.72, 0.77, 0.79), as FlyWire does for CB0219
   (0.68, 0.73). It is still a machine guess in both brains; no antibody stain was
   found. **PRELIMINARY.**

What we could not check: Shiu et al. 2022 list Scapula's FlyWire ID as
720575940624539966, an older root ID. Following an old ID to its current one needs a
FlyWire login, so that last step is **UNVERIFIED**. The five lines above make the match
very likely anyway.

**Other names for the same cell:** FlyWire type CB0219. It has no hemibrain type (the
hemibrain volume leaves out most of the SEZ). Its FlyWire hemilineage label is
"putative_primary". The v783 annotation marks it "isomorphic": the same in males and
females. Its Virtual Fly Brain IDs are fw007291 (left) and fw036378 (right).

### 2b. What is already published about Scapula

- **Shiu et al. 2022** (real flies plus wiring): "bitter GRNs do not directly synapse with
  neurons in the feeding initiation circuit". Calcium imaging: the second-order sugar
  neuron G2N-1 responded the same to sugar alone and to sugar + bitter. But "Upon
  co-activation of sugar and bitter GRNs, the Roundup response was dramatically
  decreased". Conclusion: "sugar and bitter tastes are integrated at feeding initiation
  premotor neurons". Scapula is their proposed link. **VALIDATED** (full text).
- **Jacobs et al. 2024** ran connectome-based simulations. The same lab's 2025 paper
  (Walker et al.) used the Shiu model, so this is very likely the same model, but that
  was not confirmed. The abstract (read) says the simulations "predict ... that bitter input overrides the sugar
  circuit through multiple pathways acting at third- and fourth-order neurons".
  Optogenetic experiments in flies "suggest that bitter input inhibits third- and
  fourth-order sugar neurons". Search-engine excerpts attributed to the published
  article, returned by three different searches, say: "Silencing Scapula globally
  reduced bitter suppression, whereas silencing Mime or Marge had weaker effects", and
  "bitter suppression of Roundup and MN9 was abolished by silencing Scapula but not Mime
  or Marge". **PRELIMINARY** (abstract read; the two sentences are unverified excerpts).
  If they hold, **our Phase 5 silencing result was published first there**. Two
  consistency notes:
  - "Marge" is FlyWire CB0812 in the model's reference list of named neurons. It was our
    rank-5 candidate, and silencing it alone gave at most 10% recovery. That fits "weaker
    effects".
  - "Mime" is predicted acetylcholine in snapshot 630, so the standard model cannot use
    it as a direct brake. We could not see how that paper treated it.
- **Shiu et al. 2024** (the model paper) mentions Scapula only in the Phantom -> Scapula
  -> Roundup explanation above, not as the bitter brake. Its bitter experiments name no
  inhibitory neurons. **VALIDATED.**

### 2c. Experiments in real flies

- **None on Scapula itself was found**: no genetic line, silencing or activation. Among
  fly taste papers, the Europe PMC full-text index finds "Scapula" only in Shiu 2022,
  Shiu 2024 and Tastekin 2025. Jacobs 2024 is not in that index. **PRELIMINARY** (absence of evidence).
- **Bohra et al. 2018** found "a single bilaterally homologous pair of bitter-sensitive
  interneurons ... in the subesophageal zone" that "receive specific synaptic input from
  bitter-sensitive gustatory receptor neurons". Activating them "can largely suppress
  the proboscis extension reflex to appetitive stimuli, such as sugar and water".
  According to the preprint extract, they called them bGLNs (driver line VGN6341), their
  arbors lie entirely in the SEZ, and silencing them raised proboscis extension to
  sucrose + quinine from 5% to 25% of trials. This matches the kind of cell Scapula is
  (one pair, SEZ-local, direct bitter input, stops feeding), but **no source links bGLNs
  to Scapula or CB0219: UNVERIFIED.** If they are the same cells, that experiment is the
  real-fly test, and it shows a partial effect, not a 98% one.

### 2d. Known ways bitter stops sugar feeding, and where CB0219 fits

| Mechanism | Source | In our model? | CB0219's role vs this |
|---|---|---|---|
| Central brake at the premotor neurons through a glutamate bitter neuron (Scapula) | Shiu 2022 (wiring + imaging) | yes | **the same thing** |
| Several central routes at third- and fourth-order sugar neurons (Scapula, Mime, Marge; names from excerpts) | Jacobs 2024 (simulation + optogenetics) | yes | consistent: Scapula dominates the MN9 branch (PRELIMINARY) |
| GABA neurons turn down sugar GRN output at the axon terminals (GABA_B receptors on sweet GRNs); "both sweet and bitter stimuli evoke GABAergic neuron activity" near the terminals | Chu et al. 2014 (abstract) | no (no GABA_B, no presynaptic inhibition) | not contradicted; missing from the model |
| Bitter chemicals inhibit sugar detection at the sensillum ("dual mechanism") | French et al. 2015 (abstract) | no (we stimulate neurons, not chemicals) | missing |
| Electric-field ("ephaptic") coupling in the sensillum: sweet GRNs suppress neighbouring bitter GRNs, not the reverse, giving "sweetness dominance" | Lee et al. 2025 (abstract) | no | missing, and it pushes the other way (favours sugar) |
| One pair of bitter local interneurons that suppress proboscis extension | Bohra 2018 | maybe (if = Scapula) | possibly the same cells (unverified) |

**Verdict: consistent with the literature; nothing contradicts it; nothing new except
detail.** The new detail is only quantitative:
- the left cell carries the brake (98% recovery) and the right one barely (9%); the left
  cell is on the same side as the stimulated bitter GRNs;
- the recovery shrinks to 55% at bitter 200 Hz;
- it holds at synapse strengths of 80-120%.

### 2e. What this means for our model

- CB0219 should be called **Scapula (FlyWire CB0219; male CNS GNG087)** in our docs.
- The result counts in the model's favour: it reproduces a published circuit prediction
  from the wiring alone.
- The "one neuron does 98% of the job" figure is almost certainly an overestimate for a
  real fly. The model sends all of bitter's effect through central synapses. Real flies
  add presynaptic, peripheral and electric-field mechanisms (table above). The only
  related real-fly silencing (Bohra's bGLNs) gave a partial effect. The testable
  prediction left open is: *silencing Scapula in a real fly should weaken, but probably
  not abolish, bitter suppression of proboscis extension to sugar*.
- The glutamate = inhibition assumption stays a caveat. Both brains predict glutamate,
  but no stain or receptor data were found.

---

## 3. Finding 2: the runaway

### 3a. Has anyone reported it?

- **The paper and its code:** Shiu et al. 2024 (both versions) do not mention runaway,
  self-sustained or seizure-like activity, or any smell (ORN) experiments. The paper's
  GitHub repository has 10 issues and pull requests (newest 2026-09-15); none is about
  runaway. **VALIDATED.**
- **The model author's own review** (State of Brain Emulation Report 2025, co-written by
  Philip Shiu) does not mention runaway. As an open gap it lists: "There still has not
  been a full Drosophila brain simulation in which all neurons would be active at least
  at their spontaneous levels". **VALIDATED.**
- **An independent public report of the same state.** The GitHub project
  *Jadog1122/fly-with-a-real-brain* (created 2026-09-12; it uses the Shiu model on
  snapshot 783 in Brian2) writes in its README:
  - "Olfaction cannot reach a behaviour in this model, at any setting. All 53 glomeruli
    give the same answer: ~8,300 neurons active".
  - "the network is bistable, and below the tipping point nothing reaches the
    descending neurons at all".
  - Scaling the synapse strength down (0.6, 0.35, 0.2) "moves the threshold without
    ever opening a window where different odours drive different behaviour".
  - "We did not localise the runaway". Silencing every Kenyon cell's output changed 8,324
    active neurons to 7,894.

  It is not peer-reviewed, and we did not reproduce it. It matches ours closely: the
  same ~8,300 neurons, the tipping behaviour, and Kenyon cells as passengers. It also
  suggests the state exists in **snapshot 783**, which our runaway doc lists as untested.
  **VALIDATED** that the README says this; the claim itself **UNVERIFIED**.
- **A port to the male CNS** (*Kisame76/drosophila-brain-mlx*, Shiu's equations and
  constants, measurements dated 2026-09-15) reports a self-sustaining state in the
  abdominal nerve cord after sweet-taste input. After the input is switched off at 500
  ms, 25 of 30 trials keep going. It also says DM1 smell input leaves "1,170 neurons ...
  above 100 Hz" in the brain. This is a related instability in a different wiring
  diagram and a different place. It was not traced to a cause. **UNVERIFIED** (README
  only).
- **Modellers who expected instability:**
  - Wang et al. 2025 (Sandia; the model on the Loihi 2 chip) gave every neuron
    background firing, and wrote: "to prevent potential runaway excitation, we set the
    weight scaling factor ... such that the effects of the incoming spikes would be
    negligible". **VALIDATED** (full text).
  - Pospisil et al. 2024 (the "effectome", a straight-line model of the same wiring): "W
    was scaled to have a maximum eigenvalue of 1", because "if it was too large the
    dynamics would be unstable". The leading circuits they describe are visual and
    central-complex ones; we did not see the antennal lobe among them. **PRELIMINARY**
    (automated extract).
  - Li, Ping, Zhang & Wang 2026 (bioRxiv; a FlyWire model fitted to real resting
    activity): "a highly sparse, brain-spanning ensemble of inhibitory hub neurons and
    their reciprocal synapses with excitatory partners are necessary and sufficient to
    sustain whole-brain resting-state dynamics" (abstract). A search excerpt adds that
    "Silencing one inhibitory hub releases its excitatory partner into runaway
    activity"; the hub types it names (MBON06, LPi13, LPi15) are not in the antennal
    lobe. **PRELIMINARY / excerpt UNVERIFIED.**
  - Bossard et al. 2026 and Jin et al. 2026 cite the model; neither mentions runaway.
- **Not checked:** Sapkal et al. 2024 (a companion paper that used the model for
  halting), the FlyWire forum, and any talk or poster.

### 3b. Are FlyWire's transmitter guesses for these local neurons known to be wrong?

- **Confirmed: Eckstein et al. 2024**, the paper behind the guesses (read in full by the
  Phase 7 audit lane): "many first-order sensory neurons and antennal lobe local neurons
  were mispredicted for serotonin rather than acetylcholine". About lLN2T: "~13 lLN2T_abc
  neurons ... most similar to reported cholinergic local neurons. The remainder is most
  likely GABAergic". **VALIDATED** (quoted in docs/phase7-neurotransmitter-audit.md).
- **FlyWire's own guesses for these types are weak and mixed.** From the v783 annotation
  table (our count):
  - lLN1_bc (30 cells): 11 acetylcholine, 12 dopamine, 7 serotonin, mean confidence
    about 0.3;
  - lLN2T_b (4), lLN2T_c (4) and lLN2X03 (6): all serotonin, confidence about 0.35.

  **VALIDATED** (direct count).
- **New: the male CNS guesses agree with the audit.** Male CNS predictions (Berg et al.
  2025), read through Virtual Fly Brain:
  - lLN1_bc: **30 of 30 cells acetylcholine** (mean confidence 0.79 left, 0.71 right);
  - lLN2T_a: 5 of 6 acetylcholine; lLN2T_c: 4 of 4; lLN2T_e: 4 of 4; lLN1_a: 2 of 2;
  - lLN2T_b: 2 acetylcholine (left) and 2 GABA (right, confidence 0.51).

  VFB also files the lLN1_bc cells under the class "cholinergic local interneuron of
  the adult antennal lobe". **PRELIMINARY** (database records; the male CNS paper's
  method was not read).

### 3c. What this means for our model

- The runaway is **not a secret**: at least one other user has hit it and published a
  description. It has **not been explained** anywhere we looked. The explanation in
  docs/phase6-runaway-activity.md and the "al_ln_literature" fix in
  docs/phase7-neurotransmitter-audit.md appear to be new. They are also the useful part:
  - the cause is a chemical excitatory loop through the antennal lobe's excitatory local
    neurons;
  - the fix keeps these cells excitatory but routes their chemical output only to
    inhibitory neurons, and it leaves the paper's taste results spike-for-spike
    unchanged.
- The transmitter literature now has two machine-learning sources (Eckstein's own
  caveat, and the male CNS predictions) plus the antibody work (Shang et al. 2007)
  pointing the same way: **excitatory**. So the model's sign for these cells is right,
  though only by accident: serotonin and dopamine count as excitatory in the model. The
  runaway is about *how* these cells excite (chemical vs electrical synapses, Yaksi &
  Wilson 2010), not about their label. The fix follows that reading. Huang et al. 2010
  (abstract only) still disputes it.
- The male CNS calls 2 of the right lLN2T_b cells GABA. That fits Eckstein's remark that
  some lLN2T may be inhibitory. If those cells really are GABA cells, our fix treats them
  wrongly: as excitatory cells that talk only to inhibitory neurons. It still cannot
  re-create the runaway loop, because it gives them no chemical excitation onto
  excitatory cells.

**Verdict: PARTLY KNOWN.** The phenomenon has been seen publicly (not peer-reviewed). The
cause and the fix were not found in any source.

---

## 4. Finding 3: the left/right imbalance

### 4a. What the FlyWire papers say about left and right

- Schlegel et al. 2024: "The fly brain is mostly left–right symmetric, but inspection of
  the FlyWire dataset revealed a small number of asymmetries". Only 0.4% of central-brain
  neurons show biological oddities such as a wrong route or a missing branch. "About one
  in six cell types shows a difference in numbers between the left and right
  hemisphere". Edge weights (synapses between two cell types) correlate R = 0.97 between
  the two sides of FlyWire. **VALIDATED.**
- The same paper says part of the left/right difference is **technical**:
  - Completion (the share of synapses attached to proofread neurons) differs by region
    and side. Their example: "in the mushroom body calyx ... there is a 6% difference
    between the left and right hemisphere".
  - Sample artefacts: "A small number of neurons exhibit a dark, almost black cytosol",
    which "leads to worse synapse detection". "Anecdotally, this appears to happen at a
    much higher frequency in sensory neurons compared with in brain-intrinsic neurons".
    Their example is an antennal-lobe PN: "the cytosol in the axons of DM3 adPN is dark
    on the left and normal light on the right". (DM3 is one of our non-mirroring
    glomeruli, with its left side smaller.)
  - "Some neurons are missing large arbours ... This typically happens in commissures".
    ORN axons cross to the other antennal lobe through such a commissure.

  **VALIDATED** (full text).
- Dorkenwald et al. 2024: only 44.7% of postsynapses are attached to proofread neurons
  overall. Attachment rates "were generally in agreement between the two hemispheres ...
  and varied by neuropil". **VALIDATED.** The per-region, per-side rates are in figure
  panels we could not read as text. **UNVERIFIED** for the antennal lobe specifically.

### 4b. Antennal-lobe wiring papers

- Tobin, Wilson & Lee 2017 (DM6, electron microscopy of both sides): the total ORN -> PN
  input was similar on the two sides. Gruber et al. 2025 sum it up as: "the differences
  in number of innervating uPNs between the left and right DM6 glomeruli are compensated
  by differences in synaptic strength". **VALIDATED** (as cited in our steering doc and
  in Gruber 2025).
- Schlegel et al. 2021 (hemibrain): "the total number of ALPNs is largely consistent
  across brains as well as across hemispheres of the same brain". The hemibrain
  recovered only about 70% of ORNs per glomerulus. **VALIDATED.**
- Gruber et al. 2025 (two more glomeruli, DA2 and DL5, by electron microscopy): "not all
  glomeruli appear to have the same degree of lateralized OSN connectivity";
  narrowly tuned glomeruli are less lateralized. They cite Agarwal & Isacoff 2011: in
  females, DA1 PNs "are evenly activated by either ipsi- or contralateral antennal
  stimulation". **VALIDATED** that Gruber says this; the Agarwal & Isacoff paper was not
  read. This is a possible tension with DA1 being the one channel that steers correctly
  in our model, since FlyWire is a female brain. (Taisz et al. 2023 did find DA1
  left/right coding in FlyWire, so the two papers may measure different things.) The
  steering lane may want to look at it.
- Gaudry et al. 2013, which used **DM1** (Or42b ORNs):
  - "Illuminating one antenna produced a turn toward the stimulus" in flies whose DM1
    ORNs carry a light-gated channel;
  - same-side synaptic currents were 39% larger;
  - "the number of unitary ORN-to-PN synaptic connections is essentially identical on
    the ipsi- and contralateral sides".

  **PRELIMINARY** (automated extract of the full text).

### 4c. DM1, and ORN counts per glomerulus

- **No published source reports a left/right imbalance for DM1** in FlyWire or any other
  dataset. **PRELIMINARY** (absence of evidence).
- **ORN numbers do not explain it.** From Schlegel et al. 2024's annotation table (the
  supplementary file our project already uses):
  - FlyWire has 1,116 left and 1,132 right ORNs (29 unassigned);
  - **DM1 has 35 left and 33 right ORNs** (one left ORN flagged as a biological
    outlier; none flagged as a reconstruction artefact).

  Yet the left DM1 PN gets 52% more ORN synapses (3,724 vs 2,450, docs/phase6-steering.md
  section 2). Across the 53 glomeruli of snapshot 783, the left/right synapse imbalance
  follows the left/right ORN-count imbalance only weakly (correlation 0.16). The
  imbalance is in **synapses per ORN**, not in ORN numbers. **VALIDATED** (counts);
  interpretation **PRELIMINARY**.

### 4d. What this means for our model

A 52% difference in DM1 is far larger than what Tobin et al. found for DM6. The FlyWire
authors themselves name several mechanisms that make one side lose synapses: completion
that differs by side, dark sensory axons, and branches lost in the commissure. So "one
side of this reconstruction lost DM1 synapses" is at least as likely as "this fly's
left DM1 really is bigger". Neither can be settled from the literature. The direct test
is a second brain (the BANC lane). Behaviour gives a clear standard: real flies turn
toward a one-sided DM1 signal, so the model's DM1 steering contradicts biology, and
PLAN.md says to suspect the model or the data first.

**Verdict: PARTLY KNOWN.** Left/right variability and side-specific technical noise in
FlyWire are documented. The DM1 case, and the count of 19 of 51 glomeruli that fail at
the first synapse, are not reported anywhere we looked.

---

## 5. Worth telling anyone? (recommendation only; nothing has been sent)

Finding 1 is not worth sharing as news. It is the published Scapula circuit (Shiu et al.
2022), and apparently the same model result as Jacobs et al. 2024. Our docs should adopt
the name. The one open question worth mentioning to anyone is the real-fly test of
Scapula. That is an experiment for a fly lab, not a modelling result.

Finding 3 should wait for the BANC comparison. If the second brain's DM1 is symmetric,
the result is a practical caution for anyone using FlyWire's antennal lobe for left/right
work. The FlyWire authors already warn about sensory-neuron artefacts in general, so it
would be a caution, not a discovery.

Finding 2 is the one worth telling, and the natural audience is the model's authors: an
issue on their GitHub repository, or a note. Whether and how is the author's call (PLAN.md
Phase 6 step 6). At least one other user has already hit the runaway and could not explain it.
Our cause and our literature-based fix, which leaves the paper's taste results unchanged,
would save the next person the same dead end. Before anything is sent:
1. Re-run the runaway and the fix on snapshot 783. The public report says the state is
   there too.
2. State plainly that it is a report about the model, not about flies, and that the
   literature behind the fix is disputed (Yaksi & Wilson 2010 vs Huang et al. 2010).

---

## 6. What was not verified

- **Jacobs et al. 2024 full text.** The publisher (Cell Press) and bioRxiv both refused
  automated access (403 / 429 errors). Their Scapula/Mime/Marge sentences are
  search-engine excerpts. How they treated Mime (acetylcholine in FlyWire) is unknown.
- **The old-to-new root-ID step** for Shiu 2022's Scapula ID (needs a FlyWire login). The
  identification rests on shape, ontology and wiring (section 2a).
- **Bohra et al. 2018** was read as the abstract plus an automated extract of the
  preprint. Its bGLN transmitter was not established, and neither was any link to
  Scapula.
- **Tastekin et al. 2025/2026** (the male taste connectome) mentions Scapula, according to
  the Europe PMC index, but the passage was not found or read.
- **Pospisil et al. 2024, Gaudry et al. 2013 and the Shiu 2022 quotes** came through an
  automated extraction of the full text, not a reading of every page. Chu 2014, French
  2015, Lee 2025, Berg 2025, Li 2026 and Jacobs 2024 were read as abstracts only.
- **The GitHub READMEs** are not peer-reviewed, and we did not reproduce their numbers.
- **The antennal lobe's own left/right completion rates** (Schlegel 2024 Extended Data
  Fig. 6; Dorkenwald 2024 Supplementary Fig.) are in figure panels that were not readable
  as text.
- **Search scope.** Europe PMC, PubMed Central, arXiv, GitHub, Virtual Fly Brain and
  general web search. Not searched: paywalled journals beyond their abstracts, the
  FlyWire forum, conference abstracts, and Google Scholar. "Not found" means "not found
  in these", not "does not exist".

**Small corrections for other docs (for the main session; this lane did not edit them):**
- docs/phase5-competition.md, section 8, cites "French et al. 2015, *J. Neurosci.*
  35:9542". The paper is *J Neurosci* 35(9):3990-4004 (doi:10.1523/JNEUROSCI.1312-14.2015);
  a correction to it appeared at 35:7655.
- docs/phase5-competition.md, section 8, "Is CB0219 a known neuron?", and
  docs/phase5-sugar-pathway.md, item C ("We could not find a Scapula ID"): CB0219 is
  Scapula (section 2a here).
- docs/phase6-runaway-activity.md, section 5, "this has not been reported": one public,
  non-peer-reviewed report exists (section 3a here).

## 7. Files

- This document: `docs/phase6-literature-check.md`.
- Log entry for EXPERIMENTS.md: `experiments/phase6_litcheck/log-entry.md`.
- No code or data files were changed. The look-ups used, read-only:
  - `data/flywire/Supplemental_file1_annotations_v1.1.0_630.tsv` and
    `Supplemental_file1_neuron_annotations.tsv` (cell types, sides, transmitter guesses,
    status flags);
  - `data/reference/2023_03_23_connectivity_630_final.parquet` (CB0219's inputs and
    outputs);
  - `data/reference/sez_neurons.pickle` (the model repository's named SEZ neurons);
  - `data/flywire/proofread_connections_783.feather` (where CB0219's synapses sit);
  - `experiments/phase6/steering/results/glomerulus_map_783.csv` (per-glomerulus
    counts).

  The short look-up script was kept outside the repository and is not needed to read
  this document.
