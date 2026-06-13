from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy import text
from database import get_db
from app.services.semantic_index import semantic_indexer
from pydantic import BaseModel
from app.routers.deps import get_current_user

router = APIRouter(prefix="/api/v1/orgs/{org_id}/issues", tags=["issues"])

class IssueCreateSchema(BaseModel):
    title: str
    description: str

@router.post("/index")
async def create_and_index_issue(
    org_id: UUID, 
    issue: IssueCreateSchema, 
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    combined_text = f"{issue.title}\n{issue.description}"
    vector_str = semantic_indexer.encode_text(combined_text)

    async with db.begin():
        res = await db.execute(
            text("""
            INSERT INTO issues (org_id, title, description, created_by)
            VALUES (:org_id, :title, :description, :created_by)
            RETURNING id;
            """),
            {
                "org_id": org_id,
                "title": issue.title,
                "description": issue.description,
                "created_by": current_user["id"]
            }
        )
        issue_id = res.scalar()
        
        await db.execute(
            text("""
            INSERT INTO issue_embeddings (issue_id, chunk_text, embedding, model_version)
            VALUES (:issue_id, :chunk_text, :embedding::vector, 'codebert-base-v1');
            """),
            {
                "issue_id": issue_id,
                "chunk_text": combined_text,
                "embedding": vector_str
            }
        )
    
    return {"status": "indexed", "issue_id": str(issue_id)}

@router.post("/search-similar")
async def search_similar_issues(org_id: UUID, payload: IssueCreateSchema, db=Depends(get_db)):
    combined_text = f"{payload.title}\n{payload.description}"
    vector_str = semantic_indexer.encode_text(combined_text)

    query = text("""
        SELECT
            ie.issue_id,
            ie.chunk_text,
            (ie.embedding <=> :embedding::vector) AS cosine_distance
        FROM issue_embeddings ie
        INNER JOIN issues i ON ie.issue_id = i.id
        WHERE i.org_id = :org_id
        ORDER BY ie.embedding <=> :embedding::vector ASC
        LIMIT 3;
    """)

    res = await db.execute(query, {"embedding": vector_str, "org_id": org_id})
    results = res.fetchall()

    return [
        {
            "issue_id": str(record.issue_id),
            "text": record.chunk_text,
            "score": 1 - record.cosine_distance
        }
        for record in results
    ]

