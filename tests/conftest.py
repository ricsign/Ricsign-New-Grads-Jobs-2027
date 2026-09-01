from __future__ import annotations

import pytest

from eliteboard.models import RawPosting
from eliteboard.registry import Company


def make_company(**kw) -> Company:
    base = dict(
        name="Anthropic", slug="anthropic", tier=0, category="ai-lab",
        ats="greenhouse", token="anthropic",
        careers_url="https://www.anthropic.com/careers", verified_at="2026-09-01",
    )
    base.update(kw)
    return Company(**base)


def make_posting(title: str, *, description: str = "", locations=None, **kw) -> RawPosting:
    return RawPosting(
        company_slug=kw.pop("company_slug", "anthropic"),
        company_name=kw.pop("company_name", "Anthropic"),
        source=kw.pop("source", "greenhouse"),
        external_id=kw.pop("external_id", "1"),
        title=title,
        apply_url=kw.pop("apply_url", "https://example.com/apply"),
        locations=locations if locations is not None else ["San Francisco, CA"],
        description=description,
        **kw,
    )


@pytest.fixture
def company():
    return make_company()


@pytest.fixture
def quant_company():
    return make_company(
        name="Jump Trading", slug="jump-trading", tier=1, category="quant",
        token="jumptrading", careers_url="https://www.jumptrading.com/careers/",
    )
