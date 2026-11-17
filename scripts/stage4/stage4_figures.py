#!/usr/bin/env python3
"""Stage 4 tables and the figures beyond the guide's sweeps (host, plain python3).

    python3 scripts/stage4/stage4_figures.py [output/stage4]

Not in the guide; plan PDF section 5.3. Reads what run_matrix.sh / run_extras.sh wrote and
produces, in <root>/figures/ and <root>/stage4_tables.md:

  scorecard.png         environments and faults x algorithms: flight APE in fixed classes,
                        a cross where a run failed or flight coverage < 0.95
  faults_timeline.png   error over time (flight-window alignment) through each timed fault,
                        against the same algorithm on the clean flight
  altitude.png          measured ground returns per scan against the prediction from the
                        real scan pattern (altitude/ground_points.csv), and flight APE
  cost.png              flight APE against CPU, every condition
  stage4_tables.md      every group's table, the fault deltas, the headroom table

Every number is a median over runs, coverage and TSR are the worst run (as results_table.py).
"""
import csv
import glob
import json
import math
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

ROOT = sys.argv[1] if len(sys.argv) > 1 else "output/stage4"
FIG = os.path.join(ROOT, "figures")
ALGOS = [("fastlio2", "FAST-LIO2", "#2a78d6", "o"), ("fastlivo2", "FAST-LIVO2", "#eb6834", "s"),
         ("orbslam3", "ORB-SLAM3", "#1baf7a", "^")]
NAME = {a: n for a, n, _, _ in ALGOS}
INK, MUT, GRID = "#1f2933", "#6b7280", "#e5e7eb"
ENV = ["room", "room_plain", "corridor", "field"]
FAULTS = ["cam_black_5s", "cam_dim30", "cam_dim10", "cam_dt5", "cam_dt10", "cam_dt20",
          "lidar_drop_2s", "lidar_drop_5s", "lidar_thin25"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK, "xtick.color": MUT, "ytick.color": MUT})


def f(v):
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def summary(group):
    p = os.path.join(ROOT, group, "eval", "summary_extra.csv")
    if not os.path.exists(p):
        return {}
    return {(r["condition"], r["algorithm"]): r for r in csv.DictReader(open(p))}


def ok(r):
    return r is not None and f(r.get("coverage_air")) is not None and f(r["coverage_air"]) >= 0.95 \
        and int(float(r.get("failed_runs") or 0)) == 0


def cm(v):
    return "-" if v is None else "%.2f" % (100 * v)


# ------------------------------------------------------------------ tables
def group_table(group, conds=None):
    S = summary(group)
    if not S:
        return []
    conds = conds or sorted({c for c, _ in S}, key=lambda c: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", c)])
    L = ["### %s" % group, "",
         "| Condition | Algorithm | Runs (failed) | Flight APE (cm) | horiz. | vert. | Drift %/10 m | TSR | Flight cov. | "
         "Start-up (s) | Whole-bag APE (cm) | After landing max (m) | CPU (% core) | RAM (MB) | Pose age p95 (ms) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in conds:
        for a, n, _, _ in ALGOS:
            r = S.get((c, a))
            if r is None:
                continue
            g = lambda k: f(r.get(k))
            L.append("| %s | %s | %s (%s) | %s%s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                c, n, r["runs"], r.get("failed_runs", "0"), cm(g("ape_air_rmse")), "" if ok(r) else " ✗",
                cm(g("ape_air_h_rmse")), cm(g("ape_air_v_rmse")),
                "-" if g("drift_pct") is None else "%.2f" % g("drift_pct"),
                "-" if g("tsr") is None else "%.3f" % g("tsr"),
                "-" if g("coverage_air") is None else "%.3f" % g("coverage_air"),
                "-" if g("startup_s") is None else "%.1f" % g("startup_s"),
                cm(g("ape_rmse")), "-" if g("post_landing_max") is None else "%.3f" % g("post_landing_max"),
                "-" if g("cpu_mean_pct") is None else "%.0f" % g("cpu_mean_pct"),
                "-" if g("rss_peak_mb") is None else "%.0f" % g("rss_peak_mb"),
                "-" if g("latency_p95_ms") is None else "%.1f" % g("latency_p95_ms")))
    return L + [""]


def runs(group, cond, algo):
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, group, "eval", "%s__%s__r*_errors.csv" % (algo, cond)))):
        d = np.genfromtxt(p, delimiter=",", names=True)
        if d.size and "e_3d_flight" in d.dtype.names:
            out.append(d)
    return out


