#!/usr/bin/env python3
"""Stage 5 figures and table (host, plain python3 + matplotlib, project root):

    python3 scripts/stage5/stage5_figures.py [output/stage5]

For every scored flight (flights/<name>.closed_loop.json):
  figures/closed_loop_<name>.png   path seen from above (truth, PX4's belief, setpoint),
                                   height over time with take-off and first touchdown, and
                                   the error of PX4's estimate and of the SLAM pose over time
and stage5_tables.md: one row per flight (guide 5.5 APEs + closed_loop_metrics.py report).
Colours follow the project: FAST-LIO2 is blue in every figure; PX4's estimate takes the
palette's next free hue (magenta), truth is ink; line style tells them apart as well.
"""
import glob
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import closed_loop_metrics as clm  # noqa: E402

ROOT = sys.argv[1] if len(sys.argv) > 1 else "output/stage5"
FL, FIG = os.path.join(ROOT, "flights"), os.path.join(ROOT, "figures")
INK, MUT, GRID = "#1f2933", "#6b7280", "#e5e7eb"
SLAM, PX4, SP = "#2a78d6", "#e87ba4", "#9ca3af"
# the project's colours: FAST-LIO2 blue, FAST-LIVO2 orange in every figure
ALGO = {"fastlio2": ("FAST-LIO2", "#2a78d6"), "fastlivo2": ("FAST-LIVO2", "#eb6834")}
M = clm.mount("config/generated/mount.yaml")


def style(ax):
    ax.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUT)
    ax.tick_params(colors=MUT, labelsize=8)


def err_series(est, tru, tol):
    e, r = clm.match(est, tru, tol)
    return e[:, 0], np.linalg.norm(e[:, 1:4] - r[:, 1:4], axis=1) * 100


def figure(name, o):
    lab, col = ALGO.get(o.get("algo", "fastlio2"), ALGO["fastlio2"])
    f = lambda k: clm.load(os.path.join(FL, "%s.%s.tum" % (name, k)))
    base = clm.to_base(f("gt"), M); vis, px4, sp = f("vision"), f("px4"), f("setpoint")
    tru = clm.local_truth(base, vis[0, 0])
    ta, tb = o["airborne_s"]
    t0 = ta - 5
    fig = plt.figure(figsize=(12, 4.2))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1.35, 1.35], wspace=0.28)
    a = fig.add_subplot(gs[0]); style(a)
    fly = lambda x: x[(x[:, 0] >= ta) & (x[:, 0] <= tb)]
    a.plot(fly(sp)[:, 1], fly(sp)[:, 2], ":", color=SP, lw=1.5, label="setpoint")
    a.plot(fly(tru)[:, 1], fly(tru)[:, 2], "-", color=INK, lw=2.0, label="truth")
    a.plot(fly(px4)[:, 1], fly(px4)[:, 2], "-", color=PX4, lw=1.2, label="PX4 estimate")
    a.set_aspect("equal"); a.set_xlabel("x (m)", color=MUT, fontsize=9); a.set_ylabel("y (m)", color=MUT, fontsize=9)
    a.set_title("Path from above (airborne)", fontsize=10, color=INK, loc="left")
    a.legend(fontsize=7.5, frameon=False, loc="best")
    b = fig.add_subplot(gs[1]); style(b)
    w = lambda x: x[(x[:, 0] >= t0) & (x[:, 0] <= tb + 8)]
    b.plot(w(sp)[:, 0] - ta, w(sp)[:, 3], ":", color=SP, lw=1.5, label="setpoint")
    b.plot(w(tru)[:, 0] - ta, w(tru)[:, 3], "-", color=INK, lw=2.0, label="truth")
    b.plot(w(vis)[:, 0] - ta, w(vis)[:, 3], "--", color=col, lw=1.4, label="%s pose sent to PX4" % lab)
    b.plot(w(px4)[:, 0] - ta, w(px4)[:, 3], "-", color=PX4, lw=1.2, label="PX4 estimate")
    b.axvline(tb - ta, color=MUT, lw=0.8)
    b.annotate("first touchdown", (tb - ta, b.get_ylim()[1]), xytext=(-4, -4), textcoords="offset points",
               ha="right", va="top", fontsize=7.5, color=MUT)
    b.set_xlabel("time since take-off (s)", color=MUT, fontsize=9); b.set_ylabel("height (m)", color=MUT, fontsize=9)
    b.set_title("Height", fontsize=10, color=INK, loc="left"); b.legend(fontsize=7.5, frameon=False, loc="lower center")
    c = fig.add_subplot(gs[2]); style(c)
    tp, ep = err_series(w(px4), tru, 0.02); tv, ev = err_series(w(vis), tru, 0.02)
    c.plot(tv - ta, ev, "--", color=col, lw=1.4, label="%s pose vs truth" % lab)
    if o.get("fault"):                                     # the live fault window
        for ax in (b, c):
            ax.axvspan(o["fault"]["start_s"], o["fault"]["end_s"], color="#f3c4c4", alpha=0.6, lw=0)
        c.annotate("fault", (o["fault"]["start_s"], c.get_ylim()[1]), xytext=(2, -4), textcoords="offset points",
                   va="top", fontsize=7.5, color=MUT)
    c.plot(tp - ta, ep, "-", color=PX4, lw=1.2, label="PX4 estimate vs truth")
    c.axvline(tb - ta, color=MUT, lw=0.8)
    c.set_xlabel("time since take-off (s)", color=MUT, fontsize=9); c.set_ylabel("position error (cm, unaligned)", color=MUT, fontsize=9)
    c.set_title("Error, in PX4's own frame", fontsize=10, color=INK, loc="left"); c.legend(fontsize=7.5, frameon=False, loc="upper left")
    fig.suptitle("Stage 5 closed loop, %s: PX4 flying on %s alone (no GPS, barometer or magnetometer)" % (name, lab),
                 fontsize=11, color=INK, x=0.06, ha="left")
    os.makedirs(FIG, exist_ok=True)
    fig.savefig(os.path.join(FIG, "closed_loop_%s.png" % name), dpi=180, bbox_inches="tight")
    plt.close(fig)


