"""vrcheck bench: deploy, check and destroy each topology in turn.

  uv run vrcheck bench                          # every topology-*.clab.yml in the current directory
  uv run vrcheck bench topology-exos.clab.yml   # only these topologies
  uv run vrcheck bench --dry-run                # show the plan, deploy nothing

For each topology:
  1. containerlab deploy
  2. wait until every node is healthy (vrnetlab's docker healthcheck turns healthy once the VM has booted)
  3. check all nodes; re-check the failed ones once after --retry-wait, marked "(retry)" in the results
  4. containerlab destroy --cleanup, also after an error or Ctrl-C (unless --keep-on-fail)

A lab that is already running is left alone and reported as ERROR.
containerlab runs without sudo (setuid binary + clab_admins group), --sudo prefixes it.
"""

import argparse
import shutil
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from . import report
from .checks import check_node
from .lab import ANSI_ESCAPE, lab_health, lab_name, lab_nodes

POLL_SECONDS = 15
READY = ("healthy", "no healthcheck")  # nodes without a healthcheck (plain linux) count as ready once running
DEAD = ("exited", "dead")


@dataclass
class TopologyRun:
    topology: Path
    lab: str
    results: report.Results = field(default_factory=list)
    retried: set[str] = field(default_factory=set)
    error: str = ""  # deploy failed, lab already running...
    boot_seconds: float | None = None  # deploy -> all nodes healthy, None if they never were
    total_seconds: float = 0

    @property
    def failed(self) -> list[str]:
        return [n.name for n, c in self.results if not report.node_passed(c)]

    @property
    def passed(self) -> bool:
        return not self.error and not self.failed


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}m{seconds:02d}s"


class Bench:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.log = report.detail_logger(args.log_dir)
        self.run_dir = args.log_dir / "bench" / f"{datetime.now():%Y%m%d-%H%M%S}"
        self.color = sys.stdout.isatty()

    def say(self, message: str) -> None:
        """To the screen and to vrcheck.log."""
        print(message, flush=True)
        if message.strip():
            self.log.info("bench %s", message.strip())

    def containerlab(self, lab: str, *cmd: str, no_interrupt: bool = False) -> bool:
        """Run containerlab, its output goes to <run dir>/<lab>-containerlab.log.

        Its own session, so a Ctrl-C in the terminal only reaches vrcheck.
        no_interrupt: ignore Ctrl-C until it's done (destroy must not stop halfway).
        """
        argv = (["sudo"] if self.args.sudo else []) + ["containerlab", *cmd]
        previous = signal.signal(signal.SIGINT, signal.SIG_IGN) if no_interrupt else None
        try:
            out = subprocess.run(argv, capture_output=True, text=True, start_new_session=True)
        finally:
            if no_interrupt:
                signal.signal(signal.SIGINT, previous)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with open(self.run_dir / f"{lab}-containerlab.log", "a", encoding="utf-8") as f:
            f.write(f"$ {' '.join(argv)}\n{ANSI_ESCAPE.sub('', out.stdout + out.stderr)}\n")
        return out.returncode == 0

    def wait_healthy(self, lab: str) -> bool:
        start = time.monotonic()
        last = None
        while True:
            health = lab_health(lab)
            ready = sum(status in READY for status in health.values())
            elapsed = time.monotonic() - start
            if ready != last:
                self.say(f"  {ready}/{len(health)} healthy after {_duration(elapsed)}")
                last = ready
            if health and ready == len(health):
                return True
            dead = [name for name, status in health.items() if status in DEAD]
            if dead:
                self.say(f"  container(s) stopped: {' '.join(dead)}")
                return False
            if elapsed > self.args.timeout:
                waiting = [f"{name} ({status})" for name, status in health.items() if status not in READY]
                self.say(f"  timeout after {_duration(elapsed)}, not healthy: {' '.join(waiting)}")
                return False
            time.sleep(POLL_SECONDS)

    def check(self, lab: str, names: list[str] | None = None) -> report.Results:
        nodes = lab_nodes(lab, names)
        with ThreadPoolExecutor(max_workers=self.args.workers) as pool:
            all_checks = list(pool.map(lambda n: check_node(n, device=not self.args.logs_only), nodes))
        return list(zip(nodes, all_checks))

    def run_topology(self, topology: Path) -> TopologyRun:
        run = TopologyRun(topology, lab_name(str(topology)))
        lab = run.lab
        start = time.monotonic()
        self.say(f"\n## {topology.name} ({lab})\n")
        if lab_health(lab):
            run.error = "lab already running, destroy it first"
            self.say(f"  {run.error}")
            return run

        try:
            self.say("  deploying...")
            if not self.containerlab(lab, "deploy", "-t", str(topology)):
                run.error = f"deploy failed, see {self.run_dir}/{lab}-containerlab.log"
                self.say(f"  {run.error}")
                return run
            if self.wait_healthy(lab):
                run.boot_seconds = time.monotonic() - start

            self.say("  checking...")
            run.results = self.check(lab)
            if run.failed and self.args.retry_wait:
                first = run.failed
                self.say(f"  {len(first)} failed ({' '.join(first)}), re-checking in {self.args.retry_wait}s")
                report.log_checks(self.args.log_dir, lab, "bench, first try", [r for r in run.results if r[0].name in first])
                time.sleep(self.args.retry_wait)
                again = {node.name: (node, checks) for node, checks in self.check(lab, first)}
                run.results = [again.get(node.name, (node, checks)) for node, checks in run.results]
                run.retried = set(first)

            self.report(run)
        finally:
            if self.args.keep_on_fail and not run.passed:
                self.say(f"  kept running (--keep-on-fail): containerlab destroy -c -t {topology}")
            else:
                self.say("  destroying...")
                if not self.containerlab(lab, "destroy", "--cleanup", "-t", str(topology), no_interrupt=True):
                    self.say(f"  destroy failed, see {self.run_dir}/{lab}-containerlab.log")
            run.total_seconds = time.monotonic() - start
        return run

    def report(self, run: TopologyRun) -> None:
        """Failed nodes in full, then the summary table. Every check goes to vrcheck.log."""
        failed = set(run.failed)
        for node, checks in run.results:
            if node.name in failed:
                print("\n" + "\n".join(report.render_node(node, checks, self.color)))
                self.run_dir.mkdir(parents=True, exist_ok=True)
                (self.run_dir / f"{run.lab}-{node.name}.docker.log").write_text(node.logs, encoding="utf-8")
        print("\n" + "\n".join(report.render_summary(run.results, self.color, run.retried)))
        print("\n" + report.render_verdict(run.results, self.color))
        report.save(self.args.log_dir, run.lab, "bench", run.results, run.retried)

    def prune(self) -> None:
        """Keep the last --keep-runs bench directories."""
        runs = sorted(p for p in (self.args.log_dir / "bench").glob("*") if p.is_dir())
        for old in runs[: -self.args.keep_runs]:
            shutil.rmtree(old)


