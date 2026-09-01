"""The registry is the product, so its invariants are tested hardest."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from eliteboard.registry import (
    Company,
    RegistryError,
    by_slug,
    fetchable,
    load_registry,
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "companies.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


GOOD = """
    schema_version: 1
    companies:
      - name: Anthropic
        slug: anthropic
        tier: 0
        category: ai-lab
        ats: greenhouse
        token: anthropic
        careers_url: "https://www.anthropic.com/careers"
        verified_at: "2026-09-01"
"""


class TestRealRegistry:
    def test_loads_and_validates(self):
        companies = load_registry()
        assert len(companies) >= 100

    def test_every_fetchable_company_records_when_it_was_verified(self):
        # Guards the failure mode this whole project exists to avoid: a token
        # committed on faith, quietly returning nothing forever.
        for c in fetchable(load_registry()):
            assert c.verified_at, f"{c.name} is fetchable but has no verified_at"

    def test_every_disabled_company_explains_itself(self):
        for c in load_registry():
            if not c.enabled:
                assert c.disabled_reason, f"{c.name} is disabled with no reason given"

    def test_disabled_companies_still_carry_a_usable_link(self):
        # A company we cannot scrape is still a company a candidate should see.
        for c in load_registry():
            if not c.enabled:
                assert c.careers_url.startswith("https://")

    def test_frontier_labs_are_present_and_fetchable(self):
        # The entire wedge. Competing repos carry ~1 Anthropic row and 0 OpenAI.
        index = by_slug(load_registry())
        for slug in ("anthropic", "openai", "databricks", "scale-ai", "xai"):
            assert index[slug].is_fetchable, f"{slug} must be fetchable"

    def test_split_campus_boards_are_registered_separately(self):
        # CTC and Radix post campus roles on a different Greenhouse board than
        # their lateral roles. Fetching only the main token misses every new
        # grad role these firms open.
        index = by_slug(load_registry())
        assert index["ctc-campus"].token == "chicagotradingcampus"
        assert index["ctc-lateral"].token == "chicagotrading"
        assert index["radix-university"].token == "radixuniversity"


class TestValidation:
    def test_accepts_a_well_formed_entry(self, tmp_path):
        assert len(load_registry(_write(tmp_path, GOOD))) == 1

    @pytest.mark.parametrize(
        ("mutation", "expected"),
        [
            ("slug: Anthropic_Inc", "kebab-case"),
            ("tier: 7", "tier"),
            ("category: pets", "category"),
            ("ats: telepathy", "ats"),
            ('careers_url: "http://insecure.example"', "https"),
        ],
    )
    def test_rejects_malformed_fields(self, tmp_path, mutation, expected):
        key = mutation.split(":")[0]
        body = "\n".join(
            f"    {mutation}" if line.strip().startswith(f"{key}:") else line
            for line in textwrap.dedent(GOOD).splitlines()
        )
        with pytest.raises(RegistryError, match=expected):
            load_registry(_write(tmp_path, body))

    def test_rejects_enabled_entry_with_no_token(self, tmp_path):
        body = textwrap.dedent(GOOD).replace("    token: anthropic\n", "")
        with pytest.raises(RegistryError, match="no token"):
            load_registry(_write(tmp_path, body))

    def test_rejects_duplicate_slugs(self, tmp_path):
        body = textwrap.dedent(GOOD)
        body += body.split("companies:")[1]
        with pytest.raises(RegistryError, match="duplicate slug"):
            load_registry(_write(tmp_path, body))

    def test_rejects_workday_entry_missing_tenant(self, tmp_path):
        body = textwrap.dedent(GOOD).replace("ats: greenhouse", "ats: workday")
        with pytest.raises(RegistryError, match="tenant"):
            load_registry(_write(tmp_path, body))


class TestCompany:
    def test_disabled_company_is_not_fetchable(self):
        c = Company(
            name="X", slug="x", tier=1, category="infra", ats="greenhouse",
            careers_url="https://x.example", token="x", enabled=False,
        )
        assert not c.is_fetchable
