"""Pipeline and rendering tests - the guarantees the README makes to a reader."""

from __future__ import annotations

import json
from datetime import date

import pytest
from conftest import make_company, make_posting

from eliteboard import render
from eliteboard.models import Degree, Job, Sponsorship, Track
from eliteboard.pipeline import _dedupe, build_jobs
from eliteboard.state import StateStore

TODAY = date(2026, 9, 1)


@pytest.fixture
def store(tmp_path):
    return StateStore(tmp_path / "seen.json")


@pytest.fixture
def index():
    return {
        "anthropic": make_company(),
        "ctc-campus": make_company(
            name="Chicago Trading Company", slug="ctc-campus", tier=1,
            category="quant", token="chicagotradingcampus",
            careers_url="https://www.chicagotrading.com/careers/",
        ),
        "ctc-lateral": make_company(
            name="Chicago Trading Company", slug="ctc-lateral", tier=1,
            category="quant", token="chicagotrading",
            careers_url="https://www.chicagotrading.com/careers/",
        ),
    }


class TestDedupe:
    def test_collapses_the_same_role_across_split_company_boards(self):
        # CTC runs a campus board and a lateral board under one company name.
        # A role on both must appear once.
        postings = [
            make_posting("Associate Engineer - 2027 Start", company_slug="ctc-campus",
                         company_name="Chicago Trading Company", external_id="1"),
            make_posting("Associate Engineer - 2027 Start", company_slug="ctc-lateral",
                         company_name="Chicago Trading Company", external_id="2"),
        ]
        assert len(_dedupe(postings)) == 1

    def test_keeps_distinct_roles(self):
        postings = [
            make_posting("New Grad SWE", external_id="1"),
            make_posting("New Grad SWE", external_id="2", locations=["Seattle, WA"]),
        ]
        assert len(_dedupe(postings)) == 2


class TestBuildJobs:
    def test_publishes_rejection_reasons_rather_than_dropping_silently(self, store, index):
        postings = [
            make_posting("New Grad Software Engineer", external_id="1"),
            make_posting("Senior Software Engineer", external_id="2"),
            make_posting("New Grad Software Engineer", external_id="9",
                         locations=["London, UK"]),
            make_posting("Recruiter", external_id="10"),
        ]
        jobs, rejections, per_company, samples = build_jobs(postings, index, store, today=TODAY)
        assert len(jobs) == 1
        assert sum(rejections.values()) == 3
        assert set(rejections) == {
            "senior/experienced role", "not a US location", "non-technical role",
        }
        # Reasons alone are not auditable; a sample of the actual dropped
        # titles is what lets someone check whether recall is being lost.
        assert samples["senior/experienced role"] == ["Anthropic — Senior Software Engineer"]

    def test_records_fetched_and_published_counts_per_company(self, store, index):
        postings = [
            make_posting("New Grad Software Engineer", external_id="1"),
            make_posting("Senior Software Engineer", external_id="2"),
        ]
        _, _, per_company, _ = build_jobs(postings, index, store, today=TODAY)
        # A zero-published company must still show what we pulled, so a reader
        # can tell "their board was empty" from "we filtered everything out".
        assert per_company["anthropic"] == {"fetched": 2, "published": 1}

    def test_carries_lifecycle_dates_onto_the_job(self, store, index):
        jobs, *_ = build_jobs([make_posting("New Grad SWE")], index, store, today=TODAY)
        assert jobs[0].first_seen == TODAY and jobs[0].last_verified == TODAY


def _job(**kw) -> Job:
    base = dict(
        uid="u1", company_slug="anthropic", company_name="Anthropic", company_tier=0,
        company_category="ai-lab", source="greenhouse", title="New Grad SWE",
        apply_url="https://example.com/a", locations=["San Francisco, CA"],
        track=Track.NEW_GRAD_SWE, degree=Degree.UNSPECIFIED, sponsorship=Sponsorship.SPONSORS,
        first_seen=TODAY, last_verified=TODAY,
    )
    base.update(kw)
    return Job(**base)


