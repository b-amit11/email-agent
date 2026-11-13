-- First database tables: incoming emails and the AI-written reply drafts.
-- Run this once in the Supabase SQL Editor.

-- Every customer email we pull in from Gmail.
create table if not exists emails (
    id                uuid primary key default gen_random_uuid(),
    gmail_message_id  text not null unique,
    gmail_thread_id   text,
    from_address      text not null,
    from_name         text,
    subject           text,
    body              text,
    received_at       timestamptz,
    status            text not null default 'new'
                      check (status in ('new', 'drafted', 'sent', 'ignored')),
    created_at        timestamptz not null default now()
);

-- Every reply the AI writes, waiting for a human to review it.
create table if not exists drafts (
    id           uuid primary key default gen_random_uuid(),
    email_id     uuid not null references emails (id) on delete cascade,
    body         text not null,
    final_body   text,
    model        text,
    status       text not null default 'pending'
                 check (status in ('pending', 'approved', 'rejected', 'sent')),
    created_at   timestamptz not null default now(),
    reviewed_at  timestamptz,
    sent_at      timestamptz
);

create index if not exists emails_status_idx on emails (status);
create index if not exists drafts_email_id_idx on drafts (email_id);
create index if not exists drafts_status_idx on drafts (status);

-- Lock both tables: only the backend's secret key can read or write them.
alter table emails enable row level security;
alter table drafts enable row level security;
