Codex task routing
===================

Why this exists
----------------

Two kinds of work show up in an agent session: figuring out *what* to
do (exploration, design, planning) and actually *doing* it (editing
files, running commands that change state). This project routes those
two kinds of work to different tools so that implementation work goes
through Codex CLI rather than staying in the same Claude Code session
that planned it.

The rule
--------

- **Exploratory / design tasks** (reading code, understanding a bug,
  drafting an approach, writing a plan) → stay in Claude Code.
- **Execution / implementation tasks** (editing files, running
  migrations, anything that changes repo state) → route to Codex CLI
  via the `mcp__codex__codex` MCP tool.
- **If unsure**, start with `/plan` in Codex; escalate back to Claude
  Code if more reasoning is needed before implementation can start.
- **Small-fix override**: trivial, one-line/typo-scale changes
  (renaming a variable, fixing an obvious string, adjusting a comment)
  may be made directly in the Claude Code session without routing to
  Codex. If a change grows past that scope mid-edit, stop and route
  the rest to Codex instead of continuing inline.

Trigger point
--------------

In a Claude Code session, the routing decision is made **immediately
after a plan is approved** (i.e. right after `ExitPlanMode` is
accepted) for anything implementation-shaped. At that point, hand the
approved plan to Codex via `mcp__codex__codex` using the Implementation
Plan Format below, instead of continuing to call `Edit` / `Write` /
`NotebookEdit` directly in the same session.

Implementation Plan Format
---------------------------

Example format:

```text
### Step 1: [scope] — [action]

**Files to change:** src/config/config.py, src/plugin/api.py
**What to do:** [precise instruction]
**Verify:** Run `appropriate test tool` — should pass

### Step 2: [...]
```

Sandbox mode: use `danger-full-access` for now
------------------------------------------------

`mcp__codex__codex` accepts a `sandbox` parameter. The expected/default
value, `workspace-write`, currently **fails on this host** because
Codex CLI's bubblewrap (bwrap) sandbox cannot bring up the loopback
interface inside its network namespace when nested under Claude Code's
own sandbox, combined with Ubuntu 24.04's
`kernel.apparmor_restrict_unprivileged_userns=1` default. Every
`workspace-write` call fails before the underlying command even runs.
Symptoms look like:

```text
bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted
```

```text
Failed to write file <path>
```

**Until this is fixed**, pass `sandbox: "danger-full-access"` when
invoking `mcp__codex__codex` / `mcp__codex__codex-reply`:

```text
mcp__codex__codex(
  prompt: "<implementation plan, in the format above>",
  cwd: "<repo root>",
  sandbox: "danger-full-access",
  approval-policy: "never"
)
```

`danger-full-access` removes filesystem and network sandboxing for
whatever Codex decides to run. This is an accepted tradeoff for
routing already-planned, trusted, local work in this repo — it is
**not** a substitute for fixing the underlying bwrap/userns issue, and
must not be used to run arbitrary or untrusted prompts. This is a
host-level sandbox limitation, not specific to this repo. Revisit this
section once the underlying bwrap/userns issue is fixed upstream, and
default back to `workspace-write`.
