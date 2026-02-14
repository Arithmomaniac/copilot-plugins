---
name: clipboard-markdown
description: Copy analysis, summaries, or feedback to the clipboard as markdown or block-quoted markdown. Use when the user says "copy to clipboard", "copy as markdown", "copy as quoted markdown", or asks to prepare text for pasting into PRs, docs, or chat.
---

# Clipboard Markdown

Copy text to the system clipboard formatted as plain markdown or block-quoted markdown.

## When to use

- User asks to copy something to clipboard as markdown
- User asks for block-quoted / quote-box markdown for pasting into PRs, docs, or chat
- User says "copy to clipboard", "copy as markdown", "copy as quoted markdown"

## Instructions

### 1. Determine format

- **Plain markdown** (default): Use when user says "copy to clipboard", "copy as markdown", or doesn't specify quoting.
- **Block-quoted markdown**: Use when user says "quoted", "quote box", "block quote", or explicitly asks for `>` prefixing.

### 2. Compose the content

- Be **terse** — clipboard content is for pasting, not reading in a terminal.
- Preserve structure: headings, tables, lists, code blocks.
- Do NOT include conversational preamble ("Here's a summary…"). Start directly with the content.

### 3. Handle PowerShell escaping

When building the string in PowerShell for `Set-Clipboard`:

- Use a **here-string** (`@' ... '@`) to avoid escaping issues with backticks, quotes, and special characters.
- For block-quoted format, prefix every line with `> `. Blank lines between sections become `>` (just the chevron).
- For markdown code blocks inside the here-string, use triple backticks naturally — they don't need escaping inside `@' '@`.

### 4. Copy to clipboard

```powershell
$content = @'
Your markdown content here
'@

$content | Set-Clipboard
Write-Output "Copied to clipboard ($($content.Length) chars)"
```

### 5. Confirm

Always print the character count so the user knows it worked.

## Block-quoted format

The robot emoji line comes first **unquoted**, then subsequent lines are block-quoted with `> `:

```
🤖
> ### Heading
>
> Body text here.
>
> - Bullet one
> - Bullet two
>
> ```lang
> code here
> ```
```

## Common mistakes to avoid

- **Don't use `$"..."` interpolation** in the here-string — use `@' '@` (single-quoted here-string) to avoid variable expansion.
- **Don't escape backticks** inside `@' '@` — they're literal.
- **Don't add conversational text** before or after the content inside the clipboard payload.
