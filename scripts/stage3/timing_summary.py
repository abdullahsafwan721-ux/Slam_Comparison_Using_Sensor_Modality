#!/usr/bin/env python3
"""Summarise ORB-SLAM3's per-frame tracking time (written by its REGISTER_TIMES build).

    python3 timing_summary.py <outdir>/orbslam3_times <euroc>/times.txt

Called by orbslam3_timing.sh. For every run directory r<N> reads TrackingTimeStats.txt
(one row per camera frame, in order; last column Total[ms]) and the run's trajectory, and
reports the time over (a) all frames and (b) the frames that got a pose, i.e. while the
system was initialised and working -- before that a frame costs feature extraction only.
Headroom = camera period / p95: above 1 the tracker keeps up with the camera.
Writes summary.md and summary.json beside the run directories.
"""
import glob
import json
import os
import sys

import numpy as np


def main():
    root, times = sys.argv[1], sys.argv[2]
    stamps = np.loadtxt(times) / 1e9
    period_ms = 1000.0 * float(np.median(np.diff(stamps)))
    rows = []
    for d in sorted(glob.glob(os.path.join(root, "r*"))):
        tt = np.loadtxt(os.path.join(d, "TrackingTimeStats.txt"), delimiter=",", comments="#")
        total = tt[:, -1]
        if len(total) != len(stamps):
            sys.exit("%s: %d timing rows for %d frames" % (d, len(total), len(stamps)))
        tum = glob.glob(os.path.join(d, "*.tum"))[0]
        est = np.loadtxt(tum)[:, 0] if os.path.getsize(tum) else np.array([])
        has_pose = np.isin(np.round(stamps, 3), np.round(est, 3))
        ex = glob.glob(os.path.join(d, "*_extra.json"))
        extra = json.load(open(ex[0])) if ex else {}
        t = total[has_pose] if has_pose.any() else total
        rows.append(dict(
            run=os.path.basename(d), frames=int(len(total)), frames_with_pose=int(has_pose.sum()),
            all_median_ms=float(np.median(total)), all_p95_ms=float(np.percentile(total, 95)),
            median_ms=float(np.median(t)), p95_ms=float(np.percentile(t, 95)),
            p99_ms=float(np.percentile(t, 99)), max_ms=float(t.max()),
            over_period_pct=float(100.0 * np.mean(t > period_ms)),
            headroom=float(period_ms / np.percentile(t, 95)),
            orb_extract_ms=float(np.median(tt[has_pose, 2])), local_map_ms=float(np.median(tt[has_pose, 6])),
            ape_air_rmse=extra.get("ape_air_rmse"), coverage_air=extra.get("coverage_air")))
    med = lambda k: float(np.median([r[k] for r in rows]))
    out = dict(camera_period_ms=period_ms, runs=rows,
               median_of_runs={k: med(k) for k in ("median_ms", "p95_ms", "p99_ms", "max_ms",
                                                   "over_period_pct", "headroom")})
    json.dump(out, open(os.path.join(root, "summary.json"), "w"), indent=1)
    L = ["ORB-SLAM3 tracking time per frame, timing build (camera period %.1f ms)" % period_ms, "",
         "| Run | Frames with pose | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) | Frames over period (%) "
         "| Headroom (period / p95) | Flight APE (m) | Flight coverage |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %d of %d | %.1f | %.1f | %.1f | %.1f | %.2f | %.1f | %s | %s |" % (
            r["run"], r["frames_with_pose"], r["frames"], r["median_ms"], r["p95_ms"], r["p99_ms"],
            r["max_ms"], r["over_period_pct"], r["headroom"],
            "%.4f" % r["ape_air_rmse"] if r["ape_air_rmse"] is not None else "-",
            "%.3f" % r["coverage_air"] if r["coverage_air"] is not None else "-"))
    m = out["median_of_runs"]
    L.append("| **median** | | %.1f | %.1f | %.1f | %.1f | %.2f | %.1f | | |" % (
        m["median_ms"], m["p95_ms"], m["p99_ms"], m["max_ms"], m["over_period_pct"], m["headroom"]))
    open(os.path.join(root, "summary.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
