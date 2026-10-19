# How does the model's smell circuit compare with real-fly recordings?

*Written 2026-09-23. Scripts, raw results and plots: `experiments/olfaction_realfly/`
(numbers in `results/summary.json` and `results/scores.csv`; the pre-registration, frozen
before the main runs, is `results/preregistration.md`). Downloaded data: `data/olfaction/`
(not committed). Labels: **VALIDATED** = re-run with several seeds, checked for bugs,
compared with the literature. **PRELIMINARY** = at least one of those checks is missing.
**UNVERIFIED** = not checked against a source.*

## The short version

**Partly, and only after the model's known smell bug is fixed (PRELIMINARY: 3 of 8
pre-registered facts match, 4 partly match, 1 fails). The first relay station does not
work like a real fly's.** We fed the whole-brain model the measured smell-receptor
responses of real flies to 110 real odours (Hallem & Carlson 2006, from the DoOR database).
Then we compared what its smell circuit did with 8 facts from fly recordings. We wrote the
facts and the pass marks down before running anything. With the recommended fix
(`al_ln_literature`): **3 facts match, 4 partly match, 1 fails.**

- **It stays sane with real smells.** None of the 110 odours set off the runaway (0 of
  1,332 trials), even with every smell sensor also firing at its real resting rate.
- **Memory-centre coding is sparse, like a real fly's.** One odour switches on **3.0%** of
  the 5,177 Kenyon cells (the memory centre's cells) on average (3.9% when the unmeasured receptors are filled in from
  estimates). Real flies: about **5%**. Borderline: PARTIAL with measured inputs only, MATCH
  with the estimates. PRELIMINARY.
- **Matches (PRELIMINARY):** silencing the mushroom body's feedback-inhibition cell (APL)
  makes coding denser (3.0% -> 11.3%) and odours more alike, as in real flies. Projection
  neuron responses (the antennal lobe's output) follow a real-fly formula (Olsen et al.
  2010) closely (r = 0.85). Activity in other smell channels (glomeruli) damps a
  projection neuron by about the real amount.
- **Where it falls short (PRELIMINARY; F2 fails, F3, F6 and F8 partly):** in real flies,
  projection neurons respond to more odours than their input sensors do, because weak
  input gets boosted. In the model that happens in only **8 of 23** glomeruli (real: 7 of 7),
  and a projection neuron needs about **3 times** more sensor firing to get halfway up (36-49
  vs 12-16 spikes/s). Odour patterns also become more alike in the antennal lobe instead of
  more distinct, so the Kenyon cells end up less distinct than in a real fly. Responding
  Kenyon cells fire about 6 spikes per half second, where real ones fire "a few".
- **The published model (no fix) cannot be compared at all.** It runs away for every
  odour, and even with no odour, within 20 ms. About two-thirds of all Kenyon cells then fire, against about 5% in
  a real fly.
- **Likely reasons:** the model makes every synapse the same strength, so weakly wired
  glomeruli pass too little weak input. Its lateral inhibition acts on the projection
  neuron instead of on the sensor terminals. Nothing adapts during the odour.
- **How sure:** the seeds agree (each of 3 seeds alone gives 3.1%), but everything rests on one
  receptor dataset. It covers 23 of 51 receptor types (49% of sensors), all at one
  concentration.

---

## 1. Terms used here

- **ORN** (olfactory receptor neuron): a smell sensor on the antenna. Each carries one
  receptor type (for example Or22a), and all ORNs with the same receptor send their wires to
  one ball of wiring in the brain's first smell centre, the antennal lobe. That ball is a
  **glomerulus** (named like DM2). The model has 2,271 ORNs in 51 glomeruli.
- **PN** (projection neuron): the antennal lobe's output cell. A **uPN** (uniglomerular PN)
  takes input from one glomerulus only; there are 282 in the model.
- **LN** (local neuron): antennal-lobe cells that connect glomeruli to each other, mostly
  inhibitory. **Lateral inhibition** means activity in other glomeruli damping a PN.
