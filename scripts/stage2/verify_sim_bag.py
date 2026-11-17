#!/usr/bin/env python3
"""Stage 2 gate: prove the simulated sensors are correct BEFORE any SLAM runs.

    python3 /scripts/stage2/verify_sim_bag.py /output/stage2/scripted_room.bag
    python3 /scripts/stage2/verify_sim_bag.py /output/stage3/flights/room_square.bag --flight

Runs inside the sim (or eval) container. Every check prints PASS/FAIL; the
script exits non-zero if any fail. Each check exists because its failure mode
produces plausible-looking but wrong SLAM results rather than an error.

--flight (added in Stage 3, not in the guide) is for PX4 flight bags. The kinematics
check double-differentiates the 200 Hz ground-truth position; on a real vehicle model
(250 Hz motor commands, 1 kHz physics, a touch-down impact) that amplifies content the
smooth scripted path never had, and a correct bag fails it (1.1 m/s^2 RMS on the first
flight). What an estimator needs is that the IMU INTEGRATES to the true motion, so
--flight tests that instead: the velocity change over 0.1 s windows from the IMU
(rotated by the true attitude, gravity removed) against the ground-truth velocity. It
also checks what only a flight can get wrong: camera frame intervals (PX4 runs Gazebo
in lockstep), the stationary hold before take-off, and that the vehicle landed.
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
    flight = "--flight" in sys.argv[2:]
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
            v = msg.twist.twist.linear                  # gazebo_ros_p3d: world frame
            gt.append((s, p.x, p.y, p.z, q.x, q.y, q.z, q.w, v.x, v.y, v.z))
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
    # Predict f at every GT sample, then interpolate to each IMU stamp. (The guide
    # paired each IMU sample with the NEXT GT sample within 3 ms; IMU and GT both run
    # at 200 Hz with a start-up phase of 0-4 ms, so at a 3-4 ms phase few or no
    # samples matched and a correct bag could fail -- see docs/stage2_log.md.)
    f_gt = np.array([quat_to_R(*gt[k, 4:8]).T @ (acc[k] - np.array([0.0, 0.0, -G]))
                     for k in range(len(t))])
    errs = []
    for row in imu[::10]:
        if t[2] < row[0] < t[-3]:                      # skip the finite-difference edges
            f_pred = np.array([np.interp(row[0], t, f_gt[:, j]) for j in range(3)])
            errs.append(np.linalg.norm(f_pred - row[1:4]))
    rms = math.sqrt(np.mean(np.square(errs))) if errs else float("inf")
    if not flight:
        check(rms < 0.15, "IMU accel matches GT kinematics", "RMS diff %.3f m/s^2 over %d samples" % (rms, len(errs)))
    else:
        # velocity change over 0.1 s windows: integral of R f + g against ground truth
        k = np.clip(np.searchsorted(t, imu[:, 0]), 0, len(t) - 1)
        a_w = np.array([quat_to_R(*gt[j, 4:8]) @ row[1:4] for j, row in zip(k, imu)]) + np.array([0.0, 0.0, -G])
        d = np.gradient(imu[:, 0])
        v_gt = np.array([np.interp(imu[:, 0], t, gt[:, 8 + j]) for j in range(3)]).T
        n = 20
        dv = [np.linalg.norm((a_w[i:i + n] * d[i:i + n, None]).sum(0) - (v_gt[i + n] - v_gt[i]))
              for i in range(0, len(imu) - n, n)]
        rms_dv = math.sqrt(np.mean(np.square(dv)))
        check(rms_dv < 0.01, "IMU integrates to GT velocity (0.1 s)",
              "RMS %.4f m/s, worst %.4f m/s over %d windows  (double-difference check: %.2f m/s^2, informative)"
              % (rms_dv, max(dv), len(dv), rms))
    span = np.ptp(p, axis=0)
    check(span.max() > 1.0, "rig actually moved", "extent xyz = %s m" % np.round(span, 2))
    if flight:
        print("--- flight ---")
        z0 = np.median(p[:200, 2])
        up = p[:, 2] > z0 + 0.10
        t_to, t_ld = t[np.argmax(up)], t[len(t) - 1 - np.argmax(up[::-1])]
        check(up.any() and t_to - t[0] >= 5.0, "stationary hold before take-off >= 5 s",
              "%.1f s (take-off at %.1f s, touch-down at %.1f s)" % (t_to - t[0], t_to, t_ld))
        end = p[-1] - p[0]
        check(abs(end[2]) < 0.15 and t[-1] - t_ld > 1.0, "landed (back on the ground at the end)",
              "end minus start xyz = %s m, max height %.2f m" % (np.round(end, 2), p[:, 2].max() - z0))
        iv = np.diff(sorted(left))  * 1e-9
        check(len(iv) > 0 and iv.min() > 0.040 and iv.max() < 0.065, "camera frame intervals 40-65 ms",
              "min %.1f ms, max %.1f ms, %d outside" % (iv.min() * 1e3, iv.max() * 1e3,
                                                        int(((iv <= 0.040) | (iv >= 0.065)).sum())))
        lv = np.diff(stamps["/livox/lidar"])
        check(lv.min() > 0.090 and lv.max() < 0.110, "LiDAR scan intervals 90-110 ms",
              "min %.1f ms, max %.1f ms" % (lv.min() * 1e3, lv.max() * 1e3))

    print("\n%s" % ("ALL CHECKS PASSED -- %s." % ("flight bag is sound" if flight else "Stage 2 gate open") if fails == 0 else "%d CHECK(S) FAILED." % fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
