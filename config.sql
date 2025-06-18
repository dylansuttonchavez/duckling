create table access_sessions (
    id uuid primary key default gen_random_uuid(),
    session_id text unique not null,
    used boolean not null default true,
    created_at timestamptz default now()
);