- **KC** (Kenyon cell): the mushroom body's 5,177 "memory" cells. Each gets input from a
  handful of PNs. **Sparseness** = how few KCs one odour switches on.
- **APL**: one large inhibitory neuron per side that all KCs excite and that inhibits all
  KCs back (feedback inhibition).
- **MBON**: mushroom-body output neuron (97 in the model).
- **Evoked rate**: firing rate during the odour minus the rate with no odour.
- **Lifetime sparseness**: how picky one neuron is across many odours, from 0 (responds
  equally to everything) to 1 (responds to one odour only). Formula of Vinje & Gallant 2000.
- **Runaway**: the published model's failure mode (Phase 6): more than 1,500 different
  non-sensory neurons fire within one 10 ms slice and keep firing on their own.
- **Recommended fix** (`al_ln_literature`, `docs/phase7-neurotransmitter-audit.md`): the
  model with the antennal-lobe local-neuron signs corrected from the literature. **Published
  model** (`none`): the Shiu et al. 2024 model unchanged.

---

## 2. The real-fly facts, fixed before the runs

We wrote these down, with the sources and the pass marks, before the main simulations ran
(`experiments/olfaction_realfly/results/preregistration.md`, copied here unchanged in
substance). One disclosure: a 3-odour speed test had been run first (1-hexanol, ethyl
butyrate and no odour, 3 trials each), and it had shown 5-7% of KCs firing per trial.
Nothing else had been seen.

What was read, and how: full text through PubMed Central for Honegger et al. 2011
(PMC3180869), Bhandawat et al. 2007 (PMC2838615), Olsen et al. 2010 (PMC2866644) and Lin et
al. 2014 (PMC4000970; the web tool summarised it, so the Lin quotes are checked against its
summary only). Abstract only: Turner et al. 2008 (the journal blocked the full text),
Olsen & Wilson 2008, Campbell et al. 2013, Hallem & Carlson 2006, Wilson et al. 2004. The
Turner 6% figure is as quoted by Honegger 2011.

| # | Real-fly fact (source) | Model measure | MATCH | PARTIAL | MISMATCH |
|---|---|---|---|---|---|
| F1 | One odour switches on about **5%** of KCs on average; no odour's average is above 10%; single flies reach 17% (Honegger 2011: "on average, an odor evokes responses in ~5% of the KCs"; a KC counts if it responds on at least half the presentations). Single-cell recordings: 6% (Turner 2008). "~5-10%" (Lin 2014). | fraction of KCs that fire in at least half of the trials, above their no-odour rate; averaged over odours | mean 3-10%, no odour above 20% | mean 1.5-3% or 10-20% | otherwise |
| F2 | PNs are **less picky** than their own ORNs (lower lifetime sparseness) in every glomerulus tested: 7 glomeruli, 18 odours (Bhandawat 2007, Fig. 3b). | per glomerulus (23), lifetime sparseness of the ORN input vs its uPNs | PN less picky in >= 80% of glomeruli, p < 0.05 | 50-80% | < 50% |
| F3 | **Weak ORN input is amplified, strong input saturates**: PN = 165 x ORN^1.5 / (ORN^1.5 + 12^1.5) spikes/s (Olsen 2010; half the maximum at only 12 ORN spikes/s). | drive one glomerulus alone (DL5, DM4, DM1, VM7d) at 7 levels; fit the same curve | curve saturates, half-point 6-24 Hz, maximum 83-330 Hz | saturates, numbers outside those ranges | does not saturate |
| F4 | **Lateral inhibition**: activity in other glomeruli suppresses a PN's response to its own ORNs, in proportion to total ORN activity (Olsen & Wilson 2008; Olsen 2010's equation, with its measured sensitivity m = 4.19 for DL5 and 10.63 for VM7). | same 4 glomeruli, with pentyl acetate's pattern on all other glomeruli (Olsen's "public odour") | suppression in all 4, within 2x of the equation's size | in 2-3 of 4, or outside 2x | none |
| F5 | The Olsen 2010 equation, fed Hallem & Carlson inputs, predicts real PN responses well (95% / 87% of the variance for VM7 / DL5 PNs). | correlation between model uPN responses and the equation's prediction, 23 glomeruli x 110 odours | r >= 0.7 | 0.4-0.7 | < 0.4 |
| F6 | Odour patterns become **less alike** from ORNs to KCs (Turner 2008); KC coding is decorrelated (Lin 2014). | mean correlation between two odours' patterns in ORNs, uPNs and KCs | KC below both | below one | below neither |
| F7 | **Blocking APL** makes KC responses less sparse and more alike between odours (Lin 2014, Fig. 5c-e; the size is only shown in figures). | silence both APL cells | KC fraction up and KC correlation up | one of the two | neither |
| F8 | Responding KCs fire **only a few spikes** (Lin 2014; Turner 2008; not quantified in what we read). | median spikes per responding KC per 0.5 s odour | <= 5 | 6-10 | > 10 |

