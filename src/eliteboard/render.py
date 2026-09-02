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
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import replace
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
        "residencies and fellowships — plus every PhD-required role from the "
        "other boards. This is a **cross-cutting view**: a research internship "
        "appears here *and* on Internships, because that is how a PhD student "
        "actually searches.",
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
MAX_TITLE = 88


def _escape(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def _title(text: str) -> str:
    """Escape and truncate a role title.

    Amazon in particular ships 200-character titles that enumerate every
    sub-team ("... Manipulation, Perception, Motion Planning, Autonomous Mobile
    Robots, Computer Vision, Machine Learning, Controls, and more"), which blows
    the table layout apart on any normal screen.
    """
    text = _escape(text)
    if len(text) <= MAX_TITLE:
        return text
    cut = text[:MAX_TITLE].rsplit(" ", 1)[0].rstrip(" ,;-—(")
    return f"{cut}…"


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


def _posted(job: Job) -> str:
    """Relative + absolute publish date, e.g. "4d · Aug 28"."""
    if job.posted_at is None:
        return "—"
    days = job.posted_age_days or 0
    if days == 0:
        rel = "today"
    elif days == 1:
        rel = "1d"
    elif days < 30:
        rel = f"{days}d"
    elif days < 365:
        rel = f"{days // 30}mo"
    else:
        rel = f"{days // 365}y"
    # Include the year whenever it is not the current one - "10y · Feb 24"
    # reads as this February at a glance, which is exactly wrong.
    fmt = "%b %-d" if job.posted_at.year == job.last_verified.year else "%b %-d %Y"
    return f"{rel} · {job.posted_at.strftime(fmt)}"


def _found(job: Job) -> str:
    fmt = "%b %-d" if job.first_seen.year == job.last_verified.year else "%b %-d %Y"
    return f"{_age(job)} · {job.first_seen.strftime(fmt)}"


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


def _recency(job: Job) -> int:
    """Ordinal used for "newest". Prefers the employer's own publish date.

    ``first_seen`` is when WE noticed a role, which on day one is identical for
    every row and tells a reader nothing. ``posted_at`` is on 100% of published
    rows today, so it is the field that actually answers "which is newest".
    """
    return (job.posted_at or job.first_seen).toordinal()


def _sort_key(job: Job):
    # Tier first, then genuinely most-recently-posted. Never alphabetical -
    # that is why every competing list opens on Adobe.
    return (job.company_tier, -_recency(job), job.company_name, job.title)


def group_roles(jobs: list[Job]) -> list[Job]:
    """Collapse one role posted once per metro into a single row.

    Databricks currently lists "AI Engineer - FDE" nine times, once per city,
    and Palantir and SpaceX do the same. Nine identical titles in a row is not
    nine opportunities - it is one, and rendering it as nine buries everything
    posted the same day underneath it.

    We keep the most recently posted requisition as the representative, merge
    every location, and record the count. ``data/v1/jobs.json`` is untouched and
    remains one entry per requisition, because an API consumer wants them all.
    """
    from .adapters.base import dedupe_locations

    buckets: dict[tuple[str, str], list[Job]] = {}
    for job in jobs:
        key = (job.company_slug, " ".join(job.title.split()).casefold())
        buckets.setdefault(key, []).append(job)

    out: list[Job] = []
    for group in buckets.values():
        if len(group) == 1:
            out.append(group[0])
            continue
        group.sort(key=lambda j: (-_recency(j), j.uid))
        lead = replace(
            group[0],
            locations=dedupe_locations([loc for j in group for loc in j.locations]),
            openings=len(group),
        )
        out.append(lead)
    return out


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
    "**Posted** is the employer's own publish date. **Found** is when this repo "
    "first saw the role — written once, never bumped by a re-scrape.\n\n"
    "`open Ny+` marks an evergreen requisition that has been open that long. "
    "Those are standing pipelines, not roles being filled this quarter."
)


