-- Crear tabla si no existe
create table if not exists access_sessions (
  session_id text primary key,
  expires_at timestamp not null
);

-- Activar seguridad a nivel de fila (RLS)
alter table access_sessions enable row level security;

-- Políticas necesarias (lectura, escritura, borrado público)
create policy "allow all actions"
on access_sessions
for all
using (true)
with check (true);
