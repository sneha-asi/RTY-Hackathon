"""Which Gmail account does a token belong to?  python scripts/gmail_whoami.py --token token.json"""
import argparse

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default="token.json")
    a = ap.parse_args()
    svc = build("gmail", "v1", credentials=Credentials.from_authorized_user_file(a.token), cache_discovery=False)
    print(svc.users().getProfile(userId="me").execute()["emailAddress"])
