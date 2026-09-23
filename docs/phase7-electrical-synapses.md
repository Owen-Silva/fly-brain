# Phase 7, item 5: electrical synapses (gap junctions)

*Written 2026-09-23. Code: `sim/gap_junctions.py`, tests `tests/test_gap_junctions.py`.
Scripts, tables and plots: `experiments/phase7_gap/` (pair list
`results/coupling_table.csv`, literature table `results/evidence_table.csv`, calibration
`results/calibration.json`, raw trials `results/trials.csv`, summary tables
`results/table_*.csv`, plots `plots/`). Status: **PRELIMINARY** (section 9).*

## 1. The short version

- **What was added.** Electrical connections (gap junctions) in the antennal lobe, only
  between cell types where recordings measured them: each of the 44 excitatory local neurons
  (eLNs) with the projection neurons of every glomerulus it touches (7,371 pairs; measured
  coupling about 1.3%, Yaksi & Wilson 2010, Huang et al. 2010), and projection neurons of the
  same glomerulus with each other (703 pairs; about 1.6%, Kazama & Wilson 2009). The strength
  is set so that the model, probed the way the experiments probed the flies, gives those
  measured numbers. It sits on top of the recommended sign fix `al_ln_literature`.
- **What did not change.** The taste checks of Phase 3: all 450 taste trials give exactly the
  same spike totals and MN9 rates. No runaway activity in any trial (0 of 90 for every input
  and strength tried). Kenyon cells: 3.6% respond to DM1, as before. DA1 (cVA) steering
  still points the right way for both sides.
- **What did change.** The eLNs are each joined to about 170 cells that mostly sit at rest,
  which drains their current, so they go nearly silent (16.9 -> 2.3 Hz for a DM1 smell). The
  smell's own projection neurons fire somewhat less. The lateral excitation that real eLNs
  spread to other glomeruli does **not** appear.
- **Does it fix the one-sided DM1 steering?** **No.** A right-side DM1 smell still gives a
  "turn left" signal (+5.8 Hz). The signal does now depend on the smell's side (a left smell
  gives +15.8 Hz; one-trial separability d' 0.2 -> 2.6). But a control run shows why:
  silencing the eLNs' output with no junctions at all gives the same pattern, only stronger.
  The change comes from the eLNs going quiet, not from electrical excitation reaching the
  projection neurons.
- **Verdict.** Keep it as an optional switch, not the default. Every result is
  **PRELIMINARY** (section 9). The same conclusions hold at half and double strength
  (section 7).

---

## 2. What an electrical synapse is, and why the model has none

Most connections between neurons are chemical: a spike makes the sending cell release a
transmitter, which excites or inhibits the receiving cell after a short delay. Some neurons
are also joined by **electrical synapses** (gap junctions): small pores that connect the
insides of the two cells. Current then flows from whichever cell has the higher voltage to
the other one, in both directions and with no delay. When one cell fires, its partner sees a
small bump called a "spikelet".

The wiring diagram (FlyWire) is made from electron-microscope images, which show chemical
synapses but not gap junctions. So the model has none. PLAN.md Phase 7 item 5 says to add
them "only where there's evidence". This upgrade is built on top of the recommended sign fix
`al_ln_literature` (docs/phase7-neurotransmitter-audit.md), which removed the chemical
synapses from excitatory antennal-lobe local neurons onto projection neurons *because* the
recordings say those cells reach projection neurons electrically. Adding the electrical
connections back is the second half of that same fix.

## 3. The evidence (PLAN.md Phase 6 step 3)

