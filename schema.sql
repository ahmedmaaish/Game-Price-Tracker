-- Run this once in the Supabase SQL editor:
-- Dashboard -> SQL Editor -> New query -> paste -> Run.

create table if not exists games (
    id            bigint primary key,           -- CheapShark gameID
    title         text not null,
    thumb         text,
    steam_app_id  text,
    cheapest_ever numeric(10, 2),
    updated_at    timestamptz not null default now()
);

create table if not exists price_history (
    id          bigserial primary key,
    game_id     bigint not null references games(id),
    price       numeric(10, 2) not null,
    store_id    text,
    deal_id     text,
    recorded_at date not null default current_date,
    unique (game_id, recorded_at)
);

create index if not exists idx_price_history_game
    on price_history (game_id, recorded_at);
