"""Concurrent refresh across every fetchable board, with a published health report.

Design constraint: one bad board must never fail a refresh. With 131 boards and
a 6-hourly schedule, transient failures are certain, so the orchestrator
isolates every company and reports per-company status instead of aborting.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .adapters import FetchResult, get_adapter, make_client
from .models import RawPosting
from .registry import Company, fetchable

log = logging.getLogger(__name__)

DEFAULT_WORKERS = 12


@dataclass(slots=True)
class RefreshReport:
    """What happened during a refresh. Published as data/v1/health.json."""

    results: list[FetchResult]

    @property
    def ok(self) -> list[FetchResult]:
        return [r for r in self.results if r.status == "ok"]

    @property
    def empty(self) -> list[FetchResult]:
        return [r for r in self.results if r.status == "empty"]

    @property
    def failed(self) -> list[FetchResult]:
        return [r for r in self.results if r.status == "error"]

    @property
    def postings(self) -> list[RawPosting]:
        return [p for r in self.results for p in r.postings]

    @property
    def success_rate(self) -> float:
        return len(self.ok) / len(self.results) if self.results else 0.0

    def to_dict(self) -> dict:
        return {
            "boards_attempted": len(self.results),
            "boards_ok": len(self.ok),
            "boards_empty": len(self.empty),
            "boards_failed": len(self.failed),
            "success_rate": round(self.success_rate, 4),
            "postings_fetched": len(self.postings),
            "by_source": dict(
                Counter(r.company.ats for r in self.results if r.status == "ok")
            ),
            "failures": [
                {"company": r.company.name, "ats": r.company.ats, "error": r.error}
                for r in self.failed
            ],
            "empty_boards": [
                {"company": r.company.name, "ats": r.company.ats, "token": r.company.token}
                for r in self.empty
            ],
        }


def fetch_company(company: Company, client) -> FetchResult:
    """Fetch one board. Never raises."""
    started = time.monotonic()
    try:
        postings = get_adapter(company.ats).fetch(client, company)
    except Exception as exc:  # noqa: BLE001 - isolation is the whole point
        log.warning("%s (%s): %s", company.name, company.ats, exc)
        return FetchResult(
            company=company,
            error=f"{type(exc).__name__}: {exc}"[:300],
            status="error",
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    # A board that answers 200 with zero postings is not a success. Two known
    # live-but-empty Ashby boards would otherwise look healthy forever.
    status = "ok" if postings else "empty"
    return FetchResult(
        company=company,
        postings=postings,
        status=status,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )


def fetch_all(
    companies: list[Company], *, workers: int = DEFAULT_WORKERS
) -> RefreshReport:
    targets = fetchable(companies)
    log.info("refreshing %d boards with %d workers", len(targets), workers)

    results: list[FetchResult] = []
    with make_client() as client, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_company, c, client): c for c in targets}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            log.info(
                "  %-28s %-11s %-6s %4d postings  %5dms",
                result.company.name[:28],
                result.company.ats,
                result.status,
                len(result.postings),
                result.elapsed_ms,
            )

    results.sort(key=lambda r: (r.company.tier, r.company.name))
    return RefreshReport(results=results)
