#!/usr/bin/env bash
# Replay one bag through FAST-LIO2 and record /Odometry.
#   run_fastlio2.sh <config.yaml> <in.bag> <seq-name> [rate]
#   RUNS=5 run_fastlio2.sh ...          repeat and write _r1.._rN
# Writes $OUTDIR/<seq>_r<N>.bag (+ .algo.log, .params.yaml); OUTDIR defaults to /output/fastlio2
set -eo pipefail
CFG=$1; BAG=$2; SEQ=$3; RATE=${4:-1.0}; RUNS=${RUNS:-1}
source /opt/ros/noetic/setup.bash
source /ws/devel/setup.bash
OUTDIR=${OUTDIR:-/output/fastlio2}; mkdir -p "$OUTDIR"
[ -f "$CFG" ] || { echo "!! config not found: $CFG"; exit 1; }
[ -f "$BAG" ] || { echo "!! bag not found: $BAG"; exit 1; }

# FAST-LIO installs its own SIGINT handler (so ros::shutdown is never called) and,
# with use_sim_time, its main loop then blocks in rate.sleep() on a /clock that
# stopped when the bag ended. SIGINT alone never returns, so escalate after 10 s.
# The odometry bag is already closed by then; nothing is lost.
stop() {
  kill -INT "$@" 2>/dev/null || true
  for _ in $(seq 20); do kill -0 "$@" 2>/dev/null || break; sleep 0.5; done
  kill -KILL "$@" 2>/dev/null || true
  wait "$@" 2>/dev/null || true
}

for r in $(seq 1 "$RUNS"); do
  OUT=$OUTDIR/${SEQ}_r${r}.bag
  echo "=== $SEQ run $r/$RUNS ==="
  roscore >/dev/null 2>&1 & CORE=$!
  until rostopic list >/dev/null 2>&1; do sleep 0.5; done
  rosparam set /use_sim_time true          # must be set BEFORE the node starts

  rosparam load "$CFG"
  # The paper's default configuration, Section VI-A. These are set here rather
  # than taken from a launch file because the upstream launch files disagree:
  # mapping_avia/horizon/mid360 use point_filter_num 3, not the paper's 4.
  rosparam set /feature_extract_enable false      # direct method
  rosparam set /point_filter_num 4                # 1:4 temporal downsample
  rosparam set /max_iteration 3
  rosparam set /filter_size_surf 0.5              # spatial downsample l = 0.5 m
  rosparam set /filter_size_map 0.5
  rosparam set /cube_side_length 1000.0           # local map size L = 1000 m
  rosparam set /runtime_pos_log_enable false
  rosparam dump "${OUT%.bag}.params.yaml"         # what was actually used

  rosrun fast_lio fastlio_mapping > "${OUT%.bag}.algo.log" 2>&1 & ALGO=$!
  sleep 5                                  # let it subscribe before data flows
  rosbag record -O "$OUT" /Odometry __name:=rec >/dev/null 2>&1 & REC=$!
  sleep 1
  rosbag play --clock -r "$RATE" -d 1 "$BAG"
  sleep 3                                  # drain the last scans
  rosnode kill /rec >/dev/null 2>&1 || true; wait $REC 2>/dev/null || true
  kill -0 $ALGO 2>/dev/null || echo "!! fastlio_mapping had already exited -- see ${OUT%.bag}.algo.log"
  stop $ALGO
  stop $CORE
  n=$(rosbag info -y -k messages "$OUT" 2>/dev/null || echo 0)
  echo "wrote $OUT ($n odometry messages)"
  [ "${n:-0}" -gt 0 ] || echo "!! no /Odometry recorded -- check topics with rosbag info"
done
