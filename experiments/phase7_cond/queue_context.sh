#!/bin/sh
# Context runs for the sensitivity question, after queue_resume.sh has finished.
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
R=experiments/phase7_cond/run_cond.py
L=experiments/phase7_cond/results
CHECKS="sugar_100Hz sugar_200Hz water_200Hz bitter_200Hz sugar100_bitter120 ir94e_200Hz dm1_both_150Hz"
while [ ! -f $L/queue_done.txt ]; do sleep 30; done
for v in sep_all0.9 sep_all1.1 cur_ref cur_exc0.9 cur_exc1.1 cur_inh0.9 cur_inh1.1; do
  $PY -u $R run $v $CHECKS --seeds 0 >> $L/log_$v.txt 2>&1
done
echo ALLDONE > $L/queue_context_done.txt
