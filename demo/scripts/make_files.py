"""Generate the synthetic demo PDFs (no real financials anywhere)."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "files"
DOCS = {
    "Projections_v2.pdf": ["Kestrel Labs - Financial Projections v2 (SUPERSEDED)", "SYNTHETIC DEMO DATA",
                           "FY27 revenue: Rs 4.0 Cr", "FY28 revenue: Rs 11.0 Cr"],
    "Projections_v3.pdf": ["Kestrel Labs - Financial Projections v3 (LATEST)", "SYNTHETIC DEMO DATA",
                           "FY27 revenue: Rs 4.6 Cr", "FY28 revenue: Rs 13.5 Cr", "Confidential - NDA only"],
    "Teaser_Deck.pdf": ["Kestrel Labs - Teaser", "SYNTHETIC DEMO DATA",
                        "The AI talks. The code decides. Nothing is done until it's proven."],
}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, lines in DOCS.items():
        c = canvas.Canvas(str(OUT / name), pagesize=A4, invariant=1)  # invariant=1 -> byte-stable output
        y = 780
        for line in lines:
            c.drawString(72, y, line)
            y -= 24
        c.save()
        print("wrote", OUT / name)
