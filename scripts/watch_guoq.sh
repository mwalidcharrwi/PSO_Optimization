#!/usr/bin/env bash
# Records, every 30 s, the CNOT count of every running GUOQ instance's best-so-far
# circuit (out/latest_sol__in.qasm) for anytime curves: "epoch_s,workdir,cx,mtime_s".
cd "$(dirname "$0")/.."
OUT=results/ibm_revision/guoq_trace.csv
[ -e "$OUT" ] || echo "epoch_s,workdir,cx,mtime_s" > "$OUT"
while true; do
  now=$(date +%s)
  for f in results/ibm_revision/guoq_*/work/*/out/latest_sol__in.qasm; do
    [ -e "$f" ] || continue
    m=$(stat -c %Y "$f")
    echo "$now,$(dirname "$(dirname "$f")"),$(grep -c '^cx ' "$f"),$m" >> "$OUT"
  done
  echo "$now,$(free -m | awk '/Mem:/{print $3","$7}')" >> results/ibm_revision/logs/mem.csv
  pgrep -f run_revision_guoq.sh > /dev/null || exit 0
  sleep 30
done
