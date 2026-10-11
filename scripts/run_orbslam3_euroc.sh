#!/usr/bin/env bash

set -u

cd /opt/ORB_SLAM3

declare -A SEQ=(
    [MH_01_easy]=MH01
    [MH_02_easy]=MH02
    [MH_03_medium]=MH03
    [MH_04_difficult]=MH04
    [MH_05_difficult]=MH05
    [V1_01_easy]=V101
    [V1_02_medium]=V102
    [V1_03_difficult]=V103
    [V2_01_easy]=V201
    [V2_02_medium]=V202
    [V2_03_difficult]=V203
)

RUNS="${RUNS:-1}"

# Output layout: trajectories go to /output/orbslam3/trajectories (evaluated by eval_orbslam3.sh)
TRAJ=${TRAJ:-/output/orbslam3/trajectories}
mkdir -p "$TRAJ"

for dir in "${!SEQ[@]}"; do

    short="${SEQ[$dir]}"

    if [ ! -d "/data/euroc/$dir" ]; then
        echo "SKIP $dir (not on disk)"
        continue
    fi

    for run in $(seq 1 "$RUNS"); do

        echo
        echo "======================================"
        echo "Running $dir | Run $run/$RUNS"
        echo "======================================"

        prefix="orb_${short}_r${run}"

        ./Examples/Stereo-Inertial/stereo_inertial_euroc \
            ./Vocabulary/ORBvoc.txt \
            ./Examples/Stereo-Inertial/EuRoC.yaml \
            "/data/euroc/$dir" \
            "./Examples/Stereo-Inertial/EuRoC_TimeStamps/${short}.txt" \
            "$prefix"

        if [ -f "f_${prefix}.txt" ]; then
            cp "f_${prefix}.txt" "$TRAJ/"
        else
            echo "WARNING: Full trajectory missing for $dir run $run"
        fi

        if [ -f "kf_${prefix}.txt" ]; then
            cp "kf_${prefix}.txt" "$TRAJ/"
        else
            echo "WARNING: Keyframe trajectory missing for $dir run $run"
        fi

    done

done

echo
echo "======================================"
echo "DONE"
echo "======================================"

echo "Output files:"
ls -lh "$TRAJ"
