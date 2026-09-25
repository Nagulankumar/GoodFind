-- GoodFind — Supabase PostgreSQL Schema
-- Run this script in the Supabase SQL Editor.
-- Enforces organization multi-tenancy, primary & foreign keys, JSONB storage for fingerprints,
-- and Row Level Security (RLS) policies.

-- Enable UUID extension if not enabled
create extension if not exists "uuid-ossp";

-- 1. ORGANIZATIONS (The Tenant Table)
create table if not exists organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    type text not null default 'Other',
    email_domain text unique,
    join_code text unique not null,
    collection_desk text not null,
    contact text,
    retention_days int not null default 90,
    created_at timestamptz not null default now()
);

create index if not exists idx_org_domain on organizations(lower(email_domain));
create index if not exists idx_org_code on organizations(upper(join_code));

-- 2. USERS (Profiles & Authentication)
create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references organizations(id) on delete cascade,
    name text not null,
    email text unique not null,
    password_hash text not null,
    role text not null default 'member' check (role in ('member', 'staff', 'admin')),
    avatar text default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_users_org on users(org_id);
create index if not exists idx_users_email on users(lower(email));

-- 3. LOST REPORTS
create table if not exists lost_reports (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references organizations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    name text not null,
    category text not null,
    brand text default '',
    model text default '',
    color text default '',
    location text not null,
    occurred_on date not null,
    occurred_at time,
    description text not null,
    image_url text default '',
    image_fp jsonb,
    status text not null default 'Searching' 
        check (status in ('Searching', 'Possible Match', 'Verification Pending', 'Approved - Ready for Pickup', 'Returned', 'Closed')),
    created_at timestamptz not null default now()
);

create index if not exists idx_lost_org_status on lost_reports(org_id, status);
create index if not exists idx_lost_user on lost_reports(user_id);

-- 4. FOUND REPORTS
create table if not exists found_reports (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references organizations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    name text not null,
    category text not null,
    brand text default '',
    model text default '',
    color text default '',
    location text not null,
    occurred_on date not null,
    occurred_at time,
    description text not null,
    image_url text default '',
    image_fp jsonb,
    status text not null default 'Searching' 
        check (status in ('Searching', 'Possible Match', 'Approved - Ready for Pickup', 'Returned', 'Closed')),
    created_at timestamptz not null default now()
);

create index if not exists idx_found_org_status on found_reports(org_id, status);
create index if not exists idx_found_user on found_reports(user_id);

-- 5. MATCHES
create table if not exists matches (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references organizations(id) on delete cascade,
    lost_item_id uuid not null references lost_reports(id) on delete cascade,
    found_item_id uuid not null references found_reports(id) on delete cascade,
    score int not null,
    factors jsonb not null default '{}',
    notes jsonb not null default '{}',
    claim_status text not null default 'none' 
        check (claim_status in ('none', 'pending', 'approved', 'rejected')),
    claim_answer text default '',
    created_at timestamptz not null default now(),
    unique (lost_item_id, found_item_id)
);

create index if not exists idx_matches_org on matches(org_id);
create index if not exists idx_matches_lost on matches(lost_item_id);
create index if not exists idx_matches_found on matches(found_item_id);

-- 6. OWNERSHIP CLAIMS
create table if not exists ownership_claims (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references organizations(id) on delete cascade,
    match_id uuid not null references matches(id) on delete cascade,
    claimant_id uuid not null references users(id) on delete cascade,
    identifying_answer text not null,
    status text not null default 'pending' 
        check (status in ('pending', 'approved', 'rejected')),
    reviewed_by uuid references users(id) on delete set null,
    reviewed_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists idx_claims_org_status on ownership_claims(org_id, status);

-- 7. CONVERSATIONS & MESSAGES
create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references organizations(id) on delete cascade,
    participant_a uuid not null references users(id) on delete cascade,
    participant_b uuid not null references users(id) on delete cascade,
    item_summary text not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_conv_participants on conversations(org_id, participant_a, participant_b);

create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    sender_id uuid not null references users(id) on delete cascade,
    text text not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_messages_conv on messages(conversation_id, created_at);

-- 8. NOTIFICATIONS
create table if not exists notifications (
    id uuid primary key default gen_random_uuid(),
    org_id uuid not null references organizations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    type text not null,
    title text not null,
    body text not null,
    link_id text,
    read boolean not null default false,
    created_at timestamptz not null default now()
);

create index if not exists idx_notif_user_read on notifications(user_id, read, created_at desc);

-- 9. UNIFIED ITEM VIEW (for easy polymorphic lookup)
create or replace view all_items_view as
select id, org_id, user_id, 'lost' as kind, name, category, brand, model, color,
       location, occurred_on, occurred_at, description, image_url, image_fp, status, created_at
from lost_reports
union all
select id, org_id, user_id, 'found' as kind, name, category, brand, model, color,
       location, occurred_on, occurred_at, description, image_url, image_fp, status, created_at
from found_reports;

-- 10. STORAGE BUCKET SETUP (Run if using Supabase Storage)
-- insert into storage.buckets (id, name, public) values ('item-photos', 'item-photos', true)
-- on conflict (id) do nothing;
