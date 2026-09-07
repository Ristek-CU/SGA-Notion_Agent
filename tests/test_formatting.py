import pytest
from app.services.formatter import format_for_whatsapp, format_for_telegram


def test_whatsapp_formatting():
    # Bold conversion
    assert format_for_whatsapp("Halo **Salman**!") == "Halo *Salman*!"
    assert format_for_whatsapp("***Testing Task***") == "*_Testing Task_*"
    assert format_for_whatsapp("Item *Sudah Tebal*") == "Item *Sudah Tebal*"

    # Italic, code
    assert format_for_whatsapp("Cek `status` ya") == "Cek `status` ya"
    assert format_for_whatsapp("_italic text_") == "_italic text_"

    # Links conversion from [Label](url) to Label (url)
    assert format_for_whatsapp("Buka [Notion Link](https://notion.so/ticket-1)") == "Buka Notion Link (https://notion.so/ticket-1)"
    assert format_for_whatsapp("Lihat [Dokumentasi](http://example.com/docs) sekarang") == "Lihat Dokumentasi (http://example.com/docs) sekarang"

    # Numbered list asterisks cleanup
    assert format_for_whatsapp("*1.* *Testing Task*") == "1. *Testing Task*"
    assert format_for_whatsapp("*2)* *Task Kedua*") == "2) *Task Kedua*"

    # Empty
    assert format_for_whatsapp("") == ""
    assert format_for_whatsapp(None) == ""


def test_telegram_formatting():
    # Bold & italic
    assert format_for_telegram("Halo *Salman*!") == "Halo <b>Salman</b>!"
    assert format_for_telegram("Halo **Salman**!") == "Halo <b>Salman</b>!"
    assert format_for_telegram("_italic text_") == "<i>italic text</i>"
    assert format_for_telegram("~strikethrough~") == "<s>strikethrough</s>"

    # Code block & inline code
    assert format_for_telegram("`kode inline`") == "<code>kode inline</code>"
    assert format_for_telegram("```\nprint('hello')\n```") == "<pre>print('hello')</pre>"

    # HTML character escaping
    assert format_for_telegram("Cek <script> & 'quotes'") == "Cek &lt;script&gt; &amp; 'quotes'"

    # Links conversion to safe HTML anchor
    assert format_for_telegram("Buka [Notion Link](https://notion.so/ticket-1)") == 'Buka <a href="https://notion.so/ticket-1">Notion Link</a>'
    assert format_for_telegram("Cek [SGA <Web>](https://sga.id?a=1&b=2)") == 'Cek <a href="https://sga.id?a=1&amp;b=2">SGA &lt;Web&gt;</a>'

    # Empty
    assert format_for_telegram("") == ""
    assert format_for_telegram(None) == ""
