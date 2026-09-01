"""Turn a raw posting into a classified one.

Four judgments are made here, in this order:

1. **Eligibility**  - is this an early-career US role at all? Everything else
   is discarded. Most of the value of this repo is in what this step throws away.
2. **Track**        - which board it belongs on.
3. **Degree**       - what the posting actually asks for.
4. **Sponsorship**  - the work-authorization posture, parsed from the posting.

On (4): competing boards default ~99% of rows to an unhelpful "Other". For an
international MS or PhD student that field is the first filter applied to any
list, so we resolve it from the posting text and, when the text is silent, say
UNKNOWN rather than implying anything.
"""

from __future__ import annotations

import re

from .locations import any_us, us_only
from .models import Degree, RawPosting, Sponsorship, Track
from .registry import Company

# --------------------------------------------------------------------------
# Seniority. Anything matching is not an early-career role, full stop.
# `\bII+\b` catches "Engineer II"/"III"; `\bI\b` deliberately does NOT, because
# "Software Engineer I" and "SDE I" are genuine new-grad levels.
# --------------------------------------------------------------------------
SENIOR = re.compile(
    r"\b(senior|sr\.?|staff|principal|distinguished|lead|architect|manager|"
    r"director|head\s+of|vp|vice\s+president|chief|fellow\s+engineer|"
    r"experienced|II+|IV|V|[3-9]\+?\s*years)\b",
    re.I,
)

INTERN = re.compile(
    r"\b(intern|internship|co[-\s]?op|summer\s+analyst|apprentice|"
    r"student\s+(?:researcher|worker|program)|placement\s+student)\b",
    re.I,
)

NEW_GRAD = re.compile(
    r"\b(new\s+grad(?:uate)?|university\s+grad(?:uate)?|recent\s+grad(?:uate)?|"
    r"campus\s+(?:hire|full[-\s]?time)?|early\s+career|entry[-\s]?level|"
    r"graduate\s+(?:program|programme|scheme|analyst|engineer|developer|trader|"
    r"researcher)|grad\s+program|rotational\s+program|"
    r"engineer\s+i\b|developer\s+i\b|sde\s+i\b|associate\s+(?:engineer|developer)|"
    r"20(?:26|27|28)\s+start|start\s+20(?:26|27|28)|junior)\b",
    re.I,
)

# The negative lookbehind matters: "Systems Engineer (Data Residency)" is a
# distributed-systems role, and without it that posting lands on the PhD board.
RESEARCH = re.compile(
    r"\b(research\s+(?:scientist|engineer|intern|fellow)|member\s+of\s+technical\s+staff|"
    r"\bmts\b|applied\s+scientist|research\s+resident|(?<!data\s)(?<!tax\s)residency|"
    r"ai\s+resident|phd\s+(?:researcher|scientist))\b",
    re.I,
)

QUANT = re.compile(
    r"\b(quant(?:itative)?(?:\s+(?:trader|researcher|developer|analyst|strategist))?|"
    r"trading\s+(?:analyst|engineer)|trader|systematic\s+strategies)\b",
    re.I,
)

# Roles that are not software/research/quant even at an elite employer.
NON_TECH = re.compile(
    r"\b(recruit(?:er|ing)|sales|account\s+(?:executive|manager)|marketing|"
    r"customer\s+success|support\s+(?:specialist|engineer\s+i?i)|"
    r"people\s+operations|human\s+resources|legal\s+counsel|paralegal|"
    r"accountant|accounting|controller|payroll|facilities|executive\s+assistant|"
    r"office\s+manager|content\s+(?:writer|strategist)|social\s+media|"
    r"brand\s+designer|graphic\s+designer|technician|warehouse|driver|"
    r"security\s+(?:guard|officer)|physician|nurse|teacher)\b",
    re.I,
)

