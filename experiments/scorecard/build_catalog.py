"""Build the real-fly scorecard catalogue (experiments/scorecard/catalog.csv).

Plain English
-------------
Each ITEM below is one published measurement from REAL flies that the brain
model could be scored against. The text of each item (the fly result, the
source, the model test, the expected result, the feasibility) was written by
hand from the papers; see docs/real-fly-scorecard.md.

This script only does the book-keeping that must be exact: it looks every
named cell type up in FlyWire's own annotation tables and writes the
snapshot-630 root IDs (the IDs the model uses). It never runs a simulation
and never loads the connection tables.

How a cell type becomes 630 IDs:
  * "hb"/"ct": exact match on the 630 table's hemibrain_type / cell_type.
  * "783": the name only exists in the newer snapshot-783 table (its
    cell_type / hemibrain_type / literature synonyms). Each 783 neuron is
    mapped to 630 by (1) the same root ID if the neuron was never edited
    between snapshots, else (2) the 630 neuron whose soma (or, for sensory
    neurons without a soma in the brain, whose anchor point) lies within
    2 micrometres. The method used for every ID is written to ids_630.csv.
  * "ids": an explicit list copied from a named project file (the Shiu et al.
    2024 SEZ list in data/reference/sez_neurons.pickle, the model's taste
    input sets in sim/shiu_model.py, the grooming lane's ids.py).

Outputs (next to this file):
  catalog.csv   one row per item (the fields asked for in the task)
  ids_630.csv   one row per (item, role, cell group, neuron): every root ID
Run:  .venv\\Scripts\\python.exe experiments\\scorecard\\build_catalog.py
"""

from __future__ import annotations

import ast
import csv
import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
N630 = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"
N783 = ROOT / "data" / "cache" / "connectome_783_neurons.parquet"
SEZ = ROOT / "data" / "reference" / "sez_neurons.pickle"
SHIU = ROOT / "sim" / "shiu_model.py"
HELDOUT_IDS = ROOT / "experiments" / "heldout" / "ids.py"

COLS = ["root_id", "super_class", "cell_class", "cell_type", "hemibrain_type", "side",
        "top_nt", "soma_x_nm", "soma_y_nm", "soma_z_nm", "anchor_x_nm", "anchor_y_nm",
        "anchor_z_nm"]
MATCH_NM = 2000.0          # 2 micrometres
INLINE_MAX = 12            # list IDs inline in catalog.csv only for small groups
LIST_MAX = 2500            # groups bigger than this are described by rule only


