# `vrnetlab` Test Bench

Minimal containerlab topologies for testing vrnetlab images.

> [!NOTE]
> Vendor images are not included.
> Build them yourself with [srl-labs/vrnetlab](https://github.com/srl-labs/vrnetlab), from images you are licensed to use.

## Why

vrnetlab runs vendor VMs inside containers, and each platform handles the basics its own way.
A new image version or a vrnetlab change can quietly break one feature on one platform:
the VM boots, but ignores its startup-config or keeps the default password.

## What it tests

One node per feature combination, for each platform and version:

| Feature | Checked in the boot log | Checked on the device (SSH) |
| --- | --- | --- |
| Boot | `Startup complete` logged | login works |
| Mgmt passthrough | mgmt mode matches the container env | VM has the container's IP (or `10.0.0.15` without) |
| Startup-config | push logged by vrnetlab | test changes present (or absent without a config) |
| Credentials | - | custom password works, default is refused |

What each node should do comes from its container settings, not from its name.

## What's in the repo

| Part | What it is |
| --- | --- |
| `topology-*.clab.yml` | the test matrix: one plain containerlab file per platform, no netlab needed |
| `configs/` | the startup-config snippets the `-cfg` nodes boot with |
| `vrcheck/` | the checker: `vrcheck <lab>` checks a lab you deployed, `vrcheck bench` runs the full cycle |

## Quick start

```bash
uv sync                                        # once: creates .venv/
uv run vrcheck bench topology-aoscx.clab.yml   # deploy, wait for boot, check every node, destroy
```

Results are printed as markdown tables and saved to `logs/runs.md`.

## Using it

### Test matrix

Each version gets 4 or 5 nodes (depending on tests available), connected in a ring:

| Suffix   | Mgmt passthrough | Startup-config |
|----------|------------------|----------------|
| `-base`  | no               | no             |
| `-pt`    | yes              | no             |
| `-cfg`   | no               | yes (bind)     |
| `-ptcfg` | yes              | yes (bind)     |
| `-creds` | no               | no             |

The variants are defined once as `groups` at the top of each file. A node only picks a `group` and an `image`.
containerlab merges `env` and `binds` from `defaults -> kinds -> groups -> node`, so the platform env
(e.g. `QEMU_CPU`) set in `defaults` still applies to every node.

```text
topology-exos.clab.yml    Extreme EXOS  32.6.3.126, 32.7.2.19       (kind: linux)
topology-voss.clab.yml    Extreme VOSS  8.10.1.0, 9.3.1.0, 9.4.0.0  (kind: linux)
topology-aoscx.clab.yml   Aruba AOS-CX  10.16.1060                  (kind: aruba_aoscx)
topology-vsrx.clab.yml    Juniper vSRX  22.3R1.11                   (kind: juniper_vsrx)
topology-asav.clab.yml    Cisco ASAv    9.18.1, 9.24.1 (9.9.2 off)  (kind: cisco_asav)
configs/                  startup-config snippets (bind-mounted by the *-cfg groups)
vrcheck/                  checker for a deployed lab (see "Checking a lab")
```

Bind paths are relative to the topology file, not your current directory.

### Running the whole bench

`vrcheck bench` does the full cycle for each topology, one after the other:

1. `containerlab deploy -t <topology>`
2. wait until every node is healthy: vrnetlab's docker healthcheck turns `healthy` once the VM has booted
   (`--timeout`, default 1800 s; a node that never gets there fails its checks, it doesn't stop the bench)
3. check all nodes, then re-check the failed ones once after `--retry-wait` (default 60 s, `0` = no retry).
   A node that only passes the second time shows as `PASS (retry)`, so flaky images stay visible
4. `containerlab destroy --cleanup -t <topology>`, also after an error or Ctrl-C (`--keep-on-fail` keeps a failed lab to debug it)

```bash
uv run vrcheck bench --dry-run                                  # the plan: topologies, labs, node counts
uv run vrcheck bench                                            # every topology-*.clab.yml
uv run vrcheck bench topology-exos.clab.yml topology-vsrx.clab.yml
uv run vrcheck bench --logs-only --retry-wait 0                 # quick pass: boot + docker logs only
```

A lab that is already running is never touched: that topology is reported as `ERROR` and the bench moves on.
Ctrl-C destroys the current lab, then prints the results of the topologies done so far.

containerlab is run without sudo. That works when the binary is setuid and your user is in the `clab_admins`
group (the default install). Otherwise add `--sudo`, and set up sudoers so it doesn't prompt.

A full bench takes a while (each topology boots all its VMs at once, vSRX and ASAv are the slowest), so start it and come back later.

### Checking a lab you deployed

To check a lab you deployed yourself, without the deploy/destroy cycle:

```bash
uv run vrcheck topology-exos.clab.yml     # topology file, or the lab name: uv run vrcheck vrt-exos
uv run vrcheck vrt-exos -n x327  # only nodes whose name contains "x327"
uv run vrcheck vrt-exos --logs-only
```

For each node, vrcheck reads the expected result from the container itself, not from the node name:

- passthrough expected: `CLAB_MGMT_PASSTHROUGH=true` on the container
- startup-config expected: a file mounted on `/config/startup-config.*`
- credentials: the `--username/--password` containerlab passed to vrnetlab, else the platform defaults

| Check | Source | Pass when |
| --- | --- | --- |
| `boot` | docker logs | `Startup complete in: ...` is logged |
| `log: mgmt mode` | docker logs | `Transparent mgmt interface: Enabled/Disabled` matches the env |
| `log: startup-config` | docker logs | the platform's push message is logged (only nodes with a startup-config) |
| `device: custom username` | topology | only when the node sets a username the platform can't change (vSRX): always FAIL |
| `device: ssh as <user>` | SSH | login works with the node's credentials |
| `device: default password rejected` | SSH | only with a custom password: the platform default no longer works |
| `device: mgmt IP` | SSH | VM mgmt IP = container eth0 IP with passthrough, `10.0.0.15` without |
| `device: <marker>` | SSH | the test snippet's changes are present with a startup-config, absent without |

The mgmt IP inside the VM is the proof for passthrough. `10.0.0.15` is the qemu user-net address that
vrnetlab forwards port 22 etc. to. Don't use the SSH source address in `show session`: it's `172.20.20.1` in both modes.

VOSS without passthrough loads the startup-config over TFTP and vrnetlab logs nothing about it, so
`log: startup-config` is SKIP there. The device checks still prove whether it was applied.

All `configs/*-test.*` snippets make the same changes (VLAN/subinterface 123 with 1.2.3.4/24, SNMP contact `netlab-test`),
so each platform only needs to know how to read them back.

Supported platforms: EXOS, AOS-CX, VOSS, vSRX, ASAv (`vrcheck/platforms/`).

### Output and logs

The output is markdown: one `| result | check | detail |` table per node, then a summary table
with the `RESULTS.md` columns (`node | image | pt | cfg | result`). When a node has custom credentials,
the summary also gets `user` and `pwd` columns (`default` / `custom`). Password values are never printed or logged.
Colors only show on a terminal, so `uv run vrcheck vrt-exos > out.md` gives plain markdown.

Each run is also saved to `logs/` (`--log-dir` to change it, `--no-log` to skip):

- `logs/runs.md`: the summary table of every run, appended under a `## <date> <lab>` heading
- `logs/vrcheck.log`: every check of every run, one line each (`<time> <lab> <node> PASS|FAIL|SKIP <check> <detail>`),
  rotated at 1 MB with 5 backups (`vrcheck.log.1` ... `.5`)

Each `vrcheck bench` run also gets `logs/bench/<date>-<time>/` (the last 10 are kept, `--keep-runs`):

- `<lab>-containerlab.log`: deploy/destroy output
- `<lab>-<node>.docker.log`: the full `docker logs` of each failed node, since the lab is gone once the bench moves on

### Credentials

containerlab (0.79) passes a node's `credentials` to vrnetlab as `--username/--password`, for native kinds:

```yaml
nodes:
  r1:
    kind: juniper_vsrx
    credentials:
      username: admin
      password: "New-Passw0rd"
```

The `-creds` groups in `topology-vsrx.clab.yml` and `topology-asav.clab.yml` do exactly this.
vrcheck logs in with those credentials, and checks that the platform's default password is refused.
`kind: linux` nodes (EXOS, VOSS) get no `--username/--password`, so vrnetlab's defaults apply (`vrnetlab` / `VR-netlab9`).

- vSRX (default `admin` / `admin@123`): the kind builds the arguments from `credentials` only, so `env: PASSWORD` has no effect.
  vrnetlab only uses the password (the user stays `admin`), and only with the `vsrx_user_password` fix
  (`{CRYPT_PSWD}` in `init.conf`). Without it, `init.conf` hardcodes `admin@123`.
  A custom `username` on vSRX gets the `device: custom username` FAIL, and vrcheck logs in as `admin`.
- ASAv (default `admin` / `CiscoAsa1!`): the kind builds the arguments from the `USERNAME`/`PASSWORD` env, which `credentials` fills.
  vrnetlab uses them for the local user and the enable password.

### Deploying and debugging by hand

Run from the repo root. Prefix with `sudo` if your user is not in the `clab_admins` group.

```bash
# Deploy the whole file
containerlab deploy -t topology-exos.clab.yml

# Deploy only some nodes (links to filtered-out nodes are skipped)
containerlab deploy -t topology-exos.clab.yml --node-filter x327-base,x327-ptcfg

# Redeploy from scratch (destroys the existing lab first)
containerlab deploy -t topology-exos.clab.yml --reconfigure

# Show nodes, state and mgmt IPs
containerlab inspect -t topology-exos.clab.yml

# Tear down and delete the lab directory (clab-vrt-exos/)
containerlab destroy -t topology-exos.clab.yml --cleanup

# List every running clab lab on the host (netlab labs included)
containerlab inspect --all
```

#### Watching and accessing nodes

Containers are named `clab-<lab name>-<node>`, e.g. `clab-vrt-exos-x326-pt`.
containerlab also adds these names to `/etc/hosts`.

```bash
# Follow the vrnetlab boot log (shows "Startup complete" when the VM is ready)
docker logs -f clab-vrt-exos-x326-pt

# SSH (EXOS/VOSS: vrnetlab / VR-netlab9, AOS-CX: admin / admin)
ssh vrnetlab@clab-vrt-exos-x326-pt

# Serial console of the VM (exit with Ctrl-] then "quit")
docker exec -it clab-vrt-exos-x326-pt telnet 127.0.0.1 5000

# Check which mode a node booted in (look for the passthrough / startup-config lines)
docker logs clab-vrt-exos-x326-ptcfg 2>&1 | grep -E "Transparent mgmt|Writing lines from|tftp get|Startup complete"
```

## Extending it

### Adding a version

Copy a block of nodes and its links, then change the image tag and the node-name prefix.
Each version is its own ring (eth1 -> next node's eth2). Comment out a version (nodes + links) to skip it.

### Adding a platform

1. Add a `topology-<platform>.clab.yml` with the same groups, and a `configs/<platform>-test.*` snippet
   making the same changes as the others.
2. Create `vrcheck/platforms/<platform>.py`, using `exos.py` as the model:
   - `image`: a substring of the docker image name (`extreme_voss`)
   - `netmiko_type`: the netmiko device type
   - `username` / `password` if they differ from vrnetlab's `vrnetlab` / `VR-netlab9`
     (native containerlab kinds such as `aruba_aoscx` use `admin` / `admin`)
   - `custom_username = False` if vrnetlab ignores `--username` on this platform (as on vSRX)
   - `mgmt_ip()`: run a show command and return the mgmt IPv4 address
   - `startup_config_markers()`: return one `Marker` per change the test snippet makes
   - `startup_config_log` / `hostfwd_mgmt_ip` if the defaults in `base.py` don't fit
3. Add an instance to `PLATFORMS` in `vrcheck/platforms/__init__.py`.

Until then, nodes of that platform get the log checks and the device checks are marked SKIP.

`paramiko` is pinned below 4: version 4 dropped `ssh-rsa` host keys, the only kind EXOS 32 offers.

## License

MIT, see [LICENSE](LICENSE).