For the published model (no fix) we pre-registered only a report: which odours tip it into
runaway. Real flies smell all day without their brains locking up, so any runaway is a
mismatch with biology.

---

## 3. What we did

- **Real receptor data.** DoOR 2.0 (Muench & Galizia 2016, Sci Rep 6:21841), downloaded
  from its public GitHub repository (`ropensci/DoOR.data`) into `data/olfaction/door/`.
  Inside it, the dataset `Hallem.2006.EN` is Hallem & Carlson 2006 (Cell 125:143): 24
  receptors x 110 odours at 1:100 dilution, firing rate change in spikes/s over a 0.5 s
  odour pulse, with each receptor's spontaneous rate given separately (1-47 spikes/s,
  median 12).
- **Receptor -> glomerulus -> model neurons.** From DoOR's mapping table, checked by name
  against the snapshot-630 labels (`hemibrain_type` = `ORN_<glomerulus>`). Two choices:
  Or35a's "VC3" is FlyWire's hemibrain-named `VC3l`; Or33b, which shares its neurons with
  Or47a (DM3) and Or85a (DM5), is left out, so DM3 and DM5 are driven by Or47a and Or85a.
  **Set A** (the main input): the 23 glomeruli Hallem & Carlson measured, 1,117 of the
  2,271 ORNs (49%). **Set B**: set A plus DoOR's merged estimates for 23 more glomeruli
  (875 ORNs), converted to spikes/s with one scale factor fitted where both exist (373
  spikes/s per DoOR unit, r = 0.93 over 2,530 pairs; this fit is partly circular because
  DoOR's merged values for those receptors come largely from Hallem & Carlson). Set B
  covers 46 of 51 glomeruli (88% of ORNs); a missing DoOR value counts as "no response".
  No data at all: DA1 (Or67d, the cVA pheromone receptor; none of the 110 odours), VC1,
  VC3m, VC5 (naming ambiguous between DoOR and FlyWire) and VA7m.
- **Input to the model.** Every ORN fires at random (Poisson) at its receptor's
  spontaneous rate plus the odour response, never below zero. Untested ORN types fire at
  12 spikes/s with no odour response. Each trial lasts 0.5 s, as in Hallem & Carlson.
  "No odour" trials give every ORN its spontaneous rate only.
- **Runs** (`run_odours.py`, `run_gain.py`, all on snapshot 630 with the fast engine):
  recommended fix, set A, all 110 odours + no odour, 3 seeds x 4 trials each (1,332
  trials); the same with both APL cells silenced (3 seeds x 2 trials, paired trial-for-trial
  with the intact runs); set B (3 seeds x 2 trials); the published model with set A
  (spontaneous + odour) and with the odour response alone (no spontaneous firing), 2 trials
  of 0.3 s per odour; and the Olsen-style experiment for F3/F4 (4 glomeruli x 7 input levels
  x 3 background levels x 3 seeds x 4 trials). "Seed" sets the random input spikes; the
  model itself has no other randomness.
- **Read-out.** Spike counts per neuron per trial for ORNs, all 685 PNs (282 uPNs), 424
  LNs, 5,177 KCs, 2 APL, 97 MBONs, 326 DANs and 521 lateral-horn neurons.

---

## 4. Results, fact by fact (recommended fix)

| Fact | Real fly | Model (recommended fix) | Verdict |
|---|---|---|---|
| F1 KC sparseness | ~5% per odour (Honegger 2011); 6% (Turner 2008) | 3.0% (set A; median 2.7%, max 6.7%); 3.9% (set B; max 12.9%) | PARTIAL (A: 2.98%, the line was 3%); MATCH (B) |
| F2 PNs broader than ORNs | 7 of 7 glomeruli | 8 of 23 glomeruli; median sparseness 0.57 PN vs 0.53 ORN | **MISMATCH** |
| F3 weak input amplified | half-point 12-16 Hz (45 for DM1), max 144-170 | half-point 32-49 Hz, max 168-243; saturating (gain 3-8x higher for weak input) | PARTIAL |
| F4 lateral inhibition | 50-78% less (equation, same inputs) | 75-85% less; weak input pushed below rest | MATCH (size); shape differs |
| F5 PN responses vs real-fly equation | equation explains 87-95% of real PN variance | r = 0.85 (2,530 glomerulus-odour pairs) | MATCH |
| F6 odours less alike in KCs | KCs less alike than ORNs | ORN 0.21, uPN 0.54 (measured glomeruli 0.39), KC 0.31 | PARTIAL |
| F7 APL block | denser and more alike | 3.0% -> 11.3%; r 0.30 -> 0.41 | MATCH (direction; real size UNVERIFIED) |
| F8 few spikes per KC | "a few" | median 6.2 per 0.5 s | PARTIAL |

The seeds agree closely. Each seed on its own (`results/per_seed.csv`) gives KC 3.09%, 3.09%
and 3.09%; PNs broader in 8, 9 and 9 glomeruli; equation r 0.85, 0.85 and 0.85; KC
correlation 0.30, 0.31 and 0.30; 6.0 spikes median in every seed. Stability margin: the
busiest 10 ms slice in any trial had 736 non-sensory neurons firing (runaway threshold
1,500; APL-silenced 1,420; set B 1,104).

### F1. How many Kenyon cells one odour switches on

- **Set A (measured inputs only): 3.0% of KCs on average** (median 2.7%; lowest propanal
  0.2%, highest 1-pentanol 6.7%). No odour goes above 10%. The strongest odours are the
  ones that drive the most ORNs: the KC fraction follows total ORN input almost perfectly
  (rank correlation 0.93 over 110 odours). 15 of 110 odours switch on fewer than 1%.
- With a looser count (any spike in a trial) it is also 3.0% per trial; 2.6% fire 2 or
  more spikes and 2.3% fire 3 or more, so the number barely depends on the threshold.
  With no odour, 0.38% of KCs fire at least once per 0.5 s (0.33% reliably).
- **Set B (46 glomeruli, DoOR estimates added; 6 trials per odour, so a KC counts if it
  fires in 3 of 6): 3.9% on average** (median 3.3%; highest 2,3-butanedione 12.9%; 2 of 110
  odours above 10%, none above 20%). Pre-registered verdict **MATCH**. Filling in the
  missing glomeruli moves the average about a third of the way from 3.0% towards 5%.
- Side note (not pre-registered, no verdict): real sparseness "was consistent across a wide
  range of stimuli" and "mainly invariant across concentrations" (Honegger 2011 abstract).
  In the model it tracks input strength closely (0.2% to 6.7% across odours, rank
  correlation 0.93 with total ORN input), so the model probably lacks the mechanism that
  holds sparseness steady (Honegger credits recent odour experience, i.e. adaptation).
- Verdict by the pre-registered rule: set A **PARTIAL** (2.98%, just under the 3% line).
  PRELIMINARY: the real 5% counts KCs imaged in one plane with a calcium dye, which can miss
  a KC that fires only one or two spikes; the model counts every spike.

### F2. Are projection neurons less picky than their ORNs? No, not in general.

- In real flies PNs are less selective than their own ORNs in all 7 glomeruli measured.
  In the model this holds in only **8 of 23 glomeruli**; overall the model's PNs are
  slightly *more* selective (median lifetime sparseness 0.57 vs 0.53 for the ORNs,
  p = 0.048 in the wrong direction). **MISMATCH. PRELIMINARY** (3 seeds x 4 trials per
  odour; one input dataset).
- The pattern is not random. The glomeruli whose PNs are too picky are the ones whose
  ORNs are **weakly wired** to their PN in FlyWire (`results/diag_wiring.csv`): the rank
  correlation between "PN more picky than ORN" and the size of the voltage kick one ORN
  spike gives its PN is -0.52. Extreme case: DA3. Its ORNs respond up to 82 spikes/s, but
  one ORN spike moves a DA3 PN by only 0.56 mV of input (0.275 mV per synapse), and the
  DA3 PNs never respond (0.04 spikes/s at most). Of the four most strongly wired
  glomeruli (DL5, DC1, DM4, VA6; 6.6-11 mV per spike), three behave like real flies (PN
  less picky than its ORNs); DM4 does not.
- Side observation (not pre-registered): real PN odour patterns are spread more evenly
  than ORN patterns (Bhandawat 2007: larger distances between odours). In the model the
  opposite happens: two odours' PN patterns are *more* alike than their ORN patterns
  (mean correlation 0.31 vs 0.21 over the same 23 glomeruli; F6).

### F3. Weak input amplified, strong input saturating

Driving one glomerulus at a time, with every other ORN at its spontaneous rate:

| glomerulus | model: half-point (sigma) | real fly (Olsen 2010 fit) | model maximum (Rmax) | real Rmax | gain at 0-10 Hz / gain at 80-160 Hz |
|---|---|---|---|---|---|
| DL5 | 37 Hz | 11.8 Hz | 191 | 167 | 5.6 |
| DM4 | 49 Hz | 16.3 Hz | 168 | 170 | 3.2 |
| VM7d | 36 Hz | 12.4 Hz | 181 | 163 | 6.1 |
| DM1 | 32 Hz | 44.8 Hz | 243 | 144 | 8.3 |

The shape is right: every curve rises steeply and then flattens (gain 3-8 times higher for
weak input than for strong input), and the ceilings are at or above the real ones (168-243
vs 144-170 spikes/s). But the model
needs about **3 times more ORN input** than a real fly to get a PN halfway up (except DM1,
where the real fly is also slow). Weak input is amplified, just not as much. **PARTIAL.
PRELIMINARY** (4 glomeruli, 3 seeds x 4 trials per point). Plot: `plots/orn_pn_transfer.png`.

### F4. Lateral inhibition

Adding pentyl acetate's measured pattern on all *other* glomeruli (the "public odour",
as in Olsen 2010) cut each PN's response to its own ORNs (response with the public odour /
response without):

