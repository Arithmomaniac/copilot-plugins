---
name: agent-writer
description: >-
  Guide users through creating and updating custom Agent files (.agent.md) for Copilot CLI.
  Use when the user says "create an agent", "write an agent", "update this agent",
  "improve this agent", "new agent", or "agent file". Distinct from skill-writer which
  handles SKILL.md files — agents are interactive workflow orchestrators selected via /agent,
  while skills inject triggered reference knowledge into the main agent's context.
---

# Agent Writer

Create well-structured `.agent.md` files for GitHub Copilot CLI custom agents. Agents are single-file workflow orchestrators — they define a role, a phased workflow with checkpoints, and battle-tested tips learned from real usage.

## When to Use

- Creating a new custom agent (`.agent.md`)
- Updating or improving an existing agent after a session revealed gaps
- Converting a workflow or prompt into a reusable agent
- Troubleshooting agent discovery or behavior issues

## NOT This Skill

- Creating `SKILL.md` files → use **skill-writer** instead
- Creating `AGENTS.md` / `CLAUDE.md` → repo-level instructions for the main agent
- Creating `.instructions.md` files → custom instructions, not agents

## Agent vs Skill

| Aspect | Agent (`.agent.md`) | Skill (`SKILL.md`) |
|--------|--------------------|--------------------|
| Location | `~/.copilot/agents/` or `.github/agents/` | `~/.copilot/skills/` or `.copilot/skills/` |
| Loaded when | User selects via `/agent` or `--agent=` | Auto-invoked when trigger phrases match |
| Effect | Instructions **added** to each user message | Content **injected** into main agent context |
| Survives compaction | Yes (stored on session object) | Yes (re-injected each turn) |
| File structure | **Single file** — all instructions inline | Can have supporting files (reference.md, etc.) |
| Best for | Multi-step interactive workflows with state | Reference knowledge and triggered procedures |

**Key rule**: Agents are **single-file**. No supporting `reference.md` or `examples.md` — that's a skill pattern (progressive disclosure). If an agent needs reference material, it either inlines it or **hands off to a skill** that provides it.

**Additive instructions**: The built-in system message (identity, tool usage, code change rules, git practices) remains. Don't duplicate what the system already provides.

## Instructions

### Step 1: Determine agent scope

1. **Ask clarifying questions**:
   - What specific workflow should this agent handle?
   - When would the user select this agent via `/agent`?
   - What tools does it need?
   - Is this for personal use or team sharing?

