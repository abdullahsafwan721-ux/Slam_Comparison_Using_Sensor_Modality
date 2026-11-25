#!/usr/bin/env bash
# Stage 5: one closed-loop flight, the guide's three terminals run in order by one script.
# HOST, project root, nothing else running (host networking: one ROS master on port 11311):
#   bash scripts/stage5/run_closed_loop.sh <name> <world> <mission args...>
#   bash scripts/stage5/run_closed_loop.sh room_square_r1 room square --size 4 --alt 1.5 --speed 1 --laps 2
#   GUI=true  opens the Gazebo window (watch the flight); RVIZ=true opens the SLAM map
#   SPAWN="x y"  take-off point (default -2.0 -1.8, the validated room spawn)
#   NOISE=<scale>  live IMU noise, x baseline (default 1.0)
#   FLIGHTS=<dir> EVAL=<dir>  where the flight and its scores go (default output/stage5/...)
# Stage 5 extension (closed loop over the Stage 4 matrix, run_closed_loop_matrix.sh):
#   ALGO=fastlio2|fastlivo2  the SLAM method in the loop (default fastlio2)
#   FAULT=lidar_drop_2s|lidar_drop_5s|cam_black_5s  a live sensor fault (fault_live.py)
#   EV_DELAY=<ms>  EKF2_EV_DELAY for this flight (default: ev_only.params, 0)
#
# The guide (5.4) runs three terminals by hand; this does exactly the same, in order:
#   1  sim_ev.sh      PX4 boots, EV-only parameters written and read back, PX4 reboots with
#                     NO position source, recording starts
#   2  slam_live.sh   the SLAM method on the live (noised) IMU + LiDAR (+ camera), relayed to PX4
#   3  offboard_mission.py  only once the SLAM method publishes and EKF2 reports a position
# then closes the bag (Ctrl-C of terminal 1), stops the SLAM method and scores the flight
# (eval_closed_loop.sh) -- also when the mission did not complete: in the matrix a failure is
# a result, and its numbers say what happened. Everything lands in <FLIGHTS>/<name>.*
set -o pipefail
[ -f compose.yaml ] || { echo "run from the project root"; exit 1; }
NAME=$1; WORLD=$2; shift 2
OUT=${FLIGHTS:-output/stage5/flights}; mkdir -p $OUT        # FLIGHTS=<dir> (verify_stage5.sh) flies elsewhere
B=$OUT/$NAME
[ -e "$B.bag" ] && { echo "!! $B.bag exists: one recording = one name"; exit 1; }
A=${ALGO:-fastlio2}
case "$A" in
  fastlio2)  TOPIC=/Odometry; LABEL=FAST-LIO2 ;;
  fastlivo2) TOPIC=/aft_mapped_to_init; LABEL=FAST-LIVO2 ;;
  *) echo "!! ALGO must be fastlio2 or fastlivo2"; exit 1 ;;
esac
C="docker compose run --rm -T"
S1=s5_sim_$$; S2=s5_slam_$$; S3=s5_fault_$$
cleanup() {
  docker kill -s INT $S1 >/dev/null 2>&1; sleep 8
  docker stop -t 10 $S2 $S3 $S1 >/dev/null 2>&1
  $C eval chown -R "$(id -u):$(id -g)" "/$OUT" >/dev/null 2>&1 || true
}
trap 'echo "!! interrupted"; cleanup; exit 1' INT TERM
# exact process names (a pattern search would also match a command line that mentions them)
{ pgrep -x gzserver || pgrep -x rosmaster || pgrep -x gzclient; } >/dev/null && { echo "!! a ROS master or simulator is already running on this host"; exit 1; }
waitfor() {   # waitfor <seconds> <description> <command...>
  local t=$1 what=$2; shift 2; SECONDS=0
  until "$@" >/dev/null 2>&1; do
    [ $SECONDS -lt $t ] || { echo "!! $what: not after $t s"; cleanup; exit 1; }
    sleep 2
  done
  echo "== $(date +%T) $what (${SECONDS} s)"
}
ros() { docker exec $S1 bash -c "source /opt/ros/noetic/setup.bash && $*"; }
echo "$A" > "$B.algo"
printf 'algo %s\nworld %s\nspawn %s\nnoise %s\nfault %s\nev_delay_ms %s\nmission %s\n' "$A" "$WORLD" \
    "${SPAWN:--2.0 -1.8}" "${NOISE:-1.0}" "${FAULT:-none}" "${EV_DELAY:-0 (ev_only.params)}" "$*" > "$B.config.txt"

echo "== $(date +%T) $NAME: terminal 1 (PX4, EV-only parameters, reboot)  GUI=${GUI:-false}  EV_DELAY=${EV_DELAY:-0}"
$C --name $S1 -e GUI="${GUI:-false}" -e SPAWN="${SPAWN:--2.0 -1.8}" -e EV_DELAY="${EV_DELAY:-}" sim-live \
    bash /scripts/stage5/sim_ev.sh "$WORLD" "/$B.bag" "$@" > "$B.terminal1.log" 2>&1 &
T1=$!
SECONDS=0                                      # stop waiting as soon as terminal 1 has given up
until grep -q "NO position source" "$B.terminal1.log"; do
  if ! kill -0 $T1 2>/dev/null || [ $SECONDS -ge 600 ]; then
    echo "!! PX4 did not come up without a position source:"; grep "!!" "$B.terminal1.log" | sed 's/^/   /'
    cleanup; exit 1
  fi
  sleep 2
