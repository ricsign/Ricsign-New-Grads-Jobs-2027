"""The curated programs registry.

These entries cannot be validated against a live source the way an ATS token
can, so the tests enforce the things that keep hand-maintained data honest:
every entry is dated, every URL is https, and the two programs with non-obvious
eligibility gates keep saying so.
"""

from __future__ import annotations

import textwrap

import pytest

from eliteboard.registry import RegistryError, load_programs
from eliteboard.render import render_programs_json, render_programs_section


class TestRealRegistry:
    def test_loads(self):
        assert len(load_programs()) >= 5

    def test_every_program_is_dated_and_https(self):
        for p in load_programs():
            assert p["verified_at"], f"{p['name']} has no verified_at"
            assert p["url"].startswith("https://")

    def test_the_two_traps_are_documented(self):
        # Both are year-one decisions that people routinely learn about in
        # year four. If the wording is ever lost, the entry loses its point.
        by_name = {p["name"]: p for p in load_programs()}
        google = by_name["Google PhD Fellowship"]
        assert "nominat" in google["eligibility"].lower()
        nvidia = by_name["NVIDIA Graduate Fellowship"]
        assert "internship" in nvidia["eligibility"].lower()

    def test_dormant_programs_are_marked_not_deleted(self):
        # Meta's residency is dormant. Listing it tells a reader not to wait
        # for it; deleting it just means they wonder.
        dormant = [p for p in load_programs() if p.get("status") == "dormant"]
        assert dormant and all(p.get("note") for p in dormant)


class TestValidation:
    def test_rejects_undated_entry(self, tmp_path):
        f = tmp_path / "programs.yaml"
        f.write_text(textwrap.dedent("""
            programs:
              - name: X
                org: Y
                kind: fellowship
                url: "https://example.com"
        """))
        with pytest.raises(RegistryError, match="verified_at"):
            load_programs(f)

    def test_rejects_insecure_url(self, tmp_path):
        f = tmp_path / "programs.yaml"
        f.write_text(textwrap.dedent("""
            programs:
              - name: X
                org: Y
                kind: fellowship
                url: "http://example.com"
                verified_at: "2026-09-01"
        """))
        with pytest.raises(RegistryError, match="https"):
            load_programs(f)

    def test_missing_file_is_not_fatal(self, tmp_path):
        assert load_programs(tmp_path / "nope.yaml") == []


class TestRendering:
    def test_section_links_every_program(self):
        md = render_programs_section(load_programs())
        for p in load_programs():
            assert p["url"] in md

    def test_empty_input_renders_nothing(self):
        assert render_programs_section([]) == ""

    def test_json_is_wellformed(self):
        import json

        doc = json.loads(render_programs_json(load_programs()))
        assert doc["count"] == len(doc["programs"]) >= 5
