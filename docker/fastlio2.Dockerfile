FROM evtol/base:noetic
SHELL ["/bin/bash", "-c"]
ARG DEBIAN_FRONTEND=noninteractive

# Pinned upstream versions -- record these in VERSIONS.md.
# Verified with git ls-remote on 2026-10-06.
ARG LIVOX_SDK_TAG=v2.3.1          # 14c533dd7175bd90a6b568c0aa1733f35d36cb89
ARG LIVOX_DRIVER_COMMIT=fb5669b90af07915c1870d106cc1e4e1ef1f5a15
ARG FASTLIO2_COMMIT=7cc4175de6f8ba2edf34bab02a42195b141027e9
ARG JOBS=8

# libpcl for FAST_LIO; velodyne_* to convert UTBM's raw packets into point
# clouds; nmea_navsat_driver to turn UTBM's NMEA strings into positions.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-noetic-pcl-conversions libpcl-dev \
      ros-noetic-velodyne-pointcloud ros-noetic-velodyne-msgs \
      ros-noetic-nmea-navsat-driver \
 && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Livox-SDK/Livox-SDK.git /opt/Livox-SDK \
 && cd /opt/Livox-SDK && git checkout ${LIVOX_SDK_TAG} \
 && mkdir -p build && cd build \
 && cmake .. && make -j${JOBS} && make install && ldconfig

# Order matters: FAST_LIO includes livox_ros_driver/CustomMsg.h, a header that
# only exists once the driver package has been built. The other order gives
# "cannot find livox_ros_driver/CustomMsg".
RUN mkdir -p /ws/src \
 && git clone https://github.com/Livox-SDK/livox_ros_driver.git /ws/src/livox_ros_driver \
 && cd /ws/src/livox_ros_driver && git checkout ${LIVOX_DRIVER_COMMIT}

# ikd-Tree is a submodule; without --init the build fails on a missing header.
RUN git clone https://github.com/hku-mars/FAST_LIO.git /ws/src/FAST_LIO \
 && cd /ws/src/FAST_LIO && git checkout ${FASTLIO2_COMMIT} \
 && git submodule update --init --recursive

RUN source /opt/ros/noetic/setup.bash && cd /ws \
 && catkin_make -j${JOBS} -DCMAKE_BUILD_TYPE=Release \
 && test -f /ws/devel/lib/fast_lio/fastlio_mapping

# Python deps of the FAST-LIO authors' NCLT converter
# (scripts/third_party/sensordata_to_rosbag_fastlio.py): scipy, tqdm.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-scipy python3-tqdm \
 && rm -rf /var/lib/apt/lists/*

RUN echo "source /ws/devel/setup.bash" >> /root/.bashrc
WORKDIR /ws
CMD ["bash"]
