"""Code, not AI: spoken name -> contact, category -> latest file.

Mishearing guard: over a phone line an exact first-name hit is NOT trusted on its own if a
sound-alike contact exists ("Riya" vs "Priya"). An org or surname must disambiguate."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .models import Contact, FileRecord

SOUNDALIKE = 0.75


def norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", (s or "").lower())).strip()


def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def org_matches(spoken_org: str | None, contact: Contact) -> bool:
    so, co = norm(spoken_org), norm(contact.org)
    if not so:
        return False
    if so in co or co in so:
        return True
    return any(sim(w, cw) >= 0.8 for w in so.split() for cw in co.split() if len(w) > 2)


@dataclass
class ContactMatch:
    status: str  # "one" | "none" | "many"
    contact: Contact | None = None
    candidates: list[Contact] = field(default_factory=list)


def resolve_contact(contacts: list[Contact], spoken_name: str | None, spoken_org: str | None = None) -> ContactMatch:
    name = norm(spoken_name)
    if not name or "@" in (spoken_name or ""):
        return ContactMatch("none")  # spoken email addresses are never recipients
    parts = name.split()
    first, last = parts[0], (parts[-1] if len(parts) > 1 else None)

    cands: list[Contact] = []
    for c in contacts:
        cf, cl = norm(c.first_name), norm(c.name.split()[-1])
        if sim(name, c.name) >= 0.85 or cf == first or sim(first, cf) >= SOUNDALIKE:
            if last and sim(last, cl) < 0.6 and sim(name, c.name) < 0.85:
                continue  # spoken surname clearly contradicts
            cands.append(c)

    if not cands:
        return ContactMatch("none")
    if len(cands) > 1 and spoken_org:
        by_org = [c for c in cands if org_matches(spoken_org, c)]
        exact = [c for c in cands if norm(c.first_name) == first]
        if by_org and exact and not any(c in by_org for c in exact):
            # name says one person, org says another ("Priya from Acme") -> ask, never guess
            return ContactMatch("many", candidates=exact + [c for c in by_org if c not in exact])
        if by_org:
            cands = by_org
    if len(cands) > 1 and last:
        by_full = [c for c in cands if sim(name, c.name) >= 0.85]
        if len(by_full) == 1:
            cands = by_full
    if len(cands) == 1:
        if spoken_org and not org_matches(spoken_org, cands[0]):
            return ContactMatch("none")  # "Priya from Acme" -> don't guess
        return ContactMatch("one", contact=cands[0])
    return ContactMatch("many", candidates=cands)


def contacts_mentioned(text: str, candidates: list[Contact]) -> list[Contact]:
    """Answer to a clarification ('Priya Rao from Northbeam'): which candidates are named,
    as whole words. Word boundaries matter: 'priya' must not match 'riya'."""
    t = norm(text)
    hits = []
    for c in candidates:
        words = [norm(c.first_name), norm(c.name.split()[-1])] + [w for w in norm(c.org).split() if len(w) > 3]
        if any(re.search(rf"\b{re.escape(w)}\b", t) for w in words if w):
            hits.append(c)
    return hits


CATEGORY_ALIASES = {
    "projections": "projections", "projection": "projections", "financials": "projections",
    "financial": "projections", "financial model": "projections", "forecast": "projections",
    "deck": "deck", "pitch deck": "deck", "teaser": "teaser", "teaser deck": "teaser",
    "data room": "data_room", "data_room": "data_room",
}


def canonical_category(category: str | None) -> str:
    c = norm(category)
    return CATEGORY_ALIASES.get(c, c.replace(" ", "_"))


def latest_file(files: list[FileRecord], category: str | None) -> FileRecord | None:
    cat = canonical_category(category)
    matches = [f for f in files if f.category == cat]
    return max(matches, key=lambda f: f.version) if matches else None
