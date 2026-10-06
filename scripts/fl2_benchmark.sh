#!/usr/bin/env bash
# Host-side orchestrator for the FAST-LIO2 paper benchmark.
# Repeatedly scans the sequence list; whenever a sequence's input data is fully
# downloaded and it does not yet have RUNS run bags, it prepares and runs it:
#   - Velodyne data: checks the measured per-point time unit against the config
#     (fl2_cloudcheck.py) and refuses to run on a mismatch
#   - builds ground truth / GNSS reference where the paper's metric needs it
#   - NCLT: converts raw data with the authors' converter, runs, then deletes the
#     converted bag (tens of GB) unless KEEP_NCLT_BAGS=1
#   - RUNS runs in parallel containers (fl2_parallel.sh)
# Finally runs eval_fastlio2.sh once everything available is done.
#   bash scripts/fl2_benchmark.sh            # all sequences, waits for downloads
#   ONLY="utbm8 nclt5" bash scripts/fl2_benchmark.sh
#   WAIT=0 bash scripts/fl2_benchmark.sh     # do what is ready now, then stop
set -uo pipefail
cd "$(dirname "$0")/.."
RUNS=${RUNS:-5}; WAIT=${WAIT:-1}
OUT=output/fastlio2; mkdir -p "$OUT"
LOG=$OUT/benchmark.log
log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
dc() { docker compose run --rm -T "$@" 2>&1 | grep -vE '^ ?(Container|Network) '; }

# seq | kind | input (host path relative to repo) | config | extra
SEQS="
lili6_schloss1|lili|data/lili/KA_Urban_Schloss_1.bag|lili.yaml|
lili7_schloss2|lili|data/lili/KA_Urban_Schloss_2.bag|lili.yaml|
lili8_east|lili|data/lili/KA_Urban_East.bag|lili.yaml|
liosam2_garden|velo|data/liosam/garden_dataset.bag|liosam_park_garden.yaml|points_raw
liosam1_park|velo_gps|data/liosam/park_dataset.bag|liosam_park_garden.yaml|points_raw
liosam3_campus|velo|data/liosam/campus_large_dataset.bag|liosam_campus.yaml|points_raw
utbm8|utbm|data/utbm/utbm_20180719.bag|utbm.yaml|
utbm9|utbm|data/utbm/utbm_20190131.bag|utbm.yaml|
utbm10|utbm|data/utbm/utbm_20190418.bag|utbm.yaml|
nclt9|nclt|2013-01-10|nclt.yaml|points_raw
nclt5|nclt|2012-04-29|nclt.yaml|points_raw
nclt7|nclt|2012-06-15|nclt.yaml|points_raw
nclt8|nclt|2012-12-01|nclt.yaml|points_raw
nclt10|nclt|2013-04-05|nclt.yaml|points_raw
nclt6|nclt|2012-05-11|nclt.yaml|points_raw
nclt4|nclt|2012-01-15|nclt.yaml|points_raw
"

complete() {   # a download is complete when no aria2 control file / gdown .part remains
  [ -s "$1" ] && [ ! -e "$1.aria2" ] && ! ls "$1"*.part >/dev/null 2>&1
}
ready() {
  local kind=$1 input=$2
  if [ "$kind" = nclt ]; then
    [ -s "data/nclt/$input.bag" ] && return 0
    complete "data/nclt/raw/${input}_sen.tar.gz" && complete "data/nclt/raw/${input}_vel.tar.gz" \
      && complete "data/nclt_gt/groundtruth_$input.csv"
  else
    complete "$input"
  fi
}
done_runs() { ls "$OUT/$1"_r*.bag 2>/dev/null | grep -cE "_r[0-9]+\.bag$"; }

check_unit() {  # $1 container bag path, $2 topic, $3 config -> 0 if the config unit matches the data
  local want got
  want=$(awk '/timestamp_unit:/{print $2; exit}' "config/fastlio2/$3")
  got=$(dc eval python3 /scripts/fl2_cloudcheck.py "$1" "$2" 20 | tee -a "$LOG" | sed -n 's/.*timestamp_unit: \([0-9]\).*/\1/p')
  if [ -z "$got" ]; then log "!! $1: could not determine time unit -- see log"; return 1; fi
  [ "$got" = "$want" ] || { log "!! $1: data says timestamp_unit $got, $3 says $want -- NOT RUNNING, fix the config"; return 1; }
  log "   time unit OK ($got) for $1"
}

