#!/usr/bin/env python3
"""Feed FAST-LIO's pose to PX4 as external vision.

    python3 slam_to_px4.py [--in /Odometry] [--mount /config/generated/mount.yaml]

FAST-LIO reports the IMU frame's pose in "camera_init" -- the IMU frame at the
moment FAST-LIO started. PX4 wants the VEHICLE (base_link, FLU) pose in a
gravity-aligned local frame (ENU for MAVROS, which converts to NED).

With M = T_base_imu (how the rig is mounted, from rig.yaml) and the vehicle
level and stationary when SLAM starts, the local frame can be taken as the
initial base_link frame, and then
        T_local_base(t) = M * T_ci_imu(t) * M^-1
i.e. the SLAM motion re-expressed through the mount. For the upside-down rig
this is what turns FAST-LIO's inverted world into an upright one.

Publishes geometry_msgs/PoseStamped on /mavros/vision_pose/pose, stamped with
the scan capture time -- so EKF2_EV_DELAY starts at 0.
"""
import argparse
import math

import rospy
import yaml
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry


def q_to_R(x, y, z, w):
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def R_to_q(R):
    tr = R[0][0] + R[1][1] + R[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return ((R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s, 0.25 * s)
    i = max(range(3), key=lambda k: R[k][k])
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1.0 + R[i][i] - R[j][j] - R[k][k]) * 2
    q = [0.0, 0.0, 0.0, 0.0]
    q[i] = 0.25 * s
    q[j] = (R[j][i] + R[i][j]) / s
    q[k] = (R[k][i] + R[i][k]) / s
    q[3] = (R[k][j] - R[j][k]) / s
    return tuple(q)


def mm(A, B):
    return [[sum(A[i][n] * B[n][j] for n in range(3)) for j in range(3)] for i in range(3)]


def mv(A, v):
    return [sum(A[i][n] * v[n] for n in range(3)) for i in range(3)]


def T(A):
    return [[A[j][i] for j in range(3)] for i in range(3)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="/Odometry")
    ap.add_argument("--mount", default="/config/generated/mount.yaml")
    a = ap.parse_args(rospy.myargv()[1:])
    m = yaml.safe_load(open(a.mount))
    r = m["R_base_imu"]
    M_R = [r[0:3], r[3:6], r[6:9]]
    M_t = m["t_base_imu"]
    Mi_R = T(M_R)
    Mi_t = [-v for v in mv(Mi_R, M_t)]

    rospy.init_node("slam_to_px4")
    pub = rospy.Publisher("/mavros/vision_pose/pose", PoseStamped, queue_size=10)

    def cb(msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        R_s, t_s = q_to_R(q.x, q.y, q.z, q.w), [p.x, p.y, p.z]
        # M * S * M^-1
        R = mm(mm(M_R, R_s), Mi_R)
        t = [a_ + b_ for a_, b_ in zip(mv(mm(M_R, R_s), Mi_t), mv(M_R, t_s))]
        t = [t[i] + M_t[i] for i in range(3)]
        out = PoseStamped()
        out.header.stamp = msg.header.stamp          # capture time, not "now"
        out.header.frame_id = "map"
        out.pose.position.x, out.pose.position.y, out.pose.position.z = t
        qx, qy, qz, qw = R_to_q(R)
        out.pose.orientation.x, out.pose.orientation.y = qx, qy
        out.pose.orientation.z, out.pose.orientation.w = qz, qw
        pub.publish(out)

    rospy.Subscriber(a.inp, Odometry, cb, queue_size=10)
    rospy.loginfo("relaying %s -> /mavros/vision_pose/pose through the rig mount", a.inp)
    rospy.spin()


if __name__ == "__main__":
    main()
