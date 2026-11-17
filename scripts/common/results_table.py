#!/usr/bin/env python3
"""Aggregate every evo result under a directory into one table.

    python3 results_table.py <dir> [out-prefix]

Parses <algo>__<condition>__r<run>_ape.zip / _rpe.zip (see eval_traj.sh),
reads stats.json inside each zip, and reports the MEDIAN over runs -- the
statistic the ORB-SLAM3 paper uses, and robust to one bad run.
Writes <out-prefix>.csv and <out-prefix>.md (defaults to <dir>/summary).
"Worst coverage" < ~0.95 means at least one run lost track: its APE is then
measured over only part of the flight and must not be compared at face value.

Stage 3 addition (not in the guide): if metrics_extra.py wrote <run>_extra.json files,
a second table <out-prefix>_extra.csv/.md aggregates them (medians over runs, worst
case for coverage and TSR). The original summary.csv/.md is unchanged.
"""
import collections
import glob
import json
import os
import re
import statistics
import sys
import zipfile

PAT = re.compile(r"(?P<algo>[^/]+?)__(?P<cond>.+?)__r(?P<run>\d+)_(?P<kind>ape|rpe)\.zip$")


def rmse(path):
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read("stats.json"))["rmse"]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "summary")
    data = collections.defaultdict(list)
    cov = collections.defaultdict(list)
    for f in glob.glob(os.path.join(root, "**", "*_??e.zip"), recursive=True):
        m = PAT.search(os.path.basename(f))
        if m:
            data[(m["cond"], m["algo"], m["kind"])].append(rmse(f))
            c = f[:-len("_ape.zip")] + "_coverage.txt"
            if m["kind"] == "ape" and os.path.exists(c):
                cov[(m["cond"], m["algo"])].append(float(open(c).read()))
    if not data:
        sys.exit("no <algo>__<cond>__r<N>_ape.zip files under " + root)
    conds = sorted({k[0] for k in data})
    algos = sorted({k[1] for k in data})
    rows = []
    for c in conds:
        for a in algos:
            ape, rpe = data.get((c, a, "ape"), []), data.get((c, a, "rpe"), [])
            if ape or rpe:
                rows.append((c, a, len(ape),
                             statistics.median(ape) if ape else float("nan"),
                             (max(ape) - min(ape)) if len(ape) > 1 else 0.0,
                             statistics.median(rpe) if rpe else float("nan"),
                             min(cov[(c, a)]) if cov[(c, a)] else float("nan")))
    with open(out + ".csv", "w") as f:
        f.write("condition,algorithm,runs,ape_rmse_median_m,ape_spread_m,rpe_rmse_median_m,worst_coverage\n")
        f.writelines("%s,%s,%d,%.4f,%.4f,%.4f,%.3f\n" % r for r in rows)
    with open(out + ".md", "w") as f:
        f.write("| Condition | Algorithm | Runs | APE RMSE (m, median) | APE spread (m) | RPE/1 m (m, median) | Worst coverage |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        f.writelines("| %s | %s | %d | %.4f | %.4f | %.4f | %.3f |\n" % r for r in rows)
    print(open(out + ".md").read())
    print("wrote %s.csv and %s.md" % (out, out))
    extra_table(root, out)


# (column, header, format, aggregate) -- aggregate over runs: median, or min for the
# "did every run track" metrics, or max for start-up time
EXTRA = [
    ("ape_rmse", "APE whole bag (m)", "%.4f", "median"),
    ("ape_air_rmse", "APE flight (m)", "%.4f", "median"),
    ("ape_air_h_rmse", "APE flight horiz. (m)", "%.4f", "median"),
    ("ape_air_v_rmse", "APE flight vert. (m)", "%.4f", "median"),
    ("post_landing_max", "Max error after landing (m)", "%.3f", "max"),
    ("yaw_rmse_deg", "Yaw RMSE (deg)", "%.2f", "median"),
    ("drift_pct", "Drift (% of 10 m)", "%.2f", "median"),
    ("tsr", "TSR worst", "%.3f", "min"),
    ("tsr_start", "TSR start-aligned worst", "%.3f", "min"),
    ("coverage_air", "Flight coverage worst", "%.3f", "min"),
    ("coverage_bag", "Bag coverage worst", "%.3f", "min"),
    ("startup_s", "Start-up worst (s)", "%.1f", "max"),
    ("cpu_mean_pct", "CPU mean (% core)", "%.0f", "median"),
    ("rss_peak_mb", "Peak RAM (MB)", "%.0f", "median"),
    # age of a pose when it is published: publish clock minus the pose's own time stamp
    ("latency_p95_ms", "Pose age at publish p95 (ms)", "%.1f", "median"),
]
SPARSE = ("orbslam3kf",)     # keyframe-only trajectories: APE-type columns only
SPARSE_SKIP = ("tsr", "tsr_start", "coverage_air", "coverage_bag", "startup_s")


def extra_table(root, out):
    pat = re.compile(r"(?P<algo>[^/]+?)__(?P<cond>.+?)__r(?P<run>\d+)_extra\.json$")
    runs = collections.defaultdict(list)
    for f in glob.glob(os.path.join(root, "**", "*_extra.json"), recursive=True):
        m = pat.search(os.path.basename(f))
        if m:
            runs[(m["cond"], m["algo"])].append(json.load(open(f)))
    if not runs:
        return
    agg = {"median": statistics.median, "min": min, "max": max}
    rows = []
    for (c, a) in sorted(runs):
        rec = runs[(c, a)]
        vals = []
        for key, _, fmt, how in EXTRA:
            xs = [r[key] for r in rec if key in r and r[key] == r[key]]
            sparse_skip = a in SPARSE and key in SPARSE_SKIP
            vals.append(None if (not xs or sparse_skip) else agg[how](xs))
        rows.append((c, a, len(rec), sum(1 for r in rec if r.get("failed")), vals))
    with open(out + "_extra.csv", "w") as f:
        f.write("condition,algorithm,runs,failed_runs," + ",".join(k for k, *_ in EXTRA) + "\n")
        for c, a, n, nf, vals in rows:
            f.write("%s,%s,%d,%d,%s\n" % (c, a, n, nf, ",".join("" if v is None else repr(v) for v in vals)))
    with open(out + "_extra.md", "w") as f:
        f.write("| Condition | Algorithm | Runs | Failed | " + " | ".join(h for _, h, *_ in EXTRA) + " |\n")
        f.write("|---|---|---|---|" + "---|" * len(EXTRA) + "\n")
        for c, a, n, nf, vals in rows:
            f.write("| %s | %s | %d | %d | " % (c, a, n, nf) + " | ".join(
                "-" if v is None else fmt % v for v, (_, _, fmt, _) in zip(vals, EXTRA)) + " |\n")
    print(open(out + "_extra.md").read())
    print("wrote %s_extra.csv and %s_extra.md" % (out, out))


if __name__ == "__main__":
    main()
