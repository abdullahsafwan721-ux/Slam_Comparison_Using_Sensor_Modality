#!/usr/bin/env python3
"""Stage 2 gate: prove the simulated sensors are correct BEFORE any SLAM runs.

    python3 /scripts/stage2/verify_sim_bag.py /output/stage2/scripted_room.bag

Runs inside the sim (or eval) container. Every check prints PASS/FAIL; the
script exits non-zero if any fail. Each check exists because its failure mode
produces plausible-looking but wrong SLAM results rather than an error.
"""
import math
import sys

import numpy as np
import rosbag

G = 9.8066
EXPECT = {"/livox/imu": 200, "/livox/lidar": 10, "/ground_truth/odom": 200,
          "/stereo/left/image_raw": 20, "/stereo/right/image_raw": 20}
fails = 0


def check(ok, what, detail=""):
    global fails
    fails += 0 if ok else 1
    print("%s  %-46s %s" % ("PASS" if ok else "FAIL", what, detail))


def quat_to_R(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def main():
    bag = rosbag.Bag(sys.argv[1])
    info = bag.get_type_and_topic_info().topics
    stamps = {t: [] for t in EXPECT}
    imu, gt, lidar_types = [], [], set()
    left, right = set(), set()
    offsets_nonzero = n_points = n_scans = 0
    for topic, msg, _ in bag.read_messages(topics=list(EXPECT)):
        s = msg.header.stamp.to_sec()
        stamps[topic].append(s)
        if topic == "/livox/imu":
            a, w = msg.linear_acceleration, msg.angular_velocity
            imu.append((s, a.x, a.y, a.z, w.x, w.y, w.z))
        elif topic == "/ground_truth/odom":
            p, q = msg.pose.pose.position, msg.pose.pose.orientation
            gt.append((s, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
        elif topic == "/livox/lidar":
            n_scans += 1
            n_points += msg.point_num
            offsets_nonzero += sum(1 for pt in msg.points if pt.offset_time != 0)
        elif topic == "/stereo/left/image_raw":
            left.add(msg.header.stamp.to_nsec())
        else:
            right.add(msg.header.stamp.to_nsec())

    print("--- topics and rates ---")
    for t, hz in EXPECT.items():
        st = stamps[t]
        rate = (len(st) - 1) / (st[-1] - st[0]) if len(st) > 2 else 0.0
        check(abs(rate - hz) / hz < 0.1, "%s at ~%d Hz" % (t, hz), "measured %.1f Hz" % rate)

    print("--- LiDAR ---")
    lt = info.get("/livox/lidar")
    check(lt is not None and lt.msg_type == "livox_ros_driver/CustomMsg",
          "message type livox_ros_driver/CustomMsg", lt.msg_type if lt else "missing")
    check(n_scans and 15000 < n_points / n_scans < 21000, "~20000 points per scan",
          "%.0f" % (n_points / max(n_scans, 1)))
    check(offsets_nonzero == 0, "every per-point offset_time == 0",
          "%d non-zero (patch 1 missing?)" % offsets_nonzero)

    print("--- cameras ---")
    check(len(left) > 0 and left == right, "left/right stamps identical", "%d pairs" % len(left & right))

    print("--- IMU vs ground truth (the real test) ---")
    imu, gt = np.array(imu), np.array(gt)
    hold = imu[imu[:, 0] < imu[0, 0] + 5.0]            # first 5 s: stationary
    g_norm = np.linalg.norm(hold[:, 1:4], axis=1).mean()
    check(abs(g_norm - G) < 0.05, "|accel| at rest == g", "%.4f m/s^2" % g_norm)
    check(np.abs(hold[:, 4:7]).max() < 1e-3, "gyro at rest == 0", "max %.2e rad/s" % np.abs(hold[:, 4:7]).max())
    # Specific force predicted from ground-truth kinematics: f = R^T (a - g).
    t, p = gt[:, 0], gt[:, 1:4]
    dt = np.gradient(t)
    acc = np.gradient(np.gradient(p, axis=0) / dt[:, None], axis=0) / dt[:, None]
    errs = []
    for row in imu[::10]:
        k = np.searchsorted(t, row[0])
        if 2 < k < len(t) - 2 and abs(t[k] - row[0]) < 0.003:
            R = quat_to_R(*gt[k, 4:8])
            f_pred = R.T @ (acc[k] - np.array([0.0, 0.0, -G]))
            errs.append(np.linalg.norm(f_pred - row[1:4]))
    rms = math.sqrt(np.mean(np.square(errs))) if errs else float("inf")
    check(rms < 0.15, "IMU accel matches GT kinematics", "RMS diff %.3f m/s^2 over %d samples" % (rms, len(errs)))
    span = np.ptp(p, axis=0)
    check(span.max() > 1.0, "rig actually moved", "extent xyz = %s m" % np.round(span, 2))

    print("\n%s" % ("ALL CHECKS PASSED -- Stage 2 gate open." if fails == 0 else "%d CHECK(S) FAILED." % fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
