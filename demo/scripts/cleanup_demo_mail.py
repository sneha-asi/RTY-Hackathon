"""Move every message carrying the demo label (default "Shield demo") to Trash, then delete the label.

  python scripts/cleanup_demo_mail.py --token token_watch.json [--label "Shield demo"]"""
# Run from anywhere: imports Shield from backend/, and relative paths (tokens, credentials.json, .env) resolve in backend/.
import os as _os
import sys as _sys
from pathlib import Path as _Path

_BACKEND = _Path(__file__).resolve().parents[2] / "backend"
_sys.path.insert(0, str(_BACKEND))
_os.chdir(_BACKEND)
import argparse

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default="token_watch.json")
    ap.add_argument("--label", default="Shield demo")
    a = ap.parse_args()
    svc = build("gmail", "v1", credentials=Credentials.from_authorized_user_file(a.token), cache_discovery=False)
    labels = {l["name"]: l["id"] for l in svc.users().labels().list(userId="me").execute().get("labels", [])}
    lid = labels.get(a.label)
    if not lid:
        raise SystemExit(f"no label {a.label!r}; nothing to clean")
    n, page = 0, None
    while True:
        res = svc.users().messages().list(userId="me", labelIds=[lid], pageToken=page, maxResults=100).execute()
        for m in res.get("messages", []):
            svc.users().messages().trash(userId="me", id=m["id"]).execute()
            n += 1
        page = res.get("nextPageToken")
        if not page:
            break
    svc.users().labels().delete(userId="me", id=lid).execute()
    print(f"moved {n} demo messages to Trash and removed the {a.label!r} label")
