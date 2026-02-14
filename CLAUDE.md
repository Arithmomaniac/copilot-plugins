# Copilot Plugins Marketplace

This repository is a Claude Code plugin marketplace. Skills are distributed via `.claude-plugin/marketplace.json`.

## Marketplace Maintenance Rules

**When adding a new skill:**
1. Create the skill directory under `skills/<skill-name>/` with a `SKILL.md` file
2. Add a corresponding plugin entry to `.claude-plugin/marketplace.json` with: name, description, source: "./", strict: false, version, category, keywords, and skills array pointing to the skill directory
3. Validate with `claude plugin validate .`

**When renaming a skill:**
1. Rename the directory under `skills/`
2. Update the corresponding entry in `.claude-plugin/marketplace.json` (name and skills path)
3. Validate with `claude plugin validate .`

**When removing a skill:**
1. Delete the directory under `skills/`
2. Remove the corresponding entry from `.claude-plugin/marketplace.json`
3. Validate with `claude plugin validate .`

## Skill Structure

Each skill directory must contain at minimum a `SKILL.md` with YAML frontmatter:

```yaml
---
name: skill-name
description: What this skill does and when to use it (include trigger keywords)
---
```

Optional additional files: `reference.md`, `examples.md`, `scripts/`, `templates/`, `data/`, `config.json`.
