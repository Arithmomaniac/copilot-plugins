---
name: svg-diagrams
description: General SVG/HTML diagram best practices for dark/light themed visualizations. Provides HTML template with CSS custom property theming (no blur), layout guidelines, color palette, Playwright verification workflow, and anti-patterns. Triggers on "create SVG", "SVG diagram", "HTML diagram", "dark/light toggle", "generate visualization", "diagram", "flowchart SVG".
---

# SVG Diagram Best Practices

General-purpose reference for creating SVG diagrams embedded in HTML with dark/light theme support. Use raw SVG in HTML for precise control — not Mermaid or other DSLs.

## HTML Template

Every SVG diagram file uses this structure. The SVG is **inline** (not an `<img>` tag) so CSS custom properties flow through.

**CRITICAL:** Do NOT use CSS `invert()` filter for light mode — it causes blurry text. Use CSS custom properties inside SVG elements instead.

```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<title>DIAGRAM_TITLE</title>
<style>
:root {
  --bg: #0d1117; --fg: #c9d1d9; --muted: #8b949e; --dim: #484f58;
  --card-bg: #161b22; --card-border: #30363d;
  --green-text: #3fb950;
}
[data-theme="light"] {
  --bg: #ffffff; --fg: #1f2328; --muted: #656d76; --dim: #8b949e;
  --card-bg: #f6f8fa; --card-border: #d0d7de;
  --green-text: #1a7f37;
}
body {
  background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  margin: 0; padding: 20px;
  display: flex; flex-direction: column; align-items: center;
}
svg { max-width: 1400px; width: 100%; }
.theme-toggle {
  position: fixed; top: 16px; right: 16px; z-index: 100;
  background: var(--card-bg); border: 1px solid var(--card-border);
  color: var(--fg); padding: 6px 12px; border-radius: 6px; cursor: pointer;
}
</style>
</head>
<body>
<button class="theme-toggle" onclick="toggleTheme()">🌙 / ☀️</button>

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 WIDTH HEIGHT" font-family="Segoe UI, sans-serif">
  <defs>
    <style>
      .title { font-size: 22px; font-weight: bold; fill: var(--fg); }
      .subtitle { font-size: 13px; fill: var(--muted); }
      .label { font-size: 11px; fill: var(--fg); }
      .value { font-size: 11px; fill: var(--muted); font-family: Consolas, monospace; }
      .section-title { font-size: 14px; font-weight: bold; }
      .muted { fill: var(--muted); }
      .dim { fill: var(--dim); }
    </style>
    <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
      <polygon points="0 0, 8 3, 0 6" fill="var(--muted)" />
    </marker>
  </defs>

  <!-- Background rect uses var for theming -->
  <rect width="WIDTH" height="HEIGHT" fill="var(--bg)" rx="6" />

  <!-- All text and fills use var(--fg), var(--muted), var(--dim) -->
  <!-- Accent colors (blue, green, etc.) stay constant across themes -->
</svg>

<script>
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  html.setAttribute('data-theme', current === 'light' ? 'dark' : 'light');
  localStorage.setItem('theme', html.getAttribute('data-theme'));
}
(function() {
  const saved = localStorage.getItem('theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
})();
</script>
</body></html>
```

### Theming Rules

- **Background, text, muted, dim** → use CSS custom properties (`var(--bg)`, `var(--fg)`, `var(--muted)`, `var(--dim)`)
- **Accent/semantic colors** (blue, green, red, etc.) → use hardcoded hex values — they're chosen to work on both dark and light backgrounds
- **Box fills** → use accent color with `fill-opacity="0.08-0.14"` so the background shows through in both themes
- **Strokes** → accent colors at full opacity for box borders
- **Legend/card backgrounds** → `var(--card-bg)` with `var(--card-border)` stroke

---

## SVG Layout Guidelines

Proven sizing from successful renders:

| Dimension | Recommended Range |
|-----------|------------------|
| viewBox width | 1100–1500 |
| viewBox height | 850–1100 |
| Section box height | 50–220 (varies by content) |
| Box border-radius (rx) | 5–8 |
| Box fill opacity | 0.08–0.14 |
| Box stroke width | 1.5–2px |
| Inset from box edge | 10–20px |
| Font: titles | 22px, bold |
| Font: section headers | 14px, bold |
| Font: labels | 10–11px, weight 600 |
| Font: values/mono | 9–11px, monospace |
| Font: muted/dim text | 8–9px |
| Arrow marker size | markerWidth 7–8, markerHeight 6 |

### SVG Element Patterns

