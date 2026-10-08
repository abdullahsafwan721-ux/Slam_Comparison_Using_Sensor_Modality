#!/usr/bin/env bash
# Host-side orchestrator for the FAST-LIVO2 benchmark (NTU-VIRAL + private dataset).
# Repeatedly scans the sequence list; whenever a sequence's bag is fully on disk and it
# has fewer than RUNS trajectories, it runs RUNS parallel containers (fl2_parallel.sh),
# then evaluates once everything available is done.
#   bash scripts/livo2_benchmark.sh               # waits for pending downloads
#   WAIT=0 bash scripts/livo2_benchmark.sh        # do what is ready now, then stop
# Long jobs: start it as a systemd user unit so a closed terminal cannot kill it:
#   systemd-run --user --unit=livo2-bench --collect --working-directory="$PWD" bash scripts/livo2_benchmark.sh
set -uo pipefail
cd "$(dirname "$0")/.."
RUNS=${RUNS:-5}; WAIT=${WAIT:-1}
OUT=output/fastlivo2; mkdir -p "$OUT"; LOG=$OUT/benchmark.log
log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

# seq | host bag path | config | camera config
# Private dataset: per-sequence calibration groups from the dataset's calibration.yaml
# (config/fastlivo2/private_dataset_calibration.yaml). Its images are raw, so no republish.
SEQS="
eee_01|data/ntu_viral/eee_01/eee_01/eee_01.bag|NTU_VIRAL.yaml|camera_NTU_VIRAL.yaml
eee_02|data/ntu_viral/eee_02/eee_02/eee_02.bag|NTU_VIRAL.yaml|camera_NTU_VIRAL.yaml
eee_03|data/ntu_viral/eee_03/eee_03/eee_03.bag|NTU_VIRAL.yaml|camera_NTU_VIRAL.yaml
nya_01|data/ntu_viral/nya_01/nya_01/nya_01.bag|NTU_VIRAL.yaml|camera_NTU_VIRAL.yaml
nya_02|data/ntu_viral/nya_02/nya_02/nya_02.bag|NTU_VIRAL.yaml|camera_NTU_VIRAL.yaml
nya_03|data/ntu_viral/nya_03/nya_03/nya_03.bag|NTU_VIRAL.yaml|camera_NTU_VIRAL.yaml
sbs_01|data/ntu_viral/sbs_01/sbs_01/sbs_01.bag|NTU_VIRAL.yaml|camera_NTU_VIRAL.yaml
sbs_02|data/ntu_viral/sbs_02/sbs_02/sbs_02.bag|NTU_VIRAL.yaml|camera_NTU_VIRAL.yaml
sbs_03|data/ntu_viral/sbs_03/sbs_03/sbs_03.bag|NTU_VIRAL.yaml|camera_NTU_VIRAL.yaml
hku_landmark|data/fastlivo2_private/HKU_Landmark.bag|avia_private_g2.yaml|camera_private_g2.yaml
cbd_building_01|data/fastlivo2_private/CBD_Building_01.bag|avia_private_g1.yaml|camera_private_g1.yaml
sysu_01|data/fastlivo2_private/SYSU_01.bag|avia_private_g3.yaml|camera_private_g3.yaml
cbd_building_03|data/fastlivo2_private/CBD_Building_03.bag|avia_private_g2.yaml|camera_private_g2.yaml
hku_cultural_center_01|data/fastlivo2_private/HKU_Cultural_Center_01.bag|avia_private_g2.yaml|camera_private_g2.yaml
hku_cultural_center_02|data/fastlivo2_private/HKU_Cultural_Center_02.bag|avia_private_g2.yaml|camera_private_g2.yaml
"
done_runs() { ls "$OUT/$1"_r*.txt 2>/dev/null | grep -cE "_r[0-9]+\.txt$"; }

while :; do
  pending=0
  while IFS='|' read -r seq bag cfg cam <&3; do
    [ -n "$seq" ] || continue
    [ "$(done_runs "$seq")" -ge "$RUNS" ] && continue
    # complete = bag present, no Drive "<bag>.part", and no NTU "<seq>.zip(.part)" left
    # (the NTU downloader extracts in place and deletes the zip only after unzip finished)
    base=$(basename "$bag" .bag)
    if [ -s "$bag" ] && ! ls "$bag".part data/ntu_viral/"$base".zip* >/dev/null 2>&1; then
      mkdir "$OUT/.lock_$seq" 2>/dev/null || { pending=$((pending + 1)); continue; }
      log "== $seq: starting ($cfg, $cam)"
      SERVICE=fastlivo2 bash scripts/fl2_parallel.sh "$RUNS" run_fastlivo2.sh \
          "/config/fastlivo2/$cfg" "/config/fastlivo2/$cam" "/$bag" "$seq" </dev/null | tee -a "$LOG"
      log "== $seq: $(done_runs "$seq") trajectories"
      rmdir "$OUT/.lock_$seq"
    else
      pending=$((pending + 1))
    fi
  done 3<<<"$SEQS"
  { [ "$pending" -eq 0 ] || [ "$WAIT" = 0 ]; } && break
  sleep 120
done
docker run --rm -v "$PWD/output:/o" evtol/eval:v1 chown -R "$(id -u):$(id -g)" /o/fastlivo2 /o/results 2>/dev/null
log "== evaluating"
docker compose run --rm -T eval bash -c '
  for s in eee_01 eee_02 eee_03 nya_01 nya_02 nya_03 sbs_01 sbs_02 sbs_03; do
    [ -s /output/fastlivo2/gt_$s.tum ] || python3 /scripts/viral_prep.py gt \
        /data/ntu_viral/viral_eval/result_$s/leica_pose.csv /output/fastlivo2/gt_$s.tum
  done
  bash /scripts/eval_fastlivo2.sh' </dev/null 2>&1 | tee -a "$LOG" | grep -E '^\||wrote /output/results'
