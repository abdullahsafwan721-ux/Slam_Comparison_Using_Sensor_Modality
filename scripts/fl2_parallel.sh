#!/usr/bin/env bash
# Host-side helper: start N runs of one sequence in N parallel fastlio2 containers
# (each container has its own roscore), wait for all, print a one-line status per run.
#   bash scripts/fl2_parallel.sh <N> <runner> <args...>
#   bash scripts/fl2_parallel.sh 5 run_fastlio2.sh /config/fastlio2/lili.yaml /data/lili/KA_Urban_Schloss_1.bag lili6_schloss1
#   bash scripts/fl2_parallel.sh 5 run_fastlio2_utbm.sh /data/utbm/utbm_20180719.bag utbm8
# Extra docker args (e.g. a mount) can be passed in DOCKER_ARGS; SERVICE=fastlivo2 for FAST-LIVO2.
set -uo pipefail
N=$1; RUNNER=$2; shift 2
cd "$(dirname "$0")/.."
pids=()
for k in $(seq 1 "$N"); do
  docker compose run --rm -T ${DOCKER_ARGS:-} -e RUN_START="$k" -e RUNS=1 "${SERVICE:-fastlio2}" \
      bash "/scripts/$RUNNER" "$@" < /dev/null > "/tmp/fl2_parallel_$$_$k.log" 2>&1 &
  pids+=($!)
  sleep 2
done
for k in $(seq 1 "$N"); do wait "${pids[$((k-1))]}"; grep -E '^wrote|^!!' "/tmp/fl2_parallel_$$_$k.log" | sed "s/^/[run $k] /"; done
