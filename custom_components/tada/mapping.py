from __future__ import annotations

# ID -> display name mappings (Italian)
# Appliances = Elettrodomestici
APPLIANCES_MAP: dict[int, str] = {
    17: "Stand-by",
    1000: "Altro",
    10: "Piano cottura",
    6: "Frigorifero",
    2: "Lavastoviglie",
    1: "Lavatrice",
    4: "Ferro da stiro",
}

# Activities = Attività
ACTIVITIES_MAP: dict[int, str] = {
    6: "Stand-by",
    1000: "Altro",
    3: "Cucinare",
    1: "Lavare",
}


def slugify(label: str) -> str:
    """Basic slugify for labels used in entity names/ids.

    Lowercase, replace spaces with hyphens, strip accents where simple.
    """
    s = (label or "").strip().lower()
    # replace accented 'à' and 'á' with 'a'
    s = s.replace("à", "a").replace("á", "a").replace("è", "e").replace("é", "e")
    s = s.replace("ì", "i").replace("í", "i").replace("ò", "o").replace("ó", "o")
    s = s.replace("ù", "u").replace("ú", "u")
    # spaces and punctuation
    for ch in [" ", "/", ",", ".", ";", ":", "(", ")"]:
        s = s.replace(ch, "-")
    # collapse double hyphens
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")


# Supported summary periods mapping to labels used elsewhere
SUMMARY_PERIODS: list[tuple[str, str, str]] = [
    ("yesterday", "yesterday", "Tada Yesterday"),
    ("last-week", "last_week", "Tada Last week"),
    ("last-7-days", "last_7_days", "Tada Last 7 days"),
    ("last-month", "last_month", "Tada Last month"),
    ("last-30-days", "last_30_days", "Tada Last 30 days"),
    ("last-year", "last_year", "Tada Last year"),
    ("last-365-days", "last_365_days", "Tada Last 365 days"),
]
