#!/usr/bin/env python3
"""What EKF2 did at touchdown, from PX4's own flight log. Runs INSIDE the sim container
(pyulog is part of PX4's toolchain there):

    python3 /scripts/stage5/ulog_touchdown.py /output/stage5/flights/<name>.ulg

Stage 5 found PX4's height estimate sinking 0.3-0.6 m below the ground for ~3 s after every
touchdown while FAST-LIO2's pose stayed right. This prints, from 2 s before the first ground
contact to 6 s after it (PX4 time, all heights up in metres):
  * PX4's ground truth and EKF2's estimate of height,
  * the vision height EKF2 received, its innovation and test ratio, and whether it was
    fused or REJECTED (estimator_aid_src_ev_hgt),
  * the largest vertical specific force the IMU reported (sensor_combined),
  * the land detector's state,
and a verdict: how often the vision height was rejected, the IMU peak, and the test of the
mechanism -- the vertical velocity change the IMU integrates across the touchdown against
the true one (Gazebo samples the IMU every few ms; a touchdown impulse lasts a few 1 ms
physics steps, so most of it can fall between samples: Stage 4, deviation 5).
"""
import sys

import numpy as np
from pyulog import ULog


def topic(u, name):
    d = [x for x in u.data_list if x.name == name and x.multi_id == 0]
    return d[0].data if d else None


def at(t, ts, v):
    i = np.clip(np.searchsorted(ts, t), 0, len(ts) - 1)
    return v[i]


def main():
    u = ULog(sys.argv[1])
    gt = topic(u, "vehicle_local_position_groundtruth"); lp = topic(u, "vehicle_local_position")
    ev = topic(u, "estimator_aid_src_ev_hgt"); sc = topic(u, "sensor_combined")
    ld = topic(u, "vehicle_land_detected")
    tg, zg = gt["timestamp"] / 1e6, -gt["z"]
    z0 = np.median(zg[:50])
    air = np.where(zg > z0 + 0.15)[0]
    if not len(air):
        sys.exit("no flight in this log")
    after = np.where((tg > tg[air[0]] + 5) & (zg < z0 + 0.05))[0]
    td = tg[after[0]]                                   # first touchdown (truth back on the ground)
    print("first touchdown at %.2f s (PX4 time); ground height %.3f m" % (td, z0))
    te, ze = lp["timestamp"] / 1e6, -lp["z"]
    tv = ev["timestamp_sample"] / 1e6
    tsc = sc["timestamp"] / 1e6; az = sc["accelerometer_m_s2[2]"]
    tl = ld["timestamp"] / 1e6
    print("   t-td    truth  EKF2 est  vision obs  innov  test_ratio  vision  IMU |az| max(0.25 s)  landed/maybe/contact")
    for t in np.arange(td - 2.0, td + 6.01, 0.25):
        i = min(np.searchsorted(tv, t), len(tv) - 1)
        w = (tsc >= t - 0.25) & (tsc < t)
        state = "/".join(str(int(at(t, tl, ld[k]))) for k in ("landed", "maybe_landed", "ground_contact"))
        print("  %+5.2f  %7.3f  %8.3f  %10.3f  %+6.3f  %10.2f  %-8s %18.1f  %s" % (
            t - td, at(t, tg, zg) - z0, at(t, te, ze) - z0, -ev["observation"][i] - z0, -ev["innovation"][i],
            ev["test_ratio"][i], "REJECTED" if ev["innovation_rejected"][i] else ("fused" if ev["fused"][i] else "-"),
            float(np.max(np.abs(az[w]))) if w.any() else float("nan"), state))
    w = (tv >= td) & (tv <= td + 6)
    rej = ev["innovation_rejected"][w].astype(bool)
    wi = (tsc >= td - 0.5) & (tsc <= td + 1.0)
    werr = (te >= td) & (te <= td + 6)
    err = np.abs(ze[werr] - np.interp(te[werr], tg, zg))
    print("verdict: vision height REJECTED in %d of %d updates in the 6 s after touchdown (%.1f s); max test ratio %.1f;"
          " IMU |az| peak %.1f m/s^2 (at rest 9.8); EKF2 height error peak %.2f m"
          % (rej.sum(), w.sum(), rej.sum() * np.median(np.diff(tv)), ev["test_ratio"][w].max(),
             np.abs(az[wi]).max(), err.max()))
    # mechanism: vertical velocity change across the touchdown, IMU-integrated vs true
    g = np.median(-az[(tsc > td - 3) & (tsc < td - 1)])          # 1 g as this IMU reports it
    a, b = td - 0.3, td + 0.6
    m = (tsc >= a) & (tsc <= b)
    dv_imu = float(np.sum((-az[m] - g) * np.diff(np.r_[tsc[m][0], tsc[m]])))   # up, level vehicle
    vz = -gt["vz"]
    dv_true = float(np.interp(b, tg, vz) - np.interp(a, tg, vz))
    ve = -lp["vz"]
    print("mechanism: vertical speed change across touchdown (%.1f..+%.1f s): true %+.2f m/s, IMU-integrated %+.2f m/s"
          " (%.0f %% of it); IMU rate %.0f Hz; EKF2's vertical speed %.2f s after touchdown %+.2f m/s (true %+.2f)" % (
              a - td, b - td, dv_true, dv_imu, 100 * dv_imu / dv_true if dv_true else float("nan"),
              1 / np.median(np.diff(tsc)), 0.5, float(np.interp(td + 0.5, te, ve)), float(np.interp(td + 0.5, tg, vz))))


if __name__ == "__main__":
    main()
