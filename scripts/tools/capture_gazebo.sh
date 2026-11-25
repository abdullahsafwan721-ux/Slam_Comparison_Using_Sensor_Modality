#!/usr/bin/env bash
# Pictures of the Gazebo window while a simulation container runs (HOST):
#   bash scripts/tools/capture_gazebo.sh <out dir> <container name | pattern of its command> [every s] [max] [view]
#   view = a model name to follow (e.g. iris), or "x y z qx qy qz qw" for a fixed view (world frame), or
#          "room" for the fixed view from the room's south-west corner used in the final check
#   bash scripts/tools/capture_gazebo.sh output/x/shots px4_record.sh 6 40 room &
# Waits for the container and for the Gazebo window, sets Gazebo's own view (gzclient_camera: follow
# a model, or the user camera's pose through ~/user_camera/joy_pose), then grabs the window every
# <every> seconds until the container ends or <max> pictures are taken, and converts them to PNG
# (scripts/stage5/xwd_to_png.py). Only the Gazebo window is captured (xwd -id), never the screen.
# Keyed on the container, not on a log line: tools whose output goes to a file without a terminal
# block-buffer it (rosbag, python without -u), so such lines arrive only at the end.
OUT=$1; PAT=$2; EVERY=${3:-6}; MAX=${4:-40}; VIEW=${5:-}
[ "$VIEW" = room ] && VIEW="-5.5 -3.5 4.0 -0.0625 0.1983 0.2941 0.9329"   # above the SW corner (walls 3 m, no roof), yaw 35, 24 deg down
X=${DISPLAY:-:1}; mkdir -p "$OUT"; SECONDS=0; CID=
while [ -z "$CID" ]; do
  CID=$(docker ps --filter "name=^${PAT}$" --format '{{.ID}}' | head -1)
  [ -z "$CID" ] && CID=$(docker ps --no-trunc --format '{{.ID}} {{.Command}}' | grep -F -- "$PAT" | grep -v capture_gazebo | cut -d' ' -f1 | head -1)
  [ $SECONDS -gt 7200 ] && { echo "capture_gazebo: no container '$PAT'"; exit 1; }
  [ -z "$CID" ] && sleep 1
done
win() { xwininfo -display "$X" -root -tree 2>/dev/null | grep -E '"Gazebo": \("gazebo"' | grep -oE "0x[0-9a-f]+" | head -1; }
until [ -n "$(win)" ]; do docker inspect "$CID" >/dev/null 2>&1 || exit 0; sleep 1; done
sleep 8
gzx() { docker exec "$CID" bash -c "source /opt/ros/noetic/setup.bash >/dev/null 2>&1; source /usr/share/gazebo/setup.sh >/dev/null 2>&1; $*" 2>/dev/null; }
set_view() {
  if [ -z "$VIEW" ]; then return 0; fi
  set -- $VIEW
  if [ $# -eq 1 ]; then
    gzx "timeout 20 gz camera -c gzclient_camera -f $1" >/dev/null && echo "capture_gazebo: view follows $1" \
      || echo "capture_gazebo: could not set the view to follow $1"
  else
    local topic; topic=$(gzx "timeout 20 gz topic -l" | grep -m1 "/user_camera/joy_pose$")
    gzx "timeout 20 gz camera -c gzclient_camera -f ''" >/dev/null
    gzx "timeout 20 gz topic -p $topic -m 'position {x: $1 y: $2 z: $3} orientation {x: $4 y: $5 z: $6 w: $7}'" >/dev/null \
      && echo "capture_gazebo: fixed view at ($1, $2, $3) via ${topic:-?}" || echo "capture_gazebo: could not set the fixed view"
  fi
}
set_view
i=0
while docker inspect -f '{{.State.Running}}' "$CID" 2>/dev/null | grep -q true && [ $i -lt "$MAX" ]; do
  w=$(win); [ -n "$w" ] || break
  i=$((i + 1)); xwd -display "$X" -id "$w" -silent > "$OUT/gazebo_$(printf %02d $i).xwd" 2>/dev/null
  [ $i -eq 3 ] && set_view >/dev/null      # PX4's start-up can reset the view: set it once more
  sleep "$EVERY"
done
ls "$OUT"/*.xwd >/dev/null 2>&1 && python3 -W ignore "$(dirname "$0")/../stage5/xwd_to_png.py" "$OUT"/*.xwd >/dev/null 2>&1
echo "capture_gazebo: $(ls "$OUT"/*.png 2>/dev/null | wc -l) pictures in $OUT"
