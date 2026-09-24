# Claims audit: do the numbers we quote match the saved results?

*Written 2026-09-23. Script: `experiments/claims_audit/audit.py`. Full table, one row per
claim: `experiments/claims_audit/results/audit.csv` (82 rows). Nothing was simulated for
this audit. It only re-read saved result files.*

## The short version

- **We re-checked 65 numbers and claims** that the results page and the docs' short
  versions rely on, plus 17 more we came across on the way (82 in all).
- **51 of the 65 match the saved results exactly**, to the digit quoted. Every headline
  result holds: MN9 67.0 vs the paper's 65.7, all seven Phase 3 experiments, the 12 of 12
  checks, the silencing screen (r = 0.93), the sugar/bitter competition, the ±20% tests,
  the runaway counts (90 of 90 vs 0 of 90), the DA1 steering numbers, every learning
  percentage, the body demo and the video.
- **1 real mistake on the results page.** The learning paragraph calls the neuron that
  lost 91% of its input the "avoid" output neuron. It is the **"approach"** output neuron
  (the Phase 8 doc says so). The 91% is right; only the label is wrong.
- **6 are ambiguous:** true in one reading, misleading in another. The main ones: "12 of
  12" for the one-antenna fly (in plain terms it turned toward the smell in 11 of 12);
  "every runaway begins at the 38 excitatory local neurons" (the start is among the smell
  centre's local neurons, but one of those 38 fires first in only 3 of 6 traced
  runaways); "about 8,300 neurons"; the Brian2 timing and speed-up; "counts match FlyWire's".
- **7 have no saved source in the repo:** five of the paper's own numbers (they came from
  the authors' result files, which were never saved here), the "app gives the same
  answer as code" check (it was printed, not saved), and the real-fly 90% from Hige 2015.
  That last one matters: **the model's learning speed was tuned to give 90%**, so the
  91% agreement is a calibration, not a test.
- **Among the 17 extra checks, 3 small errors inside the docs** (a neuron count, a folder
  that does not exist, a "1 Hz" that is really 3 Hz). None of them changes a conclusion.
- **Nothing found changes any conclusion.** The fixes are wording.

## How the audit worked

For each claim, `audit.py` goes back to the rawest saved file it can find (every spike of
Phase 3, the per-trial table of each experiment, the raw connection lists) and
recomputes the number itself. It does not trust the summary tables the experiments wrote,
and it does not trust one doc repeating another. Where a quoted number is the paper's, it
is checked against the paper's own supplementary table if a copy is saved here.

- **MATCH:** the recomputed number rounds to the quoted one.
- **MISMATCH:** it does not, or the words say something the data do not.
- **AMBIGUOUS:** the number is right under one reading and misleading under another, or
  the docs give different numbers for the same thing.
- **NO-SOURCE:** nothing saved in the repo can confirm it. The table names what would
  regenerate it.

Two passes read the full connection lists (about 15 million rows each), in pieces, to
count synapses. Everything else reads small files.

## The mistake on the results page

| Where | What it says | What the data say | Suggested wording |
|---|---|---|---|
| Results page, Learning section, first paragraph after "We added the published learning rule" (source line 364) | 'Afterwards the "avoid" output neuron got about 91% less input from odor A' | The read-out is MBON-γ1pedc>α/β. `docs/phase8-learning.md` (section 3) and the analysis code both class it as an **approach** neuron. The "avoid" neuron is MBON-γ5β'2a, the reward read-out. | 'Afterwards the "approach" output neuron got about 91% less input from odor A...' |

Why it matters: punishment learning works by weakening the *approach* signal for the
punished smell. Calling it the "avoid" neuron gets the story backwards.

## Ambiguous claims, with suggested wording

