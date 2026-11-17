#!/usr/bin/env python3
"""Build a copy of PX4's iris with landing gear (Stage 3 addition, not in the guide).
Runs INSIDE the sim container; sim_env.sh px4 calls it and puts the result first on
GAZEBO_MODEL_PATH, so `model://iris` (included by iris_evtol) resolves to it.

    python3 make_legged_iris.py [outdir=/tmp/evtol_models]

Why: PX4's iris has no legs in its collision model and rests on its body box (underside
0.055 m below base_link). The sensor rig hangs below that and has no collision, so on the
ground the LiDAR and both cameras were 5 cm inside the floor during the stationary hold
that initialises every algorithm (docs/stage3_log.md). rig.yaml's `landing_gear` describes
four feet under the rotors that lift the sensors ~0.12 m above the ground.

Why a patched copy rather than a separate link in iris_evtol: the feet must be collisions
OF iris::base_link. As a separate 80 g link joined to the 1.5 kg body, the vehicle
chattered on the ground (gyro 0.012 rad/s, accel 0.7 m/s^2 std at rest -- a light link
carrying a heavy one is ill-conditioned for ODE's iterative solver), whatever the foot
shape. On base_link itself it stands still (gyro < 1e-4 rad/s), like the original body.
Only the spherical feet collide (and so are visible to the LiDAR, at < 0.5 m, inside the
blind zone); the legs are visual. Nothing else of PX4's model is changed; if rig.yaml has
no `landing_gear`, the model is copied unchanged.
"""
import os
import shutil
import sys

import yaml

SRC = "/opt/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris/"
KEY = "      <visual name='base_link_inertia_visual'>"
BODY_UNDERSIDE = -0.055
MAT = ("<material><script><uri>file://media/materials/scripts/gazebo.material</uri>"
       "<name>Gazebo/DarkGrey</name></script></material>")


def main():
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else "/tmp/evtol_models", "iris")
    os.makedirs(out, exist_ok=True)
    shutil.copy(SRC + "model.config", out)
    sdf = open(SRC + "iris.sdf").read()
    g = yaml.safe_load(open("/config/rig.yaml")).get("landing_gear")
    if g:
        if sdf.count(KEY) != 1:
            sys.exit("!! make_legged_iris: PX4's iris.sdf is not laid out as expected")
        fr = g["foot_radius"]
        zf = g["foot_z"] + fr
        length = BODY_UNDERSIDE - g["foot_z"]
        zc = (BODY_UNDERSIDE + g["foot_z"]) / 2.0
        add = ""
        for i, (x, y) in enumerate(g["legs_xy"]):
            add += f"""      <collision name='foot_{i}'>
        <pose>{x} {y} {zf:.4f} 0 0 0</pose>
        <geometry><sphere><radius>{fr}</radius></sphere></geometry>
        <surface><contact><ode><min_depth>0.001</min_depth><max_vel>0</max_vel></ode></contact><friction><ode/></friction></surface>
      </collision>
      <visual name='foot_{i}_visual'>
        <pose>{x} {y} {zf:.4f} 0 0 0</pose>
        <geometry><sphere><radius>{fr}</radius></sphere></geometry>
        {MAT}
      </visual>
      <visual name='leg_{i}_visual'>
        <pose>{x} {y} {zc:.4f} 0 0 0</pose>
        <geometry><cylinder><radius>{g['radius']}</radius><length>{length:.4f}</length></cylinder></geometry>
        {MAT}
      </visual>
"""
        sdf = sdf.replace(KEY, add + KEY)
    with open(os.path.join(out, "iris.sdf"), "w") as f:
        f.write(sdf)


if __name__ == "__main__":
    main()