```xml
<!-- Section box (colored band) -->
<rect x="X" y="Y" width="W" height="H" rx="8" ry="8"
      fill="#58a6ff" fill-opacity="0.10" stroke="#58a6ff" stroke-width="1.5" />

<!-- Section title (accent colored) -->
<text x="CX" y="Y+22" text-anchor="middle" class="section-title" fill="#58a6ff">Title</text>

<!-- Label + value pair -->
<text x="X+15" y="ROW_Y" class="label">param_name</text>
<text x="X+W-15" y="ROW_Y" text-anchor="end" class="value">0.42</text>

<!-- Dim description text -->
<text x="X+15" y="ROW_Y" class="dim">Explanation of parameter</text>

<!-- Solid arrow (data/control flow) -->
<path d="M x1 y1 L x2 y2" stroke="#58a6ff" stroke-width="1.5"
      fill="none" marker-end="url(#arrowhead)" />

<!-- Dashed arrow (dependency) -->
<path d="M x1 y1 L x2 y2" stroke="var(--dim)" stroke-width="1.2"
      fill="none" stroke-dasharray="5,3" marker-end="url(#arrowhead)" />

<!-- Legend/card background -->
<rect x="X" y="Y" width="W" height="H" rx="8" ry="8"
      fill="var(--card-bg)" stroke="var(--card-border)" stroke-width="1.5" />
```

---

## Color Palette

**Accent colors** (constant across themes — chosen for contrast on both dark and light):

| Color | Hex | Semantic |
|-------|-----|----------|
| Blue | `#58a6ff` | Primary / I/O / infrastructure |
| Green | `#3fb950` | Success / enrichment / output |
| Purple | `#bc8cff` | ML / embedding / special |
| Gold | `#d29922` | Warning / labeling / concern |
| Red | `#f85149` | Error / output / monolith |
| Cyan | `#39d2c0` | Data boundaries / schemas |

**Theme-aware colors** (use CSS custom properties):

| Variable | Dark | Light | Usage |
|----------|------|-------|-------|
| `--bg` | `#0d1117` | `#ffffff` | SVG/page background |
| `--fg` | `#c9d1d9` | `#1f2328` | Primary text |
| `--muted` | `#8b949e` | `#656d76` | Secondary text, values |
| `--dim` | `#484f58` | `#8b949e` | Tertiary text, descriptions |
| `--card-bg` | `#161b22` | `#f6f8fa` | Legend/card backgrounds |
| `--card-border` | `#30363d` | `#d0d7de` | Legend/card borders |

---

## Verification Workflow

**Always verify SVG diagrams visually.** SVG coordinate math is error-prone; visual rendering catches issues that code review cannot.

### Playwright Screenshot Script

```python
from playwright.sync_api import sync_playwright
import os

session_dir = r"PATH_TO_FILES"
html_path = os.path.join(session_dir, "diagram.html")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    # Dark mode
    page.goto(f"file:///{html_path}")
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(session_dir, "diagram-dark.png"), full_page=True)

    # Light mode
    page.evaluate('document.documentElement.setAttribute("data-theme","light")')
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(session_dir, "diagram-light.png"), full_page=True)

    browser.close()
```

### What to Check

View each screenshot with the `view` tool and verify:
- **Text overlap**: labels, values, section titles must not collide
- **Band alignment**: elements visually sit inside their boxes
- **Spacing**: boxes have clear separation (10–20px gaps)
- **Readability**: font sizes legible at rendered width
- **Light mode**: all text visible, accent colors distinguishable

### Common Fixes

| Problem | Fix |
|---------|-----|
| Text overlapping rect | Increase rect height or adjust text y position |
| y-coordinates too close | Increase spacing by 10–20 units |
| Text clipping box edge | Increase inset (x+15, x+W-15) |
| Box too tall/short | Adjust height to content (count rows × 16–18px + padding) |

---

## Anti-Patterns

- **DO NOT** use CSS `invert()` filter for light mode. It blurs text because it's a pixel-level raster operation on vector SVG. Use CSS custom properties inside SVG instead.
- **DO NOT** use Mermaid or other diagram DSLs. Raw SVG gives precise control over positioning and theming.
- **DO NOT** skip Playwright verification. SVG coordinates that look correct in code often render with overlaps.
- **DO NOT** omit light mode testing. Accent colors can become illegible if background contrast is wrong.
- **DO NOT** guess sizes. Count content rows and compute heights. Verify from actual data.
- **DO NOT** hardcode `#0d1117`, `#c9d1d9`, `#8b949e`, or `#484f58` in SVG elements. Use `var(--bg)`, `var(--fg)`, `var(--muted)`, `var(--dim)` so theming works.
- **DO NOT** use `<img src="file.svg">` for themed SVGs. The SVG must be inline in the HTML so CSS custom properties can flow through.
