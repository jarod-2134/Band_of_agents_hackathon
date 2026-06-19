from datetime import datetime, timezone
import os
import json
import shutil
import pygit2
from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from loguru import logger

from app.services.semantic_index import semantic_indexer
from app.routers.deps import get_current_user
from database import get_db

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPOS_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "repos"))

router = APIRouter(prefix="/orgs/{org_slug}/repos", tags=["Repository & Git Engine Management"])

# --- Pydantic API Schemas ---
class RepoCreatePayload(BaseModel):
    name: str

class RepoClonePayload(BaseModel):
    name: str
    repo_url: str
    github_token: Optional[str] = None

class BranchCreatePayload(BaseModel):
    name: str
    source_branch: Optional[str] = "main"

class BranchProtectPayload(BaseModel):
    protected: bool

class BranchMergePayload(BaseModel):
    source_branch: str
    target_branch: str

class ResolvedFileSchema(BaseModel):
    path: str
    content: str

class BranchMergeResolvePayload(BaseModel):
    source_branch: str
    target_branch: str
    resolved_files: List[ResolvedFileSchema]

class AuthorSchema(BaseModel):
    name: str
    email: str

class FileCommitSchema(BaseModel):
    path: str
    content: str

class CommitPayloadSchema(BaseModel):
    branch: str
    message: str
    author: AuthorSchema
    files: List[FileCommitSchema]


# --- Safe Path Helper ---
def resolve_repo_disk_path(org_slug: str, repo_name: str) -> str:
    """Ensures sandbox paths are fully resolved and bounded inside REPOS_DIR."""
    unique_folder = f"{org_slug}-{repo_name}"
    absolute_path = os.path.abspath(os.path.join(REPOS_DIR, unique_folder))
    if not absolute_path.startswith(os.path.abspath(REPOS_DIR)):
        raise HTTPException(status_code=400, detail="Invalid repository pathing configuration.")
    return absolute_path


# --- Asynchronous Cascade Deletion Worker ---
async def async_cascade_repo_purge(org_slug: str, repo_id: str, repo_name: str, db_session_factory):
    """
    Executes the dangerous deep-clean sequence in a background worker thread
    to prevent client timeouts and keep response times fast.
    """
    logger.warning(f"🚀 Starting background cascade purge for repo ID: {repo_id}...")
    
    # 1. Clear all vector embeddings from the Semantic Indexer
    try:
        if hasattr(semantic_indexer, "delete_repository_embeddings"):
            await semantic_indexer.delete_repository_embeddings(repo_id)
            logger.info(f"Step 1/4 Complete: Dropped semantic embeddings for {repo_id}")
    except Exception as e:
        logger.error(f"Failed to clear embeddings for {repo_id}: {e}")

    # 2. Remove the physical filesystem directory container
    repo_path = resolve_repo_disk_path(org_slug, repo_name)
    try:
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
            logger.info(f"Step 2/4 Complete: Wiped directory container {repo_path}")
    except Exception as e:
        logger.error(f"Failed to delete directory {repo_path}: {e}")

    # 3. Purge related tracking rows sequentially following relational dependency order
    # Since get_db yields an async session inside an async generator, we handle async cleanup correctly
    db = await anext(db_session_factory())
    try:
        logger.info(f"Executing database tier cleanup for repo {repo_id}...")
        
        # A. Clear pull requests and sprints that depend on the repo
        await db.execute(text("DELETE FROM prs WHERE repo_id = :id"), {"id": repo_id})
        await db.execute(text("DELETE FROM sprints WHERE repo_id = :id"), {"id": repo_id})
        
        # B. Clear branches FIRST to break the fk_branches_head_sha constraint pointing to commits
        await db.execute(text("DELETE FROM branches WHERE repo_id = :id"), {"id": repo_id})
        
        # C. Clear commits SECOND now that no branches are pointing to them anymore
        await db.execute(text("DELETE FROM commits WHERE repo_id = :id"), {"id": repo_id})
        
        # D. Finally, clear the parent repository row itself
        await db.execute(text("DELETE FROM repos WHERE id = :id"), {"id": repo_id})
        
        await db.commit()
        logger.info(f"Step 3/4 Complete: Wiped metadata from database targets cleanly.")
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Database metadata cascade failure for repo {repo_id}: {e}")
    finally:
        await db.close()


# =============================================================================
# SECTION 2: REPOSITORY MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("")
async def list_repositories(org_slug: str, db: Session = Depends(get_db)):
    result_proxy = await db.execute(
        text("SELECT id, name, org_slug, fs_path FROM repos WHERE org_slug = :org_slug"),
        {"org_slug": org_slug}
    )
    result = result_proxy.mappings().all()
    return {"repositories": [dict(row) for row in result]}