def render_bench(runs: list[TopologyRun], color: bool = False) -> list[str]:
    rows = []
    for run in runs:
        result = "ERROR" if run.error else report.status(run.passed, color)
        rows.append([
            run.topology.name, run.lab, str(len(run.results)), str(len(run.failed)),
            " ".join(sorted(run.retried)) or "-", _duration(run.boot_seconds), _duration(run.total_seconds), result,
        ])
    return report.table(["topology", "lab", "nodes", "failed", "retried", "boot", "time", "result"], rows)


def dry_run(topologies: list[Path]) -> None:
    rows = []
    for topology in topologies:
        topo = yaml.safe_load(topology.read_text())
        nodes = topo.get("topology", {}).get("nodes", {})
        state = "RUNNING, would be skipped" if lab_health(topo["name"]) else "deploy"
        rows.append([topology.name, topo["name"], str(len(nodes)), state])
    print("\n".join(report.table(["topology", "lab", "nodes", "action"], rows)))


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="vrcheck bench", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("topologies", nargs="*", type=Path, help="topology files (default: topology-*.clab.yml)")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds to wait for all nodes to be healthy (default: 1800)")
    parser.add_argument("--retry-wait", type=int, default=60, help="seconds before re-checking failed nodes, 0 = no retry (default: 60)")
    parser.add_argument("--keep-on-fail", action="store_true", help="don't destroy a lab that failed, to debug it")
    parser.add_argument("--sudo", action="store_true", help="run containerlab with sudo")
    parser.add_argument("--logs-only", action="store_true", help="skip the SSH checks")
    parser.add_argument("-w", "--workers", type=int, default=8, help="nodes checked in parallel (default: 8)")
    parser.add_argument("--log-dir", type=Path, default=Path("logs"), help="where to save the results (default: logs/)")
    parser.add_argument("--keep-runs", type=int, default=10, help="bench directories kept in <log dir>/bench (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="show what would run, deploy nothing")
    args = parser.parse_args(argv)

    topologies = args.topologies or sorted(Path(".").glob("topology-*.clab.yml"))
    if not topologies:
        sys.exit("No topology-*.clab.yml in the current directory")
    missing = [str(t) for t in topologies if not t.is_file()]
    if missing:
        sys.exit(f"Not found: {' '.join(missing)}")
    if args.dry_run:
        dry_run(topologies)
        return
    if not shutil.which("containerlab"):
        sys.exit("containerlab not found in PATH")

    bench = Bench(args)
    bench.say(f"# vrcheck bench: {len(topologies)} topolog{'y' if len(topologies) == 1 else 'ies'}, logs in {bench.run_dir}")
    runs = []
    try:
        for topology in topologies:
            runs.append(bench.run_topology(topology))
    except KeyboardInterrupt:  # the current lab is destroyed by then, the ones done so far are still reported
        bench.say(f"\ninterrupted after {len(runs)}/{len(topologies)} topologies")
    if runs:
        print("\n## Bench\n")
        print("\n".join(render_bench(runs, bench.color)))
        report.append_run(args.log_dir, "bench", render_bench(runs))
    bench.prune()
    sys.exit(0 if all(run.passed for run in runs) and len(runs) == len(topologies) else 1)