| own ORN input | model, 4 glomeruli | Olsen 2010 equation (m = 10.63 to 4.19) |
|---|---|---|
| +20 spikes/s | -0.55 to 0.01 (PN pushed to or below its no-odour rate) | 0.09 to 0.31 |
| +40 spikes/s | 0.02 to 0.30 | 0.19 to 0.50 |
| +80 spikes/s | 0.59 to 0.76 | 0.37 to 0.71 |

At half strength the model gives -0.13 to 0.24, 0.46-0.66 and 0.82-0.90 at the same three
levels (equation 0.23-0.55, 0.39-0.73, 0.61-0.87). So the size is right (pre-registered
rule: **MATCH**, averaged over the three levels: 75-85% less vs 50-78% for the equation).
The shape is not quite right: in the model, inhibition swamps weak input completely and
pushes the PN below its resting rate (the public odour alone lowers the DL5, DM1 and VM7d
PNs by 44, 22 and 9 spikes/s), then lets strong input through more than the equation
does. Real gain control scales responses down (divides) without driving them below rest.
**PRELIMINARY.**

### F5. Whole-odour PN responses vs the real-fly equation

Across 23 glomeruli x 110 odours (2,530 pairs) the model's PN responses follow the Olsen
2010 equation fed the same Hallem & Carlson data: **r = 0.85** (rank correlation 0.89).
Without the equation's normalization term (no lateral inhibition) the fit drops to
r = 0.68, so the model's lateral inhibition is doing work of the right kind. Model PNs
are weaker on average (34 vs 48 spikes/s), but their strongest responses are as strong or
stronger (95th percentile 144 vs 122). **MATCH. PRELIMINARY** (the equation is a fit to real data from a few
glomeruli, not a recording of all 23). Plot: `plots/pn_vs_equation.png`.

