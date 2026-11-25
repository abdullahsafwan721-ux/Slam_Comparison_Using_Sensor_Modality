# Stage 5 log -- flying on SLAM: the closed loop in simulation

Implements Stage 5 of `eVTOL-SLAM-Complete-Project-Guide.pdf` (pp. 72-78) as planned in
`docs/eVTOL_SLAM_Research_and_Stage3-5_Plan.pdf` (section 6). The simulated drone takes off,
flies and lands with **FAST-LIO2 as its only source of position, height and heading**, through
PX4's EKF2. GPS, barometer and magnetometer are switched off. Stage 5 is the last stage of this
phase: Stages 6-8 need the Jetson and the real sensor (user's decision, 18 Nov).

Gate (guide 5.6):
- the mission runs to completion;
- PX4's position APE is within a small multiple of FAST-LIO2's own;
- the hover is steady, with no growing oscillation;
- EKF2_EV_DELAY is tuned only if the vehicle oscillates.

**Status: passed (18 Nov 2026)**:
- **Every flight completed:** all 8 closed-loop flights of the results set (4 squares, 3 hovers
  of 30 s, 1 hover of 120 s), the guide's three terminals run by hand, and every verification
  flight.
- **PX4 tracks SLAM closely:**
  - PX4's in-flight APE is 1.4-1.9 cm, 2.6-4.6x FAST-LIO2's 0.3-0.8 cm. Square r1 reached
    9.3x, a number inflated by a touchdown bounce (see Results).
  - Unaligned, in its own frame, PX4's estimate stayed within 2.6-5.3 cm of the truth.
  - EKF2 follows SLAM with a lag of 0.00-0.03 s, so EKF2_EV_DELAY needed no tuning.
- **The hover is steady:** standard deviation at most 2.4 cm in every hover. Over 120 s, the
  largest deviation per quarter was 8.0 / 7.7 / 7.1 / 8.2 cm: no growth.
- **The one anomaly is explained:** PX4's height estimate sinks after touchdown. PX4's own
  logs show it is a simulator artefact (Results, Landing).

**Extension (18 Nov): the closed loop over the Stage 4 matrix**, with both ROS-based SLAM methods
(FAST-LIO2 18 cells, FAST-LIVO2 19 cells, every one flown and scored):
- Both methods fly 3-27 cm from where PX4 believes it is wherever they see structure.
- FAST-LIO2's degenerate cases (corridor, field, 60 m) end metre-level off.
- FAST-LIVO2 diverges at 50-60 m and crashes the vehicle.
- A 5 s LiDAR outage triggers PX4's failsafe.
- ORB-SLAM3 cannot close this loop by design.
- FAST-LIVO2 needed a fix (it publishes its own pose to PX4) and EKF2_EV_DELAY 150 ms.

See "The closed loop over the Stage 4 matrix".

The guide's "steady **in the Gazebo window**" criterion is a judgement made by looking. Flights
were watched with Gazebo and RViz open, and pictures kept (below), but the final judgement is
the user's: `FLY=1 GUI=true bash scripts/stage5/verify_stage5.sh`.

Started 2026-11-18 on commit `38922e6` (Stage 4 verified), with the same images and no
rebuild. The go-ahead was given by the user on 18 Nov.

## How to reproduce

```bash
# host, project root, NOTHING else running (host networking: one ROS master on port 11311)
# a) the guide's three terminals, by hand (Gazebo and RViz open; a separate folder, so a
#    manual flight never mixes with the results set):
docker compose run --rm sim-live bash /scripts/stage5/sim_ev.sh room /output/stage5/manual/manual_square.bag square --size 4 --alt 1.5 --speed 1
docker compose run --rm fastlio2-live bash /scripts/stage5/slam_live.sh          # after "NO position source"
docker compose run --rm sim-live bash -c "source /opt/ros/noetic/setup.bash && \
    python3 /scripts/stage3/offboard_mission.py square --size 4 --alt 1.5 --speed 1 --sitl-params"
#    Ctrl-C terminal 1 after "landed and disarmed", then terminal 2; then:
FLIGHTS=output/stage5/manual EVAL=output/stage5/manual/eval bash scripts/stage5/eval_closed_loop.sh manual_square
# b) the same three terminals run in order by one script, then scored (what produced the results):
bash scripts/stage5/run_closed_loop.sh room_square_r1 room square --size 4 --alt 1.5 --speed 1   # r1-r4
bash scripts/stage5/run_closed_loop.sh room_hover_r1  room hover --alt 1.5                       # r1-r3
bash scripts/stage5/run_closed_loop.sh room_hover_long_r1 room hover --alt 1.5 --hold 120
#    GUI=true RVIZ=true opens the windows; alongside it, pictures:
#    bash scripts/stage5/capture_windows.sh output/stage5/flights/<name>
python3 scripts/stage5/stage5_figures.py                                          # tables + figures
bash scripts/stage5/verify_stage5.sh                                              # FLY=1 GUI=true adds a flight
# c) the extension: the closed loop over the Stage 4 matrix (~3.5 h, one flight at a time)
bash scripts/stage5/run_closed_loop_matrix.sh          # ALGOS="fastlivo2" CONDS="room field" for a subset
python3 scripts/stage5/matrix_summary.py               # matrix_tables.md + matrix_scorecard.png
for a in fastlio2 fastlivo2; do python3 scripts/stage5/stage5_figures.py output/stage5/matrix/$a; done
MATRIX=1 bash scripts/stage5/verify_stage5.sh          # + every matrix flight re-scored
```

| File | Origin | Role |
|---|---|---|
| `scripts/stage5/slam_to_px4.py` | guide 5.1, **verbatim** | FAST-LIO2's IMU pose -> base_link pose (M * T * M^-1) on `/mavros/vision_pose/pose`, stamped with the scan time |
| `config/px4/ev_only.params` | guide 5.2, **verbatim** | EKF2 on external vision only (checked against PX4 v1.14.4 in the plan, 6.3) |
| `scripts/stage5/set_params.py` | guide 5.2, **adapted** | applies the file through MAVROS, reads every value back |
| `scripts/stage5/imu_noise_live.py` | guide 5.3, **verbatim** | `/livox/imu` -> `/livox/imu_noisy`, the Stage 3 noise model live |
| `scripts/stage5/sim_ev.sh` | guide 5.4, **adapted** | terminal 1: PX4 boots, parameters written, reboot with no position source, recording; keeps PX4's flight log |
| `scripts/stage5/slam_live.sh` | guide 5.4, **adapted** | terminal 2: FAST-LIO2 on the noised IMU + relay |
| `compose.yaml` `sim-live`, `fastlio2-live` | guide Appendix (compose), **adapted** | host networking, one ROS master |
| `scripts/stage3/offboard_mission.py` | changed (Stage 3 script) | `--hold S`: length of the hover (default 30 s, as before) |
| `scripts/stage5/run_closed_loop.sh` | **new** | the three terminals in order, with waits on what each needs, then scoring |
| `scripts/stage5/eval_closed_loop.sh` | guide 5.5, **extended** | the guide's two APEs + `metrics_extra.py` + `closed_loop_metrics.py` + `ulog_touchdown.py` |
| `scripts/stage5/closed_loop_metrics.py` | **new** (plan 6.6) | offline frame check; relay / EKF2 / control / hover (with growth test) / landing metrics |
| `scripts/stage5/ulog_touchdown.py` | **new** | from PX4's flight log: what EKF2 did at touchdown, and why |
| `scripts/stage5/stage5_figures.py` | **new** | `stage5_tables.md`, `figures/closed_loop_<flight>.png` |
| `scripts/stage5/capture_windows.sh`, `xwd_to_png.py` | **new** | pictures of the Gazebo / RViz windows during a watched flight |
| `scripts/stage5/verify_stage5.sh` | **new** | verification (below) |
| `scripts/stage5/run_closed_loop_matrix.sh` | **new** (extension) | the closed loop over the Stage 4 matrix, FAST-LIO2 and FAST-LIVO2, EV_DELAY tuning first |
| `scripts/stage5/fault_live.py` | **new** (extension) | live twin of `degrade_bag.py`: LiDAR dropout, camera blackout |
| `scripts/stage5/bag_modes.py`, `matrix_summary.py` | **new** (extension) | PX4's mode changes; the matrix tables and scorecard |
| `config/launch/fastlio2.launch`, `fastlivo2.launch` | changed (extension) | `lid_topic` / `img_topic` arguments (defaults = config, replays unchanged); FAST-LIVO2's own MAVROS pose remapped away |

## Deviations from the guide, and why

| # | Where | Guide | What happens | What we do |
|---|---|---|---|---|
| 1 | `set_params.py` | `param/set` called once the services exist | right after MAVROS connects it is still downloading PX4's parameter list and the services throw a ServiceException (found in Stage 3) -- the guide's loop would crash | set/get retried for up to 60 s |
| 2 | `set_params.py` | read-back compares `.integer` or `.real`, chosen from the text of the value | `EKF2_EV_DELAY 0` and `EKF2_EV_POS_* 0` are FLOAT parameters written as integers; MAVROS returns floats in `.real` | numeric comparison of whichever field is set |
| 3 | `sim_ev.sh` | spawn at the world origin; no clearance check; waits block for ever; bag of 6 topics | the room has a box at the origin (Stage 3 deviation 7) | Stage 3's `px4_record.sh` conventions: `SPAWN` (default -2.0 -1.8), spawn height from the landing gear, `check_clearance.py` on the mission, 240 s limits; the bag adds raw and noised IMU, LiDAR, EKF2 status, so every flight can be replayed offline |
| 4 | `slam_live.sh` | relay in the foreground, no signal handling | `docker stop` left FAST-LIO2 running until killed | INT/TERM stop all three processes (Ctrl-C: clean exit in 16 s) |
| 5 | `compose.yaml` | `sim-live: <<: *sim` | our compose has no `&sim` anchor, and a merge replaces whole keys | both services written out; `ROS_HOSTNAME=localhost`, `ROS_MASTER_URI=http://localhost:11311` |
| 6 | mission | `square --size 6 --alt 1.5 --speed 1` from the origin | 6 m square from the origin hits boxes (Stage 3) | the plan's `square --size 4 --alt 1.5 --speed 1` (2 laps) from (-2.0, -1.8), with Stage 3's 0.4 m hop; plus `hover` (plan 6.6) |
| 7 | `eval_closed_loop.sh` | PX4's pose scored against the IMU's ground truth ("the 13 cm lever arm adds a few centimetres") | -- | scored against the ground truth of base_link (`T_world_imu * M^-1`), so the lever arm adds nothing |
| 8 | evaluation | APE only (evo aligns the trajectories) | an aligned APE hides a frame error and says nothing about what PX4 *believed* | `closed_loop_metrics.py`: unaligned errors in PX4's own frame (what it was told, what it believed, where it was), EKF2's lag behind SLAM, setpoint tracking, hover steadiness and its growth, the landing |
| 9 | flights | 1 flight | -- | 4 squares + 3 hovers (30 s) + 1 hover of 120 s (the growth test needs a long hold: `--hold`), plus the by-hand run |
| 10 | `sim_ev.sh` | PX4's own flight log is lost with the container | the touchdown anomaly could only be explained from EKF2's internals | the log is kept as `<flight>.ulg` (phase 2); `ulog_touchdown.py` reads it. Stage 7 tunes EV_DELAY from such logs (guide 5.6) |
| 11 | `compose.yaml` | -- | RViz opened a modal "ROS Noetic end-of-life" notice over FAST-LIO2's map | `DISABLE_ROS1_EOL_WARNINGS=1` in both live services (Noetic is the guide's choice; the notice is known) |
| 12 | FAST-LIVO2 in the loop | "FAST-LIVO2 can be substituted the same way" | FAST-LIVO2 publishes its own unrotated pose on `/mavros/vision_pose/pose`; PX4 got two contradicting streams and the flight was lost | remapped in `fastlivo2.launch`; `run_closed_loop.sh` flies only if the relay is the one publisher |
| 13 | EKF2_EV_DELAY (5.6) | step it, keep the value that minimises PX4's APE | FAST-LIVO2's pose arrives late; the Stage 3/4-window APE includes landing events | stepped 0-190 ms, chosen by PX4's error in flight: 150 ms for FAST-LIVO2; FAST-LIO2 stays at 0 |
| 14 | compose, scripts | one method (FAST-LIO2), one environment | -- | `fastlivo2-live` service, `ALGO` / `FAULT` / `EV_DELAY` options, live faults, the matrix driver; the room results above are unchanged |

