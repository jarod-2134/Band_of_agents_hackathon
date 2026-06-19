import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

engine = create_async_engine(os.getenv('DATABASE_URL'))

async def main():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT id, name, fs_path FROM repos"))
        repos = res.fetchall()
        print("Found repos:", repos)
        for repo in repos:
            if 'test' in repo.name.lower() or 'test' in repo.fs_path.lower() or 'demo' in repo.name.lower() or 'demo' in repo.fs_path.lower():
                print("Deleting", repo)
                await conn.execute(text("DELETE FROM repos WHERE id = :id"), {"id": repo.id})
        
if __name__ == "__main__":
    asyncio.run(main())
