#!/bin/sh
# Runs the remaining stages one after another (one simulation process at a time).
# Waits for the R1/R2 chain (started separately) to finish first.
cd "$(dirname "$0")"
PY=../../.venv/Scripts/python.exe
until grep -qE "wrote|Traceback|Error" results/r1r2_mech100.log 2>/dev/null; do sleep 5; done
$PY reproduce.py realism mech100 > results/realism_mech100.log 2>&1
$PY reproduce.py weight > results/weight_scan.log 2>&1
$PY reproduce.py mech > results/scan_mech.log 2>&1
$PY loops.py > results/loops.log 2>&1
$PY make_figure.py > results/make_figure.log 2>&1
echo QUEUE_DONE
