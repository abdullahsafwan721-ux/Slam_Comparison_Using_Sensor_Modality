#!/usr/bin/env bash
# Build a FAST-LIO2 input bag for one NCLT session, exactly as the FAST-LIO
# authors did: their converter (scripts/third_party/sensordata_to_rosbag_fastlio.py)
# applied to NCLT's raw velodyne_hits.bin + ms25.csv (+ gps).
# Runs in the fastlio2 container with data/nclt mounted READ-WRITE at /nclt:
#   docker compose run --rm -T -v "$PWD/data/nclt:/nclt" fastlio2 \
#       bash /scripts/nclt_to_bag.sh 2013-01-10
# Needs /nclt/raw/<date>_sen.tar.gz and /nclt/raw/<date>_vel.tar.gz.
# Writes /nclt/<date>.bag. KEEP_WORK=1 keeps the extracted files.
set -eo pipefail
D=$1
source /opt/ros/noetic/setup.bash
RAW=/nclt/raw; WORK=/nclt/work/$D; OUT=/nclt/$D.bag
[ -s "$RAW/${D}_sen.tar.gz" ] && [ -s "$RAW/${D}_vel.tar.gz" ] || { echo "!! raw tarballs for $D missing in $RAW"; exit 1; }
[ -s "$OUT" ] && { echo "== $OUT exists, skipping"; exit 0; }
mkdir -p /nclt/work
echo "== extracting $D"
tar -xzf "$RAW/${D}_sen.tar.gz" -C /nclt/work "$D/ms25.csv" "$D/ms25_euler.csv" "$D/gps.csv" "$D/gps_rtk.csv"
tar -xzf "$RAW/${D}_vel.tar.gz" -C /nclt/work "$D/velodyne_hits.bin"
echo "== converting $D (pure-Python converter: slow, roughly 1 h per GB of hits)"
cd "$WORK"
python3 /scripts/third_party/sensordata_to_rosbag_fastlio.py "$WORK/" "$OUT.tmp" > "$WORK/convert.log" 2>&1 \
  || { echo "!! converter failed -- see $WORK/convert.log"; tail -5 "$WORK/convert.log"; exit 1; }
mv "$OUT.tmp" "$OUT"
rosbag info "$OUT" | grep -E 'duration|messages|points_raw|imu_raw'
[ "${KEEP_WORK:-0}" = 1 ] || rm -rf "$WORK"
echo "== wrote $OUT"
