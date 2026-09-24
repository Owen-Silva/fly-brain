#!/usr/bin/env bash
# Runs the remaining held-out steps one after another (one brain in memory at a
# time), in priority order. Every step saves as it goes and skips finished work,
# so the queue can be stopped and restarted.
#   e = necessity screen, non-JON neurons only; d = sufficiency, non-JON only
#   a/c = the short versions of tests A and C; B, F = as in run_heldout.py
# Third version (18:20): waits for any running held-out step to finish, then runs
# the variants that can differ, the held-out feeding tests and the Phase 6 checks
# before the lower-priority items. check_changed.py showed that none of the 150
# neurons changed by al_ln_literature fires in any grooming condition, so that
# variant only gets a confirmation run (test c + F).
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/Scripts/python.exe
LOG=experiments/heldout/results/logs
export PYTHONIOENCODING=utf-8
while powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*heldout*' }) { exit 0 } else { exit 1 }"; do sleep 10; done
run() {
  echo "### $(date +%H:%M:%S) start $*" >> $LOG/queue.log
  $PY -u experiments/heldout/run_heldout.py "$@" > "$LOG/$1_$3.log" 2>&1
  echo "### $(date +%H:%M:%S) end $* (exit $?)" >> $LOG/queue.log
}
step() {   # step NAME SCRIPT ARGS...
  local name=$1; shift
  echo "### $(date +%H:%M:%S) start $name" >> $LOG/queue.log
  $PY -u "$@" > "$LOG/$name.log" 2>&1
  echo "### $(date +%H:%M:%S) end $name (exit $?)" >> $LOG/queue.log
}
run al_ln_literature --tests cF
run delays --tests aBcF
run adaptation --tests aBcF
step feeding experiments/heldout/feeding_heldout.py none al_ln_literature+da_5ht_literature al_ln_literature
step robustness experiments/heldout/robustness.py
run none --tests e
run celltype --tests cF
run gap --tests cF
step feeding_phase7 experiments/heldout/feeding_heldout.py delays adaptation
run none --tests d
echo "### $(date +%H:%M:%S) queue finished" >> $LOG/queue.log
