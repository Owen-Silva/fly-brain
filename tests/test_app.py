"""Phase 4: the explorer app's web API (FastAPI TestClient, stand-in engine).

These tests force the stand-in engine so they are fast and do not depend on
the whole-brain simulator. The tests marked "slow" use the real engine: the
Phase 4 checkpoint (sugar setup, app == direct FastBrain, MN9 67.6 Hz), the
sugar + bitter setup (MN9 47.7 Hz) and the DA1 steering setup on the
recommended fix (same rates as the saved Phase 6 run). Each builds one brain
at a time (the checkpoint builds a second, separate one on purpose).
"""
import json
import shutil
import threading
import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.engine_adapter as ea
from app import setups as st
from app.engine_adapter import (MN9_LEFT_ID as MN9_ID, SUGAR_GRN_IDS_630 as SUGAR_GRN_IDS,
                                EngineAdapter, EngineError, _normalise_result)
from app.main import create_app
from app.run_setup import compare, run_from_code, run_through_app

FAKE_IDS = [str(900000000000000000 + k) for k in range(60)]


@pytest.fixture(scope="module")
def adapter():
    return EngineAdapter(force_fake=True, fake_seconds_per_trial=0.0)


@pytest.fixture()
def client(adapter, tmp_path):
    return TestClient(create_app(adapter, setup_dir=tmp_path))


