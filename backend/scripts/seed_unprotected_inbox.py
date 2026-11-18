"""'Without Shield' scene: copy the full synthetic executive inbox (16 emails: investor requests, term sheet,
layoff plan, GST/PAN, medical note, cap-table board prep, and the hidden-instruction attacks) into a Gmail TEST
account that Instinct connects to directly. All data is synthetic. Never run this against a personal account.

  python scripts/gmail_token.py --out token_unprotected.json --scopes insert   (log in as the demo executive inbox)
  python scripts/seed_unprotected_inbox.py --token token_unprotected.json [--dry-run]"""
import argparse
import base64
import json
import sys
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import load_dotenv  # noqa: E402

load_dotenv()
from app.seed import fill_placeholders  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
FILES = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default="token_unprotected.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    missing: set[str] = set()
    emails = json.loads(fill_placeholders((DATA / "emails.json").read_text(), missing))
    files = {f["id"]: f for f in json.loads((DATA / "files.json").read_text())}
    msgs = []
    for e in emails:
        m = EmailMessage()
        m["From"] = e["from"]
        m["To"] = ", ".join(e["to"])
        m["Subject"] = e["subject"]
        m["Date"] = format_datetime(datetime.fromisoformat(e["ts"]))
        m.set_content("(HTML message)")
        m.add_alternative(e["body_html"], subtype="html")  # hidden text stays hidden, as in a real attack
        for fid in e.get("attachments", []):
            f = files[fid]
            m.add_attachment((FILES / f["path"]).read_bytes(), maintype="application", subtype="octet-stream",
                             filename=Path(f["path"]).name)
        msgs.append((e["id"], e["subject"], m))
    for eid, subj, _ in msgs:
        print(f"{eid:4} {subj}")
    if missing:
        print("note: unset placeholders (set them in .env):", ", ".join(sorted(missing)))
    if a.dry_run:
        sys.exit(0)
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    svc = build("gmail", "v1", credentials=Credentials.from_authorized_user_file(a.token), cache_discovery=False)
    for eid, subj, m in msgs:
        svc.users().messages().insert(userId="me", body={"raw": base64.urlsafe_b64encode(m.as_bytes()).decode(),
                                                         "labelIds": ["INBOX", "UNREAD"]}).execute()
    print(f"inserted {len(msgs)} synthetic emails")
