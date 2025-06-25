# XRootDRestart

## Introduction

XRootDRestart is a python script that periodically restarts cmsd and XRootD services on a list of servers. It does this using ssh to connect to each server in turn to run the necessary systemctl commands to stop and start the services.

After connecting to a server, it stops cmsd, waits for a predefined length of time before restarting XRootD.  Finally cmsd is restarted and the ssh connection is closed.  If there are any problems restarting the services alerts are generated and sent using AlertManager.  Alerts can be disabled if not required.

There are various metrics recorded which can then be processed by Prometheus.  The metrics are set to be 'pulled' by default but it can be configured to push the metrics to a push gateway. 

It has been noted that occationally the XRootD process fail to terminate.  When this happens it is necessary to reboot the server. For this reason it is recommended that XRoodDRestart be run from a machine that does not run any XRootD services.

A setup script can be used to configure XRootDRestart to run either as a service or in docker/podman container.  It also  connects to the XRootD servers and ensure they are configured correctly to allow XRootDRestart to connect and control the XRootD services.


## Requirements

The script was written using Python 3.12.7 so ensure you have a suitable version of **python** installed.  

If you want to run XRoodDRestart in a container or run the Monitoring stack for testing, you will need either **docker** or **podman** installed. 

You will need **git** to clone the github repository.

You will need the following package: **python3-devel**

The user that runs the setup script must have ssh access to all the xrootdservers.

Whichever user you choose to run XRootDRestart much have write access to /var/log/xrootdrestart.log

## Downloading

Clone the github respository:

```
# cd /opt
# git clone https://github.com/lancs-gridpp/xrootdrestart.git
# cd xrootdrestart
```

## Installing

### Overview
XRootDRestart can be run as a systemd service or using a podman/docker container.  The user used to run the setup script will dermine if a system or user service will be created.  If building a container image, the user that runs the setup script will be used by the contianer image. 

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
* If URLs are defined for the Alert Manager and PUSH Gageway, it will try opening an http connection to the defined URLs
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

Edit the config file and set the options as required.  The basic ones you will need to set are: **servers**, **ssh_user**, **pkey_name**, **pkey_path**, **cmsd_svc** and **xrootd_svc**.

**alert_url**, **cluster_id**, **metrics_port**, **metrics_method**, **prom_url** and **pushgw_url** are all used transfer metrics and generate alerts.  If you are not using these, blank the "*_url" options.

Once you have set the config file as you want it, re-run the setup script.

```
# ./setup service
Running setup script (setup.py) ...
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

Run setup in the xrootdrestart directory specifying the parameter **container**.  The user used to run the setup script will be used by the container image to run xrootdrestart.

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
Running setup script (setup.py) ...
/opt/xrootdrestart/.venv/lib64/python3.6/site-packages/paramiko/transport.py:32: CryptographyDeprecationWarning: Python 3.6 is no longer supported by the Python core team. Therefore, support for it is deprecated in cryptography. The next release of cryptography will remove support for Python 3.6.
  from cryptography.hazmat.backends import default_backend
INFO - Running setup in container mode
INFO - Config file /etc/xrootdrestart/xrootdrestart.conf created at. Please edit it and run the script again.
[root@localhost xrootdrestart]# vi /etc/xrootdrestart/xrootdrestart.conf 

```

