"""Base class for a vrnetlab platform.

To support a new platform, create a file next to this one with a subclass that:
  - sets `image`, `netmiko_type` and, if needed, the credentials
  - implements `mgmt_ip()` and `startup_config_markers()`
then add it to PLATFORMS in platforms/__init__.py.
"""

from dataclasses import dataclass

from netmiko import BaseConnection


@dataclass
class Marker:
    """One thing the test startup-config (configs/*-test.*) should have changed on the device."""

    label: str  # e.g. "VLAN 123 with 1.2.3.4/24"
    found: bool
    observed: str = ""  # what the device returned, shown in the report


class Platform:
    name = "generic"
    image = ""  # substring of the docker image name, e.g. "extreme_exos"
    netmiko_type = ""

    # vrnetlab defaults. Native containerlab kinds may pass other credentials.
    username = "vrnetlab"
    password = "VR-netlab9"
    # False when vrnetlab ignores --username and the account keeps the default name.
    custom_username = True

    # Mgmt IP inside the VM when passthrough is off (vrnetlab qemu user-net).
    hostfwd_mgmt_ip = "10.0.0.15"

    # Regex that shows in `docker logs` when vrnetlab pushes the startup-config.
    startup_config_log = r"Writing lines from /config/startup-config"

    def startup_config_log_pattern(self, passthrough: bool) -> str | None:
        """Regex for the push in `docker logs`, or None if vrnetlab logs nothing in this mode."""
        return self.startup_config_log

    def mgmt_ip(self, conn: BaseConnection) -> str | None:
        """Return the IPv4 address (no prefix length) configured on the VM's mgmt interface."""
        raise NotImplementedError

    def startup_config_markers(self, conn: BaseConnection) -> list[Marker]:
        """Return what the test startup-config should have changed on the device."""
        raise NotImplementedError
