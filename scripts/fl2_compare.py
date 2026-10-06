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

def paper_id(seq):
    m = re.match(r"(liosam|lili|ulhk|nclt|utbm)(\d+)", seq)
    return "%s %s" % m.groups() if m else None

runs = {}
for r in csv.DictReader(open(sys.argv[1])):
    if r["value_m"] in ("", "NA"): continue
    runs.setdefault((r["sequence"], r["metric"]), []).append(float(r["value_m"]))

print("| Paper id | Sequence | Metric | Paper (1000 m) | Ours (median) | Runs | Spread | Deviation | Band |")
print("|---|---|---|---|---|---|---|---|---|")
for (seq, metric), v in sorted(runs.items(), key=lambda kv: list(PAPER).index(paper_id(kv[0][0])) if paper_id(kv[0][0]) in PAPER else 99):
    pid = paper_id(seq); med = statistics.median(v); spread = max(v) - min(v)
    if pid not in PAPER:
        print("| - | %s | %s | (not in paper) | %.3f | %d | %.3f | - | functional check |" % (seq, metric, med, len(v), spread)); continue
    pm, pv, _ = PAPER[pid]
    tgt = "< 0.1" if pv is None else "%.2f" % pv
    if metric == "end_ref_gnss" and pm == "end_to_end":
        print("| %s | %s | end point vs GNSS (proxy) | %s | %.3f | %d | %.3f | - | PROXY: reference end points unpublished, GNSS is metre-level |" % (pid, seq, tgt, med, len(v), spread)); continue
    if pid.startswith("lili") and metric == "end_to_end":
        print("| %s | %s | first-to-last gap | %s | %.3f | %d | %.3f | - | NOT COMPARABLE: KA-Urban ends away from its start |" % (pid, seq, tgt, med, len(v), spread)); continue
    if pm != metric:
        print("| %s | %s | %s | paper uses %s | %.3f | %d | %.3f | - | WRONG METRIC (missing gt_%s.tum?) |" % (pid, seq, metric, pm, med, len(v), spread, seq)); continue
    if pv is None:
        band = "PASS" if med < 0.1 else "FAIL"
        print("| %s | %s | %s | < 0.1 | %.3f | %d | %.3f | - | %s |" % (pid, seq, metric, med, len(v), spread, band)); continue
    dev = (med - pv) / pv
    band = "green" if abs(dev) < 0.15 else "amber" if abs(dev) <= 0.30 else "red"
    print("| %s | %s | %s | %.2f | %.3f | %d | %.3f | %+.1f %% | %s |" % (pid, seq, metric, pv, med, len(v), spread, 100*dev, band))
