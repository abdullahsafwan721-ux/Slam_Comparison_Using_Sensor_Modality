#!/usr/bin/env python3
"""Stage 2 diagnostics beyond the gate: timing, hold length, LiDAR content, and
pictures to look at. Complements verify_sim_bag.py; it is not part of the guide.

    python3 /scripts/stage2/sim_bag_diagnostics.py <bag> [outdir] [--world room]

Runs in the sim container (system python3: rosbag, numpy, cv2), after
`source /scripts/common/sim_env.sh`. Writes PNGs and a text report to outdir.

What it measures, and why:
  * stamp grids and intervals per topic -- a sensor stamped from a throttled
    clock (e.g. ros::Time::now() on a 100 Hz /clock) shows quantised, jittered
    intervals even though its average rate is right;
  * LiDAR-to-ground-truth time offset -- every scan is re-projected into the
    world with the ground-truth pose at (stamp + delta); the delta that best
    fits the room's known planes (walls, floor) is the stamp error;
  * the stationary hold actually present in the bag (the gate and FAST-LIO2's
    gravity initialisation both rely on it);
  * per-point fields (line, tag, offset_time, zero-range rays);
  * camera frames and LiDAR projections written as PNG for a human look.
"""
import math
import os
import sys

import cv2
import numpy as np
import rosbag

TOPICS = ["/livox/imu", "/livox/lidar", "/ground_truth/odom",
          "/stereo/left/image_raw", "/stereo/right/image_raw"]


