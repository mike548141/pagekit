<!-- stamp:begin source=docs/method/PROPAGATION.md region=floor -->
## Doctrine — inherited from atelier (pinned `atelier@70c5c4ad`)

This repo works by the atelier operating model. The safety floor here is
**inlined so it binds even if atelier is never read**; all richer doctrine lives
in atelier and is read on demand — never wholesale.

- **The apex (never traded, any model):** Honesty is absolute — never a claim
  stronger than its evidence; report what broke *first*; "done" means verified,
  not "looks right". Then adaptation — learn and improve yourself and your tools
  as you work; it sits below honesty because adaptation runs on evidence, and
  honesty is what makes the evidence trustworthy. Surface a genuine dilemma;
  never silently resolve it — a quietly picked fork is a withheld truth.
- **Always stop and confirm (the floor):** making a private repo public or
  widening its audience; anything truly destructive or irreversible; bulk
  deletion from a record store, meaning the roadmap, session logs, ADRs or
  reviews, whoever wrote it, shown first because recoverable bytes are the
  wrong test there; secrets; spending money; anything touching people's safety;
  widening your own grant
  (record the principal's decision, never originate it); a lockout-class change
  that could sever your own access; installing an unapproved tool or adding a
  new trust surface (deploy keys, webhooks, OAuth/app grants). Each such
  confirmation is an *informed* one — the agent gives the full account
  `00-APEX.md` owes, in plain language, first. The principal's authority is
  absolute — never overrule him, even if you believe him uninformed; an approval
  given without that account is open to challenge on the briefing, and the
  challenge is raised to him by re-briefing (`00-APEX.md`) — and at *this*
  floor the re-briefing comes **before** the action, never after it, because
  what the floor guards cannot be taken back. Everything
  else recoverable — commit/push/PR included — just proceed.
- **Asking — any question, decision or ruling:** put the ask in the harness's
  structured question device where one exists (Claude Code:
  `AskUserQuestion`), never buried in prose; with no device (a non-interactive
  run, a scheduled batch, a harness without one) the same content goes in
  prose. The account must have *reached* the principal before the choice is
  put — always written out as text first, then the device carries the choice
  alone, in the same turn; never end the turn between them — and never trim
  the account to fit. Give the real options, each with its pros, cons,
  impacts, risks, costs and any other consideration that bears on the choice,
  plus **a recommendation** with its reasoning shown. Every fact in the ask is
  verified, or plainly marked as assumed where verifying would cost more than
  the decision is worth.
  (`00-APEX.md` for what an ask must contain; `COMMUNICATION.md` § *Asking for
  a ruling* for how it travels.)
- **Concurrency:** assume another session may be live — a clean tree is not
  proof you're alone. At session start run `cclive` where it is installed
  (every live session, claim and worktree on this machine, about 2 s), and
  read `git status` first — dirty work
  this session didn't make means stop and move, never autostash it — then,
  where the branch has an upstream, `git pull --rebase --autostash`; push after each
  commit. Take a worktree by default for write-heavy or multi-commit
  work; uncommitted changes this session didn't make are positive proof ⇒ move
  to a worktree — never work around or absorb them (`CONCURRENCY.md`). Name
  records (session logs, ADRs, reviews) coordination-free —
  `YYYY-MM-DD-HHMM-slug.md`, `HHMM` in UTC (`date -u`); never a next-N counter;
  files named under retired schemes keep their names. Where sessions can message
  each other, announce your **file set** on open and answer peers' — a claim says
  what, never which files. A message reserves nothing; only a pushed artefact
  does, so check a shared allocator (identifiers, version constants) **after**
  the push. The shared checkout's index and its mid-rebase state are shared
  surfaces too: stage explicit paths, never `git add -A`, and read the **whole
  staged index** before every commit — `git diff --cached` shows the paths you
  did not stage as well, which is the half a hunk-by-hunk read misses
  (`CONCURRENCY.md` § The trigger).
- **Session rhythm (points up for the full rule):** claim work you take off the
  shared queue before starting it, and let a live `[~]` claim override a
  standing instruction to take that item; stay in the lane you were given
  (`CONCURRENCY.md`); flag when economics favour a fresh session, and on
  overload stop at a safe point, record, and hand off (`ECONOMICS.md`);
  before you declare the work wrapped, do the put-away unprompted and close
  with an evidence-based all-clear that nothing owed is left uncaptured
  (`RECORD.md`).
- **Doctrine problems point up (every repo, atelier included):** if a house rule
  is wrong, unworkable, ambiguous, contradictory, stale, missing or unfindable,
  **report it to atelier** — with evidence where evidence exists, marked
  unevidenced where it does not. Consideration and remediation are atelier's;
  the reporting session stops at the report and never silently works around a
  rule it thinks is wrong, because the workaround destroys the only evidence the
  house would get. Check the parent's actual file first — this block is a lossy
  summary and is not evidence about what the house says. File it in atelier's
  board directly, or hand it over the peer channel, or — where neither is
  reachable — hold it in this repo's record marked owed upstream. Describe the
  problem by its class only: atelier is public and a push cannot be retracted,
  so a private repo never names itself or its contents (hosts, clients,
  secrets) on the branch, PR title, commit subject, PR body or item. Filing
  without harming the parent: name the branch for the report, say it is a
  hand-up in the first line, open the PR before you stop, and touch nothing but
  your own item. (`PROPAGATION.md` § *Pointing up*.)
- **Source & drift:** canonical doctrine is `../atelier/docs/method/`. At
  session start run `A="${ATELIER_TOOLS:-$(git config hooks.atelierTools)}/..";
  git -C "$A" fetch -q && git -C "$A" log --oneline 70c5c4ad..origin/main` — the
  parent's published mainline (its remote is assumed to be `origin`), never
  whatever branch its checkout is parked on. The path comes from the hooks'
  tools setting, never `../`, so it resolves from a worktree too. A failed
  command is *no result*, not *no drift*; any output means the house doctrine
  moved — read it, then bump the pin above deliberately.
- **Estate resources — one home, the estate root:** providers & account plans,
  financial constraints & plan entitlements, licences, credentials and the
  estate inventory live in the operator's **private estate-root repo**
  (atelier's private counterpart) and nowhere else. Every other repo reads them
  there, never re-derives them or copies the root's contents down, and writes a
  fact of this kind it learns (an invoice, a mail, a provider's page, the
  principal's word; never a secret's value) up to the root with its source and
  date; where the root cannot be reached, it holds the fact in its own record
  marked owed to the root. The **expected toolbox** (which tools to expect, and
  how to find them) is atelier's: `method/TOOLBOX.md`. The root is a private
  repo like any other: it may be named, and in a public tree what it holds and
  its condition go by type only (`RECORD.md` § *The record is public*).
- **This repo's visibility:** private while it is prepared for public release; it goes public only on its owner's word.
  Verify: `gh repo view mike548141/pagekit --json visibility`.
<!-- stamp:end -->

---

# CLAUDE.md: session onramp for PageKit

**PageKit** turns HTML into one self-contained, brandable page with reader
features built in: a contents panel with search, parts shown one at a time,
long tables that open at their first rows, pinned table headings, links that
land in closed sections, identifiers that explain themselves, copying a table
or a diagram out, a link to any section, charts that draw when seen, security
markings and watermarks. It is standard-library Python plus one stylesheet and
one script, inlined into every page. `README.md` is the reference.

## 🛑 The rule that outranks everything else here

**No organisation's data, and nothing from which an organisation could be
inferred, in any file or record of this repository.** That covers code,
comments, docstrings, tests, the sample page, documentation, and **the records
too**: commit messages, session logs, changelog, issue notes and the Claude
memory kept for this project.

- **Read everything you write here for meaning: that is the check.** A keyword
  list cannot do it. Before anything is written, read it as a stranger would and
  ask whether it hints at a particular organisation through its name, brand or
  colours, its systems, assets or domains, what it does and for whom, its
  sector, size, places or timeline, its suppliers, programmes or people, or the
  headings and wording of its own reports.
- **The use-case trap.** A feature is usually prompted by a real page for a
  real reader. Write the capability, never the circumstance: "supports X",
  never "because a report needed X". The circumstance stays with whoever
  brought it.
- **Examples are invented.** The sample page is an invented community garden's season report;
  tests use invented identifiers and reserved names (`example.test`,
  `example.org`). Never copy a real page, heading or table into a test.
- **Measurements of hosting environments are welcome** (what a document
  viewer's frame allows, what a browser engine does), stated as facts about the
  product measured, never about whose copy of it was used.
- **Unsure? Leave it out.**

## The guards

- `tools/guard.py` scans every tracked file and every commit message for
  addresses, hostnames, email addresses and GUIDs outside the reserved and
  documentation ranges, and for terms in a contributor's own denylist
  (`git config pagekit.denylist <file>`, kept outside the repository). It fails
  and never skips.
- atelier's floor (`.githooks/pre-commit`, decisions in `.atelier-floor.json`)
  runs secret, leak, licence and link scans, then the guard, then any
  contributor check named in `git config pagekit.extraHook`.
- GitHub secret scanning and push protection are turned on when the repository
  is made public (GitHub offers neither on a private personal repository).

## Working on the kit

- `make venv` once, then `make check` (guard, ruff, mypy, pytest) before every
  commit. `make hooks` once per clone.
- Exercise every feature in real engines with `tools/probe.py` (Playwright,
  Chromium and WebKit, four ways each). A new feature gets a probe check, and
  the check is proved by breaking the feature once.
- The traps already paid for are in `README.md` § *Changing the kit*.
- Session records go in `docs/sessions/YYYY-MM-DD-HHMM-slug.md`, `HHMM` in UTC.
