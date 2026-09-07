import logging
import asyncio
from typing import Dict, Any, List, Optional
from app.config import settings
from app.notion.core import NotionClient
from app.services.contacts import normalize_phone, format_title_case, _sync_contact_to_file

logger = logging.getLogger(__name__)

NOTION_MEMBERS_DB_ID = "32f3f1cb-81ff-8175-909e-cb040b90cd30"
NOTION_DIVISIONS_DB_ID = "32f3f1cb-81ff-8171-9578-f226ad73c5c1"


async def get_division_mapping(client: Optional[NotionClient] = None) -> Dict[str, str]:
    """Mengambil mapping {division_page_id: division_name} dari Notion Divisions DB."""
    div_db = settings.notion_divisions_id or NOTION_DIVISIONS_DB_ID
    c = client or NotionClient(api_key=settings.notion_api_key, version=settings.notion_version)
    div_map = {}
    try:
        pages = await c.query_all(f"/databases/{div_db}/query")
        for p in pages:
            props = p.get("properties", {})
            for v in props.values():
                if v.get("type") == "title":
                    title = "".join(x.get("plain_text", "") for x in v.get("title", [])).strip()
                    if title:
                        div_map[p["id"]] = title
                    break
    except Exception as e:
        logger.warning(f"Error loading division mapping from Notion: {e}")
    return div_map


