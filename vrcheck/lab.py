"""Read the nodes of a running containerlab lab from Docker."""

import json
import re
import subprocess
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import yaml

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class Node:
    container: str  # e.g. clab-vrt-exos-x326-pt
    name: str  # node name in the topology, e.g. x326-pt
    image: str
    ip: str  # container eth0 IP on the clab mgmt network
    passthrough: bool  # CLAB_MGMT_PASSTHROUGH=true on the container
    startup_config: bool  # a file is mounted on /config/startup-config.*
    logs: str  # docker logs, ANSI colors removed
    # --username/--password that containerlab passed to vrnetlab (from the node's `credentials`).
    # None when the kind passes none (kind: linux), then the platform defaults apply.
    username: str | None = None
    password: str | None = None


def lab_name(lab: str) -> str:
    """Accept either a lab name or the path to a .clab.yml file."""
    if lab.endswith((".yml", ".yaml")):
        return yaml.safe_load(Path(lab).read_text())["name"]
    return lab


def _docker(*args: str) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout


def _env(inspect: dict) -> dict[str, str]:
    return dict(e.split("=", 1) for e in inspect["Config"]["Env"] or [])


def _ip(inspect: dict) -> str:
    return next((n["IPAddress"] for n in inspect["NetworkSettings"]["Networks"].values() if n["IPAddress"]), "")


def _cmd_arg(inspect: dict, name: str) -> str | None:
    cmd = inspect["Config"]["Cmd"] or []
    m = re.search(rf"--{name}[ =](\S+)", " ".join(cmd))
    return m.group(1) if m else None


def _inspect_lab(lab: str) -> list[dict]:
    ids = _docker("ps", "-a", "-q", "--filter", f"label=containerlab={lab}").split()
    return json.loads(_docker("inspect", *ids)) if ids else []


def _node_name(inspect: dict) -> str:
    return inspect["Config"]["Labels"].get("clab-node-name", inspect["Name"].lstrip("/"))


def lab_health(lab: str) -> dict[str, str]:
    """Node name -> docker health ("healthy", "starting", ...), or the container state when it isn't running."""
    health = {}
    for inspect in _inspect_lab(lab):
        state = inspect["State"]
        health[_node_name(inspect)] = state.get("Health", {}).get("Status", "no healthcheck") if state["Running"] else state["Status"]
    return health


def lab_nodes(lab: str, names: Collection[str] | None = None) -> list[Node]:
    """The nodes of a running lab, or only those in `names`."""
    nodes = []
    for inspect in _inspect_lab(lab):
        if names is not None and _node_name(inspect) not in names:
            continue
        logs = subprocess.run(["docker", "logs", inspect["Id"]], capture_output=True, text=True)
        nodes.append(
            Node(
                container=inspect["Name"].lstrip("/"),
                name=_node_name(inspect),
                image=inspect["Config"]["Image"],
                ip=_ip(inspect),
                passthrough=_env(inspect).get("CLAB_MGMT_PASSTHROUGH", "").lower() == "true",
                startup_config=any(m["Destination"].startswith("/config/startup-config") for m in inspect["Mounts"]),
                logs=ANSI_ESCAPE.sub("", logs.stdout + logs.stderr),
                username=_cmd_arg(inspect, "username"),
                password=_cmd_arg(inspect, "password"),
            )
        )
    return sorted(nodes, key=lambda n: n.name)
