#!/bin/bash

# get IB port information
IB_CONFIGURE_FILE=`ls /etc/sysconfig/network-scripts | grep ^ifcfg-ib | awk 'NR==1 {print $1}'`
IB_CONFIGURE_PATH="/etc/sysconfig/network-scripts/$IB_CONFIGURE_FILE"

# configure ib network address, network segment 10.10. is used as an example here. Please set this parameter based on the site requirements.
sed -i 's/dhcp/static/g' $IB_CONFIGURE_PATH
ip addr | grep "inet " | grep -v 127.0.0.1 | awk -F '[ .:/]+' 'NR==1 {print "IPADDR=10.10."$5"."$6}' >> $IB_CONFIGURE_PATH
echo "NETMASK=255.255.0.0" >> $IB_CONFIGURE_PATH

# configure LNET
IB_NUM=${IB_CONFIGURE_FILE: -1}
echo "options lnet networks=o2ib$IB_NUM(ib$IB_NUM)" > /etc/modprobe.d/iml_lnet_module_parameters.conf

# make the LNET configuration take effect
ifdown ib$IB_NUM
ifup ib$IB_NUM

lustre_rmmod
modprobe lnet
modprobe lustre

lctl network down
lctl network up