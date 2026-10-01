import re

from .base import Marker, Platform


class Aoscx(Platform):
    name = "AOS-CX"
    image = "aruba_arubaos-cx"
    netmiko_type = "aruba_aoscx"
    # vrnetlab resets admin's password to "admin", which is also what the aruba_aoscx kind passes.
    username = "admin"
    password = "admin"

    def mgmt_ip(self, conn):
        # "  IPv4 address/subnet-mask    : 172.20.20.5/24"
        m = re.search(r"IPv4 address[^:\n]*:\s*([\d.]+)/", conn.send_command("show interface mgmt"))
        return m.group(1) if m else None

    def startup_config_markers(self, conn):
        running = conn.send_command("show running-config")
        # "interface vlan123" block with "    ip address 1.2.3.4/24"
        vlan = re.search(r"^interface vlan ?123\n(?:[ \t]+.*\n)*?[ \t]+ip address 1\.2\.3\.4/24", running, re.M)
        contact = re.search(r"^snmp-server system-contact (.*)$", running, re.M)
        contact = contact.group(1).strip() if contact else ""
        return [
            Marker("interface vlan123 with 1.2.3.4/24", vlan is not None),
            Marker("snmp system-contact netlab-test", contact == "netlab-test", contact),
        ]
