"""One long-lived simulator process shared by the Phase 5 competition and
olfaction scripts.

Plain English
-------------
Building the whole-brain model takes time and memory, and this laptop is
short on memory, so the rules say: build it ONCE and reuse it. This script
does exactly that. It builds one FastBrain (snapshot 630, 2 threads), then
waits for "job tickets": small text files dropped into the ``queue`` folder
next to this file. Each ticket holds the path of one experiment script. The
server runs that script with the ready-made ``brain`` handed to it, writes
everything the script prints to ``queue/<ticket>.log``, and renames the
ticket to ``.done`` (or ``.failed`` with the error) when it finishes.

Usage (run it in the background):
    .venv\\Scripts\\python.exe experiments\\phase5\\competition\\job_server.py
Submit a job:  write the script path into queue\\<name>.job
Stop:          create an empty file queue\\STOP
"""

import contextlib
import runpy
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from sim.fast_engine import FastBrain  # noqa: E402

QUEUE = Path(__file__).resolve().parent / "queue"
QUEUE.mkdir(exist_ok=True)


def free_ram_gb():
    """Free physical memory in GB (Windows), or None if it cannot be read."""
    try:
        import ctypes

        class MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEMSTAT()
        m.dwLength = ctypes.sizeof(MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / 1024 ** 3
    except Exception:
        return None


def main():
    t0 = time.perf_counter()
    brain = FastBrain(snapshot="630", n_threads=2)
    print(f"brain built in {time.perf_counter() - t0:.1f} s: {brain.n_neurons} neurons, "
          f"{brain.n_connections} connections", flush=True)
    while True:
        if (QUEUE / "STOP").exists():
            print("STOP file found, exiting", flush=True)
            return
        tickets = sorted(QUEUE.glob("*.job"))
        if not tickets:
            time.sleep(3)
            continue
        ticket = tickets[0]
        ram = free_ram_gb()
        if ram is not None and ram < 1.5:
            print(f"free RAM {ram:.2f} GB < 1.5 GB, waiting before {ticket.name}", flush=True)
            time.sleep(30)
            continue
        words = ticket.read_text().split()          # "script.py [args...]"
        script, args = Path(words[0]), words[1:]
        log = ticket.with_suffix(".log")
        print(f"running {script} {args} (ticket {ticket.name})", flush=True)
        t1 = time.perf_counter()
        ok = True
        with open(log, "w", encoding="utf-8", buffering=1) as fh, \
                contextlib.redirect_stdout(fh), contextlib.redirect_stderr(fh):
            try:
                # forget helper modules from earlier jobs so edits take effect
                for name in [m for m, mod in sys.modules.items()
                             if str(getattr(mod, "__file__", "") or "").startswith(str(QUEUE.parents[1]))]:
                    del sys.modules[name]
                sys.argv = [str(script)] + args
                runpy.run_path(str(script), init_globals={"brain": brain}, run_name="__main__")
            except BaseException:  # noqa: BLE001 - report every failure in the log
                ok = False
                traceback.print_exc()
        ticket.rename(ticket.with_suffix(".done" if ok else ".failed"))
        print(f"{'finished' if ok else 'FAILED'} {ticket.name} in "
              f"{time.perf_counter() - t1:.0f} s", flush=True)


if __name__ == "__main__":
    main()
