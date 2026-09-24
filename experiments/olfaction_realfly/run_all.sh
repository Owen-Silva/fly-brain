#!/bin/sh
# Runs every simulation of this lane one after the other (one whole brain in memory at a time).
cd "$(dirname "$0")"
PY=../../.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
$PY run_odours.py alln_A
$PY run_gain.py
$PY run_odours.py alln_A_noAPL
$PY run_odours.py none_A none_evoked
$PY run_odours.py alln_B
$PY run_odours.py alln_B_noAPL
echo ALL_DONE
