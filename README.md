<div align="center">

# Elite New Grad &amp; Internship Jobs — 2027

**Frontier AI labs · FAANG+ · quant/HFT · top startups. Nothing else.**

## → [**Browse and filter every role**](https://ricsign.github.io/Ricsign-New-Grads-Jobs-2027/) ←

Search by company, role or location. Filter by track, visa sponsorship, degree,
tier and how recently it was posted. Sort by newest posted, newest discovered,
or oldest. Shareable links. No sign-up, no email wall, no tracking.

[![Refresh](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/refresh.yml/badge.svg)](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/refresh.yml)
[![CI](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/ci.yml/badge.svg)](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/ci.yml)
[![Links](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/linkcheck.yml/badge.svg)](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/linkcheck.yml)

</div>

---

## The four boards

| | | |
|:--|:--|:--|
| [**New Grad SWE**](boards/NEW_GRAD_SWE.md) | Full-time entry-level software engineering, US | [filter →](https://ricsign.github.io/Ricsign-New-Grads-Jobs-2027/?track=new-grad-swe) |
| [**Internships**](boards/INTERNSHIPS.md) | Summer 2027 SWE and research internships | [filter →](https://ricsign.github.io/Ricsign-New-Grads-Jobs-2027/?track=internship) |
| [**Quant**](boards/QUANT.md) | Campus + new grad at elite quant/HFT. Highest comp band here | [filter →](https://ricsign.github.io/Ricsign-New-Grads-Jobs-2027/?track=quant) |
| [**AI / ML Research**](boards/AI_RESEARCH.md) | The PhD track — plus fellowships and residencies no scraper can find | [filter →](https://ricsign.github.io/Ricsign-New-Grads-Jobs-2027/?track=ai-research) |

**Three links worth knowing:**
[Tier 0 roles that sponsor visas](https://ricsign.github.io/Ricsign-New-Grads-Jobs-2027/?tier=0&sponsor=sponsors) ·
[PhD-required roles](https://ricsign.github.io/Ricsign-New-Grads-Jobs-2027/?degree=phd-required) ·
[Everything at frontier labs](https://ricsign.github.io/Ricsign-New-Grads-Jobs-2027/?tier=0)

## Why it's different

**A hard company bar.** [145 employers](data/companies.yaml), each admitted by a
[published test](docs/COMPANY_BAR.md). Staffing agencies, annotation vendors and
city-spammed reqs are excluded by policy. Max 3 rows per company.

**Two dates, both real.** **Posted** is the employer's own publish date, present
on 100% of rows — that is what actually answers "which of these is new."
**Found** is when this repo first saw it, written once and never bumped by a
re-scrape. Sort by either.

**Evergreen requisitions are flagged, not hidden.** 42 of the roles here have
been open over a year — Palantir has an internship posted in **October 2016**.
That is a standing pipeline, not a role being filled this quarter, and you
deserve to know which is which before you spend an afternoon on it.

**One role, not nine rows.** Databricks posts the same job once per metro. We
merge them into a single row with every location and an openings count, so a
day's genuinely new postings aren't buried under duplicates.

**Sponsorship is resolved, not defaulted.** Parsed from each posting into
`sponsors` / `no-sponsorship` / `citizenship-required` / `security-clearance` —
and honestly marked *unknown* when the posting is silent.

**Every apply link is verified on every refresh**, including soft-closed pages
that return HTTP 200 while saying "no longer accepting applications" — the
failure mode every status-code checker misses.

**A failed scrape never closes a role.** If a board times out we learn nothing
about that company; we don't conclude it closed every position.

**We publish our own misses.** [COVERAGE.md](COVERAGE.md) lists every company,
what we fetched, what we published, and which of our adapters broke.

## The receipts

We measured the largest competing boards in September 2026:

| | |
|:--|:--|
| One board carries **15,119 listings**; 2,409 are live | **15.9%** |
| Its `Age` is a re-scrape timestamp — post and update dates agree on | **6.5%** of rows |
| Its sponsorship field reads `"Other"` on | **99.1%** of live rows |
| TikTok + ByteDance share of one board's new-grad list | **8.9%** |
| Anthropic / OpenAI / DeepMind roles across **5,651** live rows on the two biggest boards | **1 / 0 / 0** |
| Roles here flagged evergreen (open 1y+), rather than shown undated | **42** |

That last row is the whole reason this exists — and the first version of this
repo shipped **0 and 0** too, until [#15](../../pull/15) fixed it. Frontier labs
don't write "new grad" in titles, and Anthropic's four **Fellows Program**
postings contain no technical keyword at all.

## Beyond the listings

| | |
|:--|:--|
| [**Playbook**](docs/PLAYBOOK.md) | When each company opens, which OA platform you'll face, and the PhD programs that never appear on a job board |
| [**Compensation**](docs/COMPENSATION.md) | Sourced new-grad comp, why TC and DOL base salary aren't comparable, and the measurable PhD premium |
| [**Sponsorship**](docs/SPONSORSHIP.md) | What H-1B filings actually show. Jane Street and HRT sponsor heavily; Anduril is the real outlier |
| [**Coverage**](COVERAGE.md) | Every company, what we pulled, what we published — including our failures |
| [**Company Bar**](docs/COMPANY_BAR.md) | The inclusion test and what we refuse to list |

## How it works

```
data/companies.yaml   145 employers · 129 live boards · every token verified
        │
        ▼  every 6h on GitHub Actions
   fetch      greenhouse · ashby · lever · workday · amazon · eightfold
        │     per-company isolation — one 500 cannot fail the run
   classify   US-only → drop senior/non-CS → track → degree → sponsorship
        │     publishes WHY each row was rejected
   lifecycle  first_seen (immutable) · closure requires a SUCCESSFUL fetch
        │
   verify     probe every apply link · hide only proven-dead or closed
        │
   render     4 boards · searchable site · jobs.json · feed.xml · COVERAGE.md
```

```bash
pip install -r requirements-dev.txt && pip install -e .
make test                          # 274 tests, no network
make refresh                       # hits every board, rewrites all outputs
python -m eliteboard.cli doctor    # which boards can't be fetched, and why
```

## Data API

```bash
BASE=https://raw.githubusercontent.com/ricsign/Ricsign-New-Grads-Jobs-2027/main/data/v1

curl -s $BASE/jobs.json | jq -r '.jobs[]
  | select(.sponsorship=="sponsors" and .company_tier==0)
  | "\(.company_name)\t\(.title)\t\(.apply_url)"'
```

[`jobs.json`](data/v1/jobs.json) · [`jobs.ndjson`](data/v1/jobs.ndjson) ·
[`feed.xml`](data/v1/feed.xml) · [`coverage.json`](data/v1/coverage.json) ·
[`programs.json`](data/v1/programs.json) · [`schema.json`](data/v1/schema.json)

Within API v1 we add fields but never remove or repurpose them.

## Honest limitations

- **Six elite firms have no fetchable board** — Jane Street, Citadel, Citadel
  Securities, D. E. Shaw, Two Sigma, Optiver. Custom JS boards, no public JSON.
  Listed with direct links and a written reason rather than silently omitted.
- **Google, Meta, Apple, Microsoft are link-only.** Google's job path is
  robots-disallowed and we respect that; the others need bespoke adapters.
- **`unknown` sponsorship is common** because many postings genuinely don't say.
  We won't invent a value to fill a column.
- **Compensation is sparse** — shown only when the ATS publishes a real band.
- **A verified link is not a guarantee the role is open.** Some pages return 200
  and are quietly closed; [report those](../../issues/new?template=dead-link.yml).

## Contributing

[Add a company](../../issues/new?template=company.yml) ·
[report a dead link](../../issues/new?template=dead-link.yml) ·
[flag a misclassified role](../../issues/new?template=misclassified.yml) ·
[write a missing adapter](CONTRIBUTING.md) (Apple, Microsoft, Meta, Snowflake)

## Related

Broader in scope, different tradeoff:
[SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions) ·
[SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships) ·
[speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs) ·
[northwesternfintech/2027QuantInternships](https://github.com/northwesternfintech/2027QuantInternships)

Want maximum coverage? Use those. Want the top of the market with metadata you
can trust? Use this.

---

<div align="center">

MIT · not affiliated with any listed employer · apply links point to official
career pages only

**If this helped, a ⭐ helps someone else find it.**

</div>
