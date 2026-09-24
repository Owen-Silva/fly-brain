"""Seed check (PLAN.md Phase 6 step 1): recompute the main set-A numbers separately for each
of the 3 seeds (4 trials each; a KC then counts as responding if it fires in >= 2 of 4
trials). Writes results/per_seed.csv."""
import numpy as np
import pandas as pd
from scipy import stats

from analyze import DOOR, LFP_PER_HZ, M_VM7, Cfg, lifetime_sparseness, mean_offdiag_corr, pn_eq
from common import RES, groups, load_labels

lab = load_labels()
g = groups(lab)
hc = pd.read_csv(RES / "hc_delta.csv", index_col=0)
sfr = pd.read_csv(RES / "hc_sfr.csv", index_col=0)["sfr_hz"]
gl = [c for c in hc.columns if c != "odour"]
or33b = pd.read_csv(DOOR / "Or33b.csv", sep=";").set_index("InChIKey")["Hallem.2006.EN"]
total24 = hc[gl].sum(axis=1) + or33b.reindex(hc.index).fillna(0)
rows = []
for seed in range(3):
    A = Cfg("alln_A", g, trial_idx=np.arange(4 * seed, 4 * seed + 4))
    kc, _ = A.kc()
    pn = A.upn_by_glom()
    keys = hc.index[[i - 1 for i in A.idx]]
    orn_ev = hc.loc[keys, gl].clip(lower=-sfr[gl], axis=1)
    s_orn = np.array([lifetime_sparseness(orn_ev[x]) for x in gl])
    s_pn = np.array([lifetime_sparseness(pn[x]) for x in gl])
    ok = np.isfinite(s_orn) & np.isfinite(s_pn)
    tot = total24.reindex(keys).to_numpy()
    pred = np.concatenate([pn_eq(hc.loc[keys, x].to_numpy(), M_VM7 * tot / LFP_PER_HZ) for x in gl])
    mod = np.concatenate([pn[x].to_numpy() for x in gl])
    upn_ev = np.array([A.counts(i)[:, A.upn_pos].mean(0) / A.dur_s for i in A.idx]) - \
        A.counts(0)[:, A.upn_pos].mean(0) / A.dur_s
    spk = np.concatenate([np.asarray(x) for x in kc.spikes_per_resp])
    rows.append({"seed": seed, "kc_resp_pct_mean": 100 * kc.kc_resp_frac.mean(),
                 "kc_resp_pct_max": 100 * kc.kc_resp_frac.max(),
                 "pn_less_picky_glomeruli": int((s_pn[ok] < s_orn[ok]).sum()), "n_glomeruli": int(ok.sum()),
                 "olsen_eq_r": float(np.corrcoef(pred, mod)[0, 1]),
                 "corr_orn": mean_offdiag_corr(orn_ev.to_numpy())[0],
                 "corr_upn": mean_offdiag_corr(upn_ev)[0],
                 "corr_kc": mean_offdiag_corr(A.evoked("kc"))[0],
                 "kc_median_spikes": float(np.median(spk))})
d = pd.DataFrame(rows)
d.to_csv(RES / "per_seed.csv", index=False)
print(d.round(3).to_string(index=False))
