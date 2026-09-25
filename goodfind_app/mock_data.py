"""
Multi-tenant data store for GoodFind with Supabase PostgreSQL integration.

This module provides a unified interface:
- If SUPABASE_URL and SUPABASE_KEY are provided in .env, queries are executed
  against Supabase PostgreSQL tables.
- Otherwise, it falls back to the in-memory data structures so local development
  and offline tests run without any external dependencies.

Tables mapped:
- organizations
- users
- lost_reports
- found_reports
- matches
- ownership_claims
- conversations & messages
- notifications
"""
import itertools
import os
import uuid
from datetime import datetime, timedelta, date, time
from werkzeug.security import generate_password_hash, check_password_hash

import supabase_client

_id_counter = itertools.count(1000)


def next_id(prefix):
    """Generate an ID. Uses UUID for Supabase, or prefixed counter for mock fallback."""
    if supabase_client.is_supabase_enabled():
        return str(uuid.uuid4())
    return f"{prefix}-{next(_id_counter)}"


CATEGORIES = [
    "Mobile Phone", "Laptop", "Wallet", "Bag", "Watch",
    "Earbuds", "Keys", "Books", "Documents", "ID Card", "Other"
]

STATUSES = [
    "Searching", "Possible Match", "Verification Pending",
    "Approved - Ready for Pickup", "Returned", "Closed"
]

ORG_TYPES = [
    "College", "School", "Workplace", "Hospital",
    "Transport hub", "Event venue", "Other"
]


# ---------------------------------------------------------------------------
# IN-MEMORY SEED DATA (Used when Supabase is not configured)
# ---------------------------------------------------------------------------
ORGANIZATIONS = {
    "org-001": {
        "id": "org-001",
        "name": "VSB Engineering College",
        "type": "College",
        "email_domain": "vsbec.ac.in",
        "join_code": "VSB2026",
        "collection_desk": "Admin Block, Room 12",
        "contact": "helpdesk@vsbec.ac.in",
        "retention_days": 90,
    },
    "org-002": {
        "id": "org-002",
        "name": "Northgate Tech Park",
        "type": "Workplace",
        "email_domain": "northgate.example",
        "join_code": "NGATE01",
        "collection_desk": "Tower B Reception",
        "contact": "facilities@northgate.example",
        "retention_days": 60,
    },
}

USERS = {
    "demo@vsbec.ac.in": {
        "id": "user-001", "org_id": "org-001", "name": "Alex Carter",
        "email": "demo@vsbec.ac.in", "password": "demo1234",
        "password_hash": generate_password_hash("demo1234"),
        "role": "member", "avatar": "",
    },
    "desk@vsbec.ac.in": {
        "id": "user-002", "org_id": "org-001", "name": "Priya (Front Desk)",
        "email": "desk@vsbec.ac.in", "password": "desk1234",
        "password_hash": generate_password_hash("desk1234"),
        "role": "staff", "avatar": "",
    },
    "admin@vsbec.ac.in": {
        "id": "user-admin", "org_id": "org-001", "name": "Campus Admin",
        "email": "admin@vsbec.ac.in", "password": "admin1234",
        "password_hash": generate_password_hash("admin1234"),
        "role": "admin", "avatar": "",
    },
    "ravi@northgate.example": {
        "id": "user-101", "org_id": "org-002", "name": "Ravi Menon",
        "email": "ravi@northgate.example", "password": "ravi1234",
        "password_hash": generate_password_hash("ravi1234"),
        "role": "member", "avatar": "",
    },
}

