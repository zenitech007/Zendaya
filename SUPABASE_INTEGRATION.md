# Supabase Integration Guide - Zendaya AI Assistant

## Overview

Zendaya now uses **Supabase** as its primary backend infrastructure, providing:
- ✅ **PostgreSQL Database** - Scalable, production-ready database
- ✅ **Supabase Auth** - Built-in authentication with JWT tokens
- ✅ **Row Level Security** - Automatic data isolation
- ✅ **Real-time subscriptions** - Live data updates
- ✅ **Edge Functions** - Serverless API endpoints

---

## Quick Start

### 1. Environment Configuration

Update your `.env` file with Supabase credentials:

```env
# Frontend Supabase Configuration
VITE_SUPABASE_URL=https://0ec90b57d6e95fcbda19832f.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGc...

# Backend Supabase Configuration
SUPABASE_URL=https://0ec90b57d6e95fcbda19832f.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
SUPABASE_DB_URL=postgresql+asyncpg://postgres:[YOUR_DB_PASSWORD]@db.0ec90b57d6e95fcbda19832f.supabase.co:5432/postgres
```

### 2. Get Your Credentials

**From Supabase Dashboard:**

1. **URL & Keys**: Project Settings → API
   - `SUPABASE_URL`: Project URL
   - `SUPABASE_ANON_KEY`: `anon` `public` key
   - `SUPABASE_SERVICE_ROLE_KEY`: `service_role` `secret` key

2. **Database Password**: Project Settings → Database
   - Click "Reset Database Password" if needed
   - Use this in `SUPABASE_DB_URL`

### 3. Install Dependencies

```bash
cd zendaya-backend
poetry add supabase asyncpg
poetry install
```

### 4. Verify Connection

```bash
cd zendaya-backend
poetry run python test_db_connection.py
```

Expected output:
```
✅ Connected to Supabase PostgreSQL
✅ Database connection test successful
✅ All database tests passed!
```

---

## Architecture

### Database Layer

**Connection Flow:**
```
Zendaya Backend
    ↓
SQLAlchemy (AsyncPG)
    ↓
Supabase PostgreSQL
    ↓
Row Level Security Policies
```

**Key Files:**
- `database/connection.py` - PostgreSQL connection with asyncpg
- `database/models.py` - SQLAlchemy ORM models
- `database/crud.py` - Database operations

**Features:**
- Connection pooling (10 base, 20 overflow)
- Automatic reconnection
- Health check endpoints
- Migration support

### Authentication Layer

**Auth Flow:**
```
User Login Request
    ↓
Supabase Auth (sign_in_with_password)
    ↓
JWT Token Generated
    ↓
Token Verified on Each Request
    ↓
User Data Retrieved from PostgreSQL
```

**Key Files:**
- `core/supabase_auth.py` - Supabase Auth integration
- `core/security.py` - JWT verification & user management

**Features:**
- Email/password authentication
- JWT token management
- Automatic token refresh
- Session management
- User metadata storage

---

## API Changes

### Authentication Endpoints

#### 1. Register (Supabase Auth)

**Endpoint:** `POST /auth/register`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "username": "johndoe",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc..."
}
```

#### 2. Login (Supabase Auth)

**Endpoint:** `POST /auth/login`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "expires_at": 1697654321,
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com"
}
```

#### 3. Token Refresh

**Endpoint:** `POST /auth/refresh`

**Request:**
```json
{
  "refresh_token": "eyJhbGc..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "expires_at": 1697654321
}
```

#### 4. Get Current User

**Endpoint:** `GET /auth/me`

**Headers:**
```
Authorization: Bearer eyJhbGc...
```

**Response:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "johndoe",
  "full_name": "John Doe"
}
```

---

## Database Schema

All tables are created via Supabase migrations (already applied):

### Core Tables

1. **users** - User accounts
   ```sql
   - id (uuid, primary key)
   - username (text, unique)
   - email (text, unique)
   - full_name (text)
   - hashed_password (text)
   - is_active (boolean)
   - created_at (timestamptz)
   ```

2. **conversations** - Chat history
3. **biometric_profiles** - Voice/face recognition
4. **registered_devices** - User devices
5. **device_notifications** - Smart notifications
6. **file_transfers** - Cross-device file sync
7. **routine_patterns** - Learned behaviors
8. **project_contexts** - Long-term memory
9. **ambient_events** - Real-world inference
10. **knowledge_entries** - Offline knowledge
11. **system_metrics** - Performance monitoring
12. **device_registry** - IoT devices
13. **user_roles** - Permissions
14. **app_integrations** - Third-party apps

### Row Level Security

All tables have RLS enabled with policies:

```sql
-- Example: Users can only read their own data
CREATE POLICY "Users can read own data"
  ON users FOR SELECT
  TO authenticated
  USING (auth.uid() = id);
```

---

## Migration from Local DB

### Automatic Migration

The backend automatically syncs users between Supabase Auth and PostgreSQL:

1. User signs up via Supabase Auth
2. JWT token generated by Supabase
3. On first API request, user created in PostgreSQL
4. Future requests use existing PostgreSQL record

### Manual Data Migration

If you have existing data:

```bash
# 1. Export from SQLite
sqlite3 zendaya.db .dump > backup.sql

