"""
Populate Supabase PostgreSQL database with initial organizations, users, and seed items.
Usage:
    python seed_supabase.py
Requires:
    SUPABASE_URL and SUPABASE_KEY configured in .env
"""
import os
import sys
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

import supabase_client
import image_ai


def seed():
    if not supabase_client.is_supabase_enabled():
        print("[ERROR] SUPABASE_URL and SUPABASE_KEY are not configured in .env")
        print("Please configure .env before running seed_supabase.py.")
        sys.exit(1)

    client = supabase_client.get_supabase()
    print("[Supabase] Connected. Seeding initial data...")

    # 1. Organizations
    org_vsb = {
        "name": "VSB Engineering College",
        "type": "College",
        "email_domain": "vsbec.ac.in",
        "join_code": "VSB2026",
        "collection_desk": "Admin Block, Room 12",
        "contact": "helpdesk@vsbec.ac.in",
        "retention_days": 90,
    }
    org_ngate = {
        "name": "Northgate Tech Park",
        "type": "Workplace",
        "email_domain": "northgate.example",
        "join_code": "NGATE01",
        "collection_desk": "Tower B Reception",
        "contact": "facilities@northgate.example",
        "retention_days": 60,
    }

    res_vsb = client.table("organizations").upsert(org_vsb, on_conflict="join_code").execute()
    vsb_id = res_vsb.data[0]["id"]
    res_ngate = client.table("organizations").upsert(org_ngate, on_conflict="join_code").execute()
    ngate_id = res_ngate.data[0]["id"]
    print(f"  Organizations seeded: {org_vsb['name']} ({vsb_id}), {org_ngate['name']} ({ngate_id})")

    # 2. Users
    users = [
        {"name": "Alex Carter", "email": "demo@vsbec.ac.in", "password": "demo1234", "role": "member", "org_id": vsb_id},
        {"name": "Priya (Front Desk)", "email": "desk@vsbec.ac.in", "password": "desk1234", "role": "staff", "org_id": vsb_id},
        {"name": "Campus Admin", "email": "admin@vsbec.ac.in", "password": "admin1234", "role": "admin", "org_id": vsb_id},
        {"name": "Ravi Menon", "email": "ravi@northgate.example", "password": "ravi1234", "role": "member", "org_id": ngate_id},
    ]
    user_map = {}
    for u in users:
        payload = {
            "name": u["name"],
            "email": u["email"],
            "password_hash": generate_password_hash(u["password"]),
            "role": u["role"],
            "org_id": u["org_id"],
            "avatar": ""
        }
        res_u = client.table("users").upsert(payload, on_conflict="email").execute()
        user_map[u["email"]] = res_u.data[0]["id"]
        print(f"  User seeded: {u['email']} [{u['role']}]")

    # 3. Lost & Found Items with Image Fingerprints
    phone_owner_fp = None
    phone_finder_fp = None
    wallet_finder_fp = None

    p_owner_path = os.path.join("static", "uploads", "seed", "phone_owner.png")
    p_finder_path = os.path.join("static", "uploads", "seed", "phone_finder.png")
    w_finder_path = os.path.join("static", "uploads", "seed", "wallet_finder.png")

    if os.path.exists(p_owner_path):
        phone_owner_fp = image_ai.fingerprint(p_owner_path)
    if os.path.exists(p_finder_path):
        phone_finder_fp = image_ai.fingerprint(p_finder_path)
    if os.path.exists(w_finder_path):
        wallet_finder_fp = image_ai.fingerprint(w_finder_path)

    lost_phone = {
        "org_id": vsb_id,
        "user_id": user_map["demo@vsbec.ac.in"],
        "name": "Black Samsung Galaxy Phone",
        "category": "Mobile Phone",
        "brand": "Samsung",
        "model": "Galaxy S23",
        "color": "Black",
        "location": "College Library reading hall",
        "occurred_on": "2026-09-17",
        "occurred_at": "14:00:00",
        "description": "Black phone with a cracked screen protector.",
        "image_url": "uploads/seed/phone_owner.png",
        "image_fp": phone_owner_fp,
        "status": "Possible Match",
    }
    res_lp = client.table("lost_reports").insert(lost_phone).execute()
    lost_phone_id = res_lp.data[0]["id"]

    found_phone = {
        "org_id": vsb_id,
        "user_id": user_map["desk@vsbec.ac.in"],
        "name": "Black Android Phone",
        "category": "Mobile Phone",
        "brand": "Samsung",
        "model": "Galaxy S23",
        "color": "Black",
        "location": "College Library, 2nd floor",
        "occurred_on": "2026-09-17",
        "occurred_at": "15:10:00",
        "description": "Found near the reading desks, screen locked. Black phone, cracked screen protector.",
        "image_url": "uploads/seed/phone_finder.png",
        "image_fp": phone_finder_fp,
        "status": "Possible Match",
    }
    res_fp = client.table("found_reports").insert(found_phone).execute()
    found_phone_id = res_fp.data[0]["id"]

    found_wallet = {
        "org_id": vsb_id,
        "user_id": user_map["desk@vsbec.ac.in"],
        "name": "Brown Leather Wallet",
        "category": "Wallet",
        "brand": "",
        "model": "",
        "color": "Brown",
        "location": "Cafeteria",
        "occurred_on": "2026-09-15",
        "occurred_at": "12:30:00",
        "description": "Bifold wallet, no cash visible.",
        "image_url": "uploads/seed/wallet_finder.png",
        "image_fp": wallet_finder_fp,
        "status": "Searching",
    }
    client.table("found_reports").insert(found_wallet).execute()

    print("  Seed items inserted successfully.")
    print("\nSupabase seeding complete! Run 'python app.py' to launch GoodFind.")


if __name__ == "__main__":
    seed()