def fault_rows():
    base = summary("environments")
    S = summary("faults")
    rows = []
    for v in FAULTS:
        meta = os.path.join(ROOT, "faults", "flights", "room_%s.fault.json" % v)
        m = json.load(open(meta)) if os.path.exists(meta) else {}
        for a, n, _, _ in ALGOS:
            r = S.get(("room_" + v, a))
            if r is None:
                continue
            b = base.get(("room", a))
            peak, bpeak = None, None
            if m.get("timed"):
                lo, hi = m["fault_start_s"], m["fault_end_s"] + 5.0
                pk = [np.nanmax(d["e_3d_flight"][(d["t"] >= lo) & (d["t"] <= hi)]) for d in runs("faults", "room_" + v, a)
                      if ((d["t"] >= lo) & (d["t"] <= hi)).any()]
                bp = [np.nanmax(d["e_3d_flight"][(d["t"] >= lo) & (d["t"] <= hi)]) for d in runs("environments", "room", a)
                      if ((d["t"] >= lo) & (d["t"] <= hi)).any()]
                peak = float(np.median(pk)) if pk else None
                bpeak = float(np.median(bp)) if bp else None
            rows.append((v, a, n, r, b, peak, bpeak, m))
    return rows


def fault_table():
    rows = fault_rows()
    if not rows:
        return []
    L = ["### faults (room flight, one sensor degraded; clean = environments/room)", "",
         "| Fault | Algorithm | Runs (failed) | Flight APE (cm) | clean | ratio | Peak error in fault + 5 s (cm) | clean | TSR | Flight cov. |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for v, a, n, r, b, peak, bpeak, m in rows:
        x, y = f(r.get("ape_air_rmse")), f(b.get("ape_air_rmse")) if b else None
        L.append("| %s | %s | %s (%s) | %s%s | %s | %s | %s | %s | %s | %s |" % (
            v, n, r["runs"], r.get("failed_runs", "0"), cm(x), "" if ok(r) else " ✗", cm(y),
            "%.1fx" % (x / y) if x and y else "-", cm(peak), cm(bpeak),
            "-" if f(r.get("tsr")) is None else "%.3f" % f(r["tsr"]),
            "-" if f(r.get("coverage_air")) is None else "%.3f" % f(r["coverage_air"])))
    return L + [""]


def headroom_table():
    L = ["### headroom (replay rate; 1x = environments/room and speed/urban_speed5)", "",
         "| Flight | Algorithm | 1x APE (cm) / cov. | 2x | 4x | 8x | Headroom |", "|---|---|---|---|---|---|---|"]
    found = False
    for cond, g1 in (("room", "environments"), ("urban_speed5", "speed")):
        for a, n, _, _ in ALGOS[:2]:
            r1 = summary(g1).get((cond, a))
            if r1 is None:
                continue
            ref = f(r1.get("ape_air_rmse"))
            cells, head = [], 1
            for rate in (2, 4, 8):
                r = summary("headroom/rate%d" % rate).get((cond, a))
                if r is None:
                    cells.append("-")
                    continue
                found = True
                x = f(r.get("ape_air_rmse"))
                good = ok(r) and x is not None and ref is not None and x <= 1.5 * ref
                if good and head == rate // 2:
                    head = rate
                cells.append("%s / %.3f%s" % (cm(x), f(r.get("coverage_air")) or 0, "" if good else " ✗"))
            L.append("| %s | %s | %s / %.3f | %s | %s | %s | %dx |" % (cond, n, cm(ref), f(r1.get("coverage_air")) or 0,
                                                                      *cells, head))
    return L + [""] if found else []


# ------------------------------------------------------------------ figures
def scorecard():
    E, F = summary("environments"), summary("faults")
    rows = [(c, E, c) for c in ENV] + [("room_" + v, F, "fault: " + v) for v in FAULTS]
    rows = [r for r in rows if any((r[0], a) in r[1] for a, _, _, _ in ALGOS)]
    if not rows:
        return
    edges = [0.01, 0.03, 0.10, 0.30]                          # m
    shades = ["#dbe9f9", "#a9cbef", "#6aa3e0", "#2f73c4", "#173f73"]   # one hue, light -> dark
    labels = ["< 1 cm", "1-3 cm", "3-10 cm", "10-30 cm", "> 30 cm"]
    fig, ax = plt.subplots(figsize=(6.8, 0.42 * len(rows) + 1.6))
    for i, (cond, S, label) in enumerate(rows):
        for j, (a, n, _, _) in enumerate(ALGOS):
            r = S.get((cond, a))
            if r is None and S is F:                           # not affected: the clean run is the answer
                ax.add_patch(Rectangle((j, i), 1, 1, fc="white", ec=GRID, lw=1))
                ax.text(j + 0.5, i + 0.5, "unaffected", ha="center", va="center", fontsize=7, color=MUT)
                continue
            if r is None:
                continue
            x = f(r.get("ape_air_rmse"))
            if not ok(r) or x is None:
                ax.add_patch(Rectangle((j, i), 1, 1, fc="#f3f4f6", ec="white", lw=2, hatch="//"))
                ax.text(j + 0.5, i + 0.5, "✗ %s" % ("failed" if x is None else cm(x) + " cm"), ha="center",
                        va="center", fontsize=8, color=INK)
                continue
            k = int(np.searchsorted(edges, x))
            ax.add_patch(Rectangle((j, i), 1, 1, fc=shades[k], ec="white", lw=2))
            ax.text(j + 0.5, i + 0.5, "%s cm" % cm(x), ha="center", va="center", fontsize=8,
                    color="white" if k >= 3 else INK)
    ax.set_xlim(0, 3); ax.set_ylim(len(rows), 0)
    ax.set_xticks([0.5, 1.5, 2.5]); ax.set_xticklabels([n for _, n, _, _ in ALGOS])
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(rows))]); ax.set_yticklabels([r[2] for r in rows])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    for k, (c, l) in enumerate(zip(shades, labels)):
        ax.add_patch(Rectangle((k * 0.6, len(rows) + 0.35), 0.18, 0.35, fc=c, clip_on=False))
        ax.text(k * 0.6 + 0.22, len(rows) + 0.53, l, fontsize=7, va="center", color=MUT, clip_on=False)
    ax.text(0, len(rows) + 1.15, "Flight-window APE, median of 3 runs. Hatched ✗ = a run failed or flight coverage < 0.95.",
            fontsize=7, color=MUT, clip_on=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "scorecard.png"), dpi=200)
    plt.close(fig)


