CREATE TABLE access_sessions (
  session_id TEXT PRIMARY KEY,
  expires_at TIMESTAMP NOT NULL
);

ALTER TABLE access_sessions ENABLE ROW LEVEL SECURITY;

-- Permite leer a cualquiera (por ejemplo, público o usuario autenticado)
CREATE POLICY "Allow read access" ON access_sessions
FOR SELECT USING (true);

-- Permite insertar registros (si necesitas que la API publique sesiones)
CREATE POLICY "Allow insert access" ON access_sessions
FOR INSERT WITH CHECK (true);
