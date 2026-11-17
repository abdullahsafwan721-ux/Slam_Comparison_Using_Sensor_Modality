# Stage 4 log -- experiments that become results

Implements Stage 4 of `eVTOL-SLAM-Complete-Project-Guide.pdf` (groups A-D) plus the
additions agreed in `docs/eVTOL_SLAM_Research_and_Stage3-5_Plan.pdf` (Part 5): sensor faults
(group E), real-time headroom, and figures beyond the guide's sweeps. Scoring follows the
decisions accepted in Stage 3 (D1 coverage and D3 APE over the flight window, D2 ORB-SLAM3
frames; landing gear 0.22 m; 0.4 m hop in every flight).

Gate (guide 4): every cell of the matrix filled with >= 3 runs, figures generated, every
result either explained or flagged. **Status: passed (17 Nov 2026)** -- every cell of groups A-E has 3 runs per affected method, the headroom test has 3 runs per rate, all figures are generated and looked at, and every result is explained except three that are flagged: FAST-LIVO2's non-monotonic camera-offset result (+20 ms better than +10 ms), the mechanism of FAST-LIVO2's divergence at 60 m, and its slightly lower error on 10 %-brightness images.

Started 2026-11-17 on the Stage 3 commit `a92c819`, same images (no rebuild).

## How to reproduce

```bash
# host, project root. Groups can run at the same time (flights are locked per name).
ONLY=environments bash scripts/stage4/run_matrix.sh
ONLY=altitude     bash scripts/stage4/run_matrix.sh      # or ALTS="20 50" ... in several streams
ONLY=speed        bash scripts/stage4/run_matrix.sh
ONLY=imu          bash scripts/stage4/run_matrix.sh
# group E: nine degraded copies of the room flight, then the affected algorithms
for v in cam_black_5s cam_dim30 cam_dim10 lidar_drop_2s lidar_drop_5s lidar_thin25 cam_dt5 cam_dt10 cam_dt20; do
  docker compose run --rm -T eval bash /scripts/common/ros_python.sh /scripts/stage4/degrade_bag.py \
      /output/stage4/flights/room.bag /output/stage4/faults/flights/room_$v.bag $v; done
ONLY=faults   bash scripts/stage4/run_extras.sh
ONLY=headroom bash scripts/stage4/run_extras.sh            # alone: it measures spare compute
# figures and tables
docker compose run --rm -T sim bash -c "source /scripts/common/sim_env.sh && python3 /scripts/stage4/ground_points.py \
    /output/stage4/altitude/ground_points.csv /output/stage4/flights/urban_alt{10,20,30,40,50,60}.bag"
docker compose run --rm -T eval python3 /scripts/stage4/plot_sweeps.py /output/stage4
python3 scripts/stage4/stage4_figures.py output/stage4
```

| File | Origin | Role |
|---|---|---|
| `scripts/stage4/run_matrix.sh` | guide 4.2, **adapted** | groups A-D: fly once, gate, 3 runs per algorithm |
| `scripts/stage4/plot_sweeps.py` | guide 4.3, **extended** | the guide's figure (`fig_<group>_guide.png`) plus the flight-window figure (`fig_<group>.png`) |
| `scripts/stage4/degrade_bag.py` | **new** (plan 5.5a) | one sensor fault per copy of the room flight |
| `scripts/stage4/run_extras.sh` | **new** (plan 5.5a, b) | fault runs; replay at 2x/4x/8x |
| `scripts/stage4/ground_points.py` | **new** (plan 5.3) | measured ground returns per scan against the scan-pattern prediction |
| `scripts/stage4/stage4_figures.py` | **new** (plan 5.3) | scorecard, fault timelines, altitude, cost; `stage4_tables.md` |
| `scripts/stage4/imu_windows.py` | **new** | diagnostic: where a bag's IMU stops integrating to the ground truth |
| `scripts/stage2/verify_sim_bag.py` | changed | `--flight` leaves the landing impact out of the IMU check, reports it |
| `scripts/common/metrics_extra.py` | changed | TSR on the flight-window alignment; `e_3d_flight` in `_errors.csv` |
| `scripts/stage3/run_all_algos.sh` | extended | `RATE=` replay rate for the headroom test; empty-output fallback fixed (deviation 13) |
| `scripts/stage3/offboard_mission.py` | changed | the hop waits for the measured hop height (deviation 12); `--hop-alt` option, default cruise altitude (deviation 10) |

