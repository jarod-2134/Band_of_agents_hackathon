import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create a configured "Session" class
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    # Initialize tables
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
        
    # Check for default user and create if missing
    async with AsyncSessionLocal() as session:
        user = await session.execute(text("SELECT id FROM users LIMIT 1"))
        if not user.scalar():
            await session.execute(text("INSERT INTO users (name, email) VALUES ('System Admin', 'admin@example.com')"))
            await session.commit()
