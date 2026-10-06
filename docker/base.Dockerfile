# Base: Ubuntu 20.04 + ROS Noetic
#
# Pinned Ubuntu 20.04 digest
FROM ubuntu:20.04@sha256:8feb4d8ca5354def3d8fce243717141ce31e2c428701f6682bd2fafe15388214

# Prevent interactive installation prompts during Docker build
ARG DEBIAN_FRONTEND=noninteractive

# Timezone
ENV TZ=Asia/Kolkata

# Use Bash instead of sh
SHELL ["/bin/bash", "-c"]

# ============================================================
# Layer 1 — System packages
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    unzip \
    nano \
    ca-certificates \
    gnupg2 \
    lsb-release \
    libeigen3-dev \
    libboost-all-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsuitesparse-dev \
    python3-pip \
    python3-dev \
    mesa-utils \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Layer 2 — ROS Noetic
# ============================================================

# Install ROS repository signing key and repository
RUN curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros/ubuntu focal main" \
    > /etc/apt/sources.list.d/ros1.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ros-noetic-desktop \
        ros-noetic-pcl-ros \
        ros-noetic-cv-bridge \
        ros-noetic-tf2-ros \
        ros-noetic-eigen-conversions \
        python3-catkin-tools \
        python3-rosdep \
        python3-rosinstall-generator \
    && rm -rf /var/lib/apt/lists/*

ENV ROS_DISTRO=noetic

# Automatically source ROS when opening Bash
RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc

WORKDIR /ws

CMD ["bash"]