**What was read.** Full text (NCBI/PMC): Yaksi & Wilson 2010 (Neuron 67:1034, PMC2954501)
and Kazama & Wilson 2009 (Nat Neurosci 12:1136, PMC2751859); their bar charts were viewed as
images (Yaksi & Wilson Fig. 4 and 6 from the publisher's image server; Kazama & Wilson Fig. 7
from PMC's open-data store). Huang et al. 2010 (Neuron 67:1021): **abstract and figures only**
(the text is behind the publisher's bot check; figure 3 was viewed as an image, its legend
was not available). Liu et al. 2016 (eLife 5:e13238): full text searched for coupling data.
**Abstract only:** Wu et al. 2011 (Curr Biol 21:848), Shyu et al. 2019 (PLoS Genet
15:e1008153), Ammer et al. 2022 (Curr Biol). All numbers below that come from bar charts
were **read by eye** (about +/-0.002 on a coupling coefficient).

A **coupling coefficient** is what the experimenters measured: inject a steady current into
one cell and divide the voltage change in the partner by the voltage change in the injected
cell. 0.01 means the partner moves 1% as much.

| Cells | What was measured | Numbers | Source | Used? |
|---|---|---|---|---|
| excitatory local neuron (eLN) -> projection neuron (PN), antennal lobe | coupling coefficient, depolarizing step (the eLN fires during it) | **0.010** control, **0.014** with chemical transmission blocked (Cd2+), about 0 in the gap-junction mutant *shakB2* (37 control, 19 mutant pairs) | Yaksi & Wilson 2010 Fig. 4C | yes |
| eLN -> PN | same, hyperpolarizing step | about 0.0025 | Yaksi & Wilson 2010 Fig. 4C | reported only |
| PN -> eLN | coupling coefficient | depolarizing 0.032 control but 0.005 with Cd2+ (mostly chemical); hyperpolarizing about 0.006 / 0.004 | Yaksi & Wilson 2010 Fig. 4F | used as a check |
| eLN <-> PN | "electrical coupling ratio" | eLN->PN depolarizing **0.015**, hyperpolarizing 0.007; PN->eLN 0.008 / 0.010 | Huang et al. 2010 Fig. 3D (figure only) | yes (0.015) |
| eLN -> PN | PN response to one eLN spike (spike-triggered average) | about 0.1-0.7 mV per pair; about 60% of the rise comes *before* the spike (shared input), part is chemical | Huang et al. 2010 Fig. 3E-K | check only |
| eLN -> all PNs | how many pairs are connected | "we performed 74 dual recordings ... of which 37 showed an excitatory LN-PN connection"; every eLN tested was connected, "implying that each eLN is connected to most or all PNs" | Yaksi & Wilson 2010 | yes (the pairing rule) |
| sister PNs (same glomerulus, same side), DM6 | coupling coefficient | hyperpolarizing about 0.013; depolarizing about 0.034 control, **0.016** with Cd2+ (the electrical part); "Coupling is negligible between heterotypic PN pairs" | Kazama & Wilson 2009 Fig. 7b,d | yes (0.016) |
| sister PNs, DA1 | coupling coefficient | depolarizing about 0.018, hyperpolarizing about 0.008; about 0 in *shakB2* | Yaksi & Wilson 2010 Fig. 6C | supports |
| eLN -> inhibitory LN | "largely chemical with a smaller electrical component" | no usable number; which FlyWire types these iLNs are is unknown | Yaksi & Wilson 2010 | no |
| eLN <-> eLN | "Reciprocal connections were also found between two krasavietz eLNs" | electrical or chemical not stated in the abstract | Huang et al. 2010 abstract | no (**UNVERIFIED**) |
| APL <-> DPM (mushroom body) | innexin proteins found in both cells; knocking them down impairs one kind of memory | no strength measured | Wu et al. 2011 (abstract) | no |
| Kenyon cells with each other; Kenyon cells with MBON-b'2mp | dye passes between cells ("In 10 out of the 14 brains, dye coupling was observed between the same subtype of KCs") | no strength; which of about 5,000 Kenyon cells is not known | Liu et al. 2016 | no |
| VS/HS visual cells | removing the gap-junction gene makes them oscillate | partners and strengths not in the abstract | Ammer et al. 2022 (abstract) | no (**UNVERIFIED**) |

Quotes that decide the design (Yaksi & Wilson 2010): "eLN-to-PN synapses transmit both
hyperpolarization and depolarization, are not diminished by blocking chemical
neurotransmission, and are abolished by a gap junction mutation"; "although these
coefficients are small, they almost certainly underestimate the strength of the connection
at the synapse. This is because both electrodes are located at the soma"; "depolarizing
signals were transmitted more effectively across this electrical connection than were
hyperpolarizing signals". And one that matters for the steering question: "wild-type DM1 PNs
consistently showed smaller lateral excitation", which the authors read as "weaker coupling"
of DM1 to the eLN network. We could not turn that into a number, so DM1 PNs get the same
strength as every other glomerulus (an assumption).

**Why only the antennal lobe.** It is the only place with measured strengths *and* cells that
can be matched to FlyWire types. The mushroom-body and visual couplings are real but either
have no strength (any number would be invented) or no way to say which of thousands of cells
are joined. They are listed, not added.

## 4. Which cells get connected

FlyWire has no gap junctions, so the partners have to be chosen by a rule. The rules:

- **eLNs:** the 44 local neurons that FlyWire's literature column lists as acetylcholine,
  citing Shang et al. 2007 (30 lLN1_bc, 8 lLN2T_b/c, 6 lLN2X03; the same set as
  `sign_fixes.eln_mask`). These are the cells the recordings were made from (krasavietz
  eLNs), matched by the annotators on shape and position. The other 93 local neurons that
  `al_ln_literature` also treats as excitatory get **no** electrical synapses: nobody has
  recorded from them.
- **Uniglomerular PNs (uPNs):** a PN belongs to glomerulus G if at least half of its smell-
  receptor (ORN) synapses, and at least 20 of them, come from G's receptors (the same rule as
  the Phase 6 steering lane, `experiments/phase6/steering/s1_anatomy.py`). 335 of the 685
  PNs qualify, in 51 glomeruli. Multiglomerular PNs get no electrical synapses.
