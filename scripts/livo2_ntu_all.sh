#!/usr/bin/env bash
# Host-side: run FAST-LIVO2 RUNS times on every NTU-VIRAL sequence whose bag is on
# disk and which does not have RUNS trajectories yet, PAR sequences at a time, then
# build ground truth (once) and score everything.
#   bash scripts/livo2_ntu_all.sh            # RUNS=5 PAR=2
set -uo pipefail
cd "$(dirname "$0")/.."
RUNS=${RUNS:-5}; PAR=${PAR:-2}
todo=()
for s in eee_01 eee_02 eee_03 nya_01 nya_02 nya_03 sbs_01 sbs_02 sbs_03; do
  [ -s "data/ntu_viral/$s/$s/$s.bag" ] || { echo "-- $s: bag not on disk yet"; continue; }
  n=$(ls output/fastlivo2/${s}_r*.txt 2>/dev/null | grep -cE "_r[0-9]+\.txt$")
  [ "$n" -ge "$RUNS" ] && { echo "-- $s: already $n runs"; continue; }
  todo+=("$s")
done
echo "== running: ${todo[*]:-nothing}"
printf '%s\n' "${todo[@]}" | xargs -r -P "$PAR" -I{} bash -c '
  SERVICE=fastlivo2 bash scripts/fl2_parallel.sh '"$RUNS"' run_fastlivo2.sh \
    /config/fastlivo2/NTU_VIRAL.yaml /config/fastlivo2/camera_NTU_VIRAL.yaml \
    /data/ntu_viral/{}/{}/{}.bag {} | sed "s/^/[{}] /"'
docker compose run --rm -T eval bash -c '
  for s in eee_01 eee_02 eee_03 nya_01 nya_02 nya_03 sbs_01 sbs_02 sbs_03; do
    [ -s /output/fastlivo2/gt_$s.tum ] || python3 /scripts/viral_prep.py gt \
        /data/ntu_viral/viral_eval/result_$s/leica_pose.csv /output/fastlivo2/gt_$s.tum
  done
  bash /scripts/eval_fastlivo2.sh' </dev/null 2>&1 | grep -E '^\||wrote /output/results'
