#!/usr/bin/env python3
"""Write a copy of a recorded flight bag with ONE sensor fault injected (Stage 4, group E).

    bash /scripts/common/ros_python.sh /scripts/stage4/degrade_bag.py <in.bag> <out.bag> <variant>

Runs INSIDE the eval container (ROS python). Not in the project guide; specified in
docs/eVTOL_SLAM_Research_and_Stage3-5_Plan.pdf, section 5.5 (a). Everything the variant
does not touch is copied message for message (same record times, same stamps), so the
IMU noise that run_all_algos.sh injects afterwards is the same draw as for the clean bag.

Timed faults sit in the middle of the flight window (take-off to touch-down from the
bag's own ground truth, as in verify_sim_bag.py), long after every method initialised;
the window is the same for all algorithms and is written to <out>.fault.json.

  cam_black_5s    both camera images all zero for 5 s (stamps and camera_info kept)
  cam_dim30       every image scaled to 30 % brightness, sensor noise re-added at the
  cam_dim10         simulated camera's own level (rig.yaml camera.noise_stddev), 10 %
  lidar_drop_2s   LiDAR scans removed for 2 s / 5 s
  lidar_drop_5s
  lidar_thin25    every 4th point kept, whole flight (point_num updated): a sparser LiDAR
  cam_dt5         camera stamps (images and camera_info) shifted by +5 / +10 / +20 ms,
  cam_dt10          whole flight; every algorithm is still told the offset is 0. The
  cam_dt20          price of imperfect hardware synchronisation.
"""
import json
import sys

import numpy as np
import rosbag
import rospy
import yaml

CAM = ("/stereo/left/image_raw", "/stereo/right/image_raw")
INFO = ("/stereo/left/camera_info", "/stereo/right/camera_info")
LIDAR = "/livox/lidar"
VARIANTS = {"cam_black_5s": 5.0, "cam_dim30": 0.30, "cam_dim10": 0.10, "lidar_drop_2s": 2.0,
            "lidar_drop_5s": 5.0, "lidar_thin25": 4, "cam_dt5": 0.005, "cam_dt10": 0.010,
            "cam_dt20": 0.020}


def flight_window(bag):
    t, z = [], []
    for _, m, _ in bag.read_messages(topics=["/ground_truth/odom"]):
        t.append(m.header.stamp.to_sec())
        z.append(m.pose.pose.position.z)
    t, z = np.array(t), np.array(z)
    up = z > np.median(z[:200]) + 0.10
    return float(t[np.argmax(up)]), float(t[len(t) - 1 - np.argmax(up[::-1])])


def main():
    inp, out, var = sys.argv[1:4]
    if var not in VARIANTS:
        sys.exit("variant must be one of: " + ", ".join(VARIANTS))
    p = VARIANTS[var]
    noise = yaml.safe_load(open("/config/rig.yaml"))["camera"]["noise_stddev"] * 255.0
    rng = np.random.default_rng(1)
    bi = rosbag.Bag(inp)
    t_to, t_ld = flight_window(bi)
    dur = p if var in ("cam_black_5s", "lidar_drop_2s", "lidar_drop_5s") else None
    if dur:
        mid = 0.5 * (t_to + t_ld)
        w0, w1 = mid - dur / 2.0, mid + dur / 2.0
    else:
        w0, w1 = t_to, t_ld                                    # whole-flight faults: for the record
    n = dict(changed=0, dropped=0, copied=0)
    with rosbag.Bag(out, "w") as bo:
        for topic, m, t in bi.read_messages():
            s = m.header.stamp.to_sec() if hasattr(m, "header") else None
            if var == "cam_black_5s" and topic in CAM and w0 <= s < w1:
                m.data = bytes(len(m.data))
                n["changed"] += 1
            elif var.startswith("cam_dim") and topic in CAM:
                img = np.frombuffer(m.data, np.uint8).astype(np.float64)
                img = img * p + rng.normal(0.0, noise, img.shape)
                m.data = np.clip(np.rint(img), 0, 255).astype(np.uint8).tobytes()
                n["changed"] += 1
            elif var.startswith("lidar_drop") and topic == LIDAR and w0 <= s < w1:
                n["dropped"] += 1
                continue
            elif var == "lidar_thin25" and topic == LIDAR:
                m.points = m.points[::p]
                m.point_num = len(m.points)
                n["changed"] += 1
            elif var.startswith("cam_dt") and topic in CAM + INFO:
                m.header.stamp = m.header.stamp + rospy.Duration.from_sec(p)
                n["changed"] += 1
            else:
                n["copied"] += 1
            bo.write(topic, m, t)
    meta = dict(variant=var, source=inp, take_off_s=t_to, touch_down_s=t_ld,
                fault_start_s=w0, fault_end_s=w1, timed=bool(dur), **n)
    json.dump(meta, open(out.rsplit(".bag", 1)[0] + ".fault.json", "w"), indent=1)
    print("%s: %s -> %s  (%s)" % (var, inp, out, ", ".join("%s %d" % kv for kv in n.items())))


if __name__ == "__main__":
    main()
