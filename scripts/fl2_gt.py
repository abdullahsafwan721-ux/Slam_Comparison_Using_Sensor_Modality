#!/usr/bin/env python3
"""Ground truth -> TUM, for evo.
    fl2_gt.py bag <bag> <topic> <out.tum>      GNSS/INS inside a rosbag
    fl2_gt.py nclt <groundtruth.csv> <out.tum> NCLT's per-session CSV

Bag topics handled: sensor_msgs/NavSatFix, nav_msgs/Odometry and
novatel_gps_msgs/Inspvax (UrbanLoco). Messages are decoded from the definition
stored INSIDE the bag, so the message package need not be installed.

Latitude/longitude are projected onto a local ENU plane at the first fix, so the
track starts at the origin like the SLAM trajectory. Over a few kilometres the
flat-earth error is millimetres, far below the metre-level errors measured."""
import math, os, sys
A = 6378137.0
E2 = (1/298.257223563) * (2 - 1/298.257223563)

def scales(lat0):
    s = math.sin(math.radians(lat0)); d = 1 - E2*s*s
    return (math.radians(1)*A*(1-E2)/d**1.5,
            math.radians(1)*A*math.cos(math.radians(lat0))/math.sqrt(d))

def quat(roll, pitch, yaw):
    cr,sr = math.cos(roll/2), math.sin(roll/2)
    cp,sp = math.cos(pitch/2), math.sin(pitch/2)
    cy,sy = math.cos(yaw/2), math.sin(yaw/2)
    return (sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy, cr*cp*sy-sr*sp*cy, cr*cp*cy+sr*sp*sy)

def write(rows, out):
    if not rows: sys.exit("!! no usable poses")
    with open(out, "w") as f:
        f.writelines("%.9f %.6f %.6f %.6f %.9f %.9f %.9f %.9f\n" % r for r in rows)
    print("wrote %d poses spanning %.1f s -> %s" % (len(rows), rows[-1][0]-rows[0][0], out))
    print("first timestamp %.3f -- it must share a time base with the estimate" % rows[0][0])

def from_bag(path, topic, out):
    try:
        import genpy.dynamic, rosbag
    except ImportError:   # eval container: venv python has no ROS -> re-run with system python + ROS
        if os.environ.get("FL2_REEXEC"): raise
        os.environ.update(FL2_REEXEC="1", PYTHONPATH="/opt/ros/noetic/lib/python3/dist-packages")
        os.execv("/usr/bin/python3", ["/usr/bin/python3"] + sys.argv)
    bag = rosbag.Bag(path); dt = md = None
    for c in bag._get_connections():
        if c.topic == topic: dt, md = c.datatype, c.msg_def; break
    if dt is None: sys.exit("!! topic %s not in bag -- check 'rosbag info'" % topic)
    cls = genpy.dynamic.generate_dynamic(dt, md)[dt]
    print("%s is %s" % (topic, dt))
    rows, org = [], None
    for _, raw, bt in bag.read_messages(topics=[topic], raw=True):
        m = cls().deserialize(raw[1])
        t = m.header.stamp.to_sec() if hasattr(m, "header") else bt.to_sec()
        q = (0.0, 0.0, 0.0, 1.0)
        if dt.endswith("Odometry"):
            p = m.pose.pose.position; o = m.pose.pose.orientation
            x, y, z = p.x, p.y, p.z; q = (o.x, o.y, o.z, o.w)
        else:
            lat = getattr(m, "latitude", None); lon = getattr(m, "longitude", None)
            alt = getattr(m, "altitude", getattr(m, "height", 0.0))
            if lat is None: sys.exit("!! %s has no latitude field" % dt)
            st = getattr(m, "status", None)
            if st is not None and getattr(st, "status", 0) < 0: continue     # no fix
            if org is None: org = (lat, lon, alt) + scales(lat)
            lat0, lon0, alt0, ml, mo = org
            x, y, z = (lon-lon0)*mo, (lat-lat0)*ml, alt-alt0
            if hasattr(m, "azimuth"):          # Inspvax: azimuth clockwise from north
                q = quat(math.radians(getattr(m,"roll",0.0)),
                         math.radians(getattr(m,"pitch",0.0)),
                         math.radians(90.0 - m.azimuth))
        rows.append((t,x,y,z)+q)
    write(rows, out)

def from_nclt(csv, out):
    rows = []
    for line in open(csv):
        line = line.strip()
        if not line or line[0] in "#%": continue
        try: v = [float(x) for x in line.split(",")]
        except ValueError: continue
        if len(v) < 7 or any(math.isnan(x) for x in v[:7]): continue   # NCLT has NaN rows
        rows.append((v[0]/1e6, v[1], v[2], v[3]) + quat(v[4], v[5], v[6]))
    write(rows, out)

if __name__ == "__main__":
    if len(sys.argv) < 4: sys.exit(__doc__)
    if sys.argv[1] == "bag": from_bag(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "nclt": from_nclt(sys.argv[2], sys.argv[3])
    else: sys.exit(__doc__)
