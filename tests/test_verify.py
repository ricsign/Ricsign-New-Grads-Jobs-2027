"""Link verification.

The governing rule: only positive evidence that a posting is gone may remove it
from a board. A bot wall, a timeout or a TLS error tells us nothing about the
job, and treating those as death is how a board silently loses real roles.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from eliteboard import verify
from eliteboard.models import Degree, Job, Sponsorship, Track


def _job(uid="u1", url="https://example.com/apply") -> Job:
    return Job(
        uid=uid, company_slug="anthropic", company_name="Anthropic", company_tier=0,
        company_category="ai-lab", source="greenhouse", title="New Grad SWE",
        apply_url=url, locations=["San Francisco, CA"], track=Track.NEW_GRAD_SWE,
        degree=Degree.UNSPECIFIED, sponsorship=Sponsorship.UNKNOWN,
        first_seen=date(2026, 9, 1), last_verified=date(2026, 9, 1),
    )


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


class TestStatusClassification:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            (200, "ok"), (301, "ok"),
            (404, "dead"), (410, "dead"),
            (403, "blocked"), (429, "blocked"), (405, "blocked"),
            (500, "error"), (503, "error"),
        ],
    )
    def test_http_codes(self, code, expected):
        body = "" if code >= 300 else "Apply now"
        with _client(lambda r: httpx.Response(code, text=body)) as c:
            assert verify._check_one(c, _job()).status == expected

    def test_network_failure_is_an_error_not_a_death(self):
        def boom(request):
            raise httpx.ConnectTimeout("timed out")

        with _client(boom) as c:
            check = verify._check_one(c, _job())
        assert check.status == "error" and not check.hides_row


class TestSoftClosureDetection:
    """The failure mode every status-code checker misses: HTTP 200 + closed."""

    @pytest.mark.parametrize(
        "body",
        [
            "<h1>We are no longer accepting applications for this role.</h1>",
            "<p>This position has been filled.</p>",
            "<div>This job is no longer available</div>",
            "<p>This posting has expired</p>",
        ],
    )
    def test_detects_closed_pages_returning_200(self, body):
        with _client(lambda r: httpx.Response(200, text=body)) as c:
            check = verify._check_one(c, _job())
        assert check.status == "closed" and check.hides_row

    def test_does_not_fire_on_an_ordinary_posting(self):
        body = "<h1>Software Engineer, New Grad</h1><p>Apply now. We accept applications on a rolling basis.</p>"
        with _client(lambda r: httpx.Response(200, text=body)) as c:
            assert verify._check_one(c, _job()).status == "ok"


class TestOnlyEvidenceHidesRows:
    @pytest.mark.parametrize(
        ("status", "hides"),
        [("dead", True), ("closed", True), ("blocked", False), ("error", False), ("ok", False)],
    )
    def test_hides_row(self, status, hides):
        assert verify.LinkCheck("u", status).hides_row is hides


class TestBatch:
    def test_verify_links_returns_one_check_per_job(self):
        jobs = [_job(uid=f"u{i}") for i in range(5)]
        with _client(lambda r: httpx.Response(200, text="apply")):
            pass
        import unittest.mock as mock

        with mock.patch.object(
            verify.httpx, "Client",
            return_value=_client(lambda r: httpx.Response(200, text="apply")),
        ):
            checks = verify.verify_links(jobs, workers=2)
        assert len(checks) == 5 and all(c.status == "ok" for c in checks.values())

    def test_empty_input_short_circuits(self):
        assert verify.verify_links([]) == {}

    def test_summarize_reports_only_conclusive_results(self):
        checks = {
            "a": verify.LinkCheck("a", "ok"),
            "b": verify.LinkCheck("b", "dead"),
            "c": verify.LinkCheck("c", "blocked"),
            "d": verify.LinkCheck("d", "blocked"),
        }
        out = verify.summarize(checks)
        # 1 ok of 2 conclusive = 50%. The two bot-walls must not drag it to 25%.
        assert out["resolving_pct"] == 50.0
        assert out["checked"] == 4 and out["conclusive"] == 2
