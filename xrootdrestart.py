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
# Exit Codes:
# 0 - Clean exit
# 1 - Private key created.  Copy public key id to servers before restarting the program.
# 2 - Terminated because of an exception.
# 3 - Signal shutdown.
#
#---------------------------------------------------------------------------------
# Notes:
# - The program doesn't exit immediately the insufficient servers alert is generated.  It
#   waits until the the start of the next server to exit.
#  
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import configparser
from datetime import datetime, timedelta
import json
import logging
import os
import paramiko
from pathlib import Path
from prometheus_client import start_http_server, Gauge, Histogram, CollectorRegistry, push_to_gateway
import requests
import schedule
import signal
import socket
import subprocess
import sys
import time
import threading
import traceback

#-----------------------------------------------------------------------------------------------------
# Global data
logger = None
alerter = None
heartbeat = None

#-----------------------------------------------------------------------------------------------------
# Constants
VERSION = "1.0.0"
OK = 'OK'
ERR = 'ERR'
PULL = 'PULL'
PUSH = 'PUSH'
LOG_FILE = '/var/log/xrootdrestart.log'
#LOG_FILE = 'xrootdrestart.log'
HEARTBEAT_INTERVAL = 5

# Prometheus and Alertmanager
ALERT_XROOTDRESTART_CONNECT_ERROR = 'XROOTDRESTART_CONNECT_ERROR'
ALERT_XROOTDRESTART_RESTART_ERROR = 'XROOTDRESTART_RESTART_ERROR'
ALERT_XROOTDRESTART_INSUFFICIENT_SERVERS = 'XROOTDRESTART_INSUFFICIENT_SERVERS'
ALERT_TYPE_LIST=[ALERT_XROOTDRESTART_CONNECT_ERROR,ALERT_XROOTDRESTART_RESTART_ERROR,ALERT_XROOTDRESTART_INSUFFICIENT_SERVERS]

#-----------------------------------------------------------------------------------------------------
# Default Config Options Values
is_root = os.geteuid() == 0
config_path = Path("/etc/xrootdrestart/" if is_root else os.path.expanduser("~/.config/xrootdrestart/"))

SSH_USER         = 'xrootdrestart'
CLUSTER_ID       = 'production'
CMSD_PERIOD      = 3 * 24 * 3600    # 3 days
CMSD_WAIT        = 300              # 5 mins
MIN_OK           = 1
PKEY_NAME        = 'xrootdrestartkey'
PKEY_PATH        = config_path
CONFIG_DIR       = config_path
CONFIG_FILE_NAME = 'xrootdrestart.conf'
LOG_LEVEL        = 'INFO'
SVR_LIST         = ''
XROOTD_SVC       = 'xrootd@cluster'
CMSD_SVC         = 'cmsd@cluster'
PROMETHEUS_URL   = 'http://localhost:9090'
ALERTMANAGER_URL = 'http://localhost:9093'
METRICS_PORT     = 8000
PUSHGW_URL       = 'http://localhost:9091'
SERVICE_TIMEOUT  = 120
METRICS_METHOD   = PULL

