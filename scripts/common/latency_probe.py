#!/usr/bin/env python3
"""Record processing latency of an odometry topic during bag replay.

    python3 latency_probe.py <topic> <out.csv>

latency = (clock when the message arrives) - (message header stamp).
With `rosbag play --clock --hz=1000` the clock is bag time at 1 ms resolution,
so this is how long the algorithm took from data capture to publishing a pose.
"""
import sys

import rospy
from nav_msgs.msg import Odometry

rows = []


def cb(msg):
    rows.append((msg.header.stamp.to_sec(), (rospy.Time.now() - msg.header.stamp).to_sec() * 1e3))


def main():
    topic, out = sys.argv[1], sys.argv[2]
    rospy.init_node("latency_probe", anonymous=True, disable_signals=False)
    rospy.Subscriber(topic, Odometry, cb, queue_size=1000)
    rospy.spin()
    with open(out, "w") as f:
        f.write("stamp_s,latency_ms\n")
        f.writelines("%.6f,%.3f\n" % r for r in rows)
    if rows:
        lat = sorted(r[1] for r in rows)
        print("latency ms: median %.1f  p95 %.1f  max %.1f  (n=%d)" % (
            lat[len(lat) // 2], lat[int(len(lat) * 0.95)], lat[-1], len(lat)))


if __name__ == "__main__":
    main()
