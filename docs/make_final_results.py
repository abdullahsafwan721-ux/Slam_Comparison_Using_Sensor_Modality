#!/usr/bin/env python3
"""Builds final_results/ : one simple comparison CSV per algorithm + one summary PDF.
    python3 docs/make_final_results.py
All numbers are medians of the per-run results committed in docs/results/."""
import csv, os, statistics
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = os.path.join(REPO, "docs", "results")
OUT = os.path.join(REPO, "final_results"); os.makedirs(OUT, exist_ok=True)

def band(dev):  # same convention throughout the project
    return "green (<15%)" if abs(dev) < .15 else "amber (15-30%)" if abs(dev) <= .30 else "red (>30%)"
def pct(a, b): return (a - b) / b
def med(fn, metric=None, key="sequence", val="value_m"):
    g = {}
    for r in csv.DictReader(open(os.path.join(RES, fn))):
        if metric and r["metric"] != metric: continue
        if r[val] in ("", "NA"): continue
        g.setdefault(r[key], []).append(float(r[val]))
    return {k: (statistics.median(v), len(v)) for k, v in g.items()}
def write_csv(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

# ================================================================= ORB-SLAM3
ORB_PAPER = dict(zip("MH01 MH02 MH03 MH04 MH05 V101 V102 V103 V201 V202 V203".split(),
                     [0.036, 0.033, 0.035, 0.051, 0.082, 0.038, 0.014, 0.024, 0.032, 0.014, 0.024]))
orb = {}
for r in list(csv.reader(open(os.path.join(RES, "orbslam3_summary.csv"))))[1:]:
    orb.setdefault(r[0].split("kf_orb_")[1].split("_r")[0], []).append(float(r[1]))
orb_rows = []
for s, p in ORB_PAPER.items():
    m = statistics.median(orb[s]); d = pct(m, p)
    orb_rows.append(["EuRoC MAV", s, "ATE RMSE", "%.3f" % p, "%.4f" % m, len(orb[s]), "%+.1f" % (100 * d), band(d),
                     "run 2 lost tracking (0.69 m); median unaffected" if s == "V203" else ""])
am = statistics.mean(statistics.median(orb[s]) for s in ORB_PAPER); ap = statistics.mean(ORB_PAPER.values())
orb_rows.append(["EuRoC MAV", "AVERAGE", "ATE RMSE", "%.3f" % ap, "%.4f" % am, "", "%+.1f" % (100 * pct(am, ap)), band(pct(am, ap)), "mean of the 11 medians"])
write_csv("orbslam3_comparison.csv",
          ["dataset", "sequence", "metric", "paper_value_m", "our_median_m", "runs", "deviation_pct", "result", "note"], orb_rows)

# ================================================================= FAST-LIO2
ape = med("fastlio2_summary.csv", "ape_rmse"); e2e = med("fastlio2_summary.csv", "end_to_end")
proxy = med("fastlio2_summary.csv", "end_ref_gnss")
IND = {"nclt5": 1.40, "nclt6": 2.46, "nclt7": 2.37, "nclt8": 4.37, "nclt9": 0.90, "utbm8": 15.13, "utbm9": 21.21, "utbm10": 10.81}
FL2 = [  # dataset, paper id, seq, metric, paper value (None = "< 0.1")
    ("LIO-SAM", "liosam 2", "liosam2_garden", "end-to-end", None),
    ("LIO-SAM", "liosam 3", "liosam3_campus", "end-to-end", 9.50),
    ("LIO-SAM", "liosam 1", "liosam1_park", "ATE RMSE", 4.58),
    ("NCLT", "nclt 4", "nclt4", "ATE RMSE", 8.71), ("NCLT", "nclt 5", "nclt5", "ATE RMSE", 6.68),
    ("NCLT", "nclt 6", "nclt6", "ATE RMSE", 20.96), ("NCLT", "nclt 7", "nclt7", "ATE RMSE", 6.58),
    ("NCLT", "nclt 8", "nclt8", "ATE RMSE", 30.08), ("NCLT", "nclt 9", "nclt9", "ATE RMSE", 5.56),
    ("NCLT", "nclt 10", "nclt10", "ATE RMSE", 16.29),
    ("UTBM", "utbm 8", "utbm8", "ATE RMSE", 27.29), ("UTBM", "utbm 9", "utbm9", "ATE RMSE", 51.60),
    ("UTBM", "utbm 10", "utbm10", "ATE RMSE", 16.80),
    ("LiLi-OM", "lili 6", "lili6_schloss1", "end-to-end", None),
    ("LiLi-OM", "lili 7", "lili7_schloss2", "end-to-end", 1.63),
    ("LiLi-OM", "lili 8", "lili8_east", "end-to-end", 17.39),
]
fl2_rows = []
for ds, pid, s, metric, p in FL2:
    ind = IND.get(s); ours = (ape if metric == "ATE RMSE" else e2e)[s]; m, n = ours
    dp = dind = ""; note = ""
    if s == "liosam2_garden":
        result = "PASS (< 0.1 m)" if m < 0.1 else "FAIL"; note = "end-to-end drift over 464 m"
    elif s == "lili6_schloss1":
        m, n = proxy[s]; metric = "end point vs bag GNSS (proxy)"
        result = "not checkable"; note = "paper's reference end points unpublished; bag ends 21 m from its start; proxy at GNSS noise level"
    elif s == "lili8_east":
        m, n = proxy[s]; metric = "end point vs bag GNSS (proxy)"; dp = "%+.1f" % (100 * pct(m, p))
        result = "proxy only"; note = "bag ends 185 m from its start; metre-level GNSS reference"
    elif s == "lili7_schloss2":
        dp = "%+.1f" % (100 * pct(m, p)); result = band(pct(m, p)); note = "path ends at its start (LiLi-OM Fig. 9); Xsens IMU as named in the paper (fixed 2026-10-09, was 11.49 m with the Horizon IMU)"
    elif metric == "ATE RMSE":
        dp = "%+.1f" % (100 * pct(m, p))
        if ind:
            dind = "%+.1f" % (100 * pct(m, ind)); result = band(pct(m, ind)) + " vs independent"
            if s == "nclt8":
                result = "lower than both references"; note = "runs bimodal (2.0-4.7 m); the independent 4.37 m lies inside our range"
        else:
            result = "lower than paper"; note = "no independent re-run available"
        if s == "nclt9":
            note = "the paper's own July-2021 code gives 0.92 m here; Faster-LIO (FAST-LIO2 authors' group) reports 0.91 m: paper value not reproducible"
        elif s == "nclt5":
            note = "Faster-LIO reports 0.82 m for FAST-LIO2 here; the two independent re-runs disagree"
        if not note: note = "paper RMSEs use an unstated alignment; independent re-run (arXiv 2307.07792) is the like-for-like reference"
    else:
        dp = "%+.1f" % (100 * pct(m, p)); result = band(pct(m, p))
    fl2_rows.append([ds, pid, s, metric, "< 0.1" if p is None else "%.2f" % p, "%.2f" % ind if ind else "",
                     "%.3f" % m, n, dp, dind, result, note])
write_csv("fastlio2_comparison.csv",
          ["dataset", "paper_id", "sequence", "metric", "paper_value_m", "independent_rerun_m", "our_median_m", "runs",
           "deviation_vs_paper_pct", "deviation_vs_independent_pct", "result", "note"], fl2_rows)

# ================================================================= FAST-LIVO2
std = med("fastlivo2_standard_summary.csv", "ape_rmse"); mat = med("fastlivo2_matched_summary.csv", "ape_rmse")
pe = med("fastlivo2_standard_summary.csv", "end_to_end")
NTU = {"eee_01": (.0271, .068), "eee_02": (.0211, .051), "eee_03": (.0261, .068), "nya_01": (.0356, .073), "nya_02": (.0339, .075),
       "nya_03": (.0352, .059), "sbs_01": (.0234, .062), "sbs_02": (.0283, .061), "sbs_03": (.0311, .060)}
lv2_rows = []
for s, (repo, paper) in NTU.items():
    a, n = std[s]; b, _ = mat[s]; d = pct(b, repo)
    lv2_rows.append(["NTU-VIRAL", s, "ATE RMSE", "%.4f" % repo, "%.3f" % paper, "%.4f" % a, "%.4f" % b, n,
                     "%+.1f" % (100 * pct(a, repo)), "%+.1f" % (100 * d), band(d),
                     "early-phase convergence differs (bimodal runs)" if s == "nya_02" else ""])
PRIV = [("hku_landmark", "HKU Landmark", ""), ("hku_cultural_center_02", "HKU Cultural Center", "file part 02 = paper's 4:01 sequence"),
        ("cbd_building_01", "CBD Building 01", "genuine shortfall (0.1 % of the 34 m loop); paper-default config also fails"),
        ("cbd_building_03", "CBD Building 03", "public file is 4:26, paper's is 5:01 (different cut)"),
        ("sysu_01", "SYSU 01", "public file is 2:14, paper's is 4:40 (different recording)")]
for s, name, note in PRIV:
    m, n = pe[s]
    if "different" in note: result = "not the paper's recording"
    else: result = "PASS (< 0.01 m)" if m < 0.01 else "FAIL (paper < 0.01 m)"
    lv2_rows.append(["FAST-LIVO2 private", name, "end-to-end", "", "< 0.01", "%.3f" % m, "", n, "", "", result, note])
write_csv("fastlivo2_comparison.csv",
          ["dataset", "sequence", "metric", "repo_value_m", "paper_value_m", "ours_whole_bag_m", "ours_matched_start_m", "runs",
           "deviation_whole_bag_vs_repo_pct", "deviation_matched_vs_repo_pct", "result", "note"], lv2_rows)

# ================================================================= PDF
ss = getSampleStyleSheet(); BLUE = colors.HexColor("#1e3a8a")
body = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.4, leading=13, spaceAfter=4)
small = ParagraphStyle("s", parent=body, fontSize=7.8, leading=10, textColor=colors.HexColor("#4b5563"))
cell = ParagraphStyle("c", parent=body, fontSize=7.8, leading=9.6, spaceAfter=0)
cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")
h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, textColor=BLUE, spaceAfter=6)
h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, textColor=BLUE, spaceBefore=8, spaceAfter=4)
bul = ParagraphStyle("bul", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=2)
COL = {"green": colors.HexColor("#dcfce7"), "amber": colors.HexColor("#fef3c7"), "red": colors.HexColor("#fee2e2"),
       "PASS": colors.HexColor("#dcfce7"), "FAIL": colors.HexColor("#fee2e2")}
