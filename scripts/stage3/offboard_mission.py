#!/usr/bin/env python3
"""Fly a repeatable profile in PX4 OFFBOARD mode through MAVROS.

    python3 offboard_mission.py <profile> [--alt 1.5] [--speed 2] [--size 6] [--laps 2]
                                          [--yaw fixed|tangent] [--hop 0.4] [--hop-alt A]
                                          [--sitl-params]

profiles
  hover    take off, hold 30 s, land
  square   square of side --size, --laps times (one corner at the take-off point,
           extending towards +x and +y)
  figure8  lemniscate of half-width --size, --laps times
  line     straight out --size metres along +x and back (corridor)

Every setpoint is a smooth function of time, so the same command produces the
same flight -- that is what makes Stage 4's conditions comparable.

--hop H (Stage 3 addition, not in the guide; default 0.4 m, 0 disables): after the climb
the altitude setpoint steps up by H for 1 s and back, before the profile starts. It is an
initialisation manoeuvre, flown in every flight so every algorithm gets the same data.
ORB-SLAM3's stereo-inertial initialisation only starts once the mean accelerometer reading
changes by >= 0.5 m/s^2 between two consecutive frames (Tracking.cc, "not enough
acceleration"); a multirotor following smooth setpoints never produces that, and on the
first Stage 3 flight ORB-SLAM3 never started. A thrust step does.

--hop-alt A (Stage 4 option; default: the cruise altitude, as in Stage 3): fly the hop at
min(--alt, A) on the way up instead. Tried at 1.5 m and rejected: over the urban plaza the
downward-looking camera sees dark, uniform paving (~320 ORB features at 1.9 m, ORB-SLAM3
needs > 500), so a hop there cannot start ORB-SLAM3; at cruise altitude the buildings are
in view (600-1200 features).
Stage 4 fix: the hop waits for the vehicle. PX4 lifts off ~3 s after arming, and a hop
timed only from arming fell inside the take-off transient at 1.5 m (no step in the ground
truth). The hop now starts 3 s after the MEASURED height (/mavros/local_position/pose) first
reaches hop height - 0.05 m, and the vehicle gets 3 s to settle back before going on.
Coordinates are MAVROS local ENU, origin at the take-off point.
--sitl-params sets the parameters that let SITL arm and stay in OFFBOARD
without an RC transmitter. NEVER use it on a real vehicle.
"""
import argparse
import math
import sys

import rospy
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import ParamValue, State
from mavros_msgs.srv import CommandBool, ParamSet, SetMode

state = State()
z_now = None


def on_pose(m):
    global z_now
    z_now = m.pose.position.z


def on_state(m):
    global state
    state = m


