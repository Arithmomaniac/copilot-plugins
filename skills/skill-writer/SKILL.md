---
name: skill-writer
description: Guide users through creating Agent Skills for Claude Code. Use when the user wants to create, write, author, or design a new Skill, or needs help with SKILL.md files, frontmatter, or skill structure. Before creating a new skill, check whether an existing skill can be reused, extended, or discovered first.
---

# Skill Writer

This Skill helps you create well-structured Agent Skills for Claude Code that follow best practices and validation requirements.

## When to use this Skill

Use this Skill when:
- Creating a new Agent Skill
- Writing or updating SKILL.md files
- Designing skill structure and frontmatter
- Troubleshooting skill discovery issues
- Converting existing prompts or workflows into Skills
- The workflow is genuinely novel and not already covered by an installed or discoverable skill

## Instructions

### Step 1: Determine Skill scope

First, understand what the Skill should do:

1. **Ask clarifying questions**:
   - What specific capability should this Skill provide?
   - When should Claude use this Skill?
   - What exact user phrases should trigger it?
   - What adjacent phrases should **not** trigger it?
   - What inputs does it expect, and what output should it produce?
   - What tools or resources does it need?
   - What external dependencies, accounts, or data sources does it rely on?
   - Is this for personal use or team sharing?
   - Should it be a personal skill, project skill, or plugin-distributed skill?
   - Could this be a refinement of an existing skill instead of a brand-new one?

2. **Check for reuse first**:
   - Re-read nearby installed skills if the workflow sounds adjacent
   - Use a discovery/search skill before creating a new one for a domain you haven't checked yet
   - Prefer extending an existing skill when the new behavior is a tighter trigger, fallback, or reference section
   - Check discoverable marketplace plugins when the request is generic authoring, evaluation, scaffolding, or publishing; do not create a duplicate local skill if an installed/discoverable plugin already covers the need
   - If a marketplace plugin is close but not exact, borrow its pattern and explain why the local skill still needs to exist

3. **Load the domain skill when updating one**:
   - When auditing, reviewing, or updating a specific domain skill, read that skill's `SKILL.md` and any relevant supporting files before proposing behavior changes.
   - `skill-writer` is only the meta-authoring guide for skill structure, frontmatter, validation, and trigger hygiene; it is not enough to understand domain-specific behavior.
   - Use the domain skill's current instructions as the source of truth for its workflow, tools, triggers, and non-triggers, then apply `skill-writer` guidance to make those instructions valid and discoverable.

4. **Keep it focused**: One Skill = one capability
   - Good: "PDF form filling", "Excel data analysis"
   - Too broad: "Document processing", "Data tools"

### Step 2: Choose Skill location

Determine where to create the Skill:

**Personal Skills** (`~/.copilot/skills/`):
- Individual workflows and preferences
- Experimental Skills
- Personal productivity tools

**Project Skills** (`.copilot/skills/`):
- Team workflows and conventions
- Project-specific expertise
- Shared utilities (committed to git)

### Step 3: Create Skill structure

Create the directory and files:

```bash
# Personal
mkdir -p ~/.copilot/skills/skill-name

# Project
mkdir -p .copilot/skills/skill-name
```

For multi-file Skills:
```
skill-name/
├── SKILL.md (required)
├── reference.md (optional)
├── examples.md (optional)
├── scripts/
│   └── helper.py (optional)
└── templates/
    └── template.txt (optional)
```

### Step 4: Write SKILL.md frontmatter

Create YAML frontmatter with required fields:

```yaml
---
name: skill-name
description: Brief description of what this does and when to use it
---
```

**Field requirements**:

- **name**:
  - Lowercase letters, numbers, hyphens only
  - Max 64 characters
  - Must match directory name
  - Good: `pdf-processor`, `git-commit-helper`
  - Bad: `PDF_Processor`, `Git Commits!`

- **description**:
  - Max 1024 characters
  - Include BOTH what it does AND when to use it
  - Use specific trigger words users would say
  - Mention file types, operations, and context

**Optional frontmatter fields**:

- **allowed-tools**: Restrict tool access (comma-separated list)
  ```yaml
  allowed-tools: Read, Grep, Glob
  ```
  Use for:
  - Read-only Skills
  - Security-sensitive workflows
  - Limited-scope operations

### Step 5: Write effective descriptions

The description is critical for Claude to discover your Skill.

**Formula**: `[What it does] + [When to use it] + [Key triggers]`

**Examples**:

✅ **Good**:
```yaml
description: Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
```

