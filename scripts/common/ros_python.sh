#!/usr/bin/env bash
# Run a Python script with ROS available, in ANY project container:
#   docker compose run --rm eval bash /scripts/common/ros_python.sh /scripts/common/bag_to_tum.py <bag> <topic> <out>
#
# Added (not in the project guide). Two reasons a bare `python3 script.py` fails here:
#  * `docker compose run <svc> python3 ...` does not read .bashrc, so ROS is not sourced
#    (ModuleNotFoundError: rosbag) -- see docs/stage2_log.md, deviation 4;
#  * in evtol/eval:v1, `python3` is the evo virtualenv (/opt/eval-venv, evo 1.31.1), which
#    cannot import rosbag at all. evo stays there; bag tools use the system interpreter.
set -eo pipefail
source /opt/ros/noetic/setup.bash
[ -f /ws/devel/setup.bash ] && source /ws/devel/setup.bash
exec /usr/bin/python3 "$@"
