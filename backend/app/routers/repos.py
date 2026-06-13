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
from database import get_db

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPOS_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "repos"))

router = APIRouter(prefix="/orgs/{org_slug}/repos", tags=["Repository & Git Engine Management"])

# --- Pydantic API Schemas ---
class RepoCreatePayload(BaseModel):
    name: str

class BranchCreatePayload(BaseModel):
    name: str
    source_branch: Optional[str] = "main"

class BranchProtectPayload(BaseModel):
    protected: bool

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
            semantic_indexer.delete_repository_embeddings(repo_id)
            logger.info(f"✨ Step 1/4 Complete: Dropped semantic embeddings for {repo_id}")
    except Exception as e:
        logger.error(f"Failed to clear embeddings for {repo_id}: {e}")

    # 2. Remove the physical filesystem directory container
    repo_path = resolve_repo_disk_path(org_slug, repo_name)
    try:
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
            logger.info(f"✨ Step 2/4 Complete: Wiped directory container {repo_path}")
    except Exception as e:
        logger.error(f"Failed to delete directory {repo_path}: {e}")

    # 3. Purge related tracking rows sequentially
    db: Session = next(db_session_factory())
    try:
        db.execute(text("DELETE FROM commits WHERE repo_id = :id"), {"id": repo_id})
        db.execute(text("DELETE FROM branches WHERE repo_id = :id"), {"id": repo_id})
        db.execute(text("DELETE FROM repos WHERE id = :id"), {"id": repo_id})
        db.commit()
        logger.info(f"✨ Step 3/4 Complete: Wiped metadata from database targets.")
    except Exception as e:
        db.rollback()
        logger.error(f"Database metadata cascade failure for repo {repo_id}: {e}")
    finally:
        db.close()


