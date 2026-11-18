#!/usr/bin/env python3
"""Stage 4 verification checks (host, plain python3, project root). verify_stage4.sh calls:

    verify_stage4.py flights              every flight recorded, cleared, gated; the hop flown
    verify_stage4.py matrix               every cell of the matrix has its runs and scores
    verify_stage4.py prepare <V>          copy ground truth + trajectories to <V>/rescore, write jobs
    verify_stage4.py compare <V>          re-scored results == stored results, run by run
    verify_stage4.py tables <V>           regenerated tables/figures == stored ones
    verify_stage4.py log <V>              every number in docs/stage4_log.md's result tables
                                          against the RE-SCORED runs (median of 3, as stated)
    verify_stage4.py replay <V>           live replay of the room flight against the stored runs

Reads output/stage4 and docs/stage4_log.md; writes only under <V>. Every check prints
PASS / FAIL / WARN; the exit code is the number of FAILs (0 = all passed).
"""
import csv
import glob
import json
import os
import re
import shutil
import statistics
import sys

S = "output/stage4"
ALL = ["fastlio2", "fastlivo2", "orbslam3", "orbslam3kf"]
CAM = ["cam_black_5s", "cam_dim30", "cam_dim10", "cam_dt5", "cam_dt10", "cam_dt20"]
LID = ["lidar_drop_2s", "lidar_drop_5s", "lidar_thin25"]
# group -> [(condition, [algorithms])], as run by run_matrix.sh and run_extras.sh
MATRIX = {
    "environments": [(c, ALL) for c in ["room", "room_plain", "corridor", "field"]],
    "altitude": [("urban_alt%d" % h, ALL) for h in (10, 20, 30, 40, 50, 60)],
    "speed": [("urban_speed%d" % v, ALL) for v in (2, 5, 8)],
    "imu": [("imu_x%d" % s, ALL) for s in (1, 3, 10, 30)],
    "faults": [("room_" + v, ["fastlivo2", "orbslam3", "orbslam3kf"]) for v in CAM]
              + [("room_" + v, ["fastlio2", "fastlivo2"]) for v in LID],
}
for _r in (2, 4, 8):
    MATRIX["headroom/rate%d" % _r] = [(c, ["fastlio2", "fastlivo2"]) for c in ["room", "urban_speed5"]]
RUNS = 3
# flight -> (cruise altitude m, hop expected in the mission log: deviation 12)
FLIGHTS = {"room": (1.5, False), "room_plain": (1.5, False), "corridor": (1.5, False), "field": (5, True)}
FLIGHTS.update({"urban_alt%d" % h: (h, True) for h in (10, 20, 30, 40, 50, 60)})
FLIGHTS.update({"urban_speed%d" % v: (20, True) for v in (2, 5, 8)})
NAMES = {"fastlio2": "FAST-LIO2", "fastlivo2": "FAST-LIVO2", "orbslam3": "ORB-SLAM3"}

FAILS = 0


def report(ok, text, warn=False):
    global FAILS
    tag = "PASS" if ok else ("WARN" if warn else "FAIL")
    if not ok and not warn:
        FAILS += 1
    print("  %s  %s" % (tag, text))


def tau(cond):
    """TSR threshold: 0.25 m indoors (room*, corridor), 1.0 m outdoors (plan H3)."""
    return 0.25 if cond.startswith(("room", "corridor")) else 1.0


def runs_of(root, group, cond, algo):
    return [os.path.join(root, group, algo if not algo.endswith("kf") else "orbslam3",
                         "%s__%s__r%d.tum" % (algo, cond, r)) for r in range(1, RUNS + 1)]


def extras(root, group, cond, algo):
    out = []
    for r in range(1, RUNS + 1):
        p = os.path.join(root, group, "eval", "%s__%s__r%d_extra.json" % (algo, cond, r))
        out.append(json.load(open(p)) if os.path.exists(p) else None)
    return out


