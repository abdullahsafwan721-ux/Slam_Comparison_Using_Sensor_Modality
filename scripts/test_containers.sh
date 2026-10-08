#!/usr/bin/env bash
# Test suite for the FAST-LIO2 and FAST-LIVO2 containers. Run on the host, from anywhere.
#   bash scripts/test_containers.sh quick        # L0 image self-tests + L1 evaluation chain (~3 min)
#   bash scripts/test_containers.sh functional   # L2 one short real run per algorithm (~8 min)
#   bash scripts/test_containers.sh all          # L0 + L1 + L2
# Prints PASS / FAIL / SKIP per check; exit code = number of failures.
# L1 re-scores runs already stored in output/ and the authors' shipped NTU-VIRAL files.
# L2 writes only to output/tests/ (never into the benchmark folders).
set -uo pipefail
cd "$(dirname "$0")/.."
MODE=${1:-quick}
PASS=0; FAIL=0; SKIP=0
ok()   { echo "  PASS  $*"; PASS=$((PASS + 1)); }
bad()  { echo "  FAIL  $*"; FAIL=$((FAIL + 1)); }
skip() { echo "  SKIP  $*"; SKIP=$((SKIP + 1)); }
has()  { if grep -q -- "$2" <<<"$3"; then ok "$1"; else bad "$1"; fi; }
# value within tolerance of expected:  near <desc> <value> <expected> <tol>
near() {
  if python3 -c "import sys; v,e,t=map(float,sys.argv[1:]); sys.exit(0 if abs(v-e)<=t else 1)" "$2" "$3" "$4" 2>/dev/null
  then ok "$1 = $2 (expected $3 +/- $4)"; else bad "$1 = ${2:-none} (expected $3 +/- $4)"; fi
}
dc() { docker compose run --rm -T "$@" </dev/null 2>/dev/null; }

