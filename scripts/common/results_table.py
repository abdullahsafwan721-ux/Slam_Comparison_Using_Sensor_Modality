#!/usr/bin/env python3
"""Aggregate every evo result under a directory into one table.

    python3 results_table.py <dir> [out-prefix]

Parses <algo>__<condition>__r<run>_ape.zip / _rpe.zip (see eval_traj.sh),
reads stats.json inside each zip, and reports the MEDIAN over runs -- the
statistic the ORB-SLAM3 paper uses, and robust to one bad run.
Writes <out-prefix>.csv and <out-prefix>.md (defaults to <dir>/summary).
"Worst coverage" < ~0.95 means at least one run lost track: its APE is then
measured over only part of the flight and must not be compared at face value.
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


if __name__ == "__main__":
    main()
