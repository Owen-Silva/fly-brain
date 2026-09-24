# Does the simulation match a real fly? The combined scorecard

Prepared 2026-09-23. This combines the tests so far that compare the model with
**measurements from real flies** (a few others are listed at the end of "What each area
tested"). Matches with the Shiu et al. 2024 paper's *model* are not counted here; those
only show our copy of their model is faithful. Every verdict is **PRELIMINARY**. Most come
from a lane doc that wrote its pass rule down before running; the Phase 6 steering,
bitter-brake and learning results had no pass rule written in advance.

## The short version

- **With the recommended fix (`al_ln_literature`): 13 of 35 real-fly tests match, 6
  partly match, 11 miss, and 5 can't be scored.** Two of the matches/partials are circular
  (the cell labels come from the same papers); without them it is 12 of 33 match. One
  more match (no learning without pairing) is built into the learning rule, so it is
  weak evidence.
- **The published model: 7 match, 3 partly, 13 miss and 4 can't be scored, out of 27.**
  Its 8 smell tests were not scored at all, and all its extra misses come from the
  runaway. Every smell and temperature input tips it into non-stop firing, which a real
  fly never does.
- **The answer:** the model gets a lot of the brain's broad design right. That includes
  sparse smell coding, the mushroom body's brake neuron, the bitter brake on feeding,
  temperature pathways, turning toward a stimulated side and the grooming pathway. It gets
  several specific pathways wrong: pheromones, some learning-circuit outputs, water vs
  sugar cells, hunger/thirst state, and steering toward vinegar or with both antennae.
  For learning, the one match is built into the rule and backward training misses.
- **Likely reasons for the misses** (not yet tested causally): missing slow chemical
  signals (hunger state, neuromodulators), wrong transmitter guesses, quirks of the one
  fly FlyWire mapped, whether biology or reconstruction (docs/banc-asymmetry.md), a left
  lean in the steering circuit that has not been traced, every neuron treated as a
  spiking cell, and no nerve cord.

## The tally, by area (every verdict PRELIMINARY)

| Area (source doc) | Tests | With the fix: match / partial / miss / can't tell | Published model |
|---|---|---|---|
| Scorecard batch 1 (docs/real-fly-scorecard-batch1.md) | 10 | 4 / 2 / 3 / 1 | 2 / 3 / 5 / 0 |
| Smell vs real recordings (docs/olfaction-vs-real-fly.md) | 8 | 3 / 4 / 1 / 0 | not scored separately; runs away on every odour |
| Grooming, Hampel 2015 (docs/heldout-validation.md) | 6 | 3 / 0 / 2 / 1 | 3 / 0 / 2 / 1 |
| Feeding state: ISNs, OA-VPM4 (docs/heldout-validation.md) | 5 | 0 / 0 / 2 / 3 | 0 / 0 / 2 / 3 |
| Steering (docs/phase6-steering.md, docs/phase9-da1-demo.md, docs/phase9-sameside.md) | 3 | 1 / 0 / 2 / 0 | 0 / 0 / 3 / 0 |
| Bitter brake, Scapula (docs/phase6-literature-check.md) | 1 | 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 |
| Learning controls, mushroom-body circuit only (docs/phase8-learning.md) | 2 | 1 / 0 / 1 / 0 | 1 / 0 / 1 / 0 |
| **Total** | **35** | **13 / 6 / 11 / 5** | **7 / 3 / 13 / 4** (27 tests; smell not scored) |

## What each area tested

- **Batch 1:**
  - Matches:
    - vpoDN excitation (circular);
    - one-sided PFL3 turning (100% vs ~92% in flies);
    - cold inhibits DN1a via TPN-II;
    - cool sensors inhibit warm projection neurons.
  - Partial:
    - pC1a vs pC1b (circular; no big gap);
    - LC16 drives the backward-walking neurons at one input level only.
  - Misses:
    - the male pheromone never reaches aSP-g;
    - MVP2 does not suppress M4/6;
    - Usnea responds to sugar as well as water.
  - Can't tell: sister-PN synchrony (the PNs were silent at low input).
  - Published model: the runaway turns the DN1a result and sister-PN synchrony into
    misses, and the warm-PN result into a partial.
- **Smell:**
  - Matches:
    - lateral inhibition is about the right size (75-85% vs 50-78%), though it pushes
      weak input below rest;
    - PN responses follow the real-fly equation (r = 0.85);
    - blocking APL makes coding denser and more alike (3.0% to 11.3% of KCs).
  - Partial:
    - KC sparseness: 3.0% vs ~5%, just under the 3% line (3.9%, a match, when the
      unmeasured receptors are filled in from estimates);
    - weak input is boosted, but PNs need about 3 times more sensor firing;
    - odour patterns get more alike in the antennal lobe, so KCs end up less distinct
      than in flies;
    - KCs fire too many spikes.
  - Miss: PN tuning is not broadened.
  - Not one of the 8 facts: with the fix, no odour set off the runaway (0 of 1,332
    trials). The published model runs away on every odour, and with no odour at all, so
    the doc scores none of its facts.
- **Grooming (Hampel 2015):** 3 right. 2 wrong: JO-F never reaches aBN2/aDN1, and aBN2
  excites aDN2 where flies show inhibition. 1 can't tell (aDN2 was to be judged against
  aDN1, which stayed silent). A seventh result was set aside before running as
  ill-posed. Both versions give identical runs, spike for spike: the fix changes only
  smell cells, which never fire here, so these tests cannot tell the two apart.
