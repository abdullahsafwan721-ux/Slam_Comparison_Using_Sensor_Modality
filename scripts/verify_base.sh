#!/usr/bin/env bash

set -u

echo "--- ROS ---"

docker run --rm \
evtol/base:noetic \
bash -c "source /opt/ros/noetic/setup.bash && rosversion -d && echo BASE_OK"

echo
echo "--- NVIDIA GPU ---"

docker run --rm \
--gpus all \
evtol/base:noetic \
nvidia-smi

echo
echo "--- OpenGL Renderer ---"

docker run --rm \
--gpus all \
-e DISPLAY="$DISPLAY" \
-e NVIDIA_VISIBLE_DEVICES=all \
-e NVIDIA_DRIVER_CAPABILITIES=all \
-e __GLX_VENDOR_LIBRARY_NAME=nvidia \
-e __NV_PRIME_RENDER_OFFLOAD=1 \
-e QT_X11_NO_MITSHM=1 \
-v /tmp/.X11-unix:/tmp/.X11-unix \
evtol/base:noetic \
glxinfo -B | grep -E "OpenGL vendor|OpenGL renderer"

