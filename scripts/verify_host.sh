#!/usr/bin/env bash

set -u

fail=0

chk() {
    printf '%-34s' "$1"
    shift

    if "$@" >/dev/null 2>&1; then
        echo "OK"
    else
        echo "FAIL"
        fail=1
    fi
}

chk "docker engine (no sudo)" docker run --rm hello-world
chk "compose plugin" docker compose version
chk "host nvidia driver" nvidia-smi
chk "gpu inside container" docker run --rm --gpus all ubuntu:22.04 nvidia-smi

display_num="${DISPLAY#:}"
display_num="${display_num%%.*}"

chk "X socket present" test -S "/tmp/.X11-unix/X${display_num}"

echo

echo "Docker root dir : $(docker info 2>/dev/null | sed -n 's/^ Docker Root Dir: //p')"
echo "Driver version : $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo unavailable)"
echo "Free space here : $(df -h . | awk 'NR==2{print $4}')"
echo "RAM / cores : $(free -g | awk 'NR==2{print $2"GB"}') / $(nproc)"

echo

if [ "$fail" -eq 0 ]; then
    echo "Host is ready."
else
    echo "Fix the FAILs above before building."
fi

exit "$fail"
