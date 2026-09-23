"""Background runs.

Plain English: a whole-brain run can take tens of seconds, so the web page
never waits on it directly. Pressing Run creates a "job". One worker thread
runs jobs one at a time (the machine is shared, so we never run two at once)
and the page asks every half second how the job is doing.
"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from .engine_adapter import MAX_BRAINS_IN_MEMORY, EngineAdapter, RunResult, check_variant, variant_key, variant_label


@dataclass
class Job:
    id: str
    params: dict[str, Any]
    state: str = "queued"           # queued -> building (a model's brain) -> running -> done | failed
    message: str = "Waiting for the previous run to finish."
    progress: float | None = None   # 0..1, or None when the engine cannot say
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    error: str | None = None
    result: RunResult | None = None
    engine: dict[str, Any] = field(default_factory=dict)
    estimate_s: float | None = None  # guess from the previous run's speed, labelled as such

    def public(self) -> dict[str, Any]:
        now = time.time()
        return {
            "job_id": self.id, "state": self.state, "message": self.message,
            "progress": self.progress,
            "elapsed_s": round((self.finished or now) - (self.started or now), 2) if self.started else 0.0,
            "error": self.error, "params": self.params, "engine": self.engine,
            "is_fake": bool(self.engine.get("is_fake")),
            "estimate_s": None if self.estimate_s is None else round(self.estimate_s, 1),
        }


class JobManager:
    def __init__(self, adapter: EngineAdapter, keep: int = 20):
        self.adapter = adapter
        self.keep = keep
        self.jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="flybrain-run")
        # Wall seconds per simulated trial-second, per model (their speeds differ).
        self._sec_per_sim_s: dict[str, float] = {}
        self._runs_done: dict[str, int] = {}

    def submit(self, params: dict[str, Any]) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], params=params, engine=dict(self.adapter.engine_info))
        with self._lock:
            self.jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > self.keep:
                old = self._order.pop(0)
                if self.jobs[old].state in ("done", "failed"):
                    self.jobs.pop(old, None)
                else:
                    self._order.insert(0, old)
                    break
        self._pool.submit(self._work, job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def _work(self, job: Job):
        job.started = time.time()
        try:
            p = job.params
            variant = p.get("variant")
            if not self.adapter.engine_built(p["snapshot"], variant):
                job.state = "building"
                label = variant_label(check_variant(variant, p["snapshot"]))
                last = self.adapter.last_build_seconds(p["snapshot"], variant)
                job.message = (f"Building the brain for the model '{label}' (map {p['snapshot']}). "
                               "This happens the first time a model is used, then it stays in memory "
                               f"(the app keeps at most {MAX_BRAINS_IN_MEMORY} built models, so one "
                               "you used earlier may be dropped and rebuilt later). "
                               + (f"It took {last:.0f} s last time." if last is not None
                                  else "This can take from a few seconds to about a minute."))

            def progress(frac):
                try:
                    job.progress = max(0.0, min(1.0, float(frac)))
                except (TypeError, ValueError):
                    pass
                if job.state != "running":
                    job.state = "running"
                job.message = f"Running: {round((job.progress or 0) * 100)}% done."

            # If the engine never calls progress(), the page shows an honest
            # "working, this engine does not report progress" instead.
            self.adapter.engine(p["snapshot"], variant)
            job.state = "running"
            job.message = "Running the simulation."
            sim_s = p["n_trials"] * p["duration_ms"] / 1000.0
            speed_key = f"{p['snapshot']}|{variant_key(check_variant(variant, p['snapshot']))}"
            if speed_key in self._sec_per_sim_s:
                job.estimate_s = self._sec_per_sim_s[speed_key] * sim_s
            job.result = self.adapter.run(p["excite"], p["silence"], p["duration_ms"],
                                          p["n_trials"], p["seed"], p["rate_hz"], progress,
                                          snapshot=p["snapshot"], variant=variant,
                                          stim_groups=p.get("stim_groups"))
            job.engine = dict(job.result.engine)
            # The first run after start-up also pays one-off compile costs, so it
            # is not used for the speed estimate.
            self._runs_done[speed_key] = self._runs_done.get(speed_key, 0) + 1
            if sim_s > 0 and self._runs_done[speed_key] > 1:
                self._sec_per_sim_s[speed_key] = job.result.wall_seconds / sim_s
            job.progress = 1.0
            job.state = "done"
            job.message = f"Finished in {job.result.wall_seconds:.1f} s."
        except Exception as exc:  # noqa: BLE001 - shown to the user, never swallowed
            job.state = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
            job.message = "The run failed. The error is shown below."
        finally:
            job.finished = time.time()

    def shutdown(self):
        self._pool.shutdown(wait=False, cancel_futures=True)
