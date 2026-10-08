#!/usr/bin/env python3
"""Builds docs/FAST-LIO2_FAST-LIVO2_Test_Commands.pdf -- the command reference and test
procedures for the FAST-LIO2 and FAST-LIVO2 containers.   python3 docs/make_test_commands_pdf.py
Reference-result tables are read from docs/results/*.csv, so they always match the data."""
import csv, os, statistics, subprocess
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, Preformatted, KeepTogether)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(REPO, "docs", "FAST-LIO2_FAST-LIVO2_Test_Commands.pdf")
RES = os.path.join(REPO, "docs", "results")
GIT = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()

# ---------------------------------------------------------------- styles
ss = getSampleStyleSheet()
BLUE = colors.HexColor("#1e3a8a")
body = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.2, leading=12.6, spaceAfter=4)
small = ParagraphStyle("small", parent=body, fontSize=7.8, leading=10, textColor=colors.HexColor("#4b5563"))
cell = ParagraphStyle("cell", parent=body, fontSize=7.6, leading=9.4, spaceAfter=0)
cellc = ParagraphStyle("cellc", parent=cell, fontName="Courier", fontSize=7.1, leading=8.8)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")
h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, textColor=BLUE, spaceBefore=2, spaceAfter=6)
h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.2, textColor=BLUE, spaceBefore=8, spaceAfter=4)
code = ParagraphStyle("code", fontName="Courier", fontSize=7.0, leading=8.8, backColor=colors.HexColor("#f3f4f6"),
                      borderColor=colors.HexColor("#d1d5db"), borderWidth=0.5, borderPadding=5, spaceBefore=3, spaceAfter=8)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=2)
GREEN, AMBER, RED, GREY = (colors.HexColor(c) for c in ("#dcfce7", "#fef3c7", "#fee2e2", "#f3f4f6"))

