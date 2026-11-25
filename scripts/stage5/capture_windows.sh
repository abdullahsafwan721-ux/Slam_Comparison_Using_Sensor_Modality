#!/usr/bin/env bash
# Pictures of a watched Stage 5 flight (host):
#   bash scripts/stage5/capture_windows.sh <flights-dir>/<name>   # while run_closed_loop.sh runs with GUI=true
# Waits for "armed, OFFBOARD" in <name>.mission.log, then grabs a window every 4 s until the
# vehicle has landed, into <name>.shots/*.png:
#   * Gazebo when RViz is not open; xwd copies what is VISIBLE in a window's area, and RViz's
#     window covers Gazebo's (found on 18 Nov: the "Gazebo" pictures showed RViz);
#   * RViz (FAST-LIO2's map and pose) when it is open.
# Only those windows are captured, never the whole screen. Gazebo's own view (the camera named
# gzclient_camera; `gz camera -l` also lists the rig's stereo cameras, and the first attempt
# picked one of those) is set to follow the drone. By hand: right-click the drone -> Follow.
B=$1; D=$B.shots; mkdir -p "$D"; SECONDS=0
until grep -q "armed, OFFBOARD" "$B.mission.log" 2>/dev/null; do [ $SECONDS -gt 900 ] && exit 1; sleep 1; done
X=${DISPLAY:-:1}
wid() { xwininfo -display "$X" -root -tree | grep -E "$1" | grep -oE "0x[0-9a-f]+" | head -1; }
SIMC=$(docker ps --no-trunc --format '{{.ID}} {{.Command}}' | grep -E "sim_ev.sh|px4_record.sh" | cut -d' ' -f1 | head -1)
# GZ_VIEW="x y z qx qy qz qw" (or "room": 4 m up over the room's south-west corner, yaw 35 deg, 24 deg down) fixes Gazebo's
# view instead of following the drone: in the room the follow view is often blocked by a wall or a box
if [ -n "$SIMC" ] && [ -n "${GZ_VIEW:-}" ]; then
  V7=$GZ_VIEW; [ "$V7" = room ] && V7="-5.5 -3.5 4.0 -0.0625 0.1983 0.2941 0.9329"
  read -r VX VY VZ QX QY QZ QW <<< "$V7"
  docker exec "$SIMC" bash -c "source /opt/ros/noetic/setup.bash >/dev/null 2>&1; source /usr/share/gazebo/setup.sh >/dev/null 2>&1
    T=\$(timeout 20 gz topic -l | grep -m1 '/user_camera/joy_pose\$'); timeout 20 gz camera -c gzclient_camera -f '' >/dev/null 2>&1
    timeout 20 gz topic -p \$T -m 'position {x: $VX y: $VY z: $VZ} orientation {x: $QX y: $QY z: $QZ w: $QW}' \
      && echo 'Gazebo view fixed at ($VX, $VY, $VZ)'" 2>/dev/null
elif [ -n "$SIMC" ]; then
  docker exec "$SIMC" bash -c 'source /scripts/common/sim_env.sh px4 >/dev/null 2>&1
  gz camera -c gzclient_camera -f iris >/dev/null 2>&1; echo "Gazebo view set to follow the drone (gz camera exit $?)"' 2>/dev/null
fi
i=0
until grep -qE "landed and disarmed|still armed" "$B.mission.log" || [ $i -ge 60 ]; do
  i=$((i + 1)); n=$(printf %02d $i)
  r=$(wid 'RViz": \("rviz"')
  if [ -n "$r" ]; then xwd -display "$X" -id "$r" -silent > "$D/rviz_$n.xwd"
  else g=$(wid '"Gazebo": \("gazebo"'); [ -n "$g" ] && xwd -display "$X" -id "$g" -silent > "$D/gazebo_$n.xwd"; fi
  sleep 4
done
ls "$D"/*.xwd >/dev/null 2>&1 && python3 -W ignore "$(dirname "$0")/xwd_to_png.py" "$D"/*.xwd > /dev/null
echo "$(ls "$D" | wc -l) pictures in $D"
