"""Platform-adaptive message formatter for WhatsApp and Telegram.

Rules:
WhatsApp:
- Bold: *bold* (markdown **bold** or ***bold italic*** converted to *bold* or *_bold italic_*)
- Italic: _italic_
- Strikethrough: ~strike~
- Monospace: `inline` or ```block```
- Hyperlinks: WA does not support [Label](url) markdown syntax; convert to "Label: url" or "Label (url)"

Telegram (HTML mode):
- Characters <, >, & are escaped properly
- Bold: <b>text</b>
- Italic: <i>text</i>
- Strikethrough: <s>text</s>
- Monospace: <code>inline</code> or <pre>block</pre>
- Hyperlinks: <a href="url">Label</a>
"""
import re
import html as _html
from typing import Optional


def format_for_whatsapp(text: Optional[str]) -> str:
    """Format raw markdown or bot responses for WhatsApp delivery."""
    if not text:
        return ""

    out = text

    # 1. Convert markdown hyperlinks [Label](url) -> Label (url)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r"\1 (\2)", out)

    # 2. Convert triple asterisks ***bold italic*** -> *_bold italic_*
    out = re.sub(r"\*{3,}([^*\n]+?)\*{3,}", r"*_\1_*", out)

    # 3. Convert double asterisks **bold** -> *bold*
    out = re.sub(r"\*{2}([^*\n]+?)\*{2}", r"*\1*", out)

    # 4. Cleanup any duplicate bold stars around lists or numbers, e.g. *1.* *Judul* -> 1. *Judul*
    out = re.sub(r"^\*(\d+[\.\)])\*\s*", r"\1 ", out, flags=re.MULTILINE)

    return out


def format_for_telegram(text: Optional[str]) -> str:
    """Convert raw markdown / bot responses into Telegram-compatible HTML."""
    if not text:
        return ""

    # First, handle code blocks before html escaping placeholders
    code_blocks = []
    def _save_code_block(match):
        code_blocks.append(match.group(1).strip("\r\n"))
        return f"\x00TGCODEBLOCK{len(code_blocks)-1}\x00"

    out = re.sub(r"```(?:\w+)?\n?(.*?)```", _save_code_block, text, flags=re.DOTALL)

    # Handle inline code before escaping
    inline_codes = []
    def _save_inline_code(match):
        inline_codes.append(match.group(1))
        return f"\x00TGINLINECODE{len(inline_codes)-1}\x00"

    out = re.sub(r"`([^`\n]+)`", _save_inline_code, out)

    # Convert markdown links [Label](url) to placeholder before escaping
    links = []
    def _save_link(match):
        label = match.group(1)
        url = match.group(2)
        links.append((label, url))
        return f"\x00TGMDLINK{len(links)-1}\x00"

    out = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", _save_link, out)

    # Now safely HTML-escape normal text characters
    out = _html.escape(out, quote=False)

    # Convert Markdown formatting to Telegram HTML
    # ***bold italic*** -> <b><i>text</i></b>
    out = re.sub(r"\*{3,}([^*\n]+?)\*{3,}", r"<b><i>\1</i></b>", out)
    # **bold** -> <b>text</b>
    out = re.sub(r"\*{2}([^*\n]+?)\*{2}", r"<b>\1</b>", out)
    # *bold* -> <b>text</b>
    out = re.sub(r"\*([^*\n]+?)\*", r"<b>\1</b>", out)
    # _italic_ -> <i>text</i>
    out = re.sub(r"_([^_\n]+?)_", r"<i>\1</i>", out)
    # ~strikethrough~ -> <s>text</s>
    out = re.sub(r"~([^~\n]+?)~", r"<s>\1</s>", out)

    # Restore links as <a href="url">Label</a>
    for idx, (lbl, url) in enumerate(links):
        safe_lbl = _html.escape(lbl, quote=False)
        safe_url = _html.escape(url, quote=True)
        out = out.replace(f"\x00TGMDLINK{idx}\x00", f'<a href="{safe_url}">{safe_lbl}</a>')

    # Restore inline code as <code>...</code>
    for idx, code in enumerate(inline_codes):
        safe_code = _html.escape(code, quote=False)
        out = out.replace(f"\x00TGINLINECODE{idx}\x00", f"<code>{safe_code}</code>")

    # Restore code blocks as <pre>...</pre>
    for idx, block in enumerate(code_blocks):
        safe_block = _html.escape(block, quote=False)
        out = out.replace(f"\x00TGCODEBLOCK{idx}\x00", f"<pre>{safe_block}</pre>")

    return out