def ape(algo, name):
    p = os.path.join(ROOT, "eval", "%s__%s__r1_extra.json" % (algo, name))
    return json.load(open(p)) if os.path.exists(p) else {}


def notes(o):
    """Faults and PX4's in-flight mode changes other than the mission's own (OFFBOARD, AUTO.LAND)."""
    out = []
    fl = o.get("fault")
    if fl:
        out.append("fault %+.0f..%+.0f s, pose gap %.1f s, PX4 vs truth max %.0f cm in fault + 10 s" % (
            fl["start_s"], fl["end_s"], fl["vision_gap_s"],
            fl["px4_truth_fault_plus10s"]["max_m"] * 100 if fl.get("px4_truth_fault_plus10s") else float("nan")))
    odd = [m for m in o.get("modes", []) if m[1] not in ("OFFBOARD", "AUTO.LAND", "MANUAL", "AUTO.LOITER") and m[0] > 0]
    if odd:
        out.append("modes: " + ", ".join("%+.0f s %s" % (m[0], m[1]) for m in odd))
    return "; ".join(out) or "-"


def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(FL, "*.closed_loop.json"))):
        o = json.load(open(p)); n = o["name"]
        figure(n, o)
        a = o.get("algo", "fastlio2")
        fl, px = ape(a, n), ape("px4", n)
        cm = lambda d, k="rmse_m": "%.2f" % (d[k] * 100) if d and d.get(k) is not None else "-"
        hov = "; ".join("%.1f / %.1f / %.1f (max %.1f)" % (*h["sd_xyz_cm"], h["max_dev_cm"]) for h in o.get("hover", [])) or "-"
        rows.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s / %s | %s | %s | %s |" % (
            n, ALGO.get(a, (a,))[0], "%.1f" % (o["airborne_s"][1] - o["airborne_s"][0]),
            cm(fl, "ape_air_rmse"), cm(px, "ape_air_rmse"), cm(o.get("relay")), cm(o.get("ekf")), cm(o.get("px4_truth")),
            o.get("control_lag_s"), cm(o.get("control_lagged"), "h_rmse_m"), hov, cm(o.get("landing_px4_truth"), "max_m"),
            notes(o)))
    L = ["# Stage 5 tables", "",
         "Generated by scripts/stage5/stage5_figures.py. All errors in cm. APE columns: guide 5.5 (evo, SE(3)-aligned) "
         "over the flight window; the SLAM method against the IMU's ground truth, PX4 against base_link's. The next three "
         "are UNALIGNED, in PX4's own frame (closed_loop_metrics.py): what PX4 was told, what it believed, and where the "
         "vehicle really was.", "",
         "| Flight | Method | Airborne (s) | SLAM APE | PX4 APE | SLAM pose sent vs truth | PX4 vs SLAM pose | PX4 vs truth "
         "| Control lag (s) / path error h | Hover sd x / y / z (cm) | Landing: PX4 max error | Notes |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"] + rows
    open(os.path.join(ROOT, "stage5_tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
