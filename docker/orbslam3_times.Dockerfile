# ORB-SLAM3 with upstream's own timing instrumentation (REGISTER_TIMES) switched on.
# Derived FROM the validated Stage 1 image, which is left untouched: evtol/orbslam3:v1
# stays the binary every accuracy number comes from; this image is used only to measure
# tracking time per frame (Stage 3, metric H5). Same source commit, one #define changed.
FROM evtol/orbslam3:v1

SHELL ["/bin/bash", "-c"]
ARG JOBS=8

RUN cd /opt/ORB_SLAM3 \
    && sed -i 's|^//#define REGISTER_TIMES|#define REGISTER_TIMES|' include/Settings.h \
    && grep -q '^#define REGISTER_TIMES' include/Settings.h \
    && cd build && make -j${JOBS}

WORKDIR /ws
CMD ["bash"]
