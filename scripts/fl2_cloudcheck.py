#!/usr/bin/env python3
"""Inspect the first point clouds on a topic and report the per-point time unit.
    fl2_cloudcheck.py <bag> <topic> [n_clouds=20]
FAST-LIO multiplies the 'time' field by a factor chosen by preprocess/timestamp_unit
(0 s, 1 ms, 2 us, 3 ns) to get milliseconds. A wrong unit silently disables or
over-applies motion de-skew, so check this on every bag before its first run.
For a 10 Hz spinning LiDAR the within-scan time spread is ~0.1 s; the spread
observed here decides the unit. Livox CustomMsg topics are reported as such."""
import os, sys
try:
    import rosbag, sensor_msgs.point_cloud2 as pc2
except ImportError:   # eval container: venv python has no ROS -> re-run with system python + ROS
    if os.environ.get("FL2_REEXEC"): raise
    os.environ.update(FL2_REEXEC="1", PYTHONPATH="/opt/ros/noetic/lib/python3/dist-packages")
    os.execv("/usr/bin/python3", ["/usr/bin/python3"] + sys.argv)
if len(sys.argv) < 3: sys.exit(__doc__)
bag, topic = sys.argv[1:3]; n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
spreads, seen = [], 0
with rosbag.Bag(bag) as b:
    for _, m, _ in b.read_messages(topics=[topic]):
        if m._type == "livox_ros_driver/CustomMsg":
            ot = [p.offset_time for p in m.points]
            print("Livox CustomMsg: %d points, offset_time %d..%d ns (lidar_type 1, unit not used)"
                  % (len(ot), min(ot), max(ot))); sys.exit(0)
        if seen == 0:
            print("fields:", ", ".join("%s(%d)" % (f.name, f.datatype) for f in m.fields))
            print("frame_id: %s   points/cloud: %d" % (m.header.frame_id, m.width * m.height))
        names = [f.name for f in m.fields]
        tf = next((t for t in ("time", "t", "timestamp", "offset_time") if t in names), None)
        if tf is None: print("!! no per-point time field -> FAST-LIO reconstructs time from azimuth (scan_rate matters)"); sys.exit(0)
        ts = [p[0] for p in pc2.read_points(m, field_names=(tf,), skip_nans=True)]
        spreads.append(max(ts) - min(ts)); seen += 1
        if seen >= n: break
if not spreads: sys.exit("!! no messages on %s" % topic)
s = sorted(spreads)[len(spreads)//2]
print("time field '%s': median within-scan spread %.6g over %d clouds" % (tf, s, len(spreads)))
for unit, name, nominal in ((0, "s", 0.1), (1, "ms", 100), (2, "us", 1e5), (3, "ns", 1e8)):
    if nominal / 10 < s < nominal * 10:
        print("=> per-point time is in %s  ->  timestamp_unit: %d" % (name, unit)); break
else:
    print("!! spread does not match a 10 Hz scan in any unit -- inspect manually")
