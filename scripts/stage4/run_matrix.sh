#!/usr/bin/env bash
# Stage 4: the full experiment matrix. Runs on the HOST from the project root:
#   bash scripts/stage4/run_matrix.sh            # everything (many hours)
#   ONLY=environments bash scripts/stage4/run_matrix.sh
#   ONLY=altitude|speed|imu ...
#   STEP=fly ONLY=altitude bash scripts/stage4/run_matrix.sh   # record + gate only
#   STEP=algos ...                                              # algorithms only
#   ALTS="20 50" ONLY=altitude ...     # a subset of the altitudes (several streams in parallel)
#
# Every flight is recorded ONCE, then replayed through all three algorithms
# RUNS times. Re-flying per algorithm would hand each algorithm different data.
#
# Guide 4.2, ADAPTED (docs/stage4_log.md):
#   * flights as validated in Stage 3: room flights are the 4 m square x 3 laps from
#     SPAWN (-2.0, -1.8); the guide's 6 m square from the origin hits boxes. The urban
#     altitude square is flown from (-15, -15), i.e. centred on the open plaza: from the
#     origin it passes 0.3 m from a 27 m building at 10 and 20 m altitude
#     (check_clearance.py). Every flight still goes through check_clearance.py.
#   * "room" is the Stage 3 gate flight itself (same command), linked, not flown again.
#   * every new bag must pass verify_sim_bag.py --flight before any algorithm sees it.
#   * a flight is locked while it is recorded, so two groups that share a flight
#     (speed and imu share urban_speed5) can run at the same time without both flying it.
#   * a failed flight or gate skips that condition and is reported; the rest goes on.
#   * a condition whose runs are complete (marker <group>/.done_<condition>) is not run
#     again, so re-running a group only fills what is missing (FORCE=1 re-runs it).
#   * TAU (tracking-success threshold) 0.25 m indoors, 1.0 m outdoors (plan, H3).
#   * ORB-SLAM3's settings keep the baseline IMU noise at every IMU level, like the two
#     LiDAR methods keep theirs: the guide's "default tuning; robustness, not re-tuning".
set -o pipefail
[ -f compose.yaml ] || { echo "run from the project root"; exit 1; }
RUNS=${RUNS:-3}
STEP=${STEP:-all}
OUT=output/stage4
C="docker compose run --rm -T"
mkdir -p $OUT/flights $OUT/logs
FAILED=()

gate() {   # gate <name>: sensor gate of a recorded flight, once
  local bag=$OUT/flights/$1.bag
  [ -s "$OUT/flights/$1.gate.txt" ] && grep -q "ALL CHECKS PASSED" "$OUT/flights/$1.gate.txt" && return 0
  $C sim bash -c "source /scripts/common/sim_env.sh && \
      python3 /scripts/stage2/verify_sim_bag.py /$bag --flight" > "$OUT/flights/$1.gate.txt" 2>&1 < /dev/null
  grep -q "ALL CHECKS PASSED" "$OUT/flights/$1.gate.txt"
}

fly() {    # fly <name> <world> <spawn "x y"> <profile> [mission args...]
  local name=$1 world=$2 spawn=$3 profile=$4; shift 4
  local bag=$OUT/flights/$name.bag attempt
  exec 9> "$OUT/flights/.$name.lock"; flock 9          # one recorder per flight name
  for attempt in 1 2; do
    if [ -s "$bag" ]; then echo "== $name: flight exists, reusing"
    else
      # One simulator at a time: with three or four running, Gazebo's LiDAR updates slipped
      # in simulation time (scan intervals 79-124 ms) and two flights failed the gate.
      exec 8> "$OUT/flights/.simulator.lock"; flock 8
      echo "== $(date +%T) $name: flying ($world from $spawn, $profile $*)"
      $C -e SPAWN="$spawn" sim bash /scripts/stage3/px4_record.sh "$world" "$profile" "/$bag" "$@" \
          > "$OUT/logs/$name.record.log" 2>&1 < /dev/null
      local rc=$?; flock -u 8
      [ $rc -eq 0 ] || { echo "!! $name: flight FAILED (see $OUT/logs/$name.record.log)"; FAILED+=("$name: flight"); flock -u 9; return 1; }
    fi
    if gate "$name"; then flock -u 9; echo "== $name: gate passed"; return 0; fi
    [ $attempt -eq 2 ] && break
    local keep=$OUT/flights/${name}_try$(date +%H%M%S)          # kept as evidence, flown again
    mkdir -p "$keep"; mv "$OUT/flights/$name".* "$keep"/; mv "$OUT/logs/$name.record.log" "$keep"/ 2>/dev/null
    echo "!! $name: sensor gate FAILED (kept in $keep); flying it again"
  done
  flock -u 9
  echo "!! $name: sensor gate FAILED twice (see $OUT/flights/$name.gate.txt)"; FAILED+=("$name: gate"); return 1
}

