"""Paths into the rest of the project, and a safe way to import other lanes' modules
(several lanes each have a file called common.py, so they are loaded by path under unique
names). vhc only READS other lanes' code and results; it never writes there."""
from __future__ import annotations

import ctypes
import importlib.util
import sys
from pathlib import Path

VHC = Path(__file__).resolve().parent
ROOT = VHC.parent
RESULTS = VHC / "results"
MINIMAL = ROOT / "experiments" / "minimal_circuit"
MB = ROOT / "experiments" / "mb_continual"
ENERGY = ROOT / "experiments" / "energy_budget"

_cache = {}


def load_module(alias, path):
    """Import ``path`` as module ``alias`` with its own folder on sys.path for its imports."""
    if alias in _cache:
        return _cache[alias]
    path = Path(path)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod            # dataclasses look the module up while it loads
    saved = sys.modules.get("common")
    sys.path.insert(0, str(path.parent))
    no_pyc = sys.dont_write_bytecode
    sys.dont_write_bytecode = True      # never write cache files into other lanes' folders
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = no_pyc
        sys.path.remove(str(path.parent))
        if saved is not None:
            sys.modules["common"] = saved
        else:
            sys.modules.pop("common", None)
    _cache[alias] = mod
    return mod


def free_ram_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 1e9


def wait_for_ram(min_gb=1.5, poll_s=20):
    import time
    while (f := free_ram_gb()) < min_gb:
        print(f"  waiting for RAM: {f:.2f} GB free (< {min_gb} GB)", flush=True)
        time.sleep(poll_s)
