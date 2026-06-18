import asyncio
import os
import sys
sys.path.insert(0, r'w:\jarod\Band_of_agents_hackathon\backend')
from database import AsyncSessionLocal
from models import EntityNode
from sqlalchemy import select

async def run():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(EntityNode).where(EntityNode.repo_id == '6fd9e7c4-7fcb-4759-9a73-26ac832fd16f'))
        nodes = res.scalars().all()
        for n in nodes:
            if len(n.name) <= 5 and n.name in ['t', 'b', 'btn', 'doc', 'cName']:
                print(n.name, n.node_type)

asyncio.run(run())
