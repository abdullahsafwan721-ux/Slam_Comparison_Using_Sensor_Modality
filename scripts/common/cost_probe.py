#!/usr/bin/env python3
"""Sample the CPU and memory cost of one algorithm process while it runs.
Runs INSIDE the algorithm's container, beside the algorithm (any python3, no ROS needed):

    python3 cost_probe.py <executable-name> <out.csv> [--hz 2] [--wait 120]

Added in Stage 3 (not in the project guide); metric H5 in
docs/eVTOL_SLAM_Research_and_Stage3-5_Plan.pdf. Waits up to --wait s for a process
whose executable name contains the given string (e.g. fastlio_mapping, fastlivo_mapping,
stereo_inertial_euroc), then samples /proc/<pid>/stat (utime+stime, all threads) and
/proc/<pid>/status (VmRSS) --hz times a second until the process exits or this probe
gets SIGINT/SIGTERM. cpu_pct is per sample interval, 100 = one full core.

CSV columns: t_s (since first sample), cpu_pct, rss_mb, threads, cpu_total_s
"""
import argparse
import os
import signal
import sys
import time

TICK = os.sysconf("SC_CLK_TCK")
stop = False


def on_signal(*_):
    global stop
    stop = True


def find(sub):
    me = os.getpid()
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == me:
            continue
        try:
            argv0 = open("/proc/%s/cmdline" % d, "rb").read().split(b"\0")[0].decode(errors="replace")
        except OSError:
            continue
        # the executable itself, not a shell / timeout / roslaunch whose arguments mention it
        if sub in os.path.basename(argv0):
            return int(d)
    return None


def sample(pid):
    with open("/proc/%d/stat" % pid) as f:
        st = f.read().rsplit(")", 1)[1].split()
    cpu = (int(st[11]) + int(st[12])) / TICK          # utime + stime (fields 14, 15)
    rss, thr = 0.0, 0
    with open("/proc/%d/status" % pid) as f:
        for line in f:
            if line.startswith("VmRSS:"):
                rss = int(line.split()[1]) / 1024.0
            elif line.startswith("Threads:"):
                thr = int(line.split()[1])
    return cpu, rss, thr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sub")
    ap.add_argument("out")
    ap.add_argument("--hz", type=float, default=2.0)
    ap.add_argument("--wait", type=float, default=120.0)
    a = ap.parse_args()
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    t_end = time.time() + a.wait
    pid = None
    while pid is None and not stop and time.time() < t_end:
        pid = find(a.sub)
        if pid is None:
            time.sleep(0.2)
    if pid is None:
        sys.exit("cost_probe: no process matching '%s' within %.0f s" % (a.sub, a.wait))

    rows = []
    t0 = time.monotonic()
    prev = None
    while not stop:
        try:
            cpu, rss, thr = sample(pid)
        except (OSError, IndexError):
            break                                       # process exited
        now = time.monotonic()
        pct = 100.0 * (cpu - prev[1]) / (now - prev[0]) if prev else 0.0
        rows.append((now - t0, pct, rss, thr, cpu))
        prev = (now, cpu)
        time.sleep(1.0 / a.hz)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        f.write("t_s,cpu_pct,rss_mb,threads,cpu_total_s\n")
        f.writelines("%.2f,%.1f,%.1f,%d,%.2f\n" % r for r in rows)
    if len(rows) > 1:
        cpus = sorted(r[1] for r in rows[1:])
        print("cost %s: pid %d, %d samples, CPU mean %.0f%% p95 %.0f%%, peak RSS %.0f MB, CPU time %.1f s"
              % (a.sub, pid, len(rows), sum(cpus) / len(cpus), cpus[int(0.95 * (len(cpus) - 1))],
                 max(r[2] for r in rows), rows[-1][4]))


if __name__ == "__main__":
    main()
