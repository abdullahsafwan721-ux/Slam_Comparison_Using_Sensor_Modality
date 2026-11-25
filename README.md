# SLAM_Comparison_Sensor_Modality_Using_Same_Dataset

**Camera, LiDAR, or both?** This project compares three SLAM algorithms for low-flying eVTOL aircraft
and drones on the **same data**: the same simulated sensor rig, the same flights and the same ground
truth. It goes from reproducing each algorithm's paper to letting each SLAM algorithm fly a PX4 drone
on its own.

| SLAM algorithm | Sensors | How it estimates the pose |
|---|---|---|
| [ORB-SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3) | stereo camera + IMU | tracks ORB corner features between images, refines keyframes by bundle adjustment, closes loops |
| [FAST-LIO2](https://github.com/hku-mars/FAST_LIO) | LiDAR + IMU | predicts with the IMU, then fits every LiDAR point to a nearby plane of its map in an iterated Kalman filter |
| [FAST-LIVO2](https://github.com/hku-mars/FAST-LIVO2) | LiDAR + camera + IMU | the same LiDAR update, then a photometric update that compares small image patches, in one filter |

Everything runs in Docker with pinned versions ([VERSIONS.md](VERSIONS.md)). Every step is one script,
and every stage has a verification script. The full procedure below was run end to end on a fresh
checkout on 20 Nov 2026: 49 of 49 steps passed. Stage 1's dataset downloads are documented here but were
not repeated in that run.

## Contents

- [The five stages](#the-five-stages)
- [Main results](#main-results)
- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Setup: machine, code and Docker images](#setup-machine-code-and-docker-images)
- [Stage 1: reproduce the papers](#stage-1-reproduce-the-papers)
- [Stage 2: the simulated sensor rig](#stage-2-the-simulated-sensor-rig)
- [Stage 3: the three SLAM algorithms on simulated data](#stage-3-the-three-slam-algorithms-on-simulated-data)
- [Stage 4: the experiment matrix](#stage-4-the-experiment-matrix)
- [Stage 5: PX4 flies on SLAM alone](#stage-5-px4-flies-on-slam-alone)
- [Verification scripts](#verification-scripts)
- [How the results are scored](#how-the-results-are-scored)
- [Time and disk space](#time-and-disk-space)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Versions and licences](#versions-and-licences)

## The five stages

| Stage | Question | Data | Main scripts | Passes when |
|---|---|---|---|---|
| 1 Reproduce the papers | Do our Docker builds give the published accuracy? | each paper's public datasets: 41 sequences, 5 runs each | `run_orbslam3_euroc.sh`, `fl2_benchmark.sh`, `livo2_benchmark.sh` | within 15 % of a like-for-like reference |
| 2 Simulated sensor rig | Do the simulated sensors tell the truth? | Gazebo 11: Livox Mid-360 LiDAR, its IMU and a stereo camera; five worlds | `record_scripted.sh`, `verify_sim_bag.py` | every sensor check against ground truth passes |
| 3 SLAM on simulated data | Do all three work on the rig, also on a real PX4 flight? | a scripted recording and a PX4 SITL flight | `run_all_algos.sh`, `px4_record.sh` | centimetre error, full coverage |
| 4 Experiment matrix | Where does each one break? | 26 conditions: world, altitude, speed, IMU grade, sensor faults | `run_matrix.sh`, `run_extras.sh` | every flight passes the sensor gate, all runs scored |
| 5 Closed loop | Can PX4 fly with SLAM as its only position source? | live flights; GPS, barometer and compass off | `run_closed_loop.sh`, `run_closed_loop_matrix.sh` | missions complete, a few cm of error, steady hover |

Each stage feeds the next: Stage 1 proves the builds, Stage 2 proves the simulator, Stage 3 proves the
pipeline on simulated data, Stage 4 measures the limits on recorded flights, and Stage 5 lets the
estimate fly the vehicle.

## Main results

**Stage 1, reproduction** (median of 5 runs per sequence):

- **ORB-SLAM3:** 3.27 cm averaged over the 11 EuRoC sequences, against 3.5 cm in its paper.
- **FAST-LIO2:** matches wherever a like-for-like reference exists, on 11 of its 16 sequences. Nine are
  within 15 %, UTBM 10 is at +24.6 %, and NCLT 8's reference lies inside the spread of our runs.
- **FAST-LIVO2:** within 15 % of the authors' released results on 8 of the 9 NTU-VIRAL sequences.

**Stages 3 and 4, accuracy on the same flights** (absolute position error over the flight, median of
3 runs):

| Condition | FAST-LIO2 | FAST-LIVO2 | ORB-SLAM3 |
|---|---|---|---|
| Room, PX4 flight | 0.70 cm | 0.29 cm | 0.60 cm |
| Room without textures | 0.75 cm | 0.30 cm | 0.73 cm |
| 60 m corridor | 28.6 cm | 7.4 cm | lost (12.5 m) |
| Open field | fails (5.8 m) | 2.6 cm | fails (9 m, 31 % covered) |
| Urban, 20 m altitude | 0.5 cm | 0.4 cm | 17.5 cm |
| Urban, 60 m altitude | 46 cm | diverges (530 m) | 32.0 cm |
| Figure-8 at 8 m/s | 0.4 cm | 0.9 cm | 6.8 cm |
| IMU noise ×30 | 1.0 cm | 1.1 cm | diverges (98 m) |

**Stage 5, closed loop:**

- **FAST-LIO2:** every room mission completed with FAST-LIO2 as PX4's only position source. PX4's
  estimate stayed within 2.6 to 5.3 cm of the truth, and a 120 s hover did not drift.
- **FAST-LIVO2:** flies just as well once PX4 is told that its pose is 150 ms old
  (`EKF2_EV_DELAY`). At 50 m and 60 m altitude its estimate diverged, and the drone crashed or flew
  away.
- **ORB-SLAM3:** cannot close the loop. It gives no pose until the vehicle has moved, and PX4 will not
  take off without one.
- **The lesson:** PX4's estimator rejects sudden jumps, but it follows a smooth drift. Flying on SLAM
  alone needs an independent integrity check.

There is no single winner. FAST-LIVO2 is the most accurate wherever both of its sensors see structure.
FAST-LIO2 is the cheapest to run and the most predictable, but fails where the LiDAR geometry runs out.
ORB-SLAM3 is competitive only indoors.

## Repository layout

```
SLAM_Comparison_Sensor_Modality_Using_Same_Dataset/
├── compose.yaml              one service per Docker image, plus host-network services for Stage 5
├── VERSIONS.md               every pinned upstream commit and tag
├── docker/                   Dockerfiles: base, orbslam3 (+ timing build), fastlio2, fastlivo2, eval, sim
├── config/
│   ├── rig.yaml              the one description of the simulated sensor rig (Stages 2-5)
│   ├── generated/            SLAM configurations generated from rig.yaml (do not edit by hand)
│   ├── launch/               FAST-LIO2 and FAST-LIVO2 launch files for simulated data
│   ├── fastlio2/, fastlivo2/ Stage 1 configurations for each paper's datasets
│   └── px4/ev_only.params    Stage 5: PX4's estimator on external vision only
├── sim/evtol_sim/            Gazebo package: rig and drone models, the five worlds, scripted trajectory driver
├── scripts/
│   ├── *.sh, *.py            Stage 1: dataset preparation, runs and scoring for each algorithm
│   ├── common/               shared tools: generators, bag conversion, IMU noise, scoring, metrics
│   ├── stage2/ ... stage5/   one folder per stage, each with its verification script
│   ├── tools/                independent APE check, simulation speed, window pictures
│   ├── third_party/          the FAST-LIO authors' NCLT converter, kept verbatim
│   ├── verify_host.sh        Gate 1: the host
│   ├── verify_base.sh        Gate 2: the base image (ROS, GPU, OpenGL)
│   ├── test_containers.sh    container self-tests
│   └── verify_stage1.sh      Stage 1 verification
├── docs/
│   ├── fastlio2_reproduction_log.md, fastlivo2_reproduction_log.md, stage1_2_audit.md
│   ├── stage2_log.md ... stage5_log.md    what was done in each stage, why, and the results
│   ├── final_verification.md             the final check of all five stages
│   ├── results/                          Stage 1 comparison tables and per-run summaries
│   └── make_final_results.py             builds final_results/ from the scored Stage 1 runs
├── final_results/            Stage 1 deliverable: paper against ours, one CSV per algorithm
├── data/                     not in git: the Stage 1 datasets
└── output/                   not in git: every run, flight, score, table and figure
```

`data/` and `output/` are created on your machine. The slides, reports and e-books made for presenting
the project are not part of this repository.

## Requirements

| | Needed | Machine the results were produced on |
|---|---|---|
| Processor | x86-64 with AVX2 (FAST-LIVO2 is compiled for `-march=skylake`) | AMD Ryzen 9 9950X, 32 threads |
| Graphics | an NVIDIA GPU and driver: Gazebo renders the simulated cameras on it | NVIDIA GeForce RTX 5090 |
| Memory | 16 GB at least (build the images one at a time) | 30 GB |
| Disk | about 20 GB for the images, plus results (see [Time and disk space](#time-and-disk-space)); Stage 1 needs another 260 GB for its datasets | |
| System | Ubuntu 22.04 or 24.04 with a graphical X11 desktop | Ubuntu 24.04.5 LTS |
| Software | Docker Engine with the Compose plugin, usable without `sudo`; NVIDIA Container Toolkit; git; Python 3 with PyYAML, NumPy and Matplotlib (and ReportLab for Stage 1's final table) | Docker 29.8.2, Compose 5.5.1 |
| Network | GitHub, the Ubuntu and ROS package servers and PyPI, while the images build | |

ROS Noetic, Gazebo, PX4, OpenCV and the three SLAM algorithms are all inside the images. The host needs
no ROS.

## Setup: machine, code and Docker images

### 1. Install Docker and the NVIDIA Container Toolkit

Follow the vendors' instructions for Ubuntu:
[Docker Engine](https://docs.docker.com/engine/install/ubuntu/) (with `docker-compose-plugin`) and the
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
Then:

```bash
sudo usermod -aG docker $USER                 # log out and in again: docker without sudo
sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
sudo apt-get install -y python3-yaml python3-numpy python3-matplotlib python3-reportlab   # host-side scripts
```

Install Docker from Docker's own package source only. A second Docker from the snap store can take
over after a restart and hide all the images.

### 2. Get the code

```bash
git clone https://github.com/abdullahsafwan721-ux/Slam_Comparison_Using_Sensor_Modality.git SLAM_Comparison_Sensor_Modality_Using_Same_Dataset
cd SLAM_Comparison_Sensor_Modality_Using_Same_Dataset
```

Run every command in this README from this folder. Keep its path free of spaces, because one Stage 5
script passes the folder path to Docker unquoted.

### 3. Prepare the host (Gate 1)

```bash
xhost +local:docker            # let containers open windows on your screen (once per login)
mkdir -p data output           # create them yourself, or Docker creates them owned by root
bash scripts/verify_host.sh    # Gate 1: every line OK, last line "Host is ready."
```

Containers write as root. Files they leave under `output/` belong to root: delete them with
`sudo rm` or with `docker compose run --rm eval rm -rf /output/<path>`.

### 4. Build the Docker images (about 1 hour, about 20 GB)

```bash
docker build -t evtol/base:noetic -f docker/base.Dockerfile .
bash scripts/verify_base.sh              # Gate 2: BASE_OK and an OpenGL renderer that names your NVIDIA GPU
docker compose build orbslam3
docker compose build fastlio2
docker compose build fastlivo2
docker compose build eval
docker compose build sim                 # the longest, about 40 minutes
docker compose build orbslam3_times      # only Stage 3's timing step needs it
docker images "evtol/*"
bash scripts/test_containers.sh quick    # every check PASS; SKIP is normal on a fresh copy
```

Build the images one at a time: OpenCV, PX4 and FAST-LIVO2 each compile with 8 jobs. With little
memory, add `--build-arg JOBS=4` to a build.

| Image | Contents | Used in |
|---|---|---|
| `evtol/base:noetic` | Ubuntu 20.04 (pinned digest), ROS Noetic, OpenGL | every other image starts from it |
| `evtol/orbslam3:v1` | OpenCV 4.4.0, Pangolin 0.6, ORB-SLAM3 v1.0 | Stages 1, 3, 4 |
| `evtol/orbslam3:v1-times` | the same, with ORB-SLAM3's timing instrumentation on | Stage 3 timing only |
| `evtol/fastlio2:v1` | Livox SDK and ROS driver, FAST-LIO2 at its pinned commit | Stages 1, 3, 4, 5 |
| `evtol/fastlivo2:v1` | Sophus, rpg_vikit, FAST-LIVO2, built for `-march=skylake` | Stages 1, 3, 4, 5 |
| `evtol/eval:v1` | evo 1.31.1 and the scoring scripts | every stage |
| `evtol/sim:v1` | Gazebo 11, PX4 v1.14.4 SITL, MAVROS, the Livox Mid-360 simulation plugin | Stages 2-5 |

## Stage 1: reproduce the papers

**Goal:** show that each Docker build is the algorithm its authors published. Each algorithm is rerun
on the public datasets of its own paper with the paper's protocol, 5 runs per sequence, and compared
with a like-for-like reference. That is the paper's own value where its protocol can be reproduced,
and otherwise an independent re-run (FAST-LIO2) or the authors' released results (FAST-LIVO2). Within
15 % is green, 15-30 % amber, above 30 % red.

Stage 1 is the only stage that needs the public datasets (about 260 GB). Later stages use only the
simulator, so you can go straight to Stage 2.

### Datasets and where they go

| Dataset | SLAM algorithm | Source | Put it in |
|---|---|---|---|
| EuRoC MAV, 11 sequences | ORB-SLAM3 | [ETH Research Collection](https://doi.org/10.3929/ethz-b-000690084): `machine_hall.zip`, `vicon_room1.zip`, `vicon_room2.zip`. Download them in a browser: the server refuses scripted downloads (HTTP 429) | `data/euroc/.zips/*.zip` |
| KA-Urban (LiLi-OM) | FAST-LIO2 | links in the [LiLi-OM README](https://github.com/KIT-ISAS/lili-om) | `data/lili/KA_Urban_Schloss_1.bag`, `..._Schloss_2.bag`, `KA_Urban_East.bag` |
| LIO-SAM | FAST-LIO2 | links in the [LIO-SAM README](https://github.com/TixiaoShan/LIO-SAM) | `data/liosam/garden_dataset.bag`, `park_dataset.bag`, `campus_large_dataset.bag` |
| UTBM | FAST-LIO2 | [UTBM robocar dataset](https://epan-utbm.github.io/utbm_robocar_dataset/) | `data/utbm/utbm_20180719.bag`, `utbm_20190131.bag`, `utbm_20190418.bag` |
| NCLT, 7 sessions | FAST-LIO2 | [NCLT](https://robots.engin.umich.edu/nclt/): `<date>_sen.tar.gz`, `<date>_vel.tar.gz`, `groundtruth_<date>.csv` | `data/nclt/raw/*.tar.gz`, `data/nclt_gt/groundtruth_<date>.csv` |
| NTU-VIRAL, 9 sequences | FAST-LIVO2 | [NTU-VIRAL](https://ntu-aris.github.io/ntu_viral_dataset/); ground truth from [viral_eval](https://github.com/ntu-aris/viral_eval) | `data/ntu_viral/<seq>/<seq>/<seq>.bag`, `data/ntu_viral/viral_eval/` |
| FAST-LIVO2 authors' dataset | FAST-LIVO2 | the Google Drive folder linked from the [Global-LVBA README](https://github.com/xuankuzcr/Global-LVBA) | `data/fastlivo2_private/*.bag` |

### Run

```bash
# ORB-SLAM3 on EuRoC: unpack the archives, 5 runs of all 11 sequences, then score
bash scripts/fetch_euroc.sh
docker compose run --rm -e RUNS=5 orbslam3 bash /scripts/run_orbslam3_euroc.sh
docker compose run --rm eval bash /scripts/eval_orbslam3.sh

# FAST-LIO2: prepares every sequence found in data/, runs it 5 times in parallel containers, scores
bash scripts/fl2_benchmark.sh
ONLY="utbm8 nclt5" WAIT=0 bash scripts/fl2_benchmark.sh     # or only a selection

# FAST-LIVO2: NTU-VIRAL and the authors' dataset (runs for hours, so start it as a service),
# then NTU-VIRAL again with the authors' "matched start" protocol
systemd-run --user --unit=livo2-bench --collect --working-directory="$PWD" \
    bash scripts/livo2_benchmark.sh
bash scripts/livo2_ntu_matched.sh

# The deliverable: final_results/*.csv, paper against ours
python3 docs/make_final_results.py
```

`fl2_benchmark.sh` waits until a sequence's files are completely downloaded. It converts NCLT, builds
the ground truth, and refuses to run when the data's per-point LiDAR time unit does not match the
configuration.

### Results

- `final_results/{orbslam3,fastlio2,fastlivo2}_comparison.csv`
- `docs/results/*_comparison.md`
- every run's trajectory and score under `output/`

The details, including why FAST-LIO2's NCLT and UTBM errors are compared with independent re-runs
rather than the paper's own table, are in `docs/fastlio2_reproduction_log.md` and
`docs/fastlivo2_reproduction_log.md`.

## Stage 2: the simulated sensor rig

**Goal:** build the simulated sensor rig and prove that every sensor tells the truth before any SLAM
algorithm sees it: right rates, right time stamps, right positions on the rig, and an IMU that agrees
with the motion the simulator applied. The rig flies a scripted path with no autopilot, so that only
the sensors are being tested.

`config/rig.yaml` is the one description of the rig:

- **LiDAR:** a Livox Mid-360, 10 Hz scans of 20 000 points, mounted upside down. Its vertical field of
  view of -7° to +52° then becomes -52° to +7°, so it sees the ground.
- **IMU:** the Mid-360's IMU at 200 Hz.
- **Camera:** a stereo pair looking forward and 35° down: 752 × 480 pixels, 20 Hz, 11 cm baseline,
  like the EuRoC cameras.

Two generators write everything that depends on the rig:

- `scripts/common/gen_configs.py` writes the simulator model and every SLAM configuration in
  `config/generated/`.
- `scripts/common/gen_world.py` writes the five worlds. Each world starves one way of sensing:
  - `room`: textured and cluttered;
  - `room_plain`: the same room, grey;
  - `corridor`: 60 m with nothing along it, which leaves a LiDAR little to work with;
  - `field`: one flat plane;
  - `urban`: buildings around a plaza, for the altitude flights.

### Run

```bash
# Regenerate everything from rig.yaml; nothing may change
python3 scripts/common/gen_configs.py && python3 scripts/common/gen_world.py
git status --short -- sim config/generated          # must print nothing

# Record the scripted rig for 120 s in the room ("true" opens the Gazebo window)
docker compose run --rm sim bash /scripts/stage2/record_scripted.sh room 120 /output/stage2/scripted_room.bag true

# The Stage 2 gate: the sensors against the ground truth recorded in the bag
docker compose run --rm sim bash -c "source /scripts/common/sim_env.sh && \
    python3 /scripts/stage2/verify_sim_bag.py /output/stage2/scripted_room.bag \
    | tee /output/stage2/scripted_room.gate.txt"

# Timing and extrinsic diagnostics (pictures are written next to the bag)
docker compose run --rm sim bash -c "source /scripts/common/sim_env.sh && \
    python3 /scripts/stage2/sim_bag_diagnostics.py /output/stage2/scripted_room.bag /output/stage2/scripted_room_diag && \
    python3 /scripts/stage2/camera_check.py /output/stage2/scripted_room.bag /sim/worlds/room.world /output/stage2/scripted_room_camcheck"

# Look with your own eyes: Gazebo, the LiDAR cloud in RViz, the camera image (Ctrl-C to close)
docker compose run --rm sim bash /scripts/stage2/first_look.sh

# The other four worlds load and pass the same gate (20 s each)
for w in room_plain corridor field urban; do
  docker compose run --rm sim bash /scripts/stage2/record_scripted.sh $w 20 /output/stage2/worlds/$w.bag
  docker compose run --rm sim bash -c "source /scripts/common/sim_env.sh && \
      python3 /scripts/stage2/verify_sim_bag.py /output/stage2/worlds/$w.bag" | tail -2
done
```

### Passes when

The gate prints `ALL CHECKS PASSED -- Stage 2 gate open.`:

- every rate is nominal: IMU and ground truth 200 Hz, LiDAR 10 Hz, cameras 20 Hz;
- the rig holds still for more than 7 s at the start;
- at rest the IMU measures gravity as 9.8066 m/s².

In the diagnostics, every "peak at" is close to zero: rotations within 0.03°, translations within
3 mm, time stamps within 2 ms. Details: `docs/stage2_log.md`.

## Stage 3: the three SLAM algorithms on simulated data

**Goal:** run ORB-SLAM3, FAST-LIO2 and FAST-LIVO2 on simulated data and score them against the truth:
first on the Stage 2 recording (3a), then on a real PX4 flight in Gazebo (3b). Stage 3 also fixes the
protocol that every later flight follows.

`scripts/stage3/run_all_algos.sh` is the workhorse, and Stage 4 calls it for every condition. For one
bag it:

1. adds realistic IMU noise with a fixed seed: white noise and bias random walk;
2. extracts the ground truth and exports the bag in the EuRoC format that ORB-SLAM3 reads;
3. runs each algorithm N times, each run in a fresh container;
4. scores every run (see [How the results are scored](#how-the-results-are-scored)).

### Run

```bash
# 3a: the three algorithms on the Stage 2 recording, 3 runs each
bash scripts/stage3/run_all_algos.sh output/stage2/scripted_room.bag room output/stage3/scripted 3
cat output/stage3/scripted/eval/summary.md

# 3b: a PX4 SITL flight in the room (4 m square, 3 laps at 1.5 m/s), recorded
mkdir -p output/stage3/flights
docker compose run --rm -T -e GUI=true -e SPAWN="-2.0 -1.8" sim bash /scripts/stage3/px4_record.sh \
    room square /output/stage3/flights/room_square.bag --size 4 --alt 1.5 --speed 1.5 --laps 3 --hop-timing start

# the flight's sensor gate
docker compose run --rm -T sim bash -c "source /scripts/common/sim_env.sh && \
    python3 /scripts/stage2/verify_sim_bag.py /output/stage3/flights/room_square.bag --flight \
    | tee /output/stage3/flights/room_square.gate.txt"

# the three algorithms on the flight, 3 runs each, and the Stage 3 gate
bash scripts/stage3/run_all_algos.sh output/stage3/flights/room_square.bag room_square output/stage3/px4 3
cat output/stage3/px4/eval/summary.md
python3 scripts/stage3/verify_stage3.py gate output/stage3

# ORB-SLAM3's tracking time per frame, and one picture of the flight
bash scripts/stage3/orbslam3_timing.sh output/stage3/px4 room_square 3
python3 scripts/stage3/plot_flight.py sim/evtol_sim/worlds/room.world output/stage3/px4 room_square \
    output/stage3/flights/room_square.overview.png
```

The mission (`offboard_mission.py`) arms the drone, takes off to 1.5 m, makes a short 0.4 m hop, flies
the square and lands. The hop is there for ORB-SLAM3: its IMU initialisation needs a change of
acceleration of at least 0.5 m/s² between camera frames, and a smooth take-off does not give one.
`check_clearance.py` refuses to fly a path that touches anything in the world.

### Passes when

- The flight passes all its sensor checks.
- In the stored results, all three algorithms cover the flight: coverage 1.00 / 1.00 / 0.98.
- They do so at centimetre error. FAST-LIO2 0.70 cm, FAST-LIVO2 0.29 cm, ORB-SLAM3 0.75 cm.
- `verify_stage3.py gate` prints PASS.

Details and the protocol decisions: `docs/stage3_log.md`.

## Stage 4: the experiment matrix

**Goal:** find where each SLAM algorithm breaks. Every condition changes one thing against the Stage 3
room flight. Each condition is flown **once**, must pass the flight gate, and is then replayed through
all three algorithms 3 times, so that every algorithm sees exactly the same data.

| Group | Conditions | Flight |
|---|---|---|
| A environments | `room`, `room_plain`, `corridor`, `field` | room is the Stage 3 flight (linked, not flown again); a 60 m line at 2 m/s in the corridor; a 15 m figure-8 at 5 m over the field |
| B altitude | `urban_alt10` ... `urban_alt60` | a 30 m square over the urban plaza at 10, 20, ..., 60 m, at 4 m/s |
| C speed | `urban_speed2`, `_speed5`, `_speed8` | a 20 m figure-8 at 20 m altitude, at 2, 5 and 8 m/s |
| D IMU grade | `imu_x1`, `x3`, `x10`, `x30` | the 5 m/s figure-8 with 1, 3, 10 and 30 times the baseline IMU noise |
| E faults | 9 copies of the room flight, each with one sensor degraded | camera blackout 5 s, images dimmed to 30 % and 10 %, camera time stamps shifted by 5/10/20 ms; LiDAR dropout 2 s and 5 s, only 25 % of the points |
| Headroom | room and `urban_speed5` replayed at 2×, 4× and 8× real time | FAST-LIO2 and FAST-LIVO2 |

### Run

```bash
# Fly and gate every condition, one simulator at a time (group D reuses the 5 m/s flight)
STEP=fly ONLY=environments bash scripts/stage4/run_matrix.sh
STEP=fly ONLY=altitude     bash scripts/stage4/run_matrix.sh
STEP=fly ONLY=speed        bash scripts/stage4/run_matrix.sh
ls -lh output/stage4/flights/*.bag && grep -c "ALL CHECKS PASSED" output/stage4/flights/*.gate.txt

# Group E: nine degraded copies of the room flight
mkdir -p output/stage4/faults/flights
for v in cam_black_5s cam_dim30 cam_dim10 lidar_drop_2s lidar_drop_5s lidar_thin25 cam_dt5 cam_dt10 cam_dt20; do
  docker compose run --rm -T eval bash /scripts/common/ros_python.sh /scripts/stage4/degrade_bag.py \
      /output/stage4/flights/room.bag /output/stage4/faults/flights/room_$v.bag $v
done

# The algorithms on every flight and fault copy, 3 runs each (five streams side by side, no simulator needed)
STEP=algos ONLY=environments bash scripts/stage4/run_matrix.sh > output/stage4/logs/stream_A.log 2>&1 &
STEP=algos ONLY=altitude     bash scripts/stage4/run_matrix.sh > output/stage4/logs/stream_B.log 2>&1 &
STEP=algos ONLY=speed        bash scripts/stage4/run_matrix.sh > output/stage4/logs/stream_C.log 2>&1 &
STEP=algos ONLY=imu          bash scripts/stage4/run_matrix.sh > output/stage4/logs/stream_D.log 2>&1 &
ONLY=faults                  bash scripts/stage4/run_extras.sh > output/stage4/logs/stream_E.log 2>&1 &
wait; tail -n 4 output/stage4/logs/stream_*.log

# Real-time headroom (run it alone: it measures spare computing power)
ONLY=headroom bash scripts/stage4/run_extras.sh

# Ground returns per LiDAR scan at each altitude, then the tables and figures
docker compose run --rm -T sim bash -c "source /scripts/common/sim_env.sh && python3 /scripts/stage4/ground_points.py \
    /output/stage4/altitude/ground_points.csv /output/stage4/flights/urban_alt{10,20,30,40,50,60}.bag"
docker compose run --rm -T eval python3 /scripts/stage4/plot_sweeps.py /output/stage4
python3 scripts/stage4/stage4_figures.py output/stage4
cat output/stage4/stage4_tables.md
```

Never fly while the algorithm streams run. They load the processor, Gazebo's LiDAR then slips in
simulated time, and the flight fails its gate. A condition whose runs are complete is skipped when a
command is started again, so an interrupted group can simply be restarted. To repeat runs on purpose,
use the scripts' `FORCE=1` and `ALGOS=...` options. One example is ORB-SLAM3, whose results change
when other programs share the processor.

### What to expect

- **FAST-LIO2** stays at centimetres wherever the LiDAR sees structure. It drifts along the corridor
  and fails over the flat field, where the geometry runs out.
- **FAST-LIVO2** is the most accurate, from millimetres to a few centimetres, field included. It
  diverges at 60 m, is the most sensitive to camera timing, and has the least computing headroom
  (2-4× on the workstation, against more than 8× for FAST-LIO2).
- **ORB-SLAM3** needs texture close to its cameras. Over the plaza, from 20 to 60 m, it covers 62-77 %
  of the flight at 15-32 cm. It never starts at 10 m, and it is lost in the corridor and over the field.
  It fails on dimmed images and diverges at 30 times the IMU noise.

Full tables and the reasons: `docs/stage4_log.md`.

## Stage 5: PX4 flies on SLAM alone

**Goal:** let the SLAM estimate fly the vehicle. In Stages 3 and 4, PX4 flew on the simulator's
perfect position and the SLAM algorithms only watched. In Stage 5, PX4's estimator (EKF2) uses external
vision and nothing else: GPS, barometer and magnetometer are switched off (`config/px4/ev_only.params`).
The SLAM pose is fed to PX4 through `scripts/stage5/slam_to_px4.py`, so if the estimate drifts, the
vehicle drifts with it.

| Terminal | What runs | Script |
|---|---|---|
| 1 | Gazebo + PX4 SITL with the EV-only parameters | `sim_ev.sh` |
| 2 | the SLAM algorithm live on the noised IMU, and the relay to PX4 | `slam_live.sh` |
| 3 | the mission | `offboard_mission.py` |

The three share one ROS master on the host network (port 11311). **Run Stage 5 with nothing else
running.** The scripts refuse to start if they find a ROS master or simulator left over.

### Run

```bash
# One watched closed-loop flight (FAST-LIO2 is PX4's only position source); the script runs the
# three terminals in order, closes the bag and scores the flight
GUI=true RVIZ=true bash scripts/stage5/run_closed_loop.sh room_square_r1 room square --size 4 --alt 1.5 --speed 1

# The results set: three more squares, three 30 s hovers and one 120 s hover
for r in 2 3 4; do
  bash scripts/stage5/run_closed_loop.sh room_square_r$r room square --size 4 --alt 1.5 --speed 1
done
for r in 1 2 3; do bash scripts/stage5/run_closed_loop.sh room_hover_r$r room hover --alt 1.5; done
bash scripts/stage5/run_closed_loop.sh room_hover_long_r1 room hover --alt 1.5 --hold 120
python3 scripts/stage5/stage5_figures.py && cat output/stage5/stage5_tables.md

# Extension: the closed loop over the Stage 4 matrix, FAST-LIO2 and FAST-LIVO2 (43 flights)
bash scripts/stage5/run_closed_loop_matrix.sh
python3 scripts/stage5/matrix_summary.py
for a in fastlio2 fastlivo2; do python3 scripts/stage5/stage5_figures.py output/stage5/matrix/$a; done
cat output/stage5/matrix/matrix_tables.md
```

`run_closed_loop.sh` also takes:

- `ALGO=fastlivo2` to put FAST-LIVO2 in the loop;
- `NOISE=<scale>` for live IMU noise;
- `FAULT=lidar_drop_2s|lidar_drop_5s|cam_black_5s` for a live sensor fault;
- `EV_DELAY=<ms>` to set `EKF2_EV_DELAY`;
- `SPAWN="x y"` to set the take-off point.

The matrix tunes `EKF2_EV_DELAY` for FAST-LIVO2 first (it settles on 150 ms).

### The same flight by hand, in three terminals

Start each terminal only when the previous one says so:

```bash
mkdir -p output/stage5/manual                    # once, before terminal 1

# terminal 1: PX4 + the simulator; wait for "PX4 is up with NO position source"
docker compose run --rm sim-live bash /scripts/stage5/sim_ev.sh room \
    /output/stage5/manual/manual_square.bag square --size 4 --alt 1.5 --speed 1

# terminal 2: FAST-LIO2 live + the relay to PX4; then wait about 20 s
docker compose run --rm fastlio2-live bash /scripts/stage5/slam_live.sh

# terminal 3: the mission; at "landed and disarmed", press Ctrl-C in terminal 1, then in terminal 2
docker compose run --rm sim-live bash -c "source /opt/ros/noetic/setup.bash && \
    python3 /scripts/stage3/offboard_mission.py square --size 4 --alt 1.5 --speed 1 --sitl-params"

# score the flight
FLIGHTS=output/stage5/manual EVAL=output/stage5/manual/eval bash scripts/stage5/eval_closed_loop.sh manual_square
```

`--sitl-params` lets SITL arm and stay in OFFBOARD without a radio transmitter. **Never use it on a
real vehicle.**

### Passes when

The log goes through these lines in order:

1. "PX4 up with NO position source"
2. "one publisher on /mavros/vision_pose/pose: the relay"
3. "EKF2 has a position from SLAM"
4. "armed, OFFBOARD"
5. "landed and disarmed"

In the room:

- FAST-LIO2's error is 0.3-0.8 cm and PX4's 1.4-1.9 cm.
- Without alignment, PX4's estimate stays within 2.6-5.3 cm of the truth.
- EKF2 follows the SLAM pose with at most 0.03 s lag.
- The 120 s hover does not drift.

Details, the matrix results and the failure cases: `docs/stage5_log.md`.

## Verification scripts

Each stage has a verification script, written for the project's final check. Each one:

- re-scores every stored run from its ground truth and trajectory;
- regenerates the tables and figures;
- checks every number written in the stage's log against the data;
- adds a new recording or flight.

The scripts compare with the results stored under `output/`. They are useful once your own results
are complete, or when you have the project's result archive.

| Command | What it checks | Time |
|---|---|---|
| `bash scripts/verify_stage1.sh` | Gates 1 and 2, the container tests, every stored Stage 1 run re-scored, `final_results/*.csv` regenerated byte for byte (needs the stored runs, not the datasets) | 15 min |
| `GUI=true bash scripts/stage2/verify_stage2.sh` | the generators, a new 120 s recording and its gate, agreement with the stored recording, all five worlds | 15 min |
| `GUI=true bash scripts/stage3/verify_stage3.sh` | every stored Stage 3 run re-scored, the log's numbers, a replay, a new PX4 flight and the Stage 3 gate | 35 min |
| `FLY=1 GUI=true bash scripts/stage4/verify_stage4.sh` | all 312 runs re-scored, tables and figures regenerated, the log's numbers, fault copies rebuilt, a new flight | 20 min + flight |
| `FLY=1 MATRIX=1 GUI=true bash scripts/stage5/verify_stage5.sh` | every flight re-scored, the gate from the numbers, a new closed-loop flight, the closed-loop matrix | 10 min + flight |
| `python3 scripts/tools/independent_ape.py` | the APE recomputed from scratch with NumPy (not evo) for 27 runs of all stages; must agree to 1e-6 m | 1 min |

All of them passed on 18 Nov 2026 (`docs/final_verification.md`). Each one writes only its own folder
under `output/`.

## How the results are scored

- **APE, the main number:** the estimated and true trajectories are matched by time stamp (at most
  0.02 s apart). The estimate is aligned to the truth with one rotation and translation (SE(3)
  Umeyama, no scale). The APE is the root-mean-square of the remaining position errors.
  It is computed with evo 1.31.1 and checked by an independent NumPy implementation.
- **Flight window (Stages 3-5):** from the moment the vehicle has moved 0.10 m from its start pose
  until it comes within 0.10 m of its end pose, both found from the ground truth.
- **Repeated runs:** combined by their **median**: 5 runs per sequence in Stage 1, 3 per condition in
  Stages 3 and 4. Coverage and tracking success are taken from the worst run. FAST-LIO2 replays
  bit-identically, FAST-LIVO2 to within about 1e-4 m, and ORB-SLAM3 varies from run to run.
- **Further metrics:** relative error (RPE), horizontal and vertical error, yaw error, drift per 10 m,
  coverage, tracking success rate, start-up time, processor and memory use, and pose age.
- **Stage 1:** follows each paper's own protocol (metric and alignment). ORB-SLAM3's EuRoC figure is
  the mean of the 11 sequence medians, as in its paper.
- **Stage 5:** PX4's estimate against the truth, without alignment, in PX4's own frame, from take-off
  to the first touchdown: what the vehicle believed against where it was.

## Time and disk space

Measured in the end-to-end run of 20 Nov 2026:

| Part | Time | Disk |
|---|---|---|
| Docker images | 55 min | about 20 GB |
| Stage 1 | many hours (downloads and runs) | 260 GB of datasets |
| Stage 2 | 8 min | 3.5 GB (the bags; delete them after Stage 3) |
| Stage 3 | 41 min | 5.7 GB at its peak |
| Stage 4 | 6 h 15 min | 118 GB at its peak; 44 GB without the files that can be re-created |
| Stage 5 | 2 h 58 min | 26 GB at its peak (the closed-loop matrix about 25 GB) |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `docker images` shows none of the images after a restart | a snap Docker took over from the apt one | `sudo snap disable docker && sudo systemctl restart docker.socket docker.service` |
| every GPU container fails; `nvidia-smi`: "Driver/library version mismatch" | an automatic driver update under the loaded kernel module | restart the machine |
| "cannot open display", no window | containers have no X access | `xhost +local:docker`; check `echo $DISPLAY` |
| permission denied in `output/` or `data/` | Docker created the folder as root | `mkdir -p data output` before the first container; `sudo chown -R $USER output` repairs it |
| compiler "Killed" during a build | not enough memory | build one image at a time; `--build-arg JOBS=4` |
| the Stage 2 gate fails on camera rates | the GPU is busy with other work | slow the simulation: `RTF=0.35` for the Stage 2 verification, `bash scripts/tools/sim_rtf.sh <container> 0.35` for a recording |
| a flight gate fails on LiDAR intervals (often high flights) | two simulations at once, or a loaded processor | one simulation at a time; if other work must go on, `PX4_SIM_SPEED_FACTOR=0.15` in front of the command (`0.25` for a busy GPU). Leave it unset otherwise |
| ORB-SLAM3 never initialises in a flight | no change of acceleration after take-off | keep the hop; `--hop-timing start` for room flights |
| FAST-LIVO2 loses track on one machine only | built with `-march=native` | keep the Dockerfile's `-march=skylake` (`CPU_ARCH`) |
| `ModuleNotFoundError: rosbag` | a ROS script run with the eval image's own Python | run it through `scripts/common/ros_python.sh` |
| Stage 5: "a ROS master or simulator is already running" | a container left from an earlier step | `docker ps`, then `docker stop <name>` |
| Stage 5: two publishers on `/mavros/vision_pose/pose` | FAST-LIVO2's own MAVROS output | the launch file remaps it; the script refuses to fly otherwise |
| the urban world crashes `gzserver` at start | an intermittent crash while loading | the Stage 5 scripts retry once; otherwise run again |

## Documentation

| File | Contents |
|---|---|
| `docs/fastlio2_reproduction_log.md` | Stage 1 for FAST-LIO2: corrections, the review of the paper's protocol, results |
| `docs/fastlivo2_reproduction_log.md` | Stage 1 for FAST-LIVO2: NTU-VIRAL, the authors' dataset, the matched-start protocol |
| `docs/stage1_2_audit.md` | the audit of Stages 1 and 2 against the project guide |
| `docs/stage2_log.md` ... `docs/stage5_log.md` | each stage: how to reproduce it, decisions, deviations from the guide and why, results, findings, threats to validity |
| `docs/final_verification.md` | the final cross-verification of all five stages |
| `docs/results/` | Stage 1 comparison tables, per-run summaries and the output layout (`OUTPUT_LAYOUT.md`) |
| `VERSIONS.md` | every pinned upstream version and why |

Some logs and code comments cite the project's planning documents: the project guide PDF and the
Stage 3-5 research plan. Those documents are not part of this repository; this README holds every
command needed to reproduce Stages 1 to 5.

## Versions and licences

The images clone every upstream project at a pinned commit or tag ([VERSIONS.md](VERSIONS.md)):

- ORB-SLAM3 v1.0 (0df83dd)
- FAST-LIO (7cc4175)
- FAST-LIVO2 (0d2c034)
- Livox SDK v2.3.1 and livox_ros_driver v2.6.0
- Sophus (a621ff2) and rpg_vikit (6c886c8)
- PX4-Autopilot v1.14.4 (1555f2b)
- the Mid-360 simulation plugin (aae8ee3)
- OpenCV 4.4.0, Pangolin 0.6, evo 1.31.1, Gazebo 11.15.1, all on Ubuntu 20.04 with ROS Noetic

This repository's own code is under the MIT licence ([LICENSE](LICENSE)). The upstream projects are not
copied into the repository; they are downloaded when the images are built and keep their own licences.
For example:

- ORB-SLAM3: GPLv3;
- FAST-LIO and FAST-LIVO2: GPLv2 (for commercial use of FAST-LIVO2, contact its authors);
- PX4: BSD-3-Clause.

`scripts/third_party/` holds one third-party script, the FAST-LIO authors' NCLT converter, kept
verbatim and not covered by the MIT licence. Its origin is in its README.
