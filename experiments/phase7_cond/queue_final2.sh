#!/bin/sh
# Replaces queue_final.sh (2026-09-23 ~09:15) because the machine is running
# 2-3x slower than in the morning: the context runs now use the five taste
# checks only (the slow Ir94e/DM1 runs are kept for the required +-10% runs).
# One brain at a time: waits until no other run_cond.py process is alive.
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
R=experiments/phase7_cond/run_cond.py
L=experiments/phase7_cond/results
CHECKS="sugar_100Hz sugar_200Hz water_200Hz bitter_200Hz sugar100_bitter120 ir94e_200Hz dm1_both_150Hz"
TASTE="sugar_100Hz sugar_200Hz water_200Hz bitter_200Hz sugar100_bitter120"
while powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*run_cond.py*' }) { exit 0 } else { exit 1 }"; do
  sleep 20
done
# 1. +-10% of each tuned scale (required): finish these, all 7 conditions
for v in sep_inh0.9 sep_inh1.1; do
  $PY -u $R run $v $CHECKS --seeds 0 >> $L/log_$v.txt 2>&1
done
# 2. context, taste checks only, most important first
for v in cur_exc0.9 cur_exc1.1 sep_all0.9 sep_all1.1 cur_ref cur_inh0.9 cur_inh1.1; do
  $PY -u $R run $v $TASTE --seeds 0 >> $L/log_$v.txt 2>&1
done
echo DONE > $L/queue_final_main_done.txt
# 3. optional: the rest of question 1's one-scale x2 model
$PY -u $R volley g2 > $L/log_volley_g2.txt 2>&1
$PY -u $R run g2 sugar100_bitter120 ir94e_200Hz dm1_both_150Hz >> $L/log_q1_g2_rest.txt 2>&1
echo ALLDONE > $L/queue_final_done.txt