# Prefix-matched on purpose. A trailing \b here silently rejected real target
# roles: "Quantitative Trader" (quant != \bquant\b) and "Researcher"
# (research != \bresearch\b) were both being dropped as non-technical.
# Elite employers post across every engineering discipline. A CS grad student
# does not want "Early Career Manufacturing Engineer" - but these titles all
# contain "Engineer" and sail straight through the TECH gate. Rejected unless
# the title also carries a CS-core signal, which keeps genuinely software-shaped
# roles like "Flight Test Engineer, Mission Autonomy".
NON_CS_DISCIPLINE = re.compile(
    r"\b(manufacturing|mechanical|civil|industrial|chemical|structural|propulsion|"
    r"aerodynamic\w*|aerothermal|thermal|materials|metallurg\w*|welding|welder|"
    r"machinist|technician|avionics|\bgnc\b|guidance,?\s+navigation|"
    r"quality\s+engineer\w*|process\s+engineer\w*|supply\s+chain|logistics|"
    r"facilities|electrical\s+engineer\w*|field\s+engineer|"
    r"optical\s+engineer\w*|packaging\s+engineer\w*|environmental)\b",
    re.I,
)
CS_CORE = re.compile(
    r"\b(softwar\w*|firmware|embedded|silicon|asic|fpga|\brtl\b|verification|"
    r"compiler\w*|kernel|machine\s+learning|deep\s+learning|\bml\b|\bai\b|"
    r"data\s+(?:scien|engineer)\w*|research\w*|quant\w*|comput\w*|swe|sde|"
    r"algorithm\w*|platform|backend|frontend|full[-\s]?stack|infrastructur\w*|"
    r"network\w*|cybersecurity|robotic\w*|perception|autonomy|autonomous|"
    r"simulation|controls?\s+software|distributed\s+systems)\b",
    re.I,
)

TECH = re.compile(
    r"\b(softwar\w*|engineer\w*|develop\w*|scien\w*|research\w*|"
    r"machine\s+learning|deep\s+learning|ml|ai|data\w*|infrastructur\w*|"
    r"system\w*|platform\w*|backend|back[-\s]end|frontend|front[-\s]end|"
    r"full[-\s]?stack|security|compiler\w*|kernel|robotic\w*|perception|"
    r"quant\w*|trad(?:er|ing)\w*|hardware|firmware|silicon|fpga|asic|"
    r"technical\s+staff|programm\w*|sre|devops|comput\w*|algorithm\w*|"
    # Abbreviations are extremely common in real titles ("New Grad SWE",
    # "SDE I") and omitting them silently rejects genuine target roles.
    r"swe|sde|sdet|mts|mle|qa|ux\s+engineer|"
    r"cryptograph\w*|network\w*|database\w*|cloud|mlops|analytic\w*)\b",
    re.I,
)

# --------------------------------------------------------------------------
# Degree
# --------------------------------------------------------------------------
PHD_REQUIRED = re.compile(
    r"(ph\.?\s?d\.?|doctora(?:l|te))[^.]{0,80}?\b(required|is\s+required|must|"
    r"candidates?\s+must|we\s+require)\b"
    r"|\b(required|require[sd]?)[^.]{0,60}?(ph\.?\s?d\.?|doctora(?:l|te))"
    r"|\b(ph\.?\s?d\.?)\s+in\s+(computer|electrical|mathematic|statistic|physic|"
    r"machine\s+learning|a\s+related)",
    re.I,
)
PHD_TITLE = re.compile(r"\b(ph\.?\s?d\.?|doctoral)\b", re.I)
# "BS/MS/PhD in Computer Science" means a PhD is ACCEPTED, not required. Without
# this, ordinary new-grad SWE postings were being tagged PhD-required and
# surfacing on the PhD research board.
PHD_ENUMERATED = re.compile(
    r"\b(b\.?s\.?|b\.?a\.?|bachelor'?s?|m\.?s\.?|master'?s?)\b[^.]{0,60}?"
    r"(?:\bor\b|/|,)\s*\b(ph\.?\s?d\.?)",
    re.I,
)
ADVANCED_DEGREE = re.compile(
    r"\b(master'?s?|\bm\.?s\.?\b|\bms/phd\b|advanced\s+degree|graduate\s+degree)\b",
    re.I,
)
BACHELORS = re.compile(r"\b(bachelor'?s?|\bb\.?s\.?\b|\bb\.?a\.?\b|undergraduate)\b", re.I)

