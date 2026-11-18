"""Put Shield's safe publication (request IDs + eligible document IDs, no addresses, no contents) into the
restricted demo inbox Instinct can read. Uses messages.insert, so nothing is sent and the sender account is not exposed.

  python demo/scripts/seed_restricted_inbox.py --token token_restricted.json [--dry-run]"""
# Run from anywhere: imports Shield from backend/, and relative paths (tokens, credentials.json, .env) resolve in backend/.
import os as _os
import sys as _sys
from pathlib import Path as _Path

_BACKEND = _Path(__file__).resolve().parents[2] / "backend"
_sys.path.insert(0, str(_BACKEND))
_os.chdir(_BACKEND)
import argparse
import base64
import sys
from email.message import EmailMessage
from pathlib import Path

from app.config import load_dotenv  # noqa: E402

load_dotenv()
from app import mirror  # noqa: E402
from app.config import Settings  # noqa: E402
from app.mail import FakeMail  # noqa: E402
from app.service import Shield  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default="token_restricted.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    settings = Settings()
    pub = mirror.publication(Shield(settings, mail=FakeMail()))
    print(f"Subject: {pub['subject']}\n\n{pub['body']}")
    if a.dry_run:
        sys.exit(0)
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    svc = build("gmail", "v1", credentials=Credentials.from_authorized_user_file(a.token), cache_discovery=False)
    m = EmailMessage()
    m["From"] = "Shield <shield@shield.local>"
    m["To"] = "me"
    m["Subject"] = pub["subject"]
    m.set_content(pub["body"])
    res = svc.users().messages().insert(userId="me", body={"raw": base64.urlsafe_b64encode(m.as_bytes()).decode(),
                                                           "labelIds": ["INBOX", "UNREAD"]}).execute()
    account = svc.users().getProfile(userId="me").execute().get("emailAddress", "restricted inbox")
    for it in pub["items"]:
        mirror.record_published(settings.runtime_dir, {"mailbox": account, "gmail_message_id": res["id"],
                                                       "subject": pub["subject"], "request": it["request"], "file": it["file"]})
    print("inserted into restricted inbox:", res.get("id"))
