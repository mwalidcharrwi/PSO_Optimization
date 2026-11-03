#!/usr/bin/env bash
# Revision, phases B and C (each run alone on the 4-core machine, after phase A).
#   B: HyPSO-QCO, resynthesis-only configuration (hypso_rs, pre-specified for mapped circuits):
#      fresh seeds 1-3 on the seven smaller circuits, seed 1 on the three large circuits,
#      and Z-slot sparsification off (seed 1) on the seven smaller circuits.
#   C: BQSKit deletion-only workflow, 15 min and 4 workers per circuit; the instantiation level
#      (1 or 2) is chosen by a pilot on mult_8 (fewer ECR gates, then fewer gates).
# Resumable: finished jobs leave markers in results/ibm_revision/.done/.
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=. OMP_NUM_THREADS=1
ROOT=results/ibm_revision
mkdir -p "$ROOT/.done" "$ROOT/logs"
while pgrep -f run_revision_guoq.sh > /dev/null || pgrep -f qoptimizer.Optimizer > /dev/null; do sleep 60; done
echo "$(date -u +%FT%TZ) phase B start" >> "$ROOT/logs/phaseBC.log"

job() {  # out method circuit seed
  local out=$1 m=$2 c=$3 s=$4 id="${2}_${3}_s${4}"
  [ -e "$ROOT/.done/$id" ] && return 0
  echo "$(date -u +%FT%TZ) start $id" >> "$ROOT/logs/phaseBC.log"
  python -m qcpso.bench.compare_ibm --out "$ROOT/$out" --methods "$m" --circuits "$c" --seeds 1 --seed0 "$s" \
      --time-limit 900 --workers 4 >> "$ROOT/logs/phaseBC_runs.log" 2>&1 && touch "$ROOT/.done/$id"
  echo "$(date -u +%FT%TZ) end $id" >> "$ROOT/logs/phaseBC.log"
}

SMALL="mult_8 heisenberg_8 add_17 qae_17 qft_16 hubbard_8 hhl_8"
LARGE="heisenberg_32 grover_10 hubbard_18"
for c in $SMALL; do job hypso_rs hypso_rs $c 1; done
for c in $LARGE; do job hypso_rs hypso_rs $c 1; done
for c in $SMALL; do job hypso_rs_nosparse hypso_rs_nosparse $c 1; done
for s in 2 3; do for c in $SMALL; do job hypso_rs hypso_rs $c $s; done; done
echo "$(date -u +%FT%TZ) phase C start" >> "$ROOT/logs/phaseBC.log"

job bqskit_del bqskit_del mult_8 0
job bqskit_del bqskit_del2 mult_8 0
LVL=$(python - <<'PY'
import csv
rows = {r["method"]: r for r in csv.DictReader(open("results/ibm_revision/bqskit_del/results.csv")) if r.get("ecr")}
key = lambda m: (int(rows[m]["ecr"]), int(rows[m]["gates"])) if m in rows else (10**9, 10**9)
print("bqskit_del2" if key("bqskit_del2") < key("bqskit_del") else "bqskit_del")
PY
)
echo "$(date -u +%FT%TZ) BQSKit pilot chose $LVL" >> "$ROOT/logs/phaseBC.log"
for c in heisenberg_8 add_17 qae_17 qft_16 hubbard_8 hhl_8 $LARGE; do job bqskit_del $LVL $c 0; done
echo "$(date -u +%FT%TZ) phase C done" >> "$ROOT/logs/phaseBC.log"