The script has created a default config file. See [Configuration File](#configuration-file) for details of the available options.

Edit the config file and set the options as required.  The basic ones you will need to set are: **servers**, **ssh_user**, **pkey_name**, **pkey_path**, **cmsd_svc** and **xrootd_svc**.

**alert_url**, **cluster_id**, **metrics_port**, **metrics_method**, **prom_url** and **pushgw_url** are all used transfer metrics and generate alerts.  If you are not using these, blank the "*_url" options.

Once you have set the config file as you want it, re-run the setup script.

```
]# ./setup container
Running setup script (setup.py) ...
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
AlmaLinux 9 - BaseOS                            6.7 MB/s | 9.5 MB     00:01    
AlmaLinux 9 - Extras                             47 kB/s |  20 kB     00:00    
Dependencies resolved.
================================================================================
 Package                    Arch       Version                 Repository  Size
================================================================================
Upgrading:
 glibc                      x86_64     2.34-168.el9_6.19       baseos     1.9 M
 glibc-common               x86_64     2.34-168.el9_6.19       baseos     295 k
 glibc-minimal-langpack     x86_64     2.34-168.el9_6.19       baseos      22 k

Transaction Summary
================================================================================
Upgrade  3 Packages

Total download size: 2.2 M
Downloading Packages:
(1/3): glibc-minimal-langpack-2.34-168.el9_6.19 407 kB/s |  22 kB     00:00    
(2/3): glibc-common-2.34-168.el9_6.19.x86_64.rp 2.5 MB/s | 295 kB     00:00    
(3/3): glibc-2.34-168.el9_6.19.x86_64.rpm       6.0 MB/s | 1.9 MB     00:00    
--------------------------------------------------------------------------------
Total                                           3.3 MB/s | 2.2 MB     00:00     
Running transaction check
Transaction check succeeded.
Running transaction test
Transaction test succeeded.
Running transaction
  Preparing        :                                                        1/1 
  Upgrading        : glibc-common-2.34-168.el9_6.19.x86_64                  1/6 
  Upgrading        : glibc-minimal-langpack-2.34-168.el9_6.19.x86_64        2/6 
  Running scriptlet: glibc-2.34-168.el9_6.19.x86_64                         3/6 
  Upgrading        : glibc-2.34-168.el9_6.19.x86_64                         3/6 
  Running scriptlet: glibc-2.34-168.el9_6.19.x86_64                         3/6 
  Cleanup          : glibc-2.34-168.el9_6.14.alma.1.x86_64                  4/6 
  Cleanup          : glibc-minimal-langpack-2.34-168.el9_6.14.alma.1.x86_   5/6 
  Cleanup          : glibc-common-2.34-168.el9_6.14.alma.1.x86_64           6/6 
  Running scriptlet: glibc-common-2.34-168.el9_6.14.alma.1.x86_64           6/6 
  Verifying        : glibc-2.34-168.el9_6.19.x86_64                         1/6 
  Verifying        : glibc-2.34-168.el9_6.14.alma.1.x86_64                  2/6 
  Verifying        : glibc-common-2.34-168.el9_6.19.x86_64                  3/6 
  Verifying        : glibc-common-2.34-168.el9_6.14.alma.1.x86_64           4/6 
  Verifying        : glibc-minimal-langpack-2.34-168.el9_6.19.x86_64        5/6 
  Verifying        : glibc-minimal-langpack-2.34-168.el9_6.14.alma.1.x86_   6/6 

Upgraded:
  glibc-2.34-168.el9_6.19.x86_64                                                
  glibc-common-2.34-168.el9_6.19.x86_64                                         
  glibc-minimal-langpack-2.34-168.el9_6.19.x86_64                               

Complete!
Last metadata expiration check: 0:00:01 ago on Wed Jun 25 11:59:21 2025.
Package python3-3.9.21-2.el9.x86_64 is already installed.
Dependencies resolved.
================================================================================
 Package                 Arch        Version               Repository      Size
================================================================================
Installing:
 openssh                 x86_64      8.7p1-45.el9          baseos         455 k
 python3-pip             noarch      21.3.1-1.el9          appstream      1.7 M
Installing weak dependencies:
 libxcrypt-compat        x86_64      4.4.18-3.el9          appstream       88 k
 python3-setuptools      noarch      53.0.0-13.el9         baseos         838 k

Transaction Summary
================================================================================
Install  4 Packages

Total download size: 3.1 M
Installed size: 15 M
Downloading Packages:
(1/4): libxcrypt-compat-4.4.18-3.el9.x86_64.rpm 1.1 MB/s |  88 kB     00:00    
(2/4): openssh-8.7p1-45.el9.x86_64.rpm          1.4 MB/s | 455 kB     00:00    
(3/4): python3-pip-21.3.1-1.el9.noarch.rpm      4.7 MB/s | 1.7 MB     00:00    
(4/4): python3-setuptools-53.0.0-13.el9.noarch. 2.4 MB/s | 838 kB     00:00    
--------------------------------------------------------------------------------
Total                                           2.8 MB/s | 3.1 MB     00:01     
Running transaction check
Transaction check succeeded.
Running transaction test
Transaction test succeeded.
Running transaction
  Preparing        :                                                        1/1 
  Installing       : python3-setuptools-53.0.0-13.el9.noarch                1/4 
  Installing       : libxcrypt-compat-4.4.18-3.el9.x86_64                   2/4 
  Installing       : python3-pip-21.3.1-1.el9.noarch                        3/4 
  Running scriptlet: openssh-8.7p1-45.el9.x86_64                            4/4 
  Installing       : openssh-8.7p1-45.el9.x86_64                            4/4 
  Running scriptlet: openssh-8.7p1-45.el9.x86_64                            4/4 
  Verifying        : libxcrypt-compat-4.4.18-3.el9.x86_64                   1/4 
  Verifying        : python3-pip-21.3.1-1.el9.noarch                        2/4 
  Verifying        : openssh-8.7p1-45.el9.x86_64                            3/4 
  Verifying        : python3-setuptools-53.0.0-13.el9.noarch                4/4 

Installed:
  libxcrypt-compat-4.4.18-3.el9.x86_64  openssh-8.7p1-45.el9.x86_64             
  python3-pip-21.3.1-1.el9.noarch       python3-setuptools-53.0.0-13.el9.noarch 

Complete!
26 files removed
--> f36d7041718b
STEP 3/9: COPY requirements.txt /tmp/requirements.txt
--> 93183872a3f0
STEP 4/9: RUN pip3 install --no-cache-dir -r /tmp/requirements.txt
Collecting paramiko
  Downloading paramiko-3.5.1-py3-none-any.whl (227 kB)
Collecting prometheus_client
  Downloading prometheus_client-0.22.1-py3-none-any.whl (58 kB)
Collecting requests
  Downloading requests-2.32.4-py3-none-any.whl (64 kB)
Collecting requests-file
  Downloading requests_file-2.1.0-py2.py3-none-any.whl (4.2 kB)
Collecting requests-ftp
  Downloading requests-ftp-0.3.1.tar.gz (7.8 kB)
  Preparing metadata (setup.py): started
  Preparing metadata (setup.py): finished with status 'done'
Collecting requests-oauthlib
  Downloading requests_oauthlib-2.0.0-py2.py3-none-any.whl (24 kB)
Collecting schedule
  Downloading schedule-1.2.2-py3-none-any.whl (12 kB)
Collecting pynacl>=1.5
  Downloading PyNaCl-1.5.0-cp36-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.manylinux_2_24_x86_64.whl (856 kB)
Collecting bcrypt>=3.2
  Downloading bcrypt-4.3.0-cp39-abi3-manylinux_2_34_x86_64.whl (284 kB)
Collecting cryptography>=3.3
  Downloading cryptography-45.0.4-cp37-abi3-manylinux_2_34_x86_64.whl (4.5 MB)
Collecting charset_normalizer<4,>=2
  Downloading charset_normalizer-3.4.2-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (149 kB)
Collecting urllib3<3,>=1.21.1
  Downloading urllib3-2.5.0-py3-none-any.whl (129 kB)
Collecting certifi>=2017.4.17
  Downloading certifi-2025.6.15-py3-none-any.whl (157 kB)
Collecting idna<4,>=2.5
  Downloading idna-3.10-py3-none-any.whl (70 kB)
Collecting oauthlib>=3.0.0
  Downloading oauthlib-3.3.1-py3-none-any.whl (160 kB)
Collecting cffi>=1.14
  Downloading cffi-1.17.1-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (445 kB)
Collecting pycparser
  Downloading pycparser-2.22-py3-none-any.whl (117 kB)
Using legacy 'setup.py install' for requests-ftp, since package 'wheel' is not installed.
Installing collected packages: pycparser, urllib3, idna, charset-normalizer, cffi, certifi, requests, pynacl, oauthlib, cryptography, bcrypt, schedule, requests-oauthlib, requests-ftp, requests-file, prometheus-client, paramiko
    Running setup.py install for requests-ftp: started
    Running setup.py install for requests-ftp: finished with status 'done'
Successfully installed bcrypt-4.3.0 certifi-2025.6.15 cffi-1.17.1 charset-normalizer-3.4.2 cryptography-45.0.4 idna-3.10 oauthlib-3.3.1 paramiko-3.5.1 prometheus-client-0.22.1 pycparser-2.22 pynacl-1.5.0 requests-2.32.4 requests-file-2.1.0 requests-ftp-0.3.1 requests-oauthlib-2.0.0 schedule-1.2.2 urllib3-2.5.0
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv
--> 71d9c23405de
STEP 5/9: COPY xrootdrestart.py /root/xrootdrestart.py
--> cfbf2f4fe2ad
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
INFO - To stop the container: podman stop xrootdrestart-container
INFO - To remove the container: podman rm xrootdrestart-container
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

