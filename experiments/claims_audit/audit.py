"""Claims audit: recompute every number quoted on the results overview page and in
the docs' short versions from the saved result files, and compare.

Read-only. Nothing here runs a simulation or loads the whole brain. The two passes
over the connection lists read three columns in batches of 2 million rows
(about 50 MB at a time) and only start when at least 1.5 GB of RAM is free.

Output: experiments/claims_audit/results/audit.csv with columns
    claim, where quoted, quoted value, recomputed value, source file, status, note
status is MATCH / MISMATCH / NO-SOURCE / AMBIGUOUS.
Claims marked "[extra]" were not on the requested list but were checked on the way.

Run (from the repo root):  .venv\\Scripts\\python.exe experiments\\claims_audit\\audit.py
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats
from scipy.optimize import curve_fit

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "results"
# The results overview page (an HTML file outside the repo). Set FLYBRAIN_OVERVIEW_PAGE to
# its path to check the page's quoted numbers too; if it is unset or missing, page claims
# are reported without a page line number.
PAGE = Path(os.environ.get("FLYBRAIN_OVERVIEW_PAGE",
                           str(OUT / "overview-page-not-set.html")))
EXP = ROOT / "experiments"
MN9 = 720575940660219265          # MN9 "contra" (the paper's main read-out)
MN9_IPSI = 720575940645521262
CB0219 = 720575940624600840
DM1_PN = {"left": 720575940631205238, "right": 720575940626410012}   # DM1_lPN (630)
DNA02 = {"L": 720575940629327659, "R": 720575940604737708}

ROWS: list[dict] = []
_TEXT: dict[str, list[str]] = {}


# ----------------------------------------------------------------- helpers
def _lines(doc: str) -> list[str]:
    if doc not in _TEXT:
        p = PAGE if doc == "page" else ROOT / doc
        lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
        if doc == "page":   # search the visible text: drop tags, &nbsp; -> space
            lines = [re.sub(r"<[^>]+>", "", ln).replace("&nbsp;", " ") for ln in lines]
        _TEXT[doc] = lines
    return _TEXT[doc]


def where(*specs: tuple[str, str]) -> str:
    """('page' or 'docs/x.md', regex) -> 'overview page line N; docs/x.md:M'."""
    out = []
    for doc, pat in specs:
        name = "overview page line " if doc == "page" else f"{doc}:"
        hits = [i + 1 for i, ln in enumerate(_lines(doc)) if re.search(pat, ln)]
        out.append(f"{name}{hits[0]}" if hits else f"{name}? (text not found)")
    return "; ".join(out)


def add(claim, where_, quoted, recomputed, source, status, note=""):
    ROWS.append({"claim": claim, "where quoted": where_, "quoted value": quoted,
                 "recomputed value": recomputed, "source file": source,
                 "status": status, "note": note})


def ok(flag: bool) -> str:
    return "MATCH" if flag else "MISMATCH"


def free_gb() -> float:
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    s = MS()
    s.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return s.ullAvailPhys / 1024 ** 3


def wait_for_ram(need_gb=1.5, max_wait_s=600) -> bool:
    t0 = time.time()
    while free_gb() < need_gb:
        if time.time() - t0 > max_wait_s:
            return False
        time.sleep(20)
    return True


def pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


# ----------------------------------------------------------------- Phase 3
def phase3():
    P = EXP / "phase3/results/v630"
    conds = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz",
             "sugar100_bitter40", "sugar100_bitter120", "sugar200_ir94e200"]
    d = {}
    for c in conds:
        s = json.loads((P / f"{c}_settings.json").read_text(encoding="utf-8"))
        sp = pd.read_parquet(P / f"{c}_spikes.parquet", columns=["trial", "flywire_id"])
        n, dur = s["n_trials"], s["duration_ms"] / 1000.0
        tr = np.arange(n)

        def per_trial(nid):
            return (sp[sp.flywire_id == nid].groupby("trial").size()
                    .reindex(tr, fill_value=0).to_numpy(float) / dur)
        d[c] = dict(n=n, n_trials_in_spikes=sp.trial.nunique(), contra=per_trial(MN9),
                    ipsi=per_trial(MN9_IPSI), active=int(sp.flywire_id.nunique()),
                    trial_s=list(s.get("trial_s", [])),
                    tot=sp.groupby("trial").size().reindex(tr, fill_value=0).to_numpy())
        if c == "sugar200_ir94e200":
            d[c]["spikes"] = sp
    src = "experiments/phase3/results/v630/<condition>_spikes.parquet + _settings.json"

    # MN9, ours vs paper (paper sugar values from the paper's Supplementary Table 1A)
    st1a = pd.read_csv(EXP / "phase5/sugar_pathway/paper_reference/paper_ST1A_sugar_firing.csv")
    mrow = st1a[st1a["Flywire ID"] == MN9].iloc[0]
    paper_local = {"sugar_100Hz": (mrow["sugarR_100Hz"], mrow["sugarR_100Hz.1"]),
                   "sugar_200Hz": (mrow["sugarR_200Hz"], mrow["sugarR_200Hz.1"])}
    Q = {"sugar_100Hz": ("sugar 100 Hz", 67.0, 65.7, r"sugar 100 Hz \(10 trials\)"),
         "sugar_200Hz": ("sugar 200 Hz", 92.7, 93.2, r"sugar 200 Hz \(10 trials\)"),
         "water_200Hz": ("water 200 Hz", 33.5, 30.7, r"water 200 Hz \(10 trials\)"),
         "bitter_200Hz": ("bitter 200 Hz", 0.0, 0.0, r"bitter 200 Hz alone"),
         "sugar100_bitter40": ("sugar 100 + bitter 40", 48.0, 45.3, r"sugar 100 \+ bitter 40 Hz"),
         "sugar100_bitter120": ("sugar 100 + bitter 120", 0.9, 1.5, r"sugar 100 \+ bitter 120 Hz"),
         "sugar200_ir94e200": ("sugar 200 + Ir94e 200", 58.4, 64.3, r"sugar 200 \+ Ir94e 200 Hz \(5")}
    for c, (label, ours_q, paper_q, pat) in Q.items():
        x = d[c]["contra"]
        w = where(("docs/phase3-explained.md", pat))
        if c == "sugar_100Hz":
            w = where(("page", r"fires at 67\.0"), ("docs/phase3-explained.md", pat))
        add(f"Phase 3 MN9, ours: {label}", w, f"{ours_q:.1f} Hz",
            f"{x.mean():.2f} +/- {x.std():.2f} Hz (n={len(x)} trials; per trial {x.astype(int).tolist()})",
            src, ok(round(x.mean(), 1) == ours_q))
        if c in paper_local:
            m, sd = paper_local[c]
            add(f"Phase 3 MN9, paper: {label}", w, f"{paper_q:.1f} Hz", f"{m:.2f} +/- {sd:.2f} Hz",
                "experiments/phase5/sugar_pathway/paper_reference/paper_ST1A_sugar_firing.csv "
                "(the paper's Supplementary Table 1A, MN9_r row)", ok(round(m, 1) == paper_q))
        else:
            add(f"Phase 3 MN9, paper: {label}", w, f"{paper_q:.1f} Hz", "not recomputable here",
                "none in the repo (authors' results.zip CSVs, cited in docs/reference-notes.md 4.3)",
                "NO-SOURCE",
                "The paper-side number was copied from the authors' result files into "
                "docs/reference-notes.md; those files are not saved here. docs/phase3-explained.md "
                "already marks it UNVERIFIED. To check it: download results.zip from Edmond "
                "(URL in docs/reference-notes.md 3.1) and read the MN9 row.")
    # ipsi (extra)
    for c, q in (("sugar_100Hz", 51.4), ("sugar_200Hz", 62.9)):
        x = d[c]["ipsi"]
        add(f"[extra] Phase 3 MN9 same side (ipsi), ours: {c}",
            where(("docs/phase3-explained.md", r"MN9 on the same side")), f"{q} Hz",
            f"{x.mean():.2f} Hz", src, ok(round(x.mean(), 1) == q))

    # the 12 direction checks (rows of comparison_table.csv, rules from its column)
    m = {c: d[c]["contra"].mean() for c in conds}
    mi = {c: d[c]["ipsi"].mean() for c in conds}
    a100, a200 = d["sugar_100Hz"]["active"], d["sugar_200Hz"]["active"]
    checks = [m["sugar_100Hz"] > 0,
              0 < mi["sugar_100Hz"] < m["sugar_100Hz"],
              a100 < a200,
              m["sugar_200Hz"] > m["sugar_100Hz"],
              0 < mi["sugar_200Hz"] < m["sugar_200Hz"],
              a200 > a100,
              0 < m["water_200Hz"] < m["sugar_200Hz"],
              0 < mi["water_200Hz"] < m["water_200Hz"],
              m["bitter_200Hz"] == 0,
              m["sugar100_bitter40"] < m["sugar_100Hz"],
              m["sugar100_bitter120"] < 0.05 * m["sugar_100Hz"],
              0.05 * m["sugar_200Hz"] < m["sugar200_ir94e200"] < m["sugar_200Hz"]]
    add("Phase 3 checkpoint passed 12 of 12 checks",
        where(("page", r"passed 12 of 12 checks"), ("page", r"12 of 12 checks, with the same"),
              ("docs/phase3-explained.md", r"Every one of the 12 checks")),
        "12 of 12", f"{sum(checks)} of {len(checks)} (active neurons: {a100} at 100 Hz, {a200} at 200 Hz)",
        src + "; rules from experiments/phase3/comparison_table.csv", ok(sum(checks) == 12),
        "All 12 direction checks re-derived from the raw spikes. Two of the 12 are the same "
        "comparison counted twice ('network grows with rate', once on the 100 Hz row and once "
        "on the 200 Hz row), so there are 11 distinct checks.")
    ns = [d[c]["n"] for c in conds]
    add("Phase 3 used 5-10 trials per condition",
        where(("page", r"5.10 trials per condition"), ("docs/phase3-explained.md", r"We ran 10 trials")),
        "5-10 trials", f"{dict(zip(conds, ns))}; {sum(ns)} trials in all",
        "experiments/phase3/results/v630/*_settings.json (n_trials, seeds)",
        ok(min(ns) == 5 and max(ns) == 10 and all(d[c]["n_trials_in_spikes"] == d[c]["n"] for c in conds)))
    # active neurons vs the reference code's own 30-trial runs (extra)
    parts = []
    for c, f in (("sugar_100Hz", "sugarR_100Hz"), ("sugar_200Hz", "sugarR")):
        ref = pd.read_parquet(ROOT / f"data/reference/results/example/{f}.parquet", columns=["trial", "flywire_id"])
        rc = ref.flywire_id.value_counts() / (ref.trial.nunique() * 1.0)       # Hz over 30 x 1 s
        ours_sp = pd.read_parquet(P / f"{c}_spikes.parquet", columns=["flywire_id"]).flywire_id
        ours_ids = set(ours_sp)
        only_ref = rc[~rc.index.isin(list(ours_ids))]
        parts.append((c, len(rc), d[c]["active"], len(only_ref), len(ours_ids - set(rc.index)), only_ref.max()))
        uni = rc.index.union(pd.Index(list(ours_ids)))
        ro = (ours_sp.value_counts() / d[c]["n"]).reindex(uni, fill_value=0.0)
        r_union = np.corrcoef(ro.to_numpy(), rc.reindex(uni, fill_value=0.0).to_numpy())[0, 1]
        if c == "sugar_200Hz":
            add("[extra] Phase 3 short answer: neuron-by-neuron correlation 0.9996 across 448 neurons (200 Hz)",
                where(("docs/phase3-explained.md", r"correlation 0\.9996 across 448")), "r = 0.9996, 448 neurons",
                f"r = {r_union:.4f} over the {len(uni)} neurons active in either run",
                "data/reference/results/example/sugarR.parquet; " + src,
                ok(round(r_union, 4) == 0.9996 and len(uni) == 448))
    add("[extra] Phase 3 doc: 'Their run has 16 or 17 more active neurons than ours (448 vs 432 at 200 Hz)'",
        where(("docs/phase3-explained.md", r"16 or 17 more")), "16 or 17 more",
        "; ".join(f"{c}: reference {a} vs ours {b} = {a - b} more; {o} active only in theirs (max {mx:.2f} Hz), "
                  f"{n} only in ours" for c, a, b, o, n, mx in parts),
        "data/reference/results/example/sugarR_100Hz.parquet, sugarR.parquet; " + src,
        ok(all(a - b in (16, 17) for _, a, b, _, _, _ in parts)),
        "At 100 Hz their run has 12 more active neurons, not 16-17: 17 fire only in theirs and 5 only in ours. "
        "The 'less than once every 4 seconds' part holds (all below 0.25 Hz). Suggested: 'Their runs have 16 "
        "(200 Hz) and 17 (100 Hz) neurons that never fired in ours, all firing less than once every 4 seconds.'")
    add("[extra] Phase 3 doc Files section: results/v783/ holds per-experiment spikes and rates",
        where(("docs/phase3-explained.md", r"`results/v783/`")), "results/v783/ exists",
        "folder exists" if (EXP / "phase3/results/v783").exists() else "folder does not exist",
        "experiments/phase3/results/", ok((EXP / "phase3/results/v783").exists()),
        "The same doc says the snapshot-783 run was dropped for time, so the folder was never made. "
        "Suggested: delete ', `results/v783/`' from the Files list.")
    # runaway in phase 3 (extra)
    ir = d["sugar200_ir94e200"]
    x = ir["contra"]
    no_drop = np.delete(x, np.argmin(x)).mean()
    add("[extra] Phase 3 Ir94e runaway: MN9 without the runaway trial where it dropped would be about 67",
        where(("docs/phase3-explained.md", r"our MN9\s*$|average for this experiment would be about 67")),
        "about 67 Hz", f"{no_drop:.2f} Hz (per trial {x.astype(int).tolist()}; spikes per trial "
        f"{ir['tot'].tolist()})", src, ok(round(no_drop) == 67))
    return d


# ----------------------------------------------------------------- fast engine
def fast_engine(p3):
    s = json.loads((EXP / "fast_engine/results/summary.json").read_text(encoding="utf-8"))
    rep = pd.read_csv(EXP / "phase6/runaway/results/brian2_replay.csv")
    same = bool((rep.brian2_total == rep.fast_total).all() and (rep.brian2_active == rep.fast_active).all()
                and (rep.brian2_runaway == rep.fast_runaway).all() and rep.first100ms_identical.all()
                and (rep.per_neuron_r >= 0.99999).all()
                and ((rep.brian2_onset_ms == rep.fast_onset_ms) | rep.brian2_onset_ms.isna()).all())
    add("Fast engine gives the same spikes as Brian2",
        where(("page", r"reproduced the same model spike for spike"), ("page", r"gives the same spikes as the reference")),
        "same spikes", f"{len(rep)} whole-brain trials replayed with identical input: total spikes, active "
        f"neurons, runaway flag and onset identical in {len(rep)}/{len(rep)}; first 100 ms identical; per-neuron r = 1.0",
        "experiments/phase6/runaway/results/brian2_replay.csv", ok(same),
        "The small-network spike-by-spike test (tests/test_fast_engine.py) has no saved log; "
        "the whole-brain replay above is the saved evidence. Across different random input the "
        "two agree statistically (experiments/fast_engine/results/summary.json, r = 0.9996-0.9998).")
    walls = [v["wall_s_per_trial"] for v in s["runs"].values()]
    one = [s["single_thread_s_per_trial_100Hz"], s["single_thread_s_per_trial_200Hz"]]
    ten = s["single_thread_s_for_one_10s_trial_100Hz"] / 10
    add("Fast engine: about 0.2-0.5 s per simulated second",
        where(("page", r"0\.2.0\.5 s per simulated second")), "0.2-0.5 s",
        f"1-s trials: {min(walls):.2f}-{max(walls):.2f} s each with 2 trials running at once; "
        f"{one[0]:.2f}-{one[1]:.2f} s on one core; one 10-s trial: {ten:.2f} s per simulated second",
        "experiments/fast_engine/results/summary.json", ok(0.2 <= min(walls + one) and max(walls + one) <= 0.5),
        "Holds for 1-second trials. A single 10-second trial ran at 0.68 s per simulated second.")
    add("Fast engine: ~0.3 s to simulate one second of the whole brain",
        where(("page", r"~0\.3 s")), "~0.3 s",
        f"median {np.median(walls + one):.2f} s over the 8 timed runs (range {min(walls + one):.2f}-{max(walls + one):.2f})",
        "experiments/fast_engine/results/summary.json", "MATCH",
        "0.22-0.34 s with two trials sharing two cores; 0.38-0.48 s on one core.")
    ts = np.array([t for c in p3 for t in p3[c]["trial_s"]])
    over4 = int((ts > 240).sum())
    add("Brian2 needs 1-4 minutes per simulated second",
        where(("page", r"instead of 1.4 minutes"), ("docs/phase3-explained.md", r"between 1 and 5 minutes")),
        "1-4 minutes (page); 1-5 minutes (Phase 3 doc)",
        f"{len(ts)} saved Brian2 trials: {ts.min() / 60:.1f}-{ts.max() / 60:.1f} min, median {np.median(ts) / 60:.1f} min; "
        f"{over4} of {len(ts)} took over 4 min, {int((ts > 300).sum())} over 5 min",
        "experiments/phase3/results/v630/*_settings.json (trial_s)", "AMBIGUOUS",
        "Typical trials fit 1-4 min, but the saved range reaches 6.5 min (two runs shared the "
        "laptop). docs/fast-engine-explained.md quotes 21-55 s for Brian2 instead (runs alone "
        "or a synthetic network), so the three places give three different Brian2 timings.")
    med = np.median(ts)
    add("Fast engine is hundreds of times faster than Brian2",
        where(("page", r"hundreds of times faster"), ("docs/fast-engine-explained.md", r"about 100 times faster")),
        "'hundreds of times' (page); 'about 100 times' / 45-145x (fast-engine doc)",
        f"median saved Brian2 trial {med:.0f} s / one-core engine {one[0]:.2f}-{one[1]:.2f} s = "
        f"{med / one[1]:.0f}-{med / one[0]:.0f}x; against the doc's 21-55 s: {21 / one[1]:.0f}-{55 / one[0]:.0f}x",
        "experiments/phase3/results/v630/*_settings.json; experiments/fast_engine/results/summary.json",
        "AMBIGUOUS", "The page and the fast-engine doc disagree. Both are defensible, depending on "
        "which Brian2 timing is used.")


# ----------------------------------------------------------------- Phase 2
def phase2():
    R = ROOT / "data/reference"
    n630 = sum(1 for _ in open(R / "2023_03_23_completeness_630_final.csv", encoding="utf-8")) - 1
    n783 = sum(1 for _ in open(R / "Completeness_783.csv", encoding="utf-8")) - 1
    e630 = pq.ParquetFile(R / "2023_03_23_connectivity_630_final.parquet").metadata.num_rows
    e783 = pq.ParquetFile(R / "Connectivity_783.parquet").metadata.num_rows
    add("Snapshot 630: 127,400 neurons, 14,687,178 connections",
        where(("page", r"Snapshot 630: 127,400"), ("page", r"127,400\s*neurons \(FlyWire")),
        "127,400 / 14,687,178", f"{n630:,} / {e630:,}",
        "data/reference/2023_03_23_completeness_630_final.csv (rows); ..._connectivity_630_final.parquet (rows)",
        ok(n630 == 127400 and e630 == 14687178))
    syn = n5 = 0
    nodes5 = set()
    if wait_for_ram():
        pf = pq.ParquetFile(R / "Connectivity_783.parquet")
        for b in pf.iter_batches(batch_size=2_000_000,
                                 columns=["Presynaptic_ID", "Postsynaptic_ID", "Connectivity"]):
            c = b.column("Connectivity").to_numpy()
            syn += int(c.sum())
            k = c >= 5
            n5 += int(k.sum())
            nodes5.update(np.unique(b.column("Presynaptic_ID").to_numpy()[k]).tolist())
            nodes5.update(np.unique(b.column("Postsynaptic_ID").to_numpy()[k]).tolist())
        rec = f"{n783:,} / {e783:,} / {syn:,}"
        st = ok(n783 == 138639 and e783 == 15091983 and syn == 54492922)
    else:
        rec, st = f"{n783:,} / {e783:,} / synapse sum not computed (RAM)", "AMBIGUOUS"
    add("Snapshot 783: 138,639 neurons, 15,091,983 connections, 54,492,922 synapses",
        where(("page", r"Snapshot 783: 138,639"), ("docs/phase2-explained.md", r"\| Neurons \| 138,639")),
        "138,639 / 15,091,983 / 54,492,922 (page: 54.5 M synapses)", rec,
        "data/reference/Completeness_783.csv; data/reference/Connectivity_783.parquet (rows; sum of Connectivity)", st)
    fw = np.load(ROOT / "data/flywire/proofread_root_ids_783.npy", mmap_mode="r").shape[0]
    add("Phase 2: 'Counts match FlyWire's'",
        where(("page", r"Counts match FlyWire")), "counts match",
        f"neurons {n783:,} vs FlyWire's proofread list {fw:,} ({fw - n783} missing); synapses {syn:,} "
        f"(published '54.5 million'); connections with >=5 synapses {n5:,}, neurons in them {len(nodes5):,} "
        "(published 2,700,513 and 134,181 per docs/phase2-explained.md)",
        "data/reference/Connectivity_783.parquet; data/flywire/proofread_root_ids_783.npy", "AMBIGUOUS",
        "Synapse and strong-connection counts match exactly, but the neuron count is 616 short of "
        "FlyWire's (every missing neuron has zero synapses, per experiments/phase2/crosscheck_zenodo.txt). "
        "Suggested page wording: 'Synapse counts match FlyWire's; 616 unconnected neurons are left out.'")
    txt = (EXP / "phase2/summary.txt").read_text(encoding="utf-8")
    c783 = float(re.search(r"cached load \(parquet cache[^:]*:\s*([\d.]+) s", txt).group(1))
    c630 = float(re.search(r"cold load [\d.]+ s, cached load ([\d.]+) s", txt).group(1))
    add("Phase 2: the map loads in under half a second (from cache)",
        where(("page", r"under half a second"), ("docs/phase2-explained.md", r"Under half a second")),
        "< 0.5 s", f"{c783} s (783), {c630} s (630), as logged", "experiments/phase2/summary.txt",
        ok(max(c783, c630) < 0.5), "Logged timing, not re-timed here (timing it would load the whole map).")


# ----------------------------------------------------------------- Phase 4
def phase4():
    s = json.loads((EXP / "fast_engine/results/summary.json").read_text(encoding="utf-8"))["runs"]["sugar_100Hz"]
    setup = json.loads((ROOT / "app/setups/sugar_grn_right.json").read_text(encoding="utf-8"))
    add("Phase 4: the sugar experiment run from code gives MN9 67.63 Hz",
        where(("docs/phase4-app-explained.md", r"67\.63 Hz both ways")), "67.63 Hz",
        f"{s['mn9_hz']:.2f} Hz (other MN9 {s['mn9b_hz']:.2f} Hz, {s['vs_reference_brian2']['neurons_active_fast']} "
        f"active neurons); same setup as app/setups/sugar_grn_right.json ({setup['n_trials']} trials, seed "
        f"{setup['seed']}, {setup['rate_hz']:.0f} Hz)", "experiments/fast_engine/results/summary.json",
        ok(round(s["mn9_hz"], 2) == 67.63))
    add("Phase 4: the app gives the same MN9 as code",
        where(("page", r"same MN9 result in the app as in code"), ("docs/phase4-app-explained.md", r"SAME RESULT\. MN9")),
        "same result (67.63 Hz both ways)", "not recomputable from saved files",
        "none (the comparison printed to the terminal; nothing was saved)", "NO-SOURCE",
        "Regenerate with: .venv\\Scripts\\python.exe -m app.run_setup sugar_grn_right --compare "
        "(or pytest tests/test_app.py -k checkpoint_sugar). It loads the whole brain, so it was not run here.")


# ----------------------------------------------------------------- silencing screen
def silencing():
    R = EXP / "phase5/sugar_pathway/results"
    runs = pd.read_csv(R / "runs.csv", dtype={"silenced": str})   # 18-digit ids: never via float
    paper = pd.read_csv(EXP / "phase5/sugar_pathway/paper_reference/paper_ST1C_sugar_top200_silencing.csv")
    paper = paper.rename(columns={"Flywire ID": "root_id", "100 Hz.2": "p100", "50 Hz.2": "p50"})
    skipped = pd.read_csv(R / "singles_50_skipped_silent.csv")
    out = {}
    for hz in (100, 50):
        base = runs[(runs.kind == "baseline") & (runs.stim_hz == hz) & (runs.seed == 0)].sort_values("trial").mn9_hz.to_numpy(float)
        ratio = {}
        for kind in ("single_stage1", "single"):          # 30-trial runs overwrite 10-trial ones
            sub = runs[(runs.kind == kind) & (runs.stim_hz == hz) & (runs.seed == 0) & (runs.n_silenced == 1)]
            for sid, g in sub.groupby("silenced"):
                x = g.sort_values("trial").mn9_hz.to_numpy(float)
                ratio[int(sid)] = x.mean() / base[: len(x)].mean()
        n_sk = 0
        if hz == 50:
            for rid in skipped.root_id.astype(np.int64):
                if int(rid) not in ratio:
                    ratio[int(rid)] = 1.0
                    n_sk += 1
        ours = pd.Series(ratio, name="ours")
        both = paper.set_index("root_id").join(ours, how="inner")
        both = both[both["p100"].notna()]
        col = "p100" if hz == 100 else "p50"
        r = np.corrcoef(both["ours"], both[col])[0, 1]
        rho = stats.spearmanr(both["ours"], both[col]).statistic
        n_fixed = int((both.index.isin(skipped.root_id.astype(np.int64))).sum()) if hz == 50 else 0
        out[hz] = (len(both), r, rho, n_fixed, len(ours))
    w = where(("page", r"198 neurons that both screens"), ("docs/phase5-sugar-pathway.md", r"r = 0\.93\*\* with"))
    for hz in (100, 50):
        n, r, rho, n_fixed, n_ours = out[hz]
        note = (f"Pearson r. The rank correlation (Spearman) is only {rho:.2f}: the 0.93 is carried by the "
                "few neurons with big effects; most of the 198 sit near 'no effect' in both screens.")
        if hz == 50:
            note += (f" {n_fixed} of the {n} were never simulated at 50 Hz (silent at 50 Hz, so their ratio "
                     "is set to exactly 1.0, which is logically exact).")
        add(f"Silencing screen vs paper: r = 0.93 over 198 neurons at {hz} Hz sugar", w, "r = 0.93, n = 198",
            f"r = {r:.4f}, n = {n} (of {n_ours} neurons we silenced)",
            "experiments/phase5/sugar_pathway/results/runs.csv (per-trial MN9) + paper_reference/"
            "paper_ST1C_sugar_top200_silencing.csv", ok(round(r, 2) == 0.93 and n == 198), note)


# ----------------------------------------------------------------- competition
def hill(b, m0, b50, n):
    return m0 / (1.0 + (np.maximum(b, 1e-9) / b50) ** n)


def competition():
    R = EXP / "phase5/competition/results"
    g = pd.read_csv(R / "grid.csv")
    s0 = g[g.seed == 0].set_index(["kind", "sugar_hz", "other_hz"]).mn9_mean
    pts = [("bitter", 100, 0, 67.0), ("bitter", 100, 40, 45.3), ("bitter", 100, 80, 11.7),
           ("bitter", 100, 120, 1.5), ("bitter", 100, 200, 0.0), ("bitter", 200, 0, 94.9),
           ("bitter", 200, 200, 11.2), ("bitter", 0, 200, 0.0), ("ir94e", 100, 200, 2.5),
           ("ir94e", 200, 200, 64.3), ("water", 40, 0, 6.3), ("water", 40, 200, 61.2),
           ("water", 0, 200, 30.9)]
    diffs = [(k, s, o, s0[(k, s, o)], p, s0[(k, s, o)] - p) for k, s, o, p in pts]
    worst = max(diffs, key=lambda t: abs(t[5]))
    add("Competition reproduces the paper within 2.5 Hz at every test point",
        where(("page", r"reproduce within 2\.5 Hz"), ("docs/phase5-competition.md", r"within 2\.5 Hz at every test point")),
        "within 2.5 Hz at all 13 points",
        f"largest gap {abs(worst[5]):.2f} Hz ({worst[0]} sugar {worst[1]} + {worst[2]}: ours {worst[3]:.2f} vs paper {worst[4]}); "
        f"all 13 within {max(abs(t[5]) for t in diffs):.2f} Hz",
        "experiments/phase5/competition/results/grid.csv (seed 0, 30 trials)",
        ok(max(abs(t[5]) for t in diffs) <= 2.5),
        "Our side recomputed; the paper side is as quoted from docs/reference-notes.md 4.3 (no local copy). "
        "Note the 'paper' sugar-alone numbers here (67.0, 94.9) come from the paper's Fig. 3b, not the "
        "65.7 / 93.2 of Fig. 1 used in Phase 3; both are the paper's own numbers.")
    add("[extra] Competition short version: sugar alone ~67 Hz, bitter pushes MN9 down to 1.4 Hz",
        where(("docs/phase5-competition.md", r"pushes it down to 1\.4 Hz")), "about 67 Hz; 1.4 Hz",
        f"{s0[('bitter', 100, 0)]:.2f} Hz; {s0[('bitter', 100, 120)]:.2f} Hz (bitter 120)",
        "experiments/phase5/competition/results/grid.csv", ok(round(s0[("bitter", 100, 120)], 1) == 1.4))
    # heat map cells: 3 seeds x 30 trials
    main = g[(g.kind == "bitter") & g.sugar_hz.isin([50, 100, 150, 200]) & g.other_hz.isin([0, 25, 50, 100, 150, 200])]
    cells = main.groupby(["sugar_hz", "other_hz"]).agg(ns=("seed", "nunique"), nt=("n_trials", "min"),
                                                       spread=("mn9_mean", lambda v: v.max() - v.min()))
    add("[extra] Heat map: each cell is the mean of 3 seeds x 30 trials",
        where(("page", r"mean of 3 seeds"), ("docs/phase5-competition.md", r"averaged over 3 seeds x 30 trials")),
        "3 seeds x 30 trials", f"{len(cells)} cells; seeds per cell {sorted(cells.ns.unique().tolist())}; "
        f"trials per seed {sorted(cells.nt.unique().tolist())}; largest seed-to-seed spread {cells.spread.max():.2f} Hz",
        "experiments/phase5/competition/results/grid.csv",
        ok(set(cells.ns) == {3} and set(cells.nt) == {30}))
    worst_cell = cells.spread.idxmax()
    sd_max = main.groupby(["sugar_hz", "other_hz"]).mn9_mean.std().max()
    add("[extra] Competition doc: across seeds the heat-map averages differ by at most about 1 Hz",
        where(("docs/phase5-competition.md", r"differ by at most about 1 Hz")), "at most about 1 Hz",
        f"largest seed-to-seed difference {cells.spread.max():.2f} Hz (sugar {worst_cell[0]} + bitter {worst_cell[1]}); "
        f"{int((cells.spread > 1.5).sum())} of {len(cells)} cells differ by more than 1.5 Hz; largest standard deviation "
        f"across seeds {sd_max:.2f} Hz", "experiments/phase5/competition/results/grid.csv", "MISMATCH",
        "The pattern is still stable (3 Hz on rates of 9-93 Hz), but the sentence understates it. Suggested: "
        "'Across seeds the averages differ by at most about 3 Hz (standard deviation at most 1.6 Hz).'")
    # Hill fits, redone from the per-seed grid
    b = g[g.kind == "bitter"].groupby(["sugar_hz", "other_hz"]).agg(mn9=("mn9_mean", "mean"),
                                                                   ns=("seed", "nunique")).reset_index()
    fits, mf = {}, {}
    for sug in (50, 100, 150, 200):
        dd = b[(b.sugar_hz == sug) & (b.ns >= 3)]
        x, y = dd.other_hz.to_numpy(float), dd.mn9.to_numpy(float)
        m0 = y[x == 0].mean()
        (m0f, b50, n), _ = curve_fit(hill, x, y, p0=[m0, np.median(x[x > 0]), 2.0],
                                     bounds=([0, 1, 0.3], [200, 2000, 30]), maxfev=20000)
        fits[sug] = (b50 / sug, 81 ** (1 / n))
        o = np.argsort(x)
        mf[sug] = np.interp(-0.5 * m0, -y[o], x[o]) / sug     # model-free: where MN9 = half of sugar alone
    lo, hi = min(v[0] for v in fits.values()), max(v[0] for v in fits.values())
    add("Competition: MN9 halves at bitter = 0.47-0.56 x sugar, at all four sugar levels",
        where(("page", r"0\.47.0\.56 times"), ("docs/phase5-competition.md", r"0\.47 to 0\.56 times")),
        "0.47-0.56", f"Hill fit b50/sugar: " + ", ".join(f"{k} Hz {v[0]:.3f}" for k, v in fits.items())
        + "; without a fit (where the measured curve crosses half of sugar-alone): "
        + ", ".join(f"{k} Hz {v:.2f}" for k, v in mf.items()),
        "experiments/phase5/competition/results/grid.csv (3-seed means, fit redone)",
        ok(round(lo, 2) == 0.47 and round(hi, 2) == 0.56),
        "The fit's 'half' is half of the fitted top, which sits a few Hz below the measured sugar-alone rate; "
        "the fit-free crossing points are shown for comparison.")
    add("[extra] Competition: 10% to 90% suppression takes a 3.3- to 4.6-fold rise in bitter",
        where(("docs/phase5-competition.md", r"3\.3- to 4\.6-fold")), "3.3-4.6x",
        ", ".join(f"{k} Hz {v[1]:.2f}x" for k, v in fits.items()),
        "experiments/phase5/competition/results/grid.csv (fit redone)",
        ok(round(min(v[1] for v in fits.values()), 1) == 3.3 and round(max(v[1] for v in fits.values()), 1) == 4.6))
    # CB0219 rescue
    rc = pd.read_csv(R / "suppressor_recovery.csv")
    sil = pd.read_csv(R / "suppressor_silencing.csv")
    top1_ids = set(sil[sil.label == "top1"].silenced.astype(str))
    mean = lambda lab, bh: rc[(rc.label == lab) & (rc.bitter_hz == bh)].mn9.mean()
    s_alone, s_b80, cb_b80 = mean("none", 0), mean("none", 80), mean("top1", 80)
    recov = (cb_b80 - s_b80) / (s_alone - s_b80)
    add("Silencing CB0219 restores MN9 12 -> 66 Hz (98% recovery) at sugar 100 + bitter 80",
        where(("page", r"back from 12 Hz to 66 Hz"), ("docs/phase5-competition.md", r"from 12 Hz to 66 Hz")),
        "12 -> 66 Hz, 98%",
        f"{s_b80:.2f} -> {cb_b80:.2f} Hz; recovery {recov * 100:.1f}% (sugar alone {s_alone:.2f} Hz; "
        f"silenced id {', '.join(top1_ids)})",
        "experiments/phase5/competition/results/suppressor_recovery.csv (mean of seeds 0-2)",
        ok(round(s_b80) == 12 and round(cb_b80) == 66 and round(recov * 100) == 98))


def connectome_630_targets(bitter_ids, sugar_ids):
    """One pass over the 630 connection list, keeping edges onto CB0219 and the DM1 PNs."""
    if not wait_for_ram():
        return None
    targets = np.array([CB0219, DM1_PN["left"], DM1_PN["right"]], dtype=np.int64)
    keep = []
    pf = pq.ParquetFile(ROOT / "data/reference/2023_03_23_connectivity_630_final.parquet")
    for b in pf.iter_batches(batch_size=2_000_000, columns=["Presynaptic_ID", "Postsynaptic_ID", "Connectivity"]):
        post = b.column("Postsynaptic_ID").to_numpy()
        k = np.isin(post, targets)
        if k.any():
            keep.append(pd.DataFrame({"pre": b.column("Presynaptic_ID").to_numpy()[k], "post": post[k],
                                      "syn": b.column("Connectivity").to_numpy()[k]}))
    return pd.concat(keep, ignore_index=True)


def cb0219_and_dm1():
    P = EXP / "phase3/results/v630"
    bitter = json.loads((P / "bitter_200Hz_settings.json").read_text(encoding="utf-8"))["excite_ids"]
    sugar = json.loads((P / "sugar_100Hz_settings.json").read_text(encoding="utf-8"))["excite_ids"]
    e = connectome_630_targets(bitter, sugar)
    if e is None:
        add("CB0219 gets 247 synapses from bitter GRNs", "", "247", "not computed (RAM)", "", "AMBIGUOUS")
        return
    onto = e[e.post == CB0219]
    fb = int(onto[onto.pre.isin(bitter)].syn.sum())
    fs = int(onto[onto.pre.isin(sugar)].syn.sum())
    add("CB0219 gets 247 synapses straight from the bitter GRNs (none from sugar GRNs)",
        where(("page", r"247 synapses"), ("docs/phase5-competition.md", r"gets 247 synapses")),
        "247 (0 from sugar)", f"{fb} from the {len(bitter)} bitter GRNs; {fs} from the {len(sugar)} sugar GRNs",
        "data/reference/2023_03_23_connectivity_630_final.parquet; GRN ids from experiments/phase3/results/v630/*_settings.json",
        ok(fb == 247 and fs == 0))
    # DM1: every DM1 ORN onto each DM1_lPN
    n = pd.read_parquet(ROOT / "data/cache/connectome_630_neurons.parquet",
                        columns=["root_id", "hemibrain_type", "side"])
    orn = n[n.hemibrain_type == "ORN_DM1"]
    tab = {}
    for pside, pid in DM1_PN.items():
        for oside in ("left", "right"):
            ids = orn[orn.side == oside].root_id
            tab[(oside, pside)] = int(e[(e.post == pid) & e.pre.isin(ids)].syn.sum())
    L = tab[("left", "left")] + tab[("right", "left")]
    Rr = tab[("left", "right")] + tab[("right", "right")]
    add("DM1: the left PN gets 52% more receptor synapses than the right one",
        where(("page", r"52% more sensor synapses"), ("docs/phase6-steering.md", r"52% more receptor synapses")),
        "52% more", f"left PN {L:,} vs right PN {Rr:,} = {pct(L / Rr - 1)} (from left ORNs {tab[('left', 'left')]}/"
        f"{tab[('left', 'right')]}, from right ORNs {tab[('right', 'left')]}/{tab[('right', 'right')]}; "
        f"{(orn.side == 'left').sum()} left and {(orn.side == 'right').sum()} right DM1 ORNs)",
        "data/reference/2023_03_23_connectivity_630_final.parquet; data/cache/connectome_630_neurons.parquet (labels)",
        ok(round((L / Rr - 1) * 100) == 52),
        "Counting all 4+4 DM1 projection neurons instead of the main one on each side gives 50% "
        "(experiments/phase6/steering/results/glomerulus_map_630.csv).")


# ----------------------------------------------------------------- sensitivity
def sensitivity():
    t = pd.read_csv(EXP / "phase5/sensitivity/results/table.csv")
    w = t.pivot_table(index=["variation", "parameter", "seed"], columns="readout", values="value").reset_index()
    w["sugar_on"] = w.sugar_mn9 >= 5
    w["water_on"] = w.water_mn9 >= 5
    w["bitter_ok"] = (w.sugar_bitter_mn9 <= 0.5 * w.sugar_mn9) & (w.sugar_mn9 >= 5)
    v = w.groupby(["variation", "parameter"]).agg(sugar=("sugar_on", "all"), water=("water_on", "all"),
                                                  bitter=("bitter_ok", "all"), smn9=("sugar_mn9", "mean"),
                                                  wmn9=("water_mn9", "mean"), ns=("seed", "nunique")).reset_index()
    params = {"w_syn", "threshold_gap", "t_mbr", "tau", "t_rfc", "t_dly", "r_poi"}
    sett = v[v.parameter.isin(params)]
    jit = v[v.variation.str.startswith("jitter20%_draw")]
    base = v[v.variation == "baseline"].smn9.iloc[0]
    both = pd.concat([sett, jit])
    lo, hi = both.smn9.min() / base - 1, both.smn9.max() / base - 1
    src = "experiments/phase5/sensitivity/results/table.csv (per seed, 3 seeds x 30 trials)"
    wq = where(("page", r"all 28 setting changes"), ("docs/phase5-sensitivity.md", r"holds in all 28 setting changes and all 15"))
    add("Sensitivity: sugar holds in 28/28 setting changes and 15/15 jitter patterns",
        wq, "28/28 and 15/15", f"{int(sett.sugar.sum())}/{len(sett)} and {int(jit.sugar.sum())}/{len(jit)}",
        src, ok(sett.sugar.sum() == 28 and len(sett) == 28 and jit.sugar.sum() == 15 and len(jit) == 15),
        "Rule: MN9 >= 5 Hz in every one of the 3 seeds.")
    add("Sensitivity: sugar response size changes -47% to +19%", wq, "-47% to +19%",
        f"{pct(lo)} ({both.loc[both.smn9.idxmin(), 'variation']}) to {pct(hi)} "
        f"({both.loc[both.smn9.idxmax(), 'variation']}); baseline {base:.2f} Hz", src,
        ok(round(lo * 100) == -47 and round(hi * 100) == 19))
    wflip_s = sett[~sett.water].variation.tolist()
    wflip_j = jit[~jit.water].variation.tolist()
    add("Sensitivity: water flips in 3 of 28 setting changes and 1 of 15 jitter patterns",
        where(("page", r"Water switches MN9 off in 3 of the 28"), ("docs/phase5-sensitivity.md", r"flips\*\* in 3 of 28")),
        "3/28 and 1/15", f"{len(wflip_s)}/28 {wflip_s} and {len(wflip_j)}/15 {wflip_j}", src,
        ok(len(wflip_s) == 3 and len(wflip_j) == 1))
    add("Sensitivity: bitter still suppresses sugar everywhere", wq, "holds everywhere",
        f"holds in {int(sett.bitter.sum())}/28 setting changes and {int(jit.bitter.sum())}/15 jitter patterns; "
        f"worst sugar+bitter / sugar = {(w.sugar_bitter_mn9 / w.sugar_mn9).max() * 100:.1f}%", src,
        ok(sett.bitter.all() and jit.bitter.all()))
    j1 = w[w.variation == "jitter20%_draw1"].sort_values("seed").water_mn9.tolist()
    add("[extra] Sensitivity doc: water, jitter pattern 1 = 5.4 / 4.8 / 5.0 Hz, 1 of 3 seeds holding",
        where(("docs/phase5-sensitivity.md", r"seeds: 5\.4, 4\.8, 5\.0")), "5.4, 4.8, 5.0 Hz; 1 of 3 hold",
        f"{', '.join(f'{x:.3f}' for x in j1)} Hz; {sum(x >= 5 for x in j1)} of 3 hold", src,
        ok([round(x, 1) for x in j1] == [5.4, 4.8, 5.0] and sum(x >= 5 for x in j1) == 1),
        "The seed shown as '5.0' is just under the 5 Hz cut-off, so the table is right but reads "
        "as 2 of 3 at first glance. Suggested: show two decimals (e.g. 4.97).")


# ----------------------------------------------------------------- runaway
def runaway(p3):
    tr = pd.read_csv(EXP / "phase7_signs/results/trials.csv")
    cnt = lambda cfg, cond: (int(tr[(tr.config == cfg) & (tr.condition == cond)].runaway.sum()),
                             int(((tr.config == cfg) & (tr.condition == cond)).sum()))
    dm = {c: (cnt("none", c), cnt("al_ln_literature", c)) for c in ("dm1_both_150Hz", "dm1_left_150Hz", "dm1_right_150Hz")}
    b = dm["dm1_both_150Hz"]
    add("DM1 smell: 90/90 runaway trials on the published model vs 0/90 with al_ln_literature",
        where(("page", r"Runaway trials out of 90"), ("docs/phase7-neurotransmitter-audit.md", r"DM1 smell input\s*$|150 Hz \*\*0 of 90")),
        "90/90 vs 0/90",
        "; ".join(f"{c}: {v[0][0]}/{v[0][1]} vs {v[1][0]}/{v[1][1]}" for c, v in dm.items()),
        "experiments/phase7_signs/results/trials.csv", ok(b[0] == (90, 90) and b[1] == (0, 90)))
    ir, ir_fix = cnt("none", "ir94e_200Hz"), cnt("al_ln_literature", "ir94e_200Hz")
    add("Ir94e 200 Hz: 10/90 runaway trials on the published model (0/90 with the fix)",
        where(("docs/phase7-neurotransmitter-audit.md", r"baseline 10 of 90")), "10/90 (fix 0/90)",
        f"{ir[0]}/{ir[1]} (fix {ir_fix[0]}/{ir_fix[1]})", "experiments/phase7_signs/results/trials.csv",
        ok(ir == (10, 90) and ir_fix == (0, 90)))
    # how many neurons "fire non-stop"
    rep = pd.read_csv(EXP / "phase6/runaway/results/reproduce_trials.csv")
    ra = rep[rep.runaway]
    sp = p3["sugar200_ir94e200"]["spikes"]
    tot = p3["sugar200_ir94e200"]["tot"]
    p3n = [int(sp[sp.trial == t].flywire_id.nunique()) for t in np.where(tot > 50000)[0]]
    t7 = tr[(tr.config == "none") & tr.runaway]
    add("Runaway: about 8,300 neurons fire non-stop",
        where(("page", r"about 8,300 neurons"), ("docs/phase6-runaway-activity.md", r"about 8,300 neurons"),
              ("docs/phase6-runaway-activity.md", r"About 8,500 neurons take part")),
        "about 8,300",
        f"Phase 3's two runaway trials: {p3n} neurons fired. Phase 6's {len(ra)} runaway trials: "
        f"{int(ra.n_active.median()):,} fired (median; range {int(ra.n_active.min()):,}-{int(ra.n_active.max()):,}), "
        f"{int(ra.distinct_last_100ms.median()):,} still firing in the last 100 ms. Phase 7's {len(t7)} runaway "
        f"trials: {int(t7.n_active.median()):,} fired (median), {int(t7.distinct_last_100ms.median()):,} still firing at the end",
        "experiments/phase3/results/v630/sugar200_ir94e200_spikes.parquet; experiments/phase6/runaway/results/"
        "reproduce_trials.csv; experiments/phase7_signs/results/trials.csv",
        "AMBIGUOUS",
        "8,300 is the count from one Phase 3 trial (8,304). Depending on the trial set and on what "
        "'non-stop' means, the saved counts run from about 7,700 (still firing at the end) to about 8,500 "
        "(fired at all); the same doc's section 4b says 8,495. Suggested: 'about 8,000 neurons'.")
    # where it begins: the 6 traced runaways
    z = np.load(EXP / "phase6/runaway/results/main_neuron_stats.npz")
    lab = pd.read_parquet(ROOT / "data/cache/connectome_630_neurons.parquet",
                          columns=["root_id", "cell_class", "hemibrain_type", "cell_type"])
    ht = (lab.hemibrain_type.fillna(lab.cell_type).fillna("(" + lab.cell_class.fillna("no label") + ", untyped)")
          .astype(str).to_numpy())
    aln = (lab.cell_class == "ALLN").fillna(False).to_numpy(bool)
    eln = aln & lab.hemibrain_type.isin(["lLN1_b,lLN1_c", "lLN2T_a", "lLN2T_b", "lLN2T_c"]).fillna(False).to_numpy(bool)
    main = rep[rep.condition == "sugar200_ir94e200"]
    healthy = main[~main.runaway]
    fh = np.zeros(len(lab))
    for _, t in healthy.iterrows():
        fh[z[f"{t.seed}_{t.trial}_idx"]] += 1
    fh /= len(healthy)
    ann = pd.read_csv(ROOT / "data/flywire/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                      usecols=["cell_class", "hemibrain_type", "known_nt"], low_memory=False)
    k783 = (ann.cell_class == "ALLN") & ann.hemibrain_type.isin(["lLN1_b,lLN1_c", "lLN2T_a", "lLN2T_b", "lLN2T_c"])
    add("[extra] Number of excitatory local neurons behind the runaway: 38 (Phase 6) vs 'about 44' (Phase 7)",
        where(("docs/phase6-runaway-activity.md", r"at 38 \"excitatory local neurons\""),
              ("docs/phase7-neurotransmitter-audit.md", r"about 44 antennal-lobe local neurons")),
        "38 / about 44",
        f"{int(eln.sum())} in the snapshot-630 brain the model runs on; {int(k783.sum())} of these types in FlyWire's "
        f"newer (783) annotation, {int((k783 & (ann.known_nt == 'acetylcholine')).sum())} of them with a literature "
        "transmitter (acetylcholine)",
        "data/cache/connectome_630_neurons.parquet; data/flywire/Supplemental_file1_neuron_annotations.tsv",
        "AMBIGUOUS",
        "Both numbers are right for different lists (the Phase 6 doc explains this in section 4c; the Phase 7 "
        "short version does not). Suggested for Phase 7: 'the 38 excitatory local neurons (44 in FlyWire's newer "
        "annotation)'.")
    per = []
    for _, t in main[main.runaway].iterrows():
        idx, first = z[f"{t.seed}_{t.trial}_idx"], z[f"{t.seed}_{t.trial}_first"] * 0.1
        rec = fh[idx] < 0.05                    # "recruited": fires in < 5% of healthy trials
        per.append((idx[rec], first[rec], float(t.onset_ms)))
    # keep neurons recruited in at least half of the runaways (the cut the doc's own ranking uses);
    # otherwise a rarely-active neuron that fires by chance early in the trial counts as "first"
    seen = pd.Series(np.concatenate([p[0] for p in per])).value_counts()
    common = seen[seen >= len(per) / 2].index.to_numpy()
    firsts = []
    for ids, fs, onset in per:
        o_all = np.argsort(fs, kind="stable")
        k = np.isin(ids, common) & (fs >= onset - 50)      # the ignition window: last 50 ms before onset, and after
        o = np.argsort(fs[k], kind="stable")
        ids2, fs2 = ids[k][o], fs[k][o]
        firsts.append(dict(first_type=ht[ids2[0]], first_is_eln=bool(eln[ids2[0]]), first_is_aln=bool(aln[ids2[0]]),
                           lead_ms=fs2[0] - onset, eln_in_first10=int(eln[ids2[:10]].sum()),
                           aln_in_first10=int(aln[ids2[:10]].sum()), any_lead_ms=fs[o_all][0] - onset))
    f = pd.DataFrame(firsts)
    rank = pd.read_csv(EXP / "phase6/runaway/results/onset_ranking.csv")
    top10 = rank.head(10)
    top10_eln = int(top10.root_id.isin(lab.root_id[eln]).sum())
    top10_types = ", ".join(top10.hemibrain_type.fillna(top10.cell_type).fillna("?").astype(str).head(6))
    add("Runaway: every runaway begins at the 38 excitatory local neurons (eLNs)",
        where(("docs/phase6-runaway-activity.md", r"at 38 \"excitatory local neurons\""),
              ("page", r"Every case starts at the same few dozen")),
        "every runaway begins at the 38 eLNs",
        f"{int(eln.sum())} eLNs in snapshot 630. In the {len(f)} traced runaways, the first neuron to fire in the "
        f"50 ms before onset, among the {len(common)} neurons recruited in at least half of them, was an antennal-lobe local neuron "
        f"{int(f.first_is_aln.sum())}/{len(f)} times and one of the 38 eLNs {int(f.first_is_eln.sum())}/{len(f)} times "
        f"(types: {', '.join(f.first_type)}; {f.lead_ms.min():.0f} to {f.lead_ms.max():.0f} ms before onset); eLNs among "
        f"the first 10: {f.eln_in_first10.tolist()}, antennal-lobe local neurons among the first 10: "
        f"{f.aln_in_first10.tolist()}. The doc's own ranking (onset_ranking.csv) starts {top10_types}; "
        f"{top10_eln} of its first 10 are eLNs.",
        "experiments/phase6/runaway/results/main_neuron_stats.npz + reproduce_trials.csv (+ onset_ranking.csv); "
        "data/cache/connectome_630_neurons.parquet (types)",
        "AMBIGUOUS",
        "Only the 6 taste-triggered runaways were traced. The first neurons are antennal-lobe local "
        "neurons, but not only the 38 eLNs (v2LN30 and lLN2X03 are among the very first, as the doc's own "
        "section 4a says). Phase 7 later found strong DM1 smell still runs away in 90/90 trials when only "
        "the eLNs are fixed (eln_electrical), through other local neurons. Suggested: 'every traced "
        "runaway begins among antennal-lobe local neurons; silencing the 38 eLNs stopped the ones started "
        "by taste input and by a brief smell pulse'.")


# ----------------------------------------------------------------- steering
def steering():
    gm = pd.read_csv(EXP / "phase6/steering/results/glomerulus_map_630.csv")
    mirror = (gm.Lorn_to_Lpn > gm.Lorn_to_Rpn) & (gm.Rorn_to_Rpn > gm.Rorn_to_Lpn)
    add("Steering: 19 of 51 glomeruli do not mirror at the first synapse",
        where(("page", r"19 of 51 glomeruli"), ("docs/phase6-steering.md", r"19 of 51 glomeruli have this problem")),
        "19 of 51", f"{int((~mirror).sum())} of {len(gm)} (DM1 among them: {not bool(mirror[gm.glomerulus == 'DM1'].iloc[0])})",
        "experiments/phase6/steering/results/glomerulus_map_630.csv (per-glomerulus ORN->PN counts)",
        ok(int((~mirror).sum()) == 19 and len(gm) == 51),
        "Recomputed from the saved synapse counts (rule: left-only smell favours the left PNs AND "
        "right-only smell favours the right PNs); the counts themselves were not re-derived here, "
        "except DM1's (row above).")
    comp = pd.read_csv(ROOT / "data/reference/2023_03_23_completeness_630_final.csv", usecols=[0])
    pos = {int(r): i for i, r in enumerate(comp.iloc[:, 0].to_numpy(np.int64))}
    S = EXP / "phase6/steering/results/sim"

    def rates(var, glom, side):
        return np.mean([np.load(S / f"{var}_{glom}_{side}_s{sd}.npz")["rates"] for sd in (0, 1, 2)], axis=0)
    L, R = rates("al_ln", "DA1", "left"), rates("al_ln", "DA1", "right")
    iL, iR = pos[DNA02["L"]], pos[DNA02["R"]]
    per_seed = [(np.load(S / f"al_ln_DA1_{s}_s{sd}.npz")["rates"][iL], np.load(S / f"al_ln_DA1_{s}_s{sd}.npz")["rates"][iR])
                for s in ("left", "right") for sd in (0, 1, 2)]
    every = all(a > b for a, b in per_seed[:3]) and all(b > a for a, b in per_seed[3:])
    add("DA1 with the fix: left-only smell drives left DNa02 22.7 vs 1.0 Hz; right-only drives right 15.7 vs 0.1 Hz",
        where(("page", r"22\.7 vs 1\.0 Hz"), ("docs/phase6-steering.md", r"22\.7 Hz vs 1\.0 Hz")),
        "22.7 vs 1.0; 15.7 vs 0.1 (every seed)",
        f"left smell: L {L[iL]:.2f} vs R {L[iR]:.2f} Hz; right smell: R {R[iR]:.2f} vs L {R[iL]:.2f} Hz; "
        f"correct side wins in every seed: {every}",
        "experiments/phase6/steering/results/sim/al_ln_DA1_{left,right}_s{0,1,2}.npz (rates)",
        ok(round(L[iL], 1) == 22.7 and round(L[iR], 1) == 1.0 and round(R[iR], 1) == 15.7
           and round(R[iL], 1) == 0.1 and every))
    res = []
    for glom in ("DM1", "DA1", "DM4", "DM2", "VA2", "DA2"):
        l, r = rates("al_ln", glom, "left"), rates("al_ln", glom, "right")
        res.append((glom, bool((l[iL] - l[iR]) > 0 > (r[iL] - r[iR]))))
    add("[extra] Only one smell channel (DA1) mirrors properly (of the 6 simulated, with the fix)",
        where(("page", r"Only one smell channel mirrors properly")), "only DA1",
        ", ".join(f"{g} {'mirrors' if m else 'no'}" for g, m in res),
        "experiments/phase6/steering/results/sim/al_ln_*.npz", ok([g for g, m in res if m] == ["DA1"]))


# ----------------------------------------------------------------- learning
def learn_table(csv):
    d = pd.read_csv(csv)
    g = d.groupby(["condition", "seed", "mbon_type", "odor", "phase"])["drive_mV"].mean().unstack("phase")
    g = g[g["pre"] > 0]
    g["change"] = g["post"] / g["pre"] - 1.0
    return g.reset_index()


def learn_stats(g, cond, readout):
    cs = "B" if cond.endswith("_recip") else "A"
    x = g[(g.condition == cond) & (g.mbon_type == readout)]
    ctl = g[(g.condition == "no_training") & (g.mbon_type == readout)]
    p = x[x.odor == cs].set_index("seed").change
    m = x[x.odor != cs].set_index("seed").change
    cp = ctl[ctl.odor == cs].set_index("seed").change
    cm = ctl[ctl.odor != cs].set_index("seed").change
    net_p, net_m = (p - cp).dropna(), (m - cm).dropna()
    return dict(raw_p=p.mean(), raw_m=m.mean(), net_p=net_p.mean(), net_m=net_m.mean(),
                n=len(net_p), n_learn=int(((net_p - net_m) < 0).sum()), n_learn_raw=int(((p - m) < 0).sum()))


def learning():
    src = "experiments/phase8/results/cond_circuit_modulatory.csv (per seed, before/after drive)"
    g = learn_table(EXP / "phase8/results/cond_circuit_modulatory.csv")
    L = "docs/phase8-learning.md"
    spec = [("aversive_paired", "MBON11", "paired, odor A vs odor B, 5 of 5 flies", (-91, -9), (("page", r"91% less"), (L, r"91% less input"))),
            ("aversive_paired_recip", "MBON11", "odors swapped", (-89, -6), ((L, r"-89% vs -6%"),)),
            ("aversive_unpaired", "MBON11", "unpaired", (0.2, None), ((L, r"separate times: \+0\.2%"),)),
            ("odor_only", "MBON11", "odor alone", (0.2, None), ((L, r"Odor alone: \+0\.2%"),)),
            ("dan_only", "MBON11", "dopamine alone", (0.0, None), ((L, r"Dopamine alone: 0\.0%"),)),
            ("appetitive_paired", "MBON01", "reward (PAM-g5 + PAM-b'2a)", (-78, -8), ((L, r"by 78%"),)),
            ("alpha1_paired", "MBON07", "PAM-alpha1", (-94, -12), ((L, r"-94% vs -12%"),)),
            ("alpha2_short", "MBON18", "alpha2, 1 s pairing", (-10, None), ((L, r"did little \(-10%\)"),)),
            ("alpha2_long", "MBON18", "alpha2, 60 s pairing", (-94, None), ((L, r"did a lot \(-94%\)"),)),
            ("aversive_backward", "MBON11", "backward (dopamine first)", (-9, None), ((L, r"small one \(-9%\)"), ("page", r"small change \(.9%\)")))]
    for cond, ro, label, (qp, qm), locs in spec:
        s = learn_stats(g, cond, ro)
        dec = 1 if qm is None and abs(qp) < 1 else 0
        good = round(s["net_p"] * 100, dec) == qp and (qm is None or round(s["net_m"] * 100) == qm)
        rec = f"trained odor {s['net_p'] * 100:+.2f}%"
        if qm is not None:
            rec += f", other odor {s['net_m'] * 100:+.2f}%; learned in {s['n_learn']} of {s['n']} flies"
        q = ("0.0%" if qp == 0 else f"{qp:+g}%") + (f" vs {qm:+g}%" if qm is not None else "")
        if cond == "aversive_paired":
            good = good and s["n_learn"] == 5 and s["n"] == 5
            q += ", 5 of 5 flies"
        add(f"Learning (circuit): {label}", where(*locs), q, rec, src, ok(good),
            "Changes are net of the no-training control, as in the doc (raw, not netted: "
            f"{s['raw_p'] * 100:+.1f}% / {s['raw_m'] * 100:+.1f}%). Read-out {ro}.")
    cal = json.loads((EXP / "phase8/results/calibration.json").read_text(encoding="utf-8"))
    add("Learning: Hige et al. 2015 measured 90% less in real flies",
        where(("page", r"Real flies show 90% less"), (L, r"measured 90% less input")), "90%",
        f"literature value, not a saved result; the model's learning speed was fitted to a "
        f"{cal['target_drive_drop_gamma1pedc'] * 100:.0f}% drop on seeds {cal['seeds'][0]}-{cal['seeds'][-1]}",
        "none for the literature value; experiments/phase8/results/calibration.json for the fit target",
        "NO-SOURCE",
        "Not checkable from saved files. Also important: the learning speed was CALIBRATED so that "
        "Hige's protocol gives 90% (docs/phase8-learning.md 2.3, results/calibration.json), so -91% vs "
        "90% is agreement by construction, not an independent prediction. The page does not say so.")
    add("Learning (page): the neuron that lost 91% is the 'avoid' output neuron",
        where(("page", r"the \"avoid\" output neuron got about")), "'avoid' output neuron",
        "the read-out is MBON-g1pedc>a/b (MBON11), which the learning doc calls the 'approach' output neuron",
        "docs/phase8-learning.md (line with 'approach' output neuron MBON-g1pedc); experiments/phase8/analyze_phase8.py APPROACH = MBON11, MBON12",
        "MISMATCH",
        "A label error, not a number error. The 'avoid' neuron is MBON-g5b'2a, the reward read-out. "
        "Suggested page wording: 'Afterwards the \"approach\" output neuron got about 91% less input...'")
    gb = learn_table(EXP / "phase8/results/cond_brain_alln_modulatory.csv")
    s = learn_stats(gb, "appetitive_paired", "MBON01")
    add("Learning (whole brain, al_ln_literature): reward -98% vs -4%, 3 of 3 flies",
        where(("docs/phase8-learning.md", r"lost 98% of odor A's input and 4%")), "-98% vs -4%, 3 of 3",
        f"raw {s['raw_p'] * 100:+.2f}% vs {s['raw_m'] * 100:+.2f}%; net of no-training {s['net_p'] * 100:+.2f}% vs "
        f"{s['net_m'] * 100:+.2f}%; learned in {s['n_learn_raw']} of {s['n']} flies",
        "experiments/phase8/results/cond_brain_alln_modulatory.csv",
        ok(abs(s["raw_p"] * 100 + 98) < 1 and round(s["raw_m"] * 100) == -4 and s["n_learn_raw"] == 3),
        "Matches the RAW changes (98.5% cut to 98; the doc's section 5 says 98.5%). The circuit numbers "
        "above are net of the no-training control; netted the same way this reads -97.5% vs -4.6%. Within "
        "a point either way, but the doc mixes the two measures.")
    ga = learn_table(EXP / "phase8_aversive/results/cond_da_5ht_literature.csv")
    nt = ga[(ga.condition == "no_training") & (ga.mbon_type == "MBON11")]
    pa = ga[ga.condition.isin(["aversive_paired", "aversive_paired_recip"]) & (ga.mbon_type == "MBON11")].copy()
    pa["cs"] = np.where(pa.condition.str.endswith("_recip"), pa.odor == "B", pa.odor == "A")
    other_means = pa[~pa.cs].groupby("condition").change.mean()
    pr = pa.pivot_table(index=["condition", "seed"], columns="cs", values="change")
    n_pair, n_pair_ok = len(pr), int((pr[True] < pr[False]).sum())
    add("Whole-brain punishment (+da_5ht_literature): test smells alone lower the read-out by about 39%",
        where(("page", r"lower the read-out by about 39%"), ("docs/phase7-neuromodulators.md", r"by about 39% on average")),
        "about 39% (3% to 76%)",
        f"no training, MBON11: mean {nt.change.mean() * 100:+.1f}% over {len(nt)} fly x odor pairs "
        f"(range {nt.change.max() * 100:+.0f}% to {nt.change.min() * 100:+.0f}%); paired runs: trained odor "
        f"{pa[pa.cs].change.mean() * 100:+.0f}%, other odor {other_means.max() * 100:+.0f}% and "
        f"{other_means.min() * 100:+.0f}% on average (single flies {pa[~pa.cs].change.min() * 100:+.0f}% to "
        f"{pa[~pa.cs].change.max() * 100:+.0f}%)",
        "experiments/phase8_aversive/results/cond_da_5ht_literature.csv",
        ok(round(-nt.change.mean() * 100) == 39 and round(-nt.change.max() * 100) == 3 and round(-nt.change.min() * 100) == 76),
        "The page's 'gap between about -100% and about -40%' matches the paired-run averages. Single flies "
        "vary a lot: in one fly the untrained odor fell 77%, so the gap is not clear in every fly "
        "(docs/phase7-neuromodulators.md says 5 of 6 paired runs count as clearly learned).")
    add("[extra] Learning doc short version: whole-brain punishment learning 'cannot be seen'",
        where(("docs/phase8-learning.md", r"Punishment learning cannot be seen")), "cannot be seen (no fix for it)",
        f"superseded: with +da_5ht_literature the trained odor dropped more than the other odor in "
        f"{n_pair_ok} of {n_pair} paired runs (docs/phase7-neuromodulators.md)",
        "docs/phase7-neuromodulators.md; experiments/phase8_aversive/results/", "AMBIGUOUS",
        "Not a wrong number: the Phase 8 doc was written before the Phase 7.5 fix and never mentions it. "
        "Suggested: add one line to its short version pointing to docs/phase7-neuromodulators.md.")


# ----------------------------------------------------------------- body (DA1 demo) and video
def body():
    R = EXP / "phase9_da1/results"
    t = pd.read_csv(R / "da1_trials.csv")
    one = t[t.condition == "one_dna02"].set_index(["layout", "rep"])
    ctl_o = t[t.condition == "one_orns_off"].set_index(["layout", "rep"]).turn_toward_intact_1s_deg
    ctl_d = t[t.condition == "one_dna02_off"].set_index(["layout", "rep"]).turn_toward_intact_1s_deg
    v = one.turn_toward_intact_1s_deg
    diff_o, diff_d = (v - ctl_o).dropna(), (v - ctl_d).dropna()
    p_mw = stats.mannwhitneyu(v, ctl_o, alternative="two-sided").pvalue
    p_wx = stats.wilcoxon(diff_o).pvalue
    neg = one[v <= 0]
    add("One-antenna fly: turned further toward the smelling side than the same-seed silenced fly in 12 of 12; "
        "+31 deg vs 0 deg in the first second; p = 0.0006",
        where(("page", r"silenced fly of the same seed in 12 of 12"), ("docs/phase9-da1-demo.md", r"12 of 12 trials compared with the silenced")),
        "12 of 12; +31 vs 0 deg; p = 0.0006",
        f"paired (brain minus same layout+seed control): {int((diff_o > 0).sum())}/{len(diff_o)} vs DA1-smell-silenced, "
        f"{int((diff_d > 0).sum())}/{len(diff_d)} vs DNa02-silenced; mean {v.mean():+.2f} vs {ctl_o.mean():+.2f} deg; "
        f"Mann-Whitney p = {p_mw:.5f} (paired Wilcoxon p = {p_wx:.5f})",
        "experiments/phase9_da1/results/da1_trials.csv",
        ok(int((diff_o > 0).sum()) == 12 and round(v.mean()) == 31 and round(ctl_o.mean()) == 0 and round(p_mw, 4) == 0.0006))
    add("What '12 of 12' counts, vs turning toward the smelling side in absolute terms",
        where(("page", r"in 12 of 12 trials"), ("docs/phase9-da1-demo.md", r"11/12\*\* \(12/12 compared")),
        "12 of 12 (paired count)",
        f"absolute: {int((v > 0).sum())} of {len(v)} turned toward the smelling side; the one that did not: "
        f"{', '.join(f'{l} rep {r} ({x:+.1f} deg)' for (l, r), x in neg.turn_toward_intact_1s_deg.items())}. "
        "The silenced flies' 0 deg mean is exact by design: each seed's silenced fly drifts the same in every "
        f"layout ({t[t.condition == 'one_orns_off'].groupby('rep').heading_change_1s_deg.first().round(2).tolist()} "
        "deg for seeds 0-2, + = left), which counts as 'toward' in half the layouts and 'away' in the other half.",
        "experiments/phase9_da1/results/da1_trials.csv", "AMBIGUOUS",
        "The page and doc words are accurate ('than the silenced fly of the same seed'), but a reader can "
        "take '12 of 12' as 'turned toward the smell in 12 of 12'. In plain terms it is 11 of 12. The doc's "
        "table says so; the page does not. Suggested page wording: 'It turned toward the smelling side in "
        "11 of 12 trials, and further than the silenced fly of the same seed in all 12'.")
    a = t[t.condition == "dna02"]
    lat = a[a.source_angle_deg != 0]
    ctl = t[t.condition == "no_odor"]
    p_d = stats.mannwhitneyu(a.min_dist_mm, ctl.min_dist_mm, alternative="two-sided").pvalue
    add("Normal fly: turns left in 15 of 15; toward the source only 6 of 12; 4.1 vs 4.2 mm (p = 0.87)",
        where(("page", r"turned left in all 15 trials"), ("docs/phase9-da1-demo.md", r"\(15 of 15\), whether")),
        "15/15 left; 6/12 toward; 4.1 vs 4.2 mm, p = 0.87",
        f"{int((a.heading_change_1s_deg > 0).sum())}/{len(a)} left; {int((lat.turn_toward_source_1s_deg > 0).sum())}/"
        f"{len(lat)} toward; closest approach {a.min_dist_mm.mean():.3f} vs {ctl.min_dist_mm.mean():.3f} mm (no-odor "
        f"control), Mann-Whitney p = {p_d:.3f}",
        "experiments/phase9_da1/results/da1_trials.csv",
        ok(int((a.heading_change_1s_deg > 0).sum()) == 15 and len(a) == 15 and int((lat.turn_toward_source_1s_deg > 0).sum()) == 6
           and len(lat) == 12 and round(a.min_dist_mm.mean(), 1) == 4.1 and round(ctl.min_dist_mm.mean(), 1) == 4.2
           and round(p_d, 2) == 0.87))
    dp = t[(t.condition == "dnpe002") & (t.source_angle_deg != 0)]
    add("Normal fly, DNpe002 read-out: toward the source 7 of 12",
        where(("docs/phase9-da1-demo.md", r"also fails \(7 of 12\)")), "7 of 12",
        f"{int((dp.turn_toward_source_1s_deg > 0).sum())} of {len(dp)}", "experiments/phase9_da1/results/da1_trials.csv",
        ok(int((dp.turn_toward_source_1s_deg > 0).sum()) == 7 and len(dp) == 12))
    h = t[t.condition == "hand_rule"]
    add("Hand-written rule reaches the source 5 of 5",
        where(("docs/phase9-da1-demo.md", r"reached the cVA source 5 of 5")), "5 of 5",
        f"{int(h.reached.astype(str).str.lower().eq('true').sum())} of {len(h)} (closest {h.min_dist_mm.min():.2f}-{h.min_dist_mm.max():.2f} mm)",
        "experiments/phase9_da1/results/da1_trials.csv", ok(int(h.reached.astype(str).str.lower().eq("true").sum()) == 5 and len(h) == 5))
    add("[extra] Video doc: the four clips are from the 142 trials of the DA1 demo",
        where(("docs/phase9-video.md", r"142 trials")), "142", f"{len(t)}",
        "experiments/phase9_da1/results/da1_trials.csv", ok(len(t) == 142))
    # video
    W = pd.read_csv(R / "da1_windows.csv")
    clips = {"a": ("one_dna02", "B_Lonly+90", 0), "b": ("one_dna02_off", "B_Lonly+90", 0),
             "c": ("dna02", "A-45", 0), "d": ("hand_rule", "A-45", 0)}
    worst, nwin, ncols = 0.0, [], []
    for k, (c, lay, rep) in clips.items():
        v2 = pd.read_csv(EXP / f"phase9_video/results/clip_{k}_windows.csv")
        s = W[(W.condition == c) & (W.layout == lay) & (W.rep == rep)].sort_values("window")
        cols = [x for x in s.columns if x in v2.columns and x not in ("condition", "layout", "rep", "window")]
        m = s.merge(v2, on="window", suffixes=("_s", "_v"))
        nwin.append((len(s), len(v2)))
        ncols.append(len(cols))
        for col in cols:
            dd = (m[col + "_s"].astype(float) - m[col + "_v"].astype(float)).abs().max()
            if pd.notna(dd):
                worst = max(worst, float(dd))
    add("Video: the re-run paths match the saved trials to within 1.4e-14",
        where(("docs/phase9-video.md", r"any column is 1\.4e-14"), ("page", r"within rounding error")),
        "within 1.4e-14", f"largest difference in any of the {min(ncols)}-{max(ncols)} shared columns: {worst:.2e}; "
        f"windows saved/re-run {nwin}",
        "experiments/phase9_da1/results/da1_windows.csv vs experiments/phase9_video/results/clip_*_windows.csv",
        ok(worst <= 1.5e-14 and all(a_ == b_ for a_, b_ in nwin) and min(ncols) >= 10),
        "The two saved text files agree exactly; the 1.4e-14 in results/path_check.csv is the gap between "
        "the re-run's in-memory numbers and the saved text (rounding when writing the file).")
    dd = diff_d.sort_values(ascending=False)
    rank = list(dd.index).index(("B_Lonly+90", 0)) + 1
    add("Video: clip A is the second-strongest of the 12 one-antenna trials (63 deg more than the silenced fly; range 8-75)",
        where(("page", r"second-strongest of the 12"), ("docs/phase9-video.md", r"second-strongest of the 12")),
        "2nd of 12; 63 deg; range 8-75 deg",
        f"rank {rank} of {len(dd)}; clip A {dd[('B_Lonly+90', 0)]:.1f} deg; range {dd.min():.1f}-{dd.max():.1f} deg",
        "experiments/phase9_da1/results/da1_trials.csv (one_dna02 minus one_dna02_off, same layout and seed)",
        ok(rank == 2 and round(dd[("B_Lonly+90", 0)]) == 63 and round(dd.min()) == 8 and round(dd.max()) == 75))


# ----------------------------------------------------------------- page headline counts
def headline():
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout

    def counts(rev):
        n_commits = int(git("rev-list", "--count", rev).strip())
        n_lines = sum(int(ln.rsplit(":", 1)[1]) for ln in git("grep", "-c", "", rev, "--", "*.py").splitlines() if ln)
        n_docs = sum(1 for p in git("ls-tree", "--name-only", rev, "docs/").splitlines() if p.endswith(".md"))
        return n_lines, n_commits, n_docs
    page_rev = "9bcdac4"      # the commit the page describes (its video is from this commit)
    at_page, at_head = counts(page_rev), counts("HEAD")
    add("[extra] Page: 28,101 lines of Python, 26 commits, 24 plain-English write-ups",
        where(("page", r"lines of Python, 26 commits")), "28,101 / 26 / 24",
        f"at commit {page_rev} (what the page describes): {at_page[0]:,} / {at_page[1]} / {at_page[2]}; "
        f"at HEAD now: {at_head[0]:,} / {at_head[1]} / {at_head[2]}",
        "git grep -c, git rev-list, git ls-tree", ok(at_page == (28101, 26, 24)),
        "True when the page was made; the counts grow with every commit (other lanes' work has "
        "already been committed since), so the page needs refreshing whenever it is republished.")
    add("[extra] Page: 211 automated tests pass", where(("page", r"211 automated tests")), "211 pass",
        "not recomputable from saved files", "none (no saved full-suite pytest log)", "NO-SOURCE",
        "Regenerate with: .venv\\Scripts\\python.exe -m pytest -q (some tests load the whole brain, "
        "so not run here). A static count finds 168 test functions; parametrised cases add more.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    p3 = phase3()
    fast_engine(p3)
    phase2()
    phase4()
    silencing()
    competition()
    cb0219_and_dm1()
    sensitivity()
    runaway(p3)
    steering()
    learning()
    body()
    headline()
    df = pd.DataFrame(ROWS, columns=["claim", "where quoted", "quoted value", "recomputed value",
                                     "source file", "status", "note"])
    df.to_csv(OUT / "audit.csv", index=False, encoding="utf-8")
    extra = df.claim.str.startswith("[extra]")
    print("rows:", len(df), "| requested:", int((~extra).sum()), "| extra:", int(extra.sum()))
    print("all:      ", df.status.value_counts().to_dict())
    print("requested:", df[~extra].status.value_counts().to_dict())
    print("extra:    ", df[extra].status.value_counts().to_dict())
    for _, r in df[df.status != "MATCH"].iterrows():
        print(f"- {r.status}: {r.claim[:90]} | quoted {str(r['quoted value'])[:40]} | got {str(r['recomputed value'])[:120]}")
    nf = df[df["where quoted"].str.contains(r"\?")]
    for _, r in nf.iterrows():
        print("LOCATION NOT FOUND:", r.claim[:60], "|", r["where quoted"])


if __name__ == "__main__":
    main()
