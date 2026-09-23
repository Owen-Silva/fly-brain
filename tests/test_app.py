"""Phase 4: the explorer app's web API (FastAPI TestClient, stand-in engine).

These tests force the stand-in engine so they are fast and do not depend on
the whole-brain simulator. One test marked "slow" runs whatever real engine the
adapter finds, with a tiny run.
"""
import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

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
