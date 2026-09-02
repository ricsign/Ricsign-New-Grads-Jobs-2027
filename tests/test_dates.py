"""Recency: which posting is actually newest.

The board originally sorted and displayed only `first_seen` — the date THIS
REPO noticed a role. On day one that is identical for all 311 rows, so the
board could not answer "what's new", which is the first question anyone asks.

`posted_at` — the employer's own publish date — is present on 100% of published
rows, and is the field that actually answers it.
"""

from __future__ import annotations

from datetime import date

import pytest

from eliteboard import render
from eliteboard.adapters.base import dedupe_locations
from eliteboard.models import Degree, Job, Sponsorship, Track

TODAY = date(2026, 9, 1)


def _job(**kw) -> Job:
    base = dict(
        uid="u1", company_slug="databricks", company_name="Databricks", company_tier=0,
        company_category="infra", source="greenhouse", title="AI Engineer - FDE",
        apply_url="https://example.com/a", locations=["Boston, Massachusetts"],
        track=Track.NEW_GRAD_SWE, degree=Degree.UNSPECIFIED,
        sponsorship=Sponsorship.UNKNOWN, first_seen=TODAY, last_verified=TODAY,
    )
    base.update(kw)
    return Job(**base)


class TestPostedAge:
    @pytest.mark.parametrize(
        ("posted", "days", "evergreen"),
        [
            (date(2026, 9, 1), 0, False),
            (date(2026, 8, 28), 4, False),
            (date(2025, 9, 1), 365, True),
            (date(2016, 2, 24), 3842, True),
            (None, None, False),
        ],
    )
    def test_age_and_evergreen(self, posted, days, evergreen):
        job = _job(posted_at=posted)
        assert job.posted_age_days == days
        assert job.is_evergreen is evergreen

    def test_evergreen_threshold_is_one_year(self):
        assert not _job(posted_at=date(2025, 9, 2)).is_evergreen
        assert _job(posted_at=date(2025, 9, 1)).is_evergreen


class TestRecencyOrdering:
    def test_recency_prefers_the_employer_publish_date(self):
        old_post = _job(uid="a", posted_at=date(2016, 2, 24))
        new_post = _job(uid="b", posted_at=date(2026, 8, 30))
        # Identical first_seen — only posted_at can separate them.
        assert render._recency(new_post) > render._recency(old_post)

    def test_recency_falls_back_to_first_seen(self):
        assert render._recency(_job(posted_at=None)) == TODAY.toordinal()

    def test_board_puts_recently_posted_first_within_a_tier(self):
        jobs = [
            _job(uid="old", title="Ancient Role", posted_at=date(2016, 2, 24)),
            _job(uid="new", title="Fresh Role", posted_at=date(2026, 8, 30)),
        ]
        md = render.render_board(Track.NEW_GRAD_SWE, jobs, today=TODAY)
        assert md.index("Fresh Role") < md.index("Ancient Role")


class TestDateFormatting:
    def test_shows_relative_and_absolute(self):
        assert render._posted(_job(posted_at=date(2026, 8, 28))) == "4d · Aug 28"

    def test_includes_the_year_when_it_is_not_the_current_one(self):
        # "10y · Feb 24" reads as this February at a glance, which is wrong.
        out = render._posted(_job(posted_at=date(2016, 2, 24)))
        assert out == "10y · Feb 24 2016"

    def test_missing_posted_date_renders_as_a_dash(self):
        assert render._posted(_job(posted_at=None)) == "—"

    def test_found_column_uses_first_seen(self):
        assert render._found(_job()) == "today · Sep 1"


class TestEvergreenFlag:
    def test_board_marks_a_decade_old_requisition(self):
        md = render.render_board(
            Track.NEW_GRAD_SWE, [_job(posted_at=date(2016, 2, 24))], today=TODAY
        )
        assert "open 10y+" in md

    def test_recent_roles_are_not_marked(self):
        md = render.render_board(
            Track.NEW_GRAD_SWE, [_job(posted_at=date(2026, 8, 28))], today=TODAY
        )
        assert "open " not in md.split("## Tier")[1]


class TestRoleGrouping:
    """Databricks posts one requisition per metro. Nine of those is one job."""

    def test_collapses_same_company_and_title(self):
        jobs = [
            _job(uid=f"u{i}", locations=[c])
            for i, c in enumerate(["Boston, MA", "Austin, TX", "Seattle, WA"])
        ]
        grouped = render.group_roles(jobs)
        assert len(grouped) == 1
        assert grouped[0].openings == 3
        assert set(grouped[0].locations) == {"Boston, MA", "Austin, TX", "Seattle, WA"}

    def test_keeps_the_most_recently_posted_as_representative(self):
        jobs = [
            _job(uid="old", posted_at=date(2026, 1, 1)),
            _job(uid="new", posted_at=date(2026, 8, 30), locations=["Austin, TX"]),
        ]
        assert render.group_roles(jobs)[0].uid == "new"

    def test_does_not_merge_different_titles(self):
        jobs = [_job(uid="a"), _job(uid="b", title="Data Engineer")]
        assert len(render.group_roles(jobs)) == 2

    def test_does_not_merge_across_companies(self):
        jobs = [_job(uid="a"), _job(uid="b", company_slug="stripe", company_name="Stripe")]
        assert len(render.group_roles(jobs)) == 2

    def test_title_matching_ignores_whitespace_and_case(self):
        jobs = [_job(uid="a", title="AI Engineer - FDE"),
                _job(uid="b", title="ai  engineer -  fde")]
        assert len(render.group_roles(jobs)) == 1

    def test_board_shows_the_openings_count(self):
        jobs = [_job(uid=f"u{i}", locations=[f"City {i}"]) for i in range(9)]
        md = render.render_board(Track.NEW_GRAD_SWE, jobs, today=TODAY)
        assert "9 openings" in md
        assert md.count("AI Engineer - FDE") == 1


class TestMultiCityLocationStrings:
    def test_splits_greenhouse_semicolon_runs(self):
        got = dedupe_locations(["Austin, Texas; Dallas, Texas; Houston, Texas"])
        assert got == ["Austin, Texas", "Dallas, Texas", "Houston, Texas"]

    def test_still_collapses_duplicates_after_splitting(self):
        got = dedupe_locations(["Chicago, IL; Chicago", "Chicago, Illinois"])
        assert len(got) == 1


class TestPostedAgeStats:
    def test_stats_expose_the_recency_distribution(self):
        import json

        jobs = [
            _job(uid="a", posted_at=date(2026, 9, 1)),
            _job(uid="b", title="B", posted_at=date(2026, 8, 28)),
            _job(uid="c", title="C", posted_at=date(2016, 2, 24)),
        ]
        stats = json.loads(
            render.render_stats(jobs, today=TODAY, freshness={}, health={})
        )
        pa = stats["posted_age"]
        assert pa["posted_last_24h"] == 1
        assert pa["posted_last_7d"] == 2
        assert pa["evergreen_over_1y"] == 1
        assert pa["with_posted_date_pct"] == 100.0

    def test_stats_separate_roles_from_requisitions(self):
        import json

        jobs = [_job(uid=f"u{i}", locations=[f"C{i}"]) for i in range(9)]
        stats = json.loads(
            render.render_stats(jobs, today=TODAY, freshness={}, health={})
        )
        assert stats["live_requisitions"] == 9
        assert stats["live_roles"] == 1
