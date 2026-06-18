import asyncio
import os
import sys
import pygit2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.semantic_index import semantic_indexer
from database import AsyncSessionLocal
from sqlalchemy import text

async def run():
    semantic_indexer.load_model()
    
    # 1. Clear existing nodes and edges
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM entity_edges"))
        await session.execute(text("DELETE FROM entity_nodes"))
        await session.commit()
        
        # 2. Get mapping of fs_path -> id
        res = await session.execute(text("SELECT id, fs_path FROM repos"))
        repo_mappings = {row['fs_path']: str(row['id']) for row in res.mappings().all()}
        
    print("Repo mappings:", repo_mappings)
        
    repos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'repos')
    
    for fs_path, repo_id in repo_mappings.items():
        repo_path = os.path.join(repos_dir, fs_path)
        if not os.path.exists(repo_path):
            continue
            
        repo = pygit2.Repository(repo_path)
        if repo.is_empty:
            continue
            
        head_commit = repo.get(repo.head.target)
        
        async def walk_tree(tree_obj, path_prefix=""):
            for entry in tree_obj:
                if entry.type == pygit2.GIT_OBJECT_BLOB:
                    blob = repo.get(entry.id)
                    content = blob.data.decode('utf-8', errors='ignore')
                    full_path = os.path.join(path_prefix, entry.name).replace("\\\\", "/")
                    if hasattr(semantic_indexer, "index_file_change"):
                        await semantic_indexer.index_file_change(repo_id, "main", full_path, content)
                elif entry.type == pygit2.GIT_OBJECT_TREE:
                    sub_tree = repo.get(entry.id)
                    await walk_tree(sub_tree, os.path.join(path_prefix, entry.name).replace("\\\\", "/"))
                    
        print(f"Indexing {fs_path} into {repo_id}...")
        await walk_tree(head_commit.tree)
        print(f"Done indexing {fs_path}.")

if __name__ == "__main__":
    asyncio.run(run())
