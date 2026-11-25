#!/usr/bin/env python3
"""Apply a PX4 parameter file through MAVROS and read every value back.

    python3 set_params.py /config/px4/ev_only.params [override.params ...]

A parameter that did not take is reported, not silently ignored: on a real
vehicle, flying with half the EV configuration applied is worse than not
flying at all.

Changes from the guide (docs/stage5_log.md):
  * set/get are retried for up to 60 s: right after MAVROS connects it is still downloading
    PX4's parameter list and the services fail with "PR: receiving not complete" (a
    ServiceException; the guide's loop would crash on the first one -- seen in Stage 3).
  * the read-back compares NUMBERS: MAVROS returns a FLOAT parameter in .real even when the
    file writes it as an integer ("EKF2_EV_DELAY 0"), so the guide's type-from-text guess
    could compare the wrong field.
"""
import sys
import time

import rospy
from mavros_msgs.msg import ParamValue
from mavros_msgs.srv import ParamGet, ParamSet


def main():
    rospy.init_node("set_params", anonymous=True)
    for s in ("/mavros/param/set", "/mavros/param/get"):
        rospy.wait_for_service(s, timeout=120)
    pset = rospy.ServiceProxy("/mavros/param/set", ParamSet)
    pget = rospy.ServiceProxy("/mavros/param/get", ParamGet)
    bad = 0
    # Stage 5 extension: several files, a later one overriding an earlier one (run_closed_loop.sh
    # passes a one-line EKF2_EV_DELAY file after ev_only.params); each parameter is set once
    params = {}
    for path in sys.argv[1:]:
        for line in open(path):
            line = line.split("#", 1)[0].strip()
            if line:
                name, raw = line.split()
                params[name] = raw
    for name, raw in params.items():
        is_int = "." not in raw
        val = ParamValue(integer=int(raw), real=0.0) if is_int else ParamValue(integer=0, real=float(raw))
        ok = got = None
        for _ in range(120):
            try:
                ok = pset(param_id=name, value=val).success
                got = pget(param_id=name)
            except rospy.ServiceException:
                ok = False
            if ok and got is not None and got.success:
                break
            time.sleep(0.5)
        back = None
        if got is not None and got.success:
            back = got.value.integer if got.value.integer != 0 else got.value.real
        match = bool(ok) and back is not None and abs(back - float(raw)) < 1e-6
        bad += 0 if match else 1
        print("%-18s set %-8s read back %-10s %s" % (name, raw, back, "OK" if match else "<-- FAILED"))
    time.sleep(2)                                 # PX4 autosaves shortly after a set
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