#--------------------------------------- Config Class -------------------------------------------------------
# Holds the current settings used in the program.
#
# Config Options
#
# alrt_url        - Alert-manager URL + port.
# cluster_id      - Value to use in the metrics cluster label.
# cmsd_period     - Time in seconds between restarting the services on a server.
# cmsd_svc        - CMSD service name.
# cmsd_wait       - Time in seconds to wait after stopping cmsd before stopping xrootd.
# log_level       - Logging output level: DEBUG, INFO, WARNING, ERROR, CRITICAL.
# metrics_port    - Listening port to provide prometheus metrics.
# metrics_method  - Method of transfering metrics: PUSH, PULL.
# min_ok          - If the number of servers that are ok drops below this number the program will stop restarting services.
# pkey_name       - File name of the private key file.  (not including path). Set blank to not use a pkey.
# pkey_path       - Directory containing pkey_name file.
# prom_url        - Prometheus URL + port.
# pushgw_url      - URL + port of the gateway for pushing prometheus metrics.
# servers         - A comma separated list of server host names.
# service_timeout - Seconds to wait for a service to stop or start.
# ssh_user        - User used by the ssh connection.
# xrootd_svc      - XRootD service name.
#
# Options automatically set but not saved to the settings file
# hostname        - Hostname of the computer running this program.
#
class Config:

    def __init__(self,fail_no_key=True):
        # If True reading the config will exit the program if the private key doesn't exist. 
        self.__fail_no_key = fail_no_key
        
        self.config_dir = CONFIG_DIR
        self.config_file = os.path.join(self.config_dir, CONFIG_FILE_NAME)
        
        self.parser = configparser.ConfigParser()
        # Time between restarts of xrootd deamon. (seconds)
        self.cmsd_period = CMSD_PERIOD
        # Wait time between stopping cmsd and restarting xrootd (seconds)
        self.cmsd_wait = CMSD_WAIT
        # List of servers with xrootd
        self.servers = []
        # Path to and name of private key for ssh connection
        self.pkey_name = PKEY_NAME
        self.pkey_path = self.config_dir

        # Metrics cluster label value
        self.cluster_id = CLUSTER_ID
        self.ssh_user = SSH_USER
        self.min_ok = MIN_OK
        self.xrootd_svc = XROOTD_SVC
        self.cmsd_svc = CMSD_SVC
        self.log_level = LOG_LEVEL
        self.prom_url = PROMETHEUS_URL
        self.alert_url = ALERTMANAGER_URL
        self.pushgw_url = PUSHGW_URL
        self.metrics_port = METRICS_PORT
        self.metrics_method = METRICS_METHOD
        self.service_timeout = SERVICE_TIMEOUT


    def load_config(self):
        # Read the settings from the config file.
        # Create a default config file if it doesn't exist.
        if not os.path.exists(self.config_file):
            logger.info(f"Create a default config file: {self.config_file}")
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            self.save_config()

        # Read the contents of the file and extract the settings.
        self.parser.read(self.config_file)

        try:
            general = self.parser['general']
        except (NoOptionError, NoSectionError):
            general = {}  
            
        self.log_level = general.get('log_level',fallback=LOG_LEVEL)
        if self.log_level not in logging._nameToLevel:
            self.log_level = LOG_LEVEL

        self.cluster_id = general.get('cluster_id', fallback=CLUSTER_ID)
        self.cmsd_period = int(general.get( 'cmsd_period', fallback=CMSD_PERIOD))
        self.cmsd_wait = int(general.get('cmsd_wait', fallback=CMSD_WAIT))
        self.pkey_name = general.get('pkey_name', fallback=PKEY_NAME)
        self.pkey_path = os.path.expanduser(general.get('pkey_path', fallback=PKEY_PATH))
        self.ssh_user = general.get('ssh_user', fallback=SSH_USER)
        self.min_ok = int(general.get('min_ok', fallback=MIN_OK))
        self.xrootd_svc = general.get('xrootd_svc', fallback=XROOTD_SVC)
        self.cmsd_svc = general.get('cmsd_svc', fallback=CMSD_SVC)
        servers_str = general.get( 'servers', fallback=SVR_LIST)
        self.servers = [server.strip() for server in servers_str.split(',')] if servers_str else []
        self.prom_url = general.get('prom_url',fallback=PROMETHEUS_URL)
        self.alert_url = general.get('alert_url',fallback=ALERTMANAGER_URL)
        self.pushgw_url = general.get('pushgw_url',fallback=PUSHGW_URL)
        self.metrics_port = int(general.get('metrics_port',fallback=METRICS_PORT))
        self.metrics_method = general.get('metrics_method',fallback=METRICS_METHOD).upper()
        self.service_timeout = int(general.get('service_timeout', fallback=SERVICE_TIMEOUT))
        if self.metrics_method not in [PUSH,PULL]:
            logger.error(f"{self.metrics_method} is not a valid metrics method.  Changing to PULL")
            self.metrics_method = PULL

        # Set object fields that aren't read from the config file.
        self.set_extra_values()

        # Check the private key exists.
        self.priv_file = os.path.join(self.pkey_path, self.pkey_name)
        if self.pkey_name and not os.path.isfile( self.priv_file ):
            if self.__fail_no_key:
                logger.info(f"The private key {self.pkey_name} doesn't exist")
                sys.exit(1)


    def set_extra_values(self):
        self.hostname = socket.gethostname()


    def save_config(self):
        # Write the settings back to the config file.
        self.parser['general'] = {
            'cluster_id': self.cluster_id,
            'cmsd_period': self.cmsd_period,
            'cmsd_wait': self.cmsd_wait,
            'service_timeout': self.service_timeout,
            'pkey_name': self.pkey_name,
            'pkey_path': self.pkey_path,
            'servers': ','.join(self.servers),
            'ssh_user': self.ssh_user,
            'min_ok': self.min_ok,
            'log_level': self.log_level,
            'prom_url': self.prom_url,
            'alert_url': self.alert_url,
            'pushgw_url': self.pushgw_url,
            'metrics_port': self.metrics_port,
            'metrics_method': self.metrics_method
        }
        with open(self.config_file, 'w') as configfile:
            self.parser.write(configfile)


    def log(self):
        logger.info(f"cluster_id: {self.cluster_id}")
        logger.info(f"cmsd_period: {self.cmsd_period}")
        logger.info(f"cmsd_wait: {self.cmsd_wait}")
        logger.info(f"service_timeout: {self.service_timeout}")
        logger.info(f"pkey_name: {self.pkey_name}")
        logger.info(f"pkey_path: {self.pkey_path}")
        logger.info(f"servers: {self.servers}")
        logger.info(f"ssh_user: {self.ssh_user}")
        logger.info(f"min_ok: {self.min_ok}")
        logger.info(f"log_level: {self.log_level}")
        logger.info(f"prom_url: {self.prom_url}")
        logger.info(f"alert_url: {self.alert_url}")
        logger.info(f"pushgw_url: {self.pushgw_url}")
        logger.info(f"metrics_port: {self.metrics_port}")
        logger.info(f"metrics_method: {self.metrics_method}")


    def create_keys(self):
        # Create an ECDSA key pair to use to authenticate the ssh connection.
        # Make sure the config directory exists first.
        if not os.path.isdir(self.pkey_path):
            logger.info(f"Creating {self.pkey_path}")
            os.makedirs(self.pkey_path)

        # Generate a new ECDSA private key and save to file.
        private_key = ec.generate_private_key(ec.SECP521R1())
        with open(self.priv_file, 'wb') as f:
            logger.debug(f"Writing private key: {self.priv_file}")
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        # Create a public key using the private key and save to file.
        pub_file = self.priv_file+".pub"
        public_key = private_key.public_key()
        with open(pub_file, 'wb') as f:
            logger.debug(f"Writing public key: {pub_file}")
            f.write(public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            ))

