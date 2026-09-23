"""Saved experiment setups (JSON files in app/setups/).

Plain English: a "setup" is a recipe for one experiment: which neurons to
stimulate (in one or more groups, each with its own input rate), which to
silence, how long to run, how many repeats, the random seed, the brain map,
the MODEL (published, or a validated variant, with a fingerprint of every code
file it uses) and which engine (and engine version) it was run with. With the
same recipe and the same code you get exactly the same result, whether you
run it from the web page or from code.

Older setups (format 1, saved before model variants and stimulus groups
existed) are still read: no "variant" means the published model, and their
single "rate_hz" becomes one stimulus group.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .engine_adapter import DEFAULT_SNAPSHOT, check_snapshot, check_variant, variant_record

SETUP_DIR = Path(__file__).resolve().parent / "setups"
FORMAT = "fly-brain-app-setup/2"
FORMATS_READ = ("fly-brain-app-setup/1", FORMAT)
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
DEFAULT_GROUP_NAME = "Stimulated"

# Hard limits keep one careless click from tying up the shared machine for hours.
LIMITS = {"duration_ms": (1, 10_000), "n_trials": (1, 100), "rate_hz": (0, 1_000),
          "seed": (0, 2**32 - 1), "max_ids": 5_000, "max_groups": 8, "group_name_chars": 40}
RUN_KEYS = ("excite", "silence", "watch", "stim_groups", "duration_ms", "n_trials", "seed",
            "rate_hz", "snapshot", "variant")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9_-]+", "_", (name or "").strip().lower()).strip("_-")
    return s[:64]


def check_name(name: str) -> str:
    if not _NAME_RE.match(name or ""):
        raise ValueError("setup names may only use a-z, 0-9, _ and - (max 64 characters)")
    return name


def path_for(name: str, folder: Path | None = None) -> Path:
    return (folder or SETUP_DIR) / f"{check_name(name)}.json"


def _clean_ids(ids, what: str) -> list[str]:
    ids = ids or []
    if not isinstance(ids, list):
        raise ValueError(f"'{what}' must be a list of FlyWire root ids")
    clean = []
    for i in ids:
        s = str(i).strip()
        if not s.isdigit():
            raise ValueError(f"'{i}' in '{what}' is not a FlyWire root id (digits only)")
        if s not in clean:
            clean.append(s)
    if len(clean) > LIMITS["max_ids"]:
        raise ValueError(f"'{what}' has {len(clean)} ids; the limit is {LIMITS['max_ids']}")
    return clean


def _number(v, key: str, cast, what: str | None = None):
    lo, hi = LIMITS[key]
    try:
        x = cast(v)
    except (TypeError, ValueError):
        raise ValueError(f"'{what or key}' is missing or not a number") from None
    if not lo <= x <= hi:
        raise ValueError(f"'{what or key}' must be between {lo} and {hi} (got {x})")
    return x


def _groups(p: dict[str, Any]) -> list[dict[str, Any]]:
    """The stimulus groups: [{"name", "rate_hz", "ids"}]. An old-style request
    (``excite`` + ``rate_hz``, no groups) is one group at that rate."""
    raw = p.get("stim_groups")
    if not raw:
        excite = _clean_ids(p.get("excite"), "excite")
        if not excite:
            return []
        return [{"name": DEFAULT_GROUP_NAME, "rate_hz": _number(p.get("rate_hz"), "rate_hz", float),
                 "ids": excite}]
    if not isinstance(raw, list):
        raise ValueError("'stim_groups' must be a list of groups")
    if len(raw) > LIMITS["max_groups"]:
        raise ValueError(f"at most {LIMITS['max_groups']} stimulus groups (got {len(raw)})")
    groups, owner = [], {}
    for n, g in enumerate(raw, 1):
        if not isinstance(g, dict):
            raise ValueError("each stimulus group must be an object with name, rate_hz and ids")
        name = str(g.get("name") or "").strip()[: LIMITS["group_name_chars"]] or f"Group {n}"
        rate = _number(g.get("rate_hz"), "rate_hz", float, f"input rate of group '{name}'")
        ids = _clean_ids(g.get("ids"), f"group '{name}'")
        for i in ids:
            if i in owner:
                raise ValueError(f"neuron {i} is in two stimulus groups ('{owner[i]}' and '{name}'); "
                                 "a neuron can only have one input rate")
            owner[i] = name
        groups.append({"name": name, "rate_hz": rate, "ids": ids})
    non_empty = [g for g in groups if g["ids"]]
    if non_empty and len(non_empty) < len(groups):
        empty = next(g["name"] for g in groups if not g["ids"])
        raise ValueError(f"stimulus group '{empty}' has no neurons; add some or remove the group")
    if p.get("excite"):
        flat = {i for g in groups for i in g["ids"]}
        if set(_clean_ids(p.get("excite"), "excite")) != flat:
            raise ValueError("'excite' and 'stim_groups' list different neurons; send only 'stim_groups'")
    return non_empty


def validate_params(p: dict[str, Any]) -> dict[str, Any]:
    """Check and tidy run parameters. Ids come back as lists of strings.

    Returns excite (every stimulated id, in group order), stim_groups, silence,
    watch, duration_ms, n_trials, seed, rate_hz (the shared rate, or None when
    groups have different rates), snapshot and variant ({"fix", "upgrades"})."""
    out: dict[str, Any] = {}
    for key in ("silence", "watch"):
        out[key] = _clean_ids(p.get(key), key)
    groups = _groups(p)
    out["excite"] = [i for g in groups for i in g["ids"]]
    if len(out["excite"]) > LIMITS["max_ids"]:
        raise ValueError(f"{len(out['excite'])} stimulated ids; the limit is {LIMITS['max_ids']}")
    out["stim_groups"] = groups
    for key, cast in (("duration_ms", float), ("n_trials", int)):
        out[key] = _number(p.get(key), key, cast)
    rates = {g["rate_hz"] for g in groups}
    if len(rates) == 1:
        out["rate_hz"] = rates.pop()
    elif not groups and p.get("rate_hz") not in (None, ""):
        out["rate_hz"] = _number(p.get("rate_hz"), "rate_hz", float)
    else:
        out["rate_hz"] = None          # several groups at different rates (see stim_groups)
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
    # The model. Missing = the published model (setups saved before variants existed).
    out["variant"] = check_variant(p.get("variant"), out["snapshot"])
    overlap = set(out["excite"]) & set(out["silence"])
    if overlap:
        raise ValueError(f"{len(overlap)} neuron(s) are in both Stimulate and Silence; "
                         "pick one list for each neuron")
    return out


def groups_text(groups: list[dict[str, Any]]) -> str:
    """'Sugar 100 Hz (21 neurons) + Bitter 40 Hz (21 neurons)'."""
    parts = []
    for g in groups:
        n = len(g["ids"])
        parts.append(f"{g['name']} {g['rate_hz']:g} Hz ({n} neuron{'' if n == 1 else 's'})")
    return " + ".join(parts) or "nothing stimulated"


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
        **{k: v for k, v in params.items() if k != "variant"},
        # The exact model: names, switches and a fingerprint of every code file it uses.
        "variant": variant_record(params["variant"]),
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
    if data.get("format") not in FORMATS_READ:
        raise ValueError(f"{path.name} is not a fly-brain app setup (format {data.get('format')!r})")
    return data


def run_params(setup: dict[str, Any]) -> dict[str, Any]:
    """The checked run parameters of a loaded setup (old or new format)."""
    return validate_params({k: setup.get(k) for k in RUN_KEYS})


def code_check(setup: dict[str, Any], engine_now: dict[str, Any]) -> tuple[bool, str | None]:
    """Has any code the setup's model uses changed since it was saved?

    Returns (same, plain-English warning or None). A setup without a
    "variant" (saved before variants existed) is the published model, whose
    only code file is the engine itself (checked through "engine")."""
    saved_eng = setup.get("engine") or {}
    notes = []
    if (saved_eng.get("name") != engine_now.get("name")
            or saved_eng.get("code_hash") != engine_now.get("code_hash")):
        notes.append(f"was saved with engine '{saved_eng.get('name')}' (version {saved_eng.get('version')}, "
                     f"code {saved_eng.get('code_hash')}); the app is now using '{engine_now.get('name')}' "
                     f"(version {engine_now.get('version')}, code {engine_now.get('code_hash')})")
    saved_var = setup.get("variant")
    if saved_var:
        try:
            now = variant_record(check_variant(saved_var, setup.get("snapshot") or DEFAULT_SNAPSHOT))
        except ValueError as exc:
            return False, f"This setup's model cannot be used any more: {exc}"
        for f, h in (saved_var.get("code") or {}).items():
            if f == "sim/fast_engine.py" and engine_now.get("is_fake"):
                continue                     # the stand-in engine does not use it
            if now["code"].get(f) != h:
                notes.append(f"uses {f}, which has changed since it was saved "
                             f"(code {h} then, {now['code'].get(f)} now)")
    if not notes:
        return True, None
    return False, "This setup " + "; it ".join(notes) + ". Results may differ from when it was saved."


def list_setups(folder: Path | None = None) -> list[dict[str, Any]]:
    out = []
    for f in sorted((folder or SETUP_DIR).glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            out.append({"name": f.stem, "title": f.stem, "error": f"unreadable: {exc}"})
            continue
        var = d.get("variant") or {}
        out.append({"name": d.get("name", f.stem), "title": d.get("title", f.stem),
                    "description": d.get("description", ""), "saved_at": d.get("saved_at"),
                    "engine": d.get("engine"), "snapshot": d.get("snapshot"),
                    "n_excite": len(d.get("excite", [])), "n_silence": len(d.get("silence", [])),
                    "n_groups": len(d.get("stim_groups") or []) or 1,
                    "model": var.get("label") or "Published model"})
    return out
