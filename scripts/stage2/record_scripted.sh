#!/usr/bin/env bash
# Stage 2: fly the rig along its scripted path in a world and record everything.
# Runs INSIDE the sim container:
#   docker compose run --rm sim bash /scripts/stage2/record_scripted.sh room 120
#
#   args: <world> <seconds> [out.bag] [gui=false]
set -eo pipefail
WORLD=${1:-room}; DUR=${2:-120}
OUT=${3:-/output/stage2/scripted_${WORLD}.bag}; GUI=${4:-false}
source /scripts/common/sim_env.sh
mkdir -p "$(dirname "$OUT")"

roslaunch /sim/launch/rig_scripted.launch world:=/sim/worlds/${WORLD}.world gui:=$GUI \
    > "${OUT%.bag}.sim.log" 2>&1 & SIM=$!
echo "waiting for the rig's sensors ..."
until rostopic list 2>/dev/null | grep -q '^/ground_truth/odom$'; do sleep 1; done
# Topics are recorded from the first second, so the stationary hold at the start
# of the path (gravity initialisation) is inside the bag.
rosbag record -O "$OUT" --duration="$DUR" \
    /livox/lidar /livox/imu /ground_truth/odom \
    /stereo/left/image_raw /stereo/right/image_raw \
    /stereo/left/camera_info /stereo/right/camera_info __name:=recorder
kill -INT $SIM; wait $SIM 2>/dev/null || true
echo "wrote $OUT -- next: python3 /scripts/stage2/verify_sim_bag.py $OUT"
