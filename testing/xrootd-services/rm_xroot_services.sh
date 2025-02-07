#!/bin/bash

# Define service files
CMSD_SERVICE_FILE="/etc/systemd/system/cmsd@cluster.service"
XROOTD_SERVICE_FILE="/etc/systemd/system/xrootd@cluster.service"
PYTHON_SCRIPT="/usr/local/bin/wait_script.py"

# Stop all instances of the services
echo "Stopping services..."
systemctl stop cmsd@cluster xrootd@cluster

# Disable all instances of the services
echo "Disabling services..."
systemctl disable cmsd@cluster xrootd@cluster

# Remove the service files
echo "Removing service files..."
rm -f "$CMSD_SERVICE_FILE" "$XROOTD_SERVICE_FILE"

# Reload systemd configuration
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Reset failed service states (if any)
systemctl reset-failed cmsd@cluster xrootd@cluster

# Verify services are removed
echo "Checking if services are still present..."
if systemctl list-units --type=service | grep -E 'cmsd@|xrootd@'; then
    echo "Some services are still present. Manual cleanup may be needed."
else
    echo "All services removed successfully."
    if [[ -e "$PYTHON_SCRIPT" ]]; then
        echo "Removing $PYTHON_SCRIPT"
        rm -f $PYTHON_SCRIPT
    fi
fi

echo "Service removal complete."

