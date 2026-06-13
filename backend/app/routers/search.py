from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

router = APIRouter(prefix="/orgs/{org_slug}/search", tags=["Semantic Search & Retrieval"])

# --- Pydantic Schema for Search Requests ---
class SearchFilters(BaseModel):
    author: Optional[str] = None
    branch: Optional[str] = None
    date_from: Optional[str] = None

class SearchPayload(BaseModel):
    query: str
    limit: Optional[int] = 10
    filters: Optional[SearchFilters] = None


# =============================================================================
# SEMANTIC SEARCH LOGIC
# =============================================================================

def build_ann_query(base_query: str, filters: Optional[SearchFilters]) -> str:
    """Dynamically appends filtered SQL constraints before ANN vector search."""
    clauses = []
    if filters:
        if filters.author: clauses.append("author = :author")
        if filters.branch: clauses.append("branch = :branch")
        if filters.date_from: clauses.append("created_at >= :date_from")
    
    where_clause = " AND ".join(clauses)
    if where_clause:
        return base_query.replace("WHERE", f"WHERE {where_clause} AND")
    return base_query


@router.post("/code")
async def search_org_code(org_slug: str, payload: SearchPayload, db: Session = Depends(get_db)):
    """Performs an organization-wide semantic search across all repositories."""
    # Uses pgvector embedding distance operator (<->)
    sql = build_ann_query("""
        SELECT content, filepath, repo_id 
        FROM code_embeddings 
        WHERE org_slug = :org_slug
        ORDER BY embedding <-> embedding_function(:query)
        LIMIT :limit
    """, payload.filters)
    
    params = {"org_slug": org_slug, "query": payload.query, "limit": payload.limit}
    if payload.filters: params.update(payload.filters.model_dump())
    
    result = db.execute(text(sql), params).mappings().all()
    return {"results": [dict(row) for row in result]}


@router.post("/issues")
async def search_issues(org_slug: str, payload: SearchPayload, db: Session = Depends(get_db)):
    """Semantic search against issue tracking databases."""
    sql = build_ann_query("""
        SELECT issue_id, title, status 
        FROM issue_embeddings 
        WHERE org_slug = :org_slug
        ORDER BY embedding <-> embedding_function(:query)
        LIMIT :limit
    """, payload.filters)
    
    params = {"org_slug": org_slug, "query": payload.query, "limit": payload.limit}
    if payload.filters: params.update(payload.filters.model_dump())
    
    result = db.execute(text(sql), params).mappings().all()
    return {"results": [dict(row) for row in result]}


@router.post("/memory")
async def search_agent_memory(org_slug: str, payload: SearchPayload, db: Session = Depends(get_db)):
    """Performs semantic retrieval across agent memory logs."""
    sql = build_ann_query("""
        SELECT summary, importance_weight, agent_id 
        FROM agent_memory_embeddings 
        WHERE org_slug = :org_slug
        ORDER BY embedding <-> embedding_function(:query)
        LIMIT :limit
    """, payload.filters)
    
    params = {"org_slug": org_slug, "query": payload.query, "limit": payload.limit}
    if payload.filters: params.update(payload.filters.model_dump())
    
    result = db.execute(text(sql), params).mappings().all()
    return {"results": [dict(row) for row in result]}


# =============================================================================
# REPOSITORY-SPECIFIC SEARCH SCOPE
# =============================================================================

@router.post("/repos/{repo_id}/search/code")
async def search_repo_code(org_slug: str, repo_id: int, payload: SearchPayload, db: Session = Depends(get_db)):
    """Scopes the semantic search context to a single repository."""
    sql = build_ann_query("""
        SELECT content, filepath 
        FROM code_embeddings 
        WHERE org_slug = :org_slug AND repo_id = :repo_id
        ORDER BY embedding <-> embedding_function(:query)
        LIMIT :limit
    """, payload.filters)
    
    params = {"org_slug": org_slug, "repo_id": repo_id, "query": payload.query, "limit": payload.limit}
    if payload.filters: params.update(payload.filters.model_dump())
    
    result = db.execute(text(sql), params).mappings().all()
    return {"results": [dict(row) for row in result]}