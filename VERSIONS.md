# Pinned upstream versions

| Component        | Commit                                     | Provenance                                                                          |
| ---------------- | ------------------------------------------ | ----------------------------------------------------------------------------------- |
| ORB_SLAM3        | `0df83dde1c85c7ab91a0d47de7a29685d046f637` | tag v1.0-release — matches the published paper                                      |
| FAST_LIO         | `7cc4175de6f8ba2edf34bab02a42195b141027e9` | HEAD of master; repo has no tags                                                    |
| FAST-LIVO2       | `0d2c0346107b75b59934975adec9a6eeeb913c64` | HEAD of master; repo has no tags                                                    |
| livox_ros_driver | `fb5669b90af07915c1870d106cc1e4e1ef1f5a15` | tag v2.6.0 (HEAD `3d240d56` is ahead; the tag is the pin)                           |
| Sophus           | `a621ff2e56c56c839a6c40418d42c3c254424b5c` | FAST-LIVO2 README §2.3 specifies `git checkout a621ff`; full hash, dated 2012-08-25 |
| rpg_vikit        | `6c886c8e5d83997806e00294826d528cea3581dd` | HEAD of github.com/xuankuzcr/rpg_vikit; pin selected for reproducibility            |
| Ubuntu base      | See `docker/base.Dockerfile`               | Fill in the digest pinned during Phase 4                                            |
