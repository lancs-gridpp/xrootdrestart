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
# Configure the current machine and remote xroot servers to work with
# xrootdrestart.
#
# On the computer where you run this script:
# It checks for a config file.  If one isn't present, a default one is
# created and the program exits to allow the user to end the config file.
# 
# Once a config file can be read, it checks for ssh keys.  If keys cannot
# be found, an ECDSA key pair is created.
#
# Write access to the log file is checked.
#
# For each server listed in the config file:
# Setup ssh so that connections can be made using the key pair.
# Create a user that will connect using ssh (xrootdrestart)
# Set the user so they can use sudo to run systemctl.
# 

import os
import sys

# Include the parent directory in the sys.path to include xrootdrestart
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

import stat
import configparser
import subprocess
import socket
from pathlib import Path
import paramiko
import xrootdrestart
import logging

def check_or_create_ecdsa_key(pkey_path, pkey_name):
    private_key_path = pkey_path / pkey_name
    public_key_path = pkey_path / f"{pkey_name}.pub"

    if not private_key_path.exists():
        logger.info(f" Private key not found at {private_key_path}. Generating new ECDSA key pair...")
        key = paramiko.ECDSAKey.generate()
        with open(private_key_path, 'w') as private_key_file:
            key.write_private_key_file(private_key_file.name)
        os.chmod(private_key_path, stat.S_IRUSR)

        with open(public_key_path, 'w') as public_key_file:
            public_key_file.write(f"{key.get_name()} {key.get_base64()}")

        logger.info(f"[SUCCESS] Created ECDSA key pair at {private_key_path} and {public_key_path}.")
    else:
        logger.info(f"[SUCCESS] ECDSA private key already exists at {private_key_path}.")

    return private_key_path, public_key_path


def check_log_file(log_file):
    log_file_path = Path(log_file)
    if not log_file_path.exists():
        logger.info(f" Log file not found at {log_file_path}. Creating it...")
        log_file_path.touch(mode=0o600, exist_ok=True)

    if not os.access(log_file_path, os.W_OK):
        logger.info(f"[ERROR] Log file at {log_file_path} is not writable. Exiting.")
        exit(1)

    logger.info(f"[SUCCESS] Log file at {log_file_path} is exists and is writable.")


def user_exists(ssh_client, ssh_user):
    stdin, stdout, stderr = ssh_client.exec_command(f"id -u {ssh_user}")
    return stdout.channel.recv_exit_status() == 0


def add_user(ssh_client,ssh_user):
    logger.info(f" Creating user {ssh_user}...")
    stdin, stdout, stderr = ssh_client.exec_command(f"useradd -M -s /bin/bash {ssh_user}")
    if stdout.channel.recv_exit_status() != 0:
        raise Exception("Error creating user {ssh_user}.  Error: {stderr.read().decode}")
        exit(1)
    logger.info(f"[SUCCESS] User {ssh_user} created")


def user_sudo_rule_exists(ssh_client, target_user):
    # Check if the rule for systemctl is defined
    try:
        specific_rule = "(ALL) NOPASSWD: /usr/bin/systemctl"
        command = f"sudo -l -U {target_user}"
        stdin, stdout, stderr = ssh_client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
    except Exception as e:
        raise Exception(f"An error occurred while checking sudo rules: {e}")

    # Raise an exception if there is an error
    if error:
        raise Exception(f"Error checking sudo rules for {target_user}: {error.strip()}")
    # Return True if the specific rule exists, False otherwise
    return specific_rule in output


def add_user_to_sudoers(ssh_client,ssh_user):
    try:
        sudo_stmnt = f"{ssh_user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl"
        sudoers_file = f"/etc/sudoers.d/{ssh_user}"
        stdin, stdout, stderr = ssh_client.exec_command(f"echo '{sudo_stmnt}' | sudo EDITOR='tee -a' visudo -f {sudoers_file}")
    except Exception as e:
        logger.info(f"[ERROR] Error adding user to sudoers: {str(e)}")
        exit(1)

    if stdout.channel.recv_exit_status() != 0:
        raise Exception("Error creating user {ssh_user}.  Error: {stderr.read().decode}")
        exit(1)
    logger.info("[SUCCESS] User added to sudoers")


def can_connect_as_user(ssh_client, server, user_name, private_key_file):
    try:
        if private_key_file == "":
            # A key wasn't give so use connect and let the system find suitable keys.
            ssh_client.connect(server, username=user_name)
        else:
            # A key has been given. Connect but disable using the system to find valid keys.
            private_key = paramiko.ECDSAKey.from_private_key_file(private_key_file)
            ssh_client.connect(server, username=user_name, pkey=private_key, allow_agent=False, look_for_keys=False)

        ssh_client.close()
        return True

    except Exception as e:
        logger.info(str(e))
        return False


