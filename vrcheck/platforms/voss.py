import re

from .base import Marker, Platform

IPV4 = r"\d+\.\d+\.\d+\.\d+"


class Voss(Platform):
    name = "VOSS"
    image = "extreme_voss"
    netmiko_type = "extreme_vsp"

    def startup_config_log_pattern(self, passthrough):
        # Without passthrough, vrnetlab loads the config over TFTP (`source /intflash/containerlab.cfg`)
        # and logs nothing about it. With passthrough, it types it in the console and logs that.
        return self.startup_config_log if passthrough else None

    def mgmt_ip(self, conn):
        conn.enable()  # netmiko's extreme_vsp driver stays in user mode
        # INST   DESCR      IPV4                 TYPE (ORIGIN)
        # 1      oob1       172.20.20.3/24        Manual
        # 4      vlan       169.254.106.4/16      Link-Local   <- onboarding VLAN, not what vrnetlab sets
        m = re.search(rf"^\s*\d+\s+oob\S*\s+({IPV4})/", conn.send_command("show mgmt ip"), re.M)
        return m.group(1) if m else None

    def startup_config_markers(self, conn):
        conn.enable()
        running = conn.send_command("show running-config")
        # interface Vlan 123
        # ip address 1.2.3.4 255.255.255.0 ...
        # exit
        vlan = re.search(
            r"^interface vlan 123\s*$(?:(?!^exit).)*?^\s*ip address 1\.2\.3\.4 255\.255\.255\.0",
            running,
            re.M | re.S | re.I,
        )
        # snmp-server contact "netlab-test"
        contact = re.search(r'^snmp-server contact "?([^"\n]*)"?', running, re.M)
        contact = contact.group(1).strip() if contact else ""
        return [
            Marker("interface vlan 123 with 1.2.3.4/24", vlan is not None),
            Marker("snmp-server contact netlab-test", contact == "netlab-test", contact),
        ]
