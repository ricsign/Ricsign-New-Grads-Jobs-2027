"""Adapter protocol and shared HTTP plumbing.

Every adapter obeys three rules:

1. It never raises into the pipeline. A board that 500s must not take down a
   refresh across 130 other companies.
2. It reports an *empty* board distinctly from a *failed* one. Several boards
   return HTTP 200 with zero postings (``ashby:deel``, ``ashby:wiz``); a naive
   200-check accepts those and scrapes nothing forever.
3. It emits ``RawPosting`` and makes no judgment about the role.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from dateutil import parser as dateparser

from ..models import RawPosting
from ..registry import Company

log = logging.getLogger(__name__)

USER_AGENT = (
    "eliteboard/1.0 (+https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027) "
    "job-board aggregator; contact via GitHub issues"
)
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=15.0)
MAX_ATTEMPTS = 3
RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass(slots=True)
class FetchResult:
    """Per-company outcome of one refresh. Feeds the published health report."""

    company: Company
    postings: list[RawPosting] = field(default_factory=list)
    error: str | None = None
    status: str = "ok"  # ok | empty | error
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None


class Adapter(Protocol):
    source: str

    def fetch(self, client: httpx.Client, company: Company) -> list[RawPosting]: ...


def make_client() -> httpx.Client:
    return httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Issue a request with bounded retries, returning parsed JSON.

    Retries only on transient status codes. A 404 means the token is wrong and
    retrying it three times just wastes CI minutes.
    """
    last: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.request(method, url, json=json_body, params=params)
            if resp.status_code in RETRY_STATUS and attempt < MAX_ATTEMPTS:
                raise httpx.HTTPStatusError(
                    f"retryable {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            last = exc
            if attempt == MAX_ATTEMPTS:
                break
            log.debug("retry %s/%s for %s: %s", attempt, MAX_ATTEMPTS, url, exc)
    raise RuntimeError(f"{method} {url} failed after {MAX_ATTEMPTS} attempts: {last}")


def parse_dt(value: Any) -> datetime | None:
    """Best-effort timestamp parsing across wildly inconsistent vendor formats.

    Handles ISO 8601, epoch seconds, epoch milliseconds, and Workday's
    relative strings ("Posted 3 Days Ago"), which carry no absolute date at all
    and therefore return None rather than a fabricated one.
    """
    if value in (None, "", 0):
        return None
    if isinstance(value, int | float):
        seconds = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower().startswith("posted"):
            return None
        try:
            dt = dateparser.parse(text)
        except (ValueError, OverflowError, TypeError):
            return None
        if dt is None:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return None


def dedupe_locations(values: list[str | None]) -> list[str]:
    """Order-preserving dedupe that collapses different spellings of one office.

    Exact-match dedupe is not enough. Greenhouse returns `location.name` *and*
    an `offices` list for the same role, so one Chicago job arrives as both
    "Chicago, IL" and "Chicago", and one Anduril job as both
    "Costa Mesa, California, United States" and "Costa Mesa, CA (OC-00)".
    Rendering all of those makes the Location column unreadable.

    Two passes: collapse by canonical city+state key keeping the most
    informative spelling, then drop any remaining entry that is a substring of
    another.
    """
    from ..locations import canonical_key

    # Greenhouse packs several offices into one string
    # ("Austin, Texas; Dallas, Texas; Houston, Texas"). Split first, or the
    # whole run is treated as a single unmatchable location and the column
    # becomes an unreadable wall of text.
    expanded: list[str] = []
    for value in values:
        if not value:
            continue
        for part in str(value).split(";"):
            part = " ".join(part.split())
            if part:
                expanded.append(part)

    best: dict[str, str] = {}
    order: list[str] = []
    for value in expanded:
        text = value
        if not text:
            continue
        key = canonical_key(text)
        if key not in best:
            best[key] = text
            order.append(key)
        elif len(text) > len(best[key]):
            best[key] = text

    kept: list[str] = []
    for key in order:
        text = best[key]
        low = text.casefold()
        if any(low in other.casefold() for other in kept):
            continue
        kept = [k for k in kept if k.casefold() not in low]
        kept.append(text)
    return kept
