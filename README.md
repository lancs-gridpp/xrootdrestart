# XRootDRestart

''NOTE'' This is currently under development.

XRootDRestart is a python script that periodically restarts xrootd and cmsd services on a list of server. It should be run from a computer that doesn't run any XRootD services.  

The script uses ssh to connect to each server to run the necessary systemctl commands.

Prometheus metrics are gathered to mlonitor the progress.  These can either be pulled directly fromm xrootdrestart or pushed via a prometheus gateway. 

## Installation

Download the files in the project into a directory on the computer that will run the script.  

The script was written for Python 3.12.7 so ensure you have a suitable version of python installed.  The necessary python packages can be installed with:

`$ pip install -r requirements.txt`


For the script to work the following need to be configured.

- xrootdrestart.conf
- ssh key pair to use for ssh authentication
- A user creating on each server running the XRootD service that will be used to authenticate when connecting via ssh. 

There is a setup script (setup.py) that will configure these.

`$ python3 setup.py`

The first time you run this it will create the xrootdrestart.conf with detault settings and terminate.  Edit the file (See config file below TODO: add link) to suit your system and then run the script again.
The setup.py script will perform the following tasks:

- Ensure the config file exists and loads the settings.
- Ensure the private/public keys to be used with SSH exist.
- Ensures the log file exists and is writable.
- For each server:
	+ Check that an ssh session can be started as the user running the setup.py script.
	+ Create the ssh user if they don't exist.
	+ Ensure the sudo rules exist to allow the ssh user to run systemctl.
	+ Copy the key to the server for ssh authentication
	+ Ensure an SSH can be enstablished as the ssh user with the key
- If URLs are defined for the Alert Manager and PUSH Gageway, it will try opening an http connection to the URL

If any of these steps fail, the setup script will abort with a message indicating the problem.  Fix the problem and run the script again. If you change the list of servers at any point just run the setup.py script to configure the new servers. 

### Running as a Service

There are two bash scripts (mk-service & rm-service)  in the *service* directory.  These scripts will create and remove the systemd service xrootdrestart.  You will need to edit scripts to set the path for your xrootdrestart.py and python command.

## Configuration File
The configuration file is used to hold the settings.  It can be editted using your favourite text editor.

The location of the text file is determined by the user who runs xrootdrestart.py.

For *root*: /etc/xrootdrestart/xrootdrestart.conf
For *others*: ~/.config/xrootdrestart/xrootdrestart.conf

This file must be writeable by xrootdrestart.py.

### Options

| Option | Default | Definition |
| --- | --- | --- |
| alrt_url       | http://localhost:9093 | Alert-manager URL + port.|
| cluseter_id    | production | Value to use in the metrics cluster label.|
| cmsd_period    | 259200 | Time in seconds between restarting the services on a server.|
| cmsd_svc       | 'cmsd@cluster' | CMSD service name.|
| cmsd_wait      | 300 | Time in seconds to wait after stopping cmsd before stopping xrootd.|
| log_level      | INFO | Logging output level: DEBUG, INFO, WARNING, ERROR, CRITICAL.|
| metrics_port   | 8000 | Listening port to provide prometheus metrics.|
| metrics_method | PULL | Method of transfering metrics: PUSH, PULL.|
| min_ok         | 1 | If the number of servers that are ok drops below this number the program will stop restarting services.|
| pkey_name      | xrootdrestartkey | File name of the private key file.|  (not including path).| Set blank to not use a pkey.|
| pkey_path      | \<same directory as the config file\> | Directory containing pkey_name file.|
| prom_url       | http://localhost:9090 | Prometheus URL + port. Not currently used. |
| pushgw_url     | http://localhost:9091 | URL + port of the gateway for pushing prometheus metrics.|
| servers        | \<blank\> | A comman separated list of server host names.|
| service_timeout| 120 | Seconds to wait for a service to stop or start.|
| ssh_user       | xrootdrestart | User used by the ssh connection.|
| xrootd_svc     | xrootd@cluster | XRootD service name.|

