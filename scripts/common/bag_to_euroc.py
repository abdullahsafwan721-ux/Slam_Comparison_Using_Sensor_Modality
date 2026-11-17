#!/usr/bin/env python3
"""Convert a simulation bag into the EuRoC ASL folder layout, so ORB-SLAM3 runs
through the SAME standalone stereo_inertial_euroc binary validated in Stage 1
(no ROS wrapper, no new unknown).

    python3 bag_to_euroc.py <bag> <outdir> [left] [right] [imu]

Writes  <outdir>/mav0/cam0/data/<ns>.png, cam0/data.csv, cam1/..., imu0/data.csv
and     <outdir>/times.txt   (one ns timestamp per stereo pair, ORB-SLAM3's format)
"""
import os
import sys

import cv2
import rosbag
from cv_bridge import CvBridge


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    bag, out = sys.argv[1], sys.argv[2]
    left = sys.argv[3] if len(sys.argv) > 3 else "/stereo/left/image_raw"
    right = sys.argv[4] if len(sys.argv) > 4 else "/stereo/right/image_raw"
    imu = sys.argv[5] if len(sys.argv) > 5 else "/livox/imu"
    br = CvBridge()
    for d in ("cam0/data", "cam1/data", "imu0"):
        os.makedirs(os.path.join(out, "mav0", d), exist_ok=True)

    imgs = {left: {}, right: {}}
    n_imu = 0
    with rosbag.Bag(bag) as b, open(os.path.join(out, "mav0/imu0/data.csv"), "w") as fi:
        fi.write("#timestamp [ns],w_RS_S_x [rad s^-1],w_RS_S_y [rad s^-1],w_RS_S_z [rad s^-1],"
                 "a_RS_S_x [m s^-2],a_RS_S_y [m s^-2],a_RS_S_z [m s^-2]\n")
        for topic, msg, _ in b.read_messages(topics=[left, right, imu]):
            ns = msg.header.stamp.to_nsec()
            if topic == imu:
                w, a = msg.angular_velocity, msg.linear_acceleration
                fi.write("%d,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f\n" % (ns, w.x, w.y, w.z, a.x, a.y, a.z))
                n_imu += 1
            else:
                cam = "cam0" if topic == left else "cam1"
                img = br.imgmsg_to_cv2(msg, desired_encoding="mono8")
                cv2.imwrite(os.path.join(out, "mav0", cam, "data", "%d.png" % ns), img)
                imgs[topic][ns] = True

    # Only frames where BOTH cameras have an image with the identical stamp.
    pairs = sorted(set(imgs[left]) & set(imgs[right]))
    for cam, topic in (("cam0", left), ("cam1", right)):
        with open(os.path.join(out, "mav0", cam, "data.csv"), "w") as f:
            f.write("#timestamp [ns],filename\n")
            for ns in pairs:
                f.write("%d,%d.png\n" % (ns, ns))
    with open(os.path.join(out, "times.txt"), "w") as f:
        f.write("".join("%d\n" % ns for ns in pairs))
    print("stereo pairs: %d   imu samples: %d   -> %s" % (len(pairs), n_imu, out))
    if not pairs or n_imu == 0:
        sys.exit("!! empty conversion -- check topic names with rosbag info")


if __name__ == "__main__":
    main()
