"""eliteboard - a curated, continuously verified job board for elite CS candidates.

Design goals, in priority order:

1. Signal over volume. A hard, versioned company bar (``data/companies.yaml``)
   decides what is even eligible. We would rather show 300 real roles at 150
   great companies than 15,000 rows nobody reads.
2. Honest freshness. ``first_seen`` is immutable and never overwritten by a
   re-scrape, so "posted 4d ago" means posted, not re-observed.
3. Resolved metadata. Sponsorship, degree requirement, and track are parsed
   from the posting itself rather than defaulted to an unhelpful "Other".
4. Machine-readable by contract. ``data/v1/jobs.json`` is a stable, schema'd,
   documented URL - not an undocumented internal dump.
"""

__version__ = "1.0.0"
