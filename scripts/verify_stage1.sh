#!/usr/bin/env bash
# Stage 1 verification: the containers, and every number of the paper-reproduction deliverable
# (final_results/*.csv) recomputed from the stored raw outputs. HOST, project root:
#   bash scripts/verify_stage1.sh          # ~15 min
# The Stage 1 datasets are no longer on disk (deleted to free space, 20 Oct and 17 Nov), so the
# runs are re-SCORED here, not re-run: each FAST-LIO2 run from its recorded /Odometry bag, each
# FAST-LIVO2 run from the pose file its node wrote, each ORB-SLAM3 run from its trajectory file,
# against the stored ground truth, with each algorithm's original evaluation script and settings.
# Writes only V (default output/final_verification/stage1), replaced on every run.
#  1 host + base   Gate 1 (verify_host.sh) and Gate 2 (verify_base.sh: ROS Noetic, GPU OpenGL)
#  2 containers    test_containers.sh quick: images, pinned commits, binaries, the eval chain
#  3 ORB-SLAM3     55 EuRoC runs re-scored (eval_orbslam3.sh's evo command), run by run vs stored
#  4 FAST-LIO2     80 runs re-scored from their bags (eval_fastlio2.sh), run by run vs stored
#  5 FAST-LIVO2    75 whole-bag + 45 matched-start runs re-scored (eval_fastlivo2.sh) vs stored
#  6 deliverable   final_results/*.csv regenerated from the re-scored runs: identical to the files
set -o pipefail
[ -f compose.yaml ] || { echo "run from the project root"; exit 1; }
V=${V:-output/final_verification/stage1}
C="docker compose run --rm -T"
FAILED=(); T0=$(date +%s)
step() { echo; echo "==[$1] $2   ($(date +%T))"; }
res() { [ "$2" -eq 0 ] || FAILED+=("$1"); }
exec 2> >(grep --line-buffered -v -E "^ Container .* (Creating|Created)" >&2)
echo "Stage 1 verification  $(date -Is)  git $(git rev-parse --short HEAD)"
$C eval bash -c "rm -rf /$V" >/dev/null 2>&1; mkdir -p "$V"

step 1 "Gate 1 (host) and Gate 2 (base image)"
rc=0
bash scripts/verify_host.sh > "$V/verify_host.txt" 2>&1
sed 's/^/     /' "$V/verify_host.txt" | grep -E "OK|FAIL|ready"
grep -q FAIL "$V/verify_host.txt" && { echo "  FAIL  host check"; rc=1; } || echo "  PASS  Gate 1: host ready"
bash scripts/verify_base.sh > "$V/verify_base.txt" 2>&1
r=$(grep -m1 "OpenGL renderer" "$V/verify_base.txt"); d=$(grep -m1 -x "noetic" "$V/verify_base.txt")
if grep -q BASE_OK "$V/verify_base.txt" && [ "$d" = noetic ] && grep -q "NVIDIA" <<<"$r"; then
  echo "  PASS  Gate 2: evtol/base:noetic runs ROS $d; ${r# }"
else echo "  FAIL  Gate 2 (see $V/verify_base.txt)"; rc=1; fi
res 1 $rc

step 2 "container test suite (L0 images + pins, L1 evaluation chain)"
bash scripts/test_containers.sh quick > "$V/test_containers.txt" 2>&1; n=$?
grep -E "^  (PASS|FAIL|SKIP)" "$V/test_containers.txt"
tail -1 "$V/test_containers.txt" | sed 's/^/  ----  /'
[ $n -eq 0 ] && echo "  PASS  container suite: 0 failures" || echo "  FAIL  container suite: $n failures"
res 2 $n

step 3 "ORB-SLAM3: 55 EuRoC runs re-scored from their trajectory files"
$C eval bash -c '
O=/output/final_verification/stage1/orbslam3; mkdir -p $O
declare -A GT=([MH01]=MH_01_easy [MH02]=MH_02_easy [MH03]=MH_03_medium [MH04]=MH_04_difficult [MH05]=MH_05_difficult
  [V101]=V1_01_easy [V102]=V1_02_medium [V103]=V1_03_difficult [V201]=V2_01_easy [V202]=V2_02_medium [V203]=V2_03_difficult)
