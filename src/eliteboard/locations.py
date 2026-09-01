"""US location detection.

This board is US-only. Getting it wrong in either direction is costly: drop a
real US role and the board is incomplete; keep a London role and a student
wastes an application. Vendors express location as free text with no country
field, so this is string work - done carefully and tested.
"""

from __future__ import annotations

import re

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

US_CITIES = {
    "san francisco", "new york", "nyc", "seattle", "austin", "boston", "chicago",
    "los angeles", "san jose", "palo alto", "mountain view", "menlo park",
    "sunnyvale", "santa clara", "cupertino", "redmond", "bellevue", "denver",
    "boulder", "atlanta", "miami", "dallas", "houston", "san diego", "portland",
    "philadelphia", "pittsburgh", "washington", "arlington", "cambridge",
    "brooklyn", "oakland", "berkeley", "irvine", "phoenix", "salt lake city",
    "nashville", "raleigh", "durham", "charlotte", "detroit", "minneapolis",
    "columbus", "st. louis", "kansas city", "las vegas", "sacramento",
    "el segundo", "culver city", "santa monica", "hawthorne", "mclean",
    "reston", "herndon", "chantilly", "ann arbor", "madison", "urbana",
    "college station", "costa mesa", "san mateo", "south san francisco",
    "foster city", "emeryville", "san bruno", "burlingame", "plano",
}

# Anything matching these is definitively not a US posting, even if it also
# mentions a US-sounding token ("London, Ontario", "Sydney", "Hyderabad").
NON_US = {
    "united kingdom", "london", "cambridge, uk", "oxford", "manchester", "dublin",
    "ireland", "france", "paris", "germany", "berlin", "munich", "netherlands",
    "amsterdam", "spain", "madrid", "barcelona", "italy", "milan", "rome",
    "switzerland", "zurich", "geneva", "sweden", "stockholm", "norway", "oslo",
    "denmark", "copenhagen", "finland", "helsinki", "poland", "warsaw", "krakow",
    "portugal", "lisbon", "belgium", "brussels", "austria", "vienna", "greece",
    "czech", "prague", "romania", "bucharest", "hungary", "budapest",
    "canada", "toronto", "vancouver", "montreal", "ottawa", "waterloo", "ontario",
    "quebec", "british columbia", "alberta", "calgary",
    "india", "bangalore", "bengaluru", "hyderabad", "mumbai", "delhi", "gurgaon",
    "pune", "chennai", "noida",
    "china", "beijing", "shanghai", "shenzhen", "hangzhou", "hong kong",
    "japan", "tokyo", "osaka", "korea", "seoul",
    "singapore", "australia", "sydney", "melbourne", "new zealand", "auckland",
    "israel", "tel aviv", "herzliya", "brazil", "sao paulo", "mexico",
    "mexico city", "guadalajara", "argentina", "chile", "colombia", "bogota",
    "uae", "dubai", "abu dhabi", "saudi", "riyadh", "egypt", "cairo",
    "south africa", "cape town", "nigeria", "lagos", "kenya", "nairobi",
    "taiwan", "taipei", "malaysia", "kuala lumpur", "philippines", "manila",
    "vietnam", "hanoi", "thailand", "bangkok", "indonesia", "jakarta",
    "turkey", "istanbul", "ukraine", "kyiv", "serbia", "belgrade", "croatia",
    "bulgaria", "sofia", "estonia", "tallinn", "latvia", "lithuania", "vilnius",
    "emea", "apac", "latam", "	emea",
}

_STATE_ABBR = re.compile(
    r"(?:^|[,\s])(" + "|".join(STATES) + r")(?:[,\s]|$)"
)
_US_MARKERS = re.compile(
    r"\b(united states|u\.s\.a?\.?|usa|us[- ]remote|remote[- ,]*us(?:a)?)\b", re.I
)
# Case-sensitive so it fires on "Remote-Friendly (US)" and "Austin, US" without
# matching the English word "us" in prose like "join us in New York".
_US_TOKEN = re.compile(r"\bUS\b")


def is_us(location: str) -> bool:
    """True when a free-text location is in the United States.

    Order matters. Non-US markers are checked first so "London, Ontario, CAN"
    and "Cambridge, UK" are rejected before the city and state passes can fire
    on "London" or "Cambridge".
    """
    if not location:
        return False
    text = location.strip().casefold()

    if any(marker in text for marker in NON_US):
        return False
    if _US_MARKERS.search(location) or _US_TOKEN.search(location):
        return True
    if _STATE_ABBR.search(location.upper()):
        return True
    if any(state.casefold() in text for state in STATES.values()):
        return True
    return any(city in text for city in US_CITIES)


def is_remote(location: str) -> bool:
    return "remote" in (location or "").casefold()


def any_us(locations: list[str]) -> bool:
    """A multi-location posting counts if any single location is US-based."""
    return any(is_us(loc) for loc in locations)


def us_only(locations: list[str]) -> list[str]:
    return [loc for loc in locations if is_us(loc)]


_PAREN = re.compile(r"\([^)]*\)")
_COUNTRY = re.compile(r"\b(united states(?: of america)?|u\.?s\.?a?\.?)\b", re.I)
_FULL_STATE = {name.casefold(): abbr for abbr, name in STATES.items()}


def canonical_key(location: str) -> str:
    """Collapse a free-text location to a comparable 'city|ST' key.

    Vendors describe one office several ways in the same posting. Greenhouse in
    particular returns both `location.name` and an `offices` list, so a single
    role arrives as "Costa Mesa, California, United States" *and*
    "Costa Mesa, CA (OC-00)". Rendering both is noise; this makes them equal.
    """
    text = _COUNTRY.sub(" ", _PAREN.sub(" ", location or ""))
    parts = [p.strip() for p in re.split(r"[,;/]", text) if p.strip()]
    if not parts:
        return (location or "").strip().casefold()

    city = parts[0].casefold()
    state = ""
    for part in parts[1:]:
        token = part.strip()
        if token.upper() in STATES:
            state = token.upper()
            break
        if token.casefold() in _FULL_STATE:
            state = _FULL_STATE[token.casefold()]
            break
    if not state and "remote" in city:
        return "remote"
    return f"{city}|{state}"
