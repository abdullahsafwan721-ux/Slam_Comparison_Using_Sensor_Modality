#!/usr/bin/env bash
# Stage 3/4 workhorse: run all three algorithms on ONE simulation bag and score them.
# Runs on the HOST from the project root:
#   bash scripts/stage3/run_all_algos.sh output/stage2/scripted_room.bag room output/stage3 [runs] [imu-scale]
#
# Produces, under <outdir>:
#   bags/<cond>__imu<scale>.bag        noise-injected input (the one every algorithm sees)
#   gt/<cond>.tum                      ground truth (IMU frame)
#   <algo>/<algo>__<cond>__r<N>.*      per-run odometry, logs, TUM trajectory
#   eval/<algo>__<cond>__r<N>_ape.zip  scores; eval/summary.md aggregates them
#
# Changes from the guide's listing (docs/stage3_log.md has the reasons):
#   A1  bag tools run through ros_python.sh (the eval image's python3 is the evo venv)
#   A2  metrics_extra.py after eval_traj.sh: h/v APE, yaw, drift %, TSR, flight-window
#       coverage (Decision D1), start-up time  -> eval/summary_extra.md
#   A3  ORB-SLAM3 scored on its frame trajectory f_*.txt (Decision D2); the keyframe
#       trajectory kf_*.txt is scored beside it as algorithm "orbslam3kf" (APE only)
#   A4  every run logs CPU/RSS (cost_probe.py) and, for the ROS methods, latency
#   A8  FAST-LIVO2 is scored on its own pose file (state-time stamps), not on its topic,
#       which is stamped at publish time (~85 ms late); see the comment at that step
#   --  `docker compose run -T` (no TTY: the script also runs unattended / in background)
#   --  the noised bag, ground truth and EuRoC folder are made once and reused if present
#       (fixed seed, so a re-run would produce identical files)
# Environment: TAU=<m> TSR threshold (default 0.25, indoor); ALGOS="fastlio2 fastlivo2 orbslam3".
set -eo pipefail
BAG=$1; COND=$2; OUT=${3%/}; RUNS=${4:-3}; SCALE=${5:-1.0}
TAU=${TAU:-0.25}; ALGOS=${ALGOS:-"fastlio2 fastlivo2 orbslam3"}
# Host paths map into containers only under output/ (mounted at /output).
for p in "$BAG" "$OUT"; do
  case "$p" in output/*) ;; *) echo "!! '$p' must be a path under output/, relative to the project root"; exit 1;; esac
done
[ -f compose.yaml ] || { echo "!! run from the project root"; exit 1; }
case "$COND" in *__*) echo "!! condition name '$COND' must not contain '__' (it separates the fields of every file name)"; exit 1;; esac
C="docker compose run --rm -T"
RP="bash /scripts/common/ros_python.sh"
IN=/$OUT/bags/${COND}__imu${SCALE}.bag
EU=euroc_${COND}__imu${SCALE}          # ORB-SLAM3's input carries the IMU, so its name carries the scale
mkdir -p "$OUT"/{bags,gt,eval,orbslam3,fastlio2,fastlivo2}
# containers write as root; hand everything back so the host can delete re-creatable files
trap '$C eval chown -R $(id -u):$(id -g) /$OUT >/dev/null 2>&1 || true' EXIT
echo "== $(date -Is)  bag=$BAG cond=$COND runs=$RUNS imu-scale=$SCALE tau=$TAU  git=$(git rev-parse --short HEAD)"

echo "== inject IMU noise (x$SCALE) and extract ground truth"
# The noised copy, the ground truth and every run in $OUT belong to ONE recording. If the
# source bag was recorded again under the same name, reusing them would silently score the
# earlier recording (it happened: a flight was re-flown, the re-run reused the old data).
if [ -s ".$IN" ] && [ "$BAG" -nt ".$IN" ]; then
  echo "!! $BAG is newer than $OUT/bags/$(basename "$IN"): everything in $OUT comes from an EARLIER"
  echo "   recording of that bag. Move $OUT aside (or choose another output directory) and run again."
  exit 1
fi
if [ -s ".$IN" ] && [ -s "$OUT/gt/$COND.tum" ] && [ -s "$OUT/orbslam3/$EU/times.txt" ]; then
  echo "   reusing $IN, gt/$COND.tum, orbslam3/$EU"
else
  $C eval bash -c "$RP /scripts/common/imu_noise.py /$BAG $IN --scale $SCALE --seed 1 && \
                   $RP /scripts/common/bag_to_tum.py $IN /ground_truth/odom /$OUT/gt/$COND.tum && \
                   $RP /scripts/common/bag_to_euroc.py $IN /$OUT/orbslam3/$EU"
fi

for r in $(seq 1 "$RUNS"); do
  for algo in fastlio2 fastlivo2; do
    case " $ALGOS " in *" $algo "*) ;; *) continue;; esac
    topic=/Odometry; proc=fastlio_mapping
    [ $algo = fastlivo2 ] && { topic=/aft_mapped_to_init; proc=fastlivo_mapping; }
    name=${algo}__${COND}__r$r
    echo "== $name"
    if [ $algo = fastlio2 ]; then
      $C -e LATENCY=1 -e COST_PROC=$proc $algo bash /scripts/common/run_ros_algo.sh \
          /config/launch/$algo.launch "$IN" "$topic" "/$OUT/$algo/$name.bag" 1.0
      # bag_to_tum.py exits non-zero on an empty topic; an algorithm that published
      # nothing must become a scored failure, not abort the batch
      $C eval $RP /scripts/common/bag_to_tum.py "/$OUT/$algo/$name.bag" "$topic" "/$OUT/$algo/$name.tum" \
          || : > "$OUT/$algo/$name.tum"
    else
      # FAST-LIVO2 stamps /aft_mapped_to_init with ros::Time::now() at publish. Its own pose
      # file (evo/pose_output_en, Log/result/sim.txt) carries the same poses stamped with the
      # state time; that is what gets scored (as in Stage 1). topic stamp - state time is its
      # true output latency.
      E="$OUT/$algo/evo_$name"; rm -rf "$E"; mkdir -p "$E"
      $C -v "$PWD/$E:/ws/src/FAST-LIVO2/Log/result" -e COST_PROC=$proc $algo \
          bash /scripts/common/run_ros_algo.sh /config/launch/$algo.launch "$IN" "$topic" "/$OUT/$algo/$name.bag" 1.0
      $C eval $RP /scripts/common/bag_to_tum.py "/$OUT/$algo/$name.bag" "$topic" "/$OUT/$algo/$name.topic.tum" \
          || : > "$OUT/$algo/$name.topic.tum"
      cp "$E/sim.txt" "$OUT/$algo/$name.tum" 2>/dev/null || : > "$OUT/$algo/$name.tum"
      if [ "$(wc -l < "$OUT/$algo/$name.tum")" = "$(wc -l < "$OUT/$algo/$name.topic.tum")" ]; then
        paste -d' ' "$OUT/$algo/$name.tum" "$OUT/$algo/$name.topic.tum" | \
          awk 'BEGIN{print "stamp_s,latency_ms"} {printf "%.6f,%.3f\n", $1, ($9-$1)*1000}' > "$OUT/$algo/$name.latency.csv"
      else
        echo "!! $name: pose file and topic differ in length; no latency"; rm -f "$OUT/$algo/$name.latency.csv"
      fi
    fi
  done
  case " $ALGOS " in *" orbslam3 "*) ;; *) continue;; esac
  name=orbslam3__${COND}__r$r
  echo "== $name"
  # stale outputs of an earlier run with the same name must never be scored as this run
  rm -f "$OUT/orbslam3/f_$name.txt" "$OUT/orbslam3/kf_$name.txt" "$OUT/orbslam3/$name.tum" \
        "$OUT/orbslam3/orbslam3kf__${COND}__r$r.tum" "$OUT/orbslam3/$name.cost.csv"
  $C orbslam3 bash -c "cd /$OUT/orbslam3 && \
      { python3 /scripts/common/cost_probe.py stereo_inertial_euroc $name.cost.csv > $name.cost.log 2>&1 & P=\$!; } && \
      /opt/ORB_SLAM3/Examples/Stereo-Inertial/stereo_inertial_euroc \
      /opt/ORB_SLAM3/Vocabulary/ORBvoc.txt /config/generated/orbslam3_sim.yaml \
      /$OUT/orbslam3/$EU /$OUT/orbslam3/$EU/times.txt $name > $name.log 2>&1; \
      wait \$P; \
      touch f_$name.txt kf_$name.txt; \
      awk '{printf \"%.9f %s %s %s %s %s %s %s\\n\", \$1/1e9, \$2,\$3,\$4,\$5,\$6,\$7,\$8}' f_$name.txt > $name.tum; \
      awk '{printf \"%.9f %s %s %s %s %s %s %s\\n\", \$1/1e9, \$2,\$3,\$4,\$5,\$6,\$7,\$8}' kf_$name.txt > orbslam3kf__${COND}__r$r.tum; \
      grep -c 'New Map created' $name.log | sed 's/^/   maps created: /'"
done

echo "== score"
for f in "$OUT"/{fastlio2,fastlivo2,orbslam3}/*__${COND}__r*.tum; do
  [ -e "$f" ] || continue
  case "$f" in *.topic.tum) continue;; esac          # FAST-LIVO2's publish-time stamps (A8)
  b=$(basename "${f%.tum}"); d=$(dirname "$f")
  rm -f "$OUT/eval/${b}"_{ape,rpe}.{zip,txt,pdf} "$OUT/eval/${b}"_{coverage.txt,extra.json,errors.csv}
  # A failed run is a RESULT: it gets a record (TSR 0, coverage 0) so that the summary's
  # "worst" columns and run count show it instead of silently reporting the survivors.
  failed() { echo "!! $1: $b"; echo '{"failed": true, "tsr": 0.0, "tsr_start": 0.0, "coverage_air": 0.0, "coverage_bag": 0.0}' > "$OUT/eval/${b}_extra.json"; }
  [ -s "$f" ] || { failed "empty trajectory (algorithm failed; see its .log)"; continue; }
  # orbslam3kf's cost belongs to the orbslam3 run that wrote it
  c=${b/orbslam3kf__/orbslam3__}
  $C eval bash -c "bash /scripts/common/eval_traj.sh /$OUT/gt/$COND.tum /$f /$OUT/eval/$b && \
      python3 /scripts/common/metrics_extra.py /$OUT/gt/$COND.tum /$f /$OUT/eval/$b --tau $TAU \
          --cost /$d/$c.cost.csv --latency /$d/$b.latency.csv" || failed "scoring failed (too few poses?)"
done
$C eval python3 /scripts/common/results_table.py "/$OUT/eval"
