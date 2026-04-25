"""
Test Database Connection and User Creation
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_connection():
    """Test Supabase PostgreSQL connection"""
    try:
        from database.connection import engine, init_db
        from database.crud import UserCRUD
        from database.connection import AsyncSessionLocal

        print("🔄 Testing database connection...")

        # Test connection
        async with engine.connect() as conn:
            print("✅ Database connection successful!")

        # Initialize tables (if needed)
        print("\n🔄 Initializing database tables...")
        await init_db()
        print("✅ Database tables initialized!")

        # Test user creation
        print("\n🔄 Testing user CRUD operations...")
        async with AsyncSessionLocal() as db:
            # Check if test user exists
            existing_user = await UserCRUD.get_user_by_username(db, "testuser")

            if existing_user:
                print(f"✅ Test user already exists: {existing_user.username}")
            else:
                # Create test user
                test_user = await UserCRUD.create_user(
                    db=db,
                    username="testuser",
                    email="test@zendaya.ai",
                    password="testpassword123",
                    full_name="Test User"
                )
                print(f"✅ Test user created successfully!")
                print(f"   - ID: {test_user.id}")
                print(f"   - Username: {test_user.username}")
                print(f"   - Email: {test_user.email}")

            # List all users
            all_users = await UserCRUD.get_all_users(db, limit=10)
            print(f"\n📊 Total users in database: {len(all_users)}")
            for user in all_users:
                print(f"   - {user.username} ({user.email})")

        print("\n✅ All database tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)