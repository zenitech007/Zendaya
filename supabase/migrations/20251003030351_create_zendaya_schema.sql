/*
  # Zendaya AI Assistant - Core Database Schema

  ## Overview
  This migration creates the complete database schema for the Zendaya AI Assistant system,
  including user management, conversations, biometric profiles, knowledge base, device registry,
  and system monitoring.

  ## Tables Created

  ### 1. users
  Stores user authentication and profile information
  - `id` (uuid, primary key)
  - `username` (text, unique, indexed)
  - `email` (text, unique, indexed)
  - `full_name` (text)
  - `hashed_password` (text) - bcrypt hashed passwords
  - `is_active` (boolean, default true)
  - `is_superuser` (boolean, default false)
  - `created_at` (timestamptz)
  - `updated_at` (timestamptz)
  - `last_login` (timestamptz)

  ### 2. conversations
  Stores all user-AI interactions with context and metrics
  - `id` (uuid, primary key)
  - `user_id` (uuid, foreign key to users)
  - `message` (text) - user's message
  - `response` (text) - AI's response
  - `context` (jsonb) - conversation context and metadata
  - `timestamp` (timestamptz)
  - `response_time` (numeric) - response time in seconds

  ### 3. biometric_profiles
  Stores biometric data for family member recognition
  - `id` (uuid, primary key)
  - `user_id` (uuid, foreign key to users)
  - `name` (text)
  - `relationship_type` (text) - family, friend, colleague
  - `voice_profile_path` (text) - path to voice embedding
  - `face_encoding_path` (text) - path to face encoding
  - `preferences` (jsonb) - personalization preferences
  - `last_recognized` (timestamptz)
  - `recognition_count` (integer, default 0)
  - `created_at` (timestamptz)

  ### 4. knowledge_entries
  Offline knowledge base for autonomous operation
  - `id` (uuid, primary key)
  - `category` (text, indexed)
  - `question_hash` (text, unique, indexed) - MD5 hash for quick lookup
  - `question` (text)
  - `answer` (text)
  - `confidence` (numeric, default 1.0)
  - `source` (text)
  - `last_used` (timestamptz)
  - `usage_count` (integer, default 0)
  - `created_at` (timestamptz)
  - `updated_at` (timestamptz)

  ### 5. device_registry
  Tracks all devices on the network
  - `id` (uuid, primary key)
  - `ip_address` (text, indexed) - IPv4/IPv6 address
  - `device_type` (text) - smart home, mobile, computer, etc.
  - `device_name` (text)
  - `capabilities` (jsonb) - device capabilities
  - `last_seen` (timestamptz)
  - `is_active` (boolean, default true)
  - `discovery_method` (text)
  - `created_at` (timestamptz)

  ### 6. system_metrics
  System health and performance monitoring
  - `id` (uuid, primary key)
  - `timestamp` (timestamptz, indexed)
  - `cpu_usage` (numeric)
  - `memory_usage` (numeric)
  - `disk_usage` (numeric)
  - `network_status` (boolean, default true)
  - `active_connections` (integer, default 0)

  ## Security
  - All tables have RLS enabled
  - Users can only access their own data
  - Authenticated users required for all operations
  - Superusers have full access for administration

  ## Indexes
  - Username and email for fast user lookups
  - Category and question_hash for knowledge base queries
  - IP address and device type for device management
  - Timestamps for time-series queries
*/

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  username text UNIQUE NOT NULL,
  email text UNIQUE NOT NULL,
  full_name text,
  hashed_password text NOT NULL,
  is_active boolean DEFAULT true NOT NULL,
  is_superuser boolean DEFAULT false NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  last_login timestamptz
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Enable RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- RLS Policies for users
CREATE POLICY "Users can view own profile"
  ON users FOR SELECT
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
  ON users FOR UPDATE
  TO authenticated
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

CREATE POLICY "Superusers have full access"
  ON users FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users 
      WHERE id = auth.uid() AND is_superuser = true
    )
  );

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  message text NOT NULL,
  response text NOT NULL,
  context jsonb,
  timestamp timestamptz DEFAULT now() NOT NULL,
  response_time numeric
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp DESC);

-- Enable RLS
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- RLS Policies for conversations
CREATE POLICY "Users can view own conversations"
  ON conversations FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own conversations"
  ON conversations FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own conversations"
  ON conversations FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);

-- Biometric profiles table
CREATE TABLE IF NOT EXISTS biometric_profiles (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  relationship_type text,
  voice_profile_path text,
  face_encoding_path text,
  preferences jsonb,
  last_recognized timestamptz,
  recognition_count integer DEFAULT 0 NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_biometric_user_id ON biometric_profiles(user_id);

-- Enable RLS
ALTER TABLE biometric_profiles ENABLE ROW LEVEL SECURITY;

-- RLS Policies for biometric profiles
CREATE POLICY "Users can view own biometric profiles"
  ON biometric_profiles FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own biometric profiles"
  ON biometric_profiles FOR ALL
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Knowledge entries table
CREATE TABLE IF NOT EXISTS knowledge_entries (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  category text NOT NULL,
  question_hash text UNIQUE NOT NULL,
  question text NOT NULL,
  answer text NOT NULL,
  confidence numeric DEFAULT 1.0 NOT NULL,
  source text,
  last_used timestamptz,
  usage_count integer DEFAULT 0 NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_entries(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_hash ON knowledge_entries(question_hash);

-- Enable RLS
ALTER TABLE knowledge_entries ENABLE ROW LEVEL SECURITY;

-- RLS Policies for knowledge entries (global knowledge base)
CREATE POLICY "Authenticated users can read knowledge"
  ON knowledge_entries FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Authenticated users can add knowledge"
  ON knowledge_entries FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "Authenticated users can update knowledge"
  ON knowledge_entries FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Device registry table
CREATE TABLE IF NOT EXISTS device_registry (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  ip_address text NOT NULL,
  device_type text NOT NULL,
  device_name text,
  capabilities jsonb,
  last_seen timestamptz DEFAULT now() NOT NULL,
  is_active boolean DEFAULT true NOT NULL,
  discovery_method text,
  created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_device_ip ON device_registry(ip_address);
CREATE INDEX IF NOT EXISTS idx_device_type ON device_registry(device_type);
CREATE INDEX IF NOT EXISTS idx_device_last_seen ON device_registry(last_seen DESC);

-- Enable RLS
ALTER TABLE device_registry ENABLE ROW LEVEL SECURITY;

-- RLS Policies for device registry (shared across authenticated users)
CREATE POLICY "Authenticated users can view devices"
  ON device_registry FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Authenticated users can manage devices"
  ON device_registry FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- System metrics table
CREATE TABLE IF NOT EXISTS system_metrics (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  timestamp timestamptz DEFAULT now() NOT NULL,
  cpu_usage numeric NOT NULL,
  memory_usage numeric NOT NULL,
  disk_usage numeric NOT NULL,
  network_status boolean DEFAULT true NOT NULL,
  active_connections integer DEFAULT 0 NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON system_metrics(timestamp DESC);

-- Enable RLS
ALTER TABLE system_metrics ENABLE ROW LEVEL SECURITY;

-- RLS Policies for system metrics
CREATE POLICY "Authenticated users can view metrics"
  ON system_metrics FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "System can insert metrics"
  ON system_metrics FOR INSERT
  TO authenticated
  WITH CHECK (true);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for users table
CREATE TRIGGER update_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Trigger for knowledge_entries table
CREATE TRIGGER update_knowledge_updated_at
  BEFORE UPDATE ON knowledge_entries
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();