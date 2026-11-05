#!/usr/bin/env bash
# Revision, phase A: GUOQ runs (two lanes in parallel, ~2 cores each).
#   * 60 min, seed 0, all ten circuits (snapshots at 1, 5, 15 and 30 min);
#   * 15 min, seeds 1 and 2, the seven smaller circuits;
#   * TKET -> GUOQ, 15 min in total, the three large circuits.
# Resumable: a finished job leaves a marker in results/ibm_revision/.done/.
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=. OMP_NUM_THREADS=1 GUOQ_DIR=${GUOQ_DIR:-/home/user/guoq}
ROOT=results/ibm_revision
mkdir -p "$ROOT/.done" "$ROOT/logs"

job() {  # lane circuit method seed time_limit snapshots heap port
  local lane=$1 c=$2 m=$3 s=$4 t=$5 snaps=$6 heap=$7 port=$8
  local id="${lane}_${c}_${m}_s${s}_t${t}"
  [ -e "$ROOT/.done/$id" ] && return 0
  rm -rf "$ROOT/guoq_$lane/work/${c}_${m}_s${s}" "$ROOT/guoq_$lane/work/${c}_${m}_s${s}_server.log"   # no stale files
  echo "$(date -u +%FT%TZ) start $id" >> "$ROOT/logs/lane_${lane}.log"
  GUOQ_HEAP=$heap python -m qcpso.bench.compare_ibm --out "$ROOT/guoq_$lane" --methods "$m" --circuits "$c" \
      --seeds 1 --seed0 "$s" --time-limit "$t" --snapshots "$snaps" --port "$port" \
      >> "$ROOT/logs/lane_${lane}.log" 2>&1 && touch "$ROOT/.done/$id"
  echo "$(date -u +%FT%TZ) end $id" >> "$ROOT/logs/lane_${lane}.log"
}

lane_a() {
  for c in hubbard_18 grover_10; do job a $c guoq 0 3600 60,300,900,1800 6g 8101; done
  for c in heisenberg_32 hhl_8 hubbard_8; do job a $c guoq 0 3600 60,300,900,1800 4g 8101; done
  for cs in mult_8:1 mult_8:2 heisenberg_8:1 heisenberg_8:2 add_17:1 add_17:2 qae_17:1 qae_17:2; do
    job a "${cs%%:*}" guoq "${cs##*:}" 900 60,300 3g 8101
  done
}

lane_b() {
  for c in mult_8 heisenberg_8 add_17 qae_17 qft_16; do job b $c guoq 0 3600 60,300,900,1800 3g 8102; done
  for cs in qft_16:1 qft_16:2 hubbard_8:1 hubbard_8:2 hhl_8:1 hhl_8:2; do
    job b "${cs%%:*}" guoq "${cs##*:}" 900 60,300 3g 8102
  done
  for c in heisenberg_32 grover_10 hubbard_18; do job b $c tket_guoq 0 900 "" 6g 8102; done
}

lane_a & lane_b & wait
echo "$(date -u +%FT%TZ) phase A done" >> "$ROOT/logs/phaseA.log"