class TestVolumeCap:
    def test_caps_rows_per_company(self):
        jobs = [_job(uid=f"u{i}", title=f"New Grad SWE {i}") for i in range(10)]
        assert len(render.cap_per_company(jobs, limit=3)) == 3

    def test_cap_is_per_company_not_global(self):
        jobs = [_job(uid=f"a{i}", title=f"R{i}") for i in range(5)]
        jobs += [
            _job(uid=f"b{i}", company_slug="openai", company_name="OpenAI", title=f"R{i}")
            for i in range(5)
        ]
        assert len(render.cap_per_company(jobs, limit=3)) == 6


class TestMarkdown:
    def test_board_renders_a_greppable_table(self):
        md = render.render_board(Track.NEW_GRAD_SWE, [_job()], today=TODAY)
        assert "| **Anthropic** |" in md
        assert "[apply](https://example.com/a)" in md
        assert "<img" not in md and "<a href" not in md, "must stay plain markdown"

    def test_empty_board_says_so_instead_of_padding(self):
        md = render.render_board(Track.QUANT, [], today=TODAY)
        assert "No roles currently open" in md
        assert "rather than padding it" in md

    def test_pipe_characters_in_titles_are_escaped(self):
        md = render.render_board(
            Track.NEW_GRAD_SWE, [_job(title="SWE | Infra")], today=TODAY
        )
        assert "SWE \\| Infra" in md

    def test_compensation_formats_as_a_band(self):
        job = _job(compensation={"min": 210000, "max": 290000, "interval": "1 YEAR"})
        md = render.render_board(Track.NEW_GRAD_SWE, [job], today=TODAY)
        assert "$210k–$290k" in md

    def test_hourly_compensation_is_not_shown_in_thousands(self):
        job = _job(compensation={"min": 63, "max": 80, "interval": "1 HOUR"})
        md = render.render_board(Track.NEW_GRAD_SWE, [job], today=TODAY)
        assert "$63–$80/hr" in md


class TestJsonApi:
    def test_jobs_json_is_versioned_and_self_describing(self):
        doc = json.loads(render.render_jobs_json([_job()], today=TODAY))
        assert doc["api_version"] == 1
        assert doc["count"] == 1
        assert doc["license"] == "MIT"
        job = doc["jobs"][0]
        assert job["first_seen"] == "2026-09-01"
        assert job["track"] == "new-grad-swe"

    def test_closed_roles_are_excluded_from_the_api(self):
        doc = json.loads(render.render_jobs_json([_job(active=False)], today=TODAY))
        assert doc["count"] == 0 and doc["jobs"] == []

    def test_ndjson_is_one_object_per_line(self):
        text = render.render_jobs_ndjson([_job(), _job(uid="u2")])
        lines = [ln for ln in text.splitlines() if ln]
        assert len(lines) == 2 and all(json.loads(ln)["uid"] for ln in lines)

    def test_stats_reports_sponsorship_resolution_rate(self):
        jobs = [_job(), _job(uid="u2", sponsorship=Sponsorship.UNKNOWN)]
        stats = json.loads(
            render.render_stats(jobs, today=TODAY, freshness={}, health={})
        )
        assert stats["sponsorship_resolved_pct"] == 50.0


class TestFeed:
    def test_atom_feed_is_well_formed(self):
        import xml.etree.ElementTree as ET

        xml = render.render_feed([_job()], today=TODAY)
        root = ET.fromstring(xml)
        assert root.tag.endswith("feed")
        assert len(root.findall("{http://www.w3.org/2005/Atom}entry")) == 1

    def test_feed_escapes_ampersands_in_titles(self):
        import xml.etree.ElementTree as ET

        xml = render.render_feed([_job(title="R&D Engineer")], today=TODAY)
        ET.fromstring(xml)  # would raise on an unescaped &
        assert "R&amp;D" in xml


