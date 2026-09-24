# Real-fly scorecard: 39 real-fly measurements we can test the model against

*Written 2026-09-23. Catalogue: `experiments/scorecard/catalog.csv` (one row per item).
Every neuron ID: `experiments/scorecard/ids_630.csv`. Both are made by
`experiments/scorecard/build_catalog.py`, which looks every cell type up in FlyWire's own
tables. No simulation was run for this document.*

## The short version

Until now the model was mostly checked against the Shiu et al. 2024 **model**, not
against **real flies**. This is a list of 39 published real-fly measurements, each turned
into a model test: which neurons to switch on, switch off or watch, their snapshot-630
IDs, the result real flies gave, and whether our model can run the test at all.

**Counts by area**

| Area | Items | YES | PARTLY | NO |
|---|---|---|---|---|
| Taste and feeding | 7 | 4 | 2 | 1 |
| Mechanosensation and grooming | 4 | 0 | 3 | 1 |
| Smell | 5 | 3 | 2 | 0 |
| Learning | 5 | 2 | 2 | 1 |
| Steering and descending neurons | 6 | 3 | 1 | 2 |
| Temperature and humidity | 5 | 4 | 1 | 0 |
| Pheromones and female courtship | 5 | 4 | 1 | 0 |
| Vision | 2 | 0 | 1 | 1 |
| **Total** | **39** | **20** | **13** | **6** |

- **YES** = the model has every cell needed and the test is a normal run.
- **PARTLY** = runnable, but a missing piece (nerve cord, graded neurons, slow chemistry,
  an unidentified cell) means a pass or fail only says part of what we want.
- **NO** = the model cannot answer it honestly. Kept in the list so the limits are on record.

**Recommended first batch** (all YES, all cheap, all with a clear target).
In priority order:

1. **FC2: the SAG input picks out pC1a.** Switch on the 2 SAG neurons. Real flies: pC1a
   strongly excited, pC1b weakly, pC1c/d/e hardly at all (Wang et al. 2020, *Nature*).
   Target: that ranking.
2. **FC5: which lateral-horn cells hear the male pheromone.** Drive the cVA sensory neurons
   (DA1). Real female flies: 11 of 15 aSP-g cells respond, 1 of 34 aSP-f, 2 of 8 aSP-h
   (Kohl et al. 2013, *Cell*). Our model is a female brain, so it should match the female
   pattern. Target: the three fractions.
3. **FC1: vpoDN gets input from vpoEN and pC1.** Switch on vpoEN, then pC1, then both.
   Real flies: both excite vpoDN, the neuron that opens the vaginal plates (Wang et al.
   2021, *Nature*). Target: vpoDN up in each case, most with both.
4. **SD4: PFL3 steers.** Switch on the PFL3 cells that end in the left steering hub (lateral
   accessory lobe). Real flies turn toward that side in about 92% of trials (Mussells
   Pires et al. 2024, *Nature*). Target: left DNa02 above right DNa02, and the mirror image.
5. **TH3: cold switches off the DN1a clock cells.** Drive the cool sensors. Real flies:
   the GABA-releasing cold projection neurons (TPN-II) fire and inhibit DN1a (Alpert et
   al. 2020, *Curr Biol*). Target: DN1a slows, and stops slowing when VP3+_vPN (our best
   match for TPN-II) is silenced.
6. **TH2 (with TH1): cool sensors inhibit the warm pathway.** Drive the warm sensors with
   and without the cool sensors. Real flies: cool signals inhibit the warm projection
   neurons through local neurons (Liu et al. 2015, *Nature*). Target: warm projection
   neurons fire less when cool sensors are active; cool projection neurons fire to cool input.
