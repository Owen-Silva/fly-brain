"""Run a saved setup from code, and (optionally) check the web app gives the same answer.

Examples (run from the project folder):
  .venv\\Scripts\\python.exe -m app.run_setup sugar_grn_right
  .venv\\Scripts\\python.exe -m app.run_setup sugar_grn_right --trials 2 --duration 200
  .venv\\Scripts\\python.exe -m app.run_setup sugar_grn_right --compare
  .venv\\Scripts\\python.exe -m app.run_setup app\\setups\\sugar_grn_right.json --csv out.csv

Plain English: --compare is the Phase 4 checkpoint. It runs the same recipe
twice: once straight from Python ("from code") and once through the web app's
own front door (the same web requests the page sends: start a run, wait for
it, download the rates). Then it compares every neuron's firing rate. If the
two agree exactly, the app adds nothing and loses nothing.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import time

from . import results as res
from . import setups as st
from .engine_adapter import EngineAdapter


def _params(setup, args):
    p = {k: setup.get(k) for k in ("excite", "silence", "watch", "duration_ms", "n_trials",
                                    "seed", "rate_hz", "snapshot")}
    changed = []
    for flag, key in (("trials", "n_trials"), ("duration", "duration_ms"), ("seed", "seed"),
                      ("rate", "rate_hz")):
        v = getattr(args, flag)
        if v is not None:
            p[key] = v
            changed.append(f"{key}={v}")
    return st.validate_params(p), changed


def run_from_code(adapter: EngineAdapter, p):
    return adapter.run(p["excite"], p["silence"], p["duration_ms"], p["n_trials"], p["seed"],
                       p["rate_hz"], snapshot=p["snapshot"])


def run_engine_directly(adapter: EngineAdapter, p):
    """The way a Phase 3 script would do it: call the engine's own API and use
    the engine's own rate arithmetic, with none of the app's code in between.
    Returns ({root_id: Hz}, description). Only possible for the fast engine;
    for other engines this falls back to the adapter and says so."""
    eng = adapter.engine(p["snapshot"])
    brain = getattr(eng, "brain", None)
    if brain is None:
        r = run_from_code(adapter, p)
        return r.rates_hz, f"{adapter.engine_info['name']} via app/engine_adapter.py (no direct path for this engine)"
    res = brain.run(excite=[int(i) for i in p["excite"]], silence=[int(i) for i in p["silence"]],
                    duration_ms=p["duration_ms"], n_trials=p["n_trials"], seed=p["seed"],
                    rate_hz=p["rate_hz"])
    rates = {int(k): float(v) for k, v in res.rates().items()}
    return rates, f"FastBrain(snapshot={getattr(eng, 'snapshot', '?')}).run(...) then SimResult.rates()"


def run_through_app(adapter: EngineAdapter, p, timeout_s: float = 3600):
    """Drive the real web API in-process, exactly as the browser page does."""
    import warnings
    with warnings.catch_warnings():  # starlette's notice about a future httpx change; harmless here
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient
    from .main import create_app
    client = TestClient(create_app(adapter))
    r = client.post("/api/runs", json=p)
    r.raise_for_status()
    job_id = r.json()["job_id"]
    t0 = time.time()
    while True:
        s = client.get(f"/api/runs/{job_id}").json()
        if s["state"] == "done":
            break
        if s["state"] == "failed":
            raise RuntimeError(f"the app's run failed: {s['error']}")
        if time.time() - t0 > timeout_s:
            raise TimeoutError("the app's run did not finish in time")
        time.sleep(0.25)
    text = client.get(f"/api/runs/{job_id}/rates.csv").text
    rows = [ln for ln in text.splitlines() if not ln.startswith("#")]
    rates = {int(r["root_id"]): float(r["rate_hz"]) for r in csv.DictReader(io.StringIO("\n".join(rows)))}
    summary = client.get(f"/api/runs/{job_id}/results", params={"top": 20}).json()
    return rates, summary


def compare(code_rates: dict[int, float], app_rates: dict[int, float], tol=1e-5):
    ids = set(code_rates) | set(app_rates)
    diffs = sorted(((abs(code_rates.get(i, 0.0) - app_rates.get(i, 0.0)), i) for i in ids), reverse=True)
    worst = diffs[0] if diffs else (0.0, None)
    n_bad = sum(1 for d, _ in diffs if d > tol)
    return {"n_neurons": len(ids), "n_different": n_bad, "max_abs_diff_hz": worst[0], "worst_id": worst[1]}


def _print_summary(adapter, result, p, top):
    s = res.summary(adapter, result, p, top=top)
    eng = s["engine"]
    print(f"Engine: {eng['name']} version {eng['version']} (code {eng['code_hash']}), snapshot {s['snapshot']}")
    if s["is_fake"]:
        print("!! STAND-IN ENGINE: these numbers are NOT from the fly brain model. " + eng["reason"])
    print(f"Ran {s['n_trials']} trial(s) of {s['duration_ms']:g} ms in {s['wall_seconds']:.1f} s; "
          f"{s['n_active_downstream']} non-stimulated neurons fired at least once.")
    for w in s["watch"]:
        print(f"  watched {w['root_id']} ({w['cell_type'] or 'unnamed'}): {w['rate_hz']:.2f} Hz")
    print(f"Top {len(s['top'])} most active non-stimulated neurons:")
    for r in s["top"]:
        print(f"  {r['rank']:>3}. {r['cell_type'] or '(no type)':<16} {r['super_class']:<12} "
              f"{r['rate_hz']:>8.2f} Hz  {r['root_id']}")
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run a saved explorer-app setup from code.")
    ap.add_argument("setup", help="setup name (in app/setups) or path to a setup .json file")
    ap.add_argument("--trials", type=int, help="override the number of trials")
    ap.add_argument("--duration", type=float, help="override the run length in ms")
    ap.add_argument("--seed", type=int, help="override the random seed")
    ap.add_argument("--rate", type=float, help="override the input rate in Hz")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--csv", help="write every neuron's rate to this CSV file")
    ap.add_argument("--compare", action="store_true",
                    help="also run it through the web app and check both give the same rates")
    args = ap.parse_args(argv)

    setup = st.load_setup(args.setup, allow_path=True)
    p, changed = _params(setup, args)
    print(f"Setup: {setup['title']}  ({len(p['excite'])} stimulated, {len(p['silence'])} silenced, "
          f"{p['duration_ms']:g} ms x {p['n_trials']} trials, seed {p['seed']}, {p['rate_hz']:g} Hz, "
          f"snapshot {p['snapshot']})")
    if changed:
        print("Overrides (differs from the saved setup): " + ", ".join(changed))

    adapter = EngineAdapter()
    saved = setup.get("engine") or {}
    if saved.get("code_hash") != adapter.engine_info.get("code_hash"):
        print(f"Note: setup was saved with engine '{saved.get('name')}' code {saved.get('code_hash')}; "
              f"now using '{adapter.engine_info['name']}' code {adapter.engine_info['code_hash']}.")
    if not args.compare:
        result = run_from_code(adapter, p)
        _print_summary(adapter, result, p, args.top)
        if args.csv:
            with open(args.csv, "w", encoding="utf-8", newline="") as f:
                f.write(res.rates_csv(adapter, result, p))
            print(f"Wrote every neuron's rate to {args.csv}")
        return 0

    print("Checking the web app gives the same answer as code (same setup, same seed)...")
    t0 = time.perf_counter()
    code_rates, how = run_engine_directly(adapter, p)
    print(f"  from code ({time.perf_counter() - t0:.0f} s): {how}")
    t0 = time.perf_counter()
    app_rates, summary = run_through_app(adapter, p)
    print(f"  through the app ({time.perf_counter() - t0:.0f} s): POST /api/runs, poll "
          "/api/runs/<id>, GET /api/runs/<id>/rates.csv")
    eng = summary["engine"]
    print(f"  engine: {eng['name']}, {eng['version']} (code {eng['code_hash']}), snapshot {summary['snapshot']}")
    top = [f"{r['cell_type'] or r['root_id']} {r['rate_hz']:.1f}" for r in summary["top"][:5]]
    print("  app's top 5 non-stimulated (Hz): " + ", ".join(top))
    c = compare(code_rates, app_rates)
    for w in p["watch"]:
        print(f"  watched {w}: from code {code_rates.get(int(w), 0.0):.4f} Hz, "
              f"through the app {app_rates.get(int(w), 0.0):.4f} Hz")
    if c["n_different"] == 0:
        print(f"SAME RESULT: all {c['n_neurons']} neurons that fired have the same rate both ways "
              f"(largest difference {c['max_abs_diff_hz']:.6f} Hz).")
        if adapter.engine_info.get("is_fake"):
            print("BUT this used the stand-in engine, so it only proves the app's plumbing, "
                  "not the Phase 4 checkpoint.")
        return 0
    print(f"DIFFERENT: {c['n_different']} of {c['n_neurons']} neurons differ "
          f"(largest {c['max_abs_diff_hz']:.4f} Hz, neuron {c['worst_id']}).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
