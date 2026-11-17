#!/usr/bin/env python3
"""Pre-flight check (Stage 3, not in the guide): does a flight profile clear the world's boxes?

    python3 check_clearance.py <world-file> <profile> [--spawn X Y] [--alt 1.5] [--size 6]
                               [--air 0.8] [--ground 0.6] [--search]

Runs inside the sim container (px4_record.sh calls it before starting PX4) or on the host.
Reads every static box of the world file (walls and clutter; gen_world.py only makes boxes),
takes the profile's path from offboard_mission.py itself, places it at the spawn point and
requires
  * --air    m horizontal clearance between the path and every box whose top is higher
             than (alt - 0.7 m): the vehicle, its legs and the rig hang below the IMU;
  * --ground m of free floor around the take-off point (where it also lands).
Exits non-zero when either fails. --search lists the best spawn points instead.

Why it exists: the guide spawns the vehicle at the world origin and flies a 6 m square
at 1.5 m in the room. In the generated room a 0.67 m box sits ON the origin, the 6 m
square passes through a 1.38 m box and 6 cm from a 1.81 m one.
"""
import argparse
import math
import os
import re
import sys

import numpy as np

BELOW = 0.7      # m, vertical band below flight altitude that must be free


def boxes(world):
    out = []
    text = open(world).read()
    for m in re.finditer(r'<model name="([^"]+)">(.*?)</model>', text, re.S):
        pose = re.search(r"<pose>([^<]*)</pose>", m.group(2))
        size = re.search(r"<box><size>([^<]*)</size></box>", m.group(2))
        if not (pose and size):
            continue
        p = [float(v) for v in pose.group(1).split()]
        s = [float(v) for v in size.group(1).split()]
        top = p[2] + s[2] / 2
        if top > 0.05:                                   # skip the floor slab
            out.append((m.group(1), p[0], p[1], p[5], s[0] / 2, s[1] / 2, top))
    return out


def dist(P, b):
    """Horizontal distance from points P (n,2) to one box footprint."""
    _, x, y, yaw, hx, hy, _ = b
    c, s = math.cos(-yaw), math.sin(-yaw)
    dx, dy = P[:, 0] - x, P[:, 1] - y
    lx, ly = c * dx - s * dy, s * dx + c * dy
    return np.hypot(np.maximum(np.abs(lx) - hx, 0), np.maximum(np.abs(ly) - hy, 0))


def profile_points(profile, size, n=1200):
    """The exact path offboard_mission.py flies, relative to the take-off point."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from offboard_mission import path
    except ImportError:                                   # host without rospy: same formulas
        def path(profile, s, size):
            if profile == "hover":
                return 0.0, 0.0
            if profile == "line":
                u = s % (2 * size)
                return (u if u < size else 2 * size - u), 0.0
            if profile == "square":
                u, h = s % (4 * size), size / 2.0
                if u < size:
                    return -h + u, -h
                if u < 2 * size:
                    return h, -h + (u - size)
                if u < 3 * size:
                    return h - (u - 2 * size), h
                return -h, h - (u - 3 * size)
            th = 2 * math.pi * (s % (6.1 * size)) / (6.1 * size)
            return size * math.sin(th), size * math.sin(th) * math.cos(th)
    per = {"hover": 1.0, "line": 2 * size, "square": 4 * size, "figure8": 6.1 * size}[profile]
    ox, oy = path(profile, 0.0, size)
    return np.array([[px - ox, py - oy] for px, py in
                     (path(profile, per * i / n, size) for i in range(n))])


def clearances(B, P, spawn, alt):
    Q = P + np.array(spawn)
    air = [(float(dist(Q, b).min()), b[0], b[6]) for b in B if b[6] > alt - BELOW]
    gnd = [(float(dist(np.array([spawn]), b)[0]), b[0], b[6]) for b in B]
    return (min(air) if air else (9.9, "-", 0.0)), (min(gnd) if gnd else (9.9, "-", 0.0))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("world")
    ap.add_argument("profile", choices=["hover", "square", "figure8", "line"])
    ap.add_argument("--spawn", type=float, nargs=2, default=[0.0, 0.0])
    ap.add_argument("--alt", type=float, default=1.5)
    ap.add_argument("--size", type=float, default=6.0)
    ap.add_argument("--air", type=float, default=0.8)
    ap.add_argument("--ground", type=float, default=0.6)
    ap.add_argument("--search", action="store_true")
    a, _ = ap.parse_known_args()                          # ignores --speed, --laps, --yaw ...
    B = boxes(a.world)
    P = profile_points(a.profile, a.size)
    if a.search:
        xs = [b[1] for b in B] + [0.0]
        ys = [b[2] for b in B] + [0.0]
        cand = []
        for x in np.arange(min(xs), max(xs) + 0.01, 0.1):
            for y in np.arange(min(ys), max(ys) + 0.01, 0.1):
                air, gnd = clearances(B, P, (x, y), a.alt)
                if air[0] >= a.air and gnd[0] >= a.ground:
                    cand.append((min(air[0], gnd[0] + 0.2), round(x, 1), round(y, 1), air[0], gnd[0]))
        cand.sort(reverse=True)
        print("%d spawn points pass for %s size %.1f alt %.1f" % (len(cand), a.profile, a.size, a.alt))
        for _, x, y, air, gnd in cand[:5]:
            print("  --spawn %5.1f %5.1f   air %.2f m   ground %.2f m" % (x, y, air, gnd))
        sys.exit(0 if cand else 1)
    air, gnd = clearances(B, P, a.spawn, a.alt)
    ok = air[0] >= a.air and gnd[0] >= a.ground
    print("%s  %s size %.1f alt %.1f from spawn (%.1f, %.1f): path %.2f m from %s (top %.2f m), "
          "take-off spot %.2f m from %s (top %.2f m)"
          % ("CLEAR" if ok else "!! BLOCKED", a.profile, a.size, a.alt, a.spawn[0], a.spawn[1],
             air[0], air[1], air[2], gnd[0], gnd[1], gnd[2]))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
