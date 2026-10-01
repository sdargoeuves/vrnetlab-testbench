"""vrcheck: verify every node of a deployed vrnetlab test lab.

  uv run vrcheck topology-exos.clab.yml  # topology file or lab name (vrt-exos)
  uv run vrcheck vrt-exos -n x327        # only nodes whose name contains "x327"
  uv run vrcheck vrt-exos --logs-only    # skip SSH, only check docker logs
  uv run vrcheck bench                   # deploy, check and destroy every topology (see: vrcheck bench -h)

Output is markdown. Each run is also saved to logs/: every check in vrcheck.log (rotated),
the summary table in runs.md.
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import bench, report
from .checks import check_node
from .lab import lab_name, lab_nodes


def topology_for(lab_arg: str, lab: str) -> str | None:
    """The topology file of a lab: the argument itself, or the topology-*.clab.yml whose name matches."""
    if lab_arg.endswith((".yml", ".yaml")):
        return lab_arg
    return next((str(t) for t in sorted(Path(".").glob("topology-*.clab.yml")) if lab_name(str(t)) == lab), None)


def not_deployed(args: argparse.Namespace, lab: str) -> None:
    """Offer to run the bench on it (deploy, check, destroy), else say how to deploy and destroy it."""
    topology = topology_for(args.lab, lab)
    print(f"Lab '{lab}' is not deployed: vrcheck only checks a running lab.")
    if topology and sys.stdin.isatty():
        answer = input("Deploy it, check it and destroy it once done (same as vrcheck bench)? [y/N] ")
        if answer.strip().lower() in ("y", "yes"):
            if args.node:
                print(f"Note: the bench checks every node, -n {args.node} is ignored.")
            bench_args = [topology, "--workers", str(args.workers), "--log-dir", str(args.log_dir)]
            bench.main(bench_args + (["--logs-only"] if args.logs_only else []))
    topology = topology or "<topology file>"
    sys.exit(
        "To do it yourself:\n"
        f"  deploy:   containerlab deploy -t {topology}\n"
        f"  check:    uv run vrcheck {args.lab}    (once the nodes are healthy in docker ps)\n"
        f"  destroy:  containerlab destroy -c -t {topology}\n"
        f"Or all in one go:  uv run vrcheck bench {topology}"
    )


def main() -> None:
    if sys.argv[1:2] == ["bench"]:
        bench.main(sys.argv[2:])
        return

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lab", help="lab name (vrt-exos) or topology file (topology-exos.clab.yml)")
    parser.add_argument("-n", "--node", help="only check nodes whose name contains this string")
    parser.add_argument("--logs-only", action="store_true", help="skip the SSH checks")
    parser.add_argument("-w", "--workers", type=int, default=8, help="nodes checked in parallel (default: 8)")
    parser.add_argument("--log-dir", type=Path, default=Path("logs"), help="where to save the results (default: logs/)")
    parser.add_argument("--no-log", action="store_true", help="don't save the results")
    args = parser.parse_args()

    lab = lab_name(args.lab)
    all_nodes = lab_nodes(lab)
    if not all_nodes:
        not_deployed(args, lab)
    nodes = [n for n in all_nodes if not args.node or args.node in n.name]
    if not nodes:
        sys.exit(f"No node of lab '{lab}' has '{args.node}' in its name: {' '.join(n.name for n in all_nodes)}")

    print(f"Checking {len(nodes)} node(s) of lab {lab}...")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        all_checks = list(pool.map(lambda n: check_node(n, device=not args.logs_only), nodes))
    results = list(zip(nodes, all_checks))

    color = sys.stdout.isatty()
    for node, checks in results:
        print("\n" + "\n".join(report.render_node(node, checks, color)))
    print("\n## Summary\n")
    print("\n".join(report.render_summary(results, color)))
    print("\n" + report.render_verdict(results, color))

    if not args.no_log:
        options = ", ".join(([f"-n {args.node}"] if args.node else []) + (["logs-only"] if args.logs_only else []))
        report.save(args.log_dir, lab, options, results)
        print(f"\nSaved to {args.log_dir}/runs.md and {args.log_dir}/vrcheck.log")

    sys.exit(0 if all(report.node_passed(c) for _, c in results) else 1)


if __name__ == "__main__":
    main()
