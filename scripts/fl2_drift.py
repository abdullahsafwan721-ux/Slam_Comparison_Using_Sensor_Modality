#!/usr/bin/env python3
"""End-to-end error for a sequence that returns to its start.
    fl2_drift.py <traj.tum> [skip_seconds]
The gap between first and last position IS the accumulated drift. It needs no
ground truth and cannot be flattered by alignment. skip_seconds drops the
initialisation transient (the Avia run showed a 1.2 m jump in the first 2 s)."""
import math, sys
skip = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
rows = [list(map(float, l.split()[:4])) for l in open(sys.argv[1]) if l.strip()]
if not rows: sys.exit("empty trajectory")
t0 = rows[0][0]
pts = [r[1:4] for r in rows if r[0] - t0 >= skip]
if len(pts) < 2: sys.exit("trajectory too short after skip")
length = sum(math.dist(pts[i], pts[i+1]) for i in range(len(pts)-1))
gap = math.dist(pts[0], pts[-1])
print("path length     %.2f m" % length)
print("end-to-end gap %.3f m    (%.3f %% of path)" % (gap, 100.0*gap/max(length,1e-9)))
