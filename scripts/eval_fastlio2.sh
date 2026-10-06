#!/usr/bin/env bash
# Score every FAST-LIO2 run present. Runs in the eval container.
#   eval_fastlio2.sh                     # scores everything in /output/fastlio2
#   RESULTS=/output/results/fl2_2026xxxx eval_fastlio2.sh
#   T_MAX_DIFF=0.05 eval_fastlio2.sh     # GT association window (default 0.02 s)
#   IN=/output/fastlio2_smoke eval_fastlio2.sh   # score another run folder
#
# For each /output/fastlio2/<seq>_r<N>.bag:
#   - convert /Odometry to TUM
#   - if /output/fastlio2/gt_<seq>.tum exists -> evo_ape (SE(3) alignment)
#   - otherwise                              -> end-to-end drift
#     (+ end point vs gnssref_<seq>.tum if present, for sequences not ending at the start)
# Never deletes earlier results: each call writes a new timestamped folder.
set -uo pipefail
IN=${IN:-/output/fastlio2}
RESULTS=${RESULTS:-/output/results/fastlio2_$(date +%Y%m%d_%H%M%S)}
T_MAX_DIFF=${T_MAX_DIFF:-0.02}
mkdir -p "$RESULTS"
export MPLBACKEND=Agg
echo "sequence,run,metric,value_m" > "$RESULTS/summary.csv"
echo "t_max_diff=$T_MAX_DIFF  evo=$(pip3 show evo 2>/dev/null | awk '/^Version/{print $2}')" > "$RESULTS/settings.txt"

shopt -s nullglob
for bag in "$IN"/*_r*.bag; do
   base=$(basename "$bag" .bag)             # <seq>_r<N>
   seq=${base%_r*}; run=${base##*_r}
   [[ "$run" =~ ^[0-9]+$ ]] || continue     # not a run bag (e.g. utbm8_fix.bag)
   tum="$IN/$base.tum"
   python3 /scripts/fl2_traj.py "$bag" /Odometry "$tum" || { echo "$seq,$run,failed,NA" >> "$RESULTS/summary.csv"; continue; }
   gt="$IN/gt_${seq}.tum"
   if [ -s "$gt" ]; then
      # SE(3) alignment: LiDAR-inertial odometry observes metric scale, so never
      # --correct_scale, which would hide a scale error.
      evo_ape tum "$gt" "$tum" --align --t_max_diff "$T_MAX_DIFF" \
              --save_results "$RESULTS/${base}_ape.zip" > "$RESULTS/${base}_ape.txt" 2>&1
      v=$(grep -E '^\s*rmse' "$RESULTS/${base}_ape.txt" | awk '{print $2}')
      echo "$seq,$run,ape_rmse,${v:-NA}" >> "$RESULTS/summary.csv"
      printf '%-28s run %-2s APE RMSE %s m\n' "$seq" "$run" "${v:-FAILED}"
   else
      v=$(python3 /scripts/fl2_drift.py "$tum" 2 | awk '/end-to-end/{print $3}')
      echo "$seq,$run,end_to_end,${v:-NA}" >> "$RESULTS/summary.csv"
      printf '%-28s run %-2s end-to-end %s m (no ground truth)\n' "$seq" "$run" "${v:-FAILED}"
      # Sequences whose true end is NOT the start (LiLi-OM KA-Urban): if a GNSS
      # track gnssref_<seq>.tum exists, also score the end point against it (proxy).
      ref="$IN/gnssref_${seq}.tum"
      if [ -s "$ref" ]; then
         er=$(python3 /scripts/fl2_endref.py "$tum" "$ref")
         v=$(awk '/end-point error/{print $5}' <<<"$er")
         echo "$seq,$run,end_ref_gnss,${v:-NA}" >> "$RESULTS/summary.csv"
         echo "$seq,$run,gnss_start_end,$(awk '/start->end displacement/{print $4}' <<<"$er")" >> "$RESULTS/summary.csv"
         printf '%-28s run %-2s end-point vs GNSS %s m (proxy)\n' "$seq" "$run" "${v:-FAILED}"
      fi
   fi
done
echo; echo "wrote $RESULTS/summary.csv"
python3 /scripts/fl2_compare.py "$RESULTS/summary.csv" | tee "$RESULTS/comparison.md"
