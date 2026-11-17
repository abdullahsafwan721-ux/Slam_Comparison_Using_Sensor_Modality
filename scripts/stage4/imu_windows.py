#!/usr/bin/env python3
"""Where does a flight bag's IMU stop integrating to the ground-truth velocity?
Runs INSIDE the sim container (ROS python):  python3 imu_windows.py <bag> [n_worst=12]
Diagnostic for verify_sim_bag.py --flight's "IMU integrates to GT velocity" check: prints
the IMU stamp gaps, the worst 0.1 s windows with their time and height, and the error
per flight phase (ground before take-off, air, ground after touch-down).
"""
import sys
import numpy as np
import rosbag

G = 9.8066


def R(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


imu, gt = [], []
for topic, m, _ in rosbag.Bag(sys.argv[1]).read_messages(topics=["/livox/imu", "/ground_truth/odom"]):
    s = m.header.stamp.to_sec()
    if topic == "/livox/imu":
        a = m.linear_acceleration
        imu.append((s, a.x, a.y, a.z))
    else:
        p, q, v = m.pose.pose.position, m.pose.pose.orientation, m.twist.twist.linear
        gt.append((s, p.x, p.y, p.z, q.x, q.y, q.z, q.w, v.x, v.y, v.z))
imu, gt = np.array(imu), np.array(gt)
t = gt[:, 0]
di = np.diff(imu[:, 0])
print("IMU %d samples, gaps: min %.4f median %.4f max %.4f s, %d gaps > 7.5 ms, %d repeated stamps"
      % (len(imu), di.min(), np.median(di), di.max(), (di > 0.0075).sum(), (di <= 0).sum()))
dg = np.diff(t)
print("GT  %d samples, gaps: min %.4f max %.4f s, %d gaps > 7.5 ms" % (len(gt), dg.min(), dg.max(), (dg > 0.0075).sum()))
k = np.clip(np.searchsorted(t, imu[:, 0]), 0, len(t) - 1)
a_w = np.array([R(*gt[j, 4:8]) @ r[1:4] for j, r in zip(k, imu)]) + np.array([0, 0, -G])
d = np.gradient(imu[:, 0])
v = np.array([np.interp(imu[:, 0], t, gt[:, 8 + j]) for j in range(3)]).T
z = np.interp(imu[:, 0], t, gt[:, 3])
n = 20
rows = []
for i in range(0, len(imu) - n, n):
    e = (a_w[i:i + n] * d[i:i + n, None]).sum(0) - (v[i + n] - v[i])
    rows.append((imu[i, 0], np.linalg.norm(e), z[i] - z[0], np.linalg.norm(v[i])))
rows = np.array(rows)
up = rows[:, 2] > 0.10
t0, t1 = rows[up, 0].min(), rows[up, 0].max()
for name, sel in (("ground before", rows[:, 0] < t0), ("air", (rows[:, 0] >= t0) & (rows[:, 0] <= t1)),
                  ("ground after", rows[:, 0] > t1)):
    e = rows[sel, 1]
    print("%-14s %4d windows  RMS %.4f  max %.4f m/s" % (name, len(e), np.sqrt((e ** 2).mean()), e.max()))
print("worst windows: t (s)  error (m/s)  height (m)  speed (m/s)")
for r in rows[np.argsort(-rows[:, 1])[: int(sys.argv[2]) if len(sys.argv) > 2 else 12]]:
    print("  %7.2f  %.4f  %6.2f  %5.2f" % tuple(r))
