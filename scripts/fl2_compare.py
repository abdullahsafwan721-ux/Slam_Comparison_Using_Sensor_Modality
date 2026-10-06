#!/usr/bin/env python3
"""Paper-vs-ours table for FAST-LIO2.    fl2_compare.py <summary.csv>

Paper values: FAST-LIO2 (1000 m) row -- the paper's default configuration --
of Table IV (ATE RMSE, m) and Table V (end-to-end error, m), Xu et al.,
"FAST-LIO2: Fast Direct LiDAR-Inertial Odometry", IEEE T-RO 2022 (arXiv 2107.06829).
Sequence names are matched on their prefix: liosam2_garden -> liosam 2, nclt9 -> nclt 9.
Deviation = (ours - paper) / paper; green < 15 %, amber 15-30 %, red > 30 %.
For the four '< 0.1 m' targets a percentage is meaningless: PASS if ours < 0.1 m.
lili (LiLi-OM KA-Urban): the paper's end-to-end error is against end locations
"registered from satellite images" (LiLi-OM paper, Sec. 5.3.2), which are not
published; the bags do NOT end at their start (GNSS: ~21 m apart on Schloss-1).
The first-to-last gap is therefore flagged as not comparable, and the GNSS proxy
(fl2_endref.py) is reported instead, with its metre-level limitation."""
import csv, re, statistics, sys

PAPER = {  # id: (metric, value_m, real sequence)   value None = '< 0.1 m'
    "liosam 2": ("end_to_end", None,  "garden"),
    "lili 6":   ("end_to_end", None,  "KA-URBAN-Schloss-1"),
    "ulhk 6":   ("end_to_end", None,  "HK-Data20190426-2"),
    "ulhk 5":   ("end_to_end", 0.39,  "HK-Data20190316-2"),
    "lili 7":   ("end_to_end", 1.63,  "KA-URBAN-Schloss-2"),
    "liosam 3": ("end_to_end", 9.50,  "campus"),
    "lili 8":   ("end_to_end", 17.39, "KA-URBAN-East"),
    "ulhk 4":   ("ape_rmse",   2.57,  "HK-Data20190117"),
    "liosam 1": ("ape_rmse",   4.58,  "park"),
    "nclt 9":   ("ape_rmse",   5.56,  "2013-01-10"),
    "nclt 7":   ("ape_rmse",   6.58,  "2012-06-15"),
    "nclt 5":   ("ape_rmse",   6.68,  "2012-04-29"),
    "nclt 4":   ("ape_rmse",   8.71,  "2012-01-15"),
    "nclt 10":  ("ape_rmse",   16.29, "2013-04-05"),
    "nclt 6":   ("ape_rmse",   20.96, "2012-05-11"),
    "nclt 8":   ("ape_rmse",   30.08, "2012-12-01"),
    "utbm 10":  ("ape_rmse",   16.80, "2019-04-18"),
    "utbm 8":   ("ape_rmse",   27.29, "2018-07-19"),
    "utbm 9":   ("ape_rmse",   51.60, "2019-01-31"),
}

# Independent re-run of FAST-LIO2 (ATE RMSE, m, full SE(3)-aligned) by Yuan et al.,
# "Semi-Elastic LiDAR-Inertial Odometry", arXiv 2307.07792, Table II, mapped to the
# FAST-LIO2 paper's ids via the session dates in their Table I. On every shared
# sequence it is 2-8x below the FAST-LIO2 paper's Table IV, i.e. the paper's own RMSE
# protocol (alignment) is not the standard full-trajectory Umeyama. Shown as a second
# reference; the paper column remains the primary target.
INDEP = {"nclt 5": 1.40, "nclt 6": 2.46, "nclt 7": 2.37, "nclt 8": 4.37, "nclt 9": 0.90,
         "utbm 8": 15.13, "utbm 9": 21.21, "utbm 10": 10.81, "ulhk 4": 1.20}

