#!/usr/bin/env python3
"""Stage 5 metrics beyond the guide's two APE numbers (eval container, numpy only).

    closed_loop_metrics.py gtbase <gt_imu.tum> <out_base.tum> [--mount M]
        ground truth of the VEHICLE (base_link) from the ground truth of the IMU:
        T_world_base = T_world_imu * M^-1, M = T_base_imu (config/generated/mount.yaml)

    closed_loop_metrics.py frame <gt_imu.tum> <vision.tum> [--mount M]
        relay check: slam_to_px4.py's output against the true base_link pose, expressed in
        the frame PX4 uses (base_link at the moment SLAM started), with NO alignment. A
        frame error (a climb read as a descent, a mirrored axis) shows as a large error and
        a negative climb correlation; a correct relay leaves only SLAM's own error.

    closed_loop_metrics.py report <dir> <name> [--mount M]
        <dir> holds <name>.{gt,px4,vision,fastlio2,setpoint}.tum (bag_to_tum.py output).
        Prints and writes <dir>/<name>.closed_loop.json:
          airborne   take-off to FIRST touchdown; every in-flight number uses this window
          relay      vision pose vs truth, unaligned (as in "frame")
          ekf        PX4's estimate vs the vision pose it was given (both PX4's frame):
                     does EKF2 follow SLAM, and with what lag
          px4_truth  PX4's estimate vs truth, unaligned: what the vehicle believed vs where
                     it was, in its own frame
          control    truth vs the setpoint (airborne): how well it flew what was commanded;
                     also with the setpoint delayed by the controller's lag (control_lagged)
          landing    PX4 vs truth and SLAM vs truth in the 5 s after the first touchdown
          hover      for every stretch where the setpoint stood still >= 8 s while airborne,
                     the standard deviation of the true position after 3 s of settling, and
                     the largest deviation from the setpoint in each quarter of it (growth test)
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import yaml


def load(path):
    a = np.loadtxt(path, ndmin=2)
    return a[np.argsort(a[:, 0])] if len(a) else a


def q2R(q):                              # TUM order qx qy qz qw
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def R2q(R):
    tr = np.trace(R)
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return np.array([(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s])
    i = int(np.argmax(np.diag(R))); j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
    q = np.zeros(4); q[i] = 0.25 * s
    q[j] = (R[j, i] + R[i, j]) / s; q[k] = (R[k, i] + R[i, k]) / s; q[3] = (R[k, j] - R[j, k]) / s
    return q


def T(row):
    M = np.eye(4); M[:3, :3] = q2R(row[4:8]); M[:3, 3] = row[1:4]
    return M


def mount(path):
    m = yaml.safe_load(open(path))
    M = np.eye(4); M[:3, :3] = np.array(m["R_base_imu"]).reshape(3, 3); M[:3, 3] = m["t_base_imu"]
    return M


def to_base(gt, M):
    Mi = np.linalg.inv(M)
    out = []
    for r in gt:
        B = T(r) @ Mi
        out.append(np.r_[r[0], B[:3, 3], R2q(B[:3, :3])])
    return np.array(out)


def match(a, b, tol=0.02):
    """Rows of b nearest in time to each row of a (within tol s)."""
    idx = np.clip(np.searchsorted(b[:, 0], a[:, 0]), 1, len(b) - 1)
    near = np.where(np.abs(b[idx - 1, 0] - a[:, 0]) < np.abs(b[idx, 0] - a[:, 0]), idx - 1, idx)
    ok = np.abs(b[near, 0] - a[:, 0]) <= tol
    return a[ok], b[near[ok]]


def local_truth(gt_base, t0):
    """Truth of base_link in PX4's frame: relative to base_link at time t0, made level.
    PX4's frame is base_link at SLAM start (the vehicle sits level, so this is a yaw-only
    frame); the spawn is level within the ground's tilt, which is kept, not hidden."""
    i = int(np.argmin(np.abs(gt_base[:, 0] - t0)))
    A = np.linalg.inv(T(gt_base[i]))
    out = []
    for r in gt_base:
        B = A @ T(r)
        out.append(np.r_[r[0], B[:3, 3], R2q(B[:3, :3])])
    return np.array(out)


def yaw(row):
    R = q2R(row[4:8])
    return math.atan2(R[1, 0], R[0, 0])


