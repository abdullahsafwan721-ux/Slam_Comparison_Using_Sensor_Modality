#!/usr/bin/env python3
"""Convert a third-party ground-truth CSV to TUM format (t x y z qx qy qz qw).

Datasets ship ground truth in every imaginable layout; this maps columns
explicitly instead of guessing.

  # NCLT: utime(us),x,y,z,roll,pitch,yaw
  python3 csv_to_tum.py gt.csv gt.tum --t 0 --t-scale 1e-6 --xyz 1 2 3 --rpy 4 5 6
  # quaternion given as x,y,z,w in columns 4-7, seconds in column 0, space separated
  python3 csv_to_tum.py gt.txt gt.tum --delim ' ' --t 0 --xyz 1 2 3 --quat-xyzw 4 5 6 7
"""
import argparse
import math


def rpy_to_q(r, p, y):
    cr, sr, cp, sp, cy, sy = (math.cos(r / 2), math.sin(r / 2), math.cos(p / 2),
                              math.sin(p / 2), math.cos(y / 2), math.sin(y / 2))
    return (sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--delim", default=",")
    ap.add_argument("--t", type=int, required=True)
    ap.add_argument("--t-scale", type=float, default=1.0, help="multiply time column to get seconds")
    ap.add_argument("--xyz", type=int, nargs=3, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rpy", type=int, nargs=3)
    g.add_argument("--quat-xyzw", type=int, nargs=4)
    g.add_argument("--quat-wxyz", type=int, nargs=4)
    a = ap.parse_args()
    n = skipped = 0
    with open(a.inp) as fi, open(a.out, "w") as fo:
        for line in fi:
            if not line.strip() or line.lstrip()[0] in "#%":
                continue
            c = line.strip().split(a.delim) if a.delim != " " else line.split()
            try:
                v = [float(x) for x in c]
            except ValueError:
                skipped += 1          # header rows
                continue
            if any(math.isnan(x) for x in v):
                skipped += 1          # NCLT has NaN rows
                continue
            if a.rpy:
                q = rpy_to_q(*(v[i] for i in a.rpy))
            elif a.quat_xyzw:
                q = tuple(v[i] for i in a.quat_xyzw)
            else:
                w, x, y, z = (v[i] for i in a.quat_wxyz)
                q = (x, y, z, w)
            fo.write("%.9f %.9f %.9f %.9f %.9f %.9f %.9f %.9f\n" % (
                (v[a.t] * a.t_scale,) + tuple(v[i] for i in a.xyz) + q))
            n += 1
    print("wrote %d poses (%d rows skipped) -> %s" % (n, skipped, a.out))


if __name__ == "__main__":
    main()