# A KA-Urban sequence counts as returning to its start when the bag's own GNSS puts
# the end within LOOP_TOL of the start (consumer GNSS is good to a few metres).
LOOP_TOL = 5.0

def band(dev):
    return "green" if abs(dev) < 0.15 else "amber" if abs(dev) <= 0.30 else "red"

def paper_id(seq):
    m = re.match(r"(liosam|lili|ulhk|nclt|utbm)(\d+)", seq)
    return "%s %s" % m.groups() if m else None

runs = {}
for r in csv.DictReader(open(sys.argv[1])):
    if r["value_m"] in ("", "NA"): continue
    runs.setdefault((r["sequence"], r["metric"]), []).append(float(r["value_m"]))

print("| Paper id | Sequence | Metric | Paper (1000 m) | Ours (median) | Runs | Spread | Deviation | Band | Independent [2307.07792] | Dev. vs independent |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for (seq, metric), v in sorted(runs.items(), key=lambda kv: list(PAPER).index(paper_id(kv[0][0])) if paper_id(kv[0][0]) in PAPER else 99):
    pid = paper_id(seq); med = statistics.median(v); spread = max(v) - min(v)
    if pid not in PAPER:
        print("| - | %s | %s | (not in paper) | %.3f | %d | %.3f | - | functional check |" % (seq, metric, med, len(v), spread)); continue
    pm, pv, _ = PAPER[pid]
    tgt = "< 0.1" if pv is None else "%.2f" % pv
    if metric == "end_ref_gnss" and pm == "end_to_end":
        print("| %s | %s | end point vs GNSS (proxy) | %s | %.3f | %d | %.3f | - | PROXY: reference end points unpublished, GNSS is metre-level |" % (pid, seq, tgt, med, len(v), spread)); continue
    if metric == "gnss_start_end": continue
    if pid.startswith("lili") and metric == "end_to_end":
        gap = runs.get((seq, "gnss_start_end"))
        gap = statistics.median(gap) if gap else None
        if gap is None or gap > LOOP_TOL:
            why = "GNSS start-end %.1f m" % gap if gap is not None else "no GNSS reference"
            print("| %s | %s | first-to-last gap | %s | %.3f | %d | %.3f | - | NOT COMPARABLE: %s, sequence does not return to its start |" % (pid, seq, tgt, med, len(v), spread, why)); continue
        if pv is None:
            print("| %s | %s | first-to-last gap | < 0.1 | %.3f | %d | %.3f | - | %s (GNSS start-end %.1f m) |" % (pid, seq, med, len(v), spread, "PASS" if med < 0.1 else "FAIL", gap)); continue
        dev = (med - pv) / pv
        print("| %s | %s | first-to-last gap | %.2f | %.3f | %d | %.3f | %+.1f %% | %s (GNSS start-end %.1f m) | - | - |" % (pid, seq, pv, med, len(v), spread, 100*dev, band(dev), gap)); continue
    if pm != metric:
        print("| %s | %s | %s | paper uses %s | %.3f | %d | %.3f | - | WRONG METRIC (missing gt_%s.tum?) |" % (pid, seq, metric, pm, med, len(v), spread, seq)); continue
    if pv is None:
        verdict = "PASS" if med < 0.1 else "FAIL"
        print("| %s | %s | %s | < 0.1 | %.3f | %d | %.3f | - | %s |" % (pid, seq, metric, med, len(v), spread, verdict)); continue
    dev = (med - pv) / pv
    ind = INDEP.get(pid)
    icol = ("%.2f | %+.1f %% (%s)" % (ind, 100*(med-ind)/ind, band((med-ind)/ind))) if ind else "- | -"
    print("| %s | %s | %s | %.2f | %.3f | %d | %.3f | %+.1f %% | %s | %s |" % (pid, seq, metric, pv, med, len(v), spread, 100*dev, band(dev), icol))