def errors(est, ref, tol=0.02):
    e, r = match(est, ref, tol)
    if len(e) == 0:
        return None
    d = e[:, 1:4] - r[:, 1:4]
    dyaw = np.array([(yaw(x) - yaw(y) + math.pi) % (2 * math.pi) - math.pi for x, y in zip(e, r)])
    h = np.hypot(d[:, 0], d[:, 1])
    climb = np.corrcoef(e[:, 3], r[:, 3])[0, 1] if np.std(r[:, 3]) > 0.05 else float("nan")
    return {"n": int(len(e)), "rmse_m": float(np.sqrt(np.mean(np.sum(d * d, 1)))),
            "h_rmse_m": float(np.sqrt(np.mean(h * h))), "v_rmse_m": float(np.sqrt(np.mean(d[:, 2] ** 2))),
            "max_m": float(np.max(np.linalg.norm(d, axis=1))), "yaw_rmse_deg": float(np.degrees(np.sqrt(np.mean(dyaw ** 2)))),
            "climb_corr": float(climb)}


def airborne(gt_base, z_off=0.15):
    """Take-off (first time 0.15 m above the start height) to FIRST touchdown (back within
    0.05 m of it). A bounce after touchdown is part of the landing, not of the flight."""
    z = gt_base[:, 3]; g = np.median(z[:20])
    up = np.where(z > g + z_off)[0]
    if not len(up):
        return (None, None)
    down = np.where((gt_base[:, 0] > gt_base[up[-1], 0] - 30) & (np.arange(len(z)) > up[0]) & (z < g + 0.05))[0]
    down = down[gt_base[down, 0] > gt_base[up[0], 0] + 5.0] if len(down) else down
    return (gt_base[up[0], 0], gt_base[down[0], 0] if len(down) else gt_base[up[-1], 0])


def lag(est, ref, lo=-0.3, hi=0.3, step=0.01):
    """Delay (s) of est behind ref that minimises the position difference."""
    best = (None, 1e9)
    for dt in np.arange(lo, hi + step / 2, step):
        sh = est.copy(); sh[:, 0] -= dt
        e = errors(sh, ref, 0.02)
        if e and e["rmse_m"] < best[1]:
            best = (round(float(dt), 3), e["rmse_m"])
    return best[0]