## Design as run

| Group | Flight | Spawn | What varies | TSR tau |
|---|---|---|---|---|
| A environments | room, room_plain: square 4 m x 3 laps, 1.5 m, 1.5 m/s | (-2.0, -1.8) | what the sensors can see | 0.25 m |
| | corridor: line 60 m x 2 laps, 1.5 m, 2 m/s | origin | | 0.25 m |
| | field: figure-8 15 m x 2 laps, 5 m, 3 m/s | origin | | 1.0 m |
| B altitude | urban: square 30 m x 2 laps at 10, 20, 30, 40, 50, 60 m, 4 m/s | (-15, -15) | height above ground | 1.0 m |
| C speed | urban: figure-8 20 m x 2 laps at 20 m, 2 / 5 / 8 m/s, yaw along the path | origin | aggressiveness | 1.0 m |
| D IMU grade | urban_speed5 with x1, x3, x10, x30 the baseline noise | -- | only the IMU | 1.0 m |
| E faults | room with one sensor degraded (9 variants) | -- | one sensor | 0.25 m |
| headroom | room and urban_speed5 replayed at 2x, 4x, 8x (FAST-LIO2, FAST-LIVO2) | -- | compute | -- |

Every flight includes the 0.4 m hop after the climb; every flight passed `check_clearance.py`
and `verify_sim_bag.py --flight` before any algorithm saw it (`output/stage4/flights/*.gate.txt`).
Each algorithm keeps its default tuning in every condition, ORB-SLAM3's settings included
(they keep the baseline IMU noise at every IMU level): the matrix measures robustness, not
re-tuning skill (guide 4.1).

## Hypotheses, written before the runs (plan 3.6, 16 Nov; unchanged)

| Condition | Expected |
|---|---|
| room | all three track; ORB-SLAM3 most accurate locally |
| room_plain | ORB-SLAM3 degrades or fails (no texture); FAST-LIO2 unaffected; FAST-LIVO2 close to FAST-LIO2 |
| corridor | FAST-LIO2 drifts along the corridor axis; ORB-SLAM3 fine (walls are textured); FAST-LIVO2 best |
| field | LiDAR methods weak horizontally (one plane, sparse posts); vision fine on grass texture |
| altitude | LiDAR methods hold to ~30 m, then depend on buildings; vertical error grows first; FAST-LIVO2's camera may carry it; ORB-SLAM3 degrades with height |
| speed | ORB-SLAM3 suffers most at 8 m/s with fast yaw (no motion blur is simulated: flatters vision) |
| IMU grade | LIO methods degrade gracefully; ORB-SLAM3 initialisation fails first at x10-x30 (its settings assume the baseline noise) |
| camera blackout | ORB-SLAM3 loses track (may start a new map); FAST-LIVO2 continues on LiDAR; FAST-LIO2 unaffected |
| LiDAR dropout | FAST-LIO2 propagates on IMU only and drifts; FAST-LIVO2 continues on vision; ORB-SLAM3 unaffected |

Added on 17 Nov before any Stage 4 result, from the urban geometry (plan 3.5): ground returns
vanish at about 31.5 m, but with the square centred on the plaza, building roofs (8-45 m)
and walls stay within the 40 m range and inside the downward field of view even at 60 m
(nearest building 15 m away horizontally). The LiDAR methods may therefore not lose
structure at all over the urban sweep; the open field is the case with nothing in range.

## Deviations from the guide, and why

