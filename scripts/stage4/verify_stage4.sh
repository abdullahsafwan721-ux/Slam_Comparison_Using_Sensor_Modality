#!/usr/bin/env bash
# Stage 4 verification: is every part of Stage 4 there, and does every reported number follow
# from the stored data? HOST, project root:
#   bash scripts/stage4/verify_stage4.sh                  # steps 1-8, ~20 min
#   REPLAY=0 bash scripts/stage4/verify_stage4.sh         # without step 8 (live replay, ~8 min)
#   FLY=1 GUI=true bash scripts/stage4/verify_stage4.sh   # plus step 9: fly room_plain again with
#                                                         # the Gazebo window open, then gate it
#   JOBS=12 ...                                           # runs scored in parallel (default 8)
# Reads output/stage4 and docs/stage4_log.md. Writes ONLY output/verify_stage4/, which is
# deleted at the start of every run. Prints PASS / FAIL / WARN per check and a summary; exit
# code = number of failed steps.
#
#  1 code         the committed Stage 4 code is what is on disk; every script parses
#  2 flights      13 flights recorded, cleared, sensor-gated, hop flown; 9 fault copies present
#  3 matrix       every cell: 3 runs per algorithm, each scored (failed runs recorded as such)
#  4 re-score     all 312 trajectories scored again from scratch (ground truth + trajectory
#                 only) and compared run by run, and cell by cell with the stored summaries
#  5 tables       stage4_tables.md and all 10 figures regenerated from the re-scored runs
#  6 log          every number in docs/stage4_log.md's result tables against the re-scored runs
#  7 rebuild      two fault copies rebuilt from flights/room.bag: byte-identical to the stored ones
#  8 replay       the room flight replayed live through all three algorithms (noise injection,
#                 ground truth, FAST-LIO2, FAST-LIVO2, ORB-SLAM3, scoring) against the stored runs
#  9 fly          (FLY=1) a new PX4 flight of room_plain, then the sensor gate on it
set -o pipefail
[ -f compose.yaml ] || { echo "run from the project root"; exit 1; }
V=output/verify_stage4
C="docker compose run --rm -T"
exec 2> >(grep --line-buffered -v -E "^ Container .* (Creating|Created)" >&2)   # docker's per-container chatter
PY="python3 scripts/stage4/verify_stage4.py"
STEPS_FAILED=()
T0=$(date +%s)
step() { echo; echo "==[$1] $2   ($(date +%T))"; }
result() { [ "$2" -eq 0 ] || STEPS_FAILED+=("$1"); }

echo "Stage 4 verification  $(date -Is)  git $(git rev-parse --short HEAD)  free on /home: $(df -h --output=avail /home | tail -1 | tr -d ' ')"
rm -rf "$V"; mkdir -p "$V"

step 1 "code: committed and parseable"
rc=0
git log -1 --format='  ----  HEAD %h %s (%ad)' --date=short
if git diff --quiet HEAD -- scripts config docs/stage4_log.md compose.yaml; then
  echo "  PASS  scripts/, config/, docs/stage4_log.md, compose.yaml: no uncommitted changes"
else
  echo "  WARN  uncommitted changes in tracked files:"; git diff --stat HEAD -- scripts config docs/stage4_log.md compose.yaml | sed 's/^/          /'
