FROM evtol/base:noetic

SHELL ["/bin/bash", "-c"]

ARG DEBIAN_FRONTEND=noninteractive

# Create an isolated Python environment for evaluation tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/eval-venv

# Upgrade packaging tools inside the venv only
RUN /opt/eval-venv/bin/pip install --no-cache-dir \
    --upgrade pip setuptools wheel

# Install evaluation dependencies inside the venv.
# evo 1.32+ requires Python >= 3.10; ROS Noetic has 3.8, so 1.31.1 is the last usable release.
RUN /opt/eval-venv/bin/pip install --no-cache-dir \
    "evo==1.31.1" \
    numpy \
    matplotlib \
    pandas \
    tabulate

# Save exact installed versions
RUN /opt/eval-venv/bin/pip freeze > /opt/eval-requirements.txt

# Make venv the default Python environment
ENV PATH="/opt/eval-venv/bin:${PATH}"

WORKDIR /output

CMD ["bash"]
