#!/usr/bin/env bash
# Revision follow-up, after scripts/run_revision_all.sh has finished:
#   BQSKit deletion on hhl_8 again with 500-gate chunks.  With the default 3000-gate chunks its first
#   chunk did not finish one sweep in 15 minutes and was cancelled, so nothing was kept
#   (log: results/ibm_revision/bqskit_del/hhl_8_bqskit_del_s0_chunk3000.log).  The later row wins in
#   the report.  Runs alone on the machine, like every BQSKit run.
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=. OMP_NUM_THREADS=1
ROOT=results/ibm_revision
until grep -q "all revision phases done" "$ROOT/logs/phaseBC.log" 2>/dev/null; do sleep 30; done
while pgrep -f "run_revision_all.sh|run_revision_hypso_bqskit.sh|run_ai_synthesis.py" > /dev/null; do sleep 30; done
id=bqskit_del_hhl_8_s0_chunk500
if [ ! -e "$ROOT/.done/$id" ]; then
  echo "$(date -u +%FT%TZ) start $id" >> "$ROOT/logs/phaseBC.log"
  BQSKIT_CHUNK=500 python -m qcpso.bench.compare_ibm --out "$ROOT/bqskit_del" --methods bqskit_del --circuits hhl_8 \
      --seeds 1 --seed0 0 --time-limit 900 --workers 4 >> "$ROOT/logs/phaseBC_runs.log" 2>&1 && touch "$ROOT/.done/$id"
  echo "$(date -u +%FT%TZ) end $id" >> "$ROOT/logs/phaseBC.log"
fi
echo "$(date -u +%FT%TZ) follow-up done" >> "$ROOT/logs/phaseBC.log"
