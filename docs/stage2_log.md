# Stage 2 log -- the simulated sensor rig

Implements Stage 2 of `eVTOL-SLAM-Complete-Project-Guide.pdf` (version pins verified
18 Sep 2026): a simulated Mid-360 LiDAR, IMU and stereo camera on a scripted path in
Gazebo Classic 11, proven correct against ground truth before any SLAM algorithm sees
the data. Gate: `scripts/stage2/verify_sim_bag.py` passes every check.

## How to reproduce

```bash
# host, project root
python3 scripts/common/gen_configs.py        # rig.yaml -> Gazebo models, launch file, algorithm configs
python3 scripts/common/gen_world.py          # seeded worlds: room, room_plain, corridor, field, urban
docker compose build sim                     # evtol/sim:v1 (needs evtol/base:noetic)
docker compose run --rm sim bash /scripts/stage2/record_scripted.sh room 120
docker compose run --rm sim bash -c "source /scripts/common/sim_env.sh && \
    python3 /scripts/stage2/verify_sim_bag.py /output/stage2/scripted_room.bag"
docker compose run --rm sim bash -c "source /scripts/common/sim_env.sh && \
    python3 /scripts/stage2/sim_bag_diagnostics.py /output/stage2/scripted_room.bag"
docker compose run --rm sim bash -c "source /scripts/common/sim_env.sh && \
    python3 /scripts/stage2/camera_check.py /output/stage2/scripted_room.bag"
```

| File | Role |
|---|---|
| `config/rig.yaml` | single source of truth: sensor poses, rates, topics, mount, scripted path, IMU noise densities |
| `scripts/common/gen_configs.py` | generates `sim/evtol_sim/{models,launch}` and `config/generated/*` from `rig.yaml` |
| `scripts/common/gen_world.py` | generates `sim/evtol_sim/worlds/*.world` (fixed seeds) |
| `scripts/common/sim_env.sh` | sourced in the sim container: ROS, our plugins, Gazebo paths (`px4` adds PX4 SITL) |
| `docker/sim.Dockerfile` | Gazebo 11, PX4 v1.14.4 SITL, MAVROS, patched Mid-360 plugin, trajectory driver |
| `sim/evtol_sim/` | catkin package: `src/trajectory_driver.cpp` (baked into the image); models, launch, worlds (generated, mounted at `/sim`) |
| `scripts/stage2/record_scripted.sh` | launches world + rig headless, records all sensor topics |
| `scripts/stage2/verify_sim_bag.py` | the gate |
| `scripts/stage2/sim_bag_diagnostics.py` | **added**: timing, hold length, LiDAR fields, pictures (not in the guide) |
| `scripts/stage2/camera_check.py` | **added**: camera extrinsics, intrinsics and stamp vs image content, scored on the world's box edges (not in the guide) |
| `scripts/stage2/first_look.sh`, `first_look.rviz` | **added**: the guide's Sec. 2.7 commands in one script (Gazebo GUI, RViz preset, left image) |
| `scripts/stage2/livox_to_pc2.py` | CustomMsg -> PointCloud2, for looking in RViz only |

Layout: Stage 2+ scripts use the guide's `scripts/common/` and `scripts/stageN/` folders
(the image and the generators reference those paths). Stage 1 scripts stay flat in
`scripts/` so every documented Stage 1 command keeps working.

**The guide's Stage 2 was never run by its author.** Appendix D: "This book was
prepared on a machine without Docker or a GPU, so no container was built and no
simulation was run while writing it." Its listed unknowns for this stage: the
trajectory driver and the patched plugin compiling against Gazebo 11, PX4's
`ubuntu.sh` running as root in a container, and the multicamera topic names. So
every runtime claim of Sec. 2 (topics, rates, timing, that every gate check passes)
is first confirmed here.

## Transcription from the PDF

