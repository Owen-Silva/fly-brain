#!/usr/bin/env bash
# Runs the remaining whole-brain jobs one after another (one brain in memory at a time).
# Waits for step 2 (main stage) to finish first.
cd "$(dirname "$0")" || exit 1
PY=../../.venv/Scripts/python.exe
until grep -qE "^finished|Traceback" results/s2_main.log; do sleep 5; done
$PY s3_localise_783.py > results/s3_localise.log 2>&1
$PY s6_ir94e_783.py > results/s6_ir94e.log 2>&1
$PY s5_wsyn_783.py > results/s5_wsyn.log 2>&1
$PY s2_runaway_783.py lr > results/s2_lr.log 2>&1
echo "queue done"