LOST_ITEMS = [
    {
        "id": "lost-001", "org_id": "org-001", "user_id": "user-001",
        "name": "Keys with blue lanyard", "category": "Keys", "brand": "",
        "model": "", "color": "Silver", "location": "Near College Library",
        "date": "2026-09-14", "time": "09:41",
        "description": "A set of 4 keys on a blue lanyard, one is a car key fob.",
        "image_url": "", "image_fp": None, "status": "Searching",
        "created_at": datetime.now() - timedelta(days=2),
    },
    {
        "id": "lost-002", "org_id": "org-001", "user_id": "user-001",
        "name": "Black Samsung Galaxy Phone", "category": "Mobile Phone",
        "brand": "Samsung", "model": "Galaxy S23", "color": "Black",
        "location": "College Library reading hall", "date": "2026-09-17",
        "time": "14:00",
        "description": "Black phone with a cracked screen protector.",
        "image_url": "uploads/seed/phone_owner.png", "image_fp": None,
        "status": "Possible Match",
        "created_at": datetime.now() - timedelta(days=1),
    },
    {
        "id": "lost-003", "org_id": "org-002", "user_id": "user-101",
        "name": "Grey laptop sleeve", "category": "Bag", "brand": "",
        "model": "", "color": "Grey", "location": "Tower B cafeteria",
        "date": "2026-09-16", "time": "13:20",
        "description": "Felt sleeve, 14 inch, small ink stain on the corner.",
        "image_url": "", "image_fp": None, "status": "Searching",
        "created_at": datetime.now() - timedelta(days=3),
    },
]

FOUND_ITEMS = [
    {
        "id": "found-004", "org_id": "org-001", "user_id": "user-002",
        "name": "Black Android Phone", "category": "Mobile Phone",
        "brand": "Samsung", "model": "Galaxy S23", "color": "Black",
        "location": "College Library, 2nd floor", "date": "2026-09-17",
        "time": "15:10",
        "description": "Found near the reading desks, screen locked. Black phone, cracked screen protector.",
        "image_url": "uploads/seed/phone_finder.png", "image_fp": None,
        "status": "Possible Match",
        "created_at": datetime.now() - timedelta(hours=20),
    },
    {
        "id": "found-005", "org_id": "org-001", "user_id": "user-002",
        "name": "Brown Leather Wallet", "category": "Wallet", "brand": "",
        "model": "", "color": "Brown", "location": "Cafeteria",
        "date": "2026-09-15", "time": "12:30",
        "description": "Bifold wallet, no cash visible.",
        "image_url": "uploads/seed/wallet_finder.png", "image_fp": None, "status": "Searching",
        "created_at": datetime.now() - timedelta(days=3),
    },
]

RETURNED_ITEMS = [
    {
        "id": "lost-000", "org_id": "org-001", "user_id": "user-001",
        "name": "Airpods Pro Case", "category": "Earbuds", "brand": "Apple",
        "model": "", "color": "White", "location": "Sports Ground",
        "date": "2026-09-05", "time": "17:00",
        "description": "White charging case, minor scratch on the lid.",
        "image_url": "", "image_fp": None, "status": "Returned",
        "created_at": datetime.now() - timedelta(days=14),
    },
]

MATCHES = []

CONVERSATIONS = [
    {
        "id": "conv-001", "org_id": "org-001",
        "participants": ["user-001", "user-002"],
        "other_user_name": "Priya (Front Desk)",
        "item_summary": "Brown Leather Wallet",
        "messages": [
            {"sender": "user-002", "text": "Hi, a brown wallet was handed in at the cafeteria desk.",
             "time": "Yesterday, 2:15 PM"},
            {"sender": "user-001", "text": "That sounds like mine. Does it have a student ID inside?",
             "time": "Yesterday, 2:20 PM"},
        ],
    },
]

NOTIFICATIONS = [
    {"id": "notif-003", "org_id": "org-001", "user_id": "user-001",
     "type": "returned", "title": "Airpods Pro Case returned",
     "body": "Collected from Admin Block, Room 12. Case closed.",
     "read": True, "created_at": datetime.now() - timedelta(days=14),
     "link_id": None},
    {"id": "notif-002", "org_id": "org-001", "user_id": "user-001",
     "type": "message", "title": "New message from Priya (Front Desk)",
     "body": "Regarding: Brown Leather Wallet", "read": False,
     "created_at": datetime.now() - timedelta(days=1), "link_id": "conv-001"},
]

OWNERSHIP_CLAIMS = []


# ---------------------------------------------------------------------------
# Normalization Helper
# ---------------------------------------------------------------------------
def _normalize_item_row(row):
    """Ensure database item row matches expected dictionary structure."""
    if not row:
        return None
    d = dict(row)
    # Map occurred_on -> date and occurred_at -> time
    if "occurred_on" in d and not d.get("date"):
        d["date"] = str(d["occurred_on"])
    if "occurred_at" in d and not d.get("time"):
        d["time"] = str(d["occurred_at"])[:5] if d["occurred_at"] else ""
    return d