# --------------------------------------------------------------------------
# Sponsorship. Checked strongest-signal first; a posting that says both
# "US citizenship required" and "we sponsor visas" is a citizenship role with
# boilerplate, not a sponsoring one.
# --------------------------------------------------------------------------
CLEARANCE = re.compile(
    r"\b(security\s+clearance|ts/sci|top\s+secret|secret\s+clearance|"
    r"active\s+clearance|polygraph|dod\s+clearance)\b",
    re.I,
)
CITIZENSHIP = re.compile(
    r"\b(u\.?s\.?\s+citizen(?:ship)?s?\b(?![^.]{0,40}\bnot\s+required)"
    r"|must\s+be\s+a\s+u\.?s\.?\s+(?:citizen|person)"
    r"|itar|export\s+control(?:led)?\s+(?:data|information|regulations)"
    r"|lawful\s+permanent\s+resident|green\s+card\s+holder"
    r"|u\.?s\.?\s+person\s+(?:as\s+defined|status|requirement))\b",
    re.I,
)
NO_SPONSORSHIP = re.compile(
    r"\b(not?\s+(?:able\s+to\s+|currently\s+)?(?:offer|provide|sponsor)"
    r"|un(?:able|willing)\s+to\s+sponsor"
    r"|do(?:es)?\s+not\s+sponsor"
    r"|will\s+not\s+(?:be\s+able\s+to\s+)?sponsor"
    r"|without\s+(?:current\s+or\s+future\s+)?(?:visa\s+)?sponsorship"
    r"|no\s+(?:visa\s+)?sponsorship"
    r"|sponsorship\s+is\s+not\s+(?:available|offered|provided))\b",
    re.I,
)
SPONSORS = re.compile(
    r"\b(will\s+sponsor|do\s+sponsor|we\s+sponsor|sponsorship\s+(?:is\s+)?available"
    r"|offer\s+(?:visa\s+)?sponsorship|provide\s+(?:visa\s+)?sponsorship"
    r"|immigration\s+(?:support|assistance|sponsorship)"
    r"|visa\s+sponsorship\s+(?:is\s+)?(?:offered|provided|available)"
    r"|happy\s+to\s+sponsor|open\s+to\s+sponsor)\b",
    re.I,
)

SEASON = re.compile(
    r"\b(summer|fall|autumn|winter|spring)\s*(20\d{2})\b|\b(20\d{2})\s+(summer|fall|winter|spring)\b",
    re.I,
)
YEAR = re.compile(r"\b(202[5-9])\b")


def classify_track(posting: RawPosting, company: Company) -> Track:
    """Assign the board. Internship wins over everything - a PhD research
    internship is an internship first, because that is how a student searches."""
    title = posting.title
    haystack = f"{title} {posting.employment_type or ''}"

    if INTERN.search(haystack):
        return Track.INTERNSHIP
    if company.category == "quant" or QUANT.search(title):
        return Track.QUANT
    if RESEARCH.search(title):
        return Track.AI_RESEARCH
    if NEW_GRAD.search(title):
        return Track.NEW_GRAD_SWE
    return Track.OTHER


def classify_degree(posting: RawPosting) -> Degree:
    """Report the degree the posting actually *requires*.

    The distinction that matters: a posting listing "BS/MS/PhD in Computer
    Science" accepts a PhD, it does not require one. Treating those as
    PhD-required mislabels ordinary new-grad SWE roles and floods the PhD board
    with them, which is exactly what happened on the first production run.
    """
    body = posting.description
    if PHD_TITLE.search(posting.title):
        return Degree.PHD_REQUIRED
    if PHD_REQUIRED.search(body) and not PHD_ENUMERATED.search(body):
        return Degree.PHD_REQUIRED
    if ADVANCED_DEGREE.search(posting.title) or ADVANCED_DEGREE.search(body):
        return Degree.MASTERS_PREFERRED
    if BACHELORS.search(body):
        return Degree.BACHELORS
    return Degree.UNSPECIFIED


