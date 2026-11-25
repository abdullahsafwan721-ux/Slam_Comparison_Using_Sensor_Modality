#!/usr/bin/env bash
# Slow a running Gazebo down to a fixed real-time factor, from the HOST, as soon as it is up:
#   bash scripts/tools/sim_rtf.sh <container name | pattern of its command> <rtf> [timeout s]
#   bash scripts/tools/sim_rtf.sh px4_record.sh 0.35 &          # alongside a recording
# Why: Gazebo renders the stereo cameras on the GPU. When the GPU is saturated by another job,
# rendering cannot keep up with real time and frames are dropped (measured 18 Nov 2026 with the
# GPU at 100 % from unrelated training jobs: 13-17 Hz instead of 20 Hz). Every sensor message
# carries SIMULATION time, so a slower simulation yields the same data while giving the renderer
# more wall time per frame. The worlds step physics at 1 ms; the real-time update rate is set to
# rtf x 1000 Hz through gazebo_ros's /gazebo/set_physics_properties, which takes the current step,
# gravity and ODE settings back unchanged. (Gazebo's own `gz physics`/`gz stats` did not reach the
# server under load: on 18 Nov they timed out while ROS answered.) PX4 SITL runs in lockstep and
# follows. Prints the measured real-time factor; exit 0 only when it is within 0.1 of the target.
PAT=$1; RTF=$2; TMO=${3:-300}
HZ=$(python3 -c "print(round(float('$RTF') * 1000.0, 3))")
SECONDS=0; CID=
while [ -z "$CID" ]; do
  CID=$(docker ps --filter "name=^${PAT}$" --format '{{.ID}}' | head -1)
  [ -z "$CID" ] && CID=$(docker ps --no-trunc --format '{{.ID}} {{.Command}}' | grep -F -- "$PAT" | cut -d' ' -f1 | head -1)
  [ $SECONDS -ge "$TMO" ] && { echo "sim_rtf: no container matching '$PAT' after $TMO s"; exit 1; }
  [ -z "$CID" ] && sleep 0.5
done
LEFT=$((TMO - SECONDS)); [ $LEFT -lt 30 ] && LEFT=30
docker exec -i "$CID" bash -c "source /opt/ros/noetic/setup.bash >/dev/null 2>&1; python3 - $HZ $RTF $LEFT" <<'EOF'
import sys, time
import rospy
from gazebo_msgs.srv import GetPhysicsProperties, SetPhysicsProperties, GetWorldProperties
hz, rtf, tmo = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
t0 = time.time()
while True:                                   # gazebo_ros up (its services exist once the world runs)
    try:
        rospy.wait_for_service("/gazebo/set_physics_properties", timeout=2)
        break
    except Exception:
        if time.time() - t0 > tmo:
            print("sim_rtf: /gazebo/set_physics_properties did not appear within %.0f s" % tmo); sys.exit(1)
get = rospy.ServiceProxy("/gazebo/get_physics_properties", GetPhysicsProperties)
put = rospy.ServiceProxy("/gazebo/set_physics_properties", SetPhysicsProperties)
world = rospy.ServiceProxy("/gazebo/get_world_properties", GetWorldProperties)
g = get()
r = put(g.time_step, hz, g.gravity, g.ode_config)
g2 = get()
a = (time.time(), world().sim_time); time.sleep(4.0); b = (time.time(), world().sim_time)
m = (b[1] - a[1]) / (b[0] - a[0])
print("sim_rtf: %s set max_update_rate %.0f -> %.0f Hz (step %.4f s, gravity z %.4f, ok=%s); measured RTF %.2f (target %.2f), %.0f s after the start"
      % (time.strftime("%H:%M:%S"), g.max_update_rate, g2.max_update_rate, g2.time_step, g2.gravity.z, r.success, m, rtf, time.time() - t0))
sys.exit(0 if r.success and abs(m - rtf) <= 0.1 else 1)
EOF