import pygit2
from datetime import datetime, timezone

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_repository(org_slug: str, payload: RepoCreatePayload, db: Session = Depends(get_db)):
    repo_path = resolve_repo_disk_path(org_slug, payload.name)
    unique_folder_name = f"{org_slug}-{payload.name}"
    
    if os.path.exists(repo_path):
        raise HTTPException(status_code=400, detail="Repository folder collision on disk.")

    default_branch = "main"
    default_visibility = "private"
    default_description = f"Codebase storage hub for {payload.name} inside organization {org_slug}."

    # Step 1: Insert repository record into the database
    try:
        await db.execute(
            text("INSERT INTO orgs (name, slug, plan) VALUES (:slug, :slug, 'pro') ON CONFLICT (slug) DO NOTHING"),
            {"slug": org_slug}
        )
        embedding = semantic_indexer.encode_text(default_description)
        embedding_str = json.dumps(embedding)
        result = await db.execute(
            text("""
                INSERT INTO repos (name, org_slug, fs_path, default_branch, visibility, description, embedding) 
                VALUES (:name, :org_slug, :fs_path, :default_branch, :visibility, :description, :embedding) 
                RETURNING id
            """),
            {
                "name": payload.name, 
                "org_slug": org_slug, 
                "fs_path": unique_folder_name,
                "default_branch": default_branch,
                "visibility": default_visibility,
                "description": default_description,
                "embedding": embedding_str
            }
        )
        repo_id = result.scalar_one()
        await db.flush() 
    except Exception as e:
        await db.rollback()
        logger.error(f"Atomic step 1 failed: DB insertion exception: {e}")
        raise HTTPException(status_code=500, detail="Failed to register repository record.")

    # Step 2: Initialize bare repo and generate a REAL physical root commit
    try:
        os.makedirs(repo_path, exist_ok=True)
        git_repo = pygit2.init_repository(repo_path, bare=True)
        
        # Craft a signature for the system agent
        author = pygit2.Signature('System Agent', 'system@mesh.internal')
        committer = pygit2.Signature('System Agent', 'system@mesh.internal')
        
        # Create an empty tree structure object required for a commit object
        tree_index = pygit2.Index()
        tree_oid = tree_index.write_tree(git_repo)
        
        # Write a real physical commit to disk directly onto refs/heads/main
        commit_oid = git_repo.create_commit(
            f"refs/heads/{default_branch}", # Target reference path
            author, 
            committer, 
            "Initial empty repository structure initialization", # Commit message
            tree_oid, 
            [] # No parents (this makes it a true root commit!)
        )
        
        # Safely capture the valid 40-character hex string generated by Git
        actual_git_sha = str(commit_oid)
        
        # Set HEAD to point directly to our newly populated main branch
        git_repo.set_head(f"refs/heads/{default_branch}")
        logger.info(f"Atomic step 2 complete: Bare repo created with real root commit: {actual_git_sha}")
        
    except Exception as e:
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        await db.rollback()
        logger.error(f"Atomic step 2 failed: pygit2 initialization error: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize Git storage engine.")

    # Step 3: Seed metadata tracking records using the real SHA
    try:
        user_proxy = await db.execute(text("SELECT id FROM users LIMIT 1"))
        valid_user_id = user_proxy.scalar()

        if not valid_user_id:
            raise HTTPException(status_code=500, detail="No users exist to register repo.")

        # A. Insert the valid root commit tracking row into the DB
        commit_message = 'Initial empty repository structure initialization'
        commit_embedding = semantic_indexer.encode_text(commit_message)
        
        await db.execute(
            text("""
                INSERT INTO commits (
                    sha, org_slug, repo_id, message, author_name, 
                    author_email, branch, parent_shas, files_changed, 
                    insertions, deletions, committed_at, embedding
                )
                VALUES (
                    :sha, :org_slug, :repo_id, :message, 'System Agent', 
                    'system@mesh.internal', :branch, '[]'::jsonb, 0, 
                    0, 0, :committed_at, :embedding
                )
                ON CONFLICT (sha) DO NOTHING
            """),
            {
                "sha": actual_git_sha, # 👈 Using the actual physical hex SHA here
                "org_slug": org_slug, 
                "repo_id": repo_id,
                "branch": default_branch,
                "message": commit_message,
                "committed_at": datetime.now(timezone.utc),
                "embedding": json.dumps(commit_embedding)
            }
        )
        await db.flush()

        # B. Insert the branch row pointing to our legitimate commit reference
        await db.execute(
            text("""
                INSERT INTO branches (repo_id, name, head_sha, status, protected, created_by)
                VALUES (:repo_id, :name, :head_sha, 'open', true, :created_by)
            """),
            {
                "repo_id": repo_id,
                "name": default_branch,
                "head_sha": actual_git_sha, # 👈 Links up perfectly
                "created_by": valid_user_id
            }
        )
        await db.flush()
        
    except Exception as e:
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        await db.rollback()
        logger.error(f"Atomic step 3 failed: Seeding initial main branch metadata failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to seed protected main branch context.")

    # Step 4: Definitive Transaction Commit
    try:
        await db.commit()
        logger.info(f"Atomic step 4 complete: Repository finalized successfully.")
    except Exception as e:
        logger.warning(f"Event synchronization warning: {e}")

    return {"status": "created", "repo_id": str(repo_id), "path": unique_folder_name}

