# Stages 1 and 2 -- goal audit and end-to-end compatibility (2026-11-05)

Checked after the Stage 2 commit (`b724ea4`), on the GPU (RTX 5090, driver 595.99.02), against
`eVTOL-SLAM-Complete-Project-Guide.pdf`. Question: is every goal the guide sets for Stages 1 and 2
met, and do the Stage 1 images, the Stage 2 simulator and the evaluation chain work together the
way Stage 3 will use them?

## Stage 1 goals (guide Sec. 1.1-1.12)

Goal: *build the three algorithms in isolated containers and prove the builds correct by
reproducing the accuracy their papers publish.*

| Guide item | Evidence | Status |
|---|---|---|
| Gate 1 -- the host is ready (1.4) | `bash scripts/verify_host.sh`: "Host is ready" | met |
| Base digest pinned (1.4) | `docker/base.Dockerfile` `FROM ubuntu:20.04@sha256:8feb4d8c...`, in VERSIONS.md | met |
| Gate 2 -- the base works (1.6) | `bash scripts/verify_base.sh`: noetic; OpenGL "NVIDIA GeForce RTX 5090/PCIe/SSE2" | met |
| One eval image for all algorithms (1.6) | `evtol/eval:v1`, evo 1.31.1 | met |
| Three algorithm images (1.9-1.11) | `evtol/orbslam3:v1`, `fastlio2:v1`, `fastlivo2:v1`; quick suite **24 PASS / 0 FAIL / 1 SKIP** (skip: NTU-VIRAL reference files are in the bin) | met |
| Shared evaluation tools (1.7) | were **missing** (this repo did Stage 1 from the earlier runbooks); added now, see below | **fixed** |
| The deliverable and gate (1.12): table of our error beside the published error, within roughly 10-20 % | `final_results/{orbslam3,fastlio2,fastlivo2}_comparison.csv` (Stage 1 closed 2026-10-20, `e8a3fdc`); ORB-SLAM3 mean of 11 medians 0.0327 m vs 0.035 m (-6 %); every non-green FAST-LIO2/FAST-LIVO2 row is explained in its reproduction log; `git diff final_results/` empty | met |
| "Earlier runbook" defects (front matter): ORB-SLAM3 output name, ns timestamps, FAST-LIVO2 topic | `scripts/eval_orbslam3.sh` divides by 1e9; run scripts pass bare names; FAST-LIVO2 scored on `/aft_mapped_to_init` | met |

Datasets differ from the guide's suggestions (FAST-LIO2: LIO-SAM/NCLT/UTBM/LiLi-OM instead of the
Avia bags; FAST-LIVO2: NTU-VIRAL + the authors' private sequences instead of MARS-LVIG). The gate
-- published accuracy reproduced -- is what matters, and it was met on more data than the guide
asks for. The 260 GB of Stage 1 data is in the bin, so Stage 1 can be re-scored but not re-run.

### The six shared tools, now added

`scripts/common/{eval_traj.sh, results_table.py, csv_to_tum.py, bag_to_tum.py, run_ros_algo.sh,
latency_probe.py}`, transcribed verbatim with `scripts/tools/guide_extract.py` (pages 9-32).
Stage 3's `run_all_algos.sh` and Stages 4 and 6 call them. Two changes were needed to make them
run in this repo's images:

| # | Problem | Fix |
|---|---|---|
| A | `evtol/eval:v1` puts evo in a virtualenv (`/opt/eval-venv`) and makes it the default `python3`; that interpreter cannot import `rosbag` (no Cryptodome, no ROS path). The guide runs `bag_to_tum.py` etc. as `docker compose run --rm eval python3 ...` | new `scripts/common/ros_python.sh`: sources ROS (and `/ws/devel` if present) and runs the system `/usr/bin/python3`. Works in every image; the eval image is not rebuilt, so Stage 1 scoring is untouched |
| B | `eval_traj.sh --save_plot` crashed: evo calls `matplotlib.use(<plot_backend>)`, default TkAgg, ignoring `MPLBACKEND`; the eval image has no tkinter | `eval_traj.sh` runs `evo_config set plot_backend Agg` first (throwaway container config) |

**Proof the tools agree with Stage 1:** all 55 stored ORB-SLAM3 EuRoC runs re-scored with
`csv_to_tum.py` + `eval_traj.sh` + `results_table.py` give the **identical** APE RMSE per run
(max difference 0.0 m) and the identical 11 medians as `final_results/orbslam3_comparison.csv`
(`output/diagnostics/stage1_tools_check/`). The guide's coverage column then reads 0.81 / 0.83 for
MH04 / MH05: not lost tracking (key frames never more than 3 s apart) but ORB-SLAM3's
stereo-inertial initialisation, which on those dark, fast-start sequences takes 3-20 s.

## Stage 2 goals (guide Sec. 2.1-2.9)

Goal: *a simulated Mid-360 LiDAR, IMU and stereo camera whose data is provably correct before any
SLAM algorithm touches it.* Gate: *verify_sim_bag.py passes every check.*