# 2. Transform to PostgreSQL (fix syntax differences)
# - Change AUTOINCREMENT to SERIAL
# - Update date formats
# - Fix UUID generation

# 3. Import to Supabase
psql "$SUPABASE_DB_URL" < transformed.sql
```

---

## Code Examples

### Python Client

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Register with Supabase Auth
response = requests.post(
    f"{BASE_URL}/auth/register",
    json={
        "email": "user@example.com",
        "password": "SecurePass123!",
        "username": "johndoe",
        "full_name": "John Doe"
    }
)
tokens = response.json()
access_token = tokens["access_token"]

# 2. Make authenticated request
headers = {"Authorization": f"Bearer {access_token}"}
user_response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
print(user_response.json())

# 3. Chat with Zendaya
chat_response = requests.post(
    f"{BASE_URL}/chat",
    headers=headers,
    json={"message": "Hello Zendaya!", "voice_enabled": False}
)
print(chat_response.json())
```

### TypeScript/React Client

```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)

// 1. Sign up
const { data, error } = await supabase.auth.signUp({
  email: 'user@example.com',
  password: 'SecurePass123!',
  options: {
    data: {
      username: 'johndoe',
      full_name: 'John Doe'
    }
  }
})

// 2. Sign in
const { data: session } = await supabase.auth.signInWithPassword({
  email: 'user@example.com',
  password: 'SecurePass123!'
})

// 3. Use token for API calls
const response = await fetch('http://localhost:8000/chat', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${session.session.access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    message: 'Hello Zendaya!',
    voice_enabled: false
  })
})
```

---

## Security Best Practices

### Token Management

1. **Access Tokens** - Short-lived (1 hour)
   - Store in memory or session storage
   - Never store in localStorage permanently

2. **Refresh Tokens** - Long-lived (30 days)
   - Store securely (httpOnly cookies preferred)
   - Use to obtain new access tokens

3. **Service Role Key** - Unlimited access
   - Never expose to frontend
   - Only use in backend
   - Keep in `.env` file

### Database Security

1. **Row Level Security** - Enabled on all tables
2. **Service Role** - Use only when bypassing RLS needed
3. **Prepared Statements** - SQLAlchemy prevents SQL injection
4. **Connection Pooling** - Limited to prevent overload

### API Security

1. **HTTPS Only** - In production
2. **CORS** - Configure allowed origins
3. **Rate Limiting** - Prevent abuse
4. **Input Validation** - Pydantic models

---

## Troubleshooting

### Connection Issues

**Error: "Could not connect to database"**
```bash
# Check database URL format
echo $SUPABASE_DB_URL
# Should be: postgresql+asyncpg://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres

# Test with psql
psql "$SUPABASE_DB_URL" -c "SELECT 1;"
```

**Error: "password authentication failed"**
- Reset database password in Supabase dashboard
- Update `SUPABASE_DB_URL` with new password

### Authentication Issues

**Error: "Invalid JWT token"**
- Token expired (1 hour lifetime)
- Use refresh token to get new access token
- Check token format: `Bearer eyJhbGc...`

**Error: "User not found"**
- User exists in Supabase Auth but not PostgreSQL
- Make authenticated request to trigger auto-creation
- Check RLS policies are correct

### Performance Issues

**Slow queries**
- Add indexes to frequently queried columns
- Use connection pooling (already configured)
- Monitor query performance in Supabase dashboard

**Too many connections**
- Use transaction pooler for serverless: `pooler.supabase.com:6543`
- Reduce pool size in `connection.py`
- Enable statement timeout

---

## Monitoring & Observability

### Supabase Dashboard

Monitor via Supabase Dashboard:
- **Database**: Table stats, query performance
- **Auth**: User signups, login attempts
- **Logs**: Real-time error logs
- **Storage**: File upload metrics

### Backend Logging

```python
# Enable debug logging
DEBUG=true python main.py

# View SQL queries
echo=True in create_async_engine()
```

### Health Checks

**Endpoint:** `GET /health`

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "supabase_auth": "configured"
}
```

---

## Production Deployment

### Environment Variables

```env
# Production settings
DEBUG=false
ALLOWED_ORIGINS=["https://yourdomain.com"]

# Use transaction pooler
SUPABASE_DB_URL=postgresql+asyncpg://postgres:PASSWORD@db.PROJECT.pooler.supabase.com:6543/postgres

# Strong secret key
SECRET_KEY=<generate-with-openssl-rand-hex-32>
```

### Database Optimizations

1. **Indexes** - Already added to migrations
2. **Connection Pooling** - Use pooler in production
3. **Backups** - Automatic via Supabase (Point-in-Time Recovery)

### Security Hardening

1. Enable 2FA for Supabase account
2. Rotate service role key regularly
3. Use environment-specific keys (dev/staging/prod)
4. Monitor auth logs for suspicious activity

---

## Summary

✅ **Database**: Supabase PostgreSQL via asyncpg
✅ **Authentication**: Supabase Auth with JWT
✅ **Security**: Row Level Security on all tables
✅ **Scalability**: Connection pooling + transaction pooler
✅ **Monitoring**: Supabase Dashboard + backend logs

**Production Ready**: Yes
**Breaking Changes**: Auth endpoints use Supabase format
**Migration Required**: Automatic for new users

Zendaya is now powered by Supabase! 🚀
