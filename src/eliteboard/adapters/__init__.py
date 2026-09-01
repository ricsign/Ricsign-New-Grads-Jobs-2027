"""Adapter registry - maps an ATS name from companies.yaml to an implementation."""

from __future__ import annotations

from .amazon import AmazonAdapter
from .ashby import AshbyAdapter
from .base import Adapter, FetchResult, make_client, request_json
from .eightfold import EightfoldAdapter
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter
from .workday import WorkdayAdapter

ADAPTERS: dict[str, Adapter] = {
    "greenhouse": GreenhouseAdapter(),
    "ashby": AshbyAdapter(),
    "lever": LeverAdapter(),
    "workday": WorkdayAdapter(),
    "amazon": AmazonAdapter(),
    "eightfold": EightfoldAdapter(),
}

__all__ = [
    "ADAPTERS",
    "Adapter",
    "FetchResult",
    "make_client",
    "request_json",
]


def get_adapter(ats: str) -> Adapter:
    try:
        return ADAPTERS[ats]
    except KeyError as exc:
        raise KeyError(f"no adapter registered for ats={ats!r}") from exc
