#!/usr/bin/env bash
# Stage 4 additions (not in the project guide; plan PDF section 5.5). HOST, project root:
#   ONLY=faults   bash scripts/stage4/run_extras.sh   # group E: sensor faults on the room flight
#   ONLY=headroom bash scripts/stage4/run_extras.sh   # replay at 2x, 4x, 8x (run it ALONE: it
#                                                     # measures spare compute)
#
# faults: degrade_bag.py has written output/stage4/faults/flights/room_<variant>.bag from the
#   room flight (output/stage4/flights/room.bag). Each variant runs only the algorithms
#   whose input it changes; the unchanged ones would see identical bytes:
#     camera faults -> FAST-LIVO2, ORB-SLAM3 (FAST-LIO2 = the control: environments/room)
#     LiDAR faults  -> FAST-LIO2, FAST-LIVO2 (ORB-SLAM3 = the control)
#   The clean baseline of every variant is output/stage4/environments, condition room.
# headroom: FAST-LIO2 and FAST-LIVO2 on the room flight and on urban_speed5 at replay rates
#   2, 4, 8; the 1x result is environments/room and speed/urban_speed5. Headroom = the
#   fastest rate that keeps flight coverage >= 0.95 and flight APE within 1.5x of 1x.
#   ORB-SLAM3's headroom comes from its tracking time (scripts/stage3/orbslam3_timing.sh).
set -o pipefail
[ -f compose.yaml ] || { echo "run from the project root"; exit 1; }
RUNS=${RUNS:-3}
OUT=output/stage4
mkdir -p $OUT/logs
FAILED=()
want() { [ -z "${ONLY:-}" ] || [ "$ONLY" = "$1" ]; }

run() {   # run <bag> <cond> <outdir> <algos> <tau> [rate]
  local done=$3/.done_$2
  if [ -e "$done" ] && [ -z "${FORCE:-}" ]; then echo "== $2 ($3): complete, skipped"; return 0; fi
  [ -s "$1" ] || { echo "!! $1 missing"; FAILED+=("$2: no bag"); return 1; }
  echo "== $(date +%T) $2 -> $3 ($4, rate ${6:-1.0})"
  ALGOS="$4" TAU=$5 RATE=${6:-1.0} bash scripts/stage3/run_all_algos.sh "$1" "$2" "$3" "$RUNS" 1.0 \
      > "$OUT/logs/$(basename "$3")__$2.run.log" 2>&1 < /dev/null \
    || { echo "!! $2: failed (see $OUT/logs/$(basename "$3")__$2.run.log)"; FAILED+=("$2: algos"); return 1; }
  date -Is > "$done"
}

if want faults; then
  F=$OUT/faults/flights
  for v in cam_black_5s cam_dim30 cam_dim10 cam_dt5 cam_dt10 cam_dt20; do
    run $F/room_$v.bag room_$v $OUT/faults "fastlivo2 orbslam3" 0.25
  done
  for v in lidar_drop_2s lidar_drop_5s lidar_thin25; do
    run $F/room_$v.bag room_$v $OUT/faults "fastlio2 fastlivo2" 0.25
  done
fi

if want headroom; then
  for r in 2 4 8; do
    run $OUT/flights/room.bag room $OUT/headroom/rate$r "fastlio2 fastlivo2" 0.25 $r
    run $OUT/flights/urban_speed5.bag urban_speed5 $OUT/headroom/rate$r "fastlio2 fastlivo2" 1.0 $r
  done
fi

echo "== $(date +%T) done${ONLY:+ ($ONLY)}"
if [ ${#FAILED[@]} -gt 0 ]; then printf '!! %s\n' "${FAILED[@]}"; exit 1; fi