# ---------------------------------------------------------------------------------------
def check_flights():
    for name, (alt, hop) in FLIGHTS.items():
        bag = os.path.join(S, "flights", name + ".bag")
        gate = os.path.join(S, "flights", name + ".gate.txt")
        if not os.path.exists(bag) or os.path.getsize(bag) == 0:
            report(False, "%-13s bag missing" % name)
            continue
        size = os.path.getsize(bag) / 1e9
        g = open(gate).read() if os.path.exists(gate) else ""
        gated = "ALL CHECKS PASSED" in g
        if name == "room":   # the Stage 3 gate flight, hard-linked (deviation 3)
            src = "output/stage3/flights/room_square"
            same = os.path.exists(src + ".bag") and os.path.samefile(bag, src + ".bag")
            clear = open(src + ".clearance.txt").read() if os.path.exists(src + ".clearance.txt") else ""
            mission = ""
            note = "the Stage 3 gate flight (same file: %s)" % ("yes" if same else "NO")
            gated = gated and same
        else:
            clear = open(os.path.join(S, "flights", name + ".clearance.txt")).read() \
                if os.path.exists(os.path.join(S, "flights", name + ".clearance.txt")) else ""
            mission = open(os.path.join(S, "flights", name + ".mission.log")).read() \
                if os.path.exists(os.path.join(S, "flights", name + ".mission.log")) else ""
            note = ""
        cleared = clear.startswith("CLEAR") or "\nCLEAR" in clear
        hop_ok = True
        if hop:
            m = re.search(r"hop ([\d.]+) m at ([\d.]+) s", mission)
            hop_ok = bool(m) and abs(float(m.group(1)) - 0.4) < 1e-6
            note = ("hop %s m at %s s after reaching cruise height" % m.groups()) if m else "NO hop in the mission log"
        report(gated and cleared and hop_ok, "%-13s %5.1f GB  clearance %s  sensor gate %s  %s" % (
            name, size, "CLEAR" if cleared else "MISSING", "PASSED" if gated else "FAILED", note))
    for v in CAM + LID:
        bag = os.path.join(S, "faults", "flights", "room_%s.bag" % v)
        meta = os.path.join(S, "faults", "flights", "room_%s.fault.json" % v)
        ok = os.path.exists(bag) and os.path.getsize(bag) > 0 and os.path.exists(meta)
        m = json.load(open(meta)) if os.path.exists(meta) else {}
        report(ok, "fault copy room_%-14s %s  (changed %s msgs, dropped %s; fault %.1f-%.1f s)" % (
            v, "present" if ok else "MISSING", m.get("changed"), m.get("dropped"),
            m.get("fault_start_s", 0), m.get("fault_end_s", 0)))


def check_matrix():
    total = failed_runs = 0
    for group, conds in MATRIX.items():
        for cond, algos in conds:
            done = os.path.exists(os.path.join(S, group, ".done_" + cond))
            line = []
            ok = done
            for a in algos:
                tums = runs_of(S, group, cond, a)
                ex = extras(S, group, cond, a)
                have = sum(os.path.exists(t) for t in tums)
                scored = sum(e is not None for e in ex)
                fail = sum(1 for e in ex if e and e.get("failed"))
                total += have
                failed_runs += fail
                ok = ok and have == RUNS and scored == RUNS
                if a != "orbslam3kf":
                    line.append("%s %d/%d%s" % (NAMES[a], scored, RUNS, " (%d failed)" % fail if fail else ""))
            report(ok, "%-15s %-18s %s%s" % (group, cond, ", ".join(line), "" if done else "  [no .done marker]"))
    print("  ----  %d trajectories in the matrix, %d of them failed runs (scored as failures, TSR 0)" % (
        total, failed_runs))


# ---------------------------------------------------------------------------------------
def prepare(V):
    """Copy what scoring needs (ground truth, trajectories, cost and latency logs) to
    <V>/rescore/<group>/ and write one scoring job per run. Nothing is read from eval/."""
    R = os.path.join(V, "rescore")
    jobs = []
    for group, conds in MATRIX.items():
        for sub in ("gt", "eval", "fastlio2", "fastlivo2", "orbslam3"):
            os.makedirs(os.path.join(R, group, sub), exist_ok=True)
        for cond, algos in conds:
            shutil.copy2(os.path.join(S, group, "gt", cond + ".tum"), os.path.join(R, group, "gt"))
            for a in algos:
                d = "orbslam3" if a.startswith("orbslam3") else a
                for r in range(1, RUNS + 1):
                    b = "%s__%s__r%d" % (a, cond, r)
                    c = b.replace("orbslam3kf__", "orbslam3__")          # kf cost = its orbslam3 run
                    for f in (b + ".tum", c + ".cost.csv", b + ".latency.csv"):
                        p = os.path.join(S, group, d, f)
                        if os.path.exists(p):
                            shutil.copy2(p, os.path.join(R, group, d))
                    inside = lambda f: "/" + os.path.join(R, group, d, f)    # container path
                    jobs.append(" ".join(["/" + os.path.join(R, group, "gt", cond + ".tum"), inside(b + ".tum"),
                                          "/" + os.path.join(R, group, "eval", b), str(tau(cond)),
                                          inside(c + ".cost.csv"), inside(b + ".latency.csv")]))
    # inputs of the tables and figures that are not scores
    os.makedirs(os.path.join(R, "faults", "flights"), exist_ok=True)
    for f in glob.glob(os.path.join(S, "faults", "flights", "*.fault.json")):
        shutil.copy2(f, os.path.join(R, "faults", "flights"))
    shutil.copy2(os.path.join(S, "altitude", "ground_points.csv"), os.path.join(R, "altitude"))
    open(os.path.join(V, "jobs.txt"), "w").write("\n".join(jobs) + "\n")
    print("  ----  copied %d runs (ground truth + trajectories + cost/latency logs) to %s" % (len(jobs), R))