def gapped(d, gap=0.5):
    """t, error with NaN inserted where no pose was published for > gap s, so a line
    is not drawn across an output gap (it would look like a gradual drift)."""
    t, e = d["t"], np.maximum(d["e_3d_flight"], 1e-4)
    k = np.where(np.diff(t) > gap)[0] + 1
    return np.insert(t, k, np.nan), np.insert(e, k, np.nan)


def faults_timeline():
    timed = [v for v in FAULTS if os.path.exists(os.path.join(ROOT, "faults", "flights", "room_%s.fault.json" % v))
             and json.load(open(os.path.join(ROOT, "faults", "flights", "room_%s.fault.json" % v))).get("timed")]
    timed = [v for v in timed if any(runs("faults", "room_" + v, a) for a, _, _, _ in ALGOS)]
    if not timed:
        return
    fig, axes = plt.subplots(len(timed), 1, figsize=(8.0, 2.4 * len(timed)), sharex=True, squeeze=False)
    for ax, v in zip(axes[:, 0], timed):
        m = json.load(open(os.path.join(ROOT, "faults", "flights", "room_%s.fault.json" % v)))
        ax.axvspan(m["fault_start_s"], m["fault_end_s"], color="#fde2d4", zorder=0)
        ax.text(m["fault_start_s"], 1.2, " fault", fontsize=7, color=MUT, va="top")
        for a, n, col, _ in ALGOS:
            rr = runs("faults", "room_" + v, a)
            if not rr:
                continue
            b = runs("environments", "room", a)
            if b:
                ax.plot(*gapped(b[0]), color=col, lw=1, ls=":", alpha=0.8)
            ax.plot(*gapped(rr[0]), color=col, lw=1.6, label=n)
        ax.set_yscale("log"); ax.set_ylim(5e-4, 3)
        ax.set_xlim(m["take_off_s"] - 1, m["touch_down_s"] + 1)
        ax.set_ylabel("error (m)")
        ax.set_title("%s (solid; dotted = same algorithm on the clean flight), run 1" % v, fontsize=8.6, loc="left", color=INK)
        ax.yaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.legend(frameon=False, fontsize=7.5, loc="upper left", ncol=3)
    axes[-1, 0].set_xlabel("simulation time (s)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "faults_timeline.png"), dpi=200)
    plt.close(fig)


def altitude():
    gp = os.path.join(ROOT, "altitude", "ground_points.csv")
    S = summary("altitude")
    if not (os.path.exists(gp) or S):
        return
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.0, 3.9))
    if os.path.exists(gp):
        g = sorted((r for r in csv.DictReader(open(gp)) if r["bag"].startswith("urban_alt")),
                   key=lambda r: float(r["altitude_m"]))
        h = [float(r["altitude_m"]) for r in g]
        a1.fill_between(h, [float(r["ground_p10"]) for r in g], [float(r["ground_p90"]) for r in g],
                        color="#a9cbef", alpha=0.6, lw=0, label="measured, 10-90 % of scans")
        a1.plot(h, [float(r["ground_median"]) for r in g], "o-", color="#2f73c4", lw=2, ms=6, label="measured, median")
        a1.plot(h, [float(r["predicted"]) for r in g], "--", color=INK, lw=1.4, label="predicted (scan pattern, flat ground)")
        a1.set_ylabel("ground returns per scan (of 20 000)")
        a1.set_xlabel("flight altitude (m)")
        a1.legend(frameon=False, fontsize=7.5)
        a1.yaxis.grid(True, color=GRID, lw=0.6)
    for a, n, col, mk in ALGOS:
        pts = sorted((int(re.fullmatch(r"urban_alt(\d+)", c).group(1)), r) for (c, al), r in S.items()
                     if al == a and re.fullmatch(r"urban_alt(\d+)", c))
        pts = [(x, f(r.get("ape_air_rmse")), ok(r)) for x, r in pts if f(r.get("ape_air_rmse"))]
        if not pts:
            continue
        a2.plot([p[0] for p in pts], [p[1] for p in pts], color=col, lw=2, label=n)
        for x, y, good in pts:
            a2.plot(x, y, mk, color=col, ms=8, mfc=col if good else "white", mew=1.6)
    a2.set_yscale("log"); a2.set_xlabel("flight altitude (m)"); a2.set_ylabel("APE over the flight (m)")
    a2.yaxis.grid(True, color=GRID, lw=0.6)
    a2.legend(frameon=False, fontsize=7.5)
    for ax in (a1, a2):
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    a2.set_title("hollow = a run failed or flight coverage < 0.95", fontsize=8, color=MUT, loc="left")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "altitude.png"), dpi=200)
    plt.close(fig)


