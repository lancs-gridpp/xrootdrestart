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
import argparse

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
import getpass
    
EXIT_CONFIG_CREATED = 1
ERR_CREATE_USER = 2
ERR_SUDO_USER = 3
ERR_FAILED_TO_CONNECT = 4
ERR_KEY_COPY = 5
ERR_FAILED_TO_CONNECT = 6
ERR_FAILED_TO_CONFIGURE = 7
ERR_LOG_NO_WRITE = 8
ERR_INVALID_MODE = 9

VENV_PATH = ".venv"
CONTAINER_TYPE = "podman"

is_root = os.geteuid() == 0
username = getpass.getuser()

def create_virtualenv(venv_path):
    """
    Create a virtual environment if it doesn't exist.
    """
    try:
        if not venv_path.exists():
            logger.info(f"Creating virtual environment at {venv_path}...")
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
            logger.info("[SUCCESS] Virtual environment created.")
        else:
            logger.info(f"[SUCCESS] Virtual environment already exists at {venv_path}.")
    except Exception as e:
        logger.error(f"[ERROR] Failed to create virtual environment: {e}")
        exit(ERR_FAILED_TO_CONFIGURE)

def activate_virtualenv(venv_path):
    """
    Activate the virtual environment.
    """
    try:
        activate_script = venv_path / 'bin' / 'activate'
        if not activate_script.exists():
            logger.error(f"[ERROR] Virtual environment activation script not found at {activate_script}.")
            exit(ERR_FAILED_TO_CONFIGURE)
        
        # Activate the virtual environment
        logger.info(f"Activating virtual environment at {venv_path}...")
        activate_command = f"source {activate_script}"
        subprocess.run(activate_command, shell=True, check=True)
        logger.info("[SUCCESS] Virtual environment activated.")
    except Exception as e:
        logger.error(f"[ERROR] Failed to activate virtual environment: {e}")
        exit(ERR_FAILED_TO_CONFIGURE)
        
