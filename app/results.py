"""Turn a finished run into the tables and raster data the page shows.

Used by both the web API and the command-line runner, so the numbers shown in
the browser and printed in the terminal come from the same code.
"""
from __future__ import annotations

import csv
import io
from typing import Any

import numpy as np

from .engine_adapter import EngineAdapter, RunResult


def _role(rid: str, params: dict[str, Any]) -> str:
    if rid in params.get("excite", []):
        return "stimulated"
    if rid in params.get("silence", []):
        return "silenced"
    return "downstream"


def ranked_rates(result: RunResult) -> list[tuple[int, float]]:
    """All neurons that fired, highest mean rate first (ties: lower id first)."""
    return sorted(result.rates_hz.items(), key=lambda kv: (-kv[1], kv[0]))


def _group_of(rid: str, result: RunResult) -> dict[str, Any] | None:
    for g in result.stim_groups:
        if rid in g["ids"]:
            return g
    return None


def neuron_row(adapter: EngineAdapter, result: RunResult, rid: int, params, rank=None):
    rec = adapter.neuron_record(rid, result.snapshot)
    rec.update(rate_hz=round(result.rates_hz.get(rid, 0.0), 4),
               rate_sd_hz=round(result.rate_sd_hz.get(rid, 0.0), 4),
               role=_role(str(rid), params))
    g = _group_of(str(rid), result) if rec["role"] == "stimulated" else None
    if g is not None:
        rec.update(group=g["name"], group_rate_hz=g["rate_hz"])
    if rank is not None:
        rec["rank"] = rank
    return rec


def summary(adapter: EngineAdapter, result: RunResult, params: dict[str, Any],
            top: int = 50, include_stimulated: bool = False) -> dict[str, Any]:
    ranked = ranked_rates(result)
    stim = set(params.get("excite", []))
    rows, rank = [], 0
    for rid, _ in ranked:
        if not include_stimulated and str(rid) in stim:
            continue
        rank += 1
        rows.append(neuron_row(adapter, result, rid, params, rank))
        if len(rows) >= top:
            break
    n_down = sum(1 for rid, _ in ranked if str(rid) not in stim)
    total_spikes = int(sum(len(v) for tr in result.trials for v in tr.values()))
    watch = [neuron_row(adapter, result, int(r), params) for r in params.get("watch", [])]
    return {
        "engine": result.engine, "is_fake": bool(result.engine.get("is_fake")),
        "snapshot": result.snapshot, "variant": result.variant,
        "stim_groups": [{"name": g["name"], "rate_hz": g["rate_hz"], "n": len(g["ids"])}
                        for g in result.stim_groups],
        "duration_ms": result.duration_ms, "n_trials": result.n_trials,
        "wall_seconds": round(result.wall_seconds, 3), "notes": result.notes,
        "n_active": len(ranked), "n_active_downstream": n_down,
        "total_spikes": total_spikes, "include_stimulated": include_stimulated,
        "top": rows, "watch": watch,
    }


def raster(adapter: EngineAdapter, result: RunResult, params: dict[str, Any],
           trial: int = 0, max_rows: int = 150, max_spikes: int = 200_000) -> dict[str, Any]:
    """Spike times for one trial, for the most interesting rows.

    Row order: stimulated neurons first, then watched ones, then the most
    active downstream neurons, up to max_rows rows.
    """
    if not 0 <= trial < result.n_trials:
        raise IndexError(f"trial must be between 0 and {result.n_trials - 1}")
    tr = result.trials[trial]
    order: list[int] = []
    seen = set()

    def add(rid):
        if rid not in seen and len(order) < max_rows:
            seen.add(rid)
            order.append(rid)

    for r in params.get("excite", []):
        add(int(r))
    for r in params.get("watch", []):
        add(int(r))
    for rid, _ in ranked_rates(result):
        add(rid)
    rows, n_spikes, truncated = [], 0, False
    for rid in order:
        ts = tr.get(rid, np.empty(0))
        if n_spikes + len(ts) > max_spikes:
            ts = ts[: max(0, max_spikes - n_spikes)]
            truncated = True
        n_spikes += len(ts)
        rec = adapter.neuron_record(rid, result.snapshot)
        g = _group_of(str(rid), result)
        rows.append({"root_id": str(rid), "cell_type": rec["cell_type"], "name": rec["name"],
                     "cell_class": rec["cell_class"],
                     "role": _role(str(rid), params),
                     "group": None if g is None else f"{g['name']}, {g['rate_hz']:g} Hz",
                     "rate_hz": round(result.rates_hz.get(rid, 0.0), 3),
                     "t_ms": [round(float(t), 2) for t in ts]})
    return {"trial": trial, "n_trials": result.n_trials, "snapshot": result.snapshot,
            "duration_ms": result.duration_ms,
            "rows": rows, "n_spikes": n_spikes, "truncated": truncated,
            "n_rows_hidden": max(0, len(result.rates_hz) - len(rows)),
            "is_fake": bool(result.engine.get("is_fake"))}


def rates_csv(adapter: EngineAdapter, result: RunResult, params: dict[str, Any]) -> str:
    buf = io.StringIO()
    eng = result.engine
    if eng.get("is_fake"):
        buf.write("# WARNING: stand-in engine, NOT the fly brain model. " + eng.get("reason", "") + "\n")
    buf.write(f"# engine={eng.get('name')} version={eng.get('version')} code_hash={eng.get('code_hash')}\n")
    var = result.variant or {}
    code = " ".join(f"{f}={h}" for f, h in (var.get("code") or {}).items())
    buf.write(f"# model={var.get('label')} fix={var.get('fix')} "
              f"upgrades={','.join(var.get('upgrades') or []) or 'none'} code: {code}\n")
    buf.write(f"# duration_ms={result.duration_ms} n_trials={result.n_trials} "
              f"seed={params.get('seed')} rate_hz={params.get('rate_hz')} snapshot={result.snapshot}\n")
    buf.write("# stimulus groups: " + "; ".join(f"{g['name']} at {g['rate_hz']:g} Hz ({len(g['ids'])} neurons)"
                                                 for g in result.stim_groups) + "\n")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["root_id", "cell_type", "super_class", "nt", "side", "role", "rate_hz", "rate_sd_hz"])
    for rid, rate in ranked_rates(result):
        rec = adapter.neuron_record(rid, result.snapshot)
        w.writerow([rid, rec["cell_type"], rec["super_class"], rec["nt"], rec["side"],
                    _role(str(rid), params), f"{rate:.6f}", f"{result.rate_sd_hz.get(rid, 0.0):.6f}"])
    return buf.getvalue()
