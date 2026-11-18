"""Create an OAuth token for one Gmail TEST account (run on your laptop; a browser opens).

  Sender account (only Shield uses it; the assistant never gets it):
    python demo/scripts/gmail_token.py --out token.json --scopes send,readonly
  Restricted demo inbox (the one Instinct can read), only to seed it:
    python demo/scripts/gmail_token.py --out token_restricted.json --scopes insert

  Your own Gmail, for the before/after demo (runs only on your laptop; the token stays there):
    python demo/scripts/gmail_token.py --out token_watch.json --scopes readonly,modify,compose

Needs credentials.json (Google Cloud OAuth client, type Desktop) in backend/. Both files are git-ignored."""
# Run from anywhere: imports Shield from backend/, and relative paths (tokens, credentials.json, .env) resolve in backend/.
import os as _os
import sys as _sys
from pathlib import Path as _Path

_BACKEND = _Path(__file__).resolve().parents[2] / "backend"
_sys.path.insert(0, str(_BACKEND))
_os.chdir(_BACKEND)
import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = {"send": "https://www.googleapis.com/auth/gmail.send",
          "readonly": "https://www.googleapis.com/auth/gmail.readonly",
          "insert": "https://www.googleapis.com/auth/gmail.insert",
          "modify": "https://www.googleapis.com/auth/gmail.modify",    # seed + clean up labelled demo mail
          "compose": "https://www.googleapis.com/auth/gmail.compose"}  # lets the watcher remove a risky draft

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--scopes", default="send,readonly")
    ap.add_argument("--client", default="credentials.json")
    a = ap.parse_args()
    flow = InstalledAppFlow.from_client_secrets_file(a.client, [SCOPES[s] for s in a.scopes.split(",")])
    creds = flow.run_local_server(port=0)
    open(a.out, "w").write(creds.to_json())
    print(f"wrote {a.out} with scopes {a.scopes}. Keep it out of git.")
