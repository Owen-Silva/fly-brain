#!/bin/sh
# Second part of the validation queue (replaces the tail of queue_validation.sh,
# which ran every condition, including the left/right steering ones, for the
# sensitivity variants too). One brain at a time.
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
R=experiments/phase7_cond/run_cond.py
L=experiments/phase7_cond/results
CHECKS="sugar_100Hz sugar_200Hz water_200Hz bitter_200Hz sugar100_bitter120 ir94e_200Hz dm1_both_150Hz"
# wait for the still-running "run sep" (started by queue_validation.sh) to end
while powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*run_cond.py*' }) { exit 0 } else { exit 1 }"; do
  sleep 20
done
$PY -u $R run sep >> $L/log_sep.txt 2>&1          # resumes; no-op if complete
$PY -u $R volley sep > $L/log_volley_sep.txt 2>&1
for v in sep_exc0.9 sep_exc1.1 sep_inh0.9 sep_inh1.1; do
  $PY -u $R run $v $CHECKS --seeds 0 > $L/log_$v.txt 2>&1
done
$PY -u $R run g2 sugar100_bitter120 ir94e_200Hz dm1_both_150Hz > $L/log_q1_g2_rest.txt 2>&1
$PY -u $R volley g2 > $L/log_volley_g2.txt 2>&1
echo ALLDONE > $L/queue_done.txt
