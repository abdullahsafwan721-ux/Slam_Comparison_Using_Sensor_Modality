#!/usr/bin/env python3
"""End-point error against an external reference (GNSS), for sequences whose true
end location is NOT the start -- e.g. LiLi-OM KA-Urban, whose end points were
"registered from satellite images" (LiLi-OM paper, Sec. 5.3.2) and are unpublished.
    fl2_endref.py <est.tum> <ref.tum> [align_fraction=0.25] [avg_s=2]
The estimate is aligned to the reference with SE(3) Umeyama using ONLY the first
align_fraction of the run (so end drift is not absorbed by the alignment); the
error is the distance between the two end positions, each averaged over the last
avg_s seconds. Accuracy is bounded by the reference: consumer GNSS is metre-level,
so this is a proxy that cannot certify a '< 0.1 m' result."""
import sys, numpy as np
est = np.loadtxt(sys.argv[1])[:, :4]; ref = np.loadtxt(sys.argv[2])[:, :4]
frac = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
avg = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
t_end = min(est[-1, 0], ref[-1, 0]); t_beg = max(est[0, 0], ref[0, 0]) + 2.0
t_cut = t_beg + frac * (t_end - t_beg)
r = ref[(ref[:, 0] >= t_beg) & (ref[:, 0] <= t_cut)]
e = np.array([np.interp(r[:, 0], est[:, 0], est[:, k]) for k in (1, 2, 3)]).T
mu_e, mu_r = e.mean(0), r[:, 1:].mean(0)
U, _, Vt = np.linalg.svd((r[:, 1:] - mu_r).T @ (e - mu_e))
S = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]); R = U @ S @ Vt; t = mu_r - R @ mu_e
def end(a): return a[a[:, 0] >= t_end - avg, 1:4].mean(0)
e_end = R @ end(est) + t; r_end = end(ref)
fit = np.sqrt(((R @ e.T).T + t - r[:, 1:]) ** 2).sum(1).mean()
print("alignment window %.0f s, fit residual %.2f m" % (t_cut - t_beg, fit))
print("reference start->end displacement %.2f m" % np.linalg.norm(r_end - r[0, 1:]))
print("end-point error vs reference %.2f m  (horizontal %.2f m)" % (np.linalg.norm(e_end - r_end), np.linalg.norm((e_end - r_end)[:2])))
