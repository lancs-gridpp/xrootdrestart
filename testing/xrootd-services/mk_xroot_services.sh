#!/bin/bash

# Define file paths
PYTHON_SCRIPT="/usr/local/bin/wait_script.py"
CMSD_SERVICE="/etc/systemd/system/cmsd@cluster.service"
XROOTD_SERVICE="/etc/systemd/system/xrootd@cluster.service"

# Create the Python script
cat <<EOF > "$PYTHON_SCRIPT"
#!/usr/bin/env python3
# Script run by the cmsd@cluster and xrootd@cluster dummy services

import time
import signal
import random
import sys

def handle_signal(signum, frame):
    print(f"Received termination signal ({signum}), delaying exit...")
    time.sleep(random.randint(10, 30))
    print("Exiting now.")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

print("Python script is running. Waiting to be terminated...")
while True:
    time.sleep(1)
EOF

# Make the script executable
chmod +x "$PYTHON_SCRIPT"

# Create the CMSD systemd service file
cat <<EOF > "$CMSD_SERVICE"
[Unit]
Description=CMSD Service for cluster %i
After=network.target

[Service]
ExecStart=$PYTHON_SCRIPT
Restart=always
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

# Create the XRootD systemd service file
cat <<EOF > "$XROOTD_SERVICE"
[Unit]
Description=XRootD Service for cluster %i
After=network.target

[Service]
ExecStart=$PYTHON_SCRIPT
Restart=always
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd daemon
systemctl daemon-reload

# Enable and start the services
systemctl enable cmsd@cluster
systemctl enable xrootd@cluster
systemctl start cmsd@cluster
systemctl start xrootd@cluster

# Show the status of the services
systemctl status cmsd@cluster --no-pager
systemctl status xrootd@cluster --no-pager

