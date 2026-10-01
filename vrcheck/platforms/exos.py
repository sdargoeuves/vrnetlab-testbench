import re

from .base import Marker, Platform


class Exos(Platform):
    name = "EXOS"
    image = "extreme_exos"
    netmiko_type = "extreme_exos"
    # vrnetlab pulls the config over TFTP without passthrough, and types it in the console with passthrough.
    startup_config_log = r"Writing lines from /config/startup-config|tftp get"

    def mgmt_ip(self, conn):
        # "    Primary IP:		 172.20.20.5/24"
        m = re.search(r"Primary IP:\s+([\d.]+)/", conn.send_command("show vlan Mgmt"))
        return m.group(1) if m else None

    def startup_config_markers(self, conn):
        vlan = conn.send_command("show vlan test123")
        # "SysContact:       netlab-test"
        contact = re.search(r"^SysContact:\s*(.*)$", conn.send_command("show switch"), re.M)
        contact = contact.group(1).strip() if contact else ""
        return [
            Marker("VLAN test123 with 1.2.3.4/24", "1.2.3.4/24" in vlan),
            Marker("SysContact netlab-test", contact == "netlab-test", contact),
        ]
