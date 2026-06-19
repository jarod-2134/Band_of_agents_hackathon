import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

engine = create_async_engine(os.getenv('DATABASE_URL'))

async def main():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE code_nodes ADD COLUMN branch VARCHAR DEFAULT 'main'"))
            await conn.execute(text("CREATE INDEX ix_code_nodes_branch ON code_nodes (branch)"))
        except Exception as e:
            print(e)
            
        try:
            await conn.execute(text("ALTER TABLE entity_nodes ADD COLUMN branch VARCHAR DEFAULT 'main'"))
            await conn.execute(text("CREATE INDEX ix_entity_nodes_branch ON entity_nodes (branch)"))
        except Exception as e:
            print(e)
            
        try:
            await conn.execute(text("ALTER TABLE entity_edges ADD COLUMN branch VARCHAR DEFAULT 'main'"))
            await conn.execute(text("CREATE INDEX ix_entity_edges_branch ON entity_edges (branch)"))
        except Exception as e:
            print(e)
            
        print("Schema update complete.")

if __name__ == "__main__":
    asyncio.run(main())
