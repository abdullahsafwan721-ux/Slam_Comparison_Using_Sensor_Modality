#!/usr/bin/env python3
"""Build docs/eVTOL_SLAM_Research_and_Stage3-5_Plan.pdf (host, plain python3).

Reference document: research findings of the 14-16 Nov 2026 sessions (project summary,
literature/web research, final metric framework) plus a detailed implementation plan for
Stages 3, 4 and 5. Figures are computed here (the altitude prediction uses the real
Mid-360 scan pattern copied from evtol/sim:v1).

    python3 docs/make_reference_pdf.py [path/to/mid360-real-centr.csv]
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Preformatted, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(REPO, "docs", "eVTOL_SLAM_Research_and_Stage3-5_Plan.pdf")
FIG = os.path.join(os.environ.get("FIGDIR", "/tmp"), "evtol_ref_figs")
os.makedirs(FIG, exist_ok=True)
CSV = sys.argv[1] if len(sys.argv) > 1 else None

# ------------------------------------------------------------------ fonts & styles
D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", D + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DV-B", D + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DV-I", D + "DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DV-BI", D + "DejaVuSans-BoldOblique.ttf"))
pdfmetrics.registerFont(TTFont("DVM", D + "DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")

INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#52514e")
RULE = colors.HexColor("#d9d9d4")
HEAD_BG = colors.HexColor("#eef1f5")
ACCENT = colors.HexColor("#2a78d6")

ST = {
    "title": ParagraphStyle("title", fontName="DV-B", fontSize=22, leading=27, textColor=INK, spaceAfter=6),
    "sub": ParagraphStyle("sub", fontName="DV", fontSize=11.5, leading=15, textColor=MUTED, spaceAfter=4),
    "h1n": ParagraphStyle("h1n", fontName="DV-B", fontSize=16, leading=20, textColor=INK, spaceAfter=8),
    "h1": ParagraphStyle("h1", fontName="DV-B", fontSize=16, leading=20, textColor=INK, spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="DV-B", fontSize=12.2, leading=15.5, textColor=INK, spaceBefore=10, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="DV-B", fontSize=10.2, leading=13, textColor=INK, spaceBefore=7, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="DV", fontSize=9.3, leading=13.2, textColor=INK, spaceAfter=5),
    "cell": ParagraphStyle("cell", fontName="DV", fontSize=8.0, leading=10.2, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="DV-B", fontSize=8.0, leading=10.2, textColor=INK),
    "bul": ParagraphStyle("bul", fontName="DV", fontSize=9.3, leading=13.0, textColor=INK, leftIndent=12,
                          bulletIndent=2, spaceAfter=2.5),
    "code": ParagraphStyle("code", fontName="DVM", fontSize=7.4, leading=9.6, textColor=INK),
    "cap": ParagraphStyle("cap", fontName="DV-I", fontSize=8.2, leading=10.5, textColor=MUTED, spaceAfter=8,
                          alignment=TA_CENTER),
    "note": ParagraphStyle("note", fontName="DV", fontSize=8.8, leading=12.2, textColor=INK),
    "toc1": ParagraphStyle("toc1", fontName="DV-B", fontSize=10, leading=15, leftIndent=0),
    "toc2": ParagraphStyle("toc2", fontName="DV", fontSize=9, leading=12.5, leftIndent=14, textColor=MUTED),
}

story = []


def P(t, s="p"):
    story.append(Paragraph(t, ST[s]))


def H1(t):
    story.append(PageBreak())
    story.append(Paragraph(t, ST["h1"]))


def H2(t):
    story.append(Paragraph(t, ST["h2"]))


def H3(t):
    story.append(Paragraph(t, ST["h3"]))


def BL(items):
    for it in items:
        story.append(Paragraph(it, ST["bul"], bulletText="•"))
    story.append(Spacer(1, 3))


def NL(items):
    for i, it in enumerate(items, 1):
        story.append(Paragraph(it, ST["bul"], bulletText="%d." % i))
    story.append(Spacer(1, 3))


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def CODE(t):
    pre = Preformatted(t.strip("\n"), ST["code"])
    tb = Table([[pre]], colWidths=[170 * mm])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f5f2")),
                            ("BOX", (0, 0), (-1, -1), 0.4, RULE),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.append(tb)
    story.append(Spacer(1, 6))


NOTE_COL = {"info": ("#eaf2fc", "#2a78d6"), "warn": ("#fdf3e1", "#c98500"),
            "key": ("#e8f6ef", "#1baf7a"), "decide": ("#f3e9f7", "#7a3fa0")}


def NOTE(title, text, kind="info"):
    bg, edge = NOTE_COL[kind]
    body = Paragraph("<b>%s</b> %s" % (title, text), ST["note"])
    tb = Table([[body]], colWidths=[170 * mm])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
                            ("LINEBEFORE", (0, 0), (0, -1), 2.5, colors.HexColor(edge)),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.append(tb)
    story.append(Spacer(1, 7))


def T(rows, widths, head=True, bold_first_col=False):
    data = []
    for i, r in enumerate(rows):
        row = []
        for j, c in enumerate(r):
            st = ST["cellb"] if (head and i == 0) or (bold_first_col and j == 0) else ST["cell"]
            row.append(Paragraph(str(c), st))
        data.append(row)
    tb = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if head else 0)
    sty = [("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LINEBELOW", (0, 0), (-1, -1), 0.35, RULE),
           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if head:
        sty += [("BACKGROUND", (0, 0), (-1, 0), HEAD_BG), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK)]
    tb.setStyle(TableStyle(sty))
    story.append(tb)
    story.append(Spacer(1, 8))


def FIGURE(path, width_mm, caption):
    import PIL.Image
    w, h = PIL.Image.open(path).size
    img = Image(path, width=width_mm * mm, height=width_mm * mm * h / w)
    story.append(KeepTogether([img, Paragraph(caption, ST["cap"])]))


# ------------------------------------------------------------------ figures
C_INK, C_MUT, C_GRID = "#1f2933", "#6b7280", "#e5e7eb"
SLOT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": C_GRID,
                     "axes.labelcolor": C_INK, "xtick.color": C_MUT, "ytick.color": C_MUT})


def box(ax, x, y, w, h, text, fc="#f3f4f6", ec="#9ca3af", fs=7.6, bold=False, tc=C_INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=0.9))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc,
            fontweight="bold" if bold else "normal", linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, text=None, col="#6b7280", fs=6.6, off=(0, 0.12)):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=col, lw=1.0, shrinkA=2, shrinkB=2))
    if text:
        ax.text((x1 + x2) / 2 + off[0], (y1 + y2) / 2 + off[1], text, ha="center", va="bottom",
                fontsize=fs, color=C_MUT)


def fig_pipeline():
    fig, ax = plt.subplots(figsize=(8.4, 3.3), dpi=220)
    ax.set_xlim(0, 12); ax.set_ylim(0, 4.6); ax.axis("off")
    box(ax, 0.1, 3.3, 2.2, 1.0, "config/rig.yaml\n(one source of truth)", fc="#eaf2fc", ec=SLOT[0], bold=True)
    box(ax, 0.1, 1.7, 2.2, 1.0, "gen_configs.py\ngen_world.py")
    box(ax, 0.1, 0.1, 2.2, 1.0, "Gazebo 11 + PX4 SITL\nMid-360 · IMU · stereo")
    arrow(ax, 1.2, 3.3, 1.2, 2.7); arrow(ax, 1.2, 1.7, 1.2, 1.1)
    box(ax, 3.0, 0.1, 2.0, 1.0, "flight .bag\nrecorded ONCE", fc="#fff7e6", ec="#c98500", bold=True)
    arrow(ax, 2.3, 0.6, 3.0, 0.6)
    box(ax, 3.0, 1.9, 2.0, 1.35, "per condition:\nIMU noise ×S\nor sensor fault\n(offline, seeded)")
    arrow(ax, 4.0, 1.1, 4.0, 1.9)
    box(ax, 5.8, 3.3, 2.1, 0.95, "FAST-LIO2\nLiDAR + IMU", fc="#eaf2fc", ec=SLOT[0])
    box(ax, 5.8, 2.05, 2.1, 0.95, "FAST-LIVO2\nLiDAR + cam + IMU", fc="#fdeee6", ec=SLOT[1])
    box(ax, 5.8, 0.8, 2.1, 0.95, "ORB-SLAM3\nstereo + IMU", fc="#e6f6ef", ec=SLOT[2])
    for y in (3.77, 2.52, 1.27):
        arrow(ax, 5.0, 2.57, 5.8, y)
    ax.text(6.85, 4.36, "same bytes to every algorithm, ×3 runs", fontsize=6.6, color=C_MUT, ha="center")
    box(ax, 8.6, 1.9, 1.5, 1.35, "evo (SE3)\n+ extra\nmetrics")
    for y in (3.77, 2.52, 1.27):
        arrow(ax, 7.9, y, 8.6, 2.57)
    box(ax, 10.6, 1.9, 1.3, 1.35, "summary\ntables\n+ figures", fc="#e8f6ef", ec="#1baf7a", bold=True)
    arrow(ax, 10.1, 2.57, 10.6, 2.57)
    box(ax, 8.6, 0.1, 1.5, 1.0, "ground truth\n(exact, 200 Hz)")
    arrow(ax, 5.0, 0.45, 8.6, 0.45); arrow(ax, 9.35, 1.1, 9.35, 1.9)
    fig.tight_layout(pad=0.2)
    p = os.path.join(FIG, "pipeline.png"); fig.savefig(p); plt.close(fig); return p


def fig_altitude():
    if CSV and os.path.exists(CSV):
        zen = np.loadtxt(CSV, delimiter=",", skiprows=1, usecols=2)
    else:
        sys.exit("need the Mid-360 scan CSV (argument 1)")
    es = np.radians(90.0 - zen)              # elevation in the sensor frame, -7..+52 deg
    hs = np.linspace(0.5, 60, 240)
    inv = [20000 * np.mean((es > 0) & (np.sin(np.clip(es, 1e-9, None)) >= h / 40.0)) for h in hs]
    upr = [20000 * np.mean((es < 0) & (np.sin(np.clip(-es, 1e-9, None)) >= h / 40.0)) for h in hs]
    fig, ax = plt.subplots(figsize=(7.6, 3.4), dpi=220)
    ax.plot(hs, inv, color=C_INK, lw=2, label="inverted mount (our design)")
    ax.plot(hs, upr, color="#8a8a85", lw=2, ls="--", label="upright mount (alternative)")
    for h in (10, 20, 30, 40, 50, 60):
        ax.axvline(h, color=C_GRID, lw=0.8, zorder=0)
    ax.axvspan(31.5, 60, color="#f3f4f6", zorder=-1)
    ax.text(45.5, 8500, "no ground return possible\n(h / sin 52° > 40 m)", ha="center", fontsize=7.4, color=C_MUT)
    ax.annotate("≈ 31.5 m", xy=(31.5, 0), xytext=(34.5, 4200), fontsize=7.4, color=C_INK,
                arrowprops=dict(arrowstyle="-", color=C_MUT, lw=0.8))
    ax.annotate("upright: ground gone\nabove ≈ 4.9 m", xy=(4.9, 30), xytext=(8, 2600), fontsize=7.2, color=C_MUT,
                arrowprops=dict(arrowstyle="-", color=C_MUT, lw=0.8))
    ax.set_xlabel("altitude above flat ground (m); grid lines = Stage 4 altitudes")
    ax.set_ylabel("ground points per scan (of 20 000)")
    ax.set_xlim(0, 60); ax.set_ylim(0, 17500)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.yaxis.grid(True, color=C_GRID, lw=0.6); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=7.6, loc="upper right", bbox_to_anchor=(1.0, 0.78))
    fig.tight_layout()
    p = os.path.join(FIG, "altitude.png"); fig.savefig(p); plt.close(fig)
    pts = {h: int(round(20000 * np.mean((es > 0) & (np.sin(np.clip(es, 1e-9, None)) >= h / 40.0))))
           for h in (1.5, 10, 20, 30, 40)}
    return p, pts


def fig_stage3():
    fig, ax = plt.subplots(figsize=(8.4, 4.1), dpi=220)
    ax.set_xlim(0, 12); ax.set_ylim(0, 5.8); ax.axis("off")
    box(ax, 0.1, 4.6, 2.6, 1.0, "input bag\nscripted_room.bag (3a)\nor PX4 flight (3b)", fc="#fff7e6", ec="#c98500")
    box(ax, 3.3, 4.6, 2.6, 1.0, "imu_noise.py\n×S, seed 1\n(eval container)")
    arrow(ax, 2.7, 5.1, 3.3, 5.1)
    box(ax, 6.5, 4.6, 2.3, 1.0, "bags/<cond>__imuS.bag\n(what every\nalgorithm sees)", fc="#fff7e6", ec="#c98500")
    arrow(ax, 5.9, 5.1, 6.5, 5.1)
    box(ax, 9.4, 4.6, 2.5, 1.0, "bag_to_tum.py\n→ gt/<cond>.tum\n(ground truth)")
    arrow(ax, 8.8, 5.1, 9.4, 5.1)
    box(ax, 0.1, 2.6, 3.4, 1.3, "fastlio2 container\nrun_ros_algo.sh fastlio2.launch\n→ /Odometry (10 Hz)", fc="#eaf2fc", ec=SLOT[0])
    box(ax, 4.0, 2.6, 3.4, 1.3, "fastlivo2 container\nrun_ros_algo.sh fastlivo2.launch\n→ /aft_mapped_to_init", fc="#fdeee6", ec=SLOT[1])
    box(ax, 7.9, 2.6, 4.0, 1.3, "bag_to_euroc.py → EuRoC folder\norbslam3 container\nstereo_inertial_euroc (Stage 1 binary)", fc="#e6f6ef", ec=SLOT[2])
    for x in (1.8, 5.7, 9.9):
        arrow(ax, 7.65, 4.6, x, 3.9)
    ax.text(0.15, 4.18, "each algorithm × RUNS (3)", fontsize=7, color=C_MUT)
    box(ax, 0.1, 0.4, 3.4, 1.4, "per run: <algo>__<cond>__rN.tum\n(bag_to_tum.py; ORB-SLAM3 file → TUM)\n+ cost.csv (new)\n+ latency.csv (LATENCY=1)")
    box(ax, 4.0, 0.4, 3.4, 1.4, "eval_traj.sh vs gt/<cond>.tum\nAPE, RPE/1 m, coverage\n+ metrics_extra.py (new)\nh/v split, yaw, drift %, TSR, start-up")
    box(ax, 7.9, 0.4, 4.0, 1.4, "results_table.py\neval/summary.md + summary.csv\n+ summary_extra.csv (new)", fc="#e8f6ef", ec="#1baf7a", bold=True)
    arrow(ax, 1.8, 2.6, 1.8, 1.8); arrow(ax, 5.7, 2.6, 2.9, 1.8); arrow(ax, 9.9, 2.6, 3.3, 1.75)
    arrow(ax, 3.5, 1.1, 4.0, 1.1); arrow(ax, 7.4, 1.1, 7.9, 1.1)
    fig.tight_layout(pad=0.2)
    p = os.path.join(FIG, "stage3.png"); fig.savefig(p); plt.close(fig); return p


def fig_stage5():
    fig, ax = plt.subplots(figsize=(8.4, 3.7), dpi=220)
    ax.set_xlim(0, 12); ax.set_ylim(0, 5.2); ax.axis("off")
    box(ax, 0.1, 3.6, 2.6, 1.3, "Gazebo + iris_evtol\nMid-360 /livox/lidar\nIMU /livox/imu", fc="#fff7e6", ec="#c98500")
    box(ax, 3.3, 3.6, 2.4, 1.3, "imu_noise_live.py\n→ /livox/imu_noisy")
    box(ax, 6.3, 3.6, 2.5, 1.3, "FAST-LIO2\n/Odometry\n(IMU pose in camera_init)", fc="#eaf2fc", ec=SLOT[0])
    box(ax, 9.4, 3.6, 2.5, 1.3, "slam_to_px4.py\nM · T · M⁻¹\n→ /mavros/vision_pose/pose", fc="#f3e9f7", ec="#7a3fa0", bold=True)
    arrow(ax, 2.7, 4.25, 3.3, 4.25); arrow(ax, 5.7, 4.25, 6.3, 4.25); arrow(ax, 8.8, 4.25, 9.4, 4.25)
    ax.annotate("", xy=(6.6, 3.6), xytext=(1.4, 3.6),
                arrowprops=dict(arrowstyle="-|>", color="#6b7280", lw=1.0, connectionstyle="arc3,rad=0.25"))
    ax.text(4.0, 3.12, "LiDAR scans (direct)", fontsize=6.6, color=C_MUT, ha="center")
    box(ax, 9.4, 1.2, 2.5, 1.4, "MAVROS → PX4 EKF2\nEV pos + yaw only\n(no GPS, baro, mag)", fc="#eaf2fc", ec=SLOT[0])
    arrow(ax, 10.65, 3.6, 10.65, 2.6)
    box(ax, 5.6, 1.2, 3.2, 1.4, "PX4 position controller\n/mavros/local_position/pose\n(what the drone believes)")
    arrow(ax, 9.4, 1.9, 8.8, 1.9)
    box(ax, 2.4, 1.2, 2.6, 1.4, "offboard_mission.py\nsquare setpoints\n(terminal 3)")
    arrow(ax, 5.0, 1.9, 5.6, 1.9)
    box(ax, 0.1, 0.1, 2.0, 0.9, "motors → physics")
    arrow(ax, 7.2, 1.2, 2.1, 0.55)
    arrow(ax, 1.1, 1.0, 1.1, 3.6)
    ax.text(0.15, 2.3, "closed\nloop", fontsize=7, color=C_INK, fontweight="bold")
    fig.tight_layout(pad=0.2)
    p = os.path.join(FIG, "stage5.png"); fig.savefig(p); plt.close(fig); return p


def fig_gantt():
    tasks = [  # (label, start day, length, category)
        ("Stage 3a: transcribe, IMU noise, scripted bag, new metrics", 1, 1, 0),
        ("Stage 3b: PX4 SITL flights, gate", 2, 1, 0),
        ("Stage 4 A: environments", 3, 1, 1),
        ("Stage 4 B: altitude (overnight)", 3.6, 1.4, 1),
        ("Stage 4 D: IMU grade", 4, 1, 1),
        ("Failure + timing-offset tests", 4.5, 2, 2),
        ("Stage 4 C: speed (overnight)", 6.5, 1, 1),
        ("Headroom, ground points, error-over-time", 6, 1, 2),
        ("Figures, scorecard; Stage 5 go/no-go", 7, 1, 3),
        ("Stage 5 OR stretch (mounting / map)", 8, 1, 2),
        ("Videos, recommendation table, slides", 9, 1, 3),
        ("Buffer + rehearsal", 10, 1, 4),
    ]
    cats = ["Stage 3", "Stage 4 core", "Additions", "Presentation", "Buffer"]
    fig, ax = plt.subplots(figsize=(8.4, 3.9), dpi=220)
    for i, (lab, s, l, c) in enumerate(tasks):
        y = len(tasks) - i
        ax.barh(y, l - 0.06, left=s, height=0.62, color=SLOT[c], edgecolor="white", linewidth=1)
        ax.text(0.92, y, lab, ha="right", va="center", fontsize=7.2, color=C_INK)
    days = ["Mon 16", "Tue 17", "Wed 18", "Thu 19", "Fri 20", "Sat 21", "Sun 22", "Mon 23", "Tue 24", "Wed 25"]
    ax.set_xticks([d + 0.5 for d in range(1, 11)]); ax.set_xticklabels(days, fontsize=7)
    ax.set_xlim(1, 11); ax.set_yticks([])
    for d in range(1, 12):
        ax.axvline(d, color=C_GRID, lw=0.6, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=SLOT[i], label=c) for i, c in enumerate(cats)], frameon=False,
              fontsize=7, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.09))
    fig.tight_layout()
    p = os.path.join(FIG, "gantt.png"); fig.savefig(p, bbox_inches="tight"); plt.close(fig); return p


F_PIPE = fig_pipeline()
F_ALT, ALT_PTS = fig_altitude()
F_S3 = fig_stage3()
F_S5 = fig_stage5()
F_GANTT = fig_gantt()

# ================================================================== CONTENT
story.append(Spacer(1, 30 * mm))
P("eVTOL SLAM Comparison", "sub")
P("Research findings and the implementation plan for Stages 3, 4 and 5", "title")
P("A reference document to read before Stage 3 starts. It collects what the last three working "
  "sessions found (project summary, literature and web research, final metrics) and explains how the "
  "next three stages will be built and checked, step by step.", "sub")
story.append(Spacer(1, 8 * mm))
T([["Item", "Value"],
   ["Date", "16 November 2026; Stage 3 results and corrections added 17 November (§4.7)"],
   ["Project status", "Stages 1 and 2 complete and audited (commits b724ea4, 080671b). Stage 3 complete, gate "
                      "passed on 16 and again on 17 Nov (docs/stage3_log.md), not yet committed. Stage 4 is next."],
   ["Project review", "In about 10 days (around 25 Nov 2026): everything up to the simulation results. "
                      "Physical hardware is Phase 2."],
   ["Master plan", "eVTOL-SLAM-Complete-Project-Guide.pdf (108 pages, 8 stages) in the repository root"],
   ["Companion documents", "docs/eVTOL_SLAM_Project_Summary.pdf (plain-language summary), docs/stage2_log.md, "
                           "docs/stage1_2_audit.md, final_results/"],
   ["Source of this PDF", "docs/make_reference_pdf.py (regenerates it, figures included)"]],
  [38, 132])
NOTE("How to read it.",
     "Part 1 explains the project and its current state. Part 2 summarises what other researchers did. "
     "Part 3 fixes the final metrics and how we will present them. Parts 4, 5 and 6 are the step-by-step "
     "plans for Stages 3, 4 and 5. Part 7 is the 10-day schedule and the review outline. The appendices "
     "hold a glossary, a command sheet, a file map and the sources. Boxes marked <b>Decision</b> are "
     "choices that need your agreement before or during Stage 3.", "info")

story.append(PageBreak())
P("Contents", "h1n")
toc = TableOfContents()
toc.levelStyles = [ST["toc1"], ST["toc2"]]
story.append(toc)

# ------------------------------------------------------------------ PART 1
H1("1. The project in brief")
H2("1.1 The question and why it matters")
P("We test three well-known open-source SLAM programs to find out which <b>sensor combination</b> lets a "
  "small electric aircraft (an eVTOL or drone) know where it is without GPS. SLAM (Simultaneous "
  "Localisation and Mapping) estimates the aircraft's position by building a map of its surroundings as it "
  "moves. GPS weakens or bounces indoors, near tall buildings and under bridges; SLAM fills that gap using "
  "only on-board sensors.")
P("Choosing those sensors is the hard part. Cameras are light and cheap but struggle in the dark and on "
  "blank walls. LiDAR measures distance directly but is heavier, draws more power and only sees to a fixed "
  "range. Published papers each test their own method on their own data, usually close to the ground, so "
  "they are hard to compare and say little about an aircraft climbing away from the ground. An eVTOL "
  "designer needs three answers: <b>which sensor set keeps working in which conditions, when and how badly "
  "each one fails, and whether the on-board computer can run it in real time</b>. This project produces "
  "those answers with evidence, and ends with a drone flying on its own SLAM estimate.")

H2("1.2 The three algorithms (one per modality)")
T([["Algorithm", "Sensors", "How it estimates position", "Strength", "Weakness"],
   ["ORB-SLAM3", "stereo camera + IMU", "tracks visual corner features (ORB) across both cameras and over time; "
    "keyframes, bundle adjustment, loop closing", "light, cheap sensors; very accurate in textured scenes",
    "needs light and texture; needs motion before its IMU initialises"],
   ["FAST-LIO2", "LiDAR + IMU", "iterated Kalman filter registers each raw scan to an incremental 3-D map "
    "(ikd-tree)", "works in the dark; direct range; cheap to compute", "fails when little is in range or the "
    "geometry is degenerate (corridor, flat plane)"],
   ["FAST-LIVO2", "LiDAR + camera + IMU", "FAST-LIO-style LiDAR update plus a direct photometric update "
    "on image patches attached to map points", "should survive where either sensor alone struggles",
    "most complex, most to calibrate, heaviest compute"]],
  [22, 24, 52, 36, 36])

H2("1.3 The simulated sensor rig")
P("All sensors are defined once in <font face='DVM'>config/rig.yaml</font>; every Gazebo model and every "
  "algorithm configuration is generated from it by <font face='DVM'>scripts/common/gen_configs.py</font>.")
T([["Sensor", "Model", "Key numbers"],
   ["LiDAR", "Livox Mid-360 (fratopa plugin, 4 patches)", "10 Hz, 20 000 points per scan, 0.1–40 m range, "
    "vertical field of view −7° to +52° (real scan pattern, 800 000 rays)"],
   ["IMU", "Mid-360 internal IMU position", "200 Hz; noise added offline with EuRoC ADIS16448 densities: gyro "
    "1.7e-4 rad/s/√Hz, accel 2.0e-3 m/s²/√Hz, random walks 1.94e-5 and 3.0e-3"],
   ["Stereo camera", "Gazebo multicamera", "752 × 480, 20 Hz, fx ≈ 458.6 px, baseline 0.11 m, image noise 0.007, "
    "looks 35° down"],
   ["Mount", "under the vehicle, upside-down (roll = π)", "offset (0.12, 0, −0.06) m from base_link. "
    "Inverted, the LiDAR sees −52° to +7°, i.e. towards the ground"],
   ["Ground truth", "Gazebo p3d plugin", "exact pose of the IMU frame, 200 Hz"]],
  [26, 50, 94])

H2("1.4 Tech stack")
T([["Layer", "What we use", "Job"],
   ["Workstation", "Ubuntu 24.04, NVIDIA RTX 5090", "builds, simulation, experiments (Stages 1–5)"],
   ["Containers", "Docker + NVIDIA Container Toolkit, Ubuntu 20.04 images", "one sealed image per algorithm "
    "(evtol/orbslam3, fastlio2, fastlivo2), plus evtol/eval and evtol/sim"],
   ["Middleware", "ROS 1 Noetic", "moves sensor data; records bag files"],
   ["Simulator", "Gazebo 11 + PX4 v1.14.4 SITL + MAVROS", "virtual worlds, sensors and the real autopilot software"],
   ["Scoring", "evo 1.31.1, Python/NumPy", "compares estimated and true paths"],
   ["Phase 2", "Jetson Orin Nano (JetPack 6.2), real Mid-360, camera, Kalibr", "embedded cost (Stage 6), "
    "real flight (Stage 7)"]],
  [28, 70, 72])

H2("1.5 The eight stages")
T([["Stage", "Goal", "Guide time", "Gate (pass/fail)", "Status"],
   ["1", "Build the three algorithms; reproduce published accuracy", "3–5 days", "our error matches the papers'", "done 20 Oct"],
   ["2", "Simulated sensor rig on a scripted path", "3–4 days", "sensors provably correct vs ground truth", "done 5 Nov"],
   ["3", "All three algorithms on simulated data, then on PX4 flights", "3–4 days", "every algorithm tracks a PX4 flight", "<b>starts today</b>"],
   ["4", "Experiment matrix built to break each algorithm", "1–2 weeks", "complete results table and figures", "next"],
   ["5", "SLAM closes the loop through PX4's EKF2 in simulation", "3–5 days", "simulated drone flies on SLAM alone", "if time allows"],
   ["6", "Accuracy and cost on the Jetson Orin Nano", "1 week", "per-power-mode accuracy, latency, power", "Phase 2"],
   ["7", "Real sensors, calibration, airframe, flight", "3–6 weeks", "real flight on SLAM, safety pilot", "Phase 2"],
   ["8", "Reproducibility package", "2–3 days", "a stranger can re-run our numbers", "Phase 2"]],
  [14, 60, 18, 52, 26])

H2("1.6 The principles every stage follows")
BL(["<b>Every stage has a gate.</b> Never introduce a new unknown until the previous one is proven. When something "
    "breaks later, the gates tell us where.",
    "<b>One source of truth.</b> rig.yaml → gen_configs.py → all configs. Generated files are never hand-edited.",
    "<b>Record once, replay many.</b> Each flight is recorded once; every algorithm, every repeat and every noise "
    "level replays the same bytes. Differences then come from the algorithms, not the data.",
    "<b>One change per experiment.</b> Environment, altitude, speed, IMU grade and sensor faults are varied one at a time.",
    "<b>Honest statistics.</b> SE3 alignment (no scale fudge), median of at least 3 runs with the spread, and coverage "
    "checked before accuracy."])
FIGURE(F_PIPE, 168, "Figure 1. The measurement pipeline: one rig file, one recording per flight, identical input "
       "to all three algorithms, one scoring tool.")

H2("1.7 Where we are: Stage 1 and Stage 2 results")
T([["Algorithm", "Stage 1 (paper datasets, median of 5 runs)", "Result"],
   ["ORB-SLAM3", "EuRoC, 11 sequences", "mean 3.27 cm vs paper 3.5 cm (−6 %); 7 green, 4 amber, 0 red"],
   ["FAST-LIO2", "LIO-SAM, NCLT, UTBM, LiLi-OM (16 sequences)", "matches the paper or independent re-runs on most; "
    "the paper's RMSE column is not reproducible by anyone (documented)"],
   ["FAST-LIVO2", "NTU-VIRAL (9) + authors' private sequences", "8 of 9 NTU-VIRAL within 15 %; one documented shortfall"]],
  [24, 60, 86])
P("Stage 2 gate: <b>13 of 13 checks passed</b> on a 120 s room flight (rates 200/10/200/20/20 Hz, 20 000 points per "
  "scan, identical stereo stamps, IMU vs ground-truth kinematics RMS 0.001 m/s²). All five worlds (room, room_plain, "
  "corridor, field, urban) load and pass. Seven deviations from the guide are documented in docs/stage2_log.md; the "
  "two that matter for Stage 3: the camera publish throttle (no duplicated frames; <i>do not</i> use Gazebo lockstep, "
  "it halves the LiDAR to 5 Hz) and gravity moved to the world level (9.8066 m/s²).")
T([["End-to-end smoke test (1 run, noise-free IMU)", "APE RMSE", "RPE / 1 m", "Coverage"],
   ["FAST-LIO2", "3.6 cm", "0.7 cm", "0.997"],
   ["FAST-LIVO2", "6.3 cm", "3.9 cm", "0.997"],
   ["ORB-SLAM3", "0.7 cm", "0.6 cm", "0.908 (waits for motion)"]],
  [70, 30, 30, 40])
NOTE("Carried into Stage 3.",
     "(1) Bag tools in the eval image must run through <font face='DVM'>scripts/common/ros_python.sh</font>. "
     "(2) ORB-SLAM3 coverage is capped near 0.91 on the scripted path because its IMU initialisation needs motion. "
     "(3) FAST-LIVO2 runs its visual update on every second image only: simulated scans have one timestamp for all "
     "points, so at 20 Hz camera / 10 Hz LiDAR every other image gets no new points. "
     "(4) The launch files and bag_to_euroc.py already ran unmodified in the smoke test.", "warn")

# ------------------------------------------------------------------ PART 2
H1("2. What other researchers did, and what we take from it")
H2("2.1 The six papers in SLAM_Comparison_Research_Papers.epub")
T([["Paper", "How they compared", "What we borrow"],
   ["1. Garigipati et al. 2022 (Tampere): eight LiDAR and visual SLAM methods",
    "one rig; varied sensor <b>mounting position</b>, ground type, speed, moving people; error and <b>CPU use</b>",
    "one factor at a time; CPU table; closing <b>'which method for which job'</b> table; mounting as a variable"],
   ["2. Tiozzo Fasiolo et al. 2023 (Robotica): LiDAR-IMU methods for 3-D mapping",
    "compared <b>maps</b> to a laser-scanner survey: cloud-to-cloud (C2C) distance, density, roughness; "
    "FAST-LIO2 densest but drifted on long loops", "score the map, not just the path (in simulation the true "
    "geometry is exact)"],
   ["3. Hernas et al. 2025 (Wrocław): ROS 2 SLAM in Gazebo",
    "closest to us: one recorded route replayed to every method; reference map from a noise-free simulated LiDAR; "
    "SSIM/IoU/Hausdorff on occupancy grids; <b>error over time</b>, ECDF, final error; CPU and RAM",
    "error-over-time and error-distribution plots; reference map from the simulator"],
   ["4. Sier et al. 2022 (Turku): multi-LiDAR benchmark",
    "divergence reported as <b>N/A</b> (a result in itself); CPU, RAM and pose output rate at 15× playback on "
    "desktop and Jetson; long corridors broke most methods", "count failures as results; measure processing "
    "headroom by fast replay"],
   ["5. Zhu et al. 2024: multi-sensor fusion survey", "open problems: degradation (darkness, featureless geometry), "
    "moving objects, synchronisation", "the failure and timing tests"],
   ["6. Fan et al. 2025: fusion SLAM survey (Sec. 5.3)", "asks whether adding another modality is always worth it",
    "<b>the framing of our whole project</b>"]],
  [46, 70, 54])

H2("2.2 What the web research added")
T([["Source", "Idea or number", "Use in our project"],
   ["Robust-SLAM perturbation benchmark (arXiv 2402.08125)", "degrade recorded data in software with a taxonomy "
    "of sensor faults; success-rate metrics", "our offline fault injection (no re-recording)"],
   ["Sensor-aware LiDAR degradation (arXiv 2512.08653)", "simulate LiDAR dropout and thinning realistically",
    "LiDAR dropout and 25 % thinning"],
   ["UAV visual SLAM study (arXiv 2605.03678)", "<b>Tracking Success Rate</b> = % of frames with error < 2 m, "
    "angle < 30° and not lost. ORB-SLAM3: 31 % in very low light, 0 % in medium or dense haze",
    "TSR as a headline robustness metric; dimming test"],
   ["Hilti SLAM Challenge 2022/2023", "graded score per control point: full marks under 1 cm, zero above 10 cm",
    "scorecard colour classes fixed in advance"],
   ["COIN-LIO case study (arXiv 2411.16931)", "reports relative translation and <b>yaw</b> errors separately",
    "heading error as its own metric"],
   ["ISPRS 2025 LiDAR odometry benchmark", "drift as % of distance travelled", "drift % (comparable across room "
    "and town)"],
   ["FAST-LIVO2 / LIR-LIVO papers", "LiDAR-degenerate and visually difficult sequences; no controlled head-to-head "
    "with ORB-SLAM3 and FAST-LIO2 under sensor failure", "the gap we fill"]],
  [50, 70, 50])
NOTE("The gap.", "No published comparison of ORB-SLAM3, FAST-LIO2 and FAST-LIVO2 under controlled darkness, "
     "sensor dropout or altitude was found. Survey 6 asks whether an extra modality is worth it; our failure tests "
     "and altitude sweep answer that with data, on identical inputs.", "key")

H2("2.3 Ideas ranked by value for effort (agreed 15 Nov)")
T([["#", "Idea", "What it shows", "Effort", "Where in the plan"],
   ["1", "Sensor-failure test on one recorded flight: camera blackout 5 s, dimming to 30 % and 10 %, LiDAR "
    "dropout 2 s and 5 s, LiDAR thinned to 25 %", "which sensor set survives which failure", "1.5 days", "Stage 4, §5.5"],
   ["2", "Camera timestamp offset 5, 10, 20 ms", "how precise Phase 2 hardware sync must be", "in #1", "Stage 4, §5.5"],
   ["3", "Error-over-time plot + Tracking Success Rate", "the clearest slide: failure and recovery", "0.5 day", "Stage 3 metrics + §5.6"],
   ["4", "Altitude sweep as the headline, with ground points per scan and the predicted line", "prediction vs result", "0.5 day", "Stage 4 B"],
   ["5", "Real-time headroom: replay at 1×, 2×, 4×, 8×; CPU and RAM", "previews the Jetson question", "0.5 day", "Stage 4, §5.5"],
   ["6", "Map accuracy against exact geometry (LiDAR methods)", "paper 2's metric, strong visuals", "1 day", "stretch"],
   ["7", "Sensor mounting: inverted vs upright", "tests our main design decision (paper 1)", "1 day", "stretch"],
   ["8", "Moving people (Gazebo actors)", "dynamic-object robustness", "new recordings", "skipped"]],
  [6, 62, 44, 16, 42])

# ------------------------------------------------------------------ PART 3
H1("3. The final metrics and comparison framework")
H2("3.1 What the project measured before this research")
T([["Where", "What it measures"],
   ["eval_traj.sh + results_table.py", "APE RMSE (median of runs), APE spread (max − min), RPE per 1 m, worst coverage"],
   ["plot_sweeps.py (Stage 4)", "APE vs altitude, speed, IMU noise; hollow markers when coverage < 0.95"],
   ["Stage 5", "PX4 local-position APE vs FAST-LIO2 APE; hover judged by eye"],
   ["Stage 6 (Phase 2)", "latency median/p95, CPU, RAM, power, temperature on the Jetson"]],
  [50, 120])
P("Missing compared with the literature: heading error, vertical vs horizontal error (crucial for the altitude "
  "sweep), drift normalised by distance, start-up time, success rate, workstation compute cost, map quality and "
  "behaviour under sensor failure.")

H2("3.2 Metric definitions (so every number on a slide is unambiguous)")
P("All trajectories are scored against the exact simulated ground truth of the IMU frame, matched by timestamp "
  "(within 20 ms) and aligned with a rigid <b>SE3 alignment</b> (Umeyama: best rotation and translation, no scale "
  "correction, because every method here observes metric scale).")
T([["Metric", "Definition", "Tool"],
   ["APE RMSE", "√( mean over poses of ‖p̂ᵢ − pᵢ‖² ) after alignment, in metres; median over ≥ 3 runs", "evo_ape (have)"],
   ["APE horizontal / vertical", "same, but the error vector split into its xy part and its z part (world frame)", "metrics_extra.py (new)"],
   ["Heading error", "RMSE of the yaw difference after alignment, degrees (plus full rotation angle via evo "
    "<font face='DVM'>--pose_relation angle_deg</font>)", "metrics_extra.py / evo"],
   ["RPE per 1 m", "translation error of relative motions over 1 m segments: local drift, insensitive to alignment", "evo_rpe (have)"],
   ["Drift %", "RPE over 10 m segments ÷ 10 m × 100. One segment length for every flight, so room and town compare", "evo_rpe --delta 10 (new)"],
   ["Coverage", "duration the estimate spans ÷ duration of the airborne part of the flight (see Decision D1)", "eval_traj.sh + new"],
   ["Start-up time", "first pose time − time the vehicle first moves (ground truth moves > 0.1 m)", "metrics_extra.py (new)"],
   ["Success rate", "runs with coverage ≥ 0.95 and APE below the failure threshold, out of N", "results table (new)"],
   ["Tracking Success Rate (TSR)", "% of airborne ground-truth samples where a pose exists within 0.1 s and its "
    "error is below τ (τ = 0.25 m indoors, 1.0 m outdoors, fixed before Stage 4)", "metrics_extra.py (new)"],
   ["Degradation Δ and recovery", "APE(degraded) − APE(clean) on the same flight; recovered = error back below τ "
    "within 5 s after the fault window ends", "fault analysis (new)"],
   ["CPU / RAM", "CPU % of one core (mean, peak) and peak resident memory of the algorithm process, sampled at "
    "2 Hz from /proc", "cost_probe.py (new)"],
   ["Latency", "output arrival time − sensor capture stamp; median and 95th percentile", "latency_probe.py (have, unused)"],
   ["Real-time headroom", "highest replay rate (1, 2, 4, 8×) at which coverage ≥ 0.95 and APE ≤ 1.5 × the 1× value", "run_ros_algo.sh rate arg"],
   ["Map C2C (stretch)", "mean and RMS distance from each map point to the reference cloud built from noise-free "
    "LiDAR at ground-truth poses; plus completeness", "map_c2c.py (new)"],
   ["Flyability (Stage 5)", "PX4 local-position APE; position standard deviation during a 20 s hover", "Stage 5 eval"]],
  [34, 100, 36])

H2("3.3 The final set: five headline metrics plus supporting ones")
T([["#", "Metric", "Question it answers", "Status", "Effort"],
   ["H1", "<b>APE, split horizontal / vertical</b>", "how far off, and is the height right?", "APE have; split new", "small script"],
   ["H2", "<b>Drift % of distance</b>", "comparable across a 6 m room and a town at 60 m", "new", "same script"],
   ["H3", "<b>Success rate + TSR</b>", "can I trust it to keep going?", "coverage have; rest new", "same script"],
   ["H4", "<b>Failure survival</b> (Δ APE, recovered yes/no)", "which sensor set survives which failure?", "new experiment", "1.5 days"],
   ["H5", "<b>Compute cost</b>: CPU, RAM, latency p95, headroom", "will it fit on the aircraft computer?", "latency tool have; rest new", "0.5 day"],
   ["S1", "Heading error (deg)", "does the heading drift?", "new", "minutes"],
   ["S2", "Start-up time", "how long before the aircraft has a position?", "new", "minutes"],
   ["S3", "Spread between runs", "is it repeatable?", "have", "–"],
   ["S4", "Map C2C accuracy (LiDAR methods)", "is the map usable for obstacle avoidance?", "new", "1 day, stretch"],
   ["S5", "PX4 APE + hover steadiness", "can it actually fly on this?", "Stage 5", "if time allows"]],
  [9, 46, 55, 34, 26])
NOTE("Why these.", "H1–H3, S1 and S2 come from one new script that runs on files we already write, so together they "
     "cost about a day, and they are built into Stage 3 so that every Stage 4 run has them automatically. Workstation "
     "compute numbers are shown as a <i>relative</i> comparison only; the Jetson gives absolute numbers in Phase 2.", "key")

H2("3.4 The comparison axes (what we vary)")
T([["Axis", "Levels", "Question", "Status"],
   ["Environment", "room, room_plain (no texture), corridor (80 m, no geometry along x), field (one plane)",
    "which modality fails first, and how gracefully?", "Stage 4 A"],
   ["<b>Altitude</b>", "urban at 10, 20, 30, 40, 50, 60 m", "where does LiDAR lose the ground? (eVTOL-specific)", "Stage 4 B, headline"],
   ["Speed / turn rate", "figure-8 at 2, 5, 8 m/s, yaw along the path", "do the methods keep up with fast turns?", "Stage 4 C (cut first if short)"],
   ["IMU grade", "×1, ×3, ×10, ×30 baseline noise, same flight", "how much accuracy does a better IMU buy?", "Stage 4 D"],
   ["<b>Sensor failure</b>", "camera blackout, dimming, LiDAR dropout, LiDAR thinning", "is the extra modality worth it?", "new, offline"],
   ["Timing offset", "camera 5, 10, 20 ms late", "how accurate must hardware sync be?", "new, offline"],
   ["Mounting", "inverted vs upright, 2–3 altitudes", "was the inverted mount the right call?", "stretch"],
   ["Compute", "replay 1, 2, 4, 8×", "how much real-time margin?", "new"]],
  [26, 62, 52, 30])

H2("3.5 The altitude hypothesis, computed from the real scan pattern")
P("The inverted Mid-360 looks between 7° above and 52° below the horizon. Over flat ground at height h, a ray "
  "pointing θ below the horizon hits the ground at slant range h / sin θ. With a 40 m maximum range, ground returns "
  "need sin θ ≥ h / 40, so the steepest ray (52°) stops reaching the ground at h = 40 × sin 52° ≈ <b>31.5 m</b>. "
  "Counting the actual 800 000-ray Mid-360 pattern gives the predicted ground points per scan below: about "
  "%d at 10 m, %d at 20 m, only %d at 30 m and none from 32 m. Above that only building roofs and walls "
  "within 40 m carry the LiDAR methods (urban buildings are 8–45 m tall). An upright mount would lose the "
  "ground above about 4.9 m, which is the quantitative argument for our design." % (ALT_PTS[10], ALT_PTS[20], ALT_PTS[30]))
FIGURE(F_ALT, 160, "Figure 2. Predicted ground returns per scan vs altitude (level flight, flat ground, 40 m range), "
       "computed from the Mid-360 scan table in evtol/sim:v1. Stage 4 B measures the real curve from the recorded "
       "scans and sets the APE curves beside it.")

H2("3.6 Hypotheses written down before running")
P("Stating expectations first is what makes the results credible. A result that contradicts a hypothesis is not a "
  "failure; it is usually the most interesting row.")
T([["Condition", "Expected"],
   ["room", "all three track; ORB-SLAM3 most accurate locally (as in the smoke test)"],
   ["room_plain", "ORB-SLAM3 degrades or fails (no texture); FAST-LIO2 unaffected; FAST-LIVO2 close to FAST-LIO2"],
   ["corridor", "FAST-LIO2 drifts along the corridor axis; ORB-SLAM3 fine (walls are textured); FAST-LIVO2 best"],
   ["field", "LiDAR methods weak horizontally (one plane, sparse posts); vision fine on grass texture"],
   ["altitude", "LiDAR methods hold to ~30 m, then depend on buildings; vertical error grows first; "
    "FAST-LIVO2's camera may carry it; ORB-SLAM3 scale/feature quality degrades with height"],
   ["speed", "ORB-SLAM3 suffers most at 8 m/s with fast yaw (note: no motion blur is simulated, so this flatters vision)"],
   ["IMU grade", "LIO methods degrade gracefully; ORB-SLAM3 initialisation fails first at ×10–×30 (its config "
    "assumes the baseline noise)"],
   ["camera blackout", "ORB-SLAM3 loses track (may start a new map); FAST-LIVO2 continues on LiDAR; FAST-LIO2 unaffected"],
   ["LiDAR dropout", "FAST-LIO2 propagates on IMU only and drifts; FAST-LIVO2 continues on vision; ORB-SLAM3 unaffected"]],
  [28, 142])

H2("3.7 How we will present it")
T([["Exhibit", "Content", "Why it works"],
   ["1. Scorecard heatmap (main slide)", "rows = every condition, columns = the three algorithms; cell colour = "
    "accuracy class, ✗ = failure. Class thresholds fixed from the Stage 3 clean results, stated on the slide "
    "(Hilti-style grading)", "the whole study on one page"],
   ["2. Altitude sweep", "two charts side by side (never one chart with two y-axes): APE (h/v) vs altitude, and "
    "measured vs predicted ground points per scan, with the 31.5 m line", "prediction vs result"],
   ["3. Error over time", "all three methods on one time axis during a fault, the fault window shaded", "you see "
    "failure and recovery"],
   ["4. Accuracy vs compute scatter", "APE vs CPU per algorithm and condition", "accuracy per unit of compute"],
   ["5. Trajectory overlays + video", "top views against ground truth; Gazebo + RViz screen recording", "intuition"],
   ["6. Recommendation table", "'use X when …' (as papers 1 and 3 close)", "the designer's answer"],
   ["Method slide", "same recording for every method; default tuning; median of 3; SE3; coverage first; builds proven "
    "against their papers (Stage 1)", "reviewers check fairness first"]],
  [40, 92, 38])
NOTE("Leave out.", "Radar charts and invented composite scores (they hide trade-offs behind arbitrary weights); "
     "absolute workstation CPU claims; single-run numbers; any APE shown without its coverage; a chart with "
     "two y-axes.", "warn")

# ------------------------------------------------------------------ PART 4  STAGE 3
H1("4. Stage 3 in detail: close the loop, then fly")
H2("4.1 Goal, order and gate")
P("<b>Goal:</b> all three algorithms running on simulated data and scored against exact ground truth; first on the "
  "Stage 2 scripted bag (<b>3a</b>), then on real PX4 flight profiles (<b>3b</b>).")
P("<b>Why that order:</b> the scripted bag has no flight controller in it. If the algorithms work there and fail on a "
  "PX4 flight, the difference is the flight: a far smaller search space than 'somewhere in the whole simulation'.")
P("<b>Gate (guide):</b> every algorithm tracks a PX4 flight to completion (coverage ≥ 0.95), scored against ground "
  "truth; APE small relative to the flight (centimetres in the room); no algorithm an order of magnitude worse "
  "than the others on the same bag (that would be a configuration fault, not a finding).")
FIGURE(F_S3, 168, "Figure 3. What run_all_algos.sh does for one bag: noise injection once, ground truth once, "
       "EuRoC conversion once, then each algorithm three times on the identical noised bag, then scoring.")

H2("4.2 Files: from the guide, adapted, and new")
T([["File", "Origin", "Purpose"],
   ["scripts/common/imu_noise.py", "guide 3.1", "adds white noise + bias random walk to the perfect simulated IMU"],
   ["scripts/common/bag_to_euroc.py", "guide 3.2 (already ran in the smoke test)", "bag → EuRoC folder, so ORB-SLAM3 "
    "uses the same standalone binary validated in Stage 1 (no new ROS wrapper)"],
   ["config/launch/fastlio2.launch, fastlivo2.launch", "guide 3.3 (already ran)", "launch with an explicit config "
    "argument, so generated configs plug in without editing upstream files"],
   ["scripts/stage3/run_all_algos.sh", "guide 3.4, <b>adapted</b>", "the workhorse for Stages 3 and 4 (adaptations A1, A4, A5)"],
   ["scripts/stage3/offboard_mission.py", "guide 3.5", "flies hover / square / figure-8 / line in OFFBOARD mode via MAVROS"],
   ["scripts/stage3/px4_record.sh", "guide 3.5", "boots PX4 SITL with the rig on the iris, records all topics, runs the mission"],
   ["scripts/common/metrics_extra.py", "<b>new</b>", "H1–H3, S1, S2 from the TUM files: h/v APE, yaw, drift %, TSR, "
    "airborne coverage, start-up time, error-over-time CSV"],
   ["scripts/common/cost_probe.py", "<b>new</b>", "samples CPU and memory of the algorithm process at 2 Hz → cost.csv"],
   ["scripts/common/results_table.py", "guide, <b>extended</b>", "adds the new columns (separate summary_extra.csv, "
    "the original summary stays byte-compatible)"],
   ["docs/stage3_log.md", "<b>new</b>", "what was run, deviations, results, like the Stage 2 log"]],
  [56, 42, 72])
P("All guide files are transcribed with <font face='DVM'>scripts/tools/guide_extract.py</font> (glyph positions, exact "
  "indentation), never with pdftotext, which broke Python indentation in Stage 2.")

H2("4.3 Adaptations to the guide (known before we start)")
T([["#", "Change", "Reason"],
   ["A1", "bag tools (imu_noise, bag_to_tum, bag_to_euroc) run as <font face='DVM'>bash /scripts/common/ros_python.sh "
    "script.py …</font> in the eval container", "the eval image's python3 is the evo virtualenv and cannot import rosbag (audit fix A)"],
   ["A2", "coverage counted over the airborne window, start-up time reported separately", "Decision D1 below"],
   ["A3", "ORB-SLAM3 scored on its frame trajectory (f_*.txt, every frame) for time-series metrics; keyframe "
    "trajectory (kf_*.txt) also scored once for continuity with Stage 1", "Decision D2 below"],
   ["A4", "LATENCY=1 and cost_probe.py on every run", "compute cost (H5) comes for free with every Stage 4 run"],
   ["A5", "metrics_extra.py called after eval_traj.sh", "the final metric set from day one"],
   ["A6", "first PX4 bag checked for sensor rates and camera intervals before any algorithm sees it", "PX4 SITL runs "
    "Gazebo in lockstep with the autopilot; the Stage 2 camera throttle must be re-verified there"],
   ["A7", "FAST-LIVO2 diagnostic: one extra run with the camera thinned to 10 Hz", "tests whether the alternate-image "
    "effect explains its higher drift (carried item 3)"]],
  [9, 88, 73])
NOTE("Decision D1 (agreed 16 Nov): coverage on PX4 flights.",
     "The guide divides the tracked duration by the whole bag. A PX4 bag begins with about 10 s on the ground plus "
     "arming; ORB-SLAM3 cannot initialise its IMU until the vehicle moves, so by that definition it will fail the "
     "≥ 0.95 gate on every flight without ever losing track. Proposal: coverage over the airborne window (take-off to "
     "touch-down, detected from ground truth), with start-up time reported as its own metric (S2). The guide's "
     "whole-bag coverage stays in the table for transparency.", "decide")
NOTE("Decision D2 (agreed 16 Nov): which ORB-SLAM3 trajectory.",
     "Stage 1 scored keyframes (as the ORB-SLAM3 paper does). Keyframes are sparse (74 in 120 s), too coarse for "
     "error-over-time and TSR. Proposal: frame trajectory as primary from Stage 3 on, keyframe APE reported beside it "
     "in Stage 3 to show the two agree.", "decide")

H2("4.4 Step by step")
H3("Step 0: pre-flight checks (10 min)")
BL(["Docker daemon is the apt one and all evtol/* images are listed (after a reboot the snap daemon can hide them).",
    "<font face='DVM'>nvidia-smi</font> works (unattended upgrades once broke all GPU containers until reboot).",
    "<font face='DVM'>git status</font> clean apart from the known untracked PDFs; <font face='DVM'>git diff --stat "
    "final_results/</font> empty.",
    "Disk: 283 GB free now. Budget for Stages 3–4 is roughly 100–120 GB (§5.4)."])
H3("Step 1: transcribe the Stage 3 files (30 min)")
CODE("python3 scripts/tools/guide_extract.py eVTOL-SLAM-Complete-Project-Guide.pdf /tmp/<scratch>/guide_files\n"
     "# copy imu_noise.py, bag_to_euroc.py, the two launch files, run_all_algos.sh,\n"
     "# offboard_mission.py, px4_record.sh into place; diff the launch files and\n"
     "# bag_to_euroc.py against output/diagnostics/stage2_e2e/harness/ (already proven)")
H3("Step 2: realistic IMU noise, and prove it (30 min)")
P("The simulated IMU is perfect, which would flatter every method. imu_noise.py applies the standard continuous-time "
  "model that Kalibr and ORB-SLAM3 themselves assume. For each sample with interval Δt:")
BL(["white noise: n ~ N(0, σ² / Δt), with σ the noise density from rig.yaml × scale S;",
    "bias random walk: b ← b + σ_b · √Δt · N(0, 1);",
    "fixed seed, so 'the same noise' is genuinely the same across runs; the parameters are written beside the output "
    "bag as JSON; every other topic is copied unchanged."])
P("<b>Check we will run</b> on the stationary first seconds of the noised bag: the per-sample standard deviation must "
  "match σ/√Δt with Δt = 5 ms: gyro 1.7e-4 / √0.005 = <b>2.4e-3 rad/s</b>, accel 2.0e-3 / √0.005 = <b>0.028 m/s²</b> "
  "(at ×30: 0.072 rad/s and 0.85 m/s²). The bias wander over 120 s should be of order σ_b·√t: gyro ≈ 2e-4 rad/s, "
  "accel ≈ 0.03 m/s².")
H3("Step 3: the EuRoC conversion for ORB-SLAM3 (10 min)")
P("bag_to_euroc.py writes mav0/cam0, cam1 (PNG per frame, named by nanosecond stamp), imu0/data.csv in EuRoC's exact "
  "column order (gyro then accel) and times.txt. Only stereo pairs with identical stamps are kept. Expected on the "
  "scripted bag: 2395 pairs, 24 000 IMU samples.")
H3("Step 4: run all three on the scripted bag, 3 runs (≈ 30 min unattended)")
CODE("bash scripts/stage3/run_all_algos.sh output/stage2/scripted_room.bag room output/stage3/scripted 3\n"
     "cat output/stage3/scripted/eval/summary.md")
P("<b>Expected:</b> numbers close to the smoke test (FAST-LIO2 ≈ 4 cm, FAST-LIVO2 ≈ 6 cm, ORB-SLAM3 ≈ 1 cm APE), "
  "now with realistic IMU noise and three runs each. FAST-LIO2 and FAST-LIVO2 are nearly deterministic; ORB-SLAM3 "
  "varies between runs (multi-threaded), which is why medians are used.")
H3("Step 5: the new metrics and cost logging (half a day, in parallel with step 4)")
P("<b>metrics_extra.py</b> reads the ground-truth and estimated TUM files, repeats the SE3 alignment (NumPy Umeyama, "
  "checked to reproduce evo's APE to 1e-6 m), and writes one JSON per run plus an error-over-time CSV: APE h/v, yaw "
  "RMSE, drift % over 10 m, TSR, airborne coverage, start-up time. <b>cost_probe.py</b> runs inside the algorithm "
  "container, finds the algorithm process by name (fastlio_mapping, fastlivo_mapping, stereo_inertial_euroc) and "
  "samples /proc utime+stime and RSS twice a second. Both are checked on the scripted results before the PX4 flights.")
H3("Step 6: PX4 SITL with the rig (3b)")
P("The same rig is mounted on PX4's standard iris quadrotor (model iris_evtol, generated from rig.yaml; a zero-range "
  "revolute joint, PX4's own payload pattern). PX4 starts with <font face='DVM'>vehicle:=iris</font> (iris airframe "
  "parameters) and <font face='DVM'>sdf:=…iris_evtol…</font> (our sensors).")
T([["Phase of px4_record.sh", "What happens", "Why"],
   ["boot", "roslaunch px4 mavros_posix_sitl.launch; wait for MAVROS 'connected' and /ground_truth/odom", "nothing records before PX4 is up"],
   ["record", "rosbag record LiDAR, IMU, ground truth, both images + camera_info, PX4 local pose, PX4 state", "one bag holds everything"],
   ["stand still 10 s", "vehicle on the ground", "FAST-LIO2 initialises gravity from a stationary start"],
   ["arm + OFFBOARD", "setpoints streamed for 2 s first (PX4 refuses OFFBOARD otherwise); SITL-only failsafe parameters", "no RC transmitter in simulation"],
   ["climb", "1 m/s to --alt, then 2 s settle", "smooth, repeatable"],
   ["profile", "square / figure-8 / line, speed ramped in and out over 3 s; every setpoint a smooth function of time", "same command = same flight"],
   ["land", "AUTO.LAND, wait for disarm (max 120 s), stop recorder, stop PX4", "clean end of bag"]],
  [32, 88, 50])
NOTE("Safety.", "<font face='DVM'>--sitl-params</font> disables RC-loss and data-link-loss failsafes (COM_RCL_EXCEPT, "
     "NAV_RCL_ACT, NAV_DLL_ACT, COM_RC_IN_MODE). Simulation only: on a real vehicle those failsafes return control to "
     "the safety pilot.", "warn")
CODE("GUI=true docker compose run --rm -e GUI -e SPAWN=\"-2.0 -1.8\" sim bash /scripts/stage3/px4_record.sh \\\n"
     "    room square /output/stage3/flights/room_square.bag --size 4 --alt 1.5 --speed 1.5 --laps 3")
P("<b>You watch this first flight</b> in the Gazebo window: take-off, a 0.4 m hop, three laps of a 4 m square at "
  "1.5 m, landing. (As run: the guide's 6 m square from the origin starts inside a box and flies through another, "
  "see §4.7.) If arming times out, the PX4 console in room_square.sim.log names the failing pre-flight check.")
H3("Step 7: check the PX4 bag before any algorithm (A6, 15 min)")
BL(["rates: IMU 200, LiDAR 10, ground truth 200, cameras 20 Hz; camera intervals 48–58 ms, no repeated stamps;",
    "Stage 2 checks that apply to a flight: 20 000 points per scan, offset_time 0, identical stereo stamps, IMU vs "
    "ground-truth kinematics (the at-rest checks apply only to the first 10 s);",
    "real-time factor in the sim log: below 1 is acceptable (all stamps are simulation time) but slows the matrix."])
H3("Step 8: all three on the PX4 flight, then the gate")
CODE("bash scripts/stage3/run_all_algos.sh output/stage3/flights/room_square.bag \\\n    room_square output/stage3/px4 3")
T([["Gate item", "Pass when"],
   ["summary lists all three algorithms", "3 runs each, no empty trajectory"],
   ["coverage", "≥ 0.95 airborne coverage for every run (Decision D1); start-up time reported"],
   ["accuracy", "APE of centimetres in the room over the flight window (Decision D3, §4.7); no method 10× worse"],
   ["new metrics", "metrics_extra and cost CSVs present for every run; evo APE reproduced by our alignment"],
   ["documentation", "docs/stage3_log.md written; results committed when you ask"]],
  [52, 118])

H2("4.5 When something fails: the order to check")
P("Stage 1 proved the algorithms; Stage 2 proved the sensors. So a failure in Stage 3 is almost always in the joint "
  "between them, configuration, and is checked in this order before suspecting an algorithm:")
NL(["<b>Topic names</b>: rosbag info on the input bag vs the config's lid_topic, imu_topic, img_topic.",
    "<b>Extrinsics</b>: re-run gen_configs.py (never hand-edit); read extrinsics_report.txt against a sketch of the rig.",
    "<b>Initialisation</b>: FAST-LIO2 needs the stationary start; ORB-SLAM3 needs rotational excitation; its log says "
    "when inertial initialisation completes.",
    "<b>Time</b>: all stamps must be simulation time; a wall-clock/sim-time mix shows up as huge gaps in rosbag info."])

H2("4.6 Risks we already expect")
T([["Risk", "Sign", "Response"],
   ["ORB-SLAM3 initialises late on PX4 flights (vertical climb gives little excitation)", "late first pose, low "
    "whole-bag coverage", "Decision D1; if it fails to initialise at all, add a short yaw manoeuvre after take-off "
    "to every profile (same for all methods)"],
   ["ORB-SLAM3 loses track and starts a new map", "'New Map created' twice in its log", "its saved trajectory is the "
    "largest map only → coverage drops; report as a failure, not hide it"],
   ["camera duplicates under PX4 lockstep", "repeated stamps in step 7", "same throttle fix as Stage 2; never "
    "gzserver --lockstep"],
   ["PX4 will not arm", "mission timeout after 90 s", "read the PX4 console log; usually a pre-flight check"],
   ["disk fills during Stage 4", "df", "noised bags and EuRoC folders are re-creatable: delete after scoring"],
   ["FAST-LIVO2 drift from alternate images", "RPE ≫ FAST-LIO2", "A7 diagnostic; if confirmed, state it as a "
    "simulation limitation"]],
  [52, 42, 76])
P("<b>Time:</b> 2 days (Mon 16 and Tue 17 Nov). Day 1 ends with 3a and the new metrics; day 2 ends with the gate.")

H2("4.7 Stage 3 as run: results, and what changed from this plan (added 17 Nov)")
P("Stage 3 was implemented on 16 Nov and re-verified on 17 Nov (results re-run, facts checked against upstream code "
  "and manuals, decisions checked against the literature). <b>The gate passed.</b> Where this section differs from "
  "§4.1–4.6, this section and docs/stage3_log.md are right.")
T([["PX4 room flight, median of 3 runs", "APE in flight", "horizontal / vertical", "Flight coverage (worst)", "Start-up",
    "CPU (cores)", "RAM", "Pose delay p95"],
   ["FAST-LIO2 (LiDAR + IMU)", "0.70 cm", "0.29 / 0.64 cm", "1.000", "0 s", "0.15", "172 MB", "8 ms"],
   ["FAST-LIVO2 (LiDAR + camera + IMU)", "0.29 cm", "0.26 / 0.12 cm", "1.000", "0 s", "0.54", "424 MB", "81–115 ms"],
   ["ORB-SLAM3 (stereo + IMU)", "0.75 cm", "0.70 / 0.26 cm", "0.981", "0.7 s", "2.0", "618 MB", "12 ms (tracking)"]],
  [44, 17, 26, 21, 13, 14, 14, 21])
P("Scripted bag (3a), whole-bag APE: FAST-LIVO2 0.6 cm, ORB-SLAM3 1.1 cm, FAST-LIO2 3.2 cm. ORB-SLAM3's whole-bag APE "
  "on the flight is 12 cm because it drifts 0.4–1.9 m on its IMU in the 5 s after landing, when its downward-pitched "
  "cameras, 12 cm above the floor, see only blurred floor texture.")
T([["What changed", "Why", "Status"],
   ["Flight: 4 m square × 3 laps from spawn (−2.0, −1.8); check_clearance.py before every flight",
    "the guide's 6 m square from the origin starts inside a box and crosses another", "in place"],
   ["Decision D3: APE over the flight window as headline; whole-bag APE and post-landing drift beside it",
    "ORB-SLAM3's post-landing drift otherwise decides its accuracy number. Precedent: DSO and OpenVINS evaluate the "
    "in-air part of EuRoC; rpg_trajectory_evaluation has start/end times", "recommended; your confirmation"],
   ["A 0.4 m altitude hop after the climb, in every flight",
    "ORB-SLAM3 needs a 0.5 m/s² acceleration step to initialise and has no setting that avoids it "
    "(IMU.fastInit is ignored by File.version 1.0 settings)", "recommended; your confirmation"],
   ["Landing gear on the iris (feet 0.22 m below the body)",
    "without it the belly sensors are 5 cm inside the floor. Livox's manual asks for 0.5 m under an inverted Mid-360; "
    "that variant was flown and bounces on landing on this small vehicle, so 0.5 m becomes a Phase 2 airframe "
    "requirement", "recommended; your confirmation"],
   ["FAST-LIVO2 scored on its own pose file, not its ROS topic",
    "the topic is stamped at publish time (70–115 ms late), which made the best method look the worst", "in place"],
   ["ORB-SLAM3 tracking time from a derived image (orbslam3:v1-times)",
    "upstream's REGISTER_TIMES; the validated image is untouched", "in place"],
   ["run_all_algos.sh refuses a bag that is newer than its derived data",
    "a re-recorded flight was once scored with the previous recording's data", "in place"]],
  [62, 78, 30])

# ------------------------------------------------------------------ PART 5  STAGE 4
H1("5. Stage 4 in detail: experiments that become results")
H2("5.1 Goal and design")
P("<b>Goal:</b> a results table and figures showing where each algorithm holds and where it breaks, under conditions "
  "built to isolate one cause at a time. <b>Gate:</b> every cell filled with ≥ 3 runs, figures generated, every "
  "result either explained or flagged.")
T([["Group", "Flight (offboard_mission.py)", "What varies", "Isolates"],
   ["A. Environments", "room, room_plain: square 4 m × 3 laps at 1.5 m, 1.5 m/s from spawn (−2.0, −1.8) · corridor: line 60 m at 1.5 m, 2 m/s · "
    "field: figure-8 15 m at 5 m, 3 m/s", "what the sensors can see", "vision starved (room_plain), LiDAR "
    "degenerate (corridor, field)"],
   ["B. Altitude", "urban: square 30 m at 10, 20, 30, 40, 50, 60 m, 4 m/s", "height above ground", "LiDAR range vs ground"],
   ["C. Speed", "urban: figure-8 20 m at 20 m, 2 / 5 / 8 m/s, yaw along path", "aggressiveness", "IMU propagation, motion"],
   ["D. IMU grade", "urban_speed5 replayed with ×1, ×3, ×10, ×30 noise", "only the IMU", "value of a better IMU"],
   ["E. Faults (new)", "room_square replayed with injected faults (§5.5)", "one sensor degraded", "value of the extra modality"]],
  [26, 70, 34, 40])
P("Group B is the project's distinctive contribution: most published comparisons fly near the ground. Group D is the "
  "cleanest experiment: images and scans are bit-identical across levels, so any change is caused by the IMU alone. "
  "Each algorithm keeps its default tuning: the experiment measures robustness, not re-tuning skill (stated in the "
  "write-up). Note the asymmetry: ORB-SLAM3's config is told the exact baseline noise densities, while FAST-LIO2 and "
  "FAST-LIVO2 use generic covariances (acc/gyr 0.1 and 0.5/0.3), so at ×1 the LiDAR methods are under-confident "
  "and at ×30 ORB-SLAM3 is over-confident.")

H2("5.2 run_matrix.sh: how the matrix runs")
CODE("ONLY=environments bash scripts/stage4/run_matrix.sh   # start here: fastest, most diagnostic\n"
     "ONLY=altitude     bash scripts/stage4/run_matrix.sh\n"
     "ONLY=imu          bash scripts/stage4/run_matrix.sh\n"
     "ONLY=speed        bash scripts/stage4/run_matrix.sh\n"
     "docker compose run --rm eval python3 /scripts/stage4/plot_sweeps.py /output/stage4")
BL(["<b>fly()</b> records a flight with px4_record.sh only if its bag does not exist yet, so an interrupted matrix resumes.",
    "<b>algos()</b> calls run_all_algos.sh on that bag: noise injection, ground truth, EuRoC conversion, 3 × 3 algorithm "
    "runs, scoring.",
    "Each group is run separately and inspected before the next: a configuration fault found in group A must not "
    "contaminate an overnight altitude run."])

H2("5.3 What each figure script draws")
T([["Script", "Figure", "Status"],
   ["plot_sweeps.py (guide)", "APE vs altitude / speed / IMU level, one line per algorithm, log y; hollow marker = lost track", "guide"],
   ["plot_sweeps.py (extended)", "the same for APE vertical and drift %; altitude panel beside ground points per scan", "new"],
   ["ground_points.py", "measured ground points per scan vs altitude from the recorded scans (points whose world z, "
    "through the ground-truth pose, is below 0.5 m), over the predicted curve of Figure 2", "new"],
   ["scorecard.py", "conditions × algorithms heatmap with fixed classes and ✗ for failures", "new"],
   ["plot_error_time.py", "error vs time for all three methods, fault windows shaded, TSR in the legend", "new"],
   ["plot_cost.py", "APE vs CPU scatter; headroom table", "new"],
   ["evo_traj", "top-view trajectory overlays", "evo built-in"]],
  [40, 105, 25])

H2("5.4 Budget: time and disk (estimates)")
P("Each algorithm replays a flight in real time, so compute time ≈ 9 × flight length per condition (3 algorithms × 3 "
  "runs) plus overhead. Flight lengths below include 10 s on the ground, climb at 1 m/s and landing.")
T([["Group", "Flights", "Approx. flight length", "Compute", "Bag data"],
   ["A", "4", "70 s, 70 s, 150 s, 95 s", "≈ 1.3 h", "≈ 7 GB"],
   ["B", "6", "≈ 110 s (10 m) to ≈ 200 s (60 m)", "≈ 2.8 h", "≈ 17 GB"],
   ["C", "3", "≈ 180, 105, 85 s", "≈ 1.1 h", "≈ 7 GB"],
   ["D", "reuses C's 5 m/s flight", "105 s × 4 noise levels", "≈ 1.1 h", "4 noised copies"],
   ["E (faults)", "reuses room_square", "70 s × 9 variants", "≈ 1.6 h", "≈ 11 GB"],
   ["Headroom", "room_square", "2 LiDAR methods × 4 rates", "≈ 0.3 h", "small"]],
  [24, 36, 48, 26, 36])
P("Roughly 8–9 hours of unattended compute in total (more if Gazebo runs below real time with PX4), so the groups fit "
  "into evenings and nights. Bags are about 18 MB/s (two 752 × 480 image streams plus 200 000 points/s); with noised "
  "copies and EuRoC folders the total is about 100–120 GB of the 283 GB free. Flights are kept; noised copies and "
  "EuRoC folders can be deleted after scoring and re-created exactly (fixed seeds).")

H2("5.5 The additions, specified")
H3("(a) Sensor-fault injection: degrade_bag.py (new)")
P("One script writes a degraded copy of a recorded bag; everything else is copied byte for byte. The faults start at "
  "a fixed time in the middle of the square, after every method has initialised, and the same window is used for all "
  "algorithms.")
T([["Variant", "What is changed", "Tests"],
   ["cam_black_5s", "both camera images set to zero for 5 s (stamps kept)", "vision loss: does FAST-LIVO2 continue on LiDAR?"],
   ["cam_dim30, cam_dim10", "all images scaled to 30 % / 10 % brightness, noise re-added at the original level", "darkness (UAV study: ORB-SLAM3 TSR 31 %)"],
   ["lidar_drop_2s, lidar_drop_5s", "LiDAR messages removed for 2 s / 5 s", "LiDAR loss: IMU-only propagation"],
   ["lidar_thin25", "every 4th point kept for the whole flight (point_num updated)", "a cheaper, sparser LiDAR"],
   ["cam_dt5, cam_dt10, cam_dt20", "camera stamps shifted +5, +10, +20 ms (all algorithms are told 0 ms)", "required hardware sync precision"]],
  [34, 76, 60])
P("ORB-SLAM3 reads images through the EuRoC conversion, so the converter is run on each degraded bag; FAST-LIO2 is "
  "unaffected by camera faults by construction and serves as the control. Scoring adds Δ APE, recovery within 5 s, "
  "and TSR; the error-over-time plot shows the window.")
H3("(b) Real-time headroom")
P("run_ros_algo.sh already takes a replay rate. FAST-LIO2 and FAST-LIVO2 are replayed at 1×, 2×, 4× and 8× on "
  "room_square and one urban flight; the headroom is the fastest rate that keeps coverage ≥ 0.95 and APE within 1.5× of "
  "the 1× result. ORB-SLAM3's EuRoC binary paces itself to real time and never drops frames, so its headroom is "
  "camera period ÷ p95 tracking time per frame, measured with upstream's own REGISTER_TIMES instrumentation in a "
  "derived image (scripts/stage3/orbslam3_timing.sh; 4.0× in the Stage 3 room flight).")
H3("(c) Stretch: mounting experiment (≈ 1 day)")
P("A second rig file, config/rig_upright.yaml, with mount roll 0 and the camera re-pointed so it still looks 35° down "
  "(rpy [0, +0.6109, 0], to be confirmed with camera_check.py). gen_configs.py accepts --rig and --tag, but today a "
  "non-'sim' tag skips the Gazebo models, so it needs a small extension to write a tagged iris model. Fly the urban "
  "square at 5, 10 and 20 m. Figure 2 predicts the upright LiDAR loses the ground above about 5 m.")
H3("(d) Stretch: map accuracy (≈ 1 day)")
P("Enable map saving for the LiDAR methods (FAST-LIO2: pcd_save_en is false in the generated config today). Build a "
  "reference cloud by transforming noise-free scans with ground-truth poses; align each saved map with the trajectory's "
  "SE3; report mean/RMS cloud-to-cloud distance and completeness; render an error-coloured map for the slides. "
  "ORB-SLAM3's sparse map is excluded.")

H2("5.6 Reading the results honestly")
BL(["Median of ≥ 3 runs, with the spread. One run is an anecdote.",
    "Coverage before APE: a run that tracked 40 % of the flight with 5 cm error is a failure, not a 5 cm result.",
    "RPE and drift % for drift, APE for the overall picture.",
    "Every anomaly gets an explanation or a flag, after the four-step configuration check of §4.5."])
H2("5.7 Threats to validity (written beside the results)")
T([["Limitation", "Effect"],
   ["No intra-scan LiDAR motion (all 20 000 points share one stamp)", "motion de-skewing is never exercised; "
    "FAST-LIVO2 uses alternate images"],
   ["Perfect synchronisation", "real sensors have offsets (partly addressed by the timing-offset test)"],
   ["Idealised camera: no blur, rolling shutter, auto-exposure, distortion", "flatters vision, especially at speed"],
   ["Idealised LiDAR: Gaussian range noise, no multipath or reflectivity effects", "flatters LiDAR"],
   ["IMU model: white noise + random walk only", "no temperature drift or vibration"],
   ["Default tuning everywhere", "measures robustness, not best achievable accuracy"],
   ["Workstation compute", "relative only; Stage 6 measures the Jetson"]],
  [80, 90])
P("These limits are why Phase 2 exists: the simulation tells us where to look, hardware tells us what is true.")

# ------------------------------------------------------------------ PART 6  STAGE 5
H1("6. Stage 5 in detail: flying on SLAM in simulation")
H2("6.1 Goal and why")
P("<b>Goal:</b> the simulated drone takes off, flies and lands with FAST-LIO2 as its <b>only</b> source of position, "
  "height and heading, through PX4's EKF2: exactly the configuration it will have on the real airframe. "
  "<b>Why:</b> Stages 1–4 measure SLAM accuracy, which is not flyability. EKF2 must accept the estimate at its rate and "
  "latency, and the controller must hold position on it. This is the integration the project exists to achieve, and "
  "far cheaper to debug in simulation. <b>Why FAST-LIO2:</b> it runs directly on the Mid-360 with no camera sync, "
  "publishes one pose per scan with low latency, and is the cheapest on the Jetson (FAST-LIVO2 can be swapped in the "
  "same way). <b>Gate:</b> a complete OFFBOARD square flown on external vision alone, PX4's estimate tracking ground "
  "truth, a stable hover.")
FIGURE(F_S5, 168, "Figure 4. The Stage 5 closed loop. The only position, height and heading information PX4 "
       "receives is FAST-LIO2's pose, re-expressed through the rig mount.")

H2("6.2 The frame problem, solved once")
P("FAST-LIO2 reports the pose of the <b>IMU</b> in <font face='DVM'>camera_init</font>, the IMU frame at the moment "
  "FAST-LIO2 started. PX4 wants the pose of the <b>vehicle</b> (base_link, x forward, y left, z up) in a "
  "gravity-aligned local frame. Because the rig hangs upside-down, the two are upside-down relative to each other: fed "
  "raw, a 2 m climb arrives at PX4 as a 2 m descent, and the controller fights it.")
P("Let M = T_base_imu, the mount from rig.yaml (rotation diag(1, −1, −1), offset (0.12, 0, −0.06) m, in "
  "config/generated/mount.yaml). The vehicle pose is the IMU pose with the mount removed: T_world_base(t) = "
  "T_world_imu(t) · M⁻¹. Choose the local frame as the vehicle frame at start-up (vehicle level and still on the "
  "ground), and note that camera_init is the IMU frame at start-up. Then")
CODE("T_local_base(t) = T_base0_world · T_world_base(t)\n"
     "                = (M · T_imu0_world) · (T_world_imu(t) · M⁻¹)\n"
     "                = M · T_ci_imu(t) · M⁻¹        ← what slam_to_px4.py computes for every pose")
P("The SLAM motion is re-expressed through the mount. Worked example: the vehicle climbs 2 m. In the inverted IMU "
  "frame 'up' is −z, so FAST-LIO2 reports z = −2 m; conjugating by M (which flips y and z) gives +2 m. The guide "
  "verified the relay numerically (200 random poses reconstructed to 4 × 10⁻¹⁵). The pose is published on "
  "/mavros/vision_pose/pose stamped with the scan's <b>capture</b> time, not the computation time, so EKF2 can place it "
  "correctly in its history and the delay parameter starts at 0.")

H2("6.3 PX4 configuration for vision-only flight (config/px4/ev_only.params)")
P("Values and meanings checked against the PX4 v1.14.4 source inside our evtol/sim:v1 image "
  "(src/modules/ekf2/ekf2_params.c).")
T([["Parameter", "Value", "Meaning (PX4 v1.14.4)", "Default"],
   ["EKF2_EV_CTRL", "11", "bitmask: 1 horizontal position + 2 vertical position + 8 yaw (4 = velocity not used: "
    "FAST-LIO's pose message has none)", "15"],
   ["EKF2_HGT_REF", "3", "height reference = vision (reboot required)", "1 (GPS)"],
   ["EKF2_GPS_CTRL", "0", "no GNSS aiding", "7"],
   ["EKF2_BARO_CTRL", "0", "no barometer", "1"],
   ["EKF2_MAG_TYPE", "5", "magnetometer never used: heading from SLAM only (reboot required)", "0 (automatic)"],
   ["EKF2_EV_NOISE_MD", "1", "use the noise parameters below, not the message covariance", "0"],
   ["EKF2_EVP_NOISE / EVA_NOISE", "0.1 m / 0.05 rad", "assumed position / angle noise of the vision pose", "–"],
   ["EKF2_EV_DELAY", "0 ms", "stamps are capture times; tune only if needed", "–"],
   ["EKF2_EV_POS_X/Y/Z", "0", "slam_to_px4.py already outputs base_link", "–"]],
  [40, 24, 82, 24])
P("GPS, barometer and magnetometer are all off on purpose: a SLAM fault must not be masked by another sensor quietly "
  "taking over. set_params.py reads every value back and fails loudly if one did not take: on a real vehicle, flying "
  "with half the configuration is worse than not flying.")
NOTE("Why two boots.", "EKF2_HGT_REF and EKF2_MAG_TYPE are marked 'reboot required' in PX4. SITL keeps parameters in a "
     "file inside the container, so sim_ev.sh boots once, writes the parameters, shuts down and boots again. On the "
     "second boot PX4 has no position source at all until SLAM publishes.", "info")

H2("6.4 A realistic IMU, live")
P("imu_noise_live.py is the live twin of imu_noise.py (same model, same densities, fixed seed): /livox/imu → "
  "/livox/imu_noisy, and FAST-LIO2 is launched with imu_topic:=/livox/imu_noisy. Closing the loop on a perfect IMU "
  "would flatter the result.")

H2("6.5 Running it: three terminals")
P("Stage 5 needs several containers sharing one ROS master, so its services use host networking. Two compose services "
  "must be added (deliberately left out in Stage 2, deviation 3): <b>sim-live</b> and <b>fastlio2-live</b>, both "
  "<font face='DVM'>network_mode: host</font>. Never run them alongside Stage 1–4 services, which start their own ROS "
  "master on the same port.")
T([["Terminal", "Command", "Wait for"],
   ["1", "docker compose run --rm sim-live bash /scripts/stage5/sim_ev.sh room", "every parameter line 'OK', then "
    "'PX4 is up with NO position source'"],
   ["2", "docker compose run --rm fastlio2-live bash /scripts/stage5/slam_live.sh", "RViz shows the map; "
    "/mavros/local_position/pose starts publishing (EKF2 accepted SLAM)"],
   ["3", "docker compose run --rm sim-live bash -c \"source /opt/ros/noetic/setup.bash &amp;&amp; python3 "
    "/scripts/stage3/offboard_mission.py square --size 4 --alt 1.5 --speed 1 --sitl-params\"", "take-off, hop, square "
    "(vehicle spawned at −2.0, −1.8 as in Stage 3), "
    "landing, disarm; then Ctrl-C terminal 1 (closes the bag), then terminal 2"]],
  [19, 97, 54])

H2("6.6 Evaluate: two numbers, two questions")
CODE("bag_to_tum.py closed_loop_room.bag /ground_truth/odom          gt.tum\n"
     "bag_to_tum.py closed_loop_room.bag /mavros/local_position/pose px4__room__r1.tum\n"
     "bag_to_tum.py closed_loop_room.bag /Odometry                  fastlio2__room__r1.tum\n"
     "eval_traj.sh gt.tum px4__room__r1.tum      eval/px4__room__r1\n"
     "eval_traj.sh gt.tum fastlio2__room__r1.tum eval/fastlio2__room__r1")
P("<b>fastlio2</b> = SLAM accuracy in closed loop. <b>px4</b> = what the vehicle believes after EKF2 fusion: the "
  "estimate it actually flies on. Ground truth is the IMU's pose and PX4's is base_link's; the 0.134 m lever arm between "
  "them (√(0.12² + 0.06²)) adds a few centimetres to the PX4 score under rotation. We add hover steadiness: the "
  "standard deviation of the ground-truth position over a 20 s hover (hover profile).")

H2("6.7 Gate and tuning")
BL(["the mission ran to completion: take-off, square, landing, disarm;",
    "PX4's APE within a small multiple of FAST-LIO2's own: EKF2 fuses the estimate rather than fighting it;",
    "the hover is steady in the Gazebo window, with no growing oscillation (a human judgement: numbers inform it);",
    "only if the vehicle oscillates while moving: step EKF2_EV_DELAY in 10 ms increments, re-fly, keep the value that "
    "minimises PX4's APE."])
H2("6.8 Stage 5 risks")
T([["Risk", "Response"],
   ["10 Hz vision rate is low: PX4 users typically feed visual odometry at 30 Hz or more", "EKF2 predicts with the "
    "IMU between updates; if the hover is soft, tune EVP/EVA noise first, then EV_DELAY"],
   ["heading only from SLAM (magnetometer off)", "intended; any yaw drift shows directly in PX4's yaw"],
   ["SLAM must be running before take-off", "terminal order is enforced; the mission waits for a local position"],
   ["frame error (a climb read as a descent)", "before the first closed-loop flight, replay a Stage 3 PX4 bag through "
    "FAST-LIO2 + slam_to_px4.py offline and compare its output with the ground-truth base_link pose"],
   ["ROS master clash", "stop all other compose services first"]],
  [70, 100])
NOTE("Schedule decision.", "Stage 5 is the most impressive demo but carries the most integration risk (guide: 3–5 days). "
     "Go/no-go on Sun 22 Nov: if Stage 4 groups A, B, D and the fault tests are done and explained, Stage 5 gets Mon 23; "
     "otherwise it is presented as the bridge to the hardware phase, with this chapter as its plan.", "decide")

# ------------------------------------------------------------------ PART 7
H1("7. The 10-day plan and the review")
FIGURE(F_GANTT, 168, "Figure 5. Ten days to the review. Long algorithm runs go overnight; days are for checking, "
       "fixing and plotting.")
T([["Day", "Work", "Done when"],
   ["Mon 16", "Stage 3a: transcribe files, IMU noise check, scripted bag × 3, metrics_extra + cost_probe", "scripted summary matches the smoke test; new metrics verified"],
   ["Tue 17", "Stage 3b: first PX4 flight (watched), bag check, 3 × 3 runs, gate, stage3_log.md", "gate passed"],
   ["Wed 18", "run_matrix.sh; group A by day; group B starts overnight", "A table and anomalies explained"],
   ["Thu 19", "inspect B; group D; write degrade_bag.py and ground_points.py", "altitude curve vs prediction"],
   ["Fri 20", "fault and timing-offset variants (overnight)", "variants verified by eye (images, scan counts)"],
   ["Sat 21", "fault analysis, error-over-time, headroom; group C overnight", "H4, H5 numbers"],
   ["Sun 22", "scorecard, altitude, trade-off figures; <b>Stage 5 go/no-go</b>", "all core figures"],
   ["Mon 23", "Stage 5, or mounting / map stretch", "closed-loop flight or stretch result"],
   ["Tue 24", "videos, recommendation table, slides", "deck complete"],
   ["Wed 25", "buffer, rehearsal", "–"]],
  [16, 104, 50])
H2("7.1 Suggested review deck (about 14 slides)")
NL(["The question: GPS-free navigation for eVTOLs; which sensor set?",
    "The three methods and the rig (inverted Mid-360, stereo, IMU).",
    "Method and fairness: record once, replay many; gates; SE3; median of 3; coverage first.",
    "Builds proven: Stage 1 table against the papers.",
    "Sensors proven: Stage 2 gate (IMU vs ground truth to 0.001 m/s²).",
    "Metrics: the five headline metrics, defined.",
    "Scorecard heatmap: the whole study.",
    "Altitude: prediction (Figure 2) vs measured, with APE h/v.",
    "Environments: which modality fails where.",
    "Sensor failures: error over time; recovery; the 'is the extra modality worth it?' answer.",
    "IMU grade and timing offset: what the hardware must meet.",
    "Compute: accuracy vs CPU, headroom (Jetson numbers in Phase 2).",
    "Recommendation table, plus Stage 5 closed loop or its plan.",
    "Threats to validity and Phase 2 plan (Stages 6–8)."])
H2("7.2 What the simulation hands to Phase 2")
BL(["the required camera-LiDAR sync precision (timing-offset test) → hardware trigger and Kalibr targets;",
    "the IMU grade that is good enough (group D) → whether the Mid-360's internal IMU suffices;",
    "the altitude envelope of each method (group B) → mission planning and the mounting decision;",
    "the integration of SLAM into PX4 (Stage 5) → the exact parameter file flown on the real airframe;",
    "workstation compute ratios → which algorithms to try first on the Jetson (Stage 6)."])

# ------------------------------------------------------------------ APPENDICES
H1("Appendix A. Glossary")
T([["Term", "Meaning"],
   ["SLAM", "Simultaneous Localisation and Mapping: estimating your own pose while building a map"],
   ["eVTOL", "electric vertical take-off and landing aircraft"],
   ["Modality", "the type of sensor a method relies on: camera, LiDAR, or both"],
   ["IMU", "inertial measurement unit: angular rate (gyro) and specific force (accelerometer)"],
   ["Noise density / random walk", "continuous-time white-noise level of an IMU, and how fast its bias wanders"],
   ["Pose", "position plus orientation; trajectory = poses over time"],
   ["Ground truth", "the true trajectory; exact in simulation"],
   ["SE3 / Sim3 alignment", "best rigid transform (rotation + translation) between estimate and truth; Sim3 also scales"],
   ["APE / ATE", "absolute pose (trajectory) error after alignment"],
   ["RPE", "relative pose error over fixed-length segments: drift"],
   ["Coverage", "share of the flight for which the method produced poses"],
   ["TSR", "tracking success rate: share of time the estimate exists and is within a threshold"],
   ["Bag", "a ROS recording of timestamped messages"],
   ["SITL", "software in the loop: the real PX4 autopilot code running against a simulator"],
   ["OFFBOARD", "PX4 mode in which an external computer streams setpoints"],
   ["EKF2", "PX4's extended Kalman filter that fuses sensors into the vehicle state"],
   ["External vision (EV)", "a pose source outside PX4 (here SLAM) fed through MAVROS"],
   ["Lockstep", "simulator and autopilot advance time together"],
   ["Extrinsics", "the fixed transforms between sensors"],
   ["C2C", "cloud-to-cloud distance between two point clouds"]],
  [42, 128])

H1("Appendix B. Command sheet")
CODE("""# --- pre-flight (host, project root)
docker images | grep evtol ; nvidia-smi ; git status ; git diff --stat final_results/ ; df -h .

