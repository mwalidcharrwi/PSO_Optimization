#!/usr/bin/env bash
# Run the hhl_8 BQSKit follow-up (500-gate chunks, see run_revision_followup.sh) now, alone on the
# machine: the unbudgeted jobs (IBM AI synthesis, verification) are paused with SIGSTOP for the
# 15 minutes and resumed afterwards.  Leaves the same .done marker, so the follow-up skips it.
#     scripts/run_bqskit_hhl8_alone.sh <pid> [<pid> ...]      (pids to pause)
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=. OMP_NUM_THREADS=1
ROOT=results/ibm_revision
id=bqskit_del_hhl_8_s0_chunk500
[ -e "$ROOT/.done/$id" ] && exit 0
kill -STOP "$@" 2>/dev/null
echo "$(date -u +%FT%TZ) paused $* for $id" >> "$ROOT/logs/phaseBC.log"
echo "$(date -u +%FT%TZ) start $id" >> "$ROOT/logs/phaseBC.log"
BQSKIT_CHUNK=500 python -m qcpso.bench.compare_ibm --out "$ROOT/bqskit_del" --methods bqskit_del --circuits hhl_8 \
    --seeds 1 --seed0 0 --time-limit 900 --workers 4 >> "$ROOT/logs/phaseBC_runs.log" 2>&1 && touch "$ROOT/.done/$id"
echo "$(date -u +%FT%TZ) end $id" >> "$ROOT/logs/phaseBC.log"
kill -CONT "$@" 2>/dev/null
echo "$(date -u +%FT%TZ) resumed $*" >> "$ROOT/logs/phaseBC.log"
