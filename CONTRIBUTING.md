# Contributing to Copilot Plugins

Thank you for your interest in contributing skills to this marketplace!

## Adding a New Skill

1. **Create a skill directory** under `skills/your-skill-name/`
2. **Add a `SKILL.md`** with YAML frontmatter:
   ```yaml
   ---
   name: your-skill-name
   description: What this skill does and when to use it
   ---

   # Your Skill Name

   Instructions for the agent...
   ```
3. **Update `.claude-plugin/marketplace.json`** — add a plugin entry for your skill
4. **Validate** — run `claude plugin validate .` to ensure the marketplace is valid
5. **Submit a PR** with your changes

## Skill Guidelines

- **One skill = one focused capability** — don't bundle unrelated features
- **Description must include trigger words** — how would a user ask for this?
- **Name must be kebab-case** — lowercase letters, numbers, hyphens only
- **No proprietary dependencies** — skills should work for anyone
- **Include examples** — concrete usage examples help the agent use the skill correctly

## Testing Your Skill

Load the marketplace locally for testing:
```
claude --plugin-dir ./
```

Or add the marketplace:
```
/plugin marketplace add ./
```