def report(d, name, M, algo="fastlio2"):
    f = lambda k: os.path.join(d, "%s.%s.tum" % (name, k))
    gt = load(f("gt")); base = to_base(gt, M)
    vis, px4, sp = load(f("vision")), load(f("px4")), load(f("setpoint"))
    out = {"name": name, "algo": algo}
    t0 = vis[0, 0] if len(vis) else px4[0, 0]
    tru = local_truth(base, t0)
    ta, tb = airborne(base)
    out["airborne_s"] = [ta, tb]
    fly = lambda a: a[(a[:, 0] >= ta) & (a[:, 0] <= tb)] if ta is not None else a
    out["relay"] = errors(vis, tru)
    out["ekf"] = errors(fly(px4), vis, 0.06)          # PX4 local pose ~30-50 Hz, vision 10 Hz
    out["ekf_lag_s"] = lag(fly(px4), vis)
    out["px4_truth"] = errors(fly(px4), tru)
    out["px4_truth_whole"] = errors(px4[px4[:, 0] >= t0], tru)
    # setpoints: the mission streams them at 30 Hz in PX4's frame (origin = take-off point)
    out["control"] = errors(fly(tru), sp, 0.05)
    # PX4's position controller follows a moving POSITION setpoint (no velocity feed-forward
    # from this mission) with a lag of about speed / MPC_XY_P: that lag, not SLAM, dominates
    # the raw tracking error. The setpoint shifted by the best lag separates the two.
    best = (None, 1e9, None)
    for dt in np.arange(0.0, 2.001, 0.05):                 # setpoint DELAYED by dt
        sh = sp.copy(); sh[:, 0] += dt
        e = errors(fly(tru), sh, 0.05)
        if e and e["h_rmse_m"] < best[1]:
            best = (round(float(dt), 2), e["h_rmse_m"], e)
    out["control_lag_s"], out["control_lagged"] = best[0], best[2]
    # the landing: from first touchdown to 5 s later, PX4's estimate vs truth and vs SLAM
    if tb is not None:
        land = lambda a: a[(a[:, 0] >= tb) & (a[:, 0] <= tb + 5.0)]
        out["landing_px4_truth"] = errors(land(px4), tru)
        out["landing_vision_truth"] = errors(land(vis), tru)
    hov = []
    if len(sp) > 1:
        still = np.r_[False, np.linalg.norm(np.diff(sp[:, 1:4], axis=0), axis=1) < 1e-4]
        i = 0
        while i < len(sp):
            if not still[i]:
                i += 1; continue
            j = i
            while j + 1 < len(sp) and still[j + 1]:
                j += 1
            a, b = sp[i - 1, 0], sp[j, 0]
            if b - a >= 8.0 and sp[i, 3] > 0.5 and ta is not None and a >= ta and b <= tb:
                w = tru[(tru[:, 0] >= a + 3.0) & (tru[:, 0] <= b)]
                if len(w) > 10:
                    q = np.array_split(w, 4)              # growth test: spread per quarter of the hold
                    hov.append({"from_s": round(a - ta, 1), "length_s": round(b - a - 3.0, 1),
                                "sd_xyz_cm": [round(float(v) * 100, 2) for v in np.std(w[:, 1:4], 0)],
                                "max_dev_cm": round(float(np.max(np.linalg.norm(w[:, 1:4] - sp[j, 1:4], axis=1))) * 100, 2),
                                "quarter_dev_cm": [round(float(np.max(np.linalg.norm(x[:, 1:4] - sp[j, 1:4], axis=1))) * 100, 2)
                                                   for x in q]})
            i = j + 1
    out["hover"] = hov
    # PX4's mode/arming changes (bag_modes.py), from 5 s before take-off on
    mp = os.path.join(d, name + ".modes.txt")
    if os.path.exists(mp) and ta is not None:
        rows = [l.split() for l in open(mp) if l.strip()]
        rows = [(r[0], " ".join(r[1:-1]) or "(none)", r[-1]) for r in rows]   # an empty mode name is possible
        out["modes"] = [[round(float(t) - ta, 2), m, int(arm)] for t, m, arm in rows if float(t) >= ta - 5]
    # a live sensor fault (fault_live.py): what happened around it
    fp = os.path.join(d, name + ".fault.txt")
    if os.path.exists(fp) and ta is not None:
        st = {l.split()[1]: float(l.split()[2]) for l in open(fp) if l.startswith("FAULT ")}
        if "START" in st:
            a0, a1 = st["START"], st.get("END", st["START"])
            seg = lambda x, lo, hi: x[(x[:, 0] >= lo) & (x[:, 0] <= hi)]
            vv = seg(vis, a0 - 1.0, a1 + 10.0)
            gap = float(np.max(np.diff(vv[:, 0]))) if len(vv) > 1 else float("nan")
            fe = lambda lo, hi: errors(seg(px4, lo, hi), tru)
            out["fault"] = {"start_s": round(a0 - ta, 2), "end_s": round(a1 - ta, 2), "vision_gap_s": round(gap, 2),
                            "px4_truth_before": fe(ta, a0), "px4_truth_fault_plus10s": fe(a0, a1 + 10.0),
                            "px4_truth_after": fe(a1 + 10.0, tb if tb else a1 + 10.0),
                            "modes": [m for m in out.get("modes", []) if a0 - ta - 1 <= m[0] <= a1 - ta + 30]}
    json.dump(out, open(os.path.join(d, name + ".closed_loop.json"), "w"), indent=1)
    show(out)