fi
for f in scripts/stage4/*.sh scripts/stage3/run_all_algos.sh scripts/stage3/px4_record.sh; do
  bash -n "$f" || { echo "  FAIL  $f does not parse"; rc=1; }
done
python3 -c "import ast,sys; [ast.parse(open(f).read(), f) for f in sys.argv[1:]]" scripts/stage4/*.py \
    scripts/stage3/offboard_mission.py scripts/common/metrics_extra.py scripts/stage2/verify_sim_bag.py \
  && echo "  PASS  every Stage 4 script (and the changed Stage 2/3 ones) parses" || { echo "  FAIL  a script does not parse"; rc=1; }
result 1 $rc

step 2 "flights and fault copies"
$PY flights; result 2 $?

step 3 "matrix completeness"
$PY matrix; result 3 $?

step 4 "re-score every run from ground truth + trajectory, compare with the stored scores"
$PY prepare "$V"
$C eval bash /scripts/stage4/verify_score.sh "/$V/jobs.txt" "${JOBS:-8}" | grep -v "^   (will retry)"
for d in "$V"/rescore/{environments,altitude,speed,imu,faults,headroom/rate2,headroom/rate4,headroom/rate8}; do
  $C eval python3 /scripts/common/results_table.py "/$d/eval" > /dev/null
done
$PY compare "$V"; result 4 $?

step 5 "tables and figures regenerated from the re-scored runs"
$C eval python3 /scripts/stage4/plot_sweeps.py "/$V/rescore" > /dev/null
python3 -W ignore scripts/stage4/stage4_figures.py "$V/rescore" > /dev/null
$PY tables "$V"; result 5 $?

step 6 "docs/stage4_log.md against the data"
$PY log "$V"; result 6 $?

step 7 "fault copies rebuilt from flights/room.bag"
rc=0
mkdir -p "$V/rebuild"
for v in cam_dt10 lidar_thin25; do
  $C eval bash /scripts/common/ros_python.sh /scripts/stage4/degrade_bag.py /output/stage4/flights/room.bag \
      "/$V/rebuild/room_$v.bag" $v > "$V/rebuild_$v.log" 2>&1
  a=$(md5sum < output/stage4/faults/flights/room_$v.bag | cut -c1-12); b=$(md5sum < "$V/rebuild/room_$v.bag" 2>/dev/null | cut -c1-12)
  if [ "$a" = "$b" ]; then echo "  PASS  room_$v rebuilt: byte-identical (md5 $a...)"
  else echo "  FAIL  room_$v rebuilt: md5 $b..., stored $a... (see $V/rebuild_$v.log)"; rc=1; fi
done
rm -rf "$V/rebuild"                                          # 2.4 GB, only needed for the md5
result 7 $rc

if [ "${REPLAY:-1}" = 1 ]; then
  step 8 "live replay of the room flight through all three algorithms (1 run each)"
  echo "  ----  running scripts/stage3/run_all_algos.sh; its log: $V/replay.log"
  TAU=0.25 bash scripts/stage3/run_all_algos.sh output/stage4/flights/room.bag room "$V/replay" 1 \
      > "$V/replay.log" 2>&1
  grep -E "^== |maps created|APE" "$V/replay.log" | sed 's/^/          /'
  $PY replay "$V"; result 8 $?
  rm -rf "$V"/replay/bags/*.bag "$V"/replay/orbslam3/euroc_*                 # big inputs, rebuildable
fi

if [ "${FLY:-0}" = 1 ]; then
  step 9 "new PX4 flight of room_plain (GUI=${GUI:-false}), then the sensor gate"
  $C -e SPAWN="-2.0 -1.8" -e GUI="${GUI:-false}" sim bash /scripts/stage3/px4_record.sh room_plain square \
      "/$V/fly/room_plain.bag" --size 4 --alt 1.5 --speed 1.5 --laps 3 > "$V/fly.log" 2>&1
  $C sim bash -c "source /scripts/common/sim_env.sh && python3 /scripts/stage2/verify_sim_bag.py /$V/fly/room_plain.bag --flight" \
      > "$V/fly/room_plain.gate.txt" 2>&1
  grep -E "^(PASS|FAIL|ALL)" "$V/fly/room_plain.gate.txt" | sed 's/^/          /'
  grep -q "ALL CHECKS PASSED" "$V/fly/room_plain.gate.txt" \
    && { echo "  PASS  new flight passes the sensor gate"; result 9 0; } \
    || { echo "  FAIL  new flight fails the sensor gate (see $V/fly.log)"; result 9 1; }
fi

$C eval chown -R "$(id -u):$(id -g)" "/$V" > /dev/null 2>&1
echo
echo "== summary ($(( ($(date +%s) - T0) / 60 )) min; details under $V/)"
if [ ${#STEPS_FAILED[@]} -eq 0 ]; then echo "   ALL STEPS PASSED"
else echo "   FAILED steps: ${STEPS_FAILED[*]}"; fi
exit ${#STEPS_FAILED[@]}
