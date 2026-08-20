from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.admin.auth import verify_token
from app.notion.ticket_service import (
    query_tickets_direct,
    create_ticket_direct,
    update_ticket_direct,
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
    role: Optional[str] = None
    division: Optional[str] = None


class ContactUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    division: Optional[str] = None


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
def list_contacts(current_user: str = Depends(verify_token)):
    contacts = get_all_contacts()
    return {"data": contacts, "error": None, "message": "Contacts fetched"}


@router.post("/contacts")
def create_contact(req: ContactCreateRequest, current_user: str = Depends(verify_token)):
    contact = add_or_update_contact(req.name, req.phone, req.role, req.division)
    return {"data": contact, "error": None, "message": "Contact saved"}


@router.put("/contacts/{phone}")
def update_contact(phone: str, req: ContactUpdateRequest, current_user: str = Depends(verify_token)):
    contact = add_or_update_contact(req.name or phone, req.phone or phone, req.role, req.division)
    return {"data": contact, "error": None, "message": "Contact updated"}


@router.delete("/contacts/{phone}")
def remove_contact(phone: str, current_user: str = Depends(verify_token)):
    deleted = delete_contact(phone)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"data": {"phone": phone}, "error": None, "message": "Contact deleted"}
