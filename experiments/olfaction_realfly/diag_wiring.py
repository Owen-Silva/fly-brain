"""Diagnostic: how strongly does each glomerulus's ORN population drive its own uPNs in the
model, and how much inhibition do uPNs get from antennal-lobe local neurons (LNs)?
Reads the Phase 2 edge cache (snapshot 630; sign = the published model's sign).
Writes results/diag_wiring.csv. No simulation.
"""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from common import RES, ROOT, groups, load_labels, wait_for_ram

wait_for_ram(1.5)
lab = load_labels()
g = groups(lab)
t = pq.read_table(ROOT / "data" / "cache" / "connectome_630_edges.parquet",
                  columns=["pre", "post", "syn_count", "sign"])
pre = t.column("pre").to_numpy()
post = t.column("post").to_numpy()
cnt = t.column("syn_count").to_numpy()
sgn = t.column("sign").to_numpy()
del t
n = len(lab)
is_upn = np.zeros(n, bool); is_upn[g["upn"]] = True
is_orn = np.zeros(n, bool); is_orn[g["orn"]] = True
is_ln = np.zeros(n, bool); is_ln[g["ln"]] = True
glom = np.full(n, "", dtype=object)
glom[g["orn"]] = g["orn_glom"]
glom[g["upn"]] = g["upn_glom"]
m = is_upn[post]
pre, post, cnt, sgn = pre[m], post[m], cnt[m], sgn[m]
rows = []
for gl in sorted(set(g["orn_glom"])):
    upn = g["upn"][g["upn_glom"] == gl]
    orn = g["orn"][g["orn_glom"] == gl]
    sel = np.isin(post, upn)
    own = sel & np.isin(pre, orn)
    other_orn = sel & is_orn[pre] & ~np.isin(pre, orn)
    ln_exc = sel & is_ln[pre] & (sgn > 0)
    ln_inh = sel & is_ln[pre] & (sgn < 0)
    pairs = own.sum()
    rows.append({"glomerulus": gl, "n_orn": orn.size, "n_upn": upn.size,
                 "own_orn_syn_per_upn": cnt[own].sum() / max(upn.size, 1),
                 "syn_per_orn_upn_pair": cnt[own].mean() if pairs else 0.0,
                 "frac_orn_upn_pairs_connected": pairs / max(orn.size * upn.size, 1),
                 "other_orn_syn_per_upn": cnt[other_orn].sum() / max(upn.size, 1),
                 "ln_exc_syn_per_upn": cnt[ln_exc].sum() / max(upn.size, 1),
                 "ln_inh_syn_per_upn": cnt[ln_inh].sum() / max(upn.size, 1)})
d = pd.DataFrame(rows)
# mV kick into one uPN from one spike of one of its ORNs (0.275 mV per synapse, model w_syn)
d["mv_per_orn_spike"] = 0.275 * d.syn_per_orn_upn_pair * d.frac_orn_upn_pairs_connected
d.to_csv(RES / "diag_wiring.csv", index=False)
print(d[["own_orn_syn_per_upn", "syn_per_orn_upn_pair", "frac_orn_upn_pairs_connected",
         "ln_inh_syn_per_upn", "ln_exc_syn_per_upn", "mv_per_orn_spike"]].describe().round(2).to_string())
