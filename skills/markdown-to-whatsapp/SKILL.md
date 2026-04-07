---
name: markdown-to-whatsapp
description: Convert markdown content to WhatsApp formatting and copy to clipboard. Use when the user says "copy for whatsapp", "whatsapp format", "format for whatsapp", "wa format", "send via whatsapp", "paste in whatsapp", or "markdown to whatsapp". Do NOT use for general clipboard operations (use clipboard-markdown instead).
---

# Markdown to WhatsApp

Convert markdown text into WhatsApp's formatting syntax and copy to clipboard.

WhatsApp uses non-standard formatting: `*bold*`, `_italic_`, `~strikethrough~`, `` `code` ``.
This skill converts standard markdown into that format using AST-based parsing.

## When to use

- User wants content formatted for WhatsApp
- User says "copy for whatsapp", "whatsapp format", "wa format", "format for whatsapp"
- User asks to convert markdown output to paste into WhatsApp

## Conversion rules

| Markdown | WhatsApp |
|---|---|
| `**bold**` | `*bold*` |
| `*italic*` / `_italic_` | `_italic_` |
| `~~strike~~` | `~strike~` |
| `` `code` `` | `` `code` `` |
| `# Heading` | `*📌 Heading*` (emoji per level) |
| `[text](url)` | `text (url)` |
| Lists | `*` / `◦` nested bullets, `☑`/`☐` tasks |
| Tables | Bulleted key-value list |
| `---` | `───────────────` |
| Code blocks | Triple-backtick preserved |
| Blockquotes | `>` prefix preserved |

## Instructions

### 1. Compose the markdown content

Write the content the user requested as standard markdown. Be terse — this is for pasting, not reading in a terminal.

### 2. Convert and copy to clipboard

Save the markdown to a temp file and run the converter:

```powershell
$md = @'
Your markdown content here
'@

$md | python "C:\_SRC\copilot-plugins\scripts\md2wa.py" --clip
```

The script reads from stdin, converts to WhatsApp format, and copies to clipboard.

### 3. Confirm

The script prints the character count. Report it to the user.

## Alternative usage modes

```powershell
# Convert a file
python "C:\_SRC\copilot-plugins\scripts\md2wa.py" input.md --clip

# Convert clipboard content in-place
python "C:\_SRC\copilot-plugins\scripts\md2wa.py" --clip

# Convert to stdout only (no clipboard)
$md | python "C:\_SRC\copilot-plugins\scripts\md2wa.py"
```

## Dependencies

- Python 3.10+
- `mistune` (`uv pip install mistune --system`)

## Common mistakes to avoid

- **Don't manually convert** markdown to WhatsApp format — always use the script.
- **Don't use `$"..."` interpolation** in the here-string — use `@' '@` (single-quoted) to avoid variable expansion.
- **Don't add conversational preamble** to the clipboard content.