def classify_sponsorship(posting: RawPosting, company: Company) -> Sponsorship:
    body = f"{posting.title}\n{posting.description}"
    if CLEARANCE.search(body):
        return Sponsorship.SECURITY_CLEARANCE
    if CITIZENSHIP.search(body):
        return Sponsorship.CITIZENSHIP_REQUIRED
    if NO_SPONSORSHIP.search(body):
        return Sponsorship.NO_SPONSORSHIP
    if SPONSORS.search(body):
        return Sponsorship.SPONSORS
    return Sponsorship.UNKNOWN


SEASON_WORD = re.compile(r"\b(summer|fall|autumn|winter|spring)\b", re.I)


def detect_season(posting: RawPosting) -> str | None:
    """Extract the intake a posting targets, e.g. 'Summer 2027'.

    The title is exhausted before the description is consulted, and that
    ordering is load-bearing. AQR's "2027 Research Summer Analyst" carries
    "Spring 2028" (a start date) in its body, and scanning the description
    first labelled a 2027 summer role as Spring 2028.

    Within the title, an adjacent pair ("Summer 2027") wins; failing that a
    season word and a year appearing separately are combined, because
    "2027 Engineering Summer Analyst" is unambiguous to a human.
    """
    title = posting.title or ""

    match = SEASON.search(title)
    if match:
        if match.group(1):
            return f"{match.group(1).title()} {match.group(2)}"
        return f"{match.group(4).title()} {match.group(3)}"

    year = YEAR.search(title)
    if year:
        word = SEASON_WORD.search(title)
        season = word.group(1).title() if word else None
        if season == "Autumn":
            season = "Fall"
        return f"{season} {year.group(1)}" if season else year.group(1)

    match = SEASON.search(posting.description[:4000] or "")
    if match:
        if match.group(1):
            return f"{match.group(1).title()} {match.group(2)}"
        return f"{match.group(4).title()} {match.group(3)}"
    return None


def is_eligible(posting: RawPosting, company: Company) -> tuple[bool, str]:
    """Gate every posting before it can reach a board.

    Returns (eligible, reason) so the pipeline can publish a rejection
    breakdown instead of silently dropping rows.
    """
    title = posting.title
    if not title or not posting.apply_url:
        return False, "missing title or apply url"
    if not any_us(posting.locations):
        return False, "not a US location"
    if NON_TECH.search(title):
        return False, "non-technical role"
    if not TECH.search(title):
        return False, "title is not a technical role"
    if NON_CS_DISCIPLINE.search(title) and not CS_CORE.search(title):
        return False, "non-CS engineering discipline"

    early = bool(INTERN.search(title) or NEW_GRAD.search(title))
    if SENIOR.search(title) and not early:
        return False, "senior/experienced role"

    track = classify_track(posting, company)
    if track is Track.OTHER:
        return False, "not an early-career posting"

    # Quant firms label almost everything "quant"; still require an early-career
    # or research marker so we do not import their entire lateral board.
    if track is Track.QUANT and not (early or RESEARCH.search(title)):
        return False, "quant role without early-career marker"
    if track is Track.AI_RESEARCH and not early and not _research_is_entry(posting):
        return False, "research role without early-career marker"
    return True, "ok"


def _research_is_entry(posting: RawPosting) -> bool:
    """Research titles rarely say 'new grad'. Accept them when the posting
    reads as entry-level: a residency, a fellowship, or a PhD-new-grad pipeline."""
    text = f"{posting.title} {posting.description[:2500]}"
    return bool(
        re.search(
            r"\b(residency|resident|fellowship|fellow|new\s+grad|recent\s+(?:phd|graduate)|"
            r"early\s+career|university\s+grad|campus|0-2\s+years|no\s+prior\s+industry)\b",
            text,
            re.I,
        )
    )


def us_locations(posting: RawPosting) -> list[str]:
    return us_only(posting.locations) or posting.locations[:1]
