"""Adapter tests against recorded fixtures shaped like each vendor's real payload.

Adapters are pinned with fixtures rather than live calls so CI is deterministic
and does not hammer 131 job boards on every push. The fixtures encode the
vendor quirks that actually bite: Greenhouse HTML-escaping its content field,
Ashby nesting compensation two levels deep, Lever using epoch milliseconds, and
Workday returning a relative date string with no absolute timestamp.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from conftest import make_company

from eliteboard.adapters import (
    AmazonAdapter,
    AshbyAdapter,
    EightfoldAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    WorkdayAdapter,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def client_returning(payload, *, capture: list | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture.append(request)
        # Paginating adapters must terminate: serve the payload once, then empty.
        if capture is not None and len(capture) > 1:
            empty = {"jobPostings": [], "positions": [], "jobs": []}
            return httpx.Response(200, json=empty)
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestGreenhouse:
    def test_parses_postings(self):
        with client_returning(load("greenhouse")) as c:
            out = GreenhouseAdapter().fetch(c, make_company())
        assert len(out) == 2
        job = out[0]
        assert job.title == "Software Engineer, New Grad (2027)"
        assert job.external_id == "4021553008"
        assert job.locations == ["San Francisco, CA", "New York City, NY"]
        assert job.department == "Research"

    def test_prefers_first_published_over_updated_at(self):
        # updated_at bumps on any edit; using it would make an old req look new.
        with client_returning(load("greenhouse")) as c:
            job = GreenhouseAdapter().fetch(c, make_company())[0]
        assert job.posted_at.date().isoformat() == "2026-08-25"

    def test_unescapes_html_content(self):
        with client_returning(load("greenhouse")) as c:
            job = GreenhouseAdapter().fetch(c, make_company())[0]
        assert "<p>" not in job.description
        assert "unable to sponsor visas" in job.description


class TestAshby:
    def test_drops_unlisted_postings(self):
        with client_returning(load("ashby")) as c:
            out = AshbyAdapter().fetch(c, make_company(ats="ashby", token="openai"))
        assert all("Draft" not in j.title for j in out)
        assert len(out) == 2

    def test_extracts_nested_compensation(self):
        with client_returning(load("ashby")) as c:
            job = AshbyAdapter().fetch(c, make_company(ats="ashby", token="openai"))[0]
        assert job.compensation == {
            "min": 210000, "max": 290000, "currency": "USD",
            "interval": "1 YEAR", "source": "ashby",
        }

    def test_merges_secondary_locations(self):
        with client_returning(load("ashby")) as c:
            job = AshbyAdapter().fetch(c, make_company(ats="ashby", token="openai"))[0]
        assert job.locations == ["San Francisco, CA", "New York, NY"]


class TestLever:
    def test_parses_epoch_millisecond_dates(self):
        company = make_company(ats="lever", token="palantir", name="Palantir", slug="palantir")
        with client_returning(load("lever")) as c:
            job = LeverAdapter().fetch(c, company)[0]
        assert job.posted_at is not None
        assert job.posted_at.year == 2025 or job.posted_at.year == 2026
        assert job.employment_type == "Full-time"


    def test_reads_requirements_out_of_the_lists_sections(self):
        # descriptionPlain is only the opening blurb. Palantir's clearance
        # requirement lives in `lists`, and missing it made defense roles
        # resolve to "sponsorship not stated".
        company = make_company(ats="lever", token="palantir", name="Palantir", slug="palantir")
        with client_returning(load("lever")) as c:
            jobs = LeverAdapter().fetch(c, company)
        assert "US Security clearance" in jobs[0].description
        assert "Strong CS fundamentals" in jobs[0].description
        assert "equal opportunity" in jobs[0].description

    def test_clearance_requirement_now_classifies(self):
        from eliteboard.classify import classify_sponsorship
        from eliteboard.models import Sponsorship

        company = make_company(ats="lever", token="palantir", name="Palantir", slug="palantir")
        with client_returning(load("lever")) as c:
            jobs = LeverAdapter().fetch(c, company)
        defense = next(j for j in jobs if "Defense" in j.title)
        assert classify_sponsorship(defense, company) is Sponsorship.SECURITY_CLEARANCE


class TestWorkday:
    def test_builds_apply_url_and_terminates_pagination(self):
        company = make_company(
            ats="workday", token="nvidia", name="NVIDIA", slug="nvidia",
            workday={"tenant": "nvidia", "wd": "wd5", "site": "NVIDIAExternalCareerSite"},
        )
        seen: list = []
        with client_returning(load("workday"), capture=seen) as c:
            out = WorkdayAdapter().fetch(c, company)
        assert out[0].apply_url == (
            "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite"
            "/job/Santa-Clara-CA/SWE_JR123"
        )
        assert len(seen) <= 3, "pagination must terminate"

    def test_never_fabricates_a_date_from_relative_text(self):
        # Workday says "Posted 3 Days Ago" with no absolute date. Inventing one
        # is exactly the freshness lie this repo exists to avoid.
        company = make_company(
            ats="workday", token="nvidia", slug="nvidia",
            workday={"tenant": "nvidia", "wd": "wd5", "site": "S"},
        )
        with client_returning(load("workday"), capture=[]) as c:
            out = WorkdayAdapter().fetch(c, company)
        assert all(j.posted_at is None for j in out)


class TestEightfoldAndAmazon:
    def test_eightfold(self):
        company = make_company(
            ats="eightfold", token="netflix.com", slug="netflix", name="Netflix",
            eightfold_host="explore.jobs.netflix.net",
        )
        with client_returning(load("eightfold"), capture=[]) as c:
            out = EightfoldAdapter().fetch(c, company)
        assert out[0].apply_url.endswith("/careers/job/790123")
        assert out[0].locations == ["Los Gatos, CA"]

    def test_amazon(self):
        company = make_company(ats="amazon", token="amazon", slug="amazon", name="Amazon")
        with client_returning(load("amazon"), capture=[]) as c:
            out = AmazonAdapter().fetch(c, company)
        assert out[0].apply_url == "https://www.amazon.jobs/en/jobs/2891234/sde-intern"
        assert out[0].external_id == "2891234"


class TestFailureIsolation:
    def test_a_failing_board_does_not_raise_into_the_pipeline(self):
        from eliteboard.fetch import fetch_company

        def boom(request):
            return httpx.Response(500, json={"error": "nope"})

        with httpx.Client(transport=httpx.MockTransport(boom)) as c:
            result = fetch_company(make_company(), c)
        assert result.status == "error" and result.error and result.postings == []

    def test_an_empty_board_is_reported_distinctly_from_a_failure(self):
        # ashby:deel and ashby:wiz both return 200 with zero jobs. A naive
        # 200-check would call that healthy and scrape nothing forever.
        from eliteboard.fetch import fetch_company

        with client_returning({"jobs": []}) as c:
            result = fetch_company(make_company(), c)
        assert result.status == "empty" and result.error is None
