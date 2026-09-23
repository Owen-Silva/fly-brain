"""The explorer app's web server (FastAPI).

Start it with:   .venv\\Scripts\\python.exe -m app            (then open http://127.0.0.1:8765)

Plain English: this file answers the web page's questions ("find neurons
called X", "start a run", "is it done yet?", "show me the results", "save this
setup"). All simulator access goes through app/engine_adapter.py.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import results as res
from . import setups as st
from .engine_adapter import (DEFAULT_SNAPSHOT, DOCS_DIR, FIX_CHOICES, SERVED_DOCS, UPGRADE_CHOICES,
                             EngineAdapter, check_snapshot, check_variant, combination_problem,
                             get_adapter, variant_key, variant_label)
from .jobs import JobManager

STATIC = Path(__file__).resolve().parent / "static"


def create_app(adapter: EngineAdapter | None = None, setup_dir: Path | None = None) -> FastAPI:
    adapter = adapter or get_adapter()
    jobs = JobManager(adapter)
    setup_dir = setup_dir or st.SETUP_DIR
    app = FastAPI(title="Fly brain explorer", docs_url="/api/docs", redoc_url=None)
    app.state.adapter, app.state.jobs, app.state.setup_dir = adapter, jobs, setup_dir

    def _job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, f"no run with id '{job_id}' (runs are forgotten when the app restarts)")
        return job

    def _done(job_id: str):
        job = _job(job_id)
        if job.state == "failed":
            raise HTTPException(409, f"this run failed: {job.error}")
        if job.state != "done":
            raise HTTPException(409, f"this run is not finished yet (state: {job.state})")
        return job

    # ---- status and neurons ---------------------------------------------
    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return {**adapter.status(), "limits": st.LIMITS}

    def _snap(s) -> str:
        try:
            return check_snapshot(s or DEFAULT_SNAPSHOT)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/neurons/search")
    def search(q: str = Query("", max_length=100), limit: int = Query(50, ge=1, le=5000),
               snapshot: str = DEFAULT_SNAPSHOT):
        snap = _snap(snapshot)
        return {**adapter.search(q, limit, snap), "neuron_table": adapter.table(snap).info}

    @app.post("/api/neurons/lookup")
    def lookup(body: dict[str, Any] = Body(...)):
        snap = _snap(body.get("snapshot"))
        try:
            return {"snapshot": snap, "neurons": adapter.lookup(body.get("ids") or [], snap)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    # ---- model variants ----------------------------------------------------
    @app.get("/api/models/state")
    def model_state(snapshot: str = DEFAULT_SNAPSHOT, fix: str = "none", upgrades: str = ""):
        """Is this model choice allowed, is it in memory, and which other choices
        are allowed from here (each with a plain-English reason if not)."""
        snap = _snap(snapshot)
        ups = [u for u in upgrades.split(",") if u]
        options = {}
        for k in FIX_CHOICES:
            why = combination_problem(k, [u for u in ups if u in UPGRADE_CHOICES], snap)
            options["fix:" + k] = {"allowed": why is None and adapter.option_problems.get(k) is None,
                                   "why": adapter.option_problems.get(k) or why}
        for k in UPGRADE_CHOICES:
            trial = sorted({*[u for u in ups if u in UPGRADE_CHOICES], k})
            why = combination_problem(fix if fix in FIX_CHOICES else "none", trial, snap)
            options["up:" + k] = {"allowed": why is None and adapter.option_problems.get(k) is None,
                                  "why": adapter.option_problems.get(k) or why}
        try:
            v = check_variant({"fix": fix, "upgrades": ups}, snap)
        except ValueError as exc:
            return {"ok": False, "problem": str(exc), "options": options, "variant": None}
        return {"ok": True, "problem": adapter.variant_unavailable(v), "variant": v,
                "key": variant_key(v), "label": variant_label(v), "options": options,
                "memory": adapter.variant_state(v, snap), "models": adapter.models_status()}

    @app.get("/api/model-docs/{name}", response_class=PlainTextResponse)
    def doc(name: str):
        """The model docs the page links to, as plain text (only the listed files)."""
        if name not in SERVED_DOCS:
            raise HTTPException(404, f"no doc called '{name}' is served by the app")
        path = DOCS_DIR / name
        if not path.exists():
            raise HTTPException(404, f"docs/{name} does not exist on this computer")
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")

    # ---- runs ------------------------------------------------------------
    @app.post("/api/runs", status_code=202)
    def start_run(body: dict[str, Any] = Body(...)):
        try:
            p = st.validate_params(body)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        if not adapter.runs_enabled:
            raise HTTPException(503, "runs are switched off: " + (adapter.banner() or ""))
        if not p["excite"]:
            raise HTTPException(400, "pick at least one neuron to stimulate; with no input the "
                                     "model brain stays silent")
        why = adapter.variant_unavailable(p["variant"])
        if why:
            raise HTTPException(400, why + ". Nothing was run in its place.")
        snap = p["snapshot"]
        unknown = adapter.unknown_ids([int(i) for i in p["excite"] + p["silence"] + p["watch"]], snap)
        if unknown:
            raise HTTPException(400, f"{len(unknown)} id(s) are not in the snapshot {snap} neuron table "
                                     f"({adapter.table(snap).info.get('source')}): "
                                     + ", ".join(map(str, unknown[:10])))
        seed_note = None
        if p["seed"] is None:
            p["seed"] = random.SystemRandom().randrange(0, 2**31)
            seed_note = "no seed given, so the app picked one; it is saved with the run"
        job = jobs.submit(p)
        return {**job.public(), "seed_note": seed_note, "banner": adapter.banner()}

    @app.get("/api/runs/{job_id}")
    def run_status(job_id: str):
        return {**_job(job_id).public(), "banner": adapter.banner()}

    @app.get("/api/runs/{job_id}/results")
    def run_results(job_id: str, top: int = Query(50, ge=1, le=2000),
                    include_stimulated: bool = False):
        job = _done(job_id)
        return {"job_id": job_id, "params": job.params, "banner": adapter.banner(),
                **res.summary(adapter, job.result, job.params, top, include_stimulated)}

    @app.get("/api/runs/{job_id}/spikes")
    def run_spikes(job_id: str, trial: int = Query(0, ge=0), max_rows: int = Query(150, ge=1, le=1000)):
        job = _done(job_id)
        try:
            return {"job_id": job_id, **res.raster(adapter, job.result, job.params, trial, max_rows)}
        except IndexError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/runs/{job_id}/rates.csv", response_class=PlainTextResponse)
    def run_rates_csv(job_id: str):
        job = _done(job_id)
        return PlainTextResponse(res.rates_csv(adapter, job.result, job.params), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="rates_{job_id}.csv"'})

    # ---- setups ------------------------------------------------------------
    @app.get("/api/setups")
    def setups_list():
        return {"setups": st.list_setups(setup_dir), "current_engine": adapter.engine_info}

    @app.get("/api/setups/{name}")
    def setups_get(name: str):
        try:
            data = st.load_setup(name, setup_dir)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from None
        same, warning = st.code_check(data, adapter.engine_info)
        try:
            params, params_error = st.run_params(data), None
        except ValueError as exc:
            params, params_error = None, f"This setup cannot be run as saved: {exc}"
        # "params": the setup as the app will run it (an old setup without a model
        # is the published model; its single input rate is one stimulus group).
        return {"setup": data, "params": params, "params_error": params_error,
                "engine_matches": same, "engine_warning": warning}

    @app.post("/api/setups", status_code=201)
    def setups_save(body: dict[str, Any] = Body(...), overwrite: bool = False):
        try:
            return {"setup": st.save_setup(body, adapter.engine_info, overwrite, setup_dir)}
        except FileExistsError as exc:
            raise HTTPException(409, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    # ---- the page ----------------------------------------------------------
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