def test_user_ssh_connection(ssh_client,ssh_user,server,private_key_path):
    testssh  = paramiko.SSHClient()
    testssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if not can_connect_as_user(testssh, server, ssh_user, ""):
            logger.info(f" Unable to connect as {ssh_user}")
            logger.info(f" Copying authorized keys to {ssh_user}")
            sftp_client = ssh_client.open_sftp()
            sftp_client.put("create_ssh_dir.sh", "/tmp/create_ssh_dir.sh")
            stdin, stdout, stderr = ssh_client.exec_command(f"chmod +x /tmp/create_ssh_dir.sh; /tmp/create_ssh_dir.sh {ssh_user}")
            if stdout.channel.recv_exit_status() != 0:
                logger.info(f"[ERROR] Unable to copy authorized keys.")
                logger.info(stdin.read().decode(), stdout.read().decode(), stderr.read().decode())
                exit(1)

            logger.info(f" Trying to connect as {ssh_user} again")
            if not can_connect_as_user(testssh, server, ssh_user, ""):
                logger.info(f"[ERROR] Unable to connect to {server} as {ssh_user}")
                exit(1)
            logger.info(f" Connected to {server} ok")

            # We can connect as ssh_user now so copy the xrootdrestart user key to the server.
            try:
                logger.info(f" Copying ssk key to {server}")
                subprocess.run(["ssh-copy-id", "-i", str(private_key_path.with_suffix(".pub")), f"{ssh_user}@{server}"], check=True)
            except Exception as e:
                logger.info(f"[ERROR] Unable to copy ssh key for {ssh_user} to {server}")
                logger.info(str(e))
                exit(1)

        logger.info(f" Checking connection to {server} using the private key")
        if not can_connect_as_user(testssh, server, ssh_user, private_key_path):
            logger.info("[ERROR] Unable to connect to {server} as {ssh_user} using the private key")
            exit(1)
        else:
            logger.info(f"[SUCCESS] Connected to {server} as {ssh_user} using the private key")

    finally:
        testssh.close()


def check_server(server, ssh_user, private_key_path):
    logger.info(f" Verifying the setup of {server}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(server, username="root")
    except Exception as e:
        logger.info(f"[ERROR] Unable to connect to {server}")
        exit(1)

    try:
        # Make sure the user exists on the server.
        logger.info(f" Checking user {ssh_user} exists.")
        if not user_exists(ssh,ssh_user):
            add_user(ssh,ssh_user)
        else:
            logger.info(f"[SUCCESS] User {ssh_user} already exists")

        # Make sure the user is allowed to sudo systemctl
        logger.info("Checking sudo rules...")
        if not user_sudo_rule_exists(ssh,ssh_user):
            add_user_to_sudoers(ssh,ssh_user)
        else:
            logger.info(f"[SUCCESS] sudo rule already exists")

        logger.info(f" Checking ssh access for {ssh_user}")
        test_user_ssh_connection(ssh,ssh_user,server,private_key_path)

    except Exception as e:
        logger.info(f"Failed to configure {server}: {e}")
        exit(1)

    finally:
        ssh.close()


def check_network_connection(url_key,url):
    try:
        logger.info(f" Checking network connection for {url_key} - {url}...")
        hostname = url.split("//")[-1].split(":")[0]
        port = int(url.split(":")[-1])

        with socket.create_connection((hostname, port), timeout=5):
            logger.info(f"[SUCCESS] Successfully connected to {url}.")
    except Exception as e:
        logger.info(f"[ERROR] Failed to connect to {url}: {e}")
        exit(1)


def main():
    global logger
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Make sure the config directory and config file exist. 
    config_dir = Path(xrootdrestart.CONFIG_DIR)
    config_dir.parent.mkdir(parents=True, exist_ok=True)
    config_file = os.path.join(config_dir, xrootdrestart.CONFIG_FILE_NAME)
    try:
        with open(config_file, 'x') as f:
            config = Config()
            config.save_config()
            logger.info(f"Config file {config_file} created at. Please edit it and run the script again.")
            exit(1)
    except FileExistsError:
        logger.info(f"[SUCCESS] The config file already exists: {config_file}")

    # We're still here so load the config file.
    config = xrootdrestart.Config(False)
    config.load_config()

    # Make sure the ssh keys exist
    pkey_name = config.pkey_name
    pkey_path = Path(config.pkey_path)
    pkey_path.mkdir(parents=True, exist_ok=True)
    private_key_path, public_key_path = check_or_create_ecdsa_key(pkey_path, pkey_name)

    # Check the log file is writeable.
    check_log_file(xrootdrestart.LOG_FILE)

    # Go through the server list and configure them.
    for server in config.servers:
        check_server(server, config.ssh_user, private_key_path)

    # Validate access to the monitoring urls.
    if config.alert_url:
        check_network_connection('Alert Manager',config.alert_url)
#    if config.prom_url:
#        check_network_connection('Prometheus',config.prom_url)
    if config.pushgw_url:
        check_network_connection('PUSH Gateway',config.pushgw_url)
    

    logger.info("All checks completed successfully.")

if __name__ == "__main__":
    main()

