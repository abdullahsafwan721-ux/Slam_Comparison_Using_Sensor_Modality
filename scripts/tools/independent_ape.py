#!/usr/bin/env python3
"""Independent cross-check of the scoring (host, plain python3 + numpy, project root):

    python3 scripts/tools/independent_ape.py [out.txt]

APE RMSE written from scratch here, using neither evo nor the project's metrics code: timestamp
association (each pose of the shorter trajectory paired with the nearest pose of the longer one
within the stated window, as evo does), a least-squares rigid alignment (Umeyama/Kabsch, no scale),
and the RMSE of the remaining position error. It re-scores a sample of stored runs from every stage,
from their trajectory files, and compares with the score each stage reported. A difference above
1e-6 m fails.
"""
import csv
import glob
import json
import os
import sys
import zipfile

import numpy as np


def tum(path):
    a = np.loadtxt(path, comments="#", ndmin=2)
    a = a[np.argsort(a[:, 0], kind="stable")]
    return a[:, 0], a[:, 1:4]


def ape(gt_path, est_path, max_diff):
    tg, pg = tum(gt_path)
    te, pe = tum(est_path)
    if len(te) <= len(tg):                       # the shorter trajectory drives the association
        short_t, long_t, short_is_est = te, tg, True
    else:
        short_t, long_t, short_is_est = tg, te, False
    idx = np.searchsorted(long_t, short_t)
    lo = np.clip(idx - 1, 0, len(long_t) - 1)
    hi = np.clip(idx, 0, len(long_t) - 1)
    pick = np.where(np.abs(long_t[lo] - short_t) <= np.abs(long_t[hi] - short_t), lo, hi)
    ok = np.abs(long_t[pick] - short_t) <= max_diff
    i_short, i_long = np.nonzero(ok)[0], pick[ok]
    if short_is_est:
        E, G = pe[i_short], pg[i_long]
    else:
        E, G = pe[i_long], pg[i_short]
    me, mg = E.mean(0), G.mean(0)
    U, S, Vt = np.linalg.svd((G - mg).T @ (E - me) / len(E))
    D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        D[2, 2] = -1
    R = U @ D @ Vt
    t = mg - R @ me
    err = np.linalg.norm(G - (E @ R.T + t), axis=1)
    return float(np.sqrt(np.mean(err ** 2))), len(E)


def zip_rmse(p):
    return json.loads(zipfile.ZipFile(p).read("stats.json"))["rmse"]


def summary_value(path, seq, run, metric="ape_rmse"):
    for r in csv.DictReader(open(path)):
        if r["sequence"] == seq and r["run"] == str(run) and r["metric"] == metric:
            return float(r["value_m"])
    return None


def cases():
    F1 = "output/final_verification/stage1"
    out = []
    # Stage 1 -- ORB-SLAM3 EuRoC (GT: EuRoC csv, ns -> TUM s, from the Stage 1-2 audit), FAST-LIO2, FAST-LIVO2
    for s, r in (("MH01", 1), ("V203", 2), ("MH05", 3)):
        out.append(("Stage 1  ORB-SLAM3 %s r%d" % (s, r), "output/diagnostics/stage1_tools_check/gt/%s.tum" % s,
                    "%s/orbslam3/kf_orb_%s_r%d_eval.txt" % (F1, s, r), 0.01,
                    zip_rmse("output/orbslam3/evaluation/kf_orb_%s_r%d_ape.zip" % (s, r))))
    for s, r in (("nclt9", 1), ("utbm8", 1), ("liosam1_park", 3)):
        out.append(("Stage 1  FAST-LIO2 %s r%d" % (s, r), "output/fastlio2/gt_%s.tum" % s, "%s/fastlio2_in/%s_r%d.tum" % (F1, s, r),
                    0.02, summary_value("docs/results/fastlio2_summary.csv", s, r)))
    for s, r in (("eee_01", 1), ("nya_02", 4)):
        out.append(("Stage 1  FAST-LIVO2 %s r%d" % (s, r), "output/fastlivo2/gt_%s.tum" % s,
                    "%s/fastlivo2_in/%s_r%d_prism.tum" % (F1, s, r), 0.01,
                    summary_value("docs/results/fastlivo2_standard_summary.csv", s, r)))
    # Stages 3 and 4 -- whole-bag APE of eval_traj.sh (evo, --t_max_diff 0.02)
    for grp, cond in (("output/stage3/px4", "room_square"), ("output/stage3/scripted", "room"),
                      ("output/stage4/environments", "corridor"), ("output/stage4/altitude", "urban_alt60"),
                      ("output/stage4/imu", "imu_x30")):
        for a in ("fastlio2", "fastlivo2", "orbslam3"):
            j = "%s/eval/%s__%s__r1_extra.json" % (grp, a, cond)
            e = json.load(open(j)) if os.path.exists(j) else {}
            if "ape_rmse" not in e:
                continue
            out.append(("Stage %s  %s %s r1" % ("3" if "stage3" in grp else "4", a, cond), "%s/gt/%s.tum" % (grp, cond),
                        "%s/%s/%s__%s__r1.tum" % (grp, a, a, cond), 0.02, e["ape_rmse"]))
    # Stage 5 -- the SLAM method's APE in the closed loop (eval_closed_loop.sh -> eval_traj.sh)
    for name in ("room_square_r2", "room_hover_long_r1"):
        for who in ("fastlio2", "px4"):
            j = "output/stage5/eval/%s__%s__r1_extra.json" % (who, name)
            if os.path.exists(j):
                e = json.load(open(j))
                gt, est = ("output/stage5/flights/" + os.path.basename(e.get(k, "")) for k in ("gt", "est"))
                out.append(("Stage 5  %s closed loop %s" % ("PX4" if who == "px4" else "FAST-LIO2", name), gt, est, 0.02,
                            e["ape_rmse"]))
    return out


def main():
    rows, fails = [], 0
    for label, gt, est, md, ref in cases():
        if not (os.path.exists(gt) and os.path.exists(est)) or ref is None:
            rows.append("  SKIP  %-44s (missing %s)" % (label, gt if not os.path.exists(gt) else est))
            continue
        v, n = ape(gt, est, md)
        ok = abs(v - ref) <= 1e-6
        fails += not ok
        rows.append("  %s  %-44s independent %.6f m  reported %.6f m  diff %.1e  (%d pairs)" %
                    ("PASS" if ok else "FAIL", label, v, ref, abs(v - ref), n))
    txt = "\n".join(rows) + "\n  %s  %d runs re-scored independently, %d differ by more than 1e-6 m\n" % (
        "PASS" if fails == 0 else "FAIL", sum(1 for r in rows if "SKIP" not in r), fails)
    print(txt)
    if len(sys.argv) > 1:
        open(sys.argv[1], "w").write(txt)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
