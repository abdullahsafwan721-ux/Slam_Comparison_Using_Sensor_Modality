#!/usr/bin/env python3
"""Inject realistic IMU noise into a (noise-free) simulation bag.

    python3 imu_noise.py <in.bag> <out.bag> [--scale S] [--seed N] [--topic /livox/imu]

Standard continuous-time model (the one Kalibr and ORB-SLAM3 assume):
  white noise   n_k ~ N(0, sigma_c^2 / dt)          sigma_c = noise density
  bias          b_k = b_{k-1} + N(0, sigma_b^2 * dt)  sigma_b = random walk
Densities come from imu_noise_baseline in config/rig.yaml, multiplied by S.
Every other topic is copied through untouched, so the same flight can be
replayed with any IMU grade -- only the IMU changes between runs.
"""
import argparse
import json
import math
import random

import rosbag
import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--topic", default="/livox/imu")
    ap.add_argument("--rig", default="/config/rig.yaml")
    a = ap.parse_args()
    with open(a.rig) as f:
        n = yaml.safe_load(f)["imu_noise_baseline"]
    gw, gb = n["gyro_noise_density"] * a.scale, n["gyro_random_walk"] * a.scale
    aw, ab = n["accel_noise_density"] * a.scale, n["accel_random_walk"] * a.scale
    rnd = random.Random(a.seed)
    bg, ba = [0.0] * 3, [0.0] * 3
    last = None
    count = 0
    with rosbag.Bag(a.inp) as bi, rosbag.Bag(a.out, "w") as bo:
        for topic, msg, t in bi.read_messages():
            if topic == a.topic:
                ts = msg.header.stamp.to_sec()
                dt = (ts - last) if last is not None and ts > last else 0.005
                last = ts
                for i in range(3):
                    bg[i] += gb * math.sqrt(dt) * rnd.gauss(0, 1)
                    ba[i] += ab * math.sqrt(dt) * rnd.gauss(0, 1)
                sw, sa = gw / math.sqrt(dt), aw / math.sqrt(dt)
                w, acc = msg.angular_velocity, msg.linear_acceleration
                w.x += bg[0] + sw * rnd.gauss(0, 1)
                w.y += bg[1] + sw * rnd.gauss(0, 1)
                w.z += bg[2] + sw * rnd.gauss(0, 1)
                acc.x += ba[0] + sa * rnd.gauss(0, 1)
                acc.y += ba[1] + sa * rnd.gauss(0, 1)
                acc.z += ba[2] + sa * rnd.gauss(0, 1)
                count += 1
            bo.write(topic, msg, t)
    meta = dict(scale=a.scale, seed=a.seed, gyro_noise_density=gw, gyro_random_walk=gb,
                accel_noise_density=aw, accel_random_walk=ab, imu_messages=count)
    with open(a.out.rsplit(".bag", 1)[0] + ".imu_noise.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("noised %d IMU messages (scale %.2f) -> %s" % (count, a.scale, a.out))


if __name__ == "__main__":
    main()
