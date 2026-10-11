#!/usr/bin/env bash

set -u

# Output layout: trajectories and evaluation results live under /output/orbslam3/
TRAJ=${TRAJ:-/output/orbslam3/trajectories}
EVAL=${EVAL:-/output/orbslam3/evaluation}
mkdir -p "$EVAL"

declare -A GT=(
    [MH01]=MH_01_easy
    [MH02]=MH_02_easy
    [MH03]=MH_03_medium
    [MH04]=MH_04_difficult
    [MH05]=MH_05_difficult
    [V101]=V1_01_easy
    [V102]=V1_02_medium
    [V103]=V1_03_difficult
    [V201]=V2_01_easy
    [V202]=V2_02_medium
    [V203]=V2_03_difficult
)

echo "=============================================="
echo " ORB-SLAM3 EuRoC Evaluation"
echo "=============================================="
echo

count=$(find "$TRAJ" -maxdepth 1 -type f -name 'kf_orb_*_r[1-5].txt' | wc -l)

echo "Found $count ORB-SLAM3 trajectory files."

if [ "$count" -ne 55 ]; then
    echo "ERROR: Expected 55 trajectory files, found $count."
    exit 1
fi

echo "Trajectory count OK: 55"
echo

rm -f "$EVAL"/kf_orb_*_r*_eval.txt
rm -f "$EVAL"/kf_orb_*_r*_ape.zip
rm -f "$EVAL"/summary.csv

echo "Old evaluation files removed."
echo

success=0
failed=0

for est in "$TRAJ"/kf_orb_*_r[1-5].txt; do

    [ -e "$est" ] || continue

    base=$(basename "$est" .txt)

    short=$(echo "$base" | sed 's/^kf_orb_//; s/_r[0-9]*$//')

    dir="${GT[$short]:-}"

    if [ -z "$dir" ]; then
        echo "ERROR: No ground truth mapping for $short"
        failed=$((failed + 1))
        continue
    fi

    eval_file="$EVAL/${base}_eval.txt"
    result_file="$EVAL/${base}_ape.zip"

    echo
    echo "=============================================="
    echo "Evaluating: $base"
    echo "Ground truth: $dir"
    echo "=============================================="

    awk '{
        printf "%.9f", $1 / 1000000000;
        for (i=2; i<=NF; i++) {
            printf " %s", $i;
        }
        printf "\n";
    }' "$est" > "$eval_file"

    if evo_ape euroc \
        "/data/euroc/$dir/mav0/state_groundtruth_estimate0/data.csv" \
        "$eval_file" \
        -va \
        --align \
        --save_results "$result_file"
    then
        echo "SUCCESS: $base"
        success=$((success + 1))
    else
        echo "FAILED: $base"
        failed=$((failed + 1))
    fi

done

echo
echo "=============================================="
echo " Evaluation finished"
echo "=============================================="
echo
echo "Successful: $success"
echo "Failed:     $failed"
echo

if [ "$failed" -ne 0 ]; then
    echo "WARNING: Some evaluations failed."
    echo "Summary will NOT be generated."
    exit 1
fi

echo "Creating summary table..."

evo_res \
    "$EVAL"/kf_orb_*_r*_ape.zip \
    --use_filenames \
    --save_table "$EVAL/summary.csv"

echo
echo "=============================================="
echo " Summary created"
echo "=============================================="
echo
echo "Output: $EVAL/summary.csv"
echo
cat "$EVAL/summary.csv"
echo
echo "=============================================="
echo " DONE"
echo "=============================================="

