#!/usr/bin/env bash
# Replay one bag through FAST-LIVO2.
#   run_fastlivo2.sh <config.yaml> <camera.yaml> <in.bag> <seq-name> [rosbag play args...]
#   RUNS=5 run_fastlivo2.sh ...                 repeat and write _r1.._rN
#   RUN_START=3 RUNS=1 run_fastlivo2.sh ...     write only _r3 (one run per container)
#   REPUBLISH=/left_camera/image run_fastlivo2.sh ...
#        bag carries <topic>/compressed: decompress it to <topic> (as mapping_avia.launch does)
# Writes $OUTDIR/<seq>_r<N>.txt   (TUM, IMU frame, written by the node itself)
#    and $OUTDIR/<seq>_r<N>.bag   (recorded /aft_mapped_to_init), .algo.log, .params.yaml
# OUTDIR defaults to /output/fastlivo2.
set -eo pipefail
CFG=$1; CAM=$2; BAG=$3; SEQ=$4; shift 4
RUNS=${RUNS:-1}; R0=${RUN_START:-1}
OUTDIR=${OUTDIR:-/output/fastlivo2}; mkdir -p "$OUTDIR"
SRC=/ws/src/FAST-LIVO2
source /opt/ros/noetic/setup.bash
source /ws/devel/setup.bash
for f in "$CFG" "$CAM" "$BAG"; do [ -f "$f" ] || { echo "!! not found: $f"; exit 1; }; done

# SIGINT, then SIGKILL after 10 s if the process is still there (with use_sim_time a
# ROS node can block on a /clock that stopped when the bag ended -- this hung every
# FAST-LIO2 run). The trajectory is flushed line by line, so nothing is lost.
stop() {
  kill -INT "$@" 2>/dev/null || true
  for _ in $(seq 20); do kill -0 "$@" 2>/dev/null || break; sleep 0.5; done
  kill -KILL "$@" 2>/dev/null || true
  wait "$@" 2>/dev/null || true
}

for r in $(seq "$R0" $((R0 + RUNS - 1))); do
  NAME=${SEQ}_r${r}
  echo "=== $NAME ==="
  rm -f "$SRC/Log/result/$NAME.txt"
  roscore >/dev/null 2>&1 & CORE=$!
  until rostopic list >/dev/null 2>&1; do sleep 0.5; done
  rosparam set /use_sim_time true

  rosparam load "$CFG"                        # global, as the launch files do
  rosparam set /evo/pose_output_en true       # node writes Log/result/<seq_name>.txt
  rosparam set /evo/seq_name "$NAME"
  # camera intrinsics: vk::camera_loader::loadFromRosNs("laserMapping") reads
  # /laserMapping/cam_*, which is where the launch files put them.
  rosparam load "$CAM" /laserMapping
  rosparam dump "$OUTDIR/$NAME.params.yaml"

  REP=
  if [ -n "${REPUBLISH:-}" ]; then
    rosrun image_transport republish compressed in:="$REPUBLISH" raw out:="$REPUBLISH" >/dev/null 2>&1 & REP=$!
  fi
  rosrun fast_livo fastlivo_mapping __name:=laserMapping > "$OUTDIR/$NAME.algo.log" 2>&1 & ALGO=$!
  sleep 5
  rosbag record -O "$OUTDIR/$NAME.bag" /aft_mapped_to_init __name:=rec >/dev/null 2>&1 & REC=$!
  sleep 1
  rosbag play --clock -d 1 "$BAG" "$@"
  # Drain: wait until the node has stopped appending poses (it can lag the bag when the
  # CPU is shared; a fixed 5 s -- the guide's value -- silently cut ~33 s off sbs_01/03).
  T="$SRC/Log/result/$NAME.txt"; prev=-1; still=0
  for _ in $(seq 300); do
    n=$(wc -l < "$T" 2>/dev/null || echo 0)
    if [ "$n" = "$prev" ]; then still=$((still + 1)); else still=0; prev=$n; fi
    [ "$still" -ge 5 ] && break             # unchanged for 10 s
    sleep 2
  done
  rosnode kill /rec >/dev/null 2>&1 || true; wait $REC 2>/dev/null || true
  kill -0 $ALGO 2>/dev/null || echo "!! fastlivo_mapping had already exited -- see $OUTDIR/$NAME.algo.log"
  stop $ALGO $REP
  stop $CORE

  if [ -s "$SRC/Log/result/$NAME.txt" ]; then
    cp "$SRC/Log/result/$NAME.txt" "$OUTDIR/$NAME.txt"
    lag=$(python3 -c "import rosbag,sys; b=rosbag.Bag(sys.argv[1]); print('%.1f' % (b.get_end_time() - float(open(sys.argv[2]).read().split()[-8])))" "$BAG" "$OUTDIR/$NAME.txt" 2>/dev/null || echo '?')
    echo "wrote $OUTDIR/$NAME.txt ($(wc -l < "$OUTDIR/$NAME.txt") poses, last pose ${lag} s before bag end)"
  else
    echo "!! no trajectory written -- check $OUTDIR/$NAME.algo.log"
  fi
done
