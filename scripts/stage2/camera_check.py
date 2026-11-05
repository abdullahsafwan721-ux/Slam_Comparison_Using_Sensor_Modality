#!/usr/bin/env python3
"""Stage 2 extra check (not in the guide): the GENERATED camera extrinsics, the
intrinsics and the camera time stamps, measured against the images themselves.

    python3 /scripts/stage2/camera_check.py <bag> [world=/sim/worlds/room.world] [outdir]

Runs in the sim container after `source /scripts/common/sim_env.sh`.

Every box of the world file has known geometry. Its 12 edges are projected into the
images through ground truth (IMU pose) and the camera extrinsic written by
gen_configs.py, and scored by the image gradient they land on. The score is then
recomputed with the extrinsic deliberately perturbed (rotations, translations), with
the principal point shifted and with the image stamps shifted. If the generated
values and the stamps are right, the unperturbed configuration scores best, and the
parabolic peak of each sweep estimates any residual error.

Both extrinsic chains Stage 3 consumes are tested:
  ORB-SLAM3   T_b_c = IMU.T_b_c1                      (config/generated/orbslam3_sim.yaml)
  FAST-LIVO2  T_b_c = T_b_l * inv(T_c_l)  from extrinsic_T/R and Rcl/Pcl (fastlivo2_sim.yaml)
plus the right camera through Stereo.T_c1_c2.
"""
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import rosbag
import yaml


def quat_to_R(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def rot(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return {"x": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]),
            "y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
            "z": np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}[axis]


def box_edges(world):
    """3-D sample points along every box edge in the world file (world frame)."""
    pts = []
    for m in ET.parse(world).getroot().iter("model"):
        pose, size = m.find("pose"), m.find(".//collision/geometry/box/size")
        if pose is None or size is None:
            continue
        x, y, z, _, _, yaw = (float(v) for v in pose.text.split())
        sx, sy, sz = (float(v) for v in size.text.split())
        R = rot("z", math.degrees(yaw))
        corners = np.array([[i * sx / 2, j * sy / 2, k * sz / 2]
                            for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]) @ R.T + [x, y, z]
        for a in range(8):
            for b in range(a + 1, 8):
                if bin(a ^ b).count("1") != 1:      # corners differing in one axis = an edge
                    continue
                n = max(2, int(np.linalg.norm(corners[a] - corners[b]) / 0.02))
                t = np.linspace(0, 1, n)[:, None]
                pts.append(corners[a] * (1 - t) + corners[b] * t)
    return np.concatenate(pts)


def pose_at(gt, t):
    ts = gt[:, 0]
    k = np.searchsorted(ts, t)
    if k <= 0 or k >= len(ts):
        return None
    a = (t - ts[k - 1]) / (ts[k] - ts[k - 1])
    q0, q1 = gt[k - 1, 4:8], gt[k, 4:8].copy()
    if np.dot(q0, q1) < 0:
        q1 = -q1
    q = (1 - a) * q0 + a * q1
    return quat_to_R(*(q / np.linalg.norm(q))), (1 - a) * gt[k - 1, 1:4] + a * gt[k, 1:4]


def score(G, Xw, R_wc, t_wc, K):
    Xc = (Xw - t_wc) @ R_wc                               # world -> camera optical
    Xc = Xc[Xc[:, 2] > 0.3]
    u = K[0] * Xc[:, 0] / Xc[:, 2] + K[2]
    v = K[1] * Xc[:, 1] / Xc[:, 2] + K[3]
    ok = (u >= 1) & (u < G.shape[1] - 2) & (v >= 1) & (v < G.shape[0] - 2)
    if ok.sum() < 200:
        return np.nan
    return float(G[np.round(v[ok]).astype(int), np.round(u[ok]).astype(int)].mean())


def peak(xs, ys):
    """Parabolic peak of a sweep (xs ascending, ys scores)."""
    k = int(np.nanargmax(ys))
    if 0 < k < len(xs) - 1:
        y0, y1, y2 = ys[k - 1], ys[k], ys[k + 1]
        den = y0 - 2 * y1 + y2
        if den < 0:
            return xs[k] + 0.5 * (y0 - y2) / den * (xs[k + 1] - xs[k])
    return xs[k]


