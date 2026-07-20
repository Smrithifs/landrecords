"""
Database connection management.
Handles PostgreSQL connection and session management.
"""

from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from contextlib import asynccontextmanager
import asyncio

from .models import Base


class DatabaseConnection:
    """Manages database connection and sessions."""
    
    def __init__(self, config: dict):
        """
        Initialize database connection.
        
        Args:
            config: Configuration dictionary containing database settings
        """
        self.config = config
        self.db_host = config.get('db_host', 'localhost')
        self.db_port = config.get('db_port', 5432)
        self.db_name = config.get('db_name', 'land_records')
        self.db_user = config.get('db_user', 'postgres')
        self.db_password = config.get('db_password', '')
        self.pool_size = config.get('pool_size', 10)
        self.max_overflow = config.get('max_overflow', 20)
        
        self.engine = None
        self.async_session_maker = None
    
    def get_database_url(self) -> str:
        """
        Construct database URL from configuration.
        
        Returns:
            Database connection URL
        """
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    async def connect(self) -> None:
        """Establish database connection and create engine."""
        try:
            database_url = self.get_database_url()
            
            self.engine = create_async_engine(
                database_url,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                echo=self.config.get('echo_sql', False)
            )
            
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            print("Database connection established successfully")
            
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            print("Database connection closed")
    
    async def create_tables(self) -> None:
        """Create all database tables."""
        if not self.engine:
            await self.connect()
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("Database tables created successfully")
    
    async def drop_tables(self) -> None:
        """Drop all database tables."""
        if not self.engine:
            await self.connect()
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        print("Database tables dropped successfully")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session context manager.
        
        Yields:
            AsyncSession instance
        """
        if not self.async_session_maker:
            await self.connect()
        
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> bool:
        """
        Check database connection health.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"Database health check failed: {e}")
            return False


# Global database connection instance
db_connection: Optional[DatabaseConnection] = None


async def get_database() -> DatabaseConnection:
    """
    Get or create global database connection instance.
    
    Returns:
        DatabaseConnection instance
    """
    global db_connection
    if db_connection is None:
        from config.settings import get_settings
        settings = get_settings()
        db_connection = DatabaseConnection(settings.DATABASE)
        await db_connection.connect()
    return db_connection


async def close_database() -> None:
    """Close global database connection."""
    global db_connection
    if db_connection:
        await db_connection.disconnect()
        db_connection = None
