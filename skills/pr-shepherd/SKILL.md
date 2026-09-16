---
name: pr-shepherd
description: Ensures completed code changes go through the full quality gate before PR/merge. Use when the user says "approve and merge", "publish approve merge", "PR process", "quality gate", "get this merged", "create PR", "submit PR", "monitor CI", or asks for final review/submission after implementation is complete.
---

> Created/edited by GitHub Copilot with human review/feedback by avilevin.

# PR Shepherd

Ensures every code change goes through the full quality gate (dual/tri model review → CI → merge) before reaching main. Prevents merging unreviewed or untested code.

## When to Use

- After a completed implementation is ready for review, PR creation, CI, or merge
- Especially when the feature involved architectural changes (schema, API surface, DB separation)
- Don't skip when the change 'looks small' — the review often catches real bugs
- When the user says 'approve and merge', 'publish.approve.merge', or 'get this to the PR process'
- When implementation is complete and the user asks for final review, CI, PR creation, publish, approval, merge, or submission

## When Not to Use

- During ordinary implementation, planning, or review-comment iteration before the work is ready for the quality gate
- Repeatedly after each small edit in the same task; wait until there is a completed change set or an explicit PR/merge request

## Instructions

1. Run the full test suite first (`uv run pytest`). Fix failures before proceeding unless they are pre-existing flaky e2e tests.
2. Run lint and type checks (`ruff check`, `ty check`). Fix new errors introduced by this change; pre-existing warnings in unrelated files can be noted but not blocked on.
3. Invoke `tri-review` and use its current dated family-diverse model table. Do not copy model IDs into this skill. Wait for all reviewers to complete.
4. Consolidate review findings by severity. Fix all High findings unconditionally. Discuss Medium findings with user before fixing. Low findings are optional.
5. After review-driven fixes, run a focused follow-up tri-review limited to the reported findings, changed lines, and directly affected behavior. Repeat the full original review scope only when a fix materially broadens the change or alters another high-risk contract.
6. Commit with a descriptive message. Include Co-authored-by trailer. Use conventional commit format (feat/fix/perf/refactor/test/docs). Prefer new commits over --amend.
7. Push to a feature branch. If on main, create a feature branch first.
8. Create a GitHub PR with a clear description. Include summary table of changes, perf improvements if any, and breaking changes.
9. Monitor CI and diagnose failures before asking the user.
10. For UI, demo, walkthrough, showcase, or other user-observable changes, present the final built or deployed result and obtain explicit user verification before merging. Once that gate is satisfied and all checks are green, merge with squash, delete the branch, and update the local main checkout.

## Best Practices

- Do run tri-review before every PR — the models catch real bugs every time (XSS, orphaned DB rows, double-rendering)
- Do keep post-fix review narrow unless the fixes expanded the risk surface
- Do use --force-push only for rebasing onto latest main, never for amending reviewed commits
- **Avoid:** Don't merge if any new test failures exist (even 'seemingly unrelated' ones)
- **Avoid:** Don't treat green CI as user acceptance for visual or experiential changes
- Do bump the version before creating PR — the CI version-bump check will fail otherwise
- **Avoid:** Don't commit stray profiling/scratch scripts that appeared during debugging

## Common Pitfalls

| Problem | Solution |
|---|---|
| CI fails on version bump check | Bump pyproject.toml and __init__.py __version__ before pushing. Patch for bug fixes, minor for features, major for breaking changes. |
| Tri-review finds XSS or security issues after code is written | Always fix High findings before merge — never defer security issues |
| Tests fail due to stale snapshot baselines after CSS/template changes | Regenerate baselines with `pytest --snapshot-update` before committing |
| Pre-push hook lints untracked scratch files and fails | Stash or delete scratch files before pushing; they should not be committed |

## Key Constraints

- Tri-review must run before every PR merge — no exceptions
- All new High findings from review must be fixed before merge
- Version must be bumped on every PR to main
- Never amend commits that have been reviewed — create a new commit