- **eLN - PN pairs:** an eLN "innervates" a glomerulus if it and that glomerulus's uPNs (same
  side) share at least 5 chemical synapses, in either direction. Chemical synapses show where
  two membranes touch, and a gap junction needs touching membranes. The eLN is then coupled
  to *every* uPN of that glomerulus. Result: 7,371 pairs; each eLN innervates a median of 51
  glomeruli and is coupled to a median of 170 uPNs (96% on its own side); each uPN has a
  median of 22 eLN partners. This matches "each eLN is connected to most or all PNs". DM1:
  21 eLNs on the left, 23 on the right, 4 uPNs on each side, so the rule itself adds no
  left/right imbalance.
- **Sister PNs:** every pair of uPNs with the same glomerulus and the same side: 703 pairs in
  78 glomerulus-sides that have two or more uPNs (DA1 has 9 per side). Different glomeruli
  are not coupled.

Total: 8,074 coupled pairs. Every row of `results/coupling_table.csv` names its class, both
cells, the glomerulus, the contact count, the strength and the papers.

## 5. Turning a measured coupling coefficient into model numbers

The model neuron has no capacitance or resistance. Its voltage follows
`dv/dt = (v_0 - v + g) / 20 ms`, where the synaptic input `g` is already in millivolts. A
real neuron with leak conductance g_L obeys the same equation with `g = I / g_L`. A gap
junction with conductance g_gap carries `I = g_gap x (v_partner - v_self)`, so in the model it
adds

    kappa x (v_partner - v_self)      where kappa = g_gap / g_L

inside the bracket. **kappa is "the junction's conductance as a fraction of the cell's own
leak conductance"**, a plain number. For two cells alone, coupling coefficient = kappa / (1 +
kappa), so kappa = 0.01 gives 0.0099.

In the brain each cell has many junctions, which "load" it and shrink the coupling
coefficient. So the calibration (`gap_junctions.calibrate_kappa`) does in the model what the
experimenters did: inject a steady current into one cell of the full coupled network and
measure the ratio. It picks, for each class, the one kappa that makes the median ratio equal
to the measured value:

| Class | Target coupling coefficient | kappa found | Same kappa, two cells alone |
|---|---|---|---|
| eLN -> uPN | 0.013 (mean of 0.010, 0.014, 0.015) | **0.0145** | 0.0142 |
| sister uPNs | 0.016 (Kazama & Wilson, electrical part) | **0.0197** | 0.0193 |