## Before the first flight: the frame check (plan 6.8)

The Stage 4 FAST-LIO2 run of the room flight (`/Odometry`) was replayed through
`slam_to_px4.py`. Its output was compared, with **no alignment**, to the true base_link pose
expressed in the frame PX4 uses (base_link when SLAM started):

| Climb correlation | RMSE | Max | Yaw RMSE |
|---|---|---|---|
| **+1.000** | 4.3 cm | 6.6 cm | 0.18 deg |

A climb is a climb, and the error is SLAM's own size. Only then was the loop closed
(`output/stage5/frame_check/`; repeated by `verify_stage5.sh` step 2).

## Results (`output/stage5/stage5_tables.md`, `figures/closed_loop_*.png`)

Every flight followed the same sequence:
1. PX4 booted.
2. All 12 EV-only parameters were read back OK.
3. PX4 rebooted with no position source.
4. FAST-LIO2 published 2-4 s after its start, and EKF2 reported a valid position 2-3 s later.
5. The mission armed, flew and landed.

All errors are in cm. **In flight** means take-off to the first touchdown. The APE columns
use the guide's scoring (evo, SE(3)-aligned) over the Stage 3/4 flight window. The next three
columns are unaligned, in PX4's own frame.

| Flight | FAST-LIO2 APE | PX4 APE | SLAM pose sent vs truth | PX4 vs SLAM pose | PX4 vs truth | EKF2 lag | Hover sd x / y / z; max deviation per quarter |
|---|---|---|---|---|---|---|---|
| square r1 | 0.76 | 7.07 * | 2.9 | 2.8 | 3.5 | 0.00 s | -- |
| square r2 | 0.58 | 1.77 | 3.8 | 2.8 | 4.6 | 0.00 s | -- |
| square r3 | 0.60 | 1.74 | 3.7 | 2.8 | 4.5 | 0.00 s | -- |
| square r4 | 0.70 | 1.80 | 3.4 | 2.7 | 4.2 | 0.00 s | -- |
| hover r1 (30 s) | 0.56 | 1.72 | 3.4 | 1.8 | 4.3 | 0.02 s | 1.7 / 1.7 / 2.3; 6.3 / 5.8 / 9.2 / 7.3 |
| hover r2 (30 s) | 0.46 | 1.63 | 1.9 | 1.8 | 2.9 | 0.00 s | 1.6 / 1.9 / 2.3; 4.9 / 5.0 / 8.0 / 5.7 |
| hover r3 (30 s) | 0.45 | 1.71 | 4.4 | 1.8 | 5.3 | 0.02 s | 1.7 / 1.6 / 2.4; 6.5 / 6.5 / 9.6 / 7.9 |
| **hover, 120 s** | 0.31 | 1.42 | 2.1 | 1.4 | 2.6 | 0.03 s | **2.0 / 2.1 / 1.9; 8.0 / 7.7 / 7.1 / 8.2** |
| by hand (square) | 0.70 | 1.92 | 3.1 | 2.8 | 4.0 | 0.00 s | -- |

