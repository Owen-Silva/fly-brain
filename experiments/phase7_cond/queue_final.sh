#!/bin/sh
# Final queue (2026-09-23, after the reboot and a slow spell): replaces the
# unfinished parts of queue_resume.sh and queue_context.sh, in priority order.
# Completed runs are skipped by run_cond.py itself. One brain at a time: it
# first waits until no other run_cond.py process is alive.
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
R=experiments/phase7_cond/run_cond.py
L=experiments/phase7_cond/results
CHECKS="sugar_100Hz sugar_200Hz water_200Hz bitter_200Hz sugar100_bitter120 ir94e_200Hz dm1_both_150Hz"
while powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*run_cond.py*' }) { exit 0 } else { exit 1 }"; do
  sleep 20
done
# 1. +-10% of each tuned scale (required)
for v in sep_exc1.1 sep_inh0.9 sep_inh1.1; do
  $PY -u $R run $v $CHECKS --seeds 0 >> $L/log_$v.txt 2>&1
done
# 2. context: both scales together, and the paper's own model with E or I scaled
for v in sep_all0.9 sep_all1.1 cur_ref cur_exc0.9 cur_exc1.1 cur_inh0.9 cur_inh1.1; do
  $PY -u $R run $v $CHECKS --seeds 0 >> $L/log_$v.txt 2>&1
done
echo DONE > $L/queue_final_main_done.txt
# 3. optional: the rest of question 1's one-scale x2 model
$PY -u $R volley g2 > $L/log_volley_g2.txt 2>&1
$PY -u $R run g2 sugar100_bitter120 ir94e_200Hz dm1_both_150Hz >> $L/log_q1_g2_rest.txt 2>&1
echo ALLDONE > $L/queue_final_done.txt
