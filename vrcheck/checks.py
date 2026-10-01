"""The checks run on every node, whatever the platform.

The expected result comes from the container itself, not from the node name:
  passthrough expected    <- CLAB_MGMT_PASSTHROUGH=true on the container
  startup-config expected <- a file mounted on /config/startup-config.*
  credentials             <- --username/--password passed to vrnetlab, else the platform defaults
"""

import re
from dataclasses import dataclass

from netmiko import ConnectHandler, NetmikoAuthenticationException

from .lab import Node
from .platforms import Platform, platform_for


@dataclass
class Check:
    name: str
    passed: bool | None  # None = skipped
    detail: str = ""


@dataclass
class Creds:
    username: str  # the one to log in with
    password: str
    custom_username: bool  # the topology asks for a non-default username
    custom_password: bool


def effective_creds(node: Node, platform: Platform) -> Creds:
    """The node's --username/--password, else the platform defaults."""
    username = node.username or platform.username
    password = node.password or platform.password
    return Creds(
        # Where vrnetlab ignores --username, the account keeps the default name.
        username=username if platform.custom_username else platform.username,
        password=password,
        custom_username=username != platform.username,
        custom_password=password != platform.password,
    )


def check_node(node: Node, device: bool = True) -> list[Check]:
    platform = platform_for(node.image)
    checks = log_checks(node, platform)
    boot_ok = checks[0].passed

    if not device:
        return checks
    if platform is None:
        checks.append(Check("device", None, f"no platform in vrcheck/platforms/ matches image {node.image}"))
    elif not boot_ok:
        checks.append(Check("device", None, "not booted"))
    else:
        checks += device_checks(node, platform)
    return checks


def log_checks(node: Node, platform: Platform | None) -> list[Check]:
    """What vrnetlab says it did, from `docker logs`."""
    booted = re.findall(r"Startup complete in: ([\d:]+)", node.logs)
    checks = [Check("boot", bool(booted), f"startup complete in {booted[-1]}" if booted else "no 'Startup complete' yet")]

    mode = re.findall(r"Transparent mgmt interface: (\w+)", node.logs)
    mode = mode[-1] if mode else "not logged"
    checks.append(Check("log: mgmt mode", (mode == "Enabled") == node.passthrough, f"transparent mgmt {mode}"))

    if node.startup_config and platform:
        pattern = platform.startup_config_log_pattern(node.passthrough)
        if not booted:
            checks.append(Check("log: startup-config", None, "not booted"))
        elif pattern is None:
            checks.append(Check("log: startup-config", None, "not logged by vrnetlab in this mode, see device checks"))
        else:
            pushed = re.search(pattern, node.logs) is not None
            checks.append(Check("log: startup-config", pushed, "pushed" if pushed else "no trace of the push"))
    return checks


def _connect(node: Node, platform: Platform, username: str, password: str):
    return ConnectHandler(
        device_type=platform.netmiko_type,
        host=node.ip,
        username=username,
        password=password,
        secret=password,  # enable password, where the platform has one (ASA)
        conn_timeout=20,
    )


def device_checks(node: Node, platform: Platform) -> list[Check]:
    """What the device actually has, over SSH."""
    creds = effective_creds(node, platform)
    username, password = creds.username, creds.password
    checks = []
    if creds.custom_username and not platform.custom_username:
        detail = f"vrnetlab {platform.name} ignores --username {node.username}, user stays {platform.username}"
        checks.append(Check("device: custom username", False, detail))
    try:
        with _connect(node, platform, username, password) as conn:
            mgmt_ip = platform.mgmt_ip(conn)
            markers = platform.startup_config_markers(conn)
    except Exception as e:  # any SSH/parsing failure fails the node, it doesn't stop the run
        return checks + [Check(f"device: ssh as {username}", False, f"{type(e).__name__}: {e}")]

    checks.append(Check(f"device: ssh as {username}", True, "custom password" if creds.custom_password else "default password"))
    if creds.custom_password:
        checks.append(default_password_rejected(node, platform, username))

    # The proof of passthrough: the VM owns the container IP, else it has the qemu user-net address.
    want_ip = node.ip if node.passthrough else platform.hostfwd_mgmt_ip
    checks.append(Check("device: mgmt IP", mgmt_ip == want_ip, f"{mgmt_ip} (expected {want_ip})"))

    # Markers must be present with a startup-config, and absent without one.
    for m in markers:
        detail = ("present" if m.found else "absent") + (f": {m.observed!r}" if m.observed else "")
        checks.append(Check(f"device: {m.label}", m.found == node.startup_config, detail))
    return checks


def default_password_rejected(node: Node, platform: Platform, username: str) -> Check:
    """With custom credentials, the platform's default password must no longer work."""
    name = "device: default password rejected"
    try:
        with _connect(node, platform, username, platform.password):
            return Check(name, False, f"'{platform.password}' still accepted for {username}")
    except NetmikoAuthenticationException:
        return Check(name, True, f"'{platform.password}' refused for {username}")
    except Exception as e:
        return Check(name, False, f"unexpected {type(e).__name__}: {e}")
