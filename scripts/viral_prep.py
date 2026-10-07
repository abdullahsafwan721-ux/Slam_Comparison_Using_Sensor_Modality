#!/usr/bin/env python3
"""NTU-VIRAL preparation, numpy only.

  viral_prep.py gt    <leica_pose.csv> <out_gt.tum>       Leica CSV -> TUM
  viral_prep.py prism <est.tum> <out_prism.tum>           IMU frame -> prism frame

Mirrors Log/result/ntu_viral/evaluate_viral.py in the FAST-LIVO2 repository
(which needs pandas + scipy; this needs numpy only). The offset comes from
ntu-aris/viral_eval/trans_B2prism.csv; the official MATLAB evaluation applies
exactly the same correction:  P_est = P_est + quatconv(Q_est, trans_B2prism).
NTU-VIRAL's ground truth is a Leica prism ~0.4 m from the body (IMU) frame that
FAST-LIVO2 estimates; without this transform the lever arm dominates the error.
"""
import sys
import numpy as np

TRANS_B2PRISM = np.array([-0.293656, -0.012288, -0.273095])      # metres, body frame


def quat_rotate(q, v):
    """Rotate v by each quaternion in q (N x 4, order x y z w)."""
    x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    n = np.sqrt(x*x + y*y + z*z + w*w)
    x, y, z, w = x/n, y/n, z/n, w/n
    R = np.empty((len(q), 3, 3))
    R[:, 0, 0] = 1-2*(y*y+z*z); R[:, 0, 1] = 2*(x*y-z*w);   R[:, 0, 2] = 2*(x*z+y*w)
    R[:, 1, 0] = 2*(x*y+z*w);   R[:, 1, 1] = 1-2*(x*x+z*z); R[:, 1, 2] = 2*(y*z-x*w)
    R[:, 2, 0] = 2*(x*z-y*w);   R[:, 2, 1] = 2*(y*z+x*w);   R[:, 2, 2] = 1-2*(x*x+y*y)
    return R @ v


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    mode, src, dst = sys.argv[1:]
    if mode == "gt":
        # leica_pose.csv: col0 = time in ns, cols 3-5 = x y z. Orientation is not
        # measured by the tracker, so TUM gets an identity quaternion.
        d = np.loadtxt(src, delimiter=",", skiprows=1)
        t = d[:, 0] / 1e9
        p = d[:, 3:6]
        q = np.tile([0.0, 0.0, 0.0, 1.0], (len(p), 1))
    elif mode == "prism":
        d = np.loadtxt(src)
        t, p, q = d[:, 0], d[:, 1:4], d[:, 4:8]
        p = p + quat_rotate(q, TRANS_B2PRISM)
    else:
        sys.exit(__doc__)
    np.savetxt(dst, np.column_stack((t, p, q)), fmt="%.6f")
    print("wrote %d poses -> %s (first t = %.3f)" % (len(t), dst, t[0]))


if __name__ == "__main__":
    main()
