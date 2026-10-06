#!/usr/bin/env python3
"""End-to-end error for a sequence that returns to its start.
    fl2_drift.py <traj.tum> [skip]        skip: seconds, or 'auto' (default)
The gap between first and last position IS the accumulated drift. It needs no
ground truth and cannot be flattered by alignment.

skip=auto starts at the first pose after the initialisation transient, defined as
any physically impossible step (> 20 m/s; the fastest platform here,
the UTBM car, peaks at 14 m/s and every sequence starts from rest) in the first 5 s -- e.g. the Avia demo
run's 1.2 m jump between its first two poses. With no such jump it starts at the
first pose. A fixed time skip is wrong for sequences that start moving at once:
on LIO-SAM garden the platform is moving by t = 2 s, and skipping 2 s moves the
start point 0.13 m along the path (gap 0.134 m instead of 0.027 m)."""
import math, sys
skip = sys.argv[2] if len(sys.argv) > 2 else "auto"
rows = [list(map(float, l.split()[:4])) for l in open(sys.argv[1]) if l.strip()]
if not rows: sys.exit("empty trajectory")
t0 = rows[0][0]
if skip == "auto":
    i0 = 0
    for i in range(1, len(rows)):
        if rows[i][0] - t0 > 5.0: break
        dt = max(rows[i][0] - rows[i-1][0], 1e-3)
        if math.dist(rows[i][1:4], rows[i-1][1:4]) / dt > 20.0: i0 = i
    rows = rows[i0:]
    if i0: print("skipped initialisation transient: first %d poses (%.2f s)" % (i0, rows[0][0] - t0))
else:
    rows = [r for r in rows if r[0] - t0 >= float(skip)]
pts = [r[1:4] for r in rows]
if len(pts) < 2: sys.exit("trajectory too short after skip")
length = sum(math.dist(pts[i], pts[i+1]) for i in range(len(pts)-1))
gap = math.dist(pts[0], pts[-1])
print("path length     %.2f m" % length)
print("end-to-end gap %.3f m    (%.3f %% of path)" % (gap, 100.0*gap/max(length,1e-9)))