# Research titles, for the cross-cutting PhD view. Same "Data Residency"
# lookbehind as the classifier - a distributed-systems role is not a residency.
RESEARCH_TITLE = re.compile(
    r"\b(research\w*|scientist|member\s+of\s+technical\s+staff|\bmts\b|"
    r"(?<!data\s)(?<!tax\s)residency|resident|fellow(?:ship)?)\b",
    re.I,
)


#: Statuses that are positive evidence a posting is gone. Everything else -
#: bot walls, timeouts - tells us nothing and must not remove a row.
HIDDEN_LINK_STATUS = {"dead", "closed"}


def select_for_board(track: Track, jobs: list[Job]) -> list[Job]:
    """Choose which roles belong on a board.

    Every board except AI/ML Research is a straight partition on ``track``.

    Research is deliberately a *view* rather than a partition. Track assignment
    puts internships on the internship board, so a strict partition left the
    PhD board with two rows while "Research Scientist Intern" and every
    PhD-required role sat elsewhere. A PhD student searches by research content,
    not by employment type, so those roles appear on both.
    """
    live = [j for j in jobs if j.active and j.link_status not in HIDDEN_LINK_STATUS]
    if track is not Track.AI_RESEARCH:
        return [j for j in live if j.track is track]
    return [
        j
        for j in live
        if j.track is Track.AI_RESEARCH
        or j.degree is Degree.PHD_REQUIRED
        or RESEARCH_TITLE.search(j.title)
    ]


