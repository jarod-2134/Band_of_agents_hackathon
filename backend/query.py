import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import AsyncSessionLocal
from sqlalchemy import text

async def query():
    async with AsyncSessionLocal() as session:
        res1 = await session.execute(text('SELECT * FROM orgs'))
        print("Orgs:", res1.mappings().all())
        res2 = await session.execute(text('SELECT * FROM org_members'))
        print("Members:", res2.mappings().all())

if __name__ == "__main__":
    asyncio.run(query())