def main():
    fine = "--pp-fine" in sys.argv          # only a 0.1 px principal-point sweep, both cameras
    argv = [a for a in sys.argv if a != "--pp-fine"]
    bagpath = argv[1]
    world = argv[2] if len(argv) > 2 else "/sim/worlds/room.world"
    out = argv[3] if len(argv) > 3 else os.path.splitext(bagpath)[0] + "_camcheck"
    os.makedirs(out, exist_ok=True)

    fs = cv2.FileStorage("/config/generated/orbslam3_sim.yaml", cv2.FILE_STORAGE_READ)
    T_b_c_orb = fs.getNode("IMU.T_b_c1").mat()
    T_c1_c2 = fs.getNode("Stereo.T_c1_c2").mat()
    lv = yaml.safe_load(open("/config/generated/fastlivo2_sim.yaml"))
    cm = yaml.safe_load(open("/config/generated/fastlivo2_sim_camera.yaml"))
    K = [float(cm[k]) for k in ("cam_fx", "cam_fy", "cam_cx", "cam_cy")]
    T_b_l = np.eye(4)
    T_b_l[:3, :3] = np.array(lv["extrin_calib"]["extrinsic_R"], float).reshape(3, 3)
    T_b_l[:3, 3] = lv["extrin_calib"]["extrinsic_T"]
    T_c_l = np.eye(4)
    T_c_l[:3, :3] = np.array(lv["extrin_calib"]["Rcl"], float).reshape(3, 3)
    T_c_l[:3, 3] = lv["extrin_calib"]["Pcl"]
    T_b_c_livo = T_b_l @ np.linalg.inv(T_c_l)
    d = T_b_c_livo - T_b_c_orb
    print("ORB-SLAM3 vs FAST-LIVO2 camera extrinsic: max |difference| %.2e (rotation and translation entries)"
          % np.abs(d).max())

    Xw = box_edges(world)
    print("world %s: %d edge samples" % (world, len(Xw)))

    gt, frames, info = [], {}, {}
    want = None
    with rosbag.Bag(bagpath) as bag:
        for topic, msg, _ in bag.read_messages(topics=["/ground_truth/odom", "/stereo/left/image_raw",
                                                       "/stereo/right/image_raw", "/stereo/left/camera_info"]):
            s = msg.header.stamp.to_sec()
            if topic == "/ground_truth/odom":
                p, q = msg.pose.pose.position, msg.pose.pose.orientation
                gt.append((s, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
            elif topic == "/stereo/left/camera_info":
                info = {"K": list(msg.K), "P": list(msg.P), "D": list(msg.D), "size": (msg.width, msg.height)}
            else:
                if want is None:
                    want = s
                ns = msg.header.stamp.to_nsec()
                side = "left" if "left" in topic else "right"
                # one stereo pair every 0.5 s
                key = round((s - want) / 0.5)
                if abs(s - want - key * 0.5) < 0.026:
                    im = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.width)
                    frames.setdefault(ns, {})[side] = im.copy()
    gt = np.array(gt)
    print("camera_info (Gazebo's own claim): K = %s  P[3] (Tx, left) = %s"
          % ([round(v, 3) for v in info["K"]], info["P"][3]))
    print("generated intrinsics: fx %.3f fy %.3f cx %.1f cy %.1f" % tuple(K))

    pairs = []
    for ns, f in sorted(frames.items()):
        if "left" in f and "right" in f:
            pairs.append((ns * 1e-9, f["left"], f["right"]))
    print("stereo pairs scored: %d" % len(pairs))

    def grad(im):
        b = cv2.GaussianBlur(im.astype(np.float32), (5, 5), 1.2)
        g = np.hypot(cv2.Sobel(b, cv2.CV_32F, 1, 0), cv2.Sobel(b, cv2.CV_32F, 0, 1))
        return g / (g.mean() + 1e-6)

    G = [(s, grad(l), grad(r)) for s, l, r in pairs]

    def total(T_b_c, Kx=K, dt=0.0, side="left", moving_only=False):
        acc = []
        for s, gl, gr in G:
            if moving_only and s < 14.0:
                continue
            pa = pose_at(gt, s + dt)
            if pa is None:
                continue
            R_wb, p_wb = pa
            T = T_b_c if side == "left" else T_b_c @ T_c1_c2
            R_wc, t_wc = R_wb @ T[:3, :3], R_wb @ T[:3, 3] + p_wb
            v = score(gl if side == "left" else gr, Xw, R_wc, t_wc, Kx)
            if not np.isnan(v):
                acc.append(v)
        return float(np.mean(acc))

    base = total(T_b_c_orb)
    print("\nedge score, nominal: left %.4f (ORB-SLAM3 chain)  left %.4f (FAST-LIVO2 chain)  right %.4f"
          % (base, total(T_b_c_livo), total(T_b_c_orb, side="right")))

    def perturbed(dR=np.eye(3), dt_c=np.zeros(3)):
        T = T_b_c_orb.copy()
        T[:3, :3] = T[:3, :3] @ dR                       # perturb in the camera frame
        T[:3, 3] = T[:3, 3] + T[:3, :3] @ dt_c
        return T

    if fine:
        pp = [round(-1.0 + 0.1 * i, 1) for i in range(16)]           # -1.0 .. +0.5 px
        print("\nprincipal point, 0.1 px sweep (score relative to the generated value, %):")
        for side in ("left", "right"):
            for name, j in (("cx", 2), ("cy", 3)):
                ys = []
                for p in pp:
                    Kx = list(K)
                    Kx[j] += p
                    ys.append(total(T_b_c_orb, Kx, side=side))
                b = ys[pp.index(0.0)]
                print("  %-5s %s  %s\n        peak at %+.2f px -> %s = %.2f"
                      % (side, name, "  ".join("%+.1f:%+.2f" % (x, 100 * (y / b - 1)) for x, y in zip(pp, ys)),
                         peak(pp, ys), name, K[j] + peak(pp, ys)))
        return

    report = []
    print("\nsweeps (score relative to nominal, %; the generated value is right if 0 is the best):")
    angs = [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]
    for ax in "xyz":
        ys = [total(perturbed(dR=rot(ax, a))) for a in angs]
        report.append(("rotation about camera %s (deg)" % ax, angs, ys))
    offs = [-0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05]
    for i, ax in enumerate("xyz"):
        e = np.zeros(3)
        ys = []
        for o in offs:
            e[:] = 0
            e[i] = o
            ys.append(total(perturbed(dt_c=e)))
        report.append(("translation along camera %s (m)" % ax, offs, ys))
    pp = [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]
    report.append(("principal point cx shift (px)", pp, [total(T_b_c_orb, [K[0], K[1], K[2] + p, K[3]]) for p in pp]))
    report.append(("principal point cy shift (px)", pp, [total(T_b_c_orb, [K[0], K[1], K[2], K[3] + p]) for p in pp]))
    dts = [-0.04, -0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.02, 0.04]
    base_m = total(T_b_c_orb, moving_only=True)
    ysm = [total(T_b_c_orb, dt=t, moving_only=True) for t in dts]
    for name, xs, ys in report:
        b = ys[xs.index(0.0)]
        print("  %-34s %s   peak at %+.3g" % (name, "  ".join("%+g:%+.1f" % (x, 100 * (y / b - 1)) for x, y in zip(xs, ys)),
                                                peak(xs, ys)))
    print("  %-34s %s   peak at %+.1f ms" % ("image stamp shift (s), moving part",
                                              "  ".join("%+g:%+.1f" % (x, 100 * (y / base_m - 1)) for x, y in zip(dts, ysm)),
                                              1000 * peak(dts, ysm)))

    # picture: projected edges on one moving left frame
    s, gl, _ = min(G, key=lambda g: abs(g[0] - 60.0))
    im = next(l for t, l, _ in pairs if t == s)
    R_wb, p_wb = pose_at(gt, s)
    R_wc, t_wc = R_wb @ T_b_c_orb[:3, :3], R_wb @ T_b_c_orb[:3, 3] + p_wb
    Xc = (Xw - t_wc) @ R_wc
    Xc = Xc[Xc[:, 2] > 0.3]
    u = (K[0] * Xc[:, 0] / Xc[:, 2] + K[2]).astype(int)
    v = (K[1] * Xc[:, 1] / Xc[:, 2] + K[3]).astype(int)
    ok = (u >= 0) & (u < im.shape[1]) & (v >= 0) & (v < im.shape[0])
    rgb = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    rgb[v[ok], u[ok]] = (0, 255, 0)
    fn = os.path.join(out, "edges_left_t%.1f.png" % s)
    cv2.imwrite(fn, rgb)
    print("\npicture: %s (world box edges through ground truth + IMU.T_b_c1, green)" % fn)


if __name__ == "__main__":
    main()
