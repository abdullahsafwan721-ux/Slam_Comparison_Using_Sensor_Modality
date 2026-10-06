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
echo "== converting $D (about 2.5 min per GB of hits on a modern CPU)"
cd "$WORK"
# Ubuntu 20.04 ships scipy 1.3, where Rotation.from_matrix is still called from_dcm
# (renamed in scipy 1.4). Alias it rather than editing the authors' script.
python3 - "$WORK/" "$OUT.tmp" > "$WORK/convert.log" 2>&1 <<'PY' || { echo "!! converter failed -- see $WORK/convert.log"; tail -5 "$WORK/convert.log"; exit 1; }
import runpy, sys
from scipy.spatial.transform import Rotation
if not hasattr(Rotation, "from_matrix"): Rotation.from_matrix = Rotation.from_dcm
sys.argv = ["sensordata_to_rosbag_fastlio.py"] + sys.argv[1:]
runpy.run_path("/scripts/third_party/sensordata_to_rosbag_fastlio.py", run_name="__main__")
PY
mv "$OUT.tmp" "$OUT"
rosbag info "$OUT" | grep -E 'duration|messages|points_raw|imu_raw'
[ "${KEEP_WORK:-0}" = 1 ] || rm -rf "$WORK"
echo "== wrote $OUT"
