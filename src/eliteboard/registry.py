"""Loading and validation for the curated company registry.

The registry (``data/companies.yaml``) is the single gate that decides which
employers may appear anywhere in this repo. Keeping that decision in one
reviewable file - rather than in scraper heuristics - is what keeps the boards
free of the staffing agencies and annotation shops that dominate every other
new-grad list.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "data" / "companies.yaml"
PROGRAMS_PATH = REPO_ROOT / "data" / "programs.yaml"

VALID_ATS = {"greenhouse", "ashby", "lever", "workday", "amazon", "eightfold", "none"}
VALID_TIERS = {0, 1, 2}
VALID_CATEGORIES = {
    "ai-lab",
    "big-tech",
    "quant",
    "infra",
    "dev-tools",
    "fintech",
    "consumer",
    "robotics",
    "security",
    "bio",
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class Company:
    name: str
    slug: str
    tier: int
    category: str
    ats: str
    careers_url: str
    token: str | None = None
    enabled: bool = True
    note: str | None = None
    disabled_reason: str | None = None
    verified_at: str | None = None
    workday: dict[str, str] | None = None
    eightfold_host: str | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_fetchable(self) -> bool:
        """True when an adapter can actually pull postings for this company."""
        return self.enabled and self.ats != "none" and bool(self.token)

    @property
    def tier_label(self) -> str:
        return {0: "Tier 0", 1: "Tier 1", 2: "Tier 2"}[self.tier]


class RegistryError(ValueError):
    """Raised when the registry violates an invariant CI must never let through."""


def _coerce(raw: dict[str, Any]) -> Company:
    known = {
        "name", "slug", "tier", "category", "ats", "careers_url", "token",
        "enabled", "note", "disabled_reason", "verified_at", "workday",
        "eightfold_host",
    }
    return Company(
        name=raw["name"],
        slug=raw["slug"],
        tier=raw["tier"],
        category=raw["category"],
        ats=raw.get("ats", "none"),
        careers_url=raw["careers_url"],
        token=raw.get("token"),
        enabled=raw.get("enabled", True),
        note=raw.get("note"),
        disabled_reason=raw.get("disabled_reason"),
        verified_at=raw.get("verified_at"),
        workday=raw.get("workday"),
        eightfold_host=raw.get("eightfold_host"),
        extra={k: v for k, v in raw.items() if k not in known},
    )


def load_registry(path: Path | None = None) -> list[Company]:
    """Parse, validate and return every company in the registry.

    Validation is strict on purpose. A typo'd ATS token produces an adapter
    that silently returns nothing, which is exactly the failure mode that makes
    competing repos rot; we would rather fail the build.
    """
    path = path or REGISTRY_PATH
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or "companies" not in doc:
        raise RegistryError(f"{path} has no top-level 'companies' key")

    companies = [_coerce(raw) for raw in doc["companies"]]
    _validate(companies)
    return companies


def _validate(companies: list[Company]) -> None:
    problems: list[str] = []

    for c in companies:
        if not SLUG_RE.match(c.slug):
            problems.append(f"{c.name}: slug {c.slug!r} must be lowercase kebab-case")
        if c.tier not in VALID_TIERS:
            problems.append(f"{c.name}: tier {c.tier} not in {sorted(VALID_TIERS)}")
        if c.category not in VALID_CATEGORIES:
            problems.append(f"{c.name}: unknown category {c.category!r}")
        if c.ats not in VALID_ATS:
            problems.append(f"{c.name}: unknown ats {c.ats!r}")
        if not c.careers_url.startswith("https://"):
            problems.append(f"{c.name}: careers_url must be https")

        # An entry either fetches, or explains in writing why it does not.
        if c.enabled and c.ats != "none" and not c.token:
            problems.append(f"{c.name}: enabled with ats={c.ats} but no token")
        if not c.enabled and not c.disabled_reason:
            problems.append(f"{c.name}: disabled entries must carry a disabled_reason")
        if c.enabled and c.ats != "none" and not c.verified_at:
            problems.append(f"{c.name}: fetchable entries must record verified_at")
        if c.ats == "workday" and not (c.workday and {"tenant", "wd", "site"} <= c.workday.keys()):
            problems.append(f"{c.name}: workday entries need tenant/wd/site")
        if c.ats == "eightfold" and not c.eightfold_host:
            problems.append(f"{c.name}: eightfold entries need eightfold_host")

    for key, label in ((lambda c: c.slug, "slug"), (lambda c: c.name, "name")):
        dupes = [v for v, n in Counter(key(c) for c in companies).items() if n > 1]
        if dupes:
            problems.append(f"duplicate {label}s: {sorted(dupes)}")

    if problems:
        raise RegistryError("registry validation failed:\n  - " + "\n  - ".join(problems))


def fetchable(companies: list[Company]) -> list[Company]:
    return [c for c in companies if c.is_fetchable]


def by_slug(companies: list[Company]) -> dict[str, Company]:
    return {c.slug: c for c in companies}


def load_programs(path: Path | None = None) -> list[dict[str, Any]]:
    """Hand-curated research programs that have no ATS presence.

    Kept deliberately separate from the company registry: these are not
    requisitions, they cannot be scraped, and staleness here cannot be detected
    automatically - which is why every entry carries a verified_at and a note.
    """
    path = path or PROGRAMS_PATH
    if not path.exists():
        return []
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    programs = doc.get("programs", [])
    for program in programs:
        missing = {"name", "org", "url", "kind", "verified_at"} - program.keys()
        if missing:
            raise RegistryError(f"program {program.get('name')!r} missing {missing}")
        if not program["url"].startswith("https://"):
            raise RegistryError(f"program {program['name']!r} url must be https")
    return programs