# --- Stage 3a: scripted bag
bash scripts/stage3/run_all_algos.sh output/stage2/scripted_room.bag room output/stage3/scripted 3
cat output/stage3/scripted/eval/summary.md

# --- Stage 3b: PX4 flight (watch the GUI), then all three algorithms
GUI=true docker compose run --rm -e GUI -e SPAWN="-2.0 -1.8" sim bash /scripts/stage3/px4_record.sh \\
    room square /output/stage3/flights/room_square.bag --size 4 --alt 1.5 --speed 1.5 --laps 3
bash scripts/stage3/run_all_algos.sh output/stage3/flights/room_square.bag \\
    room_square output/stage3/px4 3      # move output/stage3/px4 aside first if the bag was re-recorded
bash scripts/stage3/orbslam3_timing.sh output/stage3/px4 room_square 3

# --- Stage 4
ONLY=environments bash scripts/stage4/run_matrix.sh
ONLY=altitude     bash scripts/stage4/run_matrix.sh
ONLY=imu          bash scripts/stage4/run_matrix.sh
ONLY=speed        bash scripts/stage4/run_matrix.sh
docker compose run --rm eval python3 /scripts/stage4/plot_sweeps.py /output/stage4

# --- Stage 5 (three terminals, host networking, nothing else running)
docker compose run --rm sim-live bash /scripts/stage5/sim_ev.sh room
docker compose run --rm fastlio2-live bash /scripts/stage5/slam_live.sh
docker compose run --rm sim-live bash -c "source /opt/ros/noetic/setup.bash && \\
    python3 /scripts/stage3/offboard_mission.py square --size 4 --alt 1.5 --speed 1 --sitl-params"

