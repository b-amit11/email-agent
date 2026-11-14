-- Adds a "needs follow-up" flag to drafts.
-- Run this once in the Supabase SQL Editor.

-- True when the reply promises something a person must still do,
-- for example "the team will check your order".
alter table drafts
    add column if not exists needs_follow_up boolean not null default false;

-- One line saying what the person has to do. Empty when nothing is needed.
alter table drafts
    add column if not exists follow_up_note text;
