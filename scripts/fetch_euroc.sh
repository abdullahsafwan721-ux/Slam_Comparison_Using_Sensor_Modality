#!/usr/bin/env bash

# Installs the EuRoC MAV dataset into data/euroc (data/euroc/<SEQ>/mav0, ASL format).
# Runs on the HOST, not inside a container.
#
# EuRoC is no longer on robotics.ethz.ch (the old per-sequence URLs time out). It is
# now in the ETH Research Collection, https://doi.org/10.3929/ethz-b-000690084, which
# rate-limits scripted downloads, so download these there with a browser:
#   machine_hall.zip  vicon_room1.zip  vicon_room2.zip
# and put them in $ZIPS (default data/euroc/.zips). Each holds <room>/<SEQ>/<SEQ>.zip
# (ASL format, used here) and <SEQ>.bag (not used). Already extracted room folders
# (<ZIPS>/<room>/<SEQ>/<SEQ>.zip) are used as they are.
#
# All sequences:
#   bash scripts/fetch_euroc.sh
#
# Selected sequences, archives elsewhere:
#   SEQS="MH_01_easy V2_03_difficult" ZIPS=/path/to/archives bash scripts/fetch_euroc.sh

set -uo pipefail

DOI="https://doi.org/10.3929/ethz-b-000690084"

# Project root is one directory above scripts/
DEST="${DEST:-$(cd "$(dirname "$0")/.." && pwd)/data/euroc}"
ZIPS="${ZIPS:-$DEST/.zips}"

declare -A GROUP=(
    [MH_01_easy]=machine_hall
    [MH_02_easy]=machine_hall
    [MH_03_medium]=machine_hall
    [MH_04_difficult]=machine_hall
    [MH_05_difficult]=machine_hall
    [V1_01_easy]=vicon_room1
    [V1_02_medium]=vicon_room1
    [V1_03_difficult]=vicon_room1
    [V2_01_easy]=vicon_room2
    [V2_02_medium]=vicon_room2
    [V2_03_difficult]=vicon_room2
)

# If SEQS is not specified, install all sequences.
SEQS="${SEQS:-${!GROUP[*]}}"

mkdir -p "$DEST" "$ZIPS"
ZIPS="$(cd "$ZIPS" && pwd)"
cd "$DEST"

for seq in $SEQS; do
    grp="${GROUP[$seq]:-}"

    if [ -z "$grp" ]; then
        echo "!! Unknown sequence: $seq"
        continue
    fi

    if [ -d "$seq/mav0" ]; then
        echo "== $seq already extracted, skipping"
        continue
    fi

    inner="$ZIPS/$grp/$seq/$seq.zip"

    if [ ! -s "$inner" ]; then
        if [ ! -s "$ZIPS/$grp.zip" ]; then
            echo "!! $seq: need $ZIPS/$grp.zip -- download it from $DOI"
            continue
        fi

        echo "== Extracting $seq from $grp.zip"

        unzip -q -o "$ZIPS/$grp.zip" "$grp/$seq/$seq.zip" -d "$ZIPS" \
            || {
                echo "!! Could not extract $grp/$seq/$seq.zip from $grp.zip"
                continue
            }
    fi

    echo "== Unpacking $seq"

    mkdir -p "$seq"

    unzip -q -o "$inner" -d "$seq" \
        || {
            echo "!! Unzip failed: $seq"
            continue
        }
done

echo
echo "--- Verification ---"

ok=0
bad=0

for seq in $SEQS; do
    gt="$seq/mav0/state_groundtruth_estimate0/data.csv"
    n=$(ls "$seq/mav0/cam0/data" 2>/dev/null | wc -l)

    if [ -f "$gt" ] && [ "$n" -gt 0 ]; then
        printf '%-18s OK %5d left images, ground truth present\n' "$seq" "$n"
        ok=$((ok + 1))
    else
        printf '%-18s BAD (missing mav0 contents)\n' "$seq"
        bad=$((bad + 1))
    fi
done

echo
echo "$ok complete, $bad incomplete."

du -sh "$DEST" 2>/dev/null

echo
echo "Archives kept in $ZIPS"
if [ "$ZIPS" = "$DEST/.zips" ]; then
    echo "Delete them later if desired:"
    echo "rm -rf \"$ZIPS\""
fi

[ "$bad" -eq 0 ]