\* The Stage 3/4 flight window ends at the *last* time the vehicle is airborne. In r1 the
vehicle bounced 0.2 m at touchdown, so the window includes the landing error described below.
Over take-off to first touchdown, r1's PX4 error is 3.5 cm unaligned, like the others.

- **The loop works and is tight.**
  - In flight, PX4's estimate stays within 1.4-2.8 cm of the SLAM pose it is given, and
    within 2.6-5.3 cm of the truth without any alignment.
  - The best time shift between PX4's estimate and the SLAM pose is 0.00-0.03 s: EKF2 fuses
    the 10 Hz pose without lag, so EKF2_EV_DELAY stays 0 (guide: tune only if the vehicle
    oscillates; it does not).
  - The unaligned 2-5 cm is a nearly constant offset that alignment removes (aligned APE
    1.4-1.9 cm). The offline frame check shows the same gap (4.3 cm unaligned against
    1.2 cm aligned), so it is in SLAM's start frame, not in the loop. Its source was not
    isolated.
- **The hover is steady, and the oscillation does not grow.**
  - In every hover the true position has a standard deviation of at most 2.4 cm.
  - The height wanders slowly by about +/-3-5 cm, in bumps roughly 8-10 s apart, with the
    same shape in all three 30 s hovers. PX4's own estimate follows the truth through it
    (within 2 cm), so the controller, not SLAM, is moving the vehicle.
  - The 120 s hover is the growth test. The largest deviation from the setpoint per quarter
    of the hold was 8.0 / 7.7 / 7.1 / 8.2 cm: flat. In the 30 s hovers the largest quarter
    is the third (the bump at ~18 s) and the last quarter is lower again.
