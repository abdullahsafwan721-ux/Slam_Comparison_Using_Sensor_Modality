#!/usr/bin/env python3
"""Stage 3 verification checks (host, plain python3, project root). verify_stage3.sh calls:

    verify_stage3.py prepare <V>      copy ground truth + trajectories of every stored run to <V>/rescore
    verify_stage3.py compare <V>      re-scored results == stored results, run by run and cell by cell
    verify_stage3.py log <V>          every number of docs/stage3_log.md's 3a and 3b result tables
                                      against the RE-SCORED runs
    verify_stage3.py replay <V>       the scripted bag replayed again (<V>/replay_scripted, 1 run):
                                      FAST-LIO2 / FAST-LIVO2 bit-identical, ORB-SLAM3 within its spread
    verify_stage3.py gate <V>         the Stage 3 gate (guide 3.6 + D1, D3) on a NEW flight (<V>/px4)

Reads output/stage3 and docs/stage3_log.md; writes only under <V>. Exit code = number of FAILs.
"""
import csv
import filecmp
import json
import os
import re
import shutil
import statistics
import sys

S = "output/stage3"
ALL = ["fastlio2", "fastlivo2", "orbslam3", "orbslam3kf"]
GROUPS = {"scripted": "room", "px4": "room_square"}       # output dir -> condition name
RUNS = 3
NAMES = {"fastlio2": "FAST-LIO2", "fastlivo2": "FAST-LIVO2", "orbslam3": "ORB-SLAM3"}
FAILS = 0


def report(ok, text, warn=False):
    global FAILS
    tag = "PASS" if ok else ("WARN" if warn else "FAIL")
    FAILS += (not ok and not warn)
    print("  %s  %s" % (tag, text))


def extras(root, group, cond, algo, runs=RUNS):
    out = []
    for r in range(1, runs + 1):
        p = os.path.join(root, group, "eval", "%s__%s__r%d_extra.json" % (algo, cond, r))
        out.append(json.load(open(p)) if os.path.exists(p) else None)
    return out


def same(x, y):
    if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
        if x != x or y != y:
            return x != x and y != y
        return abs(x - y) <= 1e-9 * max(1.0, abs(x))
    return x == y


def prepare(V):
    R = os.path.join(V, "rescore")
    jobs = []
    for group, cond in GROUPS.items():
        for sub in ("gt", "eval", "fastlio2", "fastlivo2", "orbslam3"):
            os.makedirs(os.path.join(R, group, sub), exist_ok=True)
        shutil.copy2(os.path.join(S, group, "gt", cond + ".tum"), os.path.join(R, group, "gt"))
        for a in ALL:
            d = "orbslam3" if a.startswith("orbslam3") else a
            for r in range(1, RUNS + 1):
                b = "%s__%s__r%d" % (a, cond, r)
                c = b.replace("orbslam3kf__", "orbslam3__")
                for f in (b + ".tum", c + ".cost.csv", b + ".latency.csv"):
                    p = os.path.join(S, group, d, f)
                    if os.path.exists(p):
                        shutil.copy2(p, os.path.join(R, group, d))
                inside = lambda f: "/" + os.path.join(R, group, d, f)
                jobs.append(" ".join(["/" + os.path.join(R, group, "gt", cond + ".tum"), inside(b + ".tum"),
                                      "/" + os.path.join(R, group, "eval", b), "0.25",
                                      inside(c + ".cost.csv"), inside(b + ".latency.csv")]))
    open(os.path.join(V, "jobs.txt"), "w").write("\n".join(jobs) + "\n")
    print("  ----  copied %d stored runs (ground truth + trajectories + cost/latency logs) to %s" % (len(jobs), R))


