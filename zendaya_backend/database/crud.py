"""
CRUD Operations for Database Models
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
import json
import hashlib

from zendaya_backend.database.models import User, Conversation, BiometricProfile, SystemMetrics, KnowledgeEntry, DeviceRegistry
from zendaya_backend.core.utils.security_utils import get_password_hash, verify_password

# FIX: Added logger initialization
logger = logging.getLogger(__name__)

class UserCRUD:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user(self, user_id: int) -> Optional[User]:
        return await self.db.get(User, user_id)
    
    @staticmethod
    async def create_user(db: AsyncSession, username: str, email: str, password: str, 
                         full_name: Optional[str] = None, is_superuser: bool = False) -> User:
        """Create a new user"""
        hashed_password = get_password_hash(password)
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            is_superuser=is_superuser
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    
    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """Get user by username"""
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
        """Authenticate user credentials"""
        user = await UserCRUD.get_user_by_username(db, username)
        if not user or not verify_password(password, str(user.hashed_password)):
            return None
        
        # FIX: Use an explicit update statement to avoid Pylance errors
        await db.execute(
            update(User).where(User.id == user.id).values(last_login=datetime.utcnow())
        )
        await db.commit()
        return user
    
    @staticmethod
    async def get_all_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all users with pagination"""
        result = await db.execute(
            select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
        )
        # FIX: Cast Sequence to List to match return type
        return list(result.scalars().all())
    
    @staticmethod
    async def update_user(db: AsyncSession, user_id: str, **kwargs) -> Optional[User]:
        """Update user information"""
        await db.execute(
            update(User).where(User.id == user_id).values(**kwargs)
        )
        await db.commit()
        return await UserCRUD.get_user_by_id(db, user_id)
    
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        """Get user by ID"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def update_last_login(self, user_id: int) -> bool:
        try:
            # FIX: Use explicit update statement
            stmt = update(User).where(User.id == user_id).values(last_login=datetime.utcnow())
            result = await self.db.execute(stmt)
            await self.db.commit()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update last login: {str(e)}")
            await self.db.rollback()
            return False

class ConversationCRUD:
    @staticmethod
    async def create_conversation(db: AsyncSession, user_id: str, message: str, 
                                response: str, context: Optional[Dict] = None,
                                response_time: Optional[float] = None) -> Conversation:
        """Create a new conversation entry"""
        conversation = Conversation(
            user_id=user_id,
            message=message,
            response=response,
            context=json.dumps(context) if context else None,
            response_time=response_time
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation
    
    @staticmethod
    async def get_user_conversations(db: AsyncSession, user_id: str, 
                                   limit: int = 50) -> List[Conversation]:
        """Get user's recent conversations"""
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.timestamp.desc())
            .limit(limit)
        )
        # FIX: Cast Sequence to List to match return type
        return list(result.scalars().all())

class SystemMetricsCRUD:
    @staticmethod
    async def record_metrics(db: AsyncSession, cpu_usage: float, memory_usage: float,
                           disk_usage: float, network_status: bool = True,
                           active_connections: int = 0) -> SystemMetrics:
        """Record system metrics"""
        metrics = SystemMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            network_status=network_status,
            active_connections=active_connections
        )
        db.add(metrics)
        await db.commit()
        await db.refresh(metrics)
        return metrics
    
    @staticmethod
    async def get_recent_metrics(db: AsyncSession, hours: int = 1) -> List[SystemMetrics]:
        """Get metrics from the last N hours"""
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        result = await db.execute(
            select(SystemMetrics)
            .where(SystemMetrics.timestamp >= cutoff_time)
            .order_by(SystemMetrics.timestamp.asc())
        )
        # FIX: Cast Sequence to List to match return type
        return list(result.scalars().all())

class KnowledgeCRUD:
    @staticmethod
    async def store_knowledge(db: AsyncSession, category: str, question: str,
                            answer: str, confidence: float = 1.0,
                            source: Optional[str] = None) -> KnowledgeEntry:
        """Store knowledge entry"""
        question_hash = hashlib.md5(question.lower().encode()).hexdigest()
        
        existing = await db.execute(
            select(KnowledgeEntry).where(KnowledgeEntry.question_hash == question_hash)
        )
        entry = existing.scalar_one_or_none()
        
        if entry:
            # FIX: Use explicit update statement
            stmt = update(KnowledgeEntry).where(KnowledgeEntry.question_hash == question_hash).values(
                answer=answer,
                confidence=confidence,
                updated_at=datetime.utcnow()
            )
            await db.execute(stmt)
        else:
            entry = KnowledgeEntry(
                category=category,
                question_hash=question_hash,
                question=question,
                answer=answer,
                confidence=confidence,
                source=source
            )
            db.add(entry)
        
        await db.commit()
        if entry.id is None: # If it was a new entry, we need to get it again to have the ID
             result = await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.question_hash == question_hash))
             entry = result.scalar_one()
        return entry
    
    @staticmethod
    async def query_knowledge(db: AsyncSession, query: str) -> Optional[KnowledgeEntry]:
        """Query knowledge base"""
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()
        
        result = await db.execute(
            select(KnowledgeEntry).where(KnowledgeEntry.question_hash == query_hash)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            # FIX: Use explicit update statement for usage statistics
            stmt = update(KnowledgeEntry).where(KnowledgeEntry.id == entry.id).values(
                last_used=datetime.utcnow(),
                usage_count=KnowledgeEntry.usage_count + 1
            )
            await db.execute(stmt)
            await db.commit()
        
        return entry
