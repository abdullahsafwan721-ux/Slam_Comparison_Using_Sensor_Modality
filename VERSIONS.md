# Pinned upstream versions

| Component        | Commit                                     | Provenance                                                                          |
| ---------------- | ------------------------------------------ | ----------------------------------------------------------------------------------- |
| ORB_SLAM3        | `0df83dde1c85c7ab91a0d47de7a29685d046f637` | tag v1.0-release — matches the published paper                                      |
| FAST_LIO         | `7cc4175de6f8ba2edf34bab02a42195b141027e9` | HEAD of master; repo has no tags                                                    |
| FAST_LIO (diag.) | `f159d57da8fa48920cefae1e9b289cb1785e4faa` | evtol/fastlio2:paper2021 only (compose service fastlio2_paper2021): the code of the paper's arXiv v1 (19 Jul 2021), ikd-Tree submodule 3d115a4; diagnostic, not the benchmark build |
| FAST-LIVO2       | `0d2c0346107b75b59934975adec9a6eeeb913c64` | HEAD of main, no tags; verified with git ls-remote 2026-10-07. GPLv2 (commercial use: contact authors) |
| livox_ros_driver | `fb5669b90af07915c1870d106cc1e4e1ef1f5a15` | tag v2.6.0 (HEAD `3d240d56` is ahead; the tag is the pin)                           |
| Livox-SDK        | `14c533dd7175bd90a6b568c0aa1733f35d36cb89` | tag v2.3.1, latest release; verified with git ls-remote 2026-10-06 (was unpinned)    |
| Sophus           | `a621ff2e56c56c839a6c40418d42c3c254424b5c` | FAST-LIVO2 README §2.3 `git checkout a621ff`; + 2-line C++11 patch in so2.cpp (see fastlivo2.Dockerfile) |
| rpg_vikit        | `6c886c8e5d83997806e00294826d528cea3581dd` | HEAD of github.com/xuankuzcr/rpg_vikit (NOT the uzh-rpg / FAST-LIVO 1 fork)          |
| Ubuntu base      | sha256:8feb4d8ca5354def3d8fce243717141ce31e2c428701f6682bd2fafe15388214 | ubuntu:20.04 pinned digest                             |
| OpenCV           | `4.4.0` (tag)                              | orbslam3.Dockerfile; Ubuntu 20.04 ships 4.2, this ORB-SLAM3 release needs >= 4.4     |
| Pangolin         | `v0.6` (tag)                               | orbslam3.Dockerfile                                                                 |
| evo              | `1.31.1` (PyPI)                            | eval.Dockerfile; last release supporting Python 3.8 (1.32+ needs >= 3.10)           |
| PX4-Autopilot    | `1555f2bd2229544c43966ab5f94879c41d8e1e01` | evtol/sim:v1 (Stage 2+). Tag v1.14.4 = annotated tag object `4eb5668b`; the build fails if the tag stops pointing at this commit. Submodule sitl_gazebo-classic `2e3ed9bf` (as the project guide lists) |
| Mid360_simulation_plugin | `aae8ee3a0f16e2f21c480da9b858dd702a2cd13a` | github.com/fratopa, HEAD (2024-01-29); four patches in sim.Dockerfile, each guarded by a grep. Verified 2026-11-05 |
| Livox-SDK, livox_ros_driver (sim) | same pins as above | sim.Dockerfile (the project guide cloned Livox-SDK HEAD `9306596`; pinned to v2.3.1 like FAST-LIO2) |
| Gazebo           | `11.15.1-1~focal` (apt)                    | evtol/sim:v1, from packages.ros.org; sdformat 9.10.1, gazebo_ros 2.9.3, mavros 1.20.1 |

Apt packages (ROS Noetic, Ubuntu 20.04) are not version-pinned; they come from the
distribution's frozen Noetic repository. FAST-LIO2 image extras: velodyne_pointcloud,
velodyne_msgs, nmea_navsat_driver (needed for the UTBM benchmark bags).

Sim image (evtol/sim:v1, built 2026-11-05, image id `sha256:a736b36ea7db...`): PX4's
`Tools/setup/ubuntu.sh` also pip-installs PX4's Python tools into `/root/.local` (unpinned,
PyPI as of the build date: jinja2 3.1.6, pyros-genmsg 0.5.8, pandas 2.0.3, ...). pip left the
system numpy 1.17.4 in place, so `import pandas` fails there; nothing in this project uses it.

ORB-SLAM3 timing image (evtol/orbslam3:v1-times, built 2026-11-17, Stage 3): `FROM
evtol/orbslam3:v1`, same commit, `#define REGISTER_TIMES` switched on in
`include/Settings.h`, library and examples rebuilt. Used only by
`scripts/stage3/orbslam3_timing.sh`; every accuracy number comes from `evtol/orbslam3:v1`.

FAST-LIVO2 build flags: upstream vikit and FAST-LIVO2 hard-code `-march=native`. The image
replaces it with one explicit target for Sophus, vikit and FAST-LIVO2: `-march=skylake`
(AVX2, the paper's i7-10700K class; build arg CPU_ARCH). Reason: on this AVX-512 host the
native build lost track on NTU-VIRAL sbs_02 in 5/5 runs (1.1-308 m RMSE); the skylake build
gives 2.97 cm in 3/3. The image also runs on any AVX2 x86 machine now.
