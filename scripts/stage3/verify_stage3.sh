#!/usr/bin/env bash
# Stage 3 verification: every stored Stage 3 result recomputed, the scripted bag replayed again,
# and a NEW PX4 flight flown in Gazebo and put through all three algorithms and the Stage 3 gate.
# HOST, project root, no other simulation running:
#   bash scripts/stage3/verify_stage3.sh               # ~35 min
#   GUI=true bash scripts/stage3/verify_stage3.sh      # the Gazebo window open during the flight
#   RTF=0.35 ...                                       # fly the simulation at 0.35x real time: PX4's own speed
#                                                      # factor (PX4_SIM_SPEED_FACTOR, passed through compose).
#                                                      # Needed when the GPU is busy with other work and Gazebo
#                                                      # drops camera frames at full speed. (PX4's Gazebo plugin
#                                                      # sets the update rate when the drone loads, so the
#                                                      # gazebo_ros route of scripts/tools/sim_rtf.sh is undone)
# Writes only V (default output/final_verification/stage3), replaced on every run.
#  1 code      the Stage 3 scripts parse
#  2 re-score  all 24 stored runs (3a scripted + 3b PX4, 4 trajectories x 3 runs) scored again
#              from ground truth + trajectory, compared run by run and cell by cell
#  3 log       every number of docs/stage3_log.md's 3a and 3b tables against the re-scored runs
#  4 replay    the stored scripted bag through all three algorithms again (1 run each):
#              FAST-LIO2 and FAST-LIVO2 must reproduce their trajectories bit for bit
#  5 fly       a NEW PX4 flight of the Stage 3 mission (room, 4 m square, 3 laps, 1.5 m, 1.5 m/s,
#              with Stage 3's hop schedule: --hop-timing start), then the flight sensor gate
#              (verify_sim_bag.py --flight). Stage 4 later made the hop wait for the measured height
#              (Stage 4 deviation 12), which moves it ~9 s after take-off; the Stage 3 gate flight had it
#              in the lift-off, where ORB-SLAM3 initialises (Stage 3 Finding 9)
#  6 gate      the new flight through all three algorithms (3 runs each) and the Stage 3 gate:
#              every run completes, flight-window coverage >= 0.95, centimetre APE, no method 10x worse
set -o pipefail
[ -f compose.yaml ] || { echo "run from the project root"; exit 1; }
V=${V:-output/final_verification/stage3}
C="docker compose run --rm -T"
PY="python3 scripts/stage3/verify_stage3.py"
FAILED=(); T0=$(date +%s)
step() { echo; echo "==[$1] $2   ($(date +%T))"; }
res() { [ "$2" -eq 0 ] || FAILED+=("$1"); }
exec 2> >(grep --line-buffered -v -E "^ Container .* (Creating|Created)" >&2)
[ -n "${RTF:-}" ] && export PX4_SIM_SPEED_FACTOR=$RTF           # compose passes it to the sim container
echo "Stage 3 verification  $(date -Is)  git $(git rev-parse --short HEAD)  GUI=${GUI:-false}  RTF=${RTF:-1 (real time)}"
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>/dev/null | sed "s/^/  ----  GPU load before the start (utilisation, memory): /"
{ pgrep -x gzserver || pgrep -x rosmaster || pgrep -x gzclient; } >/dev/null && { echo "!! a simulator or ROS master is already running on this host"; exit 1; }
$C eval bash -c "rm -rf /$V" >/dev/null 2>&1; mkdir -p "$V/flights"