- **Setpoint tracking is the controller's, not SLAM's.** The true path trails the moving
  setpoint by 1.15 s: about 1 m at 1 m/s, the lag of PX4's position controller following a
  position-only setpoint (the mission sends no velocity feed-forward). Delayed by that lag,
  the setpoint is followed to 9.4-10.2 cm horizontally. The vertical difference (22 cm) comes
  from setpoints the vehicle cannot follow by design: the 1 m/s climb starts before PX4 lifts
  off (~3 s after arming), and the 1 s hop step. This is the same mission as Stages 3-4.
- **Landing: PX4's height estimate sinks below the ground after touchdown -- a simulator
  artefact, verified from PX4's own flight logs** (`<flight>.touchdown.txt`;
  `ulog_touchdown.py`; 5 flights with logs: hovers r2, r3 and 120 s, square r4, by hand):
  - **What is seen.** In the 5 s after the first touchdown, PX4's estimate is off by up to
    30-64 cm, almost all vertical (in r1: -0.54 m while the truth was 0.0-0.2 m, a bounce).
    It recovers within about 3 s. FAST-LIO2's pose stays within 3.9 cm of the truth
    throughout.
  - **Not a vision rejection.** EKF2 fused the vision height at every update (0 of 53-55
    rejected; test ratio <= 0.3), and the vision height was right.
  - **The IMU misses the impact.** Across the touchdown, the true vertical speed changes by
    +0.64-0.67 m/s, but PX4's IMU integrates only +0.07-0.25 m/s of it (10-38 %), with peaks
    of 23-44 m/s^2. So 0.5 s after touchdown EKF2 still believes the vehicle is descending at
    0.50-0.65 m/s while it stands still. The 10 Hz vision, weighted as 0.1 m noise
    (EKF2_EVP_NOISE), pulls the estimate back over ~2 s.
  - **Why.** Gazebo's IMU reports the instantaneous acceleration at 250 Hz, and a touchdown's
    contact impulse lasts a few 1 ms physics steps, so most of it falls between samples: the
    mechanism Stage 4 found in its IMU check (deviation 5 there).
  - **On hardware.** A real IMU integrates over each sample (delta velocity, anti-alias
    filter), so this mechanism should not carry over. What to check in Stage 7 is
    accelerometer clipping on a hard landing.