Checks against numbers that were *not* used in the calibration: the model's coefficient in
the other direction, PN -> eLN, comes out at **0.0053**; measured: 0.004-0.006 (Yaksi &
Wilson, electrical) and 0.008-0.010 (Huang et al.). So it lands inside the measured range.
The price: each eLN, joined to about 170 PNs, has 2.5 times its leak conductance in junctions,
so its total input conductance grows 3.5-fold (a uPN's grows 1.4-fold). In a real eLN the
measured whole-cell properties already include this load; the model gives every neuron the
same generic settings, so this cannot be checked against an eLN measurement.

**Spikes.** The model's spike is not a voltage bump (the voltage just jumps from threshold
back to reset), but a real spike briefly drives the cell's voltage far up and pushes charge
through the junction. Each spike therefore adds `kappa x (spike area) / 20 ms` to every
partner, where the spike area is its height times its width. Height 40 mV (Yaksi & Wilson:
"full-sized spikes (~40 mV amplitude)"), width 1 ms (**ASSUMED**, not from a paper). That is
0.029 mV per eLN spike in each PN partner and 0.039 mV between sisters. The spike-triggered
average in Huang et al. is 0.1-0.7 mV, but most of it starts before the spike and part of it
is chemical, so it cannot be compared directly; the model's per-spike effect is probably at
the low end.

**What the model cannot do.** The recordings show depolarization crossing better than
hyperpolarization (rectification); the model's junction is symmetric. Calibrating to the
depolarizing numbers means hyperpolarization is transmitted 2-5 times too well. The recordings
are made at the cell body, which Yaksi & Wilson say underestimates the junction; the model has
only one "cell body", so the measured number is the right one for it, but the 2x run
(section 7) shows what a stronger junction would do.

**Numerics.** Inside each 0.1 ms step the junction current is held at its value from the
start of the step and added like a constant current. A cell in its refractory period ignores
junction current and spikelets (as it ignores chemical input), but still pushes current into
its partners. A silenced cell has no effect on anyone, through junctions either. With no
junctions (or all at strength 0), the new compiled loop does exactly the old arithmetic.

**Tests** (`tests/test_gap_junctions.py`): no junctions = the old engine spike for spike and
voltage for voltage (3 random networks); junctions of strength 0 = the same; two coupled cells
give kappa/(1+kappa) to 6 digits (kappa 0.013, 0.1, 0.5); an uncoupled cell does not move; one
spike adds exactly kappa x 40/20 mV to the partner; a silenced cell does not move its partner;
a refractory cell stays frozen; the calibration hits its targets; and (slow) on the whole brain
the table has 7,371 + 703 pairs, every row has a source, and junctions at strength 0 reproduce
the `al_ln_literature` brain spike for spike on a 2-trial DM1 smell run.

## 6. What the upgrade does (1x strength vs `al_ln_literature`; PLAN.md Phase 6 step 1)

Same checks, seeds and trials as the sign-fix lane: 3 seeds x 30 one-second trials per
condition. The `al_ln_literature` numbers are the ones already in
`experiments/phase7_signs/results/trials.csv` (and, for DA1,
`experiments/phase6/steering/results/sim/`).

**First, a check that the comparison is fair** (`results/identity.txt`). This lane's brain,
run with the old engine, gave exactly the stored `al_ln_literature` numbers in 90 of 90
compared trials (spike totals, active neurons, MN9, Kenyon cells, DNa02), and the 20 DA1
trials matched the steering lane's files. The new engine with every junction set to 0 gave
exactly the old engine's numbers in all 110 compared trials. So every difference below is
caused by the junctions and nothing else.

### 6a. Phase 3 taste results (MN9, the feeding motor neuron, Hz)

| Condition | al_ln_literature | + junctions | expected |
|---|---|---|---|
| sugar 100 Hz | 67.28 | 67.28 | paper 65.7 +/- 3.3 |
| sugar 200 Hz | 93.53 | 93.53 | higher than 100 Hz |
| water 200 Hz | 30.79 | 30.79 | MN9 active |
| bitter 200 Hz | 0.00 | 0.00 | 0 |
| sugar 100 + bitter 120 | 1.36 | 1.36 | near 0 |

Every one of the 450 taste trials has the same spike total as before. The taste-to-feeding
pathway never reaches the coupled smell cells, which sit exactly at rest, so no junction
current flows. **The Phase 3 result holds.**

### 6b. Runaway, Kenyon cells

| | al_ln_literature | + junctions |
|---|---|---|
| runaway, Ir94e 200 Hz | 0 / 90 | 0 / 90 |
| runaway, DM1 150 Hz both / left / right | 0 / 90 each | 0 / 90 each |
| runaway, DA1 150 Hz left / right | not stored (0 of 10 checked) | 0 / 90 each |
| Kenyon cells firing per trial, DM1 both sides | 3.62% | 3.61% |
| same, DM1 left only / right only | 2.17% / 2.11% | 2.30% / 2.14% |

