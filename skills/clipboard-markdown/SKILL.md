---
name: clipboard-markdown
description: Copy analysis, summaries, or feedback to the clipboard as markdown or block-quoted markdown. Use when the user says "copy to clipboard", "copy as markdown", "copy as quoted markdown", "copy as rich", or asks to prepare text for pasting into PRs, docs, or chat.
---

# Clipboard Markdown

Copy text to the system clipboard formatted as plain markdown, block-quoted markdown, or rich HTML (for pasting into Teams/Outlook/etc. with formatting).

## When to use

- User asks to copy something to clipboard as markdown
- User asks for block-quoted / quote-box markdown for pasting into PRs, docs, or chat
- User says "copy to clipboard", "copy as markdown", "copy as quoted markdown"
- User says "copy as rich", "rich clipboard", "copy as HTML", "formatted paste", or wants it to paste with bold/headers/etc.

## Instructions

### 1. Determine format

- **Plain markdown** (default): Use when user says "copy to clipboard", "copy as markdown", or doesn't specify quoting.
- **Block-quoted markdown**: Use when user says "quoted", "quote box", "block quote", or explicitly asks for `>` prefixing.
- **Rich HTML**: Use when user says "rich", "HTML", "formatted", "rich clipboard", "rich paste", or wants content to paste with visual formatting into Teams/Outlook/Word/etc. This puts both plain-text markdown AND rendered HTML on the clipboard so the target app picks the richest format it supports.

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

#### Plain or block-quoted markdown

```powershell
$content = @'
Your markdown content here
'@

$content | Set-Clipboard
Write-Output "Copied to clipboard ($($content.Length) chars)"
```

#### Rich HTML (markdown text + rendered HTML)

Write the markdown content to a temp file, then use the `copy-rich-clipboard.py` helper script:

```powershell
$content = @'
Your markdown content here
'@

$tempFile = [System.IO.Path]::GetTempFileName() + ".md"
$content | Out-File -Encoding utf8 -FilePath $tempFile
python "$env:USERPROFILE\.claude\skills\clipboard-markdown\copy-rich-clipboard.py" $tempFile
Remove-Item $tempFile
```

The script converts markdown to HTML, then places both plain text (markdown) and CF_HTML on the Windows clipboard using `System.Windows.Forms.DataObject`. This way:
- Pasting into Teams/Outlook/Word → renders as rich formatted text
- Pasting into a plain text editor or code → pastes as raw markdown

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
- **For rich HTML mode**, always use the helper script — don't try to build CF_HTML headers manually.
