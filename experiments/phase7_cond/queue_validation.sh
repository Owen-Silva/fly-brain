#!/bin/sh
# Runs every validation step one after another (never two brains at once).
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
R=experiments/phase7_cond/run_cond.py
L=experiments/phase7_cond/results
$PY -u $R fit experiments/phase7_cond/fit_confirm.json 30 > $L/log_fit_confirm.txt 2>&1
$PY -u $R run sep > $L/log_sep.txt 2>&1
$PY -u $R volley sep > $L/log_volley_sep.txt 2>&1
for v in sep_exc0.9 sep_exc1.1 sep_inh0.9 sep_inh1.1; do
  $PY -u $R run $v --seeds 0 > $L/log_$v.txt 2>&1
done
$PY -u $R run g2 sugar100_bitter120 ir94e_200Hz dm1_both_150Hz > $L/log_q1_g2_rest.txt 2>&1
$PY -u $R volley g2 > $L/log_volley_g2.txt 2>&1
echo ALLDONE > $L/queue_done.txt
