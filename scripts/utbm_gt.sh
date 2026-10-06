#!/usr/bin/env bash
# UTBM ground truth: the bags carry GPS only as raw NMEA strings (/nmea_sentence,
# nmea_msgs/Sentence). Replay them through nmea_navsat_driver to get /fix
# (sensor_msgs/NavSatFix), then fl2_gt.py turns that into a TUM file.
# Runs in the fastlio2 container:
#   utbm_gt.sh <in.bag> <seq-name>     -> $OUTDIR/<seq>_fix.bag
# then in the eval container:
#   python3 /scripts/fl2_gt.py bag /output/fastlio2/<seq>_fix.bag /fix /output/fastlio2/gt_<seq>.tum
set -eo pipefail
BAG=$1; SEQ=$2; OUTDIR=${OUTDIR:-/output/fastlio2}; mkdir -p "$OUTDIR"
source /opt/ros/noetic/setup.bash
roscore >/dev/null 2>&1 & CORE=$!
until rostopic list >/dev/null 2>&1; do sleep 0.5; done
# use_sim_time stays false: nmea_topic_driver stamps /fix with the Sentence's
# header stamp (capture time), which is what must match the odometry.
rosrun nmea_navsat_driver nmea_topic_driver nmea_sentence:=/nmea_sentence >/dev/null 2>&1 & DRV=$!
sleep 2
rosbag record -O "$OUTDIR/${SEQ}_fix.bag" /fix __name:=rec >/dev/null 2>&1 & REC=$!
sleep 1
rosbag play -r 20 "$BAG" --topics /nmea_sentence >/dev/null
sleep 2
rosnode kill /rec >/dev/null 2>&1 || true; wait $REC 2>/dev/null || true
kill -INT $DRV $CORE 2>/dev/null || true; wait $DRV $CORE 2>/dev/null || true
echo "wrote $OUTDIR/${SEQ}_fix.bag ($(rosbag info -y -k messages "$OUTDIR/${SEQ}_fix.bag") fixes)"