def extract_member_data(page: Dict[str, Any], division_map: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """Mengekstrak field penting dari satu halaman Notion Member."""
    props = page.get("properties", {})
    page_id = page.get("id")

    # Member Name (title)
    name_prop = props.get("Member Name", {}).get("title", [])
    if not name_prop:
        # Fallback cari properti bertipe title apapun
        for v in props.values():
            if v.get("type") == "title":
                name_prop = v.get("title", [])
                break
    name = "".join(x.get("plain_text", "") for x in name_prop).strip()
    if not name:
        return None

    # WhatsApp (rich_text / phone_number)
    wa_prop = props.get("WhatsApp", {})
    phone_raw = ""
    if wa_prop.get("type") == "rich_text":
        phone_raw = "".join(x.get("plain_text", "") for x in wa_prop.get("rich_text", [])).strip()
    elif wa_prop.get("type") == "phone_number":
        phone_raw = str(wa_prop.get("phone_number") or "").strip()
    
    phone = normalize_phone(phone_raw) if phone_raw else None

    # Role (select)
    role_obj = props.get("Role", {}).get("select")
    role = role_obj.get("name") if role_obj else None

    # Division (relation)
    division = None
    div_rel = props.get("Division", {}).get("relation", [])
    if div_rel and division_map:
        rel_id = div_rel[0].get("id")
        division = division_map.get(rel_id)
    elif div_rel:
        rel_id = div_rel[0].get("id")
        division = rel_id

    return {
        "notion_member_id": page_id,
        "name": format_title_case(name),
        "phone": phone,
        "role": role,
        "division": division,
    }


async def sync_notion_members_to_contacts() -> Dict[str, Any]:
    """
    Sinkronisasi seluruh member dari Notion Members DB ke contacts PostgreSQL.
    Aturan:
    - Tarik data member dan divisi dari Notion.
    - Upsert ke PostgreSQL:
      * Jika sudah ada berdasarkan notion_member_id atau phone:
        update name, phone, division, role, notion_member_id (pertahankan telegram & telegram_chat_id).
      * Jika member baru:
        insert ke contacts.
    - Sinkronkan ke local contacts.json & clear identity cache.
    """
    mem_db = settings.notion_members_id or settings.notion_member_id or NOTION_MEMBERS_DB_ID
    client = NotionClient(
        api_key=settings.notion_api_key,
        version=settings.notion_version,
        max_rps=settings.notion_rate_limit_rps,
        max_retries=settings.notion_max_retries,
    )

    try:
        division_map = await get_division_mapping(client)
        pages = await client.query_all(f"/databases/{mem_db}/query")
    except Exception as e:
        logger.error(f"Failed querying Notion Members DB ({mem_db}): {e}")
        return {"success": False, "error": str(e), "synced": 0, "inserted": 0, "updated": 0, "skipped": 0}

    total_pages = len(pages)
    inserted = 0
    updated = 0
    skipped = 0

    from app.services.database import get_db_pool
    pool = await get_db_pool()

    for page in pages:
        data = extract_member_data(page, division_map)
        if not data:
            skipped += 1
            continue

        p_id = data["notion_member_id"]
        p_name = data["name"]
        p_phone = data["phone"]
        p_role = data["role"]
        p_div = data["division"]

        # Jika tidak ada nomor telepon dan tidak ada ID, skip karena phone adalah primary identity key
        if not p_phone and not p_id:
            skipped += 1
            continue

        if pool:
            try:
                async with pool.acquire() as conn:
                    # 1. Cari existing contact berdasarkan notion_member_id ATAU phone ATAU nama lengkap
                    existing = None
                    if p_id:
                        existing = await conn.fetchrow(
                            "SELECT id, name, phone, telegram, telegram_chat_id FROM contacts WHERE notion_member_id = $1 LIMIT 1",
                            p_id
                        )
                    if not existing and p_phone:
                        existing = await conn.fetchrow(
                            "SELECT id, name, phone, telegram, telegram_chat_id FROM contacts WHERE phone = $1 LIMIT 1",
                            p_phone
                        )
                    if not existing and p_name:
                        existing = await conn.fetchrow(
                            "SELECT id, name, phone, telegram, telegram_chat_id FROM contacts WHERE LOWER(TRIM(name)) = $1 LIMIT 1",
                            p_name.strip().lower()
                        )

                    if existing:
                        # Update record yang sudah ada tanpa menimpa telegram_chat_id / telegram jika tidak diubah
                        # Phone gunakan yang terbaru jika ada (dan bukan placeholder), jika tidak tetap gunakan phone lama
                        final_phone = p_phone or existing["phone"]
                        await conn.execute(
                            """
                            UPDATE contacts
                            SET name = COALESCE($1, contacts.name),
                                phone = $2,
                                division = COALESCE($3, contacts.division),
                                role = COALESCE($4, contacts.role),
                                notion_member_id = $5,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = $6
                            """,
                            p_name, final_phone, p_div, p_role, p_id, existing["id"]
                        )
                        updated += 1
                    else:
                        # Jika member baru belum ada nomor telepon, generate placeholder agar NOT NULL constraint terpenuhi
                        insert_phone = p_phone or f"notion_{p_id.replace('-', '')[:15]}"
                        await conn.execute(
                            """
                            INSERT INTO contacts (name, nickname, phone, division, role, aliases, notion_member_id)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            ON CONFLICT (phone) DO UPDATE SET
                                name = EXCLUDED.name,
                                division = COALESCE(EXCLUDED.division, contacts.division),
                                role = COALESCE(EXCLUDED.role, contacts.role),
                                notion_member_id = EXCLUDED.notion_member_id,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            p_name, p_name, insert_phone, p_div, p_role, [p_name.lower()], p_id
                        )
                        inserted += 1
            except Exception as e:
                logger.warning(f"Error syncing contact {p_name} ({p_id}): {e}")
                skipped += 1
        else:
            # Fallback jika database pool tidak aktif
            if p_phone:
                from app.services.contacts import add_or_update_contact
                await add_or_update_contact(
                    name=p_name,
                    phone=p_phone,
                    role=p_role,
                    division=p_div,
                    notion_member_id=p_id
                )
                updated += 1
            else:
                skipped += 1

    # Update cache contacts.json dari PostgreSQL untuk sinkronisasi fallback
    if pool:
        try:
            from app.services.contacts import get_all_contacts, _save_contacts_to_file
            all_c = await get_all_contacts()
            _save_contacts_to_file(all_c)
        except Exception as e:
            logger.warning(f"Error refreshing contacts.json cache after sync: {e}")

    try:
        from app.services.identity import clear_identity_cache
        clear_identity_cache()
    except Exception:
        pass

    logger.info(f"Notion members sync completed: total={total_pages}, inserted={inserted}, updated={updated}, skipped={skipped}")
    return {
        "success": True,
        "total_notion_pages": total_pages,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
    }


async def update_notion_member_phone(page_id: str, new_phone: str) -> bool:
    """
    Two-way sync: Perbarui properti 'WhatsApp' di halaman Notion Member terkait.
    """
    if not page_id or not new_phone:
        return False

    client = NotionClient(
        api_key=settings.notion_api_key,
        version=settings.notion_version,
    )
    norm = normalize_phone(new_phone)
    payload = {
        "properties": {
            "WhatsApp": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": norm}
                    }
                ]
            }
        }
    }
    try:
        await client.request("PATCH", f"/pages/{page_id}", body=payload)
        logger.info(f"Updated Notion member page {page_id} WhatsApp to {norm}")
        return True
    except Exception as e:
        logger.warning(f"Failed updating WhatsApp on Notion page {page_id}: {e}")
        return False