- **Feeding state:** driving the ISNs reverses both halves of the real-fly result (2
  misses). Real flies take more sugar and less water (Jourjine et al. 2016); in the model
  the feeding motor neuron responds less to sugar and more to water. OA-VPM4 barely moves
  it (can't tell), and the two switch-off tests can't be scored because neither cell type
  fires during tasting in the model. Identical in both versions, as for grooming.
- **Steering:**
  - Match (fix only): a one-antenna fly turns toward the smelling side (DA1). It is weak:
    the right side turns less, and the fly does not reach the source. Phase 9's own
    verdict, which also counts the two-antenna failure below, is PARTIAL. The same-side
    re-test (docs/phase9-sameside.md) confirms the turn, 12 of 12 against a silenced twin;
    it is not counted as a new test.
  - Misses, in both versions:
    - a DM1 (vinegar) smell on either side turns the model left (flies turn toward it;
      Gaudry et al. 2013). A body test with vinegar also failed
      (docs/phase9-body-loop.md). DM1's lopsided first relay is mostly a quirk of the one
      fly FlyWire mapped (docs/banc-asymmetry.md). A diagnostic added afterwards, with
      that map evened out, let a one-antenna vinegar fly turn toward the smell, which
      suggests the lean can be overcome; it was not pre-registered, so it is not counted;
    - a normal two-antenna fly turns left regardless (15 of 15 trials). Adding the
      missing same-side effect (Gaudry et al. 2013) did not help: still 15 of 15 left, and
      the same with a hand-balanced map (docs/phase9-sameside.md). The lean is not in the
      smell map: the left and right cVA projection neurons fire within about 3% of each
      other, yet DNa02 fires about 12 Hz on the left and almost nothing on the right.
      Where it comes from has not been traced.
  - The published model fails all three: it runs away and turns hard left for every smell
    on either side (Phase 6 brain-only runs; its two-antenna body run used one seed).
- **Bitter brake:** the model's CB0219 is the published Scapula brake, which real-fly
  imaging supports (Shiu et al. 2022). It was found in the published model
  (docs/phase5-competition.md) and not re-tested with the fix. No real-fly test of
  Scapula itself has been found.
- **Learning** (run on the mushroom-body circuit alone, which is the same in both versions;
  in the whole published brain smell runs away, so no learning can be read there):
  - Match: no learning without pairing (+0.2%), as in real conditioning. The learning rule
    has this built in, so the doc treats it mainly as a check that the code does not leak.
  - Miss: backward training (dopamine before the smell) gives a small change (-9%) where
    flies show none (Hige et al. 2015). The doc calls this its one mismatch. It depends
    on how long dopamine lingers, a number not yet measured.
  - The 90% match with Hige et al. 2015 is a calibration, so it is not counted.
- **Not in the tally:**
  - the paper's own real-fly checks, which our copy reproduces, including misses the
    paper already reported (Roundup and FMIn; docs/phase5-sugar-pathway.md). With the
    2026 aBN2 cells, one of its grooming hits becomes a miss (docs/heldout-validation.md,
    section 3.2);
  - Phase 5's first, informal smell and steering checks (docs/phase5-olfaction.md,
    section 6), which overlap the rows above;
  - other model versions: Kenyon-cell sparseness with measured cell settings
    (docs/phase7-celltype-params.md) and whole-brain learning
    (docs/phase7-neuromodulators.md).

## What this means for the next step

The parts the brain-inspired computing plan would rely on are mostly among the
better-matching ones: sparse coding in the smell/memory system and the APL brake. The
local learning rule is less proven: its one match is built into the rule, and backward
training misses. The pheromone, hunger-state and learning-output misses matter less for that plan.
They are the known limits to fix if the goal were a more faithful fly.