✅ **Good**:
```yaml
description: Analyze Excel spreadsheets, create pivot tables, and generate charts. Use when working with Excel files, spreadsheets, or analyzing tabular data in .xlsx format.
```

❌ **Too vague**:
```yaml
description: Helps with documents
description: For data analysis
```

**Tips**:
- Include specific file extensions (.pdf, .xlsx, .json)
- Mention common user phrases ("analyze", "extract", "generate")
- List concrete operations (not generic verbs)
- Add context clues ("Use when...", "For...")

### Step 6: Structure the Skill content

Use clear Markdown sections:

```markdown
# Skill Name

Brief overview of what this Skill does.

## Quick start

Provide a simple example to get started immediately.

## Instructions

Step-by-step guidance for Claude:
1. First step with clear action
2. Second step with expected outcome
3. Handle edge cases

## Examples

Show concrete usage examples with code or commands.

## Best practices

- Key conventions to follow
- Common pitfalls to avoid
- When to use vs. not use

## Requirements

List any dependencies or prerequisites:
```bash
pip install package-name
```

## Advanced usage

For complex scenarios, see [reference.md](reference.md).
```

### Step 7: Add progressive disclosure (optional)

Use progressive disclosure when the Skill has important detail that should not be loaded on every invocation. Keep `SKILL.md` small, actionable, and sufficient for the normal path; put optional depth in supporting files.

Keep in `SKILL.md`:
- Frontmatter and activation guidance
- Quick start and the normal happy-path workflow
- Required first-run steps and hard constraints
- Links to supporting files with clear "read when" instructions

