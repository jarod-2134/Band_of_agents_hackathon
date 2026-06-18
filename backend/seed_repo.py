import asyncio
import os
from app.services.semantic_index import semantic_indexer
from database import AsyncSessionLocal
from database import init_db

async def seed():
    await init_db()
    repo_id = "1d768da1-bd2b-43bd-a1a4-571b7834d6d7"
    repo_path = f"repos/{repo_id}"
    
    # Create some fake code
    code1 = """
class MathHelper:
    def add(self, a, b):
        return a + b
        
    def subtract(self, a, b):
        return a - b
"""
    code2 = """
from math_helper import MathHelper

def main():
    helper = MathHelper()
    print(helper.add(5, 3))

if __name__ == '__main__':
    main()
"""
    with open(os.path.join(repo_path, "math_helper.py"), "w") as f:
        f.write(code1)
    with open(os.path.join(repo_path, "main.py"), "w") as f:
        f.write(code2)
        
    semantic_indexer.load_model()
    # Index them
    await semantic_indexer.index_file_change(repo_id, "main", "math_helper.py", code1)
    await semantic_indexer.index_file_change(repo_id, "main", "main.py", code2)
    print("Seeded successfully!")

asyncio.run(seed())
