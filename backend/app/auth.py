"""CALLER check: registered number AND spoken PIN. Plain code, no AI."""
from __future__ import annotations

import hmac
import re

from .models import CallSession, Founder

MAX_PIN_ATTEMPTS = 2

_WORDS = {
    "zero": "0", "oh": "0", "o": "0", "one": "1", "won": "1", "two": "2", "to": "2", "too": "2",
    "three": "3", "tree": "3", "four": "4", "for": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "ate": "8", "nine": "9",
}


def normalize_pin(spoken: str | None) -> str:
    """Speech-to-text gives '4 3 2 1', 'four three two one', 'double four'... -> digits."""
    if not spoken:
        return ""
    out: list[str] = []
    tokens = re.findall(r"[a-zA-Z]+|\d", spoken.lower())
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("double", "triple") and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            d = nxt if nxt.isdigit() else _WORDS.get(nxt, "")
            out.append(d * (2 if t == "double" else 3))
            i += 2
            continue
        if t.isdigit():
            out.append(t)
        elif t in _WORDS:
            out.append(_WORDS[t])
        i += 1
    return "".join(out)


def normalize_number(num: str | None) -> str:
    """Compare the last 10 digits so +91 98..., 098... and 98... all match."""
    return re.sub(r"\D", "", num or "")[-10:]


def number_registered(founder: Founder, caller_number: str | None) -> bool:
    n = normalize_number(caller_number)
    return len(n) == 10 and any(normalize_number(r) == n for r in founder.registered_numbers)


def verify(session: CallSession, founder: Founder, spoken_pin: str | None) -> tuple[bool, str]:
    """Returns (verified, internal reason). Mutates the session.
    The caller is never told which factor failed."""
    if session.verified:
        return True, "already verified"
    if session.locked:
        return False, "call locked after failed attempts"
    session.pin_attempts += 1
    registered = number_registered(founder, session.caller_number)
    session.number_registered = registered
    pin_ok = hmac.compare_digest(normalize_pin(spoken_pin).encode(), founder.pin.encode())
    if registered and pin_ok:
        session.verified = True
        return True, "registered number + PIN"
    if session.pin_attempts >= MAX_PIN_ATTEMPTS:
        session.locked = True
    reasons = []
    if not registered:
        reasons.append("unregistered number")
    if not pin_ok:
        reasons.append("wrong PIN")
    if session.locked:
        reasons.append("call locked")
    return False, ", ".join(reasons)