step 1 "code"
rc=0
for f in scripts/stage3/*.sh; do bash -n "$f" || { echo "  FAIL  $f does not parse"; rc=1; }; done
python3 -c "import ast,sys; [ast.parse(open(f).read(), f) for f in sys.argv[1:]]" scripts/stage3/*.py scripts/common/*.py \
  && echo "  PASS  every Stage 3 script (and scripts/common) parses" || { echo "  FAIL  a script does not parse"; rc=1; }
res 1 $rc

step 2 "re-score every stored Stage 3 run from ground truth + trajectory"
$PY prepare "$V"
$C eval bash /scripts/stage4/verify_score.sh "/$V/jobs.txt" 8 | grep -v "^   (will retry)"
for g in scripted px4; do $C eval python3 /scripts/common/results_table.py "/$V/rescore/$g/eval" > /dev/null; done
$PY compare "$V"; res 2 $?

step 3 "docs/stage3_log.md against the data"
$PY log "$V"; res 3 $?

step 4 "replay of the stored scripted bag (3a) through all three algorithms, 1 run each"
echo "  ----  scripts/stage3/run_all_algos.sh; log: $V/replay_scripted.log"
TAU=0.25 bash scripts/stage3/run_all_algos.sh output/stage2/scripted_room.bag room "$V/replay_scripted" 1 \
    > "$V/replay_scripted.log" 2>&1
$PY replay "$V"; res 4 $?
$C eval bash -c "rm -rf /$V/replay_scripted/bags/*.bag /$V/replay_scripted/orbslam3/euroc_*" > /dev/null 2>&1

step 5 "a NEW PX4 flight in Gazebo (room, 4 m square, 3 laps), then the flight sensor gate"
N=s3verify_$$
$C --name $N -e SPAWN="-2.0 -1.8" -e GUI="${GUI:-false}" sim bash /scripts/stage3/px4_record.sh room square \
    "/$V/flights/room_square.bag" --size 4 --alt 1.5 --speed 1.5 --laps 3 --hop-timing start > "$V/fly.log" 2>&1 &
FP=$!
if [ "${GUI:-false}" = true ]; then      # pictures of the Gazebo window, view from a corner of the room
  bash scripts/tools/capture_gazebo.sh "$V/flights/shots" $N 6 60 room > "$V/capture.log" 2>&1 &
fi
wait $FP; rc=$?
# the real-time factor actually flown, from the mission log's [wall, sim] stamps (armed -> landed)
python3 - "$V/flights/room_square.mission.log" <<'PY' | sed 's/^/  ----  /'
import re, sys
s = [tuple(map(float, m)) for m in re.findall(r"\[INFO\] \[([\d.]+), ([\d.]+)\]", open(sys.argv[1]).read())]
if len(s) > 1 and s[-1][0] > s[0][0]:
    print("flown at real-time factor %.2f (sim %.1f s in %.1f s wall; PX4_SIM_SPEED_FACTOR=%s)" % (
        (s[-1][1] - s[0][1]) / (s[-1][0] - s[0][0]), s[-1][1] - s[0][1], s[-1][0] - s[0][0], __import__("os").environ.get("PX4_SIM_SPEED_FACTOR", "1")))
PY
grep -E "armed|hop|profile|landed|!!" "$V/flights/room_square.mission.log" 2>/dev/null | sed 's/^/     /'
$C sim bash -c "source /scripts/common/sim_env.sh >/dev/null 2>&1 && python3 /scripts/stage2/verify_sim_bag.py /$V/flights/room_square.bag --flight" \
    > "$V/flights/room_square.gate.txt" 2>&1
grep -E "^(PASS|FAIL|WARN)" "$V/flights/room_square.gate.txt" | sed 's/^/     /'
if [ $rc -eq 0 ] && grep -q "ALL CHECKS PASSED" "$V/flights/room_square.gate.txt"; then
  echo "  PASS  new flight: mission complete, $(grep -c '^PASS' "$V/flights/room_square.gate.txt") flight-gate checks passed"
else
  echo "  FAIL  new flight: mission rc $rc; gate: $(grep -c '^FAIL' "$V/flights/room_square.gate.txt" 2>/dev/null) failed check(s) (see $V/fly.log)"; rc=1
fi
res 5 $rc

step 6 "the new flight through all three algorithms (3 runs each), and the Stage 3 gate"
if [ -s "$V/flights/room_square.bag" ]; then
  echo "  ----  scripts/stage3/run_all_algos.sh; log: $V/px4.log"
  TAU=0.25 bash scripts/stage3/run_all_algos.sh "$V/flights/room_square.bag" room_square "$V/px4" 3 > "$V/px4.log" 2>&1
  grep -E "maps created" "$V/px4.log" | sed 's/^/          /'
  $PY gate "$V"; res 6 $?
  $C eval bash -c "rm -rf /$V/px4/bags/*.bag /$V/px4/orbslam3/euroc_*" > /dev/null 2>&1
else
  echo "  FAIL  no flight bag"; res 6 1
fi

$C eval chown -R "$(id -u):$(id -g)" "/$V" >/dev/null 2>&1
if ls "$V"/flights/shots/*.xwd >/dev/null 2>&1; then
  python3 -W ignore scripts/stage5/xwd_to_png.py "$V"/flights/shots/*.xwd >/dev/null 2>&1
  echo; echo "  ----  $(ls "$V"/flights/shots/*.png 2>/dev/null | wc -l) pictures of the Gazebo window in $V/flights/shots/"
fi
echo
echo "== Stage 3 verification finished in $(( ($(date +%s) - T0) / 60 )) min"
if [ ${#FAILED[@]} -eq 0 ]; then echo "== ALL STEPS PASSED"; else echo "== FAILED STEPS: ${FAILED[*]}"; fi
exit ${#FAILED[@]}