- **Observed, harmless here:**
  - Before arming, PX4 reports "Preflight Fail: Yaw estimate error / heading estimate not
    stable" for a few seconds, while EKF2's heading (from vision only) settles. The mission's
    arming loop simply retries.
  - In every flight, at about 46 s of simulation time, MAVROS logged "TM : Time jump
    detected. Resetting time synchroniser". The error traces show no step there. On hardware
    the time synchronisation matters more (Stage 7).

## The guide's way of running it: by hand, and watched

- **By hand.** The guide's three terminals were run exactly as in "How to reproduce" (a); only
  `-T` was added, because the run had no TTY.
  - Terminal 1 passed the clearance check, read back all 12 parameters and rebooted with no
    position source.
  - Terminal 2 published 4 s after its start.
  - Terminal 3 flew the square to "landed and disarmed".
  - Ctrl-C on terminal 1 closed the bag and kept PX4's log; Ctrl-C on terminal 2 exited
    cleanly in 16 s.
  - Scored with the documented command: in line with the scripted flights (table, last row).
- **Watched.** Hovers r2, r3 and the 120 s hover were flown with the Gazebo window and
  FAST-LIO2's RViz map open (`GUI=true RVIZ=true`). Their numbers equal the headless flights'.
  - RViz pictures of the 120 s hover are in `flights/room_hover_long_r1.shots/`: FAST-LIO2's
    map of the room and the vehicle's pose.
  - Pictures of the Gazebo window from the same flight were discarded: `xwd` copies what is
    visible, and RViz's window covered Gazebo's.
  - `capture_windows.sh` now photographs Gazebo only when RViz is closed, and sets Gazebo's own
    view (`gzclient_camera`) to follow the drone. The first attempt picked a camera from
    `gz camera -l`, which also lists the rig's stereo cameras, and did not find the simulator
    container (`docker ps` truncates long commands). Both are fixed and checked.
  - The final verification flight has 16 such pictures, 4 s apart, in
    `output/stage5/verify_pictures/20261118_1025/`. The view moves with the drone, and the
    drone is seen flying in the room. At the follow distance, a box or wall sometimes
    blocks the view.
  - By hand: right-click the drone in Gazebo and choose Follow.

## The closed loop over the Stage 4 matrix (extension, 18 Nov)

Asked by the user: every algorithm, environment and configuration of the project, flown in the
closed loop, not only FAST-LIO2 in the room. `scripts/stage5/run_closed_loop_matrix.sh` flies
every Stage 4 condition with its Stage 4 mission and spawn, the SLAM method being PX4's ONLY
source of position, height and heading:
- **A environments:** room, room_plain, corridor, field.
- **B altitude:** urban square at 10-60 m.
- **C speed:** figure-8 at 2 / 5 / 8 m/s.
- **D IMU grade:** x3, x10, x30 the baseline noise, injected live into the IMU the SLAM method uses.
- **E faults:** injected live by `fault_live.py`: LiDAR gone for 2 s and for 5 s, camera black
  for 5 s.

There are 18 FAST-LIO2 cells and 19 FAST-LIVO2 cells, plus 6 FAST-LIVO2 delay-tuning flights.
Every cell was flown and scored (`output/stage5/matrix/matrix_tables.md`,
`matrix_scorecard.png`, one figure per flight in `<algo>/figures/`). It is one flight per cell:
a test of the loop, not a statistic.

### ORB-SLAM3 cannot be in this loop
- ORB-SLAM3 never gives a pose before the vehicle moves. In 69 of 69 Stage 4 runs its first pose
  came after take-off: at the earliest 0.7 s, median 19 s, and 9 runs never started.
- A PX4 that flies on vision alone cannot take off without a pose.
- So stereo-inertial initialisation needs motion, and the motion needs a pose: a deadlock by
  design, not a bug.
- Closing the loop with ORB-SLAM3 needs a second source for take-off (GNSS, barometer and optical
  flow) and a hand-over once it has initialised. That is a different architecture from the
  guide's "SLAM is the only source", so it was not flown. There is also no live ORB-SLAM3 node in
  this project (it runs on EuRoC exports).