def compare(V):
    R = os.path.join(V, "rescore")
    skip = {"gt", "est"}                                    # paths differ by construction
    for group, conds in MATRIX.items():
        n = diff = 0
        bad = []
        for cond, algos in conds:
            for a in algos:
                for r, (old, new) in enumerate(zip(extras(S, group, cond, a), extras(R, group, cond, a)), 1):
                    n += 1
                    if old is None or new is None:
                        bad.append("%s %s r%d: missing" % (a, cond, r)); diff += 1; continue
                    keys = (set(old) | set(new)) - skip
                    d = [k for k in keys if not same(old.get(k), new.get(k))]
                    if d:
                        diff += 1
                        bad.append("%s %s r%d: %s" % (a, cond, r, ", ".join(
                            "%s %s -> %s" % (k, old.get(k), new.get(k)) for k in sorted(d)[:4])))
        # the aggregated tables, cell by cell
        cells = cdiff = 0
        for t in ("summary.csv", "summary_extra.csv"):
            a_, b_ = os.path.join(S, group, "eval", t), os.path.join(R, group, "eval", t)
            A = list(csv.reader(open(a_))) if os.path.exists(a_) else []
            B = list(csv.reader(open(b_))) if os.path.exists(b_) else []
            A.sort(); B.sort()
            for ra, rb in zip(A, B):
                for x, y in zip(ra, rb):
                    cells += 1
                    cdiff += x != y
            cdiff += abs(len(A) - len(B))
        report(diff == 0 and cdiff == 0 and cells > 0,
               "%-15s %3d runs re-scored, %d differ; summary tables %d cells, %d differ" % (group, n, diff, cells, cdiff))
        for b in bad[:6]:
            print("          " + b)


def same(x, y):
    if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
        if x != x or y != y:                               # NaN (e.g. tsr_start of a kf trajectory)
            return x != x and y != y
        return abs(x - y) <= 1e-9 * max(1.0, abs(x))
    return x == y


def tables(V):
    R = os.path.join(V, "rescore")
    a, b = os.path.join(S, "stage4_tables.md"), os.path.join(R, "stage4_tables.md")
    A, B = open(a).read().splitlines(), open(b).read().splitlines() if os.path.exists(b) else []
    nd = sum(1 for x, y in zip(A, B) if x != y) + abs(len(A) - len(B))
    report(nd == 0, "stage4_tables.md regenerated from the re-scored runs: %d lines, %d differ" % (len(A), nd))
    if nd:
        for x, y in [(x, y) for x, y in zip(A, B) if x != y][:5]:
            print("          stored: %s\n          new:    %s" % (x[:150], y[:150]))
    import matplotlib.image as mpimg
    import numpy as np
    pngs = sorted(glob.glob(os.path.join(S, "fig_*.png")) + glob.glob(os.path.join(S, "figures", "*.png")))
    for p in pngs:
        q = os.path.join(R, os.path.relpath(p, S))
        if not os.path.exists(q):
            report(False, "%-28s not regenerated" % os.path.relpath(p, S)); continue
        x, y = mpimg.imread(p), mpimg.imread(q)
        eq = x.shape == y.shape and np.array_equal(x, y)
        frac = 0.0 if eq or x.shape != y.shape else float(np.mean(np.any(x != y, axis=-1)))
        report(eq, "%-28s regenerated, %s" % (os.path.relpath(p, S),
               "pixel-identical" if eq else "differs (%.3f%% of pixels; compare %s and %s)" % (100 * frac, p, q)),
               warn=not eq and frac < 0.001)


