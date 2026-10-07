# Pinned upstream versions

| Component        | Commit                                     | Provenance                                                                          |
| ---------------- | ------------------------------------------ | ----------------------------------------------------------------------------------- |
| ORB_SLAM3        | `0df83dde1c85c7ab91a0d47de7a29685d046f637` | tag v1.0-release — matches the published paper                                      |
| FAST_LIO         | `7cc4175de6f8ba2edf34bab02a42195b141027e9` | HEAD of master; repo has no tags                                                    |
| FAST-LIVO2       | `0d2c0346107b75b59934975adec9a6eeeb913c64` | HEAD of main, no tags; verified with git ls-remote 2026-10-07. GPLv2 (commercial use: contact authors) |
| livox_ros_driver | `fb5669b90af07915c1870d106cc1e4e1ef1f5a15` | tag v2.6.0 (HEAD `3d240d56` is ahead; the tag is the pin)                           |
| Livox-SDK        | `14c533dd7175bd90a6b568c0aa1733f35d36cb89` | tag v2.3.1, latest release; verified with git ls-remote 2026-10-06 (was unpinned)    |
| Sophus           | `a621ff2e56c56c839a6c40418d42c3c254424b5c` | FAST-LIVO2 README §2.3 `git checkout a621ff`; + 2-line C++11 patch in so2.cpp (see fastlivo2.Dockerfile) |
| rpg_vikit        | `6c886c8e5d83997806e00294826d528cea3581dd` | HEAD of github.com/xuankuzcr/rpg_vikit (NOT the uzh-rpg / FAST-LIVO 1 fork)          |
| Ubuntu base      | sha256:8feb4d8ca5354def3d8fce243717141ce31e2c428701f6682bd2fafe15388214 | ubuntu:20.04 pinned digest                             |
| OpenCV           | `4.4.0` (tag)                              | orbslam3.Dockerfile; Ubuntu 20.04 ships 4.2, this ORB-SLAM3 release needs >= 4.4     |
| Pangolin         | `v0.6` (tag)                               | orbslam3.Dockerfile                                                                 |
| evo              | `1.31.1` (PyPI)                            | eval.Dockerfile; last release supporting Python 3.8 (1.32+ needs >= 3.10)           |

Apt packages (ROS Noetic, Ubuntu 20.04) are not version-pinned; they come from the
distribution's frozen Noetic repository. FAST-LIO2 image extras: velodyne_pointcloud,
velodyne_msgs, nmea_navsat_driver (needed for the UTBM benchmark bags).

FAST-LIVO2 build flags: upstream vikit and FAST-LIVO2 hard-code `-march=native`. The image
replaces it with one explicit target for Sophus, vikit and FAST-LIVO2: `-march=skylake`
(AVX2, the paper's i7-10700K class; build arg CPU_ARCH). Reason: on this AVX-512 host the
native build lost track on NTU-VIRAL sbs_02 in 5/5 runs (1.1-308 m RMSE); the skylake build
gives 2.97 cm in 3/3. The image also runs on any AVX2 x86 machine now.