7. **OS4: sister smell neurons fire in sync.** Give every smell sensory neuron independent,
   low-rate random input. Real flies: projection neurons of the same glomerulus fire
   synchronised spikes, odours make them more synchronised, and neurons of different
   glomeruli are only weakly synchronised (Kazama & Wilson 2009, *Nat Neurosci*). Target:
   DA1 sister pairs far more synchronised than cross-glomerulus pairs. (The olfaction lane's
   `docs/olfaction-vs-real-fly.md` already scores lateral inhibition, the amplification
   curve and APL, so those are not repeated here.)
8. **LL1: MVP2 silences the "avoid" outputs.** Give the mushroom body an odour and switch on
   MBON11 (MVP2). Real flies: odour responses of the M4/6 output neurons drop, the V2 output
   neurons do not change (Perisse et al. 2016, *Neuron*). Target: that split.
9. **SD1 (with SD2): looming detectors drive the backward-walking neurons.** Switch on LC16.
   Real flies: LC16 drives the moonwalker neurons (MDN) and backward walking; one-sided
   LC16 gives turning (Sen et al. 2017). Target: MDN fire; one-sided input makes the two
   MDN sides differ.
10. **TF4: which feeding neurons see water and which see sugar.** Drive water, then sugar
    taste neurons. Real flies: Usnea responds to water only, Phantom to both, Clavicle to
    sugar (Shiu et al. 2022, *eLife*). Target: that pattern. (Check first that Shiu et al.
    2024 did not already score it.)

Reserves if any of these turn out blocked: FC3 (pC1 brakes egg laying through oviIN),
OS1 (a silenced glomerulus still excited by its neighbours; a held-out smell test of the
al_ln_literature fix), TF6 (bitter acts at the premotor stage).

**Suggested pass rule** (borrowed from the held-out lane, so the two lanes score alike):
a cell "responds" if it fires at least 1 Hz more than in the same run without the
stimulus, in every seed; a change "counts" if it is more than 20% and more than 1 Hz, in
every seed. Write the rule down before running, as the held-out lane did.

**What to trust.** 17 items were checked against the paper's full text (searched for the
exact sentences), 22 against the abstract only; each row says which. All neuron IDs were
looked up by code, not typed by hand. Only 2 neurons could not be carried over from FlyWire's
newer version (two hearing sensory neurons; they appear in 2 items, so 4 of the 3,125 ID rows
are blank).

---

## How to read the catalogue

Each row of `catalog.csv` has: the real-fly result in one sentence; the measurement type
(behaviour, electrophysiology or calcium imaging); the paper, year and figure; whether we
read the full text or the abstract; the model test; the cell types and their 630 IDs
(listed in the row for groups of up to 12 cells, otherwise in `ids_630.csv`); how sure we
are that FlyWire's cells are the paper's cells; the expected model result and any number
the paper gives; feasibility with the reason; cost; first-batch rank.

**How the IDs were found.** Most cell types carry a label in the snapshot-630 table the
model uses (2,039 of 3,125 ID rows). Some names exist only in FlyWire's newer snapshot 783
(for example the aSP-g/aSP-f pheromone cells, aIPg, and the hearing sensory neurons JO-A
and JO-B). Those were carried back to 630 by the same root ID when the neuron was never
edited (805 rows), or by the neuron with its cell body (or, for sensory neurons, its anchor
point) at the same spot (20 rows, all at exactly 0.00 micrometres, so they are the same
cells under a new number). The feeding neurons come from the Shiu lab's own list that ships
with the model (`data/reference/sez_neurons.pickle`), and the taste inputs from
`sim/shiu_model.py`.

---

## 1. Taste and feeding (7 items: 4 YES, 2 PARTLY, 1 NO)

- **TF1 Fdg starts feeding (YES).** Switching on the pair of Fdg neurons makes a fly run its
  whole feeding sequence (Flood et al. 2013, *Nature*; abstract). Test: drive Fdg, read MN9.
  Note: Shiu et al. 2024 included Fdg in its named cells; check it was not already scored.
