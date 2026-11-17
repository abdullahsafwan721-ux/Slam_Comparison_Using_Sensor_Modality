#!/usr/bin/env bash
# Source (do not execute) inside the sim container:
#   source /scripts/common/sim_env.sh          # Gazebo + our plugins
#   source /scripts/common/sim_env.sh px4      # ... plus PX4 SITL
# Order matters: PX4's setup script APPENDS its paths, so ours are prepended
# afterwards to guarantee our models win any name clash.
source /opt/ros/noetic/setup.bash
source /ws/devel/setup.bash
source /usr/share/gazebo/setup.sh
if [ "${1:-}" = "px4" ]; then
  PX4=/opt/PX4-Autopilot
  source $PX4/Tools/simulation/gazebo-classic/setup_gazebo.bash $PX4 $PX4/build/px4_sitl_default >/dev/null
  export ROS_PACKAGE_PATH=$ROS_PACKAGE_PATH:$PX4:$PX4/Tools/simulation/gazebo-classic/sitl_gazebo-classic
fi
export GAZEBO_MODEL_PATH=/sim/models:${GAZEBO_MODEL_PATH:-}
if [ "${1:-}" = "px4" ]; then
  # Stage 3: PX4's iris plus the landing gear of rig.yaml, built here from the image's own
  # iris.sdf and put first so that model://iris finds it (see make_legged_iris.py).
  python3 /scripts/common/make_legged_iris.py /tmp/evtol_models
  export GAZEBO_MODEL_PATH=/tmp/evtol_models:$GAZEBO_MODEL_PATH
fi
export GAZEBO_PLUGIN_PATH=/ws/devel/lib:${GAZEBO_PLUGIN_PATH:-}
