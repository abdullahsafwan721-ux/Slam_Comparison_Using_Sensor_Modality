#!/usr/bin/env python3
"""Stage 4 figures. Runs INSIDE the eval container:
    python3 /scripts/stage4/plot_sweeps.py /output/stage4

Guide 4.3, EXTENDED (docs/stage4_log.md). For each sweep (altitude, speed, imu):

  fig_<group>_guide.png  the guide's figure exactly: whole-bag APE (median of runs) from
                         <group>/eval/summary.csv, hollow marker = worst whole-bag
                         coverage < 0.95.
  fig_<group>.png        the headline figure (Decisions D1, D3): three panels from
                         <group>/eval/summary_extra.csv -- APE over the flight window,
                         its vertical part, and drift % per 10 m -- hollow marker = a run
                         failed or flight-window coverage < 0.95, so a partial
                         trajectory's flattering APE is never mistaken for a success.

The environments group has no numeric axis; scorecard.py draws it.
"""
import csv
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SWEEPS = {  # group: (condition regex, x label, log-x)
    "altitude": (r"urban_alt(\d+)", "Flight altitude (m)", False),
    "speed": (r"urban_speed(\d+)", "Cruise speed (m/s)", False),
    "imu": (r"imu_x(\d+)", "IMU noise (x EuRoC ADIS16448 baseline)", True),
}
# the project's fixed categorical order (same colours in every Stage 3-4 figure)
STYLE = {"fastlio2": ("#2a78d6", "o", "FAST-LIO2"), "fastlivo2": ("#eb6834", "s", "FAST-LIVO2"),
         "orbslam3": ("#1baf7a", "^", "ORB-SLAM3")}
INK, MUT, GRID = "#1f2933", "#6b7280", "#e5e7eb"


def guide_figure(root, group, pat, xlabel, logx):
    """The guide's plot_sweeps.py, unchanged apart from colours and the file name."""
    f = os.path.join(root, group, "eval", "summary.csv")
    if not os.path.exists(f):
        return
    series = {}
    for r in csv.DictReader(open(f)):
        m = re.fullmatch(pat, r["condition"])
        if m and r["algorithm"] in STYLE:
            series.setdefault(r["algorithm"], []).append(
                (float(m.group(1)), float(r["ape_rmse_median_m"]), float(r["worst_coverage"])))
    if not series:
        return
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for algo, pts in sorted(series.items()):
        pts.sort()
        col, mk, label = STYLE[algo]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=col, lw=1.6, label=label)
        for x, y, c in pts:
            ax.plot(x, y, mk, color=col, ms=6, mfc=col if c >= 0.95 else "none")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("APE RMSE (m), median of runs")
    ax.set_yscale("log")
    if logx:
        ax.set_xscale("log")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False)
    ax.set_title("Guide definition: whole-bag APE and coverage. Hollow = coverage < 0.95",
                 fontsize=9, color="#555555")
    fig.tight_layout()
    out = os.path.join(root, "fig_%s_guide.png" % group)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print("wrote", out)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def headline_figure(root, group, pat, xlabel, logx):
    f = os.path.join(root, group, "eval", "summary_extra.csv")
    if not os.path.exists(f):
        return
    series = {}
    for r in csv.DictReader(open(f)):
        m = re.fullmatch(pat, r["condition"])
        if m and r["algorithm"] in STYLE:
            cov = num(r.get("coverage_air"))
            ok = (cov is not None and cov >= 0.95 and int(float(r.get("failed_runs") or 0)) == 0)
            series.setdefault(r["algorithm"], []).append(
                (float(m.group(1)), num(r.get("ape_air_rmse")), num(r.get("ape_air_v_rmse")),
                 num(r.get("drift_pct")), ok))
    if not series:
        return
    panels = [(1, "APE over the flight (m)", True), (2, "vertical APE over the flight (m)", True),
              (3, "drift (% of 10 m travelled)", True)]
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.9))
    for ax, (k, ylabel, logy) in zip(axes, panels):
        for algo in STYLE:
            pts = sorted(p for p in series.get(algo, []) if p[k] is not None and p[k] > 0)
            if not pts:
                continue
            col, mk, label = STYLE[algo]
            ax.plot([p[0] for p in pts], [p[k] for p in pts], color=col, lw=2, label=label)
            for p in pts:
                ax.plot(p[0], p[k], mk, color=col, ms=8, mfc=col if p[4] else "white", mew=1.6)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if logy:
            ax.set_yscale("log")
        if logx:
            ax.set_xscale("log")
        ax.yaxis.grid(True, which="major", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Median of runs. Hollow marker = a run failed or flight coverage < 0.95 "
                 "(its APE covers only part of the flight)", fontsize=9, color=MUT)
    fig.tight_layout()
    out = os.path.join(root, "fig_%s.png" % group)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print("wrote", out)


def main():
    root = sys.argv[1]
    for group, (pat, xlabel, logx) in SWEEPS.items():
        guide_figure(root, group, pat, xlabel, logx)
        headline_figure(root, group, pat, xlabel, logx)


if __name__ == "__main__":
    main()
