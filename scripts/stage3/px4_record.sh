#!/usr/bin/env bash
# Stage 3: PX4 SITL flight with the sensor rig, recorded to a bag.
# Runs INSIDE the sim container:
#   docker compose run --rm sim bash /scripts/stage3/px4_record.sh room square /output/stage3/px4_room_square.bag --size 6 --alt 1.5
#
#   args: <world> <profile> <out.bag> [offboard_mission.py options...]
# GUI=true in the environment opens the Gazebo window.
# SPAWN="x y" in the environment is the take-off point in world coordinates (default "0 0").
#
# Stage 3 changes from the guide's listing (docs/stage3_log.md):
#   * SPAWN + check_clearance.py: the guide spawns at the world origin, where the room has a
#     box, and its 6 m square crosses two tall boxes. The flight is refused unless the path
#     and the take-off spot are clear. Validated in the room at 1.5 m:
#       square  --size 4  SPAWN="-2.0 -1.8"     figure8 --size 3  SPAWN="0.9 -0.5"
#       line    --size 6  SPAWN="-5.1 0.7"      (check_clearance.py --search lists others)
#   * the two start-up waits give up after 240 s instead of blocking forever.
set -eo pipefail
WORLD=$1; PROFILE=$2; OUT=$3; shift 3
source /scripts/common/sim_env.sh px4
mkdir -p "$(dirname "$OUT")"
LOG="${OUT%.bag}"
read -r SX SY <<< "${SPAWN:-0 0}"
# spawn with the feet 2 cm above the floor (rig.yaml: landing_gear.foot_z)
SZ=$(python3 -c "import yaml; print(0.02 - yaml.safe_load(open('/config/rig.yaml')).get('landing_gear', {}).get('foot_z', 0.0))")
python3 /scripts/stage3/check_clearance.py /sim/worlds/${WORLD}.world "$PROFILE" \
    --spawn "$SX" "$SY" "$@" | tee "$LOG.clearance.txt"

# vehicle:=iris keeps PX4's iris airframe; sdf:= swaps in the iris WITH our rig.
roslaunch px4 mavros_posix_sitl.launch vehicle:=iris \
    sdf:=/sim/models/iris_evtol/model.sdf world:=/sim/worlds/${WORLD}.world \
    x:=$SX y:=$SY z:=$SZ \
    gui:=${GUI:-false} interactive:=false > "$LOG.sim.log" 2>&1 & SIM=$!
echo "waiting for PX4 + MAVROS ..."
giveup() { echo "!! $1 after 240 s -- see $LOG.sim.log"; kill -INT $SIM; wait $SIM 2>/dev/null; exit 1; }
SECONDS=0
until timeout 10 rostopic echo -n1 /mavros/state 2>/dev/null | grep -q 'connected: True'; do
  [ $SECONDS -lt 240 ] || giveup "MAVROS not connected to PX4"; sleep 1; done
until rostopic list 2>/dev/null | grep -q '^/ground_truth/odom$'; do
  [ $SECONDS -lt 240 ] || giveup "no /ground_truth/odom"; sleep 1; done

rosbag record -O "$OUT" \
    /livox/lidar /livox/imu /ground_truth/odom \
    /stereo/left/image_raw /stereo/right/image_raw \
    /stereo/left/camera_info /stereo/right/camera_info \
    /mavros/local_position/pose /mavros/state __name:=recorder >/dev/null 2>&1 & REC=$!
sleep 10                        # stationary on the ground: gravity initialisation
RC=0
python3 /scripts/stage3/offboard_mission.py "$PROFILE" --sitl-params "$@" 2>&1 | tee "$LOG.mission.log" || RC=1
sleep 3
rosnode kill /recorder >/dev/null 2>&1 || true; wait $REC 2>/dev/null || true
kill -INT $SIM; wait $SIM 2>/dev/null || true
# (added) a failed mission must still close the bag and stop the simulator, and must not
# look like a flight: the bag is kept under another name for the post-mortem.
if [ $RC -ne 0 ] || ! grep -q "landed and disarmed" "$LOG.mission.log"; then
  mv -f "$OUT" "${OUT%.bag}.FAILED.bag" 2>/dev/null || true
  echo "!! mission failed -- see $LOG.mission.log and $LOG.sim.log"; exit 1
fi
# (added 20 Nov 2026, reproduction guide) the flight's files go to the owner of the folder they are in:
# written as root, the bag cannot be hard-linked by the host user (fs.protected_hardlinks), and Stage 4's
# run_matrix.sh links the Stage 3 room flight that way. A no-op when the folder belongs to root.
chown --reference="$(dirname "$OUT")" "${OUT%.bag}".* 2>/dev/null || true
echo "wrote $OUT"
