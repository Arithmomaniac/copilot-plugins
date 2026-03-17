"""Copy markdown file to clipboard as both plain text and rich HTML (CF_HTML).

Usage: python copy-rich-clipboard.py <markdown-file>

Renders markdown to HTML, then invokes PowerShell to place both
plain text (markdown) and CF_HTML on the Windows clipboard.
"""

import sys
import os
import re
import subprocess
import tempfile


def preprocess_markdown(md: str) -> str:
    """Normalize markdown whitespace for reliable HTML conversion.

    Fixes common issues where the Python markdown library needs blank lines
    that authors typically omit:
    - Insert blank line before list items inside blockquotes
    - Insert blank line before list items after paragraphs
    - Normalize line endings
    """
    md = md.replace("\r\n", "\n")

    lines = md.split("\n")
    result = []
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if i > 0:
            prev = result[-1].rstrip()
            # Inside a blockquote: previous line is "> text" (not blank, not a list),
            # current line is "> - item" or "> * item" or "> 1. item"
            if re.match(r"^(\s*>\s+)[-*]\s", stripped) or re.match(r"^(\s*>\s+)\d+\.\s", stripped):
                if prev and not re.match(r"^\s*>\s*$", prev) and not re.match(r"^\s*>\s+[-*]\s", prev) and not re.match(r"^\s*>\s+\d+\.\s", prev):
                    # Extract the blockquote prefix (e.g., "> ")
                    m = re.match(r"^(\s*>)\s", stripped)
                    result.append(m.group(1) if m else ">")
            # Outside a blockquote: previous line is text, current is list item
            elif re.match(r"^\s*[-*]\s", stripped) or re.match(r"^\s*\d+\.\s", stripped):
                if prev and not re.match(r"^\s*[-*]\s", prev) and not re.match(r"^\s*\d+\.\s", prev) and not prev == "":
                    result.append("")
        result.append(line)
    return "\n".join(result)


def build_cf_html(html_body: str) -> str:
    """Wrap HTML body in the CF_HTML clipboard header format."""
    header_template = (
        "Version:0.9\r\n"
        "StartHTML:{start_html:010d}\r\n"
        "EndHTML:{end_html:010d}\r\n"
        "StartFragment:{start_fragment:010d}\r\n"
        "EndFragment:{end_fragment:010d}\r\n"
    )
    prefix = "<html><body>\r\n<!--StartFragment-->"
    suffix = "<!--EndFragment-->\r\n</body></html>"

    dummy_header = header_template.format(
        start_html=0, end_html=0, start_fragment=0, end_fragment=0
    )
    start_html = len(dummy_header.encode("utf-8"))
    start_fragment = start_html + len(prefix.encode("utf-8"))
    end_fragment = start_fragment + len(html_body.encode("utf-8"))
    end_html = end_fragment + len(suffix.encode("utf-8"))

    header = header_template.format(
        start_html=start_html,
        end_html=end_html,
        start_fragment=start_fragment,
        end_fragment=end_fragment,
    )
    return header + prefix + html_body + suffix


def main():
    if len(sys.argv) < 2:
        print("Usage: python copy-rich-clipboard.py <markdown-file>", file=sys.stderr)
        sys.exit(1)

    md_path = sys.argv[1]
    with open(md_path, "r", encoding="utf-8-sig") as f:
        md_text = f.read()

    md_text = preprocess_markdown(md_text)

    # Convert markdown to HTML
    try:
        import markdown
    except ImportError:
        os.system(f"{sys.executable} -m pip install markdown -q")
        import markdown

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists"],
    )

    cf_html = build_cf_html(html_body)

    # Write CF_HTML as raw UTF-8 bytes (no BOM) and markdown as UTF-8 text
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".html", delete=False) as hf:
        hf.write(cf_html.encode("utf-8"))
        html_path = hf.name
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as tf:
        tf.write(md_text.encode("utf-8"))
        text_path = tf.name

    # Use PowerShell + System.Windows.Forms to set both formats on clipboard
    # CF_HTML must be set as raw bytes, not as a decoded string, because the
    # header offsets are byte-based. Read as bytes and convert to MemoryStream.
    ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$utf8 = New-Object System.Text.UTF8Encoding($false)
$cfHtmlBytes = [System.IO.File]::ReadAllBytes('{html_path}')
$plainText = [System.IO.File]::ReadAllText('{text_path}', $utf8)
$ms = New-Object System.IO.MemoryStream(,$cfHtmlBytes)
$dataObj = New-Object System.Windows.Forms.DataObject
$dataObj.SetData([System.Windows.Forms.DataFormats]::Text, $plainText)
$dataObj.SetData([System.Windows.Forms.DataFormats]::Html, $ms)
[System.Windows.Forms.Clipboard]::SetDataObject($dataObj, $true)
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command", ps_script],
        capture_output=True, text=True
    )

    # Cleanup temp files
    os.unlink(html_path)
    os.unlink(text_path)

    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Copied to clipboard as rich HTML ({len(md_text)} chars markdown, {len(html_body)} chars HTML)")


if __name__ == "__main__":
    main()
