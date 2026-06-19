import asyncio
import os
import pygit2
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
engine = create_async_engine(os.getenv('DATABASE_URL'))

from app.services.semantic_index import semantic_indexer

async def sync_commits():
    semantic_indexer.load_model()
    async with engine.begin() as conn:
        try:
            repo_proxy = await conn.execute(text("SELECT id, fs_path, org_slug, name FROM repos"))
            repos = repo_proxy.mappings().all()
            if not repos:
                print("No repos in DB!")
                return
            
            for repo_row in repos:
                repo_id = repo_row['id']
                org_slug = repo_row['org_slug']
                repo_name = repo_row['name']
                print(f"Found repo {repo_id}: slug={org_slug}, name={repo_name}")
                
                repo_path = os.path.abspath(os.path.join("W:\\jarod\\Band_of_agents_hackathon\\backend\\repos", f"{org_slug}-{repo_name}"))
                
                print(f"Targeting physical path: {repo_path}")
                if not os.path.exists(repo_path):
                    print(f"Path not found: {repo_path}")
                    continue
                
                git_repo = pygit2.Repository(repo_path)
                head_ref = git_repo.lookup_reference("refs/heads/main")
                head_commit = git_repo.get(head_ref.target)
                head_sha = str(head_commit.id)
                
                res = await conn.execute(text("SELECT sha FROM commits WHERE sha = :sha"), {"sha": head_sha})
                if not res.first():
                    print(f"Commit {head_sha} missing from DB! Inserting...")
                    commit_embedding = semantic_indexer.encode_text(head_commit.message)
                    parent_shas = [str(p.id) for p in head_commit.parents]
                    
                    await conn.execute(
                        text("""
                            INSERT INTO commits (
                                sha, org_slug, repo_id, message, author_name, 
                                author_email, branch, parent_shas, files_changed, 
                                insertions, deletions, committed_at, embedding
                            ) VALUES (
                                :sha, :org_slug, :repo_id, :msg, :author_name, 
                                :author_email, 'main', :parent_shas, 0, 
                                0, 0, :committed_at, :embedding
                            )
                        """),
                        {
                            "org_slug": org_slug,
                            "repo_id": str(repo_id),
                            "sha": head_sha, 
                            "msg": head_commit.message, 
                            "author_name": head_commit.author.name,
                            "author_email": head_commit.author.email,
                            "parent_shas": json.dumps(parent_shas),
                            "committed_at": datetime.now(timezone.utc),
                            "embedding": json.dumps(commit_embedding)
                        }
                    )
                    
                    await conn.execute(
                        text("UPDATE branches SET head_sha = :head_sha WHERE repo_id = :repo_id AND name = 'main'"),
                        {"head_sha": head_sha, "repo_id": str(repo_id)}
                    )
                    print("Successfully backfilled commit and updated branch.")
                else:
                    print(f"Commit {head_sha} is already in the database.")
                
        except Exception as e:
            print("Error:", e)

asyncio.run(sync_commits())
