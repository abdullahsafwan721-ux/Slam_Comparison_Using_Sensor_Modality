#!/usr/bin/env bash
# Score one estimated trajectory against ground truth. Runs INSIDE the eval container.
#
#   eval_traj.sh <gt.tum> <est.tum> <out-prefix> [se3|sim3]
#
# Naming convention used by every stage:  <out-prefix> = .../<algo>__<condition>__r<run>
# results_table.py parses exactly that, so keep it.
#
# Writes <prefix>_ape.zip, <prefix>_rpe.zip, <prefix>_ape.pdf, <prefix>_coverage.txt
#   APE  absolute trajectory error (translation), after alignment
#   RPE  relative error over 1 m segments -- drift, insensitive to alignment
# se3  (default) is correct for every stereo- or LiDAR-inertial method here:
#      metric scale is observable. sim3 would hide a scale error; use it only
#      for monocular output.
set -euo pipefail
[ $# -ge 3 ] || { sed -n '2,15p' "$0"; exit 1; }
GT=$1; EST=$2; PRE=$3; MODE=${4:-se3}
ALIGN="--align"; [ "$MODE" = "sim3" ] && ALIGN="--align --correct_scale"
export MPLBACKEND=Agg                                   # headless plotting
# evo ignores MPLBACKEND: it calls matplotlib.use(<its plot_backend setting>), default TkAgg,
# and evtol/eval:v1 has no tkinter, so --save_plot crashed. Set evo's own option (writes
# ~/.evo/settings.json inside the throwaway container). Added; not in the project guide.
evo_config set plot_backend Agg > /dev/null
mkdir -p "$(dirname "$PRE")"
evo_ape tum "$GT" "$EST" $ALIGN --t_max_diff 0.02 \
        --save_results "${PRE}_ape.zip" --save_plot "${PRE}_ape.pdf" --plot_mode xy > "${PRE}_ape.txt"
evo_rpe tum "$GT" "$EST" $ALIGN --t_max_diff 0.02 --delta 1 --delta_unit m \
        --save_results "${PRE}_rpe.zip" > "${PRE}_rpe.txt"
# Coverage: fraction of the ground-truth duration the estimate spans. An
# algorithm that loses track halfway can still post a small APE on the half
# it kept -- coverage is what exposes that.
awk 'NR==FNR{if(NR==1)g0=$1; g1=$1; next} FNR==1{e0=$1} {e1=$1}
     END{c=(e1-e0)/(g1-g0); if(c>1)c=1; printf "%.3f\n", c}' "$GT" "$EST" > "${PRE}_coverage.txt"
echo "$(basename "$PRE")  APE $(grep -E '^ *rmse' "${PRE}_ape.txt" | awk '{print $2}') m  coverage $(cat "${PRE}_coverage.txt")"
