"""End-to-end refresh: fetch → classify → track lifecycle → render.

Every stage reports what it discarded and why. A pipeline that silently drops
rows is how a board quietly becomes wrong, so the rejection breakdown is
published in ``data/v1/stats.json`` rather than logged and forgotten.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import classify, render
from .fetch import RefreshReport, fetch_all
from .models import Job, RawPosting
from .registry import REPO_ROOT, Company, by_slug, load_registry
from .state import StateStore

log = logging.getLogger(__name__)

DATA_DIR = REPO_ROOT / "data"
API_DIR = DATA_DIR / "v1"
STATE_PATH = DATA_DIR / "state" / "seen.json"
BOARDS_DIR = REPO_ROOT / "boards"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


@dataclass(slots=True)
class PipelineResult:
    jobs: list[Job]
    rejections: Counter = field(default_factory=Counter)
    report: RefreshReport | None = None
    newly_added: list[Job] = field(default_factory=list)
    newly_closed: list[str] = field(default_factory=list)


def _dedupe(postings: list[RawPosting]) -> list[RawPosting]:
    """Collapse the same requisition seen twice.

    Two passes. ``uid`` catches a board returning a duplicate. The second key
    catches the genuinely tricky case: firms like Chicago Trading and Radix run
    a campus board *and* a lateral board under one company name, and a role
    listed on both must appear once.
    """
    seen_uid: set[str] = set()
    seen_role: set[tuple[str, str, str]] = set()
    out: list[RawPosting] = []
    for p in postings:
        role_key = (
            p.company_name.casefold(),
            " ".join(p.title.split()).casefold(),
            (p.locations[0] if p.locations else "").casefold(),
        )
        if p.uid in seen_uid or role_key in seen_role:
            continue
        seen_uid.add(p.uid)
        seen_role.add(role_key)
        out.append(p)
    return out


def build_jobs(
    postings: list[RawPosting],
    companies: dict[str, Company],
    store: StateStore,
    *,
    today: date,
) -> tuple[list[Job], Counter]:
    rejections: Counter = Counter()
    jobs: list[Job] = []

    for posting in _dedupe(postings):
        company = companies.get(posting.company_slug)
        if company is None:
            rejections["unknown company"] += 1
            continue

        eligible, reason = classify.is_eligible(posting, company)
        if not eligible:
            rejections[reason] += 1
            continue

        lifecycle = store.observe(
            posting.uid,
            today=today,
            posted_at=posting.posted_at.date() if posting.posted_at else None,
        )
        jobs.append(
            Job(
                uid=posting.uid,
                company_slug=company.slug,
                company_name=company.name,
                company_tier=company.tier,
                company_category=company.category,
                source=posting.source,
                title=posting.title,
                apply_url=posting.apply_url,
                locations=classify.us_locations(posting),
                track=classify.classify_track(posting, company),
                degree=classify.classify_degree(posting),
                sponsorship=classify.classify_sponsorship(posting, company),
                first_seen=lifecycle.first_seen,
                last_verified=lifecycle.last_verified,
                posted_at=lifecycle.posted_at,
                season=classify.detect_season(posting),
                compensation=posting.compensation,
                department=posting.department,
                active=True,
            )
        )
    return jobs, rejections


def run(*, today: date | None = None, workers: int = 12) -> PipelineResult:
    today = today or date.today()
    companies = load_registry()
    index = by_slug(companies)

    report = fetch_all(companies, workers=workers)
    store = StateStore(STATE_PATH)
    known_before = set(store.entries)

    jobs, rejections = build_jobs(report.postings, index, store, today=today)

    # Only companies whose fetch actually succeeded may cause closures.
    trusted = {r.company.slug for r in report.results if r.status in ("ok", "empty")}
    uid_owner = {j.uid: j.company_slug for j in jobs}
    uid_owner.update(
        {p.uid: p.company_slug for p in report.postings}
    )
    closed = store.close_missing(
        live_uids={j.uid for j in jobs},
        trusted_slugs=trusted,
        uid_owner=uid_owner,
        today=today,
    )
    store.prune(today=today)
    store.save()

    newly_added = [j for j in jobs if j.uid not in known_before]
    log.info(
        "pipeline: %d live · +%d new · -%d closed · %d rejected",
        len(jobs), len(newly_added), len(closed), sum(rejections.values()),
    )
    return PipelineResult(
        jobs=jobs, rejections=rejections, report=report,
        newly_added=newly_added, newly_closed=closed,
    )


def write_outputs(result: PipelineResult, *, today: date | None = None) -> list[Path]:
    today = today or date.today()
    store = StateStore(STATE_PATH)
    written: list[Path] = []

    BOARDS_DIR.mkdir(parents=True, exist_ok=True)
    API_DIR.mkdir(parents=True, exist_ok=True)

    for track, (filename, _, _) in render.BOARDS.items():
        path = BOARDS_DIR / filename
        path.write_text(render.render_board(track, result.jobs, today=today), encoding="utf-8")
        written.append(path)

    health = result.report.to_dict() if result.report else {}
    health["rejections"] = dict(result.rejections.most_common())

    outputs = {
        API_DIR / "jobs.json": render.render_jobs_json(result.jobs, today=today),
        API_DIR / "jobs.ndjson": render.render_jobs_ndjson(result.jobs),
        API_DIR / "feed.xml": render.render_feed(result.jobs, today=today),
        API_DIR / "stats.json": render.render_stats(
            result.jobs, today=today, freshness=store.freshness(today), health=health
        ),
    }
    for path, body in outputs.items():
        path.write_text(body, encoding="utf-8")
        written.append(path)

    entry = render.render_changelog_entry(
        today=today,
        added=result.newly_added,
        closed=result.newly_closed,
        total=len(result.jobs),
    )
    previous = ""
    if CHANGELOG.exists():
        text = CHANGELOG.read_text(encoding="utf-8")
        previous = text.split("<!-- entries -->", 1)[-1].lstrip("\n")
        # Never stack two entries for the same day; replace instead.
        if previous.startswith(f"## {today.isoformat()}"):
            previous = "\n".join(previous.split("\n## ")[1:])
            previous = f"## {previous}" if previous else ""
    CHANGELOG.write_text(
        "# Changelog\n\nDaily record of what opened and closed. "
        "Generated by the refresh workflow.\n\n<!-- entries -->\n\n"
        + entry
        + "\n"
        + previous,
        encoding="utf-8",
    )
    written.append(CHANGELOG)
    return written
