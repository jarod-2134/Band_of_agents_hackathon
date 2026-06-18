import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal, engine, init_db
import models

async def setup():
    async with engine.begin() as conn:
        # Enable the pgvector extension required for vector embeddings
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        
        queries = [
            '''CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR,
                email VARCHAR
            );''',
            '''CREATE TABLE IF NOT EXISTS repos (
                id SERIAL PRIMARY KEY,
                name VARCHAR,
                org_slug VARCHAR,
                fs_path VARCHAR,
                default_branch VARCHAR,
                visibility VARCHAR,
                description TEXT
            );''',
            '''CREATE TABLE IF NOT EXISTS branches (
                id SERIAL PRIMARY KEY,
                repo_id INTEGER,
                name VARCHAR,
                head_sha VARCHAR,
                status VARCHAR,
                protected BOOLEAN,
                created_by INTEGER
            );''',
            '''CREATE TABLE IF NOT EXISTS commits (
                id SERIAL PRIMARY KEY,
                sha VARCHAR UNIQUE,
                org_slug VARCHAR,
                repo_id INTEGER,
                message TEXT,
                author_name VARCHAR,
                author_email VARCHAR,
                branch VARCHAR,
                parent_shas JSONB,
                files_changed INTEGER,
                insertions INTEGER,
                deletions INTEGER,
                committed_at TIMESTAMP
            );''',
            '''CREATE TABLE IF NOT EXISTS prs (
                id SERIAL PRIMARY KEY,
                repo_id INTEGER
            );''',
            '''CREATE TABLE IF NOT EXISTS sprints (
                id SERIAL PRIMARY KEY,
                repo_id INTEGER
            );'''
        ]
        for q in queries:
            await conn.execute(text(q))
            
    # Initialize SQLAlchemy tables defined in models.py (e.g., CodeNode, AgentActionLog, etc.)
    await init_db()
        
    async with AsyncSessionLocal() as session:
        user = await session.execute(text("SELECT id FROM users LIMIT 1"))
        if not user.scalar():
            await session.execute(text("INSERT INTO users (name, email) VALUES ('System Admin', 'admin@example.com')"))
            await session.commit()
        print("Database tables and default user initialized successfully!")

asyncio.run(setup())
