# 🚀 Buildathon: Make Wednesdays Great Again

**Masters' Union · For AI Developers · Winner gets Rs. 25,000**

> **Every team must build in a fork of this repository.** Projects not built in a fork of this repo won't be judged.

| | |
|---|---|
| **Date** | Wednesday, 18 November 2026 |
| **Hacking** | **3:00 PM – 7:00 PM IST** (code freeze at 7:00 PM sharp) |
| **Venue** | CDS Audi, 8th floor |
| **Prize** | Rs. 25,000 to the winning team |
| **Register your fork** | 👉 **[https://forms.gle/ZJUYKwTYjsMsVB2b9](https://forms.gle/ZJUYKwTYjsMsVB2b9)** (**deadline 3:30 PM IST**) |
| **Final submission** | Your fork as it stands at **7:00 PM IST**. There's nothing else to submit. |

> 🤖 **Using an AI coding agent?** Point it at [`AGENTS.md`](AGENTS.md). It has the full event brief, tracks, judging and rules in a form agents can read directly. Claude Code loads it automatically through `CLAUDE.md`, and Codex reads `AGENTS.md` natively.

---

## 🎯 Pick one build track

| # | Track | Brief |
|---|---|---|
| **01** | **Build for the Physical World** | Make a real-world task easier, faster or more reliable. Show it in a realistic scenario. |
| **02** | **Build for AI Agents** | Find something an agent struggles with. Build the tool that fixes it, then demo the agent using it. |
| **03** | **Build in Your Area of Expertise** | Pick a field you know firsthand. Ship a working product that improves how people handle it today. |

## ⚖️ How you'll be judged (each criterion is ⅓ of your score)

| Criterion | The question judges ask |
|---|---|
| **Working product** | Does it do what you say it does? Show the core workflow in your demo. |
| **Problem insight** | Who faces this problem, and why does it happen? |
| **Depth of execution** | How well did you solve the hardest part of the build? |

---

## Why fork this repo?

Everyone starts from the same commit (the **genesis commit**) at the same time. Organizers can then check that:
- all code was written **during** the Buildathon and not brought in from an earlier project,
- teams commit steadily instead of pasting in one huge AI-generated dump at the end,
- every repo stays public and visible while you build.

The organizers track every fork automatically: commits, timing and activity. Read [RULES.md](RULES.md) before you write any code.

---

## ✅ Setup (about 5 minutes, do it at 3:00 PM)

**In short:** fork → register your fork in the form **by 3:30 PM** → build → push before 7:00 PM.

### 1. Fork this repo
Click **Fork** (top right). On the fork screen:
- **Owner:** one team member's personal account. Only **one fork per team**.
- **Repository name:** `buildathon-<team-name>`, for example `buildathon-byte-bandits`
- Click **Create fork**.

> ⚠️ Don't download a ZIP or copy the files into a new repo. **It has to be a real GitHub fork**, or the tracker can't see you.

### 2. Keep it public
Forks of a public repo are public. **Don't make it private, archive it, or delete it** until judging is over.

### 3. Add your teammates
In your fork: **Settings → Collaborators → Add people**. Add each teammate's GitHub account so their commits count toward the team.

### 4. Enable Actions
Open the **Actions** tab of your fork and click **"I understand my workflows, go ahead and enable them"**. This runs the automatic check on every push.

### 5. Make your registration commit (your first commit)
Fill in [`team.json`](team.json). `track` must be one of `physical-world`, `ai-agents` or `area-of-expertise`. Then:

```bash
git clone https://github.com/<your-username>/buildathon-<team-name>.git
cd buildathon-<team-name>
# edit team.json
git add team.json
git commit -m "register: <team name>"
git push
```

The **Hackathon check** in the Actions tab should go green ✅. If it's red, open the run to see what's wrong in `team.json`.

### 6. Register your fork (deadline: 3:30 PM IST)
👉 **[https://forms.gle/ZJUYKwTYjsMsVB2b9](https://forms.gle/ZJUYKwTYjsMsVB2b9)**

It's a 4-question Google Form: team name, fork link, track, team members. It connects your repo to the organizers' live tracker.

- Fill it in **once per team**, right after forking, and **no later than 3:30 PM IST**. **Teams that don't register can't be tracked.**
- Paste your **fork's** URL (`https://github.com/<you>/buildathon-<team-name>`), not this starter repo's.
- Need to change something? Use the **"Edit your response"** link on the confirmation page. Don't fill it in twice.
- **Final submission is automatic.** Whatever is pushed to your fork at 7:00 PM IST is what gets judged.

---

## 🛠 While you build (3:00 – 7:00 PM)

- Put your code anywhere in the repo (`app/`, `src/`, `frontend/`, `backend/`…). There's no required layout.
- **Commit early, commit often**, at least every 30 minutes of real work, with messages that say what changed.
- **Push regularly.** Commits you never push don't exist to the tracker.
- AI coding tools (Claude Code, Codex, Cursor, Copilot…) are **allowed and encouraged**. Keep `AGENTS.md` and `CLAUDE.md` in the repo; they keep your agent within the rules.
- Before 7:00 PM, replace the "Your project" section below with your project's README.

## 🧊 Code freeze: 7:00 PM IST

At 7:00 PM the tracker takes a snapshot of every fork. **Commits pushed after code freeze are ignored.** Judges look at your last commit before 7:00 PM.

## ❌ Things that get you flagged

- Rewriting history (`git push --force`, rebasing away the genesis commit, squashing everything into one commit)
- Commits dated before 3:00 PM
- One or two giant commits containing most of the project
- A repo that isn't a fork of this one, or that's private or deleted

See [RULES.md](RULES.md) for the full list.

---

## Your project

**Shield**: an executive sets one standing policy for what their AI assistant can learn and what it can propose. The assistant can prepare a confidential share without opening the file. The executive approves the exact outgoing message, and Shield verifies what was sent.

- **Team:** Axon (Sneha, `sneha-asi`)
- **Track:** `ai-agents`, Build for AI Agents
- **Problem:** Executives deal with a lot of sensitive information next to routine work: term sheets, cap tables and layoff plans sit beside investor follow-ups, and much of it is other people's data. Their outgoing messages carry authority. Assistants like Instinct, Muse and OpenClaw ask for access to all of it; Instinct emailed an investor "without checking with me first". An assistant that combines private data, untrusted content and a way to act outward can be steered by anything it reads, and a model can't be made to reliably refuse. Vendors' controls are per assistant and self-audited.
- **What we built:** an MCP server the assistant connects to instead of Gmail.
  - **One standing policy** (the founder enables "investor follow-ups" once) governs both what the assistant learns and what it may propose.
  - **Reads:** the assistant gets only handles (`THREAD_1`, `FILE_2`) and summaries that Shield writes itself, never email text, addresses or file contents. Unrelated sensitive mail appears only as withheld counts. Hidden-instruction emails are quarantined.
  - **Actions:** there is no send tool. `propose_send_document(THREAD_1, FILE_2)` answers *that request*: Shield takes the recipient from the request and checks that the file matches what was asked for.
  - **Checks and approval:** five checks run (WHO, WHAT, POLICY, CONTENT, LOCK), then Shield seals the exact message bytes. The founder approves that exact message in a local owner console.
  - **Send and verify:** Shield sends the same bytes it checked and looks the message up in the Sent folder by its sealed Message-ID. Only **Verified in Sent** counts as success.
- **The hardest part:** making "done" trustworthy and at-most-once.
  - Approval binds to a hash of the exact MIME bytes and the attachment, so any change after approval fails before anything is sent.
  - A send-attempt marker is flushed to a local journal before the provider call. A timeout becomes `VERIFICATION_PENDING` and is only ever re-verified, never resent, even after a restart.
  - A Sent record that differs from the approval is `UNVERIFIED` with the differing field. `FAILED` is reserved for messages that definitely weren't sent.
  - The MCP listener is a separate app, so a tunnel to it can't reach approval or raw data.
  - The demo validates the core enforcement path, and the 122-test suite checks the M0 invariants: the five checks, state machine, seal, no-resend, restart recovery, listener isolation, and a fixture-enumerated test that no planted sensitive value reaches the model.
- **How to run it:**
  ```bash
  cd backend && pip install -r requirements.txt && cp .env.example .env   # set SHIELD_USER_SECRET
  python -m pytest -q        # 122 tests
  python run.py              # owner console http://127.0.0.1:8000 · MCP http://127.0.0.1:8765/mcp
  claude mcp add --transport http shield http://127.0.0.1:8765/mcp   # then ask: "Handle my investor follow-ups"
  ```
  Default is the sandbox mailbox. For a live send, set `SHIELD_MAIL=gmail` with a `token.json` (gmail.send + gmail.readonly) for the sender account.
- **Demo:** "Handle my investor follow-ups." In order:
  1. The assistant sees three requests as summaries; the cap table, layoff plan, PAN and medical note appear only as withheld counts; three hidden-instruction items are quarantined.
  2. The stranger's data-room request → 🛑 BLOCKED (unknown recipient; not covered by the policy).
  3. Priya's request → checks green → the founder approves the exact message → ✅ Verified in Sent.
  4. "Did any AI see my cap table today?" → "Shield released the cap table 0 times and withheld it once today."
- **Docs:** [docs/](docs/README.md) has the one-pager, PRD (first principles B1–B6, invariants I1–I10), HLD and LLD.