# ---------------------------------------------------------------------------
# ORGANIZATIONS
# ---------------------------------------------------------------------------
def get_all_orgs():
    """Return all organizations."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("organizations").select("*").execute()
            return res.data or []
        except Exception as e:
            print(f"[Supabase] get_all_orgs error: {e}")
    return list(ORGANIZATIONS.values())


def get_org(org_id):
    """Retrieve organization by its ID."""
    if not org_id:
        return None
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("organizations").select("*").eq("id", org_id).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[Supabase] get_org error: {e}")
    return ORGANIZATIONS.get(org_id)


def get_org_by_domain(email):
    """Auto-join rule: match the email domain against every org domain."""
    if not email or "@" not in email:
        return None
    domain = email.split("@")[-1].strip().lower()
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("organizations").select("*").ilike("email_domain", domain).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[Supabase] get_org_by_domain error: {e}")
    return next((o for o in ORGANIZATIONS.values()
                 if (o.get("email_domain") or "").lower() == domain), None)


def get_org_by_code(code):
    """Find organization by join code."""
    code = (code or "").strip().upper()
    if not code:
        return None
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("organizations").select("*").ilike("join_code", code).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[Supabase] get_org_by_code error: {e}")
    return next((o for o in ORGANIZATIONS.values()
                 if (o.get("join_code") or "").upper() == code), None)


def create_org(name, org_type, email_domain, join_code, collection_desk, contact):
    """Create a new organization."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            payload = {
                "name": name.strip(),
                "type": org_type or "Other",
                "email_domain": email_domain.strip().lower() if email_domain else None,
                "join_code": join_code.strip().upper(),
                "collection_desk": collection_desk.strip(),
                "contact": contact.strip() if contact else None,
                "retention_days": 90,
            }
            res = client.table("organizations").insert(payload).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[Supabase] create_org error: {e}")

    org_id = next_id("org")
    ORGANIZATIONS[org_id] = {
        "id": org_id, "name": name.strip(), "type": org_type,
        "email_domain": email_domain.strip().lower(),
        "join_code": join_code.strip().upper(),
        "collection_desk": collection_desk.strip(),
        "contact": contact.strip(), "retention_days": 90,
    }
    return ORGANIZATIONS[org_id]


def update_org_collection_desk(org_id, desk):
    """Update collection desk location for an organization."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            client.table("organizations").update({"collection_desk": desk.strip()}).eq("id", org_id).execute()
            return True
        except Exception as e:
            print(f"[Supabase] update_org_collection_desk error: {e}")
    org = ORGANIZATIONS.get(org_id)
    if org:
        org["collection_desk"] = desk.strip()
        return True
    return False


# ---------------------------------------------------------------------------
# USERS & AUTHENTICATION
# ---------------------------------------------------------------------------
def get_user_by_id(user_id):
    """Retrieve user by ID."""
    if not user_id:
        return None
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("users").select("*").eq("id", user_id).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[Supabase] get_user_by_id error: {e}")
    return next((u for u in USERS.values() if u["id"] == user_id), None)


def get_user_by_email(email):
    """Find user record by email (case-insensitive)."""
    if not email:
        return None
    email_clean = email.strip().lower()
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("users").select("*").ilike("email", email_clean).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[Supabase] get_user_by_email error: {e}")
    return USERS.get(email_clean)


def create_user(name, email, password, org_id, role="member"):
    """Register a new user account with hashed password."""
    email_clean = email.strip().lower()
    hashed = generate_password_hash(password)
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            payload = {
                "org_id": org_id,
                "name": name.strip(),
                "email": email_clean,
                "password_hash": hashed,
                "role": role,
                "avatar": "",
            }
            res = client.table("users").insert(payload).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[Supabase] create_user error: {e}")

    user_id = next_id("user")
    user = {
        "id": user_id, "org_id": org_id, "name": name.strip(),
        "email": email_clean, "password": password, "password_hash": hashed,
        "role": role, "avatar": "",
    }
    USERS[email_clean] = user
    return user


def verify_user_password(user, password):
    """Verify plaintext password against user record."""
    if not user:
        return False
    if "password_hash" in user and user["password_hash"]:
        return check_password_hash(user["password_hash"], password)
    return user.get("password") == password


def update_user_name(user_id, name):
    """Update user's display name."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            client.table("users").update({"name": name.strip()}).eq("id", user_id).execute()
            return True
        except Exception as e:
            print(f"[Supabase] update_user_name error: {e}")
    user = get_user_by_id(user_id)
    if user:
        user["name"] = name.strip()
        return True
    return False


