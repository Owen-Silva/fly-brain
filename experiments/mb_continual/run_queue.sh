#!/usr/bin/env bash
# Runs the secondary analyses one after another (one heavy process at a time).
# Each python script waits for >= 1.5 GB free RAM before it starts.
cd "$(dirname "$0")"
PY=../../.venv/Scripts/python.exe
for v in k2 k3 k7.5 k10 T0.02 T0.1 T0.2 T0.5 syn5 kcnorm setA; do
  $PY run_incremental.py "$v" --seeds 20 > "results/raw/incr_$v.log" 2>&1 || echo "FAILED $v"
  echo "variant $v finished"
done
$PY run_capacity.py --seeds 20 --mlp-seeds 5 > results/raw/capacity.log 2>&1 || echo "FAILED capacity"
echo "capacity finished"
$PY run_mnist.py --seeds 5 --mlp-seeds 3 > results/raw/mnist.log 2>&1 || echo "FAILED mnist"
echo "mnist finished"
echo "QUEUE DONE"