### F6. Do odour patterns become less alike on the way to the KCs?

Mean correlation between two odours' activity patterns (110 odours, all 5,995 pairs):
ORN input 0.21; uPNs 0.54 over all 282, 0.39 over the uPNs of the 23 measured glomeruli
(0.31 if each glomerulus is averaged first); **KCs 0.31** (0.27 if a KC counts only as
on/off). The all-uPN figure is inflated by our input (section 6, point 3). KCs are less alike than PNs, as in real
flies, but not less alike than the ORN input, which the real fly achieves (Turner 2008).
The loss happens in the model's antennal lobe, which makes odours more alike instead of
more distinct (F2). **PARTIAL. PRELIMINARY.** Plot: `plots/odour_correlations.png`.

### F7. Blocking APL

Silencing both APL cells (their output set to zero), on exactly the same input spikes
(trials 0-1 of each seed): the KCs responding to an odour go from **3.0% to 11.3%** on
average (3.7 times; denser for 110 of 110 odours), and the mean correlation between two
odours' KC patterns rises from **0.30 to 0.41**. Both directions match Lin et al. 2014.
**MATCH** in direction. The real size could not be compared, because the text we read
gives it only in figures (the size is **UNVERIFIED**). With APL silenced and no odour,
0.48% of KCs fire per trial (0.38% with APL). **PRELIMINARY.**