def org_members(org_id):
    """Return all members belonging to an organization."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("users").select("*").eq("org_id", org_id).order("name").execute()
            return res.data or []
        except Exception as e:
            print(f"[Supabase] org_members error: {e}")
    return [u for u in USERS.values() if u.get("org_id") == org_id]


# ---------------------------------------------------------------------------
# ITEMS (Lost, Found, Returned)
# ---------------------------------------------------------------------------
def get_item(item_id):
    """Polymorphic lookup: finds item across lost, found, and returned pools."""
    if not item_id:
        return None
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            # Check lost_reports
            r_lost = client.table("lost_reports").select("*").eq("id", item_id).execute()
            if r_lost.data:
                item = _normalize_item_row(r_lost.data[0])
                item["kind"] = "lost"
                return item
            # Check found_reports
            r_found = client.table("found_reports").select("*").eq("id", item_id).execute()
            if r_found.data:
                item = _normalize_item_row(r_found.data[0])
                item["kind"] = "found"
                return item
        except Exception as e:
            print(f"[Supabase] get_item error: {e}")

    for i in LOST_ITEMS + FOUND_ITEMS + RETURNED_ITEMS:
        if i["id"] == item_id:
            return i
    return None


def org_lost_items(org_id):
    """Return all lost reports for an organization."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("lost_reports").select("*").eq("org_id", org_id).execute()
            return [_normalize_item_row(r) for r in (res.data or [])]
        except Exception as e:
            print(f"[Supabase] org_lost_items error: {e}")
    return [i for i in LOST_ITEMS if i.get("org_id") == org_id]


def org_found_items(org_id):
    """Return all found reports for an organization."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("found_reports").select("*").eq("org_id", org_id).execute()
            return [_normalize_item_row(r) for r in (res.data or [])]
        except Exception as e:
            print(f"[Supabase] org_found_items error: {e}")
    return [i for i in FOUND_ITEMS if i.get("org_id") == org_id]


def add_lost_report(item_data):
    """Insert a new lost report."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            payload = {
                "org_id": item_data["org_id"],
                "user_id": item_data["user_id"],
                "name": item_data["name"],
                "category": item_data["category"],
                "brand": item_data.get("brand", ""),
                "model": item_data.get("model", ""),
                "color": item_data.get("color", ""),
                "location": item_data["location"],
                "occurred_on": item_data.get("date"),
                "occurred_at": item_data.get("time") or None,
                "description": item_data["description"],
                "image_url": item_data.get("image_url", ""),
                "image_fp": item_data.get("image_fp"),
                "status": item_data.get("status", "Searching"),
            }
            res = client.table("lost_reports").insert(payload).execute()
            if res.data:
                saved = _normalize_item_row(res.data[0])
                item_data["id"] = saved["id"]
                return saved
        except Exception as e:
            print(f"[Supabase] add_lost_report error: {e}")

    LOST_ITEMS.append(item_data)
    return item_data


def add_found_report(item_data):
    """Insert a new found report."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            payload = {
                "org_id": item_data["org_id"],
                "user_id": item_data["user_id"],
                "name": item_data["name"],
                "category": item_data["category"],
                "brand": item_data.get("brand", ""),
                "model": item_data.get("model", ""),
                "color": item_data.get("color", ""),
                "location": item_data["location"],
                "occurred_on": item_data.get("date"),
                "occurred_at": item_data.get("time") or None,
                "description": item_data["description"],
                "image_url": item_data.get("image_url", ""),
                "image_fp": item_data.get("image_fp"),
                "status": item_data.get("status", "Searching"),
            }
            res = client.table("found_reports").insert(payload).execute()
            if res.data:
                saved = _normalize_item_row(res.data[0])
                item_data["id"] = saved["id"]
                return saved
        except Exception as e:
            print(f"[Supabase] add_found_report error: {e}")

    FOUND_ITEMS.append(item_data)
    return item_data


def get_user_lost_reports(user_id, org_id):
    """Lost reports belonging to a specific user within their organization."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("lost_reports").select("*")\
                .eq("user_id", user_id).eq("org_id", org_id)\
                .neq("status", "Returned").execute()
            return [_normalize_item_row(r) for r in (res.data or [])]
        except Exception as e:
            print(f"[Supabase] get_user_lost_reports error: {e}")
    return [i for i in LOST_ITEMS if i.get("user_id") == user_id and i.get("org_id") == org_id]


