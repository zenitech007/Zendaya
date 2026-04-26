/*
  Add zendaya_sessions and zendaya_messages tables required by the
  React real-time chat (useSupabaseChat / useChatStore).

  Also enables Supabase Realtime on zendaya_messages so postgres_changes
  events are broadcast to subscribed clients.
*/

-- Sessions table
CREATE TABLE IF NOT EXISTS zendaya_sessions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_zendaya_sessions_user ON zendaya_sessions(user_id);

ALTER TABLE zendaya_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own sessions"
  ON zendaya_sessions FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create own sessions"
  ON zendaya_sessions FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- Allow anonymous users (anon role) the same access so signInAnonymously works
CREATE POLICY "Anon can view own sessions"
  ON zendaya_sessions FOR SELECT
  TO anon
  USING (auth.uid() = user_id);

CREATE POLICY "Anon can create own sessions"
  ON zendaya_sessions FOR INSERT
  TO anon
  WITH CHECK (auth.uid() = user_id);

-- Messages table
CREATE TABLE IF NOT EXISTS zendaya_messages (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id uuid NOT NULL REFERENCES zendaya_sessions(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  role text NOT NULL CHECK (role IN ('user', 'ai', 'system')),
  text text NOT NULL,
  meta jsonb,
  created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_zendaya_messages_session ON zendaya_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_zendaya_messages_created ON zendaya_messages(created_at);

ALTER TABLE zendaya_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view messages in own sessions"
  ON zendaya_messages FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM zendaya_sessions s
      WHERE s.id = zendaya_messages.session_id AND s.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert messages in own sessions"
  ON zendaya_messages FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM zendaya_sessions s
      WHERE s.id = zendaya_messages.session_id AND s.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can update messages in own sessions"
  ON zendaya_messages FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM zendaya_sessions s
      WHERE s.id = zendaya_messages.session_id AND s.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can delete messages in own sessions"
  ON zendaya_messages FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM zendaya_sessions s
      WHERE s.id = zendaya_messages.session_id AND s.user_id = auth.uid()
    )
  );

-- Anon policies (for anonymous sign-in)
CREATE POLICY "Anon can view messages in own sessions"
  ON zendaya_messages FOR SELECT
  TO anon
  USING (
    EXISTS (
      SELECT 1 FROM zendaya_sessions s
      WHERE s.id = zendaya_messages.session_id AND s.user_id = auth.uid()
    )
  );

CREATE POLICY "Anon can insert messages in own sessions"
  ON zendaya_messages FOR INSERT
  TO anon
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM zendaya_sessions s
      WHERE s.id = zendaya_messages.session_id AND s.user_id = auth.uid()
    )
  );

-- Enable Supabase Realtime on zendaya_messages so postgres_changes events fire
ALTER publication supabase_realtime ADD TABLE zendaya_messages;
