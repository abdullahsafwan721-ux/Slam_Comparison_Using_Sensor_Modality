#!/usr/bin/env bash
# ORB-SLAM3 tracking time per frame (Stage 3, metric H5; not in the project guide).
#
#   bash scripts/stage3/orbslam3_timing.sh <outdir> <condition> [runs=3] [imu-scale=1.0]
#
# Run from the project root, AFTER run_all_algos.sh has prepared <outdir> for <condition>
# (it reuses that run's EuRoC folder and ground truth). Nothing else should be running:
# these are timings.
#
# Why a second image: ORB-SLAM3's EuRoC example publishes nothing, so "pose age at publish"
# cannot be measured for it the way it is for the two ROS methods. Upstream has its own
# instrumentation, switched on by one #define (REGISTER_TIMES, include/Settings.h); the
# image evtol/orbslam3:v1-times is evtol/orbslam3:v1 rebuilt with it. Accuracy numbers keep
# coming from the validated v1 image; this script only adds the timing, and scores each
# timing run so that one can see it tracked like the v1 runs.
#
# Writes <outdir>/orbslam3_times/r<N>/{TrackingTimeStats.txt,ExecMean.txt,...} and
# <outdir>/orbslam3_times/summary.{md,json}. Total[ms] per frame = stereo rectification +
# resize + System::TrackStereo, i.e. image in -> pose out (image decoding not included).
set -euo pipefail
[ $# -ge 2 ] || { sed -n '2,20p' "$0"; exit 1; }
OUT=${1%/}; COND=$2; RUNS=${3:-3}; SCALE=${4:-1.0}
case "$OUT" in output/*) ;; *) echo "!! '$OUT' must be a path under output/"; exit 1;; esac
[ -f compose.yaml ] || { echo "!! run from the project root"; exit 1; }
C="docker compose run --rm -T"
EU=/$OUT/orbslam3/euroc_${COND}__imu${SCALE}; GT=/$OUT/gt/$COND.tum
[ -s ".$EU/times.txt" ] && [ -s ".$GT" ] || { echo "!! $EU or $GT missing: run run_all_algos.sh first"; exit 1; }
T=$OUT/orbslam3_times; mkdir -p "$T"
trap '$C eval chown -R $(id -u):$(id -g) /$T >/dev/null 2>&1 || true' EXIT
for r in $(seq 1 "$RUNS"); do
  name=orbslam3times__${COND}__r$r; D=/$T/r$r
  echo "== $name"
  rm -rf ".$D"; mkdir -p ".$D"
  $C orbslam3_times bash -c "cd $D && \
      /opt/ORB_SLAM3/Examples/Stereo-Inertial/stereo_inertial_euroc \
      /opt/ORB_SLAM3/Vocabulary/ORBvoc.txt /config/generated/orbslam3_sim.yaml \
      $EU $EU/times.txt $name > $name.log 2>&1; \
      touch f_$name.txt; \
      awk '{printf \"%.9f %s %s %s %s %s %s %s\\n\", \$1/1e9, \$2,\$3,\$4,\$5,\$6,\$7,\$8}' f_$name.txt > $name.tum"
  $C eval python3 /scripts/common/metrics_extra.py $GT $D/$name.tum $D/$name > ".$D/score.log" 2>&1 \
      || echo "!! $name: scoring failed"
done
$C eval python3 /scripts/stage3/timing_summary.py /$T $EU/times.txt
