"""Ashby job boards - https://api.ashbyhq.com/posting-api

Dominant among frontier AI labs: OpenAI, Cursor, Cognition, Perplexity,
Thinking Machines, Reflection, Sierra, Harvey and Physical Intelligence all
publish here. Ashby also returns structured compensation on many postings,
which we keep - it is far more trustworthy than a scraped salary guess.
"""

from __future__ import annotations

from typing import Any

from ..models import RawPosting, clean_text
from ..registry import Company
from .base import dedupe_locations, parse_dt, request_json

API = "https://api.ashbyhq.com/posting-api/job-board/{token}"


class AshbyAdapter:
    source = "ashby"

    def fetch(self, client, company: Company) -> list[RawPosting]:
        payload = request_json(
            client,
            "GET",
            API.format(token=company.token),
            params={"includeCompensation": "true"},
        )
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        return [self._parse(company, j) for j in jobs if j.get("isListed", True)]

    def _parse(self, company: Company, job: dict) -> RawPosting:
        secondary = [
            (loc or {}).get("location") for loc in (job.get("secondaryLocations") or [])
        ]
        locations = dedupe_locations([job.get("location"), *secondary])
        if job.get("isRemote") and not locations:
            locations = ["Remote"]

        return RawPosting(
            company_slug=company.slug,
            company_name=company.name,
            source=self.source,
            external_id=str(job.get("id")),
            title=clean_text(job.get("title")),
            apply_url=job.get("applyUrl") or job.get("jobUrl", ""),
            locations=locations,
            posted_at=parse_dt(job.get("publishedAt")),
            updated_at=parse_dt(job.get("updatedAt")),
            description=clean_text(job.get("descriptionPlain") or job.get("descriptionHtml")),
            department=job.get("department") or job.get("team"),
            employment_type=job.get("employmentType"),
            compensation=_compensation(job.get("compensation")),
        )


def _compensation(comp: Any) -> dict[str, Any] | None:
    """Pull a usable salary band out of Ashby's nested compensation object."""
    if not isinstance(comp, dict):
        return None
    for tier in comp.get("compensationTiers") or []:
        for component in tier.get("components") or []:
            if component.get("compensationType") != "Salary":
                continue
            low, high = component.get("minValue"), component.get("maxValue")
            if low is None and high is None:
                continue
            return {
                "min": low,
                "max": high,
                "currency": component.get("currencyCode", "USD"),
                "interval": component.get("interval"),
                "source": "ashby",
            }
    return None