| # | Where | Guide | What happens | What we do |
|---|---|---|---|---|
| 1 | `run_matrix.sh` | room flights: 6 m square from the origin | hits boxes (Stage 3, deviation 7) | 4 m square x 3 laps from (-2.0, -1.8), as in Stage 3 |
| 2 | `run_matrix.sh` | urban square 30 m from the origin at every altitude | at 10 and 20 m it passes 0.3 m from a 27 m building (`check_clearance.py`) | spawn (-15, -15): the square is centred on the open plaza, >= 15 m from every building, the same horizontal path at all six altitudes |
| 3 | `run_matrix.sh` | room flown again | it is the Stage 3 gate flight, same command | linked (`flights/room.bag`), not flown again |
| 4 | `run_matrix.sh` | flights go straight to the algorithms | -- | every new bag must pass `verify_sim_bag.py --flight` first; failures are kept and reported |
| 5 | `verify_sim_bag.py` | (Stage 3 check) IMU integrates to ground-truth velocity over the whole bag | correct flights failed on the landing alone: Gazebo's IMU reports the instantaneous acceleration every 5 ms, the contact impulse of a touch-down lasts a few 1 ms physics steps and falls between samples (0.47 m/s in room_plain, 0.70 m/s in urban_speed5 where the vehicle bounced; every airborne window agrees to < 0.02 m/s) | the landing (first contact to 1 s after the last) is reported on its own line and left out of the check; it lies outside the flight window every metric uses |
| 6 | flights | -- | flights recorded while the machine was busy failed the gate's LiDAR check: single scans 10-13 ms late (the next one early), scattered through the flight -- with four simulators at once (field, urban 20/30/40 m: 7-15 slips, 79-124 ms), and once with one simulator but seven algorithm runs (urban 40 m: 5 slips in flight, 88-112 ms). Gazebo's sensors update in their own thread; under CPU load an update starts late in simulation time | flights recorded one simulator at a time (lock in `run_matrix.sh`); a failed flight is kept (`flights/<name>_try<time>/`) and flown again, the last ones after the algorithm runs had drained. Load logged in `logs/load.log` |
| 6b | `verify_sim_bag.py` | (Stage 3 check) every LiDAR interval 90-110 ms over the whole bag | the solo 20 m flight failed on ONE scan 13 ms late while PX4 and MAVROS started up on the ground, 9 s before take-off | 90-110 ms inside the flight window; anywhere in the bag no dropped or duplicated scan (50-150 ms). All flights recorded under load still fail it |
| 7 | `metrics_extra.py` | -- | TSR used the whole-trajectory alignment, the flight APE (D3) the flight-window one: a run's post-landing drift could lower its in-flight TSR | TSR on the flight-window alignment, the old value kept as `tsr_whole_align`; Stage 3 and 4 re-scored (no Stage 3 value changed) |
| 8 | `run_matrix.sh` | groups run one after another | ~9 h | groups (and the altitude sweep) run as parallel streams; flights are locked per name so a shared flight (urban_speed5) is flown once; conditions that are complete are skipped on a re-run. The headroom test runs alone |
| 9 | `plot_sweeps.py` | whole-bag APE and coverage | with D1/D3 the headline is the flight window | both figures: `fig_<group>_guide.png` (guide) and `fig_<group>.png` (flight window, + vertical APE and drift) |

