"""Hidden-text stripping and instruction detection (LLD §4.1). A safeguard on top of I1, not the guarantee."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Comment

ZERO_WIDTH = re.compile(r"[​-‏⁠﻿­]")
WHITE = {"white", "#fff", "#ffffff", "rgb(255,255,255)"}

HIDDEN_STYLE = [
    re.compile(r"display\s*:\s*none"),
    re.compile(r"visibility\s*:\s*hidden"),
    re.compile(r"font-size\s*:\s*[0-2](\.\d+)?(px|pt)?\b"),
    re.compile(r"opacity\s*:\s*0(\.0+)?\b"),
    re.compile(r"(left|top)\s*:\s*-\d{3,}px"),
]

PATTERNS: dict[str, re.Pattern] = {
    "override": re.compile(r"\b(ignore|disregard)\b.{0,30}\b(instructions|rules|above)\b", re.I),
    "addresses_ai": re.compile(r"\b(assistant|ai agent|agent|ai|llm)\s*[:,]|\b(you are|as an?) (ai|assistant|agent)\b", re.I),
    "exfil_send": re.compile(r"\b(forward|send|email|share)\b.{0,60}\bto\b.{0,40}[\w.+-]+@[\w-]+\.\w+", re.I),
    "add_recipient": re.compile(r"\b(cc|bcc)\b.{0,30}[\w.+-]+@|\balso (send|copy) to\b", re.I),
    "search_secrets": re.compile(r"\b(search|find|look for)\b.{0,40}\b(api[ _-]?keys?|passwords?|tokens?|secrets?|credentials)\b", re.I),
    "link_payload": re.compile(r"(put|include|append|embed).{0,40}(link|url|image)|!\[[^\]]*\]\(https?://", re.I),
    "concealment": re.compile(r"\bdo not (tell|mention|inform)\b.{0,10}\buser\b|\bwithout (asking|confirmation)\b", re.I),
    "create_action": re.compile(r"\b(create|add|schedule)\b.{0,10}\b(event|meeting|invite)\b.{0,60}@", re.I),
}


@dataclass
class CleanResult:
    text: str
    hidden_text: str = ""
    hidden_spans: int = 0
    hits: list[str] = field(default_factory=list)
    hidden_hits: list[str] = field(default_factory=list)
    quarantined: bool = False
    reason: str = ""


def _is_hidden(tag) -> bool:
    if tag.has_attr("hidden") or tag.get("aria-hidden") == "true":
        return True
    style = (tag.get("style") or "").lower().replace(" ", "")
    if not style:
        return False
    if any(p.search(style) for p in HIDDEN_STYLE):
        return True
    color = re.search(r"(?<![-\w])color:([^;]+)", style)
    bg = re.search(r"background(-color)?:([^;]+)", style)
    if color and color.group(1) in WHITE and (not bg or bg.group(2) in WHITE):
        return True
    return False


def scan(text: str) -> list[str]:
    return [name for name, p in PATTERNS.items() if p.search(text)]


def clean(html: str, sender_trusted: bool) -> CleanResult:
    soup = BeautifulSoup(html or "", "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in soup(["script", "style", "template"]):
        t.decompose()
    hidden: list[str] = []
    for tag in soup.find_all(True):
        if tag.parent is not None and _is_hidden(tag):
            hidden.append(tag.get_text(" ", strip=True))
            tag.decompose()
    for img in soup.find_all("img"):
        img.decompose()
    text = ZERO_WIDTH.sub("", soup.get_text(" ", strip=True))
    text = re.sub(r"\s{20,}", "\n", text)
    hidden_text = " ".join(h for h in hidden if h)
    r = CleanResult(text=text, hidden_text=hidden_text, hidden_spans=len(hidden))
    r.hidden_hits = scan(hidden_text) if hidden_text else []
    r.hits = sorted(set(scan(text)) | set(r.hidden_hits))
    r.quarantined = bool(r.hidden_hits) or (not sender_trusted and len(scan(text)) >= 1)
    if r.quarantined:
        r.reason = f"{r.hidden_spans} hidden span(s); patterns: {', '.join(r.hits)}"
    return r
