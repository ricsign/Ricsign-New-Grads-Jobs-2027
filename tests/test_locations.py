"""US location detection.

This board is US-only, and getting it wrong is costly in both directions: drop
a real US role and the board is incomplete; keep a London role and someone
wastes an application. Vendors give free text with no country field, so the
tricky cases are the ambiguous city names.
"""

from __future__ import annotations

import pytest

from eliteboard.locations import any_us, is_us, us_only


class TestUnambiguous:
    @pytest.mark.parametrize(
        "location",
        [
            "San Francisco, CA", "New York City, NY", "Seattle, WA",
            "Cambridge, MA", "Austin, TX", "Hawthorne, California",
            "McLean, VA", "United States", "Remote - US", "Remote-Friendly (US)",
            "Mountain View, CA; Seattle, WA", "Chicago, IL", "Los Gatos, CA",
        ],
    )
    def test_us_locations(self, location):
        assert is_us(location)

    @pytest.mark.parametrize(
        "location",
        [
            "London, UK", "Dublin, Ireland", "Zurich, Switzerland",
            "Bengaluru, India", "Singapore", "Sydney, Australia",
            "Tel Aviv, Israel", "Tokyo, Japan", "Remote (EMEA)",
            "São Paulo, Brazil", "Toronto, Canada",
        ],
    )
    def test_non_us_locations(self, location):
        assert not is_us(location)


class TestAmbiguousCityNames:
    """The cases that make naive substring matching wrong."""

    def test_london_ontario_is_not_us(self):
        assert not is_us("London, Ontario, CAN")

    def test_cambridge_uk_is_not_us_but_cambridge_ma_is(self):
        assert not is_us("Cambridge, UK")
        assert is_us("Cambridge, MA")

    def test_the_english_word_us_does_not_count_as_a_country(self):
        # A case-insensitive \bus\b would match "join us" in half of all prose.
        assert not is_us("Join us in Paris")

    def test_vancouver_is_not_us(self):
        assert not is_us("Vancouver, BC")


class TestMultiLocation:
    def test_any_us_keeps_a_posting_with_one_us_office(self):
        assert any_us(["London, UK", "San Francisco, CA"])

    def test_any_us_rejects_a_fully_international_posting(self):
        assert not any_us(["London, UK", "Paris, France"])

    def test_us_only_filters_the_display_list(self):
        assert us_only(["London, UK", "San Francisco, CA", "Tokyo, Japan"]) == [
            "San Francisco, CA"
        ]

    def test_empty_input_is_not_us(self):
        assert not is_us("") and not any_us([])
