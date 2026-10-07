#!/usr/bin/env bash
# Score every FAST-LIVO2 run present. Runs in the eval container.
#   eval_fastlivo2.sh
#   IN=/output/fastlivo2_smoke RESULTS=/output/results/x eval_fastlivo2.sh
# For each $IN/<seq>_r<N>.txt (TUM, IMU frame, written by the node):
#   - if $IN/gt_<seq>.tum exists -> prism transform, then evo_ape tum gt prism -a
#     (the authors' own command; evo's DEFAULT 0.01 s association window is what
#      reproduces their published RMSE -- do not widen it)
#   - otherwise                  -> end-to-end drift (private dataset loops)
# Never deletes earlier results: each call writes a new timestamped folder.
set -uo pipefail
IN=${IN:-/output/fastlivo2}
RESULTS=${RESULTS:-/output/results/fastlivo2_$(date +%Y%m%d_%H%M%S)}
mkdir -p "$RESULTS"
export MPLBACKEND=Agg
echo "sequence,run,metric,value_m" > "$RESULTS/summary.csv"
echo "evo=$(pip3 show evo 2>/dev/null | awk '/^Version/{print $2}') t_max_diff=evo default (0.01 s) align=SE(3)" > "$RESULTS/settings.txt"

shopt -s nullglob
for est in "$IN"/*_r*.txt; do
   base=$(basename "$est" .txt)
   seq=${base%_r*}; run=${base##*_r}
   [[ "$run" =~ ^[0-9]+$ ]] || continue
   gt="$IN/gt_${seq}.tum"
   if [ -s "$gt" ]; then
      prism="$IN/${base}_prism.tum"
      python3 /scripts/viral_prep.py prism "$est" "$prism" >/dev/null
      evo_ape tum "$gt" "$prism" -a \
              --save_results "$RESULTS/${base}_ape.zip" > "$RESULTS/${base}_ape.txt" 2>&1
      v=$(grep -E '^\s*rmse' "$RESULTS/${base}_ape.txt" | awk '{print $2}')
      echo "$seq,$run,ape_rmse,${v:-NA}" >> "$RESULTS/summary.csv"
      printf '%-22s run %-2s APE RMSE %s m\n' "$seq" "$run" "${v:-FAILED}"
   else
      out=$(python3 /scripts/fl2_drift.py "$est" auto)
      v=$(awk '/end-to-end/{print $3}' <<<"$out"); L=$(awk '/path length/{print $3}' <<<"$out")
      echo "$seq,$run,end_to_end,${v:-NA}" >> "$RESULTS/summary.csv"
      printf '%-22s run %-2s end-to-end %s m over %s m\n' "$seq" "$run" "${v:-FAILED}" "${L:-?}"
   fi
done
echo; echo "wrote $RESULTS/summary.csv"
python3 /scripts/livo2_compare.py "$RESULTS/summary.csv" | tee "$RESULTS/comparison.md"
