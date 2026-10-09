#!/usr/bin/env bash
# FAST-LIO2 review runs (2026-10-09). Re-runs sequences into a separate folder so the
# committed results in output/fastlio2 stay untouched; ground truth is linked, not copied.
#   bash scripts/fl2_review.sh <variant> <seq...>
#   variant v2        : evtol/fastlio2:v1 (FAST_LIO HEAD 7cc4175) with the corrected configs
#   variant paper2021 : evtol/fastlio2:paper2021 (FAST_LIO f159d57, the paper's July-2021 code)
#   LILI_CFG=lili_xsens.yaml TAG=_xsens  -> lili with the Xsens IMU, into output/fastlio2_<variant>_xsens
# Then score:  docker compose run --rm -T -e IN=/output/fastlio2_<variant> eval bash /scripts/eval_fastlio2.sh
set -uo pipefail
cd "$(dirname "$0")/.."
V=$1; shift; RUNS=${RUNS:-5}
case $V in
  v2) SVC=fastlio2 ;;
  paper2021) SVC=fastlio2_paper2021 ;;
  *) echo "variant must be v2 or paper2021"; exit 1 ;;
esac
D=fastlio2_$V${TAG:-}                    # TAG: suffix for a config variant, e.g. TAG=_xsens
OUT=output/$D; mkdir -p "$OUT"
LILI=${LILI_CFG:-lili.yaml}
for f in output/fastlio2/gt_*.tum output/fastlio2/gnssref_*.tum; do
  ln -sfn "../fastlio2/$(basename "$f")" "$OUT/$(basename "$f")"
done
C=/config/fastlio2
for seq in "$@"; do
  case $seq in
    lili6_schloss1) a=(run_fastlio2.sh $C/$LILI /data/lili/KA_Urban_Schloss_1.bag) ;;
    lili7_schloss2) a=(run_fastlio2.sh $C/$LILI /data/lili/KA_Urban_Schloss_2.bag) ;;
    lili8_east)     a=(run_fastlio2.sh $C/$LILI /data/lili/KA_Urban_East.bag) ;;
    liosam1_park)   a=(run_fastlio2.sh $C/liosam_park_garden.yaml /data/liosam/park_dataset.bag) ;;
    liosam2_garden) a=(run_fastlio2.sh $C/liosam_park_garden.yaml /data/liosam/garden_dataset.bag) ;;
    liosam3_campus) a=(run_fastlio2.sh $C/liosam_campus.yaml /data/liosam/campus_large_dataset.bag) ;;
    utbm8)          a=(run_fastlio2_utbm.sh /data/utbm/utbm_20180719.bag) ;;
    utbm9)          a=(run_fastlio2_utbm.sh /data/utbm/utbm_20190131.bag) ;;
    utbm10)         a=(run_fastlio2_utbm.sh /data/utbm/utbm_20190418.bag) ;;
    nclt*)          a=(run_fastlio2.sh $C/nclt.yaml "/data/nclt/${NCLT_DATE:?set NCLT_DATE}.bag") ;;
    *) echo "!! unknown sequence $seq"; continue ;;
  esac
  echo "[$(date '+%F %T')] == $V $seq"
  SERVICE=$SVC DOCKER_ARGS="-e OUTDIR=/output/$D" bash scripts/fl2_parallel.sh "$RUNS" "${a[@]}" "$seq"
done
docker run --rm -v "$PWD/output:/o" evtol/eval:v1 chown -R "$(id -u):$(id -g)" "/o/$D" 2>/dev/null
echo "[$(date '+%F %T')] == $V done: $*"
