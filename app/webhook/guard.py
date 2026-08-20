import re
from typing import Dict, Any, List

PROGRAMMING_PATTERNS = [
    r"\b(python|javascript|typescript|java|c\+\+|golang|rust|php|html|css|sql|bash|shell)\b",
    r"\b(function|def|class|import|const|let|var|public|private|void|return|async|await)\b",
    r"\b(script|code|coding|program|framework|algorithm)\b",
    r"\b(tulis|buatkan|bikin|contoh|buat)\s+(kode|code|script|fungsi|function|program)\b",
    r"\b(tulisin|buatkan)\s+kode\b",
]

OUT_OF_SCOPE_PATTERNS = [
    r"\b(cuaca|weather|gempa|berita|news|saham|crypto|bitcoin|investasi)\b",
    r"\b(resep|masak|makanan|restoran|kuliner)\b",
    r"\b(film|musik|lagu|game|olahraga|sepak\s*bola|skor)\b",
    r"\b(curhat|jodoh|ramalan|zodiak|cinta)\b",
    r"\b(siapa\s+presiden|politik|pemilu)\b",
]

SGA_WHITELIST_PATTERNS = [
    r"\b(tiket|ticket|backlog|tugas|task|projek|project|notion)\b",
    r"\b(divisi|ristek|media|humas|internal|external|event|sga)\b",
    r"\b(status|pic|assign|prioritas|priority|backlog)\b",
]


def check_out_of_scope(message: str) -> Dict[str, Any]:
    text = message.lower().strip()

    # 1. Check whitelist
    has_whitelist = False
    for pat in SGA_WHITELIST_PATTERNS:
        if re.search(pat, text):
            has_whitelist = True
            break

    # 2. Check programming patterns
    prog_matches = sum(1 for pat in PROGRAMMING_PATTERNS if re.search(pat, text))
    
    # 3. Check out of scope patterns
    oos_matches = sum(1 for pat in OUT_OF_SCOPE_PATTERNS if re.search(pat, text))

    is_asking = bool(re.search(r"\b(bagaimana|cara|tulis|tulisin|buat|bikin|contoh|apa|gimana|jelaskan)\b", text))

    # If explicit programming request with no ticket/task context, block even if whitelist matched keyword
    if prog_matches >= 2 or (prog_matches >= 1 and (is_asking or "kode" in text or "script" in text)):
        if not ("buat tiket" in text or "create ticket" in text or "tambah tiket" in text):
            return {
                "is_out_of_scope": True,
                "reason": "Maaf, saya adalah Notion Agent SGA dan tidak bisa membantu penulisan kode atau pemograman.",
            }

    if has_whitelist:
        return {"is_out_of_scope": False, "reason": None}

    if oos_matches >= 2 or (oos_matches >= 1 and is_asking):
        return {
            "is_out_of_scope": True,
            "reason": "Maaf, topik tersebut di luar lingkup tugas saya sebagai Notion Agent SGA.",
        }

    return {"is_out_of_scope": False, "reason": None}