for est in /output/orbslam3/trajectories/kf_orb_*_r[1-5].txt; do
  base=$(basename $est .txt); s=$(echo $base | sed "s/^kf_orb_//; s/_r[0-9]*$//")
  awk "{printf \"%.9f\", \$1 / 1000000000; for (i=2; i<=NF; i++) printf \" %s\", \$i; printf \"\\n\"}" $est > $O/${base}_eval.txt
  # eval_orbslam3.sh, verbatim: evo_ape euroc <EuRoC GT csv> <est> -va --align (GT: the kept byte-identical copy)
  evo_ape euroc /output/orbslam3/groundtruth/${GT[$s]}_state_groundtruth_estimate0.csv $O/${base}_eval.txt -va --align \
      --save_results $O/${base}_ape.zip > $O/${base}_ape.txt 2>&1 || echo "FAILED $base"
done
evo_res $O/kf_orb_*_r*_ape.zip --use_filenames --save_table $O/summary.csv > /dev/null 2>&1' | tee "$V/orbslam3.log"
python3 - "$V/orbslam3/summary.csv" docs/results/orbslam3_summary.csv <<'EOF'
import csv, os, sys
def rd(p):
    return {os.path.basename(r[0]): float(r[1]) for r in list(csv.reader(open(p)))[1:]}
new, old = rd(sys.argv[1]), rd(sys.argv[2])
d = [abs(new[k] - old[k]) for k in old if k in new]
miss = sorted(set(old) - set(new))
print("  ----  runs: stored %d, re-scored %d, max |re-scored - stored| APE RMSE = %.1e m" % (len(old), len(new), max(d) if d else float("nan")))
ok = len(new) == len(old) == 55 and not miss and max(d) < 1e-9
print("  %s  ORB-SLAM3: every run's APE RMSE reproduced%s" % ("PASS" if ok else "FAIL", "" if ok else " (missing: %s)" % miss))
sys.exit(0 if ok else 1)
EOF
res 3 $?

cmp_summary() {   # cmp_summary <label> <new summary.csv> <stored summary.csv>
python3 - "$@" <<'EOF'
import csv, sys
lab, a, b = sys.argv[1:4]
def rd(p):
    return {(r["sequence"], r["run"], r["metric"]): r["value_m"] for r in csv.DictReader(open(p))}
new, old = rd(a), rd(b)
bad, worst = [], 0.0
for k, v in old.items():
    w = new.get(k)
    if w is None:
        bad.append((k, v, "missing")); continue
    try:
        x, y = float(v), float(w)
    except ValueError:
        if v != w: bad.append((k, v, w))
        continue
    dec = len(v.split(".")[1]) if "." in v else 0         # the stored value's printed precision
    tol = max(1e-9, 0.5 * 10 ** -dec + 1e-12)
    worst = max(worst, abs(x - y))
    if abs(x - y) > tol: bad.append((k, v, w))
extra = sorted(set(new) - set(old))
print("  ----  %s: %d stored values, %d re-scored, largest difference %.1e m%s" % (
    lab, len(old), len(new), worst, ", extra: %s" % extra[:4] if extra else ""))
for k, v, w in bad[:10]:
    print("  FAIL  %s run %s %s: stored %s, re-scored %s" % (k[0], k[1], k[2], v, w))
print("  %s  %s: every stored value reproduced" % ("PASS" if not bad else "FAIL", lab))
sys.exit(1 if bad else 0)
EOF
}
links() {   # links <stored dir name under output/> <link dir> <glob>...: relative links (resolve inside containers)
  local src=$1 dst=$2; shift 2; mkdir -p "$dst"
  for g in "$@"; do for f in output/$src/$g; do [ -e "$f" ] && ln -sf "../../../$src/$(basename "$f")" "$dst/$(basename "$f")"; done; done
}

