"""Rendering: markdown boards, the versioned JSON API, and the Atom feed.

Two deliberate choices differ from every competing repo.

**Plain markdown tables, not embedded HTML.** One competing board renders every
cell as `<a><img>` soup, which makes the file impossible to grep, impossible to
diff usefully, and unreadable in a terminal. Ours is greppable.

**A guaranteed machine-readable URL.** ``data/v1/jobs.json`` is versioned,
schema'd and documented. One competitor advertises a JSON path in its llms.txt
that 404s; another ships an 11 MB undocumented dump on a side branch.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime

from .models import Degree, Job, Sponsorship, Track

REPO_URL = "https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027"
MAX_ROWS_PER_COMPANY = 3

SPONSOR_BADGE = {
    Sponsorship.SPONSORS: ("🌏", "Sponsors visas"),
    Sponsorship.NO_SPONSORSHIP: ("🛂", "No sponsorship"),
    Sponsorship.CITIZENSHIP_REQUIRED: ("🇺🇸", "US citizenship required"),
    Sponsorship.SECURITY_CLEARANCE: ("🔒", "Security clearance required"),
    Sponsorship.UNKNOWN: ("·", "Posting does not say"),
}
DEGREE_BADGE = {
    Degree.PHD_REQUIRED: ("🎓", "PhD"),
    Degree.MASTERS_PREFERRED: ("📗", "MS preferred"),
    Degree.BACHELORS: ("", ""),
    Degree.UNSPECIFIED: ("", ""),
}

BOARDS: dict[Track, tuple[str, str, str]] = {
    Track.NEW_GRAD_SWE: (
        "NEW_GRAD_SWE.md",
        "New Grad Software Engineering — 2027",
        "Full-time entry-level software engineering roles in the US.",
    ),
    Track.AI_RESEARCH: (
        "AI_RESEARCH.md",
        "AI / ML Research — 2027",
        "Research Scientist, Research Engineer, Member of Technical Staff, "
        "residencies and fellowships. The PhD-track board.",
    ),
    Track.QUANT: (
        "QUANT.md",
        "Quant — Trading, Research & Development",
        "Campus and new-grad roles at elite quant and HFT firms. "
        "Highest compensation band on this repo.",
    ),
    Track.INTERNSHIP: (
        "INTERNSHIPS.md",
        "Internships — Summer 2027",
        "Software engineering and research internships at the same curated bar.",
    ),
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _escape(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def _locations(job: Job, limit: int = 2) -> str:
    if not job.locations:
        return "—"
    shown = job.locations[:limit]
    suffix = f" +{len(job.locations) - limit}" if len(job.locations) > limit else ""
    return _escape(", ".join(shown) + suffix)


def _comp(job: Job) -> str:
    comp = job.compensation
    if not comp:
        return "—"
    low, high, interval = comp.get("min"), comp.get("max"), comp.get("interval")
    unit = "/hr" if interval and "hour" in str(interval).lower() else ""

    def fmt(value):
        if value is None:
            return None
        value = float(value)
        return f"${value:,.0f}" if unit else f"${value / 1000:,.0f}k"

    lo, hi = fmt(low), fmt(high)
    if lo and hi and lo != hi:
        return f"{lo}–{hi}{unit}"
    return f"{lo or hi}{unit}" if (lo or hi) else "—"


def _age(job: Job) -> str:
    days = job.age_days
    if days <= 0:
        return "today"
    if days == 1:
        return "1d"
    if days < 30:
        return f"{days}d"
    return f"{days // 30}mo"


def _badges(job: Job) -> str:
    sponsor = SPONSOR_BADGE[job.sponsorship][0]
    degree = DEGREE_BADGE[job.degree][0]
    return f"{sponsor}{degree}".strip() or "·"


def _sort_key(job: Job):
    # Tier first, then most recently first observed. Never alphabetical - that
    # is why every competing list opens on Adobe.
    return (job.company_tier, -job.first_seen.toordinal(), job.company_name, job.title)


def cap_per_company(jobs: list[Job], limit: int = MAX_ROWS_PER_COMPANY) -> list[Job]:
    """Enforce the volume cap so one large campus program cannot flood a board."""
    counts: Counter[str] = Counter()
    kept: list[Job] = []
    for job in sorted(jobs, key=_sort_key):
        if counts[job.company_slug] >= limit:
            continue
        counts[job.company_slug] += 1
        kept.append(job)
    return kept


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------
LEGEND = (
    "**Legend** — 🌏 sponsors visas · 🛂 no sponsorship · 🇺🇸 US citizenship required · "
    "🔒 clearance required · `·` posting doesn't say · 🎓 PhD · 📗 MS preferred\n\n"
    "`Age` is time since **we first saw the posting**, not since we last re-scraped it."
)


def render_board(track: Track, jobs: list[Job], *, today: date) -> str:
    filename, title, blurb = BOARDS[track]
    live = cap_per_company([j for j in jobs if j.active and j.track is track])

    lines = [
        f"# {title}",
        "",
        blurb,
        "",
        f"**{len(live)} open roles** · last verified {today.isoformat()} · "
        f"[all boards]({REPO_URL}#boards) · [jobs.json]({REPO_URL}/blob/main/data/v1/jobs.json)",
        "",
        LEGEND,
        "",
    ]

    by_tier: dict[int, list[Job]] = defaultdict(list)
    for job in live:
        by_tier[job.company_tier].append(job)

    tier_titles = {
        0: "Tier 0 — Frontier labs & category-defining firms",
        1: "Tier 1 — Established elite",
        2: "Tier 2 — Strong specialists",
    }

    if not live:
        lines += [
            "> No roles currently open on this board.",
            ">",
            "> This is expected off-cycle and is not a bug — we show an empty board",
            "> rather than padding it with stale or out-of-scope listings.",
            "",
        ]

    for tier in sorted(by_tier):
        lines += [
            f"## {tier_titles[tier]}",
            "",
            "| Company | Role | Location | Comp | Flags | Age | Apply |",
            "|:--|:--|:--|:--|:-:|--:|:-:|",
        ]
        for job in by_tier[tier]:
            season = f" · _{job.season}_" if job.season else ""
            lines.append(
                f"| **{_escape(job.company_name)}** "
                f"| {_escape(job.title)}{season} "
                f"| {_locations(job)} "
                f"| {_comp(job)} "
                f"| {_badges(job)} "
                f"| {_age(job)} "
                f"| [apply]({job.apply_url}) |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"[how this list is built]({REPO_URL}/blob/main/docs/COMPANY_BAR.md) · "
        f"[report a bad link]({REPO_URL}/issues/new?template=dead-link.yml)",
        "",
    ]
    return "\n".join(lines)


def render_recent(jobs: list[Job], *, today: date, limit: int = 25) -> str:
    """The 'what changed' table pinned to the README."""
    fresh = sorted(
        (j for j in jobs if j.active),
        key=lambda j: (-j.first_seen.toordinal(), j.company_tier),
    )[:limit]
    if not fresh:
        return "_No postings tracked yet._"

    lines = [
        "| Added | Company | Role | Track | Location | Flags |",
        "|:--|:--|:--|:--|:--|:-:|",
    ]
    for job in fresh:
        lines.append(
            f"| {_age(job)} | **{_escape(job.company_name)}** | "
            f"[{_escape(job.title)}]({job.apply_url}) | "
            f"{job.track.value} | {_locations(job, 1)} | {_badges(job)} |"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# machine-readable outputs
# --------------------------------------------------------------------------
def render_jobs_json(jobs: list[Job], *, today: date) -> str:
    payload = {
        "api_version": 1,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": REPO_URL,
        "license": "MIT",
        "count": sum(1 for j in jobs if j.active),
        "jobs": [j.to_dict() for j in sorted(jobs, key=_sort_key) if j.active],
    }
    return json.dumps(payload, indent=1, ensure_ascii=False) + "\n"


def render_jobs_ndjson(jobs: list[Job]) -> str:
    return "".join(
        json.dumps(j.to_dict(), ensure_ascii=False) + "\n"
        for j in sorted(jobs, key=_sort_key)
        if j.active
    )


def render_stats(jobs: list[Job], *, today: date, freshness: dict, health: dict) -> str:
    live = [j for j in jobs if j.active]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "live_roles": len(live),
        "companies_with_open_roles": len({j.company_slug for j in live}),
        "by_track": {t.value: sum(1 for j in live if j.track is t) for t in Track},
        "by_tier": {str(t): sum(1 for j in live if j.company_tier == t) for t in (0, 1, 2)},
        "by_sponsorship": {
            s.value: sum(1 for j in live if j.sponsorship is s) for s in Sponsorship
        },
        "by_degree": {d.value: sum(1 for j in live if j.degree is d) for d in Degree},
        "sponsorship_resolved_pct": round(
            100 * sum(1 for j in live if j.sponsorship is not Sponsorship.UNKNOWN)
            / max(len(live), 1),
            1,
        ),
        "freshness": freshness,
        "pipeline_health": health,
    }
    return json.dumps(payload, indent=1) + "\n"


def render_feed(jobs: list[Job], *, today: date, limit: int = 50) -> str:
    """Atom feed of newly-seen roles. No competing repo publishes one."""
    fresh = sorted((j for j in jobs if j.active), key=lambda j: -j.first_seen.toordinal())[:limit]
    now = datetime.now(UTC).isoformat(timespec="seconds")

    def esc(text: str) -> str:
        return (
            (text or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    entries = "\n".join(
        f"""  <entry>
    <title>{esc(j.company_name)} — {esc(j.title)}</title>
    <link href="{esc(j.apply_url)}"/>
    <id>tag:ricsign.github.io,2026:{j.uid}</id>
    <updated>{j.first_seen.isoformat()}T00:00:00Z</updated>
    <category term="{j.track.value}"/>
    <summary>{esc(', '.join(j.locations))} · {j.sponsorship.value} · {j.degree.value}</summary>
  </entry>"""
        for j in fresh
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Elite 2027 New Grad &amp; Internship Roles</title>
  <link href="{REPO_URL}"/>
  <link rel="self" href="{REPO_URL}/blob/main/data/v1/feed.xml"/>
  <id>tag:ricsign.github.io,2026:eliteboard</id>
  <updated>{now}</updated>
{entries}
</feed>
"""


def render_changelog_entry(
    *, today: date, added: Iterable[Job], closed: list[str], total: int
) -> str:
    added = list(added)
    lines = [f"## {today.isoformat()}", ""]
    lines.append(f"**+{len(added)} new · −{len(closed)} closed · {total} live**")
    lines.append("")
    if added:
        for job in sorted(added, key=_sort_key)[:40]:
            lines.append(
                f"- `+` **{job.company_name}** — [{_escape(job.title)}]({job.apply_url}) "
                f"({job.track.value}, {_locations(job, 1)})"
            )
        if len(added) > 40:
            lines.append(f"- _…and {len(added) - 40} more_")
    else:
        lines.append("- _No new roles today._")
    lines.append("")
    return "\n".join(lines)
