"""amazon.jobs public search JSON.

Amazon runs the largest early-career program of any company on this list and
opens requisitions earlier than any other big-tech employer - typically July
for the following summer. It also exposes a clean, unauthenticated endpoint:

    GET https://www.amazon.jobs/en/search.json?base_query=...&result_limit=100

We query a small set of early-career terms rather than pulling all ~30k
requisitions, then let the classifier make the final call.
"""

from __future__ import annotations

from ..models import RawPosting, clean_text
from ..registry import Company
from .base import dedupe_locations, parse_dt, request_json

API = "https://www.amazon.jobs/en/search.json"
PAGE_SIZE = 100
MAX_PAGES = 5
QUERIES = (
    "software development engineer intern",
    "software development engineer new grad",
    "applied scientist intern",
    "student programs software",
)


class AmazonAdapter:
    source = "amazon"

    def fetch(self, client, company: Company) -> list[RawPosting]:
        out: dict[str, RawPosting] = {}
        for query in QUERIES:
            for page in range(MAX_PAGES):
                payload = request_json(
                    client,
                    "GET",
                    API,
                    params={
                        "base_query": query,
                        "country": "USA",
                        "result_limit": PAGE_SIZE,
                        "offset": page * PAGE_SIZE,
                        "sort": "recent",
                    },
                )
                jobs = payload.get("jobs") or []
                if not jobs:
                    break
                for job in jobs:
                    posting = self._parse(company, job)
                    out.setdefault(posting.external_id, posting)
                if len(jobs) < PAGE_SIZE:
                    break
        return list(out.values())

    def _parse(self, company: Company, job: dict) -> RawPosting:
        path = job.get("job_path", "")
        description = " ".join(
            filter(
                None,
                [
                    job.get("description_short") or job.get("description"),
                    job.get("basic_qualifications"),
                    job.get("preferred_qualifications"),
                ],
            )
        )
        return RawPosting(
            company_slug=company.slug,
            company_name=company.name,
            source=self.source,
            external_id=str(job.get("id_icims") or job.get("id") or path),
            title=clean_text(job.get("title")),
            apply_url=f"https://www.amazon.jobs{path}" if path else "",
            locations=dedupe_locations(
                [job.get("normalized_location") or job.get("location")]
            ),
            posted_at=parse_dt(job.get("posted_date")),
            updated_at=parse_dt(job.get("updated_time")),
            description=clean_text(description),
            department=job.get("business_category") or job.get("job_family"),
        )
