#!/usr/bin/env bash
# Stage 2, Sec. 2.7 "First look, with your eyes" -- the guide's commands in one script.
# Runs INSIDE the sim container; opens Gazebo, RViz (LiDAR cloud) and the left camera image:
#   docker compose run --rm sim bash /scripts/stage2/first_look.sh [world=room]
# Close the Gazebo window (or Ctrl-C here) to stop everything. Nothing is recorded.
#
# What you should see (guide): the orange rig box hanging over the floor, holding still for
# eight seconds, then moving in a smooth figure; a point cloud outlining floor, clutter and
# walls; a camera image showing floor and walls upright.
# Gazebo's view starts close to the rig: scroll to zoom out. RViz shows "Global Status: Warn"
# because nothing publishes a TF for livox_frame; the cloud is drawn in that frame anyway.
set -eo pipefail
WORLD=${1:-room}
source /scripts/common/sim_env.sh
LOG=/tmp/first_look_sim.log

roslaunch /sim/launch/rig_scripted.launch world:=/sim/worlds/${WORLD}.world gui:=true \
    > "$LOG" 2>&1 & SIM=$!
trap 'kill $(jobs -p) 2>/dev/null; wait 2>/dev/null; true' EXIT INT TERM
echo "waiting for the rig's sensors ... (Gazebo log: $LOG inside the container)"
until rostopic list 2>/dev/null | grep -q '^/ground_truth/odom$'; do
    kill -0 $SIM 2>/dev/null || { echo "Gazebo exited early:"; tail -20 "$LOG"; exit 1; }
    sleep 1
done
rostopic list | grep -E '^/(livox|stereo|ground_truth)'
timeout 4 rostopic hz /livox/imu 2>/dev/null | grep -m1 'average rate' || true   # ~200

# RViz cannot show Livox CustomMsg; this converts /livox/lidar -> /livox/points for viewing.
python3 /scripts/stage2/livox_to_pc2.py &
rviz -d /scripts/stage2/first_look.rviz > /dev/null 2>&1 &
rqt_image_view /stereo/left/image_raw > /dev/null 2>&1 &
echo "Gazebo, RViz and the image viewer are open. Close Gazebo or press Ctrl-C to stop."
wait $SIM