There is no `evtol-slam-project.tar.gz`, so every file was taken from the PDF. Plain
`pdftotext -layout` is not good enough: it shifts indentation between text blocks
(fatal for Python) and turned the two-space `sed` pattern `^  message_generation$`
into one space (the build's grep guard would have failed). Instead the code was
rebuilt from glyph positions: code blocks are Menlo 7.68 pt with a fixed 4.625 pt
advance and column 0 at x = 59.53 pt on every page, so each glyph's column is exact;
blank lines come from the constant 10.96 pt line pitch; wrapped lines (continuation
marked with U+21AA) wrap at 98 columns, so a break at column 97 swallowed one space
and a break at 98 is mid-token (all 34 Stage 2 joins checked by hand). The method is
`scripts/tools/guide_extract.py` (host, pdfminer.six); use it for the Stage 3+ files too:
`python3 scripts/tools/guide_extract.py eVTOL-SLAM-Complete-Project-Guide.pdf <outdir>`
writes all 69 printed files plus every Host/Container command block.

Check: running the transcribed `gen_configs.py` on the transcribed `rig.yaml` gives
**byte-identical** copies of the 11 generated files the guide prints (Sec. 2.3 and
Appendix A), except two PDF artefacts in the printed copies: the wrapped `Rcl` line
of `fastlivo2_sim.yaml` lost its alignment spaces, and one blank line of `model.sdf`
falls on a page break. (This check was made on the verbatim transcription; deviation 6
below has since changed the camera plugin block of both `model.sdf` files.) Both sanity checks the guide gives by eye also hold: the third
column of `T_b_c` is (0.819, 0, 0.574); the right camera sits at +0.11 m along the
left camera's x axis.

## Verified against primary sources (2026-11-05)

- Pins (`git ls-remote`): PX4 tag v1.14.4 is tag object `4eb5668b`, commit
  `1555f2bd2229544c43966ab5f94879c41d8e1e01`; Livox-SDK v2.3.1 = `14c533d` (HEAD is
  `9306596`); livox_ros_driver v2.6.0 = `fb5669b`; fratopa/Mid360_simulation_plugin
  `aae8ee3` is HEAD (2024-01-29, "Minor bug fixes to timestamps").
- Plugin source at `aae8ee3`: every `sed` patch target exists exactly as the
  Dockerfile expects (offset_time line 597, timebase line 560, the CustomMsg/CustomPoint
  types at lines 18/118/552/589, `libprotobuf.so.9` at CMakeLists line 52,
  `  message_generation` with two spaces at line 13, `livox_ros_driver2` in package.xml).
- The plugin loads its scan table from `dirname(__FILE__)/../scan_mode/<csv>`;
  `mid360-real-centr.csv` has 800 000 rays (azimuth, zenith 37.8-97.2 deg = +52..-7 deg
  elevation, the Mid-360 FOV). Each 10 Hz scan takes the next 20 000 rays.
- Per-point fields written by the plugin: `line = i % 4` (0-3; FAST-LIO2 drops
  `line >= scan_line`, here 4), `tag = 0x10` (accepted by FAST-LIO2's Livox filter),
  `reflectivity = 100`, `offset_time` = 0 after patch 1. Rays with no return are
  published as (0, 0, 0); the algorithms' `blind` range removes them.

## Deviations from the guide

| # | Guide | Here | Why |
|---|---|---|---|
| 1 | `sim.Dockerfile` clones Livox-SDK HEAD | `git checkout v2.3.1` | same pin as `fastlio2.Dockerfile`; HEAD (`9306596`) is ahead of the tag |
| 2 | `--branch v1.14.4` only | also `test $(git rev-parse HEAD) = 1555f2bd...` | a moved tag now fails the build instead of silently changing PX4 |
| 3 | compose: `x-sim` anchor + `sim`, `sim-live`, `fastlio2-live`, `hw`, `kalibr` | only `sim`, written in the repo's existing style | the other services belong to Stages 5 and 7 |
| 4 | gate command `docker compose run --rm sim python3 /scripts/stage2/verify_sim_bag.py ...` | `... sim bash -c "source /scripts/common/sim_env.sh && python3 ..."` | a command run directly does not read `.bashrc`, so ROS is not sourced: `ModuleNotFoundError: No module named 'rosbag'` (same class as FAST-LIO2 corrections 2-3) |
| 5 | `gen_world.py`: `<gravity>` and `<magnetic_field>` inside `<physics>` ("match PX4's own worlds") | moved to `<world>` | SDF 1.6 defines both as `<world>` elements (sdformat9 `1.6/world.sdf`, gravity default `0 0 -9.8`). Inside `<physics>` Gazebo 11 logs `[Err] PhysicsEngine.cc:255 SetParam(gravity) std::any_cast error` and silently keeps 9.8: measured **9.8000** m/s^2 at rest. Fixed: **9.8066**. PX4's own `empty.world` has the same latent layout; the gate's 0.05 tolerance hid it |
| 6 | `gen_configs.py`: multicamera plugin `<updateRate>0.0</updateRate>` (publish every render) | `<updateRate>` = 2 x camera rate (40), a publish throttle with a 25 ms minimum gap | on the GPU, Gazebo's rendering catch-up (`Sensor::Update`, `updateDelay`) emitted **2471 frames instead of 2400** in 120 s: bursts 0-3 ms after the previous frame, 13 of them with an identical stamp (different image noise). The gate passed (20.6 Hz is within 10 %), but ORB-SLAM3 and FAST-LIVO2 need strictly increasing image times. With the throttle: 2395 frames, intervals 48-58 ms, none repeated. Not seen under llvmpipe (too slow to catch up). Rejected alternative: `gzserver --lockstep` gives exact 50.000 ms frames but **halves the Mid-360 to 5 Hz**: in strict-rate mode `Sensor::NeedsUpdate` measures from `lastMeasurementTime`, which `RaySensor::UpdateImpl` sets *after* the plugin's 20 000-ray cast, while the ray thread sleeps exactly one period, so every first wake-up is a few ms short (Gazebo 11 `Sensor.cc`, `SensorManager.cc`; evidence in `output/diagnostics/stage2/lockstep_test/`) |

## Results (2026-11-05, room world, 120 s)

Recorded on the GPU (RTX 5090, driver 595.99.02) with the camera throttle of deviation 6:
`output/stage2/scripted_room.bag`, 2.2 GB, recorded 15:09-15:11. Two earlier 120 s bags, both
passing the gate, are kept in `output/diagnostics/stage2/`: `llvmpipe_room_120s/` (software
rendering, before the reboot) and `gpu_room_120s_unthrottled/` (the guide's camera setting).
The tables below are the final GPU bag; the llvmpipe values differed by at most 0.2 ms in the
time offsets and 0.1 px in the principal point. Recording starts at sim time 1.16 s:
model loading blocks the world update (sim time advanced only 0.046 -> 0.171 s during the
2.3 s spawn), so start-up does not eat the 8 s hold, although the trajectory driver counts it
from absolute sim time rather than from the spawn.

**Gate (`verify_sim_bag.py`): ALL CHECKS PASSED** (`output/stage2/scripted_room.gate.txt`)

| Check | Measured | Limit |
|---|---|---|
| /livox/imu, /livox/lidar, /ground_truth/odom rates | 200.0, 10.0, 200.0 Hz | +-10 % |
| /stereo/left, /stereo/right rates | 20.0, 20.0 Hz (2395 frames; unthrottled GPU bag: 20.6 Hz, 2471) | +-10 % |
| LiDAR message type | `livox_ros_driver/CustomMsg` (patch 3) | exact |
| points per scan | 20 000 | 15 000-21 000 |
| non-zero per-point `offset_time` | 0 (patch 1) | 0 |
| left/right stamps identical | 2395 pairs | all |
| \|accel\| at rest | 9.8066 m/s^2 | g +- 0.05 |
| gyro at rest | 0.00 rad/s (max) | < 1e-3 |
| **IMU accel vs ground-truth kinematics** | **RMS 0.001 m/s^2** over 2399 samples | < 0.15 |
| rig moved | extent 6.0 x 4.0 x 1.0 m (= 2 x amp_xyz) | > 1 m |

**Beyond the gate** (`sim_bag_diagnostics.py`, `camera_check.py`; outputs in
`output/stage2/scripted_room_diag/`, `scripted_room_diag.txt`, `scripted_room_camcheck*`). The gate checks each sensor against ground truth; these
check time stamps across sensors and the generated extrinsics that Stage 3 consumes.

| Quantity | Result | Meaning |
|---|---|---|
| LiDAR stamp vs true scan time | -1.2 ms (plane fit of 1071 scans to the room's walls and floor; fit +10 % / +17 % worse at -10 / +10 ms) | the plugin stamps with `ros::Time::now()`, but `/clock` runs at the physics rate, so stamps are exact to the 1 ms step. No fifth patch needed |
| camera stamp vs image content | +1.4 ms (world box edges through ground truth, 252 stereo pairs; -6 % / -10 % at +-10 ms) | stamps match content. Frame intervals 48-58 ms (mean 50.1, std 0.8 ms); llvmpipe jittered 16-109 ms |
| IMU / ground truth stamps | both exactly every 5.000 ms; same phase or 1 ms apart depending on the run | the relative phase is set at start-up. The LiDAR (-1.2 ms) and camera (+1.4 ms) residuals have opposite signs, so they are not one common ground-truth offset: all sensors agree with ground truth to about one 1 ms physics step |
| stationary hold in the bag | 7.29 s (motion detected at 8.44 s) | gate uses the first 5 s; FAST-LIO2 initialises gravity here |
| LiDAR fields | lines 0-3, tag 0x10, 1.1 % rays without return (published as 0,0,0) | pass FAST-LIO2's Livox filter (`line < scan_line 4`, tag 0x10) |
| camera extrinsic, rotation | best within +0.02 deg of the generated `IMU.T_b_c1` (0.5 deg costs 22-46 % of the edge score) | ORB-SLAM3 and FAST-LIVO2 chains agree to 3e-8 |
| camera extrinsic, translation | best within 2.2 mm (1 cm costs 5-24 %) | right camera through `Stereo.T_c1_c2` scores as well as the left |
| LiDAR -> camera (`Rcl`/`Pcl`) | scan rings land on the surfaces they hit (`overlay_t*.png`) | read back from the generated `fastlivo2_sim.yaml` |
| principal point | best at cx 375.46, cy 239.62 (GPU, coarse sweep; llvmpipe 0.1 px sweep, both cameras: 375.45, 239.70); generated 376.0 / 240.0; Gazebo's `camera_info` claims 376.5 / 240.5 | ~0.5 px residual: OpenCV's pixel-centre convention puts a symmetric frustum at (w-1)/2 = 375.5. Common to both cameras (no stereo effect), ~1 mrad bearing. **Kept as the guide has it**; one-line change in `gen_configs.py` (`cx = (w-1)/2`) if wanted |

Looked at (the guide's "first look", done on extracted frames; the GUI look is still to do):
camera images upright, floor at the bottom, 35 deg down, textured; stereo disparity in the
right direction (about 16 px at about 3 m); LiDAR top view shows the 14 x 10 m room, floor
rings, clutter shadows, a 1.2 m blind radius below the rig (1.5 m / tan 52 deg = 1.17 m) and
returns up to 2.33 m on the walls (+7 deg FOV edge: 1.5 + 7 tan 7 deg = 2.36 m).

## Notes

- **Smoothstep ramp.** `trajectory_driver.cpp` ramps the amplitude with a cubic smoothstep,
  whose second derivative jumps at the end of the ramp (t = 12 s): an acceleration step of
  about 0.8 m/s^2 along x. Harmless for the gate (IMU and ground truth see the same motion);
  "acceleration never jumps" in the guide's comment is not literally true.
- **Dark boxes** in the images are shadowed faces of textured boxes (every box uses a
  textured material); the GPU and llvmpipe renders of the same moment are practically
  identical, so this is lighting, not a renderer fault.
- **De-skew is not exercised in simulation** (patch 1: all rays fire at once), as the guide
  says; motion compensation is tested only on real data (Stage 1 datasets, Stage 7).

## Host state on 2026-11-05 (GPU)

Unattended upgrades replaced the NVIDIA user-space driver with 595.99 at 06:29 while the
595.91 kernel module stayed loaded: `nvidia-smi` reported "Driver/library version mismatch",
and every GPU container failed (`/run/nvidia-persistenced/socket: no such file`). Until the
reboot the sim container ran with a scratch compose override (no GPU reservation,
`LIBGL_ALWAYS_SOFTWARE=1`, `__GLX_VENDOR_LIBRARY_NAME=mesa`): Mesa llvmpipe through the host
X server `:1`; that is the `llvmpipe_room_120s` bag.

**After the reboot (kernel 7.0.0-42, 14:58):** driver 595.99.02 loaded; apt Docker daemon
(snap daemon disabled), all `evtol/*` images present; `verify_host.sh` "Host is ready";
`verify_base.sh` renderer "NVIDIA GeForce RTX 5090/PCIe/SSE2", also inside `evtol/sim:v1`.
The final bag above was recorded on the GPU.

**Still to do for Stage 2:** the GUI first look (Sec. 2.7), a human step:
`docker compose run --rm sim bash /scripts/stage2/first_look.sh` (opens Gazebo, RViz with the
Mid-360 cloud, and the left camera image; records nothing). Test-launched 15:15: all sensor
topics present, IMU 200 Hz, real-time factor 0.94 with the GUI, the cloud outlines the room.
The judgement of what it shows is still yours.
