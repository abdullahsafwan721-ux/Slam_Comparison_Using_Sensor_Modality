#!/usr/bin/env python3
"""Re-stamp UTBM VelodyneScan messages with the time of their FIRST packet.

UTBM's bags stamp each /hdl32e_left/velodyne_packets scan with its LAST packet
(header - packets[0].stamp = 0.0995 s, measured on utbm_20180719.bag), and
velodyne_pointcloud computes each point's `time` relative to that header, so the
cloud's per-point times run from -0.0995 to +0.0005 s. FAST-LIO expects the header
to be the scan START and times from 0 to the scan period; with negative times its
de-skew walks the IMU poses out of order. Re-stamped, the clouds carry the
first-packet stamp and times 0..0.100 s (checked on 200 scans). FAST_LIO's
`time_offset_lidar_to_imu` only applies to Livox messages, so the fix is made here,
before conversion. Used by run_fastlio2_utbm.sh (rosbag play remaps the bag topic
to .../velodyne_packets_orig)."""
import os
import rospy
from velodyne_msgs.msg import VelodyneScan

SHIFT = rospy.Duration.from_sec(float(os.environ.get("UTBM_TIME_SHIFT", "0")))  # diagnostics only

rospy.init_node("utbm_restamp")
pub = rospy.Publisher("/hdl32e_left/velodyne_packets", VelodyneScan, queue_size=200)


def cb(scan):
    if scan.packets:
        scan.header.stamp = scan.packets[0].stamp + SHIFT
    pub.publish(scan)


rospy.Subscriber("/hdl32e_left/velodyne_packets_orig", VelodyneScan, cb, queue_size=200, tcp_nodelay=True)
rospy.spin()
