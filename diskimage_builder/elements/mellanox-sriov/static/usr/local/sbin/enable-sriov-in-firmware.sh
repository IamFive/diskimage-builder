#!/bin/bash

sudo mst start
MST_DEVICE=$(sudo mst status | grep "/dev/mst" | cut -d ' ' -f 1)

sudo mlxconfig -y -d ${MST_DEVICE} set SRIOV_EN=1 NUM_OF_VFS=@DIB_MLNX_SRIOV_VFS_NUM@

# NOTE(turnbig): This action has no effect in fact, 
# a reboot is still required to make previous action take effct
# mlxfwreset -y --device ${MST_DEVICE} reset