Move to supporting files:
- **reference.md**: Detailed API docs, option matrices, schemas, and advanced behavior
- **examples.md**: Extended examples, realistic prompts, expected outputs, and edge cases
- **scripts/**: Helper scripts and utilities
- **templates/**: Boilerplate files, prompt templates, or output templates
- **data/** or **config.json**: Large lookup tables or configuration defaults

Reference supporting files from `SKILL.md` only when the main workflow needs them:
```markdown
For advanced usage, see [reference.md](reference.md).
For realistic examples and expected outputs, see [examples.md](examples.md).

Run the helper script:
\`\`\`bash
python scripts/helper.py input.txt
\`\`\`
```

Avoid these progressive disclosure anti-patterns:
- Hiding required first-run setup in a file the agent might not read
- Linking to files without saying when to read them
- Splitting guidance into many tiny files that force excessive context loading
- Duplicating the same instructions in `SKILL.md` and `reference.md`
- Moving safety constraints out of the primary `SKILL.md`

### Step 8: Validate the Skill

Check these requirements:

✅ **File structure**:
- [ ] SKILL.md exists in correct location
- [ ] Directory name matches frontmatter `name`

✅ **YAML frontmatter**:
- [ ] Opening `---` on line 1
- [ ] Closing `---` before content
- [ ] Valid YAML (no tabs, correct indentation)
- [ ] `name` follows naming rules
- [ ] `description` is specific and < 1024 chars

✅ **Content quality**:
- [ ] Clear instructions for Claude
- [ ] Concrete examples provided
- [ ] Edge cases handled
- [ ] Dependencies listed (if any)

✅ **Testing**:
- [ ] Description matches user questions
- [ ] Skill activates on relevant queries
- [ ] Instructions are clear and actionable

### Step 9: Test the Skill

1. **Restart Claude Code** (if running) to load the Skill

2. **Ask relevant questions** that match the description:
   ```
   Can you help me extract text from this PDF?
   ```

3. **Verify activation**: Claude should use the Skill automatically

4. **Check behavior**: Confirm Claude follows the instructions correctly

### Step 10: Debug if needed

If Claude doesn't use the Skill:

1. **Make description more specific**:
   - Add trigger words
   - Include file types
   - Mention common user phrases

2. **Check file location**:
   ```bash
   ls ~/.copilot/skills/skill-name/SKILL.md
   ls .copilot/skills/skill-name/SKILL.md
   ```

3. **Validate YAML**:
   ```bash
   cat SKILL.md | head -n 10
   ```

4. **Run debug mode**:
   ```bash
   claude --debug
   ```

## Common patterns

### Read-only Skill

```yaml
---
name: code-reader
description: Read and analyze code without making changes. Use for code review, understanding codebases, or documentation.
allowed-tools: Read, Grep, Glob
---
```

### Script-based Skill

```yaml
---
name: data-processor
description: Process CSV and JSON data files with Python scripts. Use when analyzing data files or transforming datasets.
---

# Data Processor

## Instructions

1. Use the processing script:
\`\`\`bash
python scripts/process.py input.csv --output results.json
\`\`\`

2. Validate output with:
\`\`\`bash
python scripts/validate.py results.json
\`\`\`
```

### Multi-file Skill with progressive disclosure

```yaml
---
name: api-designer
description: Design REST APIs following best practices. Use when creating API endpoints, designing routes, or planning API architecture.
---

# API Designer

Quick start: See [examples.md](examples.md)

Detailed reference: See [reference.md](reference.md)

## Instructions

1. Gather requirements
2. Design endpoints (see examples.md)
3. Document with OpenAPI spec
4. Review against best practices (see reference.md)
```

### Skill with reference material

Use this pattern when the skill has a compact workflow plus large optional detail:

```markdown
# Incident Query Helper

## Quick start

1. Gather the incident ID and affected service.
2. Run the standard query.
3. Summarize impact and next action.

## References

- Read [queries.md](queries.md) when the standard query is insufficient.
- Read [examples.md](examples.md) when drafting user-facing incident summaries.
- Use `scripts/normalize.py` only after confirming the raw export path.
```

## Best practices for Skill authors

1. **One Skill, one purpose**: Don't create mega-Skills
2. **Specific descriptions**: Include trigger words users will say
3. **Clear instructions**: Write for Claude, not humans
4. **Concrete examples**: Show real code, not pseudocode
5. **List dependencies**: Mention required packages in description
6. **Test with teammates**: Verify activation and clarity
7. **Version your Skills**: Document changes in content
8. **Use progressive disclosure**: Put advanced details in separate files
9. **Design negative triggers**: State when adjacent workflows should use a different skill or no skill
10. **Prefer reuse over duplication**: Improve an existing skill when the request is a refinement, not a new capability

## Quality gate

Before finalizing a Skill, give it a short quality verdict:

| Dimension | Check |
|-----------|-------|
| Instruction clarity | Can Claude follow the steps without guessing? |
| Behavioral completeness | Are setup, normal path, edge cases, and exit conditions covered? |
| Trigger specificity | Does the description include realistic user phrases and file/context clues? |
| Negative triggers | Does it distinguish nearby skills and non-goals? |
| Example quality | Are examples concrete enough to anchor behavior? |
| Progressive disclosure fit | Is required guidance in `SKILL.md` and optional detail in supporting files? |
| Safety boundaries | Are destructive actions, credentials, and external data handled explicitly? |
| Tool fit | Are required tools/resources named without over-granting access? |
| Portability | Will it work in the intended personal/project/plugin location? |
| Maintainability | Is repeated or volatile detail factored into references, scripts, or templates? |

Use the verdict to recommend one of: **keep**, **tighten triggers**, **move detail to supporting files**, **inline critical rules**, **merge with an existing skill**, or **defer to an existing plugin**.

## Validation checklist

Before finalizing a Skill, verify:

- [ ] Name is lowercase, hyphens only, max 64 chars
- [ ] Description is specific and < 1024 chars
- [ ] Description includes "what" and "when"
- [ ] YAML frontmatter is valid
- [ ] Instructions are step-by-step
- [ ] Examples are concrete and realistic
- [ ] Dependencies are documented
- [ ] File paths use forward slashes
- [ ] Supporting files are linked with clear "read when" guidance
- [ ] Required setup and safety rules are not hidden in supporting files
- [ ] Nearby installed/discoverable skills or plugins were considered before creating a duplicate
- [ ] Skill activates on relevant queries
- [ ] Claude follows instructions correctly

## Troubleshooting

**Skill doesn't activate**:
- Make description more specific with trigger words
- Include file types and operations in description
- Add "Use when..." clause with user phrases

**Multiple Skills conflict**:
- Make descriptions more distinct
- Use different trigger words
- Narrow the scope of each Skill

**Skill has errors**:
- Check YAML syntax (no tabs, proper indentation)
- Verify file paths (use forward slashes)
- Ensure scripts have execute permissions
- List all dependencies

## Examples

See the documentation for complete examples:
- Simple single-file Skill (commit-helper)
- Skill with tool permissions (code-reviewer)
- Multi-file Skill (pdf-processing)

## Output format

When creating a Skill, I will:

1. Ask clarifying questions about scope and requirements
2. Suggest a Skill name and location
3. Create the SKILL.md file with proper frontmatter
4. Include clear instructions and examples
5. Add supporting files if needed
6. Provide testing instructions
7. Validate against all requirements

The result will be a complete, working Skill that follows all best practices and validation rules.
