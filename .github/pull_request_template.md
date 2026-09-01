## What changes

<!-- One or two sentences. -->

## Why

<!-- What problem does this solve for someone using the boards? -->

## Checklist

- [ ] `make lint && make test` passes
- [ ] If I added a company: I fetched its ATS token and it returned a **non-zero** count
- [ ] If I added an adapter: there is a fixture in `tests/fixtures/` and tests do not hit the network
- [ ] If I changed the classifier: I added the **real posting title, verbatim** as a test case
- [ ] I did not hand-edit generated files (`boards/*.md`, `data/v1/*`, `CHANGELOG.md`)