| Claim, and where | What the saved results show | Suggested wording |
|---|---|---|
| **"12 of 12 trials"** for the one-antenna fly. Results page, "One antenna covered" bullet (line 271); `docs/phase9-da1-demo.md` short version (line 25). | "12 of 12" counts trials where the fly turned further toward the smelling side **than the silenced fly of the same seed**. In plain terms, 11 of 12 turned toward the smelling side; the 12th (right antenna smelling, seed 0) turned 1.2° the wrong way. Also, the silenced fly's "0°" is exactly zero by design: in each seed it drifts the same 7-14° in every layout (left in one seed, right in the other two), and half the layouts count that as "toward" and half as "away", so the average cancels. The doc's table says "11/12 (12/12 against the same-seed control)"; the page does not. | Page: "It turned toward the smelling side in 11 of 12 trials, and further than the silenced fly of the same seed in all 12 (+31° on average in the first second, p = 0.0006)." |
| **"Every runaway begins ... at 38 excitatory local neurons."** `docs/phase6-runaway-activity.md` short version (line 21). The page (line 339) says "Every case starts at the same few dozen local neurons", which is closer. | Only 6 runaways were traced (all from taste input). In the 50 ms before each one takes off, the first neuron to fire is a smell-centre local neuron in 4 of 6, and one of the 38 in only 3 of 6. Among the first 10 to fire, 5-7 are smell-centre local neurons but only 0-3 are from the 38. The doc's own section 4a lists v2LN30 and lLN2X03, which are not in the 38, among the very first. What *is* solid: silencing the 38 stops the runaways started by taste input and by a brief smell pulse (0 of 60 vs 9 of 60). But Phase 7 found that strong, steady DM1 smell still runs away in 90 of 90 trials when only these neurons are fixed. | Doc: "Every runaway we traced begins among the smell centre's local neurons. Silencing 38 of them, the 'excitatory local neurons', stopped every runaway started by taste input or by a brief smell pulse." Page: "Every case we traced starts among a few dozen local neurons..." |
| **"About 8,300 neurons fire non-stop."** Results page, Runaway section (line 339); `docs/phase6-runaway-activity.md` short version (line 9), whose own section 4b (line 202) says "about 8,500". | 8,300 is the count from one Phase 3 trial (8,304). Across the saved runaway trials, about 8,200 neurons fire at all (median of 26 in Phase 6, and of 280 in Phase 7), and about 7,700 are still firing at the end of the second. Individual trials range from about 4,800 to 8,500. | "about 8,000 neurons" (both places), or give the range. |
| **Brian2 takes "1-4 minutes"** per simulated second. Results page, Fast engine row (line 287). `docs/phase3-explained.md` says "1 to 5 minutes" (line 52); `docs/fast-engine-explained.md` says 21-55 s. | The 55 saved Brian2 trials took 1.0 to 6.5 minutes, typically 1.9 minutes; 7 took over 4 minutes. They ran two at a time, which slowed them. The 21-55 s figures are for one run alone or a synthetic network. Three places, three different figures. | Page: "...instead of about 2 minutes (1 to 6.5 minutes in our Phase 3 runs)". Phase 3 doc: "between 1 and 6.5 minutes". |
| **"Hundreds of times faster."** Results page, Phase 3 "How sure" (line 234), versus "about 100 times faster" in `docs/fast-engine-explained.md` (line 4). | Against the saved Phase 3 Brian2 trials it is about 240-300 times faster. Against the fast-engine doc's own Brian2 figures (21-55 s) it is about 45-145 times. Both are defensible; they should agree. | Both places: "about 100 to 300 times faster, depending on how the Brian2 run is timed". |
| **"Counts match FlyWire's."** Results page, Phase 2 row (line 285). | The synapse count (54,492,922) and the strong-connection counts (2,700,513 connections, 134,181 neurons) match exactly. The neuron count does not: 138,639 here vs 139,255 in FlyWire's list. The 616 missing neurons have no synapses at all, so they cannot matter. | "Synapse counts match FlyWire's exactly; 616 neurons with no connections are left out." |

Two more ambiguities turned up among the extra checks:

| Claim, and where | What the saved results show | Suggested wording |
|---|---|---|
| **38 vs "about 44"** excitatory local neurons. `docs/phase6-runaway-activity.md` (line 21) says 38; `docs/phase7-neurotransmitter-audit.md` short version (line 11) says "about 44". | Both are right for different lists: 38 in the snapshot-630 brain the model runs on; 48 of these types in FlyWire's newer annotation, 44 of them with a literature transmitter. The Phase 6 doc explains this (section 4c); the Phase 7 short version does not. | Phase 7: "the 38 excitatory local neurons (44 in FlyWire's newer annotation)". |
| **Whole-brain punishment learning "cannot be seen."** `docs/phase8-learning.md` short version (line 43). | Out of date, not wrong at the time. With the later `+da_5ht_literature` switch, the trained smell dropped more than the other smell in 6 of 6 paired runs (`docs/phase7-neuromodulators.md`). The page already says this correctly. | Add one line to the Phase 8 short version pointing to `docs/phase7-neuromodulators.md`. |

## No saved source

