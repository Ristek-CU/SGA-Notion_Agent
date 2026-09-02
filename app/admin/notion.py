from typing import Optional, List, Dict, Any
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.admin.auth import verify_token
from app.notion.ticket_service import (
    query_tickets_direct,
    create_ticket_direct,
    update_ticket_direct,
    get_ticket_detail,
    get_ticket_blocks,
    add_ticket_note,
    add_ticket_comment,
)
from app.notion.org_service import list_divisions, get_backlog_stats
from app.services.contacts import (
    get_all_contacts,
    add_or_update_contact,
    delete_contact,
)

router = APIRouter(tags=["Admin Notion & Contacts"])


class TicketCreateRequest(BaseModel):
    title: str
    division: Optional[str] = None
    pic_id: Optional[str] = None
    priority: Optional[str] = "Normal"
    status: Optional[str] = "Backlog"
    description: Optional[str] = None


class TicketUpdateRequest(BaseModel):
    title: Optional[str] = None
    division: Optional[str] = None
    pic_id: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None


class CommentRequest(BaseModel):
    comment: str


class NoteRequest(BaseModel):
    note: str


class ContactCreateRequest(BaseModel):
    name: str
    phone: str
    nickname: Optional[str] = None
    role: Optional[str] = None
    division: Optional[str] = None
    telegram: Optional[str] = None


class ContactUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    nickname: Optional[str] = None
    role: Optional[str] = None
    division: Optional[str] = None
    telegram: Optional[str] = None


@router.get("/notion/backlog")
async def get_backlog(
    status: Optional[str] = None,
    division: Optional[str] = None,
    current_user: str = Depends(verify_token),
):
    tickets = await query_tickets_direct(status=status, division=division)
    return {"data": tickets, "error": None, "message": "Backlog tickets fetched"}


@router.get("/notion/overview")
async def get_overview(current_user: str = Depends(verify_token)):
    stats = await get_backlog_stats()
    return {"data": stats, "error": None, "message": "Notion overview fetched"}


@router.post("/notion/tickets")
async def create_ticket(req: TicketCreateRequest, current_user: str = Depends(verify_token)):
    res = await create_ticket_direct(
        title=req.title,
        division=req.division,
        priority=req.priority or "Normal",
        status=req.status or "Backlog",
        description=req.description,
        pic_id=req.pic_id,
    )
    return {"data": res, "error": None, "message": "Ticket created"}


@router.get("/notion/tickets/{page_id}")
async def get_ticket(page_id: str, current_user: str = Depends(verify_token)):
    try:
        page = await get_ticket_detail(page_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Notion API error")
    if "id" not in page:
        raise HTTPException(status_code=404, detail="Ticket not found")

    props = page.get("properties", {})
    people = props.get("PIC", {}).get("people") or []
    relation = props.get("PIC", {}).get("relation") or []

    def _plain(rt_list):
        return "".join(t.get("plain_text", "") for t in rt_list or [])

    rich_content = []
    try:
        blocks = await get_ticket_blocks(page_id)
        for b in blocks.get("results", []):
            text = _plain(b.get(b.get("type", ""), {}).get("rich_text"))
            if text:
                rich_content.append({"type": b.get("type"), "text": text})
    except Exception:
        pass  # ponytail: blocks optional; add pagination when tickets exceed 100 blocks

    data = {
        "id": page.get("id"),
        "ticket_id": _plain(props.get("ID", {}).get("rich_text")),
        "title": _plain(props.get("Name", {}).get("title")),
        "status": (props.get("Status", {}).get("status") or {}).get("name"),
        "priority": (props.get("Priority", {}).get("select") or {}).get("name"),
        "division": (props.get("Division", {}).get("select") or {}).get("name"),
        "pic": (
            [{"id": p.get("id"), "name": p.get("name")} for p in people]
            if people
            else [{"id": r.get("id")} for r in relation]
        ),
        "assignee": [
            {"id": p.get("id"), "name": p.get("name")}
            for p in (props.get("Assignee", {}).get("people") or [])
        ],
        "created_time": page.get("created_time"),
        "last_edited_time": page.get("last_edited_time"),
        "url": page.get("url"),
        "rich_content": rich_content,
    }
    return {"data": data, "error": None, "message": "Ticket detail fetched"}


@router.patch("/notion/tickets/{page_id}")
async def update_ticket(page_id: str, req: TicketUpdateRequest, current_user: str = Depends(verify_token)):
    properties: Dict[str, Any] = {}
    if req.title:
        properties["Name"] = {"title": [{"text": {"content": req.title}}]}
    if req.status:
        properties["Status"] = {"status": {"name": req.status}}
    if req.priority:
        properties["Priority"] = {"select": {"name": req.priority}}
    if req.division:
        properties["Division"] = {"select": {"name": req.division}}
    if req.pic_id:
        properties["PIC"] = {"relation": [{"id": req.pic_id}]}

    res = await update_ticket_direct(page_id, properties)
    return {"data": res, "error": None, "message": "Ticket updated"}


@router.post("/notion/tickets/{page_id}/note")
async def add_note(page_id: str, req: NoteRequest, current_user: str = Depends(verify_token)):
    res = await add_ticket_note(page_id, req.note)
    return {"data": res, "error": None, "message": "Note added to ticket"}


@router.post("/notion/tickets/{page_id}/comment")
async def add_comment(page_id: str, req: CommentRequest, current_user: str = Depends(verify_token)):
    res = await add_ticket_comment(page_id, req.comment)
    return {"data": res, "error": None, "message": "Comment added to ticket"}


@router.get("/notion/divisions")
async def get_divisions(current_user: str = Depends(verify_token)):
    divisions = await list_divisions()
    return {"data": divisions, "error": None, "message": "Divisions fetched"}


# Contacts CRUD
@router.get("/contacts")
async def list_contacts(current_user: str = Depends(verify_token)):
    contacts = await get_all_contacts()
    return {"data": contacts, "error": None, "message": "Contacts fetched"}


@router.post("/contacts")
async def create_contact(req: ContactCreateRequest, current_user: str = Depends(verify_token)):
    contact = await add_or_update_contact(req.name, req.phone, req.role, req.division, nickname=req.nickname, telegram=req.telegram)
    return {"data": contact, "error": None, "message": "Contact saved"}


@router.put("/contacts/{phone}")
async def update_contact(phone: str, req: ContactUpdateRequest, current_user: str = Depends(verify_token)):
    contact = await add_or_update_contact(req.name, req.phone or phone, req.role, req.division, nickname=req.nickname, telegram=req.telegram)
    return {"data": contact, "error": None, "message": "Contact updated"}


@router.delete("/contacts/{phone}")
async def remove_contact(phone: str, current_user: str = Depends(verify_token)):
    deleted = await delete_contact(phone)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"data": {"phone": phone}, "error": None, "message": "Contact deleted"}
