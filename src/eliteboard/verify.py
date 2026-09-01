"""Verify that every published posting actually still exists.

A job board's only real promise is that clicking a row leads somewhere useful.
Two failure modes break that promise, and they need different treatment:

**Hard dead** (404/410) - the requisition is gone. Safe to hide.

**Soft closed** - the page returns HTTP 200 and renders "no longer accepting
applications". This is the one that quietly rots a board, because every
status-code-based checker in this space reports it as healthy. It is also why
competing lists accumulate months-old listings that still look live.

Everything else - bot walls, timeouts, TLS errors - tells us nothing about the
posting, so it must never remove a row. We record what we saw and move on.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx

from .models import Job

log = logging.getLogger(__name__)

DEAD_CODES = {404, 410}
BLOCKED_CODES = {401, 403, 405, 429}
MAX_BODY = 400_000

# Deliberately narrow. A vague pattern here hides live jobs, which is a worse
# failure than showing a stale one, so each phrase is one an ATS actually emits.
CLOSED_PATTERNS = re.compile(
    r"no longer accepting applications"
    r"|we are no longer accepting"
    r"|this (?:job|position|role|posting) (?:has been|is) (?:closed|filled)"
    r"|this (?:job|position|role|posting) is no longer (?:available|open|active)"
    r"|the (?:job|position|posting) you(?:'| a)re looking for (?:is|has)"
    r"|this posting has expired"
    r"|job posting not found"
    r"|position has been filled",
    re.I,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36 eliteboard/1.0 "
        "(+https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(slots=True)
class LinkCheck:
    uid: str
    status: str  # ok | dead | closed | blocked | error
    detail: str = ""

    @property
    def hides_row(self) -> bool:
        """Only positive evidence of absence removes a posting from a board."""
        return self.status in {"dead", "closed"}


def _check_one(client: httpx.Client, job: Job) -> LinkCheck:
    try:
        resp = client.get(job.apply_url)
    except Exception as exc:  # noqa: BLE001 - a network failure is not a verdict
        return LinkCheck(job.uid, "error", type(exc).__name__)

    code = resp.status_code
    if code in DEAD_CODES:
        return LinkCheck(job.uid, "dead", str(code))
    if code in BLOCKED_CODES:
        return LinkCheck(job.uid, "blocked", str(code))
    if code >= 400:
        return LinkCheck(job.uid, "error", str(code))

    body = resp.text[:MAX_BODY] if resp.text else ""
    if match := CLOSED_PATTERNS.search(body):
        return LinkCheck(job.uid, "closed", match.group(0)[:60])
    return LinkCheck(job.uid, "ok", str(code))


def verify_links(
    jobs: list[Job], *, workers: int = 12, timeout: float = 20.0
) -> dict[str, LinkCheck]:
    """Probe every posting's apply URL. Never raises."""
    if not jobs:
        return {}
    log.info("verifying %d apply links", len(jobs))
    with httpx.Client(
        timeout=timeout, follow_redirects=True, headers=HEADERS
    ) as client, ThreadPoolExecutor(max_workers=workers) as pool:
        checks = list(pool.map(lambda j: _check_one(client, j), jobs))
    return {c.uid: c for c in checks}


def summarize(checks: dict[str, LinkCheck]) -> dict[str, int | float]:
    counts: dict[str, int] = {}
    for check in checks.values():
        counts[check.status] = counts.get(check.status, 0) + 1
    conclusive = counts.get("ok", 0) + counts.get("dead", 0) + counts.get("closed", 0)
    return {
        **counts,
        "checked": len(checks),
        "conclusive": conclusive,
        "resolving_pct": round(100 * counts.get("ok", 0) / max(conclusive, 1), 1),
    }
