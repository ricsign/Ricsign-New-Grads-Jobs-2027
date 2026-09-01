"""Greenhouse job boards - https://boards-api.greenhouse.io

The single most common ATS among elite employers: 79 of our 131 fetchable
companies, including Anthropic, Databricks, Stripe, SpaceX and most quant firms.
"""

from __future__ import annotations

from ..models import RawPosting, clean_text
from ..registry import Company
from .base import dedupe_locations, parse_dt, request_json

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseAdapter:
    source = "greenhouse"

    def fetch(self, client, company: Company) -> list[RawPosting]:
        payload = request_json(
            client, "GET", API.format(token=company.token), params={"content": "true"}
        )
        return [self._parse(company, job) for job in payload.get("jobs", [])]

    def _parse(self, company: Company, job: dict) -> RawPosting:
        offices = [o.get("name") for o in job.get("offices", []) or []]
        primary = (job.get("location") or {}).get("name")
        departments = [d.get("name") for d in job.get("departments", []) or []]

        # Greenhouse exposes `first_published` on most boards. Prefer it: it is
        # the real post date, whereas `updated_at` bumps on any edit and would
        # make an eight-month-old requisition look new.
        posted = parse_dt(job.get("first_published")) or parse_dt(job.get("updated_at"))

        return RawPosting(
            company_slug=company.slug,
            company_name=company.name,
            source=self.source,
            external_id=str(job.get("id")),
            title=clean_text(job.get("title")),
            apply_url=job.get("absolute_url", ""),
            locations=dedupe_locations([primary, *offices]),
            posted_at=posted,
            updated_at=parse_dt(job.get("updated_at")),
            description=clean_text(job.get("content")),
            department=next((d for d in departments if d), None),
        )
