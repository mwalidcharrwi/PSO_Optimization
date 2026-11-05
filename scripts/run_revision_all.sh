#!/usr/bin/env bash
# Revision master: phase A (GUOQ), then phases B and C (HyPSO-QCO, BQSKit).  Resumable.
cd "$(dirname "$0")/.."
export GUOQ_DIR=${GUOQ_DIR:-/home/user/guoq}
mkdir -p results/ibm_revision/logs
scripts/watch_guoq.sh &
scripts/run_revision_guoq.sh
scripts/run_revision_hypso_bqskit.sh
echo "$(date -u +%FT%TZ) all revision phases done" >> results/ibm_revision/logs/phaseBC.log
