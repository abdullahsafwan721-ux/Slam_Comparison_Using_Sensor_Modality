#!/usr/bin/env bash
# Stage 5 extension: the closed loop over the Stage 4 matrix. HOST, project root, nothing else
# running (one closed loop at a time: host networking, one ROS master):
#   bash scripts/stage5/run_closed_loop_matrix.sh                    # everything not flown yet
#   ALGOS="fastlivo2" CONDS="room field" bash scripts/stage5/run_closed_loop_matrix.sh
#   GUI=true ...                                                     # watch every flight
# Every condition flies the Stage 4 mission from the Stage 4 spawn (scripts/stage4/run_matrix.sh),
# with the SLAM method as PX4's ONLY source of position, height and heading:
#   A environments  room, room_plain, corridor, field
#   B altitude      urban_alt10 ... urban_alt60
#   C speed         urban_speed2, urban_speed5, urban_speed8
#   D IMU grade     imu_x3, imu_x10, imu_x30 (the urban_speed5 flight, live IMU noise; x1 = urban_speed5)
#   E faults, live  room_lidar_drop_2s, room_lidar_drop_5s (both methods), room_cam_black_5s (FAST-LIVO2)
# FAST-LIVO2 first gets the guide's EKF2_EV_DELAY tuning (5.6): the room flight with 0, 40, 75,
# 110, 150, 190 ms (EVDS); the delay with the lowest PX4 error IN FLIGHT (unaligned, take-off to
# first touchdown) is used for all its other flights (<M>/fastlivo2/ev_delay.txt). The guide says
# "PX4's APE"; the Stage 3/4 flight window can include a touchdown bounce, and at 40 ms a landing
# event (the vehicle relaunched) made that number 97 cm while the flight itself was 12 cm.
# FAST-LIO2 flies with 0 (Stage 5: lag 0.00 s).
# ORB-SLAM3 is not in this loop: it never gives a pose before take-off (69 of 69 Stage 4 runs)
# and PX4 on vision alone cannot take off without one (docs/stage5_log.md).
# A condition whose <name>.closed_loop.json exists has been flown and scored -- completed or not:
# a SLAM failure in the loop is a result. A harness failure (no score) is moved to
# <M>/<algo>/failed/<name>_<time>/ and flown once more. Progress: <M>/status.txt, <M>/matrix.log.
set -o pipefail
[ -f compose.yaml ] || { echo "run from the project root"; exit 1; }
M=output/stage5/matrix; mkdir -p $M
ROOM="-2.0 -1.8"; PLAZA="-15 -15"; ORIGIN="0 0"
SQ="square --size 4 --alt 1.5 --speed 1.5 --laps 3"            # the Stage 4 room flight
F8="figure8 --size 20 --alt 20 --speed 5 --yaw tangent"        # urban_speed5, the IMU-grade flight
#  name                  world       spawn     noise fault          mission
TABLE="
room                     room        ROOM      1.0   -              $SQ
room_plain               room_plain  ROOM      1.0   -              $SQ
corridor                 corridor    ORIGIN    1.0   -              line --size 60 --alt 1.5 --speed 2
field                    field       ORIGIN    1.0   -              figure8 --size 15 --alt 5 --speed 3
urban_alt10              urban       PLAZA     1.0   -              square --size 30 --alt 10 --speed 4
urban_alt20              urban       PLAZA     1.0   -              square --size 30 --alt 20 --speed 4
urban_alt30              urban       PLAZA     1.0   -              square --size 30 --alt 30 --speed 4
urban_alt40              urban       PLAZA     1.0   -              square --size 30 --alt 40 --speed 4
urban_alt50              urban       PLAZA     1.0   -              square --size 30 --alt 50 --speed 4
urban_alt60              urban       PLAZA     1.0   -              square --size 30 --alt 60 --speed 4
urban_speed2             urban       ORIGIN    1.0   -              figure8 --size 20 --alt 20 --speed 2 --yaw tangent
urban_speed5             urban       ORIGIN    1.0   -              $F8
urban_speed8             urban       ORIGIN    1.0   -              figure8 --size 20 --alt 20 --speed 8 --yaw tangent
imu_x3                   urban       ORIGIN    3     -              $F8
imu_x10                  urban       ORIGIN    10    -              $F8
imu_x30                  urban       ORIGIN    30    -              $F8
room_lidar_drop_2s       room        ROOM      1.0   lidar_drop_2s  $SQ
room_lidar_drop_5s       room        ROOM      1.0   lidar_drop_5s  $SQ
room_cam_black_5s        room        ROOM      1.0   cam_black_5s   $SQ
"
log() { echo "$*" | tee -a $M/matrix.log; }
status() { echo "$(date -Is) $*" >> $M/status.txt; }