### FAST-LIVO2: two things the guide does not say
- **FAST-LIVO2 publishes its own pose to PX4.**
  - `LIVMapper.cpp:212` advertises `/mavros/vision_pose/pose` and publishes its raw pose there,
    in its unrotated (upside-down) IMU frame.
  - The first FAST-LIVO2 closed-loop flight therefore fed PX4 two contradicting pose streams:
    1942 poses from the relay (frame `map`) and 1966 from FAST-LIVO2 (frame `camera_init`). The
    vehicle was lost in the climb. FAST-LIVO2 itself was right throughout, within millimetres of
    the truth.
  - The offline frame check could not see this, because there FAST-LIVO2 was not running.
  - Fixed by a remap in `config/launch/fastlivo2.launch`, which has no effect on replays.
  - `run_closed_loop.sh` now refuses to fly unless the relay is the only publisher on that topic.
  - The two lost flights are kept in `fastlivo2/invalid_double_publisher/`.
  - Every FAST-LIO2 flight was checked: it received at most one relayed pose per FAST-LIO2 pose.
  - The guide's "FAST-LIVO2 can be substituted the same way" is not true as printed.
- **FAST-LIVO2's pose arrives late, and EKF2_EV_DELAY must be tuned (guide 5.6).**
  - Live, FAST-LIVO2 publishes 76-98 ms after the state it describes (median; p95 ~110 ms; 74 ms
    in replay).
  - PX4's estimate, measured directly, lagged the truth by 130 / 100 / 55 / 35 ms at a delay of
    0 / 40 / 75 / 110 ms.
  - The guide's procedure was applied: the room flight was flown with the delay stepped, and the
    value giving the lowest PX4 error was kept.

  | EKF2_EV_DELAY | 0 ms | 40 ms | 75 ms | 110 ms | **150 ms** | 190 ms |
  |---|---|---|---|---|---|---|
  | PX4 vs truth in flight (cm) | 15.0 | 12.2 | 7.4 | 4.7 | **2.6** | 9.3 |
  | PX4 APE, Stage 3/4 window (cm) | 12.3 | 96.6 | 5.4 | 3.4 | 85.4 | 10.1 |

  - **Criterion changed from the guide.** The guide's criterion is "PX4's APE". Here the error in
    flight (take-off to first touchdown) was used, because the Stage 3/4 window takes in the
    landing, and two landing events (below) made that APE meaningless at 40 and 150 ms.
  - With 150 ms, FAST-LIVO2's loop is as tight as FAST-LIO2's (2.6-4.4 cm in the room). The
    0.15 s is the end-to-end delay of this simulated setup; on hardware it must be measured
    again.

### Results (PX4 vs truth while airborne, unaligned, in its own frame: what the vehicle believed vs where it was)

| Condition | FAST-LIO2 | FAST-LIVO2 | Stage 4 open-loop SLAM APE (LIO2 / LIVO2) |
|---|---|---|---|
| room | 3.5 cm | 4.4 cm | 0.70 / 0.29 cm |
| room_plain | 4.8 cm | 4.8 cm | 0.75 / 0.30 cm |
| corridor | **1.74 m** (max 3.6 m) | 12.5 cm | 28.6 / 7.5 cm |
| field | **8.8 m** (max 16 m) | 8.3 cm | 5.8 m / 2.6 cm |
| urban 10 / 20 / 30 m | 5.5 / 9.0 / 6.8 cm | 9.3 / 7.4 / 4.6 cm | <= 1.1 / <= 0.44 cm |
| urban 40 m | 26.9 cm | 7.1 cm | 1.65 / 1.78 cm |
| urban 50 m | 12.6 cm | **diverged, crashed** (mission incomplete) | 5.6 / 4.9 cm |
| urban 60 m | **1.26 m** (max 2.8 m) | **diverged, flew away 412 m** (2 of 2 flights) | 46 cm / diverged |
| speed 2 / 5 / 8 m/s | 3.0 / 4.6 / 12.9 cm | 6.8 / 6.2 / 19.0 cm | <= 0.55 / <= 0.92 cm |
| IMU x3 / x10 / x30 | 5.2 / 4.9 / 12.6 cm | 5.3 / 3.0 / 6.3 cm | <= 1.04 / <= 1.07 cm |
| LiDAR gone 2 s | 5.0 cm (max 10.3) | 3.4 cm (max 6.7) | |
| LiDAR gone 5 s | 13.6 cm (max 1.2 m) | 18.6 cm (max 1.3 m) | |
| camera black 5 s | (no camera) | 3.4 cm (max 6.7) | |

