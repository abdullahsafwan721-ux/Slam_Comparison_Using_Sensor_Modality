#!/usr/bin/env bash
# Stage 4 verification helper. Runs INSIDE the eval container; verify_stage4.sh calls it:
#   bash /scripts/stage4/verify_score.sh <jobs.txt> [parallel]
# One job per line: <gt.tum> <est.tum> <out-prefix> <tau> <cost.csv> <latency.csv>
# Scores exactly like the "score" step of scripts/stage3/run_all_algos.sh (eval_traj.sh, then
# metrics_extra.py; an empty trajectory or a scoring failure becomes the same failure record),
# but many runs at a time instead of one container per run.
set -o pipefail
JOBS=$1; P=${2:-8}
FAILED='{"failed": true, "tsr": 0.0, "tsr_start": 0.0, "coverage_air": 0.0, "coverage_bag": 0.0}'
evo_config set plot_backend Agg > /dev/null 2>&1

one() {   # one <gt> <est> <prefix> <tau> <cost> <latency>; exit 0 = scored (or empty run recorded)
  if [ ! -s "$2" ]; then echo "$FAILED" > "$3_extra.json"; echo "   empty trajectory (failed run): $(basename "$3")"; return 0; fi
  bash /scripts/common/eval_traj.sh "$1" "$2" "$3" > "$3.score.log" 2>&1 &&
    python3 /scripts/common/metrics_extra.py "$1" "$2" "$3" --tau "$4" --cost "$5" --latency "$6" >> "$3.score.log" 2>&1
}
export -f one; export FAILED

n=$(wc -l < "$JOBS")
echo "   scoring $n runs, $P at a time"
xargs -P "$P" -L 1 bash -c 'one "$@" || echo "   (will retry) $(basename "$3")"' _ < "$JOBS"
# evo rewrites ~/.evo/settings.json on every call; parallel calls can collide, so whatever did
# not produce a result is scored again, one at a time, before it counts as a failure
while read -r gt est pre tau cost lat; do
  [ -s "${pre}_extra.json" ] && continue
  one "$gt" "$est" "$pre" "$tau" "$cost" "$lat" ||
    { echo "$FAILED" > "${pre}_extra.json"; echo "   scoring failed: $(basename "$pre") (see $pre.score.log)"; }
done < "$JOBS"
echo "   scoring done"