def render_board(
    track: Track, jobs: list[Job], *, today: date, programs: list[dict] | None = None
) -> str:
    filename, title, blurb = BOARDS[track]
    live = cap_per_company(group_roles(select_for_board(track, jobs)))

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

    if track is Track.AI_RESEARCH and programs:
        lines.append(render_programs_section(programs))

    fresh = [j for j in live if (j.posted_age_days or 999) <= 7]
    if fresh:
        lines += [
            f"## 🆕 Posted in the last 7 days ({len(fresh)})",
            "",
            "| Company | Role | Location | Posted |",
            "|:--|:--|:--|--:|",
        ]
        for job in sorted(fresh, key=_sort_key)[:15]:
            lines.append(
                f"| **{_escape(job.company_name)}** | [{_title(job.title)}]({job.apply_url}) "
                f"| {_locations(job, 1)} | {_posted(job)} |"
            )
        lines += ["", ""]

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
            "| Company | Role | Location | Comp | Flags | Posted | Found | Apply |",
            "|:--|:--|:--|:--|:-:|--:|--:|:-:|",
        ]
        for job in by_tier[tier]:
            season = f" · _{job.season}_" if job.season else ""
            if job.openings > 1:
                season += f" · `{job.openings} openings`"
            if job.is_evergreen:
                years = (job.posted_age_days or 0) // 365
                season += f" · `open {years}y+`"
            lines.append(
                f"| **{_escape(job.company_name)}** "
                f"| {_title(job.title)}{season} "
                f"| {_locations(job)} "
                f"| {_comp(job)} "
                f"| {_badges(job)} "
                f"| {_posted(job)} "
                f"| {_found(job)} "
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
            f"[{_title(job.title)}]({job.apply_url}) | "
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
    live = [j for j in jobs if j.active and j.link_status not in HIDDEN_LINK_STATUS]
    grouped = group_roles(live)
    posted_ages = sorted(
        j.posted_age_days for j in grouped if j.posted_age_days is not None
    )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        # Requisitions, and the distinct roles they collapse into. Employers
        # like Databricks post one req per metro; nine of those is one job.
        "live_requisitions": len(live),
        "live_roles": len(grouped),
        "companies_with_open_roles": len({j.company_slug for j in live}),
        "posted_age": {
            "median_days": posted_ages[len(posted_ages) // 2] if posted_ages else None,
            "posted_last_24h": sum(1 for a in posted_ages if a <= 1),
            "posted_last_7d": sum(1 for a in posted_ages if a <= 7),
            "posted_last_30d": sum(1 for a in posted_ages if a <= 30),
            "evergreen_over_1y": sum(1 for a in posted_ages if a >= Job.EVERGREEN_DAYS),
            "with_posted_date_pct": round(
                100 * len(posted_ages) / max(len(grouped), 1), 1
            ),
        },
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
        "link_verified_pct": round(
            100 * sum(1 for j in live if j.link_status == "ok") / max(len(live), 1), 1
        ),
        "by_link_status": {
            status: sum(1 for j in live if j.link_status == status)
            for status in ("ok", "blocked", "error", "dead", "closed", "unchecked")
        },
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
                f"- `+` **{job.company_name}** — [{_title(job.title)}]({job.apply_url}) "
                f"({job.track.value}, {_locations(job, 1)})"
            )
        if len(added) > 40:
            lines.append(f"- _…and {len(added) - 40} more_")
    else:
        lines.append("- _No new roles today._")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# coverage
# --------------------------------------------------------------------------
def _coverage_rows(companies, result):
    """Per-company outcome, joined against the registry and the fetch report."""
    status_by_slug = {}
    if result.report:
        status_by_slug = {r.company.slug: r for r in result.report.results}

    rows = []
    for company in companies:
        fetched = result.per_company.get(company.slug, {}).get("fetched", 0)
        published = result.per_company.get(company.slug, {}).get("published", 0)
        fetch_result = status_by_slug.get(company.slug)

        if not company.is_fetchable:
            status = "link-only"
        elif fetch_result is None:
            status = "not attempted"
        elif fetch_result.status == "error":
            status = "FETCH FAILED"
        elif fetched == 0:
            status = "board empty"
        elif published == 0:
            status = "none matched"
        else:
            status = "ok"
        rows.append((company, fetched, published, status))
    return rows


def render_coverage(companies, result, *, today: date) -> str:
    """A per-company audit of what we fetched versus what we published.

    This exists because "48 companies have roles" invites the obvious question
    about the other 97, and a job board that cannot answer it is asking to be
    trusted rather than earning it. Every company is listed with its raw fetch
    count, so a zero is visibly either "their board is empty", "nothing cleared
    our early-career bar", or "our adapter broke" - three very different facts.
    """
    rows = _coverage_rows(companies, result)
    total_fetched = sum(r[1] for r in rows)
    total_published = sum(r[2] for r in rows)
    failed = [r for r in rows if r[3] == "FETCH FAILED"]
    none_matched = [r for r in rows if r[3] == "none matched"]
    empty = [r for r in rows if r[3] == "board empty"]

    lines = [
        "# Coverage",
        "",
        f"Generated {today.isoformat()} · [live JSON](data/v1/coverage.json)",
        "",
        "Every company in the registry, with what we actually pulled from its board.",
        "A zero in **Published** is not automatically a gap — it may mean the company",
        "has no early-career roles open right now, which is itself worth knowing.",
        "",
        "| | |",
        "|:--|--:|",
        f"| Companies in registry | {len(rows)} |",
        f"| Postings fetched | {total_fetched:,} |",
        f"| Postings published | {total_published:,} |",
        f"| Boards that failed to fetch | **{len(failed)}** |",
        f"| Boards live but with nothing early-career | {len(none_matched)} |",
        f"| Boards returning nothing at all | {len(empty)} |",
        "",
    ]

    if failed:
        lines += [
            "## ⚠ Adapters that failed",
            "",
            "These are our bugs, not empty boards. Each one is lost coverage.",
            "",
            "| Company | ATS | Token |",
            "|:--|:--|:--|",
        ]
        lines += [
            f"| {c.name} | {c.ats} | `{c.token}` |" for c, _, _, _ in failed
        ]
        lines.append("")

    if none_matched:
        lines += [
            "## Boards we read that had nothing early-career",
            "",
            "These companies are hiring — just not for roles that clear the bar today.",
            "A sample of what we saw and why we dropped it, so you can check our work",
            "rather than take it on faith.",
            "",
        ]
        for company, fetched, _, _ in sorted(
            none_matched, key=lambda r: (r[0].tier, r[0].name)
        )[:24]:
            samples = result.zero_samples.get(company.slug, [])
            lines.append(
                f"<details><summary><b>{_escape(company.name)}</b> — "
                f"{fetched} postings read, none early-career</summary>\n"
            )
            for sample in samples[:6]:
                lines.append(f"- `{_escape(sample)}`")
            lines.append("\n</details>\n")
        lines.append("")

    lines += [
        "## Every company",
        "",
        "| Company | Tier | Board | Fetched | Published | Status |",
        "|:--|:-:|:--|--:|--:|:--|",
    ]
    for company, fetched, published, status in sorted(
        rows, key=lambda r: (r[0].tier, -r[2], r[0].name)
    ):
        board = f"`{company.ats}:{company.token}`" if company.is_fetchable else "—"
        mark = {"ok": "✅", "FETCH FAILED": "⚠️", "link-only": "🔗"}.get(status, "○")
        lines.append(
            f"| [{_escape(company.name)}]({company.careers_url}) | {company.tier} | {board} "
            f"| {fetched or '—'} | {published or '—'} | {mark} {status} |"
        )
    lines += ["", "---", "", f"[Back to the boards]({REPO_URL}#boards)", ""]
    return "\n".join(lines)


def render_coverage_json(companies, result, *, today: date) -> str:
    rows = _coverage_rows(companies, result)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "companies": [
            {
                "slug": c.slug,
                "name": c.name,
                "tier": c.tier,
                "ats": c.ats,
                "token": c.token,
                "fetched": fetched,
                "published": published,
                "status": status,
            }
            for c, fetched, published, status in rows
        ],
        "rejections": dict(result.rejections.most_common()),
        "rejection_samples": result.rejection_samples,
        "zero_published_samples": result.zero_samples,
    }
    return json.dumps(payload, indent=1, ensure_ascii=False) + "\n"



