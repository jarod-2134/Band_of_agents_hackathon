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
            
            # Add missing column to code_nodes
            await conn.execute(text("ALTER TABLE code_nodes ADD COLUMN IF NOT EXISTS repo_id VARCHAR;"))
            await conn.execute(text("ALTER TABLE code_nodes ALTER COLUMN embedding TYPE vector(768);"))
            
            # Add missing column to tasks
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS band_room_id VARCHAR;"))
            
            print("Successfully migrated schemas! Added vectorized columns to commits, prs, and sprints, and band_room_id to tasks.")
        except Exception as e:
            print(f"Error altering tables: {e}")

asyncio.run(migrate())