level0() {
  echo "== L0: images and container self-tests"
  for img in evtol/base:noetic evtol/fastlio2:v1 evtol/fastlivo2:v1 evtol/eval:v1; do
    if docker image inspect "$img" >/dev/null 2>&1; then ok "image $img"; else bad "image $img (build it first)"; fi
  done
  local o
  o=$(dc fastlio2 bash -c 'source /opt/ros/noetic/setup.bash; source /ws/devel/setup.bash
      test -f /ws/devel/lib/fast_lio/fastlio_mapping && echo BIN_OK
      rospack find velodyne_pointcloud >/dev/null && echo VELO_OK
      rospack find nmea_navsat_driver >/dev/null && echo NMEA_OK
      echo "SDK=$(cd /opt/Livox-SDK && git describe --tags)"
      echo "DRV=$(cd /ws/src/livox_ros_driver && git rev-parse HEAD)"
      echo "FL=$(cd /ws/src/FAST_LIO && git rev-parse HEAD)"')
  has "fastlio2: fastlio_mapping binary"            BIN_OK "$o"
  has "fastlio2: velodyne_pointcloud (UTBM)"        VELO_OK "$o"
  has "fastlio2: nmea_navsat_driver (UTBM)"         NMEA_OK "$o"
  has "fastlio2: Livox-SDK pinned v2.3.1"           "SDK=v2.3.1" "$o"
  has "fastlio2: livox_ros_driver pin fb5669b"      "DRV=fb5669b90af07915c1870d106cc1e4e1ef1f5a15" "$o"
  has "fastlio2: FAST_LIO pin 7cc4175"              "FL=7cc4175de6f8ba2edf34bab02a42195b141027e9" "$o"
  o=$(dc fastlivo2 bash -c 'source /opt/ros/noetic/setup.bash; source /ws/devel/setup.bash
      test -f /ws/devel/lib/fast_livo/fastlivo_mapping && echo BIN_OK
      test -f /usr/local/lib/libSophus.so && echo SOPHUS_OK
      rospack find vikit_common >/dev/null && echo VIKIT_OK
      rospack find compressed_image_transport >/dev/null && echo COMPRESSED_OK
      echo "LIVO=$(cd /ws/src/FAST-LIVO2 && git rev-parse HEAD)"
      z=0; for f in /ws/devel/lib/*.so /usr/local/lib/libSophus.so; do z=$((z + $(objdump -d $f | grep -c zmm))); done
      echo "ZMM=$z"')
  has "fastlivo2: fastlivo_mapping binary"          BIN_OK "$o"
  has "fastlivo2: Sophus installed"                 SOPHUS_OK "$o"
  has "fastlivo2: vikit_common"                     VIKIT_OK "$o"
  has "fastlivo2: compressed image plugin"          COMPRESSED_OK "$o"
  has "fastlivo2: FAST-LIVO2 pin 0d2c034"           "LIVO=0d2c0346107b75b59934975adec9a6eeeb913c64" "$o"
  has "fastlivo2: no AVX-512 code (Skylake build)"  "ZMM=0$" "$o"
  o=$(dc eval bash -c 'echo "EVO=$(pip3 show evo 2>/dev/null | sed -n "s/^Version: //p")"; python3 /scripts/fl2_traj.py 2>&1 | grep -m1 "Odometry bag"')
  has "eval: evo 1.31.1"                            "EVO=1.31.1" "$o"
  has "eval: ROS rosbag usable from helper scripts" "Odometry bag -> TUM" "$o"
}

level1() {
  echo "== L1: evaluation chain reproduces published / stored numbers"
  # FAST-LIVO2 gate: the authors' own shipped NTU-VIRAL trajectories vs their README (cm)
  if [ -s data/ntu_viral/reference/eee_01_prism.txt ]; then
    local o s r
    o=$(dc eval bash -c 'cd /data/ntu_viral/reference; for s in eee_01 eee_02 eee_03 nya_01 nya_02 nya_03 sbs_01 sbs_02 sbs_03; do
          echo "$s $(evo_ape tum ${s}_gt.txt ${s}_prism.txt -a 2>/dev/null | awk "/^ *rmse/{print \$2}")"; done')
    for sr in eee_01:0.0271 eee_02:0.0211 eee_03:0.0261 nya_01:0.0356 nya_02:0.0339 nya_03:0.0352 sbs_01:0.0234 sbs_02:0.0283 sbs_03:0.0311; do
      s=${sr%%:*}; r=$(awk -v s="$s" '$1==s{print $2}' <<<"$o")
      near "fastlivo2 gate: authors' $s" "$r" "${sr##*:}" 0.00015
    done
  else skip "fastlivo2 gate (data/ntu_viral/reference missing)"; fi
  # stored runs re-scored with the eval container: FAST-LIO2
  if [ -s output/fastlio2/nclt9_r1.tum ] && [ -s output/fastlio2/gt_nclt9.tum ]; then
    near "fastlio2 nclt9_r1 ATE (m)" "$(dc eval bash -c 'evo_ape tum /output/fastlio2/gt_nclt9.tum /output/fastlio2/nclt9_r1.tum --align --t_max_diff 0.02 2>/dev/null | awk "/^ *rmse/{print \$2}"')" 0.954287 0.0001
  else skip "fastlio2 nclt9_r1 (no stored run)"; fi
  if [ -s output/fastlio2/utbm8_r1.tum ] && [ -s output/fastlio2/gt_utbm8.tum ]; then
    near "fastlio2 utbm8_r1 ATE (m)" "$(dc eval bash -c 'evo_ape tum /output/fastlio2/gt_utbm8.tum /output/fastlio2/utbm8_r1.tum --align --t_max_diff 0.02 2>/dev/null | awk "/^ *rmse/{print \$2}"')" 12.795859 0.001
  else skip "fastlio2 utbm8_r1 (no stored run)"; fi
  if [ -s output/fastlio2/liosam2_garden_r1.tum ]; then
    near "fastlio2 liosam2_garden_r1 end-to-end (m)" "$(python3 scripts/fl2_drift.py output/fastlio2/liosam2_garden_r1.tum | awk '/end-to-end/{print $3}')" 0.027 0.0005
  else skip "fastlio2 garden_r1 (no stored run)"; fi
  # stored runs re-scored: FAST-LIVO2
  if [ -s output/fastlivo2/eee_02_r1.txt ] && [ -s output/fastlivo2/gt_eee_02.tum ]; then
    near "fastlivo2 eee_02_r1 ATE (m)" "$(dc eval bash -c 'python3 /scripts/viral_prep.py prism /output/fastlivo2/eee_02_r1.txt /tmp/p.tum >/dev/null && evo_ape tum /output/fastlivo2/gt_eee_02.tum /tmp/p.tum -a 2>/dev/null | awk "/^ *rmse/{print \$2}"')" 0.029931 0.00001
  else skip "fastlivo2 eee_02_r1 (no stored run)"; fi
  if [ -s output/fastlivo2/hku_landmark_r1.txt ]; then
    near "fastlivo2 hku_landmark_r1 end-to-end (m)" "$(python3 scripts/fl2_drift.py output/fastlivo2/hku_landmark_r1.txt | awk '/end-to-end/{print $3}')" 0.004 0.0005
  else skip "fastlivo2 hku_landmark_r1 (no stored run)"; fi
}

level2() {
  echo "== L2: one short real run per algorithm (outputs in output/tests/)"
  mkdir -p output/tests
  local pids=() g h e
  if [ -s data/liosam/garden_dataset.bag ]; then
    dc -e OUTDIR=/output/tests/fastlio2 -e RUNS=1 fastlio2 bash /scripts/run_fastlio2.sh \
       /config/fastlio2/liosam_park_garden.yaml /data/liosam/garden_dataset.bag liosam2_garden > output/tests/fastlio2_garden.log 2>&1 &
    pids+=($!)
  fi
  if [ -s data/fastlivo2_private/HKU_Landmark.bag ]; then
    dc -e OUTDIR=/output/tests/fastlivo2 -e RUNS=1 fastlivo2 bash /scripts/run_fastlivo2.sh \
       /config/fastlivo2/avia_private_g2.yaml /config/fastlivo2/camera_private_g2.yaml \
       /data/fastlivo2_private/HKU_Landmark.bag hku_landmark > output/tests/fastlivo2_landmark.log 2>&1 &
    pids+=($!)
  fi
  if [ -s data/ntu_viral/eee_02/eee_02/eee_02.bag ]; then
    dc -e OUTDIR=/output/tests/fastlivo2 -e RUNS=1 fastlivo2 bash /scripts/run_fastlivo2.sh \
       /config/fastlivo2/NTU_VIRAL.yaml /config/fastlivo2/camera_NTU_VIRAL.yaml \
       /data/ntu_viral/eee_02/eee_02/eee_02.bag eee_02 -s 0.3 > output/tests/fastlivo2_eee02.log 2>&1 &
    pids+=($!)
  fi
  [ ${#pids[@]} -gt 0 ] && echo "  ... ${#pids[@]} run(s) in progress (garden ~7 min, Landmark ~2 min, eee_02 ~6 min)"
  for p in "${pids[@]}"; do wait "$p"; done
  if [ -s data/liosam/garden_dataset.bag ]; then
    g=$(dc eval bash -c 'python3 /scripts/fl2_traj.py /output/tests/fastlio2/liosam2_garden_r1.bag /Odometry /output/tests/fastlio2/liosam2_garden_r1.tum >/dev/null && python3 /scripts/fl2_drift.py /output/tests/fastlio2/liosam2_garden_r1.tum' | awk '/end-to-end/{print $3}')
    near "fastlio2 LIO-SAM garden end-to-end (m; paper < 0.1)" "$g" 0.027 0.02
  else skip "fastlio2 garden run (data/liosam/garden_dataset.bag missing)"; fi
  if [ -s data/fastlivo2_private/HKU_Landmark.bag ]; then
    h=$(python3 scripts/fl2_drift.py output/tests/fastlivo2/hku_landmark_r1.txt 2>/dev/null | awk '/end-to-end/{print $3}')
    near "fastlivo2 HKU Landmark end-to-end (m; paper < 0.01)" "$h" 0.006 0.003
  else skip "fastlivo2 HKU Landmark run (bag missing)"; fi
  if [ -s data/ntu_viral/eee_02/eee_02/eee_02.bag ]; then
    cp output/fastlivo2/gt_eee_02.tum output/tests/fastlivo2/ 2>/dev/null || \
      dc eval python3 /scripts/viral_prep.py gt /data/ntu_viral/viral_eval/result_eee_02/leica_pose.csv /output/tests/fastlivo2/gt_eee_02.tum >/dev/null
    e=$(dc eval bash -c 'python3 /scripts/viral_prep.py prism /output/tests/fastlivo2/eee_02_r1.txt /tmp/p.tum >/dev/null && evo_ape tum /output/tests/fastlivo2/gt_eee_02.tum /tmp/p.tum -a 2>/dev/null | awk "/^ *rmse/{print \$2}"')
    near "fastlivo2 NTU eee_02 matched-start ATE (m; repo 0.0211)" "$e" 0.0229 0.002
  else skip "fastlivo2 eee_02 run (bag missing)"; fi
  docker run --rm -v "$PWD/output:/o" evtol/eval:v1 chown -R "$(id -u):$(id -g)" /o/tests 2>/dev/null
}

case "$MODE" in
  quick)      level0; level1 ;;
  functional) level2 ;;
  all)        level0; level1; level2 ;;
  *) echo "usage: $0 quick|functional|all"; exit 2 ;;
esac
echo; echo "== $PASS passed, $FAIL failed, $SKIP skipped"
exit "$FAIL"
