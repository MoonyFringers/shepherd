# Agent workflows

These documents are the repository's agent-neutral operational guidance.
They apply to people and every coding agent. Claude-specific wrappers in
`.claude/` preserve Claude discovery only and must not diverge from these
documents.

| Workflow | Use when |
| --- | --- |
| [release-process](release-process.md) | Cut a release, bump version, publish a build |
| [plugin-authoring](plugin-authoring.md) | Build or modify a shepherd plugin |
| [pr-prep](pr-prep.md) | Commit, push, or open a pull request |
| [local-dev-testing](local-dev-testing.md) | Set up the dev environment, run tests/lint locally |
| [codex-task-routing](codex-task-routing.md) | Decide whether a task should run in Claude Code or route to Codex MCP |