- **Where the SLAM method sees structure, the loop works.** PX4 flies within 3-27 cm of where it
  believes it is, with both methods, missions complete, apart from the cases below.
  - SLAM accuracy in the loop stays within 2x of the open-loop replay in 27 of the 35 completed
    cells.
  - Of the other 8, four are FAST-LIVO2 cells where PX4 still stayed within 3-6 cm: room_plain
    0.72 against 0.30 cm, 30 m 2.2 against 0.39 cm, IMU x3 5.1 against 0.9 cm, IMU x30 8.4 against
    1.1 cm.
  - FAST-LIO2 at 8 m/s: 1.85 against 0.35 cm, with PX4 at 12.9 cm.
  - The rest are FAST-LIO2's weak cases, next.
- **Where it does not, closing the loop makes the SLAM error the vehicle's error, and larger.**
  - FAST-LIO2 drifts along the corridor: 1.43 m in the loop against 0.29 m open loop.
  - At 40 m it reaches 17.5 cm against 1.65 cm, and at 60 m 94 cm against 46 cm.
  - The likely reason: on ground truth the path is fixed; in the loop it follows SLAM's error,
    which feeds back into what the LiDAR sees. These are single flights, not proven.
  - In the open field PX4 believed it flew the figure-8 while the vehicle wandered up to 16 m
    away; it landed elsewhere, mission "complete". No check inside PX4 can see this, because SLAM
    is its only source.
- **A diverging SLAM is followed, not rejected.**
  - At 50 m FAST-LIVO2 diverged two legs into the square. EKF2 accepted the smoothly diverging
    pose, and PX4 flew the vehicle onto a building roof about 25 m up, where it stayed, armed,
    believing it was kilometres away.
  - At 60 m (2 of 2 flights) it flew about 300 m sideways in 30 s and came down 412 m from
    take-off. PX4's failsafe (ALTCTL) engaged only about 28 s after the divergence.
  - Innovation gating rejects jumps, not a self-consistent drift.
  - In open loop FAST-LIVO2 held 4.9 cm at 50 m and diverged only at 60 m: in the loop it went
    one altitude level lower.
- **LiDAR outages trigger PX4's failsafe at EKF2's no-aiding timeout (5 s).**
  - A 2 s outage passes: PX4 dead-reckons on its IMU, with 7-10 cm at most and no mode change.
  - A 5 s outage ends with PX4 switching to ALTCTL just as the pose stream returns. With no RC
    in SITL, the vehicle fell about 1.3 m to the floor within about 1 s, with both methods. It
    then climbed back when OFFBOARD resumed and finished the mission.
  - On the real airframe a safety pilot holds the sticks in ALTCTL. Without one, losing SLAM for
    5 s at low height is a hard landing.
- **A camera blackout does not matter to FAST-LIVO2:** the LiDAR carries it, with a 0.1 s pose
  gap.
- **Landing events with FAST-LIVO2.**
  - In 2 of its 6 delay-tuning flights, at touchdown the IMU artefact (Results, Landing) drove
    EKF2's height away fast enough that EKF2 **rejected** the correct SLAM height (41/60 and
    35/60 updates). Its estimate ran off by 4.9 and 3.6 m.
  - Once (40 ms) PX4, in AUTO.LAND, believing it was below the floor, climbed the vehicle back up
    to 2 m before EKF2 reset, landed and disarmed.
  - In none of FAST-LIO2's logged flights was the vision height rejected. FAST-LIVO2's ~0.1 s
    older poses make the rejection more likely.
  - The trigger is the simulator's touchdown artefact, but "estimate runs off, vision rejected,
    vehicle relaunches during landing" is worth knowing on hardware.
- **The harness itself.**
  - `gzserver` segfaulted while loading the urban world in 2 of about 30 second boots. The matrix
    retried and both flights then flew; `sim_ev.sh` now retries a boot itself.
  - One FAST-LIVO2 60 m flight was set aside unscored because of a parser bug (MAVROS reports an
    empty mode name after the crash). It was scored afterwards: it diverged the same way.

### What the matrix adds to Stage 4
- Stage 4 ranked SLAM accuracy; the closed loop shows **which failures are survivable**.
- FAST-LIO2's degenerate cases (corridor, field, 60 m) become flights that complete with the
  vehicle metres from where it believes it is: dangerous, but not visible to PX4.
- FAST-LIVO2 avoids those, but its divergence at 50-60 m becomes a fly-away.
- Both need a pilot, or a second source, behind the 5 s failsafe.
- A real deployment needs:
  - an independent consistency check of the SLAM pose, so that a divergence ends the flight;
  - RC and a safety pilot for the failsafe;
  - the delay (EV_DELAY) measured end to end on the airframe.

## Threats to validity

- **Simulation flatters SLAM.** There is no LiDAR motion distortion and no vibration, and
  the camera is not used at all. The IMU noise is the EuRoC-grade model added live. The room
  is small and structured: FAST-LIO2's best case (Stage 4: 0.7 cm).
