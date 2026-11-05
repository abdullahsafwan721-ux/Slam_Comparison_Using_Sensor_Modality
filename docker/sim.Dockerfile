# Simulation image: Gazebo 11 + PX4 SITL (gazebo-classic) + MAVROS + the
# patched Mid-360 LiDAR plugin + our trajectory-driver plugin.
# Stages 2-5 run here. Worlds, models and launch files are NOT baked in: they
# are mounted from ./sim/evtol_sim at /sim, so editing config/rig.yaml and
# re-running gen_configs.py never requires rebuilding this image.
#
# Transcribed from eVTOL-SLAM-Complete-Project-Guide.pdf Sec. 2.1. Two changes,
# both hardening the pins (see docs/stage2_log.md):
#   - Livox-SDK pinned to v2.3.1, as in fastlio2.Dockerfile (the guide clones HEAD).
#   - The build fails if the PX4 tag no longer points at the recorded commit.
FROM evtol/base:noetic
SHELL ["/bin/bash", "-c"]
ARG DEBIAN_FRONTEND=noninteractive

# Verified 2026-09-18 with git ls-remote (guide); re-verified 2026-11-05.
# PX4_COMMIT is the commit the annotated tag v1.14.4 (tag object 4eb5668b) points at.
# LIVOX_SDK_TAG v2.3.1 = commit 14c533dd7175bd90a6b568c0aa1733f35d36cb89.
ARG PX4_TAG=v1.14.4
ARG PX4_COMMIT=1555f2bd2229544c43966ab5f94879c41d8e1e01
ARG MID360_PLUGIN_COMMIT=aae8ee3a0f16e2f21c480da9b858dd702a2cd13a
ARG LIVOX_SDK_TAG=v2.3.1
ARG LIVOX_DRIVER_COMMIT=fb5669b90af07915c1870d106cc1e4e1ef1f5a15
ARG JOBS=8