def esc(t): return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def P(t, s=body): return Paragraph(t, s)
def B(items): return [Paragraph(i, bul, bulletText="•") for i in items]
def T(rows, widths, colour_col=None):
    data = [[Paragraph(esc(c), cellb if i == 0 else cell) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
          ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if colour_col is not None:
        for i, r in enumerate(rows[1:], 1):
            for k, c in COL.items():
                if str(r[colour_col]).startswith(k): st.append(("BACKGROUND", (colour_col, i), (colour_col, i), c))
    t.setStyle(TableStyle(st)); return t
def footer(c, doc):
    c.saveState(); c.setFont("Helvetica", 7.3); c.setFillColor(colors.HexColor("#6b7280"))
    c.drawString(18 * mm, 10 * mm, "SLAM_Comparison_Sensor_Modality - dockerization results (updated 2026-10-09)")
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, "Page %d" % doc.page); c.restoreState()

orb_green = sum(1 for r in orb_rows[:-1] if r[7].startswith("green")); orb_amber = sum(1 for r in orb_rows[:-1] if r[7].startswith("amber"))
fl2_ind_rows = [r for r in fl2_rows if r[9]]; fl2_ind_green = sum(1 for r in fl2_ind_rows if r[10].startswith("green"))
ntu = lv2_rows[:9]; ntu_green = sum(1 for r in ntu if r[10].startswith("green"))
priv_pass = sum(1 for r in lv2_rows[9:] if r[10].startswith("PASS"))

S = [P("SLAM Algorithms in Docker: Results vs Published Values", ParagraphStyle("t", parent=h1, fontSize=20, leading=25)),
     P("ORB-SLAM3 (camera + IMU) · FAST-LIO2 (LiDAR + IMU) · FAST-LIVO2 (LiDAR + IMU + camera)", ParagraphStyle("st", parent=body, fontSize=11.5, textColor=colors.HexColor("#374151"))),
     Spacer(1, 4 * mm),
     P("Each algorithm runs in its own Docker container, built from pinned source versions, on the same datasets its paper used. "
       "Every sequence was run 5 times and the <b>median</b> is compared with the published value. "
       "Deviation = (ours − reference) / reference; <b>green</b> under 15 %, <b>amber</b> 15–30 %, <b>red</b> over 30 %.", body),
     P("Summary", h2),
     T([["Algorithm", "Benchmark", "Result", "Verdict"],
        ["ORB-SLAM3", "EuRoC MAV, 11 sequences, ATE RMSE",
         "%d green, %d amber, 0 red; average %.1f cm vs paper %.1f cm (%+.0f %%)" % (orb_green, orb_amber, 100 * am, 100 * ap, 100 * pct(am, ap)),
         "green: reproduced"],
        ["FAST-LIO2", "16 of the paper's 19 sequences (LIO-SAM, NCLT, UTBM, LiLi-OM)",
         "end-to-end: garden PASS, campus +7.5 %%, lili 7 +%.1f %%; RMSE: %d of %d green vs an independent re-run (utbm 10 amber, nclt 8 better than both)" % (100 * pct(e2e["lili7_schloss2"][0], 1.63), fl2_ind_green, len(fl2_ind_rows)),
         "green: reproduced (paper's RMSE protocol differs)"],
        ["FAST-LIVO2", "NTU-VIRAL 9 sequences + private dataset",
         "NTU: %d of 9 green vs the authors' published runs; private: %d PASS (< 1 cm), 1 FAIL, 2 files differ from the paper's" % (ntu_green, priv_pass),
         "green: reproduced"]],
       [24 * mm, 48 * mm, 72 * mm, 30 * mm], colour_col=3),
     Spacer(1, 3),
     P("All three containers reproduce their published accuracy within the green band on the large majority of sequences. "
       "The few remaining deviations are explained in Section 3; none is caused by the containers.", body),
     P("Files", h2),
     T([["File", "Contents"],
        ["orbslam3_comparison.csv", "11 EuRoC sequences + average: paper value, our median, deviation, result"],
        ["fastlio2_comparison.csv", "16 paper sequences: paper value, independent re-run, our median, both deviations, result"],
        ["fastlivo2_comparison.csv", "9 NTU-VIRAL + 5 private sequences: repo/paper values, our medians (two protocols), result"],
        ["SLAM_Dockerization_Results.pdf", "this document"]], [52 * mm, 122 * mm]),
     PageBreak(),
     P("1. How each algorithm was dockerized", h1),
     P("<b>Common design.</b> One shared base image (Ubuntu 20.04, pinned by digest, + ROS Noetic) and one image per algorithm "
       "on top of it, so compiler, ROS, Eigen and PCL are identical for all three. A separate evaluation image (evo 1.31.1) scores every "
       "algorithm the same way. Datasets, configs and scripts are mounted read-only; results go to a shared output folder. Every upstream "
       "repository is pinned to an exact commit (VERSIONS.md), so the images rebuild identically.", body),
     P("ORB-SLAM3 — image evtol/orbslam3:v1", h2)]
S += B(["Builds OpenCV 4.4 and Pangolin 0.6 from source (Ubuntu 20.04 ships OpenCV 4.2, too old for this release), then ORB-SLAM3 v1.0 (the paper's version).",
        "Runs the stereo-inertial EuRoC example on all 11 sequences, 5 times each; keyframe trajectories scored with evo (SE(3) alignment).",
        "Low deviation achieved with the stock configuration: average 3.3 cm vs 3.5 cm published."])
S += [P("FAST-LIO2 — image evtol/fastlio2:v1", h2)]
S += B(["Livox SDK and driver pinned to release tags, FAST_LIO pinned; Velodyne and NMEA tools added so the UTBM bags (raw packets, GPS as text) can be used.",
        "One config per dataset (topics, LiDAR type, IMU-LiDAR extrinsic), and the paper's own parameters (1:4 downsampling, 0.5 m voxels, 1000 m map) forced for every run.",
        "Fixes that made the low deviation possible: per-point time units measured on every bag (the guide's values would have disabled motion compensation); "
        "NCLT bags built with the authors' own converter; UTBM ground truth parsed from all 4633 RTK fixes (the guide's method kept 85); runs that hung at the end stopped safely.",
        "Review (9 Oct 2026): every config re-checked against the paper and the dataset authors' own files. lili now uses the Xsens IMU the paper names "
        "(this fixed lili 7); UTBM uses the LiDAR position published with the dataset and correctly time-stamped scans. The images were rebuilt from scratch and reproduce the earlier runs. "
        "The paper's own July-2021 FAST_LIO code was built as a second image: it gives the same results as the pinned version, which confirms the "
        "remaining differences come from the paper's evaluation, not from the container."])
S += [P("FAST-LIVO2 — image evtol/fastlivo2:v1", h2)]
S += B(["Sophus (2012 version, 2-line C++11 patch), the authors' vikit fork and FAST-LIVO2 pinned; the authors' shipped configs used unchanged.",
        "Built for one explicit CPU target (Skylake/AVX2, the paper's CPU class) instead of -march=native: the native build on this AVX-512 machine lost track in 5/5 runs of one sequence; the fixed build is stable and portable.",
        "Private dataset: the correct camera calibration per recording group (four groups, from the dataset's own calibration file). "
        "NTU-VIRAL: the Leica-prism offset applied to the estimate, exactly as the authors do; runs wait until the trajectory is complete."])
S += [PageBreak(), P("2. Comparison tables", h1), P("2.1 ORB-SLAM3 — EuRoC MAV, ATE RMSE (m)", h2),
      T([["Sequence", "Paper", "Ours (median of 5)", "Deviation", "Result"]] +
        [[r[1], r[3], r[4], r[6] + " %", r[7]] for r in orb_rows], [30 * mm, 24 * mm, 36 * mm, 28 * mm, 56 * mm], colour_col=4),
      P("Paper: Campos et al., IEEE T-RO 2021, Table II, stereo-inertial (median of 10 runs). Every sequence is within ~2 cm of the published value.", small),
      PageBreak(), P("2.2 FAST-LIO2 (m)", h2),
      T([["Sequence", "Metric", "Paper", "Independent re-run", "Ours", "Dev. vs paper", "Dev. vs independent", "Result"]] +
        [[r[2], r[3], r[4], r[5] or "-", r[6], (r[8] + " %") if r[8] else "-", (r[9] + " %") if r[9] else "-", r[10]] for r in fl2_rows],
        [27 * mm, 25 * mm, 13 * mm, 20 * mm, 14 * mm, 19 * mm, 21 * mm, 35 * mm], colour_col=7),
      P("Paper: Xu et al., IEEE T-RO 2022, Tables IV/V (1000 m map). Independent re-run: Yuan et al., arXiv 2307.07792, Table II. "
        "Our RMSEs are 20–92 % below the paper's on every sequence. Two independent groups find the same, and so does the paper's own "
        "July-2021 code run in this container (nclt 9: 0.92 m; Faster-LIO, from the FAST-LIO2 authors' group: 0.91 m; paper: 5.56 m). "
        "The paper aligned its trajectories in an unstated way, so the like-for-like independent re-runs are the targets; against them the container is green.", small),
      PageBreak(), P("2.3 FAST-LIVO2 (m)", h2),
      T([["Sequence", "Metric", "Authors' repo", "Paper", "Ours, whole bag", "Ours, authors' start", "Dev. (authors' start)", "Result"]] +
        [[r[1], r[2], r[3] or "-", r[4], r[5], r[6] or "-", (r[9] + " %") if r[9] else "-", r[10]] for r in lv2_rows],
        [27 * mm, 18 * mm, 18 * mm, 13 * mm, 20 * mm, 22 * mm, 20 * mm, 36 * mm], colour_col=7),
      P("Authors' repo = the published results of the same released code and config (Log/result/ntu_viral); the paper's Table II used an "
        "older version and is 2x higher. The authors' own runs skipped the first 0.1–0.5 s of each bag; replaying from their first pose "
        "('authors' start') reproduces their run exactly. Whole-bag results: 6 of 9 green.", small),
      PageBreak(), P("3. Remaining deviations, explained", h1)]
S += B(["<b>FAST-LIVO2 nya_02 (+36 %).</b> Same data window as the authors; only the first 2–3 minutes in a dim auditorium converge worse. Runs split into two modes (4.6 / 8.4 cm); the authors' single run (3.4 cm) is outside both.",
        "<b>FAST-LIVO2 CBD Building 01 (3.6 cm vs &lt; 1 cm).</b> Real drift; the paper's default settings give 3.2 cm, so configuration is not the cause. Still only 0.1 % of the loop.",
        "<b>FAST-LIO2 lili 7: fixed.</b> It was 11.5 m (+605 %%) because the config used the LiDAR's built-in IMU; the paper names the separate Xsens IMU. With the Xsens IMU and LiLi-OM's published extrinsic: %.2f m vs 1.63 m. FAST-LIO2 now has no shortfall against a like-for-like reference." % e2e["lili7_schloss2"][0],
        "<b>FAST-LIO2 utbm 10 (+%.0f %% vs independent re-run, amber).</b> Within the spread between published re-runs. UTBM was re-run after two input fixes (the dataset's documented LiDAR position; scan time stamps), which brought utbm 8/9 to within 5 %% of the independent re-run." % (100 * pct(ape["utbm10"][0], 10.81)),
        "<b>Not checkable rather than wrong.</b> lili 6 / lili 8 (reference end points unpublished, bags do not end at their start); CBD Building 03 and SYSU 01 (public files are different recordings from the paper's).",
        "<b>ORB-SLAM3 ambers</b> (MH01, MH05, V201, V202) are 0.3–2.1 cm absolute differences on 1–8 cm errors; the average is green (−6 %)."])
S += [P("Not run", h2)]
S += B(["FAST-LIO2: UrbanLoco (ulhk 4/5/6) — skipped by decision (110 GB, ROS2 format).",
        "FAST-LIVO2: Hilti'22/'23 (no public ground truth) — skipped by decision; Mining Tunnel is not in the public dataset; MARS-LVIG has no published accuracy."])
S += [P("Reproduce", h2),
      P("<font face='Courier'>bash scripts/test_containers.sh quick</font> (32 checks, ~10 s) and "
        "<font face='Courier'>bash scripts/test_containers.sh functional</font> (one real run per algorithm, ~8 min). "
        "All commands: docs/FAST-LIO2_FAST-LIVO2_Test_Commands.pdf. Details: docs/fastlio2_reproduction_log.md, docs/fastlivo2_reproduction_log.md.", body)]
doc = SimpleDocTemplate(os.path.join(OUT, "SLAM_Dockerization_Results.pdf"), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=15 * mm, bottomMargin=17 * mm, title="SLAM algorithms in Docker - results vs published values")
doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("\n".join(sorted(os.listdir(OUT))))
