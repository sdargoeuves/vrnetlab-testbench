import re

from .base import Marker, Platform


class Vsrx(Platform):
    name = "vSRX"
    image = "juniper_vsrx"
    netmiko_type = "juniper_junos"
    # Defaults of the juniper_vsrx kind and of vrnetlab's init.conf.
    username = "admin"
    password = "admin@123"
    # init.conf hard-codes `user admin`: vrnetlab only applies --password.
    custom_username = False
    # vrnetlab appends the startup-config to init.conf and boots from a config ISO (trace log).
    startup_config_log = r"Startup config file /config/startup-config\.cfg found"

    def mgmt_ip(self, conn):
        # "fxp0.0                  up    up   inet     172.20.20.5/24"
        m = re.search(r"inet\s+([\d.]+)/", conn.send_command("show interfaces fxp0.0 terse"))
        return m.group(1) if m else None

    def startup_config_markers(self, conn):
        # "set interfaces ge-0/0/1 unit 123 family inet address 1.2.3.4/24"
        intf = conn.send_command("show configuration interfaces ge-0/0/1 | display set")
        # "set snmp contact netlab-test"
        contact = re.search(r'^set snmp contact "?([^"\n]*)"?', conn.send_command("show configuration snmp | display set"), re.M)
        contact = contact.group(1).strip() if contact else ""
        return [
            Marker("ge-0/0/1.123 with 1.2.3.4/24", "unit 123 family inet address 1.2.3.4/24" in intf),
            Marker("snmp contact netlab-test", contact == "netlab-test", contact),
        ]
