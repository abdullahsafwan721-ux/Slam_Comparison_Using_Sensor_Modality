#!/usr/bin/env python3
"""Live counterpart of imu_noise.py: /livox/imu -> /livox/imu_noisy.

The simulated IMU is noise-free; closing the loop on a perfect IMU would
flatter the result. Same model and same rig.yaml densities as the offline tool.
"""
import math
import random
import sys

import rospy
import yaml
from sensor_msgs.msg import Imu


def main():
    scale = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    n = yaml.safe_load(open("/config/rig.yaml"))["imu_noise_baseline"]
    gw, gb = n["gyro_noise_density"] * scale, n["gyro_random_walk"] * scale
    aw, ab = n["accel_noise_density"] * scale, n["accel_random_walk"] * scale
    rnd = random.Random(1)
    st = {"bg": [0.0] * 3, "ba": [0.0] * 3, "last": None}
    rospy.init_node("imu_noise_live")
    pub = rospy.Publisher("/livox/imu_noisy", Imu, queue_size=400)

    def cb(m):
        t = m.header.stamp.to_sec()
        dt = (t - st["last"]) if st["last"] is not None and t > st["last"] else 0.005
        st["last"] = t
        for i in range(3):
            st["bg"][i] += gb * math.sqrt(dt) * rnd.gauss(0, 1)
            st["ba"][i] += ab * math.sqrt(dt) * rnd.gauss(0, 1)
        sw, sa = gw / math.sqrt(dt), aw / math.sqrt(dt)
        w, a = m.angular_velocity, m.linear_acceleration
        w.x += st["bg"][0] + sw * rnd.gauss(0, 1)
        w.y += st["bg"][1] + sw * rnd.gauss(0, 1)
        w.z += st["bg"][2] + sw * rnd.gauss(0, 1)
        a.x += st["ba"][0] + sa * rnd.gauss(0, 1)
        a.y += st["ba"][1] + sa * rnd.gauss(0, 1)
        a.z += st["ba"][2] + sa * rnd.gauss(0, 1)
        pub.publish(m)

    rospy.Subscriber("/livox/imu", Imu, cb, queue_size=400)
    rospy.spin()


if __name__ == "__main__":
    main()
