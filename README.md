<div align="center">

# Elite New Grad & Internship Jobs — 2027

**Frontier AI labs · FAANG+ · quant/HFT · top startups. Nothing else.**

A curated 2027 job board for CS students optimizing for the top of the market —
re-verified every 6 hours, with sponsorship, compensation and real freshness
data on every row.

[**New Grad SWE**](boards/NEW_GRAD_SWE.md) · [**AI/ML Research**](boards/AI_RESEARCH.md) · [**Quant**](boards/QUANT.md) · [**Internships**](boards/INTERNSHIPS.md)

[![Refresh](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/refresh.yml/badge.svg)](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/refresh.yml)
[![CI](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/ci.yml/badge.svg)](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/ci.yml)
[![Links](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/linkcheck.yml/badge.svg)](https://github.com/ricsign/Ricsign-New-Grads-Jobs-2027/actions/workflows/linkcheck.yml)

</div>

---

## Why this exists

There are good 2027 job repos. They share one problem: they optimize for
**coverage**, and coverage is not what a strong candidate is short of.

Here is what we measured across the largest of them in September 2026:

| | What we found |
|:--|:--|
| **Dead weight** | One board carries 15,119 listings. **2,409 are live — 15.9%.** Of those, only 36% are actually Summer 2027. |
| **Fake freshness** | Its `Age` column is a *re-scrape* timestamp. Post date and update date agree on **6.5%** of rows, so ~93% of displayed ages are wrong. 221 rows over 120 days old still show as live. |
| **Decorative metadata** | Its sponsorship field reads `"Other"` on **99.1%** of live rows. The 🛂/🇺🇸 legend fires on under 1%. |
| **Noise** | TikTok + ByteDance = **8.9%** of one board's entire new-grad list. A single data-annotation vendor posts 64 open reqs. |
| **The actual gap** | Across **5,651 live rows** on the two biggest boards: **Anthropic 1. OpenAI 0. DeepMind 0.** |

That last row is the whole reason this repo exists. The lists are enormous and
still do not contain the jobs at the top of the market.

## What we do differently

**1 · A hard company bar, written down.**
[145 employers](data/companies.yaml), each admitted by a published
[inclusion test](docs/COMPANY_BAR.md). Staffing agencies, annotation vendors and
city-spammed requisitions are excluded by policy. **Max 3 rows per company**, so
one large campus program cannot flood a board.

**2 · `first_seen` is immutable.**
Written once, never overwritten by a re-scrape. When we say a role is 4 days
old, it is 4 days old. We publish `first_seen`, `last_verified` and `closed_at`
separately so you can check us.

**3 · Sponsorship is resolved, not defaulted.**
Every posting is parsed for its actual work-authorization clause →
`sponsors` / `no-sponsorship` / `citizenship-required` / `security-clearance`.
When a posting is silent we say **unknown**, because that is the truth.
[SPONSORSHIP.md](docs/SPONSORSHIP.md) cross-checks employer behavior against
public DOL H-1B filings — and overturns two widely repeated myths.

**4 · A PhD-track board that actually exists.**
Research Scientist, Research Engineer, MTS, residencies and fellowships are
split out from SWE. An MIT PhD does not want to scroll past 842 hardware reqs.

**5 · A failed scrape never closes a role.**
If a board times out, we learn nothing about that company — we do not conclude
it closed every position. This is the most common way these lists go quietly
wrong.

**6 · A machine-readable URL that resolves.**
[`data/v1/jobs.json`](data/v1/jobs.json) is versioned, [schema'd](data/v1/schema.json)
and documented, with [NDJSON](data/v1/jobs.ndjson) and an
[Atom feed](data/v1/feed.xml) alongside. One competitor advertises a JSON path
that 404s; another ships an 11 MB undocumented dump on a side branch.

---

## Boards

| Board | Who it is for |
|:--|:--|
| [**New Grad SWE**](boards/NEW_GRAD_SWE.md) | Full-time entry-level software engineering, US |
| [**AI / ML Research**](boards/AI_RESEARCH.md) | Research Scientist / Engineer, MTS, residencies — the PhD track |
| [**Quant**](boards/QUANT.md) | Campus + new grad at elite quant/HFT. Highest comp band here |
| [**Internships**](boards/INTERNSHIPS.md) | Summer 2027 SWE and research internships |

**Legend** — 🌏 sponsors visas · 🛂 no sponsorship · 🇺🇸 US citizenship required ·
🔒 clearance required · `·` posting doesn't say · 🎓 PhD · 📗 MS preferred

## Beyond the listings

| | |
|:--|:--|
| [**The Playbook**](docs/PLAYBOOK.md) | When each company opens, which OA platform you will face, and the PhD programs that never appear on a job board |
| [**Compensation**](docs/COMPENSATION.md) | Sourced new-grad comp, the TC-vs-DOL-base distinction, and the measurable PhD premium |
| [**Sponsorship**](docs/SPONSORSHIP.md) | What H-1B filings actually show. Jane Street and HRT sponsor heavily; Anduril is the real outlier |
| [**The Company Bar**](docs/COMPANY_BAR.md) | The inclusion test, the tiers, and what we refuse to list |

---

## How it works

```
data/companies.yaml   145 employers · 131 live boards · every token verified
        │
        ▼
   fetch (6-hourly, GitHub Actions, 12 workers)
   greenhouse · ashby · lever · workday · amazon · eightfold
        │   per-company isolation — one 500 cannot fail the run
        ▼
   classify   US-only → drop senior/non-technical → track → degree → sponsorship
        │     publishes WHY each row was rejected, never drops silently
        ▼
   lifecycle  first_seen (immutable) · last_verified · closed_at
        │     closure requires a SUCCESSFUL fetch that omitted the role
        ▼
   render     4 markdown boards · jobs.json · jobs.ndjson · feed.xml
              stats.json · CHANGELOG.md
```

Run it yourself:

```bash
pip install -r requirements-dev.txt
make test                          # 144 tests, no network
make refresh                       # hits every board, rewrites all outputs
python -m eliteboard.cli doctor    # which boards can't be fetched, and why
```

## Using the data

```bash
BASE=https://raw.githubusercontent.com/ricsign/Ricsign-New-Grads-Jobs-2027/main/data/v1

# Tier-0 roles that sponsor visas
curl -s $BASE/jobs.json | jq -r '.jobs[]
  | select(.sponsorship=="sponsors" and .company_tier==0)
  | "\(.company_name)\t\(.title)\t\(.apply_url)"'

# PhD-track research roles
curl -s $BASE/jobs.json | jq -r '.jobs[]
  | select(.track=="ai-research") | "\(.company_name) — \(.title)"'
```

Fields are documented in [`schema.json`](data/v1/schema.json). Within API v1 we
add fields but never remove or repurpose them.

## Honest limitations

We would rather state these than have you discover them.

- **Six elite firms have no fetchable board.** Jane Street, Citadel, Citadel
  Securities, D. E. Shaw, Two Sigma and Optiver run custom JS-rendered boards
  with no public JSON. They are in the registry with direct links and a written
  explanation — listed honestly rather than silently omitted.
  `python -m eliteboard.cli doctor` prints the full list.
- **Google, Meta, Apple and Microsoft are link-only** for now. Google's job
  results path is disallowed by its robots.txt, which we respect. The other
  three need bespoke adapters — contributions very welcome.
- **`unknown` sponsorship is common**, because many postings genuinely do not
  say. We will not invent a value to make a column look complete.
- **Compensation is sparse.** We show it when the ATS publishes a real band
  (Ashby often does) and leave it blank otherwise, rather than putting an
  estimate next to a real number.

## Contributing

- **A company that should be here** → [open a company issue](../../issues/new?template=company.yml). Argue that it clears [the bar](docs/COMPANY_BAR.md).
- **A dead link** → [report it](../../issues/new?template=dead-link.yml). The daily linkcheck catches hard 404s but misses soft ones.
- **A missing adapter** → Apple, Microsoft, Meta and Snowflake are the highest-value gaps. See [CONTRIBUTING.md](CONTRIBUTING.md).
- **A sourced comp number** for anything in the [unsourced list](docs/COMPENSATION.md#unsourced--deliberately-blank).

## Related

Genuinely useful, broader in scope, different tradeoff:
[SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions) ·
[SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships) ·
[speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs) ·
[northwesternfintech/2027QuantInternships](https://github.com/northwesternfintech/2027QuantInternships)

If you want maximum coverage, use those. If you want the top of the market with
metadata you can trust, use this.

---

<div align="center">

MIT licensed · not affiliated with any listed employer · apply links point to
official career pages only

**If this helped, a ⭐ helps someone else find it.**

</div>