#-----------------------------------------------------------------------------------------------------

class Server:

    CONNECT_ERR = 1
    RESTART_ERR = 2

    received_signal = 0
    _status = OK


    class TerminateException(Exception):
        pass
        
    class RestartException(Exception):
        pass


    def __init__(self, server_name, config, parent):
        # The parent tracks the number of servers that are ok.  When the status of this server
        # changes the parent is notified.  
        self.parent = parent

        # Host name of the server. Used to connect using ssh.
        self.name = server_name

        # The ssh user that will be used to restart the services.
        self.ssh_user = config.ssh_user

        # The names of the CMSD AND XROOTD services to be restarted
        self.cmsd_svc = config.cmsd_svc
        self.xrootd_svc = config.xrootd_svc

        # How long to wait between stopping CMSD and stopping XROOTD
        self.cmsd_wait = config.cmsd_wait

        # How long to wait for a service to start/stop
        self.service_timeout = config.service_timeout

        self.status(OK)

        # Assume the server is in error at the start.
        # If it isn't it won't matter.  If it is it will clear any alerts
        # the server is working.
        self.err_list = [self.CONNECT_ERR,self.RESTART_ERR]

        # Private key to use with the ssh connection
        self.pkey_file = config.priv_file
        self.private_key = paramiko.ECDSAKey.from_private_key_file(self.pkey_file)


    def __str__(self):
        return self.name


    def status(self,status):
        if status:
            # If the status has changed, update the parent server list.
            if status != self._status:
                logger.debug(f"Settings status for {self.name} to {status}")
                self._status = status
                if status == OK:
                    self.parent.ajust_servers_ok( 1 )
                else:
                    self.parent.ajust_servers_ok( -1 )
        else:
            return self._status


    def set_error(self,err_type):
        # Add err_type to the list of current errors.  
        # Make sure there is only one entry in the list.
        if not err_type in self.err_list:
            self.err_list.append(err_type)


    def clear_error(self,err_type):
        # Remove err_type from the list of current errors.
        if err_type in self.err_list:
            self.err_list.remove(err_type)


    def signal_handler(self,signum, frame):
        # Used to detect the program exit.  It sets a flag so the restart routine can try and leave
        # a server in a good way before exiting. 
        logger.info(f"Signal {signum} received. Setting flag to abort the restart process..")
        self.received_signal = signum


    def restart(self):
        try:
            # Restart the cmsd service, wait for cmsd_wait seconds and then restart xrootd service.
            logger.info(f"Restarting {self.name}")
            
            # Make sure the flag to say a shutdown signal has been seen is cleared.
            self.received_signal = 0

            # Reassign the signal handlers to stop the restarting being interupted
            # and left in a odd state.
            
            # Save original signal handlers so they can be restored at the end.
            logger.debug("Reassigning signal handler for restart()")
            original_sigint_handler = signal.getsignal(signal.SIGINT)
            original_sigterm_handler = signal.getsignal(signal.SIGTERM)

            try:
                # Set custom handlers to capture signals and set received_signal.
                signal.signal(signal.SIGINT, self.signal_handler)
                signal.signal(signal.SIGTERM, self.signal_handler)

                # Set the metric for restarting
                alerter.restart_begin(self.name)
            
                alerter.set_restart_time(self.name)
                
                # Do the restart and record the histogram metrics.
                with alerter.xrootdrestart_duration.labels(node=self.name).time():
                    self.do_restart()

            finally:
                alerter.restart_end(self.name)

                # Restore original signal handlers
                logger.debug("Restoring the original signal handlers")
                signal.signal(signal.SIGINT, original_sigint_handler)
                signal.signal(signal.SIGTERM, original_sigterm_handler)
                
        except self.TerminateException as e:
            raise
               
        except Exception as e:
            logger.error(f"Exception restarting {self.name}: {str(e)}")


    def do_restart(self):
        # Flags to keep track of what has been stopped incase of SIGINT/SIGTERM
        CONNECTED = 1
        CMSDSTOPPED = 2
        XROOTDSTOPPED = 3
        state = []

        # Open an ssh connection to the server
        try:
            ssh_client = self.connect()
            state.append(CONNECTED)
            # If the server previoiusly had a connect error, clear the alert.
            if self.CONNECT_ERR in self.err_list:
                alerter.clear_connect_alert(self.name)
                self.clear_error(self.CONNECT_ERR)
        except Exception as e:
            logger.error( f"Error connecting to {self.name}" )
            logger.error( f"ERROR:{str(e)}" )
            self.set_error(self.CONNECT_ERR)
            self.status(ERR)
            alerter.cant_connect(self.name, f"XRootDRestart is unable to connect to {self.name}",str(e))
        else:
            try:
                # If the program is interupted at any point received_signal will be non-zero.
                # stop_service() and start_service() will raise a self.TerminateException if a non-zero value is set.
                self.stop_service(ssh_client, self.cmsd_svc)
                state.append(CMSDSTOPPED)

                logger.info(f"Pausing for {self.cmsd_wait} seconds before stopping xrootd")
                i = self.cmsd_wait
                while i>0:
                    time.sleep(1)
                    i -= 1
                    # Check for program termination and terminate the wait if it is set.  
                    # The stop_service() and start_service()functions check for the recieved signal 
                    # being set and raise an exception. It isn't the most efficent method but it 
                    # makes the code easier to read. The extra overhead isn't that big. 
                    if self.received_signal != 0:
                        logger.debug("CMSD_WAIT terminated because a signal has been set.")
                        break

                # Methods will raise a TerminateException exception if received_signal set.
                self.stop_service(ssh_client, self.xrootd_svc)
                state.append(XROOTDSTOPPED)

                self.start_service(ssh_client, self.xrootd_svc)
                state.remove(XROOTDSTOPPED)

                self.start_service(ssh_client, self.cmsd_svc)
                state.remove(CMSDSTOPPED)

                self.close_connection(ssh_client)
                state.remove(CONNECTED)

                # All the services have been restarted.
                self.status(OK)
                
                # Clear the alert if there was a prior restart error.
                if self.RESTART_ERR in self.err_list:
                    alerter.clear_restart_alert(self.name)
                    self.clear_error(self.RESTART_ERR)

                logger.info(f"Restarting {self.name} complete")

            except self.TerminateException as e:
                # The program has been interupted.  Try and leave the server in a sensible state
                logger.info(f"Restarting services as needed and closing the connection to {self.name}")

                try:
                    # Try and restart any services that were stopped before exiting to shutdown. 
                    if XROOTDSTOPPED in state:
                        self.start_service(ssh_client, self.xrootd_svc, False)
                    if CMSDSTOPPED in state:
                        self.start_service(ssh_client, self.cmsd_svc, False)
                    if CONNECTED in state:
                        self.close_connection(ssh_client)
                        
                    print(f"Restarting {self.name} was interrupted.")
                    
                except Exception as e2:
                    logger.error(f"Error while resolving termination of server restart: {str(e2)}")
                    logger.info(f"Please verify the state of {self.name} is ok")
                    print(f"Restarting {self.name} was interrupted.  Please verify the state of {self.name} is ok")

                raise e;

            except Exception as e:
                logger.error( f"Error restarting {self.name}" )
                logger.error( f"ERROR:{e}" )
                self.status(ERR)
                self.set_error(self.RESTART_ERR)
                alerter.restart_failure(self.name,f"Unable to restart the services on {self.name}",str(e))
                self.close_connection(ssh_client)


    def connect(self):
        # Connect to the server. Only use the private key specified in the config.
        # Stop it using the agent as that could result in intermittent working/not working.
        # Don't look in the .ssh directory for valid keys.
        logger.info(f"Connecting to {self.name}")
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(self.name, username=self.ssh_user, pkey=self.private_key, allow_agent=False, look_for_keys=False)
        logger.debug(f"Connected to {self.name}")
        return ssh_client


    def execute_command(self, ssh_client, command):
        logger.debug(f"Executing command ({self.name}): {command}")
        
        try:
            # NOTE: exec_command() doen't generate an exception when service_timeout is reached.
            #       The exception is raised when stdout.read() is executed.  
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=self.service_timeout)
            ret_stdout = stdout.read().decode().strip()
            ret_stderr = stderr.read().decode().strip()
        except socket.timeout:
            logger.error(f"Timeout while executing command on {self.name}: {command}")
            raise Server.RestartException(f"Timeout running command: {command}")
        except paramiko.SSHException as e:
            logger.error(f"SSH error while executing command on {self.name}: {e}")
            raise Server.RestartException(f"SSH error running command: {command}")
        except Exception as e:
            logger.error(f"An exception occurred while executing command on {self.name}: {e}")
            raise Server.RestartException(f"Error running command: {command}")
            
        logger.debug(f"stdout: {ret_stdout}")
        logger.debug(f"stderr: {ret_stderr}")
        
        if ret_stderr:
            raise Exception(f"Error running command: {ret_stderr}")
            
        return ret_stdout, ret_stderr


    def stop_service(self, ssh_client, service_name, raise_term_exception=True):
        if self.received_signal !=0 and raise_term_exception:
            raise Server.TerminateException("Program termination detected.  Exiting restart")
            
        try:
            start_time = time.time()
            logger.info(f"Stopping service {service_name} on {self.name}")
            stdout, stderr = self.execute_command(ssh_client, f"sudo systemctl stop {service_name}")
            
            logger.info(f"Checking the state of {service_name}")
            stdout,stderr = self.execute_command(ssh_client, f"sudo systemctl is-active {service_name}")
            if stdout.strip() == "active":
                raise Server.RestartException(f"{service_name} failed to stop")
                
            logger.info(f"{service_name} stopped successfully")
            elapsed_time = time.time() - start_time
            logger.debug(f"Stoppping {service_name} took {elapsed_time}s")
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.debug(f"Stoppping {service_name} took {elapsed_time}s")
            raise Server.RestartException(f"Error stopping {service_name}: {str(e)}")
            

    def start_service(self, ssh_client, service_name, raise_term_exception=True):
        if self.received_signal !=0 and raise_term_exception:
            raise Server.TerminateException("Program termination detected.  Exiting restart")

        try:
            start_time = time.time()
            logger.info(f"Starting service {service_name} on {self.name}")

            # Double check the service is actually stopped before starting it.
            # If it's already active there is a problem so raise an exception.
            stdout,stderr = self.execute_command(ssh_client, f"sudo systemctl is-active {service_name}")
            if stdout.strip() == "active":
                raise Server.RestartException(f"{service_name} already active before starting.")

            stdout, stderr = self.execute_command(ssh_client, f"sudo systemctl start {service_name}")
               
            logger.info(f"Checking the state of {service_name}")
            stdout,stderr = self.execute_command(ssh_client, f"sudo systemctl is-active {service_name}")
            if stdout.strip() == "inactive":
                raise Server.RestartException(f"{service_name} failed to start")
                
            logger.info(f"{service_name} started successfully")
            elapsed_time = time.time() - start_time
            logger.debug(f"Starting {service_name} took {elapsed_time}s")
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.debug(f"Starting {service_name} took {elapsed_time}s")
            raise Server.RestartException(f"Error starting {service_name}: {str(e)}")


    def close_connection(self, ssh_client):
        try:
            logger.info(f"Closing connection to {self.name}")
            ssh_client.close()
        except Exception as e:
            logger.error(f"Error closing connection to {self.name}: {str(e)}")

