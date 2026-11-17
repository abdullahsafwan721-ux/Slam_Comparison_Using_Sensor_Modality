#!/usr/bin/env python3
"""Fly a repeatable profile in PX4 OFFBOARD mode through MAVROS.

    python3 offboard_mission.py <profile> [--alt 1.5] [--speed 2] [--size 6] [--laps 2]
                                          [--yaw fixed|tangent] [--hop 0.4] [--sitl-params]

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
    ap.add_argument("--sitl-params", action="store_true")
    a = ap.parse_args(rospy.myargv()[1:])

    rospy.init_node("offboard_mission")
    rospy.Subscriber("/mavros/state", State, on_state)
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

    climb = a.alt / 1.0                                    # 1 m/s climb
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
    while not rospy.is_shutdown():
        t = (rospy.Time.now() - start).to_sec()
        if t < climb + 2.0:                                # climb above the start point
            x, y, z = x0, y0, min(a.alt, a.alt * t / climb)
        elif a.hop > 0 and t < climb + 2.0 + 3.0:          # initialisation hop: up 1 s, back 2 s
            x, y, z = x0, y0, a.alt + (a.hop if t < climb + 3.0 else 0.0)
        else:
            tc = t - climb - 2.0 - (3.0 if a.hop > 0 else 0.0)
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
