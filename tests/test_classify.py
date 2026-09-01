"""Classifier tests built from REAL posting titles observed on live boards.

Every title in TestRealWorldTitles was seen verbatim on a company's actual job
board during registry verification. Synthetic titles would not have caught
"Campus Full Time 2027 - Quantitative Trader" or "Associate Engineer - 2027 Start".
"""

from __future__ import annotations

import pytest
from conftest import make_company, make_posting

from eliteboard.classify import (
    classify_degree,
    classify_sponsorship,
    classify_track,
    detect_season,
    is_eligible,
)
from eliteboard.models import Degree, Sponsorship, Track


class TestRealWorldTitles:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            # Quant firms - observed verbatim
            ("Campus Quantitative Researcher, PhD (Full-Time)", Track.QUANT),
            ("Campus Software Engineer (Full-Time)", Track.NEW_GRAD_SWE),
            ("Quantitative Trader - 2027 Graduate Program (August Start)", Track.QUANT),
            ("Software Engineer - 2027 Internship Program (June Start)", Track.INTERNSHIP),
            ("Campus Full Time 2027 - Quantitative Trader", Track.QUANT),
            ("Summer Intern 2027 - Quantitative Researcher (PhD)", Track.INTERNSHIP),
            ("Associate Engineer - 2027 Start", Track.NEW_GRAD_SWE),
            ("2027 Engineering Summer Analyst", Track.INTERNSHIP),
            ("Research Developer - New Grad", Track.NEW_GRAD_SWE),
            # Big tech / labs
            ("Software Engineer, University Graduate (US)", Track.NEW_GRAD_SWE),
            ("Member of Technical Staff", Track.AI_RESEARCH),
            ("Research Engineer, Residency", Track.AI_RESEARCH),
            ("Software Development Engineer Intern - Summer 2027", Track.INTERNSHIP),
            ("Applied Scientist Intern", Track.INTERNSHIP),
            ("Software Engineer I", Track.NEW_GRAD_SWE),
            ("SDE I", Track.NEW_GRAD_SWE),
        ],
    )
    def test_track_assignment(self, title, expected):
        posting = make_posting(title)
        company = make_company(category="quant") if expected is Track.QUANT else make_company()
        assert classify_track(posting, company) is expected

    def test_internship_beats_research_and_quant(self, quant_company):
        # A PhD research internship is an internship first: that is how a
        # student filters, and it is the board they will look at.
        p = make_posting("Summer Intern 2027 - Quantitative Researcher (PhD)")
        assert classify_track(p, quant_company) is Track.INTERNSHIP


class TestEligibility:
    @pytest.mark.parametrize(
        "title",
        [
            "Senior Software Engineer",
            "Staff Machine Learning Engineer",
            "Principal Engineer, Infrastructure",
            "Engineering Manager, Platform",
            "Software Engineer III",
            "Director of Engineering",
            "Software Engineer, 5+ years",
        ],
    )
    def test_rejects_senior_roles(self, title, company):
        ok, reason = is_eligible(make_posting(title), company)
        assert not ok and "senior" in reason

    def test_engineer_i_is_not_treated_as_seniority(self, company):
        # "Engineer I" is a new grad level; "Engineer II" is not. The seniority
        # regex must not swallow the former.
        ok, _ = is_eligible(make_posting("Software Engineer I"), company)
        assert ok
        ok2, _ = is_eligible(make_posting("Software Engineer II"), company)
        assert not ok2

    @pytest.mark.parametrize(
        "title",
        [
            "Recruiter, Technical",
            "Account Executive, Startups",
            "Marketing Intern",
            "Executive Assistant",
            "Paralegal",
        ],
    )
    def test_rejects_non_technical_roles(self, title, company):
        ok, _ = is_eligible(make_posting(title), company)
        assert not ok

    def test_rejects_non_us_locations(self, company):
        ok, reason = is_eligible(
            make_posting("New Grad Software Engineer", locations=["London, UK"]), company
        )
        assert not ok and "US" in reason

    def test_keeps_multi_location_posting_with_one_us_office(self, company):
        ok, _ = is_eligible(
            make_posting(
                "New Grad Software Engineer",
                locations=["London, UK", "San Francisco, CA"],
            ),
            company,
        )
        assert ok

    def test_rejects_posting_with_no_apply_url(self, company):
        ok, _ = is_eligible(make_posting("New Grad SWE", apply_url=""), company)
        assert not ok

    def test_rejects_lateral_quant_role(self, quant_company):
        # Quant firms label most of their board "quant". Without an early-career
        # marker we would import their entire lateral pipeline.
        ok, reason = is_eligible(make_posting("Quantitative Researcher"), quant_company)
        assert not ok and "early-career" in reason

    def test_accepts_research_role_with_residency_signal(self, company):
        p = make_posting(
            "Research Engineer",
            description="Our residency is designed for recent PhD graduates.",
        )
        assert is_eligible(p, company)[0]