def show(o):
    print("== %s%s  (airborne %.1f-%.1f s)" % (o.get("name"), "  [%s]" % o["algo"] if o.get("algo") else "",
                                              *(o["airborne_s"] if o.get("airborne_s") and o["airborne_s"][0] else (0, 0))))
    for k, what in (("relay", "SLAM pose sent to PX4 vs truth (unaligned)"),
                    ("ekf", "PX4 estimate vs the SLAM pose it was given"),
                    ("px4_truth", "PX4 estimate vs truth (unaligned, airborne)"),
                    ("control", "true position vs setpoint (airborne)"),
                    ("control_lagged", "  same, setpoint delayed by the control lag"),
                    ("landing_px4_truth", "landing (5 s from touchdown): PX4 vs truth"),
                    ("landing_vision_truth", "landing (5 s from touchdown): SLAM vs truth")):
        if k not in o:
            continue
        e = o.get(k)
        if e:
            print("   %-46s RMSE %6.2f cm (h %5.2f, v %5.2f)  max %6.2f cm  yaw %5.2f deg  n=%d%s" % (
                what, e["rmse_m"] * 100, e["h_rmse_m"] * 100, e["v_rmse_m"] * 100, e["max_m"] * 100,
                e["yaw_rmse_deg"], e["n"], "  climb corr %+.3f" % e["climb_corr"] if not math.isnan(e["climb_corr"]) else ""))
        else:
            print("   %-46s -- no matched poses" % what)
    if "ekf_lag_s" in o:
        print("   EKF2 output lag behind the SLAM pose:           %s s" % o["ekf_lag_s"])
    if o.get("control_lag_s") is not None:
        print("   position-control lag behind the setpoint:       %s s" % o["control_lag_s"])
    fl = o.get("fault")
    if fl:
        g = lambda k: ("%.1f cm" % (fl[k]["rmse_m"] * 100) + " (max %.1f)" % (fl[k]["max_m"] * 100)) if fl.get(k) else "-"
        print("   FAULT %+.1f..%+.1f s after take-off: longest gap in the poses PX4 got %.2f s; PX4 vs truth before %s,"
              " fault + 10 s %s, after %s" % (fl["start_s"], fl["end_s"], fl["vision_gap_s"], g("px4_truth_before"),
                                              g("px4_truth_fault_plus10s"), g("px4_truth_after")))
        print("   PX4 modes around the fault: %s" % (", ".join("%+.1f s %s%s" % (m[0], m[1], "" if m[2] else " (disarmed)")
                                                        for m in fl["modes"]) or "no change"))
    for h in o.get("hover", []):
        print("   hover at +%5.1f s for %4.1f s: sd x/y/z %s cm, max deviation from setpoint %.2f cm;"
              " max deviation per quarter %s cm" % (
            h["from_s"], h["length_s"], " / ".join("%.2f" % v for v in h["sd_xyz_cm"]), h["max_dev_cm"],
            " / ".join("%.1f" % v for v in h.get("quarter_dev_cm", []))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gtbase", "frame", "report"])
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--mount", default="/config/generated/mount.yaml")
    ap.add_argument("--algo", default="fastlio2", help="report: the SLAM method in the loop")
    a = ap.parse_args()
    M = mount(a.mount)
    if a.cmd == "gtbase":
        np.savetxt(a.b, to_base(load(a.a), M), fmt="%.9f")
    elif a.cmd == "frame":
        base = to_base(load(a.a), M); vis = load(a.b)
        tru = local_truth(base, vis[0, 0])
        o = {"name": "frame check", "airborne_s": list(airborne(base)), "relay": errors(vis, tru)}
        show(o)
        # a SLAM output stamped late (FAST-LIVO2's topic: publish time, not state time) is
        # compared again at the time shift that fits best; the frame verdict uses that one
        dt = lag(vis, tru, 0.0, 0.2, 0.005)
        if dt:
            sh = vis.copy(); sh[:, 0] -= dt
            e2 = errors(sh, tru)
            print("   stamps %.3f s late: at state time  RMSE %6.2f cm (h %5.2f, v %5.2f)  max %6.2f cm  yaw %5.2f deg" % (
                dt, e2["rmse_m"] * 100, e2["h_rmse_m"] * 100, e2["v_rmse_m"] * 100, e2["max_m"] * 100, e2["yaw_rmse_deg"]))
            o["relay"] = dict(e2, climb_corr=o["relay"]["climb_corr"])
        e = o["relay"]
        ok = e and e["climb_corr"] > 0.99 and e["rmse_m"] < 0.05 and e["yaw_rmse_deg"] < 2
        print("   %s  relay frame %s" % ("PASS" if ok else "FAIL", "correct: a climb is a climb, errors at SLAM level" if ok else "WRONG"))
        sys.exit(0 if ok else 1)
    else:
        report(a.a, a.b, M, a.algo)


if __name__ == "__main__":
    main()