| Claim, and where | Why it cannot be checked here | What would settle it |
|---|---|---|
| The paper's MN9 for water 200 Hz (30.7), bitter 200 Hz (0.0), sugar 100 + bitter 40 (45.3), sugar 100 + bitter 120 (1.5) and sugar 200 + Ir94e 200 (64.3). `docs/phase3-explained.md` lines 82-86; the page's Phase 3 bar chart. | They were copied from the authors' own result files into `docs/reference-notes.md`, but those files were never saved in the repo. The Phase 3 doc already labels them UNVERIFIED. (The paper's sugar numbers, 65.7 and 93.2, **are** confirmed: the paper's Supplementary Table 1A is saved here.) | Download `results.zip` from Edmond (address in `docs/reference-notes.md` 3.1), save `figure_3/fig_3a_rate.csv`, `fig_3b_rate.csv` and `figure_4/fig_4a_rate.csv` under `data/reference/`, and re-run the audit. |
| The app gives the same MN9 as code. Page, Phase 4 row (line 288); `docs/phase4-app-explained.md` line 182. | The code side is saved and matches (67.63 Hz, `experiments/fast_engine/results/summary.json`). The app side was printed to the terminal and never saved. | `.venv\Scripts\python.exe -m app.run_setup sugar_grn_right --compare`, with its printout saved to a file. It loads the whole brain, so it was not run here. |
| Real flies show 90% less (Hige et al. 2015). Page, Learning (line 364); `docs/phase8-learning.md` line 23. | A number from a paper, not a saved result. **More important:** `experiments/phase8/results/calibration.json` shows the learning speed was fitted to give a 90% drop (on separate seeds). So our 91% agreeing with 90% is by design. The real tests are the controls (no pairing, no learning). The Phase 8 doc says this in section 2.3; the short version and the page do not. | Page: "Real flies show 90% less (Hige et al. 2015); we set the learning speed to match that, so the real test is that nothing is learned without pairing." |
| 211 automated tests pass. Page header (line 207). | No saved log of a full test run. A quick count finds 168 test functions; tests that run several cases count more than once. | `.venv\Scripts\python.exe -m pytest -q` (some tests load the whole brain). |

## Small errors inside the docs

These were not on the requested list; none is in a short version.

| Where | What it says | What the data say | Suggested fix |
|---|---|---|---|
| `docs/phase3-explained.md` line 97 | "Their run has 16 or 17 more active neurons than ours" | At 200 Hz it is 16 more (448 vs 432). At 100 Hz it is 12 more (404 vs 392): 17 fire only in theirs, 5 only in ours. The "less than once every 4 seconds" part holds. | "Their runs have 16 (200 Hz) and 17 (100 Hz) neurons that never fired in ours, all firing less than once every 4 seconds." |
| `docs/phase3-explained.md` line 170 | the files are in "`results/v630/`, `results/v783/`" | `experiments/phase3/results/v783/` does not exist (the snapshot-783 run was dropped, as the same doc says). | Delete "`results/v783/`" from that line. |
| `docs/phase5-competition.md` line 84 | "Across seeds the averages differ by at most about 1 Hz" | Up to 3.1 Hz (sugar 50 + bitter 25). 7 of the 24 cells differ by more than 1.5 Hz. The largest standard deviation across seeds is 1.6 Hz. The pattern is still stable. | "...differ by at most about 3 Hz (standard deviation at most 1.6 Hz)." |

## Everything that matched

