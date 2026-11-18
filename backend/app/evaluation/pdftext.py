"""Minimal text extraction for the ReportLab demo PDFs (ASCII85 + Flate streams). Direct baseline only."""
from __future__ import annotations

import base64
import re
import zlib


def pdf_text(b: bytes) -> str:
    out = []
    for m in re.finditer(rb"/Filter\s*\[?([^\]>]*)\]?.*?stream\r?\n(.*?)endstream", b, re.S):
        data, filt = m.group(2).strip(), m.group(1)
        try:
            if b"ASCII85" in filt:
                data = base64.a85decode(data[:-2] if data.endswith(b"~>") else data)
            if b"Flate" in filt:
                data = zlib.decompress(data)
        except Exception:
            continue
        out += [t.decode("latin-1") for t in re.findall(rb"\((.*?)\) Tj", data)]
    return "\n".join(out)