def get_user_found_reports(user_id, org_id):
    """Found reports handed in by a user within their organization."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("found_reports").select("*")\
                .eq("user_id", user_id).eq("org_id", org_id)\
                .neq("status", "Returned").execute()
            return [_normalize_item_row(r) for r in (res.data or [])]
        except Exception as e:
            print(f"[Supabase] get_user_found_reports error: {e}")
    return [i for i in FOUND_ITEMS if i.get("user_id") == user_id and i.get("org_id") == org_id]


def get_user_returned_reports(user_id, org_id):
    """Reports returned/closed for a user within their organization."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            r1 = client.table("lost_reports").select("*").eq("user_id", user_id).eq("org_id", org_id).eq("status", "Returned").execute()
            r2 = client.table("found_reports").select("*").eq("user_id", user_id).eq("org_id", org_id).eq("status", "Returned").execute()
            combined = (r1.data or []) + (r2.data or [])
            return [_normalize_item_row(r) for r in combined]
        except Exception as e:
            print(f"[Supabase] get_user_returned_reports error: {e}")
    return [i for i in RETURNED_ITEMS if i.get("user_id") == user_id and i.get("org_id") == org_id]


def update_item_status(item_id, status):
    """Update status of a lost or found report."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            client.table("lost_reports").update({"status": status}).eq("id", item_id).execute()
            client.table("found_reports").update({"status": status}).eq("id", item_id).execute()
            return True
        except Exception as e:
            print(f"[Supabase] update_item_status error: {e}")
    item = get_item(item_id)
    if item:
        item["status"] = status
        return True
    return False


# ---------------------------------------------------------------------------
# MATCHES
# ---------------------------------------------------------------------------
def add_match(lost_item, found_item, score, factors, notes=None):
    """Insert or update a match record between a lost and found item."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            payload = {
                "org_id": lost_item["org_id"],
                "lost_item_id": lost_item["id"],
                "found_item_id": found_item["id"],
                "score": score,
                "factors": factors or {},
                "notes": notes or {},
            }
            res = client.table("matches").upsert(payload, on_conflict="lost_item_id,found_item_id").execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[Supabase] add_match error: {e}")

    for m in MATCHES:
        if m["lost_item_id"] == lost_item["id"] and m["found_item_id"] == found_item["id"]:
            m["score"], m["factors"], m["notes"] = score, factors, notes or {}
            return m
    match = {
        "id": next_id("match"), "org_id": lost_item["org_id"],
        "lost_item_id": lost_item["id"], "found_item_id": found_item["id"],
        "score": score, "factors": factors, "notes": notes or {},
        "claim_status": "none", "claim_answer": "", "created_at": datetime.now(),
    }
    MATCHES.append(match)
    return match


def get_match(match_id):
    """Retrieve match record by ID."""
    if not match_id:
        return None
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("matches").select("*").eq("id", match_id).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"[Supabase] get_match error: {e}")
    return next((m for m in MATCHES if m["id"] == match_id), None)


def get_matches_for_user(user_id, org_id):
    """Retrieve matches for reports submitted by this user in their organization."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            # Get user's lost report IDs
            r_lost = client.table("lost_reports").select("id").eq("user_id", user_id).eq("org_id", org_id).execute()
            lost_ids = [r["id"] for r in (r_lost.data or [])]
            if not lost_ids:
                return []
            res = client.table("matches").select("*").in_("lost_item_id", lost_ids).order("score", desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"[Supabase] get_matches_for_user error: {e}")

    my_lost = {i["id"] for i in LOST_ITEMS if i["user_id"] == user_id and i["org_id"] == org_id}
    rows = [m for m in MATCHES if m["lost_item_id"] in my_lost]
    return sorted(rows, key=lambda m: m["score"], reverse=True)


def get_claims_for_staff(org_id):
    """Pending ownership claims that front-desk staff must review."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("matches").select("*").eq("org_id", org_id).eq("claim_status", "pending").execute()
            return res.data or []
        except Exception as e:
            print(f"[Supabase] get_claims_for_staff error: {e}")
    return [m for m in MATCHES if m["org_id"] == org_id and m.get("claim_status") == "pending"]