def path(profile, s, size):
    """Horizontal position after travelling arc length s along the profile."""
    if profile == "hover":
        return 0.0, 0.0
    if profile == "line":
        per = 2 * size
        u = s % per
        return (u if u < size else per - u), 0.0
    if profile == "square":
        per = 4 * size
        u = s % per
        h = size / 2.0
        if u < size:
            return -h + u, -h
        if u < 2 * size:
            return h, -h + (u - size)
        if u < 3 * size:
            return h - (u - 2 * size), h
        return -h, h - (u - 3 * size)
    if profile == "figure8":                    # lemniscate of Gerono, param by angle
        per = 6.1 * size                        # approx. arc length of one loop
        th = 2 * math.pi * (s % per) / per
        return size * math.sin(th), size * math.sin(th) * math.cos(th)
    raise ValueError(profile)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", choices=["hover", "square", "figure8", "line"])
    ap.add_argument("--alt", type=float, default=1.5)
    ap.add_argument("--speed", type=float, default=2.0)
    ap.add_argument("--size", type=float, default=6.0)
    ap.add_argument("--laps", type=float, default=2.0)
    ap.add_argument("--yaw", choices=["fixed", "tangent"], default="fixed")
    ap.add_argument("--hop", type=float, default=0.4)
    ap.add_argument("--hop-alt", type=float, default=None)
    ap.add_argument("--sitl-params", action="store_true")
    a = ap.parse_args(rospy.myargv()[1:])

    rospy.init_node("offboard_mission")
    rospy.Subscriber("/mavros/state", State, on_state)
    rospy.Subscriber("/mavros/local_position/pose", PoseStamped, on_pose)
    pub = rospy.Publisher("/mavros/setpoint_position/local", PoseStamped, queue_size=10)
    for srv in ("/mavros/cmd/arming", "/mavros/set_mode", "/mavros/param/set"):
        rospy.wait_for_service(srv, timeout=120)
    arm = rospy.ServiceProxy("/mavros/cmd/arming", CommandBool)
    mode = rospy.ServiceProxy("/mavros/set_mode", SetMode)
    pset = rospy.ServiceProxy("/mavros/param/set", ParamSet)
    rate = rospy.Rate(30)
    while not rospy.is_shutdown() and not state.connected:
        rate.sleep()
    rospy.loginfo("FCU connected")

    if a.sitl_params:
        for pid, val in (("COM_RCL_EXCEPT", 4), ("NAV_RCL_ACT", 0),
                         ("NAV_DLL_ACT", 0), ("COM_RC_IN_MODE", 4)):
            # Stage 3 fix (not in the guide): right after "FCU connected" MAVROS is still
            # downloading PX4's parameter list and param/set fails ("PR: receiving not
            # complete", a ServiceException). Retry for up to 60 s.
            ok = False
            for _ in range(60):
                try:
                    ok = pset(param_id=pid, value=ParamValue(integer=val, real=0.0)).success
                except rospy.ServiceException:
                    ok = False
                if ok or rospy.is_shutdown():
                    break
                rospy.sleep(1.0)
            rospy.loginfo("param %s = %d  %s", pid, val, "ok" if ok else "FAILED")
            if not ok:
                sys.exit("!! could not set %s -- PX4 would refuse OFFBOARD without RC" % pid)

    sp = PoseStamped()
    sp.header.frame_id = "map"

    def send(x, y, z, yaw):
        sp.header.stamp = rospy.Time.now()
        sp.pose.position.x, sp.pose.position.y, sp.pose.position.z = x, y, z
        sp.pose.orientation.z, sp.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        pub.publish(sp)

    # PX4 rejects OFFBOARD unless setpoints are already streaming.
    for _ in range(60):
        send(0, 0, 0, 0)
        rate.sleep()
    t0 = rospy.Time.now()
    while not rospy.is_shutdown() and not (state.mode == "OFFBOARD" and state.armed):
        if (rospy.Time.now() - t0).to_sec() > 90:
            sys.exit("!! could not arm/enter OFFBOARD in 90 s -- check the PX4 console for the preflight failure")
        if state.mode != "OFFBOARD":
            mode(custom_mode="OFFBOARD")
        elif not state.armed:
            arm(True)
        send(0, 0, 0, 0)
        for _ in range(30):
            rate.sleep()
    rospy.loginfo("armed, OFFBOARD")

    h1 = min(a.alt, a.hop_alt) if (a.hop > 0 and a.hop_alt) else a.alt   # height of the first leg of the climb
    climb = h1 / 1.0                                       # 1 m/s climb
    climb2 = (a.alt - h1) / 1.0                            # rest of the climb, after the hop
    total = a.laps * {"hover": 0, "line": 2 * a.size, "square": 4 * a.size,
                      "figure8": 6.1 * a.size}[a.profile]
    cruise = 30.0 if a.profile == "hover" else total / a.speed
    ramp = 3.0                                             # speed ramp, seconds
    start = rospy.Time.now()
    # Stage 3 change (not in the guide): the profile is shifted so that it STARTS above the
    # take-off point. The guide climbed above path(0), which for the square is the corner
    # (-size/2, -size/2): a diagonal dash of size/sqrt(2) m while still near the ground,
    # through the room's clutter, and a landing on that corner instead of the take-off spot.
    ox, oy = path(a.profile, 0.0, a.size)
    x0, y0 = 0.0, 0.0
    last = (x0, y0)
    yaw = 0.0
    hop_start = None if a.hop > 0 else climb + 2.0         # set once the vehicle is at h1
    reached = None
    while not rospy.is_shutdown():
        t = (rospy.Time.now() - start).to_sec()
        if hop_start is None:
            if reached is None and z_now is not None and z_now >= h1 - 0.05:
                reached = t
                rospy.loginfo("at hop height %.2f m after %.1f s", z_now, t)
            if reached is not None and t >= max(climb + 2.0, reached + 3.0):
                hop_start = t
                rospy.loginfo("hop %.2f m at %.1f s", a.hop, t)
            elif t > climb + 30.0:
                sys.exit("!! vehicle never reached the hop height %.2f m" % h1)
        hs = hop_start if hop_start is not None else 1e9
        hop_end = hs + (4.0 if a.hop > 0 else 0.0)
        rest = climb2 + 2.0 if climb2 > 0 else 0.0         # second leg + 2 s settle, if any
        if t < hs:                                         # climb above the start point, hold
            x, y, z = x0, y0, min(h1, h1 * t / climb)
        elif a.hop > 0 and t < hop_end:                    # initialisation hop: up 1 s, back 3 s
            x, y, z = x0, y0, h1 + (a.hop if t < hs + 1.0 else 0.0)
        elif t < hop_end + rest:                           # rest of the climb, 1 m/s
            x, y, z = x0, y0, min(a.alt, h1 + (t - hop_end))
        else:
            tc = t - hop_end - rest
            if tc > cruise + ramp:
                break
            # distance travelled with a linear speed ramp in and out
            s = a.speed * (tc - ramp / 2.0) if tc > ramp else a.speed * tc * tc / (2 * ramp)
            s = min(max(s, 0.0), total)
            x, y = path(a.profile, s, a.size)
            x, y = x - ox, y - oy
            z = a.alt
            if a.yaw == "tangent" and math.hypot(x - last[0], y - last[1]) > 0.02:
                yaw = math.atan2(y - last[1], x - last[0])
            last = (x, y)
        send(x, y, z, yaw)
        rate.sleep()

    rospy.loginfo("profile done, landing")
    mode(custom_mode="AUTO.LAND")
    t0 = rospy.Time.now()
    while not rospy.is_shutdown() and state.armed and (rospy.Time.now() - t0).to_sec() < 120:
        rate.sleep()
    rospy.loginfo("landed and disarmed" if not state.armed else "!! still armed after 120 s")


if __name__ == "__main__":
    main()