### F8. Responding KCs fire only a few spikes

A responding KC fires a median of **6.2 spikes** in the 0.5 s odour (90th percentile
15). Real KCs fire "only a few". **PARTIAL** by the pre-registered line (5). Likely reason:
the model's inputs are constant for the whole 0.5 s, while real PN responses peak soon
after odour onset and then decline (Bhandawat 2007: responses "rise and accommodate
rapidly"), and the model has no adaptation. **PRELIMINARY; the real number is only
"a few" in what we read (UNVERIFIED as a number).**

### Other read-outs (not scored)

- **APL** fires a median 72 spikes/s above rest per odour (10-147). **MBONs:** a median of
  2 of 97 MBONs rise by more than 5 spikes/s (up to 20; 80% of odours move at least one).
  **Lateral horn** neurons rise 3.5 spikes/s on average, **LNs** 9.7, **uPNs** 10.5.
  **Dopamine neurons** do not change on average (-0.05 spikes/s).

---

## 5. The published model (no fix): every odour, and no odour at all, runs away

- **With realistic spontaneous firing, the published model cannot even rest.** Giving every
  ORN only its measured spontaneous rate (no odour) tips it into runaway in both trials,
  within 20 ms. Every one of the 110 odours does the same (220 of 220 trials, within
  10-20 ms). About 67% of all KCs then fire, against about 5% in a real fly.
- **With the odour response alone** (no spontaneous firing anywhere, the way earlier
  phases drove single glomeruli), all 110 odours still run away, in 220 of 220 trials,
  within 10-20 ms of odour onset (10 ms is the time resolution). Stronger odours tip
  faster (rank correlation -0.77 between tipping time and total ORN input), but even the
  weakest odour in the set (putrescine, 268 ORN spikes/s summed over the 24 receptors)
  tips within 20 ms. 66% of KCs fire.
- So the answer to "which odours tip it" is **all of them**, and no odour is needed. This
  fits Phase 5 (3 spikes from 3 DM1 ORNs are enough) and confirms that no real-fly
  comparison can be made with the published model. **PRELIMINARY** (one seed, 2 trials
  of 0.3 s per odour; it agrees with the 90 of 90 DM1 runaways found with 3 seeds in
  Phases 5-7).

---

## 6. Why the model misses where it misses (plausible reasons, with the evidence we have)

1. **The ORN -> PN step is too weak where FlyWire shows few synapses (F2, F3, F6).** The
   model turns every synapse into the same 0.275 mV, so a glomerulus's strength is set by
   its synapse count. One ORN spike moves its PN's input by 0.56-0.67 mV in DA3, VA1v and VA1d
   but by 11 mV in DL5 (`results/diag_wiring.csv`). The PNs that come out too picky are
   mostly the weakly wired ones (rank correlation -0.52), and the DA3 PNs never respond at
   all. Real PNs are driven hard by even weak ORN input in every glomerulus measured
   (half-point about 12 ORN spikes/s; the model needs about 36-49). Background knowledge,
   not re-read in this lane (**UNVERIFIED** here): real ORN -> PN synapses are strong and
   reliable and they weaken with use (short-term depression), which is what makes the real
   curve steep at first and flat later. The model has no synaptic depression; its curves
   flatten only because of inhibition and the 2.2 ms refractory period.
2. **Lateral inhibition acts in the wrong place (F4 shape).** Real lateral inhibition acts
   largely on the ORN axon terminals, before the synapse (Olsen & Wilson 2008: "a
   substantial portion ... acts at a presynaptic locus"), so it scales the input down. In
   the model, an ORN driven by the input generator fires on every input kick (68.75 mV)
   whatever inhibition it receives, so inhibition of ORN terminals has almost no effect. All
   the inhibition lands on the PN itself as a subtracted current, which can cancel weak input
   completely and push the PN below rest (up to -44 spikes/s for DL5).
3. **Odour patterns get more alike in the antennal lobe, and the KCs inherit it (F6).**
   Part of this is our input, part is the model. Our input: the 166 uPNs of the 28 untested
   glomeruli get no odour response of their own, so every odour just pushes them down a
   little through lateral inhibition (median -2.1 spikes/s; below rest for 110 of 110
   odours). Their patterns are therefore nearly identical for every odour (correlation
   0.92), which inflates the all-uPN figure (0.54). The model: even the uPNs of the 23
   measured glomeruli are more alike than their own ORN input (0.39 per neuron, 0.31 per
   glomerulus, vs 0.21), where real PNs are less alike (Bhandawat 2007). The KCs remove
   part of the similarity (0.31) but end up no less alike than the ORN input.
4. **No adaptation, constant input (F8, and probably part of F1).** Hallem & Carlson's
   numbers are averages over 0.5 s; we fed them as constant rates. Real PN responses peak
   and then decline (Bhandawat 2007); nothing in the model adapts. The model's KCs
   therefore keep firing for the whole 0.5 s (6.2 spikes median).
5. **Half the nose is unmeasured (F1).** Set A drives only 49% of ORNs with measured
   responses; the KC fraction follows total ORN input almost perfectly (rank correlation
   0.93), so missing glomeruli push the number down. Adding DoOR estimates for 23 more
   glomeruli raises it from 3.0% to 3.9%.
6. **The published model's runaway (section 5)** has the cause already traced in Phases 6
   and 7: the excitatory local neurons' chemical synapses. The recommended fix removes it.

---

## 7. How sure are we?

- **Solid (PRELIMINARY, 3 seeds, pre-registered, one input dataset):** the recommended-fix
  model stays stable for all 110 real odours (0 runaways in 1,332 trials); KC coding is
  sparse (3%) and APL keeps it sparse (11% without APL); PN responses follow the real-fly
  normalization equation (r = 0.85); lateral inhibition is about the right size.
- **Solid mismatch (PRELIMINARY):** PN tuning is not broadened as in real flies, and weak input needs
  about 3 times more ORN firing than in a real fly to half-drive a PN.
- **Weak points of the comparison:** (1) Hallem & Carlson recorded each receptor in a
  substitute ORN ("empty neuron"), at one concentration, and we feed their 0.5 s averages as
  constant rates. (2) 28 of 51 ORN types have no measured response in set A; set B fills 23
  of them with DoOR estimates that rest on a single scale factor. (3) The real numbers come
  from other flies and other methods (calcium imaging for KCs, 7 glomeruli for PNs).
  (4) The F3/F4 real values are an equation fitted to real recordings, not recordings of
  these exact inputs. (5) Only 3 seeds x 4 trials (intact) or x 2 trials (APL-silenced,
  set B), and the random input is the model's only source of variability.
- **UNVERIFIED:** the real size of the APL effect (figures only); the real spike count of
  responding KCs ("a few"); Turner 2008's text beyond its abstract; Lin 2014 beyond the
  summary of its full text; the short-term-depression explanation in section 6.
- **Not checked:** the sugar -> MN9 baseline was not re-run here (nothing in `sim/` was
  changed, so it cannot have moved); other concentrations; other odour datasets.

---

## 8. Files

All in `experiments/olfaction_realfly/` unless noted.

- `prep_inputs.py`: reads DoOR, builds the odour x glomerulus input tables
  (`results/hc_delta.csv`, `hc_sfr.csv`, `door_ext_delta.csv`, `coverage.csv`,
  `backproject_fit.json`).
- `common.py`: neuron groups, odour -> ORN rates, per-trial read-out and runaway test.
- `run_odours.py`: the odour runs (configs `alln_A`, `alln_A_noAPL`, `alln_B`, `none_A`,
  `none_evoked`; `alln_B_noAPL` was defined but skipped for time). Raw per-trial spike
  counts: `results/counts/<config>/NNN.npz`.
- `run_gain.py`: the Olsen-style experiment (F3/F4) -> `results/gain_trials.csv`.
- `analyze.py`: scoring -> `results/scores.csv`, `summary.json`, `per_odour.csv`,
  `lifetime_sparseness.csv`, `pn_vs_olsen_eq.csv`, `gain_transfer_fits.csv`,
  `gain_lateral_inhibition.csv`. `robustness.py`: per-seed check -> `results/per_seed.csv`.
  `diag_wiring.py`: ORN -> PN and LN -> PN wiring per glomerulus -> `results/diag_wiring.csv`.
- `plots.py` -> `plots/kc_sparseness.png`, `orn_pn_transfer.png`, `lifetime_sparseness.png`,
  `pn_vs_equation.png`, `odour_correlations.png`.
- `speed_test.py` (the pre-registration disclosure), `lit_fetch.py` and `pdf_text.py`
  (literature download helpers), `run_all.sh` (runs everything in order; log
  `results/run_all.log`), `results/preregistration.md`.
- Not committed: `data/olfaction/door/` (DoOR.data CSVs) and `data/olfaction/lit/`
  (abstracts and full texts). DoOR.data is licensed CC BY-SA 4.0; `results/hc_delta.csv`,
  `hc_sfr.csv` and `door_ext_delta.csv` are derived from it (cite Muench & Galizia 2016 and
  Hallem & Carlson 2006). `results/counts/` holds 16 MB of raw per-trial spike counts
  (566 small files); they can be regenerated with `run_all.sh`.

To re-run: `sh experiments/olfaction_realfly/run_all.sh` (about 50 minutes; one whole
brain in memory at a time), then `analyze.py`, `robustness.py` and `plots.py` from that folder.
