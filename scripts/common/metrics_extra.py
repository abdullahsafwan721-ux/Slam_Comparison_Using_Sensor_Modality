#!/usr/bin/env python3
"""The project's extra trajectory metrics, beyond eval_traj.sh's APE / RPE / coverage.
Runs INSIDE the eval container (its python3 is the evo virtualenv):

    python3 metrics_extra.py <gt.tum> <est.tum> <out-prefix> [--tau 0.25] [--seg 10]
                             [--cost <cost.csv>] [--latency <latency.csv>]

Added in Stage 3 (not in the project guide); definitions are in
docs/eVTOL_SLAM_Research_and_Stage3-5_Plan.pdf, Part 3. Writes
  <prefix>_extra.json   one record per run (results_table.py aggregates them)
  <prefix>_errors.csv   error over time: t, ex, ey, ez, e_h, e_v, e_3d, yaw_err_deg

Alignment is evo's own (same association, --t_max_diff 0.02, same SE3 Umeyama call as
evo_ape --align), so ape_rmse here equals eval_traj.sh's APE; the script checks that
against <prefix>_ape.zip when it exists and stops if they differ by more than 1e-6 m.

  H1 ape_h_rmse / ape_v_rmse  APE split into horizontal (xy) and vertical (z) parts, in the
                              ground-truth world frame (z up), after alignment
     ape_air_rmse (+ _h, _v)  the same APE restricted to the flight window (take-off to
                              touch-down, as coverage_air), aligned on that window only.
                              ape_rmse above stays evo's whole-trajectory number
     post_landing_max         largest error after touch-down under the flight-window
                              alignment: what the estimate does while the vehicle stands
                              still again (ORB-SLAM3 loses the scene on the ground and
                              drifts on its IMU; that spoils a whole-trajectory APE)
  H2 drift_pct                mean RPE translation over --seg metre segments / seg x 100
  H3 tsr                      tracking success rate: fraction of the flight window (0.1 s
                              grid) where a pose exists within 0.5 s and its error < tau
     tsr_start                the same, but with the trajectory aligned on its first 20 s
                              of flight only. A run that tracks for a minute and then diverges keeps
                              its good minute here; under the global alignment the diverged
                              tail spoils the fit and tsr collapses towards 0
     coverage_air             Decision D1: fraction of the flight window the estimate spans,
                              holes > 1 s excluded. The flight window runs from the first
                              ground-truth motion (> 0.10 m from the start pose: take-off on
                              a PX4 flight) to the last (> 0.10 m from the end pose:
                              touch-down)
  S1 yaw_rmse_deg             heading error of the body x axis, after alignment (assumes the
                              estimate's body frame is the IMU frame, as for all three
                              methods here; yaw_mean_deg far from 0 would say it is not)
  S2 startup_s                first estimated pose minus flight-window start (0 if earlier)
  H5 cpu_* / rss_peak_mb      from cost_probe.py's CSV; latency_* from latency_probe.py's
"""
import argparse
import copy
import csv
import json
import math
import os
import zipfile

import numpy as np
from evo.core import geometry, lie_algebra as lie, metrics, sync
from evo.core.units import Unit
from evo.tools import file_interface

MAX_DIFF = 0.02          # same as eval_traj.sh
MOVE_THR = 0.10          # m, flight-window detection
HOLE = 1.0               # s, a gap longer than this is not covered
NEAR = 0.5               # s, TSR: a grid point needs a pose this close
START = 20.0             # s, tsr_start: alignment uses the first START s of flight


def flight_window(t, p):
    d0 = np.linalg.norm(p - p[0], axis=1)
    d1 = np.linalg.norm(p - p[-1], axis=1)
    if not (d0 > MOVE_THR).any():
        return t[0], t[-1]                 # never moved: the whole bag
    i0 = int(np.argmax(d0 > MOVE_THR))
    i1 = len(t) - 1 - int(np.argmax(d1[::-1] > MOVE_THR))
    if t[i1] - t[i0] < 1.0:
        return t[0], t[-1]                 # a twitch, not a flight: the whole bag
    return t[i0], t[i1]


def covered(grid, ts):
    """True where a grid instant lies between two consecutive estimate stamps <= HOLE apart."""
    if len(ts) == 0:
        return np.zeros(len(grid), bool)
    k = np.searchsorted(ts, grid, side="right")
    ok = np.zeros(len(grid), bool)
    inside = (k > 0) & (k < len(ts))
    ok[inside] = (ts[k[inside]] - ts[k[inside] - 1]) <= HOLE
    ok |= np.isin(grid, ts)                # exactly on the last stamp
    return ok