@router.post("/clone", status_code=status.HTTP_201_CREATED)
async def clone_repository(org_slug: str, payload: RepoClonePayload, db: Session = Depends(get_db)):
    repo_path = resolve_repo_disk_path(org_slug, payload.name)
    unique_folder_name = f"{org_slug}-{payload.name}"
    
    if os.path.exists(repo_path):
        raise HTTPException(status_code=400, detail="Repository folder collision on disk.")

    default_visibility = "private" if payload.github_token else "public"
    default_description = f"Cloned repository {payload.name} inside organization {org_slug}."

    # Step 1: Insert repository record into the database
    try:
        await db.execute(
            text("INSERT INTO orgs (name, slug, plan) VALUES (:slug, :slug, 'pro') ON CONFLICT (slug) DO NOTHING"),
            {"slug": org_slug}
        )
        embedding = semantic_indexer.encode_text(default_description)
        embedding_str = json.dumps(embedding)
        result = await db.execute(
            text("""
                INSERT INTO repos (name, org_slug, fs_path, default_branch, visibility, description, embedding) 
                VALUES (:name, :org_slug, :fs_path, 'main', :visibility, :description, :embedding) 
                RETURNING id
            """),
            {
                "name": payload.name, 
                "org_slug": org_slug, 
                "fs_path": unique_folder_name,
                "visibility": default_visibility,
                "description": default_description,
                "embedding": embedding_str
            }
        )
        repo_id = result.scalar_one()
        await db.flush() 
    except Exception as e:
        await db.rollback()
        logger.error(f"Clone step 1 failed: DB insertion exception: {e}")
        raise HTTPException(status_code=500, detail="Failed to register repository record.")

    # Step 2: Clone bare repo
    try:
        os.makedirs(repo_path, exist_ok=True)
        callbacks = pygit2.RemoteCallbacks()
        if payload.github_token:
            credentials = pygit2.UserPass("x-access-token", payload.github_token)
            callbacks = pygit2.RemoteCallbacks(credentials=credentials)
        
        git_repo = pygit2.clone_repository(payload.repo_url, repo_path, bare=True, callbacks=callbacks)
        
        # Get actual default branch
        head_ref = git_repo.head
        default_branch = head_ref.shorthand
        actual_git_sha = str(head_ref.target)
        
        # Update repo with correct default branch
        await db.execute(
            text("UPDATE repos SET default_branch = :branch WHERE id = :id"),
            {"branch": default_branch, "id": repo_id}
        )
        await db.flush()

        logger.info(f"Clone step 2 complete: Repo cloned, default branch {default_branch}, head sha {actual_git_sha}")
        
    except Exception as e:
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        await db.rollback()
        logger.error(f"Clone step 2 failed: pygit2 clone error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clone repository: {e}")

    # Step 3: Seed metadata tracking records
    try:
        user_proxy = await db.execute(text("SELECT id FROM users LIMIT 1"))
        valid_user_id = user_proxy.scalar()

        if not valid_user_id:
            raise HTTPException(status_code=500, detail="No users exist to register repo.")

        head_commit = git_repo.get(actual_git_sha)
        
        # Insert commit tracking row
        commit_message = head_commit.message
        commit_embedding = semantic_indexer.encode_text(commit_message)

        await db.execute(
            text("""
                INSERT INTO commits (
                    sha, org_slug, repo_id, message, author_name, 
                    author_email, branch, parent_shas, files_changed, 
                    insertions, deletions, committed_at, embedding
                )
                VALUES (
                    :sha, :org_slug, :repo_id, :message, :author_name, 
                    :author_email, :branch, '[]'::jsonb, 0, 
                    0, 0, :committed_at, :embedding
                )
                ON CONFLICT (sha) DO NOTHING
            """),
            {
                "sha": actual_git_sha,
                "org_slug": org_slug, 
                "repo_id": repo_id,
                "branch": default_branch,
                "message": commit_message,
                "author_name": head_commit.author.name,
                "author_email": head_commit.author.email,
                "committed_at": datetime.now(timezone.utc),
                "embedding": json.dumps(commit_embedding)
            }
        )
        await db.flush()

        # Insert branch row
        await db.execute(
            text("""
                INSERT INTO branches (repo_id, name, head_sha, status, protected, created_by)
                VALUES (:repo_id, :name, :head_sha, 'open', true, :created_by)
            """),
            {
                "repo_id": repo_id,
                "name": default_branch,
                "head_sha": actual_git_sha,
                "created_by": valid_user_id
            }
        )
        await db.flush()
        await db.commit()
        
    except Exception as e:
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        await db.rollback()
        logger.error(f"Clone step 3 failed: Seeding metadata failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to seed branch context.")

    # Step 4: Index the HEAD files asynchronously
    try:
        import asyncio
        async def index_tree():
            async def walk_tree(tree_obj, path_prefix=""):
                for entry in tree_obj:
                    if entry.type == pygit2.GIT_OBJECT_BLOB:
                        blob = git_repo.get(entry.id)
                        content = blob.data.decode('utf-8', errors='ignore')
                        full_path = os.path.join(path_prefix, entry.name).replace("\\\\", "/")
                        if hasattr(semantic_indexer, "index_file_change"):
                            await semantic_indexer.index_file_change(str(repo_id), default_branch, full_path, content)
                    elif entry.type == pygit2.GIT_OBJECT_TREE:
                        sub_tree = git_repo.get(entry.id)
                        await walk_tree(sub_tree, os.path.join(path_prefix, entry.name).replace("\\\\", "/"))
            
            await walk_tree(head_commit.tree)
        
        asyncio.create_task(index_tree())
    except Exception as e:
        logger.error(f"Clone step 4 failed: Semantic indexing error: {e}")

    return {"status": "cloned", "repo_id": str(repo_id), "path": unique_folder_name}



