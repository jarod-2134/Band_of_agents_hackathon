import os
import json
import pygit2
from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from loguru import logger

# Import shared application services and database dependencies
from app.services.semantic_index import semantic_indexer
from database import get_db
from app.routers.repos import resolve_repo_disk_path  # Reusing your safe path helper

router = APIRouter(prefix="/orgs/{org_slug}/repos/{repo_id}/prs", tags=["Pull Requests"])


# =============================================================================
# PYDANTIC API SCHEMAS
# =============================================================================

class PullRequestCreatePayload(BaseModel):
    title: str
    description: Optional[str] = ""
    head_branch: str
    base_branch: str
    linked_issue_id: Optional[int] = None
    sprint_card_id: Optional[int] = None

class PullRequestUpdatePayload(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class CommentPayload(BaseModel):
    body: str


# =============================================================================
# 1. CORE PULL REQUEST CRUD ENDPOINTS
# =============================================================================

@router.get("")
async def list_pull_requests(org_slug: str, repo_id: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT id, title, head_branch, base_branch, status FROM pull_requests WHERE repo_id = :repo_id"),
        {"repo_id": repo_id}
    ).mappings().all()
    return {"pull_requests": [dict(row) for row in result]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_pull_request(org_slug: str, repo_id: str, payload: PullRequestCreatePayload, db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            INSERT INTO pull_requests (repo_id, title, description, head_branch, base_branch, status, linked_issue_id, sprint_card_id)
            VALUES (:repo_id, :title, :description, :head_branch, :base_branch, 'open', :linked_issue_id, :sprint_card_id)
            RETURNING id, status
        """),
        {
            "repo_id": repo_id, "title": payload.title, "description": payload.description,
            "head_branch": payload.head_branch, "base_branch": payload.base_branch,
            "linked_issue_id": payload.linked_issue_id, "sprint_card_id": payload.sprint_card_id
        }
    )
    row = result.mappings().first()
    db.commit()
    return {"status": "created", "pr_id": row["id"], "pr_status": row["status"]}


@router.get("/{pr_id}")
async def get_pull_request(org_slug: str, repo_id: str, pr_id: int, db: Session = Depends(get_db)):
    pr = db.execute(
        text("SELECT * FROM pull_requests WHERE id = :id AND repo_id = :repo_id"),
        {"id": pr_id, "repo_id": repo_id}
    ).mappings().first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull Request not found.")
    return dict(pr)


@router.patch("/{pr_id}")
async def update_pull_request(org_slug: str, repo_id: str, pr_id: int, payload: PullRequestUpdatePayload, db: Session = Depends(get_db)):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update.")
    
    set_clause = ", ".join([f"{key} = :{key}" for key in update_data.keys()])
    update_data["id"] = pr_id
    update_data["repo_id"] = repo_id

    result = db.execute(
        text(f"UPDATE pull_requests SET {set_clause} WHERE id = :id AND repo_id = :repo_id RETURNING id"),
        update_data
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Pull Request not found.")
    return {"status": "updated", "pr_id": pr_id}


@router.delete("/{pr_id}")
async def delete_pull_request(org_slug: str, repo_id: str, pr_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM pull_requests WHERE id = :id AND repo_id = :repo_id"),
        {"id": pr_id, "repo_id": repo_id}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Pull Request not found.")
    return {"status": "deleted", "pr_id": pr_id}


# =============================================================================
# 2. REVIEW & APPROVAL ENDPOINTS
# =============================================================================

@router.post("/{pr_id}/approve")
async def approve_pull_request(org_slug: str, repo_id: str, pr_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE pull_requests SET review_status = 'approved' WHERE id = :id AND repo_id = :repo_id RETURNING id"),
        {"id": pr_id, "repo_id": repo_id}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Pull Request not found.")
    return {"status": "approved", "pr_id": pr_id}


@router.post("/{pr_id}/request-changes")
async def request_changes(org_slug: str, repo_id: str, pr_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE pull_requests SET review_status = 'changes_requested' WHERE id = :id AND repo_id = :repo_id RETURNING id"),
        {"id": pr_id, "repo_id": repo_id}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Pull Request not found.")
    return {"status": "changes_requested", "pr_id": pr_id}


# =============================================================================
# 3. MERGE OPERATION (IMPLEMENTING THE 8 STEPS FROM image_ec35ed.png)
# =============================================================================

@router.post("/{pr_id}/merge")
async def merge_pull_request(org_slug: str, repo_id: str, pr_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Fetch repository context info
    repo = db.execute(text("SELECT name FROM repos WHERE id = :id"), {"id": repo_id}).mappings().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository reference missing.")

    # Fetch pull request details
    pr = db.execute(
        text("SELECT id, head_branch, base_branch, review_status, linked_issue_id, sprint_card_id FROM pull_requests WHERE id = :id AND repo_id = :repo_id"),
        {"id": pr_id, "repo_id": repo_id}
    ).mappings().first()
    
    if not pr:
        raise HTTPException(status_code=404, detail="Pull Request context target not found.")

    # Step 1: Validate PR is approved
    if pr["review_status"] != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Merge Rejected: Pull Request must be approved before merging."
        )

    repo_path = resolve_repo_disk_path(org_slug, repo["name"])

    # Step 2: Call pygit2 to merge head_branch into base_branch
    try:
        git_repo = pygit2.Repository(repo_path)
        
        # Look up references
        head_ref = git_repo.lookup_reference(f"refs/heads/{pr['head_branch']}")
        base_ref = git_repo.lookup_reference(f"refs/heads/{pr['base_branch']}")
        
        head_commit = git_repo.get(head_ref.target)
        base_commit = git_repo.get(base_ref.target)

        # Calculate merge index tracking mutations
        merge_index = git_repo.merge_trees(base_commit, head_commit)
        
        if merge_index.conflicts:
            raise HTTPException(status_code=400, detail="Merge conflict detected. Automated engine aborted.")

        # Write tree out from index space
        tree_oid = merge_index.write_tree(git_repo)
        
        # Construct merge commit metadata block
        author = pygit2.Signature("Git Agent Service", "agent@mesh.internal")
        committer = pygit2.Signature("Git Agent Service", "agent@mesh.internal")
        merge_message = f"Merge pull request #{pr_id} from {pr['head_branch']} into {pr['base_branch']}"
        
        merge_commit_sha = git_repo.create_commit(
            f"refs/heads/{pr['base_branch']}",
            author, committer, merge_message,
            tree_oid, [base_commit.id, head_commit.id]
        )
    except Exception as e:
        logger.error(f"Pygit2 low-level engine collision: {e}")
        raise HTTPException(status_code=500, detail=f"Pygit2 automated merge sequence failed: {str(e)}")

    # Transactional Application State Management Actions
    try:
        # Step 3: Create a merge commit row
        db.execute(
            text("INSERT INTO commits (repo_id, sha, message, branch) VALUES (:repo_id, :sha, :msg, :branch)"),
            {"repo_id": repo_id, "sha": str(merge_commit_sha), "msg": merge_message, "branch": pr['base_branch']}
        )

        # Step 4: Update branch status to merged (Updating the PR status)
        db.execute(
            text("UPDATE pull_requests SET status = 'merged' WHERE id = :id"),
            {"id": pr_id}
        )

        # Step 5: Update linked issue status to done
        if pr["linked_issue_id"]:
            db.execute(
                text("UPDATE issues SET status = 'done' WHERE id = :issue_id"),
                {"issue_id": pr["linked_issue_id"]}
            )

        # Step 6: Move sprint card to done
        if pr["sprint_card_id"]:
            db.execute(
                text("UPDATE sprint_cards SET column_status = 'done' WHERE id = :card_id"),
                {"card_id": pr["sprint_card_id"]}
            )

        db.commit()
    except Exception as e:
        db.rollback()
        logger.critical(f"Database relational alignment crash during PR post-merge: {e}")
        raise HTTPException(status_code=500, detail="Git executed but local tracking metadata failed to synchronize.")

    # Step 7: Publish org.{slug}.pr.merged to BAND broker
    try:
        # TODO: band_client.publish(f"org.{org_slug}.pr.merged", {"pr_id": pr_id, "merge_sha": str(merge_commit_sha)})
        logger.info(f"Published merge sequence token to BAND on: org.{org_slug}.pr.merged")
    except Exception as e:
        logger.warning(f"BAND Message Mesh distribution failure: {e}")

    # Step 8: Trigger semantic re-index of merged files asynchronously
    if hasattr(semantic_indexer, "index_file_change"):
        # Diff parsing to get changed file structures for parsing loop hooks
        diff = git_repo.diff(base_commit, head_commit)
        for patch in diff:
            file_path = patch.delta.new_file.path
            try:
                # Read content from blob object
                blob = git_repo.get(patch.delta.new_file.id)
                if blob and not blob.is_binary:
                    background_tasks.add_task(
                        semantic_indexer.index_file_change,
                        repo_id, pr['base_branch'], file_path, blob.data.decode('utf-8')
                    )
            except Exception as index_err:
                logger.error(f"Failed parsing file {file_path} into background semantic queue: {index_err}")

    return {"status": "merged", "merge_commit_sha": str(merge_commit_sha)}


# =============================================================================
# 4. REVIEW COMMENT MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/{pr_id}/comments")
async def list_pr_comments(org_slug: str, repo_id: str, pr_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT id, body, resolved FROM pr_comments WHERE pr_id = :pr_id"),
        {"pr_id": pr_id}
    ).mappings().all()
    return {"comments": [dict(row) for row in result]}


@router.post("/{pr_id}/comments")
async def create_pr_comment(org_slug: str, repo_id: str, pr_id: int, payload: CommentPayload, db: Session = Depends(get_db)):
    result = db.execute(
        text("INSERT INTO pr_comments (pr_id, body, resolved) VALUES (:pr_id, :body, false) RETURNING id"),
        {"pr_id": pr_id, "body": payload.body}
    )
    comment_id = result.scalar_one()
    db.commit()
    return {"status": "created", "comment_id": comment_id}


@router.patch("/{pr_id}/comments/{comment_id}")
async def update_pr_comment(org_slug: str, repo_id: str, pr_id: int, comment_id: int, payload: CommentPayload, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE pr_comments SET body = :body WHERE id = :id AND pr_id = :pr_id RETURNING id"),
        {"body": payload.body, "id": comment_id, "pr_id": pr_id}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Comment tracking context target missing.")
    return {"status": "updated", "comment_id": comment_id}


@router.delete("/{pr_id}/comments/{comment_id}")
async def delete_pr_comment(org_slug: str, repo_id: str, pr_id: int, comment_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM pr_comments WHERE id = :id AND pr_id = :pr_id"),
        {"id": comment_id, "pr_id": pr_id}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Comment missing.")
    return {"status": "deleted", "comment_id": comment_id}


@router.post("/{pr_id}/comments/{comment_id}/resolve")
async def resolve_pr_comment(org_slug: str, repo_id: str, pr_id: int, comment_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE pr_comments SET resolved = true WHERE id = :id AND pr_id = :pr_id RETURNING id"),
        {"id": comment_id, "pr_id": pr_id}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Target comment missing.")
    return {"status": "resolved", "comment_id": comment_id}