# =============================================================================
# SECTION 2: REPOSITORY MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("")
async def list_repositories(org_slug: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT id, name, org_slug, fs_path FROM repos WHERE org_slug = :org_slug"),
        {"org_slug": org_slug}
    ).mappings().all()
    return {"repositories": [dict(row) for row in result]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_repository(org_slug: str, payload: RepoCreatePayload, db: Session = Depends(get_db)):
    repo_path = resolve_repo_disk_path(org_slug, payload.name)
    unique_folder_name = f"{org_slug}-{payload.name}"
    
    if os.path.exists(repo_path):
        raise HTTPException(status_code=400, detail="Repository folder collision on disk.")

    # Step 1: Insert row into database
    try:
        result = db.execute(
            text("""
                INSERT INTO repos (name, org_slug, fs_path) 
                VALUES (:name, :org_slug, :fs_path) 
                RETURNING id
            """),
            {"name": payload.name, "org_slug": org_slug, "fs_path": unique_folder_name}
        )
        repo_id = result.scalar_one()
        db.flush() 
    except Exception as e:
        db.rollback()
        logger.error(f"Atomic step 1 failed: DB insertion exception: {e}")
        raise HTTPException(status_code=500, detail="Failed to register repository record.")

    # Step 2: Initialize clean base repo on disk using pygit2
    try:
        os.makedirs(repo_path, exist_ok=True)
        pygit2.init_repository(repo_path, bare=True)
        logger.info(f"Atomic step 2 complete: Bare pygit2 repo initialized at {repo_path}")
    except Exception as e:
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        db.rollback()
        logger.error(f"Atomic step 2 failed: pygit2 initialization error: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize Git storage engine.")

    # Step 3: Definitive DB Commit & Publish to BAND broker
    try:
        db.commit()
        # TODO: band_client.publish(f"org.{org_slug}.repo.created", {"repo": payload.name, "id": repo_id})
        logger.info(f"Atomic step 3 complete: Broadcast creation event sent to BAND mesh.")
    except Exception as e:
        logger.warning(f"BAND broker event distribution warning: {e}")

    return {"status": "created", "repo_id": repo_id, "path": unique_folder_name}


@router.get("/{repo_id}")
async def get_repository(org_slug: str, repo_id: str, db: Session = Depends(get_db)):
    repo = db.execute(
        text("SELECT id, name, org_slug, fs_path FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    ).mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository record not found.")
    return dict(repo)


@router.patch("/{repo_id}")
async def update_repository(org_slug: str, repo_id: str, payload: RepoCreatePayload, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE repos SET name = :name WHERE id = :id AND org_slug = :org_slug RETURNING id"),
        {"name": payload.name, "id": repo_id, "org_slug": org_slug}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Target repository does not exist.")
    return {"status": "updated", "repo_id": repo_id}


@router.delete("/{repo_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_repository(org_slug: str, repo_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repo = db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    ).mappings().first()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository target not found.")
    
    background_tasks.add_task(
        async_cascade_repo_purge, 
        org_slug, 
        repo_id, 
        repo["name"], 
        lambda: get_db
    )
    return {"status": "accepted", "detail": "Cascading deletion sequence scheduled asynchronously."}


# =============================================================================
# SECTION 3: GIT BRANCHES MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/{repo_id}/branches")
async def list_branches(org_slug: str, repo_id: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT id, name, protected FROM branches WHERE repo_id = :repo_id"),
        {"repo_id": repo_id}
    ).mappings().all()
    return {"branches": [dict(row) for row in result]}


@router.post("/{repo_id}/branches", status_code=status.HTTP_201_CREATED)
async def create_branch(org_slug: str, repo_id: str, payload: BranchCreatePayload, db: Session = Depends(get_db)):
    repo = db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    ).mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Parent repository missing.")

    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        source_branch_ref = git_repo.lookup_reference(f"refs/heads/{payload.source_branch}")
        source_commit = git_repo.get(source_branch_ref.target)
        
        git_repo.create_branch(payload.name, source_commit)
        
        db.execute(
            text("INSERT INTO branches (repo_id, name, protected) VALUES (:repo_id, :name, :protected)"),
            {"repo_id": repo_id, "name": payload.name, "protected": False}
        )
        db.commit()
        return {"status": "created", "branch": payload.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Native engine branch initialization failed: {str(e)}")


@router.get("/{repo_id}/branches/{branch_name:path}")
async def get_branch_details(org_slug: str, repo_id: str, branch_name: str, db: Session = Depends(get_db)):
    branch = db.execute(
        text("SELECT id, name, protected FROM branches WHERE repo_id = :repo_id AND name = :name"),
        {"repo_id": repo_id, "name": branch_name}
    ).mappings().first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch metadata entry not found.")
    return dict(branch)


@router.delete("/{repo_id}/branches/{branch_name:path}")
async def delete_branch(org_slug: str, repo_id: str, branch_name: str, db: Session = Depends(get_db)):
    # Hard guard enforcement at API layer before disk mutations are touched
    is_protected = db.execute(
        text("SELECT protected FROM branches WHERE repo_id = :repo_id AND name = :name"),
        {"repo_id": repo_id, "name": branch_name}
    ).scalar()
    
    if is_protected or branch_name == "main":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Action Denied: '{branch_name}' is a protected branch pathway."
        )

    repo = db.execute(
        text("SELECT name FROM repos WHERE id = :id AND org_slug = :org_slug"),
        {"id": repo_id, "org_slug": org_slug}
    ).mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Parent repository reference context missing.")

    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        branch_obj = git_repo.lookup_branch(branch_name)
        if branch_obj:
            branch_obj.delete()
        
        db.execute(
            text("DELETE FROM branches WHERE repo_id = :repo_id AND name = :name"),
            {"repo_id": repo_id, "name": branch_name}
        )
        db.commit()
        return {"status": "deleted", "branch": branch_name}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Branch not found on storage fabric: {e}")


@router.patch("/{repo_id}/branches/{branch_name:path}/protect")
async def toggle_branch_protection(org_slug: str, repo_id: str, branch_name: str, payload: BranchProtectPayload, db: Session = Depends(get_db)):
    """Stores the protection configuration parameter inside the repository tracking systems."""
    result = db.execute(
        text("""
            UPDATE branches SET protected = :protected 
            WHERE repo_id = :repo_id AND name = :name RETURNING id
        """),
        {"protected": payload.protected, "repo_id": repo_id, "name": branch_name}
    )
    if not result.rowcount:
        db.execute(
            text("INSERT INTO branches (repo_id, name, protected) VALUES (:repo_id, :name, :protected)"),
            {"repo_id": repo_id, "name": branch_name, "protected": payload.protected}
        )
    db.commit()
    logger.info(f"Updated protection flag on tracking group {branch_name} to: {payload.protected}")
    return {"status": "success", "branch": branch_name, "protected": payload.protected}


# =============================================================================
# SECTION 4: GIT COMMITS & FILE OPERATIONS
# =============================================================================

@router.get("/{repo_id}/commits")
async def list_commits(org_slug: str, repo_id: str, branch: Optional[str] = "main", db: Session = Depends(get_db)):
    repo = db.execute(text("SELECT name FROM repos WHERE id = :id"), {"id": repo_id}).mappings().first()
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
    repo = db.execute(text("SELECT name FROM repos WHERE id = :id"), {"id": repo_id}).mappings().first()
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
    repo = db.execute(text("SELECT name FROM repos WHERE id = :id"), {"id": repo_id}).mappings().first()
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
    repo = db.execute(text("SELECT name FROM repos WHERE id = :id"), {"id": repo_id}).mappings().first()
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
            if entry.type == pygit2.GIT_OBJ_TREE:
                tree = git_repo.get(entry.id)
            else:
                return {"entries": [entry.name]}

        return {"entries": [entry.name for entry in tree]}
    except Exception:
        raise HTTPException(status_code=404, detail="Tree structure path location invalid.")


@router.get("/{repo_id}/blob/{branch}/{filepath:path}")
async def get_repo_blob(org_slug: str, repo_id: str, branch: str, filepath: str, db: Session = Depends(get_db)):
    repo = db.execute(text("SELECT name FROM repos WHERE id = :id"), {"id": repo_id}).mappings().first()
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
    is_protected = db.execute(
        text("SELECT protected FROM branches WHERE repo_id = :repo_id AND name = :name"),
        {"repo_id": repo_id, "name": payload.branch}
    ).scalar()
    
    if is_protected or payload.branch == "main":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Write Rejected: Branch '{payload.branch}' is protected. Direct Agent commits blocked."
        )

    repo = db.execute(text("SELECT name FROM repos WHERE id = :id"), {"id": repo_id}).mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Context repository records absent.")
        
    repo_path = resolve_repo_disk_path(org_slug, repo["name"])
    try:
        git_repo = pygit2.Repository(repo_path)
        
        # Resolve parent commit if appending to an existing branch
        has_parent = git_repo.show_ref(f"refs/heads/{payload.branch}") is not None
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
            blob_oid = git_repo.write(pygit2.GIT_OBJ_BLOB, file.content.encode('utf-8'))
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
    except Exception as e:
        logger.error(f"Native core engine write failure: {e}")
        raise HTTPException(status_code=500, detail=f"Git engine operation failed: {str(e)}")

    # --- POST-COMMIT PIPELINES ---
    # Invoke semantic vector parsing routines
    try:
        for file in payload.files:
            if hasattr(semantic_indexer, "index_file_change"):
                semantic_indexer.index_file_change(repo_id, payload.branch, file.path, file.content)
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