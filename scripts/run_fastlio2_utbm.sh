#!/usr/bin/env bash
# UTBM: velodyne_pointcloud must run alongside FAST-LIO2, because the bag holds
# raw packets rather than point clouds.
#    run_fastlio2_utbm.sh <in.bag> <seq-name>
# The bag stamps each scan with its LAST packet (point times come out negative);
# utbm_restamp.py re-stamps it with the first one so FAST-LIO's scan start is right
# (UTBM_RESTAMP=0 restores the pre-2026-10-09 behaviour).
set -eo pipefail
BAG=$1; SEQ=$2; RUNS=${RUNS:-1}
source /opt/ros/noetic/setup.bash; source /ws/devel/setup.bash
OUTDIR=${OUTDIR:-/output/fastlio2}; mkdir -p "$OUTDIR"
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

R0=${RUN_START:-1}                       # first run index (parallel containers: RUN_START=k RUNS=1)
for r in $(seq "$R0" $((R0 + RUNS - 1))); do
  OUT=$OUTDIR/${SEQ}_r${r}.bag
  echo "=== $SEQ run $r ==="
  roscore >/dev/null 2>&1 & CORE=$!
  until rostopic list >/dev/null 2>&1; do sleep 0.5; done
  rosparam set /use_sim_time true
  roslaunch /config/fastlio2/utbm_convert.launch > "${OUT%.bag}.convert.log" 2>&1 & CONV=$!
  REMAP=(); RS=""
  if [ "${UTBM_RESTAMP:-1}" = 1 ]; then
    python3 /scripts/utbm_restamp.py >> "${OUT%.bag}.convert.log" 2>&1 & RS=$!
    REMAP=(/hdl32e_left/velodyne_packets:=/hdl32e_left/velodyne_packets_orig)
  fi
  sleep 5
  rosparam load "${UTBM_CFG:-/config/fastlio2/utbm.yaml}"   # UTBM_CFG: diagnostic variants only
  rosparam set /feature_extract_enable false
  rosparam set /point_filter_num 4
  rosparam set /max_iteration 3
  rosparam set /filter_size_surf 0.5
  rosparam set /filter_size_map 0.5
  rosparam set /cube_side_length 1000.0
  rosparam set /runtime_pos_log_enable false
  rosparam dump "${OUT%.bag}.params.yaml"
  rosrun fast_lio fastlio_mapping > "${OUT%.bag}.algo.log" 2>&1 & ALGO=$!
  sleep 5
  rosbag record -O "$OUT" /Odometry __name:=rec >/dev/null 2>&1 & REC=$!
  sleep 1
  rosbag play --clock -d 1 "$BAG" "${REMAP[@]}"
  sleep 3
  rosnode kill /rec >/dev/null 2>&1 || true; wait $REC 2>/dev/null || true
  kill -0 $ALGO 2>/dev/null || echo "!! fastlio_mapping had already exited -- see ${OUT%.bag}.algo.log"
  stop $ALGO $CONV $RS
  stop $CORE
  n=$(rosbag info -y -k messages "$OUT" 2>/dev/null || echo 0)
  echo "wrote $OUT ($n odometry messages)"
  [ "${n:-0}" -gt 0 ] || echo "!! no /Odometry recorded -- check the conversion log"
done
