#!/usr/bin/env python3
"""Odometry bag -> TUM trajectory.   fl2_traj.py <bag> <topic> <out.tum>
Uses the message HEADER stamp (capture time), never the bag's receive time."""
import os, sys
try:
    import rosbag
except ImportError:   # eval container: venv python has no ROS -> re-run with system python + ROS
    if os.environ.get("FL2_REEXEC"): raise
    os.environ.update(FL2_REEXEC="1", PYTHONPATH="/opt/ros/noetic/lib/python3/dist-packages")
    os.execv("/usr/bin/python3", ["/usr/bin/python3"] + sys.argv)
if len(sys.argv) != 4: sys.exit(__doc__)
bag, topic, out = sys.argv[1:]
n = 0
with rosbag.Bag(bag) as b, open(out, "w") as f:
    for _, m, _ in b.read_messages(topics=[topic]):
        p = m.pose.pose if hasattr(m.pose, "pose") else m.pose
        f.write("%.9f %.9f %.9f %.9f %.9f %.9f %.9f %.9f\n" % (
            m.header.stamp.to_sec(), p.position.x, p.position.y, p.position.z,
            p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w))
        n += 1
if n == 0: sys.exit("!! no messages on %s" % topic)
print("%d poses -> %s" % (n, out))
