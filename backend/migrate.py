import asyncio
from sqlalchemy import text
from database import engine

async def migrate():
    async with engine.begin() as conn:
        try:
            # Drop old duplicate vectorized table if it exists
            await conn.execute(text("DROP TABLE IF EXISTS github_commits;"))
            
            # Add missing columns to commits
            await conn.execute(text("ALTER TABLE commits ADD COLUMN IF NOT EXISTS diff TEXT;"))
            await conn.execute(text("ALTER TABLE commits ADD COLUMN IF NOT EXISTS embedding vector(768);"))
            
            # Add missing columns to prs
            await conn.execute(text("ALTER TABLE prs ADD COLUMN IF NOT EXISTS title VARCHAR;"))
            await conn.execute(text("ALTER TABLE prs ADD COLUMN IF NOT EXISTS description TEXT;"))
            await conn.execute(text("ALTER TABLE prs ADD COLUMN IF NOT EXISTS embedding vector(768);"))
            
            # Add missing columns to sprints
            await conn.execute(text("ALTER TABLE sprints ADD COLUMN IF NOT EXISTS name VARCHAR;"))
            await conn.execute(text("ALTER TABLE sprints ADD COLUMN IF NOT EXISTS goal TEXT;"))
            await conn.execute(text("ALTER TABLE sprints ADD COLUMN IF NOT EXISTS embedding vector(768);"))
            
            print("Successfully migrated schemas! Added vectorized columns to commits, prs, and sprints.")
        except Exception as e:
            print(f"Error altering tables: {e}")

asyncio.run(migrate())
