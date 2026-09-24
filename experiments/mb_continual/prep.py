"""Step 1: build the real wiring of both brain halves, check the random controls, and
write a census (results/wiring_census.json) plus a per-glomerulus table
(results/glomerulus_table.csv).

Checks (Phase 6 step 2, bugs):
* every control keeps each KC's number of inputs and its exact synapse counts;
* the "shuffled" control reproduces the real glomerulus frequencies (correlation);
* the "uniform" control does not;
* the odour table's strongest glomerulus for three well-known odours matches the source.
"""
import numpy as np
import pandas as pd

from common import (RES, all_glomeruli, control_wiring, glomerulus_frequency,
                    glomerulus_kc_table, load_odours, log, pn_mean, real_wiring, save_json)

t, census = glomerulus_kc_table()
gloms = all_glomeruli()
od = load_odours(gloms)
census["glomeruli_reaching_kcs"] = len(gloms)
census["glomeruli_with_odour_data_setA"] = int(od.set_a.sum())
census["glomeruli_with_odour_data_setAB"] = int(od.has_data.sum())
census["glomeruli_without_odour_data"] = [g for g, h in zip(gloms, od.has_data) if not h]
census["upn_share_of_pn_to_kc_synapses"] = (census["pn_to_kc_synapses_upns"]
                                           / census["pn_to_kc_synapses_all_pns"])
rows = []
for side in ("left", "right"):
    for min_syn in (1, 5):
        r = real_wiring(side, min_syn=min_syn, table=t, gloms=gloms)
        deg = (r.W > 0).sum(1)
        key = f"{side}_minsyn{min_syn}"
        census[key] = {"n_kc": int(r.W.shape[0]), "synapses": int(r.W.sum()),
                       "inputs_per_kc_mean": float(deg.mean()),
                       "inputs_per_kc_median": float(np.median(deg)),
                       "inputs_per_kc_p5_p95": [float(np.percentile(deg, 5)),
                                                float(np.percentile(deg, 95))],
                       "glomeruli_present": int((r.W > 0).any(0).sum()),
                       "kc_types": pd.Series(r.kc_types).value_counts().to_dict()}
        if min_syn != 1:
            continue
        f_real = glomerulus_frequency(r.W)
        rng = np.random.default_rng(12345)
        for kind in ("shuffled", "uniform"):
            fs = []
            for _ in range(5):
                c = control_wiring(r, kind, rng)
                # keeps in-degree and the multiset of synapse counts of every KC
                assert np.array_equal((c.W > 0).sum(1), deg)
                assert np.allclose(np.sort(c.W, 1), np.sort(r.W, 1))
                fs.append(glomerulus_frequency(c.W))
            fm = np.mean(fs, 0)
            census[key][f"{kind}_freq_corr_with_real"] = float(np.corrcoef(fm, f_real)[0, 1])
        for gi, g in enumerate(gloms):
            rows.append({"side": side, "glomerulus": g, "real_freq": f_real[gi],
                         "kcs_reached": int((r.W[:, gi] > 0).sum()),
                         "synapses": int(r.W[:, gi].sum()),
                         "odour_data": "A" if od.set_a[gi] else ("B" if od.has_data[gi] else "none")})
pd.DataFrame(rows).to_csv(RES / "glomerulus_table.csv", index=False)

# odour-table alignment check
P = pn_mean(od.delta, od.set_a)
chk = {}
for name in ("ethyl acetate", "1-hexanol", "E2-hexenal"):
    i = od.names.index(name)
    chk[name] = {"strongest_receptor_glomerulus": gloms[int(np.argmax(od.delta[i]))],
                 "strongest_pn_glomerulus": gloms[int(np.argmax(P[i]))],
                 "n_glomeruli_pn_above_20hz": int((P[i] > 20).sum())}
census["odour_checks"] = chk
census["pn_mean_evoked_hz"] = {"median_over_odour_glom_with_data": float(np.median(P[:, od.has_data])),
                               "p95": float(np.percentile(P[:, od.has_data], 95)),
                               "odours_with_no_glomerulus_above_20hz": int(((P > 20).sum(1) == 0).sum())}
save_json(census, RES / "wiring_census.json")
log("census written")
for k in ("left_minsyn1", "right_minsyn1"):
    c = census[k]
    log(f"{k}: {c['n_kc']} KCs, {c['synapses']} syn, inputs/KC {c['inputs_per_kc_mean']:.2f}, "
        f"glom present {c['glomeruli_present']}, shuffled r={c['shuffled_freq_corr_with_real']:.3f}, "
        f"uniform r={c['uniform_freq_corr_with_real']:.3f}")
log(f"no-data glomeruli: {census['glomeruli_without_odour_data']}")
log(f"odour checks: {chk}")
log(f"PN evoked: {census['pn_mean_evoked_hz']}")
