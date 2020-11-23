=============
mellanox-ofed
=============

This element aims to install MLNX_OFED_LINUX package for target image. 

This element shadows the mellanox element. Mellanox driver is included in
Mellanox OFED package. Please Note that all other Mellanox, OEM, OFED, RDMA 
or Distribution IB packages will be removed. Those packages are removed due
to conflicts with MLNX_OFED_LINUX, do not reinstall them.

To include this element:
 * This element only supports CentOS 7.8 distribution
 * DIB tool should be installed on a CentOS 7.8 OS with kernel 3.10.0-1127
 * The server should has physical Mellanox infiniband port present
