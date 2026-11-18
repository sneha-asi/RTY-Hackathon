"""Put Shield's safe publication (request IDs + eligible document IDs, no addresses, no contents) into the
restricted demo inbox Instinct can read. Uses messages.insert, so nothing is sent and the sender account is not exposed.

  python scripts/seed_restricted_inbox.py --token token_restricted.json [--dry-run]"""
import argparse
import base64
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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
    pub = mirror.publication(Shield(Settings(), mail=FakeMail()))
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
    print("inserted into restricted inbox:", res.get("id"))
