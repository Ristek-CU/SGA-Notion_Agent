import random
import re
import string
from typing import List, Dict, Any, Optional
from app.notion.core import NotionClient
from app.config import settings

client = NotionClient(
    api_key=settings.notion_api_key,
    version=settings.notion_version,
    max_rps=settings.notion_rate_limit_rps,
    max_retries=settings.notion_max_retries,
)

# Status valid di DB Tiket (type: status)
VALID_STATUSES = ["Not started", "Blocking", "In progress", "Need to review", "Need to fix", "Done"]

# Alias input user -> nama status Notion
STATUS_ALIASES = {
    "todo": "Not started",
    "notstarted": "Not started",
    "belum": "Not started",
    "inprogress": "In progress",
    "doing": "In progress",
    "proses": "In progress",
    "review": "Need to review",
    "needtoreview": "Need to review",
    "fix": "Need to fix",
    "needtofix": "Need to fix",
    "blocked": "Blocking",
    "done": "Done",
    "selesai": "Done",
}


def normalize_status(user_status: str) -> str:
    key = re.sub(r"[^a-z]", "", (user_status or "").lower())
    if key in STATUS_ALIASES:
        return STATUS_ALIASES[key]
    # fuzzy: "progres", "inprogres", "donee" dsb -> opsi valid terdekat
    for v in VALID_STATUSES:
        vk = re.sub(r"[^a-z]", "", v.lower())
        if key and (key in vk or vk in key):
            return v
    return ""


def ticket_code(page_id: str) -> str:
    """ID singkat unik utk user: 8 char terakhir hex (prefix 8-char TIDAK unik di workspace ini)."""
    return (page_id or "").replace("-", "")[-8:]


def generate_ticket_id() -> str:
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    import datetime
    today = datetime.date.today().strftime("%Y%m%d")
    return f"TK-{today}-{rand}"


async def resolve_division_id(name: Optional[str]) -> Optional[str]:
    """Cari page-id divisi di DB Divisions berdasarkan nama (fuzzy contains)."""
    if not name or not settings.notion_divisions_id:
        return None
    try:
        pages = await client.query_all(f"/databases/{settings.notion_divisions_id}/query")
        q = name.strip().lower()
        for p in pages:
            props = p.get("properties", {})
            for v in props.values():
                t = v.get("title", [])
                if t and q in t[0].get("plain_text", "").lower():
                    return p["id"]
        return None
    except Exception:
        return None


async def create_ticket_direct(
    title: str,
    division: Optional[str] = None,
    priority: str = "Medium",
    status: str = "Not started",
    description: Optional[str] = None,
    pic_id: Optional[str] = None,
    database_id: Optional[str] = None,
    division_id: Optional[str] = None,
) -> Dict[str, Any]:
    db_id = database_id or settings.notion_database_id
    ticket_id = generate_ticket_id()

    properties: Dict[str, Any] = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Status": {"status": {"name": status}},
        "Priority Level": {"select": {"name": priority if priority in ("High", "Medium", "Low") else "Medium"}},
    }

    if pic_id:
        properties["PIC"] = {"relation": [{"id": pic_id}]}

    if division_id:
        properties["🧏‍♀️ Divisions"] = {"relation": [{"id": division_id}]}

    # Deskripsi ditulis sebagai isi halaman (DB tak punya properti Description)
    children = []
    if description:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": description}}]},
        })

    body: Dict[str, Any] = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }
    if children:
        body["children"] = children

    res = await client.request("POST", "/pages", body=body)
    client.clear_cache()
    return {"ticket_id": ticket_id, "page": res}


def _extract(page: Dict[str, Any]) -> Dict[str, Any]:
    """Normalisasi satu page tiket sesuai skema asli."""
    props = page.get("properties", {})
    t = props.get("Name", {}).get("title", [])
    st = props.get("Status", {}).get("status", {}).get("name", "?")
    pr = (props.get("Priority Level", {}) or {}).get("select") or {}
    pr = pr.get("name")
    pic_ids = [r.get("id") for r in props.get("PIC", {}).get("relation", [])]
    div_ids = [r.get("id") for r in props.get("🧏‍♀️ Divisions", {}).get("relation", [])]
    created = props.get("Created time", {}).get("created_time", "")
    return {
        "page_id": page.get("id"),
        "ticket_id": None,  # DB tak punya properti ID; pakai page id
        "title": t[0].get("plain_text", "") if t else "",
        "status": st,
        "priority": pr,
        "pic_ids": pic_ids,
        "division_ids": div_ids,
        "created": created,
    }


def _find_by_ticket_prefix(pages: List[Dict[str, Any]], tid: str) -> Optional[Dict[str, Any]]:
    """Cocokkan kode tiket (8 char terakhir) atau full page-id. Kembalikan None kalau ambigu."""
    t = (tid or "").strip().lower().replace("-", "")
    if not t:
        return None
    exact = next((p for p in pages if p["id"].replace("-", "").lower() == t), None)
    if exact:
        return exact
    matches = [p for p in pages if p["id"].replace("-", "").lower().endswith(t)]
    return matches[0] if len(matches) == 1 else None


async def query_tickets_direct(
    database_id: Optional[str] = None,
    status: Optional[str] = None,
    division: Optional[str] = None,
) -> List[Dict[str, Any]]:
    db_id = database_id or settings.notion_database_id
    filters = []

    if status:
        filters.append({"property": "Status", "status": {"equals": status}})
    # ponytail: filter divisi dilewati (relation perlu page-id, bukan nama) — add when needed

    body = {}
    if len(filters) == 1:
        body["filter"] = filters[0]
    elif len(filters) > 1:
        body["filter"] = {"and": filters}

    results = await client.query_all(f"/databases/{db_id}/query", body=body)
    return results


async def get_ticket_detail(page_id: str) -> Dict[str, Any]:
    return await client.request("GET", f"/pages/{page_id}")


async def get_ticket_blocks(page_id: str) -> Dict[str, Any]:
    return await client.request("GET", f"/blocks/{page_id}/children")


async def update_ticket_direct(page_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    res = await client.request("PATCH", f"/pages/{page_id}", body={"properties": properties})
    client.clear_cache()
    return res


async def add_ticket_note(page_id: str, note_text: str) -> Dict[str, Any]:
    body = {
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": note_text}}]
                },
            }
        ]
    }
    return await client.request("PATCH", f"/blocks/{page_id}/children", body=body)


async def add_ticket_comment(page_id: str, comment_text: str) -> Dict[str, Any]:
    body = {
        "parent": {"page_id": page_id},
        "rich_text": [{"text": {"content": comment_text}}],
    }
    return await client.request("POST", "/comments", body=body)