Runaway is the Phase 6 definition (more than 1,500 different neurons firing in some 10 ms
slice). Real flies: roughly 5-10% of Kenyon cells respond to one odour (background knowledge
carried over from Phase 5, not re-read). No change that matters.

Ir94e detail: 71 of 90 Ir94e trials have exactly the same spike total as before. In the
other 19, one projection neuron or eLN fires a single spike without junctions, and with
junctions it does not: the extra junction conductance keeps that cell just below threshold.
That one missing spike then changes the rest of the brain's activity by between 1 and about
3,100 spikes (median about 20; a trial has about 7,800), in the same way at every strength.
Checked by re-running five of these trials with the old engine and with the new one at
strength 0, 1 and 2 (`results/check_ir94e.txt`). Runaway stays at 0.

### 6c. Inside the antennal lobe (mean rates, Hz, `results/table_antennal_lobe.csv`)

| Smell input | Cells | al_ln_literature | + junctions |
|---|---|---|---|
| DM1 both sides | the 44 eLNs | 16.9 | **2.3** |
| | DM1 uPNs left / right | 91.1 / 72.7 | 72.4 / 58.7 |
| | all other uPNs ("lateral excitation") | 0.15 | 0.14 |
| DM1 left only | eLNs | 14.6 | 1.7 |
| | DM1 uPNs left / right | 54.3 / 42.6 | 52.8 / 42.7 |
| DM1 right only | eLNs | 8.5 | 1.2 |
| | DM1 uPNs left / right | 55.9 / 44.8 | 48.6 / 44.1 |
| DA1 left only | DA1 uPNs left / right | 84.7 / 58.5 | 80.5 / 48.9 |
| DA1 right only | DA1 uPNs left / right | 78.7 / 72.5 | 70.7 / 67.3 |

Three things happen:

1. **The eLNs go almost quiet** (about 7 times fewer spikes). Each eLN is now joined to about
   170 projection neurons that mostly sit at rest, and they drain its current: its input
   conductance is 3.5 times what it was (section 5). The same smell input now depolarizes it
   far less.
2. **The smell's own projection neurons fire somewhat less** (DM1 left PNs 91 -> 72 Hz), for
   the same reason on a smaller scale (their input conductance is 1.4 times what it was).
3. **Lateral excitation does not appear.** The recordings show eLNs spreading excitation to
   the projection neurons of *other* glomeruli (Yaksi & Wilson 2010, Fig. 7: abolished in
   *shakB2*). In the model, the other 309 uPNs stay near silent (0.15 -> 0.14 Hz). One eLN
   spike moves a PN by only about 0.03 mV, and the eLNs hardly fire.

One more detail, which matters for steering: the left DM1 projection neurons now prefer a
left-side smell (52.8 Hz for a left smell vs 48.6 Hz for a right smell). Before, they
preferred the right-side smell (54.3 vs 55.9 Hz), which was part of the Phase 6 problem.

### 6d. Left/right steering (docs/phase6-steering.md; 3 seeds x 30 trials per side)

"turn" = left DNa02 minus right DNa02 (Hz); positive means "turn left". A correct steering
signal is positive for a left smell and negative for a right smell.

