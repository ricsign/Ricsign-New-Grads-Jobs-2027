"""Command line entrypoint: `eliteboard refresh | render | validate | doctor`."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import pipeline
from .registry import RegistryError, fetchable, load_registry


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname).1s %(message)s",
        stream=sys.stderr,
    )


def cmd_refresh(args) -> int:
    result = pipeline.run(workers=args.workers, check_links=not args.no_verify)
    written = pipeline.write_outputs(result)

    report = result.report
    print(f"\n{'=' * 64}")
    print(f"  live roles        {len(result.jobs)}")
    print(f"  newly added       {len(result.newly_added)}")
    print(f"  newly closed      {len(result.newly_closed)}")
    if report:
        print(f"  boards ok         {len(report.ok)}/{len(report.results)}")
        print(f"  boards empty      {len(report.empty)}")
        print(f"  boards failed     {len(report.failed)}")
        print(f"  postings fetched  {len(report.postings)}")
    if result.link_health:
        lh = result.link_health
        hidden = sum(1 for j in result.jobs if j.link_status in ("dead", "closed"))
        print(f"  links checked     {lh.get('checked', 0)}")
        print(f"    resolving       {lh.get('ok', 0)}  ({lh.get('resolving_pct', 0)}% of conclusive)")
        print(f"    dead (404/410)  {lh.get('dead', 0)}")
        print(f"    closed (soft)   {lh.get('closed', 0)}")
        print(f"    bot-blocked     {lh.get('blocked', 0)}   (kept - not a verdict)")
        print(f"  rows hidden       {hidden}")
    print(f"{'=' * 64}")
    if result.rejections:
        print("  filtered out:")
        for reason, count in result.rejections.most_common(10):
            print(f"    {count:>6}  {reason}")
    if report and report.failed:
        print("  failures:")
        for failure in report.failed:
            print(f"    {failure.company.name} ({failure.company.ats}): {failure.error}")
    print(f"\n  wrote {len(written)} files")
    # A refresh where most boards fail should fail the job, not commit a
    # near-empty board over a good one.
    if report and report.results and report.success_rate < 0.5:
        print("\nERROR: fewer than half of boards fetched successfully", file=sys.stderr)
        return 1
    return 0


def cmd_validate(args) -> int:
    try:
        companies = load_registry()
    except RegistryError as exc:
        print(f"registry invalid:\n{exc}", file=sys.stderr)
        return 1
    print(f"registry OK: {len(companies)} companies, {len(fetchable(companies))} fetchable")

    jobs_path = pipeline.API_DIR / "jobs.json"
    if jobs_path.exists():
        doc = json.loads(jobs_path.read_text())
        required = {"uid", "company_name", "title", "apply_url", "track", "first_seen"}
        for job in doc.get("jobs", []):
            missing = required - job.keys()
            if missing:
                print(f"jobs.json: {job.get('uid')} missing {missing}", file=sys.stderr)
                return 1
        print(f"jobs.json OK: {doc.get('count', 0)} live roles")
    return 0


def cmd_doctor(args) -> int:
    """Report which boards are configured but not currently fetchable."""
    companies = load_registry()
    disabled = [c for c in companies if not c.is_fetchable]
    print(f"{len(companies)} companies · {len(companies) - len(disabled)} fetchable\n")
    for company in sorted(disabled, key=lambda c: (c.tier, c.name)):
        reason = company.disabled_reason or "no ATS token"
        print(f"  [T{company.tier}] {company.name:<26} {reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eliteboard")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh", help="fetch every board and rewrite all outputs")
    refresh.add_argument("--workers", type=int, default=12)
    refresh.add_argument(
        "--no-verify",
        action="store_true",
        help="skip probing apply links (faster; used for local iteration only)",
    )
    refresh.set_defaults(func=cmd_refresh)

    sub.add_parser("validate", help="validate the registry and published data").set_defaults(
        func=cmd_validate
    )
    sub.add_parser("doctor", help="list companies that cannot currently be fetched").set_defaults(
        func=cmd_doctor
    )

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