def heading(q_wxyz):
    """Heading of the body x axis in the world xy plane, rad (robust to the inverted mount)."""
    w, x, y, z = q_wxyz.T
    r00 = 1 - 2 * (y * y + z * z)
    r10 = 2 * (x * y + w * z)
    return np.arctan2(r10, r00)


def cost_summary(path):
    rows = list(csv.DictReader(open(path)))
    if not rows:
        return {}
    cpu = np.array([float(r["cpu_pct"]) for r in rows[1:]] or [0.0])
    busy = np.flatnonzero(cpu > 5.0)       # playback = first to last busy sample, nothing
    act = cpu[busy[0]:busy[-1] + 1] if len(busy) else cpu   # dropped inside it (idle waits are outside)
    rss = np.array([float(r["rss_mb"]) for r in rows])
    return dict(cpu_mean_pct=float(act.mean()), cpu_p95_pct=float(np.percentile(act, 95)),
                rss_peak_mb=float(rss.max()), cpu_total_s=float(rows[-1]["cpu_total_s"]),
                cost_samples=len(rows))


def latency_summary(path):
    lat = np.array([float(r["latency_ms"]) for r in csv.DictReader(open(path))])
    if len(lat) == 0:
        return {}
    return dict(latency_median_ms=float(np.median(lat)), latency_p95_ms=float(np.percentile(lat, 95)),
                latency_max_ms=float(lat.max()), latency_samples=int(len(lat)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("gt")
    ap.add_argument("est")
    ap.add_argument("prefix")
    ap.add_argument("--tau", type=float, default=0.25, help="TSR error threshold, m (indoor 0.25, outdoor 1.0)")
    ap.add_argument("--seg", type=float, default=10.0, help="drift segment length, m")
    ap.add_argument("--cost")
    ap.add_argument("--latency")
    a = ap.parse_args()

    ref_full = file_interface.read_tum_trajectory_file(a.gt)
    est_full = file_interface.read_tum_trajectory_file(a.est)
    t_gt, p_gt = ref_full.timestamps, ref_full.positions_xyz
    w0, w1 = flight_window(t_gt, p_gt)

    ref, est = sync.associate_trajectories(ref_full, est_full, MAX_DIFF,
                                           first_name="reference", snd_name="estimate")
    est_start = copy.deepcopy(est)
    p_raw = est.positions_xyz.copy()
    est.align(ref, correct_scale=False)
    # start-aligned copy: SE(3) fit on the first START s of FLIGHT only (a stationary hold
    # cannot define a rotation), applied to the whole trajectory
    seg = (est.timestamps >= max(w0, est.timestamps[0])) & (est.timestamps <= max(w0, est.timestamps[0]) + START)
    e_start = None
    if seg.sum() >= 10 and np.ptp(ref.positions_xyz[seg], axis=0).max() > 1.0:
        try:
            r_a, t_a, _ = geometry.umeyama_alignment(est_start.positions_xyz[seg].T,
                                                     ref.positions_xyz[seg].T, False)
            est_start.transform(lie.se3(r_a, t_a))
            e_start = np.linalg.norm(est_start.positions_xyz - ref.positions_xyz, axis=1)
        except geometry.GeometryException:
            e_start = None
    e = est.positions_xyz - ref.positions_xyz
    e_h = np.linalg.norm(e[:, :2], axis=1)
    e_v = np.abs(e[:, 2])
    e_3d = np.linalg.norm(e, axis=1)
    yaw = np.degrees(np.angle(np.exp(1j * (heading(est.orientations_quat_wxyz) -
                                             heading(ref.orientations_quat_wxyz)))))
    rms = lambda x: float(math.sqrt(np.mean(np.square(x))))

    out = dict(gt=a.gt, est=a.est, tau_m=a.tau, seg_m=a.seg, matched_poses=int(len(e)),
               ape_rmse=rms(e_3d), ape_h_rmse=rms(e_h), ape_v_rmse=rms(e_v),
               ape_h_max=float(e_h.max()), ape_v_max=float(e_v.max()), ape_max=float(e_3d.max()),
               yaw_rmse_deg=rms(yaw), yaw_max_deg=float(np.abs(yaw).max()),
               yaw_mean_deg=float(np.mean(yaw)), failed=False)

    # flight-window APE: alignment and error on [w0, w1] only
    air = (est.timestamps >= w0) & (est.timestamps <= w1)
    if air.sum() >= 10 and np.ptp(ref.positions_xyz[air], axis=0).max() > 1.0:
        try:
            r_a, t_a, _ = geometry.umeyama_alignment(p_raw[air].T, ref.positions_xyz[air].T, False)
            e_all = (p_raw @ r_a.T + t_a) - ref.positions_xyz
            ea = e_all[air]
            out.update(ape_air_rmse=rms(np.linalg.norm(ea, axis=1)),
                       ape_air_h_rmse=rms(np.linalg.norm(ea[:, :2], axis=1)),
                       ape_air_v_rmse=rms(np.abs(ea[:, 2])),
                       ape_air_max=float(np.linalg.norm(ea, axis=1).max()))
            after = est.timestamps > w1
            if after.any():
                out["post_landing_max"] = float(np.linalg.norm(e_all[after], axis=1).max())
        except geometry.GeometryException:
            pass

    # cross-check against evo_ape's own number (eval_traj.sh ran first)
    z = a.prefix + "_ape.zip"
    if os.path.exists(z):
        with zipfile.ZipFile(z) as f:
            evo_rmse = json.loads(f.read("stats.json"))["rmse"]
        out["evo_ape_rmse"] = evo_rmse
        if abs(evo_rmse - out["ape_rmse"]) > 1e-6:
            raise SystemExit("!! APE mismatch with evo: %.9f vs %.9f" % (out["ape_rmse"], evo_rmse))

    # H2 drift: RPE over seg-metre segments (alignment-free in effect). Segments are
    # measured along the GROUND-TRUTH path (pairs_from_reference): along the estimate's own
    # path a diverging run lengthens its path and so shrinks its own drift figure.
    path_len = float(np.sum(np.linalg.norm(np.diff(ref.positions_xyz, axis=0), axis=1)))
    out["path_length_m"] = path_len
    try:
        rpe = metrics.RPE(metrics.PoseRelation.translation_part, delta=a.seg,
                          delta_unit=Unit.meters, all_pairs=True, pairs_from_reference=True)
        rpe.process_data((ref, est))
        out["drift_pct"] = float(np.mean(rpe.error)) / a.seg * 100.0
        out["drift_segments"] = int(len(rpe.error))
        rpe_r = metrics.RPE(metrics.PoseRelation.rotation_angle_deg, delta=a.seg,
                            delta_unit=Unit.meters, all_pairs=True, pairs_from_reference=True)
        rpe_r.process_data((ref, est))
        out["rot_drift_deg_per_seg"] = float(np.mean(rpe_r.error))
    except Exception as ex:                          # path shorter than one segment
        out["drift_pct"] = float("nan")
        out["drift_note"] = str(ex)

    # D1 coverage, H3 TSR, S2 start-up -- all on the flight window
    ts_all = np.sort(est_full.timestamps)
    grid = np.arange(w0, w1, 0.1)
    cov = covered(grid, ts_all)
    k = np.clip(np.searchsorted(est.timestamps, grid), 1, len(est.timestamps) - 1)
    left, right = est.timestamps[k - 1], est.timestamps[k]
    near = np.where(np.abs(grid - left) <= np.abs(right - grid), k - 1, k)
    close = cov & (np.abs(est.timestamps[near] - grid) <= NEAR)
    ok = close & (e_3d[near] < a.tau)
    out["tsr_start"] = float((close & (e_start[near] < a.tau)).mean()) if e_start is not None else float("nan")
    out.update(window_start=float(w0), window_end=float(w1), window_s=float(w1 - w0),
               coverage_air=float(cov.mean()), tsr=float(ok.mean()),
               first_pose_s=float(ts_all[0]), last_pose_s=float(ts_all[-1]),
               startup_s=float(max(0.0, ts_all[0] - w0)),
               coverage_bag=float(min(1.0, (ts_all[-1] - ts_all[0]) / (t_gt[-1] - t_gt[0]))))
    gaps = np.diff(ts_all[(ts_all >= w0) & (ts_all <= w1)])
    out["max_gap_s"] = float(gaps.max()) if len(gaps) else float("nan")

    if a.cost and os.path.exists(a.cost):
        out.update(cost_summary(a.cost))
    if a.latency and os.path.exists(a.latency):
        out.update(latency_summary(a.latency))

    with open(a.prefix + "_extra.json", "w") as f:
        json.dump(out, f, indent=1)
    with open(a.prefix + "_errors.csv", "w") as f:
        f.write("t,ex,ey,ez,e_h,e_v,e_3d,yaw_err_deg\n")
        for i in range(len(e)):
            f.write("%.6f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.3f\n" % (
                est.timestamps[i], e[i, 0], e[i, 1], e[i, 2], e_h[i], e_v[i], e_3d[i], yaw[i]))
    print("%s  APE h %.4f v %.4f m  yaw %.2f deg  drift %.2f %%  TSR %.3f  cov_air %.3f  startup %.1f s" % (
        os.path.basename(a.prefix), out["ape_h_rmse"], out["ape_v_rmse"], out["yaw_rmse_deg"],
        out["drift_pct"], out["tsr"], out["coverage_air"], out["startup_s"]))


if __name__ == "__main__":
    main()