def match_count_for_item(item_id):
    """Count matches generated for a lost report."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("matches").select("id", count="exact").eq("lost_item_id", item_id).execute()
            return res.count or 0
        except Exception as e:
            print(f"[Supabase] match_count_for_item error: {e}")
    return sum(1 for m in MATCHES if m["lost_item_id"] == item_id)


def submit_ownership_claim(match_id, lost_item_id, claimant_id, answer):
    """Submit proof of ownership for a match."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            match = get_match(match_id)
            if match:
                client.table("matches").update({
                    "claim_status": "pending",
                    "claim_answer": answer.strip()
                }).eq("id", match_id).execute()
                client.table("lost_reports").update({"status": "Verification Pending"}).eq("id", lost_item_id).execute()
                # Record in ownership_claims audit table
                client.table("ownership_claims").insert({
                    "org_id": match["org_id"],
                    "match_id": match_id,
                    "claimant_id": claimant_id,
                    "identifying_answer": answer.strip(),
                    "status": "pending"
                }).execute()
                return True
        except Exception as e:
            print(f"[Supabase] submit_ownership_claim error: {e}")

    match = get_match(match_id)
    lost = get_item(lost_item_id)
    if match and lost:
        match["claim_answer"] = answer.strip()
        match["claim_status"] = "pending"
        lost["status"] = "Verification Pending"
        OWNERSHIP_CLAIMS.append({
            "id": next_id("claim"), "org_id": match["org_id"],
            "match_id": match_id, "claimant_id": claimant_id,
            "identifying_answer": answer.strip(), "status": "pending",
            "created_at": datetime.now()
        })
        return True
    return False


def decide_ownership_claim(match_id, decision, reviewer_id=None):
    """Staff decision: approve or reject claim."""
    match = get_match(match_id)
    if not match:
        return False

    lost_id = match["lost_item_id"]
    found_id = match["found_item_id"]

    new_claim_status = "approved" if decision == "approve" else "rejected"
    new_lost_status = "Approved - Ready for Pickup" if decision == "approve" else "Searching"
    new_found_status = "Approved - Ready for Pickup" if decision == "approve" else "Possible Match"

    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            client.table("matches").update({"claim_status": new_claim_status}).eq("id", match_id).execute()
            client.table("lost_reports").update({"status": new_lost_status}).eq("id", lost_id).execute()
            if decision == "approve":
                client.table("found_reports").update({"status": new_found_status}).eq("id", found_id).execute()
            client.table("ownership_claims").update({
                "status": new_claim_status,
                "reviewed_by": reviewer_id,
                "reviewed_at": datetime.now().isoformat()
            }).eq("match_id", match_id).execute()
            return True
        except Exception as e:
            print(f"[Supabase] decide_ownership_claim error: {e}")

    match["claim_status"] = new_claim_status
    lost = get_item(lost_id)
    found = get_item(found_id)
    if lost:
        lost["status"] = new_lost_status
    if found and decision == "approve":
        found["status"] = new_found_status
    return True