- **TF2 One Fdg, lopsided feeding (PARTLY).** One Fdg alone gives lopsided feeding (same
  paper). Test: left Fdg alone vs right; compare left and right MN9. MN9 may not capture a
  sideways proboscis movement.
- **TF3 Fdg needed for sugar feeding (PARTLY).** Killing Fdg abolishes sugar feeding, and Fdg
  responds to food only when starved (same paper). Test: sugar input with Fdg silenced. The
  model has no hunger state, and Shiu et al. 2022 found Fdg does not respond to taste on
  the proboscis, so the fly's route may use throat or leg sensors we do not have.
- **TF4 Water vs sugar neurons (YES, batch 10).** See the first batch.
- **TF5 Which feeding neurons start or are needed for extension (YES).** Activating Usnea,
  G2N-1 or Clavicle increases proboscis extension, Fudog does not; silencing Rattle or Usnea
  reduces it (Shiu et al. 2022, Fig. 4A and 4D, and legends that sit with Fig. 1 figure supplement 2). The silencing half probably overlaps the
  already-covered Shiu 2024 silencing screen.
- **TF6 Bitter acts late (YES).** Adding bitter input cuts the premotor neuron Roundup's
  sugar response, but G2N-1 just upstream is unchanged (Shiu et al. 2022, Fig. 5B-C).
  Related to the already-covered Scapula brake; the new part is the G2N-1 control.
- **TF7 A dopamine neuron boosts sugar acceptance (NO).** TH-VUM increases extension to
  sugar (Marella et al. 2012). It works by slow dopamine signalling, which the model does not
  have; the published model would "pass" for the wrong reason (fast excitation). This is
  the same problem the held-out lane found for OA-VPM4.

## 2. Mechanosensation and grooming (4 items: 0 YES, 3 PARTLY, 1 NO)

The weakest area. Most touch and grooming results depend on the nerve cord or on graded
signals, and the key relay cells are often not named in FlyWire.

- **MG1 Courtship song reaches vpoEN (PARTLY).** vpoEN are hearing neurons tuned to the
  male's song (Wang et al. 2021). Test: drive the hearing sensory neurons JO-A and JO-B
  (356 cells), read vpoEN. Song tuning depends on sound timing we would have to invent.
- **MG2 Hearing neurons feed the escape neuron (PARTLY).** Sound-detecting sensory neurons
  make mixed electrical and chemical synapses onto the giant fiber (Pezier et al. 2014). The
  model has only the chemical half.
- **MG3 Wind direction (PARTLY).** "Wedge projection neurons" combine both antennae to code
  wind direction (Suver et al. 2019). These cells are not named in FlyWire, so they would
  have to be found first.
- **MG4 Head bristles aim grooming (NO).** Each head bristle class makes the fly groom that
  spot (Eichler et al. 2024). Only behaviour was measured, and grooming is made in the
  nerve cord.

The antennal grooming results of Hampel et al. 2015 are being tested by the held-out lane
and are not repeated here.

## 3. Smell (5 items: 3 YES, 2 PARTLY)

**Overlap:** the olfaction lane (`docs/olfaction-vs-real-fly.md`, in progress) already scores
OS2, most of OS3 and OS5 against real flies, on both the published model and the
al_ln_literature fix. They stay in the catalogue for completeness but should not be re-run.
OS1 and OS4 are not covered there.

- **OS1 A silenced glomerulus still gets excited by its neighbours (PARTLY).** Olsen et al.
  2007: silencing all sensory neurons of one glomerulus still leaves its projection neurons
  responding to odours. Test: silence DA1 sensory neurons, drive other smell inputs, read DA1
  projection neurons. In flies this runs largely through electrical synapses, which the model
  has only as the Phase 7 switch.
- **OS2 Inhibition grows with total input (YES; being scored by the olfaction lane).**
  Inhibition between glomeruli outweighs excitation and grows with total sensory activity
  (Olsen & Wilson 2008; Olsen et al. 2010).