#-----------------------------------------------------------------------------------------------------

class ServerList:

    def  __init__(self,config):
        logger.debug("Creating server list")
        self.alert_set = True;
        self.list = []
        self.current = 0
        self.num_ok = len(config.servers)
        self.min_ok = config.min_ok
        for name in config.servers:
            logger.debug(f"Adding server {name}")
            server = Server(name, config, self)
            # Set the alert states according to what alerts were active on the last run. 
            alerter.reset_alerts( server.name )
            self.list.append( server )


    def __len__(self):
        return len(self.list)


    def __str__(self):
        ret = ""
        comma = ""
        for server in self.list:
            ret += comma + str(server)
            comma = ","
        return ret


    def next(self):
        self.current += 1
        if self.current >= len(self.list):
            self.current = 0
        return self.list[self.current]


    def restart_next_server(self):
        if self.num_ok >= self.min_ok:
            logger.debug("Doing next server")
            self.next().restart()
        else:
            # There aren't enough running servers.  Log the fact and terminate since the program can't do anyting else
            logger.info(f"There are {self.num_ok} servers ok.  There are insufficient to continue restarting servers")
            raise Exception("Insufficient servers running.")


    def ajust_servers_ok(self,amount):
        # Update the number of good servers.  If the number drops below
        # min_ok just raise an alert.  Let restart_next_server() exit
        # the process.  This should give prometheus time to collect the 
        # metrics.
        self.num_ok += amount
        logger.debug(f"Adjusting num_ok in server list by: {amount} num_ok now {self.num_ok}.  min_ok={self.min_ok}")
        if self.num_ok < self.min_ok:
            logger.info(f"Number of working servers ({self.num_ok}) dropped below the minimum ({self.min_ok})")
            self.alert_set = True
            alerter.send_insuffucient_alert(f"Insufficient servers running.  There are {self.num_ok} servers ok. No more servers will be restarted")
        elif self.alert_set:
            self.alert_set = False
            # Currently this will never happen because it needs to run the restart to clear an error.
            alerter.clear_insuffucient_alert()