# --- bag tools inside the eval container always go through ros_python.sh
docker compose run --rm eval bash /scripts/common/ros_python.sh \\
    /scripts/common/bag_to_tum.py <bag> <topic> <out.tum>""")

H1("Appendix C. File map")
T([["Path", "What it is"],
   ["config/rig.yaml", "the rig: single source of truth"],
   ["config/generated/", "algorithm configs, mount.yaml, extrinsics_report.txt (generated, never edited)"],
   ["config/launch/ (Stage 3)", "explicit-config launch files for FAST-LIO2 and FAST-LIVO2"],
   ["config/px4/ev_only.params (Stage 5)", "PX4 vision-only parameter set"],
   ["sim/evtol_sim/", "Gazebo models (evtol_rig_scripted, iris_evtol), worlds, launch (generated)"],
   ["scripts/common/", "shared tools: gen_configs, gen_world, eval_traj, results_table, bag_to_tum, run_ros_algo, "
    "latency_probe, ros_python, sim_env; Stage 3 adds imu_noise, bag_to_euroc, metrics_extra, cost_probe"],
   ["scripts/stage2/", "recording and the Stage 2 gate"],
   ["scripts/stage3/", "run_all_algos.sh, offboard_mission.py, px4_record.sh"],
   ["scripts/stage4/", "run_matrix.sh, plot_sweeps.py, degrade_bag.py, ground_points.py, scorecard.py, plot_error_time.py"],
   ["scripts/stage5/", "slam_to_px4.py, set_params.py, imu_noise_live.py, sim_ev.sh, slam_live.sh"],
   ["output/stage3, stage4, stage5", "flights, noised bags, per-run trajectories, eval/summary tables, figures"],
   ["docs/", "logs per stage, audit, summary PDF, this document and its generator"],
   ["final_results/", "Stage 1 comparison tables (check git diff before claiming consistency)"]],
  [56, 114])

H1("Appendix D. Sources")
SRC = [
    ("Project guide", "eVTOL-SLAM-Complete-Project-Guide.pdf, Stages 3–5 (repository root)"),
    ("Project logs", "docs/stage2_log.md, docs/stage1_2_audit.md, final_results/"),
    ("Paper 1", "Garigipati et al. 2022, evaluation of eight LiDAR and visual SLAM methods (EPUB collection)"),
    ("Paper 2", "Tiozzo Fasiolo et al. 2023, LiDAR and IMU SLAM for 3-D mapping, Robotica (EPUB collection)"),
    ("Paper 3", "Hernas et al. 2025, ROS 2 SLAM comparison in Gazebo (EPUB collection)"),
    ("Paper 4", "Sier et al. 2022, multi-LiDAR SLAM benchmark (EPUB collection)"),
    ("Papers 5–6", "Zhu et al. 2024 and Fan et al. 2025, multi-sensor fusion SLAM surveys (EPUB collection)"),
    ("Robust-SLAM", "https://arxiv.org/html/2402.08125v1"),
    ("LiDAR degradation", "https://arxiv.org/abs/2512.08653"),
    ("UAV visual SLAM study", "https://arxiv.org/abs/2605.03678"),
    ("Hilti 2023", "https://arxiv.org/html/2404.09765v2"),
    ("Hilti 2022", "https://arxiv.org/pdf/2208.09825.pdf"),
    ("Hilti-style scoring", "https://arxiv.org/pdf/2403.02280"),
    ("COIN-LIO study", "https://arxiv.org/html/2411.16931v2"),
    ("ISPRS 2025 benchmark", "https://isprs-archives.copernicus.org/articles/XLVIII-1-W6-2025/25/2025/"),
    ("LiDAR odometry survey", "https://link.springer.com/content/pdf/10.1007/s11370-024-00515-8.pdf"),
    ("FAST-LIVO2", "https://arxiv.org/pdf/2408.14035"),
    ("LIR-LIVO", "https://arxiv.org/pdf/2502.08676"),
    ("PX4 v1.14 EKF2 guide", "https://docs.px4.io/v1.14/en/advanced_config/tuning_the_ecl_ekf.html"),
    ("PX4 parameters", "PX4-Autopilot v1.14.4, src/modules/ekf2/ekf2_params.c (inside evtol/sim:v1)"),
    ("PX4 forum, EV rate", "https://discuss.px4.io/t/ekf2-vio-not-working-settings-and-code-not-correct/39289"),
    ("evo metrics", "https://github.com/MichaelGrupp/evo/wiki/Metrics"),
    ("Mid-360 scan table", "fratopa/Mid360_simulation_plugin, scan_mode/mid360-real-centr.csv (inside evtol/sim:v1)"),
]
T([["Source", "Reference"]] + [[a, esc(b)] for a, b in SRC], [40, 130])


# ------------------------------------------------------------------ build
class Doc(BaseDocTemplate):
    def __init__(self, fn, **kw):
        super().__init__(fn, **kw)
        fr = Frame(20 * mm, 18 * mm, 170 * mm, 259 * mm, id="f")
        self.addPageTemplates([PageTemplate(id="p", frames=[fr], onPage=self.deco)])

    def deco(self, c, doc):
        if doc.page == 1:
            return
        c.saveState()
        c.setFont("DV", 7.5); c.setFillColor(MUTED)
        c.drawString(20 * mm, 10 * mm, "eVTOL SLAM: research findings and Stage 3–5 plan · 16 Nov 2026")
        c.drawRightString(190 * mm, 10 * mm, "page %d" % doc.page)
        c.setStrokeColor(RULE); c.line(20 * mm, 13.5 * mm, 190 * mm, 13.5 * mm)
        c.restoreState()

    def afterFlowable(self, f):
        if isinstance(f, Paragraph):
            s = f.style.name
            if s in ("h1", "h2"):
                txt = f.getPlainText()
                key = "k%d" % id(f)
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(txt, key, level=0 if s == "h1" else 1)
                self.notify("TOCEntry", (0 if s == "h1" else 1, txt, self.page, key))


doc = Doc(OUT, pagesize=A4, title="eVTOL SLAM: research findings and Stage 3-5 plan",
          author="eVTOL SLAM project", leftMargin=20 * mm, rightMargin=20 * mm)
doc.multiBuild(story)
print("wrote", OUT)
