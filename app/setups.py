"""Saved experiment setups (JSON files in app/setups/).

Plain English: a "setup" is a recipe for one experiment: which neurons to
stimulate, which to silence, how long to run, how many repeats, the random
seed, the input rate, and which engine (and engine version) it was run with.
With the same recipe and the same engine version you get exactly the same
result, whether you run it from the web page or from code.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .engine_adapter import DEFAULT_SNAPSHOT, check_snapshot

SETUP_DIR = Path(__file__).resolve().parent / "setups"
FORMAT = "fly-brain-app-setup/1"
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

# Hard limits keep one careless click from tying up the shared machine for hours.
LIMITS = {"duration_ms": (1, 10_000), "n_trials": (1, 100), "rate_hz": (0, 1_000),
          "seed": (0, 2**32 - 1), "max_ids": 5_000}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9_-]+", "_", (name or "").strip().lower()).strip("_-")
    return s[:64]


def check_name(name: str) -> str:
    if not _NAME_RE.match(name or ""):
        raise ValueError("setup names may only use a-z, 0-9, _ and - (max 64 characters)")
    return name


def path_for(name: str, folder: Path | None = None) -> Path:
    return (folder or SETUP_DIR) / f"{check_name(name)}.json"


def validate_params(p: dict[str, Any]) -> dict[str, Any]:
    """Check and tidy run parameters. Ids come back as lists of strings."""
    out: dict[str, Any] = {}
    for key in ("excite", "silence", "watch"):
        ids = p.get(key) or []
        if not isinstance(ids, list):
            raise ValueError(f"'{key}' must be a list of FlyWire root ids")
        clean = []
        for i in ids:
            s = str(i).strip()
            if not s.isdigit():
                raise ValueError(f"'{i}' in '{key}' is not a FlyWire root id (digits only)")
            if s not in clean:
                clean.append(s)
        if len(clean) > LIMITS["max_ids"]:
            raise ValueError(f"'{key}' has {len(clean)} ids; the limit is {LIMITS['max_ids']}")
        out[key] = clean
    for key, cast in (("duration_ms", float), ("n_trials", int), ("rate_hz", float)):
        lo, hi = LIMITS[key]
        try:
            v = cast(p[key])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"'{key}' is missing or not a number") from None
        if not lo <= v <= hi:
            raise ValueError(f"'{key}' must be between {lo} and {hi} (got {v})")
        out[key] = v
    seed = p.get("seed")
    if seed is None or seed == "":
        out["seed"] = None
    else:
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            raise ValueError("'seed' must be a whole number") from None
        lo, hi = LIMITS["seed"]
        if not lo <= seed <= hi:
            raise ValueError(f"'seed' must be between {lo} and {hi}")
        out["seed"] = seed
    # Neuron ids differ between FlyWire snapshots, so the snapshot is part of every run.
    out["snapshot"] = check_snapshot(p.get("snapshot") or DEFAULT_SNAPSHOT)
    overlap = set(out["excite"]) & set(out["silence"])
    if overlap:
        raise ValueError(f"{len(overlap)} neuron(s) are in both Stimulate and Silence; "
                         "pick one list for each neuron")
    return out


def save_setup(data: dict[str, Any], engine: dict[str, Any], overwrite: bool = False,
               folder: Path | None = None) -> dict[str, Any]:
    name = check_name(slugify(data.get("name") or data.get("title") or ""))
    params = validate_params(data)
    if params["seed"] is None:
        raise ValueError("a saved setup needs a fixed seed, otherwise it cannot be re-run exactly")
    path = path_for(name, folder)
    if path.exists() and not overwrite:
        raise FileExistsError(f"a setup called '{name}' already exists")
    setup = {
        "format": FORMAT,
        "name": name,
        "title": (data.get("title") or name)[:120],
        "description": (data.get("description") or "")[:4000],
        **params,
        "engine": {k: engine.get(k) for k in ("name", "module", "version", "code_hash", "is_fake")},
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(setup, indent=2) + "\n", encoding="utf-8")
    return setup


def load_setup(name_or_path: str | Path, folder: Path | None = None,
               allow_path: bool = False) -> dict[str, Any]:
    """Load by setup name. allow_path=True (command line only) also accepts a file path."""
    p = Path(name_or_path)
    path = p if allow_path and p.suffix == ".json" and p.exists() else path_for(str(name_or_path), folder)
    if not path.exists():
        raise FileNotFoundError(f"no saved setup called '{name_or_path}'")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise ValueError(f"{path.name} is not a fly-brain app setup (format {data.get('format')!r})")
    return data


def list_setups(folder: Path | None = None) -> list[dict[str, Any]]:
    out = []
    for f in sorted((folder or SETUP_DIR).glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            out.append({"name": f.stem, "title": f.stem, "error": f"unreadable: {exc}"})
            continue
        out.append({"name": d.get("name", f.stem), "title": d.get("title", f.stem),
                    "description": d.get("description", ""), "saved_at": d.get("saved_at"),
                    "engine": d.get("engine"), "snapshot": d.get("snapshot"), "n_excite": len(d.get("excite", [])),
                    "n_silence": len(d.get("silence", []))})
    return out
