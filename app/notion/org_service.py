from typing import List, Dict, Any, Optional
from app.notion.core import NotionClient
from app.config import settings

client = NotionClient(
    api_key=settings.notion_api_key,
    version=settings.notion_version,
    max_rps=settings.notion_rate_limit_rps,
    max_retries=settings.notion_max_retries,
)

DIVISION_ALIASES = {
    "ristek": "Ristek",
    "medkom": "Media & Komunikasi",
    "media": "Media & Komunikasi",
    "humas": "Humas",
    "internal": "Internal",
    "external": "External",
}


def resolve_division_alias(query: str) -> Optional[str]:
    q = query.strip().lower()
    return DIVISION_ALIASES.get(q, query.title())


async def list_divisions() -> List[Dict[str, Any]]:
    div_db = settings.notion_divisions_id or settings.notion_database_id
    try:
        results = await client.query_all(f"/databases/{div_db}/query")
        return results
    except Exception:
        return [{"name": v} for v in set(DIVISION_ALIASES.values())]


async def list_members() -> List[Dict[str, Any]]:
    mem_db = settings.notion_members_id or settings.notion_database_id
    try:
        results = await client.query_all(f"/databases/{mem_db}/query")
        return results
    except Exception:
        return []


async def get_backlog_stats(database_id: Optional[str] = None) -> Dict[str, Any]:
    db_id = database_id or settings.notion_database_id
    try:
        pages = await client.query_all(f"/databases/{db_id}/query")
        total = len(pages)
        by_status: Dict[str, int] = {}
        by_division: Dict[str, int] = {}

        for p in pages:
            props = p.get("properties", {})
            st_prop = props.get("Status", {}).get("status", {})
            st = st_prop.get("name", "Unknown") if st_prop else "Unknown"
            by_status[st] = by_status.get(st, 0) + 1

            div_prop = props.get("Division", {}).get("select", {})
            div = div_prop.get("name", "Unassigned") if div_prop else "Unassigned"
            by_division[div] = by_division.get(div, 0) + 1

        return {
            "total": total,
            "by_status": by_status,
            "by_division": by_division,
        }
    except Exception:
        return {"total": 0, "by_status": {}, "by_division": {}}
