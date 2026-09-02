"""Lever job boards - https://api.lever.co/v0/postings

Used by Palantir and Belvedere Trading in our registry.
"""

from __future__ import annotations

from ..models import RawPosting, clean_text
from ..registry import Company
from .base import dedupe_locations, parse_dt, request_json

API = "https://api.lever.co/v0/postings/{token}"


class LeverAdapter:
    source = "lever"

    def fetch(self, client, company: Company) -> list[RawPosting]:
        payload = request_json(
            client, "GET", API.format(token=company.token), params={"mode": "json"}
        )
        return [self._parse(company, j) for j in payload or []]

    def _parse(self, company: Company, job: dict) -> RawPosting:
        cats = job.get("categories") or {}
        extra = [w.get("location") for w in (job.get("workplaceType") or []) if isinstance(w, dict)]

        return RawPosting(
            company_slug=company.slug,
            company_name=company.name,
            source=self.source,
            external_id=str(job.get("id")),
            title=clean_text(job.get("text")),
            apply_url=job.get("hostedUrl") or job.get("applyUrl", ""),
            locations=dedupe_locations([cats.get("location"), *extra]),
            posted_at=parse_dt(job.get("createdAt")),
            updated_at=parse_dt(job.get("updatedAt") or job.get("createdAt")),
            description=_full_description(job),
            department=cats.get("team") or cats.get("department"),
            employment_type=cats.get("commitment"),
        )


def _full_description(job: dict) -> str:
    """Concatenate every prose field Lever exposes.

    ``descriptionPlain`` is only the opening blurb. Requirements live in
    ``lists`` — an array of {text, content} sections — and closing notes in
    ``additionalPlain``. Reading only the blurb is why Palantir's defense roles
    resolved to "sponsorship not stated" while their requirements section said
    "Eligibility and willingness to obtain a US Security clearance".
    """
    parts = [job.get("descriptionPlain") or job.get("description") or ""]
    for section in job.get("lists") or []:
        if isinstance(section, dict):
            parts.append(section.get("text") or "")
            parts.append(section.get("content") or "")
    parts.append(job.get("additionalPlain") or job.get("additional") or "")
    return clean_text(" ".join(p for p in parts if p))