| Topic | Checked | Result |
|---|---|---|
| Phase 3, ours | MN9 for all seven experiments: 67.0, 92.7, 33.5, 0.0, 48.0, 0.9, 58.4 Hz; the same-side MN9 (51.4, 62.9) | all match, recomputed from every saved spike |
| Phase 3, the paper | 65.7 and 93.2 Hz for sugar 100 and 200 | match the paper's own Supplementary Table 1A (65.70 and 93.23) |
| Phase 3 checkpoint | 12 of 12 direction checks; 5-10 trials per condition (55 in all); correlation 0.9996 over 448 neurons; MN9 about 67 without the one runaway trial | all match. Note: 2 of the 12 checks are the same comparison counted twice, so there are 11 distinct checks. |
| Fast engine | same spikes as Brian2 (5 whole-brain trials replayed: identical totals, runaway timing and first 100 ms); 0.2-0.5 s and ~0.3 s per simulated second | match (a single 10-second trial ran at 0.68 s per second) |
| Phase 2 | 127,400 neurons and 14,687,178 connections (630); 138,639 neurons, 15,091,983 connections and 54,492,922 synapses (783); cached load under half a second (0.45 s and 0.37 s, as logged) | all match, counted from the raw data files |
| Phase 4 | MN9 67.63 Hz from code, same settings as the app's saved setup | match |
| Silencing screen | r = 0.93 over 198 neurons at 100 Hz (0.9305) and 50 Hz (0.9334) | match. It is the ordinary (Pearson) correlation; ranked, it is only 0.58-0.65, because a few big effects carry it. |
| Competition | within 2.5 Hz of the paper at all 13 points (largest gap 2.40 Hz); MN9 halves at 0.47-0.56 times the sugar rate (fit redone: 0.465, 0.541, 0.556, 0.561); 3.3- to 4.6-fold steepness; CB0219 gets 247 synapses from bitter neurons and none from sugar neurons (counted from the raw connection list); silencing it restores MN9 from 12.4 to 65.7 Hz, 97.6% recovery; heat-map cells are 3 seeds × 30 trials | all match |
| Sensitivity | sugar holds in 28/28 and 15/15; size -47.2% to +18.7%; water flips in 3/28 (synaptic weight -20%, threshold gap +20%, synaptic time constant -20%) and 1/15; bitter holds everywhere | all match. The doc's "5.0 Hz" water seed is really 4.97, just under the 5 Hz cut-off, which is why only 1 of 3 seeds holds there. |
| Runaway | DM1 smell 90/90 on the published model vs 0/90 with `al_ln_literature` (both, left and right); Ir94e 200 Hz 10/90 vs 0/90 | match |
| Steering | DM1's left PN gets 52% more receptor synapses (3,724 vs 2,450, counted from the raw connection list); 19 of 51 glomeruli fail to mirror; DA1 left 22.69 vs 1.01 Hz, right 15.73 vs 0.14 Hz, right side wins in every seed; DA1 is the only one of the 6 tested channels that mirrors | all match |
| Learning, circuit | -91% vs -9% (5 of 5 flies); swapped -89% vs -6%; unpaired +0.2%; odor alone +0.2%; dopamine alone 0.0%; reward -78% vs -8%; PAM-α1 -94% vs -12%; α2 1 s -10% vs 60 s -94%; backward -9% | all match, recomputed from the per-fly before/after table |
| Learning, whole brain | reward -98% vs -4% (3 of 3); with `+da_5ht_literature`, test smells alone lower the read-out by 38.7% (3% to 76%) | match. The reward numbers are the raw changes (-98.5%, -4.1%), while the circuit numbers are measured against a no-training control. Measured that way the reward reads -97.5% vs -4.6%. |
| Body demo | +31° vs 0°, p = 0.0006 (0.00058); normal fly left in 15 of 15, toward the source 6 of 12, closest approach 4.1 vs 4.2 mm, p = 0.87; DNpe002 7 of 12; hand-written rule 5 of 5 | all match |
| Video | re-runs equal the saved trials (the two saved files agree exactly; the 1.4e-14 is rounding when the file was written); clip A is 2nd of 12 (63.2° beyond the silenced fly; the 12 range 8.2-74.5°); 142 trials in the demo | all match |
| Page header | 28,101 lines of Python, 26 commits, 24 write-ups | match the repo at commit 9bcdac4, the one the page describes. Other lanes' work has been committed since (now 29,339 / 27 / 25), so refresh these whenever the page is republished. |

## Other things worth knowing (not errors)

- **The paper has two sets of "sugar alone" numbers.** Phase 3 compares with 65.7 and
  93.2 Hz (the paper's Figure 1). The competition doc compares with 67.0 and 94.9 Hz (its
  Figure 3b, a separate run). Both are the paper's own numbers, so neither doc is wrong.
- **The competition doc uses two sets of numbers for the same experiments without saying
  so.** Section 3 uses seed 0 (sugar 40 + water 200: 61.8 Hz; sugar 40 alone: 6.1 Hz).
  Section 6 uses the three-seed average (62.4 and 5.5 Hz). Both are correct.
- **The fast-engine doc gives two MN9 values for sugar 100 Hz,** 67.6 and 69.7 Hz. They
  come from two different 30-trial runs with different random input. Both are saved.
- **Single flies vary a lot in the whole-brain punishment test.** On average the untrained
  smell falls 41-47%, but in one fly it fell 77%. The neuromodulator doc already says
  only 5 of 6 paired runs count as clearly learned.

## Re-running the audit

From the repo root: `.venv\Scripts\python.exe experiments\claims_audit\audit.py`. It takes
about a minute, needs about 1.5 GB of free memory for the two passes over the connection
lists (it waits until that is free), and rewrites `results/audit.csv`. Page line numbers
refer to the results page's source file, `fly-brain-results.html`.
