# XRootDRestart

''NOTE'' This is currently under development.

## Introduction

XRootDRestart is a python script that periodically restarts cmsd and XRootD services on a list of servers. It does this using ssh to connect to each server to run the necessary systemctl commands to stop and start the services.

After connecting to a server, it stops cmsd, waits for a predefined length of time before restarting XRootD.  Finally cmsd is restarted and the ssh connection is closed.  If there are any problems restarting the services alerts are generated and sent using AlertManager.  This can be disabled if not required. 

There are various metrics recorded which can then be processed by Prometheus.  The metrics are set to be 'pulled' by default but it can be configured to push the metrics to a push gateway. 

It has been noted that occationally the XRootD processes fail to terminate.  When this happens it is necessary to reboot the server so it is recommended that XRoodDRestart be run from a machine that does not run any XRootD services. 

There is a setup script (setup.py) that will connect to the XRootD servers and ensure they are configured correctly to allow XRootDRestart to connect and control the XRootD services.  It then configures XRootDRestart to run as a system service or creates a docker/podman image


## Requirements

The script was written using Python 3.12.7 so ensure you have a suitable version of python installed.  

The requirements.txt file lists the required python packages. 

If you want to run XRoodDRestart in a container or run the Monitoring stack for testing, you will need either docker or podman installed. 

## Downloading

Clone the github respository:

```
# cd /opt
# git clone https://github.com/lancs-gridpp/xrootdrestart.git
```

## Install as a Service

### Overview
XRootDRestart can be run as a systemd service. 

The **setup** script will check and configure the system as necessary. Run the setup script from the project root directory as a user that has ssh access to the XRootD hosts.  The setup script will need to ssh to the XRootD machines to create a user and setup them up to allow ssh key authentication.

The first time you run the setupscript it will create the XRootDRestart.conf with detault settings and terminate.  Edit the file to suit your system and then run the script again.

When you run the script again it will:

* Ensure the config file exists and loads the settings.
* Ensure the private/public keys to be used with SSH exist.
* Ensures the log file exists and is writable.
* For each server:
	* Check that an ssh session can be started as the user running the setup.py script.
	* Create the ssh user if they don't exist.
	* Ensure the sudo rules exist to allow the ssh user to run systemctl.
	* Copy the key to the server for ssh authentication
	* Ensure an SSH can be enstablished as the ssh user with the key
* If URLs are defined for the Alert Manager and PUSH Gageway, it will try opening an http connection to the URL
* Configure either the systemd xrootdrestart service or docker image.

If any of these steps fail, the setup script will abort with a message indicating the problem.  Fix the problem and run the script again. You can run the script as many times as necessary.

If you change the list of servers at any point just run the setup.py script to configure the new servers. 


### Details

```
# python3 setup.py systemd
INFO - Running setup in systemd mode
INFO - Config file /etc/xrootdrestart/xrootdrestart.conf created at. Please edit it and run the script again.
```

The script has created a default config file.

```
[general]
cluster_id = production
cmsd_period = 259200
cmsd_wait = 300
service_timeout = 120
pkey_name = xrootdrestartkey
pkey_path = /etc/xrootdrestart
servers =
ssh_user = xrootdrestart
min_ok = 1
log_level = INFO
prom_url = http://localhost:9090
alert_url = http://localhost:9093
pushgw_url = http://localhost:9091
metrics_port = 8000
metrics_method = PULL
```