# ---------------------------------------------------------------------------------------
UNIT = {"cm": 1.0, "m": 100.0}
FAULT_ROWS = {"camera black 5 s": "cam_black_5s", "camera 30 % brightness": "cam_dim30",
              "camera 10 % brightness": "cam_dim10", "camera stamps +5 ms": "cam_dt5",
              "camera stamps +10 ms": "cam_dt10", "camera stamps +20 ms": "cam_dt20",
              "LiDAR gone 2 s": "lidar_drop_2s", "LiDAR gone 5 s": "lidar_drop_5s",
              "LiDAR 25 % of points": "lidar_thin25"}
SECTIONS = {  # heading prefix -> (group, row label -> condition)
    "### B. Altitude": ("altitude", lambda s: "urban_alt" + re.match(r"(\d+) m$", s).group(1)),
    "### C. Speed": ("speed", lambda s: "urban_speed" + re.match(r"(\d+) m/s$", s).group(1)),
    "### D. IMU": ("imu", lambda s: "imu_" + s.strip()),
    "### A. Environments (indoor)": ("environments", lambda s: s.split()[0]),
    "### E. Sensor faults": ("faults", lambda s: "room_" + FAULT_ROWS[s.strip()]),
}


def agg(R, group, cond, algo):
    ex = [e for e in extras(R, group, cond, algo) if e is not None]
    ok = [e for e in ex if not e.get("failed")]
    med = lambda k: statistics.median(e[k] for e in ok) if ok and all(k in e for e in ok) else None
    return {"runs": len(ex), "failed": len(ex) - len(ok), "ape_cm": med("ape_air_rmse") and med("ape_air_rmse") * 100,
            "h_cm": med("ape_air_h_rmse") and med("ape_air_h_rmse") * 100,
            "cov": min(e.get("coverage_air", 0) for e in ex) if ex else None,
            "tsr": min(e.get("tsr", 0) for e in ex) if ex else None,
            "drift": med("drift_pct"), "cpu": med("cpu_mean_pct"), "age": med("latency_p95_ms")}


def close(shown, value):
    """shown: the number as printed in the log; value: the data. Equal after rounding."""
    d = len(shown.split(".")[1]) if "." in shown else 0
    return value is not None and abs(value - float(shown)) <= 0.5 * 10 ** -d + 1e-9


