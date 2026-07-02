---
name: markdown-doc-writer
description: >-
  Write and revise Markdown documentation that is not a formal design doc:
  how-to guides, pattern guides, READMEs, reference docs, team docs, and
  source-backed explanatory docs. Use when the user asks to write, edit,
  restructure, tighten, or review a Markdown document, especially with tables,
  lists, examples, code samples, headings, and tone/flow feedback. Do not use
  for formal design docs, RFCs, tech specs, or architecture proposals; use
  design-doc-writer for those.
---

# Markdown Doc Writer

Use this skill for practical Markdown documentation: how-to guides, pattern guides, READMEs, reference pages, team docs, and source-backed explanatory docs.

Do not turn a general doc into a design doc unless the user explicitly asks for a design document, RFC, tech spec, architecture proposal, or design decision record.

## Core workflow

1. Identify the document type: how-to, guide, reference, README, explainer, or checklist.
2. Add or update the required header disclaimer for every created or edited Markdown document.
3. Identify the audience and what they can assume. If unclear, make the doc standalone rather than assuming prior internal context.
4. Preserve the user's current intent and selected text when they are iterating in an editor.
5. Prefer focused edits over broad rewrites once the document has an established shape.
6. Ground claims in source examples when the user asks for worked examples or source-backed documentation.
7. Keep headings honest: major concepts use `##`; examples under a concept usually use `###` or inline labels.
8. Use tables, lists, and code samples where they reduce prose, but do not table-ify simple explanatory paragraphs.
9. Avoid syncing or copying documents outside the repo unless the user explicitly asks.

## Preserve existing structure by default

Before adding document scaffolding, decide whether the target is a narrative deliverable or a shared artifact.

- **Narrative docs and reports** can use a top-level title, short framing intro, sections, conclusions, and report-like flow when the user asks for a guide, report, explainer, proposal, or new standalone document.
- **Shared artifacts** such as reference pages, changelogs, catalogs, inventories, indexes, tables, checklists, and other non-narrative docs should receive minimal in-place edits that match the existing headings, ordering, tables, bullets, and naming style.

For shared/reference/changelog/catalog/non-narrative docs, do **not** add top-level headers, narrative framing, executive summaries, conclusions, or report structure unless the user explicitly asks for that transformation.

Concise examples:

| User asks | Good default | Avoid |
|-----------|--------------|-------|
| "Write a report on this subsystem" | Create a narrative doc with title, intro, sections, and evidence. | A bare catalog unless requested. |
| "Update this changelog entry" | Edit the existing version/date bullet in place. | Adding `# Changelog`, an overview, or a conclusion. |
| "Add this skill to the catalog/reference page" | Add one row or bullet matching the existing catalog format. | Reframing the catalog as a guide or report. |

## Required header disclaimer

Every Markdown document created or edited with this skill must start with this disclaimer before the document's main heading:

```markdown
> Created/edited by GitHub Copilot with human review/feedback by {reviewer}.
```

Load `{reviewer}` from `config.yml` in this skill directory:

```yaml
reviewer: avilevin
```

If the document already has this disclaimer, update it rather than adding a duplicate. If `config.yml` is missing or `reviewer` is blank, use the current OS username rather than leaving a placeholder in the document.

## Style rules

- Lead with the practical point, then add the evidence or example.
- Keep prose tight. Remove throat-clearing, repeated summaries, and duplicate section endings.
- Prefer standalone explanations: define terms the reader needs before using them.
- Use code comments inside samples when they clarify the example better than surrounding prose.
- Make examples realistic enough to show the pattern, but not so large that they obscure it.
- Use appendices for optional extensions, advanced variants, and concepts that would distract from the main flow.

## Structure patterns

For a how-to or pattern guide, a useful default order is:

1. Short intro: what problem this solves and the core idea.
2. Basic concepts: the vocabulary the reader needs.
3. Core pattern: the reusable mechanism or workflow.
4. Worked example: a concrete source-backed example.
5. Use-site examples: DI, startup, filtering, cleanup, tests, or other consumers.
6. Adoption checklist: a compact end-of-doc checklist.
7. Appendix: optional variants or advanced extensions.

Do not force this structure if the user's document already has a better one.

## Editing heuristics

| Symptom | Good fix |
|---------|----------|
| A section summarizes the rest of the document | Rename it as a checklist, move it to the end, or remove it. |
| A concept appears before its mechanism | Move it under the section that explains the mechanism. |
| A table is unclear | Add a lead-in sentence, simplify columns, or replace it with prose. |
| A code-adjacent paragraph repeats code comments | Remove the paragraph and let the code comments carry the point. |
| The same idea appears in several places | Keep the most useful occurrence and delete or fold the others into it. |
| An appendix assumes prior knowledge | Start from the current approach, then introduce the optional extension. |

## Source-backed examples

When using source code examples:

1. Search for the real implementation before inventing a sample.
2. Include only the lines needed to show the pattern.
3. Add a brief "meaning" table when a code block maps inputs to behavior.
4. Avoid standalone source-path sentences if the code sample comment already names the file.
5. Distinguish what is project-specific from what is reusable.

## Large document split/combine workflow

For large Markdown documents, especially source-backed reports and multi-section guides:

1. Prefer editing canonical section files rather than repeatedly editing one huge combined file.
2. Keep generated combined documents clearly marked as generated/concatenated and list the source section files near the top.
3. Use stable numeric prefixes for section files when ordering matters, for example `01-overview.md`, `02-architecture.md`, `03-workflow.md`.
4. Regenerate the combined file after every meaningful source-section change, then copy or publish that generated artifact only if the user asked for a combined deliverable.
5. Avoid making manual-only edits in the combined file unless it is the source of truth. If you must patch the combined file directly, back-port the change to the source section or document that the combined file is now canonical.
6. For review passes, inspect both levels: section files for maintainability and the combined file for reader flow, duplicate headings, broken transitions, and ordering.
7. When excluding sections from a combined deliverable, say why in the generated intro so readers know the scope.

## When not to use this skill

- Formal design docs, RFCs, tech specs, architecture proposals, and design decision records: use `design-doc-writer`.
- Word documents (`.docx`): use `docx`.
- Slide decks (`.pptx`) or presentations: use `pptx`.
- Diagrams as the main deliverable: use the relevant diagram skill.
- Audit recommendations, planning, or meta-discussion about documentation unless
  the user asks to create, edit, restructure, review, or produce an actual
  Markdown file or Markdown deliverable.