def render_programs_section(programs: list[dict]) -> str:
    """Pinned block at the top of the research board.

    These are the highest-value entry points into frontier research for a grad
    student, and not one of them is a job requisition. Two carry gates you must
    clear years ahead: the Google PhD Fellowship is university-nominated and
    cannot be applied to directly, and the NVIDIA fellowship requires an NVIDIA
    Research internship you must already have completed. People routinely learn
    both facts too late, which is the entire reason this block exists.
    """
    if not programs:
        return ""
    lines = [
        "## Programs that never appear on a job board",
        "",
        "Not requisitions — named programs with their own applications and calendars.",
        "No scraper will ever surface these. Hand-verified; open an issue if one moves.",
        "",
        "| Program | What you get | Who it's for |",
        "|:--|:--|:--|",
    ]
    for p in programs:
        dormant = " _(dormant)_" if p.get("status") == "dormant" else ""
        lines.append(
            f"| **[{_escape(p['name'])}]({p['url']})**{dormant}<br><sub>{_escape(p['org'])}</sub> "
            f"| {_escape(p.get('stipend', '—'))}<br><sub>{_escape(p.get('duration', ''))}</sub> "
            f"| {_escape(p.get('eligibility', '—'))} |"
        )
    notes = [p for p in programs if p.get("note")]
    if notes:
        lines.append("")
        for p in notes:
            lines.append(f"- **{_escape(p['name'])}** — {_escape(p['note'])}")
    lines.append("")
    return "\n".join(lines)


def render_programs_json(programs: list[dict]) -> str:
    return json.dumps(
        {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "count": len(programs),
            "programs": programs,
        },
        indent=1,
        ensure_ascii=False,
    ) + "\n"
