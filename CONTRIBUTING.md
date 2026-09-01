# Contributing

The listings refresh themselves. What actually needs humans is **the company
bar**, **broken links**, and **the four missing adapters**.

## Add or remove a company

Open an issue with the `company` template. Additions need one concrete argument
that the company clears [the bar](docs/COMPANY_BAR.md) — "they're hiring" is not
an argument. Removals are welcome and held to the same standard.

If you want to open the PR yourself, add one entry to `data/companies.yaml`:

```yaml
- { name: Example Labs, slug: example-labs, tier: 1, category: ai-lab,
    ats: greenhouse, token: examplelabs,
    careers_url: "https://example.com/careers", verified_at: "2026-09-01" }
```

**Verify the token before you commit it.** An unverified token produces an
adapter that silently returns nothing forever, which is the exact rot this repo
exists to avoid. CI will reject an entry without `verified_at`.

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/<TOKEN>/jobs?content=false" | jq '.meta.total'
curl -s "https://api.ashbyhq.com/posting-api/job-board/<TOKEN>"                  | jq '.jobs | length'
curl -s "https://api.lever.co/v0/postings/<TOKEN>?mode=json"                     | jq 'length'
```

A board that returns HTTP 200 with **zero** postings is not verified — two live
Ashby boards do exactly this. Check the count, not the status code.

## Write a missing adapter

Highest-value gaps, roughly in order:

| Target | Why it is hard |
|:--|:--|
| **Apple** | `POST jobs.apple.com/api/role/search` needs an `X-Apple-CSRF-Token` scraped per session |
| **Microsoft** | `gcsservices.careers.microsoft.com/search/api/v1/search` is undocumented; needs verification from CI |
| **Snowflake / Cisco** | Phenom People `POST /widgets` — one adapter unlocks several employers |
| **Millennium** | Eightfold tenant; our adapter exists, the endpoint shape needs confirming |

An adapter is one class with a `source` attribute and a `fetch(client, company)`
method returning `list[RawPosting]`. Add it to `ADAPTERS` in
`src/eliteboard/adapters/__init__.py`, record a fixture in `tests/fixtures/`,
and test against the fixture — **not** against the live network, so CI stays
deterministic.

We do not accept adapters that bypass a `robots.txt` disallow. Google's job
results path is disallowed, which is why Google is link-only.

## Improve the classifier

`src/eliteboard/classify.py` decides what reaches a board. If you find a real
posting that is wrongly kept or wrongly dropped, that is a bug worth a PR —
please add the **real title verbatim** to `tests/test_classify.py`. Every case
in `TestRealWorldTitles` was observed on a live board; synthetic titles would
not have caught `Campus Full Time 2027 - Quantitative Trader`.

## Ground rules

- `make lint && make test` must pass. 112 tests, no network required.
- Do not hand-edit `boards/*.md`, `data/v1/*` or `CHANGELOG.md` — they are
  generated and your changes will be overwritten on the next refresh.
- No affiliate links, referral codes, or redirects through third-party trackers.
  Apply links point at official career pages, and that is not negotiable.
- No scraping behind authentication, and no CAPTCHA circumvention.
