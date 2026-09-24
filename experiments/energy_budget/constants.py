"""Literature constants for the energy budget, each with a low / mid / high value and a source.

These are ESTIMATES. Every energy number the lane reports is recomputed at the low and
high ends so the reader sees how far the totals move. "ASSUMPTION" marks a value that
is our own judgement rather than a published measurement.
"""
N_AVOGADRO = 6.02214076e23

# ---------------------------------------------------------------- the fly -----------
# Sengupta et al. 2010 PLoS Comput Biol 6:e1000840: a squid-axon spike with a Na+ load of
# 1098 nC/cm2 costs 2.3e12 ATP/cm2, so 1 nC of Na+ costs 2.3e12/1098 ATP.
ATP_PER_NC = 2.3e12 / 1098.0
# Na+ charge per spike per cm2 of membrane. Efficient spikes (mouse thalamocortical relay
# neuron 65 nC/cm2; bee Kenyon cell, rat interneuron and granule cell "below 200").
NA_LOAD_NC_PER_CM2 = dict(low=65.0, mid=130.0, high=200.0)
# Membrane area one spike charges. ASSUMPTION: FlyWire has 149.2 m of neurite in 139,255
# neurons = 1.07 mm per neuron; times pi x an assumed mean neurite diameter of
# 0.15-0.6 um gives about 500-2,000 um2 (1 um2 = 1e-8 cm2).
SPIKE_AREA_CM2 = dict(low=500e-8, mid=1000e-8, high=2000e-8)
ATP_PER_SPIKE = {k: ATP_PER_NC * NA_LOAD_NC_PER_CM2[k] * SPIKE_AREA_CM2[k] for k in ("low", "mid", "high")}

# Attwell & Laughlin 2001: 1.64e5 ATP per vesicle released (mammalian grey matter, mostly
# the postsynaptic ion currents), with a typical release probability of 0.25.
# A FlyWire "synapse" is one presynaptic site -> one partner pair, and a fly release site
# (T-bar) has on average 6.7 postsynaptic partners (hemibrain: 64 million PSDs / 9.5 million
# T-bars, Scheffer et al. 2020). low / mid: one vesicle's cost shared by those 6.7 partners
# (release probability 0.1 / 0.25). high: every partner costs a whole mammalian vesicle and
# release probability is 0.5.
ATP_PER_VESICLE = 1.64e5
RELEASE_PROB = dict(low=0.1, mid=0.25, high=0.5)
PARTNERS_PER_TBAR = 6.7
VESICLE_SHARE = dict(low=1 / PARTNERS_PER_TBAR, mid=1 / PARTNERS_PER_TBAR, high=1.0)
ATP_PER_SYN_EVENT = {k: ATP_PER_VESICLE * RELEASE_PROB[k] * VESICLE_SHARE[k] for k in ("low", "mid", "high")}

# Free energy of ATP hydrolysis in living cells: about -47 kJ/mol (E. coli) to -70 kJ/mol
# (human muscle), Milo & Phillips, Cell Biology by the Numbers.
KJ_PER_MOL_ATP = dict(low=47.0, mid=55.0, high=70.0)
J_PER_ATP = {k: v * 1e3 / N_AVOGADRO for k, v in KJ_PER_MOL_ATP.items()}

# Sanity checks for the whole brain / whole fly
BRAIN_POWER_W = 256e-9        # explanted adult female brain, room temperature (Panda et al. 2026)
FLY_POWER_W = (43e-3 * 0.78e-3, 65e-3 * 0.78e-3)   # 43-65 mW/g x 0.78 mg (Piper et al. 2014)

# --------------------------------------------------------------- chips --------------
# Intel Loihi (Davies et al. 2018 IEEE Micro, Table 2, pre-silicon at 0.75 V)
LOIHI1 = dict(synop_J=23.6e-12, neuron_update_inactive_J=52e-12, neuron_update_active_J=81e-12,
              neurons_per_chip=128 * 1024, cores_per_chip=128)
# Intel Loihi 2: no per-operation energy has been published. DERIVED upper bounds from the
# Hala Point system (1,152 chips, max 2,600 W, 380e12 synaptic ops/s, 240e12 neuron ops/s):
# all of the power charged to one kind of operation at a time.
HALA_POINT = dict(chips=1152, max_W=2600.0, synops_per_s=380e12, neuron_ops_per_s=240e12)
LOIHI2 = dict(synop_J=HALA_POINT["max_W"] / HALA_POINT["synops_per_s"],
              neuron_update_J=HALA_POINT["max_W"] / HALA_POINT["neuron_ops_per_s"],
              neurons_per_chip=1_000_000, max_W_per_chip=HALA_POINT["max_W"] / HALA_POINT["chips"])
# Sandia (Wang et al. 2025, arXiv:2508.16792): FlyWire on 12 Loihi 2 chips (1,440 cores);
# wall time per simulated second of the sugar experiment. No power was measured.
SANDIA = dict(chips=12, cores=1440, sugar_wall_s_dt01=53.76e-3, sugar_wall_s_dt1=12.40e-3,
              brian2_wall_s=4.419, stacs_wall_s=2.656)
# IBM TrueNorth (Merolla et al. 2014 Science): 1M neurons, 256M synapses, 4,096 cores,
# 63 mW on a video task; 26 pJ per synaptic event; at most 256 inputs per neuron.
TRUENORTH = dict(synevent_J=26e-12, chip_W=63e-3, neurons_per_chip=1_000_000, fan_in=256)
# SpiNNaker: about 20 nJ per synaptic event (early chip-level figure) up to 0.6 uJ for a
# whole machine running a cortical model in real time (Rhodes et al. 2020).
SPINNAKER = dict(synevent_J=(20e-9, 0.6e-6))
# SpiNNaker2 (Scholze et al. 2026, arXiv:2607.24396): >150,000 neurons and >1.8e9 synaptic
# events/s per chip at a 1 ms step; no per-event energy published.
SPINNAKER2 = dict(neurons_per_chip=150_000, synevents_per_s=1.8e9)
# GPU reference (Knight & Nowotny 2018, via Rhodes et al. 2020): 0.3-0.47 uJ per synaptic event.
GPU = dict(synevent_J=(0.3e-6, 0.47e-6))

# ------------------------------------------------------------- this laptop ----------
LAPTOP_CPU = "Intel Core i3-1215U (2 performance + 4 efficient cores, 8 threads)"
LAPTOP_SPEC_W = dict(base=15.0, max_turbo=55.0)   # Intel product page
LOGICAL_CPUS = 8