done
echo "== $(date +%T) PX4 up with NO position source (${SECONDS} s)"
grep -E "set .* read back" "$B.terminal1.log" | sed 's/^/     /'
grep -q "FAILED" "$B.terminal1.log" && { echo "!! a parameter did not take"; cleanup; exit 1; }

if [ -n "${FAULT:-}" ]; then
  echo "== $(date +%T) fault node: $FAULT (starts 20 s after arming)"
  $C --name $S3 sim-live bash -c "source /opt/ros/noetic/setup.bash && source /ws/devel/setup.bash && \
      python3 -u /scripts/stage5/fault_live.py $FAULT" > "$B.fault.log" 2>&1 &
fi
echo "== $(date +%T) terminal 2 ($LABEL live, IMU noise x${NOISE:-1.0}${FAULT:+, on the $FAULT topic})  RVIZ=${RVIZ:-false}"
VOL=
if [ "$A" = fastlivo2 ]; then        # its own pose file carries the state-time stamps (Stage 3, A8)
  mkdir -p "$B.livo_result"; VOL="-v $PWD/$B.livo_result:/ws/src/FAST-LIVO2/Log/result"
fi
$C --name $S2 $VOL -e RVIZ="${RVIZ:-false}" -e ALGO="$A" -e FAULT="${FAULT:-}" ${A}-live \
    bash /scripts/stage5/slam_live.sh "${NOISE:-1.0}" > "$B.terminal2.log" 2>&1 &
T2=$!
waitfor 120 "$LABEL publishes $TOPIC" ros "timeout 5 rostopic echo -n1 $TOPIC"
waitfor 60 "relay publishes /mavros/vision_pose/pose" ros "timeout 5 rostopic echo -n1 /mavros/vision_pose/pose"
# interlock: PX4 must receive ONE pose stream, the relay's. FAST-LIVO2 publishes its own unrotated
# pose on this topic unless its launch file remaps it -- that lost a flight (docs/stage5_log.md)
PUBS=$(ros "rostopic info /mavros/vision_pose/pose" 2>/dev/null | sed -n '/Publishers:/,/Subscribers:/p' | grep -c '^ \* ')
ros "rostopic info /mavros/vision_pose/pose" > "$B.vision_pose_info.txt" 2>&1
if [ "$PUBS" != 1 ] || ! grep -q "/slam_to_px4" "$B.vision_pose_info.txt"; then
  echo "!! /mavros/vision_pose/pose has $PUBS publishers (must be exactly the relay /slam_to_px4) -- not flying"
  cat "$B.vision_pose_info.txt"; cleanup; exit 1
fi
echo "== $(date +%T) one publisher on /mavros/vision_pose/pose: the relay"
# EKF2 has accepted the vision pose once its status reports a valid relative horizontal and
# a valid vertical position (ESTIMATOR_STATUS flags, MAVROS /mavros/estimator_status)
if ros "timeout 8 rostopic echo -n1 /mavros/estimator_status"; then
  waitfor 90 "EKF2 has a position from SLAM" ros "timeout 5 rostopic echo -n1 /mavros/estimator_status | grep -q 'pos_horiz_rel_status_flag: True' && timeout 5 rostopic echo -n1 /mavros/estimator_status | grep -q 'pos_vert_abs_status_flag: True'"
  ros "timeout 5 rostopic echo -n1 /mavros/estimator_status" > "$B.estimator_status_before.txt" 2>&1
else
  echo "   (PX4 does not stream ESTIMATOR_STATUS here; the mission's arming check is the test)"
  sleep 10
fi
sleep 5                                       # the vehicle stays still while EKF2 settles

echo "== $(date +%T) terminal 3 (mission: $*)"
# python3 -u: without a terminal, Python block-buffers the mission's output, so the mission log
# would only fill at the end (capture_windows.sh and the progress lines below wait on it)
$C sim-live bash -c "source /opt/ros/noetic/setup.bash && python3 -u /scripts/stage3/offboard_mission.py $* --sitl-params" \
    2>&1 | grep --line-buffered -v "^ Container" | tee "$B.mission.log" \
    | grep --line-buffered -E "armed|hop|profile|landed|!!" | sed -u 's/^/     /'
sleep 3
echo "== $(date +%T) closing the bag (Ctrl-C of terminal 1), stopping $LABEL"
docker kill -s INT $S1 >/dev/null 2>&1; wait $T1 2>/dev/null
docker stop -t 10 $S2 $S3 >/dev/null 2>&1; wait $T2 2>/dev/null
$C eval chown -R "$(id -u):$(id -g)" "/$OUT" >/dev/null 2>&1
if [ -n "${FAULT:-}" ]; then
  grep -E "^FAULT (START|END)" "$B.fault.log" > "$B.fault.txt"
  sed 's/^/     /' "$B.fault.txt"
fi
RC=0
grep -q "landed and disarmed" "$B.mission.log" || { echo "!! the mission did not complete (see $B.mission.log); scoring it anyway"; RC=1; }
[ -s "$B.bag" ] || { echo "!! no bag (see $B.terminal1.log)"; exit 1; }
echo "== $(date +%T) scoring"
bash scripts/stage5/eval_closed_loop.sh "$NAME" || RC=1
exit $RC