class TestResearchBoardIsACrossCuttingView:
    """The PhD board is a view, not a partition.

    A strict partition on `track` left it with 2 rows in production, because
    "Research Scientist Intern" is classified as an internship and every
    PhD-required SWE role sits on the new-grad board. A PhD student searches by
    research content, not employment type.
    """

    def test_includes_research_internships(self):
        job = _job(uid="r1", title="Research Scientist Intern, Summer 2027",
                   track=Track.INTERNSHIP)
        assert job in render.select_for_board(Track.AI_RESEARCH, [job])

    def test_includes_phd_required_roles_from_other_boards(self):
        job = _job(uid="r2", title="Campus Quantitative Researcher",
                   track=Track.QUANT, degree=Degree.PHD_REQUIRED)
        assert job in render.select_for_board(Track.AI_RESEARCH, [job])

    def test_excludes_ordinary_swe_roles(self):
        job = _job(uid="r3", title="New Grad Software Engineer")
        assert render.select_for_board(Track.AI_RESEARCH, [job]) == []

    def test_excludes_data_residency_systems_roles(self):
        job = _job(uid="r4", title="Systems Engineer (Data Residency)")
        assert render.select_for_board(Track.AI_RESEARCH, [job]) == []

    def test_other_boards_remain_strict_partitions(self):
        research = _job(uid="r5", title="Research Engineer", track=Track.AI_RESEARCH)
        assert render.select_for_board(Track.NEW_GRAD_SWE, [research]) == []

    def test_a_role_may_appear_on_two_boards(self):
        job = _job(uid="r6", title="Research Scientist Intern", track=Track.INTERNSHIP)
        assert job in render.select_for_board(Track.INTERNSHIP, [job])
        assert job in render.select_for_board(Track.AI_RESEARCH, [job])


class TestTitleTruncation:
    """Amazon ships 200-character titles that enumerate every sub-team."""

    LONG = (
        "Robotics - Applied Scientist II Intern / Co-op - 2026 (Robotics, "
        "Manipulation, Perception, Motion Planning, Autonomous Mobile Robots, "
        "Computer Vision, Machine Learning, Controls, and more)"
    )

    def test_long_titles_are_truncated_on_a_word_boundary(self):
        out = render._title(self.LONG)
        assert len(out) <= render.MAX_TITLE + 1
        assert out.endswith("\u2026")
        assert not out.endswith(" \u2026")

    def test_short_titles_are_untouched(self):
        assert render._title("Research Engineer, Residency") == "Research Engineer, Residency"

    def test_truncation_still_escapes_pipes(self):
        assert "\\|" in render._title("A" * 80 + " | infra")

    def test_board_row_stays_a_single_table_row(self):
        job = _job(title=self.LONG, track=Track.INTERNSHIP)
        md = render.render_board(Track.INTERNSHIP, [job], today=TODAY)
        row = [ln for ln in md.splitlines() if ln.startswith("| **Anthropic**")]
        assert len(row) == 1 and row[0].count("|") == 8


class TestDeadRowsAreHiddenFromBoards:
    def test_dead_and_closed_rows_are_hidden(self):
        for status in ("dead", "closed"):
            job = _job(uid=status, link_status=status)
            assert render.select_for_board(Track.NEW_GRAD_SWE, [job]) == []

    def test_bot_blocked_rows_are_still_shown(self):
        # A bot wall is not evidence the job is gone. Hiding these would lose
        # real roles at every employer with aggressive bot protection.
        job = _job(uid="blocked", link_status="blocked")
        assert render.select_for_board(Track.NEW_GRAD_SWE, [job]) == [job]

    def test_unchecked_rows_are_shown(self):
        job = _job(uid="unchecked", link_status="unchecked")
        assert render.select_for_board(Track.NEW_GRAD_SWE, [job]) == [job]