def cost():
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    any_ = False
    for a, n, col, mk in ALGOS:
        xs, ys = [], []
        for group in ("environments", "altitude", "speed", "imu"):
            for (c, al), r in summary(group).items():
                if al == a and f(r.get("cpu_mean_pct")) and f(r.get("ape_air_rmse")):
                    xs.append(f(r["cpu_mean_pct"]) / 100.0)
                    ys.append(f(r["ape_air_rmse"]))
        if xs:
            any_ = True
            ax.scatter(xs, ys, s=40, color=col, marker=mk, label=n, edgecolor="white", lw=0.8)
    if not any_:
        plt.close(fig)
        return
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("CPU, cores (mean over the run, workstation)"); ax.set_ylabel("APE over the flight (m)")
    ax.set_title("Every Stage 4 condition, median of 3 runs", fontsize=8.6, loc="left", color=INK)
    ax.grid(True, which="major", color=GRID, lw=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=7.5)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "cost.png"), dpi=200)
    plt.close(fig)


def main():
    os.makedirs(FIG, exist_ok=True)
    L = ["# Stage 4 tables", "", "Generated by scripts/stage4/stage4_figures.py from the eval/summary_extra.csv files. "
         "APE in cm over the flight window (D3), median of runs; TSR and coverage are the worst run; "
         "✗ = a run failed or flight coverage < 0.95.", ""]
    L += group_table("environments", ENV)
    for g in ("altitude", "speed", "imu"):
        L += group_table(g)
    L += fault_table()
    L += headroom_table()
    open(os.path.join(ROOT, "stage4_tables.md"), "w").write("\n".join(L) + "\n")
    for fn in (scorecard, faults_timeline, altitude, cost):
        fn()
    print("wrote", os.path.join(ROOT, "stage4_tables.md"), "and", sorted(os.listdir(FIG)))


if __name__ == "__main__":
    main()