def create_systemd_service(service_name):
    """
    Create a systemd service file for the xrootdrestart script.
    """
    try:
        script_path = os.path.join(os.getcwd(), "xrootdrestart.py")
        python_bin = os.path.join(os.getcwd(), ".venv", "bin", "python")
        systemd_path = Path("/etc/systemd/system") if is_root else Path.home() / ".config" / "systemd" / username
        systemd_path.mkdir(parents=True, exist_ok=True)
        service_file = os.path.join(systemd_path,f"{service_name}.service")

        # Ensure the python script exists
        if not os.path.isfile(script_path):
            logger.error(f"[ERROR] Python script not found at {script_path}")
            exit(ERR_FAILED_TO_CONFIGURE)
        else:
            # Create systemd service file
            logger.info(f"Creating systemd service file at {service_file}...")
            service_content = f"""[Unit]
Description=Restart XRootD Service Script
After=network.target

[Service]
Type=simple
ExecStart={python_bin} {script_path}
Restart=always
WorkingDirectory={os.path.dirname(script_path)}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
            # Write the service file
            with open(service_file, 'w') as f:
                f.write(service_content)

            # TODO: Why was this done?
            # Set executable permissions for the script
#            subprocess.run(["sudo", "chmod", "+x", script_path], check=True)

            # Reload systemd and enable the service
            logger.info("Reloading systemd daemon...")
            if is_root:
                subprocess.run(["systemctl", "daemon-reload"], check=True)
                logger.info(f"Enabling {service_name} service...")
                subprocess.run(["systemctl", "enable", service_name], check=True)

                # Start the service
                logger.info(f"Starting {service_name} service...")
                subprocess.run(["systemctl", "start", service_name], check=True)

                # Check service status
                logger.info("Checking service status...")
                subprocess.run(["systemctl", "status", service_name, "--no-pager"], check=True)
            else:
                subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
                logger.info(f"Enabling {service_name} service...")
                subprocess.run(["systemctl", "--user", "enable", service_name], check=True)

                # Start the service
                logger.info(f"Starting {service_name} service...")
                subprocess.run(["systemctl", "--user", "start", service_name], check=True)

                # Check service status
                logger.info("Checking service status...")
                subprocess.run(["systemctl", "--user", "status", service_name, "--no-pager"], check=True)


            logger.info("[SUCESS] xrootdrestart service setup complete!")
    except Exception as e:
        logger.error(f"[ERROR] Failed to create systemd service: {e}")
        exit(ERR_FAILED_TO_CONFIGURE)

def create_container_image():
    """
    Create a container image using Dockerfile
    """
    logger.info(f"Building {CONTAINER_TYPE} image 'xrootdrestart' using Dockerfile...")
    try:
        subprocess.run([CONTAINER_TYPE, "build", "-t", "xrootdrestart", "."], check=True)
        logger.info("[SUCCESS] Container image 'xrootdrestart' created successfully.")
    except subprocess.CalledProcessError as e:
        logger.error("[ERROR] Failed to build container image: {e}")
        exit(ERR_FAILED_TO_CONFIGURE)
    except FileNotFoundError:
        logger.error(f"[ERROR] {CONTAINER_TYPE} not found. Please install {CONTAINER_TYPE}.")
        exit(ERR_FAILED_TO_CONFIGURE)


def output_container_run_command(config_dir, pkey_path, log_file, metrics_port):
    """
    Output the command to create and run an xrootdrestart container
    """
    try:
        config_dir_abs = os.path.abspath(config_dir)
        pkey_path_abs = os.path.abspath(pkey_path)
        log_file_abs = os.path.abspath(log_file)
        log_dir = os.path.dirname(log_file_abs)

        vol_pkey = f"        -v {pkey_path_abs}:{pkey_path_abs} \\\n        " if pkey_path_abs != config_dir_abs else ""
#        vol_pkey = f"-v {pkey_path_abs}:{pkey_path_abs} \\\n        "

        run_command = f"""podman run -d \\
        --name xrootdrestart \\
        -v {config_dir_abs}:/etc/xrootdrestart \\
        {vol_pkey}-v {log_dir}:{log_dir} \\
        -p {metrics_port}:{metrics_port} \\
        xrootdrestart"""
        
        logger.info("Container run command:")
        logger.info("=" * 50)
        logger.info(run_command)
        logger.info("=" * 50)
        
        logger.info("To start the container, run the above command.")
        logger.info("To stop the container: podman stop xrootdrestart-container")
        logger.info("To remove the container: podman rm xrootdrestart-container")
    except Exception as e:
        logger.error(f"[ERROR] Failed to output container run command: {e}")
        exit(ERR_FAILED_TO_CONFIGURE)

def check_or_create_ecdsa_key(pkey_path, pkey_name):
    """
    Check if an ECDSA key pair exists at the specified path.  If not, create a new ECDSA key pair.
    """
    try:
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
    except Exception as e:
        logger.error(f"[ERROR] Failed to create or check ECDSA key pair: {e}")
        exit(ERR_FAILED_TO_CONFIGURE)

def check_log_file(log_file):
    """
    Check if the log file exists and is writable. If not, create it with appropriate permissions.
    """
    try:
        log_file_path = Path(log_file)
        if not log_file_path.exists():
            logger.info(f" Log file not found at {log_file_path}. Creating it...")
            log_file_path.touch(mode=0o600, exist_ok=True)

        if not os.access(log_file_path, os.W_OK):
            logger.info(f"[ERROR] Log file at {log_file_path} is not writable. Exiting.")
            exit(ERR_LOG_NO_WRITE)

        logger.info(f"[SUCCESS] Log file at {log_file_path} exists and is writable.")
    except Exception as e:
        logger.error(f"[ERROR] Failed to check or create log file: {e}")
        exit(ERR_LOG_NO_WRITE)

def user_exists(ssh_client, ssh_user):
    """
    Check if a user exists on the remote server.
    """
    try:
        stdin, stdout, stderr = ssh_client.exec_command(f"id -u {ssh_user}")
        return stdout.channel.recv_exit_status() == 0
    except Exception as e:
        logger.error(f"[ERROR] An error occurred while checking if user {ssh_user} exists: {e}")
        exit(ERR_FAILED_TO_CONFIGURE)

def add_user(ssh_client,ssh_user):
    """
    Create a new user on the remote server.
    """
    try:
        logger.info(f" Creating user {ssh_user}...")
        stdin, stdout, stderr = ssh_client.exec_command(f"useradd -M -s /bin/bash {ssh_user}")
        if stdout.channel.recv_exit_status() != 0:
            raise Exception("Error creating user {ssh_user}.  Error: {stderr.read().decode}")
            exit(ERR_CREATE_USER)
        logger.info(f"[SUCCESS] User {ssh_user} created")
    except Exception as e:
        logger.error(f"[ERROR] Error creating user {ssh_user}: {str(e)}")
        exit(ERR_CREATE_USER)

def user_sudo_rule_exists(ssh_client, target_user):
    # Check if the rule for systemctl is defined
    try:
        specific_rule = "(ALL) NOPASSWD: /usr/bin/systemctl"
        command = f"sudo -l -U {target_user}"
        stdin, stdout, stderr = ssh_client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        if error:
            logger.error(f"[ERROR] Error checking sudo rules for {target_user}: {error.strip()}")
            exit(ERR_FAILED_TO_CONFIGURE)
    except Exception as e:
        logger.error(f"[ERROR] An error occurred while checking sudo rules: {e}")
        exit(ERR_FAILED_TO_CONFIGURE)

    return specific_rule in output


def add_user_to_sudoers(ssh_client,ssh_user):
    try:
        sudo_stmnt = f"{ssh_user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl"
        sudoers_file = f"/etc/sudoers.d/{ssh_user}"
        stdin, stdout, stderr = ssh_client.exec_command(f"echo '{sudo_stmnt}' | sudo EDITOR='tee -a' visudo -f {sudoers_file}")
        if stdout.channel.recv_exit_status() != 0:
            logger.error(f"[ERROR] Error creating user {ssh_user}.  Error: {stderr.read().decode}")
            exit(ERR_SUDO_USER)
    except Exception as e:
        logger.error(f"[ERROR] Error adding user to sudoers: {str(e)}")
        exit(ERR_SUDO_USER)

    logger.info("[SUCCESS] User added to sudoers")


def can_connect_as_user(ssh_client, server, user_name, private_key_file):
    try:
        if private_key_file == "":
            # A key wasn't give to use. Connect and let the system find suitable keys.
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
    try:
        testssh  = paramiko.SSHClient()
        testssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if not can_connect_as_user(testssh, server, ssh_user, ""):
            logger.info(f" Unable to connect as {ssh_user}")
            logger.info(f" Copying authorized keys to {ssh_user}")
            sftp_client = ssh_client.open_sftp()
            sftp_client.put("create_ssh_dir.sh", "/tmp/create_ssh_dir.sh")
            stdin, stdout, stderr = ssh_client.exec_command(f"chmod +x /tmp/create_ssh_dir.sh; /tmp/create_ssh_dir.sh {ssh_user}")
            if stdout.channel.recv_exit_status() != 0:
                logger.error(f"[ERROR] Unable to copy authorized keys: {stderr.read().decode()}")
                exit(ERR_KEY_COPY)

            logger.info(f" Trying to connect as {ssh_user} again")
            if not can_connect_as_user(testssh, server, ssh_user, ""):
                logger.error(f"[ERROR] Unable to connect to {server} as {ssh_user}")
                exit(ERR_FAILED_TO_CONNECT)
            logger.info(f" Connected to {server} ok")

            # We can connect as ssh_user now so copy the xrootdrestart user key to the server.
            try:
                logger.info(f" Copying ssh key to {server}")
                subprocess.run(["ssh-copy-id", "-i", str(private_key_path.with_suffix(".pub")), f"{ssh_user}@{server}"], check=True)
            except Exception as e:
                logger.error(f"[ERROR] Error copying ssh key for {ssh_user} to {server}: {str(e)}")
                exit(ERR_KEY_COPY)

        logger.info(f" Checking connection to {server} using the private key")
        if not can_connect_as_user(testssh, server, ssh_user, private_key_path):
            # A new private key might have been generated so copy the identity to the server again and retry.
            logger.info(f" Unable to connect to {server} as {ssh_user} using the private key. Copying the key again.")
            try:
                subprocess.run(["ssh-copy-id", "-i", str(private_key_path.with_suffix(".pub")), f"{ssh_user}@{server}"], check=True)
            except Exception as e:
                logger.error(f"[ERROR] Error copying ssh key for {ssh_user} to {server}: {str(e)}")
                exit(ERR_KEY_COPY)
            logger.info(f" Trying to connect to {server} as {ssh_user} using the private key again")
            if not can_connect_as_user(testssh, server, ssh_user, private_key_path):
                logger.error(f"[ERROR] Unable to connect to {server} as {ssh_user} using the private key after copying it again")
                exit(ERR_FAILED_TO_CONNECT)
            logger.info(f"[SUCCESS] Connected to {server} as {ssh_user} using the private key")
        else:
            logger.info(f"[SUCCESS] Connected to {server} as {ssh_user} using the private key")

    except Exception as e:
        logger.info(f"[ERROR] An error occurred while testing SSH connection: {e}")
        exit(ERR_FAILED_TO_CONNECT)

    finally:
        testssh.close()


def check_server(server, ssh_user, private_key_path):
    """
    Check if the server is reachable and configure it for xrootdrestart.
    """
    try:
        logger.info(f" Verifying the setup of {server}")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server, username="root")
    except Exception as e:
        logger.error(f"[ERROR] Unable to connect to {server}")
        exit(ERR_FAILED_TO_CONNECT)

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
        logger.error(f"[ERROR] Failed to configure {server}: {str(e)}")
        exit(ERR_FAILED_TO_CONFIGURE)

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
        logger.error(f"[ERROR] Failed to connect to {url}: {str(e)}")
        exit(ERR_FAILED_TO_CONNECT)


def parse_arguments():
    parser = argparse.ArgumentParser(description='Setup xrootdrestart for systemd or container deployment')
    parser.add_argument('mode', choices=['systemd', 'container'], 
                       help='Deployment mode: systemd or container')
    return parser.parse_args()


def main():
    global logger
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info(f"Running setup in {args.mode} mode")

    # Make sure the config directory and config file exist. 
    config_dir = Path(xrootdrestart.CONFIG_DIR)
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = os.path.join(config_dir, xrootdrestart.CONFIG_FILE_NAME)
    try:
        with open(config_file, 'x') as f:
            config = xrootdrestart.Config()
            config.save_config()
            logger.info(f"Config file {config_file} created at. Please edit it and run the script again.")
            exit(EXIT_CONFIG_CREATED)
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

    # Mode-specific setup
    if args.mode == 'systemd':
        create_virtualenv(Path(VENV_PATH))    
        activate_virtualenv(Path(VENV_PATH))
        create_systemd_service("xrootdrestart")
        logger.info("Systemd setup completed successfully.")

    elif args.mode == 'container':
        create_container_image()
        output_container_run_command(config_dir, pkey_path, Path(xrootdrestart.LOG_FILE),xrootdrestart.METRICS_PORT)
        logger.info("Container setup completed successfully.")

    logger.info("All checks completed successfully.")

if __name__ == "__main__":
    main()