algos() {  # algos <flight> <group> <tau> [condition] [imu-scale]
  local bag=$OUT/flights/$1.bag cond=${4:-$1}
  grep -q "ALL CHECKS PASSED" "$OUT/flights/$1.gate.txt" 2>/dev/null \
    || { echo "!! $cond: no gated flight $1, skipped"; FAILED+=("$cond: no flight"); return 1; }
  local done=$OUT/$2/.done_$cond
  if [ -e "$done" ] && [ -z "${FORCE:-}" ]; then echo "== $cond: runs complete, skipped"; return 0; fi
  echo "== $(date +%T) $cond: algorithms ($RUNS runs)"
  TAU=$3 bash scripts/stage3/run_all_algos.sh "$bag" "$cond" "$OUT/$2" "$RUNS" "${5:-1.0}" \
      > "$OUT/logs/$2__$cond.run.log" 2>&1 < /dev/null \
    || { echo "!! $cond: run_all_algos failed (see $OUT/logs/$2__$cond.run.log)"; FAILED+=("$cond: algos"); return 1; }
  date -Is > "$done"
}
want() { [ -z "${ONLY:-}" ] || [ "$ONLY" = "$1" ]; }
doing() { [ "$STEP" = all ] || [ "$STEP" = "$1" ]; }

ROOM="-2.0 -1.8"; PLAZA="-15 -15"; ORIGIN="0 0"

# --- A. Environments: each built to starve ONE sensing modality -------------
if want environments; then
  if doing fly; then
    # the Stage 3 gate flight IS this condition (same world, spawn and command)
    [ -e $OUT/flights/room.bag ] || ln output/stage3/flights/room_square.bag $OUT/flights/room.bag
    [ -e $OUT/flights/room.gate.txt ] || cp output/stage3/flights/room_square.gate.txt $OUT/flights/room.gate.txt
    fly room       room       "$ROOM"   square  --size 4  --alt 1.5 --speed 1.5 --laps 3
    fly room_plain room_plain "$ROOM"   square  --size 4  --alt 1.5 --speed 1.5 --laps 3  # no texture: vision starves
    fly corridor   corridor   "$ORIGIN" line    --size 60 --alt 1.5 --speed 2             # no geometry along x
    fly field      field      "$ORIGIN" figure8 --size 15 --alt 5   --speed 3             # one plane
  fi
  if doing algos; then
    for n in room room_plain corridor; do algos $n environments 0.25; done
    algos field environments 1.0
  fi
fi

# --- B. Altitude sweep: the eVTOL-specific question -------------------------
if want altitude; then
  for h in ${ALTS:-10 20 30 40 50 60}; do
    doing fly && fly urban_alt$h urban "$PLAZA" square --size 30 --alt $h --speed 4
    doing algos && algos urban_alt$h altitude 1.0
  done
fi

# --- C. Aggressiveness: speed and yaw rate ----------------------------------
if want speed; then
  for v in 2 5 8; do
    doing fly && fly urban_speed$v urban "$ORIGIN" figure8 --size 20 --alt 20 --speed $v --yaw tangent
    doing algos && algos urban_speed$v speed 1.0
  done
fi

# --- D. IMU grade: ONE flight, noise injected at several levels --------------
if want imu; then
  doing fly && fly urban_speed5 urban "$ORIGIN" figure8 --size 20 --alt 20 --speed 5 --yaw tangent
  if doing algos; then
    for s in 1 3 10 30; do    # same input bag every time; only the injected noise differs
      algos urban_speed5 imu 1.0 imu_x$s $s
    done
  fi
fi

echo "== $(date +%T) done${ONLY:+ ($ONLY)}"
if [ ${#FAILED[@]} -gt 0 ]; then printf '!! %s\n' "${FAILED[@]}"; exit 1; fi
