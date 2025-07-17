#!/usr/bin/bash

################################################################################
# mystartup.sh
#
# This shell program is for testing a startup like rc.local using systemd.
# By David Both
# Licensed under GPL V2
#
################################################################################

# This program should be placed in /usr/local/bin

################################################################################
# This is a test entry

svc_enabled=$(systemctl is-enabled oled_monitor.service)
if [ "${svc_enabled}" == "disabled" ];then
	systemctl enable oled_monitor.service
	systemctl start oled_monitor.service
fi

echo `date +%F" "%T` "Startup worked" >> /var/log/mystartup.log
