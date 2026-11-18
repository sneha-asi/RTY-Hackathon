"""Which Gmail account does a token belong to?  python scripts/gmail_whoami.py --token token.json"""
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
    ap.add_argument("--token", default="token.json")
    a = ap.parse_args()
    svc = build("gmail", "v1", credentials=Credentials.from_authorized_user_file(a.token), cache_discovery=False)
    print(svc.users().getProfile(userId="me").execute()["emailAddress"])
