"""One long-lived simulator process for the Phase 6 "runaway activity" checks.

Plain English
-------------
Building the whole-brain model costs time and memory, so it is built ONCE
here (snapshot 630, one CPU core, because the computer is shared with other
work). The process then waits for "job tickets": small text files named
``queue/<name>.job`` holding the path of one experiment script. It runs that
script with the ready-made ``brain`` handed to it, writes the script's printed
output to ``queue/<name>.log``, and renames the ticket to ``.done`` (or
``.failed``). Before each job it checks free memory and waits if there is
less than 1.5 GB. An empty file ``queue/STOP`` ends the process.

Run:  .venv\\Scripts\\python.exe experiments\\phase6\\runaway\\server.py
"""

import contextlib
import runpy
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from sim.fast_engine import FastBrain  # noqa: E402
from common import free_ram_gb  # noqa: E402

QUEUE = HERE / "queue"
QUEUE.mkdir(exist_ok=True)


def main():
    t0 = time.perf_counter()
    brain = FastBrain(snapshot="630", n_threads=1)
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
        words = ticket.read_text().split()
        script, args = Path(words[0]), words[1:]
        log = ticket.with_suffix(".log")
        print(f"running {script.name} {args}", flush=True)
        t1 = time.perf_counter()
        ok = True
        with open(log, "w", encoding="utf-8", buffering=1) as fh, \
                contextlib.redirect_stdout(fh), contextlib.redirect_stderr(fh):
            sys.argv = [str(script)] + args
            try:
                runpy.run_path(str(script), init_globals={"brain": brain}, run_name="__main__")
            except Exception:
                ok = False
                traceback.print_exc()
        ticket.rename(ticket.with_suffix(".done" if ok else ".failed"))
        print(f"  {'done' if ok else 'FAILED'} in {time.perf_counter() - t1:.0f} s", flush=True)


if __name__ == "__main__":
    main()
