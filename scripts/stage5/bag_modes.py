#!/usr/bin/env python3
"""PX4's flight-mode and arming changes in a Stage 5 flight bag (eval container, through
ros_python.sh: the eval image's python3 has no rosbag):

    bash /scripts/common/ros_python.sh /scripts/stage5/bag_modes.py <flight.bag> <out.txt>

Writes one line per change of /mavros/state: "<bag time s> <mode> <armed 0|1>". In a fault test
this is what PX4 *did* when SLAM paused (stayed in OFFBOARD, or switched to a failsafe mode).
"""
import sys

import rosbag


def main():
    bag, out = sys.argv[1], sys.argv[2]
    last = None
    lines = []
    with rosbag.Bag(bag) as b:
        for _, m, t in b.read_messages(topics=["/mavros/state"]):
            key = (m.mode, int(m.armed))
            if key != last:
                lines.append("%.3f %s %d" % (t.to_sec(), m.mode or "(none)", int(m.armed)))   # MAVROS sends "" for a mode it cannot name
                last = key
    open(out, "w").write("\n".join(lines) + "\n")
    print("%s: %d mode/arming changes -> %s" % (bag, len(lines), out))


if __name__ == "__main__":
    main()
