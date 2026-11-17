#!/usr/bin/env python3
"""Stage 3 diagnostic A7 (not in the guide): thin the stereo stream so that every image
has a LiDAR scan before it, i.e. 20 Hz camera -> ~10 Hz, locked to the 10 Hz LiDAR.

    bash /scripts/common/ros_python.sh /scripts/stage3/thin_camera.py <in.bag> <out.bag>

Why: FAST-LIVO2 cuts the LiDAR stream at each image time. With all points of a simulated
scan sharing one stamp (offset_time 0), every second 20 Hz image gets no new points and
only propagates (docs/stage1_2_audit.md, item 3). If that interleaving causes its higher
drift, FAST-LIVO2 on this bag should drift less. A stereo pair (and its camera_info) is
kept only if a LiDAR scan was stamped after the previously kept image; every other topic
is copied unchanged.
"""
import bisect
import sys

import rosbag

LIDAR = "/livox/lidar"
CAMS = ("/stereo/left/", "/stereo/right/")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1:]
    with rosbag.Bag(src) as b:
        scans = sorted(m.header.stamp.to_sec() for _, m, _ in b.read_messages(topics=[LIDAR]))
        img = sorted({m.header.stamp.to_nsec() for _, m, _ in
                      b.read_messages(topics=["/stereo/left/image_raw"])})
    keep, last = set(), -1.0
    for ns in img:
        t = ns * 1e-9
        i = bisect.bisect_right(scans, last)       # first scan after the last kept image
        if i < len(scans) and scans[i] <= t:
            keep.add(ns)
            last = t
    n_in = n_out = 0
    with rosbag.Bag(src) as b, rosbag.Bag(dst, "w") as o:
        for topic, msg, t in b.read_messages():
            if topic.startswith(CAMS):
                n_in += 1
                if msg.header.stamp.to_nsec() not in keep:
                    continue
                n_out += 1
            o.write(topic, msg, t)
    print("stereo pairs %d -> %d kept (%.1f Hz); camera messages %d -> %d -> %s"
          % (len(img), len(keep), len(keep) / ((img[-1] - img[0]) * 1e-9), n_in, n_out, dst))


if __name__ == "__main__":
    main()