- **OS3 Projection neurons boost weak input (YES).** Weak sensory input is amplified, strong
  input is not, and projection neurons are more reliable than their inputs (Bhandawat et al.
  2007). Test: sweep DA1 input from 5 to 200 Hz. The "fast onset" part needs the Phase 7
  adaptation switch.
- **OS4 Sister projection neurons fire in sync (YES, batch 7).** See the first batch. It
  rests only on wiring the model has (each sensory neuron contacts every projection neuron
  in its glomerulus).
- **OS5 APL keeps Kenyon cells sparse (PARTLY).** Blocking the APL feedback makes Kenyon-cell
  responses less sparse and more alike between odours (Lin et al. 2014, Fig. 5c-e). APL is
  a non-spiking cell with local effects, which one model neuron cannot copy.

Kenyon-cell sparseness itself (Turner et al. 2008) was already compared in Phases 5 and 7,
and Gaudry et al. 2013 (left/right steering) is already covered.

## 4. Learning (5 items: 2 YES, 2 PARTLY, 1 NO)

- **LL1 MVP2 silences the avoid outputs (YES, batch 8).** See the first batch.
- **LL2 Learning shifts the M4b' response (YES).** After punishment training the M4b'
  output neuron (MBON-b'2mp) responds relatively more to the trained odour; after reward
  training, relatively less (Owald et al. 2015, Fig. 3I-L). In our model synapses can only
  weaken, so a rise can only come from MVP2 losing its drive and releasing its brake. This
  tests learning and wiring together. Needs Phase 8.
- **LL3 Sugar switches on reward dopamine neurons (PARTLY).** PAM dopamine neurons respond to
  sugar drinking (Liu et al. 2012). The model has only proboscis sugar sensors and no hunger.
- **LL4 Bitter relays to punishment dopamine neurons (PARTLY).** Switching on the bitter taste
  projection neurons TPN3 drives most PPL1 dopamine neurons (Kim et al. 2017). TPN3 is not
  named in FlyWire, so the test uses the standard bitter input instead.
- **LL5 Backward pairing strengthens (NO).** Dopamine after an odour strengthens the synapse
  (Handler et al. 2019). Phase 8 has no strengthening rule yet.

Not listed on purpose: Hige et al. 2015 (used to set the learning speed) and Aso & Rubin
2016 (used to mark the slow a2/a3 compartments in `sim/plasticity.py`). A test that set the
model cannot also test it.

## 5. Steering and descending neurons (6 items: 3 YES, 1 PARTLY, 2 NO)

- **SD1 LC16 drives the backward-walking neurons (YES, batch 9)** and **SD2 one-sided LC16
  (YES)**. See the first batch.
- **SD3 The escape neuron adds looming size and speed (PARTLY).** LC4 gives speed, LPLC2 gives
  size; silencing LPLC2 removes the size part (Ache et al. 2019; von Reyn et al. 2017). The
  loom's time course must be invented, and the giant fiber works with graded voltage and
  electrical synapses.
- **SD4 PFL3 steers (YES, batch 4).** See the first batch. The model's known left lean in
  DNa02 (Phase 6) could bias it; run both sides and several seeds.
- **SD5 Descending-neuron activation screen (NO)** and **SD6 MDN makes flies walk backward
  (NO)** (Cande et al. 2018; Bidaye et al. 2014). Both are about what descending neurons do to
  the legs, which happens in the nerve cord. They matter only as the read-out rules the brain
  tests rely on.

## 6. Temperature and humidity (5 items: 4 YES, 1 PARTLY)

A surprisingly good area: FlyWire labels the temperature and humidity sensory neurons by
glomerulus (TRN_VP2 warm, TRN_VP3a/b cool, HRN_VP4 dry, HRN_VP5 humid), and they spike.

- **TH1 Cool projection neurons follow cool sensors (YES)** and **TH2 cool sensors inhibit the
  warm pathway (YES, batch 6)**. Liu et al. 2015: 14 of 17 local neurons were excited by
  cooling and inhibited by warming, and blocking inhibition depolarised warm projection
  neurons by 6 +/- 1 mV. Which FlyWire projection neuron is the paper's "cool-PN" or
  "warm-PN" is a moderate-to-low confidence match.
- **TH3 Cold switches off DN1a (YES, batch 5).** See the first batch.
- **TH4 Cooling excites DN1p clock cells (PARTLY).** Yadlapalli et al. 2018. Part of their input
  comes from body thermoreceptors in the nerve cord.
- **TH5 Humid-only and mixed humidity-temperature projection neurons (YES).** One projection
  neuron type answers only to humid air; "broad" ones combine dry air with temperature (Frank
  et al. 2017). Test: drive each sensor type alone and in pairs; read all VP projection
  neurons.

## 7. Pheromones and female courtship (5 items: 4 YES, 1 PARTLY)

The best area for a first batch: small circuits, every cell labelled in the 630 table, and
the model is a female brain like the flies in these papers.

- **FC1, FC2, FC5**: see the first batch.
- **FC3 pC1 brakes egg laying through oviIN (YES).** pC1 excites the GABA-releasing oviIN,
  which inhibits the egg-laying descending neurons oviDN (Wang et al. 2020, Fig. 4f). Their
  other input, oviEN, is not named in FlyWire, so give oviDN a steady background input instead.
- **FC4 pC1d/e leave minutes-long activity (PARTLY).** A brief pC1d/e activation leaves
  activity in pC1 and aIPg that lasts minutes (Deutsch et al. 2020, Fig. 8). The model has no
  slow processes, so this is a hard test of whether its recurrent wiring can hold activity
  without running away. Expect a fail; it is still worth knowing.

## 8. Vision (2 items: 1 PARTLY, 1 NO)

Most early visual neurons (photoreceptors, lamina, T4/T5 motion detectors) do not fire
spikes; they signal with graded voltage. A spiking model with invented input cannot test
them honestly, and the model has no eyes.

- **VI1 T4/T5 motion detectors (NO).** Maisak et al. 2013. Listed to record the limit.
- **VI2 The compass bump persists in darkness (PARTLY).** The E-PG "compass" bump stays in
  place in darkness (Seelig & Jayaraman 2015). Test: briefly drive one wedge of E-PGs, then
  watch whether one bump stays.

Vision results that start at spiking visual projection neurons (LC16, LC4, LPLC2) are
testable and are listed under steering (SD1-SD3).

---

## What is not verified

- **22 of 39 items were checked against the abstract only.** Their figure numbers say "not
  checked". Before an item is scored, someone should read its figure to confirm the exact
  condition (for example, which side wins in SD2).
- **Cell-identity matches rated moderate or low.** Especially: which FlyWire projection
  neurons are Liu et al.'s cool-PN and warm-PN (TH1, TH2), TPN-II = VP3+_vPN (TH3; three
  lines of evidence, no direct match), V2a/V2a' = MBON18/MBON16-17 (LL1; from Aso et al.
  2014, not re-checked here), and the aSP-f/g/h clusters (FC5; FlyWire's literature
  synonyms, and the paper recorded only a sample of each cluster).
- **Possible overlap with the Shiu et al. 2024 paper's own checks** for TF1, TF4 and TF5
  (it named Fdg, Usnea, Phantom and Clavicle). Not checked in the paper's figures.
- **Not found in FlyWire:** TPN3 (taste), oviEN (egg laying), the wedge projection neurons
  (wind). Items that need them say so.
- **2 neurons could not be mapped to 630** (hearing sensory neurons, 783 IDs
  720575940615041064 and 720575940639742627; nearest 630 neuron 5.7-5.9 micrometres away).
  They are blank rows in MG1 and MG2 (4 of 3,125 ID rows).
- No simulation was run. Every "expected" result is the real-fly result, not a model
  prediction.
