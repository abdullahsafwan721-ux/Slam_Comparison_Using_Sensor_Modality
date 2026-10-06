#!/usr/bin/env bash
# UTBM ground truth: the bags carry GPS only as raw NMEA strings (/nmea_sentence,
# nmea_msgs/Sentence: GGA + RMC + GST at 5 Hz, RTK fixed/float).
# GGA sentences are parsed directly from the bag into sensor_msgs/NavSatFix on
# /fix, stamped with each Sentence's header stamp (capture time).
#
# Why not the guide's nmea_navsat_driver replay: replaying at -r 20 dropped
# almost everything (85 fixes from 4633 GGA sentences on 2018-07-19), and at 1x
# it would cost the full sequence duration. Parsing is exact and takes seconds.
#
# Runs in the fastlio2 container:
#   utbm_gt.sh <in.bag> <seq-name> [min_gga_quality=4]  -> $OUTDIR/<seq>_fix.bag
# then in the eval container:
#   python3 /scripts/fl2_gt.py bag /output/fastlio2/<seq>_fix.bag /fix /output/fastlio2/gt_<seq>.tum
# GGA quality: 4 = RTK fixed, 5 = RTK float, 1/2 = GPS/DGPS. Default keeps 4 and 5;
# a session with no RTK at all (2019-01-31) falls back to quality >= 1, with a warning.
set -eo pipefail
BAG=$1; SEQ=$2; MINQ=${3:-4}; OUTDIR=${OUTDIR:-/output/fastlio2}; mkdir -p "$OUTDIR"
source /opt/ros/noetic/setup.bash
python3 - "$BAG" "$OUTDIR/${SEQ}_fix.bag" "$MINQ" <<'PY'
import sys, collections, rosbag, genpy.dynamic
from sensor_msgs.msg import NavSatFix, NavSatStatus
src, dst, minq = sys.argv[1], sys.argv[2], int(sys.argv[3])
keep = {4, 5} if minq >= 4 else set(range(minq, 10))
b = rosbag.Bag(src)
c = next(x for x in b._get_connections() if x.topic == "/nmea_sentence")
cls = genpy.dynamic.generate_dynamic(c.datatype, c.msg_def)[c.datatype]
def deg(v, h):
    d = int(float(v) / 100); x = d + (float(v) - 100 * d) / 60.0
    return -x if h in "SW" else x
gga = []
for _, raw, _ in b.read_messages(topics=["/nmea_sentence"], raw=True):
    m = cls().deserialize(raw[1]); s = m.sentence.strip().split("*")[0].split(",")
    if s[0].endswith("GGA") and len(s) >= 10 and s[2] and s[6]: gga.append((m.header.stamp, s))
q = collections.Counter(int(s[6]) for _, s in gga)
if not keep & set(q):   # e.g. 2019-01-31 has no RTK at all: fall back to what exists
    keep = {k for k in q if k >= 1}
    print("!! no fixes of quality %s -- falling back to %s (metre-level GPS)" % (sorted({4, 5} if minq >= 4 else [minq]), sorted(keep)))
n = 0
with rosbag.Bag(dst, "w") as out:
    for stamp, s in gga:
        qual = int(s[6])
        if qual not in keep: continue
        f = NavSatFix(); f.header.stamp = stamp; f.header.frame_id = "gps"
        f.status.status = NavSatStatus.STATUS_GBAS_FIX if qual in (4, 5) else NavSatStatus.STATUS_FIX
        f.status.service = NavSatStatus.SERVICE_GPS
        f.latitude = deg(s[2], s[3]); f.longitude = deg(s[4], s[5])
        f.altitude = float(s[9]) + (float(s[11]) if len(s) > 11 and s[11] else 0.0)  # ellipsoidal
        out.write("/fix", f, stamp); n += 1
print("GGA quality counts %s; kept %s" % (dict(q), sorted(keep)))
print("wrote %s (%d fixes)" % (dst, n))
PY