| Guide item | Evidence | Status |
|---|---|---|
| 2.1/2.6 simulation image | `evtol/sim:v1`; Gazebo 11.15.1, PX4 v1.14.4 (commit asserted), patched Mid-360 plugin; renders on the RTX 5090 | met |
| 2.2 one rig file | `config/rig.yaml`, byte-identical to the guide | met |
| 2.3 generator + two by-eye checks | 11 printed files regenerate byte-identically (before deviation 6); T_b_c column 3 = (0.819, 0, 0.574); right camera +0.11 m on left x | met |
| 2.4 trajectory driver | compiles; 8 s hold then the figure path (bag: motion from 8.44 s) | met |
| 2.5 five worlds | all five load and pass the gate in a 20 s run (`output/diagnostics/stage2/worlds_load/`) | met |
| 2.7 first look, with your eyes | done by the user 2026-11-05 ("everything looks fine"), `scripts/stage2/first_look.sh` | met |
| 2.8 record, then prove (the gate) | `output/stage2/scripted_room.bag` (120 s, GPU): 13/13 PASS, IMU vs ground truth RMS 0.001 m/s^2 over 2399 samples | met |
| 2.9 troubleshooting items | trajectory driver loaded; camera roll pi; glxinfo names the GPU | met |

Every Stage 2 file differs from the guide only by a documented deviation (docs/stage2_log.md,
1-7). Deviation 7 (the gate's IMU/ground-truth pairing could fail a correct bag, depending on a
0-4 ms start-up phase) was found during this audit by the five-world test.

## Stage 1 <-> Stage 2 interfaces

| Interface Stage 3 relies on | Check | Result |
|---|---|---|
| Livox `CustomMsg` definition | MD5 in sim, fastlio2 (`livox_ros_driver` v2.6.0) and FAST-LIVO2's bundled header | all `e4d6829bdfe657cb6c21a746c86b21a6` |
| same mounts in every service | compose `x-common`: `/data` ro, `/config` ro, `/scripts` ro, `/output` | identical for all six services |
| `/ws/devel/setup.bash` (run_ros_algo.sh) | fastlio2, fastlivo2, sim | present |
| ORB-SLAM3 binary + vocabulary paths used by Stage 3 | `/opt/ORB_SLAM3/Examples/Stereo-Inertial/stereo_inertial_euroc`, `Vocabulary/ORBvoc.txt` | present |
| bag tools in the eval image | `ros_python.sh` (fix A) | works |
| evo plots | fix B | works |
| `scripts/stage1/...` paths in later stages | only Stage 1 itself uses them (flat `scripts/` here is fine) | no conflict |
| strictly increasing, paired image stamps | deviation 6; `bag_to_euroc.py`: 2395 of 2395 frames paired | ok |

## End-to-end run

The final Stage 2 bag through each Stage 1 image with its Stage 2 generated config, scored by the
Stage 1 eval image -- the steps of the guide's Stage 3 `run_all_algos.sh`, without its IMU-noise
injection (the IMU is noise-free), one run each. Stage 3 launch files and `bag_to_euroc.py` were
taken unmodified from the guide for this test only (not committed; harness in
`output/diagnostics/stage2_e2e/harness/`).

| Algorithm | Config | APE RMSE | RPE / 1 m | Coverage | Log |
|---|---|---|---|---|---|
| FAST-LIO2 | `fastlio2_sim.yaml` | **0.036 m** | 0.007 m | 0.997 | clean (one "No point" on the first scan) |
| FAST-LIVO2 | `fastlivo2_sim.yaml` + `_camera.yaml` | **0.063 m** | 0.039 m | 0.997 | 2394 images received; VIO ran on 1197 frames (about 73 visual points updated per frame) |
| ORB-SLAM3 | `orbslam3_sim.yaml` | **0.007 m** | 0.006 m | 0.908 | one map, 74 key frames, no reset or loss |

All three track the 120 s room flight (6 x 4 x 1 m) to centimetres: the bag, the generated
extrinsics and the images are compatible end to end. These are smoke-test numbers (one run,
noise-free IMU), not Stage 3 results.

## Carried into Stage 3

1. **Run bag tools through `ros_python.sh`** in `run_all_algos.sh` (and Stage 4/6 scripts):
   `$C eval bash /scripts/common/ros_python.sh /scripts/common/bag_to_tum.py ...`. Same for
   `imu_noise.py` and `bag_to_euroc.py`.
2. **ORB-SLAM3 coverage is capped near 0.91 on this path**: its IMU initialisation needs motion, and
   the path holds still for 8 s and then ramps up gently until 12 s (first key frame at 12.1 s).
   `results_table.py`'s "worst coverage < 0.95" warning will always fire here; it is not
   tracking loss.
3. **FAST-LIVO2 runs VIO on alternate images.** It cuts the LiDAR stream at each image time; with
   patch 1 all 20 000 points of a scan share one stamp, so at 20 Hz camera / 10 Hz LiDAR every
   second image gets no new points ("[ LIO ]: No point!!!" / "[ VIO ] No point!!!", 1195 times)
   and only propagates. A real Mid-360 spreads points over the scan. Its RPE (0.039 m per metre)
   is higher than FAST-LIO2's (0.007); whether this interleaving is the cause is not
   investigated yet -- a Stage 3 question.
4. The two `config/launch/*.launch` files, `bag_to_euroc.py` and `imu_noise.py` are Stage 3 files;
   the launch files and converter already ran unmodified here.

## Not checked

- Re-running Stage 1 on its datasets (they are in the bin); stored runs were re-scored instead.
- The functional (L2) level of `scripts/test_containers.sh` (needs those datasets).
- `latency_probe.py` (only runs with `LATENCY=1`, a Stage 6 measurement); the other five shared
  tools were all exercised above.