def mark_item_returned(item_id):
    """Mark item as returned and close matching cases."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            client.table("found_reports").update({"status": "Returned"}).eq("id", item_id).execute()
            # Find approved matches
            r_match = client.table("matches").select("*").eq("found_item_id", item_id).eq("claim_status", "approved").execute()
            for m in (r_match.data or []):
                client.table("lost_reports").update({"status": "Returned"}).eq("id", m["lost_item_id"]).execute()
            return True
        except Exception as e:
            print(f"[Supabase] mark_item_returned error: {e}")

    found = get_item(item_id)
    if not found:
        return False
    found["status"] = "Returned"
    for m in MATCHES:
        if m["found_item_id"] == item_id and m.get("claim_status") == "approved":
            lost = get_item(m["lost_item_id"])
            if lost:
                lost["status"] = "Returned"
                if lost in LOST_ITEMS:
                    LOST_ITEMS.remove(lost)
                    RETURNED_ITEMS.append(lost)
    return True


# ---------------------------------------------------------------------------
# MESSAGING
# ---------------------------------------------------------------------------
def get_conversations_for_user(user_id, org_id):
    """Retrieve all conversation threads involving this user."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("conversations").select("*, messages(*)").eq("org_id", org_id)\
                .or_(f"participant_a.eq.{user_id},participant_b.eq.{user_id}").execute()
            convs = []
            for c in (res.data or []):
                other_id = c["participant_b"] if c["participant_a"] == user_id else c["participant_a"]
                other_u = get_user_by_id(other_id)
                msgs = sorted(c.get("messages", []), key=lambda m: m["created_at"])
                convs.append({
                    "id": c["id"],
                    "org_id": c["org_id"],
                    "participants": [c["participant_a"], c["participant_b"]],
                    "other_user_name": other_u["name"] if other_u else "Member",
                    "item_summary": c["item_summary"],
                    "messages": [
                        {"sender": m["sender_id"], "text": m["text"],
                         "time": str(m["created_at"])[:16]} for m in msgs
                    ]
                })
            return convs
        except Exception as e:
            print(f"[Supabase] get_conversations_for_user error: {e}")

    return [c for c in CONVERSATIONS
            if user_id in c["participants"] and c["org_id"] == org_id]


def start_conversation(org_id, user_a, user_b, item_summary, opening=None):
    """Open or reuse a private thread between owner and finder."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            # Check existing thread
            res = client.table("conversations").select("*").eq("org_id", org_id)\
                .eq("item_summary", item_summary)\
                .or_(f"and(participant_a.eq.{user_a},participant_b.eq.{user_b}),and(participant_a.eq.{user_b},participant_b.eq.{user_a})")\
                .execute()
            if res.data:
                return res.data[0]

            new_conv = client.table("conversations").insert({
                "org_id": org_id,
                "participant_a": user_a,
                "participant_b": user_b,
                "item_summary": item_summary
            }).execute()
            conv_id = new_conv.data[0]["id"]
            if opening:
                client.table("messages").insert({
                    "conversation_id": conv_id,
                    "sender_id": user_a,
                    "text": opening
                }).execute()
            return new_conv.data[0]
        except Exception as e:
            print(f"[Supabase] start_conversation error: {e}")

    for c in CONVERSATIONS:
        if (c["org_id"] == org_id and c["item_summary"] == item_summary
                and set(c["participants"]) == {user_a, user_b}):
            return c
    other = get_user_by_id(user_b)
    conv = {
        "id": next_id("conv"), "org_id": org_id,
        "participants": [user_a, user_b],
        "other_user_name": other["name"] if other else "Finder",
        "item_summary": item_summary, "messages": [],
    }
    if opening:
        conv["messages"].append({"sender": user_a, "text": opening,
                                 "time": datetime.now().strftime("%d %b, %I:%M %p")})
    CONVERSATIONS.append(conv)
    return conv


def get_conversation(conv_id):
    """Retrieve conversation by ID."""
    if not conv_id:
        return None
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("conversations").select("*, messages(*)").eq("id", conv_id).execute()
            if res.data:
                c = res.data[0]
                msgs = sorted(c.get("messages", []), key=lambda m: m["created_at"])
                return {
                    "id": c["id"],
                    "org_id": c["org_id"],
                    "participants": [c["participant_a"], c["participant_b"]],
                    "item_summary": c["item_summary"],
                    "messages": [
                        {"sender": m["sender_id"], "text": m["text"],
                         "time": str(m["created_at"])[:16]} for m in msgs
                    ]
                }
        except Exception as e:
            print(f"[Supabase] get_conversation error: {e}")
    return next((c for c in CONVERSATIONS if c["id"] == conv_id), None)


def add_message(conv_id, sender_id, text):
    """Add a message to a conversation thread."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            client.table("messages").insert({
                "conversation_id": conv_id,
                "sender_id": sender_id,
                "text": text.strip()
            }).execute()
            return True
        except Exception as e:
            print(f"[Supabase] add_message error: {e}")

    conv = get_conversation(conv_id)
    if conv and text:
        conv["messages"].append({"sender": sender_id, "text": text.strip(),
                                 "time": datetime.now().strftime("%d %b, %I:%M %p")})
        return True
    return False