def P(t, s=body): return Paragraph(t, s)
def C(t): return Preformatted(t.strip("\n"), code)
def B(items): return [Paragraph(i, bullet, bulletText="•") for i in items]
def T(rows, widths, mono_cols=(), extra=None, header=True):
    data = []
    for ri, r in enumerate(rows):
        data.append([c if not isinstance(c, str) else Paragraph(c, cellb if (header and ri == 0) else (cellc if ci in mono_cols else cell))
                     for ci, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
          ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if header: st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")))
    for i in range(1 if header else 0, len(rows)):
        if i % 2 == 0: st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f9fafb")))
    if extra: st += extra
    t.setStyle(TableStyle(st)); return t

def on_page(c, doc):
    c.saveState(); c.setFont("Helvetica", 7.3); c.setFillColor(colors.HexColor("#6b7280"))
    c.drawString(18 * mm, 10 * mm, "FAST-LIO2 / FAST-LIVO2 containers - test & command reference (2026-10-08, git %s)" % GIT)
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, "Page %d" % doc.page); c.restoreState()

def median_rows(fn, metric):
    runs = {}
    for r in csv.DictReader(open(os.path.join(RES, fn))):
        if r["metric"] == metric and r["value_m"] not in ("", "NA"):
            runs.setdefault(r["sequence"], []).append(float(r["value_m"]))
    return {k: (statistics.median(v), len(v), max(v) - min(v)) for k, v in runs.items()}

def band(d): return GREEN if abs(d) < .15 else AMBER if abs(d) <= .30 else RED

S = []
# ============================================================ cover
S += [Spacer(1, 22 * mm),
      P("FAST-LIO2 &amp; FAST-LIVO2 Docker Containers", ParagraphStyle("t", parent=h1, fontSize=22, leading=27)),
      P("Test procedures and complete command reference", ParagraphStyle("st", parent=body, fontSize=13, leading=17, textColor=colors.HexColor("#374151"))),
      Spacer(1, 6 * mm),
      T([["Item", "Value"],
         ["Repository", "SLAM_Comparison_Sensor_Modality (git %s)" % GIT],
         ["Images", "evtol/base:noetic, evtol/fastlio2:v1, evtol/fastlivo2:v1, evtol/eval:v1"],
         ["Upstream pins", "FAST_LIO 7cc4175, Livox-SDK v2.3.1, livox_ros_driver v2.6.0; FAST-LIVO2 0d2c034, Sophus a621ff, rpg_vikit 6c886c8; evo 1.31.1"],
         ["Host", "Ubuntu 24.04, Docker + Compose; GPU only for RViz (all algorithms are CPU-only)"],
         ["Companion documents", "docs/fastlio2_reproduction_log.md, docs/fastlivo2_reproduction_log.md, docs/results/"]],
        [38 * mm, 136 * mm]),
      Spacer(1, 6 * mm),
      P("<b>How to use this document.</b> Every command is meant to be run from the repository root on the host "
        "(<font face='Courier'>cd ~/Documents/safwan/SLAM/SLAM_Comparison_Sensor_Modality</font>). Section 1 tests both "
        "containers in two commands. Sections 2-3 cover layout and building. Section 4 explains the test suite. "
        "Sections 5 and 6 list every command for FAST-LIO2 and FAST-LIVO2 (inspect, run, ground truth, evaluate, full "
        "benchmark). Section 7 covers long unattended jobs, Section 8 troubleshooting, Section 9 the reference results "
        "a correct setup must reproduce.", body),
      P("<b>Conventions.</b> <font face='Courier'>docker compose run --rm -T SERVICE ...</font> runs one command in a fresh "
        "container (<font face='Courier'>-T</font>: no TTY, safe in scripts; drop it for an interactive shell). Inside "
        "containers the repository folders are mounted as <font face='Courier'>/data</font> (read-only), "
        "<font face='Courier'>/config</font> (ro), <font face='Courier'>/scripts</font> (ro) and "
        "<font face='Courier'>/output</font> (read-write). Use <font face='Courier'>bash -c</font> with explicit "
        "<font face='Courier'>source</font> lines -- <font face='Courier'>bash -lc</font> does not read .bashrc, so ROS "
        "would not be sourced.", body),
      PageBreak()]

# ============================================================ 1 quick start
S += [P("1. Quick start: test both containers", h1),
      C("""
cd ~/Documents/safwan/SLAM/SLAM_Comparison_Sensor_Modality
bash scripts/test_containers.sh quick        # ~10 s : images, pins, tools, evaluation chain (32 checks)
bash scripts/test_containers.sh functional   # ~8 min: one real run per algorithm (3 checks)
bash scripts/test_containers.sh all          # both
"""),
      P("Expected end of output (exit code = number of failures, 0 when everything is right):", body),
      C("""
== 32 passed, 0 failed, 0 skipped                                   (quick)
  PASS  fastlio2 LIO-SAM garden end-to-end (m; paper < 0.1) = 0.027 (expected 0.027 +/- 0.02)
  PASS  fastlivo2 HKU Landmark end-to-end (m; paper < 0.01) = 0.005 (expected 0.006 +/- 0.003)
  PASS  fastlivo2 NTU eee_02 matched-start ATE (m; repo 0.0211) = 0.022883
                                                           (expected 0.0229 +/- 0.002)
== 3 passed, 0 failed, 0 skipped                                    (functional)
"""),
      P("A <b>SKIP</b> means the data for that check is not on disk (e.g. on a fresh clone); it is not an error. "
        "Functional-test outputs go to <font face='Courier'>output/tests/</font> and never touch the benchmark folders. "
        "For long jobs use <font face='Courier'>systemd-run</font> (Section 7) so that closing the terminal cannot kill them:", body),
      C("""
mkdir -p output/tests
systemd-run --user --unit=test-functional --collect --working-directory="$PWD" \\
    -p StandardOutput=file:$PWD/output/tests/functional.log bash scripts/test_containers.sh functional
tail -f output/tests/functional.log
"""),
      PageBreak()]

# ============================================================ 2 layout
S += [P("2. Repository and output layout", h1),
      T([["Path (host)", "In container", "Contents"],
         ["docker/", "-", "base / fastlio2 / fastlivo2 / eval Dockerfiles"],
         ["config/fastlio2/", "/config/fastlio2", "lili, liosam_park_garden, liosam_campus, nclt, utbm (+ utbm_convert.launch), ulhk, avia"],
         ["config/fastlivo2/", "/config/fastlivo2", "NTU_VIRAL + camera_NTU_VIRAL; avia_private_g1..g4 + camera_private_g1..g4 (+ _paperdefault); shipped avia, HILTI22"],
         ["scripts/", "/scripts", "runners, ground-truth tools, evaluation, orchestrators, test suite"],
         ["data/", "/data (ro)", "lili, liosam, utbm, nclt (+ nclt_gt), ntu_viral (+ viral_eval, reference), fastlivo2_private, euroc"],
         ["output/fastlio2/", "/output/fastlio2", "FAST-LIO2 runs: &lt;seq&gt;_r&lt;N&gt;.bag/.tum/.algo.log/.params.yaml, gt_*.tum, benchmark.log"],
         ["output/fastlivo2/", "/output/fastlivo2", "FAST-LIVO2 standard runs: &lt;seq&gt;_r&lt;N&gt;.txt (TUM), _prism.tum, gt_*.tum, benchmark.log"],
         ["output/fastlivo2_matched/", "same", "FAST-LIVO2 NTU-VIRAL matched-start runs"],
         ["output/orbslam3/", "same", "trajectories/ and evaluation/ (ORB-SLAM3)"],
         ["output/results/", "same", "fastlio2_final, fastlivo2_standard_final, fastlivo2_matched_final; history/ = earlier evaluations"],
         ["output/diagnostics/", "same", "smoke tests, config variants, build experiments (see output/README.md)"],
         ["output/tests/", "same", "test_containers.sh functional runs"],
         ["docs/results/", "-", "committed final tables + per-run CSVs for all three algorithms"]],
        [40 * mm, 34 * mm, 100 * mm], mono_cols=(0, 1)),
      P("Raw outputs in <font face='Courier'>output/</font> are git-ignored (bags are large); "
        "<font face='Courier'>output/README.md</font> (copy: <font face='Courier'>docs/results/OUTPUT_LAYOUT.md</font>) "
        "says which script produced each folder. Files written by containers belong to root; hand them back with:", body),
      C('docker run --rm -v "$PWD/output:/o" evtol/eval:v1 chown -R $(id -u):$(id -g) /o'),
      PageBreak()]

# ============================================================ 3 build
S += [P("3. Building and checking the images", h1),
      C("""
bash scripts/verify_host.sh                       # docker, compose, GPU, X socket
# Ubuntu 20.04 + ROS Noetic: the FROM of the other three images
docker build -t evtol/base:noetic  -f docker/base.Dockerfile .
docker build -t evtol/fastlio2:v1  -f docker/fastlio2.Dockerfile .
docker build -t evtol/fastlivo2:v1 -f docker/fastlivo2.Dockerfile .
docker build -t evtol/eval:v1      -f docker/eval.Dockerfile .
# the same through compose (the base image must exist first)
docker compose build fastlio2 fastlivo2 eval
# FAST-LIVO2 for another CPU target (needs AVX2; default skylake = the paper's i7-10700K class)
docker build --build-arg CPU_ARCH=haswell -t evtol/fastlivo2:v1 \\
    -f docker/fastlivo2.Dockerfile .
"""),
      P("<b>Why FAST-LIVO2 is not built with -march=native.</b> Upstream hard-codes it; on an AVX-512 host the native "
        "binary diverged on NTU-VIRAL sbs_02 in 5/5 runs (1.1-308 m). Sophus, vikit and FAST-LIVO2 are therefore all "
        "built for one explicit target (build arg <font face='Courier'>CPU_ARCH</font>), which also makes the image portable.", body),
      P("3.1 Manual self-tests (what the quick suite automates)", h2),
      C("""
docker compose run --rm -T fastlio2 bash -c '
  source /opt/ros/noetic/setup.bash; source /ws/devel/setup.bash
  test -f /ws/devel/lib/fast_lio/fastlio_mapping && echo "fastlio_mapping OK"
  rospack find velodyne_pointcloud >/dev/null && echo "velodyne_pointcloud OK"
  rospack find nmea_navsat_driver  >/dev/null && echo "nmea_navsat_driver OK"
  cd /opt/Livox-SDK && git describe --tags; cd /ws/src/FAST_LIO && git rev-parse --short HEAD'

docker compose run --rm -T fastlivo2 bash -c '
  source /opt/ros/noetic/setup.bash; source /ws/devel/setup.bash
  test -f /ws/devel/lib/fast_livo/fastlivo_mapping && echo "fastlivo_mapping OK"
  test -f /usr/local/lib/libSophus.so && echo "Sophus OK"
  rospack find vikit_common >/dev/null && echo "vikit OK"
  cd /ws/src/FAST-LIVO2 && git rev-parse --short HEAD
  objdump -d /ws/devel/lib/liblio.so | grep -c zmm      # 0 = no AVX-512 code'

docker compose run --rm -T eval bash -c 'pip3 show evo | sed -n 1,2p'  # Version: 1.31.1
"""),
      PageBreak()]

# ============================================================ 4 test suite
S += [P("4. The test suite: scripts/test_containers.sh", h1),
      T([["Level", "Check", "Expected", "Proves"],
         ["L0 quick", "4 images present", "-", "build done"],
         ["L0 quick", "fastlio2: binary, velodyne_pointcloud, nmea_navsat_driver, Livox-SDK v2.3.1, driver fb5669b, FAST_LIO 7cc4175", "all present / pinned", "image = VERSIONS.md"],
         ["L0 quick", "fastlivo2: binary, Sophus, vikit, compressed plugin, FAST-LIVO2 0d2c034, zmm count", "present; zmm = 0", "Skylake build, no AVX-512"],
         ["L0 quick", "eval: evo version; helper scripts can import rosbag", "1.31.1; usage text", "evaluation stack"],
         ["L1 quick", "authors' shipped NTU-VIRAL trajectories re-scored (9)", "README values +/- 0.00015 m", "evo/alignment/prism chain = authors'"],
         ["L1 quick", "stored FAST-LIO2 runs re-scored: nclt9_r1, utbm8_r1, garden_r1", "0.954287 / 12.795859 / 0.027 m", "FAST-LIO2 evaluation reproducible"],
         ["L1 quick", "stored FAST-LIVO2 runs re-scored: eee_02_r1, hku_landmark_r1", "0.029931 / 0.004 m", "FAST-LIVO2 evaluation reproducible"],
         ["L2 functional", "FAST-LIO2, LIO-SAM garden, 1 new run", "0.027 +/- 0.02 m (paper &lt; 0.1)", "FAST-LIO2 container works end to end"],
         ["L2 functional", "FAST-LIVO2, HKU Landmark, 1 new run", "0.006 +/- 0.003 m (paper &lt; 0.01)", "LIVO2 + private calibration group"],
         ["L2 functional", "FAST-LIVO2, NTU eee_02 from 0.3 s, 1 new run", "0.0229 +/- 0.002 m (repo 0.0211)", "LIVO2 + NTU + prism + evo"]],
        [21 * mm, 70 * mm, 43 * mm, 40 * mm]),
      Spacer(1, 4),
      P("Tolerances: L1 values are deterministic re-evaluations of stored files (tight tolerance). L2 values come from new "
        "runs; FAST-LIO2/LIVO2 are multi-threaded, so the tolerance covers run-to-run spread observed over 5-10 runs.", small),
      PageBreak()]

# ============================================================ 5 FAST-LIO2
S += [P("5. FAST-LIO2 commands", h1),
      P("5.1 Shell and data inspection", h2),
      C("""
docker compose run --rm fastlio2 bash            # interactive; ROS + /ws sourced via .bashrc
docker compose run --rm -T fastlio2 bash -c \\
    "source /opt/ros/noetic/setup.bash; rosbag info /data/lili/KA_Urban_Schloss_1.bag"
# per-point time unit of a Velodyne cloud topic (must match timestamp_unit in the config)
docker compose run --rm -T eval python3 /scripts/fl2_cloudcheck.py \\
    /data/liosam/garden_dataset.bag /points_raw 20
"""),
      P("5.2 Paper sequences: name, config, bag, runner, reference", h2),
      T([["Paper id", "Seq name", "Config", "Bag (container path)", "Reference"],
         ["lili 6/7/8", "lili6_schloss1, lili7_schloss2, lili8_east", "lili.yaml", "/data/lili/KA_Urban_{Schloss_1,Schloss_2,East}.bag", "end-to-end; GNSS proxy gnssref_&lt;seq&gt;.tum"],
         ["liosam 2 / 3", "liosam2_garden, liosam3_campus", "liosam_park_garden / liosam_campus", "/data/liosam/{garden,campus_large}_dataset.bag", "end-to-end"],
         ["liosam 1", "liosam1_park", "liosam_park_garden.yaml", "/data/liosam/park_dataset.bag", "ATE vs /gps/fix"],
         ["utbm 8/9/10", "utbm8, utbm9, utbm10", "utbm.yaml (+ utbm_convert.launch)", "/data/utbm/utbm_{20180719,20190131,20190418}.bag", "ATE vs NMEA GGA (utbm_gt.sh)"],
         ["nclt 4..10", "nclt4 .. nclt10", "nclt.yaml", "/data/nclt/&lt;date&gt;.bag (convert first)", "ATE vs groundtruth_&lt;date&gt;.csv"]],
        [17 * mm, 37 * mm, 31 * mm, 55 * mm, 34 * mm], mono_cols=(1, 2, 3)),
      P("NCLT dates: nclt4 2012-01-15, nclt5 2012-04-29, nclt6 2012-05-11, nclt7 2012-06-15, nclt8 2012-12-01, "
        "nclt9 2013-01-10, nclt10 2013-04-05. ulhk (UrbanLoco) was not run.", small),
      P("5.3 Run", h2),
      C("""
# one run (the runner forces the paper parameters: point_filter_num 4, 0.5 m voxel, 1000 m map)
docker compose run --rm -T -e RUNS=1 fastlio2 bash /scripts/run_fastlio2.sh \\
    /config/fastlio2/lili.yaml /data/lili/KA_Urban_Schloss_1.bag lili6_schloss1
# five runs in five parallel containers (results identical to serial runs)
bash scripts/fl2_parallel.sh 5 run_fastlio2.sh \\
    /config/fastlio2/lili.yaml /data/lili/KA_Urban_Schloss_1.bag lili6_schloss1
# UTBM: raw Velodyne packets are converted in the same ROS graph
bash scripts/fl2_parallel.sh 5 run_fastlio2_utbm.sh /data/utbm/utbm_20180719.bag utbm8
# keep a test run out of the benchmark folder
docker compose run --rm -T -e OUTDIR=/output/tests/fastlio2 -e RUNS=1 fastlio2 \\
    bash /scripts/run_fastlio2.sh \\
    /config/fastlio2/liosam_park_garden.yaml /data/liosam/garden_dataset.bag liosam2_garden
"""),
      P("5.4 Ground truth and references", h2),
      C("""
# NCLT: the authors' converter on NCLT raw data (data/nclt mounted read-write), then the GT csv
docker compose run --rm -T -v "$PWD/data/nclt:/nclt" fastlio2 \\
    bash /scripts/nclt_to_bag.sh 2013-01-10
docker compose run --rm -T eval python3 /scripts/fl2_gt.py nclt \\
    /data/nclt_gt/groundtruth_2013-01-10.csv /output/fastlio2/gt_nclt9.tum
# UTBM: GGA sentences -> /fix bag -> TUM
docker compose run --rm -T fastlio2 bash /scripts/utbm_gt.sh /data/utbm/utbm_20180719.bag utbm8
docker compose run --rm -T eval python3 /scripts/fl2_gt.py bag \\
    /output/fastlio2/utbm8_fix.bag /fix /output/fastlio2/gt_utbm8.tum
# LIO-SAM park: GPS inside the bag
docker compose run --rm -T eval python3 /scripts/fl2_gt.py bag \\
    /data/liosam/park_dataset.bag /gps/fix /output/fastlio2/gt_liosam1_park.tum
# lili: the bag's GNSS as end-point reference (proxy; the true end points are unpublished)
docker compose run --rm -T eval python3 /scripts/fl2_gt.py bag \\
    /data/lili/KA_Urban_Schloss_1.bag /gnss /output/fastlio2/gnssref_lili6_schloss1.tum
"""),
      P("5.5 Evaluate", h2),
      C("""
# all runs -> output/results/fastlio2_<time>/
docker compose run --rm -T eval bash /scripts/eval_fastlio2.sh
# another run folder, own results folder
docker compose run --rm -T eval bash -c \\
    'IN=/output/tests/fastlio2 RESULTS=/output/results/test_fl2 bash /scripts/eval_fastlio2.sh'
# single steps
mkdir -p output/tests
docker compose run --rm -T eval python3 /scripts/fl2_traj.py \\
    /output/fastlio2/nclt9_r1.bag /Odometry /output/tests/nclt9_r1.tum
docker compose run --rm -T eval evo_ape tum \\
    /output/fastlio2/gt_nclt9.tum /output/fastlio2/nclt9_r1.tum --align --t_max_diff 0.02
# end-to-end drift; GNSS end-point proxy; paper comparison table
docker compose run --rm -T eval python3 /scripts/fl2_drift.py \\
    /output/fastlio2/liosam2_garden_r1.tum
docker compose run --rm -T eval python3 /scripts/fl2_endref.py \\
    /output/fastlio2/lili6_schloss1_r1.tum /output/fastlio2/gnssref_lili6_schloss1.tum
docker compose run --rm -T eval python3 /scripts/fl2_compare.py \\
    /output/results/fastlio2_final/summary.csv
"""),
      P("5.6 Whole benchmark, unattended", h2),
      C("""
systemd-run --user --unit=fl2-bench --collect --working-directory="$PWD" \\
    bash scripts/fl2_benchmark.sh
# a subset, data already on disk only
systemd-run --user --unit=fl2-sub --collect --working-directory="$PWD" \\
    --setenv=ONLY="nclt9 utbm8" --setenv=WAIT=0 bash scripts/fl2_benchmark.sh
tail -f output/fastlio2/benchmark.log
"""),
      PageBreak()]

# ============================================================ 6 FAST-LIVO2
S += [P("6. FAST-LIVO2 commands", h1),
      P("6.1 Shell and the evaluation gate", h2),
      C("""
docker compose run --rm fastlivo2 bash            # interactive
# gate: the authors' own shipped NTU-VIRAL results must re-score to their README (2.71 ... 3.11 cm)
docker compose run --rm -T eval bash -c 'cd /data/ntu_viral/reference
  for s in eee_01 eee_02 eee_03 nya_01 nya_02 nya_03 sbs_01 sbs_02 sbs_03; do
    printf "%s " $s
    evo_ape tum ${s}_gt.txt ${s}_prism.txt -a 2>/dev/null | awk "/^ *rmse/{print \\$2}"
  done'
"""),
      P("6.2 NTU-VIRAL", h2),
      C("""
# ground truth (Leica prism) for one sequence -- once
docker compose run --rm -T eval python3 /scripts/viral_prep.py gt \\
    /data/ntu_viral/viral_eval/result_eee_02/leica_pose.csv /output/fastlivo2/gt_eee_02.tum
# one run (standard protocol: the whole bag)
docker compose run --rm -T -e RUNS=1 fastlivo2 bash /scripts/run_fastlivo2.sh \\
    /config/fastlivo2/NTU_VIRAL.yaml /config/fastlivo2/camera_NTU_VIRAL.yaml \\
    /data/ntu_viral/eee_02/eee_02/eee_02.bag eee_02
# five runs in five parallel containers
SERVICE=fastlivo2 bash scripts/fl2_parallel.sh 5 run_fastlivo2.sh \\
    /config/fastlivo2/NTU_VIRAL.yaml /config/fastlivo2/camera_NTU_VIRAL.yaml \\
    /data/ntu_viral/eee_02/eee_02/eee_02.bag eee_02
# extra arguments go to rosbag play, e.g. start 0.3 s in (as the authors' run effectively did)
docker compose run --rm -T -e RUNS=1 -e OUTDIR=/output/tests/fastlivo2 fastlivo2 \\
    bash /scripts/run_fastlivo2.sh \\
    /config/fastlivo2/NTU_VIRAL.yaml /config/fastlivo2/camera_NTU_VIRAL.yaml \\
    /data/ntu_viral/eee_02/eee_02/eee_02.bag eee_02 -s 0.3
# all nine sequences (whatever is on disk), then the matched-start protocol
WAIT=0 bash scripts/livo2_benchmark.sh
bash scripts/livo2_ntu_matched.sh
# evaluate: prism transform + evo_ape -a (evo's default 0.01 s association window)
docker compose run --rm -T eval bash /scripts/eval_fastlivo2.sh
docker compose run --rm -T eval bash -c 'IN=/output/fastlivo2_matched \\
    RESULTS=/output/results/fastlivo2_matched_new bash /scripts/eval_fastlivo2.sh'
# completeness: flags runs that end before the authors' runs do
python3 scripts/livo2_check_complete.py output/fastlivo2
"""),
      P("6.3 Private dataset (calibration groups)", h2),
      T([["Group", "Configs", "Sequences (file names)"],
         ["g1", "avia_private_g1.yaml + camera_private_g1.yaml (= shipped avia/camera_pinhole)", "Retail_Street, CBD_Building_01, Bright_Screen_Wall"],
         ["g2", "avia_private_g2.yaml + camera_private_g2.yaml", "HKU_Landmark, HKU_Centennial_Garden_01/02, HKU_Main_Building, HKU_Cultural_Center_01/02, HKU_Lecture_Center_01/02, CBD_Building_02/03"],
         ["g3", "avia_private_g3.yaml + camera_private_g3.yaml", "HIT_Graffiti_Wall_01..04, SYSU_01, SYSU_02"],
         ["g4", "avia_private_g4.yaml + camera_private_g4.yaml", "Red_Sculpture"]],
        [12 * mm, 66 * mm, 96 * mm], mono_cols=(1, 2)),
      C("""
SERVICE=fastlivo2 bash scripts/fl2_parallel.sh 5 run_fastlivo2.sh \\
    /config/fastlivo2/avia_private_g2.yaml /config/fastlivo2/camera_private_g2.yaml \\
    /data/fastlivo2_private/HKU_Landmark.bag hku_landmark
# end-to-end drift of one run
docker compose run --rm -T eval python3 /scripts/fl2_drift.py \\
    /output/fastlivo2/hku_landmark_r1.txt
# paper Sec. IX-A defaults instead of the shipped config (diagnostic):
#   use avia_private_g<k>_paperdefault.yaml
# bags with compressed images only: add  -e REPUBLISH=/left_camera/image  (these bags are raw)
"""),
      P("6.4 Whole benchmark, unattended", h2),
      C("""
systemd-run --user --unit=livo2-bench --collect --working-directory="$PWD" \\
    bash scripts/livo2_benchmark.sh
tail -f output/fastlivo2/benchmark.log
"""),
      PageBreak()]

# ============================================================ 7 long jobs + 8 troubleshooting
S += [P("7. Long jobs, monitoring, stopping", h1),
      P("A run started from a terminal dies with the terminal (its whole process scope is killed, even with "
        "<font face='Courier'>nohup</font>/<font face='Courier'>setsid</font>). Start long jobs as systemd user units:", body),
      C("""
systemd-run --user --unit=NAME --collect --working-directory="$PWD" bash scripts/<script>.sh
systemctl --user list-units 'fl2-*' 'livo2-*' 'test-*'      # what is running
journalctl --user -u NAME -f                                # its output (if not redirected)
systemctl --user stop NAME                                  # stop it (run containers end with it)
docker ps                                                   # run containers currently active
"""),
      P("8. Troubleshooting", h1),
      T([["Symptom", "Cause", "Fix"],
         ["run never ends after the bag finished", "FAST-LIO hangs on sim time after SIGINT", "runners escalate SIGINT -> SIGKILL after 10 s (already built in)"],
         ["rospack: command not found", "bash -lc does not read .bashrc", "use bash -c with explicit source lines"],
         ["ModuleNotFoundError: rosbag (eval)", "eval venv python has no ROS", "helper scripts re-exec with system python automatically"],
         ["evo: found no matching timestamps", "estimate and GT in different time bases", "compare head -1 of both files"],
         ["FAST-LIVO2 trajectory ends early", "node lagged, queue not drained", "runner waits until poses stop; check with livo2_check_complete.py"],
         ["FAST-LIVO2 diverges (metres)", "-march=native AVX-512 build", "use the image (Skylake target); never mix -march between Sophus/vikit/LIVO2"],
         ["config refused by fl2_benchmark.sh", "per-point time unit mismatch", "fl2_cloudcheck.py on the topic; fix timestamp_unit"],
         ["files in output/ owned by root", "containers run as root", "chown via the eval container (Section 2)"],
         ["Google Drive 'Quota exceeded'", "anonymous download blocked", "signed-in session or a mirror"]],
        [52 * mm, 50 * mm, 72 * mm]),
      PageBreak()]

# ============================================================ 9 reference results
S += [P("9. Reference results a correct setup reproduces", h1),
      P("Medians of 5 runs from <font face='Courier'>docs/results/</font> (generated from the committed CSVs).", body),
      P("9.1 FAST-LIO2 (ATE RMSE or end-to-end, m)", h2)]
fl2_paper = {"nclt9": 5.56, "nclt7": 6.58, "nclt5": 6.68, "nclt4": 8.71, "nclt10": 16.29, "nclt6": 20.96, "nclt8": 30.08,
             "utbm10": 16.80, "utbm8": 27.29, "utbm9": 51.60, "liosam1_park": 4.58}
fl2_ind = {"nclt5": 1.40, "nclt6": 2.46, "nclt7": 2.37, "nclt8": 4.37, "nclt9": 0.90, "utbm8": 15.13, "utbm9": 21.21, "utbm10": 10.81}
ape = median_rows("fastlio2_summary.csv", "ape_rmse"); e2e = median_rows("fastlio2_summary.csv", "end_to_end")
rows = [["Sequence", "Metric", "Ours", "Paper", "Independent re-run", "Note"]]; extra = []
for s in ["liosam2_garden", "liosam3_campus"]:
    if s in e2e:
        p = {"liosam2_garden": "&lt; 0.1", "liosam3_campus": "9.50"}[s]
        rows.append([s, "end-to-end", "%.3f" % e2e[s][0], p, "-", "PASS" if s == "liosam2_garden" else "+7.5 %"])
for s in ["liosam1_park", "nclt4", "nclt5", "nclt6", "nclt7", "nclt8", "nclt9", "nclt10", "utbm8", "utbm9", "utbm10"]:
    if s in ape:
        m = ape[s][0]; ind = fl2_ind.get(s)
        rows.append([s, "ATE", "%.3f" % m, "%.2f" % fl2_paper[s], "%.2f" % ind if ind else "-",
                     ("%+.1f %% vs indep." % (100 * (m - ind) / ind)) if ind else "no independent value"])
        if ind: extra.append(("BACKGROUND", (5, len(rows) - 1), (5, len(rows) - 1), band((m - ind) / ind)))
for s in ["lili6_schloss1", "lili7_schloss2", "lili8_east"]:
    if s in e2e:
        rows.append([s, "first-to-last", "%.3f" % e2e[s][0], {"lili6_schloss1": "&lt; 0.1", "lili7_schloss2": "1.63", "lili8_east": "17.39"}[s], "-",
                     {"lili6_schloss1": "not comparable (ends 21 m away)", "lili7_schloss2": "red (genuine)", "lili8_east": "not comparable (ends 185 m away)"}[s]])
S += [T(rows, [30 * mm, 21 * mm, 16 * mm, 16 * mm, 27 * mm, 64 * mm], mono_cols=(0,), extra=extra),
      P("Paper RMSEs are systematically higher than full-trajectory SE(3) alignment gives; an independent re-run "
        "(arXiv 2307.07792) shows the same, hence its column.", small),
      P("9.2 FAST-LIVO2, NTU-VIRAL (ATE RMSE, m) vs the authors' repo results", h2)]
REPO_V = {"eee_01": .0271, "eee_02": .0211, "eee_03": .0261, "nya_01": .0356, "nya_02": .0339, "nya_03": .0352, "sbs_01": .0234, "sbs_02": .0283, "sbs_03": .0311}
std = median_rows("fastlivo2_standard_summary.csv", "ape_rmse"); mat = median_rows("fastlivo2_matched_summary.csv", "ape_rmse")
rows = [["Seq", "Repo", "Standard (whole bag)", "dev.", "Matched start", "dev."]]; extra = []
for s, r in REPO_V.items():
    a = std.get(s, (float("nan"),))[0]; b = mat.get(s, (float("nan"),))[0]
    rows.append([s, "%.4f" % r, "%.4f" % a, "%+.1f %%" % (100 * (a - r) / r), "%.4f" % b, "%+.1f %%" % (100 * (b - r) / r)])
    i = len(rows) - 1; extra += [("BACKGROUND", (3, i), (3, i), band((a - r) / r)), ("BACKGROUND", (5, i), (5, i), band((b - r) / r))]
S += [T(rows, [20 * mm, 20 * mm, 34 * mm, 22 * mm, 34 * mm, 22 * mm], mono_cols=(0,), extra=extra),
      P("9.3 FAST-LIVO2, private dataset (end-to-end, m; paper claim &lt; 0.01 m)", h2)]
pe = median_rows("fastlivo2_standard_summary.csv", "end_to_end")
note = {"hku_landmark": "PASS", "hku_cultural_center_02": "PASS (paper's 4:01 HKU Cultural Center)", "cbd_building_01": "FAIL (genuine, 0.1 % of path)",
        "cbd_building_03": "file 4:26 vs paper 5:01 (different cut)", "sysu_01": "file 2:14 vs paper 4:40 (different recording)",
        "hku_cultural_center_01": "not in the paper"}
rows = [["Sequence", "Ours", "Verdict"]]; extra = []
for s in ["hku_landmark", "hku_cultural_center_02", "cbd_building_01", "cbd_building_03", "sysu_01", "hku_cultural_center_01"]:
    if s in pe:
        rows.append([s, "%.3f" % pe[s][0], note[s]])
        if note[s].startswith("PASS"): extra.append(("BACKGROUND", (2, len(rows) - 1), (2, len(rows) - 1), GREEN))
        if note[s].startswith("FAIL"): extra.append(("BACKGROUND", (2, len(rows) - 1), (2, len(rows) - 1), RED))
S += [T(rows, [48 * mm, 18 * mm, 108 * mm], mono_cols=(0,), extra=extra)]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=17 * mm,
                        title="FAST-LIO2 & FAST-LIVO2 containers - test and command reference", author="SLAM_Comparison_Sensor_Modality")
doc.build(S, onFirstPage=on_page, onLaterPages=on_page)
print(OUT)