def compare(V):
    R = os.path.join(V, "rescore")
    for group, cond in GROUPS.items():
        n = diff = 0
        bad = []
        for a in ALL:
            for r, (old, new) in enumerate(zip(extras(S, group, cond, a), extras(R, group, cond, a)), 1):
                n += 1
                if old is None or new is None:
                    bad.append("%s r%d: missing" % (a, r)); diff += 1; continue
                d = [k for k in (set(old) | set(new)) - {"gt", "est"} if not same(old.get(k), new.get(k))]
                if d:
                    diff += 1
                    bad.append("%s r%d: %s" % (a, r, ", ".join("%s %s -> %s" % (k, old.get(k), new.get(k)) for k in sorted(d)[:4])))
        cells = cdiff = 0
        for t in ("summary.csv", "summary_extra.csv"):
            A = sorted(csv.reader(open(os.path.join(S, group, "eval", t))))
            pb = os.path.join(R, group, "eval", t)
            B = sorted(csv.reader(open(pb))) if os.path.exists(pb) else []
            for ra, rb in zip(A, B):
                for x, y in zip(ra, rb):
                    cells += 1
                    cdiff += x != y
            cdiff += abs(len(A) - len(B))
        report(diff == 0 and cdiff == 0 and cells > 0,
               "%-9s %2d stored runs re-scored from scratch, %d differ; summary tables %d cells, %d differ" % (group, n, diff, cells, cdiff))
        for b in bad[:6]:
            print("          " + b)


COLS = [("APE whole bag", "ape_rmse"), ("APE motion window", "ape_air_rmse"), ("APE flight", "ape_air_rmse"),
        ("horiz", "ape_air_h_rmse"), ("vert", "ape_air_v_rmse"), ("Max error after landing", "post_landing_max"),
        ("Yaw", "yaw_rmse_deg"), ("Drift", "drift_pct"), ("TSR", "tsr"), ("Window cov", "coverage_air"),
        ("Flight cov", "coverage_air"), ("Bag cov", "coverage_bag"), ("Start-up", "startup_s"),
        ("CPU", "cpu_mean_pct"), ("RAM", "rss_peak_mb"), ("Pose age p95", "latency_p95_ms")]
ROWS = {"FAST-LIO2": "fastlio2", "FAST-LIVO2": "fastlivo2", "ORB-SLAM3 (frames)": "orbslam3",
        "ORB-SLAM3 (keyframes)": "orbslam3kf"}


def close(shown, value):
    d = len(shown.split(".")[1]) if "." in shown else 0
    return value is not None and abs(value - float(shown)) <= 0.5 * 10 ** -d + 1e-9