#-----------------------------------------------------------------------------------------------------

class Alerter:
    # Registry used to push metric prometheus
    registry = None


    def __init__(self, config):
        self.metrics_method = config.metrics_method
        self.cluster_id = config.cluster_id
        self.hostname = config.hostname
        self.pushgw_url = config.pushgw_url
        self.alert_url = config.alert_url
        self.metrics_port = config.metrics_port
        self.alerts_on = config.alert_url != ""
        logger.info(f"Alerts are {'enabled' if self.alerts_on else 'disabled'}")

        # Setup the metrics
        
        # Setup the histogram metrics
        # Workout the buckets based on the time between stopping cmsd (cmsd_wait) and
        # the service_timeout value.
        b_size = 15
        b_start = (config.cmsd_wait // b_size) * b_size
        b_end = ((config.cmsd_wait + 2*config.service_timeout+b_size) // b_size) * b_size
        duration_buckets = [x for x in range(b_start, b_end, b_size)]

        if self.metrics_method == PULL:
            # Pull needs a webserver to serve the metrics.
            logger.debug(f"Creating webserver on port {self.metrics_port}")
            start_http_server(self.metrics_port)
            labels = ["node"]
        else:
            labels = ["node","cluster"]
        self.create_metrics(labels,duration_buckets)
        

    def create_metrics(self,labels,duration_buckets):
        self.heartbeat_metric = Gauge("xrootdrestart_heartbeat", f"xrootdrestart heartbeat generated every {HEARTBEAT_INTERVAL} seconds",labels)
        self.xrootdrestart_restart_active = Gauge("xrootdrestart_restart_active","State of the service restart on an XRootD node. 1=Restart Active, 0=Idle",labels)
        self.xrootdrestart_start_time = Gauge("xrootdrestart_start_time","Time when the xrootdrestart started restarting a server",labels)
        self.xrootdrestart_restart_alert_state = Gauge("xrootdrestart_restart_alert_state","state of the restart alert for a node. 1=Alert, 0=No Alert",labels)
        self.xrootdrestart_connect_alert_state = Gauge("xrootdrestart_connect_alert_state","Unable to connect alert state. 1=Alert, 0=No Alert",labels)
        self.xrootdrestart_insufficuent_alert_state = Gauge("xrootdrestart_insufficient_alert_state","State of the alert indicating there are insuffucient servers to allow restarting to continue. 1=Alert, 0=No Alert",labels)
        self.xrootdrestart_duration = Histogram("xrootdrestart_restart_duration_seconds","How long it took to restart a server",labels,buckets=duration_buckets)

        self.xrootdrestart_insufficuent_alert_state.labels(**self.metrics_labels(self.hostname)).set(0)
        
        
    def metrics_labels(self,node):
        # Return a list of labels to use with a metric value.
        ret = {"node": node}
        if self.metrics_method == PUSH:
            ret["cluster"] = self.cluster_id
        return ret


    def remove_active_alerts(self):
        # End all the active alerts on the alert manager.
        alerts = self.get_active_alerts(ALERT_TYPE_LIST)
        for alert in alerts:
            self.end_alert(alert)


    def get_active_alerts(self,alert_types):
        # Return a list of active alerts in the alert manager that match the alert types in alert_types.
        ret = []
        if self.alerts_on:
            url = f"{self.alert_url}/api/v2/alerts"
            try:
                logger.debug(f"Requesting alerts from {url}")
                response = requests.get(url)
                response.raise_for_status()
                alerts = response.json()
                for alert in alerts:
                    if alert.get("labels", {}).get("alertname") in alert_types:
                        ret.append(alert)
                logger.debug(f"{len(ret)} alerts read")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching active alerts: {e}")
        return ret


    def end_alert(self,alert):
        # Set the end time of the alert and update the alert manager. 
        alert_name = alert.get("labels", {}).get("alertname")
        logger.info("Ending alert: %s", alert)
        alert["endsAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.send_alert(alert)


    def restart_failure(self,server_name,err_summary,err_message):
        # Send the alert manager an ALERT_XROOTDRESTART_RESTART_ERROR and set the XROOTDRESTART_RESTART_ALERT_STATE metric
        if self.alerts_on:
            alert = self.new_alert(ALERT_XROOTDRESTART_RESTART_ERROR,server_name,err_summary,err_message)
            self.send_alert(alert)
        self.xrootdrestart_restart_alert_state.labels(**self.metrics_labels(server_name)).set(1)


    def clear_restart_alert(self,server_name):
        # Clear ALERT_XROOTDRESTART_RESTART_ERROR on the alert manager and unset the XROOTDRESTART_RESTART_ALERT_STATE metric
        if self.alerts_on:
            logger.debug(f"Clearing restart alert for {server_name}")
            alert = self.find_alert(ALERT_XROOTDRESTART_RESTART_ERROR,server_name)
            if alert:
                self.end_alert(alert)
        self.xrootdrestart_restart_alert_state.labels(**self.metrics_labels(server_name)).set(0)


    def cant_connect(self,server_name,err_summary,err_message):
        # Send the alert manager an ALERT_XROOTDRESTART_CONNECT_ERROR and set the XROOTDRESTART_CONNECT_ALERT_STATE metric
        if self.alerts_on:
            logger.debug(f"Sending ALERT_XROOTDRESTART_CONNECT_ERROR alert for {server_name}" )
            alert = self.new_alert(ALERT_XROOTDRESTART_CONNECT_ERROR,server_name,err_summary,err_message)
            self.send_alert(alert)
        self.xrootdrestart_connect_alert_state.labels(**self.metrics_labels(server_name)).set(1)


    def clear_connect_alert(self, server_name):
        # Clear ALERT_XROOTDRESTART_CONNECT_ERROR on the alert manager and unset the XROOTDRESTART_CONNECT_ALERT_STATE metric
        if self.alerts_on:
            logger.debug(f"Clearing ALERT_XROOTDRESTART_CONNECT_ERROR alert for {server_name}")
            alert = self.find_alert(ALERT_XROOTDRESTART_CONNECT_ERROR,server_name)
            if alert:
                self.end_alert(alert)
        self.xrootdrestart_connect_alert_state.labels(**self.metrics_labels(server_name)).set(0)


    def send_insuffucient_alert(self,err_message):
        # Send the alert manager an ALERT_XROOTDRESTART_INSUFFICIENT_SERVERS and set the XROOTDRESTART_INSUFFICUENT_ALERT_STATE metric
        if self.alerts_on:
            alert = self.new_alert(ALERT_XROOTDRESTART_INSUFFICIENT_SERVERS,"","Too many servers down",err_message)
            self.send_alert(alert)
        self.xrootdrestart_insufficuent_alert_state.labels(**self.metrics_labels(self.hostname)).set(1)


    def clear_insuffucient_alert(self):
        # Clear ALERT_XROOTDRESTART_INSUFFICIENT_SERVERS on the alert manager and unset the XROOTDRESTART_INSUFFICUENT_ALERT_STATE metric
        if self.alerts_on:
            logger.debug(f"Clearing ALERT_XROOTDRESTART_INSUFFICIENT_SERVERS alert")
            alert = self.find_alert(ALERT_XROOTDRESTART_INSUFFICIENT_SERVERS,"")
            if alert:
                self.end_alert(alert)
        self.xrootdrestart_insufficuent_alert_state.labels(**self.metrics_labels(self.hostname)).set(0)
    

    def new_alert(self,alert_type,server_name,err_summary,err_message):
        # Create an alert object
        ret = {
                "labels": {
                    "alertname": alert_type,
                    "severity": "critical",
                },
                "annotations": {
                    "summary": err_summary,
                    "description": err_message,
                },
                "startsAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        if server_name != "":
            ret["labels"]["node"] = server_name

        return ret


    def send_alert(self,alert):
        # Send the alert to the alert manager
        if self.alerts_on:
            logger.debug(f"Sending alert: {alert}")
            try:
                mgr_url = f"{self.alert_url}/api/v2/alerts"
                logger.debug(f"Sending alert to {mgr_url}")
                response = requests.post( 
                    url=mgr_url, 
                    data=f"[{json.dumps(alert)}]",
                    headers={"Content-type": "application/json"}
                )
                if response.status_code == 200:
                    logger.debug("Alert sent successfully")
                else:
                    raise Exception(f"Failed to send alert: {response.status_code} {response.text}")
            except Exception as e:
                logger.error(f"Error sending alert: {alert}, Exception: {e}")


    def find_alert(self, alert_type, server_name):
        # Find the alert_type alert on the alert manaager.
        ret = None
        alerts = self.get_active_alerts(alert_type)
        for alert in alerts:
            if server_name != "" and alert.get("labels", {}).get("node") == server_name:
                ret = alert
                break
            elif server_name == "":
                ret = alert
                break
        return ret


    def reset_alerts(self, server_name):
        # Set/unset the alert mentrics for a server dependant on the current active alerts on the alert manager. 
        # NOTE: Should the current alerts be stored localy for when the alert manager isn't used. 
        if self.find_alert(ALERT_XROOTDRESTART_CONNECT_ERROR,server_name):
            self.xrootdrestart_restart_alert_state.labels(**self.metrics_labels(server_name)).set(1)
        else:
            self.xrootdrestart_restart_alert_state.labels(**self.metrics_labels(server_name)).set(0)

        if self.find_alert(ALERT_XROOTDRESTART_RESTART_ERROR,server_name):
            self.xrootdrestart_connect_alert_state.labels(**self.metrics_labels(server_name)).set(1)
        else:
            self.xrootdrestart_connect_alert_state.labels(**self.metrics_labels(server_name)).set(0)


    def set_restart_time(self,server):
        # Set the service last restart time metric for server.
        alerter.xrootdrestart_start_time.labels(**self.metrics_labels(server)).set(time.time())


    def set_heartbeat(self):
        # Set the heartbeat metric to the current time and PUSH to the gateway if metrics are being pushed.
        logger.debug("heartbeat")
        self.heartbeat_metric.labels(**self.metrics_labels(self.hostname)).set(time.time())
        # Push the metric if needed.
        if self.metrics_method == PUSH:
            logger.debug(f"Pushing metrics to {self.pushgw_url}")
            push_to_gateway(self.pushgw_url, registry=self.heartbeat_metric.registry)
            
    def restart_begin(self,server_name):
        self.xrootdrestart_restart_active.labels(**self.metrics_labels(server_name)).set(1)
        
    def restart_end(self,server_name):
        self.xrootdrestart_restart_active.labels(**self.metrics_labels(server_name)).set(0)

#-----------------------------------------------------------------------------------------------------

class UniqueFilter(logging.Filter):
    # Filter duplicated log entries.  Multiple heartbeat log entries will be reduced to two log entries.
    # The first log entry and then a summary line showing how many times the log entry was repeated.
    # This stops the log file filling up with "heartbeat" entries.
    def __init__(self):
        self.last_message = None
        self.last_level = None
        self.count = 0


    def filter(self, record):
        # Skip processing if this is a summary record being output.  We don't want to dive into infinite recursion.
        if getattr(record, "is_summary", False):
            return True

        # Get the current message and see if it's a repeat of the last.
        current_message = record.getMessage()
        if current_message == self.last_message:
            # We're doing a repeated message.  Inc the repeat count and stop the current message being output.
            self.count += 1
            return False
        else:
            # This is a non-repeated message.  Any repeats before this one?
            if self.count > 0:
                # The current message is different to the last. The previous log message
                # was repeated so we need to output two log messages this
                # time: The summary of the message repeat and the new log message.

                # If there were only two messages the same, just display the same message twice.
                if self.count == 1:
                    log_msg = self.last_message
                else:
                    log_msg = f"Repeated {self.count} more times: {self.last_message}"

                # Create a summary record for repeated messages
                summary_record = logging.LogRecord(
                    name=record.name,
                    level=self.last_level,
                    pathname=record.pathname,
                    lineno=record.lineno,
                    msg=log_msg,
                    args=(),
                    exc_info=None,
                )
                # Mark it as a summary to avoid recursion
                summary_record.is_summary = True
                logging.getLogger(record.name).handle(summary_record)

            # Reset things for the new messages
            self.last_message = current_message
            self.last_level = record.levelno
            self.count = 0

            return True

#-----------------------------------------------------------------------------------------------------
class Heartbeat:
    
    def __init__(self):
        self.running = True
        self.heartbeat_thread = threading.Thread(target=self.generate_heartbeat)
        self.heartbeat_thread.daemon = True
        
    def start(self):
        self.heartbeat_thread.start()
        
    def stop(self):
        self.running = False
        
    def generate_heartbeat(self):
        while self.running:
            try:
                alerter.set_heartbeat()
                time.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.error(f"Error generating the heartbeat: {str(e)}")
                self.running = False;
                logger.error("Heartbeat disabled")
            
#-----------------------------------------------------------------------------------------------------
def signal_handler(sig, frame):
    # Handle program shutdown.  If a server is being restarted when a shutdown is instigated, the server object will 
    # make sure the services are running on the server before exiting.
    logger.info("Received signal to stop")
    logger.info("Stopping heartbeat")
    heartbeat.stop()
    if sig == signal.SIGTERM:
        logger.info("Program terminated.  Exit gracefully")
    else:
        logger.info("Program terminated by user.  Exit gracefully")
        print("Program terminated by user.")
    sys.exit(0)


#-----------------------------------------------------------------------------------------------------
def main():
    global logger, alerter, heartbeat
    
    # Configure the logging output.
    # Set the format for the messages and filter repeating messages.
    logger = logging.getLogger('xrootdrestart')
    handler = logging.FileHandler(LOG_FILE)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    unique_filter = UniqueFilter()
    handler.addFilter(unique_filter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    # Logger active and configured so log the program start. 
    logger.info("===========================================================================")
    logger.info("=============================  PROGRAM START ==============================")
    logger.info("===========================================================================")

    # Read in the config file.
    config = Config()
    logger.info(f"Reading config file: {config.config_file}")
    config.load_config()
    # Adjust the logging level to the value in the config.
    logger.info(f"Setting log level to {config.log_level}")
    logger.setLevel(config.log_level)
    
    # Output current settings to the log
    logger.info(f"Version: {VERSION}")
    config.log()

    # Setup the alerter object
    logger.info("Starting Alerter")
    alerter = Alerter(config)

    # Start the heartbeat thread
    logger.info("Starting heartbeat thread")
    heartbeat = Heartbeat()
    heartbeat.start()

    # Setup the server list
    server_list = ServerList( config )
    if len(server_list)>0:
        logger.info(f"Processing server list: {server_list}")

        # Work out the time between restarting all servers so that each server is restarted every cmsd_period.
        restart_interval = config.cmsd_period / len(server_list)
        logger.info(f"A server will be restarted every {restart_interval} seconds")

        # Put hook in to handle SIGTERM and SIGINT events.
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Start the scheduler
        schedule.every(restart_interval).seconds.do( server_list.restart_next_server )
        logger.debug(f"restart_next_server() scheduled to run every {restart_interval} seconds")

        try:
            # Run the first restart because schedule will wait for the restart_interval before doing the first run.
            server_list.restart_next_server()

            # Sit in a loop waiting for the next schedule.
            while True:
                schedule.run_pending()
                time.sleep(5)
        except Server.TerminateException as e:
            logger.info("Program terminating")
            sys.exit(3)
        except Exception as e:
            logger.error(f"Program terminating because of an exception: {str(e)}")
            # Print the exception message
            print(f"An error occurred: {e}")
            
            # Get the traceback details
            tb = traceback.format_exc()
            print("Traceback details:")
            print(tb)            
            logger.error(tb)
            logger.info("Program terminating")
            sys.exit(2)
    else:
        logger.info("No servers specified.  Program exit")


if __name__ == "__main__":
    main()