def other_participant_name(conv, viewer_id):
    """Compute the display name of the other chatter."""
    for pid in conv.get("participants", []):
        if pid != viewer_id:
            u = get_user_by_id(pid)
            return u["name"] if u else conv.get("other_user_name", "Member")
    return conv.get("other_user_name", "Member")


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------
def add_notification(org_id, user_id, ntype, title, body, link_id=None):
    """Create a notification for a user."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            payload = {
                "org_id": org_id,
                "user_id": user_id,
                "type": ntype,
                "title": title,
                "body": body,
                "link_id": link_id,
                "read": False,
            }
            client.table("notifications").insert(payload).execute()
            return
        except Exception as e:
            print(f"[Supabase] add_notification error: {e}")

    NOTIFICATIONS.append({
        "id": next_id("notif"), "org_id": org_id, "user_id": user_id,
        "type": ntype, "title": title, "body": body, "read": False,
        "created_at": datetime.now(), "link_id": link_id,
    })


def get_notifications_for_user(user_id, org_id):
    """Return all notifications for user in reverse chronological order."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("notifications").select("*").eq("user_id", user_id).eq("org_id", org_id).order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"[Supabase] get_notifications_for_user error: {e}")
    return [n for n in NOTIFICATIONS
            if n["user_id"] == user_id and n["org_id"] == org_id]


def unread_notification_count(user_id, org_id):
    """Count unread notifications for a user."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            res = client.table("notifications").select("id", count="exact").eq("user_id", user_id).eq("org_id", org_id).eq("read", False).execute()
            return res.count or 0
        except Exception as e:
            print(f"[Supabase] unread_notification_count error: {e}")
    return sum(1 for n in NOTIFICATIONS
               if n["user_id"] == user_id and n["org_id"] == org_id and not n["read"])


def dismiss_notification(notif_id):
    """Mark a notification as read."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            client.table("notifications").update({"read": True}).eq("id", notif_id).execute()
            return True
        except Exception as e:
            print(f"[Supabase] dismiss_notification error: {e}")
    for n in NOTIFICATIONS:
        if n["id"] == notif_id:
            n["read"] = True
            return True
    return False


# ---------------------------------------------------------------------------
# ADMIN STATS
# ---------------------------------------------------------------------------
def admin_stats(org_id):
    """Compute organization dashboard metrics."""
    if supabase_client.is_supabase_enabled():
        client = supabase_client.get_supabase()
        try:
            users_cnt = client.table("users").select("id", count="exact").eq("org_id", org_id).execute().count or 0
            lost_cnt = client.table("lost_reports").select("id", count="exact").eq("org_id", org_id).execute().count or 0
            found_cnt = client.table("found_reports").select("id", count="exact").eq("org_id", org_id).execute().count or 0
            returned_cnt = client.table("found_reports").select("id", count="exact").eq("org_id", org_id).eq("status", "Returned").execute().count or 0
            matches_cnt = client.table("matches").select("id", count="exact").eq("org_id", org_id).execute().count or 0
            claims_cnt = client.table("matches").select("id", count="exact").eq("org_id", org_id).eq("claim_status", "pending").execute().count or 0
            reported = lost_cnt + returned_cnt
            return {
                "total_users": users_cnt,
                "lost_reports": lost_cnt,
                "found_reports": found_cnt,
                "possible_matches": matches_cnt,
                "successful_returns": returned_cnt,
                "pending_claims": claims_cnt,
                "return_rate": round(returned_cnt / reported * 100) if reported else 0,
            }
        except Exception as e:
            print(f"[Supabase] admin_stats error: {e}")

    lost = org_lost_items(org_id)
    found = org_found_items(org_id)
    returned = [i for i in RETURNED_ITEMS if i["org_id"] == org_id]
    matches = [m for m in MATCHES if m["org_id"] == org_id]
    reported = len(lost) + len(returned)
    return {
        "total_users": len(org_members(org_id)),
        "lost_reports": len(lost),
        "found_reports": len(found),
        "possible_matches": len(matches),
        "successful_returns": len(returned),
        "pending_claims": sum(1 for m in matches if m.get("claim_status") == "pending"),
        "return_rate": round(len(returned) / reported * 100) if reported else 0,
    }