| 10 | `offboard_mission.py` | (Stage 3 protocol) the 0.4 m hop after the climb, at cruise altitude | in the first urban flights ORB-SLAM3 started only at the hop: no poses for the whole climb (start-up 19.4 s at 20 m), and at 10 m the first map failed before its inertial initialisation (3 of 3 runs empty) | **tried and withdrawn.** `--hop-alt 1.5` (hop on the way up at 1.5 m) made it worse: ORB-SLAM3 never started at 10 and 20 m and started only at the end of the square at 30-60 m (coverage 0.20-0.26). Two causes, both checked: (a) the hop was never flown -- see 12; (b) with a real hop at 1.9 m over the plaza (test flight `diag/hoptest/`) the jerk criterion is met (consecutive-frame mean-acceleration change >= 0.5 m/s^2 at the hop) but the downward-looking camera sees dark, uniform paving: ~320 ORB features (OpenCV ORB, ORB-SLAM3's settings), below ORB-SLAM3's 500, so "not enough acceleration" is never the blocker there -- the image is. At cruise height the buildings are in view (600-1200). The hop is back at cruise altitude (Stage 3 protocol, the default again); field and the nine urban flights were flown again with 12. Kept: `superseded_hop_at_cruise/` (first set, open-loop hop at cruise, incomplete) and `superseded_hop_at_liftoff/` (complete set with the 1.5 m hop) |
| 11 | `run_extras.sh` | -- | each fault changes one sensor's data; the other methods would see identical bytes | a fault runs only the methods it affects (camera: FAST-LIVO2, ORB-SLAM3; LiDAR: FAST-LIO2, FAST-LIVO2); the clean room run is the control |
| 12 | `offboard_mission.py` | -- | PX4 lifts off ~3 s after arming. The hop was timed from arming, so at 1.5 m it fell inside the take-off transient: the ground truth of room and urban flights shows no step (room: 0.12 m bump; urban: the climb simply went on) | the hop starts 3 s after the measured height (`/mavros/local_position/pose`) first reaches hop height - 0.05 m, and the vehicle gets 3 s to settle back. Room, room_plain, corridor and the faults were not flown again: there ORB-SLAM3 initialised during the take-off itself (start-up 0.7-1.8 s), which is what the hop is for. Field and urban flights use the fixed hop |
| 13 | `run_all_algos.sh` | -- | the first FAST-LIO2 run with no output (headroom 4x, room r3) aborted the batch: `bag_to_tum.py` runs as root in its container and creates the output file before it finds the topic empty; the host's fallback `: > file` then hit "Permission denied" and `set -e` stopped everything (the exit trap's chown hid the cause) | the fallback leaves an existing (empty) file alone, so the run is scored as failed and the batch goes on. The failed 4x set is kept in `headroom_rate4_failed_1757/`. Also: /home ran full at that point; with the user's approval the noise-injected input copies (`bags/*.bag`, regenerable from the kept flights with the fixed seed) of both superseded sets were deleted (55 GB) |

## Results

Numbers: flight-window APE RMSE (D3), mean of 3 runs; per-run values in
`output/stage4/<group>/eval/`, all tables in `output/stage4/stage4_tables.md`. Runs of the
same bag were identical to the last digit for FAST-LIO2 and FAST-LIVO2 in most conditions
(deterministic replay); ORB-SLAM3 varies run to run (multi-threaded).

### B. Altitude (urban square, 4 m/s; `fig_altitude.png`)

| Altitude | FAST-LIO2 | FAST-LIVO2 | ORB-SLAM3 (coverage) |
|---|---|---|---|
| 10 m | 1.1 cm | 0.4 cm | **never starts** (3/3) |
| 20 m | 0.5 cm | 0.3 cm | 15.5 cm (0.76) |
| 30 m | 0.6 cm | 0.3 cm | 11.8 cm (0.72) |
| 40 m | 0.9 cm | 0.9 cm | 18.1 cm (0.69) |
| 50 m | 3.5 cm | 4.7 cm | 18.4 cm (0.62) |
| 60 m | 46 cm | **diverges** (137 m; 3/3) | 20.3 cm (0.62) |