2. **Check for reuse first**:
   - Search `~/.copilot/agents/` for existing agents that might cover this
   - Consider whether a skill would be more appropriate (if it's triggered knowledge, not a workflow)
   - Check if an existing agent can be extended rather than creating a new one

3. **Keep it focused**: One agent = one workflow domain
   - Good: "PR comment reviewer", "IcM incident investigator", "Fleet orchestrator"
   - Too broad: "Code helper", "DevOps assistant"

### Step 2: Choose agent location

**Personal agents** (`~/.copilot/agents/`):
- Individual workflows and personal productivity
- Discovery is recursive — subdirectories work

**Project agents** (`.github/agents/`):
- Team workflows committed to the repo
- Project-specific agents shared via git

### Step 3: Write the frontmatter

```yaml
---
name: my-agent
description: >-
  Brief explanation of what this agent does and when to use it.
  Include trigger phrases.
tools: ["*"]
---
```

**Frontmatter schema** (from CLI source):

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | string | No | `""` | Display name shown in `/agent` list |
| `description` | string | **Yes** | — | First 3 non-header lines (≤1024 chars) shown as summary |
| `tools` | string or string[] | No | `["*"]` | Use CLI-native names |
| `model` | string | No | — | Override default model for this agent |
| `argument-hint` | string | No | — | Hint for what argument text to provide |
| `mcp-servers` | object | No | — | Additional MCP server config |
| `infer` | boolean | No | — | Allow model to auto-select this agent |
| `disable-model-invocation` | boolean | No | — | Prevent auto-triggering |
| `user-invocable` | boolean | No | `true` | Show in `/agent` list |

**No file size limit**: The markdown body has no character limit. The entire body is passed as the
agent's prompt. (The 1024-char limit applies only to the description summary extraction.)

Use `tools: ["*"]` unless you have a specific reason to restrict. If restricting, use CLI-native names:

| CLI Native | VS Code Alias (avoid) |
|-----------|----------------------|
| `powershell` / `bash` | `execute`, `runInTerminal` |
| `grep` / `glob` | `search` |
| `view` / `edit` / `create` | `read_file`, `edit_file` |
| `task` | `agent` |
| `web_fetch` | `web/fetch` |

### Step 4: Write the description

The description determines how the agent appears in `/agent` and whether it gets auto-selected.

**Formula**: `[What it does] + [When to use it] + [Key trigger phrases]`

✅ **Good**:
```yaml
description: >-
  Interactively review and address PR comments from Azure DevOps pull requests
  using a two-pass approach. Use when the user provides a PR URL or asks to
  review PR comments.
```

❌ **Too vague**:
```yaml
description: Helps with code reviews
```

### Step 5: Structure the agent body

Agents follow a consistent structure. Every section is optional except Workflow, but mature agents accumulate most of these over time. The sections are listed in the order they should appear:

#### 5a. Header and role declaration

Open with an `# Agent Name` header and a role statement. The role sets identity and operating mode.

```markdown
# Fleet Orchestrator

You are the Fleet Orchestrator — a workflow manager that decomposes large
bodies of work into a DAG, then executes tasks in parallel across git worktrees.
```

Role declarations are brief but set clear boundaries: "You are an analyst, not a coder", "You are a manager of software engineers, not a coder".

#### 5b. Description / When to Use

A `## Description` paragraph and/or `## When to Use` bullet list. These also feed the description summary extraction.

```markdown
## When to Use
- When user asks to review/address PR comments
- When user provides an Azure DevOps PR URL
- When user wants to iterate through feedback on their code
```

#### 5c. Constraints and CRITICALs

Hard limits come in two forms — use both:

**Inline CRITICALs** (primary pattern — from `review-pr-comments`): Place constraints directly inside the workflow step where violation would occur. These are harder to miss during execution:

```markdown
### 2. Present Organized Summary
**CRITICAL**: Do NOT go item-by-item. Instead:
1. Read relevant context
2. Organize into categories
3. Present with recommendations

### 7. Finalize
**CRITICAL WORKFLOW ORDER:**
1. First: commit and push
2. Then: post replies
3. Then: mark resolved

**Never mark threads as Fixed before pushing** — local edits don't count.
```

**Standalone Constraints section** (secondary — for agents that delegate heavily): When the agent's primary job is orchestration and the constraints are global (not step-specific), a `## Constraints` section works:

```markdown
## Constraints

- DO NOT implement code yourself — delegate to general-purpose subagents
- DO NOT block the user waiting for background work — pipeline everything
```

**Which to use?** If the agent does the work itself (like `review-pr-comments`), inline CRITICALs are better — they sit right where the agent would make the mistake. If the agent mostly delegates (like `fleet-orchestrator`), a standalone section establishes global rules before the workflow begins. Most agents should use **both**: global constraints at the top, plus inline CRITICALs at high-risk workflow steps.

#### 5d. Workflow (the core)

The workflow is the heart of the agent. Use numbered phases with clear sub-steps.

```markdown
## Workflow Steps

### 1. Fetch Data
Use [API/tool] to get [data]. Filter to [criteria].

### 2. Present Organized Summary
**CRITICAL**: Do NOT go item-by-item. Instead:
1. Read relevant context
2. Organize into categories
3. Present with recommendations

**Checkpoint:** Wait for user to provide decisions before proceeding.

### 3. Execute Decisions
#### If "Adopt":
- Research existing patterns first
- Make changes
- Track for resolution

#### If "Won't fix":
- Track for reply explaining why

### 4. Finalize (When User Asks)
**Note**: Only perform this step when the user explicitly asks.

**CRITICAL WORKFLOW ORDER:**
1. First: commit and push
2. Then: post replies
3. Then: mark resolved

**Never mark threads as Fixed before pushing** — local edits don't count.
```

**Three workflow control mechanisms** (use as needed):

1. **`**CRITICAL**:` inline markers** — for steps where violation would cause real damage. Bold the word CRITICAL. Place at the start of the step, not buried in prose.

2. **`**Checkpoint:**` pause points** — after any phase where the agent gathers data or presents choices:
   ```markdown
   **Checkpoint:** Present the summary table. Wait for user confirmation before proceeding.
   ```

3. **`**Note**: Only perform this step when the user explicitly asks`** — for steps that should never be auto-initiated (finalizing, pushing, resolving).

**Decision trees**: When the workflow branches, show the branches explicitly with `#### If "X":` sub-sections.

#### 5e. Skill handoffs

When an agent orchestrates a workflow that a skill provides reference details for, declare the handoff:

```markdown
The **fleet-orchestrated-pipeline** skill handles all the detailed procedures —
your job is to sequence the phases and keep the user informed at each checkpoint.
```

This pattern keeps agents lean (orchestration) while skills provide the reference material (progressive disclosure). The agent says what to do; the skill says how.

#### 5f. Model assignment (for agents that dispatch sub-agents)

```markdown
## Model Assignment

| Role | Model | Reason |
|------|-------|--------|
| This orchestrator | Claude Sonnet 4.6 | Fast coordination |
| Implementation agents | Claude Opus 4.6 | Deep reasoning |
| Review agent 1 | Claude Sonnet 4.6 | Architectural concerns |
| Review agent 2 | GPT-5.4 | Logical correctness |
| Review agent 3 | Gemini 3 Pro | Edge cases |
```

Include fallback guidance: "If a model is unavailable, fall back to Sonnet 4.6."

#### 5g. State tracking

Define SQL tables inline as the single source of truth. Include the schema, dashboard format, and lifecycle rules.

```markdown
## State Tracking

Use a SQL table as the single source of truth:
\`\`\`sql
CREATE TABLE IF NOT EXISTS work_items (
    id TEXT PRIMARY KEY, summary TEXT, status TEXT DEFAULT 'new',
    verbatim TEXT, notes TEXT
);
\`\`\`

After every state-changing action, show the dashboard:
\`\`\`
📊 N items: X new | X decided | X done
Next: N items ready to execute (w3, w4, w5)
\`\`\`

**Status lifecycle:** `new` → `decided` → `in_progress` → `done`
```

Key rules for state tracking:
- **Never create separate tracking tables** — one table is the single source of truth
- **Never execute undecided items** — only act where `decision` is recorded
- **Store verbatim text** — so it can be recalled without re-fetching
- **Record commit SHAs** — link items to the commits that address them

#### 5h. Pre-execution checklists

Verification steps to run before critical actions (push, resolve, deploy).

```markdown
## Pre-Push Checklist

Before pushing, verify:
1. **Tracker audit** — query table for stale notes, missing decisions
2. **No stray files** — `git status` for unintended additions
3. **Local validation** — run tests if changes touch scripts or pipelines
4. **Resolution plan** — which items get Fixed vs Won't Fix vs Closed
```

#### 5i. Domain-specific reference sections

Inline reference material specific to the agent's domain. These are lookup tables, status codes, category taxonomies, and similar reference data that the agent needs during execution.

```markdown
## Comment Thread Status Values
- "Active" = 1
- "Fixed" = 2
- "WontFix" = 3
- "Closed" = 4
```

#### 5j. Sub-agent delegation

When the agent's workflow involves dispatching work to sub-agents via the `task` tool, include a section explaining the delegation pattern. The system prompt already covers `task` tool mechanics — the agent only needs to specify:

- **What gets delegated** and what the agent does itself
- **Which agent types** to use for which tasks (explore for research, general-purpose for code changes, code-review for reviews, task for builds/tests)
- **Grouping rules** — what can run in parallel vs must be serial (typically: same-file = serial, different files = parallel)
- **What to spot-check** before presenting results to the user

Example from `review-pr-comments`:

```markdown
## Parallel Execution via Sub-Agents

When multiple Adopt decisions target independent files:
1. Group items by file — items touching the same file must be serial
2. Dispatch independent groups via sub-agents in parallel
3. Each sub-agent receives: comment verbatim, file path/context, decision details
4. Spot-check results before presenting to user

When drafting multiple replies:
- Use explore sub-agents in parallel to research code context for each comment
- Present all draft replies together for batch sign-off
```

Keep it domain-specific — describe *your agent's* parallelism pattern, not generic `task` tool docs.

#### 5k. Presentation style

How the agent should present information to the user.

```markdown
## Presentation Style

- **Group explanations by motivation** (e.g. "Dockerfile cleanup"), not by file
- **Keep explanations concise** — tag by number, one or two sentences each
- **Don't repeat full listings** — once presented, refer by number
- **Include context with proposals** — verbatim + code + proposed action together
```

#### 5l. Tips

A numbered list of **battle-tested lessons** from real usage sessions. Tips are the most valuable part of a mature agent — they encode what went wrong and how to prevent it.

```markdown
## Tips

1. **Read ALL relevant code** before presenting the organized summary
2. **Search session history** for context — don't guess when history exists
3. **Verify claims before replying** — actually check (web search, docs, code traces)
4. **Read linked work items** — the context may change your recommendation
5. **Don't mark Fixed until pushed** — local edits don't count
```

**Tips are not theoretical best practices.** Each tip should trace back to a specific mistake or missed opportunity in a real session. If you can't point to a concrete incident, it's guidance for the workflow section, not a tip.

Start with 3–5 tips on initial creation. Expect to add 5–10 more after the first few real usage sessions.

#### 5m. Anti-patterns (optional)

❌-prefixed list of common mistakes, distinct from constraints (which are hard rules) and tips (which are positive guidance).

```markdown
## Anti-patterns to avoid

- ❌ Text-matching on conversation content instead of querying ground-truth tables
- ❌ Using heavy models for parallel classification tasks
- ❌ Spending too much time on low-signal items instead of high-impact ones
```

#### 5n. Prior instances (optional)

Table of past sessions where this agent was used, with key findings. Helps the agent learn from its own history.

```markdown
## Prior instances

| Session | Date | Findings |
|---------|------|----------|
| `0b8a32f6` | 2026-02-26 | First run: 235 items, Kusto retry tax #1 issue |
| `4906737c` | 2026-03-13 | Second run: applied fixes to 8 files across 3 repos |
```

#### 5o. Recovery/resume

What to do when context is lost (compaction, session restart).

```markdown
On resume (context loss), query `work_items` table to rebuild state
and present the recovery summary before continuing.
```

#### 5p. Boundaries (optional)

Three-tier boundary system for nuanced guidance:

```markdown
## Boundaries

### ✅ Always Do
- Provide actionable, specific recommendations
- Prioritize findings by severity

### ⚠️ Ask First
- Before suggesting major refactors
- When recommending changes to shared interfaces

### 🚫 Never Do
- Make direct code changes without explicit permission
- Skip the mode selection step
```

### Step 6: Validate the agent

✅ **File structure**:
- [ ] File has `.agent.md` extension
- [ ] Located in `~/.copilot/agents/` or `.github/agents/`
- [ ] Single file — no supporting files in a subdirectory

✅ **YAML frontmatter**:
- [ ] Opening `---` on line 1
- [ ] Closing `---` before content
- [ ] Valid YAML (no tabs, correct indentation)
- [ ] `description` is present and specific (< 1024 chars for summary)
- [ ] `tools` uses CLI-native names or `["*"]`
- [ ] Unknown fields are OK (warn but don't fail)

✅ **Content quality**:
- [ ] Opens with role declaration ("You are...")
- [ ] Has phased workflow with numbered steps
- [ ] Checkpoints pause for user confirmation
- [ ] Constraints are explicit "DO NOT" rules
- [ ] Tips are battle-tested (from real usage, not theoretical)
- [ ] Instructions don't duplicate system message content
- [ ] No broken markdown (unclosed code blocks, orphaned lists)
- [ ] No progressive disclosure files — everything is inline

✅ **Testing**:
- [ ] Restart CLI or start new session
- [ ] Run `/agent` and verify it appears in list
- [ ] Select it and test with a real prompt
- [ ] Verify it follows the workflow correctly

### Step 7: Iterate based on real usage

After real usage sessions, update the agent with:
- **New tips** — every mistake the agent makes becomes a tip
- **Refined constraints** — every "DO NOT" traces back to an incident
- **New reference sections** — domain-specific lookup tables discovered during work
- **Prior instances** — add session IDs and dates to the table
- **Better state tracking** — schema evolves as edge cases emerge

**Track what went wrong**: When the agent makes mistakes, add explicit guidance to prevent recurrence.
This is more valuable than theoretical best practices. A mature agent (like review-pr-comments at 350 lines, 20 tips) is mostly lessons learned.

## What NOT to include in agents

These are already provided by the built-in system message:
- Tool usage instructions (powershell, grep, view, edit, etc.)
- General coding rules and style guidelines
- Git commit practices and trailer format
- Tone/brevity rules
- Parallel tool calling rules
- Code change instructions (surgical edits, linting, testing)

## Troubleshooting

**Agent doesn't appear in `/agent` list**:
- Check file extension is `.agent.md` (not `.md`)
- Verify location (`~/.copilot/agents/` or `.github/agents/`)
- Restart the CLI session
- Check `user-invocable` is not set to `false`
- Directory junctions for agents may not work — use flat files or file-level symlinks

**Agent loads but doesn't follow instructions**:
- Instructions may be too vague — add concrete steps with decision trees
- May be conflicting with system message — don't duplicate built-in rules
- Add explicit "DO NOT" constraints for common mistakes
- Check if compaction is losing conversation history — agent instructions survive, but context doesn't
- Add a recovery/resume section for post-compaction behavior

**Agent uses wrong tool names**:
- Replace VS Code aliases with CLI-native names
- Use `["*"]` to avoid tool restriction issues entirely
