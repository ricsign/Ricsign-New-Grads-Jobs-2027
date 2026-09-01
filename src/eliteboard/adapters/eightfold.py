"""Eightfold AI career sites - Netflix and Qualcomm in our registry.

    GET https://{host}/api/apply/v2/jobs?domain={domain}&start=0&num=10

``num`` is capped at 10 server-side on most tenants, so this pages.
"""

from __future__ import annotations

from ..models import RawPosting, clean_text
from ..registry import Company
from .base import dedupe_locations, parse_dt, request_json

PAGE_SIZE = 10
MAX_PAGES = 60


class EightfoldAdapter:
    source = "eightfold"

    def fetch(self, client, company: Company) -> list[RawPosting]:
        host = company.eightfold_host
        endpoint = f"https://{host}/api/apply/v2/jobs"
        out: dict[str, RawPosting] = {}

        for page in range(MAX_PAGES):
            payload = request_json(
                client,
                "GET",
                endpoint,
                params={
                    "domain": company.token,
                    "start": page * PAGE_SIZE,
                    "num": PAGE_SIZE,
                    "sort_by": "timestamp",
                },
            )
            positions = payload.get("positions") or []
            if not positions:
                break
            for job in positions:
                posting = self._parse(company, job, host)
                out.setdefault(posting.external_id, posting)
            if len(out) >= int(payload.get("count") or 0):
                break
        return list(out.values())

    def _parse(self, company: Company, job: dict, host: str) -> RawPosting:
        job_id = str(job.get("id") or job.get("ats_job_id") or "")
        url = (
            job.get("canonicalPositionUrl")
            or job.get("careerSiteJobUrl")
            or f"https://{host}/careers/job/{job_id}"
        )
        return RawPosting(
            company_slug=company.slug,
            company_name=company.name,
            source=self.source,
            external_id=job_id,
            title=clean_text(job.get("name")),
            apply_url=url,
            locations=dedupe_locations(job.get("locations") or [job.get("location")]),
            posted_at=parse_dt(job.get("t_create") or job.get("t_update")),
            updated_at=parse_dt(job.get("t_update")),
            description=clean_text(job.get("job_description")),
            department=job.get("department"),
        )
