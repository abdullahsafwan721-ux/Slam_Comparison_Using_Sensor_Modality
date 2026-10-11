FROM evtol/base:noetic

SHELL ["/bin/bash", "-c"]

ARG DEBIAN_FRONTEND=noninteractive

# Reproducible ORB-SLAM3 version
ARG ORBSLAM3_COMMIT=0df83dde1c85c7ab91a0d47de7a29685d046f637

# OpenCV version required by this ORB-SLAM3 release
ARG OPENCV_VERSION=4.4.0

# Limit parallel compilation to avoid excessive RAM usage
ARG JOBS=8


# ------------------------------------------------------------
# ORB-SLAM3 + OpenCV build dependencies
# ------------------------------------------------------------

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    unzip \
    pkg-config \
    libgtk-3-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    gfortran \
    openexr \
    libatlas-base-dev \
    libtbb-dev \
    libglew-dev \
    libssl-dev \
    libepoxy-dev \
    libpython3-dev \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*


# ------------------------------------------------------------
# OpenCV 4.4.0
# Ubuntu 20.04 provides OpenCV 4.2, but this ORB-SLAM3 release
# requires OpenCV >= 4.4.
# ------------------------------------------------------------

RUN git clone --depth 1 --branch ${OPENCV_VERSION} \
    https://github.com/opencv/opencv.git /opt/opencv \
    && mkdir -p /opt/opencv/build \
    && cd /opt/opencv/build \
    && cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DBUILD_TESTS=OFF \
        -DBUILD_PERF_TESTS=OFF \
        -DBUILD_EXAMPLES=OFF \
        -DBUILD_opencv_python3=OFF \
        -DWITH_CUDA=OFF \
    && make -j${JOBS} \
    && make install \
    && ldconfig


# ------------------------------------------------------------
# Pangolin v0.6
# ------------------------------------------------------------

RUN git clone --depth 1 --branch v0.6 \
    https://github.com/stevenlovegrove/Pangolin.git /opt/Pangolin \
    && mkdir -p /opt/Pangolin/build \
    && cd /opt/Pangolin/build \
    && cmake .. -DCMAKE_BUILD_TYPE=Release \
    && make -j${JOBS} \
    && make install \
    && ldconfig


# ------------------------------------------------------------
# ORB-SLAM3
# ------------------------------------------------------------

RUN git clone https://github.com/UZ-SLAMLab/ORB_SLAM3.git /opt/ORB_SLAM3 \
    && cd /opt/ORB_SLAM3 \
    && git checkout ${ORBSLAM3_COMMIT} \
    && chmod +x build.sh \
    && ./build.sh


WORKDIR /ws

CMD ["bash"]