def check_log(V):
    R = os.path.join(V, "rescore")
    text = open("docs/stage4_log.md").read()
    m = re.search(r"Numbers: flight-window APE RMSE \(D3\), (\w+) of 3 runs", text)
    report(bool(m) and m.group(1) == "median", "results statistic stated as '%s of 3 runs' (the tables use the median)"
           % (m.group(1) if m else "?"))
    lines = text.splitlines()
    sec = None
    cols = []
    checked = 0
    for ln in lines:
        if ln.startswith("#"):
            sec = next((k for k in SECTIONS if ln.startswith(k)), None)
            cols = []
            continue
        if sec is None or not ln.startswith("|") or ln.startswith("|---"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if not cols:                                      # header row: algorithm per column
            cols = [next((a for a, n in NAMES.items() if c.startswith(n)), None) for c in cells]
            continue
        group, rowmap = SECTIONS[sec]
        cond = rowmap(cells[0].replace("*", ""))
        for c, algo in zip(cells[1:], cols[1:]):
            if algo is None or "same data" in c:
                continue
            a = agg(R, group, cond, algo)
            plain = c.replace("*", "")
            where = "%s | %s | %s: \"%s\"" % (sec[4:].split("(")[0].strip(), cells[0], NAMES[algo], plain)
            checked += 1
            if re.search(r"never (starts|initialise|initializes)", plain):
                report(a["failed"] == a["runs"] == RUNS, "%s -> %d of %d runs failed" % (where, a["failed"], a["runs"]))
                continue
            errs = []
            v = re.search(r"([\d.]+) (cm|m)\b", plain)
            if v:
                x = a["ape_cm"] / UNIT[v.group(2)] if a["ape_cm"] is not None else None
                if not close(v.group(1), x):
                    errs.append("APE %s %s, data %s (horizontal %s)" % (
                        v.group(1), v.group(2), "%.3g" % x if x is not None else "-",
                        "%.3g" % (a["h_cm"] / UNIT[v.group(2)]) if a["h_cm"] else "-"))
            if "diverges" in plain and not (a["ape_cm"] or 0) > 100:
                errs.append("'diverges' but APE %.2f cm" % (a["ape_cm"] or 0))
            cv = re.search(r"coverage (\d\.\d+)|\((\d\.\d+)\)", plain)
            if cv:
                s = cv.group(1) or cv.group(2)
                if not close(s, a["cov"]):
                    errs.append("coverage %s, data %.3f (worst run; TSR %.3f)" % (s, a["cov"], a["tsr"]))
            dr = re.search(r"drift ([\d.]+) ?%", plain)
            if dr and not close(dr.group(1), a["drift"]):
                errs.append("drift %s %%, data %.2f %%" % (dr.group(1), a["drift"]))
            report(not errs, "%s%s" % (where, (" -> " + "; ".join(errs)) if errs else ""))
    # the headroom table: the 1x row (APE, CPU, pose age of both flights) and the 8x urban cell
    m = re.search(r"\| 1x \(matrix\) \| ([^|]+)\| ([^|]+)\|", text)
    if m:
        for algo, cell in zip(("fastlio2", "fastlivo2"), m.groups()):
            nums = re.findall(r"([\d.]+) / ([\d.]+)", cell)
            for (x, y), (key, scale, name) in zip(nums, [("ape_cm", 1, "APE cm"), ("cpu", 100, "CPU cores"),
                                                        ("age", 1, "pose age p95 ms")]):
                for shown, (grp, cond) in zip((x, y), [("environments", "room"), ("speed", "urban_speed5")]):
                    val = agg(R, grp, cond, algo)[key]
                    checked += 1
                    report(close(shown, val / scale if val is not None else None),
                           "headroom 1x | %s %s %s: %s, data %.3f" % (NAMES[algo], cond, name, shown, val / scale))
    m = re.search(r"urban: coverage \*\*([\d.]+)\*\*, ([\d.]+) cm", text)
    if m:
        a = agg(R, "headroom/rate8", "urban_speed5", "fastlivo2")
        checked += 1
        report(close(m.group(1), a["cov"]) and close(m.group(2), a["ape_cm"]),
               "headroom 8x | FAST-LIVO2 urban_speed5: coverage %s, %s cm; data %.3f, %.2f cm" % (
                   m.group(1), m.group(2), a["cov"], a["ape_cm"]))
    print("  ----  %d numbers in the log's result tables checked against the re-scored runs" % checked)


def replay(V):
    """The live replay (run_all_algos.sh, 1 run each, into <V>/replay) against the stored runs."""
    P = os.path.join(V, "replay")
    g_old, g_new = os.path.join(S, "environments", "gt", "room.tum"), os.path.join(P, "gt", "room.tum")
    report(os.path.exists(g_new) and open(g_old, "rb").read() == open(g_new, "rb").read(),
           "ground truth extracted again from flights/room.bag is byte-identical to the stored one")
    n_old = json.load(open(os.path.join(S, "environments", "bags", "room__imu1.0.imu_noise.json")))
    pn = os.path.join(P, "bags", "room__imu1.0.imu_noise.json")
    n_new = json.load(open(pn)) if os.path.exists(pn) else {}
    report(n_old == n_new, "IMU noise injection (seed 1) has the same parameters and message count (%s msgs)"
           % n_new.get("imu_messages"))
    for algo in ("fastlio2", "fastlivo2", "orbslam3"):
        p = os.path.join(P, "eval", "%s__room__r1_extra.json" % algo)
        if not os.path.exists(p):
            report(False, "%-10s live replay produced no score" % NAMES[algo]); continue
        new = json.load(open(p))
        old = [e for e in extras(S, "environments", "room", algo) if e]
        vals = [e["ape_air_rmse"] * 100 for e in old if not e.get("failed")]
        x = new.get("ape_air_rmse", float("nan")) * 100
        if algo == "orbslam3":   # multi-threaded: varies run to run; must land near the stored spread
            lo, hi = min(vals), max(vals)
            ok = not new.get("failed") and 0.5 * lo <= x <= 1.5 * hi
            report(ok, "%-10s live run %.2f cm, coverage %.3f; stored runs %s cm (varies run to run)" % (
                NAMES[algo], x, new.get("coverage_air", 0), " ".join("%.2f" % v for v in vals)))
        else:
            ok = not new.get("failed") and any(abs(x - v) < 0.05 for v in vals)
            report(ok, "%-10s live run %.3f cm, coverage %.3f; stored runs %s cm" % (
                NAMES[algo], x, new.get("coverage_air", 0), " ".join("%.3f" % v for v in vals)))


if __name__ == "__main__":
    if not os.path.exists("compose.yaml"):
        sys.exit("run from the project root")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    V = sys.argv[2] if len(sys.argv) > 2 else "output/verify_stage4"
    {"flights": check_flights, "matrix": check_matrix}.get(cmd, lambda: None)()
    {"prepare": prepare, "compare": compare, "tables": tables, "log": check_log, "replay": replay}.get(
        cmd, lambda v: None)(V)
    sys.exit(min(FAILS, 100))
