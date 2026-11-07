import re
from typing import Optional, Tuple

MII_BASE_NAMES = {
    "mii brawler": "Mii Brawler",
    "mii gunner": "Mii Gunner",
    "mii swordfighter": "Mii Swordfighter",
    "mii sword fighter": "Mii Swordfighter",
}


def parse_mii_moveset(raw_text: Optional[str]) -> Optional[str]:
    """
    Extract a 4-digit moveset string (e.g. '1332') from a string like 'Mii Brawler (1332)'.
    Only moves consisting of digits 1-3 are valid for Ultimate Mii fighters.
    """
    if not raw_text:
        return None
    match = re.search(r"\(?([1-3]{4})\)?", str(raw_text).strip())
    return match.group(1) if match else None


def normalize_character_name(raw_name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalizes a character name, stripping moveset notations for Mii fighters so that
    it maps cleanly to TSH's character list in Super Smash Bros. Ultimate.

    Returns:
        Tuple of (canonical_base_character_name, moveset_string_or_None).

    Examples:
        'Mii Brawler (1332)'       -> ('Mii Brawler', '1332')
        'Mii Gunner (3122)'        -> ('Mii Gunner', '3122')
        'Mii Swordfighter (2132)'  -> ('Mii Swordfighter', '2132')
        'Mii Sword Fighter (2132)' -> ('Mii Swordfighter', '2132')
        'Mii Brawler 1332'         -> ('Mii Brawler', '1332')
        'Mii Brawler'              -> ('Mii Brawler', None)
        'Mario'                    -> ('Mario', None)
        None                       -> (None, None)
    """
    if not raw_name:
        return None, None

    clean = str(raw_name).strip()
    if not clean:
        return None, None

    moveset = parse_mii_moveset(clean)
    clean_lower = clean.lower()

    for prefix, canonical in MII_BASE_NAMES.items():
        if clean_lower.startswith(prefix):
            return canonical, moveset

    return clean, moveset
