#!/bin/sh
# Resume after the 03:09 reboot (2026-09-23). Completed runs are skipped by
# run_cond.py itself (it checks results/counts). One brain at a time: every
# step runs after the previous one has exited.
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
R=experiments/phase7_cond/run_cond.py
L=experiments/phase7_cond/results
CHECKS="sugar_100Hz sugar_200Hz water_200Hz bitter_200Hz sugar100_bitter120 ir94e_200Hz dm1_both_150Hz"
# whole-brain tests (the old ones unchanged, plus the new ones)
$PY -m pytest tests/test_realism.py tests/test_realism_conductance.py -m slow -q > $L/log_slow_tests.txt 2>&1
# +-10% sensitivity of the two tuned scales (seed 0 x 30 trials)
for v in sep_exc0.9 sep_exc1.1 sep_inh0.9 sep_inh1.1; do
  $PY -u $R run $v $CHECKS --seeds 0 >> $L/log_$v.txt 2>&1
done
# question 1, the remaining checks for the one-scale x2 model
$PY -u $R run g2 sugar100_bitter120 ir94e_200Hz dm1_both_150Hz > $L/log_q1_g2_rest.txt 2>&1
$PY -u $R volley g2 > $L/log_volley_g2.txt 2>&1
echo ALLDONE > $L/queue_done.txt
