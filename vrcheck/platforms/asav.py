import re

from .base import Marker, Platform


class Asav(Platform):
    name = "ASAv"
    image = "cisco_asav"
    netmiko_type = "cisco_asa"
    # Defaults of the cisco_asav kind and of vrnetlab's launch.py (login and enable password).
    username = "admin"
    password = "CiscoAsa1!"
    startup_config_log = r"Startup configuration file found"

    def mgmt_ip(self, conn):
        # "	IP address 172.20.20.5, subnet mask 255.255.255.0"
        m = re.search(r"IP address ([\d.]+),", conn.send_command("show interface Management0/0"))
        return m.group(1) if m else None

    def startup_config_markers(self, conn):
        # " ip address 1.2.3.4 255.255.255.0"
        intf = conn.send_command("show running-config interface GigabitEthernet0/0.123")
        # "snmp-server contact netlab-test"
        contact = re.search(r"^snmp-server contact (.*)$", conn.send_command("show running-config snmp-server"), re.M)
        contact = contact.group(1).strip() if contact else ""
        return [
            Marker("Gi0/0.123 with 1.2.3.4/24", "ip address 1.2.3.4 255.255.255.0" in intf),
            Marker("snmp-server contact netlab-test", contact == "netlab-test", contact),
        ]
