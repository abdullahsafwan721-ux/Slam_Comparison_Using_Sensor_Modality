#!/usr/bin/env bash
# Stage 5, TERMINAL 1: PX4 SITL configured to fly on SLAM alone.
#   docker compose run --rm sim-live bash /scripts/stage5/sim_ev.sh room [out.bag] [mission args]
#   e.g. ... sim_ev.sh room /output/stage5/flights/room_square.bag square --size 4 --alt 1.5
#
# PX4 SITL keeps parameters in a file inside this container. Some EKF2 settings
# (sources, height reference) only take full effect at boot, so we boot twice:
#   phase 1  boot normally (GPS), write the EV-only parameters, shut down
#   phase 2  boot again -- EKF2 now has NO position source until SLAM publishes
#
# Changes from the guide's listing (docs/stage5_log.md), all taken from Stage 3's
# px4_record.sh, which flies the same vehicle:
#   * SPAWN="x y" (default -2.0 -1.8, the validated room take-off point; the guide spawns at
#     the origin, where the room has a box) and the spawn height from rig.yaml's landing gear;
#   * the mission arguments, if given, go through check_clearance.py first: no flight
#     whose path or take-off spot is not clear;
#   * every wait gives up after 240 s instead of blocking for ever;
#   * GUI defaults to true as in the guide; run_closed_loop.sh passes GUI=false;
#   * the bag also records the raw and noised IMU, the LiDAR and EKF2's status, so a flight
#     can be replayed and diagnosed offline;
#   * EV_DELAY=<ms> overrides EKF2_EV_DELAY for this flight (FAST-LIVO2 publishes its pose
#     ~75 ms after the state it describes; the guide's tuning knob, 5.6);
#   * Ctrl-C (or docker kill -s INT) closes the bag, then stops PX4 and Gazebo, and keeps
#     PX4's own flight log (<out>.ulg; arm to disarm): EKF2's innovations and test ratios
#     are only there, and Stage 7 tunes EKF2_EV_DELAY from exactly these logs (guide 5.6).
set -eo pipefail
WORLD=${1:-room}; OUT=${2:-/output/stage5/closed_loop_${WORLD}.bag}; shift 2 || shift $#
source /scripts/common/sim_env.sh px4
mkdir -p "$(dirname "$OUT")"
LOG=${OUT%.bag}
read -r SX SY <<< "${SPAWN:--2.0 -1.8}"
SZ=$(python3 -c "import yaml; print(0.02 - yaml.safe_load(open('/config/rig.yaml')).get('landing_gear', {}).get('foot_z', 0.0))")
if [ $# -gt 0 ]; then
  python3 /scripts/stage3/check_clearance.py /sim/worlds/${WORLD}.world "$@" --spawn "$SX" "$SY" \
      | tee "$LOG.clearance.txt"
fi

SIM=; REC=
stop() {
  [ -n "$REC" ] && { rosnode kill /recorder >/dev/null 2>&1 || true; wait $REC 2>/dev/null || true; }
  [ -n "$SIM" ] && { kill -INT $SIM 2>/dev/null || true; wait $SIM 2>/dev/null || true; }
  if [ -e /tmp/phase2.start ]; then        # PX4's flight log of phase 2 (the closed-loop flight)
    U=$(find ~/.ros /opt/PX4-Autopilot/build -name '*.ulg' -newer /tmp/phase2.start 2>/dev/null | sort | tail -1)
    [ -n "$U" ] && cp "$U" "$LOG.ulg" && echo "== PX4 flight log kept: $LOG.ulg"
  fi
}
trap 'stop; exit 0' INT TERM
boot() {   # boot <phase>: one attempt; 0 = MAVROS connected to PX4
  roslaunch px4 mavros_posix_sitl.launch vehicle:=iris \
      sdf:=/sim/models/iris_evtol/model.sdf world:=/sim/worlds/${WORLD}.world \
      x:=$SX y:=$SY z:=$SZ \
      gui:=${GUI:-true} interactive:=false > "$LOG.sim_$1.log" 2>&1 &
  SIM=$!
  SECONDS=0
  until timeout 10 rostopic echo -n1 /mavros/state 2>/dev/null | grep -q 'connected: True'; do
    if [ $SECONDS -ge 240 ] || grep -q "process has died" "$LOG.sim_$1.log"; then
      if grep -q "process has died" "$LOG.sim_$1.log"; then echo "!! $1: a simulator process died while starting (see $LOG.sim_$1.log)"
      else echo "!! $1: MAVROS not connected after 240 s (see $LOG.sim_$1.log)"; fi
      kill -INT $SIM 2>/dev/null; wait $SIM 2>/dev/null; SIM=
      return 1
    fi
    sleep 1
  done
}
# gzserver segfaulted while loading the urban world in 2 of ~30 second boots (exit code 139,
# PX4's start-up script then fails): a fresh attempt has always come up. One retry per phase;
# the failed attempt's log is kept as <out>.sim_<phase>.failed.log
boot_retry() {
  boot "$1" && return 0
  mv -f "$LOG.sim_$1.log" "$LOG.sim_$1.failed.log"; sleep 5
  echo "== $1: second attempt"
  boot "$1" || { stop; exit 1; }
}

echo "== phase 1: writing EV-only parameters"
boot_retry phase1
PFILES=/config/px4/ev_only.params
if [ -n "${EV_DELAY:-}" ]; then               # Stage 5 extension: per-flight EKF2_EV_DELAY (ms)
  printf 'EKF2_EV_DELAY %.1f\n' "$EV_DELAY" > /tmp/ev_delay.params   # a FLOAT: written with a point
  PFILES="$PFILES /tmp/ev_delay.params"
fi
if ! python3 /scripts/stage5/set_params.py $PFILES | tee "$LOG.params.txt"; then
  echo "!! a parameter did not take -- not flying"; stop; exit 1
fi
kill -INT $SIM; wait $SIM 2>/dev/null || true; SIM=
sleep 3

echo "== phase 2: booting on external vision only"
touch /tmp/phase2.start
boot_retry phase2
until rostopic list 2>/dev/null | grep -q '^/ground_truth/odom$'; do sleep 1; done
rosbag record -O "$OUT" /ground_truth/odom /Odometry /aft_mapped_to_init /mavros/vision_pose/pose \
    /mavros/local_position/pose /mavros/setpoint_position/local /mavros/state \
    /mavros/estimator_status /mavros/extended_state \
    /livox/imu /livox/imu_noisy /livox/lidar __name:=recorder >/dev/null 2>&1 &
REC=$!
cat <<'MSG'

  PX4 is up with NO position source. Now:
    TERMINAL 2:  docker compose run --rm fastlio2-live bash /scripts/stage5/slam_live.sh
    wait until:  FAST-LIO2 publishes /Odometry (RViz shows the map)
    TERMINAL 3:  docker compose run --rm sim-live bash -c "source /opt/ros/noetic/setup.bash && \
                   python3 /scripts/stage3/offboard_mission.py square --size 4 --alt 1.5 --speed 1 \
                   --sitl-params"
  Ctrl-C here when the vehicle has landed; the bag is closed on exit.

MSG
wait $SIM || true
