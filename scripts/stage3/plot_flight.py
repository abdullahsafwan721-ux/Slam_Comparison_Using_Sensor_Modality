#!/usr/bin/env python3
"""One picture of a PX4 flight and how the three algorithms followed it (host, plain python3).

    python3 scripts/stage3/plot_flight.py <world-file> <outdir> <condition> <out.png> [run=1]

<outdir> is a run_all_algos.sh output directory. Left: top view of the world's boxes with the
ground-truth path (boxes tall enough to reach the flight band are dark). Right: position
error over time of run <run> of each algorithm, aligned on the flight window (Decision D3),
on a log axis, with the flight window marked. Added in Stage 3; not in the project guide.
"""
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_clearance import BELOW, boxes  # noqa: E402

INK, MUT, GRID = "#1f2933", "#6b7280", "#e5e7eb"
ALGOS = [("fastlio2", "FAST-LIO2", "#2a78d6"), ("fastlivo2", "FAST-LIVO2", "#eb6834"),
         ("orbslam3", "ORB-SLAM3", "#1baf7a")]


def umeyama(a, b):
    """Rigid transform (R, t) that maps points a onto b, least squares, no scale."""
    ma, mb = a.mean(0), b.mean(0)
    u, _, vt = np.linalg.svd((b - mb).T @ (a - ma))
    s = np.eye(3)
    s[2, 2] = np.sign(np.linalg.det(u @ vt))
    r = u @ s @ vt
    return r, mb - r @ ma


def main():
    world, out, cond, png = sys.argv[1:5]
    run = sys.argv[5] if len(sys.argv) > 5 else "1"
    gt = np.loadtxt(os.path.join(out, "gt", cond + ".tum"))
    ex = json.load(open(os.path.join(out, "eval", "fastlio2__%s__r%s_extra.json" % (cond, run))))
    w0, w1 = ex["window_start"], ex["window_end"]          # bag stamps (simulation time), s
    alt = float(np.median(gt[(gt[:, 0] > w0 + 8) & (gt[:, 0] < w1 - 8), 3]))

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": GRID})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.6), dpi=200, gridspec_kw={"width_ratios": [1.15, 1]})

    for name, x, y, yaw, hx, hy, top in boxes(world):
        c, s = math.cos(yaw), math.sin(yaw)
        pts = [(x + c * dx - s * dy, y + s * dx + c * dy) for dx, dy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
        tall = top > alt - BELOW
        a1.add_patch(Polygon(pts, closed=True, fc="#9ca3af" if tall else "#e5e7eb", ec="white", lw=0.6, zorder=1))
    a1.plot(gt[:, 1], gt[:, 2], color=INK, lw=1.4, zorder=3)
    a1.plot(gt[0, 1], gt[0, 2], "o", ms=7, mfc="white", mec=INK, mew=1.6, zorder=4)
    a1.annotate("take-off and landing", (gt[0, 1], gt[0, 2]), xytext=(8, -14), textcoords="offset points",
                fontsize=7.6, color=INK)
    a1.set_aspect("equal"); a1.autoscale_view()
    a1.set_xlabel("x (m)"); a1.set_ylabel("y (m)")
    a1.set_title("Top view: ground-truth path at %.1f m; dark boxes reach the flight band" % alt,
                 fontsize=8.6, color=INK, loc="left")
    for s in ("top", "right"):
        a1.spines[s].set_visible(False)

    a2.axvspan(w0, w1, color="#f3f4f6", zorder=0)
    a2.text((w0 + w1) / 2, 0.97, "flight window (take-off to touch-down)", transform=a2.get_xaxis_transform(), ha="center", va="top",
            fontsize=7.6, color=MUT)
    for key, label, col in ALGOS:
        f = os.path.join(out, key, "%s__%s__r%s.tum" % (key, cond, run))
        if not (os.path.exists(f) and os.path.getsize(f)):
            continue
        e = np.loadtxt(f)
        i = np.searchsorted(gt[:, 0], e[:, 0]).clip(1, len(gt) - 1)
        i -= (e[:, 0] - gt[i - 1, 0]) < (gt[i, 0] - e[:, 0])
        ok = np.abs(gt[i, 0] - e[:, 0]) < 0.02
        e, g = e[ok], gt[i[ok]]
        air = (e[:, 0] >= w0) & (e[:, 0] <= w1)
        r, t = umeyama(e[air, 1:4], g[air, 1:4])
        err = np.linalg.norm((e[:, 1:4] @ r.T + t) - g[:, 1:4], axis=1)
        a2.plot(e[:, 0], np.maximum(err, 1e-4), color=col, lw=1.3, label=label)
    a2.set_yscale("log"); a2.set_ylim(1e-4, 3)
    a2.set_xlim(gt[0, 0], gt[-1, 0])
    a2.set_xlabel("simulation time (s)"); a2.set_ylabel("position error (m)")
    a2.set_title("Error over time, run %s, aligned on the flight window" % run, fontsize=8.6, color=INK, loc="left")
    a2.yaxis.grid(True, color=GRID, lw=0.6); a2.set_axisbelow(True)
    for s in ("top", "right"):
        a2.spines[s].set_visible(False)
    a2.legend(frameon=False, fontsize=7.8, loc="lower left", ncol=3)
    fig.tight_layout()
    fig.savefig(png)
    print("wrote", png)


if __name__ == "__main__":
    main()