def wait_done(client, job_id, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/runs/{job_id}").json()
        if s["state"] in ("done", "failed"):
            return s
        time.sleep(0.02)
    raise AssertionError("run did not finish")


def run_params(**kw):
    p = {"excite": [str(i) for i in SUGAR_GRN_IDS], "silence": [], "watch": [str(MN9_ID)],
         "duration_ms": 50, "n_trials": 3, "seed": 7, "rate_hz": 150, "snapshot": "630"}
    p.update(kw)
    return p


def test_fake_engine_is_flagged_everywhere(client):
    s = client.get("/api/status").json()
    assert s["is_fake"] is True and s["engine"]["is_fake"] is True
    assert "NOT from the fly brain model" in s["banner"]
    assert "FLYBRAIN_APP_FAKE" in s["engine"]["reason"]
    r = client.post("/api/runs", json=run_params()).json()
    assert r["is_fake"] is True and r["banner"]
    wait_done(client, r["job_id"])
    res = client.get(f"/api/runs/{r['job_id']}/results").json()
    assert res["is_fake"] is True and res["engine"]["is_fake"] is True
    csv = client.get(f"/api/runs/{r['job_id']}/rates.csv").text
    assert csv.startswith("# WARNING: stand-in engine")


def test_page_and_assets_are_served(client):
    html = client.get("/").text
    assert 'id="banner"' in html and "/static/app.js" in html
    assert "cdn" not in html.lower()
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200


def test_search_by_type_name_and_id(client):
    r = client.get("/api/neurons/search", params={"q": "fake-mn9"}).json()
    assert r["total"] == 3 and r["results"][0]["cell_type"] == "FAKE-MN9"
    assert r["snapshot"] == "630"                          # the default snapshot
    assert client.get("/api/neurons/search", params={"q": "x", "snapshot": "999"}).status_code == 400
    r = client.get("/api/neurons/search", params={"q": "sugar_1"}).json()
    assert r["results"][0]["name"] == "sugar_1"          # exact name match ranks first
    r = client.get("/api/neurons/search", params={"q": str(MN9_ID)[:12]}).json()
    assert str(MN9_ID) in [n["root_id"] for n in r["results"]]
    assert all(isinstance(n["root_id"], str) for n in r["results"])  # ids stay text for JS
    assert client.get("/api/neurons/search", params={"q": ""}).json()["total"] == 0
    look = client.post("/api/neurons/lookup", json={"ids": [str(MN9_ID), "123"]}).json()["neurons"]
    assert look[0]["known"] is True and look[1]["known"] is False


def test_run_lifecycle(client):
    r = client.post("/api/runs", json=run_params())
    assert r.status_code == 202
    job = r.json()
    assert job["state"] in ("queued", "building", "running", "done")
    s = wait_done(client, job["job_id"])
    assert s["state"] == "done", s
    res = client.get(f"/api/runs/{job['job_id']}/results", params={"top": 10}).json()
    assert 0 < len(res["top"]) <= 10
    assert all(row["role"] != "stimulated" for row in res["top"])
    assert res["watch"][0]["root_id"] == str(MN9_ID)
    rates = [row["rate_hz"] for row in res["top"]]
    assert rates == sorted(rates, reverse=True)
    incl = client.get(f"/api/runs/{job['job_id']}/results",
                      params={"include_stimulated": True}).json()
    assert any(row["role"] == "stimulated" for row in incl["top"])
    sp = client.get(f"/api/runs/{job['job_id']}/spikes", params={"trial": 2}).json()
    assert sp["trial"] == 2 and sp["rows"][0]["role"] == "stimulated"
    assert all(0 <= t <= 50 for row in sp["rows"] for t in row["t_ms"])
    assert client.get(f"/api/runs/{job['job_id']}/spikes", params={"trial": 3}).status_code == 400
    assert client.get("/api/runs/nope").status_code == 404


def test_same_seed_same_result_and_seed_is_recorded(client):
    def rates(p):
        j = client.post("/api/runs", json=p).json()
        wait_done(client, j["job_id"])
        return j, client.get(f"/api/runs/{j['job_id']}/rates.csv").text

    _, a = rates(run_params(seed=11))
    _, b = rates(run_params(seed=11))
    _, c = rates(run_params(seed=12))
    assert a == b and a != c
    j, _ = rates(run_params(seed=None))
    assert isinstance(j["params"]["seed"], int) and j["seed_note"]


@pytest.mark.parametrize("bad, words", [
    ({"excite": []}, "at least one"),
    ({"silence": [str(SUGAR_GRN_IDS[0])]}, "both Stimulate and Silence"),
    ({"excite": ["123456"]}, "not in the snapshot 630 neuron table"),
    ({"excite": ["abc"]}, "not a FlyWire root id"),
    ({"duration_ms": 0}, "duration_ms"),
    ({"n_trials": 1000}, "n_trials"),
    ({"snapshot": "999"}, "snapshot must be one of"),
])
def test_bad_runs_are_refused_with_a_reason(client, bad, words):
    r = client.post("/api/runs", json=run_params(**bad))
    assert r.status_code == 400 and words in r.json()["detail"]


def test_engine_failure_is_reported_not_swallowed(adapter, tmp_path, monkeypatch):
    c = TestClient(create_app(adapter, setup_dir=tmp_path))

    def boom(*a, **k):
        raise EngineError("simulated crash")
    monkeypatch.setattr(adapter, "run", boom)
    j = c.post("/api/runs", json=run_params()).json()
    s = wait_done(c, j["job_id"])
    assert s["state"] == "failed" and "simulated crash" in s["error"]
    assert c.get(f"/api/runs/{j['job_id']}/results").status_code == 409


def test_setup_save_list_load_round_trip(client):
    body = {**run_params(seed=5), "name": "my_test", "title": "A test", "description": "notes"}
    r = client.post("/api/setups", json=body)
    assert r.status_code == 201
    saved = r.json()["setup"]
    assert saved["engine"]["name"] and saved["engine"]["code_hash"]
    assert client.post("/api/setups", json=body).status_code == 409
    assert client.post("/api/setups", params={"overwrite": True}, json=body).status_code == 201
    names = [s["name"] for s in client.get("/api/setups").json()["setups"]]
    assert names == ["my_test"]
    got = client.get("/api/setups/my_test").json()
    assert got["engine_matches"] is True and got["setup"]["snapshot"] == "630"
    for k in ("excite", "silence", "watch", "duration_ms", "n_trials", "seed", "rate_hz", "snapshot"):
        assert got["setup"][k] == st.validate_params(body)[k]
    assert client.post("/api/setups", json={**body, "seed": None}).status_code == 400
    assert client.get("/api/setups/..%2F..%2Fsecret").status_code in (400, 404)
    assert client.get("/api/setups/missing").status_code == 404


def test_loaded_setup_reruns_identically(client):
    body = {**run_params(seed=3), "name": "rerun"}
    client.post("/api/setups", json=body)
    s = client.get("/api/setups/rerun").json()["setup"]
    out = []
    for _ in range(2):
        j = client.post("/api/runs", json={k: s[k] for k in ("excite", "silence", "watch",
                                                             "duration_ms", "n_trials", "seed",
                                                             "rate_hz", "snapshot")}).json()
        wait_done(client, j["job_id"])
        out.append(client.get(f"/api/runs/{j['job_id']}/rates.csv").text)
    assert out[0] == out[1]


def test_ready_made_sugar_setup_and_code_vs_app(adapter):
    s = st.load_setup("sugar_grn_right")
    p = st.validate_params({**s, "duration_ms": 50, "n_trials": 2})
    assert len(p["excite"]) == 21 and str(MN9_ID) in p["watch"]
    assert p["snapshot"] == "630" and s["snapshot"] == "630"   # the paper's snapshot
    assert p["excite"] == [str(i) for i in SUGAR_GRN_IDS]      # exactly the notebook ids
    code = run_from_code(adapter, p)
    app_rates, summary = run_through_app(adapter, p)
    c = compare(code.rates_hz, app_rates)
    assert c["n_different"] == 0 and c["n_neurons"] > 0
    assert summary["is_fake"] is True


def test_normaliser_reads_reference_format_in_seconds():
    spikes = pd.DataFrame({"t_s": [0.010, 0.020, 0.015], "trial": [0, 0, 1],
                           "root_id": [5, 5, 6]})
    trials, rates, sd, notes = _normalise_result(
        {"spikes": spikes, "rates": pd.Series({5: 20.0, 6: 10.0}),
         "rate_sd": pd.Series({5: 20.0, 6: 10.0})}, n_trials=2, duration_ms=100)
    assert np.allclose(trials[0][5], [10.0, 20.0]) and np.allclose(trials[1][6], [15.0])
    assert rates == {5: 20.0, 6: 10.0} and sd[5] == 20.0
    with pytest.raises(EngineError, match="time unit"):
        _normalise_result({"spikes": spikes.assign(t_s=[10.0, 20.0, 15.0])}, 2, 100)
    trials, rates, sd, notes = _normalise_result({"spikes": [{7: [1.0, 2.0]}, {}]}, 2, 1000)
    assert rates == {7: 1.0} and sd[7] == 1.0 and notes  # population sd, rates computed by app


def test_no_engine_means_runs_refused_with_banner(monkeypatch, tmp_path):
    """If the simulator cannot be imported the app must NOT make results up."""
    import app.engine_adapter as ea
    monkeypatch.setattr(ea, "_import", lambda name: (None, f"sim/{name}.py failed to import (test)"))
    monkeypatch.setattr(ea, "_ANNOTATION_FILES", {s: tmp_path / "missing.tsv" for s in ea.SNAPSHOTS})
    none = EngineAdapter(force_fake=False)
    c = TestClient(create_app(none, setup_dir=tmp_path))
    s = c.get("/api/status").json()
    assert s["runs_enabled"] is False and s["is_fake"] is False
    assert "Runs are switched off" in s["banner"] and "fast_engine.py failed to import" in s["banner"]
    r = c.post("/api/runs", json=run_params())
    assert r.status_code == 503 and "switched off" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Model variants, per-group input rates and backward-compatible setups
# (added 2026-09-23). Stand-in engine: these check the app's plumbing, not biology.
# ---------------------------------------------------------------------------
FIX = {"fix": "al_ln_literature", "upgrades": []}
SUGAR = [str(i) for i in SUGAR_GRN_IDS]
BITTER = [str(i) for i in ea.BITTER_GRN_IDS_630]


def run_and_wait(client, p):
    r = client.post("/api/runs", json=p)
    assert r.status_code == 202, r.text
    j = r.json()
    return j, wait_done(client, j["job_id"])


def group_params(groups, **kw):
    p = {k: v for k, v in run_params(**kw).items() if k not in ("excite", "rate_hz")}
    p["stim_groups"] = groups
    return p


@pytest.fixture()
def fresh(tmp_path):
    """A client with its own stand-in adapter, so the brain cache starts empty."""
    return TestClient(create_app(EngineAdapter(force_fake=True, fake_seconds_per_trial=0.0),
                                 setup_dir=tmp_path))


def test_variant_is_run_recorded_and_reproducible(fresh):
    c = fresh
    j, s = run_and_wait(c, run_params(variant=FIX))
    assert s["state"] == "done" and s["params"]["variant"] == FIX
    res = c.get(f"/api/runs/{j['job_id']}/results").json()
    v = res["variant"]
    assert (v["fix"], v["upgrades"], v["label"]) == ("al_ln_literature", [], "Recommended neurotransmitter fix")
    assert set(v["code"]) == {"sim/fast_engine.py", "sim/sign_fixes.py"} and all(v["code"].values())
    csv = c.get(f"/api/runs/{j['job_id']}/rates.csv").text
    assert "fix=al_ln_literature" in csv and "sim/sign_fixes.py=" in csv
    j0, _ = run_and_wait(c, run_params())          # no variant given = the published model
    assert c.get(f"/api/runs/{j0['job_id']}/results").json()["variant"]["key"] == "published"
    rates = lambda job: c.app.state.jobs.get(job["job_id"]).result.rates_hz  # noqa: E731
    assert rates(j0) != rates(j)                   # the choice really reaches the engine
    j2, _ = run_and_wait(c, run_params(variant=FIX))
    assert rates(j2) == rates(j)                   # same model + seed -> identical
    up = {"fix": "none", "upgrades": ["adaptation", "delays"]}
    j3, s3 = run_and_wait(c, run_params(variant=up))
    v3 = c.get(f"/api/runs/{j3['job_id']}/results").json()["variant"]
    assert v3["upgrades"] == ["delays", "adaptation"] and "sim/realism.py" in v3["code"]


@pytest.mark.parametrize("variant, snapshot, words", [
    ({"fix": "bogus"}, "630", "unknown model"),
    ({"fix": "eln_electrical"}, "630", "unknown model"),       # exists in sim/, not offered
    ({"fix": "none", "upgrades": ["conductance"]}, "630", "not validated"),
    ({"fix": "al_ln_literature", "upgrades": ["adaptation"]}, "630", "never tested"),
    ({"fix": "none", "upgrades": ["celltype", "delays"]}, "630", "on their own"),
    ({"fix": "al_ln_literature"}, "783", "630 brain map only"),
    ({"fix": "none", "upgrades": ["delays"]}, "783", "630 brain map only"),
    ("al_ln_literature", "630", "must be an object"),
])
def test_models_not_offered_are_refused_with_a_reason(client, variant, snapshot, words):
    r = client.post("/api/runs", json=run_params(variant=variant, snapshot=snapshot))
    assert r.status_code == 400 and words in r.json()["detail"], r.text
    r = client.post("/api/setups", json={**run_params(variant=variant, snapshot=snapshot), "name": "x"})
    assert r.status_code == 400 and words in r.json()["detail"]


def test_model_panel_state_and_docs(fresh):
    c = fresh
    r = c.get("/api/models/state", params={"fix": "al_ln_literature"}).json()
    assert r["ok"] and r["label"] == "Recommended neurotransmitter fix" and r["problem"] is None
    assert r["options"]["up:adaptation"] == {"allowed": False, "why": r["options"]["up:adaptation"]["why"]}
    assert "never tested" in r["options"]["up:adaptation"]["why"]
    assert r["options"]["fix:none"]["allowed"] is True
    assert r["memory"]["in_memory"] is False and r["memory"]["error"] is None
    r = c.get("/api/models/state", params={"upgrades": "delays,adaptation"}).json()
    assert r["ok"] and r["key"] == "none+delays+adaptation"
    assert not r["options"]["up:celltype"]["allowed"] and not r["options"]["fix:al_ln_literature"]["allowed"]
    r = c.get("/api/models/state", params={"snapshot": "783"}).json()
    assert r["ok"] and all(not o["allowed"] for k, o in r["options"].items() if k != "fix:none")
    r = c.get("/api/models/state", params={"fix": "al_ln_literature", "upgrades": "delays"}).json()
    assert r["ok"] is False and "never tested" in r["problem"]
    models = c.get("/api/status").json()["models"]
    assert [o["id"] for o in models["fixes"]] == ["none", "al_ln_literature"]
    assert [o["id"] for o in models["upgrades"]] == ["delays", "adaptation", "celltype"]
    for o in models["fixes"] + models["upgrades"]:
        assert o["label"] and o["about"] and o["available"] is True
        d = c.get(f"/api/model-docs/{o['doc']}")
        assert d.status_code == 200 and len(d.text) > 200
    assert c.get("/api/model-docs/PLAN.md").status_code == 404


def test_at_most_two_brains_in_memory_least_recent_dropped(fresh):
    c = fresh
    ad = c.app.state.adapter
    for v in (None, FIX, {"fix": "none", "upgrades": ["adaptation"]}):
        assert run_and_wait(c, run_params(variant=v))[1]["state"] == "done"
    ms = ad.models_status()
    assert ea.MAX_BRAINS_IN_MEMORY == 2 and len(ms["in_memory"]) == 2
    assert [m["key"] for m in ms["in_memory"]] == ["none+adaptation", "al_ln_literature"]  # newest first
    assert "dropped 'Published model'" in ms["dropped"][-1]
    st_ = c.get("/api/models/state").json()        # the published model needs a rebuild now
    assert st_["memory"]["in_memory"] is False
    assert st_["memory"]["will_drop"].startswith("Recommended neurotransmitter fix")


def test_building_a_model_is_shown_while_it_happens(fresh, monkeypatch):
    c = fresh
    ad = c.app.state.adapter
    gate, real = threading.Event(), ad._build
    monkeypatch.setattr(ad, "_build", lambda snap, v: (gate.wait(10), real(snap, v))[1])
    j = c.post("/api/runs", json=run_params(variant=FIX)).json()
    t0 = time.time()
    while not c.get("/api/models/state", params={"fix": "al_ln_literature"}).json()["memory"]["building"]:
        assert time.time() - t0 < 10, "never reported as building"
        time.sleep(0.01)
    s = c.get(f"/api/runs/{j['job_id']}").json()
    assert s["state"] == "building"
    assert "Building the brain for the model 'Recommended neurotransmitter fix'" in s["message"]
    assert c.get("/api/status").json()["models"]["building"]["label"] == "Recommended neurotransmitter fix"
    gate.set()
    assert wait_done(c, j["job_id"])["state"] == "done"
    assert c.get("/api/status").json()["models"]["building"] is None


def test_model_that_fails_to_build_is_reported_never_replaced(fresh, monkeypatch):
    c = fresh
    ad = c.app.state.adapter
    real = ad._build

    def broken(snap, v):
        if v["fix"] == "al_ln_literature":
            raise MemoryError("not enough memory (test)")
        return real(snap, v)
    monkeypatch.setattr(ad, "_build", broken)
    j, s = run_and_wait(c, run_params(variant=FIX))
    assert s["state"] == "failed"
    assert "Recommended neurotransmitter fix" in s["error"] and "not enough memory (test)" in s["error"]
    assert "Nothing was run in its place" in s["error"]
    assert c.get(f"/api/runs/{j['job_id']}/results").status_code == 409
    status = c.get("/api/status").json()
    assert "could not be built" in status["banner"] and "not enough memory (test)" in status["banner"]
    ms = c.get("/api/models/state", params={"fix": "al_ln_literature"}).json()
    assert "not enough memory (test)" in ms["memory"]["error"]
    assert ms["models"]["in_memory"] == []          # nothing was built in its place
    assert run_and_wait(c, run_params())[1]["state"] == "done"   # the published model still runs


def test_model_whose_code_cannot_load_is_refused_visibly(fresh):
    c = fresh
    c.app.state.adapter.option_problems["al_ln_literature"] = \
        "sim/sign_fixes.py exists but failed to import: SyntaxError (test)"
    r = c.post("/api/runs", json=run_params(variant=FIX))
    assert r.status_code == 400 and "failed to import" in r.json()["detail"]
    assert "Nothing was run in its place" in r.json()["detail"]
    fixes = {o["id"]: o for o in c.get("/api/status").json()["models"]["fixes"]}
    assert fixes["al_ln_literature"]["available"] is False and "failed to import" in fixes["al_ln_literature"]["problem"]
    assert "failed to import" in c.get("/api/models/state", params={"fix": "al_ln_literature"}).json()["problem"]


def test_each_group_gets_its_own_rate(fresh, monkeypatch):
    c = fresh
    seen, orig = [], ea.FakeEngine.run

    def spy(self, excite, silence, duration_ms, n_trials, seed, rate_hz, progress=None):
        seen.append((excite, rate_hz))
        return orig(self, excite, silence, duration_ms, n_trials, seed, rate_hz, progress)
    monkeypatch.setattr(ea.FakeEngine, "run", spy)
    p = group_params([{"name": "Sugar", "rate_hz": 100, "ids": SUGAR},
                      {"name": "Bitter", "rate_hz": 40, "ids": BITTER}], duration_ms=2000, n_trials=5)
    j, s = run_and_wait(c, p)
    assert s["state"] == "done"
    excite, rate = seen[-1]
    assert isinstance(excite, dict) and rate is None
    assert list(excite) == [int(i) for i in SUGAR + BITTER]          # group order kept
    assert {excite[int(i)] for i in SUGAR} == {100.0} and {excite[int(i)] for i in BITTER} == {40.0}
    res = c.get(f"/api/runs/{j['job_id']}/results", params={"include_stimulated": True, "top": 200}).json()
    assert res["stim_groups"] == [{"name": "Sugar", "rate_hz": 100.0, "n": 21},
                                  {"name": "Bitter", "rate_hz": 40.0, "n": 21}]
    assert res["params"]["rate_hz"] is None
    rows = {r["root_id"]: r for r in res["top"]}
    assert rows[BITTER[0]]["group"] == "Bitter" and rows[SUGAR[0]]["group"] == "Sugar"
    assert 85 < np.mean([rows[i]["rate_hz"] for i in SUGAR]) < 115      # stand-in fires them at
    assert 30 < np.mean([rows[i]["rate_hz"] for i in BITTER]) < 50      # their own input rate
    sp = c.get(f"/api/runs/{j['job_id']}/spikes").json()
    assert {r["group"] for r in sp["rows"] if r["role"] == "stimulated"} == {"Sugar, 100 Hz", "Bitter, 40 Hz"}
    csv = c.get(f"/api/runs/{j['job_id']}/rates.csv").text
    assert "# stimulus groups: Sugar at 100 Hz (21 neurons); Bitter at 40 Hz (21 neurons)" in csv


def test_one_group_is_exactly_the_old_single_rate_run(client):
    old = run_params(seed=21)
    new = group_params([{"name": "Anything", "rate_hz": 150, "ids": old["excite"]}], seed=21)
    a, _ = run_and_wait(client, old)
    b, _ = run_and_wait(client, new)
    jobs = client.app.state.jobs
    assert jobs.get(a["job_id"]).result.rates_hz == jobs.get(b["job_id"]).result.rates_hz
    assert a["params"]["stim_groups"] == [{"name": "Stimulated", "rate_hz": 150.0, "ids": old["excite"]}]
    assert a["params"]["rate_hz"] == b["params"]["rate_hz"] == 150.0


@pytest.mark.parametrize("groups, words", [
    ([{"name": "A", "rate_hz": 100, "ids": SUGAR[:2]}, {"name": "B", "rate_hz": 40, "ids": SUGAR[1:3]}],
     "two stimulus groups"),
    ([{"name": "A", "rate_hz": 100, "ids": SUGAR[:2]}, {"name": "Empty", "rate_hz": 40, "ids": []}],
     "'Empty' has no neurons"),
    ([{"name": "A", "rate_hz": 5000, "ids": SUGAR[:2]}], "input rate of group 'A'"),
    ([{"name": "A", "rate_hz": None, "ids": SUGAR[:2]}], "missing or not a number"),
    ([{"name": "A", "rate_hz": 10, "ids": SUGAR[:1]}] * 9, "at most 8"),
])
def test_bad_stimulus_groups_are_refused_with_a_reason(client, groups, words):
    r = client.post("/api/runs", json=group_params(groups))
    assert r.status_code == 400 and words in r.json()["detail"], r.text


def test_old_setup_without_model_loads_as_the_published_model(client, tmp_path):
    shutil.copy(st.SETUP_DIR / "sugar_grn_right.json", tmp_path / "sugar_grn_right.json")
    raw = json.loads((tmp_path / "sugar_grn_right.json").read_text(encoding="utf-8"))
    assert raw["format"] == "fly-brain-app-setup/1" and "variant" not in raw and "stim_groups" not in raw
    got = client.get("/api/setups/sugar_grn_right").json()
    p = got["params"]
    assert got["params_error"] is None
    assert p["variant"] == {"fix": "none", "upgrades": []}
    assert p["stim_groups"] == [{"name": "Stimulated", "rate_hz": 100.0, "ids": raw["excite"]}]
    assert p["rate_hz"] == 100.0 and p["excite"] == raw["excite"]
    # Saved with the real engine while the stand-in runs: warned, not silently accepted.
    assert got["engine_matches"] is False and "sim.fast_engine" in got["engine_warning"]
    assert st.code_check(raw, dict(raw["engine"])) == (True, None)   # same engine code: no warning
    j, _ = run_and_wait(client, {k: p[k] for k in st.RUN_KEYS})
    assert client.get(f"/api/runs/{j['job_id']}/results").json()["variant"]["key"] == "published"
    listed = client.get("/api/setups").json()["setups"]
    assert listed[0]["model"] == "Published model" and listed[0]["n_groups"] == 1


def test_setup_with_groups_and_model_round_trips_and_flags_code_changes(client, monkeypatch):
    body = group_params([{"name": "Sugar", "rate_hz": 100, "ids": SUGAR},
                         {"name": "Bitter", "rate_hz": 40, "ids": BITTER}], seed=9, variant=FIX)
    body.update(name="comp_fix", title="Competition, fixed model")
    r = client.post("/api/setups", json=body)
    assert r.status_code == 201, r.text
    saved = r.json()["setup"]
    assert saved["format"] == "fly-brain-app-setup/2" and saved["rate_hz"] is None
    assert saved["variant"]["fix"] == "al_ln_literature" and saved["variant"]["code"]["sim/sign_fixes.py"]
    assert saved["stim_groups"][1] == {"name": "Bitter", "rate_hz": 40.0, "ids": BITTER}
    got = client.get("/api/setups/comp_fix").json()
    assert got["engine_matches"] is True and got["engine_warning"] is None
    assert got["params"]["variant"] == FIX and got["params"]["stim_groups"] == saved["stim_groups"]
    out = []
    for _ in range(2):
        j, _ = run_and_wait(client, {k: got["params"][k] for k in st.RUN_KEYS})
        out.append(client.app.state.jobs.get(j["job_id"]).result.rates_hz)
    assert out[0] == out[1]
    real_hash = ea._file_hash
    monkeypatch.setattr(ea, "_file_hash",
                        lambda path: "0000changed0" if path.name == "sign_fixes.py" else real_hash(path))
    got = client.get("/api/setups/comp_fix").json()
    assert got["engine_matches"] is False and "sim/sign_fixes.py, which has changed" in got["engine_warning"]


def test_ready_made_competition_and_steering_setups(adapter):
    p = st.run_params(st.load_setup("sugar_bitter_competition"))
    assert [(g["name"], g["rate_hz"], g["ids"]) for g in p["stim_groups"]] == [
        ("Sugar", 100.0, SUGAR), ("Bitter", 40.0, BITTER)]
    assert (p["variant"], p["snapshot"], p["seed"], p["duration_ms"], p["n_trials"]) == (
        {"fix": "none", "upgrades": []}, "630", 0, 1000.0, 30)
    assert str(MN9_ID) in p["watch"]
    q = st.run_params(st.load_setup("da1_left_smell_fix"))
    assert q["variant"] == FIX and q["snapshot"] == "630" and q["seed"] == 0
    assert [(g["rate_hz"], g["ids"]) for g in q["stim_groups"]] == [
        (150.0, [str(i) for i in ea.DA1_LEFT_ORN_IDS_630])]
    assert set(q["watch"]) == {str(i) for _, left, right in ea.STEERING_DN_IDS_630 for i in (left, right)}
    for prm in (p, q):           # both run end to end (stand-in: plumbing only)
        small = {**prm, "duration_ms": 50, "n_trials": 2}
        app_rates, summary = run_through_app(adapter, small)
        assert compare(run_from_code(adapter, small).rates_hz, app_rates)["n_different"] == 0
        assert summary["is_fake"] is True and summary["variant"]["fix"] == prm["variant"]["fix"]


def test_da1_and_steering_ids_match_the_630_labels():
    f = ea.ROOT / "data" / "cache" / "connectome_630_neurons.parquet"
    if not f.exists():
        pytest.skip("630 label cache not built on this computer")
    lab = pd.read_parquet(f, columns=["root_id", "cell_class", "hemibrain_type", "side"])
    da1 = lab[(lab.cell_class == "olfactory") & (lab.hemibrain_type == "ORN_DA1") & (lab.side == "left")]
    assert da1.root_id.tolist() == ea.DA1_LEFT_ORN_IDS_630          # same set, model row order
    by = lab.set_index("root_id")
    for name, left, right in ea.STEERING_DN_IDS_630:
        assert (by.loc[left, "side"], by.loc[right, "side"]) == ("left", "right"), name


@pytest.mark.slow
def test_checkpoint_sugar_setup_app_equals_direct_fast_engine():
    """Phase 4 checkpoint: the saved sugar setup (snapshot 630, 100 Hz, 30 x 1000 ms,
    seed 0) run through the web API gives exactly the rates of a direct
    sim.fast_engine run with the same settings. MN9 is about 67.6 Hz."""
    from sim.fast_engine import FastBrain
    s = st.load_setup("sugar_grn_right")
    assert (s["snapshot"], s["rate_hz"], s["n_trials"], s["duration_ms"]) == ("630", 100.0, 30, 1000.0)
    real = EngineAdapter(force_fake=False)
    assert real.engine_info["name"] == "sim.fast_engine", real.engine_info["reason"]
    c = TestClient(create_app(real))
    params = {k: s[k] for k in ("excite", "silence", "watch", "duration_ms", "n_trials", "seed",
                                "rate_hz", "snapshot")}
    j = c.post("/api/runs", json=params).json()
    assert wait_done(c, j["job_id"], timeout=600)["state"] == "done"
    app_rates = c.app.state.jobs.get(j["job_id"]).result.rates_hz
    csv_mn9 = next(ln for ln in c.get(f"/api/runs/{j['job_id']}/rates.csv").text.splitlines()
                   if ln.startswith(str(MN9_ID)))

    brain = FastBrain(snapshot="630")          # built separately: no app code involved
    direct = brain.run(excite=np.array([int(i) for i in s["excite"]], dtype=np.int64),
                       duration_ms=s["duration_ms"], n_trials=s["n_trials"], seed=s["seed"],
                       rate_hz=s["rate_hz"])
    direct_rates = {int(k): float(v) for k, v in direct.rates().items()}
    assert app_rates[MN9_ID] == direct.rate(MN9_ID)            # exactly equal
    assert csv_mn9.split(",")[6] == f"{direct.rate(MN9_ID):.6f}"
    assert app_rates[MN9_ID] == pytest.approx(67.6, abs=0.1)
    assert app_rates == direct_rates                           # every neuron, exactly


@pytest.mark.slow
def test_competition_setup_through_app_equals_direct_run():
    """Sugar 100 Hz + bitter 40 Hz (published model, seed 0): the app gives exactly
    the rates of the engine's own per-neuron-rate call on the same brain, and MN9
    is 47.7 Hz (Phase 5, docs/phase5-competition.md; paper 45.3 Hz)."""
    p = st.run_params(st.load_setup("sugar_bitter_competition"))
    real = EngineAdapter(force_fake=False)
    assert real.engine_info["name"] == "sim.fast_engine", real.engine_info["reason"]
    app_rates, summary = run_through_app(real, p)
    assert summary["variant"]["key"] == "published"
    brain = real.engine("630").brain
    direct = brain.run(excite={int(i): float(g["rate_hz"]) for g in p["stim_groups"] for i in g["ids"]},
                       duration_ms=1000.0, n_trials=30, seed=0)
    assert compare({int(k): float(v) for k, v in direct.rates().items()}, app_rates)["n_different"] == 0
    assert app_rates[MN9_ID] == pytest.approx(47.7, abs=0.05)


@pytest.mark.slow
def test_da1_setup_on_recommended_fix_reproduces_phase6():
    """DA1 left-only smell on the recommended fix (seed 0): left DNa02 far above the
    right one, and every neuron's rate equals the saved Phase 6 run (if present)."""
    p = st.run_params(st.load_setup("da1_left_smell_fix"))
    real = EngineAdapter(force_fake=False)
    app_rates, summary = run_through_app(real, p)
    assert summary["variant"]["fix"] == "al_ln_literature"
    dna02_l, dna02_r = ea.STEERING_DN_IDS_630[0][1:]
    assert app_rates.get(dna02_l, 0.0) > 15.0 > 3.0 > app_rates.get(dna02_r, 0.0)
    saved = ea.ROOT / "experiments/phase6/steering/results/sim/al_ln_DA1_left_s0.npz"
    if saved.exists():
        z = np.load(saved)
        root_ids = real.engine("630", p["variant"]).brain.root_ids
        old = {int(r): float(v) for r, v in zip(root_ids, z["rates"]) if v}
        assert compare(old, app_rates, tol=1e-4)["n_different"] == 0
