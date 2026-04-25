# 🚀 Quick Start - Supabase Integration

Get Zendaya AI Assistant running with Supabase in 5 minutes!

---

## Step 1: Get Supabase Credentials (2 min)

### Create Project
1. Go to https://supabase.com
2. Click "New Project"
3. Wait for project to initialize (~2 minutes)

### Get Credentials
1. **Project Settings** → **API**
   - Copy **Project URL** → This is your `SUPABASE_URL`
   - Copy **anon public** key → This is your `SUPABASE_ANON_KEY`
   - Copy **service_role secret** → This is your `SUPABASE_SERVICE_ROLE_KEY`

2. **Project Settings** → **Database**
   - Copy or reset **Database Password** → Use in next step

---

## Step 2: Configure Environment (1 min)

### Root `.env` File
```bash
# Copy template
cp .env.example .env
```

### Add to `.env`:
```env
# Supabase Configuration
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_DB_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres

# Frontend (same values)
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Security
SECRET_KEY=your-secret-key-here
```

**Generate SECRET_KEY:**
```bash
openssl rand -hex 32
```

---

## Step 3: Install Dependencies (1 min)

### Backend
```bash
cd zendaya-backend
poetry add supabase asyncpg
poetry install
```

### Frontend
```bash
npm install
```

---

## Step 4: Test Connection (30 sec)

```bash
cd zendaya-backend
poetry run python test_db_connection.py
```

**Expected:**
```
✅ Connected to Supabase PostgreSQL
✅ Database connection test successful
✅ All database tests passed!
```

---

## Step 5: Start Services (30 sec)

### Terminal 1 - Backend
```bash
cd zendaya-backend
poetry run python main.py
```

**Expected:**
```
✅ Supabase Auth client initialized
✅ Connected to Supabase PostgreSQL
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2 - Frontend
```bash
npm run dev
```

**Expected:**
```
VITE v5.4.8  ready in XXX ms
➜  Local:   http://localhost:5173/
```

---

## Step 6: Test Authentication (1 min)

### Option A: Using cURL

**Register:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!",
    "username": "testuser"
  }'
```

**Login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!"
  }'
```

Save the `access_token` from response.

**Get User:**
```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Option B: Using Web Dashboard

1. Open http://localhost:5173
2. Click "Register"
3. Fill in email, password, username
4. Login with credentials
5. You're in!

---

## ✅ Success Checklist

- [ ] Supabase project created
- [ ] Environment variables configured
- [ ] Dependencies installed
- [ ] Database connection test passes
- [ ] Backend starts without errors
- [ ] Frontend accessible at localhost:5173
- [ ] User registration works
- [ ] User login works
- [ ] Protected endpoints return user data

---

## 🐛 Troubleshooting

### "Could not connect to database"
```bash
# Check your SUPABASE_DB_URL format
echo $SUPABASE_DB_URL
# Should be: postgresql+asyncpg://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

### "Authentication failed"
- Check `SUPABASE_URL` and `SUPABASE_ANON_KEY` are correct
- Verify credentials in Supabase Dashboard → API

### "Module not found: supabase"
```bash
cd zendaya-backend
poetry add supabase asyncpg
poetry install
```

---

## 🎯 Next Steps

Now that Supabase is working:

1. **Configure AI Services** (optional)
   ```env
   GEMINI_API_KEY=your-key
   ELEVENLABS_API_KEY=your-key
   ```

2. **Read Full Documentation**
   - `SUPABASE_INTEGRATION.md` - Complete guide
   - `DATABASE_SETUP.md` - Database details
   - `AUTH_USAGE_GUIDE.md` - Auth API reference

3. **Deploy to Production**
   - Use transaction pooler: `pooler.supabase.com:6543`
   - Enable HTTPS
   - Configure CORS
   - Set up monitoring

---

## 📚 Useful Commands

```bash
# Test database
poetry run python test_db_connection.py

# Start backend
cd zendaya-backend && poetry run python main.py

# Start frontend
npm run dev

# Build frontend
npm run build

# Run tests
cd zendaya-backend && poetry run pytest

# Check logs
tail -f zendaya-backend/logs/app.log
```

---

## 🆘 Need Help?

1. Check logs in terminal
2. Review `SUPABASE_INTEGRATION.md`
3. Check Supabase Dashboard → Logs
4. Verify environment variables are loaded

---

## 🎊 You're Ready!

Zendaya AI Assistant is now running on Supabase with:
- ✅ Cloud PostgreSQL database
- ✅ Built-in authentication
- ✅ Row Level Security
- ✅ Automatic backups
- ✅ Production-ready infrastructure

**Total Time: ~5 minutes** ⚡

Start chatting with Zendaya! 🤖
