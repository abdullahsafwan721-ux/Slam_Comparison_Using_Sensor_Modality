# Stage 3 log -- close the loop, then fly

Implements Stage 3 of `eVTOL-SLAM-Complete-Project-Guide.pdf` plus the additions agreed in
`docs/eVTOL_SLAM_Research_and_Stage3-5_Plan.pdf` (Part 4): all three algorithms on simulated
data with realistic IMU noise, scored against exact ground truth -- first on the Stage 2
scripted bag (3a), then on a PX4 SITL flight (3b).

Gate (guide 3.6, with Decision D1): every algorithm tracks a PX4 flight to completion
(flight-window coverage >= 0.95), APE of centimetres in the room, no method an order of
magnitude worse than the others. **Result: PASSED on 2026-11-16**, on the third PX4 flight
(the first two exposed faults of the set-up; see 3b), **and again on 2026-11-17** on a second
recording of the same flight, after a full re-verification (section "Re-verification,
2026-11-17"). The tables below are the files on disk today.

Run on 2026-11-16 and 17, repo at `db3116f` plus this stage's changes, 32-core host, RTX 5090,
images `evtol/{orbslam3,fastlio2,fastlivo2,eval,sim}:v1` unchanged (no rebuild). One image was
added, for timing only: `evtol/orbslam3:v1-times`, derived from `orbslam3:v1`.

## How to reproduce

```bash
# host, project root
python3 scripts/common/gen_configs.py && python3 scripts/common/gen_world.py

# 3a  scripted bag: noise injection once, each algorithm 3x, scoring
bash scripts/stage3/run_all_algos.sh output/stage2/scripted_room.bag room output/stage3/scripted 3
cat output/stage3/scripted/eval/summary.md output/stage3/scripted/eval/summary_extra.md

# 3b  PX4 flight, then its sensor gate. To WATCH it:  GUI=true docker compose run --rm -e GUI -e SPAWN=... sim ...
docker compose run --rm -T -e SPAWN="-2.0 -1.8" sim bash /scripts/stage3/px4_record.sh \
    room square /output/stage3/flights/room_square.bag --size 4 --alt 1.5 --speed 1.5 --laps 3
docker compose run --rm -T sim bash -c "source /scripts/common/sim_env.sh && \
    python3 /scripts/stage2/verify_sim_bag.py /output/stage3/flights/room_square.bag --flight"
bash scripts/stage3/run_all_algos.sh output/stage3/flights/room_square.bag room_square output/stage3/px4 3

# re-score existing runs without re-running anything: runs = 0
bash scripts/stage3/run_all_algos.sh output/stage3/flights/room_square.bag room_square output/stage3/px4 0

# ORB-SLAM3 tracking time per frame (build the timing image once), and one picture of the flight
docker compose build orbslam3_times
bash scripts/stage3/orbslam3_timing.sh output/stage3/px4 room_square 3
python3 scripts/stage3/plot_flight.py sim/evtol_sim/worlds/room.world output/stage3/px4 room_square \
    output/stage3/flights/room_square.overview.png
```

**Recording a flight again under the same bag name:** move the old output directory aside
first. `run_all_algos.sh` refuses to run when the bag is newer than the noised copy in the
output directory (deviation 14); without that check it scored the earlier recording.

| File | Origin | Role |
|---|---|---|
| `scripts/common/imu_noise.py` | guide 3.1, unchanged | white noise + bias random walk on the perfect simulated IMU |
| `scripts/common/bag_to_euroc.py` | guide 3.2, unchanged | bag -> EuRoC folder for ORB-SLAM3's standalone binary |
| `config/launch/fastlio2.launch`, `fastlivo2.launch` | guide 3.3, unchanged | launch with an explicit config |
| `scripts/stage3/run_all_algos.sh` | guide 3.4, **adapted** | the Stage 3/4 workhorse |
| `scripts/stage3/offboard_mission.py` | guide 3.5, **2 fixes** | OFFBOARD flight profiles |
| `scripts/stage3/px4_record.sh` | guide 3.5, **adapted** | PX4 SITL + rig, record, fly |
| `scripts/stage3/check_clearance.py` | **new** | refuses a flight whose path or take-off spot hits a box |
| `scripts/common/make_legged_iris.py` | **new** | PX4's iris + the landing gear of `rig.yaml`, built in the sim container |
| `scripts/common/sim_env.sh` | extended | `px4` mode builds the legged iris and puts it first on the model path |
| `config/rig.yaml` | extended | `landing_gear` block |
| `scripts/stage3/thin_camera.py` | **new** | diagnostic A7: camera thinned to the LiDAR rate |
| `scripts/common/metrics_extra.py` | **new** | flight-window APE (h/v), yaw, drift %, TSR, flight-window coverage, start-up, post-landing drift, cost |
| `scripts/common/cost_probe.py` | **new** | CPU and RSS of the algorithm process, 2 Hz |
| `scripts/common/results_table.py` | extended | adds `summary_extra.csv/.md`; `summary.*` unchanged |
| `scripts/common/run_ros_algo.sh` | extended | `COST_PROC=` hook; two `kill` lines made safe |
| `scripts/common/eval_traj.sh` | fixed | re-scoring no longer hangs on evo's overwrite prompt |
| `scripts/common/gen_configs.py` | 1 line | FAST-LIVO2 `pose_output_en: true` |
| `scripts/common/gen_world.py` | 1 line | `room_plain` now really is `room` with grey surfaces |
| `scripts/stage2/verify_sim_bag.py` | extended | `--flight` mode for PX4 bags |
| `docker/orbslam3_times.Dockerfile`, `compose.yaml` | **new** / 1 service | `evtol/orbslam3:v1-times`: `orbslam3:v1` rebuilt with upstream's `REGISTER_TIMES`; timing only |
| `scripts/stage3/orbslam3_timing.sh`, `timing_summary.py` | **new** | ORB-SLAM3 tracking time per frame, headroom against the camera period |
| `scripts/stage3/plot_flight.py` | **new** | top view of the flight and error over time (`flights/room_square.overview.png`) |

Guide files were transcribed with `scripts/tools/guide_extract.py`; the two launch files and
`bag_to_euroc.py` are byte-identical to the copies that already ran in the Stage 2 smoke test.

## Decisions taken with the user (D1, D2: 2026-11-16; D3, landing gear, hop: 2026-11-17)

- **D1 -- coverage on the flight window.** Coverage is counted from the first ground-truth
  motion (take-off) to the last (touch-down), holes longer than 1 s excluded; start-up time
  is its own metric. The guide's whole-bag coverage stays in both tables. Reason: ORB-SLAM3
  cannot initialise its IMU before the vehicle moves, so whole-bag coverage fails it on every
  flight without any tracking loss (0.909 on the scripted bag, where it never loses track).
- **D2 -- ORB-SLAM3 frame trajectory.** `f_*.txt` (every frame) is the scored trajectory;
  the keyframe trajectory `kf_*.txt` is scored beside it as algorithm `orbslam3kf` (APE-type
  columns only: 74 keyframes in 120 s are too sparse for coverage or TSR).

- **D3 -- APE on the flight window (applied on 16 Nov; checked against the literature and
  accepted by the user on 2026-11-17).** Same window as D1:
  alignment and RMSE over take-off to touch-down only (`ape_air_*`). evo's whole-trajectory
  APE stays in both tables as "APE whole bag". Reason: after touch-down ORB-SLAM3 loses the
  scene and coasts on its IMU for 5 s, drifting 0.4-1.9 m while the vehicle stands still; in
  the whole-bag APE that tail also spoils the alignment of the flight itself (0.12 m against
  0.008 m in flight). The drift is reported on its own (`post_landing_max`), not hidden.
  - Why it loses the scene: the cameras look 35 deg down from 0.12 m above the floor, so on
    the ground the whole image is a magnified, blurred patch of the floor texture
    (`flights/room_square.onboard_left.mp4`, first and last seconds). Confirmed by
    experiment: with the cameras 0.46 m above the floor ORB-SLAM3 does not lose track after
    landing (3b, "Landing gear at Livox's clearance"). It is therefore a caveat of this
    set-up, not a general ORB-SLAM3 result.
  - Precedent: DSO evaluates EuRoC on "only the parts of the sequence where the MAV is in
    the air"; OpenVINS skips the pick-up and set-down of the EuRoC and UZH-FPV sequences;
    `rpg_trajectory_evaluation` has `start_time_sec` / `end_time_sec`; OpenLORIS reports a
    second correct-rate that excludes initialisation time. Against: the common default is
    the whole sequence (ORB-SLAM3's own paper, KITTI), and no benchmark defines a "flight
    window". Hence both numbers stay in every table.
  - Safeguards in place: the window comes from ground truth only (first and last motion
    > 0.10 m), is the same for every method, and the alignment uses the same window for
    every method. Checked on the gate flight: restricting all three methods to the common
    interval that starts at ORB-SLAM3's first pose changes no APE at the fourth decimal;
    stationary drift before take-off is at most 3.3 cm (FAST-LIO2) and 0.3 cm (FAST-LIVO2).
  - Alignment is SE(3) for all three. A yaw-only alignment (recommended for inertial systems
    by Zhang and Scaramuzza 2018) does not apply here: none of the three trajectories is
    written in a gravity-aligned frame (FAST-LIO2 and FAST-LIVO2 use the first IMU frame,
    which is upside-down on this rig; ORB-SLAM3's frame file uses its first keyframe's body
    frame). ORB-SLAM3's paper and the HILTI challenge use SE(3) as well.

## Deviations from the guide, and why

The guide's author never ran Stage 3 (its Appendix D). Every item below was found by running
it; each is marked in the file it touches.

| # | Where | What the guide does | What happens | What we do |
|---|---|---|---|---|
| 1 | `run_all_algos.sh` | `python3` for bag tools in the eval container | that `python3` is the evo virtualenv: `ModuleNotFoundError: rosbag` | `ros_python.sh` (audit fix A) |
| 2 | `run_all_algos.sh` | scores FAST-LIVO2 on `/aft_mapped_to_init` | that topic is stamped `ros::Time::now()` at publish (`LIVMapper.cpp`, `publish_odometry`), ~85 ms after the state's own time; APE 0.064 m instead of 0.006 m | score FAST-LIVO2's own pose file (`evo/pose_output_en`, stamped `last_lio_update_time`), exactly as Stage 1 did; the topic trajectory is kept as `*.topic.tum` |
| 3 | `run_all_algos.sh` | keyframe trajectory for ORB-SLAM3 | too sparse for time-series metrics | Decision D2 |
| 4 | `eval_traj.sh` | `evo_ape --save_results` on an existing file | evo asks "overwrite? (y/n)" and waits for ever; a re-score hung for 3 h | remove old outputs, `--no_warnings` |
| 5 | `offboard_mission.py` | sets PX4 parameters right after "FCU connected" | MAVROS is still downloading the parameter list: `ServiceException` ("PR: receiving not complete"), mission dies before arming | retry for up to 60 s |
| 6 | `offboard_mission.py` | climbs above `path(0)`, for the square the corner (-size/2, -size/2) | a diagonal dash of size/sqrt(2) m while still near the ground; lands on that corner | every profile is shifted to start (and end) above the take-off point |
| 7 | `px4_record.sh` | spawns at the world origin, flies `--size 6 --alt 1.5` in the room | a 0.67 m box stands on the origin; the 6 m square crosses a 1.38 m box and passes 6 cm from a 1.81 m one | `SPAWN="x y"` + `check_clearance.py`; room flight is a 4 m square from (-2.0, -1.8), 3 laps (48 m, the guide's path length) |
| 8 | `px4_record.sh` | waits for MAVROS with no limit; on a failed mission `set -e` exits at once | hangs for ever / leaves an unclosed `.bag.active` that looks like a flight | 240 s limit; a failed mission closes the bag as `*.FAILED.bag` and exits 1 |
| 9 | `verify_sim_bag.py` | compares the IMU with the twice-differentiated 200 Hz ground truth | fails a correct flight bag (1.13 m/s^2): motor steps and the touch-down impact are above what that difference resolves | `--flight`: the IMU must integrate to the ground-truth velocity over 0.1 s windows (0.6 mm/s RMS), plus camera/LiDAR intervals, hold before take-off, landed |
| 10 | `gen_world.py` | `room_plain` = "same room, grey surfaces" | the grey variant did not draw from the random generator, so its 40 boxes were somewhere else | draw and discard; layouts now identical (`room.world` byte-identical to Stage 2's) |
| 11 | `iris_evtol` model | rig hung 6-10 cm under PX4's iris, which rests on its body box | on the ground the LiDAR and both cameras were 5 cm inside the floor for the whole initialisation hold | `landing_gear` in `rig.yaml`; `make_legged_iris.py` adds four sphere feet to `iris::base_link` (a separate gear link made the vehicle chatter at rest) |
| 12 | `offboard_mission.py` | smooth setpoints only | ORB-SLAM3 never initialises: it needs a >= 0.5 m/s^2 change of mean acceleration between frames (`Tracking.cc:2347`) | `--hop 0.4`: altitude step after the climb, in every flight |
| 13 | `run_all_algos.sh` | -- | containers write as root; a `docker compose run` without `-T` needs a terminal | `chown` on exit; `-T` |
| 14 | `run_all_algos.sh` | reuses the noised bag, ground truth and EuRoC folder when they exist | the flight was recorded again under the same name (16 Nov, 21:16); the next run reused the first recording's data and scored that, while the bag on disk was another flight | refuses to run when the source bag is newer than the noised copy; the output directory has to be moved aside first |
| 15 | `offboard_mission.py` | arming loop: one setpoint, then wait 1 s, ask for OFFBOARD / arm | one setpoint per second is below PX4's 2 Hz minimum for OFFBOARD. At full speed PX4 accepted it anyway (every flight of Stages 3-5 armed), but in the final verification (18 Nov), with the simulation slowed down for a busy GPU (`PX4_SIM_SPEED_FACTOR` 0.35 / 0.6), it never armed ("could not arm/enter OFFBOARD in 90 s") | the setpoint stream stays at 30 Hz while OFFBOARD and arming are requested once a second; the climb starts 1 s after the arm command, as before. Measured: the take-off is the same with the old and the new loop. (The old loop's failures on 18 Nov also had a second cause: with `PX4_SIM_SPEED_FACTOR` set, even to 1, PX4's rcS sets COM_OF_LOSS_T to factor x 0.5 s instead of 1.0 s) |
| 16 | `offboard_mission.py` | (Stage 3 hop: 2 s after the scripted climb, timed from its start) | Stage 4 deviation 12 made the hop wait for the measured height (right outdoors), which moves it ~9 s after the lift-off in the room; ORB-SLAM3 then starts only there and a re-flown room flight fails the coverage gate (0.82, Finding 9) | `--hop-timing start` reproduces the Stage 3 schedule exactly; `verify_stage3.sh` flies with it. Default stays Stage 4's |

Checked and kept as the guide has them: `--sitl-params` values. The v1.14 parameter
reference gives `NAV_RCL_ACT` a minimum of 1, but v1.14.4's `failsafe.cpp`
(`fromNavDllOrRclActParam`) maps 0 to `Action::None` for both `NAV_RCL_ACT` and
`NAV_DLL_ACT`; PX4 accepted all four and flew.

Robustness added after an independent review of the new code (a second agent re-implemented
the metrics in plain NumPy: APE agrees to 1e-12 m, every other number to the grid
resolution): a run that publishes nothing or cannot be scored becomes a **failure record**
(TSR 0, coverage 0, counted in the "Failed" column) instead of aborting the batch or
vanishing from the "worst" columns; stale ORB-SLAM3 outputs are deleted before each run; the
EuRoC folder name carries the IMU scale; condition names may not contain `__`.

## Verified against primary sources (2026-11-16)

Checked by a separate agent against upstream source and official documentation:

- **IMU noise model**: Kalibr wiki "IMU Noise Model": sigma_d = sigma / sqrt(dt), bias
  increment sigma_b * sqrt(dt). ORB-SLAM3's `EuRoC.yaml` has the four `rig.yaml` values
  (gyro 1.7e-4 is ORB-SLAM3's rounding of EuRoC's 1.6968e-4).
- **FAST-LIVO2** (`hku-mars/FAST-LIVO2`, `src/LIVMapper.cpp`): `publish_odometry` stamps
  `ros::Time::now()`, is called only from `handleLIO`; the pose file is stamped
  `LidarMeasures.last_lio_update_time` (in LIVO mode the image capture time). Both carry the
  state after the LIO update and before that frame's VIO update. No upstream issue discusses
  it; in issue #179 (about ground-truth time stamps of the MARS-LVIG dataset, not about this
  stamping) a maintainer recommends `evo_ape --t_offset` for time misalignment.
- **FAST-LIO2** (`hku-mars/FAST_LIO`): `/Odometry` is stamped `lidar_end_time`; with every
  per-point offset 0 (our simulated scans) that equals the scan header time and there is no
  de-skew. Upstream `mid360.yaml` / `mapping_mid360.launch` values match our generated config
  (`blind 0.5`, `point_filter_num 3`, `filter_size_surf/map 0.5`).
- **ORB-SLAM3** (`UZ-SLAMLab/ORB_SLAM3`, `v1.0-release`): `f_`/`kf_` files hold nanosecond
  stamps, IMU-body poses, quaternion x y z w, largest map only; the two files are in
  different world frames (each is aligned separately here). The EuRoC example paces itself
  to the image stamps and prints no tracking-time statistics.
- **PX4 v1.14 OFFBOARD**: setpoints must stream (> 2 Hz) before the mode switch;
  `COM_RCL_EXCEPT` bit 2 = Offboard (value 4); `COM_RC_IN_MODE` 4 = stick input disabled;
  `AUTO.LAND` is MAVROS's string for land mode; `/mavros/setpoint_position/local` is ENU.
- **Lockstep**: PX4's `<enable_lockstep>` makes Gazebo and PX4 wait on each other for
  sensor/actuator messages; it is not Gazebo's `--lockstep` (strict sensor rates), which
  Stage 2 rejected. Confirmed in our bag: all sensor rates and intervals are nominal.
- **evo**: `--align` is SE(3) Umeyama without scale; RPE over metres picks one pair per
  start pose; segments here are measured along the ground-truth path.

### Second pass, 2026-11-17 (two agents, upstream code at the pinned tags, official manuals, papers)

18 factual claims of this log were re-checked line by line: 12 hold as written, 5 needed
sharper wording, 1 was wrong in a detail. None changes a result. The corrections:

- **ORB-SLAM3 has no usable "start without motion" switch.** `IMU.fastInit` exists
  (`Tracking.cc:1396`, skips the 0.5 m/s^2 test) but only the old parameter parser reads it;
  settings files with `File.version: "1.0"` (ours, and upstream's own `EuRoC.yaml`) go
  through the `Settings` class, which never reads it. Even with it, a stationary vehicle is
  reset by `LocalMapping.cc:138` ("Not enough motion for initializing", until 15 s of motion
  have accumulated). So the hop (deviation 12) is the only way to start ORB-SLAM3 without
  editing its source. Accepted practice: EuRoC's sequences begin with deliberate excitation
  for the same reason; "nearly all state-of-the-art VIO algorithms rely on excitation in
  their initialization" (Scheiber et al., ICRA 2021).
- **The 5 s of drift after landing is ORB-SLAM3's designed behaviour**: `RECENTLY_LOST`,
  pose from the IMU alone for `time_recently_lost = 5.0` s (hard-coded, `Tracking.cc:48`),
  then a new map. It applies only once the second inertial bundle adjustment ("VIBA 2") is
  done; before that a tracking loss resets the map. Our logs show exactly that: VIBA 2, then
  ~101 x "Fail to track local map!" (5 s at 20 Hz), then map 1, which never initialises.
- `REGISTER_TIMES` is in `include/Settings.h:24` (upstream's README still says `Config.h`).
- FAST_LIO issues #435 and #444 (Mid-360 height drift) were closed by the stale bot without
  any human reply: "no maintainer diagnosis" stands.
- ORB-SLAM3's frame file is written relative to the first keyframe's body frame, the
  keyframe file in the map frame: that is why the two are aligned separately.
- PX4's code checks that the last OFFBOARD setpoint is younger than `COM_OF_LOSS_T` (1 s);
  the "2 Hz" figure is from the documentation.
- Gazebo's `--lockstep` exists from 9.14 and 11.1; evo's `pairs_from_reference` from 1.22
  (we run 1.31.1); `--no_warnings` is documented as "no warnings requiring user
  confirmation".
- Confirmed unchanged: the acceleration test and its line, largest-map-only and nanosecond
  output, FAST-LIVO2's publish-time stamp and pose file, FAST-LIO2's `lidar_end_time` stamp
  and Mid-360 settings, `fromNavDllOrRclActParam(0) = None`, the iris collision box
  (0.47 x 0.47 x 0.11 m, no legs), Kalibr's noise model and the EuRoC IMU values, ODE's
  documented trouble with joints between very different masses.
- **Livox Mid-360 manual (v1.2, p. 9), not known on 16 Nov:** "If mounting the Mid-360
  upside down, allow a space of no less than 0.5 m between the mounting surface and the
  ground." Our landing gear gives 0.16 m. See "Landing gear at Livox's clearance" in 3b.
  The spec also calls 0.1 m the "close proximity blind zone" and marks returns between 0.1
  and 0.2 m as "reference only".

Metric definitions against the literature: drift per 10 m is KITTI's relative translation
error on shorter segments (Delmerico and Scaramuzza use 7-35 m for MAVs); a
threshold-plus-gap success rate is OpenLORIS's "correct rate"; CPU as percent of one core
at a fixed sampling rate is Delmerico's and OpenVINS's convention; "pose age at publish" is
our name for their "time from receiving the measurement to updating the pose". None is
non-standard; the names "TSR" and "pose age" are ours and are defined in
`metrics_extra.py`.

## 3a -- scripted bag with IMU noise (3 runs each)

IMU noise check (`noised - original`, 24 001 samples): white noise per axis gyro
2.42/2.42/2.40e-3 rad/s (model 2.404e-3), accel 0.0280/0.0284/0.0286 m/s^2 (model 0.02828);
bias wander over 120 s of the expected order (gyro 2e-4..8e-4 rad/s, accel 0.03 m/s^2). The
original bag's IMU is exactly noise-free (std 0).

`output/stage3/scripted/eval/summary_extra.md` (runs of 2026-11-16, 20:30-20:53; the motion
window of the scripted path takes the place of the flight window):

| Algorithm | APE whole bag (m) | APE motion window (m) | horiz. | vert. | Yaw (deg) | Drift (%/10 m) | TSR | Window cov. | Bag cov. | Start-up (s) | CPU (% core) | RAM (MB) | Pose age p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FAST-LIO2 | 0.0322 | 0.0244 | 0.0099 | 0.0223 | 0.05 | 0.22 | 1.000 | 1.000 | 0.997 | 0.0 | 15 | 172 | 8.0 |
| FAST-LIVO2 | 0.0061 | 0.0063 | 0.0062 | 0.0011 | 0.04 | 0.05 | 1.000 | 1.000 | 0.997 | 0.0 | 67 | 743 | 109.2 |
| ORB-SLAM3 (frames) | 0.0109 | 0.0108 | 0.0106 | 0.0026 | 0.05 | 0.20 | 0.971 | 0.971 | 0.909 | 3.2 | 219 | 759 | 12.9 (tracking time) |
| ORB-SLAM3 (keyframes) | 0.0106 | 0.0106 | 0.0104 | 0.0021 | 0.04 | 0.21 | -- | -- | -- | -- | | | |

Medians of 3 runs; TSR and coverage are the worst run. FAST-LIO2 is deterministic
(bit-identical trajectories in all three runs). FAST-LIVO2 is not quite: its APE agrees to
1e-4 m (whole bag 0.00608-0.00614 m), but single poses differ by up to 1.9 cm between runs
(corrected 18 Nov by the final verification, which first assumed bit-identity); ORB-SLAM3 varies between runs
(whole-bag APE 0.0066, 0.0109, 0.0116 m in this set; 0.0057, 0.0098, 0.0131 m in the set
run earlier the same day), which is why medians are used. One map per ORB-SLAM3 run.

## 3b -- PX4 flight

Flight: 4 m square, 3 laps, 1.5 m, 1.5 m/s, from spawn (-2.0, -1.8), with landing gear and
the 0.4 m initialisation hop. Two recordings of it exist:

- **Recording 2 (the bag on disk, `flights/room_square.bag`, recorded 2026-11-16 21:16).**
  69 s, 1.3 GB. Take-off at 21.6 s after an 18.8 s stationary hold, touch-down at 62.9 s,
  landed 6 cm from the take-off point. `verify_sim_bag.py --flight`: **all 17 checks pass**
  (`flights/room_square.gate.txt`): rates nominal, camera intervals 48-53 ms with no
  duplicates under PX4 lockstep, LiDAR intervals 91-110 ms, gyro at rest 8.5e-5 rad/s, IMU
  integrates to the ground-truth velocity within 0.8 mm/s RMS. Results in `px4/`.
- **Recording 1 (2026-11-16 20:04, the gate flight of the first write-up).** Its raw bag was
  overwritten by recording 2; its noised bag, ground truth, EuRoC folder, gate file and the
  runs repeated on 17 Nov are kept in `px4_recording1/`. Take-off 21.8 s, touch-down 63.0 s,
  landed 2 cm from the take-off point, same 17 checks passed.

`output/stage3/px4/eval/summary_extra.md`, recording 2 (medians of 3 runs; TSR and coverage
worst run; runs of 2026-11-17):

| Algorithm | APE flight (m) | horiz. | vert. | APE whole bag | Max error after landing (m) | Yaw (deg) | Drift (%/10 m) | TSR | Flight cov. | Start-up (s) | CPU (% core) | RAM (MB) | Pose age p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FAST-LIO2 | 0.0070 | 0.0029 | 0.0064 | 0.0119 | 0.022 | 0.10 | 0.14 | 1.000 | 1.000 | 0.0 | 15 | 172 | 7.9 |
| FAST-LIVO2 | 0.0029 | 0.0026 | 0.0012 | 0.0024 | 0.004 | 0.01 | 0.04 | 1.000 | 1.000 | 0.0 | 54 | 424 | 80.6 |
| ORB-SLAM3 (frames) | 0.0075 | 0.0070 | 0.0026 | 0.1206 | 1.863 | 0.30 | 0.35 | 0.981 | 0.981 | 0.7 | 197 | 618 | 12.4 (tracking time) |
| ORB-SLAM3 (keyframes) | 0.0076 | 0.0069 | 0.0031 | 0.1488 | 1.585 | 0.50 | 1.62 | -- | -- | -- | | | |

Gate:

| Gate item | Result |
|---|---|
| summary lists all three, 3 runs each, no empty trajectory | yes; 0 failed runs |
| flight-window coverage >= 0.95 for every run (D1) | 1.000 / 1.000 / 0.981 |
| APE of centimetres in the room, no method 10x worse | 0.3-0.8 cm in flight for all three (D3). Whole-bag APE of ORB-SLAM3 is 0.12 m because of its drift after landing: reported, see Findings 6 |
| new metrics and cost present for every run; evo's APE reproduced | yes (the script stops if its APE differs from evo's by > 1e-6 m) |

The same flight, recording 1 (`px4_recording1/`): flight APE 0.0083 / 0.0049 / 0.0044 m
(FAST-LIO2 / FAST-LIVO2 / ORB-SLAM3), coverage 1.000 / 1.000 / 0.956, ORB-SLAM3 start-up
1.7 s. FAST-LIO2's three runs on that recording are bit-identical; FAST-LIVO2's differ by at
most 0.16 mm (36-62 of 683 poses). ORB-SLAM3 over 9 runs on the two recordings: flight-window APE
0.0036-0.0089 m in every run; whole-bag APE 0.057-0.27 m; largest error after landing
0.41-1.86 m. Its start-up (0.7 s and 1.7 s after take-off) depends on when the hop's
acceleration step falls between two camera frames.

ORB-SLAM3 in every run: one map during the flight, VIBA 1 and 2 completed, about 101
"Fail to track local map!" after touch-down (5 s), then an empty second map.

**ORB-SLAM3 tracking time** (`px4/orbslam3_times/summary.md`, image `orbslam3:v1-times`, 3
runs): median 10.2 ms, p95 12.4 ms, maximum 16.3 ms per stereo frame while tracking; no
frame over the 50 ms camera period; headroom 4.0x at 20 Hz. Scripted bag: p95 12.9 ms,
3.9x. The timing build tracks like the validated one (flight APE 0.0048-0.0074 m, coverage
0.981). This is image-in to pose-out and so is the counterpart of "pose age at publish"
of the two ROS methods, without sensor transport.

Picture and video of recording 2: `flights/room_square.overview.png` (top view, error over
time) and `flights/room_square.onboard_left.mp4` (left camera, real time).

### Landing gear at Livox's clearance (sensitivity test, 2026-11-17)

Livox's manual requires 0.5 m under an upside-down Mid-360 (second verification pass), so
the gear was tried at that height: `foot_z: -0.56`, feet in the same places, everything else
unchanged (`flights/room_square_gear05.*`, `diag/gear05/`, one run per algorithm).

| | Gear 0.22 m (kept) | Gear 0.56 m (tested) |
|---|---|---|
| Sensor gate (`--flight`) | all 17 pass | failed on 17 Nov: IMU against ground-truth velocity 0.030 m/s RMS, worst 0.56 m/s, all of it at the landing; passes under the Stage 4 gate, which leaves the landing impact out (0.003 m/s RMS elsewhere, see below) |
| On the ground | still (gyro 8.5e-5 rad/s) | rocks 2.7 deg at lift-off; on landing bounces, rocks +-7 deg for 2 s, ends 0.52 m from the take-off point |
| LiDAR sees its own feet | 0.4 % of points, inside the blind radius | no (all four below the -52 deg edge) |
| FAST-LIO2 flight / whole-bag APE | 0.70 / 1.19 cm | 1.08 / 2.49 cm |
| FAST-LIVO2 flight / whole-bag APE | 0.29 / 0.24 cm | 0.59 / 0.49 cm |
| ORB-SLAM3 flight / whole-bag APE | 0.75 / 12.1 cm | 0.88 / 0.88 cm |
| ORB-SLAM3 largest error after landing | 0.8-1.9 m | 0.012 m (no tracking loss at all) |

Two things follow. (1) With the cameras 0.46 m above the floor ORB-SLAM3 keeps tracking
after landing, which proves that its drift after landing comes from the camera height of
this set-up (D3's caveat) and not from the algorithm. (2) Four rigid feet 0.56 m under a
0.55 m quadrotor are not a usable landing gear in this simulation: the vehicle rocks at
lift-off and bounces 0.5 m sideways on landing. (Corrected in Stage 4: the failed IMU check
was the landing impact itself, which Gazebo's point-sampled IMU aliases on any hard
touch-down, also with the 0.22 m gear; the Stage 4 gate leaves the landing out and this bag
passes. See docs/stage4_log.md, deviation 5.) **Decision:
the gear stays at 0.22 m**; results in flight do not depend on it (all three stay at or
below 1.1 cm), and the flight-window scoring of D3 removes the ground artefact from the
comparison. A stable 0.5 m gear (wider stance, which then enters the LiDAR's view, or
damped contacts) is a design task of its own; it is listed under "Not done / open".

### The two flights before it (kept as evidence)

- `flights/v1_no_gear/`, `px4_v1_no_gear/`: guide's vehicle, no hop. The bag passes the sensor
  gate, yet FAST-LIVO2 had 0.17 m APE (0.16 m vertical: a ~0.4 m height inconsistency
  between ground and flight), FAST-LIO2 0.049 m, and ORB-SLAM3 never initialised in 3 of 3
  runs ("not enough acceleration" x732). Cause 1: on the ground the LiDAR origin was at
  z = -0.050 m; a third of its rays returned nothing and most others hit the inside of the
  floor slab (a false plane at z = -0.10 m); both cameras showed uniform grey. Cause 2: the
  scripted path had exactly two frames above ORB-SLAM3's 0.5 m/s^2 trigger (12.02, 12.07 s);
  the flight had none while the camera could see anything.
- `flights/v2_gear_as_link/`: landing gear as a separate 80 g link (cylinder legs, then
  sphere feet). The vehicle chattered on the ground (gyro 0.012 rad/s, accel 0.7 m/s^2 std
  at rest) and the bag failed "gyro at rest". With the feet on `iris::base_link` it is still.

### Diagnostic A7 (`output/stage3/diag/`)

FAST-LIVO2 on the scripted bag with the camera thinned to one image per LiDAR scan (10 Hz):
"No point" messages fall from 2390 to 48, APE 0.0095 m against 0.0061 m at 20 Hz. The
alternate images do not hurt; the extra frames help slightly. Carried item 3 of the audit
is closed: its "higher drift" was the time-stamp artefact of deviation 2.

## Findings

1. **FAST-LIVO2's topic time stamps are not measurement times.** Scored on
   `/aft_mapped_to_init`, FAST-LIVO2 looked the worst method (APE 0.064 m, RPE 0.039 m/m);
   shifting those stamps by -85 ms brought it to 0.0105 m, and its own state-time pose file
   gives 0.0061 m, the best of the three. A time-shift sweep finds the optimum at exactly
   0 ms for FAST-LIO2, ORB-SLAM3 and the pose file, so the other trajectories are stamped
   correctly. The Stage 2 audit's "higher drift from alternate images" (carried item 3) was
   this artefact. Consequence for Stage 5: a consumer of the topic receives poses that are
   70-115 ms old and labelled "now".
2. **FAST-LIO2's error is vertical.** Scripted bag: horizontal 1.0 cm, vertical 3.1 cm, a
   slow height drift of about 1 mm/s (-6 cm early, +4.5 cm at the end), the same with and
   without IMU noise. PX4 flight (41 s): horizontal 0.4 cm, vertical 0.8 cm. Not a blind-zone or extrinsic fault (`blind 0.5 m`, generated
   extrinsics). FAST-LIO2 runs upstream's Mid-360 settings (0.5 m voxels, every 3rd point);
   height drift with the Mid-360 is reported upstream (issues #435, #444) without a
   maintainer diagnosis. To be characterised in Stage 4 (altitude sweep, open field).
3. **Cost ordering** (replay at real time, desktop CPU; scripted bag / PX4 flight):
   FAST-LIO2 0.15 / 0.15 core and 0.17 GB, FAST-LIVO2 0.67 / 0.54 core and 0.74 / 0.42 GB,
   ORB-SLAM3 2.2 / 2.0 cores and 0.76 / 0.62 GB.
4. **Pose age at publish** (p95): FAST-LIO2 8 ms; FAST-LIVO2 81-115 ms depending on the
   recording (it waits for the image that closes each LiDAR slice, so the camera-to-LiDAR
   phase of a recording sets it); ORB-SLAM3 12-13 ms tracking time per frame, 4x headroom
   at 20 Hz (timing build).
5. **The guide's room flight would have crashed** (deviation 7), and `room_plain` was not
   the same room (deviation 10): both would have corrupted Stage 4 silently.
6. **ORB-SLAM3 needs an initialisation manoeuvre, and drifts after landing.** Without a
   >= 0.5 m/s^2 change of acceleration between frames it never starts (3 of 3 runs on the
   smooth flight), and upstream offers no setting that avoids it (second verification pass).
   With the hop it starts 0.7-1.7 s after take-off and is as accurate in flight as the LiDAR
   methods (0.4-0.9 cm). After touch-down it reports "Fail to track local map!" and coasts
   on its IMU for 5 s, drifting 0.4-1.9 m. The cause in this simulation is the view: cameras
   pitched 35 deg down, 0.12 m above the floor, see only blurred floor texture. Both matter
   for Stage 5 and for hardware; the second is a caveat of the set-up, not a general result.
7. **A belly-mounted, inverted Mid-360 needs real ground clearance.** Without landing gear
   every LiDAR method initialises its map from inside the ground. Livox's manual asks for at
   least 0.5 m between the mounting surface and the ground for an upside-down Mid-360; the
   simulated vehicle has 0.16 m (see the sensitivity test in 3b). Phase 2 hand-over: design
   the airframe for 0.5 m.
8. **FAST-LIVO2 occasionally stamps a pose one camera interval off.** On recording 1, 4 of
   683 poses are 2-7.5 cm off along the direction of flight (7.5 cm = 50 ms at 1.5 m/s),
   identically in every run; its pose-file stamps alternate 0.05 / 0.15 s there. Recording 2
   has none (largest error in flight 1.0 cm). Effect on the RMSE: none at the third decimal.

9. **ORB-SLAM3 starts at take-off only with Stage 3's hop schedule** (found by the final
   verification, 18 Nov). In the Stage 3 gate flight the hop came 2 s after the scripted 1.5 s
   climb, timed from its start, and so fell into the lift-off: one sharp push (peak vertical
   acceleration 1.67 m/s^2, 0.9 s after lift-off; largest change of the mean acceleration between
   camera frames 0.87-1.17 m/s^2 in the four stored room-type flights), which passes ORB-SLAM3's
   0.5 m/s^2 initialisation test: it started 0.7-1.8 s after take-off. Stage 4 deviation 12 made the
   hop wait for the measured height (needed outdoors) and did not re-fly the room flights. Flown
   with that schedule, the room flight lifts off smoothly (0.41-0.44 m/s^2, with the old or the new
   arming loop alike), ORB-SLAM3 starts only at the hop, 8.9 s after take-off in all three runs,
   and its flight coverage is 0.82 (gate 0.95); its accuracy once started is unchanged
   (0.40-0.59 cm). With `--hop-timing start` (deviation 16) the take-off is the stored one again
   (1.41 m/s^2 between frames, peak 1.66 m/s^2 0.9 s after lift-off). ORB-SLAM3's early start
   indoors therefore depends on a well-timed manoeuvre in the lift-off; the protocol has to say so.

## Hand-over to Stage 4

- Every flight now includes the hop and the landing gear. ORB-SLAM3's flight coverage was
  0.956 on a 41 s flight (1.7 s start-up): flights much shorter than 40 s will fail the 0.95
  threshold on start-up alone, so keep Stage 4 flights at least that long.
- Room flights: `square --size 4` from `SPAWN="-2.0 -1.8"`, `figure8 --size 3` from
  `"0.9 -0.5"`, `line --size 6` from `"-5.1 0.7"`; `check_clearance.py --search` for others.
  `room_plain` now shares these. Corridor: only `line` fits at the origin; field and urban
  are clear at the origin for all profiles.
- `run_all_algos.sh <bag> <cond> <out> 0` re-scores; `ALGOS="fastlivo2"` runs a subset;
  `TAU=1.0` for outdoor conditions.
- IMU scale S: `orbslam3_sim.yaml` holds the baseline IMU noise; decide in Stage 4 whether
  ORB-SLAM3's config follows S (the estimator is told the truth) or stays fixed.
- One recording, one bag name, one output directory. Never record over a bag whose results
  are still wanted; `run_all_algos.sh` now stops if it sees that (deviation 14).
- `orbslam3_timing.sh <out> <cond>` after `run_all_algos.sh` gives ORB-SLAM3's tracking time
  for a condition (needed only for the cost figure, not for every Stage 4 cell).
- On the ground the cameras see nothing useful (0.12 m above the floor): ORB-SLAM3 will
  drift for 5 s after every landing. Score flights on the flight window (D3) and expect its
  whole-bag APE to be poor everywhere.
- Disk: a 64 s flight bag is 1.2 GB; one condition with 3 runs each is about 3 GB including
  the noised bag and the EuRoC folder (both re-creatable).

## Re-verification, 2026-11-17

What was checked, and what it found:

1. **Results on disk against this log.** They no longer matched: after the first write-up the
   scripted runs were repeated (16 Nov, 20:30) and the flight was recorded again under the
   same bag name (21:16); a later run of the algorithms (17 Nov, 04:36) silently reused the
   first recording's noised bag and ground truth. Nothing was wrong in any number, but the
   bag on disk and the results belonged to different flights. Fixed: deviation 14; the first
   recording's data moved to `px4_recording1/`; all three algorithms re-run on the bag on
   disk (`px4/`); every table of this log regenerated from the files.
2. **Reproducibility.** FAST-LIO2 reproduces bit-identically across the runs of two days.
   FAST-LIVO2 reproduces its APE to 1e-4 m but not bit for bit (single poses differ by up to
   1.9 cm between runs; corrected 18 Nov by the final verification). ORB-SLAM3's flight-window APE stays within 0.4-0.9 cm over 9 runs.
3. **Facts against upstream code and manuals** (section "Second pass"): no result affected.
4. **The three autonomous decisions against the literature**: D3 keep (safeguards listed
   under D3), hop keep (no upstream alternative), landing gear keep at 0.22 m in simulation
   (the 0.5 m variant was flown and is worse on this vehicle; see 3b).
5. **Open item "ORB-SLAM3 headroom"**: done with a derived image, the validated image
   untouched.

## Final cross-verification, 2026-11-18

`RTF=0.25 GUI=true bash scripts/stage3/verify_stage3.sh` (log `output/final_verification/verify_stage3.log`):
**all 6 steps passed**. All 24 stored runs re-scored identically (260 table cells); the 89 numbers of
this log's 3a/3b tables confirmed; the scripted bag replayed (FAST-LIO2 bit-identical, FAST-LIVO2
APE within its stored range, ORB-SLAM3 within its spread); a new PX4 flight of the gate mission,
with Stage 3's hop schedule (`--hop-timing start`, deviation 16) and slowed to 0.25x real time for a
GPU busy with other work, passes all 17 flight-gate checks; on it FAST-LIO2 0.98 cm, FAST-LIVO2
0.44 cm, ORB-SLAM3 3.43 cm, flight coverage 1.000 / 1.000 / 0.979, no failed run. ORB-SLAM3's
3.43 cm (runs 2.19-3.87) is the flight-window rule, not its tracking: this vehicle bounced and slid
0.38 m at touchdown, so the window (to the last motion > 0.10 m from the end pose) took in 1.3 s on
the ground, where ORB-SLAM3 always loses the scene; over the airborne part alone (height > 0.10 m)
its error is 0.63-0.69 cm, as in the stored runs (0.63-0.89 cm), best Sim(3) scale 1.002 in both.
Earlier attempts are kept (`verify_stage3_run*.log`): one at full speed failed only the camera rate
(GPU), one could not arm at 0.35x (deviation 15), one with Stage 4's hop schedule gave ORB-SLAM3 a
coverage of 0.82 (Finding 9).

## Not done / open

- (closed 2026-11-17) The user accepted Decision D3, the landing gear at 0.22 m and the hop
  in every flight, after the re-verification above.
- A look at the flight by the user: `flights/room_square.onboard_left.mp4` and
  `room_square.overview.png` now exist; recording 2 may also have been watched in the GUI.
- Landing gear at Livox's 0.5 m clearance in simulation: needs a wider-stance gear design
  than the one tested (3b); only worth doing if the ground phase itself becomes a subject.
- FAST-LIO2's slow height drift: to be characterised in Stage 4 (Finding 2).
- IMU scale S for ORB-SLAM3's settings file: Stage 4 decision (hand-over).