fly() {   # fly <algo> <name> <world> <spawn> <noise> <fault> <ev_delay> <mission...>
  local algo=$1 name=$2 world=$3 spawn=$4 noise=$5 fault=$6 evd=$7; shift 7
  local F=$M/$algo/flights E=$M/$algo/eval try rc
  mkdir -p $F $E
  if [ -s $F/$name.closed_loop.json ]; then log "== $algo $name: flown and scored, skipped"; return 0; fi
  local free; free=$(df -BG --output=avail /home | tail -1 | tr -dc 0-9)
  [ "$free" -lt 30 ] && { log "!! only ${free} GB free on /home: stopping before $algo $name"; exit 1; }
  for try in 1 2; do
    if ls $F/$name.* >/dev/null 2>&1; then              # an earlier attempt without a score
      local keep=$M/$algo/failed/${name}_$(date +%H%M%S); mkdir -p $keep; mv $F/$name.* $keep/
      log "   (earlier attempt kept in $keep)"
    fi
    log "== $(date +%T) $algo $name (try $try): $world from $spawn, noise x$noise, fault $fault, EV_DELAY ${evd} ms: $*"
    FLIGHTS=$F EVAL=$E ALGO=$algo SPAWN="$spawn" NOISE=$noise EV_DELAY=$evd \
      FAULT=$([ "$fault" = - ] || echo "$fault") GUI=${GUI:-false} RVIZ=${RVIZ:-false} \
      bash scripts/stage5/run_closed_loop.sh $name $world "$@" > $F/$name.run.log 2>&1 < /dev/null   # compose reads stdin
    rc=$?
    grep -E "^!!|RMSE|lag behind|FAULT|modes around|hover at|verdict|mechanism|landed|still armed" $F/$name.run.log \
      | sed 's/^/     /' | tee -a $M/matrix.log
    if [ -s $F/$name.closed_loop.json ]; then
      local done_; done_=$(grep -q "landed and disarmed" $F/$name.mission.log 2>/dev/null && echo "mission complete" || echo "MISSION INCOMPLETE")
      status "$algo $name scored ($done_)"; return 0
    fi
    status "$algo $name try $try: NO SCORE (rc $rc, see $F/$name.run.log)"
  done
  log "!! $algo $name: no score after 2 tries"; return 1
}

spawn_of() { case $1 in ROOM) echo "$ROOM";; PLAZA) echo "$PLAZA";; *) echo "$ORIGIN";; esac; }
want_algo() { case " ${ALGOS:-fastlio2 fastlivo2} " in *" $1 "*) return 0;; esac; return 1; }
want_cond() { [ -z "${CONDS:-}" ] && return 0; case " $CONDS " in *" $1 "*) return 0;; esac; return 1; }

log "== $(date -Is) closed-loop matrix  git $(git rev-parse --short HEAD)  algos: ${ALGOS:-fastlio2 fastlivo2}  conds: ${CONDS:-all}"

# --- FAST-LIVO2: EKF2_EV_DELAY first (guide 5.6) --------------------------------------------
EVD_FILE=$M/fastlivo2/ev_delay.txt
EVDS=${EVDS:-"0 40 75 110 150 190"}
if want_algo fastlivo2 && [ ! -s $EVD_FILE ]; then
  for d in $EVDS; do fly fastlivo2 room_evd$d room "$ROOM" 1.0 - $d $SQ; done
  python3 - "$M/fastlivo2" "$EVD_FILE" $EVDS <<'EOF'
import json, os, sys
D, out = sys.argv[1:3]; rows = []
for d in map(int, sys.argv[3:]):
    j = os.path.join(D, "flights", "room_evd%d.closed_loop.json" % d)
    a = os.path.join(D, "eval", "px4__room_evd%d__r1_extra.json" % d)
    if os.path.exists(j):
        o = json.load(open(j))
        ape = json.load(open(a))["ape_air_rmse"] if os.path.exists(a) else float("nan")
        rows.append((o["px4_truth"]["rmse_m"], d, ape))
if len(rows) < 3:
    sys.exit("!! EV_DELAY sweep incomplete: %s" % rows)
best = min(rows)[1]
txt = ", ".join("%d ms %.1f (APE %.1f)" % (d, v * 100, a * 100) for v, d, a in sorted(rows, key=lambda r: r[1]))
open(out, "w").write("%d\n# PX4 vs truth in flight, cm (PX4 APE over the Stage 3/4 window, cm) per EKF2_EV_DELAY: %s\n" % (best, txt))
print("== FAST-LIVO2 EKF2_EV_DELAY: %d ms (PX4 vs truth in flight per delay: %s)" % (best, txt))
EOF
  [ -s $EVD_FILE ] || { log "!! no EV_DELAY chosen for FAST-LIVO2"; exit 1; }
  log "$(head -2 $EVD_FILE | tr '\n' ' ')"
  # the minimum must not sit at the edge of the sweep
  [ "$(head -1 $EVD_FILE)" = "${EVDS##* }" ] && { log "!! the best EV_DELAY is the largest tried: extend EVDS"; rm -f $EVD_FILE; exit 1; }
fi
LIVO_EVD=$(head -1 $EVD_FILE 2>/dev/null)

# --- the matrix: each condition with both methods -------------------------------------------
while read -r name world sp noise fault mission; do               # (not a pipe: exit must stop the script)
  [ -z "$name" ] && continue
  want_cond $name || continue
  for algo in fastlio2 fastlivo2; do
    want_algo $algo || continue
    case $fault in cam_*) [ $algo = fastlio2 ] && continue;; esac      # FAST-LIO2 has no camera
    evd=0; [ $algo = fastlivo2 ] && evd=${LIVO_EVD:?no EV_DELAY for FAST-LIVO2}
    fly $algo $name $world "$(spawn_of $sp)" $noise $fault $evd $mission
  done
done < <(echo "$TABLE")
log "== $(date -Is) matrix done"
