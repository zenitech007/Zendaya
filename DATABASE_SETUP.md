# Database Setup Guide - Zendaya AI Assistant

## Overview

Zendaya uses **Supabase PostgreSQL** as its persistent database for user authentication, conversations, device management, and all other data storage needs.

## Database Architecture

### Primary Tables

1. **users** - User accounts with authentication
2. **conversations** - Chat history
3. **biometric_profiles** - Voice and face recognition data
4. **registered_devices** - Cross-platform device registry
5. **device_notifications** - Intelligent notification hub
6. **file_transfers** - File and clipboard sync
7. **routine_patterns** - Learned behavior patterns
8. **project_contexts** - Long-term memory contexts
9. **ambient_events** - Real-world event inference
10. **user_roles** - Role-based permissions
11. **app_integrations** - Third-party app connections
12. **knowledge_entries** - Offline knowledge base
13. **system_metrics** - System monitoring
14. **device_registry** - Smart home devices

### Security Features

- ✅ Row Level Security (RLS) enabled on all tables
- ✅ JWT-based authentication
- ✅ Bcrypt password hashing
- ✅ Secure token-based device authentication
- ✅ User data isolation

## Setup Instructions

### 1. Get Supabase Database Password

You'll need your Supabase database password. You can find or reset it in:
- Supabase Dashboard → Project Settings → Database → Database Password

### 2. Configure Backend Environment

Update `/zendaya-backend/.env` with your database credentials:

```env
# Direct connection for development (lower latency)
DATABASE_URL=postgresql+asyncpg://postgres:[YOUR_PASSWORD]@db.0ec90b57d6e95fcbda19832f.supabase.co:5432/postgres

# Transaction pooler for production (better connection handling)
# DATABASE_URL=postgresql+asyncpg://postgres:[YOUR_PASSWORD]@db.0ec90b57d6e95fcbda19832f.pooler.supabase.com:6543/postgres

# Generate a secure secret key
SECRET_KEY=your-secret-key-here  # Use: openssl rand -hex 32
```

### 3. Install Dependencies

```bash
cd zendaya-backend
poetry install
```

### 4. Test Database Connection

Run the test script to verify everything works:

```bash
cd zendaya-backend
poetry run python test_db_connection.py
```

Expected output:
```
🔄 Testing database connection...
✅ Database connection successful!

🔄 Initializing database tables...
✅ Database tables initialized!

🔄 Testing user CRUD operations...
✅ Test user created successfully!
   - ID: [uuid]
   - Username: testuser
   - Email: test@zendaya.ai

📊 Total users in database: 1
   - testuser (test@zendaya.ai)

✅ All database tests passed!
```

### 5. Start the Backend

```bash
cd zendaya-backend
poetry run python main.py
```

The backend will:
- Connect to Supabase PostgreSQL
- Initialize all required tables (if not exists)
- Start the FastAPI server on http://localhost:8000
- Serve API docs at http://localhost:8000/docs

## Database Connection Modes

### Direct Connection (Development)
- **URL**: `db.0ec90b57d6e95fcbda19832f.supabase.co:5432`
- **Use case**: Local development, lower latency
- **Max connections**: 60 direct connections per project

### Transaction Pooler (Production)
- **URL**: `db.0ec90b57d6e95fcbda19832f.pooler.supabase.com:6543`
- **Use case**: Production, serverless, many concurrent connections
- **Mode**: Transaction mode (one connection per transaction)
- **Benefits**: Better connection pooling, no connection limits

### Session Pooler (Advanced)
- **URL**: `db.0ec90b57d6e95fcbda19832f.pooler.supabase.com:6543`
- **Use case**: When you need session-level features
- **Note**: Set `?pgbouncer=true` parameter

## Authentication Flow

### 1. User Registration
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "secure_password",
    "email": "john@example.com",
    "full_name": "John Doe"
  }'
```

### 2. User Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=john_doe&password=secure_password"
```

Response:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

### 3. Authenticated Requests
```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer eyJhbGc..."
```

## SQLAlchemy Models

All models are defined in `/zendaya-backend/database/models.py`:

### User Model
```python
class User(Base):
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
```

## CRUD Operations

All database operations are in `/zendaya-backend/database/crud.py`:

### UserCRUD
- `create_user(db, username, email, password, full_name)`
- `get_user_by_username(db, username)`
- `get_user_by_email(db, email)`
- `authenticate_user(db, username, password)`
- `get_all_users(db, skip, limit)`
- `update_user(db, user_id, **kwargs)`

### ConversationCRUD
- `create_conversation(db, user_id, message, response, context)`
- `get_user_conversations(db, user_id, limit)`

### SystemMetricsCRUD
- `record_metrics(db, cpu_usage, memory_usage, disk_usage)`
- `get_recent_metrics(db, hours)`

### KnowledgeCRUD
- `store_knowledge(db, category, question, answer, confidence)`
- `query_knowledge(db, query)`

## Troubleshooting

### Connection Error: "could not translate host name"
- Check your database URL is correct
- Verify you're using `postgresql+asyncpg://` prefix
- Ensure your internet connection is active

### Authentication Failed
- Verify your database password is correct
- Check if you're using the right connection URL (direct vs pooler)
- Ensure your IP is not blocked by Supabase

### Table Does Not Exist
- Run `poetry run python test_db_connection.py` to create tables
- Or let the backend auto-create tables on startup
- Check Supabase dashboard to verify tables exist

### SSL/TLS Errors
- Supabase requires SSL connections by default
- asyncpg handles this automatically
- If issues persist, add `?sslmode=require` to connection URL

## Migration Management

While the backend auto-creates tables on startup, for production you should use Alembic migrations:

```bash
# Create a new migration
cd zendaya-backend
poetry run alembic revision --autogenerate -m "Description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1
```

## Monitoring

### View Database Activity
```sql
-- Active connections
SELECT * FROM pg_stat_activity WHERE datname = 'postgres';

-- Table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Health Check
```bash
curl http://localhost:8000/health
```

## Security Best Practices

1. **Never commit** `.env` files with real credentials
2. **Use strong passwords** for database and SECRET_KEY
3. **Rotate secrets** regularly in production
4. **Enable RLS policies** on all tables (already done)
5. **Use transaction pooler** for production deployments
6. **Monitor database connections** to avoid hitting limits
7. **Regular backups** via Supabase dashboard

## Performance Tips

1. **Use indexes** on frequently queried columns (already added)
2. **Limit query results** with pagination
3. **Use connection pooling** (built into asyncpg)
4. **Cache frequently accessed data** with offline intelligence
5. **Monitor slow queries** via Supabase dashboard

## Support

For issues:
1. Check Supabase logs in dashboard
2. Review backend logs for connection errors
3. Verify environment variables are loaded
4. Test connection with `test_db_connection.py`

## Next Steps

Once database is set up:
1. ✅ Register your first user
2. ✅ Test authentication flow
3. ✅ Start building with Zendaya!
4. 🚀 Deploy to production with transaction pooler

---

**Database Status**: ✅ All 14 tables created with RLS policies
**Authentication**: ✅ SQLAlchemy models with bcrypt hashing
**Ready for Production**: ✅ Yes, update SECRET_KEY and use pooler URL
