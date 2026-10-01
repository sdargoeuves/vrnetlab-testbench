"""Results as markdown, on screen and in the logs.

  <log dir>/vrcheck.log   every check of every run, one line each, rotated (1 MB, 5 backups)
  <log dir>/runs.md       the summary table of each run, appended
  <log dir>/bench/        per bench run: containerlab output, full docker logs of the failed nodes
"""

import logging
from collections.abc import Collection
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .checks import Check, effective_creds
from .lab import Node
from .platforms import platform_for

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
WORDS = {True: "PASS", False: "FAIL", None: "SKIP"}
COLORS = {True: GREEN, False: RED, None: YELLOW}

DETAIL_LOG_BYTES = 1_000_000
DETAIL_LOG_BACKUPS = 5

Results = list[tuple[Node, list[Check]]]


def status(passed: bool | None, color: bool = False) -> str:
    return f"{COLORS[passed]}{WORDS[passed]}{RESET}" if color else WORDS[passed]


def node_passed(checks: list[Check]) -> bool:
    return all(c.passed is not False for c in checks)


def _yes_no(b: bool) -> str:
    return "yes" if b else "no"


def _creds(node: Node) -> tuple[str, str]:
    """(user, pwd) columns: default or custom. Passwords themselves are never shown or logged."""
    platform = platform_for(node.image)
    if platform is None:
        return "-", "-"
    creds = effective_creds(node, platform)
    return ("custom" if creds.custom_username else "default"), ("custom" if creds.custom_password else "default")


def _cell(text: str) -> str:
    return str(text).replace("\n", " ").replace("|", r"\|")


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    line = lambda cells: "| " + " | ".join(cells) + " |"
    return [line(header), line(["-" * len(h) for h in header]), *(line(r) for r in rows)]


def render_node(node: Node, checks: list[Check], color: bool = False) -> list[str]:
    user, pwd = _creds(node)
    info = f"`{node.image}` ip={node.ip} pt={_yes_no(node.passthrough)} cfg={_yes_no(node.startup_config)} user={user} pwd={pwd}"
    rows = [[status(c.passed, color), _cell(c.name), _cell(c.detail)] for c in checks]
    return [f"### {node.name}", "", info, "", *table(["result", "check", "detail"], rows)]


def render_summary(results: Results, color: bool = False, retried: Collection[str] = ()) -> list[str]:
    """`retried`: nodes re-checked after a first failure, marked "(retry)" so flaky nodes stay visible."""
    # user/pwd only when a node has custom credentials, so the other tables match RESULTS.md.
    show_creds = any("custom" in _creds(node) for node, _ in results)
    header = ["node", "image", "pt", "cfg", *(["user", "pwd"] if show_creds else []), "result"]
    rows = [
        [node.name, node.image, _yes_no(node.passthrough), _yes_no(node.startup_config),
         *(_creds(node) if show_creds else []),
         status(node_passed(checks), color) + (" (retry)" if node.name in retried else "")]
        for node, checks in results
    ]
    return table(header, rows)


def render_verdict(results: Results, color: bool = False) -> str:
    failed = [n.name for n, c in results if not node_passed(c)]
    if not failed:
        text = f"All {len(results)} nodes passed."
        return f"{GREEN}{text}{RESET}" if color else text
    text = f"{len(failed)}/{len(results)} failed: {' '.join(failed)}"
    return f"{RED}{text}{RESET}" if color else f"**{text}**"


def detail_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("vrcheck")
    log.setLevel(logging.INFO)
    log.propagate = False
    if not log.handlers:
        handler = RotatingFileHandler(
            log_dir / "vrcheck.log", maxBytes=DETAIL_LOG_BYTES, backupCount=DETAIL_LOG_BACKUPS, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        log.addHandler(handler)
    return log


def log_checks(log_dir: Path, lab: str, options: str, results: Results) -> None:
    """Every check to vrcheck.log."""
    log = detail_logger(log_dir)
    log.info("%s run: %d node(s)%s", lab, len(results), f" ({options})" if options else "")
    for node, checks in results:
        user, pwd = _creds(node)
        log.info(
            "%s %s node: image=%s ip=%s pt=%s cfg=%s user=%s pwd=%s", lab, node.name, node.image, node.ip,
            _yes_no(node.passthrough), _yes_no(node.startup_config), user, pwd,
        )
        for c in checks:
            log.info("%s %s %s %-40s %s", lab, node.name, status(c.passed), c.name, c.detail.replace("\n", " "))
    log.info("%s result: %s", lab, render_verdict(results).strip("*"))


def append_run(log_dir: Path, title: str, lines: list[str]) -> None:
    """A `## <date> <title>` section in runs.md."""
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / "runs.md", "a", encoding="utf-8") as f:
        f.write("\n".join([f"## {datetime.now():%Y-%m-%d %H:%M} {title}", "", *lines, "", ""]))


def save(log_dir: Path, lab: str, options: str, results: Results, retried: Collection[str] = ()) -> None:
    """Every check to vrcheck.log, the summary table to runs.md."""
    log_checks(log_dir, lab, options, results)
    title = lab + (f" ({options})" if options else "")
    append_run(log_dir, title, [*render_summary(results, retried=retried), "", render_verdict(results)])
