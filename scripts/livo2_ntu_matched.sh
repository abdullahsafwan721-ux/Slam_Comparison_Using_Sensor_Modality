#!/usr/bin/env bash
# Host-side: NTU-VIRAL "matched start" protocol for FAST-LIVO2.
# The authors' shipped trajectories (Log/result/ntu_viral/<seq>_prism.txt) start 0-0.5 s
# after the bag's first LiDAR scan on some sequences -- their rosbag play evidently began
# before the node had subscribed, so the first scans were never seen. Initialisation then
# differs, and on eee_02 that alone moves ATE from 2.98 to 2.29 cm (repo: 2.11 cm).
# This replays each sequence from the authors' own first pose time:
#   offset = first stamp of <seq>_prism.txt  -  first stamp of our clean run (<seq>_r1.txt)
# and writes to /output/fastlivo2_matched. The clean protocol (all data) stays the main result.
#   bash scripts/livo2_ntu_matched.sh            # RUNS=5
set -uo pipefail
cd "$(dirname "$0")/.."
RUNS=${RUNS:-5}; OUT=output/fastlivo2_matched; mkdir -p "$OUT"
for s in eee_01 eee_02 eee_03 nya_01 nya_02 nya_03 sbs_01 sbs_02 sbs_03; do
  ref=data/ntu_viral/reference/${s}_prism.txt; clean=output/fastlivo2/${s}_r1.txt
  [ -s "$ref" ] && [ -s "$clean" ] || { echo "-- $s: missing reference or clean run"; continue; }
  off=$(python3 -c "import sys; a=float(open(sys.argv[1]).readline().split()[0]); b=float(open(sys.argv[2]).readline().split()[0]); print('%.3f' % max(a-b, 0.0))" "$ref" "$clean")
  n=$(ls $OUT/${s}_r*.txt 2>/dev/null | grep -cE "_r[0-9]+\.txt$")
  [ "$n" -ge "$RUNS" ] && { echo "-- $s: already $n runs"; continue; }
  cp output/fastlivo2/gt_$s.tum $OUT/ 2>/dev/null
  echo "== $s: start offset $off s"
  extra=(); [ "$off" != "0.000" ] && extra=(-s "$off")
  DOCKER_ARGS="-e OUTDIR=/output/fastlivo2_matched" SERVICE=fastlivo2 bash scripts/fl2_parallel.sh "$RUNS" run_fastlivo2.sh \
      /config/fastlivo2/NTU_VIRAL.yaml /config/fastlivo2/camera_NTU_VIRAL.yaml /data/ntu_viral/$s/$s/$s.bag "$s" "${extra[@]}" </dev/null
done
docker compose run --rm -T eval bash -c 'IN=/output/fastlivo2_matched RESULTS=/output/results/fastlivo2_matched_$(date +%Y%m%d_%H%M%S) bash /scripts/eval_fastlivo2.sh' </dev/null 2>&1 | grep -E '^\||wrote /output/results'
