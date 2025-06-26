# XRootDRestart

## Introduction

XRootDRestart is a python script that periodically restarts cmsd and XRootD services on a list of servers. It does this using ssh to connect to each server in turn to run the necessary systemctl commands to stop and start the services.

After connecting to a server, it stops cmsd, waits for a predefined length of time before restarting XRootD.  Finally cmsd is restarted and the ssh connection is closed.  If there are any problems restarting the services alerts are generated and sent using AlertManager.  Alerts can be disabled if not required.

There are various metrics recorded which can then be processed by Prometheus.  The metrics are set to be 'pulled' by default but it can be configured to push the metrics to a push gateway.  A monintoring stack is also included for testing which is run in docker containers. 

It has been noted that occationally the XRootD process fail to terminate.  When this happens it is necessary to reboot the server. For this reason it is recommended that XRoodDRestart be run from a machine that does not run any XRootD services.

A setup script configures XRootDRestart to run:  as a systemd service; in a docker/podman container; from the command line.  It also ensures the XRootD servers are configured correctly to allow XRootDRestart to connect and control the XRootD services.


## Requirements

The script was written using Python 3.12.7 so ensure you have a suitable version of **python** installed.  

You need **git** to clone the github repository.

You need the following package: **python3-devel**

If you want to run XRoodDRestart in a container or run the Monitoring stack for testing, you need either **docker** or **podman** installed. 

The user that runs the setup script must have ssh access to all the xrootdservers.

The user running XRootDRestart must have write access to /var/log/xrootdrestart.log

## Downloading

Clone the github respository:

```
# cd /opt
# git clone https://github.com/lancs-gridpp/xrootdrestart.git
# cd xrootdrestart
```

## Running From the Command Line

Run setup

```
# ./setup
Python virtual environment not found. Creating a new one...
Upgrading pip...
Requirement already satisfied: pip in ./.venv/lib/python3.12/site-packages (24.0)
Collecting pip
  Using cached pip-25.1.1-py3-none-any.whl.metadata (3.6 kB)
Using cached pip-25.1.1-py3-none-any.whl (1.8 MB)
Installing collected packages: pip
  Attempting uninstall: pip
    Found existing installation: pip 24.0
    Uninstalling pip-24.0:
      Successfully uninstalled pip-24.0
Successfully installed pip-25.1.1
Installing required packages from requirements.txt...
Collecting paramiko (from -r requirements.txt (line 1))
      :                       :
      :                       :
Required packages installed successfully.
Activate the virtual environment using 'source .venv/bin/activate' before running 'python3 xrootdrestart.py'

```

Activate the virtual environment and run XRootDRestart

```
# source .venv/bin/activate
# python3 xrootdrestart.py
```



## Installing as Either a Service or in a Docker Image

### Overview
XRootDRestart can be run as a systemd service or using a podman/docker container.  The user used to run the setup script dermines if a system or user service is created.  If building a container image, the user that runs the setup script is used by the contianer image. 

The **setup** script checks and configure the system as necessary. The user running the setup script must have ssh access to the XRootD hosts as the setup script needs to the XRootD machines using ssh in order to create and configure a user to control the XRootD and CMSD services.

The first time you run the setupscript it:
* creates a python virtual environment and installed the required python packages.
* creates the XRootDRestart.conf with detault settings and terminate.  

Edit the file to suit your system and then run the script again.

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
* If URLs are defined for the Alert Manager and PUSH Gageway, it tries opening an http connection to the defined URLs
* Configure either the systemd xrootdrestart service or create a docker image.

If any of these steps fail, the setup script will abort with a message indicating the problem.  Fix the problem and run the script again. You can run the script as many times as necessary.

If you change the list of servers at any point just run the setup script to configure the new servers.

### Installing as a Service

Run setup script in the xrootdrestart directory specifying systemd to install XRootDRestart as a service. If you want to install a system service run the setup script as root.  If you want the xrootdrestart service to be run as a specific user, login as that user to run the setup script. 

Ensure that the user running the setup scripts can write to /var/log/xrootdrestart.log.  