process() {
  local seq=$1 kind=$2 input=$3 cfg=$4 topic=$5 bag
  log "== $seq ($kind): starting"
  case $kind in
    lili)
      bag=/data/${input#data/}
      [ -s "$OUT/gnssref_$seq.tum" ] || dc eval python3 /scripts/fl2_gt.py bag "$bag" /gnss "/output/fastlio2/gnssref_$seq.tum" | tee -a "$LOG"
      bash scripts/fl2_parallel.sh "$RUNS" run_fastlio2.sh "/config/fastlio2/$cfg" "$bag" "$seq" | tee -a "$LOG" ;;
    velo|velo_gps)
      bag=/data/${input#data/}
      check_unit "$bag" "$topic" "$cfg" || return 1
      if [ "$kind" = velo_gps ] && [ ! -s "$OUT/gt_$seq.tum" ]; then
        local fix
        fix=$(dc fastlio2 bash -c "source /opt/ros/noetic/setup.bash; rosbag info -y -k topics $bag" \
              | awk '/topic:/{t=$2} /type: sensor_msgs\/NavSatFix/{print t; exit}')
        [ -n "$fix" ] || { log "!! $seq: no NavSatFix topic in bag"; return 1; }
        log "   GPS topic $fix"
        dc eval python3 /scripts/fl2_gt.py bag "$bag" "$fix" "/output/fastlio2/gt_$seq.tum" | tee -a "$LOG"
      fi
      bash scripts/fl2_parallel.sh "$RUNS" run_fastlio2.sh "/config/fastlio2/$cfg" "$bag" "$seq" | tee -a "$LOG" ;;
    utbm)
      bag=/data/${input#data/}
      if [ ! -s "$OUT/gt_$seq.tum" ]; then
        dc fastlio2 bash /scripts/utbm_gt.sh "$bag" "$seq" | tee -a "$LOG"
        dc eval python3 /scripts/fl2_gt.py bag "/output/fastlio2/${seq}_fix.bag" /fix "/output/fastlio2/gt_$seq.tum" | tee -a "$LOG"
      fi
      bash scripts/fl2_parallel.sh "$RUNS" run_fastlio2_utbm.sh "$bag" "$seq" | tee -a "$LOG" ;;
    nclt)
      [ -s "data/nclt/$input.bag" ] || dc -v "$PWD/data/nclt:/nclt" fastlio2 bash /scripts/nclt_to_bag.sh "$input" | tee -a "$LOG"
      [ -s "data/nclt/$input.bag" ] || { log "!! $seq: conversion failed"; return 1; }
      check_unit "/data/nclt/$input.bag" "$topic" "$cfg" || return 1
      [ -s "$OUT/gt_$seq.tum" ] || dc eval python3 /scripts/fl2_gt.py nclt "/data/nclt_gt/groundtruth_$input.csv" "/output/fastlio2/gt_$seq.tum" | tee -a "$LOG"
      bash scripts/fl2_parallel.sh "$RUNS" run_fastlio2.sh "/config/fastlio2/$cfg" "/data/nclt/$input.bag" "$seq" | tee -a "$LOG"
      if [ "$(done_runs "$seq")" -ge "$RUNS" ] && [ "${KEEP_NCLT_BAGS:-0}" != 1 ]; then
        rm -f "data/nclt/$input.bag" && log "   removed converted data/nclt/$input.bag (re-create with nclt_to_bag.sh)"
      fi ;;
  esac
  log "== $seq: $(done_runs "$seq") run bags"
}

declare -A failed=()
while :; do
  pending=0
  while IFS='|' read -r seq kind input cfg topic; do
    [ -n "$seq" ] || continue
    if [ -n "${ONLY:-}" ] && ! grep -qw "$seq" <<<"$ONLY"; then continue; fi
    [ "$(done_runs "$seq")" -ge "$RUNS" ] && continue
    [ -n "${failed[$seq]:-}" ] && continue
    if ready "$kind" "$input"; then
      process "$seq" "$kind" "$input" "$cfg" "$topic" || failed[$seq]=1
    else
      pending=$((pending + 1))
    fi
  done <<<"$SEQS"
  [ "$pending" -eq 0 ] || [ "$WAIT" = 0 ] && break
  sleep 120
done
[ ${#failed[@]} -eq 0 ] || log "!! failed: ${!failed[*]}"
log "== evaluating"
dc eval bash /scripts/eval_fastlio2.sh | tee -a "$LOG" | grep -E '^\||wrote'
