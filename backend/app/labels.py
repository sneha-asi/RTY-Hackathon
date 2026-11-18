"""Sensitive-value detectors and sensitivity labels (LLD §4.2)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_V_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
        [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
        [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_V_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
        [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]


def verhoeff_ok(num: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _V_D[c][_V_P[i % 8][int(ch)]]
    return c == 0


def luhn_ok(num: str) -> bool:
    total, alt = 0, False
    for ch in reversed(num):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


# order matters: earlier detectors win overlaps of equal length
DETECTORS: list[tuple[str, re.Pattern, object]] = [
    ("api_key", re.compile(r"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36}|AIza[0-9A-Za-z_-]{35}|xox[abprs]-[A-Za-z0-9-]{10,}"), None),
    ("gstin", re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"), lambda v: 1 <= int(v[:2]) <= 38),
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), lambda v: v[3] in "PCHFATBLJG"),
    ("ifsc", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), None),
    ("upi", re.compile(r"\b[\w.-]{2,}@(ok(axis|sbi|hdfcbank|icici)|ybl|paytm|upi|apl|ibl|axl)\b"), None),
    ("email", re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), None),
    ("card", re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), lambda v: 13 <= len(_digits(v)) <= 19 and luhn_ok(_digits(v))),
    ("aadhaar", re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b"), lambda v: verhoeff_ok(_digits(v))),
    ("phone", re.compile(r"(\+91[\s-]?)?\b[6-9]\d{9}\b"), None),
    ("money", re.compile(r"(₹|\bRs\.?|\bINR|\$|\bUSD)\s?\d[\d,]*(\.\d+)?(\s?(cr|crore|lakh|L|k|M|mn|bn)\b)?", re.I), None),
]


@dataclass
class Span:
    detector: str
    start: int
    end: int
    value: str

    @property
    def value_hash(self) -> str:
        return hashlib.sha256(self.value.encode()).hexdigest()[:16]


def detect(text: str) -> list[Span]:
    found: list[Span] = []
    for name, rx, ok in DETECTORS:
        for m in rx.finditer(text or ""):
            v = m.group(0)
            if ok and not ok(v):
                continue
            found.append(Span(name, m.start(), m.end(), v))
    found.sort(key=lambda s: (s.start, -(s.end - s.start)))
    out: list[Span] = []
    for s in found:
        if out and s.start < out[-1].end:
            continue
        out.append(s)
    return out


KEYWORDS: dict[str, list[str]] = {
    "financial": ["cap table", "valuation", "runway", "burn", "projections", "revenue", "arr", "bank", "pre-money"],
    "legal": ["term sheet", "nda", "litigation", "lawsuit", "indemnity", "liquidation preference"],
    "hr": ["layoff", "salary", "offer letter", "termination", "severance", "restructuring"],
    "health": ["diagnosis", "medical", "prescription", "hospital", "doctor"],
    "deal": ["term sheet", "acquisition", "loi", "data room", "due diligence"],
    "secrets": ["password", "credentials", "api key"],
}
DETECTOR_LABEL = {"pan": "identity_ids", "aadhaar": "identity_ids", "gstin": "identity_ids", "card": "identity_ids",
                  "upi": "identity_ids", "ifsc": "identity_ids", "api_key": "secrets", "money": "financial"}


def labels_for(text: str) -> set[str]:
    low = (text or "").lower()
    out = {lab for lab, words in KEYWORDS.items() if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words)}
    out |= {DETECTOR_LABEL[s.detector] for s in detect(text) if s.detector in DETECTOR_LABEL}
    return out
