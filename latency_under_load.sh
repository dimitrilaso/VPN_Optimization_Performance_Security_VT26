#!/bin/bash
set -euo pipefail

# ---------- CONFIG ----------
TARGET_PING="192.168.9.10"        # Site A host to ping
IPERF_SERVER="192.168.9.10"       # Site A iperf3 server IP (same host is fine)
CAP_MBPS=200                      # <-- set this to your measured tunnel capacity (in Mbps)

LOAD_PCTS=(25 50 75)              # load levels (% of capacity)
BATCHES=10                        # batches per load level
PING_COUNT=100                    # pings per batch
WARMUP_SEC=5                      # iperf warm-up before ping starts
DURATION_SEC=120                  # iperf duration per batch (cover pings + warm-up margin)
SLEEP_BETWEEN=20                  # pause between batches
OUTDIR="./latency_under_load_logs"
# -----------------------------

mkdir -p "$OUTDIR"

cleanup() {
  pkill -f "iperf3 -u -c $IPERF_SERVER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for pct in "${LOAD_PCTS[@]}"; do
  rate_mbps=$(awk -v c="$CAP_MBPS" -v p="$pct" 'BEGIN{printf "%.2f", c*p/100.0}')
  subdir="$OUTDIR/load_${pct}pct_${rate_mbps}Mbps"
  mkdir -p "$subdir"

  echo "=== Load ${pct}% (~${rate_mbps} Mbps UDP) ==="
  for i in $(seq 1 $BATCHES); do
    ts=$(date +"%Y%m%d_%H%M%S")
    iperf_log="$subdir/iperf_${pct}pct_batch${i}_$ts.txt"
    ping_log="$subdir/ping_${pct}pct_batch${i}_$ts.txt"

    echo "[${ts}] Starting iperf3 background at ${rate_mbps} Mbps (UDP) ..."
    # Run iperf3 a bit longer than ping duration
    (iperf3 -u -c "$IPERF_SERVER" -b "${rate_mbps}M" -t "$DURATION_SEC" -i 1 --get-server-output > "$iperf_log" 2>&1) & iperf_pid=$!

    echo "Warming up ${WARMUP_SEC}s..."
    sleep "$WARMUP_SEC"

    echo "Running ping batch $i/$BATCHES (${PING_COUNT} packets) to $TARGET_PING ..."
    ping -c "$PING_COUNT" "$TARGET_PING" > "$ping_log"

    echo "Waiting for iperf3 to finish..."
    wait "$iperf_pid" || true

    echo "Saved: $ping_log"
    echo "Saved: $iperf_log"

    if [ "$i" -lt "$BATCHES" ]; then
      echo "Sleeping ${SLEEP_BETWEEN}s before next batch..."
      sleep "$SLEEP_BETWEEN"
    fi
  done
done

echo "✅ All under-load latency batches completed. Logs in $OUTDIR"