# ---------------------------------------------------------------------------
# ID sources that live in project files
# ---------------------------------------------------------------------------
def _py_lists(path: Path) -> dict[str, list[int]]:
    """Top-level NAME = [ints] assignments in a .py file, read without importing it."""
    tree = ast.parse(path.read_text(encoding="utf8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                val = ast.literal_eval(node.value)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(val, (list, int)):
                out[node.targets[0].id] = val
    return out


SHIU_LISTS = _py_lists(SHIU)
HELD = _py_lists(HELDOUT_IDS)
with open(SEZ, "rb") as fh:
    SEZ_NAMES = {k.lower(): [int(x) for x in v] for k, v in pickle.load(fh).items()}

MN9 = [SHIU_LISTS["MN9_LEFT"], SHIU_LISTS["MN9_RIGHT_630"]]


def sez(name: str) -> dict:
    return {"ids": SEZ_NAMES[name.lower()],
            "src": f"Shiu et al. 2024 SEZ list (data/reference/sez_neurons.pickle, '{name}')"}


def shiu(name: str) -> dict:
    v = SHIU_LISTS[name]
    return {"ids": v if isinstance(v, list) else [v], "src": f"sim/shiu_model.py {name}"}


# Selector shorthands --------------------------------------------------------
def hb(name, side=None):
    return {"db": "630", "col": "hemibrain_type", "eq": name, "side": side}


def hbre(rx, side=None):
    return {"db": "630", "col": "hemibrain_type", "re": rx, "side": side}


def ct(name, side=None):
    return {"db": "630", "col": "cell_type", "eq": name, "side": side}


def ctre(rx, side=None):
    return {"db": "630", "col": "cell_type", "re": rx, "side": side}


def f783(col, rx, side=None):
    return {"db": "783", "col": col, "re": rx, "side": side}


def rule(text):
    return {"rule": text}


def none(text):
    return {"none": text}


# ---------------------------------------------------------------------------
# The catalogue. Field names follow the task brief.
# ---------------------------------------------------------------------------
TASTE, MECH, SMELL, LEARN, STEER, THERMO, COURT, VISION = (
    "Taste and feeding", "Mechanosensation and grooming", "Smell", "Learning",
    "Steering and descending neurons", "Thermo- and hygrosensation",
    "Pheromones and female courtship", "Vision")

ITEMS = [
    # ------------------------------------------------------------------ TASTE
    dict(id="TF1", area=TASTE, short="Fdg activation starts feeding",
         result="Switching on the single pair of Fdg ('feeding') neurons makes a fly run its whole feeding sequence, proboscis extension included, with no food present.",
         measure="behaviour",
         source="Flood et al. 2013, Nature 499:83 (doi:10.1038/nature12208)", figure="not checked (abstract only)", access="abstract",
         test="Drive both Fdg neurons (50 and 100 Hz), no taste input. Read both MN9s, the model's proboscis-extension motor neurons.",
         targets=[("stimulate", "Fdg", sez("Fdg")), ("read", "MN9 (left, right)", {"ids": MN9, "src": "sim/shiu_model.py MN9_LEFT, MN9_RIGHT_630"})],
         confidence="high: Fdg IDs are the Shiu lab's own FlyWire identification shipped with the model (FlyWire's 630 table has no label for them)",
         expected="MN9 fires clearly above zero in every seed.", numeric="none published in the abstract (direction only)",
         feas="YES", feas_why="Fdg and MN9 are both in the brain model; one short activation run.", cost="cheap", batch="",
         notes="Shiu et al. 2024 included Fdg among its 106 named SEZ types; check its figures so this exact comparison is not double counted."),
    dict(id="TF2", area=TASTE, short="One Fdg gives one-sided feeding",
         result="Activating only one of the two Fdg neurons makes feeding movements lopsided, and killing one Fdg makes sugar-evoked feeding lopsided.",
         measure="behaviour", source="Flood et al. 2013, Nature 499:83", figure="not checked (abstract only)", access="abstract",
         test="Drive the left Fdg alone, then the right Fdg alone. Compare left and right MN9.",
         targets=[("stimulate", "Fdg, one at a time", sez("Fdg")), ("read", "MN9 (left, right)", {"ids": MN9, "src": "sim/shiu_model.py"})],
         confidence="high for the cells; moderate that a left/right MN9 difference is the right read-out",
         expected="The two MN9s respond unequally, and the stronger side flips when the other Fdg is driven.", numeric="none (direction only)",
         feas="PARTLY", feas_why="The model can show a left/right MN9 difference, but 'lopsided feeding' is a proboscis movement that MN9 alone may not capture (other motor neurons, no body).",
         cost="cheap", batch="", notes=""),
    dict(id="TF3", area=TASTE, short="Fdg needed for sugar feeding",
         result="Silencing or killing the Fdg neurons abolishes sugar-induced feeding, and Fdg respond to food only in starved flies.",
         measure="behaviour; electrophysiology and calcium imaging", source="Flood et al. 2013, Nature 499:83", figure="not checked (abstract only)", access="abstract",
         test="The model's standard sugar input (21 sugar taste neurons, 100 Hz) with and without both Fdg silenced. Read MN9; also read Fdg itself during sugar input.",
         targets=[("stimulate", "sugar taste neurons (model's standard set)", shiu("SUGAR_R_630")), ("silence", "Fdg", sez("Fdg")),
                  ("read", "MN9 (left, right)", {"ids": MN9, "src": "sim/shiu_model.py"}), ("read", "Fdg", sez("Fdg"))],
         confidence="high for the cells",
         expected="Sugar-evoked MN9 falls to near zero with Fdg silenced.", numeric="none (direction only)",
         feas="PARTLY", feas_why="Silencing is easy, but the model has no hunger state, and Shiu et al. 2022 found Fdg does not respond to taste on the proboscis (only to optogenetic sugar-neuron activation), so the fly's Fdg route may run through throat or leg sugar sensors the model lacks.",
         cost="cheap", batch="", notes="May overlap the Shiu 2024 silencing screen if Fdg was in it; the real-fly comparison (Flood 2013) is the new part."),
    dict(id="TF4", area=TASTE, short="Which feeding neurons see water vs sugar",
         result="Calcium imaging of second-order taste neurons: Usnea responds to water only, Phantom responds about equally to water and sugar, Clavicle responds to sugar (and to water only in a thirsty-like state); Fdg ignores taste on the proboscis but responds when sugar sensory neurons are switched on optogenetically.",
         measure="calcium imaging", source="Shiu et al. 2022, eLife 11:e79887 (PMC9292995)", figure="Fig. 3; Fig. 3 figure supplement 1A, 1C", access="full text (searched)",
         test="Drive the model's water taste neurons, then its sugar taste neurons (standard sets). Read Usnea, Phantom, Clavicle and Fdg.",
         targets=[("stimulate", "water taste neurons (model's standard set)", shiu("WATER_R_630")), ("stimulate", "sugar taste neurons (model's standard set)", shiu("SUGAR_R_630")),
                  ("read", "Usnea", sez("usnea")), ("read", "Phantom", sez("phantom")), ("read", "Clavicle", sez("clavicle")), ("read", "Fdg", sez("Fdg"))],
         confidence="high: all four are the Shiu lab's own FlyWire identifications",
         expected="Usnea: water >> sugar. Phantom: water about equal to sugar. Clavicle: sugar > water (the model behaves like a hungry fly). Fdg: fires to sugar-neuron drive.",
         numeric="none (a 4-cell pattern of which input each cell prefers)",
         feas="YES", feas_why="Same taste inputs as Phase 3; only the read-outs are new. All cells spike.", cost="cheap", batch="10",
         notes="Shiu et al. 2024 may have compared some of these model responses with this imaging; confirm before counting as held-out."),
    dict(id="TF5", area=TASTE, short="Which feeding neurons start or are needed for proboscis extension",
         result="Optogenetic activation of Usnea triggers proboscis extension, activation of G2N-1 or Clavicle increases it in food-deprived flies, activation of Fudog does not; hyperpolarising Rattle or Usnea reduces extension to 100 mM sucrose, while hyperpolarising other second-order neurons does not.",
         measure="behaviour", source="Shiu et al. 2022, eLife 11:e79887", figure="Fig. 4A and 4D (G2N-1, Clavicle); Usnea/Fudog activation and Rattle/Usnea silencing legends sit with Fig. 1 figure supplement 2B-C (located by text position, not seen)", access="full text (searched)",
         test="Drive Usnea, G2N-1, Clavicle and Fudog one at a time (50 Hz); read MN9. Then silence Rattle or Usnea during the standard sugar input; read MN9.",
         targets=[("stimulate", "Usnea", sez("usnea")), ("stimulate", "G2N-1", sez("G2N_1")), ("stimulate", "Clavicle", sez("clavicle")), ("stimulate", "Fudog", sez("fudog")),
                  ("silence", "Rattle", sez("rattle")), ("silence", "Usnea", sez("usnea")), ("read", "MN9 (left, right)", {"ids": MN9, "src": "sim/shiu_model.py"})],
         confidence="high for the cells",
         expected="MN9 up for Usnea, G2N-1 and Clavicle, not for Fudog; silencing Rattle or Usnea lowers sugar-evoked MN9.",
         numeric="none (yes/no per cell type; n = 30-144 flies per genotype)",
         feas="YES", feas_why="All cells and MN9 are in the model; each is one short run.", cost="cheap", batch="",
         notes="The silencing half probably overlaps the already-covered Shiu 2024 silencing screen; the activation half may overlap Shiu 2024's own checks."),
    dict(id="TF6", area=TASTE, short="Bitter acts at the premotor stage, not earlier",
         result="Adding bitter-neuron activation to sugar-neuron activation strongly cuts the premotor neuron Roundup's response, while the second-order neuron G2N-1 directly upstream of Roundup responds the same with or without bitter.",
         measure="calcium imaging", source="Shiu et al. 2022, eLife 11:e79887", figure="Fig. 5B-C", access="full text (searched)",
         test="Standard sugar input alone vs sugar + standard bitter input. Read Roundup and G2N-1.",
         targets=[("stimulate", "sugar taste neurons", shiu("SUGAR_R_630")), ("stimulate", "bitter taste neurons", shiu("BITTER_R_630")),
                  ("read", "Roundup", sez("roundup")), ("read", "G2N-1", sez("G2N_1"))],
         confidence="high for the cells",
         expected="Roundup drops a lot with bitter added; G2N-1 changes little.", numeric="none ('dramatically decreased' vs 'indistinguishable')",
         feas="YES", feas_why="One pair of runs with existing inputs.", cost="cheap", batch="",
         notes="Related to the already-covered Scapula/CB0219 brake (Scapula is the proposed inhibitor of Roundup); the new part is the G2N-1 control."),
    dict(id="TF7", area=TASTE, short="One dopamine neuron boosts sugar acceptance",
         result="Activating dopamine neurons increases proboscis extension to sucrose (not to bitter or water), silencing them reduces it, and one SEZ dopamine neuron (TH-VUM) triggers extension and changes its activity with satiety.",
         measure="behaviour; calcium imaging", source="Marella, Mann & Scott 2012, Neuron 73:941 (PMC3310174)", figure="not checked", access="abstract",
         test="Drive TH-VUM with weak sugar input; read MN9.",
         targets=[("stimulate", "TH-VUM", sez("TH_VUM")), ("read", "MN9", {"ids": MN9, "src": "sim/shiu_model.py"})],
         confidence="high for the cell",
         expected="Real fly: more extension to sugar.", numeric="none",
         feas="NO", feas_why="The effect is dopamine modulation (slow). The published model treats dopamine as fast excitation, so a 'pass' would be for the wrong reason; with the Phase 7 slow-signal switch TH-VUM has no effect outside the mushroom body. Same problem the held-out lane found for OA-VPM4.",
         cost="cheap but uninformative", batch="", notes="Listed to show a clear model limit."),
    # ------------------------------------------------------------ MECHANO
    dict(id="MG1", area=MECH, short="Courtship song reaches vpoEN",
         result="The female's vpoEN neurons are auditory neurons tuned to specific features of the D. melanogaster courtship song, and they excite the vpoDN descending neurons that open the vaginal plates.",
         measure="calcium imaging", source="Wang et al. 2021, Nature 589:577 (doi:10.1038/s41586-020-2972-7)", figure="not checked", access="abstract",
         test="Drive the auditory Johnston's organ neurons (JO-A and JO-B) with pulse-song-like spike trains; read vpoEN and vpoDN.",
         targets=[("stimulate", "JO-A and JO-B neurons", f783("cell_type", r"^JO-[AB]")), ("read", "vpoEN", hb("vpoEN")), ("read", "vpoDN", hb("vpoDN"))],
         confidence="moderate: JO-A/B are FlyWire 783 labels mapped to 630 (see ids_630.csv); vpoEN/vpoDN are labelled in 630",
         expected="vpoEN fire; vpoDN follow.", numeric="none",
         feas="PARTLY", feas_why="Spikes can travel JO -> vpoEN, but song tuning depends on the timing pattern of sound and graded/active properties of antennal neurons; the model's JO input pattern would be made up.",
         cost="medium", batch="", notes=""),
    dict(id="MG2", area=MECH, short="Hearing neurons feed the giant fiber",
         result="A subset of sound-detecting Johnston's organ neurons makes mixed electrical and chemical synapses onto the giant fiber (the escape neuron), and sound raises the chance that the giant fiber fires.",
         measure="electrophysiology; anatomy", source="Pezier et al. 2014, J Neurosci 34:11691 (PMC4145173)", figure="not checked", access="abstract",
         test="Drive JO-A/JO-B neurons, alone and together with a weak giant-fiber drive; read giant-fiber (DNp01) firing probability.",
         targets=[("stimulate", "JO-A and JO-B neurons", f783("cell_type", r"^JO-[AB]")), ("read", "giant fiber (DNp01)", ct("DNp01"))],
         confidence="moderate (JO mapping); high for the giant fiber",
         expected="JO input raises giant-fiber firing probability.", numeric="none",
         feas="PARTLY", feas_why="The model has only the chemical half of this synapse; electrical synapses exist only as a Phase 7 switch in the antennal lobe.",
         cost="cheap", batch="", notes=""),
    dict(id="MG3", area=MECH, short="Wind direction from both antennae",
         result="Second-order mechanosensory neurons respond mainly to the same-side antenna, while 'wedge projection neurons' combine both antennae and give a more linear code for wind direction.",
         measure="electrophysiology; behaviour", source="Suver et al. 2019, Neuron 102:828 (PMC6533146)", figure="not checked", access="abstract",
         test="Drive left and right wind-sensitive JO neurons (JO-C/E) in different ratios; read second-order antennal-mechanosensory neurons and wedge projection neuron candidates.",
         targets=[("stimulate", "JO-C/E neurons (grooming lane's set)", {"ids": HELD["JON_CE"], "src": "experiments/heldout/ids.py JON_CE (paper's own IDs)"}),
                  ("read", "wedge projection neurons", none("not labelled in FlyWire's 630 or 783 annotation; would need identifying by shape and inputs"))],
         confidence="low: the key read-out cells are not identified in FlyWire",
         expected="Read-out cells respond to the left-right difference.", numeric="none",
         feas="PARTLY", feas_why="Read-out cells unidentified; wind is a graded antenna displacement the model approximates with spike rates.",
         cost="medium", batch="", notes=""),
    dict(id="MG4", area=MECH, short="Head bristles aim grooming",
         result="Each class of head bristle mechanosensory neuron, when activated, makes the fly groom the matching spot on its head; together they produce a whole-head grooming sequence.",
         measure="behaviour", source="Eichler et al. 2024, eLife 12:RP87602 (PMC11026096)", figure="not checked", access="abstract",
         test="None usable: the brain model could show which descending neurons each bristle class reaches, but the paper measured only behaviour, which is produced in the nerve cord.",
         targets=[("stimulate", "head bristle neurons (FlyWire 783 types BM_*)", rule("783 cell_type starting 'BM_' (about 1,400 neurons); not mapped because the item is not runnable"))],
         confidence="moderate (FlyWire names the bristle classes)",
         expected="n/a", numeric="n/a",
         feas="NO", feas_why="Grooming movements are generated in the nerve cord, which the model does not have.", cost="n/a", batch="", notes=""),
    # -------------------------------------------------------------- SMELL
    dict(id="OS1", area=SMELL, short="Silenced glomerulus still gets lateral excitation",
         result="When all sensory neurons of one glomerulus are genetically silenced, that glomerulus's projection neurons still respond to odours, because they receive substantial excitation from other glomeruli.",
         measure="electrophysiology", source="Olsen, Bhandawat & Wilson 2007, Neuron 54:89 (PMC2048819)", figure="not checked", access="abstract",
         test="Silence the DA1 sensory neurons; drive many other sensory neuron types at odour-like rates (e.g. from the DoOR tables in data/olfaction/door); read DA1 projection neurons. Repeat with the al_ln_literature sign fix and the Phase 7 gap-junction switch.",
         targets=[("silence", "DA1 sensory neurons (ORN_DA1)", hb("ORN_DA1")), ("stimulate", "other olfactory sensory neurons", rule("630 hemibrain_type starting 'ORN_' except ORN_DA1 (about 2,150 neurons), at odour-specific rates")),
                  ("read", "DA1 projection neurons", hbre(r"^DA1_[lv]PN$"))],
         confidence="high for cells (FlyWire glomerulus labels); the paper's own glomerulus is not stated in the abstract",
         expected="DA1 projection neurons fire above baseline despite silent DA1 input.", numeric="none in the abstract ('substantial')",
         feas="PARTLY", feas_why="In flies much of this excitation travels through electrical synapses (excitatory local neurons coupled to projection neurons); the model has them only as the Phase 7 switch. The chemical part and the disputed local-neuron signs decide the published model's answer.",
         cost="medium", batch="", notes="A held-out SMELL test of the al_ln_literature fix (docs/heldout-validation.md asked for one); not covered by the olfaction lane. Reserve for the first batch."),
    dict(id="OS2", area=SMELL, short="Lateral inhibition scales with total input",
         result="Inhibition between glomeruli outweighs excitation: removing input from other glomeruli broadens a projection neuron's odour tuning, and the inhibition grows with the total activity of all olfactory sensory neurons (divisive normalisation), acting partly on the sensory axon terminals.",
         measure="electrophysiology", source="Olsen & Wilson 2008, Nature 452:956 (PMC2824883); Olsen, Bhandawat & Wilson 2010, Neuron 66:287 (PMC2866644)", figure="not checked", access="abstract (both)",
         test="Drive the DA1 sensory neurons at a fixed rate (20, 40, 80 Hz) while adding more and more other sensory-neuron types; read DA1 projection neurons. Run the published model and the al_ln_literature sign fix.",
         targets=[("stimulate", "DA1 sensory neurons", hb("ORN_DA1")), ("stimulate", "other olfactory sensory neurons", rule("630 hemibrain_type starting 'ORN_' except ORN_DA1, in growing subsets")),
                  ("read", "DA1 projection neurons", hbre(r"^DA1_[lv]PN$"))],
         confidence="high for cells",
         expected="The DA1 projection-neuron response to the same DA1 input falls as total sensory activity rises (the curve shifts right).", numeric="none in the abstracts",
         feas="YES", feas_why="Local-neuron synapses onto projection neurons and onto sensory terminals are in the connectome. Missing: the slow GABA-B part, which should weaken, not reverse, the effect.",
         cost="medium", batch="", notes="DUPLICATE: already being scored by the olfaction lane (docs/olfaction-vs-real-fly.md, items F3-F5, published model and al_ln_literature). Do not re-run here."),
    dict(id="OS3", area=SMELL, short="Projection neurons boost weak input",
         result="Projection neurons amplify weak sensory input but not strong input (a saturating curve), respond more reliably from trial to trial than their sensory neurons, and emphasise odour onset.",
         measure="electrophysiology (paired recordings in 7 glomeruli)", source="Bhandawat et al. 2007, Nat Neurosci 10:1474 (PMC2838615)", figure="not checked", access="abstract",
         test="Drive one glomerulus's sensory neurons (e.g. DA1) at 5-200 Hz; read its projection neurons; compare rates and trial-to-trial variability.",
         targets=[("stimulate", "DA1 sensory neurons", hb("ORN_DA1")), ("read", "DA1 projection neurons", hbre(r"^DA1_[lv]PN$"))],
         confidence="high for cells",
         expected="Steep projection-neuron rise at low input, flattening at high input; less variable than the input.", numeric="none in the abstract",
         feas="YES", feas_why="Rate curve and reliability are testable now; the 'onset emphasis' part needs spike-frequency adaptation (Phase 7 switch).",
         cost="cheap", batch="", notes="PARTLY DUPLICATE: the olfaction lane scores the amplification curve and PN-vs-ORN pickiness (docs/olfaction-vs-real-fly.md, F2-F3); the trial-to-trial reliability part is not covered there."),
    dict(id="OS4", area=SMELL, short="Sister projection neurons fire in sync",
         result="Projection neurons fed by the same sensory-neuron type fire synchronised spontaneous spikes, odours make them more correlated, and projection neurons from different glomeruli are only weakly correlated.",
         measure="electrophysiology (dual recordings)", source="Kazama & Wilson 2009, Nat Neurosci 12:1136 (PMC2751859)", figure="not checked", access="abstract",
         test="Independent low-rate Poisson input to every olfactory sensory neuron; measure spike synchrony for pairs of DA1 projection neurons versus pairs from different glomeruli; then raise DA1 input.",
         targets=[("stimulate", "all olfactory sensory neurons", rule("630 hemibrain_type starting 'ORN_' (about 2,280 neurons)")), ("read", "DA1 projection neurons (sister pairs)", hbre(r"^DA1_[lv]PN$")),
                  ("read", "projection neurons of other glomeruli", rule("630 cell_class ALPN, uniglomerular types"))],
         confidence="high for cells",
         expected="Sister pairs much more synchronised than cross-glomerulus pairs; synchrony rises with odour-like input.", numeric="none in the abstract",
         feas="YES", feas_why="Depends on each sensory neuron contacting every projection neuron in its glomerulus, which is in the connectome.", cost="cheap", batch="7", notes="Not covered by the olfaction lane (checked docs/olfaction-vs-real-fly.md)."),
    dict(id="OS5", area=SMELL, short="APL keeps Kenyon cells sparse",
         result="Kenyon cells excite the APL neuron and APL inhibits them; blocking this feedback makes Kenyon-cell odour responses less sparse and more alike between odours, and flies then fail to learn to tell similar odours apart.",
         measure="calcium imaging; behaviour", source="Lin et al. 2014, Nat Neurosci 17:559 (PMC4000970)", figure="Fig. 5c-e", access="full text (searched)",
         test="Two similar odour-like inputs, with APL intact and silenced; read the fraction of Kenyon cells active and the overlap between the two odours' Kenyon-cell patterns.",
         targets=[("silence", "APL", hb("APL")), ("read", "Kenyon cells", rule("630 cell_class Kenyon_Cell (5,177 neurons)"))],
         confidence="high for cells",
         expected="Silencing APL raises the active fraction and the overlap between odours.", numeric="baseline 5-10% of Kenyon cells respond to an odour (quoted in the paper); change: direction only",
         feas="PARTLY", feas_why="APL is a non-spiking neuron with local, graded inhibition; one LIF cell cannot do that. Kenyon-cell sparseness also depends on the Phase 7 threshold and sign fixes.",
         cost="medium", batch="", notes="DUPLICATE: already being scored by the olfaction lane (docs/olfaction-vs-real-fly.md, F7). Kenyon-cell sparseness itself was compared with Turner et al. 2008 in Phases 5 and 7."),
    # ------------------------------------------------------------ LEARNING
    dict(id="LL1", area=LEARN, short="MVP2 silences the avoidance output neurons",
         result="Optogenetically activating the GABAergic output neuron MVP2 (MBON-g1pedc>a/b) quickly and reversibly suppresses odour responses in the M4/6 output neurons, but has no visible effect on the V2a/V2a' output neurons.",
         measure="calcium imaging", source="Perisse et al. 2016, Neuron 90:1086 (PMC4893166)", figure="Fig. 4A-B", access="full text (searched)",
         test="Standard odour input to the mushroom body, with and without driving MBON11 (MVP2). Read M4/6 (MBON01, MBON02, MBON03, MBON04) and the V2 cluster (MBON18, MBON16, MBON17).",
         targets=[("stimulate", "MVP2 = MBON11", hb("MBON11")), ("read", "M4/6: MBON01 (g5b'2a)", hb("MBON01")), ("read", "M4/6: MBON02 (b2b'2a)", hb("MBON02")),
                  ("read", "M4/6: MBON03, MBON04 (b'2mp)", hbre(r"^MBON0[34]$")), ("read", "V2a: MBON18 (a2sc)", hb("MBON18")), ("read", "V2a': MBON16, MBON17 (a'3)", hbre(r"^MBON1[67]$"))],
         confidence="high for MBON11 and M4/6 (names in Owald et al. 2015); moderate for V2a = MBON-a2sc and V2a' = MBON-a'3 (from Aso et al. 2014, not re-checked here)",
         expected="M4/6 odour responses drop while MBON11 is driven; V2 responses do not.", numeric="none ('rapid and robust' vs 'no effect')",
         feas="YES", feas_why="MBON11's GABA synapses are in the connectome. The M4/6 cells must respond to odour first (check in the published model; true with the sign fix).",
         cost="cheap", batch="8", notes="sim/plasticity.py cites Perisse 2016 only for read-out labels; this activation result has not been used or tested."),
    dict(id="LL2", area=LEARN, short="Learning shifts the M4b' odour response",
         result="Aversive conditioning raises, and appetitive conditioning lowers, the M4b' output neuron's (MBON-b'2mp) response to the trained odour relative to the untrained one.",
         measure="calcium imaging", source="Owald et al. 2015, Neuron 86:417 (PMC4416108)", figure="Fig. 3I-L", access="full text (searched)",
         test="Phase 8: pair odour A with the punishment dopamine neuron PPL1-g1pedc (PPL101); test A and B; read MBON03/MBON04. Repeat with reward dopamine neurons of the b'2 compartments.",
         targets=[("stimulate", "punishment DAN PPL1-g1pedc", hb("PPL101")), ("stimulate", "reward DANs for b'2 (PAM02, PAM05, PAM06)", hbre(r"^PAM0[256]$")),
                  ("read", "M4b' = MBON03, MBON04", hbre(r"^MBON0[34]$")), ("read", "MVP2 = MBON11", hb("MBON11"))],
         confidence="high for cells",
         expected="Aversive: A/B response ratio in MBON03/04 rises vs mock. Appetitive: it falls.", numeric="none (direction only)",
         feas="YES", feas_why="Needs Phase 8 plasticity. Because the model can only weaken synapses, the aversive rise can only come from MBON11 losing drive and releasing its inhibition (the Perisse mechanism), so this jointly tests learning and wiring.",
         cost="medium", batch="", notes=""),
    dict(id="LL3", area=LEARN, short="Sugar activates reward dopamine neurons",
         result="PAM-cluster dopamine neurons are activated by sugar ingestion (more strongly when the fly is starved) and carry the reward signal for odour memories.",
         measure="calcium imaging; behaviour", source="Liu et al. 2012, Nature 488:512 (doi:10.1038/nature11304)", figure="not checked", access="abstract",
         test="Standard sugar input; read the PAM types (PAM01-PAM15).",
         targets=[("stimulate", "sugar taste neurons", shiu("SUGAR_R_630")), ("read", "PAM dopamine neurons", hbre(r"^PAM\d\d$"))],
         confidence="high for PAM cells; moderate for the stimulus (the fly drank sugar; the model has only proboscis sugar neurons)",
         expected="PAM firing rises above baseline.", numeric="none",
         feas="PARTLY", feas_why="Real stimulus was ingestion (throat and possibly internal nutrient signals) in a hungry fly; the model has proboscis sugar neurons only and no hunger state.",
         cost="cheap", batch="", notes=""),
    dict(id="LL4", area=LEARN, short="Bitter taste relays to punishment dopamine neurons",
         result="Activating the bitter taste projection neurons TPN3 (which respond to bitter on legs and proboscis) drives calcium responses in most PPL1 dopamine neurons; TPN3 are needed for taste-aversion learning, and TPN3 activation can replace bitter as the punishment.",
         measure="calcium imaging; behaviour", source="Kim, Kirkhart & Scott 2017, eLife 6:e23386", figure="Figs 8-9 (imaging), 5-7 (behaviour)", access="full text (summary)",
         test="TPN3 is not labelled in FlyWire, so drive the model's standard bitter input and read PPL1 dopamine neurons (PPL101-PPL106). Once TPN3 is identified, drive it directly.",
         targets=[("stimulate", "bitter taste neurons (standard set)", shiu("BITTER_R_630")), ("read", "PPL1 dopamine neurons", hbre(r"^PPL10[1-6]$")),
                  ("stimulate", "TPN3", none("not labelled in FlyWire 630 or 783; needs identification by shape"))],
         confidence="high for PPL1; low for the stimulus substitution",
         expected="PPL1 dopamine neurons fire above baseline.", numeric="none ('most PPL1 neurons')",
         feas="PARTLY", feas_why="TPN3 not identified; much of its input comes from the legs via the nerve cord (missing).", cost="cheap", batch="", notes=""),
    dict(id="LL5", area=LEARN, short="Backward pairing strengthens",
         result="Dopamine arriving after an odour (backward pairing) strengthens the Kenyon-cell-to-MBON-g4 synapse and raises the MBON's odour response, while forward pairing weakens it; one trial of the opposite order reverses either.",
         measure="calcium imaging; behaviour", source="Handler et al. 2019, Cell 178:60 (PMC9012144)", figure="Fig. 4B; Fig. S3A-B", access="full text (searched)",
         test="Phase 8 backward pairing; read the g4 output neurons.",
         targets=[("read", "g4 output neurons (MBON05, MBON21, MBON29)", hbre(r"^MBON(?:05|21|29)$"))],
         confidence="high for cells",
         expected="Real flies: the MBON's odour response rises after backward pairing.", numeric="none",
         feas="NO", feas_why="Phase 8 has only a weakening rule; docs/phase8-learning.md already lists the missing strengthening rule.",
         cost="medium (after a new rule)", batch="", notes="Also: Aso & Rubin 2016 (slow a3 learning) is NOT listed because Phase 8 already uses it to set SLOW_COMPARTMENTS, so it is not a fair test."),
    # ---------------------------------------------------------- STEERING
    dict(id="SD1", area=STEER, short="Looming detectors drive backward walking",
         result="The visual projection neurons LC16 respond to looming and make flies walk backward, through the moonwalker descending neurons (MDN).",
         measure="calcium imaging; behaviour", source="Sen et al. 2017, Curr Biol 27:766; Wu et al. 2016, eLife 5:e21022", figure="not checked", access="abstract (both)",
         test="Drive LC16 on both sides (50-100 Hz); read MDN.",
         targets=[("stimulate", "LC16", hb("LC16")), ("read", "MDN", hb("MDN"))],
         confidence="high: both labelled in 630",
         expected="MDN fire.", numeric="none",
         feas="YES", feas_why="LC16 and MDN both spike and are in the model; no eye is needed if LC16 is driven directly.", cost="cheap", batch="9", notes="Run SD2 in the same session (same cells)."),
    dict(id="SD2", area=STEER, short="One-sided LC16 gives lopsided MDN",
         result="Turning while walking backward reflects unequal activation of the left and right MDNs; one-sided LC16 activation makes flies turn.",
         measure="behaviour; calcium imaging", source="Sen et al. 2017, Curr Biol 27:766; Wu et al. 2016, eLife 5:e21022", figure="not checked", access="abstract (both)",
         test="Drive the left LC16 only, then the right only; compare left and right MDN.",
         targets=[("stimulate", "LC16, left", hb("LC16", side="left")), ("stimulate", "LC16, right", hb("LC16", side="right")), ("read", "MDN", hb("MDN"))],
         confidence="high",
         expected="The two MDN sides respond unequally, and the bias flips with the stimulated side (which side wins: take from the paper's figures).", numeric="none",
         feas="YES", feas_why="Neural asymmetry is testable now; the turn itself needs the body loop.", cost="cheap", batch="", notes=""),
    dict(id="SD3", area=STEER, short="Giant fiber adds looming size and speed",
         result="The giant fiber sums two looming features: speed of expansion from LC4 and size from LPLC2. Silencing LPLC2 removes the size part of its response, leaving only the speed part; both synapse directly onto the giant fiber.",
         measure="electrophysiology (patch clamp)", source="Ache et al. 2019, Curr Biol 29:1073; von Reyn et al. 2017, Neuron 94:1190", figure="not checked", access="abstract (both)",
         test="Drive LC4 and LPLC2 with loom-shaped rate time-courses; read the giant fiber; repeat with LPLC2 or LC4 silenced.",
         targets=[("stimulate", "LC4", hb("LC4")), ("stimulate", "LPLC2", hb("LPLC2")), ("read", "giant fiber (DNp01)", ct("DNp01"))],
         confidence="high: all labelled in 630",
         expected="Without LPLC2 the size-dependent part disappears; without LC4 the speed part does.", numeric="none in the abstracts",
         feas="PARTLY", feas_why="No eyes, so the LC4/LPLC2 time-courses must be invented; the giant fiber integrates graded voltage and fires at most one spike, and has large electrical synapses the model lacks.",
         cost="medium", batch="", notes=""),
    dict(id="SD4", area=STEER, short="PFL3 steers through the lateral accessory lobe",
         result="Optogenetically stimulating PFL3 neurons in the left or right lateral accessory lobe makes walking flies turn toward the stimulated side; about 8% of trials did not turn that way.",
         measure="behaviour; calcium imaging", source="Mussells Pires et al. 2024, Nature 626:819 (PMC10881393)", figure="Fig. 5e-h; Extended Data Fig. 10", access="full text (searched)",
         test="Drive the PFL3 neurons whose axons end in the left lateral accessory lobe (select by output side from the connection list); read DNa02 left vs right; then the right side.",
         targets=[("stimulate", "PFL3 (split by output side before running)", hb("PFL3")), ("read", "DNa02 (left, right)", hb("DNa02"))],
         confidence="high for cells; the soma 'side' label is not the output side, so the split must be made from the wiring",
         expected="Left-side PFL3 drive gives more left than right DNa02 (a left turn by the body loop's rule), and the mirror for the right.", numeric="turn toward the stimulated side in about 92% of trials",
         feas="YES", feas_why="PFL3 are spiking central-complex neurons with direct outputs in the lateral accessory lobe; the DNa02-to-turn rule is the body loop's existing assumption (Rayshubskiy et al. 2025).",
         cost="cheap", batch="4", notes="The model's known left lean in DNa02 (Phase 6) could bias this; run both sides and several seeds."),
    dict(id="SD5", area=STEER, short="Descending-neuron activation screen",
         result="Optogenetic activation of individual descending neuron types drives specific, stereotyped behaviours, often depending on what the fly was doing before.",
         measure="behaviour", source="Cande et al. 2018, eLife 7:e34275 (PMC6031430)", figure="not checked", access="abstract",
         test="None in a brain-only model: descending-neuron-to-behaviour happens in the nerve cord.",
         targets=[("stimulate", "descending neurons", rule("many DN types; not resolved because the item is not runnable"))],
         confidence="n/a", expected="n/a", numeric="n/a",
         feas="NO", feas_why="No nerve cord. Useful only to check the hand-built Phase 9 body mapping, not the brain.", cost="n/a", batch="", notes=""),
    dict(id="SD6", area=STEER, short="MDN makes flies walk backward",
         result="MDN activity is needed for flies to walk backward at a dead end and is enough to make them walk backward.",
         measure="behaviour", source="Bidaye et al. 2014, Science 344:97 (doi:10.1126/science.1249964)", figure="not checked", access="abstract",
         test="None for the brain: this is the read-out rule that SD1 relies on (MDN active = backward walking).",
         targets=[("read", "MDN", hb("MDN"))], confidence="high for cells", expected="n/a", numeric="n/a",
         feas="NO", feas_why="Descending neuron to legs is outside the brain model; in the body loop it would be an assumption, not a test.", cost="n/a", batch="", notes=""),
    # ------------------------------------------------------------ THERMO
    dict(id="TH1", area=THERMO, short="Cool projection neurons follow cool sensors",
         result="Projection neurons excited by cooling get mainly feed-forward excitation from cool-sensing receptor neurons.",
         measure="electrophysiology", source="Liu, Mazor & Wilson 2015, Nature 519:353 (PMC5488797)", figure="not checked", access="full text (searched)",
         test="Drive the cool sensory neurons (TRN_VP3a, TRN_VP3b); read the projection neurons of the VP3 glomerulus.",
         targets=[("stimulate", "cool sensory neurons", hbre(r"^TRN_VP3[ab]$")), ("read", "VP3 projection neurons", hbre(r"^(?:VP3\+_l2PN|VP3\+VP1l_ivPN|VP1l\+VP3_ilPN|VP3\+_vPN)$"))],
         confidence="high for the sensory neurons (FlyWire glomerulus labels); moderate-low for which FlyWire projection neuron is Liu's 'cool-PN'",
         expected="VP3 projection neurons fire.", numeric="none",
         feas="YES", feas_why="Sensory and projection neurons spike and are in the model.", cost="cheap", batch="", notes="Run in the same session as TH2 (first-batch rank 6)."),
    dict(id="TH2", area=THERMO, short="Cool sensors inhibit warm projection neurons",
         result="Warm projection neurons get excitation from warm receptors plus 'crossover' inhibition from cool receptors via local neurons: 14 of 17 recorded local neurons were tonically active, inhibited by warming and excited by cooling, and blocking inhibition depolarised warm projection neurons by 6 +/- 1 mV.",
         measure="electrophysiology", source="Liu, Mazor & Wilson 2015, Nature 519:353 (PMC5488797)", figure="Fig. 4a-f; Extended Data Fig. 10", access="full text (searched)",
         test="Drive the warm sensory neurons (TRN_VP2) at a fixed rate, with and without cool sensory drive (TRN_VP3a/b); read the VP2 projection neurons.",
         targets=[("stimulate", "warm sensory neurons", hb("TRN_VP2")), ("stimulate", "cool sensory neurons", hbre(r"^TRN_VP3[ab]$")),
                  ("read", "VP2 projection neurons", hbre(r"^(?:VP2_adPN|VP2\+_adPN|VP2_l2PN)$"))],
         confidence="high for sensory neurons; moderate-low for the projection-neuron match",
         expected="VP2 projection neurons fire less when cool sensors are also active.", numeric="14/17 local neurons cool-excited; +6 +/- 1 mV when inhibition is blocked",
         feas="YES", feas_why="The sign depends on the model's local-neuron transmitters. The 'tonic' part needs baseline input, because the model's sensors are silent unless driven.",
         cost="cheap", batch="6", notes=""),
    dict(id="TH3", area=THERMO, short="Cold projection neurons inhibit DN1a clock cells",
         result="Cold-activated, GABAergic TPN-II projection neurons fire steadily below about 25 C and directly inhibit the DN1a clock neurons; picrotoxin (a GABA-A blocker) abolishes the cold inhibition.",
         measure="electrophysiology; calcium imaging", source="Alpert et al. 2020, Curr Biol 30:2275 (PMC7314653)", figure="Fig. 5 (5D, 5G-J)", access="full text (searched)",
         test="Give DN1a a steady background input; add cool sensory drive (TRN_VP3a/b); read VP3+_vPN (the TPN-II candidate) and DN1a. Control: silence VP3+_vPN.",
         targets=[("stimulate", "cool sensory neurons", hbre(r"^TRN_VP3[ab]$")), ("read", "TPN-II candidate VP3+_vPN", hb("VP3+_vPN")), ("read", "DN1a", hb("DN1a"))],
         confidence="moderate for TPN-II = VP3+_vPN (GABA-predicted in FlyWire, cold glomerulus, and Marin et al. 2020 say the slow-cool VP3 vPN targets the calyx micro-glomerulus that TPN-IIs innervate); high for DN1a",
         expected="VP3+_vPN fires; DN1a slows; the slowing disappears when VP3+_vPN is silenced.", numeric="none (direction; complete block by picrotoxin)",
         feas="YES", feas_why="All cells spike; one short run per condition.", cost="cheap", batch="5", notes=""),
    dict(id="TH4", area=THERMO, short="Cooling excites DN1p clock cells",
         result="DN1p clock neurons are excited by cooling and inhibited by heating, using thermoreceptors in the aristae and chordotonal organs.",
         measure="calcium imaging", source="Yadlapalli et al. 2018, Nature 555:98 (doi:10.1038/nature25740)", figure="not checked", access="abstract",
         test="Drive cool sensory neurons; read DN1pA/DN1pB. With a DN1p background input, drive warm sensory neurons and expect a drop.",
         targets=[("stimulate", "cool sensory neurons", hbre(r"^TRN_VP3[ab]$")), ("stimulate", "warm sensory neurons", hb("TRN_VP2")), ("read", "DN1p", hbre(r"^DN1p[AB]$"))],
         confidence="moderate: FlyWire labels only part of the DN1p cluster",
         expected="Cool up, warm down.", numeric="none",
         feas="PARTLY", feas_why="The chordotonal-organ thermoreceptors are in the body (nerve cord), so part of the input is missing.", cost="cheap", batch="", notes=""),
    dict(id="TH5", area=THERMO, short="Humid-only and combined humidity-temperature projection neurons",
         result="One projection neuron type samples only the humid-air glomerulus and responds only to humid air, while 'broadly tuned' projection neurons combine dry-air sensors with arista temperature receptors.",
         measure="calcium imaging", source="Frank et al. 2017, Curr Biol 27:2381 (PMC5600489)", figure="Fig. 2J (humid vs dry traces)", access="full text (searched)",
         test="Drive humid (HRN_VP5), dry (HRN_VP4), warm (TRN_VP2) and cool (TRN_VP3a/b) sensors one at a time and in pairs; read all VP projection-neuron types.",
         targets=[("stimulate", "humid sensors", hb("HRN_VP5")), ("stimulate", "dry sensors", hb("HRN_VP4")), ("stimulate", "warm sensors", hb("TRN_VP2")),
                  ("stimulate", "cool sensors", hbre(r"^TRN_VP3[ab]$")), ("read", "VP projection neurons", hbre(r"^VP\d"))],
         confidence="high for sensors; low-moderate for which FlyWire projection neurons match the paper's genetic lines",
         expected="At least one projection-neuron type responds to humid input only; at least one responds to both dry and temperature input.", numeric="none",
         feas="YES", feas_why="All sensors and projection neurons are in the brain and spike.", cost="cheap", batch="", notes="The only hygrosensation item with a central-neuron measurement found in this pass."),
    # ------------------------------------------------------------- COURTSHIP
    dict(id="FC1", area=COURT, short="Song and mating-status inputs converge on vpoDN",
         result="The female-only vpoDN descending neurons, which open the vaginal plates, get excitatory input from song-tuned vpoEN neurons and from pC1 neurons (which encode mating status); after mating, vpoDN's song responses drop but vpoEN's do not, via pC1.",
         measure="calcium imaging; behaviour", source="Wang et al. 2021, Nature 589:577 (doi:10.1038/s41586-020-2972-7)", figure="not checked", access="abstract",
         test="Drive vpoEN; read vpoDN. Drive pC1 (all five subtypes); read vpoDN. Drive both together.",
         targets=[("stimulate", "vpoEN", hb("vpoEN")), ("stimulate", "pC1a-e", hbre(r"^pC1[a-e]$")), ("read", "vpoDN", hb("vpoDN"))],
         confidence="high: all labelled in 630",
         expected="vpoDN fires to each input and more to both together.", numeric="none",
         feas="YES", feas_why="Small, fully labelled circuit; spiking cells.", cost="cheap", batch="3", notes=""),
    dict(id="FC2", area=COURT, short="SAG input picks out pC1a",
         result="Activating the SAG ascending neurons (which carry the uterine sex-peptide signal) strongly depolarises pC1a, weakly depolarises pC1b, and has little or no effect on pC1c, pC1d and pC1e.",
         measure="electrophysiology", source="Wang et al. 2020, Nature 579:101 (PMC7687045)", figure="Fig. 3d-f", access="full text (searched)",
         test="Drive the two SAG neurons (their axons are in the brain model); read pC1a to pC1e.",
         targets=[("stimulate", "SAG", hb("SAG")), ("read", "pC1a", hb("pC1a")), ("read", "pC1b", hb("pC1b")), ("read", "pC1c, pC1d, pC1e", hbre(r"^pC1[cde]$"))],
         confidence="high: all labelled in 630",
         expected="pC1a >> pC1b > pC1c/d/e (about zero).", numeric="rank order: pC1a strong, pC1b weak, pC1c-e little or none",
         feas="YES", feas_why="Two input cells, ten read-out cells, one short run.", cost="cheap", batch="1", notes=""),
    dict(id="FC3", area=COURT, short="pC1 brakes egg laying through oviIN",
         result="Photoactivating pC1 excites the GABAergic oviIN neurons, which inhibit the egg-laying descending neurons oviDN and their excitatory input oviEN (feed-forward inhibition).",
         measure="calcium imaging; connectome", source="Wang et al. 2020, Nature 579:101 (PMC7687045)", figure="Fig. 4f (pC1 -> oviIN)", access="full text (searched)",
         test="Drive pC1; read oviIN. Give oviDN a background input, add pC1 drive; expect oviDN to drop; repeat with oviIN silenced.",
         targets=[("stimulate", "pC1a-e", hbre(r"^pC1[a-e]$")), ("read", "oviIN", hb("oviIN")), ("read", "oviDNa (FlyWire cell types oviDNa_a, oviDNa_b)", ctre(r"^oviDNa_[ab]$")), ("read", "oviDNb", hb("oviDNb")),
                  ("read", "oviEN", none("not labelled in FlyWire 630 or 783; use background drive instead"))],
         confidence="high for pC1, oviIN, oviDN",
         expected="oviIN fires; oviDN slows; the slowing disappears with oviIN silenced.", numeric="none",
         feas="YES", feas_why="All spiking, labelled cells.", cost="cheap", batch="", notes="Reserve for the first batch."),
    dict(id="FC4", area=COURT, short="pC1d/e leave minutes-long activity",
         result="Brief activation of pC1d/e neurons produces persistent activity that lasts minutes in pC1 and aIPg neurons, supported by strong recurrent pC1d/e <-> aIPg wiring.",
         measure="calcium imaging", source="Deutsch et al. 2020, eLife 9:e59502 (PMC7787663)", figure="Fig. 8", access="full text (searched)",
         test="Drive pC1d and pC1e for 1-2 s, then stop; read pC1d/e and aIPg for at least 10 s afterwards.",
         targets=[("stimulate", "pC1d, pC1e", hbre(r"^pC1[de]$")), ("read", "aIPg", f783("hemibrain_type", r"^aIPg\d$"))],
         confidence="high for pC1d/e; moderate for aIPg (FlyWire 783 labels mapped to 630)",
         expected="Real flies: activity outlasts the stimulus by minutes.", numeric="persistence on a minutes time-scale",
         feas="PARTLY", feas_why="The model has no slow processes except adaptation, so any persistence must come from recurrent excitation; minutes-long persistence without runaway is unlikely. A strong test of the model's recurrent dynamics.",
         cost="medium (long simulated time)", batch="", notes=""),
    dict(id="FC5", area=COURT, short="Female lateral-horn cells for the male pheromone",
         result="In females, most aSP-g lateral-horn neurons respond to the male pheromone cVA (11 of 15), aSP-f almost never (1 of 34) and aSP-h rarely (2 of 8); in males it is reversed (aSP-f 20 of 37, aSP-g 1 of 17).",
         measure="electrophysiology", source="Kohl et al. 2013, Cell 155:1610 (PMC3898676)", figure="Fig. 1J-N; response counts in the figure legend", access="full text (searched)",
         test="Drive the cVA sensory neurons (ORN_DA1) or the DA1 projection neurons; read aSP-g, aSP-f and aSP-h cells and count how many respond.",
         targets=[("stimulate", "cVA sensory neurons (ORN_DA1)", hb("ORN_DA1")), ("read", "aSP-g", f783("cell_type", r"^aSP-g")),
                  ("read", "aSP-f", f783("cell_type", r"^(?:aSP-f|SLP157$|SLP160$|SLP162a$)")), ("read", "aSP-h", f783("synonyms", r"aSP-h"))],
         confidence="moderate: the aSP names come from FlyWire 783 literature synonyms (Cachero et al. 2010 names) mapped to 630; the paper's recorded cells were a sample of each cluster",
         expected="Fraction of cells responding: aSP-g high, aSP-f near zero, aSP-h low.", numeric="aSP-g 11/15 (73%); aSP-f 1/34 (3%); aSP-h 2/8 (25%)",
         feas="YES", feas_why="The model is a female brain, and DA1 input already works (Phase 9); only the read-outs are new.", cost="cheap", batch="2", notes=""),
    # ---------------------------------------------------------------- VISION
    dict(id="VI1", area=VISION, short="T4/T5 motion detectors",
         result="T4 cells respond to moving bright edges and T5 cells to moving dark edges, each subtype tuned to one of four directions of motion.",
         measure="calcium imaging", source="Maisak et al. 2013, Nature 500:212 (doi:10.1038/nature12320)", figure="not checked", access="abstract",
         test="None meaningful.",
         targets=[("read", "T4a-d, T5a-d", rule("783 cell_type T4a-d and T5a-d (about 11,700 neurons); 630 has no optic-lobe type labels; not mapped because the item is not runnable"))],
         confidence="high for the names in 783", expected="n/a", numeric="n/a",
         feas="NO", feas_why="Photoreceptors and most early visual neurons are graded (non-spiking), motion detection depends on graded, delayed signals, and the model has no eyes. LIF with made-up input cannot test this honestly.",
         cost="n/a", batch="", notes="Visual items that start at spiking visual projection neurons (LC16, LC4, LPLC2) are in the steering area."),
    dict(id="VI2", area=VISION, short="Compass bump persists in darkness",
         result="The ellipsoid-body compass neurons (E-PG) carry a single bump of activity that tracks heading, and in darkness with no self-motion the bump persists.",
         measure="calcium imaging", source="Seelig & Jayaraman 2015, Nature 521:186 (PMC4704792)", figure="not checked", access="abstract",
         test="Briefly drive E-PGs of one wedge, then stop; read all E-PGs and Delta7s for several seconds.",
         targets=[("stimulate", "E-PG (one wedge)", hb("EPG")), ("read", "E-PG", hb("EPG")), ("read", "Delta7", hb("Delta7"))],
         confidence="high for cells; wedge assignment of each E-PG must be taken from its arbor",
         expected="One localised bump that outlasts the stimulus.", numeric="none",
         feas="PARTLY", feas_why="A ring attractor needs sustained recurrent excitation and broad inhibition; the model has no baseline activity and no slow processes, so persistence over seconds is not guaranteed.",
         cost="medium", batch="", notes=""),
]


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    a = pd.read_parquet(N630, columns=COLS)
    b = pd.read_parquet(N783, columns=COLS + ["synonyms"])
    return a, b


class Resolver:
    def __init__(self, a: pd.DataFrame, b: pd.DataFrame):
        self.a, self.b = a, b
        self.ids630 = set(a.root_id.to_numpy().tolist())
        soma = a[["soma_x_nm", "soma_y_nm", "soma_z_nm"]].to_numpy(dtype=float)
        anc = a[["anchor_x_nm", "anchor_y_nm", "anchor_z_nm"]].to_numpy(dtype=float)
        ok = ~np.isnan(soma).any(axis=1)
        self.soma_idx = np.flatnonzero(ok)
        self.soma_tree = cKDTree(soma[ok])
        ok2 = ~np.isnan(anc).any(axis=1)
        self.anc_idx = np.flatnonzero(ok2)
        self.anc_tree = cKDTree(anc[ok2])

    def _map783(self, rows: pd.DataFrame) -> list[tuple[int, str, str]]:
        out = []
        for r in rows.itertuples(index=False):
            rid = int(r.root_id)
            if rid in self.ids630:
                out.append((rid, "same root ID in 630 and 783", str(r.side)))
                continue
            if not np.isnan(r.soma_x_nm):
                d, j = self.soma_tree.query([r.soma_x_nm, r.soma_y_nm, r.soma_z_nm])
                idx, how = self.soma_idx[j], "soma"
            else:
                d, j = self.anc_tree.query([r.anchor_x_nm, r.anchor_y_nm, r.anchor_z_nm])
                idx, how = self.anc_idx[j], "anchor"
            if d <= MATCH_NM:
                m = self.a.iloc[idx]
                out.append((int(m.root_id), f"{how} within {d / 1000:.2f} um (783 id {rid})", str(m.side)))
            else:
                out.append((0, f"UNMAPPED ({how} nearest {d / 1000:.1f} um; 783 id {rid})", str(r.side)))
        return out

    def resolve(self, sel: dict) -> tuple[list[tuple[int, str, str]], str]:
        """-> ([(root_id_630, method, side)], description)."""
        if "rule" in sel:
            return [], "RULE: " + sel["rule"]
        if "none" in sel:
            return [], "NOT MAPPED: " + sel["none"]
        if "ids" in sel:
            sub = self.a[self.a.root_id.isin(sel["ids"])]
            side = dict(zip(sub.root_id, sub.side))
            res = [(int(i), sel["src"] if int(i) in self.ids630 else "NOT IN 630 TABLE: " + sel["src"],
                    str(side.get(int(i), "?"))) for i in sel["ids"]]
            return res, sel["src"]
        df = self.a if sel["db"] == "630" else self.b
        col = df[sel["col"]].astype("string")
        if "eq" in sel:
            m = (col == sel["eq"]).fillna(False)
            desc = f"{sel['db']} {sel['col']} == '{sel['eq']}'"
        else:
            m = col.str.contains(sel["re"], regex=True).fillna(False)
            desc = f"{sel['db']} {sel['col']} matches /{sel['re']}/"
        if sel.get("side"):
            m &= (df.side == sel["side"])
            desc += f", side {sel['side']}"
        rows = df[m.to_numpy()]
        if sel["db"] == "630":
            return [(int(r.root_id), "630 label", str(r.side)) for r in rows.itertuples(index=False)], desc
        return self._map783(rows), desc + " (mapped to 630)"


def main() -> None:
    a, b = load()
    res = Resolver(a, b)
    cat_rows, id_rows = [], []
    for it in ITEMS:
        parts_types, parts_ids, n_total, methods = [], [], 0, set()
        for role, label, sel in it["targets"]:
            got, desc = res.resolve(sel)
            ids = [g[0] for g in got if g[0]]
            n_total += len(ids)
            for g in got:
                methods.add(g[1].split(" (783 id")[0].split(" within")[0])
                if len(got) <= LIST_MAX:
                    id_rows.append(dict(item=it["id"], role=role, group=label, root_id_630=str(g[0]) if g[0] else "",
                                        side=g[2], how_found=g[1], selection=desc))
            parts_types.append(f"{role}: {label} [{desc}]")
            if not got:
                parts_ids.append(f"{role} {label}: {desc.split(': ', 1)[-1] if desc.startswith(('RULE', 'NOT')) else 'none found'}")
            elif len(ids) <= INLINE_MAX:
                parts_ids.append(f"{role} {label} (n={len(ids)}): " + " ".join(str(i) for i in ids))
            else:
                parts_ids.append(f"{role} {label} (n={len(ids)}): see ids_630.csv")
        cat_rows.append(dict(
            id=it["id"], area=it["area"], name=it["short"], real_fly_result=it["result"],
            measurement_type=it["measure"], source=it["source"], figure=it["figure"],
            source_read=it["access"], model_test=it["test"],
            cell_types=" | ".join(parts_types), root_ids_630=" | ".join(parts_ids),
            n_id_rows=n_total, mapping_confidence=it["confidence"],
            expected_model_result=it["expected"], numeric_target=it["numeric"],
            feasibility=it["feas"], feasibility_reason=it["feas_why"], cost=it["cost"],
            first_batch_rank=it["batch"], notes=it["notes"]))
    cat = pd.DataFrame(cat_rows)
    cat.to_csv(OUT / "catalog.csv", index=False, quoting=csv.QUOTE_MINIMAL, encoding="utf-8")
    ids = pd.DataFrame(id_rows)
    ids.to_csv(OUT / "ids_630.csv", index=False, encoding="utf-8")

    # ---- summary printed for the log -------------------------------------
    print(f"items: {len(cat)}")
    print(pd.crosstab(cat.area, cat.feasibility, margins=True).to_string())
    print("\nfirst batch:")
    fb = cat[cat.first_batch_rank != ""].copy()
    fb["r"] = fb.first_batch_rank.astype(int)
    for r in fb.sort_values("r").itertuples():
        print(f"  {r.first_batch_rank:>2} {r.id} {r.name} ({r.feasibility}, {r.cost})")
    print("\nID rows:", len(ids), "| how found:")
    how = ids.how_found.str.replace(r" \(783 id \d+\)", "", regex=True).str.replace(r"within [\d.]+ um", "within 2 um", regex=True)
    print(how.value_counts().to_string())
    miss = ids[ids.root_id_630 == ""]
    if len(miss):
        print("\nUNMAPPED 783 neurons by item/group:")
        print(miss.groupby(["item", "group"]).size().to_string())
    notin = ids[ids.how_found.str.startswith("NOT IN 630")]
    if len(notin):
        print("\nIDs from project lists missing from the 630 table:", len(notin))
    print("\nper-group counts:")
    for it in cat.itertuples():
        print(f"  {it.id}: {it.root_ids_630[:300]}")


if __name__ == "__main__":
    main()
