# The 2027 Playbook

A job list tells you what is open. This tells you when to move, what you will be
tested on, and which doors exist that are not on any board.

---

## 1. The calendar is the whole game

The structural fact that decides most outcomes: **finance recruits 12–18 months
ahead, everyone else 6–9, and almost all of tech is rolling rather than batch.**
Reviewers work applications as they arrive and stop when the class is full
([internlist](https://internlist.org/resources/internship-recruiting-timeline-by-industry)).

That has a blunt implication. **Applying in week one of a posting is worth more
than a materially stronger application in week six.** Waiting for a campus
career fair is now a structural disadvantage, not a neutral choice.

### Typical windows

Quant firms open earliest — August for the following summer — and the best desks
fill first. For scale: Citadel took [fewer than 300 interns from over 108,000
applications](https://youngandcalculated.substack.com/p/how-to-land-a-quant-internship-in),
roughly 0.4%.

| Company | Opens | Review style |
|:--|:--|:--|
| Quant / HFT | **Jul–Aug 2026** | Rolling, fills fast |
| Amazon | Jul–Aug 2026 | Rolling — earliest big tech |
| Databricks, Stripe, Salesforce | Early Aug 2026 | Rolling |
| Microsoft | Mid-Aug 2026 | Rolling |
| Palantir | Late Aug–Sep 2026 | Rolling; slots gone before Nov |
| NVIDIA | Aug–Oct 2026 | Short windows — Ignite ran **13 days** |
| Meta | Early Sep 2026 | Rolling into Dec |
| Apple | Sep–Nov 2026 | Rolling, team-by-team |
| Google | ~Mid-Oct 2026 | **2–4 week burst** |
| Startups / labs | Dec 2026–Mar 2027 | Genuinely later cycle |

> Company dates other than the quant row are **aggregator projections**
> ([extern](https://www.extern.com/post/tech-internships-summer-2027-guide)), not
> company statements. The authoritative answer is the live board — which is what
> [our boards](../README.md#boards) are for.

**The practical read:** if it is September and you have not applied to quant, you
are late. If it is September and you have not applied to startups, you are early.

---

## 2. What you will actually be tested on

Which online-assessment platform a company uses tells you what to practice.

| Platform | Companies |
|:--|:--|
| **CodeSignal** | HRT (4 questions, 600-point scale), Capital One, Roblox, ByteDance, Robinhood, Brex, Dropbox |
| **HackerRank** | Citadel, Millennium, Goldman Sachs, JPMorgan, Microsoft (some US SWE intern teams), Snowflake |
| **Codility** | Microsoft, LSEG, Chicago Trading Company |
| **CoderPad** | Figma (winter SWE intern), monday.com, Cresta |

Source: [PracHub OA provider survey](https://prachub.com/resources/which-companies-use-codesignal-hackerrank-codility-or-coderpad-in-2027).
These change; treat as a prior, not gospel. We deliberately omit Karat's company
list because we could not source it.

**The one that is different:** CodeSignal's scored format (notably HRT's) is not
pass/fail — you are ranked on a scale. Partial credit is real, so submitting a
working brute force beats an unfinished optimal solution. That is the opposite
of the usual interview advice, and people lose offers to it.

---

## 3. Doors that are not on any job board

If you are a PhD student, some of the best-paying, least-contested paths are
programs, not requisitions. They will never appear on a scraped list.

| Program | What it is | Terms |
|:--|:--|:--|
| [Anthropic Fellows](https://alignment.anthropic.com/2025/anthropic-fellows-program-2026/) | 4-month mentored research projects | **$3,850/week** + ~$15k/mo compute. Explicitly *no PhD, prior ML experience, or publications required.* |
| [OpenAI Residency](https://openai.com/residency/) | 6-month transition into research | **$18,333/month**, SF onsite 3+ days, rolling starts, sponsorship offered. Cannot be enrolled in school. |
| [Google DeepMind Student Researcher](https://deepmind.google/student-researcher-program/) | 12–24 week paid research placement | BS/MS/PhD eligible. One application considers you across all Google AI teams. |
| [Google PhD Fellowship](https://research.google/programs-and-events/phd-fellowship/) | Up to 2 years at **$85k/yr** | **University-nominated only — you cannot apply directly.** Ask your department who nominates. |
| [NVIDIA Graduate Fellowship](https://blogs.nvidia.com/blog/applications-open-graduate-fellowship-awards-2025/) | Up to **$60,000** | Requires ≥1 year of PhD study **and a prior in-person NVIDIA Research summer internship.** Plan two years out. |

Two of these have non-obvious gates worth internalizing early: the Google
fellowship is nominated, not applied for, and the NVIDIA fellowship requires an
internship you must already have done. Both are decisions you make in year one
of a PhD, not year four.

[Meta AI Residency](https://ai.meta.com/join-us/residency-program/) still shows
"applications are now closed" against a 2023 cohort — treat it as dormant until
that changes.

---

## 4. The return-offer math

The only credibly sourced figure is
[NACE's 2024 report](https://www.naceweb.org/talent-acquisition/trends-and-predictions/intern-conversion-rate-fell-fueled-by-lower-offer-rate):
**53% conversion**, down from ~58%, on a **~67% offer rate** — a five-year low.

Any company-specific tech conversion rate you see quoted is anecdotal. None are
published. If someone tells you "company X converts 90%", ask where that came
from.

The useful implication: an internship is roughly a coin flip toward a full-time
offer, not a guarantee. Plan to run a full-time search in parallel.

---

## 5. How to actually use this repo

1. **Subscribe, don't browse.** Watch the repo, or point a reader at
   [`data/v1/feed.xml`](../data/v1/feed.xml). Rolling review means being early
   beats being thorough.
2. **Filter by sponsorship first** if you need it — see
   [SPONSORSHIP.md](SPONSORSHIP.md). It eliminates more of the list than any
   other filter, and doing it last wastes weeks.
3. **PhD students: start at [AI_RESEARCH.md](../boards/AI_RESEARCH.md)**, not
   the SWE board. The comp premium is real and measurable
   ([COMPENSATION.md](COMPENSATION.md)).
4. **Check `Age`.** Ours is time since we first saw the posting. A role at 1d on
   a rolling req is a materially different opportunity than one at 60d.
5. **Query it as data.** `data/v1/jobs.json` is schema'd and stable:

   ```bash
   curl -s https://raw.githubusercontent.com/ricsign/Ricsign-New-Grads-Jobs-2027/main/data/v1/jobs.json \
     | jq -r '.jobs[] | select(.sponsorship=="sponsors" and .company_tier==0)
              | "\(.company_name)\t\(.title)\t\(.apply_url)"'
   ```

---

## 6. Things worth saying plainly

**Applying to 400 roles is a worse strategy than applying to 40 well.** These
boards are curated so that the list you are working from is short enough to
treat each application seriously. That is the point of the company bar.

**A referral moves you past resume screen, not past the loop.** It is worth
asking for, and it is not worth agonizing over if you do not have one.

**Prestige is not the same as fit.** Tier 0 here means "hard to get into and
pays extremely well". It does not mean "best place for you to work". A team
where you will be mentored well matters more over a career than the logo, and
this repo cannot rank that for you.
