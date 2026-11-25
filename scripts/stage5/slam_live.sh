#!/usr/bin/env bash
# Stage 5, TERMINAL 2: FAST-LIO live on the simulator, relayed to PX4.
#   docker compose run --rm fastlio2-live bash /scripts/stage5/slam_live.sh [imu-noise-scale]
# Host networking: this container joins the ROS master started in terminal 1.
# Start it only AFTER terminal 1 prints "PX4 is up with NO position source": during phase 1
# the simulator already publishes /livox/imu, and that ROS master dies at the reboot.
# Change from the guide (docs/stage5_log.md): a stop signal (Ctrl-C, docker stop) also
# stops FAST-LIO2 and the IMU-noise node, so the container exits cleanly.
# Stage 5 extension (the guide: "FAST-LIVO2 can be substituted the same way"):
#   ALGO=fastlivo2 (with the fastlivo2-live service) runs FAST-LIVO2 and relays its
#     /aft_mapped_to_init instead of FAST-LIO2's /Odometry;
#   FAULT=lidar_drop_2s|lidar_drop_5s|cam_black_5s runs the method on the *_fault topic that
#     fault_live.py publishes (run_closed_loop.sh starts that node in its own container).
set -eo pipefail
source /opt/ros/noetic/setup.bash
source /ws/devel/setup.bash
A=${ALGO:-fastlio2}
case "$A" in
  fastlio2)  LAUNCH=/config/launch/fastlio2.launch;  TOPIC=/Odometry ;;
  fastlivo2) LAUNCH=/config/launch/fastlivo2.launch; TOPIC=/aft_mapped_to_init ;;
  *) echo "!! ALGO must be fastlio2 or fastlivo2"; exit 1 ;;
esac
TOPICS="lid_topic:=/livox/lidar"
case "${FAULT:-}" in
  "") ;;
  lidar_*) TOPICS="lid_topic:=/livox/lidar_fault" ;;
  cam_*)   [ "$A" = fastlivo2 ] || { echo "!! $FAULT changes the camera, which $A does not use"; exit 1; }
           TOPICS="$TOPICS img_topic:=/stereo/left/image_fault" ;;
  *) echo "!! unknown FAULT $FAULT"; exit 1 ;;
esac
echo "waiting for the simulator's IMU ..."
until rostopic list 2>/dev/null | grep -q '^/livox/imu$'; do sleep 1; done
python3 /scripts/stage5/imu_noise_live.py "${1:-1.0}" & NOISE=$!
echo "== $A on the noised IMU (x${1:-1.0}), $TOPICS -> relay of $TOPIC"
roslaunch $LAUNCH imu_topic:=/livox/imu_noisy $TOPICS rviz:=${RVIZ:-true} & ALGO_PID=$!
trap 'kill -INT $ALGO_PID $NOISE $RELAY 2>/dev/null || true' INT TERM
sleep 3
python3 /scripts/stage5/slam_to_px4.py --in $TOPIC & RELAY=$!
wait $RELAY || true
kill -INT $ALGO_PID $NOISE 2>/dev/null || true
wait $ALGO_PID $NOISE 2>/dev/null || true