```
# ./setup service
Python virtual environment not found. Creating a new one...
Upgrading pip...
Collecting pip
  Downloading https://files.pythonhosted.org/packages/a4/6d/6463d49a933f547439d6b5b98b46af8742cc03ae83543e4d7688c2420f8b/pip-21.3.1-py3-none-any.whl (1.7MB)
    100% |████████████████████████████████| 1.7MB 1.3MB/s 
Installing collected packages: pip
  Found existing installation: pip 9.0.3
    Uninstalling pip-9.0.3:
      Successfully uninstalled pip-9.0.3
Successfully installed pip-21.3.1
You are using pip version 21.3.1, however version 25.1.1 is available.
You should consider upgrading via the 'pip install --upgrade pip' command.
Installing required packages from requirements.txt...
Collecting paramiko
  Downloading paramiko-3.5.1-py3-none-any.whl (227 kB)
      :                       :
      :                       :
INFO - Running setup in systemd mode
INFO - Config file /etc/xrootdrestart/xrootdrestart.conf created at. Please edit it and run the script again.

```

The script has created a default config file. See [Configuration File](#configuration-file) for details of the available options.

Edit the config file and set the options as required.  The basic ones you need to set are: **servers**, **ssh_user**, **pkey_name**, **pkey_path**, **cmsd_svc** and **xrootd_svc**.

**alert_url**, **cluster_id**, **metrics_port**, **metrics_method**, **prom_url** and **pushgw_url** are all used transfer metrics and generate alerts.  If you are not using these, blank the "*_url" options.

Once you have set the config file as you want it, re-run the setup script.

```
# ./setup service
Running service setup ...
/opt/xrootdrestart/.venv/lib64/python3.6/site-packages/paramiko/transport.py:32: CryptographyDeprecationWarning: Python 3.6 is no longer supported by the Python core team. Therefore, support for it is deprecated in cryptography. The next release of cryptography will remove support for Python 3.6.
  from cryptography.hazmat.backends import default_backend
INFO - Running setup in service mode
INFO - [SUCCESS] The config file already exists: /etc/xrootdrestart/xrootdrestart.conf
INFO -  Private key not found at /etc/xrootdrestart/xrootdrestartkey. Generating new ECDSA key pair...
INFO - [SUCCESS] Created ECDSA key pair at /etc/xrootdrestart/xrootdrestartkey and /etc/xrootdrestart/xrootdrestartkey.pub.
INFO -  Log file not found at /var/log/xrootdrestart.log. Creating it...
INFO - [SUCCESS] Log file at /var/log/xrootdrestart.log exists and is writable.
INFO -  Verifying the setup of rock01
INFO -  Checking user xrootdrestart exists.
INFO -  Creating user xrootdrestart...
INFO - [SUCCESS] User xrootdrestart created
INFO - Checking sudo rules...
INFO - [SUCCESS] User added to sudoers
INFO -  Checking ssh access for xrootdrestart
INFO - Authentication failed.
INFO -  Unable to connect as xrootdrestart
INFO -  Copying authorized keys to xrootdrestart
INFO -  Trying to connect as xrootdrestart again
INFO -  Connected to rock01 ok
INFO -  Copying ssh key to rock01
/usr/bin/ssh-copy-id: INFO: Source of key(s) to be installed: "/etc/xrootdrestart/xrootdrestartkey.pub"
/usr/bin/ssh-copy-id: INFO: attempting to log in with the new key(s), to filter out any that are already installed
/usr/bin/ssh-copy-id: INFO: 1 key(s) remain to be installed -- if you are prompted now it is to install the new keys

Number of key(s) added: 1

Now try logging into the machine, with:   "ssh 'xrootdrestart@rock01'"
and check to make sure that only the key(s) you wanted were added.

INFO -  Checking connection to rock01 using the private key
INFO - [SUCCESS] Connected to rock01 as xrootdrestart using the private key
INFO -  Checking network connection for Alert Manager - http://192.168.122.203:9093...
INFO - [SUCCESS] Successfully connected to http://192.168.122.203:9093.
INFO -  Checking network connection for PUSH Gateway - http://192.168.122.203:9091...
INFO - [SUCCESS] Successfully connected to http://192.168.122.203:9091.
INFO - Creating systemd service file at /etc/systemd/system/xrootdrestart.service...
INFO - Reloading systemd daemon...
INFO - Enabling xrootdrestart service...
Created symlink /etc/systemd/system/multi-user.target.wants/xrootdrestart.service → /etc/systemd/system/xrootdrestart.service.
INFO - Starting xrootdrestart service...
INFO - Checking service status...
● xrootdrestart.service - Restart XRootD Service Script
   Loaded: loaded (/etc/systemd/system/xrootdrestart.service; enabled; vendor preset: disabled)
   Active: active (running) since Tue 2025-06-24 11:17:46 BST; 31ms ago
 Main PID: 90891 (python)
    Tasks: 1 (limit: 22598)
   Memory: 6.5M
   CGroup: /system.slice/xrootdrestart.service
           └─90891 /opt/xrootdrestart/.venv/bin/python /opt/xrootdrestart/xrootdrestart.py

Jun 24 11:17:46 localhost.localdomain systemd[1]: Started Restart XRootD Service Script.
INFO - [SUCESS] xrootdrestart service setup complete!
INFO - Systemd setup completed successfully.
INFO - All checks completed successfully.

```

### Run XRootDRestart in a Docker Container

Run setup in the xrootdrestart directory specifying the parameter **container**.  The user used to run the setup script is used by the container image to run xrootdrestart.

```
# ./setup container
Python virtual environment not found. Creating a new one...
Upgrading pip...
Collecting pip
  Downloading https://files.pythonhosted.org/packages/a4/6d/6463d49a933f547439d6b5b98b46af8742cc03ae83543e4d7688c2420f8b/pip-21.3.1-py3-none-any.whl (1.7MB)
    100% |████████████████████████████████| 1.7MB 1.3MB/s 
Installing collected packages: pip
  Found existing installation: pip 9.0.3
    Uninstalling pip-9.0.3:
      Successfully uninstalled pip-9.0.3
Successfully installed pip-21.3.1
You are using pip version 21.3.1, however version 25.1.1 is available.
You should consider upgrading via the 'pip install --upgrade pip' command.
Installing required packages from requirements.txt...
      :                       :
      :                       :
Required packages installed successfully.
Running container setup ...
/opt/xrootdrestart/.venv/lib64/python3.6/site-packages/paramiko/transport.py:32: CryptographyDeprecationWarning: Python 3.6 is no longer supported by the Python core team. Therefore, support for it is deprecated in cryptography. The next release of cryptography will remove support for Python 3.6.
  from cryptography.hazmat.backends import default_backend
INFO - Running setup in container mode
INFO - Config file /etc/xrootdrestart/xrootdrestart.conf created at. Please edit it and run the script again.
[root@localhost xrootdrestart]# vi /etc/xrootdrestart/xrootdrestart.conf 

```

The script has created a default config file. See [Configuration File](#configuration-file) for details of the available options.

Edit the config file and set the options as required.  The basic ones you need to set are: **servers**, **ssh_user**, **pkey_name**, **pkey_path**, **cmsd_svc** and **xrootd_svc**.

**alert_url**, **cluster_id**, **metrics_port**, **metrics_method**, **prom_url** and **pushgw_url** are all used transfer metrics and generate alerts.  If you are not using these, blank the "*_url" options.

Once you have set the config file as you want it, re-run the setup script.

```
]# ./setup container
Running container setup ...
/opt/xrootdrestart/.venv/lib64/python3.6/site-packages/paramiko/transport.py:32: CryptographyDeprecationWarning: Python 3.6 is no longer supported by the Python core team. Therefore, support for it is deprecated in cryptography. The next release of cryptography will remove support for Python 3.6.
  from cryptography.hazmat.backends import default_backend
INFO - Running setup in container mode
INFO - Running as user: root (UID: 0, GID: 0)
INFO - [SUCCESS] The config file already exists: /etc/xrootdrestart/xrootdrestart.conf
INFO -  Private key not found at /etc/xrootdrestart/xrootdrestartkey. Generating new ECDSA key pair...
INFO - [SUCCESS] Created ECDSA key pair at /etc/xrootdrestart/xrootdrestartkey and /etc/xrootdrestart/xrootdrestartkey.pub.
INFO -  Log file not found at /var/log/xrootdrestart.log. Creating it...
INFO - [SUCCESS] Log file at /var/log/xrootdrestart.log exists and is writable.
INFO -  Verifying the setup of rock01
INFO -  Checking user xrootdrestart exists.
INFO -  Creating user xrootdrestart...
INFO - [SUCCESS] User xrootdrestart created
INFO - Checking sudo rules...
INFO - [SUCCESS] User added to sudoers
INFO -  Checking ssh access for xrootdrestart
INFO - Authentication failed.
INFO -  Unable to connect as xrootdrestart
INFO -  Copying authorized keys to xrootdrestart
INFO -  Trying to connect as xrootdrestart again
INFO -  Connected to rock01 ok
INFO -  Copying ssh key to rock01
/usr/bin/ssh-copy-id: INFO: Source of key(s) to be installed: "/etc/xrootdrestart/xrootdrestartkey.pub"
/usr/bin/ssh-copy-id: INFO: attempting to log in with the new key(s), to filter out any that are already installed
/usr/bin/ssh-copy-id: INFO: 1 key(s) remain to be installed -- if you are prompted now it is to install the new keys

Number of key(s) added: 1

Now try logging into the machine, with:   "ssh 'xrootdrestart@rock01'"
and check to make sure that only the key(s) you wanted were added.

INFO -  Checking connection to rock01 using the private key
INFO - [SUCCESS] Connected to rock01 as xrootdrestart using the private key
INFO -  Checking network connection for Alert Manager - http://192.168.122.203:9093...
INFO - [SUCCESS] Successfully connected to http://192.168.122.203:9093.
INFO -  Checking network connection for PUSH Gateway - http://192.168.122.203:9091...
INFO - [SUCCESS] Successfully connected to http://192.168.122.203:9091.
INFO - Creating Dockerfile
Dockerfile created successfully at: Dockerfile
User: root (UID: 0, GID: 0)
INFO - Dockerfile created successfully.
INFO - Building podman image 'xrootdrestart' using Dockerfile...
STEP 1/9: FROM almalinux:9
Resolved "almalinux" as an alias (/etc/containers/registries.conf.d/000-shortnames.conf)
Trying to pull docker.io/library/almalinux:9...
Getting image source signatures
Copying blob 40f8af2da988 done   | 
Copying config 623706a2d9 done   | 
Writing manifest to image destination
STEP 2/9: RUN dnf -y update &&     dnf -y install python3 python3-pip openssh &&     dnf clean all
AlmaLinux 9 - AppStream                         1.4 MB/s |  11 MB     00:07    
      :                       :
      :                       :
STEP 6/9: RUN chown root:root /root/xrootdrestart.py
--> 0ff99f4a9aa7
STEP 7/9: WORKDIR /root
--> 828c059c6adc
STEP 8/9: ENTRYPOINT ["python3", "xrootdrestart.py"]
--> efefa9357c21
STEP 9/9: EXPOSE 8000
COMMIT xrootdrestart
--> 773e9f8feb8b
Successfully tagged localhost/xrootdrestart:latest
773e9f8feb8becb30a99776de31634f3d9980cb9e7b0a05af0b178318b2c60c7
INFO - [SUCCESS] Container image 'xrootdrestart' created successfully.
INFO - Container run command:
INFO - ==================================================
INFO - podman run -d \
        --name xrootdrestart \
        --userns=keep-id \
        --restart=always \
        -v /etc/xrootdrestart:/etc/xrootdrestart \
        -v /var/log:/var/log \
        -p 8000:8000 \
        xrootdrestart
INFO - ==================================================
INFO - To start the container, run the above command.
INFO - To stop the container: podman stop xrootdrestart
INFO - To remove the container: podman rm xrootdrestart
INFO - Container setup completed successfully.
INFO - All checks completed successfully.

```

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

XRootDRestart by default generates the following allerts

| Alert | Definition |
| --- | --- |
| ALERT_XROOTDRESTART_CONNECT_ERROR | Unable to connect to XRootD server |
| ALERT_XROOTDRESTART_RESTART_ERROR | Error restarting the XRootD/cmsd services |
| ALERT_XROOTDRESTART_INSUFFICIENT_SERVERS | The number of active XRootD services has dropped to the minumum allowed. No more servers will be restarted. |

Alerts are sent to the Alertmanager address set in the config option **alert_url**

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

*testing/xrootd-service/mk_xroot_service.sh* creates a dummy XRootD and cmsd services which can be used to test XRootDRestart without having to restart live servers. The services have a built in random delay of between 10 and 30 seconds when shutting down the service.

## Test Monitoring Stack

A monitoring stack is included that is run using docker containers.  

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

