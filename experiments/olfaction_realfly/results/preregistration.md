# Pre-registration: real-fly smell facts and what counts as a match

Frozen 2026-09-23, before the main simulation runs (`run_odours.py`, `run_gain.py`).
Copied into `docs/olfaction-vs-real-fly.md` section 2 unchanged.

**What had been seen before freezing (disclosed):** a speed test (`speed_test.py`) with 3
inputs x 3 trials x 0.5 s, seed 0: in the `al_ln_literature` brain, spontaneous ORN input
alone gave 0.37% of KCs with >= 1 spike per trial; 1-hexanol 6.6%, ethyl butyrate 5.3%
(per-trial measure, not the reliable-responder measure below). In the published brain
(`none`) all three inputs, including spontaneous input alone, ran away. Nothing else.

**Inputs.** ORN rate = Hallem & Carlson 2006 spontaneous rate of that receptor + its odour
response (spikes/s, 10^-2 dilution, 0.5 s), never below 0, for the 23 glomeruli they tested
("set A"). Untested ORN types fire at 12 Hz (median tested spontaneous rate), no odour
response. "Set B" adds DoOR consensus responses back-projected to spikes/s for 23 more
glomeruli (missing odour = no response). Trials 0.5 s, constant rates from t = 0,
3 seeds x 4 trials per odour; "baseline" = spontaneous rates only.

**Definitions.** Evoked rate = odour-trial rate minus baseline rate, same neuron.
A KC "responds" to an odour if it fires >= 1 spike in at least half of the 12 trials
(Honegger 2011's "at least half of presentations" rule) and its mean count is above its
baseline mean. Lifetime sparseness: Vinje & Gallant (2000) formula over odours on
rectified evoked rates. Correlation: Pearson over neurons between two odours' evoked
vectors, averaged over all odour pairs.

| # | Real-fly fact (source; what we read) | Model measure | MATCH | PARTIAL | MISMATCH |
|---|---|---|---|---|---|
| F1 | On average an odour activates ~5% of KCs; no odour's mean above 10%; single flies up to 17% (Honegger et al. 2011, full text via PMC: "on average, an odor evokes responses in ~5% of the KCs"). Single-cell recordings: 6% (Turner et al. 2008, as quoted by Honegger). "~5-10%" (Lin et al. 2014 intro). | mean over odours of the fraction of KCs responding (set A and set B) | mean 3-10% and no odour above 20% | mean 1.5-3% or 10-20% | otherwise |
| F2 | PNs are less selective (lower lifetime sparseness) than their ORNs, in every glomerulus tested (7 glomeruli, 18 odours; Bhandawat et al. 2007, full text via PMC, Fig. 3b). | per glomerulus (23, set A): lifetime sparseness of ORN input vs its uPNs' evoked rates | PN < ORN in >= 80% of glomeruli and Wilcoxon p < 0.05 | 50-80% | < 50% |
| F3 | Weak ORN input is amplified, strong input is not: PN = Rmax * ORN^1.5 / (ORN^1.5 + sigma^1.5), Rmax = 165 spikes/s, sigma = 12 spikes/s (Olsen et al. 2010, full text via PMC; Bhandawat 2007 Fig. 6). | one glomerulus driven alone at 6 rates (DL5, DM4, DM1, VM7d); fit the same equation to the uPN evoked rate | saturating, with sigma 6-24 Hz and Rmax 83-330 Hz | saturating (gain at the lowest step > 2x gain at the highest) but parameters outside those bands | not saturating |
| F4 | Lateral inhibition: activity in other glomeruli suppresses a PN's response to its own ORNs, more as total ORN activity grows (Olsen & Wilson 2008 abstract; Olsen et al. 2010: s = m * total ORN, m = 10.63 mV / 190 mV s^2/spikes for VM7). | same 4 glomeruli, with a "public" odour (pentyl acetate pattern on all other glomeruli, x0.5 and x1) vs without | suppression present in all 4 and within 2x of the Olsen-2010 equation's size | present but outside 2x, or in 2-3 of 4 | absent or facilitation |
| F5 | The Olsen 2010 normalization equation, fed the Hallem & Carlson inputs, predicts real PN odour responses (it explained 95% / 87% of variance for VM7 / DL5 PNs). | correlation between model uPN evoked rates and the equation's prediction, 23 glomeruli x 110 odours | r >= 0.7 | 0.4-0.7 | < 0.4 |
| F6 | Odour representations become less correlated from ORNs to KCs (Turner et al. 2008 abstract); KC coding is "decorrelated" (Lin et al. 2014 abstract). | mean inter-odour correlation: ORN input, uPNs, KCs | KC < PN and KC < ORN | KC < one of them | KC >= both |
| F7 | Blocking APL output makes KC responses less sparse and more correlated between odours (Lin et al. 2014, abstract + full text via PMC, Fig. 5c-e; no numbers stated in text). | silence APL (both cells), set A | KC fraction up AND inter-odour KC correlation up | only one up | neither |
| F8 | KCs that respond fire only a few spikes (Lin et al. 2014 intro; Turner 2008). Not quantified in what we read. | median spikes per responding KC-odour pair in 0.5 s | median <= 5 | 6-10 | > 10 |

Published brain (`none`): report, per odour, whether it runs away (Phase 6 rule, driven
ORNs excluded from the count) with spontaneous input, and with odour-evoked input only.
Real flies smell without runaway, so any runaway is a mismatch with biology.