def check_log(V):
    R = os.path.join(V, "rescore")
    summ = {}
    for group in GROUPS:
        for r in csv.DictReader(open(os.path.join(R, group, "eval", "summary_extra.csv"))):
            summ[(group, r["algorithm"])] = r
    group = None
    cols = None
    checked = bad = 0
    for ln in open("docs/stage3_log.md").read().splitlines():
        if ln.startswith("## "):
            group = "scripted" if ln.startswith("## 3a") else "px4" if ln.startswith("## 3b") else None
            cols = None
            continue
        if group is None or not ln.startswith("|") or ln.startswith("|---"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if cells[0] == "Algorithm":
            cols = [next((k for h, k in COLS if c.startswith(h)), None) for c in cells]
            continue
        if cols is None or cells[0] not in ROWS:
            continue
        algo = ROWS[cells[0]]
        row = summ.get((group, algo))
        for c, k in zip(cells[1:], cols[1:]):
            if k is None or not re.fullmatch(r"-?\d+(\.\d+)?", c):
                continue                                       # "--", empty, "12.9 (tracking time)"
            try:
                v = float(row[k]) if row and row.get(k) not in (None, "") else None
            except ValueError:
                v = None
            checked += 1
            if not close(c, v):
                bad += 1
                print("          %s %s %s: log %s, data %s" % (group, algo, k, c, v))
    report(checked > 0 and bad == 0, "docs/stage3_log.md 3a + 3b tables: %d numbers checked against the re-scored runs, %d differ" % (checked, bad))


def replay(V):
    P = os.path.join(V, "replay_scripted")
    cond = GROUPS["scripted"]
    for a in ("fastlio2", "fastlivo2"):
        new = os.path.join(P, a, "%s__%s__r1.tum" % (a, cond))
        olds = [os.path.join(S, "scripted", a, "%s__%s__r%d.tum" % (a, cond, r)) for r in range(1, RUNS + 1)]
        pn = os.path.join(P, "eval", "%s__%s__r1_extra.json" % (a, cond))
        e_new = json.load(open(pn)) if os.path.exists(pn) else None
        e_old = extras(S, "scripted", cond, a)
        ident = os.path.exists(new) and all(filecmp.cmp(new, o, shallow=False) for o in olds if os.path.exists(o))
        ape_new = e_new and e_new.get("ape_rmse")
        ape_old = [e["ape_rmse"] for e in e_old if e]
        txt = "%-10s replay trajectory %s the stored 3 runs (APE whole bag new %s m, stored %s)" % (
            NAMES[a], "bit-identical to" if ident else "differs from", "%.5f" % ape_new if ape_new else "-",
            "/".join("%.5f" % x for x in ape_old))
        if a == "fastlio2" or ident:          # FAST-LIO2 is bit-deterministic (checked on every stored set)
            report(ident, txt)
        else:                                 # FAST-LIVO2 is not: single poses differ between runs (up to 1.9 cm on
            tol = max(2e-4, 0.03 * statistics.median(ape_old))   # this bag), its APE only in the 4th decimal
            ok = ape_new is not None and min(ape_old) - tol <= ape_new <= max(ape_old) + tol
            report(ok, txt + "; not bit-deterministic, APE within %.1e m of the stored runs' range" % tol)
    pn = os.path.join(P, "eval", "orbslam3__%s__r1_extra.json" % cond)
    e_new = json.load(open(pn)) if os.path.exists(pn) else None
    old = [e["ape_rmse"] for e in extras(S, "scripted", cond, "orbslam3") if e]
    ok = e_new is not None and not e_new.get("failed") and old and e_new["ape_rmse"] <= 2 * max(old)
    report(ok, "ORB-SLAM3  replay APE whole bag %s m; stored runs %s m (it is not deterministic: within 2x of the worst)" % (
        "%.4f" % e_new["ape_rmse"] if e_new and "ape_rmse" in e_new else "-", "/".join("%.4f" % x for x in old)))


def gate(V):
    P = os.path.join(V, "px4", "eval", "summary_extra.csv")
    if not os.path.exists(P):
        report(False, "no %s" % P)
        return
    new = {r["algorithm"]: r for r in csv.DictReader(open(P))}
    old = {r["algorithm"]: r for r in csv.DictReader(open(os.path.join(S, "px4", "eval", "summary_extra.csv")))}
    print("  %-11s %-26s %-26s %s" % ("", "flight APE (cm) new | stored", "flight coverage new | stored", "runs / failed"))
    apes = []
    for a in ("fastlio2", "fastlivo2", "orbslam3"):
        n, o = new.get(a), old.get(a)
        if n is None:
            report(False, "%s missing from the new flight's summary" % NAMES[a]); continue
        ape = float(n["ape_air_rmse"]); cov = float(n["coverage_air"]); apes.append(ape)
        print("  %-11s %10.2f | %-13.2f %10.3f | %-13.3f %s / %s" % (NAMES[a], ape * 100, float(o["ape_air_rmse"]) * 100,
                                                                    cov, float(o["coverage_air"]), n["runs"], n["failed_runs"]))
        report(n["runs"] == "3" and n["failed_runs"] == "0", "%s: 3 runs, none failed" % NAMES[a])
        report(cov >= 0.95, "%s: flight-window coverage %.3f >= 0.95 in the worst run (D1)" % (NAMES[a], cov))
        report(ape < 0.05, "%s: flight APE %.2f cm, centimetres in the room (D3)" % (NAMES[a], ape * 100))
    if len(apes) == 3:
        report(max(apes) / min(apes) < 10, "no method an order of magnitude worse than another (max/min %.1f)" % (max(apes) / min(apes)))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    V = sys.argv[2] if len(sys.argv) > 2 else "output/final_verification/stage3"
    {"prepare": prepare, "compare": compare, "log": check_log, "replay": replay, "gate": gate}[cmd](V)
    sys.exit(FAILS)
