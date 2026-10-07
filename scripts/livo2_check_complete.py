#!/usr/bin/env python3
"""Flag NTU-VIRAL FAST-LIVO2 runs whose trajectory ends early.
    livo2_check_complete.py <dir> [tolerance_s=2]
Compares the last pose time of each <seq>_r<N>.txt with the last pose of the authors'
shipped trajectory (data/ntu_viral/reference/<seq>_prism.txt). A run that ends earlier
was cut off before the node had drained its queue (the guide's fixed 5 s wait did this
on loaded CPUs: ~33 s missing on sbs_01/03). Exit code 1 if any run is truncated."""
import glob, os, re, sys
d = sys.argv[1]; tol = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
ref = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "ntu_viral", "reference")
bad = 0
for f in sorted(glob.glob(os.path.join(d, "*_r*.txt"))):
    m = re.match(r"(.+)_r(\d+)\.txt$", os.path.basename(f))
    r = os.path.join(ref, "%s_prism.txt" % m.group(1)) if m else None
    if not r or not os.path.exists(r): continue
    last = float(open(f).read().split()[-8]); rlast = float(open(r).read().split()[-8])
    short = rlast - last
    flag = "TRUNCATED" if short > tol else "ok"
    bad += short > tol
    print("%-22s ends %6.1f s before the authors' run  %s" % (os.path.basename(f), short, flag))
sys.exit(1 if bad else 0)
