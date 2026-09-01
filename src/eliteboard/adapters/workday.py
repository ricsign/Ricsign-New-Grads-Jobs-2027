"""Workday CXS boards.

Covers NVIDIA, Salesforce, Adobe, AMD, Intel and Broadcom. Workday exposes a
POST-only JSON endpoint behind every ``*.myworkdayjobs.com`` career site:

    POST https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
    {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}

Two quirks worth knowing. ``limit`` is capped at 20 server-side regardless of
what you ask for, so a 4,000-req tenant needs 200 round trips - we bound that.
And ``postedOn`` is a *relative* string ("Posted 3 Days Ago") with no absolute
date, so posted_at stays None rather than being invented.
"""

from __future__ import annotations

import re

from ..models import RawPosting, clean_text
from ..registry import Company
from .base import dedupe_locations, request_json

PAGE_SIZE = 20
MAX_PAGES = 40  # 800 postings/company; far past anything a campus filter returns
REL_DAYS = re.compile(r"posted\s+(\d+)\+?\s+days?\s+ago", re.I)


class WorkdayAdapter:
    source = "workday"

    def fetch(self, client, company: Company) -> list[RawPosting]:
        cfg = company.workday or {}
        tenant, wd, site = cfg["tenant"], cfg["wd"], cfg["site"]
        base = f"https://{tenant}.{wd}.myworkdayjobs.com"
        endpoint = f"{base}/wday/cxs/{tenant}/{site}/jobs"

        out: list[RawPosting] = []
        seen: set[str] = set()
        for page in range(MAX_PAGES):
            payload = request_json(
                client,
                "POST",
                endpoint,
                json_body={
                    "appliedFacets": {},
                    "limit": PAGE_SIZE,
                    "offset": page * PAGE_SIZE,
                    "searchText": "",
                },
            )
            batch = payload.get("jobPostings") or []
            if not batch:
                break
            for job in batch:
                posting = self._parse(company, job, base, site)
                if posting.external_id not in seen:
                    seen.add(posting.external_id)
                    out.append(posting)
            if len(out) >= int(payload.get("total") or 0):
                break
        return out

    def _parse(self, company: Company, job: dict, base: str, site: str) -> RawPosting:
        path = job.get("externalPath", "")
        req_id = next(
            (b for b in job.get("bulletFields") or [] if b),
            path.rsplit("/", 1)[-1] or path,
        )
        return RawPosting(
            company_slug=company.slug,
            company_name=company.name,
            source=self.source,
            external_id=str(req_id),
            title=clean_text(job.get("title")),
            apply_url=f"{base}/en-US/{site}{path}",
            locations=dedupe_locations([job.get("locationsText")]),
            posted_at=None,  # Workday gives relative text only; never fabricate.
            description=clean_text(job.get("jobDescription")),
        )
