#!/usr/bin/env python3
"""Measured vs predicted ground returns per LiDAR scan over the altitude sweep (Stage 4, B).

    python3 /scripts/stage4/ground_points.py <out.csv> <bag> [<bag> ...]

Runs INSIDE the sim container (ROS python, numpy, the Mid-360 scan pattern). Not in the
guide; plan PDF section 5.3. For every bag: the scans of the cruise (ground truth within
0.5 m of the bag's highest median cruise altitude) are put into the world frame with the
ground-truth pose of the IMU frame and the rig's LiDAR extrinsic (config/rig.yaml), and a
point counts as GROUND when its world height is below 0.5 m (streets and plaza lie at 0;
building roofs are at 8-45 m). Prediction for the same altitude, from the real scan
pattern (the 'Figure 2' formula of the plan): a ray at elevation e below the horizon
reaches flat ground within the 40 m range when sin(e) >= h / 40.

CSV columns: bag, altitude_m, scans, ground_median, ground_p10, ground_p90,
             other_median (non-ground returns), predicted
"""
import csv
import math
import os
import sys

import numpy as np
import rosbag
import yaml

PATTERN = "/ws/src/Mid360_simulation_plugin/livox_laser_simulation/scan_mode/mid360-real-centr.csv"
RANGE = 40.0


def rot(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


def main():
    out, bags = sys.argv[1], sys.argv[2:]
    rig = yaml.safe_load(open("/config/rig.yaml"))["lidar"]
    R_il, t_il = rpy(*rig["rpy"]), np.array(rig["xyz"])
    zen = np.loadtxt(PATTERN, delimiter=",", skiprows=1, usecols=2)
    es = np.radians(90.0 - zen)                  # elevation in the sensor frame, -7..+52 deg
    rows = []
    for b in bags:
        gt_t, gt = [], []
        bag = rosbag.Bag(b)
        for _, m, _ in bag.read_messages(topics=["/ground_truth/odom"]):
            p, q = m.pose.pose.position, m.pose.pose.orientation
            gt_t.append(m.header.stamp.to_sec())
            gt.append((p.x, p.y, p.z, q.x, q.y, q.z, q.w))
        gt_t, gt = np.array(gt_t), np.array(gt)
        z0 = np.median(gt[:200, 2])
        h = np.median(gt[gt[:, 2] > gt[:, 2].max() - 1.0, 2]) - z0     # cruise altitude
        ground, other = [], []
        for _, m, _ in bag.read_messages(topics=["/livox/lidar"]):
            s = m.header.stamp.to_sec()
            k = int(np.clip(np.searchsorted(gt_t, s), 0, len(gt_t) - 1))
            if abs(gt[k, 2] - z0 - h) > 0.5:
                continue
            P = np.array([(pt.x, pt.y, pt.z) for pt in m.points])
            P = P[np.linalg.norm(P, axis=1) > 0.1]
            W = (rot(*gt[k, 3:7]) @ (R_il @ P.T + t_il[:, None])).T + gt[k, :3]
            g = int((W[:, 2] < 0.5).sum())
            ground.append(g)
            other.append(len(P) - g)
        pred = 20000 * np.mean((es > 0) & (np.sin(np.clip(es, 1e-9, None)) >= h / RANGE))
        ground = np.array(ground) if ground else np.array([0])
        rows.append(dict(bag=os.path.basename(b), altitude_m=round(float(h), 2), scans=len(other),
                         ground_median=float(np.median(ground)), ground_p10=float(np.percentile(ground, 10)),
                         ground_p90=float(np.percentile(ground, 90)),
                         other_median=float(np.median(other)) if other else 0.0, predicted=round(float(pred), 1)))
        print(rows[-1])
    with open(out, "w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
