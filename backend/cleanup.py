import asyncio
from database import AsyncSessionLocal
from sqlalchemy import text

async def cleanup():
    async with AsyncSessionLocal() as session:
        repo_id = '1d768da1-bd2b-43bd-a1a4-571b7834d6d7'
        await session.execute(text("DELETE FROM entity_edges WHERE repo_id = :r AND (source_id IN (SELECT id FROM entity_nodes WHERE file_path IN ('math_helper.py', 'main.py')) OR target_id IN (SELECT id FROM entity_nodes WHERE file_path IN ('math_helper.py', 'main.py')))"), {'r': repo_id})
        await session.execute(text("DELETE FROM entity_nodes WHERE repo_id = :r AND file_path IN ('math_helper.py', 'main.py')"), {'r': repo_id})
        await session.commit()
        print('Cleaned up mock data')

asyncio.run(cleanup())