| Smell channel | | al_ln_literature | + junctions |
|---|---|---|---|
| DM1 (vinegar) | DNa02 L / R, left smell | 6.7 / 0.9 | 17.5 / 1.6 |
| | DNa02 L / R, right smell | 7.3 / 2.5 | 8.8 / 3.0 |
| | **turn: left smell / right smell** | **+5.7 / +4.8** | **+15.8 / +5.8** |
| | how well one trial tells the sides apart (d') | 0.2 | **2.6** |
| | turn differs between smell sides (p, each seed) | 0.16 / 0.43 / 0.75 | < 1e-8 in all 3 |
| DA1 (cVA) | turn: left smell / right smell | +21.7 / -15.6 | +21.5 / -15.6 |
| | d' | 33.6 | 36.6 |

**Does restoring the eLN-to-PN electrical connection fix the DM1 bias? No.** A right-side
DM1 smell still says "turn left" (+5.8 Hz). What changes is that the turn signal now clearly
depends on the smell's side: a left smell says "turn left" three times as strongly as a
right smell, and one 1-second trial now tells the two apart well (d' 2.6 instead of 0.2).
So the model gains real side information, but it sits on top of the same fixed left offset.
DA1, the one channel that already steered correctly, is unchanged.

## 7. Sensitivity: half and double the junction strength (3 seeds x 30 trials each)

| | al_ln_literature | 0.5x | **1x** | 2x |
|---|---|---|---|---|
| sugar 100 / 200, water, bitter, sugar+bitter -> MN9 (Hz) | 67.28 / 93.53 / 30.79 / 0.00 / 1.36 | identical | identical | identical |
| runaway, every input tested | 0 / 90 (DA1 not stored) | 0 / 90 | 0 / 90 | 0 / 90 |
| Kenyon cells, DM1 both sides | 3.62% | 3.61% | 3.61% | 3.57% |
| eLN rate, DM1 both sides (Hz) | 16.9 | 3.8 | 2.3 | 0.6 |
| DM1 uPNs left / right, DM1 both sides (Hz) | 91.1 / 72.7 | 83.4 / 63.7 | 72.4 / 58.7 | 64.2 / 57.8 |
| other uPNs, DM1 both sides (Hz) | 0.15 | 0.16 | 0.14 | 0.08 |
| DM1 turn, left smell / right smell (Hz) | +5.7 / +4.8 | +11.0 / +6.3 | +15.8 / +5.8 | +13.1 / +5.5 |
| DM1 d' | 0.2 | 1.0 | 2.6 | 1.9 |
| DA1 turn, left smell / right smell (Hz) | +21.7 / -15.6 | +21.6 / -15.4 | +21.5 / -15.6 | +21.6 / -15.4 |

Every conclusion holds at half and double strength: taste results identical (all 450 taste
trials give the same spike total, active-neuron count and MN9 rate at every strength), no runaway, Kenyon cells unchanged, DA1 still
steers correctly, DM1 still says "turn left" for both sides, and the DM1 turn signal
separates the two sides better than before (d' 1.0-2.6). The eLNs go quieter the stronger
the junctions (3.8 -> 2.3 -> 0.6 Hz), and lateral excitation never appears.

## 8. What actually moves the DM1 steering? (diagnostics, DM1 left/right, 3 seeds x 30 trials)

Three extra versions, each changing one thing (`results/table_steering.csv`, plot
`plots/fig4_dm1_diagnostics.png`):

| Version | eLN rate, left smell (Hz) | DM1 turn, left smell / right smell (Hz) | d' |
|---|---|---|---|
| al_ln_literature (no junctions) | 14.6 | +5.7 / +4.8 | 0.2 |
| all junctions (the upgrade) | 1.7 | +15.8 / +5.8 | 2.6 |
| eLN-PN junctions only | 1.8 | +20.1 / +5.4 | 3.7 |
| sister-PN junctions only | 14.4 | +3.4 / +4.7 | -0.3 |
| **no junctions, the 44 eLNs silenced** (their output removed) | 14.4 (no effect on anyone) | **+30.8 / +5.2** | 6.6 |

- The change comes from the **eLN-PN junctions**; the sister junctions alone do little.
- **Simply switching off the eLNs' output, with no junctions at all, produces the same
  pattern, only stronger.** So the upgrade changes DM1 steering mainly because the junctions
  *quiet the eLNs* (section 6c), which removes their remaining chemical drive onto inhibitory
  neurons (the only chemical output `al_ln_literature` left them), not because electrical
  excitation reaches the projection neurons. In other words, the "restored electrical
  excitation" is not what the model is responding to.
- In none of the versions does a right-side DM1 smell give a "turn right" signal: the fixed
  left offset (about +5 Hz) survives every change tried here.

## 9. Verdict and validation status (PLAN.md Phase 6)

**Verdict: keep as an optional, switchable upgrade; do not make it the default yet.** It
passes every Phase 3 check (identical), causes no runaway, leaves the Kenyon-cell response and
the DA1 steering alone, and is built only from measured couplings. But its main effect in the
model is a side effect of the translation: joining each eLN to about 170 cells at the
measured pair strength drains it (input conductance x3.5), so the eLNs fall nearly silent,
while the lateral excitation that real eLNs are known for (Yaksi & Wilson 2010) does not
appear. Whether real eLNs are this "loaded" cannot be checked: the model gives every neuron
the same generic settings, and no eLN input resistance was used. So the steering change of
section 6d should not be read as a finding about flies.

**The DM1 answer:** restoring the eLN-to-PN electrical connection does **not** remove the
DM1 left bias. It makes the turn signal depend on the smell's side (a left smell now says
"turn left" 2-3 times as strongly as a right smell), but a right smell still says "turn
left". The Phase 6 conclusion stands: DM1 steering must stay labelled NOT brain-driven.

**Status: PRELIMINARY.**

| Phase 6 step | Done? |
|---|---|
| 1. seeds and parameter variation | yes: 3 seeds x 30 trials, strength 0.5x / 1x / 2x, plus 3 diagnostics |
| 2. bug checks | yes: tests (section 5); zero strength = old engine spike for spike on the whole brain; this lane's baseline equals the stored al_ln_literature and steering numbers |
| 3. literature | yes, with the gaps below |
| 4. contradicts biology? | partly: the lateral excitation that Yaksi & Wilson 2010 measured is missing, and the eLNs go nearly silent. Whether real eLNs stay active when only one glomerulus is driven was not checked against a recording |
| 5. write-up | this file; `experiments/phase7_gap/log-entry.md` |

**Not verified / assumed:**
- Every coupling coefficient was read by eye from bar charts (about +/-0.002). Huang et al.
  2010 was read from its figures and abstract only; its text and figure legends were not
  accessible.
- The spike width behind the spikelet (1 ms) is assumed; the 40 mV height is from Yaksi &
  Wilson's soma recordings.
- Which cells are coupled is a rule, not a measurement: eLN identity (FlyWire's literature
  column, a shape-and-position match to the recorded krasavietz cells), "touching" = at least
  5 shared chemical synapses, uPN glomerulus = the steering lane's ORN-input rule.
- DM1 PNs were given the same strength as other glomeruli, although Yaksi & Wilson saw
  "smaller lateral excitation" in DM1 PNs (no number to use).
- The model junction is symmetric; real eLN-PN junctions pass depolarization better.
- Not added, for lack of a strength or a way to pick the cells: eLN-iLN electrical component,
  eLN-eLN (mechanism UNVERIFIED), APL-DPM, Kenyon-cell and Kenyon-cell-MBON couplings,
  visual VS/HS couplings (UNVERIFIED).
- A translation that keeps each cell's total conductance unchanged, so the eLNs are not
  drained, is not possible at these strengths. An eLN's junctions add up to about 2.5 times
  its own leak, so its leak would have to become negative. Not run.

## 10. Files

- `sim/gap_junctions.py`: coupling rules, the calibration, the compiled loop with junctions
  (`GapBrain`), `build_gap_brain(fix="al_ln_literature", scale=1.0)`. `run_baseline()` runs
  the old engine on the same brain.
- `tests/test_gap_junctions.py`: 13 fast tests + 1 whole-brain test (`-m slow`).
- `experiments/phase7_gap/build_table.py` -> `results/coupling_table.csv` (8,074 pairs, a
  source on every row), `results/evidence_table.csv`, `results/upn_glomeruli.csv`,
  `results/calibration.json`.
- `experiments/phase7_gap/run_validation.py` -> `results/trials.csv` (one row per trial),
  `results/counts/` (spikes per neuron), `results/run_validation.log`.
- `experiments/phase7_gap/analyze.py` -> `results/table_*.csv`, `results/identity.txt`,
  `results/analysis.txt`, `plots/fig1_checks.png`, `fig2_steering.png`,
  `fig3_antennal_lobe.png`, `fig4_dm1_diagnostics.png`.
- `experiments/phase7_gap/check_ir94e.py` -> `results/check_ir94e.txt` (why 19 Ir94e trials
  differ; section 6b).
- `experiments/phase7_gap/diag_rate_changes.py` -> `results/rate_changes_gap_x1.csv` (which
  cell types changed most).
- `experiments/phase7_gap/log-entry.md`: the EXPERIMENTS.md entry.
