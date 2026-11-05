# output/ -- every measured output, by algorithm

Raw outputs (bags, trajectories, logs) live here and are git-ignored (size). The final tables
are also committed in `docs/results/`. Mounted as `/output` in every container.
Layout organised on 2026-10-08 (FAST-LIO2 lili/utbm runs replaced 2026-10-09, old runs kept under diagnostics); nothing was deleted.

| Folder | What | Produced by |
|---|---|---|
| `orbslam3/trajectories/` | ORB-SLAM3 EuRoC, 11 seq x 5 runs: `kf_orb_<SEQ>_r<N>.txt` (keyframes, ns stamps), `f_orb_*` (all frames) | `scripts/run_orbslam3_euroc.sh` (orbslam3 container) |
| `orbslam3/evaluation/` | `*_eval.txt` (stamps in s), `*_ape.zip` (evo), `summary.csv` | `scripts/eval_orbslam3.sh` (eval container) |
| `orbslam3/groundtruth/` | EuRoC ground truth, 11 seq: `<SEQ>_state_groundtruth_estimate0.csv`, byte-identical copies of `mav0/state_groundtruth_estimate0/data.csv` (sha256 checked), kept so the ORB-SLAM3 runs stay scorable after `data/` was moved to the trash on 2026-10-20 | copied by hand |
| `fastlio2/` | FAST-LIO2, 16 paper sequences x 5 runs (lili and utbm re-run 2026-10-09): `<seq>_r<N>.bag` (/Odometry), `.tum`, `.algo.log`, `.params.yaml`; ground truth `gt_<seq>.tum`, GNSS refs `gnssref_<seq>.tum`, UTBM `<seq>_fix.bag`; `benchmark.log` | `scripts/fl2_benchmark.sh` -> `run_fastlio2.sh` / `run_fastlio2_utbm.sh` |
| `fastlivo2/` | FAST-LIVO2 standard protocol (whole bag): NTU-VIRAL 9 seq + private 6 seq x 5 runs: `<seq>_r<N>.txt` (TUM, IMU frame), `_prism.tum`, `.bag`, `.algo.log`, `.params.yaml`; `gt_<seq>.tum`; `benchmark.log` | `scripts/livo2_benchmark.sh` -> `run_fastlivo2.sh` |
| `fastlivo2_matched/` | FAST-LIVO2 NTU-VIRAL "matched start" protocol (replay from the authors' own first pose) | `scripts/livo2_ntu_matched.sh` |
| `stage2/` | Stage 2 simulated rig (2026-11-05): `scripted_room.bag` (120 s, room world, GPU-rendered: /livox/imu 200 Hz, /livox/lidar Mid-360 CustomMsg 10 Hz, /stereo/{left,right}/image_raw 20 Hz, /ground_truth/odom 200 Hz), `.sim.log` (Gazebo), `.gate.txt` (verify_sim_bag.py), `scripted_room_diag/` + `_diag.txt` (diagnostics report; camera, LiDAR, LiDAR-on-camera PNGs), `scripted_room_camcheck/` + `.txt` (camera extrinsic/intrinsic/time check, world-edge PNG) | `scripts/stage2/record_scripted.sh`, `verify_sim_bag.py`, `sim_bag_diagnostics.py`, `camera_check.py` (sim container) |
| `results/fastlio2_final/` | final FAST-LIO2 evaluation: `summary.csv`, `comparison.md`, per-run `*_ape.zip/.txt` | `scripts/eval_fastlio2.sh` |
| `results/fastlivo2_standard_final/` | final FAST-LIVO2 evaluation, standard protocol | `scripts/eval_fastlivo2.sh` |
| `results/fastlivo2_matched_final/` | final FAST-LIVO2 evaluation, matched-start protocol | `IN=/output/fastlivo2_matched eval_fastlivo2.sh` |
| `results/history/` | every earlier, timestamped evaluation run (superseded, kept for traceability) | same scripts |
| `diagnostics/fastlio2/avia_functional_test/` | first FAST-LIO2 run (Sept 2026): Avia demo bag, not a paper sequence | manual |
| `diagnostics/fastlio2/smoke_lili6_slice/` | pipeline smoke test on an 89 s lili slice | `run_fastlio2.sh` |
| `diagnostics/fastlio2/smoke_parallel_vs_serial/` | proof that parallel runs = serial runs (identical results) | `fl2_parallel.sh` |
| `diagnostics/fastlio2/lili7_config_variants/` | lili 7 with Xsens IMU / no extrinsic estimation / point_filter_num 3 | `run_fastlio2.sh` |
| `diagnostics/fastlio2/superseded_20261007_lili_horizon_imu/` | lili 6/7/8 benchmark runs until 2026-10-09: Horizon built-in IMU (wrong IMU, lili 7 = 11.5 m) | `run_fastlio2.sh` + `lili_horizon_imu.yaml` |
| `diagnostics/fastlio2/superseded_20261007_utbm_zero_extrinsic/` | utbm 8/9/10 benchmark runs until 2026-10-09: zero LiDAR-IMU extrinsic | `run_fastlio2_utbm.sh` |
| `diagnostics/fastlio2/review_20261009_lili_horizon_imu_blind001/` | review: Horizon IMU with `blind 0.01` (blind is not the lili 7 cause) | `fl2_review.sh v2` |
| `diagnostics/fastlio2/review_20261009_rebuild_control/` | review: rebuilt image vs committed results (liosam 2, nclt 9) | `fl2_review.sh v2` |
| `diagnostics/fastlio2/paper2021_code/` | review: the paper's July-2021 FAST_LIO code (lili, liosam, utbm, nclt 9) | `fl2_review.sh paper2021` |
| `diagnostics/fastlio2/review_20261009_utbm_extrinsic_no_restamp/` | review: utbm 8/9/10 with the dataset extrinsic but scans still end-stamped (superseded by the re-stamped benchmark runs) | `fl2_review.sh v2` |
| `diagnostics/fastlio2/review_20261009_utbm_variants/` | review: one utbm 8 run each -- de-skew off, extrinsic estimation off, extrinsic yaw +-90 deg, LiDAR clock +-50 ms (`cfg/` holds the variant configs) | `run_fastlio2_utbm.sh` with `UTBM_CFG` / `UTBM_TIME_SHIFT` |
| `diagnostics/fastlivo2/native_avx512_build/` | FAST-LIVO2 built with upstream `-march=native` (AVX-512): sbs_02 diverges; runs truncated by the old 5 s drain | old image |
| `diagnostics/fastlivo2/skylake_build_test/` | first Skylake-ISA build test (sbs_02 / eee_02) | diagnostic image |
| `diagnostics/fastlivo2/INVALID_generic_build_abi_mismatch/` | invalid: only FAST-LIVO2 rebuilt without -march (Eigen ABI mismatch with vikit) -- do not use | diagnostic image |
| `diagnostics/fastlivo2/eee02_start_offset_0.3s/` | eee_02 replayed from 0.3 s (start-offset test) | `run_fastlivo2.sh ... -s 0.3` |
| `diagnostics/fastlivo2/private_paper_default_config/` | private dataset with the paper's Sec. IX-A defaults | `avia_private_g*_paperdefault.yaml` |
| `diagnostics/stage2/smoke_20s_world_gravity_ignored/` | first 20 s Stage 2 run, before the gen_world.py gravity fix (world gravity ignored by Gazebo: 9.8000 m/s^2 at rest) | `record_scripted.sh` |
| `diagnostics/stage2/llvmpipe_room_120s/` | 120 s room bag + gate + diagnostics recorded with Mesa llvmpipe (GPU down before the reboot); passed the gate; superseded | `record_scripted.sh` (CPU override) |
| `diagnostics/stage2/gpu_room_120s_unthrottled/` | 120 s GPU room bag with the guide's camera `updateRate 0.0`: 2471 frames, bursts with repeated stamps; superseded by the throttle fix | `record_scripted.sh` |
| `diagnostics/stage2/lockstep_test/` | 40 s bags with/without `gzserver --lockstep`: exact camera frames but Mid-360 halved to 5 Hz; lockstep rejected | scratch launch file |

Reports: `docs/fastlio2_reproduction_log.md`, `docs/fastlivo2_reproduction_log.md`, `docs/stage2_log.md`,
`docs/FAST-LIO2_FAST-LIVO2_Test_Commands.pdf` (all commands to build, test and evaluate).
