#!/usr/bin/env python
import json
import logging
import os
import subprocess
import sys
from urllib2 import Request, urlopen, URLError

MLNX_ADDRESS_LEN = 59

MLNX_SRIOV_KEY = "mlnx_sriov"
BD_ENABLE_SRIOV = 'enable_sriov'
BD_DFT_LIMITED_PKEYS = 'default_limited_pkeys'
BD_PHYSICAL_GUIDS = 'physical_guids'
BD_VIRTUAL_GUIDS = 'virtual_guids'
BD_DYNAMIC_PKEY = 'dynamic_pkey'

MLNX_VENDOR_ID = '0x15b3'
# Mellanox Prefix to generate InfiniBand CLient-ID
MLNX_INFINIBAND_CLIENT_ID_PREFIX = 'ff:00:00:00:00:00:02:00:00:02:c9:00:'

VENDOR_DATA2_URL = ("http://169.254.169.254/openstack"
                    "/2018-08-27/vendor_data2.json")

LOG_LEVEL = logging.DEBUG
LOG_FMT = '%(asctime)-15s [%(funcName)s:%(lineno)s] %(message)s'


def setup_logging():
    logging.basicConfig(
        filename='/var/log/mlnx-sriov.log',
        level=LOG_LEVEL,
        format=LOG_FMT
    )

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(LOG_LEVEL)
    console.setFormatter(logging.Formatter(LOG_FMT))

    logger = logging.getLogger()
    logger.addHandler(console)


def run_cmd(cmd, exit_on_error=True):
    """
    Execute the external command and get its exitcode, stdout and stderr.
    """
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    ret = proc.returncode

    logging.info("Run os cmd: %s, ret code: %d.", cmd, ret)
    logging.info("Stdout:: \n%s", stdout)
    if ret != 0:
        logging.info("Stderr:: \n%s", stderr)

    if ret != 0 and exit_on_error:
        exit(ret)

    return ret, stdout, stderr


def _get_device_info(dev, devclass, field):
    """Get the device info according to device class and field."""
    try:
        devname = os.path.basename(dev)
        with open('/sys/class/%s/%s/device/%s' % (devclass, devname, field),
                  'r') as f:
            return f.read().strip()
    except IOError:
        logging.info("Can't find field {} for device {} in device class {}"
                     .format(field, dev, devclass))


def _get_guid_from_address(address):
    """The InfiniBand address is 59 characters
    composed from GID:GUID. The last 24 characters are the
    GUID. The InfiniBand MAC is upper 10 characters and lower
    9 characters from the GUID.

    Example:
    address   - ff:00:00:00:00:00:02:00:00:02:c9:00:04:bd:70:03:00:37:44:86
                (Mellanox InfiniBand Prefix)      + address[36:]
    GUID      - 04:bd:70:03:00:37:44:86
    MAC       - 04:bd:70:37:44:86

    :param address: mellanox port address
    :return:
    """
    if address and len(address) == MLNX_ADDRESS_LEN:
        return address[-24:].replace(':', '')

    return address


def load_vendor2_metadata():
    req = Request(VENDOR_DATA2_URL)
    try:
        response = urlopen(req)
        vendor_data2_string = response.read()
        vendor_data2_json = json.loads(vendor_data2_string)
        mlnx_sriov_vif_details = vendor_data2_json.get(MLNX_SRIOV_KEY)
        return mlnx_sriov_vif_details
    except URLError as e:
        if hasattr(e, 'reason'):
            logging.error('Failed to reach metadata server. Reason: %s',
                          e.reason)
        elif hasattr(e, 'code'):
            logging.error(
                'Metadata server failed to responses. Error code: %s', e.code)
        raise
    except Exception as e:
        logging.info("Failed to load vendor data2 metadata, Exception :", e)
        raise


def create_sriov_interfaces():
    vif_details = load_vendor2_metadata()
    """SR-IOV binding details list example:
    {
        "physical_guids": [
            "04bd700300374486",
            "04bd700300374487"
        ],
        "dynamic_pkey": "0x3e7e",
        "default_limited_pkeys": [
            "0xBAD0",
            "0xF00D"
        ],
        "enable_sriov": true,
        "virtual_guids": [
            [
                "fefeab03004f86b9",
                "fefe2b03002a5777"
            ],
            [
                "fefe6a03009db202",
                "fefe7d030069c502"
            ]
        ]
    }
    """

    # if len(vif_details) == 0:
    #     logging.info("No sriov binding details returned.")
    #     return
    create_interfaces(vif_details)
    rebind_vf_interfaces()

    # TODO(turnbig): dhcp IB interfaces?