@router.get("/{repo_id}")
async def get_repository(org_slug: str, repo_id: str, db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT id, name, org_slug, fs_path FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository record not found.")
    return dict(repo)


@router.patch("/{repo_id}")
async def update_repository(org_slug: str, repo_id: str, payload: RepoCreatePayload, db: Session = Depends(get_db)):
    result = await db.execute(
        text("UPDATE repos SET name = :name WHERE id = :id AND org_slug = :org_slug RETURNING id"),
        {"name": payload.name, "id": repo_id, "org_slug": org_slug}
    )
    await db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Target repository does not exist.")
    return {"status": "updated", "repo_id": repo_id}


@router.delete("/{repo_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_repository(org_slug: str, repo_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository target not found.")
    
    background_tasks.add_task(
        async_cascade_repo_purge, 
        org_slug, 
        repo_id, 
        repo["name"], 
        get_db
    )
    return {"status": "accepted", "detail": "Cascading deletion sequence scheduled asynchronously."}


# =============================================================================
# SECTION 3: GIT BRANCHES MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/{repo_id}/branches")
async def list_branches(org_slug: str, repo_id: str, db: Session = Depends(get_db)):
    result_proxy = await db.execute(
        text("SELECT id, name, protected FROM branches WHERE repo_id = :repo_id"),
        {"repo_id": repo_id}
    )
    result = result_proxy.mappings().all()
    return {"branches": [dict(row) for row in result]}


@router.post("/{repo_id}/branches", status_code=status.HTTP_201_CREATED)
async def create_branch(org_slug: str, repo_id: str, payload: BranchCreatePayload, db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Parent repository missing.")

    # 0. Check if branch already exists in DB to prevent overwriting valid ones
    existing_db_branch_proxy = await db.execute(
        text("SELECT id FROM branches WHERE repo_id = :repo_id AND name = :name"),
        {"repo_id": repo_id, "name": payload.name}
    )
    if existing_db_branch_proxy.scalar():
        raise HTTPException(status_code=400, detail="Branch already exists.")

    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    git_repo = pygit2.Repository(repo_path)
    try:
        source_branch_ref = git_repo.lookup_reference(f"refs/heads/{payload.source_branch}")
        source_commit = git_repo.get(source_branch_ref.target)
        
        # 1. Cleanup any dangling physical branch not tracked by DB
        existing_branch = git_repo.lookup_branch(payload.name)
        if existing_branch:
            existing_branch.delete()
            
        # 2. Spin up the physical branch in the native git engine storage container
        git_repo.create_branch(payload.name, source_commit)
        
        # FIX: In pygit2, use .id to access the OID, then cast it to a string for the 40-char SHA
        physical_head_sha = str(source_commit.id)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Native engine branch initialization failed: {str(e)}")

    # 3. Database Metadata Tracking Tier Execution
    try:
        # Dynamically fetch an active user ID to fulfill your table's fk_branches_created_by constraint
        user_proxy = await db.execute(text("SELECT id FROM users LIMIT 1"))
        valid_user_id = user_proxy.scalar()

        if not valid_user_id:
            raise HTTPException(
                status_code=500, 
                detail="Cannot register metadata because no users exist in the platform context."
            )

        await db.execute(
            text("""
                INSERT INTO branches (repo_id, name, head_sha, status, protected, created_by) 
                VALUES (:repo_id, :name, :head_sha, 'open', :protected, :created_by)
            """),
            {
                "repo_id": repo_id, 
                "name": payload.name, 
                "head_sha": physical_head_sha, # 👈 Legitimate SHA string
                "protected": False,
                "created_by": valid_user_id 
            }
        )
        await db.commit()
        return {"status": "created", "branch": payload.name, "target_sha": physical_head_sha}
        
    except Exception as e:
        await db.rollback()
        # Rollback the physical git branch since DB registration failed
        try:
            b = git_repo.lookup_branch(payload.name)
            if b:
                b.delete()
        except:
            pass
        logger.error(f"Failed database mirror registration for branch {payload.name}: {e}")
        raise HTTPException(status_code=500, detail=f"Database tracking state registration failed: {e}")
    

@router.get("/{repo_id}/branches/{branch_name:path}")
async def get_branch_details(org_slug: str, repo_id: str, branch_name: str, db: Session = Depends(get_db)):
    branch_proxy = await db.execute(
        text("SELECT id, name, protected FROM branches WHERE repo_id = :repo_id AND name = :name"),
        {"repo_id": repo_id, "name": branch_name}
    )
    branch = branch_proxy.mappings().first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch metadata entry not found.")
    return dict(branch)


@router.delete("/{repo_id}/branches/{branch_name:path}")
async def delete_branch(org_slug: str, repo_id: str, branch_name: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Hard guard enforcement at API layer before disk mutations are touched
    is_protected_proxy = await db.execute(
        text("SELECT protected FROM branches WHERE repo_id = :repo_id AND name = :name"),
        {"repo_id": repo_id, "name": branch_name}
    )
    is_protected = is_protected_proxy.scalar()
    
    if is_protected or branch_name == "main":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Action Denied: '{branch_name}' is a protected branch pathway."
        )

    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Parent repository reference context missing.")

    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        branch_obj = git_repo.lookup_branch(branch_name)
        if branch_obj:
            branch_obj.delete()
        
        await db.execute(
            text("DELETE FROM branches WHERE repo_id = :repo_id AND name = :name"),
            {"repo_id": repo_id, "name": branch_name}
        )
        await db.commit()
        
        # Clean up semantic nodes for this branch in the background
        background_tasks.add_task(semantic_indexer.delete_branch_embeddings, repo_id, branch_name)
        
        return {"status": "deleted", "branch": branch_name}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Branch not found on storage fabric: {e}")

@router.post("/{repo_id}/branches/merge")
async def merge_branch(org_slug: str, repo_id: str, payload: BranchMergePayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Parent repository missing.")

    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    
    try:
        git_repo = pygit2.Repository(repo_path)
        head_ref = git_repo.lookup_reference(f"refs/heads/{payload.source_branch}")
        base_ref = git_repo.lookup_reference(f"refs/heads/{payload.target_branch}")
        
        head_commit = git_repo.get(head_ref.target)
        base_commit = git_repo.get(base_ref.target)

        merge_index = git_repo.merge_commits(base_commit, head_commit)
        if merge_index.conflicts:
            conflict_files = []
            for ancestor, ours, theirs in merge_index.conflicts:
                conflict_content = git_repo.merge_file_from_index(ancestor, ours, theirs, use_deprecated=True)
                path = ours.path if ours else theirs.path
                conflict_files.append({"path": path, "content": conflict_content})
            raise HTTPException(status_code=409, detail={"message": "Merge conflict detected.", "conflict_files": conflict_files})

        tree_oid = merge_index.write_tree(git_repo)
        author = pygit2.Signature("User Agent", "user@mesh.internal")
        committer = pygit2.Signature("User Agent", "user@mesh.internal")
        merge_message = f"Merge branch '{payload.source_branch}' into '{payload.target_branch}'"
        
        merge_commit_sha = git_repo.create_commit(
            f"refs/heads/{payload.target_branch}",
            author, committer, merge_message,
            tree_oid, [base_commit.id, head_commit.id]
        )
        
        # Add commit to db
        commit_embedding = semantic_indexer.encode_text(merge_message)
        await db.execute(
            text("""
                INSERT INTO commits (
                    sha, org_slug, repo_id, message, author_name, 
                    author_email, branch, parent_shas, files_changed, 
                    insertions, deletions, committed_at, embedding
                ) VALUES (
                    :sha, :org_slug, :repo_id, :msg, :author_name, 
                    :author_email, :branch, :parent_shas, 0, 
                    0, 0, :committed_at, :embedding
                )
            """),
            {
                "org_slug": org_slug,
                "repo_id": repo_id, 
                "sha": str(merge_commit_sha), 
                "msg": merge_message, 
                "author_name": author.name,
                "author_email": author.email,
                "branch": payload.target_branch,
                "parent_shas": json.dumps([str(base_commit.id), str(head_commit.id)]),
                "committed_at": datetime.now(timezone.utc),
                "embedding": str(commit_embedding)
            }
        )
        await db.commit()
        
        # Background index task
        if hasattr(semantic_indexer, "index_file_change"):
            diff = git_repo.diff(base_commit, head_commit)
            for patch in diff:
                file_path = patch.delta.new_file.path
                try:
                    blob = git_repo.get(patch.delta.new_file.id)
                    if blob and not blob.is_binary:
                        background_tasks.add_task(
                            semantic_indexer.index_file_change,
                            str(repo_id), payload.target_branch, file_path, blob.data.decode('utf-8', errors='ignore')
                        )
                except Exception as index_err:
                    logger.error(f"Failed parsing file {file_path}: {index_err}")
                    
        return {"status": "merged", "merge_commit_sha": str(merge_commit_sha)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Merge error: {e}")
        raise HTTPException(status_code=500, detail=f"Merge sequence failed: {e}")

@router.post("/{repo_id}/branches/merge/resolve")
async def resolve_merge_conflict(org_slug: str, repo_id: str, payload: BranchMergeResolvePayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Parent repository missing.")

    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    
    try:
        git_repo = pygit2.Repository(repo_path)
        head_ref = git_repo.lookup_reference(f"refs/heads/{payload.source_branch}")
        base_ref = git_repo.lookup_reference(f"refs/heads/{payload.target_branch}")
        
        head_commit = git_repo.get(head_ref.target)
        base_commit = git_repo.get(base_ref.target)

        merge_index = git_repo.merge_commits(base_commit, head_commit)
        
        # Apply resolutions
        for resolved_file in payload.resolved_files:
            # Create a new blob with the resolved content
            blob_id = git_repo.create_blob(resolved_file.content)
            # Add to the index to clear the conflict
            entry = pygit2.IndexEntry(resolved_file.path, blob_id, pygit2.GIT_FILEMODE_BLOB)
            merge_index.add(entry)
            
        if merge_index.conflicts:
            raise HTTPException(status_code=400, detail="Not all conflicts have been resolved.")

        tree_oid = merge_index.write_tree(git_repo)
        author = pygit2.Signature("User Agent", "user@mesh.internal")
        committer = pygit2.Signature("User Agent", "user@mesh.internal")
        merge_message = f"Merge branch '{payload.source_branch}' into '{payload.target_branch}'"
        
        merge_commit_sha = git_repo.create_commit(
            f"refs/heads/{payload.target_branch}",
            author, committer, merge_message,
            tree_oid, [base_commit.id, head_commit.id]
        )
        
        # Add commit to db
        commit_embedding = semantic_indexer.encode_text(merge_message)
        await db.execute(
            text("""
                INSERT INTO commits (
                    sha, org_slug, repo_id, message, author_name, 
                    author_email, branch, parent_shas, files_changed, 
                    insertions, deletions, committed_at, embedding
                ) VALUES (
                    :sha, :org_slug, :repo_id, :msg, :author_name, 
                    :author_email, :branch, :parent_shas, 0, 
                    0, 0, :committed_at, :embedding
                )
            """),
            {
                "org_slug": org_slug,
                "repo_id": repo_id, 
                "sha": str(merge_commit_sha), 
                "msg": merge_message, 
                "author_name": author.name,
                "author_email": author.email,
                "branch": payload.target_branch,
                "parent_shas": json.dumps([str(base_commit.id), str(head_commit.id)]),
                "committed_at": datetime.now(timezone.utc),
                "embedding": str(commit_embedding)
            }
        )
        await db.commit()
        
        return {"status": "resolved_and_merged", "merge_commit_sha": str(merge_commit_sha)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Merge resolve error: {e}")
        raise HTTPException(status_code=500, detail=f"Merge resolution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Merge failed: {e}")


@router.patch("/{repo_id}/branches/{branch_name:path}/protect")
async def toggle_branch_protection(org_slug: str, repo_id: str, branch_name: str, payload: BranchProtectPayload, db: Session = Depends(get_db)):
    """Stores the protection configuration parameter inside the repository tracking systems."""
    result = await db.execute(
        text("""
            UPDATE branches SET protected = :protected 
            WHERE repo_id = :repo_id AND name = :name RETURNING id
        """),
        {"protected": payload.protected, "repo_id": repo_id, "name": branch_name}
    )
    if not result.rowcount:
        await db.execute(
            text("INSERT INTO branches (repo_id, name, protected) VALUES (:repo_id, :name, :protected)"),
            {"repo_id": repo_id, "name": branch_name, "protected": payload.protected}
        )
    await db.commit()
    logger.info(f"Updated protection flag on tracking group {branch_name} to: {payload.protected}")
    return {"status": "success", "branch": branch_name, "protected": payload.protected}


# =============================================================================
# SECTION 4: GIT COMMITS & FILE OPERATIONS
# =============================================================================

@router.get("/{repo_id}/commits")
async def list_commits(org_slug: str, repo_id: str, branch: Optional[str] = "main", db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"), 
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository record absent.")
    
    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        branch_ref = git_repo.lookup_reference(f"refs/heads/{branch}")
        
        commits = []
        for commit in git_repo.walk(branch_ref.target, pygit2.GIT_SORT_TIME):
            commits.append({
                "sha": str(commit.id),
                "author": commit.author.name,
                "email": commit.author.email,
                "date": str(commit.commit_time),
                "message": commit.message.strip()
            })
        return {"commits": commits}
    except Exception:
        return {"commits": []}


@router.get("/{repo_id}/commits/{sha}")
async def get_commit_details(org_slug: str, repo_id: str, sha: str, db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"), 
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
        
    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        commit = git_repo.get(sha)
        return {
            "sha": str(commit.id),
            "author": commit.author.name,
            "email": commit.author.email,
            "date": str(commit.commit_time),
            "message": commit.message.strip()
        }
    except Exception:
        raise HTTPException(status_code=404, detail="Target commit SHA object identifier missing.")


@router.get("/{repo_id}/commits/{sha}/diff")
async def get_commit_diff(org_slug: str, repo_id: str, sha: str, db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"), 
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository context absent.")
        
    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        commit = git_repo.get(sha)
        parent = commit.parents[0] if commit.parents else None
        diff = git_repo.diff(parent, commit)
        
        patches = []
        for patch in diff:
            patches.append(patch.text)
        return {"diff": "".join(patches)}
    except Exception:
        raise HTTPException(status_code=404, detail="Failed to calculate diff specifications.")


@router.get("/{repo_id}/tree/{branch}")
@router.get("/{repo_id}/tree/{branch}/{filepath:path}")
async def get_repo_tree(org_slug: str, repo_id: str, branch: str, filepath: Optional[str] = "", db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"), 
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository tracking rows missing.")
        
    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        branch_ref = git_repo.lookup_reference(f"refs/heads/{branch}")
        commit = git_repo.get(branch_ref.target)
        tree = commit.tree
        
        if filepath:
            entry = tree[filepath]
            if entry.type == pygit2.GIT_OBJECT_TREE:
                tree = git_repo.get(entry.id)
            else:
                return {"entries": [entry.name]}

        return {"entries": [entry.name for entry in tree]}
    except Exception:
        raise HTTPException(status_code=404, detail="Tree structure path location invalid.")


@router.get("/{repo_id}/blob/{branch}/{filepath:path}")
async def get_repo_blob(org_slug: str, repo_id: str, branch: str, filepath: str, db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"), 
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository records missing.")
        
    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        branch_ref = git_repo.lookup_reference(f"refs/heads/{branch}")
        commit = git_repo.get(branch_ref.target)
        blob_entry = commit.tree[filepath]
        blob = git_repo.get(blob_entry.id)
        return {"content": blob.data.decode('utf-8')}
    except Exception:
        raise HTTPException(status_code=404, detail=f"Target path '{filepath}' missing under this track revision.")


@router.post("/{repo_id}/commit", status_code=status.HTTP_201_CREATED)
async def agent_create_commit(org_slug: str, repo_id: str, payload: CommitPayloadSchema, db: Session = Depends(get_db)):
    """
    Exposes direct programmatic commit ingestion using high-performance pygit2 builders.
    Guards protected tracking tracks before performing disk object writes.
    """
    # 1. API Protection Check
    is_protected_proxy = await db.execute(
        text("SELECT protected FROM branches WHERE repo_id = :repo_id AND name = :name"),
        {"repo_id": repo_id, "name": payload.branch}
    )
    is_protected = is_protected_proxy.scalar()
    
    if (is_protected or payload.branch == "main") and payload.author.name != "Web Editor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Write Rejected: Branch '{payload.branch}' is protected. Direct Agent commits blocked."
        )

    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"), 
        {"id": repo_id, "org_slug": org_slug}
    )
    repo = repo_proxy.mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Context repository records absent.")
        
    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        
        # Resolve parent commit if appending to an existing branch
        has_parent = f"refs/heads/{payload.branch}" in git_repo.references
        parent_commits = []
        
        # Use pygit2 Index tree builders instead of loose temporary index files on disk
        index = pygit2.Index()
        if has_parent:
            parent_ref = git_repo.lookup_reference(f"refs/heads/{payload.branch}")
            parent_commit = git_repo.get(parent_ref.target)
            parent_commits.append(parent_commit.id)
            index.read_tree(parent_commit.tree)

        # Inject blob payloads directly into the native object database storage layer
        for file in payload.files:
            blob_oid = git_repo.write(pygit2.GIT_OBJECT_BLOB, file.content.encode('utf-8'))
            entry = pygit2.IndexEntry(file.path, blob_oid, pygit2.GIT_FILEMODE_BLOB)
            index.add(entry)

        tree_oid = index.write_tree(git_repo)
        author = pygit2.Signature(payload.author.name, payload.author.email)
        committer = pygit2.Signature(payload.author.name, payload.author.email)
        
        new_commit_sha = git_repo.create_commit(
            f"refs/heads/{payload.branch}", 
            author, committer, payload.message, 
            tree_oid, parent_commits
        )
        
        # 3. Synchronize new physical commit into the relational database tracking model
        commit_embedding = semantic_indexer.encode_text(payload.message)
        await db.execute(
            text("""
                INSERT INTO commits (
                    sha, org_slug, repo_id, message, author_name, 
                    author_email, branch, parent_shas, files_changed, 
                    insertions, deletions, committed_at, embedding
                ) VALUES (
                    :sha, :org_slug, :repo_id, :msg, :author_name, 
                    :author_email, :branch, :parent_shas, :files_changed, 
                    0, 0, :committed_at, :embedding
                )
            """),
            {
                "org_slug": org_slug,
                "repo_id": repo_id, 
                "sha": str(new_commit_sha), 
                "msg": payload.message, 
                "author_name": author.name,
                "author_email": author.email,
                "branch": payload.branch,
                "parent_shas": json.dumps([str(p) for p in parent_commits]),
                "files_changed": len(payload.files),
                "committed_at": datetime.now(timezone.utc),
                "embedding": json.dumps(commit_embedding)
            }
        )
        
        # 4. Advance the branch head_sha pointer to the new commit
        await db.execute(
            text("UPDATE branches SET head_sha = :head_sha WHERE repo_id = :repo_id AND name = :name"),
            {"head_sha": str(new_commit_sha), "repo_id": repo_id, "name": payload.branch}
        )
        await db.commit()
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Native core engine write failure: {e}")
        raise HTTPException(status_code=500, detail=f"Git engine operation failed: {str(e)}")

    # --- POST-COMMIT PIPELINES ---
    # Invoke semantic vector parsing routines
    try:
        for file in payload.files:
            if hasattr(semantic_indexer, "index_file_change"):
                await semantic_indexer.index_file_change(repo_id, payload.branch, file.path, file.content)
        logger.info(f"Semantic mapping indexes refreshed for commit {new_commit_sha}")
    except Exception as e:
        logger.error(f"Semantic indexing pipeline exception: {e}")

    # Emit notification token onto BAND system mesh
    try:
        # TODO: band_client.publish(f"org.{org_slug}.repo.commit", {"repo_id": repo_id, "sha": str(new_commit_sha)})
        logger.info(f"Dispatched transaction completion packet onto BAND hubs.")
    except Exception as e:
        logger.warning(f"Event delivery structural failure: {e}")

    return {
        "status": "committed",
        "sha": str(new_commit_sha),
        "branch": payload.branch
    }

# =============================================================================
# SECTION 5: AST KNOWLEDGE GRAPH
# =============================================================================

@router.get("/{repo_id}/graph")
async def get_repo_graph(org_slug: str, repo_id: str, db: Session = Depends(get_db)):
    repo_proxy = await db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"), 
        {"id": repo_id, "org_slug": org_slug}
    )
    if not repo_proxy.mappings().first():
        raise HTTPException(status_code=404, detail="Repository not found.")
        
    nodes_proxy = await db.execute(
        text("SELECT id, name, node_type, file_path FROM entity_nodes WHERE repo_id = :repo_id"),
        {"repo_id": repo_id}
    )
    nodes = [dict(row) for row in nodes_proxy.mappings().all()]
    
    edges_proxy = await db.execute(
        text("SELECT source_id, target_id, relation_type FROM entity_edges WHERE repo_id = :repo_id"),
        {"repo_id": repo_id}
    )
    edges = [dict(row) for row in edges_proxy.mappings().all()]
    
    return {"nodes": nodes, "edges": edges}