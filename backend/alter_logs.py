import asyncio
from sqlalchemy import text
from database import engine

async def alter():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE agent_action_logs ADD COLUMN IF NOT EXISTS org_slug VARCHAR;"))
            await conn.execute(text("ALTER TABLE agent_action_logs ADD COLUMN IF NOT EXISTS repo_id VARCHAR;"))
            await conn.execute(text("ALTER TABLE agent_action_logs ADD COLUMN IF NOT EXISTS agent_role VARCHAR;"))
            print("Successfully added org_slug, repo_id, and agent_role to agent_action_logs.")
        except Exception as e:
            print(f"Error altering table: {e}")

asyncio.run(alter())
