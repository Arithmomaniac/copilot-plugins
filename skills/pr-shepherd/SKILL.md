---
name: pr-shepherd
description: Ensures every code change goes through the full quality gate before merge. Use when the user says "approve and merge", "publish approve merge", "PR process", "quality gate", "get this merged", "create PR", "submit PR", or after any implementation touching more than one file.
---

# PR Shepherd

Ensures every code change goes through the full quality gate (dual/tri model review → VS Code open → CI → merge) before reaching main. Prevents merging unreviewed or untested code.

## When to Use

- After any implementation that touches more than one file
- Especially when the feature involved architectural changes (schema, API surface, DB separation)
- Don't skip when the change 'looks small' — the review often catches real bugs
- When the user says 'approve and merge', 'publish.approve.merge', or 'get this to the PR process'

## Instructions

1. Run the full test suite first (`uv run pytest`). Fix failures before proceeding unless they are pre-existing flaky e2e tests.
2. Run lint and type checks (`ruff check`, `ty check`). Fix new errors introduced by this change; pre-existing warnings in unrelated files can be noted but not blocked on.
3. Launch tri-review in parallel (Sonnet 4.6, GPT-5.4, and optionally a third model). Wait for all to complete.
4. Consolidate review findings by severity. Fix all High findings unconditionally. Discuss Medium findings with user before fixing. Low findings are optional.
5. Open the diff in VS Code (`code --diff` or `code .`) so the user can review the actual changes before committing.
6. Commit with a descriptive message. Include Co-authored-by trailer. Use conventional commit format (feat/fix/perf/refactor/test/docs). Prefer new commits over --amend.
7. Push to a feature branch. If on main, create a feature branch first.
8. Create a GitHub PR with a clear description. Include summary table of changes, perf improvements if any, and breaking changes.
9. Monitor CI — check all 5 checks (version bump, lint ubuntu, lint windows, tests ubuntu, tests windows). Diagnose failures before asking user.
10. Once all checks green, merge with squash. Delete the branch. Pull main locally.

## Best Practices

- Do run tri-review before every PR — the models catch real bugs every time (XSS, orphaned DB rows, double-rendering)
- **Avoid:** Don't skip the VS Code open step — user wants to visually confirm diffs before commit
- Do use --force-push only for rebasing onto latest main, never for amending reviewed commits
- **Avoid:** Don't merge if any new test failures exist (even 'seemingly unrelated' ones)
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