step 4 "FAST-LIO2: every run re-scored from its recorded /Odometry bag"
links fastlio2 "$V/fastlio2_in" '*_r[0-9].bag' 'gt_*.tum' 'gnssref_*.tum'
echo "  ----  $(ls "$V"/fastlio2_in/*_r*.bag | wc -l) run bags linked"
$C -e IN=/$V/fastlio2_in -e RESULTS=/$V/fastlio2 eval bash /scripts/eval_fastlio2.sh > "$V/fastlio2.log" 2>&1
cmp_summary "FAST-LIO2" "$V/fastlio2/summary.csv" docs/results/fastlio2_summary.csv
res 4 $?

step 5 "FAST-LIVO2: every run re-scored from its pose file (whole bag, and NTU-VIRAL matched start)"
rc=0
links fastlivo2 "$V/fastlivo2_in" '*_r[0-9].txt' 'gt_*.tum'
links fastlivo2_matched "$V/fastlivo2_matched_in" '*_r[0-9].txt' 'gt_*.tum'
$C -e IN=/$V/fastlivo2_in -e RESULTS=/$V/fastlivo2_standard eval bash /scripts/eval_fastlivo2.sh > "$V/fastlivo2_standard.log" 2>&1
$C -e IN=/$V/fastlivo2_matched_in -e RESULTS=/$V/fastlivo2_matched eval bash /scripts/eval_fastlivo2.sh > "$V/fastlivo2_matched.log" 2>&1
cmp_summary "FAST-LIVO2 whole bag" "$V/fastlivo2_standard/summary.csv" docs/results/fastlivo2_standard_summary.csv || rc=1
cmp_summary "FAST-LIVO2 matched start" "$V/fastlivo2_matched/summary.csv" docs/results/fastlivo2_matched_summary.csv || rc=1
res 5 $rc

step 6 "the deliverable: final_results/*.csv regenerated from the re-scored runs"
rc=0
R=$V/regen; mkdir -p "$R/docs/results"
cp docs/make_final_results.py "$R/docs/"; cp docs/results/* "$R/docs/results/"
cp "$V/orbslam3/summary.csv" "$R/docs/results/orbslam3_summary.csv"
cp "$V/fastlio2/summary.csv" "$R/docs/results/fastlio2_summary.csv"
cp "$V/fastlivo2_standard/summary.csv" "$R/docs/results/fastlivo2_standard_summary.csv"
cp "$V/fastlivo2_matched/summary.csv" "$R/docs/results/fastlivo2_matched_summary.csv"
python3 "$R/docs/make_final_results.py" > "$R/make_final_results.log" 2>&1 || { echo "  FAIL  make_final_results.py"; rc=1; }
for f in orbslam3_comparison.csv fastlio2_comparison.csv fastlivo2_comparison.csv; do
  if cmp -s "$R/final_results/$f" "final_results/$f"; then
    echo "  PASS  final_results/$f: regenerated from the re-scored runs, byte-identical ($(($(wc -l < "final_results/$f") - 1)) rows)"
  else
    echo "  FAIL  final_results/$f differs:"; diff "final_results/$f" "$R/final_results/$f" | head -8 | sed 's/^/          /'; rc=1
  fi
done
if [ -z "$(git status --porcelain -- final_results docs/results/*.csv)" ]; then
  echo "  PASS  final_results/ and docs/results/*.csv: no change since the commit (git status clean)"
else echo "  FAIL  final_results/ or docs/results changed since the commit:"; git status --short -- final_results docs/results | sed 's/^/          /'; rc=1; fi
grep -E "^EuRoC MAV,AVERAGE" final_results/orbslam3_comparison.csv | awk -F, '{print "  ----  ORB-SLAM3 EuRoC mean of 11 medians "$5" m vs paper "$4" m ("$7" %)"}'
res 6 $rc

$C eval chown -R "$(id -u):$(id -g)" "/$V" >/dev/null 2>&1
echo
echo "== Stage 1 verification finished in $(( ($(date +%s) - T0) / 60 )) min"
if [ ${#FAILED[@]} -eq 0 ]; then echo "== ALL STEPS PASSED"; else echo "== FAILED STEPS: ${FAILED[*]}"; fi
exit ${#FAILED[@]}
