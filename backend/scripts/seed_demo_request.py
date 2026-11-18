"""Seed ONE clearly labelled synthetic email into the Gmail account Instinct reads, for the live recording:
"[Shield Demo] Priya — investor follow-up" with the safe summary, REQ_7 and FILE_2. No attachment, no destination
address. On success Shield records the publication (with Gmail's message id as evidence) for the receipt.

  python scripts/gmail_token.py --out token_watch.json --scopes readonly,modify,compose   (sign in as that Gmail)
  python scripts/seed_demo_request.py --token token_watch.json [--request REQ_7] [--dry-run]"""
import argparse
import base64
import hashlib
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
    ap.add_argument("--token", default="token_watch.json")
    ap.add_argument("--request", default="REQ_7")
    ap.add_argument("--label", default="Shield demo")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    settings = Settings()
    em = mirror.demo_email(Shield(settings, mail=FakeMail()), a.request)
    print(f"Subject: {em['subject']}\n\n{em['body']}")
    if a.dry_run:
        sys.exit("dry run: nothing published")
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    svc = build("gmail", "v1", credentials=Credentials.from_authorized_user_file(a.token), cache_discovery=False)
    account = svc.users().getProfile(userId="me").execute()["emailAddress"]
    labels = {l["name"]: l["id"] for l in svc.users().labels().list(userId="me").execute().get("labels", [])}
    lid = labels.get(a.label) or svc.users().labels().create(userId="me", body={"name": a.label}).execute()["id"]
    m = EmailMessage()
    m["From"] = "Shield demo <shield-demo@shield.local>"
    m["To"] = account
    m["Subject"] = em["subject"]
    m.set_content(em["body"])
    res = svc.users().messages().insert(userId="me", body={"raw": base64.urlsafe_b64encode(m.as_bytes()).decode(),
                                                           "labelIds": ["INBOX", "UNREAD", lid]}).execute()
    mirror.record_published(settings.runtime_dir, {
        "mailbox": account, "gmail_message_id": res["id"], "subject": em["subject"], "request": em["request"],
        "file": em["file"], "body_sha256": hashlib.sha256(em["body"].encode()).hexdigest()})
    print(f"Published to {account} (Gmail id {res['id']}). Restart is not needed; Shield reads this record live.")
