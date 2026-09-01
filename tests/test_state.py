"""Lifecycle tests. The invariants here are the repo's main freshness claim."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from eliteboard.state import StateStore


@pytest.fixture
def store(tmp_path):
    return StateStore(tmp_path / "seen.json")


DAY1 = date(2026, 9, 1)
DAY5 = date(2026, 9, 5)
DAY30 = date(2026, 9, 30)


class TestFirstSeenIsImmutable:
    def test_first_seen_survives_re_observation(self, store):
        store.observe("abc", today=DAY1)
        store.observe("abc", today=DAY5)
        store.observe("abc", today=DAY30)
        entry = store.entries["abc"]
        assert entry.first_seen == DAY1, "re-scraping must never reset first_seen"
        assert entry.last_verified == DAY30

    def test_age_reflects_true_age_not_last_scrape(self, store):
        store.observe("abc", today=DAY1)
        store.observe("abc", today=DAY30)
        e = store.entries["abc"]
        assert (e.last_verified - e.first_seen).days == 29

    def test_survives_a_save_load_round_trip(self, tmp_path):
        s1 = StateStore(tmp_path / "seen.json")
        s1.observe("abc", today=DAY1, posted_at=DAY1)
        s1.save()
        s2 = StateStore(tmp_path / "seen.json")
        assert s2.entries["abc"].first_seen == DAY1
        assert s2.entries["abc"].posted_at == DAY1


class TestClosureRequiresEvidence:
    def test_closes_posting_absent_from_a_successful_fetch(self, store):
        store.observe("gone", today=DAY1)
        closed = store.close_missing(
            live_uids=set(), trusted_slugs={"anthropic"},
            uid_owner={"gone": "anthropic"}, today=DAY5,
        )
        assert closed == ["gone"]
        assert store.entries["gone"].closed_at == DAY5

    def test_does_not_close_when_the_board_failed_to_fetch(self, store):
        # The critical guard. If Anthropic's board 500s, we learn nothing about
        # Anthropic - we must not conclude every Anthropic role closed.
        store.observe("still-open", today=DAY1)
        closed = store.close_missing(
            live_uids=set(), trusted_slugs=set(),  # nothing fetched successfully
            uid_owner={"still-open": "anthropic"}, today=DAY5,
        )
        assert closed == []
        assert store.entries["still-open"].closed_at is None

    def test_does_not_close_postings_still_present(self, store):
        store.observe("open", today=DAY1)
        closed = store.close_missing(
            live_uids={"open"}, trusted_slugs={"anthropic"},
            uid_owner={"open": "anthropic"}, today=DAY5,
        )
        assert closed == []

    def test_reopens_a_relisted_posting_keeping_original_first_seen(self, store):
        store.observe("role", today=DAY1)
        store.close_missing(
            live_uids=set(), trusted_slugs={"anthropic"},
            uid_owner={"role": "anthropic"}, today=DAY5,
        )
        store.observe("role", today=DAY30)
        entry = store.entries["role"]
        assert entry.closed_at is None
        assert entry.first_seen == DAY1


class TestPruning:
    def test_prunes_only_long_closed_entries(self, store):
        store.observe("old", today=DAY1)
        store.observe("live", today=DAY1)
        store.close_missing(
            live_uids={"live"}, trusted_slugs={"c"},
            uid_owner={"old": "c", "live": "c"}, today=DAY1,
        )
        removed = store.prune(today=DAY1 + timedelta(days=90), older_than_days=60)
        assert removed == 1
        assert "live" in store.entries and "old" not in store.entries


class TestFreshness:
    def test_reports_live_and_closed_counts(self, store):
        for uid in ("a", "b", "c"):
            store.observe(uid, today=DAY1)
        store.close_missing(
            live_uids={"a", "b"}, trusted_slugs={"c"},
            uid_owner={"a": "c", "b": "c", "c": "c"}, today=DAY5,
        )
        report = store.freshness(DAY5)
        assert report["live"] == 2 and report["closed"] == 1
        assert report["median_age_days"] == 4
