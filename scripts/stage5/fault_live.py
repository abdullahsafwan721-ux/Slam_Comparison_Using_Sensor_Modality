#!/usr/bin/env python3
"""Stage 5: one sensor fault injected LIVE -- the live twin of scripts/stage4/degrade_bag.py.
Runs in a sim-live container (host networking; it has the Livox and MAVROS messages):

    python3 /scripts/stage5/fault_live.py <fault> [--start S]

  lidar_drop_2s, lidar_drop_5s   /livox/lidar -> /livox/lidar_fault, every scan dropped
  cam_black_5s                   /stereo/left/image_raw -> /stereo/left/image_fault, black images

The SLAM method is launched on the *_fault topic (slam_live.sh does that when FAULT is set).
The fault starts S seconds (default 20: mid-square in the room flight) after the vehicle arms
(/mavros/state) and lasts as named; outside it every message passes unchanged. The window is
printed as "FAULT START <t>" / "FAULT END <t>" in simulation time (the scoring reads it).
"""
import argparse

import rospy
from livox_ros_driver.msg import CustomMsg
from mavros_msgs.msg import State
from sensor_msgs.msg import Image

FAULTS = {"lidar_drop_2s": ("lidar", 2.0), "lidar_drop_5s": ("lidar", 5.0), "cam_black_5s": ("cam", 5.0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fault", choices=sorted(FAULTS))
    ap.add_argument("--start", type=float, default=20.0)
    a = ap.parse_args(rospy.myargv()[1:])
    kind, dur = FAULTS[a.fault]
    rospy.init_node("fault_live")
    st = {"t0": None, "started": False, "ended": False, "dropped": 0, "changed": 0}

    def on_state(m):
        if m.armed and st["t0"] is None:
            st["t0"] = rospy.get_time() + a.start
            rospy.loginfo("armed: %s from %.3f to %.3f s", a.fault, st["t0"], st["t0"] + dur)

    def inside(t):
        if st["t0"] is None:
            return False
        on = st["t0"] <= t < st["t0"] + dur
        if on and not st["started"]:
            st["started"] = True
            print("FAULT START %.3f %s" % (t, a.fault), flush=True)
        if not on and st["started"] and not st["ended"] and t >= st["t0"] + dur:
            st["ended"] = True
            print("FAULT END %.3f %s (dropped %d, changed %d)" % (t, a.fault, st["dropped"], st["changed"]), flush=True)
        return on

    rospy.Subscriber("/mavros/state", State, on_state, queue_size=10)
    if kind == "lidar":
        pub = rospy.Publisher("/livox/lidar_fault", CustomMsg, queue_size=20)

        def cb(m):
            if inside(m.header.stamp.to_sec()):
                st["dropped"] += 1
                return
            pub.publish(m)
        rospy.Subscriber("/livox/lidar", CustomMsg, cb, queue_size=20)
    else:
        pub = rospy.Publisher("/stereo/left/image_fault", Image, queue_size=20)

        def cb(m):
            if inside(m.header.stamp.to_sec()):
                m.data = bytes(len(m.data))
                st["changed"] += 1
            pub.publish(m)
        rospy.Subscriber("/stereo/left/image_raw", Image, cb, queue_size=20)
    rospy.loginfo("fault_live: %s, %.1f s, starting %.1f s after arming", a.fault, dur, a.start)
    rospy.spin()


if __name__ == "__main__":
    main()
