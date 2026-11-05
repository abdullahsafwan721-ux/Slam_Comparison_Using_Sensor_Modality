#!/usr/bin/env python3
"""Extract one pose topic from a bag as a TUM trajectory (t x y z qx qy qz qw).

    python3 bag_to_tum.py <bag> <topic> <out.txt>

Handles nav_msgs/Odometry, geometry_msgs/PoseStamped and
PoseWithCovarianceStamped. Uses the message HEADER stamp (when the data was
captured), never the bag's receive time.
"""
import sys
import rosbag


def pose_of(msg):
    p = getattr(msg, "pose", None)
    if hasattr(p, "pose"):          # Odometry / PoseWithCovarianceStamped
        p = p.pose
    return p
def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    bag, topic, out = sys.argv[1:]
    n = 0
    with rosbag.Bag(bag) as b, open(out, "w") as f:
        for _, msg, _ in b.read_messages(topics=[topic]):
            p = pose_of(msg)
            t = msg.header.stamp.to_sec()
            f.write("%.9f %.9f %.9f %.9f %.9f %.9f %.9f %.9f\n" % (
                t, p.position.x, p.position.y, p.position.z,
                p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w))
            n += 1
    if n == 0:
        sys.exit("!! no messages on %s in %s" % (topic, bag))
    print("%s: %d poses -> %s" % (topic, n, out))


if __name__ == "__main__":
    main()
