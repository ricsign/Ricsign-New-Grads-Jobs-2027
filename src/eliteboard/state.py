"""Posting lifecycle: first_seen, last_verified, closed_at.

This module exists because every competing board gets freshness wrong in the
same way. They recompute "age" from the last time their scraper touched a row,
so a requisition that has been open since March displays as "1d". On one
competing list, the posted date and the last-updated date agree on only 6.5% of
rows - meaning 93.5% of its displayed ages are re-scrape timestamps.

Here, ``first_seen`` is written exactly once and never overwritten.

The second guarantee is subtler and matters more. A posting is marked closed
only when its company's board was **successfully fetched and did not contain
it**. If Anthropic's board times out, we must not conclude that Anthropic
closed every role - we simply learn nothing about Anthropic this cycle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

STATE_VERSION = 1
PRUNE_AFTER_DAYS = 60


@dataclass(slots=True)
class Lifecycle:
    uid: str
    first_seen: date
    last_verified: date
    posted_at: date | None = None
    closed_at: date | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "first_seen": self.first_seen.isoformat(),
            "last_verified": self.last_verified.isoformat(),
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Lifecycle:
        def parse(key: str) -> date | None:
            value = raw.get(key)
            return date.fromisoformat(value) if value else None

        return cls(
            uid=raw["uid"],
            first_seen=date.fromisoformat(raw["first_seen"]),
            last_verified=date.fromisoformat(raw["last_verified"]),
            posted_at=parse("posted_at"),
            closed_at=parse("closed_at"),
        )


class StateStore:
    """Durable per-posting history, committed to the repo alongside the data."""

    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[str, Lifecycle] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        self.entries = {
            raw["uid"]: Lifecycle.from_dict(raw) for raw in doc.get("postings", [])
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state_version": STATE_VERSION,
            "postings": [e.to_dict() for e in sorted(self.entries.values(), key=lambda e: e.uid)],
        }
        self.path.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n", encoding="utf-8")

    # ---------------------------------------------------------------- observe
    def observe(self, uid: str, *, today: date, posted_at: date | None = None) -> Lifecycle:
        """Record that a posting is live right now.

        ``first_seen`` is set on the first observation and never touched again.
        A posting that reappears after being marked closed is reopened, keeping
        its original first_seen - companies do re-list roles.
        """
        entry = self.entries.get(uid)
        if entry is None:
            entry = Lifecycle(
                uid=uid, first_seen=today, last_verified=today, posted_at=posted_at
            )
            self.entries[uid] = entry
            return entry

        entry.last_verified = today
        entry.closed_at = None
        if entry.posted_at is None and posted_at is not None:
            entry.posted_at = posted_at
        return entry

    # ----------------------------------------------------------------- close
    def close_missing(
        self, *, live_uids: set[str], trusted_slugs: set[str], uid_owner: dict[str, str], today: date
    ) -> list[str]:
        """Close postings that a *successfully fetched* board no longer lists.

        ``trusted_slugs`` is the set of companies whose fetch actually
        succeeded this cycle. Anything owned by a company outside that set is
        left untouched: absence of evidence is not evidence of closure.
        """
        closed: list[str] = []
        for uid, entry in self.entries.items():
            if uid in live_uids or entry.closed_at is not None:
                continue
            owner = uid_owner.get(uid)
            if owner is None or owner not in trusted_slugs:
                continue
            entry.closed_at = today
            closed.append(uid)
        return closed

    def prune(self, *, today: date, older_than_days: int = PRUNE_AFTER_DAYS) -> int:
        """Drop long-closed postings so the state file does not grow forever."""
        cutoff = today - timedelta(days=older_than_days)
        stale = [
            uid
            for uid, e in self.entries.items()
            if e.closed_at is not None and e.closed_at < cutoff
        ]
        for uid in stale:
            del self.entries[uid]
        return len(stale)

    # ---------------------------------------------------------------- report
    def freshness(self, today: date) -> dict[str, Any]:
        live = [e for e in self.entries.values() if e.closed_at is None]
        ages = sorted((today - e.first_seen).days for e in live)
        return {
            "tracked": len(self.entries),
            "live": len(live),
            "closed": len(self.entries) - len(live),
            "median_age_days": ages[len(ages) // 2] if ages else None,
            "p90_age_days": ages[int(len(ages) * 0.9)] if ages else None,
            "max_age_days": ages[-1] if ages else None,
            "verified_within_24h": sum(1 for e in live if (today - e.last_verified).days <= 1),
        }