Hypothesis largely right for the LiDAR methods, with a twist. Both are flat to 30 m, then
degrade, **vertical error first** (FAST-LIO2 vertical 0.1 cm at 10 m, 4.3 cm at 50 m) as
the ground returns vanish (measured: ~11 000 ground points per scan at 10 m, ~1 000 at
30 m, none from 40 m; `altitude/ground_points.csv`); from 40 m only roofs and walls are in
range. "FAST-LIVO2's camera may carry it" is wrong at the top: at 60 m FAST-LIVO2 tracks the
climb and the hop, then diverges ~40 s into the square in all three runs (km-scale), while
FAST-LIO2 on the same scans holds 46 cm. With few LiDAR points the photometric update
dominates and pulls the state away; we did not isolate the mechanism further (flagged).
ORB-SLAM3 needs the hop to start (start-up = time of the hop: 23 s at 20 m to 63 s at
60 m, hence coverage 0.62-0.76) and then holds 12-20 cm with no clear trend in height. At
10 m it builds a map at the hop, the map is reset before its inertial initialisation, and
no later jerk restarts it (the same in the first, superseded set). Its error barely grows
with height because what it tracks (rooftops and walls 10-50 m away) does not change much.

### C. Speed (figure-8 at 20 m, yaw along the path; `fig_speed.png`)

| Speed | FAST-LIO2 | FAST-LIVO2 | ORB-SLAM3 |
|---|---|---|---|
| 2 m/s | 0.4 cm | 0.3 cm | 8.8 cm |
| 5 m/s | 0.5 cm | 0.9 cm | 6.7 cm |
| 8 m/s | 0.4 cm | 0.9 cm | 5.6 cm |

Hypothesis wrong: ORB-SLAM3 does not suffer at 8 m/s; it gets *better* (more parallax per
frame, no motion blur in the simulation -- the threat the hypothesis already named).
FAST-LIO2 is flat. FAST-LIVO2 is the only method that degrades with speed (3x from 2 to
5 m/s), consistent with its sensitivity to camera timing (group E): at higher speed the
same residual timing error is a larger displacement. Up to 8 m/s, speed alone is not a
stressor in this simulation; motion blur and rolling shutter would be (Phase 2).

### D. IMU grade (urban_speed5 with x1-x30 the baseline noise; `fig_imu.png`)

| IMU noise | FAST-LIO2 | FAST-LIVO2 | ORB-SLAM3 |
|---|---|---|---|
| x1 | 0.5 cm | 0.9 cm | 7.8 cm |
| x3 | 0.8 cm | 0.9 cm | 9.8 cm |
| x10 | 0.7 cm | 0.9 cm | 14.7 cm |
| x30 | 1.0 cm | 1.1 cm | **diverges** (88 m, 3/3) |

Hypothesis right. The LiDAR methods barely notice a 30x worse IMU (2x at most); ORB-SLAM3
degrades steadily and fails at x30. A side effect explains its start-up times: the
"enough acceleration" test (>= 0.5 m/s^2 between frames) is passed by noise alone at x10
(start-up 15 s, before the hop) and on the ground at x30 (1 s), where it initialises from a
stationary, noise-driven solution and never recovers. Its settings keep the baseline
noise at every level, as planned (guide 4.1).

### A. Environments (outdoor field, figure-8 at 5 m)

FAST-LIO2 fails (5.8 m APE, drift 11 %): flat ground plus a few posts leave the horizontal
position unconstrained, as predicted. FAST-LIVO2's camera fixes it (2.6 cm). ORB-SLAM3
fails, against the hypothesis "vision fine on grass": it starts at the hop and then resets
its map 131 times ("Not enough motion for initializing", LocalMapping) -- coverage 0.31,
9 m error.

### E. Sensor faults (room flight; control = clean room: FAST-LIO2 0.70 cm, FAST-LIVO2 0.29, ORB-SLAM3 0.60)

| Fault | FAST-LIO2 | FAST-LIVO2 | ORB-SLAM3 |
|---|---|---|---|
| camera black 5 s | (same data) | 0.27 cm, coverage 1.00 | loses track, **never restarts**: coverage 0.54, 4.3 cm over what it tracked |
| camera 30 % brightness | (same data) | 0.27 cm | **3/3 runs never initialise** |
| camera 10 % brightness | (same data) | 0.22 cm | **3/3 runs never initialise** |
| camera stamps +5 ms | (same data) | 0.80 cm (2.7x) | 0.64 cm (1.1x) |
| camera stamps +10 ms | (same data) | 1.87 cm (6.4x) | 0.90 cm (1.5x) |
| camera stamps +20 ms | (same data) | 0.35 cm (1.2x) -- **flagged**, see below | 1.53 cm (2.6x) |
| LiDAR gone 2 s | 0.66 cm, coverage 0.95 | 0.30 cm, coverage 0.95 | (same data) |
| LiDAR gone 5 s | 0.61 cm, coverage 0.88 | 0.35 cm, coverage 0.88 | (same data) |
| LiDAR 25 % of points | 0.94 cm (1.3x) | 0.58 cm (2.0x) | (same data) |

