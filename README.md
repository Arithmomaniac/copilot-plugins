# Copilot Plugins

A Claude Code plugin marketplace with agent skills for Git workflows, productivity, and developer tools.

## Install

Add this marketplace to Claude Code:

```
/plugin marketplace add arithmomaniac/copilot-plugins
```

Or via CLI:

```bash
claude plugin marketplace add arithmomaniac/copilot-plugins
```

Individual skills can also be installed via [claude-plugins.dev](https://claude-plugins.dev):

```bash
npx skills-installer install @arithmomaniac/copilot-plugins/skill-name
```

## Available Skills

| Skill | Description |
|-------|-------------|
| **clipboard-markdown** | Copy text to clipboard as markdown or block-quoted markdown |
| **create-worktree** | Create git branches and worktrees from context |
| **git-branch-cleanup** | Clean up stale git branches and worktrees |
| **goral-hagra** | Torah/Tanakh verse guidance via Sefaria API |
| **openspec-workflow** | Spec-driven development workflow with multi-model review |
| **skill-writer** | Guide for authoring Claude Code Agent Skills |
| **skills-discovery** | Search and install skills from the claude-plugins.dev registry |
| **azsafe** | Safe read-only Azure CLI proxy |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding new skills.

## License

[MIT](LICENSE)
