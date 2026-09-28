#!/usr/bin/env bash
# Final HyPSO-QCO v2 runs for the related-work comparison (results/ibm_literature).
# GUOQ / QUESO / TKET / Qiskit were run with qcpso.bench.compare_ibm into sibling folders;
# this script waits until no other comparison job is running, then runs HyPSO-QCO alone
# on the machine (equal wall-clock budget: 900 s per circuit).
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
OUT=results/ibm_literature
SMALL=mult_8,heisenberg_8,add_17,qae_17,qft_16,hubbard_8,hhl_8
while pgrep -f "compare_ibm --out $OUT/(guoq|queso)" > /dev/null; do sleep 30; done

# 1. main runs, all ten circuits, 4 resynthesis workers
python -m qcpso.bench.compare_ibm --out $OUT/hypso --methods hypso --time-limit 900 --workers 4 \
    > $OUT/logs/hypso.log 2>&1

# 2. compute-matched variant (one resynthesis worker), three circuits at a time
i=0
for c in ${SMALL//,/ }; do
    python -m qcpso.bench.compare_ibm --out $OUT/hypso_w1/$c --circuits $c --methods hypso_w1 \
        --time-limit 900 --workers 1 > $OUT/logs/hypso_w1_$c.log 2>&1 &
    i=$((i + 1))
    if [ $((i % 3)) -eq 0 ]; then wait; fi
done
wait

# 3. ablation: memetic phase only (no swarm phase), 4 workers
python -m qcpso.bench.compare_ibm --out $OUT/ablation --circuits $SMALL --methods hypso_noswarm \
    --time-limit 900 --workers 4 > $OUT/logs/ablation.log 2>&1
echo "all HyPSO-QCO runs finished"
