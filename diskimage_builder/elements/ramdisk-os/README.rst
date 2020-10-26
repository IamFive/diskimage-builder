===========================
ramdisk-os
===========================
Builds a ramdisk image.

This element aims to build ramdisk image for Ironic "ramdisk" deploy 
interface.

Along with building ramdisk image, this element includes below features:

* Installs the ``dhcp-all-interfaces`` so the node, upon booting, attempts to
  obtain an IP address on all available network interfaces.
* Installs the ``runtime-ssh-host-keys`` and ``openssh-server`` to enable ssh
  login which is commonly required by a cloud operating system.

This element outputs two files:

- ``$IMAGE-NAME.initramfs``: The ramdisk image file.
- ``$IMAGE-NAME.kernel``: The kernel binary file.