See [Configuration File](#configuration-file) for details of the available options.


Edit the config file and set the options as required.  The basic ones you will need to set are: **servers**, **ssh_user**, **pkey_name**, **pkey_path**, **cmsd_svc** and **xrootd_svc**.

**alert_url**, **cluster_id**, **metrics_port**, **metrics_method**, **prom_url** and **pushgw_url** are all used transfer metrics and generate alerts.  If you are not using these, blank the "*_url" options.

Once you have set the config file as you want it, re-run the setup script.

```
# ./setup
Running setup script...
- INFO - [SUCCESS] The config file already exists: /etc/xrootdrestart/xrootdrestart.conf
- INFO -  Private key not found at /etc/xrootdrestart/xrootdrestartkey. Generating new ECDSA key pair...
- INFO - [SUCCESS] Created ECDSA key pair at /etc/xrootdrestart/xrootdrestartkey and /etc/xrootdrestart/xrootdrestartkey.pub.
- INFO - [SUCCESS] Log file at /var/log/xrootdrestart.log exists and is writable.
- INFO -  Verifying the setup of rock01
- INFO -  Checking user xrootdrestart exists.
- INFO -  Creating user xrootdrestart...
- INFO - [SUCCESS] User xrootdrestart created
- INFO - Checking sudo rules...
- INFO - [SUCCESS] User added to sudoers
- INFO -  Checking ssh access for xrootdrestart
- INFO - Authentication failed.
- INFO -  Unable to connect as xrootdrestart
- INFO -  Copying authorized keys to xrootdrestart
- INFO -  Trying to connect as xrootdrestart again
- INFO -  Connected to rock01 ok
- INFO -  Copying ssh key to rock01
/usr/bin/ssh-copy-id: INFO: Source of key(s) to be installed: "/etc/xrootdrestart/xrootdrestartkey.pub"
/usr/bin/ssh-copy-id: INFO: attempting to log in with the new key(s), to filter out any that are already installed
/usr/bin/ssh-copy-id: INFO: 1 key(s) remain to be installed -- if you are prompted now it is to install the new keys

Number of key(s) added: 1

Now try logging into the machine, with:   "ssh 'xrootdrestart@rock01'"
and check to make sure that only the key(s) you wanted were added.

- INFO -  Checking connection to rock01 using the private key
- INFO - [SUCCESS] Connected to rock01 as xrootdrestart using the private key
- INFO -  Checking network connection for Alert Manager - http://localhost:9093...
- INFO - [SUCCESS] Successfully connected to http://localhost:9093.
- INFO -  Checking network connection for PUSH Gateway - http://localhost:9091...
- INFO - [SUCCESS] Successfully connected to http://localhost:9091.
- INFO - All checks completed successfully.
Creating systemd service file at /etc/systemd/system/xrootdrestart.service...
Reloading systemd daemon...
Enabling xrootdrestart service...
Created symlink /etc/systemd/system/multi-user.target.wants/xrootdrestart.service → /etc/systemd/system/xrootdrestart.service.
Starting xrootdrestart service...
Checking service status...
● xrootdrestart.service - Restart XRootD Service Script
     Loaded: loaded (/etc/systemd/system/xrootdrestart.service; enabled; preset: enabled)
     Active: active (running) since Wed 2025-06-04 15:52:51 BST; 22ms ago
   Main PID: 23263 (python)
      Tasks: 1 (limit: 4597)
     Memory: 3.0M (peak: 3.0M)
        CPU: 11ms
     CGroup: /system.slice/xrootdrestart.service
             └─23263 /home/gerard/Projects/devshared/xrootdrestart/.venv/bin/python /home/gerard/Projects/devshared/xrootdrestart/xrootdrestart.py

Jun 04 15:52:51 gerarddev2 systemd[1]: Started xrootdrestart.service - Restart XRootD Service Script.
Setup complete!
```

## Run XRootDRestart in a Docker Container

**Dockerfile** will create an Alma 9 image 

## Monitoring

### Metrics

XRootDRestart by default opens port 8000 (metrics_port) which can be used by Prometheus to pull (metrics_method) the XRootDRestart metrics.  If you want to push the metrics to Prometheus set the configuration option **metrics_method"** to PUSH and set the option **pushgw_url** to the address (including a port number) when the metrics should be pushed to.  The metrics are pushed every 5 seconds.

The following metrics are created:

| Metric | Type | Definition |
| --- |:---:| --- |
| xrootdrestart_heartbeat | Gauge | xrootdrestart Heartbeat generated every 5 seconds |
| xrootdrestart_restart_active | Gauge | State of the service restart on an XRootD node. 1=Restart Active, 0=Idle.  The node label specifies the server. |
| xrootdrestart_start_time | Gauge | Time when the xrootdrestart began restarting a server.  The node label specifies the server. |
| xrootdrestart_restart_alert_state | Gauge | state of the restart alert for a node. 1=Alert, 0=No Alert.  The node label specifies the server. |
| xrootdrestart_connect_alert_state | Gauge | Unable to connect alert state. 1=Alert, 0=No Alert.  The node label specifies the server. |
| xrootdrestart_insufficient_alert_state | Gauge | State of the alert indicating there are insuffucient servers to allow restarting to continue. 1=Alert, 0=No Alert.  The node label specifies the server. |
| xrootdrestart_restart_duration_seconds | Histogram | How long it took to restart a server. |

### Alerts 

XRootDRestart by default will generate the following allerts

| Alert | Definition |
| --- | --- |
| ALERT_XROOTDRESTART_CONNECT_ERROR | Unable to connect to XRootD server |
| ALERT_XROOTDRESTART_RESTART_ERROR | Error restarting the XRootD/cmsd services |
| ALERT_XROOTDRESTART_INSUFFICIENT_SERVERS | The number of active XRootD services has dropped to the minumum allowed. No more servers will be restarted. |

Alerts will be sent to the Alertmanager address set in the config option **alert_url**

If you do not want alerts to be generated set **alert_url** to be blank.

## Configuration File

The location of the configuration file (xrootdrestart.conf) is determined by the user who runs xrootdrestart.py.

For *root*: /etc/xrootdrestart/xrootdrestart.conf

For *others*: ~/.config/xrootdrestart/xrootdrestart.conf

This file must be writeable by the user running xrootdrestart.py.

### Options

| Option | Default | Definition |
| --- | --- | --- |
| alrt_url       | http://localhost:9093 | Alert-manager URL + port.|
| cluseter_id    | production | Value to use in the metrics cluster label.|
| cmsd_period    | 259200 | Time in seconds between restarting the services on a server.|
| cmsd_svc       | 'cmsd@cluster' | CMSD service name.|
| cmsd_wait      | 300 | Time in seconds to wait after stopping cmsd before stopping XRootD.|
| log_level      | INFO | Logging output level: DEBUG, INFO, WARNING, ERROR, CRITICAL.|
| metrics_port   | 8000 | Listening port to provide prometheus metrics.|
| metrics_method | PULL | Method of transfering metrics: PUSH, PULL.|
| min_ok         | 1 | If the number of servers that are ok drops below this number the program will stop restarting services.|
| pkey_name      | xrootdrestartkey | File name of the private key file.|  (not including path).| Set blank to not use a pkey.|
| pkey_path      | \<same directory as the config file\> | Directory containing pkey_name file.|
| pushgw_url     | http://localhost:9091 | URL + port of the gateway for pushing prometheus metrics.|
| servers        | \<blank\> | A comman separated list of server host names.|
| service_timeout| 120 | Seconds to wait for a service to stop or start.|
| ssh_user       | xrootdrestart | User used by the ssh connection.|
| xrootd_svc     | xrootd@cluster | XRootD service name.|


## Running Test XRootD and CMSD Services

*testing/xrootd-service/mk_xroot_service.sh* will create a dummy XRootD and cmsd services which can be used to test XRootDRestart without having to restart live servers. The services have a built in random delay of between 10 and 30 seconds when shutting down the service.

## Test Monitoring Stack

A monitoring stack is included that will run in docker containers.  

The docker compose file (/Monitoring/docker-compose.yml) creates the following containers and volumes:

| Container | Port |
| --- |:---:|
| node-exporter | 9100 | 
| prometheus | 9090 |
| alertmanager | 9093 | 
| pushgateway | 9091 |
| grafana | 3000 |

| Volume |
| --- |
| prometheus_data
| grafana_data |
| alertmanager_data |
| push_gateway |
| node_exporter |

| Network |
| --- |
| monitoring |

### Node Exporter

The paths /, /sys and /proc are exposed to the container (read-only).

The container directory /var/lib/node_exporter/textfile_collector is used to hold the collector text file and is mapped to the node-exporter volume. 

### Prometheus

The Prometheus db directory is mapped to the prometheus_data volume.  

The files prometheus.yml and alert.rules in /Monitor are mapped to the container. Prometheus is configure to scrape metrics from localhost:8000 (XRootDRestart) every 15 seconds.  You may need to modify it to scrape from the ip address of the host running the containers instead of localhost.  

### Alert Manager

/Monitor/alertmanger.yml configures the alertmanager to send email alerts.  This file needs updating to use your mail server.  The alertmanager_data volume is used to hold the alertmanager data.

### Push Gateway

The push gateway isn't used unless you set XRootDRestart to push metrics.  The pushgateway volume is used to hold the push gateway data. 

### Grafana

The admin user name and password is admin/grafana.  Modify the docker-compose file if you want to use different credentials. The grafana_data volume is used to hold the grafana data. 

