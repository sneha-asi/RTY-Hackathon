"""Live rehearsal of the protected send with real Gmail test accounts (sends ONE real email).

  SHIELD_MAIL=gmail python scripts/gmail_smoke.py --yes

Uses the same path as the demo: intake "REQ_7 FILE_2" → checks → seal → approve → send from the sender test account
(GMAIL_TOKEN) to INVESTOR_TEST_GMAIL → verify against Gmail Sent."""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import load_dotenv  # noqa: E402

load_dotenv()
from app import mirror  # noqa: E402
from app.service import Shield  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="really send one email")
    a = ap.parse_args()
    sh = Shield()
    if sh.settings.mail_backend != "gmail":
        sys.exit("Set SHIELD_MAIL=gmail (and GMAIL_TOKEN for the sender test account).")
    out = mirror.intake(sh, "REQ_7 FILE_2 Note: Gmail smoke test", source="gmail_smoke")
    act = sh.guard.actions[out["action_id"]]
    print("proposal:", act.state.value, "→", act.payload.to, act.payload.subject, act.payload.file_name)
    if not a.yes:
        sys.exit("Dry run. Re-run with --yes to send.")
    sh.guard.approve(act.id, "owner", act.payload_hash)
    for _ in range(20):
        if act.state.value not in ("EXECUTING", "VERIFICATION_PENDING"):
            break
        time.sleep(3)
    print("result:", act.state.value, "|", sh.guard.status_text(act), "|", act.verification)
