-- Adds the list of fact sheets a draft was answered from.
-- Run this once in the Supabase SQL Editor.

-- The names of the fact sheets the reply's facts came from, for example
-- {02-shipping,03-returns-and-refunds}. An empty list means the reply used
-- none. Drafts written before this column existed have no value here.
alter table drafts
    add column if not exists sources text[];