def quat_to_R(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def slerp_R(gt, t):
    """GT pose (R, p) at time t: linear position, normalised-lerp quaternion (200 Hz, fine)."""
    ts = gt[:, 0]
    k = np.searchsorted(ts, t)
    if k <= 0 or k >= len(ts):
        return None
    a = (t - ts[k - 1]) / (ts[k] - ts[k - 1])
    p = (1 - a) * gt[k - 1, 1:4] + a * gt[k, 1:4]
    q0, q1 = gt[k - 1, 4:8], gt[k, 4:8]
    if np.dot(q0, q1) < 0:
        q1 = -q1
    q = (1 - a) * q0 + a * q1
    q /= np.linalg.norm(q)
    return quat_to_R(*q), p


def stats(name, st, nominal):
    st = np.asarray(st)
    d = np.diff(st)
    msg = ("%-26s n=%5d  first=%8.3f  last=%8.3f  rate=%7.2f Hz  dt mean=%.4f  min=%.4f  max=%.4f  std=%.5f"
           % (name, len(st), st[0], st[-1], (len(st) - 1) / (st[-1] - st[0]), d.mean(), d.min(), d.max(), d.std()))
    # quantisation: fraction of stamps on a 1 ms and a 10 ms grid
    on1 = np.mean(np.abs(st * 1000 - np.round(st * 1000)) < 1e-3)
    on10 = np.mean(np.abs(st * 100 - np.round(st * 100)) < 1e-4)
    msg += "  on-1ms-grid=%.2f  on-10ms-grid=%.2f  jitter(|dt-1/f|>1ms)=%d" % (
        on1, on10, int(np.sum(np.abs(d - 1.0 / nominal) > 1e-3)))
    return msg


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    bagpath = args[0]
    out = args[1] if len(args) > 1 else os.path.splitext(bagpath)[0] + "_diag"
    os.makedirs(out, exist_ok=True)
    rep = open(os.path.join(out, "report.txt"), "w")

    def say(s=""):
        print(s)
        rep.write(s + "\n")

    bag = rosbag.Bag(bagpath)
    stamps = {t: [] for t in TOPICS}
    recv = {t: [] for t in TOPICS}
    imu, gt, scans = [], [], []
    lines, tags, offs, zeros, npts = set(), set(), 0, 0, 0
    snap_times = [2.0, 15.0, 30.0, 60.0, 90.0]
    imgs = {"/stereo/left/image_raw": {}, "/stereo/right/image_raw": {}}
    t_first = None
    for topic, msg, t in bag.read_messages(topics=TOPICS):
        s = msg.header.stamp.to_sec()
        stamps[topic].append(s)
        recv[topic].append(t.to_sec())
        if t_first is None:
            t_first = s
        if topic == "/livox/imu":
            a, w = msg.linear_acceleration, msg.angular_velocity
            imu.append((s, a.x, a.y, a.z, w.x, w.y, w.z))
        elif topic == "/ground_truth/odom":
            p, q = msg.pose.pose.position, msg.pose.pose.orientation
            gt.append((s, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
        elif topic == "/livox/lidar":
            P = np.array([(p.x, p.y, p.z) for p in msg.points], dtype=float)
            for p in msg.points[::97]:
                lines.add(p.line)
                tags.add(p.tag)
            offs += sum(1 for p in msg.points if p.offset_time != 0)
            nz = np.any(P != 0.0, axis=1)
            zeros += int(np.sum(~nz))
            npts += len(P)
            scans.append((s, P[nz], msg.timebase))
        else:
            for st in snap_times:
                key = round(st, 1)
                if key not in imgs[topic] and s - t_first >= st:
                    imgs[topic][key] = (s, np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width).copy()
                                        if msg.encoding in ("mono8", "8UC1") else None, msg.encoding)
    imu, gt = np.array(imu), np.array(gt)

    say("== stamps (header) per topic")
    nominal = {"/livox/imu": 200, "/livox/lidar": 10, "/ground_truth/odom": 200,
               "/stereo/left/image_raw": 20, "/stereo/right/image_raw": 20}
    for t in TOPICS:
        if stamps[t]:
            say(stats(t, stamps[t], nominal[t]))
    lid = np.array([s for s, _, _ in scans])
    tb = np.array([b for _, _, b in scans], dtype=float) * 1e-9
    say("LiDAR timebase vs header stamp: max |diff| = %.6f s" % np.max(np.abs(tb - lid)))
    lag = np.array(recv["/livox/lidar"]) - lid
    say("LiDAR bag-receive minus header stamp: mean %.4f s, max %.4f s" % (lag.mean(), lag.max()))

    say("\n== stationary hold present in the bag")
    wn = np.linalg.norm(imu[:, 4:7], axis=1)
    moving = np.nonzero(wn > 1e-3)[0]
    t_move = imu[moving[0], 0] if len(moving) else float("nan")
    say("first IMU stamp %.3f s; first |gyro| > 1e-3 rad/s at %.3f s -> %.2f s of hold in the bag "
        "(path hold ends at sim time 8.0 s)" % (imu[0, 0], t_move, t_move - imu[0, 0]))
    rest = imu[imu[:, 0] < t_move - 0.5]
    say("|accel| at rest = %.5f m/s^2 (world file asks for 9.8066; SDF default 9.8)"
        % np.linalg.norm(rest[:, 1:4], axis=1).mean())

    say("\n== LiDAR per-point fields")
    say("points/scan %.0f, zero-range rays %.1f %%, lines %s, tags %s, non-zero offset_time %d"
        % (npts / len(scans), 100.0 * zeros / max(npts, 1), sorted(lines), sorted(hex(x) for x in tags), offs))

    # ---- LiDAR stamp error against ground truth, from the room's planes
    say("\n== LiDAR time offset vs ground truth (room planes)")
    # room.world: walls centred at x = +-7, y = +-5, 0.2 m thick -> inner faces at
    # +-6.9 / +-4.9; floor top at z = 0. Clutter is excluded by the selection boxes.
    T_bl = np.array([-0.011, -0.02329, 0.04412])          # LiDAR in IMU (rig.yaml)
    deltas = np.arange(-0.030, 0.0301, 0.001)
    cost = np.zeros(len(deltas))
    used = 0
    for s, P, _ in scans:
        if s < 14.0:                                      # moving part only
            continue
        Pb = P + T_bl
        res_all = []
        for i, d in enumerate(deltas):
            pose = slerp_R(gt, s + d)
            if pose is None:
                res_all = None
                break
            R, p = pose
            W = Pb @ R.T + p
            ax, ay, az = np.abs(W[:, 0]), np.abs(W[:, 1]), W[:, 2]
            ex = ax[(ax > 6.6) & (ax < 7.2) & (az > 0.3) & (az < 2.7) & (np.abs(W[:, 1]) < 4.5)] - 6.9
            ey = ay[(ay > 4.6) & (ay < 5.2) & (az > 0.3) & (az < 2.7) & (np.abs(W[:, 0]) < 6.5)] - 4.9
            ez = az[(np.abs(az) < 0.15) & (np.abs(W[:, 0]) < 6.5) & (np.abs(W[:, 1]) < 4.5)]
            e = np.concatenate([ex, ey, ez])
            res_all.append(np.mean(np.minimum(e * e, 0.05 ** 2)) if len(e) > 200 else np.nan)
        if res_all is None or np.any(np.isnan(res_all)):
            continue
        cost += np.array(res_all)
        used += 1
    if used:
        k = int(np.argmin(cost))
        # parabola through the minimum for sub-ms resolution
        if 0 < k < len(deltas) - 1:
            c0, c1, c2 = cost[k - 1], cost[k], cost[k + 1]
            frac = 0.5 * (c0 - c2) / (c0 - 2 * c1 + c2)
        else:
            frac = 0.0
        best = deltas[k] + frac * 0.001
        say("scans used %d; best delta = %+.1f ms (true scan time = stamp + delta); "
            "cost at 0 ms / at best: %.3e / %.3e" % (used, best * 1000, cost[np.argmin(np.abs(deltas))] / used, cost[k] / used))
        # sensitivity: how much worse the fit gets away from the minimum (a flat
        # curve would make the estimate meaningless)
        curve = "  ".join("%+d ms: %+.1f%%" % (round(d * 1000), 100.0 * (cost[i] / cost[k] - 1.0))
                          for i, d in enumerate(deltas) if round(d * 1000) in (-20, -10, -5, -2, 0, 2, 5, 10, 20))
        say("fit cost relative to the minimum:  " + curve)
    else:
        say("no usable scans (bag too short?)")

    # ---- pictures
    say("\n== pictures in %s" % out)
    for topic, side in (("/stereo/left/image_raw", "left"), ("/stereo/right/image_raw", "right")):
        for key, (s, im, enc) in sorted(imgs[topic].items()):
            if im is not None:
                fn = os.path.join(out, "cam_%s_t%05.1f.png" % (side, key))
                cv2.imwrite(fn, im)
                say("  %s  (stamp %.3f, %s)" % (os.path.basename(fn), s, enc))
    for st in snap_times:
        cand = [sc for sc in scans if sc[0] - t_first >= st]
        if not cand:
            continue
        s, P, _ = cand[0]
        img = np.full((500, 1000, 3), 255, np.uint8)
        # left: top view in the LiDAR frame (x up the image), right: side view (x, z)
        for (u, v), off in (((0, 1), 0), ((0, 2), 500)):
            sc = 30.0
            cu = (P[:, v] * -sc + 250 + off).astype(int)
            cv = (P[:, u] * -sc + 250).astype(int)
            ok = (cu >= off) & (cu < off + 500) & (cv >= 0) & (cv < 500)
            img[cv[ok], cu[ok]] = (0, 0, 0)
        cv2.putText(img, "top view x/y (LiDAR frame)", (10, 20), 0, 0.5, (0, 0, 255), 1)
        cv2.putText(img, "side view x/z (LiDAR frame)", (510, 20), 0, 0.5, (0, 0, 255), 1)
        fn = os.path.join(out, "lidar_t%05.1f.png" % st)
        cv2.imwrite(fn, img)
        say("  %s  (stamp %.3f, %d points)" % (os.path.basename(fn), s, len(P)))

    # ---- LiDAR -> left camera overlay with the GENERATED FAST-LIVO2 extrinsics, so
    # Rcl/Pcl and the intrinsics are checked against the data, not against the
    # generator's own algebra. Points coloured by depth: red near, blue far.
    try:
        import yaml
        lv = yaml.safe_load(open("/config/generated/fastlivo2_sim.yaml"))["extrin_calib"]
        cm = yaml.safe_load(open("/config/generated/fastlivo2_sim_camera.yaml"))
        Rcl = np.array(lv["Rcl"], dtype=float).reshape(3, 3)
        Pcl = np.array(lv["Pcl"], dtype=float)
        fx, fy, cx, cy = (float(cm[k]) for k in ("cam_fx", "cam_fy", "cam_cx", "cam_cy"))
    except Exception as e:                                # noqa: BLE001 -- report and go on
        say("overlay skipped: %s" % e)
        return
    say("\n== LiDAR -> left camera overlay (generated Rcl/Pcl, fx=%.3f cx=%.1f cy=%.1f)" % (fx, cx, cy))
    for key, (s_img, im, _) in sorted(imgs["/stereo/left/image_raw"].items()):
        if im is None:
            continue
        s_lid, P, _ = min(scans, key=lambda sc: abs(sc[0] - s_img))
        C = P @ Rcl.T + Pcl
        C = C[C[:, 2] > 0.2]
        u, v = fx * C[:, 0] / C[:, 2] + cx, fy * C[:, 1] / C[:, 2] + cy
        ok = (u >= 0) & (u < im.shape[1]) & (v >= 0) & (v < im.shape[0])
        rgb = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        z = np.clip((C[ok, 2] - 0.5) / 6.0, 0, 1)
        for (uu, vv), zz in zip(np.stack([u[ok], v[ok]], 1).astype(int), z):
            rgb[vv, uu] = (int(255 * zz), 0, int(255 * (1 - zz)))
        fn = os.path.join(out, "overlay_t%05.1f.png" % key)
        cv2.imwrite(fn, rgb)
        say("  %s  (image %.3f, scan %.3f, dt %+.1f ms, %d points in view)"
            % (os.path.basename(fn), s_img, s_lid, 1000 * (s_lid - s_img), int(ok.sum())))
    rep.close()


if __name__ == "__main__":
    main()
