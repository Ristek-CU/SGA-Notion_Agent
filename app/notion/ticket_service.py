import random
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


def generate_ticket_id() -> str:
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    import datetime
    today = datetime.date.today().strftime("%Y%m%d")
    return f"TK-{today}-{rand}"


async def create_ticket_direct(
    title: str,
    division: Optional[str] = None,
    priority: str = "Medium",
    status: str = "To Do",
    description: Optional[str] = None,
    pic_id: Optional[str] = None,
    database_id: Optional[str] = None,
) -> Dict[str, Any]:
    db_id = database_id or settings.notion_database_id
    ticket_id = generate_ticket_id()

    properties: Dict[str, Any] = {
        "Name": {"title": [{"text": {"content": title}}]},
        "ID": {"rich_text": [{"text": {"content": ticket_id}}]},
        "Status": {"status": {"name": status}},
        "Priority": {"select": {"name": priority}},
    }

    if division:
        properties["Division"] = {"select": {"name": division}}

    if description:
        properties["Description"] = {"rich_text": [{"text": {"content": description}}]}

    if pic_id:
        properties["PIC"] = {"relation": [{"id": pic_id}]}

    body = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }

    res = await client.request("POST", "/pages", body=body)
    client.clear_cache()
    return {"ticket_id": ticket_id, "page": res}


async def query_tickets_direct(
    database_id: Optional[str] = None,
    status: Optional[str] = None,
    division: Optional[str] = None,
) -> List[Dict[str, Any]]:
    db_id = database_id or settings.notion_database_id
    filters = []

    if status:
        filters.append({"property": "Status", "status": {"equals": status}})
    if division:
        filters.append({"property": "Division", "select": {"equals": division}})

    body = {}
    if len(filters) == 1:
        body["filter"] = filters[0]
    elif len(filters) > 1:
        body["filter"] = {"and": filters}

    cache_key = f"tickets:{db_id}:{status}:{division}"
    
    # Check cache via client request if caching desired, or query_all directly
    results = await client.query_all(f"/databases/{db_id}/query", body=body)
    return results


async def get_ticket_detail(page_id: str) -> Dict[str, Any]:
    return await client.request("GET", f"/pages/{page_id}")


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
        "discussion_id": "",
        "rich_text": [{"text": {"content": comment_text}}],
    }
    return await client.request("POST", "/comments", body=body)