def rebind_vf_interfaces():
    logging.info("Rebinding SRIOV virtual functions now")

    unbind_cmd = "echo %s > /sys/bus/pci/drivers/mlx5_core/unbind"
    bind_cmd = "echo %s > /sys/bus/pci/drivers/mlx5_core/bind"

    get_vf_list_cmd = 'lspci -D | grep Mellanox | grep "Virtual Function"'
    ret, stdout, stderr = run_cmd(get_vf_list_cmd)
    vf_list = stdout.strip().split('\n')
    for vf in vf_list:
        pci_id = vf.split(' ')[0].strip()
        if pci_id and len(pci_id) > 0:
            run_cmd(unbind_cmd % pci_id)
            run_cmd(bind_cmd % pci_id)


def create_interfaces(vif_details):
    if_names = os.listdir('/sys/class/net')
    for if_name in if_names:
        if _get_device_info(if_name, 'net', 'vendor') != MLNX_VENDOR_ID:
            logging.info("Interface %s is not a Mellanox port, skip.", if_name)
            continue

        logging.info("Interface %s is a Mellanox port, processing now.",
                     if_name)
        # try to get guid and physical status
        with open('/sys/class/net/%s/address' % if_name, 'r') as f:
            address = f.read().strip()

        guid = _get_guid_from_address(address)
        logging.info("IF %s's address is: %s, guid is: %s",
                     if_name, address, guid)
        if not guid:
            logging.info("guid %s is not a valid Mellanox GUID, skip IF %s.",
                         (guid, if_name))
            continue

        logging.info("Try create SRIOV ports with vif details: %s",
                     vif_details)
        sriov_enabled = vif_details.get(BD_ENABLE_SRIOV, False)
        if not sriov_enabled:
            logging.info("SR-IOV is not enabled, skip this binding "
                         "details.")
            continue

        physical_guids = vif_details.get(BD_PHYSICAL_GUIDS)
        if guid in physical_guids:
            idx = physical_guids.index(guid)
            virtual_guids_list = vif_details.get(BD_VIRTUAL_GUIDS)
            virtual_guids = virtual_guids_list[idx]
            logging.info("Pending created SRIOV ports have "
                         "virtual guids: %s", virtual_guids)
            # create SRIOV ports now

            # step1: make sure allowed VF number is greater than virtual guids
            sriov_totalvfs = _get_device_info(if_name, 'net', 'sriov_totalvfs')
            if sriov_totalvfs and sriov_totalvfs.isdigit():
                if len(virtual_guids) > int(sriov_totalvfs):
                    logging.error("SRIOV total VFS number %d is less than "
                                  "required amount %d."
                                  % (int(sriov_totalvfs), len(virtual_guids)))
                    exit(1)
            else:
                logging.error("SRIOV is not enabled on Mellanox firmware.")
                exit(1)

            # Step2: Set SRIOV VFS number. Changing the number of VFs is
            # non-persistent and does not survive a server reboot!
            sriov_numvfs_path = ('/sys/class/net/%s/device/sriov_numvfs' %
                                 if_name)
            set_vfs_number_cmd = "echo %d > %s" % (len(virtual_guids),
                                                   sriov_numvfs_path)
            subprocess.call(set_vfs_number_cmd, shell=True)

            # Step3: update SRIOV ports's policy and virtual guid
            for i in range(0, len(virtual_guids)):
                sriov_port_path = ('/sys/class/net/%s/device/sriov/%d'
                                   % (if_name, i))
                subprocess.call("echo Follow > %s/policy" % sriov_port_path,
                                shell=True)

                virtual_guid = virtual_guids[i]
                guid = ':'.join(virtual_guid[n:n + 2]
                                for n in range(0, len(virtual_guid), 2))
                write_node_guid_cmd = ("echo %s > %s/node"
                                       % (guid, sriov_port_path))
                ret = subprocess.call(write_node_guid_cmd, shell=True)
                logging.info("Run cmd: %s, ret code: %d",
                             write_node_guid_cmd, ret)

                write_port_guid_cmd = ("echo %s > %s/port"
                                       % (guid, sriov_port_path))
                ret = subprocess.call(write_port_guid_cmd, shell=True)
                logging.info("Run cmd: %s, ret code: %d",
                             write_port_guid_cmd, ret)
        else:
            logging.info("physical guid is not included, skip this binding "
                         "details.")
            continue


if __name__ == "__main__":
    setup_logging()
    create_sriov_interfaces()
