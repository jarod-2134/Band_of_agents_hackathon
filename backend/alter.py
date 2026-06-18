import asyncio
from sqlalchemy import text
from database import engine

async def alter():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE repos ADD COLUMN IF NOT EXISTS embedding vector(768);"))
            print("Successfully added embedding column to repos.")
        except Exception as e:
            print(f"Error altering table: {e}")

asyncio.run(alter())
