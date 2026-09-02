"""Core data types.

Two shapes matter:

``RawPosting``  - what an ATS adapter returns. Deliberately dumb: no judgment
                  about track, degree or sponsorship, just faithfully normalized
                  fields from whatever the vendor gave us.
``Job``         - a raw posting after classification and lifecycle enrichment.
                  This is what gets rendered and published.

Keeping the two apart means a classifier bug can be re-run over cached raw data
without re-hitting 131 job boards.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class Track(StrEnum):
    """Which board a role belongs on."""

    NEW_GRAD_SWE = "new-grad-swe"
    AI_RESEARCH = "ai-research"
    QUANT = "quant"
    INTERNSHIP = "internship"
    OTHER = "other"


class Degree(StrEnum):
    """Highest degree the posting actually asks for."""

    BACHELORS = "bachelors"
    MASTERS_PREFERRED = "masters-preferred"
    PHD_REQUIRED = "phd-required"
    UNSPECIFIED = "unspecified"


class Sponsorship(StrEnum):
    """Work-authorization posture, resolved from the posting text.

    Competing boards default ~99% of rows to an unhelpful "Other". For an
    international MS or PhD student this is the first filter applied to any
    list, so we resolve it properly or admit we could not.
    """

    SPONSORS = "sponsors"
    NO_SPONSORSHIP = "no-sponsorship"
    CITIZENSHIP_REQUIRED = "citizenship-required"
    SECURITY_CLEARANCE = "security-clearance"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class RawPosting:
    """A posting exactly as the source board describes it."""

    company_slug: str
    company_name: str
    source: str
    external_id: str
    title: str
    apply_url: str
    locations: list[str] = field(default_factory=list)
    posted_at: datetime | None = None
    updated_at: datetime | None = None
    description: str = ""
    department: str | None = None
    employment_type: str | None = None
    compensation: dict[str, Any] | None = None

    @property
    def uid(self) -> str:
        """Stable identity for a posting across refreshes.

        Keyed on company + source id, NOT on the URL: several ATS vendors
        rewrite job URLs (job-boards.greenhouse.io vs boards.greenhouse.io)
        without the requisition changing, and keying on URL would make every
        such rewrite look like a brand-new posting.
        """
        basis = f"{self.company_slug}:{self.source}:{self.external_id}"
        return hashlib.sha1(basis.encode()).hexdigest()[:16]


@dataclass(slots=True)
class Job:
    """A classified, lifecycle-tracked posting - the published unit."""

    uid: str
    company_slug: str
    company_name: str
    company_tier: int
    company_category: str
    source: str
    title: str
    apply_url: str
    locations: list[str]
    track: Track
    degree: Degree
    sponsorship: Sponsorship
    first_seen: date
    last_verified: date
    posted_at: date | None = None
    closed_at: date | None = None
    season: str | None = None
    compensation: dict[str, Any] | None = None
    department: str | None = None
    active: bool = True
    #: Result of probing apply_url on the last refresh: ok | dead | closed |
    #: blocked | error | unchecked. Only "dead" and "closed" hide a row; a bot
    #: wall or a timeout is not evidence that a posting is gone.
    link_status: str = "unchecked"
    #: How many separate requisitions this displayed row represents. Employers
    #: like Databricks post one req per metro; the boards show a single role
    #: with the locations merged. data/v1/jobs.json stays per-requisition.
    openings: int = 1

    #: A requisition open this long is evergreen: a standing pipeline rather
    #: than a role someone is filling this quarter. Palantir has 31 of them,
    #: some first published in 2016.
    EVERGREEN_DAYS = 365

    @property
    def posted_age_days(self) -> int | None:
        """Days since the EMPLOYER published it, not since we noticed it.

        This is the honest answer to "which of these is newest". ``first_seen``
        only tells you when this repo started watching, so on day one it is the
        same value for every row.
        """
        if self.posted_at is None:
            return None
        return max(0, (self.last_verified - self.posted_at).days)

    @property
    def is_evergreen(self) -> bool:
        age = self.posted_age_days
        return age is not None and age >= self.EVERGREEN_DAYS

    @property
    def age_days(self) -> int:
        """Days since the role was first observed.

        This is anchored to ``first_seen``, which is written once and never
        overwritten. Competing boards recompute "age" from the last time their
        scraper touched the row, so a months-old requisition displays as "1d".
        """
        return (self.last_verified - self.first_seen).days

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in ("first_seen", "last_verified", "posted_at", "closed_at"):
            if d[key] is not None:
                d[key] = d[key].isoformat()
        for key in ("track", "degree", "sponsorship"):
            d[key] = str(d[key])
        return d


_WS = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    """Collapse whitespace and strip HTML from vendor-supplied prose.

    Order matters and is easy to get backwards. Greenhouse returns *escaped*
    HTML ("&lt;p&gt;"), so stripping tags first and unescaping second leaves
    literal "<p>" in the output. Unescape, strip, then unescape once more for
    entities that were double-encoded.
    """
    if not value:
        return ""
    value = html.unescape(value)
    value = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return _WS.sub(" ", value).strip()