class TestSponsorship:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("This role requires an active TS/SCI security clearance.", Sponsorship.SECURITY_CLEARANCE),
            ("Applicants must be a U.S. Person as defined by ITAR.", Sponsorship.CITIZENSHIP_REQUIRED),
            ("US Citizenship is required for this position.", Sponsorship.CITIZENSHIP_REQUIRED),
            ("We are unable to sponsor visas for this role.", Sponsorship.NO_SPONSORSHIP),
            ("This employer does not sponsor employment visas.", Sponsorship.NO_SPONSORSHIP),
            ("Candidates must be authorized to work without sponsorship.", Sponsorship.NO_SPONSORSHIP),
            ("We offer visa sponsorship and immigration support.", Sponsorship.SPONSORS),
            ("Visa sponsorship is available for this position.", Sponsorship.SPONSORS),
            ("We are an equal opportunity employer.", Sponsorship.UNKNOWN),
            ("", Sponsorship.UNKNOWN),
        ],
    )
    def test_resolution(self, text, expected, company):
        assert classify_sponsorship(make_posting("SWE", description=text), company) is expected

    def test_citizenship_beats_generic_sponsorship_boilerplate(self, company):
        # A defense posting that carries both must resolve to the restrictive one.
        text = "US Citizenship is required. We offer visa sponsorship for other roles."
        got = classify_sponsorship(make_posting("SWE", description=text), company)
        assert got is Sponsorship.CITIZENSHIP_REQUIRED

    def test_unknown_is_used_rather_than_guessing(self, company):
        # The competing failure mode is defaulting ~99% of rows to a meaningless
        # value. UNKNOWN must mean "the posting did not say".
        got = classify_sponsorship(make_posting("SWE", description="Great team!"), company)
        assert got is Sponsorship.UNKNOWN


class TestDegree:
    def test_phd_in_title(self):
        p = make_posting("Quantitative Researcher, PhD (Full-Time)")
        assert classify_degree(p) is Degree.PHD_REQUIRED

    def test_phd_required_in_body(self):
        p = make_posting("Research Scientist", description="A PhD in Computer Science is required.")
        assert classify_degree(p) is Degree.PHD_REQUIRED

    def test_masters_preferred(self):
        p = make_posting("SWE", description="Master's degree preferred but not required.")
        assert classify_degree(p) is Degree.MASTERS_PREFERRED

    def test_bachelors(self):
        p = make_posting("SWE", description="Bachelor's degree in Computer Science.")
        assert classify_degree(p) is Degree.BACHELORS

    def test_unspecified_when_silent(self):
        assert classify_degree(make_posting("SWE", description="Join us!")) is Degree.UNSPECIFIED


class TestSeason:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("Software Engineer Intern, Summer 2027", "Summer 2027"),
            ("2027 Engineering Summer Analyst", "Summer 2027"),
            ("Fall 2026 Co-op", "Fall 2026"),
            ("Associate Engineer - 2027 Start", "2027"),
            ("Software Engineer", None),
        ],
    )
    def test_detection(self, title, expected):
        assert detect_season(make_posting(title)) == expected
