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
| `stage3/scripted/` | Stage 3a (2026-11-16): the Stage 2 scripted bag with IMU noise through all three algorithms, 3 runs each. `bags/` noised bag + noise parameters, `gt/` ground truth, `orbslam3/euroc_room__imu1.0/` EuRoC folder, `<algo>/<algo>__room__r<N>.*` (trajectory `.tum`, logs, `cost.csv`, `latency.csv`), `eval/` (evo zips, `*_extra.json`, `*_errors.csv`, `summary.md`, `summary_extra.md`), `orbslam3_times/` (timing build) | `scripts/stage3/run_all_algos.sh`, `orbslam3_timing.sh` |
| `stage3/flights/` | PX4 SITL flight bags: `room_square.bag` (the gate flight, recording of 2026-11-16 21:16) with `.gate.txt`, `.clearance.txt`, `.mission.log`, `.sim.log`, `.overview.png`, `.onboard_left.mp4`; `room_square_gear05.*` (0.5 m landing-gear test: rocks at lift-off, bounces on landing); `v1_no_gear/`, `v2_gear_as_link/` (the two flights that exposed set-up faults) | `scripts/stage3/px4_record.sh`, `verify_sim_bag.py --flight`, `plot_flight.py` |
| `stage3/px4/` | Stage 3b gate results on `flights/room_square.bag`: same layout as `stage3/scripted/`, condition `room_square` | `scripts/stage3/run_all_algos.sh`, `orbslam3_timing.sh` |
| `stage3/px4_recording1/` | the same flight's first recording (2026-11-16 20:04; its raw bag was overwritten): noised bag, ground truth, EuRoC folder, gate file and 3 runs per algorithm | `scripts/stage3/run_all_algos.sh` |
| `stage3/px4_v1_no_gear/` | results on the first flight (no landing gear, no hop): ORB-SLAM3 never initialises, FAST-LIVO2 0.17 m | `scripts/stage3/run_all_algos.sh` |
| `stage3/diag/` | diagnostic A7 (camera thinned to 10 Hz for FAST-LIVO2) and `gear05/` (one run per algorithm on the 0.5 m-gear flight) | `scripts/stage3/thin_camera.py`, `run_all_algos.sh` |
| `stage3/logs/` | build log of `evtol/orbslam3:v1-times`, run logs of the 17 Nov re-verification | -- |
| `stage4/flights/` | every Stage 4 flight bag (room linked from Stage 3) with `.gate.txt`, `.clearance.txt`, `.mission.log`, `.sim.log`; `urban_alt50_try*/` flights that failed the LiDAR-timing gate under load | `scripts/stage4/run_matrix.sh` |
| `stage4/{environments,altitude,speed,imu,faults}/` | one folder per group, same layout as `stage3/px4/` (3 runs per algorithm per condition, `eval/summary_extra.md`); `faults/flights/` holds the nine degraded room bags (+ `.fault.json`); `altitude/ground_points.csv` | `run_matrix.sh`, `run_extras.sh`, `degrade_bag.py`, `ground_points.py` |
| `stage4/headroom/rate{2,4,8}/` | FAST-LIO2 and FAST-LIVO2 replayed at 2x/4x/8x (room, urban_speed5); `headroom_rate4_failed_1757/` the aborted first 4x set, `headroom_aborted_1517/` a set stopped when urban flights were redone | `run_extras.sh` |
| `stage4/fig_*.png`, `stage4/figures/`, `stage4/stage4_tables.md` | sweep figures (guide and flight-window versions), scorecard, fault timelines, altitude, cost; all tables | `plot_sweeps.py`, `stage4_figures.py` |
| `stage4/superseded_hop_at_cruise/`, `stage4/superseded_hop_at_liftoff/` | the two superseded urban/field sets (Stage 4 log, deviations 10 and 12); their noised `bags/*.bag` copies were deleted 2026-11-17 (disk full), results and flights kept | -- |
| `stage4/diag/hoptest/` | test flight with a real hop at 1.9 m over the plaza: ORB-SLAM3 still never starts (~320 ORB features) | `px4_record.sh` |
| `stage4/logs/` | flight, run and launcher logs; `load.log` (load average every 15 s) | -- |
| `verify_stage4/`, `verify_stage4.log` | the Stage 4 verification: re-scored copy of every run (`rescore/`, with regenerated tables and figures), the live room replay (`replay/`), an optional new flight (`fly/`); replaced on every run | `scripts/stage4/verify_stage4.sh` |
| (deleted 2026-11-17) | to free disk, with the user's approval: every Stage 4 noise-injected input copy (`<group>/bags/*.bag`; the `.imu_noise.json` records are kept) and every ORB-SLAM3 image export (`orbslam3/euroc_*`), and the large files of the failed/aborted test runs. `run_all_algos.sh` rebuilds both from the kept flight bags when a condition is run again (fixed seed: a rebuilt copy was checked byte-identical); a re-score reads only `gt/` and the trajectories | -- |
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
| `diagnostics/stage2/worlds_load/` | 20 s bag + gate per world (room, room_plain, corridor, field, urban): all 13/13 PASS | `record_scripted.sh <world> 20` |
| `diagnostics/stage2_e2e/` | end-to-end smoke test: the final Stage 2 bag through FAST-LIO2, FAST-LIVO2 and ORB-SLAM3 (generated configs), scored by the eval image (`eval/summary.md`); `harness/` holds the script and the guide's Stage 3 launch files it used | see `docs/stage1_2_audit.md` |
| `diagnostics/stage1_tools_check/` | the 55 stored ORB-SLAM3 EuRoC runs re-scored with the guide's shared tools (`csv_to_tum.py`, `eval_traj.sh`, `results_table.py`): identical to final_results | `rescore.sh` (eval container) |

Reports: `docs/fastlio2_reproduction_log.md`, `docs/fastlivo2_reproduction_log.md`, `docs/stage2_log.md`, `docs/stage1_2_audit.md`, `docs/stage3_log.md`, `docs/stage4_log.md`,
`docs/FAST-LIO2_FAST-LIVO2_Test_Commands.pdf` (all commands to build, test and evaluate).
