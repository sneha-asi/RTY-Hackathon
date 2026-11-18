# Work plan to code freeze (7:00 PM IST)

Two coding agents, split by **file ownership** so we never edit the same file. Read [AGENTS.md](../AGENTS.md) rules first: small commits, push often, no force-push, no rebase of `main`, no amending pushed commits, no secrets in git.

## Already done (don't redo)

Slices 1, 2, 3, 5 and 7 from LLD §16, with 29 tests (`cd backend && python -m pytest -q`):

- standing policy (`data/policy.json`)
- broker summaries; cleaner and quarantine
- request-bound `propose_send_document(request, file, note)` with WHO / WHAT / POLICY / CONTENT / LOCK
- exact-MIME seal; owner-only approval
- no-resend with a durable journal; `VERIFICATION_PENDING` / `UNVERIFIED`
- separate MCP listener (`:8765/mcp`); owner console (`127.0.0.1:8000`); receipts

Run: `cd backend && python run.py`.

## Ownership

| Area | Owner | Files |
|---|---|---|
| Detector + cleaner unit tests (and bug fixes they reveal) | **Codex** | `backend/tests/test_detectors.py`, `backend/tests/test_cleaner.py`, `backend/app/labels.py`, `backend/app/cleaner.py` |
| Live Gmail path | **Codex** | `backend/app/mail.py` (`GmailMail` and `parse_raw` only), `backend/scripts/gmail_token.py`, `backend/scripts/gmail_smoke.py` |
| Demo runbook + reset script | **Codex** | `docs/DEMO.md`, `backend/scripts/demo_reset.sh` |
| Direct-vs-Shielded comparison | **Claude** | `backend/app/direct_tools.py`, `backend/app/harness.py`, `backend/tests/test_harness_scoring.py` |
| Server, guard, broker, console | **Claude** | `backend/app/main.py`, `guard.py`, `broker.py`, `service.py`, `tools.py`, `static/index.html`, `run.py` |
| Docs (PRD / HLD / LLD / one-pager / README) | **Claude** | `docs/*.md` except `DEMO.md`, `README.md` |

If you need a change in a file you don't own, write it down in your final note instead of editing it.

## Codex tasks (in order, about 45 min total)

1. **Detector and cleaner tests** (~15 min). Follow LLD §4.1, §4.2 and §15.
   - `test_detectors.py`: each detector in `labels.DETECTORS` gets at least 2 positive and 2 negative cases. Cover a bad Verhoeff Aadhaar, a bad-Luhn card, a PAN with a wrong 4th character, UPI vs email, and a GSTIN with a bad state code. Also test overlap resolution (longest span wins) and `labels_for` keywords.
   - `test_cleaner.py`: one case per hidden rule:
     - `display:none`
     - `visibility:hidden`
     - `font-size:0` / ≤2px
     - `opacity:0`
     - white on white
     - off-screen positioning
     - `hidden` / `aria-hidden`
     - comments, `<script>`, `<style>`
   - Also in `test_cleaner.py`:
     - zero-width characters and whitespace padding
     - each instruction pattern
     - a trusted sender with a visible instruction is not quarantined
     - hidden text with an instruction is quarantined for any sender
     - a newsletter preheader (hidden, no instruction) is not quarantined
     - seed items e10, e11 and ev6 are quarantined
   - Fix real bugs in `labels.py` / `cleaner.py`; keep the public functions (`detect`, `labels_for`, `clean`, `scan`) unchanged.
2. **Live Gmail path** (~20 min). Follow LLD §6–§7.
   - `scripts/gmail_token.py`: run the installed-app OAuth flow from `credentials.json`, with scopes `gmail.send` and `gmail.readonly`, and write `token.json`. Both files are git-ignored; never commit them.
   - `scripts/gmail_smoke.py`: build a payload with `guard.build_mime` (one `To`), send it with `GmailMail.send_raw`, then poll `GmailMail.find_sent(message_id)`. Print whether recipients, subject, normalised body and attachment `(filename, sha256)` match.
   - Fix `GmailMail` / `parse_raw` so Gmail's Sent copy parses to the same values as FakeMail. Watch for header folding, display names, CRLF in the body, and attachment filename encoding. Keep the `MailClient` interface (`send_raw(raw, envelope, bcc)`, `find_sent(message_id_header)`) unchanged.
   - Done when one real email to the investor test inbox verifies with `SHIELD_MAIL=gmail`.
3. **Demo runbook** (~10 min). `docs/DEMO.md`, following PRD §10.10 and the one-pager demo section:
   - exact commands: env, `python run.py`, `claude mcp add --transport http shield http://127.0.0.1:8765/mcp`
   - the one prompt: *"Handle my investor follow-ups"*
   - what should appear on the console at each step
   - the single approval, and the receipt question
   - the sandbox fallback switch (`SHIELD_MAIL=fake`)

   `scripts/demo_reset.sh` calls `POST /dev/reset` and prints the console URL. Rehearse it once end to end and note anything that breaks.

## Claude tasks

1. Direct-vs-Shielded comparison: raw tools on the same sandbox, the same request and model, scored from sandbox state (sensitive values exposed, task completed). Shown on the console as measured numbers.
2. Keep the docs in sync with whatever Codex changes; keep `main` updated.

## Sync points (IST)

| Time | What |
|---|---|
| 6:30 | Feature freeze. Both agents push; Claude merges to `main`. `pytest` green |
| 6:30–6:50 | Rehearse the demo 5× (live Gmail, or the sandbox fallback); record the backup video |
| 6:55 | Final push. Nothing after 7:00 |

## Hand-off

Codex works in the user's local copy and does **not** use git. When a task is done, the user gives Claude the changed files. Claude puts them in the repo, runs `pytest`, commits and pushes to the branch and `main`.

Hand-offs:

| By (IST) | Files |
|---|---|
| ~6:05 | Task 1: test files and any fixes |
| ~6:20 | Task 2: Gmail files |
| ~6:25 | Task 3: demo runbook and reset script |