# ---- Gazebo 11, ROS integration, MAVROS -------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-noetic-gazebo-ros-pkgs ros-noetic-gazebo-plugins \
      ros-noetic-mavros ros-noetic-mavros-extras ros-noetic-mavros-msgs \
      ros-noetic-rqt-image-view ros-noetic-xacro \
      gazebo11 libgazebo11-dev \
      python3-yaml python3-numpy python3-opencv \
      sudo ninja-build libpcl-dev ros-noetic-pcl-conversions \
 && rm -rf /var/lib/apt/lists/*

# MAVROS aborts at start-up without the GeographicLib geoid dataset.
RUN /opt/ros/noetic/lib/mavros/install_geographiclib_datasets.sh

# ---- PX4 SITL ----------------------------------------------------------------
# v1.14 is the line whose setup script treats Ubuntu 20.04 + Gazebo Classic 11
# as first-class. --no-nuttx skips the flight-controller cross-compiler, which
# SITL does not need.
RUN git clone --branch ${PX4_TAG} --depth 1 --recursive \
      https://github.com/PX4/PX4-Autopilot.git /opt/PX4-Autopilot \
 && test "$(git -C /opt/PX4-Autopilot rev-parse HEAD)" = "${PX4_COMMIT}" \
 && bash /opt/PX4-Autopilot/Tools/setup/ubuntu.sh --no-nuttx \
 && rm -rf /var/lib/apt/lists/*

# Build PX4 and its Gazebo plugins without launching anything.
RUN cd /opt/PX4-Autopilot && DONT_RUN=1 make px4_sitl_default gazebo-classic

# ---- Livox SDK + driver: needed only for the CustomMsg message definition ----
RUN git clone https://github.com/Livox-SDK/Livox-SDK.git /opt/Livox-SDK \
 && cd /opt/Livox-SDK && git checkout ${LIVOX_SDK_TAG} \
 && mkdir -p /opt/Livox-SDK/build && cd /opt/Livox-SDK/build \
 && cmake .. && make -j${JOBS} && make install && ldconfig
RUN mkdir -p /ws/src \
 && git clone https://github.com/Livox-SDK/livox_ros_driver.git /ws/src/livox_ros_driver \
 && cd /ws/src/livox_ros_driver && git checkout ${LIVOX_DRIVER_COMMIT}

# ---- Mid-360 LiDAR plugin, with four patches --------------------------------
# 1. offset_time: upstream stamps point i with i*5 us, spreading one scan over
#    0.1 s. But Gazebo fires every ray at the same instant. FAST-LIO and
#    FAST-LIVO2 would then "de-skew" motion that never happened, injecting
#    error that grows with speed. Zero is the TRUE per-point time here.
# 2. timebase: upstream uses clock_gettime(...).tv_nsec -- wall-clock, and only
#    the sub-second part. Replaced with ROS (simulation) time.
# 3. Message type: upstream publishes its own livox_laser_simulation/CustomMsg;
#    both algorithms subscribe to livox_ros_driver/CustomMsg.
# 4. libprotobuf.so.9 is the Ubuntu 16.04 soname; Focal ships .so.17.
# The trailing greps make the build FAIL if any patch silently matched nothing.
# NOTE: the plugin finds its scan-pattern CSV relative to its own SOURCE file
# (__FILE__), so the source tree must stay in the image. Do not clean it up.
RUN git clone https://github.com/fratopa/Mid360_simulation_plugin.git /ws/src/Mid360_simulation_plugin \
 && cd /ws/src/Mid360_simulation_plugin && git checkout ${MID360_PLUGIN_COMMIT} \
 && cd livox_laser_simulation \
 && sed -i 's#pt.offset_time = (1e9/200000\*i);#pt.offset_time = 0;#' src/livox_points_plugin.cpp \
 && sed -i 's#msg.timebase = tn.tv_nsec;#msg.timebase = ros::Time::now().toNSec();#' src/livox_points_plugin.cpp \
 && sed -i 's#livox_laser_simulation/CustomMsg.h#livox_ros_driver/CustomMsg.h#; s#livox_laser_simulation::CustomMsg#livox_ros_driver::CustomMsg#g; s#livox_laser_simulation::CustomPoint#livox_ros_driver::CustomPoint#g' src/livox_points_plugin.cpp \
 && sed -i 's#libprotobuf.so.9#protobuf#' CMakeLists.txt \
 && sed -i 's#^  message_generation$#  message_generation\n  livox_ros_driver#' CMakeLists.txt \
 && echo 'add_dependencies(livox_laser_simulation ${catkin_EXPORTED_TARGETS})' >> CMakeLists.txt \
 && sed -i 's#livox_ros_driver2#livox_ros_driver#g' package.xml \
 && grep -q 'pt.offset_time = 0;' src/livox_points_plugin.cpp \
 && grep -q 'toNSec' src/livox_points_plugin.cpp \
 && grep -q 'livox_ros_driver::CustomMsg msg' src/livox_points_plugin.cpp \
 && grep -q '^  livox_ros_driver$' CMakeLists.txt \
 && ! grep -q 'libprotobuf.so.9' CMakeLists.txt

# ---- Our package: only the plugin source is baked in --------------------------
COPY sim/evtol_sim/package.xml sim/evtol_sim/CMakeLists.txt /ws/src/evtol_sim/
COPY sim/evtol_sim/src /ws/src/evtol_sim/src

RUN source /opt/ros/noetic/setup.bash \
 && cd /ws && catkin_make -j${JOBS} -DCMAKE_BUILD_TYPE=Release \
 && test -f /ws/devel/lib/liblivox_laser_simulation.so \
 && test -f /ws/devel/lib/libtrajectory_driver.so

RUN echo "source /scripts/common/sim_env.sh 2>/dev/null || true" >> /root/.bashrc
WORKDIR /ws
CMD ["bash"]