- **One environment, one speed (1 m/s), FAST-LIO2 only.** FAST-LIVO2 can be swapped in the
  same way (guide); Stage 4 says it has the least compute headroom and diverged at 60 m.
  Flying it, or flying FAST-LIO2 where Stage 4 saw it fail (open field, corridor), is the
  obvious next test of the loop rather than of the plumbing.
- **PX4 SITL in lockstep** with Gazebo: the timing of the real Pixhawk link (serial,
  timesync, EV delay) is not represented. EKF2_EV_DELAY = 0 is a simulation result. Stage 7
  tunes it from flight logs, as the guide says.
- **The verdict on the hover's look** is the user's to make, by watching a flight.
- **Extension: one flight per cell.** The matrix tests the loop; it does not give spread. The
  FAST-LIVO2 60 m and the delay results were repeated or swept; the others were not.
- **IMU grade only reaches the SLAM method.** The injected noise degrades the Livox IMU that
  FAST-LIO2 / FAST-LIVO2 use, not PX4's own simulated IMU that EKF2 fuses.
- **No RC in SITL.** PX4's failsafe behaviour after a 5 s SLAM outage (ALTCTL, then a fall to the
  floor) depends on that; with a safety pilot the sticks would hold altitude.

## Verification (`scripts/stage5/verify_stage5.sh`)

The script writes only `output/verify_stage5/`. Its steps:
1. the code parses, and both host-network services exist;
2. the offline frame check;
3. every flight: parameters, reboot, mission complete;
4. every flight re-scored from its bag (and its PX4 log), with every number equal;
5. tables and figures regenerated, pixel-identical;
6. the gate from the numbers, including the hover growth test and the touchdown explanation;
7. with `FLY=1`, a new closed-loop flight, scored and gated the same way. With `GUI=true`,
   Gazebo is open, its view follows the drone, and pictures of its window are kept in
   `output/stage5/verify_pictures/<date_time>/`.
8. with `MATRIX=1`: every cell of the closed-loop matrix flown and scored; every matrix flight
   re-scored from its bag, every number equal; `matrix_tables.md` regenerated identically.

Last full run, 18 Nov 14:15-14:32, on the final code (`FLY=1 MATRIX=1 GUI=true RVIZ=false`):
**all 8 steps passed**.
- All 51 closed-loop flights (8 results set, 18 FAST-LIO2 and 25 FAST-LIVO2 matrix flights)
  re-scored identically, and the tables and figures were identical.
- The gate passed for the results set, including the hover growth test and the touchdown
  explanation.
- The new watched flight passed: PX4 vs truth 5.1 cm in flight, PX4 APE 2.4x FAST-LIO2's, 15
  pictures in `verify_pictures/20261118_1421/`.
- Every matrix cell present.

Final cross-verification of Stages 1-5, 18 Nov 22:22-22:41 (`GZ_VIEW=room FLY=1 MATRIX=1 GUI=true
RVIZ=false`, after the 30 Hz arming-loop fix of Stage 3 deviation 15): **all 8 steps passed** again.
- The new flight: PX4 vs truth 3.0 cm in flight, PX4 APE 2.7x FAST-LIO2's, follows SLAM with
  0.00 s lag; pictures (Gazebo's view fixed in a corner of the room) in
  `verify_pictures/20261118_2228/`.
- Two more flights of matrix cells (`output/final_verification/stage5/`): FAST-LIO2 over the city at
  20 m, complete, PX4 vs truth 5.5 cm (18 Nov: 9.0 cm); FAST-LIVO2 in the room (EV_DELAY 150 ms),
  complete, 2.9 cm in flight (18 Nov: 4.4 cm), but its landing repeated the event below
  ("Landing events with FAST-LIVO2"): vision height rejected in 44 of 60 updates after touchdown,
  and PX4 in AUTO.LAND climbed the vehicle back up to 4.2 m before it landed and disarmed.

## Hand-over to Stage 6 / 7

- `config/px4/ev_only.params` is the configuration the real Pixhawk flies (guide). It needs no
  change from Stage 5, except that EV_DELAY must be measured on hardware.
- Re-check on hardware: accelerometer clipping at touchdown, and MAVROS's time
  synchronisation.
- With FAST-LIVO2:
  - keep the remap of its own MAVROS pose (`fastlivo2.launch`);
  - measure EKF2_EV_DELAY end to end (150 ms in this simulation);
  - do not fly above ~40 m on it alone (it diverged at 50-60 m).
- A divergence is followed, not rejected: add an independent consistency check of the SLAM pose
  (for example against GNSS when available) that ends the flight, and fly with RC and a safety
  pilot, because the 5 s failsafe hands over to altitude control.
- `slam_to_px4.py` uses the mount from `config/generated/mount.yaml`. The real mount must be
  measured (Stage 7 calibration) before the first closed-loop flight, and the offline frame
  check repeated with a hand-carried walk.
