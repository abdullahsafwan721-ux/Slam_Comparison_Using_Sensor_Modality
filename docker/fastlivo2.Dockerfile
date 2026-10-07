FROM evtol/base:noetic
SHELL ["/bin/bash", "-c"]
ARG DEBIAN_FRONTEND=noninteractive

# Pinned and verified with git ls-remote on 2026-10-07. Recorded in VERSIONS.md.
# FAST-LIVO2 has no release tags; this is HEAD of main at the time of writing.
ARG SOPHUS_COMMIT=a621ff2e56c56c839a6c40418d42c3c254424b5c
ARG VIKIT_COMMIT=6c886c8e5d83997806e00294826d528cea3581dd
ARG FASTLIVO2_COMMIT=0d2c0346107b75b59934975adec9a6eeeb913c64
ARG JOBS=8

# README §2.2 asks for PCL>=1.8, Eigen>=3.3.4, OpenCV>=4.2. Ubuntu 20.04 ships
# OpenCV 4.2 through ROS, which satisfies the minimum -- no source build needed
# here (unlike the ORB-SLAM3 image, which needs 4.4).
RUN apt-get update && apt-get install -y --no-install-recommends \
      libopencv-dev libpcl-dev ros-noetic-pcl-conversions \
      ros-noetic-cv-bridge ros-noetic-image-transport ros-noetic-image-transport-plugins \
      libboost-all-dev \
 && rm -rf /var/lib/apt/lists/*

# ---- Sophus: the non-templated, double-only version (README §2.3: "git checkout a621ff")
# That 2012 code does not compile under C++11 or later: sophus/so2.cpp assigns to
# std::complex::real()/imag(), which return by value since C++11 ("lvalue required
# as left operand of assignment"). Two lines; the greps make the build fail loudly
# if the patch ever stops matching instead of silently patching nothing.
RUN git clone https://github.com/strasdat/Sophus.git /opt/Sophus \
  && cd /opt/Sophus && git checkout ${SOPHUS_COMMIT} \
  && sed -i 's/unit_complex_\.real() = 1\.;/unit_complex_.real(1.);/' sophus/so2.cpp \
  && sed -i 's/unit_complex_\.imag() = 0\.;/unit_complex_.imag(0.);/' sophus/so2.cpp \
  && grep -q 'unit_complex_.real(1.)' sophus/so2.cpp \
  && grep -q 'unit_complex_.imag(0.)' sophus/so2.cpp \
  && mkdir build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release \
  && make -j${JOBS} && make install && ldconfig

# ---- Vikit: camera models and math helpers. README §2.4: NOT the FAST-LIVO 1 fork.
RUN mkdir -p /ws/src \
 && git clone https://github.com/xuankuzcr/rpg_vikit.git /ws/src/rpg_vikit \
 && cd /ws/src/rpg_vikit && git checkout ${VIKIT_COMMIT}

RUN git clone https://github.com/hku-mars/FAST-LIVO2.git /ws/src/FAST-LIVO2 \
 && cd /ws/src/FAST-LIVO2 && git checkout ${FASTLIVO2_COMMIT}

RUN source /opt/ros/noetic/setup.bash && cd /ws \
 && catkin_make -j${JOBS} -DCMAKE_BUILD_TYPE=Release \
 && test -f /ws/devel/lib/fast_livo/fastlivo_mapping

# The node writes its trajectory to <source>/Log/result/<seq_name>.txt. That path
# is inside the image, so the run script copies the file out to /output.
RUN echo "source /ws/devel/setup.bash" >> /root/.bashrc
WORKDIR /ws
CMD ["bash"]
