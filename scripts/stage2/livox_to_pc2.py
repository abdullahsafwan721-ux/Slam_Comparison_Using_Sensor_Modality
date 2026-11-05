#!/usr/bin/env python3
"""View a Livox CustomMsg in RViz: /livox/lidar -> /livox/points (PointCloud2).

RViz cannot display livox_ros_driver/CustomMsg. This is for LOOKING only --
the algorithms always consume the original CustomMsg. In RViz set Fixed Frame
to `livox_frame` and add a PointCloud2 display on /livox/points.
"""
import rospy
import sensor_msgs.point_cloud2 as pc2
from livox_ros_driver.msg import CustomMsg
from sensor_msgs.msg import PointCloud2


def main():
    rospy.init_node("livox_to_pc2")
    pub = rospy.Publisher("/livox/points", PointCloud2, queue_size=2)

    def cb(m):
        pts = [(p.x, p.y, p.z) for p in m.points if p.x or p.y or p.z]
        pub.publish(pc2.create_cloud_xyz32(m.header, pts))

    rospy.Subscriber("/livox/lidar", CustomMsg, cb, queue_size=1, buff_size=2 ** 24)
    rospy.spin()


if __name__ == "__main__":
    main()
