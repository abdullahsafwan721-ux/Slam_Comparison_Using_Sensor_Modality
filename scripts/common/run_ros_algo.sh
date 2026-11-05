#!/usr/bin/env bash
# Replay one bag through one ROS algorithm and record its odometry.
# Runs INSIDE an algorithm container (fastlio2 / fastlivo2 / hw).
#
#   run_ros_algo.sh <launch-file> <bag> <odom-topic> <out.bag> [rate] [roslaunch args...]
#
# Example:
#   bash /scripts/common/run_ros_algo.sh /config/launch/fastlio2.launch \
#        /output/stage2/room.bag /Odometry /output/stage3/fastlio2__room__r1.bag \
#        1.0 cfg:=/config/generated/fastlio2_sim.yaml
#
# LATENCY=1 in the environment also records per-message processing latency
# (see latency_probe.py) next to the output bag.
set -eo pipefail
[ $# -ge 4 ] || { sed -n '2,15p' "$0"; exit 1; }
LAUNCH=$1; BAG=$2; TOPIC=$3; OUT=$4; RATE=${5:-1.0}
shift $(( $# < 5 ? $# : 5 ))
source /opt/ros/noetic/setup.bash
source /ws/devel/setup.bash
mkdir -p "$(dirname "$OUT")"
LOG="${OUT%.bag}"

roscore >/dev/null 2>&1 & CORE=$!
until rostopic list >/dev/null 2>&1; do sleep 0.5; done
rosparam set /use_sim_time true           # before any node starts

roslaunch "$LAUNCH" "$@" rviz:=false > "$LOG.algo.log" 2>&1 & ALGO=$!
sleep 5                                    # let the node subscribe before data flows
rosbag record -O "$OUT" "$TOPIC" __name:=recorder >/dev/null 2>&1 & REC=$!
if [ "${LATENCY:-0}" = "1" ]; then
  python3 /scripts/common/latency_probe.py "$TOPIC" "$LOG.latency.csv" & PROBE=$!
fi
sleep 1
# --clock publishes the bag's time as /clock; --hz=1000 makes that clock fine
# enough (1 ms) for latency measurement. -d 1 waits for subscribers.
rosbag play --clock --hz=1000 -r "$RATE" -d 1 "$BAG" > "$LOG.play.log" 2>&1
sleep 3                                    # drain the last scans
[ -n "${PROBE:-}" ] && kill -INT $PROBE 2>/dev/null && wait $PROBE || true
rosnode kill /recorder >/dev/null 2>&1 || true; wait $REC 2>/dev/null || true
kill -INT $ALGO 2>/dev/null; wait $ALGO 2>/dev/null || true
kill -INT $CORE 2>/dev/null; wait $CORE 2>/dev/null || true
echo "wrote $OUT  (algorithm log: $LOG.algo.log)"