- **Camera blackout**: as predicted ORB-SLAM3 loses track, but it does not start a new map:
  after RECENTLY_LOST it needs a new stereo-inertial initialisation, and that needs the
  "enough acceleration" jerk again (311 "not enough acceleration" lines after the blackout;
  smooth flight never provides it). FAST-LIVO2 is unaffected (LiDAR carries it).
- **Dim images**: ORB-SLAM3 never initialises at 30 % or 10 % brightness. Contrast scales
  with brightness against FAST's fixed thresholds (20, then 7 grey levels): ORB features per
  frame (OpenCV ORB, ORB-SLAM3's settings, 10 frames sampled) fall from 1200 (clean) to
  3-1157 (30 %, often < 500) and 0-277 (10 %); initialisation needs > 500 at the moment of a
  jerk (the take-off). FAST-LIVO2 is unaffected (0.27, 0.22 cm). Its exposure estimation
  is off in our config; every image is dimmed alike, so the map's reference patches are dim
  too and the photometric residuals stay consistent, and the LiDAR carries the geometry.
  The slightly lower error at 10 % fits a smaller visual weight (smaller residuals), not
  verified.
- **LiDAR dropout**: both LiDAR methods **stop publishing** for the length of the gap (max gap
  2.1 s and 5.1 s) and resume with no loss of accuracy (`figures/faults_timeline.png`;
  FAST-LIVO2's first pose after the 5 s gap is 4 cm off and back to normal one scan later). FAST-LIO2 does not output IMU-only
  poses, and FAST-LIVO2 does **not** continue on vision: its measurement packages are built
  around LiDAR scans, so without scans no image is processed either. The hypothesis
  ("FAST-LIO2 drifts on IMU, FAST-LIVO2 continues on vision") is wrong on both counts; the
  room map is good enough to re-register the first scan after the gap.
- **Time offset**: FAST-LIVO2 is the most sensitive (its photometric update uses the image at
  its stamp to correct a state propagated to that stamp), ORB-SLAM3 degrades smoothly. The
  +20 ms result for FAST-LIVO2 is non-monotonic (better than +10 ms) and identical in all
  three runs; not explained. Candidate: how shifted image stamps interleave with the
  100 ms scans (FAST-LIVO2 splits each scan at image times; a 20 ms shift and a 10 ms shift
  put the split at different points of the 50 ms image period). A finer sweep (0-50 ms in
  5 ms steps) would settle it; listed as open.

### Real-time headroom (replay at 2x, 4x, 8x; nothing else running; `headroom/rate<r>/`)

| Replay | FAST-LIO2 room / urban_speed5 | FAST-LIVO2 room / urban_speed5 |
|---|---|---|
| 1x (matrix) | 0.70 / 0.53 cm; CPU 0.15 / 0.24 cores; pose age p95 8 / 11 ms | 0.29 / 0.91 cm; CPU 0.69 / 0.70; 84 / 113 ms |
| 2x | unchanged; CPU 0.26 / 0.45; 11 / 18 ms | unchanged; CPU 0.85 / 1.19; 86 / 124 ms |
| 4x | unchanged; CPU 0.41 / 0.71; 17 / 29 ms | unchanged; CPU 1.42 / 1.88; 107 / **262 ms** |
| 8x | unchanged; CPU 0.60 / 1.06; 28 / 51 ms | room unchanged but output **7.9 s late**; urban: coverage **0.48**, 1.03 cm |

FAST-LIO2 keeps up at 8x with about one core; its headroom on this workstation is > 8x.
FAST-LIVO2 keeps up at 2x, queues at 4x and falls behind at 8x: headroom 2-4x on the
workstation, so on a Jetson-class computer (several times slower per core) it may have
none -- Stage 6's question. ORB-SLAM3's headroom comes from its tracking time (Stage 3:
p95 12.4 ms per 50 ms frame, 4.0x). The first 4x attempt aborted on a harness fault, not
on load (deviation 13); in the re-run every FAST-LIO2 run produced output.

### What the matrix says, in one paragraph

No method wins everywhere. FAST-LIVO2 is the most accurate wherever both its sensors see
structure (room, corridor, field, urban to 30 m) and the only one that survives the open
field and the corridor, but it is the most sensitive to camera timing, the only one that
degrades with speed, it diverged at 60 m where FAST-LIO2 held, and it has the least
compute headroom. FAST-LIO2 is the cheapest and the most robust to IMU grade, speed and
height, but fails where the LiDAR geometry is degenerate (open field; drifts along the
corridor). ORB-SLAM3 is competitive only indoors; it depends on an initialisation
manoeuvre with enough texture in view, does not recover from losing track in smooth
flight, fails on dim images, repetitive texture and noisy IMUs. Losing a LiDAR for up to
5 s costs neither LiDAR method accuracy in a known room, but both stop publishing.

### A. Environments (indoor)

| Condition | FAST-LIO2 | FAST-LIVO2 | ORB-SLAM3 |
|---|---|---|---|
| room | 0.70 cm | 0.29 cm | 0.60 cm (coverage 0.98) |
| room_plain | 0.75 cm | 0.30 cm | 0.73 cm (coverage 0.96) |
| corridor (60 m line) | 28.6 cm, drift 1.5 % | 7.5 cm, drift 0.3 % | **12.5 m**, drift 21 % |

- **room_plain**: hypothesis wrong -- ORB-SLAM3 still tracks (0.73 cm). The world removes the
  wall and box textures but not the lit edges and corners of the boxes; that is enough for
  ORB features at 1-3 m. A truly feature-poor room needs uniform lighting as well (Stage 6
  candidate).
- **corridor**: FAST-LIO2 drifts **along the corridor axis** as predicted (RMS error x 36.5 cm,
  y 0.4 cm, z 16.8 cm: the walls fix y, nothing fixes x). FAST-LIVO2's camera fixes it
  (x 7.4 cm). ORB-SLAM3 fails, against the hypothesis: the floor texture is stretched into
  streaks along the direction of flight, and the walls repeat one tile pattern; per run
  236-392 loop candidates were rejected ("BAD LOOP") and 4 new maps started -- perceptual
  aliasing. Coverage stays 0.99, so tracking "succeeds" while the map is wrong: the TSR
  (0.00) catches it, coverage alone does not.

## Threats to validity (guide 4.5, plus what Stages 3-4 found)

- No intra-scan LiDAR motion: simulated scans are instantaneous, so motion de-skewing is
  never exercised.
- Perfect synchronisation: one clock, zero offsets (the `cam_dt` faults probe the price of
  an offset).
- Idealised camera: no motion blur, rolling shutter, auto-exposure or distortion; textures
  stretched over large surfaces.
- Idealised LiDAR returns: no multipath, no reflectivity-dependent range, Gaussian noise only.
- IMU: white noise + random walk only; no temperature drift or vibration. The simulated IMU
  also point-samples the acceleration, so landing impacts alias (deviation 5).
- Default tuning everywhere: robustness, not best achievable accuracy.
- Workstation compute, parallel streams: cost numbers are relative (checked against the
  serial Stage 3 runs of the same flight); the Jetson is Phase 2.
- On the ground the cameras are 0.12 m above the floor (Stage 3, Finding 6): ORB-SLAM3's
  error after landing is a property of this set-up.
