#!/bin/bash
#---------------------------------------------------------------------------------
# Copyright (c) 2025 Lancaster University
# Written by: Gerard Hand
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#---------------------------------------------------------------------------------
#
# Usage:
# create_ssh_dir.sh <user name>
#
# Description:
# The script will create the .ssh directory and files for <user name> if they
# don't already exist.  No action is taken if the specified <user name> does not
# exist.  
#
# If the .ssh directory is created, the .ssh settings for the current 
# user will be used for <user name>.  This will allow the current user to
# connect as <user name>.

if [ $# -ne 1 ]; then
    echo "Usage: $0 <username>"
    exit 1
fi

USERNAME=$1

# Get the home directory and .ssh directory of the user running the script
CURRENT_USER_HOME=$(eval echo "~$USER")
CURRENT_USER_SSH_DIR="$CURRENT_USER_HOME/.ssh"

# Check if the user exists
if ! id -u "$USERNAME" &>/dev/null; then
    echo "User '$USERNAME' does not exist"
    exit 1
fi

# Get the target user's home directory and .ssh directory
TARGET_USER_HOME=$(eval echo "~$USERNAME")
TARGET_USER_SSH_DIR="$TARGET_USER_HOME/.ssh"

# Check if the .ssh directory exists for the target user
if [ ! -d "$TARGET_USER_SSH_DIR" ]; then
    # Create the .ssh directory with suitable permissions
    mkdir -p "$TARGET_USER_SSH_DIR"
    chown -R "$USERNAME:$USERNAME" "$TARGET_USER_SSH_DIR"
    chmod 700 "$TARGET_USER_SSH_DIR"
else
    echo ".ssh directory already exists for user '$USERNAME'"
fi

# Copy authorized_keys and known_hosts files from the current user's .ssh directory
if [ -f "$CURRENT_USER_SSH_DIR/authorized_keys" ] && [ ! -f "$TARGET_USER_SSH_DIR/authorized_keys" ]; then
    cp "$CURRENT_USER_SSH_DIR/authorized_keys" "$TARGET_USER_SSH_DIR/"
    chown "$USERNAME:$USERNAME" "$TARGET_USER_SSH_DIR/authorized_keys"
    chmod 600 "$TARGET_USER_SSH_DIR/authorized_keys"
else
    echo "authorized_keys file already exists for user '$USERNAME' or source file not found."
fi

if [ -f "$CURRENT_USER_SSH_DIR/known_hosts" ] && [ ! -f "$TARGET_USER_SSH_DIR/known_hosts" ]; then
    cp "$CURRENT_USER_SSH_DIR/known_hosts" "$TARGET_USER_SSH_DIR/"
    chown "$USERNAME:$USERNAME" "$TARGET_USER_SSH_DIR/known_hosts"
    chmod 644 "$TARGET_USER_SSH_DIR/known_hosts"
else
    echo "known_hosts file already exists for user '$USERNAME' or source file not found."
fi

